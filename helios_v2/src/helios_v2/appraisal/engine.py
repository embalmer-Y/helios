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