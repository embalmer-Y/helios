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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from helios_v2.sensory import Stimulus, StimulusBatch

# The R97 `anchor_catalog` is a runtime-injected field on `GroundedDimensionEstimator`;
# the import here is intentionally lazy to break the `engine` <-> `anchor_catalog`
# import cycle (catalog also imports `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` from
# this module). The default value is resolved by `GroundedDimensionEstimator`'s
# `__post_init__`-equivalent dataclass field default, which is a function call:
# we use a sentinel `_ANCHOR_CATALOG_SENTINEL` here and resolve to
# `DEFAULT_ANCHOR_CATALOG` lazily at first construction.

from .contracts import (
    AssessStimulusBatchOp,
    PublishRapidAppraisalBatchOp,
    RapidAppraisal,
    RapidAppraisalBatch,
    RapidAppraisalError,
    RapidSalienceAppraisalAPI,
    RapidSalienceVector,
)

if TYPE_CHECKING:
    from .anchor_catalog import AnchorCatalog
    from .concept_state import ConceptPrior, DEFAULT_CONCEPTS as _DEFAULT_CONCEPTS, EmotionConcept


@runtime_checkable
class InteroceptionSource(Protocol):
    """Owner: rapid salience appraisal (R-PROTO-LEARN.1).

    Purpose:
        Provide a hormone-state-derived interoception snapshot for appraisal
        adjustment. R36 already maps appraisal -> hormone (one direction);
        R-PROTO-LEARN.1 closes the OTHER direction by feeding the current
        hormone state back into appraisal (the body-as-context reading).
        This mirrors the cortical-amygdalar feedback loop: the amygdala's
        salience read is partly informed by current body state, not only
        by external stimulus features.

    Notes:
        Injected into the owner. The concrete source (composition glue)
        reaches the neuromodulator owner; this owner never imports it.
        Returning `None` means "no interoception data available" (cold
        start or non-running neuromodulator subsystem), in which case
        the appraisal falls back to stimulus-only scoring.
    """

    def hormone_state_snapshot(self) -> "Mapping[str, float] | None":
        """Return the current 9-channel hormone state as `{channel: value}` in [0, 1].

        Returns `None` if no hormone state is available (cold start).
        """


def _resolve_default_concepts() -> tuple["EmotionConcept", ...]:  # pragma: no cover - trivial
    """Lazy import of DEFAULT_CONCEPTS to break engine <-> concept_state cycle."""
    from .concept_state import DEFAULT_CONCEPTS as _CATALOG
    return _CATALOG


def _resolve_default_concept_prior() -> "ConceptPrior":  # pragma: no cover - trivial
    """Lazy import of ConceptPrior.empty() to break engine <-> concept_state cycle."""
    from .concept_state import ConceptPrior as _CP
    return _CP.empty()


@runtime_checkable
class LlmAppraisalSource(Protocol):
    """Owner: rapid salience appraisal (R-PROTO-LEARN.2).

    Purpose:
        Provide a Layer 2 LLM-driven appraisal fallback for cases where
        Layer 1 (R40 + R97/R98 + R-PROTO-LEARN.6 + R-PROTO-LEARN.1) is
        ambiguous. The LLM directly emits 5-dimension scores
        `{threat, reward, novelty, social, uncertainty}` in `[0, 1]`
        for the given stimulus content, without consulting memory or
        prior emotion concepts. This is the "amygdala fast path":
        the system-2 reasoning (LLM) is invoked when the system-1
        (deterministic prototypes + RAG + interoception) cannot
        produce a confident read.

    Notes:
        Injected into the owner. The concrete implementation lives in
        a higher-level composition glue module that bridges to the LLM
        gateway; this owner never imports the gateway directly (preserves
        owner 02's no-LLM-dependency boundary). Returning `None` or an
        empty dict means "LLM appraisal unavailable" (gateway down,
        timeout, refusal), in which case the owner falls back to
        Layer 1's best-effort read (R40 + R-PROTO-LEARN.6 + .1).
    """

    def llm_appraise(
        self, content: str
    ) -> "Mapping[str, float] | None":
        """Return LLM-appraised 5-dim scores for `content`, or `None` if unavailable.

        The returned dict may have any subset of the 5 keys; missing
        keys are filled with the Layer 1 fallback value. Out-of-range
        values are clamped by the owner. The implementation is
        expected to be cheap (one LLM call) and synchronous.
        """


# R-PROTO-LEARN.2 (Layer 2 trigger heuristic): when Layer 1's best
# confidence is below this threshold, the owner asks the LLM source
# for a fresh appraisal. The default 0.4 was chosen empirically: R40
# prototypes for ZH yield 0.5-0.9 cosine on clearly-threat stimuli,
# but 0.0-0.3 on ambiguous ones, so 0.4 is a conservative cut
# (Layer 2 fires only when Layer 1 is uncertain).
R_PROTO_LEARN_2_DEFAULT_LLM_TRIGGER_THRESHOLD: float = 0.4


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


def _max_of_two_scaled(
    a: float | None, b: float | None, gain: float
) -> float:
    """R97 helper: take the max of two optional cosine facts, then scale by `gain`.

    Both `a` and `b` are optional (`None` means "no comparable input"); the result is
    `0.0` only when **both** are `None`. When at least one is present, the larger
    (positive-only, clamped to [0, 1] after the gain) wins. This implements the R97
    owner-side "max-of-max across (R40 prototypes) and (anchor catalog)" pattern
    without leaking catalog awareness into the composition source: the owner asks
    the source for the max cosine of two separate prototype tuples and combines
    them here.

    Notes:
        Owner-internal helper. Not exported on the public surface.
    """

    candidates: list[float] = []
    for value in (a, b):
        if value is not None:
            candidates.append(max(0.0, value))
    if not candidates:
        return 0.0
    return round(min(1.0, max(0.0, gain * max(candidates))), 4)


def _max_of_three_scaled(
    a: float | None, b: float | None, c: float | None, gain: float
) -> float:
    """R-PROTO-LEARN.6 helper: max of three optional cosine facts, scaled by `gain`.

    Extends the R97 `_max_of_two_scaled` pattern to add a third cosine fact —
    typically the R-PROTO-LEARN.6 description-fallback cosine (EmoGist
    context-dependent retrieval). `None` facts are skipped; the result is
    `0.0` only when **all three** are `None`. Owner-internal helper.
    """

    candidates: list[float] = []
    for value in (a, b, c):
        if value is not None:
            candidates.append(max(0.0, value))
    if not candidates:
        return 0.0
    return round(min(1.0, max(0.0, gain * max(candidates))), 4)


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


# R97: lazily resolve the default anchor catalog. This helper is called from
# `GroundedDimensionEstimator.anchor_catalog` `default_factory`; the lazy import
# is required because `appraisal.anchor_catalog` imports `THREAT_PROTOTYPES` /
# `REWARD_PROTOTYPES` from this module. By the time `default_factory` runs,
# this module is fully initialized, so the back-import is safe.
def _resolve_default_anchor_catalog() -> AnchorCatalog:  # pragma: no cover - trivial
    from .anchor_catalog import DEFAULT_ANCHOR_CATALOG as _CATALOG
    return _CATALOG


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

          R97 (去英文中心 / 中文 appraisal grounding) extends this with a multilingual
          `anchor_catalog: AnchorCatalog` (default `DEFAULT_ANCHOR_CATALOG`, bilingual
          Chinese + English). The owner-owned threat / reward scoring now takes
          `max(R40 prototypes_max, catalog_dimension_max)` across the two candidate
          phrase sets, so a Chinese emotion input scoring near-zero against the
          English R40 anchors can still score highly against the Chinese catalog
          anchors. The catalog is the clean P5 learned-catalog replacement seam
          (a P5 learned catalog is just `AnchorCatalog(sets=learned_sets)` injected
          at the same composition seam). When `anchor_catalog` is the default
          `DEFAULT_ANCHOR_CATALOG`, the R40 path remains byte-level equivalent for
          English inputs (the English subset of the default catalog aliases
          `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES`); the catalog only adds new
          Chinese coverage. Composition injects the catalog; the appraisal owner
          consumes it via `phrases_for(dimension)` and owns which dimension
          string maps to which salience.
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
    # R97: anchor catalog is resolved lazily (default_factory) to break the
    # `engine` <-> `anchor_catalog` import cycle. The default is `DEFAULT_ANCHOR_CATALOG`,
    # which is a frozen bilingual catalog (Chinese + English) built from this module's
    # R40 constants + the hand-authored Chinese anchors in `appraisal.anchor_catalog`.
    anchor_catalog: AnchorCatalog = field(
        default_factory=lambda: _resolve_default_anchor_catalog()
    )
    threat_gain: float = 1.0
    reward_gain: float = 1.0
    social_floor: float = 0.0
    social_gain: float = 1.0
    # R-PROTO-LEARN.6 (Layer 1 fallback, EmoGist context-dependent retrieval):
    # when the best phrase-level cosine (across R40 + catalog phrases) is below
    # this threshold AND the catalog has descriptions for this dimension,
    # the estimator also queries the description embeddings and takes the
    # max-of-three (prototype_max, phrase_max, description_max). A HIGHER
    # threshold = MORE aggressive fallback (description runs whenever phrase
    # match is "not strong enough"); a LOWER threshold = MORE conservative.
    # - threshold=1.0 (default): description ALWAYS runs when descriptions exist.
    # - threshold=0.0: description never runs (effectively disabled).
    # The default is 1.0 (always fallback) because that matches the R-PROTO-LEARN.6
    # design intent: the description path is always on by default and only the
    # catalog's description availability gates it.
    description_threshold: float = 1.0
    # R-PROTO-LEARN.5 (Layer 5 learning, Bayesian update):
    # the appraisal owner maintains a mutable ConceptPrior across ticks.
    # The frozen dataclass constraint requires the field itself to be a
    # single-element list (the list is mutable, the dataclass field is
    # frozen). `concept_prior[0]` is the live prior; updates via
    # `observe(estimate)` replace it in-place.
    # Default: empty prior (zero counts); seeded via `observe()` or via
    # `seed_prior(concepts)` to initialize from the DEFAULT_CONCEPTS taxonomy.
    concept_prior: list["ConceptPrior"] = field(
        default_factory=lambda: [_resolve_default_concept_prior()]
    )
    # The concepts taxonomy used by the heuristic observation mapping. By
    # default = DEFAULT_CONCEPTS. Tests can inject a smaller taxonomy.
    concepts: tuple["EmotionConcept", ...] = field(
        default_factory=lambda: _resolve_default_concepts()
    )
    # Bayesian learning rate (multiplier on observation weight). 1.0 = full
    # learning; 0.0 = effectively disabled. Tunable per deployment.
    concept_learning_rate: float = 1.0
    # R-PROTO-LEARN.1 (Layer 1 interoception, Active Inference):
    # the appraisal owner reads the current hormone state via an injected
    # `interoception_source` and applies a bounded bias to the output.
    # R36 already maps appraisal -> hormone (this owner is the consumer
    # there); R-PROTO-LEARN.1 closes the OTHER direction (hormone -> appraisal).
    # This is the cortical-amygdalar feedback loop: the amygdala's
    # salience read is partly informed by current body state, not only by
    # external stimulus features. A `None` source means no interoception
    # path (cold start or non-running neuromodulator subsystem); the
    # appraisal then falls back to stimulus-only scoring (R40 path).
    interoception_source: InteroceptionSource | None = None
    # Interoception gain: scales the hormone-derived bias. 0.0 = disabled
    # (R40 byte-level preservation on interoception axis); 1.0 = full
    # effect per the mapping table. Default 0.1 keeps the influence
    # bounded (single-tick per-channel cap ≤ 0.10 per the R98 magnitude
    # cap convention).
    interoception_gain: float = 0.1
    # R-PROTO-LEARN.2 (Layer 2 LLM-driven appraisal, the "amygdala
    # fast path"): when Layer 1's best confidence is below
    # `llm_appraisal_threshold`, the owner consults an injected
    # `llm_appraisal_source` for a fresh 5-dim read. A `None` source
    # means no Layer 2 path; the owner then falls back to Layer 1
    # only. This is a per-tick opt-in (the trigger heuristic is
    # owner-internal; the LLM call is delegated to the injected
    # source, preserving owner 02's no-LLM-dependency boundary).
    llm_appraisal_source: LlmAppraisalSource | None = None
    # Layer 2 trigger threshold: the Layer 1 max-of-three confidence
    # must be below this for the LLM to be consulted. Default 0.4
    # matches `R_PROTO_LEARN_2_DEFAULT_LLM_TRIGGER_THRESHOLD` and
    # is the empirical boundary between "confident R40 + R97/R98
    # read" (≥ 0.4) and "ambiguous, ask the LLM" (< 0.4). Set to
    # 0.0 to disable Layer 2 firing (R40 byte-level preservation
    # on the appraisal axis); set to 1.0 to always fire (Layer 2
    # dominates Layer 1).
    llm_appraisal_threshold: float = R_PROTO_LEARN_2_DEFAULT_LLM_TRIGGER_THRESHOLD
    # Layer 2 confidence blending: when Layer 2 fires, the final
    # estimate is `blend_alpha * layer_1 + (1 - blend_alpha) * layer_2`.
    # Default 0.5 = equal weight. 1.0 = Layer 1 dominates (LLM is a
    # tie-breaker); 0.0 = Layer 2 dominates (LLM overrides R40).
    # The default keeps both layers' contributions visible, which
    # is the conservative ship for R-PROTO-LEARN.2.
    llm_appraisal_blend_alpha: float = 0.5

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
        # R97 (中文 appraisal grounding): also query the owner-owned anchor catalog
        # for the same dimension, and take the max across (R40 prototypes) and
        # (catalog phrases). When the catalog is the default `DEFAULT_ANCHOR_CATALOG`,
        # the English subset aliases the R40 module constants, so the English-only
        # path remains byte-level equivalent; the catalog only adds Chinese coverage.
        catalog_threat_phrases = self.anchor_catalog.phrases_for("threat")
        catalog_threat_fact = (
            self.prototype_source.max_similarity_to(stimulus, catalog_threat_phrases)
            if catalog_threat_phrases
            else None
        )
        # R-PROTO-LEARN.6 (Layer 1 fallback, EmoGist context-dependent retrieval):
        # when (phrase-level max across R40 + catalog phrases) is BELOW
        # `description_threshold` AND the catalog has descriptions for this
        # dimension, also query the description embeddings. The final threat
        # value takes the max-of-three (prototype_max, phrase_max, description_max).
        # Gate: `phrase_max < threshold` => description path runs.
        # Semantics: a HIGHER threshold = MORE aggressive fallback.
        #   - threshold=1.0 (default): any phrase_max < 1.0 triggers => always fallback.
        #   - threshold=0.0: phrase_max < 0.0 is impossible => never fallback.
        phrase_threat_max = max(
            (v for v in (threat_fact, catalog_threat_fact) if v is not None),
            default=0.0,
        )
        threat_description_fact: float | None = None
        if phrase_threat_max < self.description_threshold:
            catalog_threat_descriptions = self.anchor_catalog.descriptions_for("threat")
            if catalog_threat_descriptions:
                threat_description_fact = self.prototype_source.max_similarity_to(
                    stimulus, catalog_threat_descriptions
                )
        threat = _max_of_three_scaled(
            threat_fact, catalog_threat_fact, threat_description_fact, self.threat_gain
        )

        reward_fact = self.prototype_source.max_similarity_to(stimulus, self.reward_prototypes)
        catalog_reward_phrases = self.anchor_catalog.phrases_for("reward")
        catalog_reward_fact = (
            self.prototype_source.max_similarity_to(stimulus, catalog_reward_phrases)
            if catalog_reward_phrases
            else None
        )
        phrase_reward_max = max(
            (v for v in (reward_fact, catalog_reward_fact) if v is not None),
            default=0.0,
        )
        reward_description_fact: float | None = None
        if phrase_reward_max < self.description_threshold:
            catalog_reward_descriptions = self.anchor_catalog.descriptions_for("reward")
            if catalog_reward_descriptions:
                reward_description_fact = self.prototype_source.max_similarity_to(
                    stimulus, catalog_reward_descriptions
                )
        reward = _max_of_three_scaled(
            reward_fact, catalog_reward_fact, reward_description_fact, self.reward_gain
        )

        estimate = RapidDimensionEstimate(
            threat=threat,
            reward=reward,
            novelty=novelty,
            social=social,
            uncertainty=uncertainty,
        )
        # R-PROTO-LEARN.5 (Layer 5 learning, Bayesian update): after the
        # dimension estimate is computed, apply one observation step to
        # the concept prior. The observation mapping is owner-internal
        # (`observe_dimension`); it activates threat/reward concepts
        # proportional to the magnitude of the corresponding dimension.
        # Updates are no-ops when both threat and reward are at/below 0.5.
        self._auto_observe(estimate)
        # R-PROTO-LEARN.1 (Layer 1 interoception, Active Inference):
        # apply a bounded hormone-derived bias to the estimate. The
        # bias is computed by `_apply_interoception` from the current
        # hormone state via `interoception_source`. Returns a NEW
        # `RapidDimensionEstimate` (the original is not mutated); the
        # estimate passed to `_auto_observe` above is the pre-bias
        # version (concept observation is driven by the stimulus-only
        # read, not the body-modulated one — this keeps the prior
        # strictly tied to "what the input actually was" rather than
        # the body's amplification).
        adjusted = self._apply_interoception(estimate)
        # R-PROTO-LEARN.2 (Layer 2 LLM appraisal, "amygdala fast path"):
        # when Layer 1's best confidence is below the configured
        # threshold AND an LLM source is injected, consult the LLM
        # and blend its read with the Layer 1 read. The pre-bias
        # `estimate` is the Layer 1 base; the post-bias `adjusted`
        # is the body-modulated Layer 1 read. The LLM output
        # represents the system-2 / LLM-driven "what does this
        # actually feel like" read; the blend keeps both layers
        # in play by default. Returns a NEW `RapidDimensionEstimate`;
        # the inputs are not mutated.
        blended = self._apply_llm_appraisal(stimulus, adjusted)
        return blended

    # --------------------------------------------------------------------- #
    # R-PROTO-LEARN.5 public surface: observation + distribution read-back. #
    # --------------------------------------------------------------------- #

    def _auto_observe(self, estimate: RapidDimensionEstimate) -> None:
        """Owner-internal: apply one observation step derived from `estimate`.

        Called at the end of `estimate_dimensions`. Updates the prior's
        counts via `bayesian_update` with the heuristic mapping from the
        owner-internal `observe_dimension(threat, reward, concepts)` helper.
        Mutates `self.concept_prior[0]` in place (the field is a 1-element
        list; the frozen dataclass is preserved by mutating only the list).
        """
        from .concept_state import bayesian_update as _bayesian_update, observe_dimension as _observe
        observation = _observe(estimate.threat, estimate.reward, self.concepts)
        if observation:
            prior = self.concept_prior[0]
            new_prior = _bayesian_update(prior, observation)
            self.concept_prior[0] = new_prior

    # --------------------------------------------------------------------- #
    # R-PROTO-LEARN.1 public surface: interoception adjustment.            #
    # --------------------------------------------------------------------- #

    def _apply_interoception(
        self, estimate: RapidDimensionEstimate
    ) -> RapidDimensionEstimate:
        """Owner-internal: apply a hormone-derived bias to `estimate`.

        The bias mapping (first-version, R-PROTO-LEARN.1 ship):
        - cortisol > 0.7 (high stress): threat += +0.05 * gain
        - cortisol < 0.3 (low stress):  threat += -0.02 * gain
        - oxytocin > 0.7 (high bond):   reward += +0.05 * gain
        - oxytocin < 0.3 (low bond):    reward += -0.02 * gain
        - serotonin > 0.7 (calm):       uncertainty += -0.03 * gain
        - dopamine > 0.7 (high):        novelty += -0.03 * gain
        - norepinephrine > 0.7 (alert): uncertainty += +0.04 * gain
        - inhibition > 0.7 (gated):     novelty += +0.04 * gain

        Each bias is clamped to the per-dimension `[0, 1]` range. The
        final estimate is a NEW `RapidDimensionEstimate` (the input is
        not mutated). When `interoception_source is None` or returns
        `None`, the input is returned unchanged (cold-start semantics).

        The mapping is heuristic (R-PROTO-LEARN.1 ship); a future P5
        learning loop can replace it with a learned mapping. The
        gain keeps the total per-tick influence bounded (default
        0.1 * 0.05 = 0.005 per channel, well under the R98 ±0.10
        per-tick cap).
        """
        if self.interoception_source is None or self.interoception_gain == 0.0:
            return estimate
        state = self.interoception_source.hormone_state_snapshot()
        if state is None:
            return estimate
        gain = self.interoception_gain
        threat = estimate.threat
        reward = estimate.reward
        novelty = estimate.novelty
        uncertainty = estimate.uncertainty
        social = estimate.social

        cortisol = state.get("cortisol")
        if cortisol is not None:
            if cortisol > 0.7:
                threat += 0.05 * gain
            elif cortisol < 0.3:
                threat -= 0.02 * gain
        oxytocin = state.get("oxytocin")
        if oxytocin is not None:
            if oxytocin > 0.7:
                reward += 0.05 * gain
            elif oxytocin < 0.3:
                reward -= 0.02 * gain
        serotonin = state.get("serotonin")
        if serotonin is not None and serotonin > 0.7:
            uncertainty -= 0.03 * gain
        dopamine = state.get("dopamine")
        if dopamine is not None and dopamine > 0.7:
            novelty -= 0.03 * gain
        norepinephrine = state.get("norepinephrine")
        if norepinephrine is not None and norepinephrine > 0.7:
            uncertainty += 0.04 * gain
        inhibition = state.get("inhibition")
        if inhibition is not None and inhibition > 0.7:
            novelty += 0.04 * gain

        return RapidDimensionEstimate(
            threat=round(min(1.0, max(0.0, threat)), 4),
            reward=round(min(1.0, max(0.0, reward)), 4),
            novelty=round(min(1.0, max(0.0, novelty)), 4),
            uncertainty=round(min(1.0, max(0.0, uncertainty)), 4),
            social=round(min(1.0, max(0.0, social)), 4),
        )

    def interoception_bias(
        self, estimate: RapidDimensionEstimate
    ) -> RapidDimensionEstimate:
        """Public surface: apply the interoception adjustment to `estimate`.

        Same as `_apply_interoception` but exposed for callers who want
        to re-run the adjustment on an external estimate (e.g. a replayed
        estimate from a saved batch).

        Returns a NEW `RapidDimensionEstimate`; the input is not mutated.
        """
        return self._apply_interoception(estimate)

    # --------------------------------------------------------------------- #
    # R-PROTO-LEARN.2 public surface: LLM appraisal fallback.              #
    # --------------------------------------------------------------------- #

    def _layer1_confidence(self, estimate: RapidDimensionEstimate) -> float:
        """Owner-internal: compute Layer 1's best-confidence scalar from `estimate`.

        The confidence is the maximum dimension value. This is a
        coarse signal (R40 + R97/R98 + R-PROTO-LEARN.6 + .1's
        evidence) — a stimulus with any dimension scoring ≥
        `llm_appraisal_threshold` is considered "Layer 1 is
        confident enough; do not bother the LLM".

        Notes:
            The 0.4 default threshold is empirically calibrated for
            ZH threat stimuli (R40 + R97 ZH anchors score 0.5-0.9
            on clear threats, 0.0-0.3 on ambiguous). EN may differ;
            deployments can tune the threshold without touching
            owner-internal logic.
        """
        return max(
            estimate.threat,
            estimate.reward,
            estimate.novelty,
            estimate.uncertainty,
            estimate.social,
        )

    def _apply_llm_appraisal(
        self, stimulus: Stimulus, layer1: RapidDimensionEstimate
    ) -> RapidDimensionEstimate:
        """Owner-internal: consult the LLM source when Layer 1 is uncertain.

        Trigger condition: `layer1`'s best confidence is below
        `llm_appraisal_threshold` AND `llm_appraisal_source` is not
        `None`. When the LLM is consulted, its 5-dim read is blended
        with `layer1` via `llm_appraisal_blend_alpha`:

            final = alpha * layer1 + (1 - alpha) * llm_read

        Each dimension is filled by the LLM read if the LLM provides
        the key, otherwise the Layer 1 value is used. All values
        are clamped to `[0, 1]` and rounded to 4 decimal places.

        Returns a NEW `RapidDimensionEstimate`; inputs are not mutated.
        When the LLM source is unavailable / returns `None` / returns
        an empty dict, `layer1` is returned unchanged (Layer 1 only).
        """
        if self.llm_appraisal_source is None:
            return layer1
        confidence = self._layer1_confidence(layer1)
        if confidence >= self.llm_appraisal_threshold:
            return layer1
        content = getattr(stimulus, "content", None) or ""
        if not content:
            return layer1
        llm_read = self.llm_appraisal_source.llm_appraise(content)
        if not llm_read:
            return layer1
        alpha = self.llm_appraisal_blend_alpha
        return RapidDimensionEstimate(
            threat=self._blend_dim("threat", layer1, llm_read, alpha),
            reward=self._blend_dim("reward", layer1, llm_read, alpha),
            novelty=self._blend_dim("novelty", layer1, llm_read, alpha),
            uncertainty=self._blend_dim("uncertainty", layer1, llm_read, alpha),
            social=self._blend_dim("social", layer1, llm_read, alpha),
        )

    def _blend_dim(
        self,
        dim: str,
        layer1: RapidDimensionEstimate,
        llm_read: "Mapping[str, float]",
        alpha: float,
    ) -> float:
        """Owner-internal helper: blend one dimension, clamp + round."""
        layer1_val = getattr(layer1, dim)
        llm_val = llm_read.get(dim, layer1_val)
        try:
            llm_val = float(llm_val)
        except (TypeError, ValueError):
            llm_val = layer1_val
        blended = alpha * layer1_val + (1.0 - alpha) * llm_val
        return round(min(1.0, max(0.0, blended)), 4)

    def llm_appraisal_blend(
        self, stimulus: Stimulus, layer1: RapidDimensionEstimate
    ) -> RapidDimensionEstimate:
        """Public surface: re-run the Layer 2 LLM blend for an external stimulus + Layer 1 read.

        Returns a NEW `RapidDimensionEstimate`; the inputs are not mutated.
        The LLM is only consulted when `layer1`'s best confidence is
        below `llm_appraisal_threshold` (same trigger as the inline
        path in `estimate_dimensions`).
        """
        return self._apply_llm_appraisal(stimulus, layer1)

    def observe(self, observation: "Mapping[str, float]") -> None:
        """Public surface: explicit Bayesian update with caller-supplied observation.

        `observation` is `{concept_name: weight}` (weight >= 0). Use this for
        observations that are not derived from a `RapidDimensionEstimate`
        (e.g. an LLM-injected `emotion concept` from Layer 4 construction).

        Failure semantics:
            Negative weights are silently skipped (a Bayesian prior must
            not move backward). Unknown concept names are silently added.
            Empty observation is a no-op.
        """
        from .concept_state import bayesian_update as _bayesian_update
        prior = self.concept_prior[0]
        self.concept_prior[0] = _bayesian_update(prior, observation)

    def concept_distribution(self) -> "Mapping[str, float]":
        """Public surface: return the current concept probability distribution.

        Laplace-smoothed (default `smoothing_mass=1.0`) so no concept ever
        has zero probability. Empty prior returns an empty mapping.
        """
        from .concept_state import normalize as _normalize
        return _normalize(self.concept_prior[0])

    def top_concepts(self, k: int = 3) -> "tuple[tuple[str, float], ...]":
        """Public surface: return the top-k concepts by current probability.

        Ties broken alphabetically (deterministic).
        """
        from .concept_state import top_concepts as _top
        return _top(self.concept_prior[0], k=k)

    def seed_prior(self, concepts: "tuple[EmotionConcept, ...] | None" = None) -> None:
        """Public surface: reset the prior seeded from a concept taxonomy.

        `concepts=None` uses the estimator's `self.concepts`. After this call,
        the prior has zero counts for every concept but is initialized with
        the concept names so observations can target them.

        Failure semantics:
            Empty concepts tuple leaves the prior empty (no concept names).
        """
        from .concept_state import ConceptPrior as _CP
        target = concepts if concepts is not None else self.concepts
        self.concept_prior[0] = _CP.from_concepts(target)


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