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
from typing import TYPE_CHECKING, Protocol, runtime_checkable

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

if TYPE_CHECKING:  # pragma: no cover - circular-import guard for the R80 estimator.
    from .r80_internal_monologue import InternalMonologueAppraisalEstimator


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


@dataclass
class WeightedAggregateEstimator(AggregateJudgmentEstimator):
    """Owner: rapid salience appraisal (R41).

    Purpose:
        Compute the aggregate coarse-salience judgment as a deterministic convex combination of
        the five real `03` dimensions, replacing the constant first-version shim. This closes the
        `03` owner's P3 de-shim: with R41 every `03` output (five dimensions + aggregate) is a real
        signal under the semantic-memory assembly.

    Failure semantics:
        Total deterministic function of the dimensions + config weights; it never branches into a
        degraded mode and never diverges outside `[0, 1]` (convex combination of in-range values
        plus a defensive clamp).

    Notes:
        The aggregate semantic is owned here, not in composition glue. The per-dimension weights
        are explicit first-version bounded constants summing to 1.0; they are a PLACEHOLDER
        allocation (an engineering choice, not a calibrated importance prior) and are the surface a
        later P5 learning slice or a model-assisted/non-linear overall appraisal replaces -- they
        must not be over-claimed. The combination is monotonic non-decreasing in each dimension and
        stateless (no prior-tick read). The aggregate inherits the grounding strength of its
        inputs: while threat/reward are the R40 `C_engineering_hypothesis` prototype anchor, the
        aggregate's threat/reward contribution is only as strong as that anchor; it strengthens
        automatically as the input dimensions are upgraded.
    """

    weight_threat: float = 0.25
    weight_reward: float = 0.25
    weight_novelty: float = 0.20
    weight_uncertainty: float = 0.15
    weight_social: float = 0.15

    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        """Return the convex-combination aggregate of the five dimensions, clamped to `[0, 1]`.

        Ignores `stimulus` (the aggregate is a function of the dimensions only in this slice).
        Deterministic and stateless.
        """

        del stimulus
        combined = (
            self.weight_threat * dimensions.threat
            + self.weight_reward * dimensions.reward
            + self.weight_novelty * dimensions.novelty
            + self.weight_uncertainty * dimensions.uncertainty
            + self.weight_social * dimensions.social
        )
        return round(min(1.0, max(0.0, combined)), 4)


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


@runtime_checkable
class RetrievalAmbiguitySource(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Provide a memory-retrieval fact for uncertainty appraisal: the top-N cosine
        similarities (descending) of one stimulus to stored experience. This is a raw retrieval
        fact, not a salience judgment; the uncertainty salience mapping stays owned by this owner.

    Notes:
        Injected into the owner. The concrete source (composition glue) reaches the embedding and
        persistence owners; this owner never imports them. Returning an empty tuple means there is
        no comparable memory (empty stimulus content or a cold/all-non-embedded store).
    """

    def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
        """Owner: rapid salience appraisal (injected source).

        Purpose:
            Return the top-N cosine similarities of the stimulus to stored experience, descending.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A tuple of cosine similarities in `[-1.0, 1.0]` ordered descending (length 0..N), or an
            empty tuple when there is no comparable memory.

        Raises:
            May propagate an embedding or store failure as a hard stop. It must not fabricate a
            similarity to mask a failure.

        Notes:
            This returns a raw retrieval fact only. The ambiguity-to-uncertainty mapping is owned
            by the appraisal owner, not by this source.
        """


@runtime_checkable
class SocialContextSource(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Provide a raw transport fact for social appraisal: a bounded social-presence value in
        `[0,1]` indicating whether one stimulus originates from an external interactive-agent
        channel (another subject). This is a transport fact, not a salience judgment; the social
        salience mapping stays owned by this owner.

    Notes:
        Injected into the owner. The concrete source (composition glue) owns the channel-to-presence
        classification because it wired the channels; this owner never hardcodes channel names and
        never imports the channel owner.
    """

    def social_presence_for(self, stimulus: Stimulus) -> float:
        """Owner: rapid salience appraisal (injected source).

        Purpose:
            Return the social-presence transport fact for one stimulus.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A bounded presence value in `[0.0, 1.0]` (external interactive-agent channel -> high;
            internal body/background -> low/zero).

        Raises:
            RapidAppraisalError-compatible failures may propagate; it must not fabricate presence.

        Notes:
            This returns a raw transport fact only. The presence-to-social mapping is owned by the
            appraisal owner, not by this source.
        """


def _normalize_cosine(value: float) -> float:
    """Map a cosine similarity in [-1, 1] to [0, 1]."""

    return min(1.0, max(0.0, (value + 1.0) / 2.0))


# First-version threat/reward prototype phrase sets owned by the `03` appraisal owner (R40).
# They encode the owner's first-version definition of "what counts as threat / reward" for the
# prototype-embedding scorer. They are an explicit, hand-authored, English-centric PLACEHOLDER
# anchor with `C_engineering_hypothesis` grounding -- NOT a calibrated affective model. They are
# the surface a later slice replaces (P5 learning of the prototypes/gains, a `06` memory-affect
# grounding scoring threat/reward from the outcomes of similar past experience, or a slow
# `11`-LLM second-stage re-appraisal). They must not be over-claimed as real threat/reward
# understanding.
THREAT_PROTOTYPES: tuple[str, ...] = (
    "a dangerous threat",
    "I am under attack",
    "this will cause harm",
    "an urgent emergency",
    "something is broken or failing",
)
REWARD_PROTOTYPES: tuple[str, ...] = (
    "a valuable reward",
    "this is helpful and good",
    "a successful achievement",
    "a positive useful outcome",
    "something beneficial and worthwhile",
)


@runtime_checkable
class PrototypeSimilaritySource(Protocol):
    """Owner: rapid salience appraisal.

    Purpose:
        Provide a mechanical similarity fact for threat/reward appraisal: the maximum cosine
        similarity of one stimulus to any phrase in an owner-provided prototype set. This is a
        mechanical fact, not a salience judgment; the prototype set and the cosine-to-salience
        mapping stay owned by this owner.

    Notes:
        Injected into the owner. The concrete source (composition glue) embeds the owner-provided
        phrases and the stimulus through the embedding callable and computes cosine; this owner
        never imports the embedding owner. The source does not know that one set means "threat"
        and another "reward" -- the owner passes the sets and owns their meaning. Returning `None`
        means there is no comparable input (empty stimulus content).
    """

    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        """Return the max cosine similarity of the stimulus to any prototype phrase, or `None`.

        `None` indicates no comparable input (empty stimulus content). The raw cosine fact carries
        no salience semantic; the prototype-to-salience mapping is owned by the appraisal owner.
        """


@dataclass
class GroundedDimensionEstimator(RapidDimensionEstimator):
    """Owner: rapid salience appraisal.

    Purpose:
        Compute all five `03` dimensions from injected raw facts. This is the P3 cognitive-owner
        de-shim of the appraisal dimensions: novelty (R35), uncertainty + social (R39), and
        threat + reward (R40). With R40 all five dimensions are real under the semantic-memory
        assembly; none remain first-version constants here.

    Failure semantics:
        Propagates any failure raised by an injected source as a hard stop. It never falls back to
        a constant dimension when grounding is active.

    Notes:
        All three salience mappings live here, in the owner, not in composition glue:
        - novelty = clamp(1 - max_similarity, 0, 1); `None` (no comparable memory) -> 1.0 (R35
          semantics, unchanged).
        - uncertainty = retrieval ambiguity: with no comparable memory (empty top similarities)
          -> 1.0; otherwise, with `n1`/`n2` the top two cosines normalized to [0,1]
          (`n2 = 0.0` if only one hit), uncertainty = clamp(1 - (n1 - n2), 0, 1). A single
          dominant match -> low uncertainty; several near-equal matches -> high uncertainty. This
          is a distinct read of the retrieval result from novelty (which reads only the top match).
          Grounding is `B_functional_inspiration`: retrieval ambiguity is a functional proxy for
          categorization uncertainty, not a calibrated confidence.
        - social = clamp(social_floor + social_gain * social_presence, 0, 1) from the raw transport
          presence fact. Social is a transport fact and does not require the embedding/store
          substrate; it is bundled under the same opt-in here only to keep one rollout switch.
        - threat / reward = clamp(gain * max(0.0, max_cosine_to_prototypes), 0, 1) from the
          prototype-similarity fact (R40). Positive correlation: a stimulus more similar to the
          owner's threat/reward prototype phrases scores higher; only positive similarity
          contributes; `None` (empty content) -> 0.0. The prototype phrase sets
          (`THREAT_PROTOTYPES`/`REWARD_PROTOTYPES`) and this mapping are owned here. Grounding is
          `C_engineering_hypothesis`: the prototype set is a hand-authored, English-centric
          PLACEHOLDER anchor, not a calibrated affective model; it is the surface a later P5 /
          `06` memory-affect / `11`-LLM-re-appraisal slice replaces. It must not be over-claimed.
        The aggregate judgment stays owned by the separate aggregate estimator. Stateless: no
        prior-tick read. No cold-start for threat/reward (prototypes are fixed, embedded once by
        the source).
    """

    similarity_source: MemorySimilaritySource
    ambiguity_source: RetrievalAmbiguitySource
    social_source: SocialContextSource
    prototype_source: PrototypeSimilaritySource
    threat_prototypes: tuple[str, ...] = THREAT_PROTOTYPES
    reward_prototypes: tuple[str, ...] = REWARD_PROTOTYPES
    threat_gain: float = 1.0
    reward_gain: float = 1.0
    social_floor: float = 0.0
    social_gain: float = 1.0

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        """Owner: rapid salience appraisal.

        Purpose:
            Estimate the coarse dimensions for one stimulus, with novelty/uncertainty derived from
            injected memory-retrieval facts, social from the injected transport fact, and
            threat/reward from the injected prototype-similarity fact.

        Inputs:
            One normalized `Stimulus`.

        Returns:
            A `RapidDimensionEstimate` whose `novelty`, `uncertainty`, and `social` reflect real
            facts.

        Raises:
            Propagates an injected-source failure as a hard stop.

        Notes:
            Deterministic given the same stimulus, stored vectors, and transport provenance. Reads
            no prior-tick state.
        """

        similarity = self.similarity_source.max_similarity_for(stimulus)
        if similarity is None:
            novelty = 1.0
        else:
            novelty = round(min(1.0, max(0.0, 1.0 - similarity)), 4)

        top_similarities = self.ambiguity_source.top_similarities_for(stimulus)
        if not top_similarities:
            uncertainty = 1.0
        else:
            n1 = _normalize_cosine(top_similarities[0])
            n2 = _normalize_cosine(top_similarities[1]) if len(top_similarities) > 1 else 0.0
            uncertainty = round(min(1.0, max(0.0, 1.0 - (n1 - n2))), 4)

        social_presence = self.social_source.social_presence_for(stimulus)
        social = round(
            min(1.0, max(0.0, self.social_floor + self.social_gain * social_presence)),
            4,
        )

        threat_fact = self.prototype_source.max_similarity_to(stimulus, self.threat_prototypes)
        threat = (
            0.0
            if threat_fact is None
            else round(min(1.0, max(0.0, self.threat_gain * max(0.0, threat_fact))), 4)
        )
        reward_fact = self.prototype_source.max_similarity_to(stimulus, self.reward_prototypes)
        reward = (
            0.0
            if reward_fact is None
            else round(min(1.0, max(0.0, self.reward_gain * max(0.0, reward_fact))), 4)
        )

        return RapidDimensionEstimate(
            threat=threat,
            reward=reward,
            novelty=novelty,
            social=social,
            uncertainty=uncertainty,
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
    internal_monologue_estimator: "InternalMonologueAppraisalEstimator | None" = None

    def _estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        """Owner: rapid salience appraisal.

        Purpose:
            Per-modality dispatch for the dimension estimator. The R80 design adds a
            per-modality override: when `internal_monologue_estimator` is injected and
            the stimulus modality is `"internal_monologue"`, the engine routes to the
            internal-monologue estimator; otherwise it falls back to the default
            `dimension_estimator`. This preserves the existing P3 de-shim path for
            all other modalities (semantic-memory grounding, prototype-similarity
            scoring, etc.).
        """
        if (
            self.internal_monologue_estimator is not None
            and stimulus.modality == "internal_monologue"
        ):
            return self.internal_monologue_estimator.estimate_dimensions(stimulus)
        return self.dimension_estimator.estimate_dimensions(stimulus)

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
            dimensions = self._estimate_dimensions(stimulus)
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