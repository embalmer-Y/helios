"""Owner: rapid salience appraisal.

Owns:
- batch-level rapid appraisal orchestration
- estimator invocation order
- request and publication op construction

Does not own:
- permanent scoring strategy semantics
- fine semantic interpretation
- memory retrieval
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.sensory import Stimulus, StimulusBatch

from .contracts import (
    AssessStimulusBatchOp,
    PublishRapidAppraisalBatchOp,
    RapidAppraisal,
    RapidAppraisalBatch,
    RapidAppraisalError,
    RapidSalienceAppraisalAPI,
    RapidSalienceVector,
)


@dataclass(frozen=True)
class RapidDimensionEstimate:
    """Owner: rapid salience appraisal.

    Purpose:
        Hold coarse dimension estimates prior to aggregate judgment construction.

    Failure semantics:
        Values are validated when converted into `RapidSalienceVector`.
    """

    threat: float
    reward: float
    novelty: float
    social: float
    uncertainty: float


@runtime_checkable
class RapidDimensionEstimator(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Produce coarse dimension estimates for one normalized stimulus.
    """

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        """Owner: rapid salience appraisal.

        Purpose:
            Estimate threat, reward, novelty, social salience, and uncertainty.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A `RapidDimensionEstimate` without aggregate judgment.

        Raises:
            RapidAppraisalError if estimation cannot proceed safely.

        Notes:
            This interface is injected into the owner skeleton and is not a downstream public runtime API.
        """


@runtime_checkable
class AggregateJudgmentEstimator(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Produce the owner-level coarse aggregate judgment for one stimulus.
    """

    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        """Owner: rapid salience appraisal.

        Purpose:
            Estimate the aggregate coarse salience value.

        Inputs:
            One normalized `Stimulus` and one `RapidDimensionEstimate`.

        Returns:
            One aggregate salience score within the contract range.

        Raises:
            RapidAppraisalError if aggregate estimation cannot proceed safely.

        Notes:
            The caller must not assume a fixed formula; the owner controls how this estimator is supplied.
        """


@runtime_checkable
class MemorySimilaritySource(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Provide a memory-retrieval fact for novelty appraisal: the maximum cosine similarity
        of one stimulus to the system's stored experience. This is a retrieval fact, not a
        salience judgment; the novelty salience mapping stays owned by this owner.

    Notes:
        Injected into the owner. The concrete source (composition glue) reaches the embedding
        and persistence owners; this owner never imports them. Returning `None` means there is
        no comparable memory (empty stimulus content or a cold/all-non-embedded store).
    """

    def max_similarity_for(self, stimulus: Stimulus) -> float | None:
        """Owner: rapid salience appraisal (injected source).

        Purpose:
            Return the maximum cosine similarity of the stimulus to stored experience.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A cosine similarity in `[-1.0, 1.0]`, or `None` when there is no comparable memory.

        Raises:
            May propagate an embedding or store failure as a hard stop. It must not fabricate a
            similarity to mask a failure.

        Notes:
            This returns a raw retrieval fact only. The `novelty = 1 - similarity` mapping is
            owned by the appraisal owner, not by this source.
        """


@dataclass
class MemoryGroundedDimensionEstimator(RapidDimensionEstimator):
    """Owner: rapid salience appraisal.

    Purpose:
        Compute the novelty dimension from memory similarity while keeping the other four
        coarse dimensions at their first-version constant values. This is the P3 de-shim of the
        novelty dimension only.

    Failure semantics:
        Propagates any failure raised by the injected `MemorySimilaritySource` as a hard stop.
        It never falls back to a constant novelty when grounding is active.

    Notes:
        The novelty salience semantic lives here: `novelty = 1 - max_similarity`, clamped into
        the `RapidSalienceVector` range, and `None` (no comparable memory: empty content or a
        cold store) maps to maximum novelty `1.0` ("unlike anything remembered"). The four
        non-novelty dimensions remain constant first-version values and are the next de-shim
        slices. The aggregate judgment stays owned by the separate aggregate estimator.
    """

    similarity_source: MemorySimilaritySource
    threat: float = 0.2
    reward: float = 0.1
    social: float = 0.0
    uncertainty: float = 0.3

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        """Owner: rapid salience appraisal.

        Purpose:
            Estimate the coarse dimensions for one stimulus, with novelty derived from the
            injected memory-similarity fact and the other four dimensions held constant.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A `RapidDimensionEstimate` whose `novelty` reflects memory similarity.

        Raises:
            RapidAppraisalError is not raised here directly; an injected-source failure
            propagates as the source's own hard-stop error.

        Notes:
            `novelty = clamp(1 - max_similarity, 0, 1)`; a `None` similarity (no comparable
            memory) yields `1.0`. Deterministic given the same stimulus and stored vectors.
        """

        similarity = self.similarity_source.max_similarity_for(stimulus)
        if similarity is None:
            novelty = 1.0
        else:
            novelty = round(min(1.0, max(0.0, 1.0 - similarity)), 4)
        return RapidDimensionEstimate(
            threat=self.threat,
            reward=self.reward,
            novelty=novelty,
            social=self.social,
            uncertainty=self.uncertainty,
        )


def _validate_stimulus_batch(batch: StimulusBatch) -> None:
    if not batch.batch_id:
        raise RapidAppraisalError("StimulusBatch must declare a non-empty batch_id")
    for stimulus in batch.stimuli:
        if not stimulus.stimulus_id or not stimulus.source_name or not stimulus.provenance_signal_id:
            raise RapidAppraisalError("StimulusBatch contains stimulus with incomplete provenance")


@dataclass
class RapidSalienceAppraisalEngine(RapidSalienceAppraisalAPI):
    """Owner: rapid salience appraisal.

    Purpose:
        Execute batch-level rapid appraisal using injected dimension and aggregate estimators.

    Failure semantics:
        Malformed batches fail before estimator invocation. Estimator errors propagate as explicit appraisal failures.
    """

    dimension_estimator: RapidDimensionEstimator
    aggregate_estimator: AggregateJudgmentEstimator

    def assess_batch(self, batch: StimulusBatch) -> RapidAppraisalBatch:
        """Owner: rapid salience appraisal.

        Purpose:
            Consume one normalized stimulus batch and return one coarse appraisal batch.

        Inputs:
            A `StimulusBatch` emitted by sensory ingress.

        Returns:
            A `RapidAppraisalBatch` containing one appraisal per input stimulus.

        Raises:
            RapidAppraisalError when batch invariants or estimator outputs are invalid.

        Notes:
            Low-salience outputs remain valid results if provenance and score ranges are valid.
        """

        _validate_stimulus_batch(batch)

        appraisals = []
        for stimulus in batch.stimuli:
            dimensions = self.dimension_estimator.estimate_dimensions(stimulus)
            aggregate = self.aggregate_estimator.estimate_aggregate(stimulus, dimensions)
            salience = RapidSalienceVector(
                threat=dimensions.threat,
                reward=dimensions.reward,
                novelty=dimensions.novelty,
                social=dimensions.social,
                uncertainty=dimensions.uncertainty,
                aggregate=aggregate,
            )
            appraisals.append(RapidAppraisal.from_stimulus(stimulus, salience))

        return RapidAppraisalBatch(
            batch_id=f"rapid-appraisal-batch:{batch.batch_id}",
            appraisals=tuple(appraisals),
        )

    def build_assess_batch_op(self, batch: StimulusBatch) -> AssessStimulusBatchOp:
        """Owner: rapid salience appraisal.

        Purpose:
            Build the request op describing one appraisal request.

        Inputs:
            A `StimulusBatch` emitted by sensory ingress.

        Returns:
            An `AssessStimulusBatchOp` summarizing batch identity and source coverage.

        Raises:
            RapidAppraisalError if the batch is malformed.

        Notes:
            This method validates provenance before creating the request op.
        """

        _validate_stimulus_batch(batch)
        return AssessStimulusBatchOp(
            op_name="assess_stimulus_batch",
            owner="rapid_salience_appraisal",
            stimulus_batch_id=batch.batch_id,
            stimulus_count=len(batch.stimuli),
            source_names=tuple(sorted({stimulus.source_name for stimulus in batch.stimuli})),
        )

    def build_publish_batch_op(self, batch: RapidAppraisalBatch) -> PublishRapidAppraisalBatchOp:
        """Owner: rapid salience appraisal.

        Purpose:
            Build the publication op for one coarse appraisal batch.

        Inputs:
            A `RapidAppraisalBatch` produced by this owner.

        Returns:
            A `PublishRapidAppraisalBatchOp` summarizing publication metadata.

        Raises:
            RapidAppraisalError if the batch is malformed.

        Notes:
            Publication requires preserved appraisal provenance for every record.
        """

        if not batch.batch_id:
            raise RapidAppraisalError("RapidAppraisalBatch must declare a non-empty batch_id")
        source_names = []
        for appraisal in batch.appraisals:
            if not appraisal.appraisal_id or not appraisal.source_name or not appraisal.provenance_signal_id:
                raise RapidAppraisalError("RapidAppraisalBatch contains malformed appraisal provenance")
            source_names.append(appraisal.source_name)
        return PublishRapidAppraisalBatchOp(
            op_name="publish_rapid_appraisal_batch",
            owner="rapid_salience_appraisal",
            appraisal_batch_id=batch.batch_id,
            appraisal_count=len(batch.appraisals),
            source_names=tuple(sorted(set(source_names))),
        )