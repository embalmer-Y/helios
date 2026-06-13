"""Owner: runtime composition root.

First-version owner-neutral cross-owner bridges and first-version injected owner
capabilities required to assemble the runnable `01 -> 18` chain from shipped code.

These bridges promote the previously test-only `Fixed*` doubles in
`tests/test_runtime_stage_chain.py` into shipped, provenance-preserving, tick-general
implementations. They are assembly glue, not owners:

1. each bridge consumes explicit upstream stage results and produces the next owner's
   request or context contract,
2. each bridge preserves the upstream provenance ids the downstream stage contract
   requires and fails fast (via the owners' own errors) on inconsistency,
3. no bridge computes a downstream owner's semantic decision on its behalf,
4. no bridge embeds a hardcoded runtime strategy branch; values not yet produced by an
   owner come from explicit upstream contract fields.

The first-version injected owner capabilities (appraisal estimators, neuromodulator
update path, feeling construction path, memory formation path, workspace paths, and the
directed-retrieval memory candidate provider) are deterministic and bounded. They are
the minimum shipped behavior needed to make the chain runnable and are explicitly not
the final owner policy; later owner-deepening waves replace them through the owners.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from helios_v2.appraisal.engine import (
    AggregateJudgmentEstimator,
    MemorySimilaritySource,
    PrototypeSimilaritySource,
    RapidDimensionEstimate,
    RapidDimensionEstimator,
    RetrievalAmbiguitySource,
    SocialContextSource,
)
from helios_v2.action_externalization import ThoughtExternalizationRequest
from helios_v2.autonomy import (
    AutonomyDriveInputProjection,
    ProactiveCognitionFacts,
    ProactiveDriveRequest,
)
from helios_v2.channel import ChannelSubsystemAPI
from helios_v2.directed_retrieval import (
    DirectedMemoryCandidateProvider,
    MemoryRetrievalCandidate,
    RetrievalQueryPlan,
    RetrievalRequest,
)
from helios_v2.evaluation import EvaluationEvidenceBundle, EvaluationRequest
from helios_v2.experience_writeback import ExperienceWritebackRequest
from helios_v2.feeling import (
    FeelingConstructionPath,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
)
from helios_v2.identity_governance import GovernanceCarryState, IdentityGovernanceRequest
from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFamily,
    MemoryFormationPath,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    RecalledMemoryFact,
    RecalledMemoryProvider,
    ReplayCandidateSelector,
)
from helios_v2.neuromodulation import (
    ActiveChannelReporter,
    NeuromodulatorConfig,
    NeuromodulatorLevels,
    NeuromodulatorState,
    NeuromodulatorUpdatePath,
)
from helios_v2.observability import ExecutionTimelineView
from helios_v2.persistence import ExperienceStore, PersistedExperienceRecord, cosine_similarity
from helios_v2.continuity_checkpoint import RuntimeContinuitySnapshot
from helios_v2.outward_expression_externalization import OutwardExpressionExternalizationRequest
from helios_v2.planner_bridge import PlannerBridgeRequest
from helios_v2.prompt_contract import EmbodiedPromptRequest
from helios_v2.sensory import RawSignal, Stimulus
from helios_v2.thought_gating import SelectedStimulusSummary, ThoughtGateSignalSnapshot
from helios_v2.workspace import (
    WorkingStateRetentionPath,
    WorkingStateSnapshot,
    WorkspaceCandidate,
    WorkspaceCandidateSet,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionPath,
)

# ---------------------------------------------------------------------------
# First-version injected owner capabilities (deterministic, bounded, baseline).
# ---------------------------------------------------------------------------


@dataclass
class FirstVersionSensorySource:
    """Owner: composition.

    Purpose:
        Provide one bounded raw-signal batch per tick through the sensory ingress owner.

    Notes:
        This is a driver-facing baseline source. Real external input replaces it through
        the same `SensorySource` protocol in a later requirement.
    """

    source_name_value: str = "cli"
    signals: tuple[RawSignal, ...] = ()

    @property
    def source_name(self) -> str:
        """Stable source owner name consumed by sensory ingress registration."""

        return self.source_name_value

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Return the configured bounded raw-signal batch for the current collection."""

        if self.signals:
            return self.signals
        return (
            RawSignal(
                signal_id="001",
                source_name=self.source_name_value,
                signal_type="text",
                content="hello runtime",
                channel=self.source_name_value,
                metadata={"turn_id": "t1"},
            ),
        )


@dataclass
class SequenceExternalSignalSource:
    """Owner: composition (external-afferent assembly only, R59).

    Purpose:
        A first-version injectable external `SensorySource` that replays a caller-supplied
        sequence of real `RawSignal` batches, one batch per tick. It is the honest in-repo
        demonstration of the external-afferent seam: it carries only the real signals the
        caller provides and emits an explicitly empty batch once the sequence is exhausted.

    Failure semantics:
        None of its own; `02` sensory owns required-signal validation. An empty batch is a
        defined honest-absence behavior, never a fabricated stimulus.

    Notes:
        This source fabricates no content. It does not invent, randomize, or cycle canned
        text to simulate a changing external world (that would be the prompt theater
        `ARCHITECTURE_PHILOSOPHY` §4.3/§8 forbids). Real deployments inject their own
        `SensorySource` (e.g. a network-driver adapter in `wave_C`); this type exists so the
        seam is exercised with real, caller-owned signals in tests and dev. The cursor advances
        per `emit_raw_signals` call; past the end it yields `()`.
    """

    source_name_value: str = "external"
    batches: tuple[tuple[RawSignal, ...], ...] = ()
    _cursor: int = field(default=0, init=False, repr=False)

    @property
    def source_name(self) -> str:
        """Stable source owner name consumed by sensory ingress registration."""

        return self.source_name_value

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Return the current tick's caller-supplied real signal batch, then advance.

        Past the end of the supplied sequence this returns an empty tuple (honest absence),
        never a fabricated constant.
        """

        if self._cursor >= len(self.batches):
            return ()
        batch = self.batches[self._cursor]
        self._cursor += 1
        return batch


@dataclass
class SubsystemBackedSensorySource:
    """Owner: composition (channel-bound assembly only).

    Purpose:
        Feed the `RawSignal` objects drained from the channel subsystem into the sensory
        ingress owner through the standard `SensorySource` protocol.

    Notes:
        This adapter holds the current tick's drained signals (set by the assembly after the
        channel inbound drain stage runs) and returns them on `emit_raw_signals`. It performs
        no normalization; sensory owns that. It replaces `FirstVersionSensorySource` only in
        the explicit channel-bound assembly.
    """

    source_name_value: str = "cli"
    _pending: tuple[RawSignal, ...] = ()

    @property
    def source_name(self) -> str:
        """Stable source owner name consumed by sensory ingress registration."""

        return self.source_name_value

    def set_pending(self, signals: tuple[RawSignal, ...]) -> None:
        """Owner: composition. Set the drained raw signals for the current tick."""

        self._pending = signals

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Return and clear the current tick's drained raw signals."""

        pending = self._pending
        self._pending = ()
        return pending


@dataclass
class ChannelSubsystemStateProvider:
    """Owner: composition (channel-bound assembly only).

    Purpose:
        Provide the planner-bridge request's `channel_descriptor_snapshot` and
        `channel_status_snapshot` from the channel subsystem's real per-driver state,
        replacing the hardcoded shim for the channel-bound assembly.

    Notes:
        Owner-neutral glue. It projects the subsystem's `ChannelStateSnapshot` into the
        planner's expected snapshot shape. It carries transport facts only and never
        recommends a channel selection; the planner still owns selection/acceptance. A
        connected driver is reported available, bound, and executable so the planner produces
        the same executed path as the shim; the real transport happens in the dispatch stage.
    """

    subsystem: ChannelSubsystemAPI

    def channel_descriptor_snapshot(self) -> dict[str, dict[str, object]]:
        """Owner: composition. Project real driver descriptors into the planner snapshot shape."""

        snapshot = self.subsystem.channel_state_snapshot()
        descriptors: dict[str, dict[str, object]] = {}
        for descriptor in snapshot.descriptors:
            if "outbound" not in descriptor.directions:
                continue
            descriptors[descriptor.driver_id] = {
                "supported_ops": tuple(descriptor.output_ops),
                "output_ops": tuple(descriptor.output_ops),
            }
        return descriptors

    def channel_status_snapshot(self) -> dict[str, dict[str, object]]:
        """Owner: composition. Project real driver statuses into the planner snapshot shape."""

        snapshot = self.subsystem.channel_state_snapshot()
        statuses: dict[str, dict[str, object]] = {}
        for status in snapshot.statuses:
            connected = status.connected
            statuses[status.driver_id] = {
                "available": connected,
                "bound": connected,
                # The planner accepts and marks executed; the real transport is performed by
                # the outbound dispatch stage after the planner stage.
                "execute_now": True,
                "execution_success": True,
            }
        return statuses


@dataclass
class FirstVersionDimensionEstimator(RapidDimensionEstimator):
    """Owner: composition. First-version coarse dimension estimator (deterministic)."""

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        del stimulus
        return RapidDimensionEstimate(
            threat=0.2,
            reward=0.1,
            novelty=0.6,
            social=0.0,
            uncertainty=0.3,
        )


@dataclass
class FirstVersionAggregateEstimator(AggregateJudgmentEstimator):
    """Owner: composition. First-version aggregate salience estimator (deterministic).

    Notes (R63):
        Returns ``0.7``, an honest moderate baseline.  The default assembly has no real
        salience grounding yet (all five dimensions are first-version constants), so the
        aggregate is a composition-injected moderate judgment: "a first-version system
        attributes moderate significance to its percept."  At ``0.7`` the stimulus term
        (``aggregate * 0.30 = 0.21``) contributes to gate firing alongside the other real
        signals but cannot force a fire alone (``0.21 < fire_threshold 0.55``).  The semantic
        assembly uses ``WeightedAggregateEstimator`` (R41) and is unaffected.
    """

    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        del stimulus, dimensions
        return 0.7


@dataclass
class MemoryGroundedSimilaritySource(MemorySimilaritySource):
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Provide the `03` appraisal owner with a memory-retrieval fact for novelty: the maximum
        cosine similarity of a stimulus to the system's stored experience. It embeds the
        stimulus content through the injected embedding callable (the same callable and
        embedding profile the store was written with) and runs the store's bounded similarity
        search.

    Failure semantics:
        An embedding failure or store read failure propagates as a hard stop; this source never
        fabricates a similarity. Empty stimulus content and a cold/all-non-embedded store both
        return `None` (no comparable memory), which the appraisal owner maps to maximum novelty.

    Notes:
        Owner-neutral glue. It returns a raw cosine fact (or `None`); it never applies the
        `novelty = 1 - similarity` salience mapping — that semantic is owned by `03`. It reaches
        the embedding owner only through the injected `embed_text` callable (no embedding-owner
        import) and the persistence owner only through the `ExperienceStore` public API.
    """

    embed_text: Callable[[str], tuple[float, ...]]
    store: ExperienceStore
    max_scan: int = 256

    def max_similarity_for(self, stimulus: Stimulus) -> float | None:
        """Owner: composition. Return the stimulus's max cosine similarity to stored memory.

        Empty content yields `None` without calling the embedding capability; a cold or
        all-non-embedded store yields `None` after a search with no hits. Otherwise returns the
        top hit's cosine similarity. Embedding/store failures propagate as a hard stop.
        """

        text = stimulus.content.strip()
        if not text:
            return None
        query_vector = self.embed_text(text)
        result = self.store.search_similar(query_vector, limit=1, max_scan=self.max_scan)
        if not result.hits:
            return None
        return result.hits[0].similarity


@dataclass
class MemoryGroundedRetrievalAmbiguitySource(RetrievalAmbiguitySource):
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Provide the `03` appraisal owner with a memory-retrieval fact for uncertainty: the top-N
        cosine similarities of a stimulus to stored experience, descending. It embeds the stimulus
        content through the injected embedding callable (the same callable and embedding profile
        the store was written with) and runs the store's bounded similarity search.

    Failure semantics:
        An embedding failure or store read failure propagates as a hard stop; this source never
        fabricates similarities. Empty stimulus content and a cold/all-non-embedded store both
        return an empty tuple (no comparable memory), which the appraisal owner maps to maximum
        uncertainty.

    Notes:
        Owner-neutral glue. It returns raw cosine facts only; it never applies the ambiguity ->
        uncertainty mapping — that semantic is owned by `03`. It reaches the embedding owner only
        through the injected `embed_text` callable and the persistence owner only through the
        `ExperienceStore` public API. `top_n` defaults to 2 (the margin between the top two hits
        is what the uncertainty mapping reads).
    """

    embed_text: Callable[[str], tuple[float, ...]]
    store: ExperienceStore
    top_n: int = 2
    max_scan: int = 256

    def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
        """Owner: composition. Return the stimulus's top-N cosine similarities to stored memory.

        Empty content yields an empty tuple without calling the embedding capability; a cold or
        all-non-embedded store yields an empty tuple after a search with no hits. Otherwise returns
        the top-N hit cosines descending. Embedding/store failures propagate as a hard stop.
        """

        text = stimulus.content.strip()
        if not text:
            return ()
        query_vector = self.embed_text(text)
        result = self.store.search_similar(query_vector, limit=self.top_n, max_scan=self.max_scan)
        return tuple(hit.similarity for hit in result.hits)


@dataclass
class TransportGroundedSocialContextSource(SocialContextSource):
    """Owner: composition.

    Purpose:
        Provide the `03` appraisal owner with a raw transport fact for social appraisal: whether a
        stimulus originates from an external interactive-agent channel (another subject). The
        composition root owns this classification because it wired the channels.

    Notes:
        Owner-neutral glue. It returns a bounded presence value in `[0,1]`; it never applies the
        presence -> social salience mapping — that semantic is owned by `03`. Classification is a
        transport fact: a stimulus whose modality is internal (body/interoceptive/background) has
        presence 0.0; otherwise a stimulus whose channel or source_name is a configured external
        interactive-agent channel has presence `external_presence` (default 1.0), else 0.0. `03`
        never hardcodes channel names; this source owns the channel knowledge.
    """

    external_agent_channels: frozenset[str] = frozenset({"cli"})
    internal_modalities: frozenset[str] = frozenset({"body", "interoceptive", "background"})
    external_presence: float = 1.0

    def social_presence_for(self, stimulus: Stimulus) -> float:
        """Owner: composition. Return the social-presence transport fact for one stimulus."""

        if stimulus.modality in self.internal_modalities:
            return 0.0
        channel = stimulus.channel or ""
        if channel in self.external_agent_channels or stimulus.source_name in self.external_agent_channels:
            return self.external_presence
        return 0.0


@dataclass
class EmbeddingPrototypeSimilaritySource(PrototypeSimilaritySource):
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Provide the `03` appraisal owner with a mechanical similarity fact for threat/reward: the
        maximum cosine similarity of a stimulus to any phrase in an owner-provided prototype set.
        It embeds the stimulus content and each prototype phrase through the injected embedding
        callable (the same callable/profile the store uses) and computes cosine.

    Failure semantics:
        An embedding failure propagates as a hard stop; this source never fabricates a similarity.
        Empty stimulus content returns `None` (no comparable input), which the appraisal owner
        maps to threat/reward `0.0`.

    Notes:
        Owner-neutral glue. It returns a raw cosine fact only; it never applies the
        prototype -> salience mapping and does not know which set means threat vs reward -- the
        `03` owner passes the sets and owns their meaning (the `C_engineering_hypothesis`
        prototype anchor). It reaches the embedding owner only through the injected `embed_text`
        callable (no embedding-owner import). Prototype phrase embeddings are cached per phrase
        tuple so they are embedded once across ticks, not per tick.
    """

    embed_text: Callable[[str], tuple[float, ...]]
    _prototype_cache: dict[tuple[str, ...], tuple[tuple[float, ...], ...]] = field(
        default_factory=dict, repr=False
    )

    def _prototype_vectors(self, prototypes: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        cached = self._prototype_cache.get(prototypes)
        if cached is None:
            cached = tuple(self.embed_text(phrase) for phrase in prototypes)
            self._prototype_cache[prototypes] = cached
        return cached

    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        """Owner: composition. Return the stimulus's max cosine similarity to a prototype set.

        Empty content yields `None` without embedding the stimulus; otherwise embeds the stimulus
        once and returns the maximum cosine to any prototype vector. Embedding failures propagate
        as a hard stop.
        """

        text = stimulus.content.strip()
        if not text or not prototypes:
            return None
        query_vector = self.embed_text(text)
        prototype_vectors = self._prototype_vectors(prototypes)
        return max(cosine_similarity(query_vector, vector) for vector in prototype_vectors)


@dataclass
class FirstVersionNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: composition. First-version neuromodulator update path (deterministic)."""

    def update_levels(
        self,
        batch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: NeuromodulatorLevels | None = None,
    ) -> NeuromodulatorLevels:
        del batch, config, tick_id, prior_levels
        return NeuromodulatorLevels(
            dopamine=0.6,
            norepinephrine=0.4,
            serotonin=0.3,
            acetylcholine=0.7,
            cortisol=0.2,
            oxytocin=0.1,
            opioid_tone=0.1,
            excitation=0.8,
            inhibition=0.3,
        )


@dataclass
class FirstVersionActiveChannelReporter(ActiveChannelReporter):
    """Owner: composition. First-version active-channel reporter (deterministic)."""

    def report_active_channels(
        self,
        state: NeuromodulatorState,
        config: NeuromodulatorConfig,
    ) -> tuple[str, ...]:
        del state, config
        return ("acetylcholine", "excitation")


def _clamp(value: float, low: float, high: float) -> float:
    """Owner: composition. Clamp a value into [low, high].

    A pure owner-neutral numeric helper used by several projection bridges (recall similarity,
    interoceptive workload pressure). It encodes no cognitive scoring policy.
    """

    return round(min(high, max(low, value)), 4)


@dataclass
class FirstVersionFeelingConstructionPath(FeelingConstructionPath):
    """Owner: composition. First-version interoceptive feeling construction (deterministic)."""

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        del neuromodulator_state, internal_signals, config, tick_id, prior_feeling
        return InteroceptiveFeelingVector(
            valence=0.4,
            arousal=0.7,
            tension=0.5,
            comfort=0.2,
            fatigue=0.3,
            pain_like=0.1,
            social_safety=0.4,
        )


@dataclass
class FirstVersionDominantDimensionReporter:
    """Owner: composition. First-version dominant-feeling-dimension reporter (deterministic)."""

    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        del state, config
        return ("arousal", "tension")


@dataclass
class FirstVersionMemoryFormationPath(MemoryFormationPath):
    """Owner: composition. First-version memory formation path (deterministic).

    Consumes the explicit binding context and feeling state; forms one episodic item that
    preserves the upstream feeling-state and binding-context provenance.
    """

    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        del mismatch_evidence, config
        if binding_context is None:
            return ()
        return (
            AffectTaggedMemoryItem(
                memory_id=f"memory:runtime:{tick_id}",
                family="episodic",
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


@dataclass
class FirstVersionReplayCandidateSelector(ReplayCandidateSelector):
    """Owner: composition. First-version replay-candidate selector (deterministic)."""

    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        del mismatch_evidence, config
        candidates: list[MemoryReplayCandidate] = []
        for index, item in enumerate(memory_items):
            candidates.append(
                MemoryReplayCandidate(
                    candidate_id=f"candidate:runtime:{feeling_state.tick_id}:{index}",
                    memory_id=item.memory_id,
                    family=item.family,
                    source_feeling_state_id=feeling_state.state_id,
                    replay_reasons=(
                        "high_affect_intensity",
                        "prediction_mismatch_or_surprise",
                    ),
                    forced_consolidation=True,
                    priority_hint=0.9,
                )
            )
        return tuple(candidates)


@dataclass
class FirstVersionWorkspaceCompetitionPath(WorkspaceCompetitionPath):
    """Owner: composition. First-version workspace competition path (deterministic).

    Promotes each forced-consolidation replay candidate into one workspace candidate that
    preserves the source replay-candidate id and feeling-state provenance.
    """

    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        del config
        candidates: list[WorkspaceCandidate] = []
        for index, replay_candidate in enumerate(replay_candidates):
            candidates.append(
                WorkspaceCandidate(
                    candidate_id=f"workspace-candidate:runtime:{tick_id}:{index}",
                    source_memory_candidate_id=replay_candidate.candidate_id,
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=replay_candidate.priority_hint,
                    forced_consolidation=replay_candidate.forced_consolidation,
                    workspace_score_hint=0.95,
                )
            )
        return WorkspaceCandidateSet(
            set_id=f"workspace-set:runtime:{tick_id}",
            source_feeling_state_id=feeling_state.state_id,
            candidates=tuple(candidates),
            tick_id=tick_id,
        )


@dataclass
class FirstVersionWorkingStateRetentionPath(WorkingStateRetentionPath):
    """Owner: composition. First-version working-state retention path (deterministic)."""

    def retain_working_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkingStateSnapshot:
        del config
        return WorkingStateSnapshot(
            state_id=f"working-state:runtime:{tick_id}",
            source_candidate_set_id=candidate_set.set_id,
            retained_candidate_ids=tuple(
                candidate.candidate_id for candidate in candidate_set.candidates
            ),
            tick_id=tick_id,
        )


@dataclass
class FirstVersionDirectedMemoryCandidateProvider(DirectedMemoryCandidateProvider):
    """Owner: composition. First-version directed-retrieval candidate provider (deterministic).

    Returns a bounded tiered candidate set derived from the explicit retrieval plan so the
    directed-retrieval owner can assemble a thought-window bundle.
    """

    def collect_candidates(self, plan: RetrievalQueryPlan) -> tuple[MemoryRetrievalCandidate, ...]:
        return (
            MemoryRetrievalCandidate(
                candidate_id=f"candidate:short:{plan.plan_id}",
                tier="short_term",
                memory_id=f"memory:short:{plan.plan_id}",
                memory_type="short_term_context",
                summary="current runtime stimulus context",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
            MemoryRetrievalCandidate(
                candidate_id=f"candidate:mid:{plan.plan_id}",
                tier="mid_term",
                memory_id=f"memory:mid:{plan.plan_id}",
                memory_type="episodic",
                summary="situational-summary: prior runtime context",
                score=0.85,
                source="memory_affect_and_replay",
                tags=("episodic",),
            ),
            MemoryRetrievalCandidate(
                candidate_id=f"candidate:auto:{plan.plan_id}",
                tier="autobiographical",
                memory_id=f"memory:auto:{plan.plan_id}",
                memory_type="autobiographical",
                summary="runtime continuity trace",
                score=0.65,
                source="memory_affect_and_replay",
                tags=("continuity",),
            ),
        )


# ---------------------------------------------------------------------------
# Cross-owner bridges (owner-neutral request/context assembly, provenance-preserving).
# ---------------------------------------------------------------------------


@dataclass
class TimelineViewHolder:
    """Owner: composition.

    Purpose:
        Hold the previous completed tick's execution-timeline view so it can be carried
        forward into the next tick's evaluation evidence assembly, plus whether the runtime
        is instrumented at all, plus the previous completed tick's published consequence
        claim so the next tick's evaluation can corroborate the self-report against the
        timeline.

    Notes:
        Owner-neutral carry only. It transports a formal `ExecutionTimelineView` produced
        by the observability owner and a plain projection of the evaluation owner's published
        `ConsequenceClaim`; it never interprets or mutates either. The `instrumented` flag
        lets evaluation distinguish an instrumented first tick (no prior timeline yet) from a
        genuinely uninstrumented runtime. `prior_consequence_claim` is tick-aligned with
        `view`: both describe the same previous completed tick.
    """

    view: ExecutionTimelineView | None = None
    instrumented: bool = False
    prior_consequence_claim: dict | None = None


@dataclass
class FirstVersionPriorConsequenceClaimEvidenceBridge:
    """Owner: composition.

    Purpose:
        Project the carried previous-tick published consequence claim into the prior-claim
        evidence entry consumed by the evaluation bundle.

    Notes:
        Owner-neutral glue. It forwards only the evaluation owner's own published claim
        projection (owner-published statuses plus the prior tick id). When no prior claim
        has been captured yet (first tick or uninstrumented), it yields an empty tuple, which
        the evaluation owner reads as an explicit `unverifiable_no_timeline` verdict rather
        than a corroboration. It never computes or re-derives any owner status.
    """

    def build_claim_evidence(self, holder: "TimelineViewHolder | None") -> tuple[dict, ...]:
        if holder is None or holder.prior_consequence_claim is None:
            return ()
        return (dict(holder.prior_consequence_claim),)


@dataclass
class ExperienceRecordBridge:
    """Owner: composition.

    Purpose:
        Project the `15` experience-writeback stage result of one completed tick into durable
        `PersistedExperienceRecord` values for the `33` experience store.

    Notes:
        Owner-neutral glue. It flattens each published `ExperienceWritebackResult` plus its
        `ContinuityEvidencePacket` into one storage record, preserving the upstream
        `source_provenance` linkage ids verbatim. It computes no status, ranks nothing, and
        decides no storage policy. It is used only by the explicit opt-in persistence assembly.
    """

    def build_records(self, writeback_stage_result, tick_id) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: composition.

        Purpose:
            Build the durable records for one tick from the writeback stage result.

        Inputs:
            `writeback_stage_result` - the tick's `ExperienceWritebackStageResult`.
            `tick_id` - the completed tick id.

        Returns:
            One `PersistedExperienceRecord` per published writeback result, preserving
            provenance linkage. Empty when the stage published no results.

        Notes:
            Linkage is copied verbatim from each continuity packet's `source_provenance`; only
            string-valued linkage ids are kept (the record contract requires string ids).
        """

        records: list[PersistedExperienceRecord] = []
        for result in writeback_stage_result.results:
            packet = result.continuity_packet
            linkage = {
                key: value
                for key, value in packet.source_provenance.items()
                if isinstance(value, str) and value
            }
            records.append(
                PersistedExperienceRecord(
                    record_id=f"experience:{result.result_id}",
                    tick_id=tick_id,
                    continuity_kind=packet.continuity_kind,
                    outcome_class=packet.outcome_class,
                    source_outcome_kind=packet.source_outcome_kind,
                    source_outcome_id=packet.source_outcome_id,
                    writeback_status=result.status,
                    summary=packet.summary,
                    requested_effect_summary=packet.requested_effect_summary,
                    applied_effect_summary=packet.applied_effect_summary,
                    reason_trace=packet.reason_trace,
                    linkage=linkage,
                )
            )
        return tuple(records)


@dataclass
class MemoryRecordBridge:
    """Owner: composition.

    Purpose:
        Project the `06` memory affect-and-replay stage result of one completed tick into
        durable `PersistedExperienceRecord` values for the `33` experience store, persisting
        exactly the consolidation-worthy memory items the `06` owner marked.

    Notes:
        Owner-neutral glue. It reads only the published `MemoryFormationState` (the formed
        memory items plus the replay candidates whose `forced_consolidation` flag the `06`
        salience gate already set) and projects exactly those flagged items into storage
        records tagged `record_kind="affect_memory"`. It re-derives no salience, re-ranks
        nothing, and decides no consolidation policy; it filters by the flag `06` published.
        It is used only by the explicit opt-in semantic-memory assembly. Affect-memory records
        store the `06` family as the continuity kind (the store's tier mapping reads it as a
        by-kind transport fact) and never replace or suppress the `15` continuity stream.
    """

    def build_records(self, memory_stage_result, tick_id) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: composition.

        Purpose:
            Build the durable affect-memory records for one tick from the memory stage result.

        Inputs:
            `memory_stage_result` - the tick's `MemoryAffectReplayStageResult`.
            `tick_id` - the completed tick id.

        Returns:
            One `PersistedExperienceRecord` per consolidation-worthy memory item (those whose
            replay candidate carries `forced_consolidation=True`), preserving feeling-state
            provenance. Empty when no item cleared the `06` salience gate this tick.

        Notes:
            The summary is a bounded projection of the item's content packet; the store never
            reads it for meaning. The candidate's `replay_reasons` become the record reason
            trace, preserving why `06` judged the memory worth consolidating.
        """

        state = memory_stage_result.state
        worthy_candidates = {
            candidate.memory_id: candidate
            for candidate in state.replay_candidates
            if candidate.forced_consolidation
        }
        records: list[PersistedExperienceRecord] = []
        for item in state.memory_items:
            candidate = worthy_candidates.get(item.memory_id)
            if candidate is None:
                continue
            linkage = {"source_feeling_state_id": item.source_feeling_state_id}
            if item.binding_context_id:
                linkage["binding_context_id"] = item.binding_context_id
            metadata = {
                "memory_family": item.family,
                # R52: persist the formed memory's affect vector so a later tick can recall it
                # with its original felt charge and replay it into the workspace competition.
                "affect_vector": _encode_affect_vector(item.affect_tag),
            }
            records.append(
                PersistedExperienceRecord(
                    record_id=f"affect-memory:{item.memory_id}",
                    tick_id=tick_id,
                    continuity_kind=item.family,
                    outcome_class="affect_memory",
                    source_outcome_kind="memory_item",
                    source_outcome_id=item.memory_id,
                    writeback_status="formed",
                    summary=_memory_content_summary(item),
                    requested_effect_summary="",
                    applied_effect_summary="",
                    reason_trace=candidate.replay_reasons,
                    linkage=linkage,
                    record_kind="affect_memory",
                    metadata=metadata,
                )
            )
        return tuple(records)


def _memory_content_summary(item) -> str:
    """Owner: composition. Build a bounded non-empty summary from a memory item's content.

    The `PersistedExperienceRecord` contract requires a non-empty summary. This projects the
    item's `MemoryContentPacket` into a stable string, preferring an explicit summary ref, then
    a context ref, then the salient tokens, then a stable fallback keyed by the memory id. It is
    a transport projection; the store never reads it for meaning.
    """

    content = item.content
    if content.summary_ref:
        return content.summary_ref
    if content.context_ref:
        return content.context_ref
    if content.salient_tokens:
        return " ".join(content.salient_tokens)
    return f"affect-memory:{item.memory_id}"


# R52: the affect-memory metadata key carrying the formed memory's affect vector, so a recalled
# memory can be replayed into the workspace with its original felt charge. String-encoded because
# `PersistedExperienceRecord.metadata` is a `Mapping[str, str]`.
_AFFECT_VECTOR_METADATA_KEY = "affect_vector"
_AFFECT_VECTOR_DIMENSIONS: tuple[str, ...] = (
    "valence",
    "arousal",
    "tension",
    "comfort",
    "fatigue",
    "pain_like",
    "social_safety",
)


def _encode_affect_vector(affect: InteroceptiveFeelingVector) -> str:
    """Owner: composition. Encode an affect vector as a comma-joined string of 7 rounded floats.

    The order is the fixed `_AFFECT_VECTOR_DIMENSIONS` order. It is a transport projection; the
    store never reads it for meaning.
    """

    return ",".join(f"{round(getattr(affect, dimension), 4)}" for dimension in _AFFECT_VECTOR_DIMENSIONS)


def _decode_affect_vector(encoded: str | None) -> InteroceptiveFeelingVector | None:
    """Owner: composition. Decode an affect vector encoded by `_encode_affect_vector`.

    Returns `None` for an absent (legacy record) or malformed value (wrong component count,
    non-numeric, or out-of-range), so such records are simply not workspace-recall-eligible
    rather than crashing recall. A successful decode reconstructs the original
    `InteroceptiveFeelingVector` (within rounding).
    """

    if not encoded:
        return None
    parts = encoded.split(",")
    if len(parts) != len(_AFFECT_VECTOR_DIMENSIONS):
        return None
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return None
    if any(value < 0.0 or value > 1.0 for value in values):
        return None
    return InteroceptiveFeelingVector(**dict(zip(_AFFECT_VECTOR_DIMENSIONS, values)))


@dataclass
class StoreBackedRecalledMemoryProvider(RecalledMemoryProvider):
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Semantically recall prior affect-memories from the durable store and return them as raw
        `RecalledMemoryFact`s for the `06` owner to replay into the workspace competition. It
        embeds the current binding-context content through the injected embedding callable (the
        same callable/profile the store was written with) and ranks stored `affect_memory`-kind
        records by cosine similarity (reusing the `34` store similarity surface), reconstructing
        each recalled memory's original affect vector from its durably persisted metadata.

    Failure semantics:
        An embedding failure or store read failure propagates as a hard stop; this provider never
        fabricates a recall. Empty binding-context content, a cold/all-non-embedded store, no
        `affect_memory` hit, or a hit without a decodable persisted affect vector all yield no
        fact for that hit (an empty tuple overall when nothing qualifies).

    Notes:
        Owner-neutral glue. It returns raw facts only (no priority, no item/candidate); the `06`
        owner owns the replay-priority mapping and the re-forming. It reaches the embedding owner
        only through the injected `embed_text` callable (no embedding-owner import) and the
        persistence owner only through the `ExperienceStore` public API. Recall is bounded by
        `limit`/`max_scan`.
    """

    embed_text: Callable[[str], tuple[float, ...]]
    store: ExperienceStore
    limit: int = 3
    max_scan: int = 256

    def recall(
        self,
        binding_context: MemoryBindingContext,
        feeling_state: InteroceptiveFeelingState,
    ) -> tuple[RecalledMemoryFact, ...]:
        """Owner: composition. Recall bounded prior affect-memory facts for the current context."""

        del feeling_state
        query_text = _binding_context_query_text(binding_context)
        if not query_text.strip():
            return ()
        query_vector = self.embed_text(query_text)
        result = self.store.search_similar(query_vector, limit=self.limit, max_scan=self.max_scan)
        facts: list[RecalledMemoryFact] = []
        for hit in result.hits:
            record = hit.record
            if record.record_kind != "affect_memory":
                continue
            affect = _decode_affect_vector(record.metadata.get(_AFFECT_VECTOR_METADATA_KEY))
            if affect is None:
                continue
            family = _recalled_family_from_record(record)
            facts.append(
                RecalledMemoryFact(
                    memory_id=record.source_outcome_id,
                    family=family,
                    summary=record.summary,
                    recall_similarity=_clamp(hit.similarity, 0.0, 1.0),
                    affect=affect,
                )
            )
        return tuple(facts)


def _binding_context_query_text(binding_context: MemoryBindingContext) -> str:
    """Owner: composition. Project a binding context's content into a bounded query string."""

    content = binding_context.content
    if content.summary_ref:
        return content.summary_ref
    if content.context_ref:
        return content.context_ref
    if content.salient_tokens:
        return " ".join(content.salient_tokens)
    return ""


def _recalled_family_from_record(record: PersistedExperienceRecord) -> MemoryFamily:
    """Owner: composition. Recover the stored memory family from an affect-memory record.

    R45 persists the family in both `metadata["memory_family"]` and `continuity_kind`. This reads
    the metadata value (falling back to `continuity_kind`) and maps it onto the fixed
    `MemoryFamily` taxonomy, defaulting to `episodic` for any unrecognized legacy value so recall
    never crashes on an out-of-taxonomy string.
    """

    raw = record.metadata.get("memory_family") or record.continuity_kind
    if raw in ("episodic", "semantic", "autobiographical"):
        return raw  # type: ignore[return-value]
    return "episodic"


@dataclass
class ContinuityCheckpointBridge:
    """Owner: composition.

    Purpose:
        Project the genuinely cross-tick continuity state of one completed tick into a
        `RuntimeContinuitySnapshot` for the `42` checkpoint store, and reconstruct the `09`/`18`
        owner states from a loaded snapshot so a restarted runtime can resume them.

    Notes:
        Owner-neutral glue. `build_snapshot` reads only owner-published stage-result values (the
        `09` continuation state and the `18`/`24` long-horizon continuity) and copies them
        verbatim; it computes no continuity decision. The reused owner contracts carry their own
        validation, so reconstruction (here, simply unpacking the snapshot's reused-contract
        fields) preserves owner ownership of state shape. It is used only by the explicit opt-in
        checkpoint assembly.
    """

    def build_snapshot(
        self,
        thought_gating_stage_result,
        autonomy_stage_result,
        tick_id,
        neuromodulator_stage_result=None,
        feeling_stage_result=None,
    ) -> RuntimeContinuitySnapshot:
        """Owner: composition.

        Purpose:
            Build the latest-state continuity snapshot for one completed tick.

        Inputs:
            `thought_gating_stage_result` - the tick's `ThoughtGatingStageResult` (its
                `continuation_state` is the `09` cross-tick state).
            `autonomy_stage_result` - the tick's `AutonomyStageResult` (its
                `result.deferred_records` and `result.long_horizon_state.threads` are the
                `18`/`24` cross-tick state).
            `tick_id` - the completed tick id.
            `neuromodulator_stage_result` - optional `NeuromodulatorStageResult`; when present its
                `state.levels` (the R43 cross-tick `04` state) are captured into the snapshot.
            `feeling_stage_result` - optional `InteroceptiveFeelingStageResult`; when present its
                `state.feeling` (the R44 cross-tick `05` state) is captured into the snapshot.

        Returns:
            A `RuntimeContinuitySnapshot` carrying the published cross-tick state verbatim.

        Notes:
            Copies owner-published values only; preserves no private state and computes nothing.
        """

        levels = (
            neuromodulator_stage_result.state.levels
            if neuromodulator_stage_result is not None
            else None
        )
        feeling = (
            feeling_stage_result.state.feeling
            if feeling_stage_result is not None
            else None
        )
        return RuntimeContinuitySnapshot(
            tick_id=tick_id,
            continuation_state=thought_gating_stage_result.continuation_state,
            deferred_records=autonomy_stage_result.result.deferred_records,
            continuity_threads=autonomy_stage_result.result.long_horizon_state.threads,
            neuromodulator_levels=levels,
            feeling=feeling,
        )

    def restore_neuromodulator_state(self, snapshot: RuntimeContinuitySnapshot):
        """Owner: composition.

        Purpose:
            Reconstruct a `NeuromodulatorState` from a snapshot's `04` levels so composition can
            seed the `04` stage's prior state on restart, or return `None` when the snapshot
            carries no levels (a pre-`04`-checkpoint or stateless snapshot).

        Inputs:
            `snapshot` - the loaded `RuntimeContinuitySnapshot`.

        Returns:
            A `NeuromodulatorState` carrying the restored levels with a restore-provenance id, or
            `None`.

        Notes:
            Owner-neutral: it only wraps the owner-published levels back into the owner's own state
            contract (running that contract's validation). It computes no dynamics.
        """

        if snapshot.neuromodulator_levels is None:
            return None
        return NeuromodulatorState(
            state_id=f"neuromodulator-state:restored:{snapshot.tick_id if snapshot.tick_id is not None else 'na'}",
            source_appraisal_batch_id="restored-from-continuity-checkpoint",
            levels=snapshot.neuromodulator_levels,
            tick_id=snapshot.tick_id,
        )

    def restore_feeling_state(self, snapshot: RuntimeContinuitySnapshot):
        """Owner: composition.

        Purpose:
            Reconstruct an `InteroceptiveFeelingState` from a snapshot's `05` feeling so
            composition can seed the `05` stage's prior state on restart, or return `None` when
            the snapshot carries no feeling (a pre-`05`-checkpoint or stateless snapshot).

        Inputs:
            `snapshot` - the loaded `RuntimeContinuitySnapshot`.

        Returns:
            An `InteroceptiveFeelingState` carrying the restored feeling with a restore-provenance
            id, or `None`.

        Notes:
            Owner-neutral: it only wraps the owner-published feeling back into the owner's own
            state contract (running that contract's validation). It computes no dynamics.
        """

        if snapshot.feeling is None:
            return None
        return InteroceptiveFeelingState(
            state_id=f"interoceptive-feeling-state:restored:{snapshot.tick_id if snapshot.tick_id is not None else 'na'}",
            source_neuromodulator_state_id="restored-from-continuity-checkpoint",
            feeling=snapshot.feeling,
            tick_id=snapshot.tick_id,
        )


@dataclass
class FirstVersionExecutionTimelineEvidenceBridge:
    """Owner: composition.

    Purpose:
        Project the carried previous-tick `ExecutionTimelineView` into the execution-timeline
        evidence entry consumed by the evaluation bundle.

    Notes:
        Owner-neutral glue. It forwards only the formal observability timeline projection
        (execution-timing facts). When the runtime is instrumented but no prior tick exists
        yet, it emits an explicit no-prior-timeline marker (tick_id None) so evaluation can
        distinguish a first instrumented tick from a genuinely uninstrumented runtime. When
        the runtime is uninstrumented, it yields an empty tuple.
    """

    def build_timeline_evidence(self, holder: "TimelineViewHolder | None") -> tuple[dict, ...]:
        if holder is None or not holder.instrumented:
            return ()
        if holder.view is None:
            return (
                {
                    "evidence_id": "execution-timeline-evidence:no-prior-tick",
                    "tick_id": None,
                    "completed": False,
                    "stage_count": 0,
                    "stages": [],
                },
            )
        view = holder.view
        return (view.to_evidence(f"execution-timeline-evidence:tick:{view.tick_id}"),)


@dataclass
class FirstVersionMemoryBindingContextBridge:
    """Owner: composition.

    Purpose:
        Build the explicit memory binding context for one tick from the real perceived
        stimulus this tick (the `02` sensory batch already present in the frame), so the
        memory `06` forms is a record of what the system actually perceived.

    Notes:
        Owner-neutral glue (R60). It projects the real `02` percept into the `06`
        `MemoryBindingContext`/`MemoryContentPacket` contract: provenance ids from the real
        stimulus/batch and `salient_tokens` mechanically tokenized from the real perceived
        content. It invents nothing — every token is a substring of the real content — and on
        an empty perceived batch it returns `None` (honest absence: `06` forms no memory that
        tick), never a fabricated content packet. It decides no `06` memory formation policy.
    """

    def build_binding_context(self, frame, feeling_result) -> MemoryBindingContext | None:
        from helios_v2.runtime.stages import SensoryIngressStageResult

        tick_id = frame.tick_id
        stage_results = frame.stage_results or {}
        sensory = stage_results.get("sensory_ingress")
        stimuli = (
            sensory.batch.stimuli if isinstance(sensory, SensoryIngressStageResult) else ()
        )
        if stimuli:
            # Prefer the external percept (what the world presented); fall back to the whole batch
            # (e.g. an interoceptive-only tick) so a real internal percept still binds a real memory.
            external = [s for s in stimuli if s.modality not in _INTERNAL_MODALITIES]
            perceived = external or list(stimuli)
            primary = perceived[0]
            return MemoryBindingContext(
                context_id=f"binding:runtime:{tick_id}",
                source_kind="perceived_stimulus",
                content=MemoryContentPacket(
                    content_kind="perceived-stimulus-summary",
                    summary_ref=primary.stimulus_id,
                    context_ref=sensory.batch.batch_id,
                    salient_tokens=_tokens_from(primary.content),
                ),
            )
        # Honest absence: the tick perceived nothing. We do not fabricate external content.
        # R65: after zero-percept pre-gate closure, the runtime stage adapter short-circuits `06`
        # before calling this bridge when the `02` batch is empty, so this path is now a defensive
        # fallback unreachable from the standard runtime path. It is preserved for non-runtime
        # callers (e.g. future composition variants) that may still reach this bridge directly.
        # It binds an explicit no-percept context anchored to the REAL feeling state this tick.
        return MemoryBindingContext(
            context_id=f"binding:runtime:{tick_id}",
            source_kind="no_perceived_stimulus",
            content=MemoryContentPacket(
                content_kind="no-perceived-stimulus",
                summary_ref=feeling_result.state.state_id,
                context_ref=None,
                salient_tokens=(),
            ),
        )


@dataclass
class FirstVersionPredictionMismatchEvidenceBridge:
    """Owner: composition.

    Purpose:
        Build prediction-mismatch (surprise) evidence for one tick from the real `03` appraisal
        novelty, so genuinely novel/surprising percepts raise the `06` consolidation salience and
        bias memory toward the autobiographical family, while familiar/expected percepts produce
        low or no surprise.

    Notes:
        Owner-neutral glue (R61). It reads the real `03` `RapidSalienceAppraisalStageResult` in the
        frame and projects the batch-max `novelty` (the surprise core: `1 - max cosine similarity`
        to stored experience, "unlike anything remembered") and `uncertainty` into the `06`
        `PredictionMismatchEvidence` contract. It computes no `06` consolidation/family policy
        (those stay in the `06` owner) and invents no forward-model prediction. Below
        `_MISMATCH_NOVELTY_THRESHOLD` (a familiar/expected percept) it returns `None`, so `06`
        treats the tick as a non-surprising episodic memory. **Honest grounding
        (`B_functional_inspiration`): this is novelty-as-surprise in a memory-grounded system, not
        a true predictive-coding forward-model error (a later P5 concern); it must not be
        over-claimed.** In the default/recency assemblies `03` novelty is the first-version
        constant `0.6` (>= the threshold), so those assemblies still emit a `0.6`-derived mismatch
        rather than the retired `0.8` constant.
    """

    def build_mismatch_evidence(self, frame, feeling_result) -> PredictionMismatchEvidence | None:
        from helios_v2.runtime.stages import RapidSalienceAppraisalStageResult

        stage_results = frame.stage_results or {}
        appraisal = stage_results.get("rapid_salience_appraisal")
        if not isinstance(appraisal, RapidSalienceAppraisalStageResult):
            return None
        appraisals = appraisal.batch.appraisals
        if not appraisals:
            return None
        # The dominant percept's real surprise: the most unlike-anything-remembered stimulus drives
        # mismatch (batch-max novelty), with its retrieval ambiguity as the confidence inverse.
        novelty = max(a.salience.novelty for a in appraisals)
        uncertainty = max(a.salience.uncertainty for a in appraisals)
        if novelty < _MISMATCH_NOVELTY_THRESHOLD:
            # Familiar/expected percept: no surprise evidence -> `06` forms an episodic memory.
            return None
        return PredictionMismatchEvidence(
            evidence_id=f"mismatch:runtime:{frame.tick_id}",
            source_reference_id=feeling_result.state.state_id,
            mismatch_score=_clamp(novelty, 0.0, 1.0),
            anomaly_score=_clamp(novelty, 0.0, 1.0),
            confidence=_clamp(1.0 - uncertainty, 0.0, 1.0),
        )


@dataclass
class FirstVersionThoughtGateSignalBridge:
    """Owner: composition.

    Purpose:
        Build the normalized thought-gate signal snapshot from the conscious-content result.

    Notes:
        Owner-neutral glue. It preserves the upstream conscious-state id and forwards a
        bounded signal snapshot; it does not decide the gate result.
    """

    temporal_source: object | None = None
    drive_urgency_holder: object | None = None

    def build_signal_snapshot(self, frame, conscious_result) -> ThoughtGateSignalSnapshot:
        tick_id = frame.tick_id
        temporal_signal, dmn_available = _temporal_inputs(frame, self.temporal_source)
        return ThoughtGateSignalSnapshot(
            snapshot_id=f"gate-snapshot:runtime:{tick_id}",
            source_conscious_state_id=conscious_result.state.state_id,
            workload_pressure=_interoceptive_workload_pressure(frame),
            global_activation_level=0.9,
            temporal_signal=temporal_signal,
            drive_urgency_signal=_drive_urgency_signal(self.drive_urgency_holder),
            dmn_available=dmn_available,
            selected_stimuli=_selected_stimuli_from_appraisal(frame, tick_id),
            tick_id=tick_id,
        )


@dataclass
class NeuromodulatorAwareThoughtGateSignalBridge:
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Build the normalized thought-gate signal snapshot exactly like the first-version
        bridge, but additionally forward two real upstream facts: the real `04` norepinephrine
        level (R37) as `neuromodulatory_arousal`, and (R48) the real `07` workspace activation as
        `global_activation_level` (the dominant ignition strength held in the working state),
        replacing the constant `0.9`.

    Failure semantics:
        The `04` neuromodulator and `07` workspace stages both run before `09` in the canonical
        order, so their results must be present. A missing or wrong-typed result of either is a
        hard fail (the existing runtime stage error), never a silent uncoupled snapshot.

    Notes:
        Owner-neutral glue. It forwards the raw norepinephrine level and the raw workspace
        activation fact verbatim; it computes no gate score and no gate weighting. The
        arousal-to-gate and activation-to-gate semantics are owned by the `09` gate path (its
        existing weights), exactly as R35 keeps the novelty salience semantic in `03` while
        composition only forwards the raw fact. The remaining gate-signal inputs
        (`workload_pressure`, `temporal_signal`, `drive_urgency_signal`, `dmn_available`) stay
        first-version constants or prior-tick carries this slice. The `selected_stimuli`
        projection is now real (R63): it reads the same-tick `03` appraisal batch-max salience
        through `_selected_stimuli_from_appraisal`.
    """

    neuromodulator_stage_name: str = "neuromodulator_system"
    workspace_stage_name: str = "workspace_competition_and_working_state"
    temporal_source: object | None = None
    drive_urgency_holder: object | None = None

    def build_signal_snapshot(self, frame, conscious_result) -> ThoughtGateSignalSnapshot:
        from helios_v2.runtime.stages import (
            NeuromodulatorStageResult,
            RuntimeStageExecutionError,
            WorkspaceCompetitionStageResult,
        )

        tick_id = frame.tick_id
        stage_results = frame.stage_results or {}
        neuromodulator_result = stage_results.get(self.neuromodulator_stage_name)
        if neuromodulator_result is None:
            raise RuntimeStageExecutionError(
                "Neuromodulator-aware gate signal requires the upstream "
                f"'{self.neuromodulator_stage_name}' result before thought gating"
            )
        if not isinstance(neuromodulator_result, NeuromodulatorStageResult):
            raise RuntimeStageExecutionError(
                "Neuromodulator-aware gate signal expected the upstream "
                f"'{self.neuromodulator_stage_name}' result to be NeuromodulatorStageResult"
            )
        norepinephrine = neuromodulator_result.state.levels.norepinephrine
        workspace_result = stage_results.get(self.workspace_stage_name)
        if workspace_result is None:
            raise RuntimeStageExecutionError(
                "Workspace-grounded gate signal requires the upstream "
                f"'{self.workspace_stage_name}' result before thought gating"
            )
        if not isinstance(workspace_result, WorkspaceCompetitionStageResult):
            raise RuntimeStageExecutionError(
                "Workspace-grounded gate signal expected the upstream "
                f"'{self.workspace_stage_name}' result to be WorkspaceCompetitionStageResult"
            )
        global_activation_level = _workspace_activation(workspace_result)
        temporal_signal, dmn_available = _temporal_inputs(frame, self.temporal_source)
        return ThoughtGateSignalSnapshot(
            snapshot_id=f"gate-snapshot:runtime:{tick_id}",
            source_conscious_state_id=conscious_result.state.state_id,
            workload_pressure=_interoceptive_workload_pressure(frame),
            global_activation_level=global_activation_level,
            temporal_signal=temporal_signal,
            drive_urgency_signal=_drive_urgency_signal(self.drive_urgency_holder),
            dmn_available=dmn_available,
            selected_stimuli=_selected_stimuli_from_appraisal(frame, tick_id),
            tick_id=tick_id,
            neuromodulatory_arousal=norepinephrine,
        )


def _workspace_activation(workspace_result) -> float:
    """Owner: composition. Project the real `07` workspace activation for the `09` gate signal.

    The global workspace's activation level is the strength of the dominant content it is
    currently holding in attention: the maximum `workspace_score_hint` among the candidates
    retained in the working state. An empty working state means the workspace did not ignite this
    tick, yielding `0.0`. A candidate with no score floors to `0.0`. The result is clamped into
    `[0, 1]` and rounded for determinism. This reads only already-published `07` values and
    applies no gate semantic.
    """

    retained = set(workspace_result.working_state.retained_candidate_ids)
    scores = [
        candidate.workspace_score_hint or 0.0
        for candidate in workspace_result.candidate_set.candidates
        if candidate.candidate_id in retained
    ]
    if not scores:
        return 0.0
    return round(min(1.0, max(0.0, max(scores))), 4)


# R53: the interoceptive load channels (the R50 compute/runtime-pressure afferent) that ground the
# `09` gate's `workload_pressure`. cpu+memory are the runtime-load channels; latency/error are
# first-version injectable defaults in the R50 sampler and are not load-suppressive here.
_WORKLOAD_PRESSURE_CHANNELS = frozenset({"cpu", "memory"})

# Reserved interoceptive-afferent metadata keys the `50` runtime interoceptive source sets on each
# interoceptive stimulus (mirrored here as the producer-side literals; the `05` feeling owner reads
# the same keys for R51). These are owner-read transport facts, not a typed cross-owner contract.
_PRESSURE_CHANNEL_METADATA_KEY = "pressure_channel"
_PRESSURE_VALUE_METADATA_KEY = "pressure_value"


def _interoceptive_workload_pressure(frame, default: float = 0.1) -> float:
    """Owner: composition (R53). Derive the `09` gate `workload_pressure` from the `02` afferent.

    Reads the current tick's `02` sensory batch for interoceptive cpu/memory load stimuli (the R50
    afferent) and returns the maximum of their bounded `pressure_value`s (the dominant resource
    pressure), or `default` when no recognized load stimulus is present (so an assembly without the
    interoceptive source keeps the constant first-version value byte-for-byte).

    Owner-neutral glue: it forwards a raw bounded load fact only; the gate weight and the
    resource-pressure block threshold stay owned by the `09` thought-gating owner. It reads only the
    reserved `pressure_channel`/`pressure_value` metadata the `50` producer set (never the content
    string) and skips any stimulus whose channel is not a recognized load channel or whose value is
    not a numeric in `[0,1]`, contributing nothing rather than raising or fabricating a load.
    """

    from helios_v2.runtime.stages import SensoryIngressStageResult

    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult):
        return default
    pressures: list[float] = []
    for stimulus in sensory.batch.stimuli:
        if stimulus.modality != "interoceptive":
            continue
        metadata = stimulus.metadata or {}
        channel = metadata.get(_PRESSURE_CHANNEL_METADATA_KEY)
        value = metadata.get(_PRESSURE_VALUE_METADATA_KEY)
        if channel not in _WORKLOAD_PRESSURE_CHANNELS:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if numeric < 0.0 or numeric > 1.0:
            continue
        pressures.append(numeric)
    if not pressures:
        return default
    return _clamp(round(max(pressures), 4), 0.0, 1.0)


# R55: stimulus modalities that are internal (not an external task). DMN engages at rest (no
# external stimulus) and is suppressed when an external stimulus is present.
_INTERNAL_MODALITIES = frozenset({"body", "interoceptive", "background"})


# R61: below this real `03` novelty level a percept is familiar/expected and yields no
# prediction-mismatch (surprise) evidence, so the `06` owner forms an episodic (not
# autobiographical) memory. First-version projection cut-point (composition glue, not a `06`
# policy weight).
_MISMATCH_NOVELTY_THRESHOLD = 0.5


# R62: the documented first-tick neutral baseline for the `09` gate's `drive_urgency_signal`.
# Before any `18` proactive drive exists (tick 1), the gate uses this neutral value (the same
# value the pre-R62 constant used); from tick 2 onward the real prior-tick `18` drive supersedes
# it through the carry holder. It is a defined cold-start baseline, not a fabricated high signal.
_DRIVE_URGENCY_COLD_START = 0.7


def _drive_urgency_signal(holder: object | None) -> float:
    """Owner: composition (R62). Return the `09` gate `drive_urgency_signal` from the carry holder.

    When a `PriorDriveUrgencyHolder` is wired, returns the bounded prior-tick `18` proactive-drive
    urgency it carries (the neutral cold-start value until the first `18` drive exists); otherwise
    returns the documented cold-start baseline. Owner-neutral: the `09` owner keeps the gate weight.
    """

    if holder is None:
        return _DRIVE_URGENCY_COLD_START
    return holder.current()


@dataclass
class PriorDriveUrgencyHolder:
    """Owner: composition (R62).

    Purpose:
        Carry the prior tick's real `18` proactive-drive urgency forward into the next tick's `09`
        gate signal, since `18` runs after `09` in the tick. Mirrors the R49 recall-directive and
        R55 temporal cross-tick carry seams.

    Notes:
        Owner-neutral carry. `set_from_drive_state` projects the `18` owner's already-published
        `outward_drive` (a bounded raw fact, clamped into the gate's `[0,1]` input range, exactly
        as R48 clamps the published `07` activation); it computes no `18` disposition. `current()`
        returns the carried value, defaulting to the documented neutral cold-start until the first
        `18` drive exists.
    """

    urgency: float = _DRIVE_URGENCY_COLD_START

    def set_from_drive_state(self, drive_state) -> None:
        """Owner: composition. Set the carried urgency from a published `18` `ProactiveDriveState`."""

        components = getattr(drive_state, "pressure_components", None) or {}
        outward_drive = components.get("outward_drive", 0.0)
        if isinstance(outward_drive, bool) or not isinstance(outward_drive, (int, float)):
            return
        self.urgency = _clamp(float(outward_drive), 0.0, 1.0)

    def current(self) -> float:
        """Owner: composition. Return the carried prior-tick drive urgency (bounded)."""

        return self.urgency


# R63: documented cold-start fallback values for the `09` gate's `selected_stimuli` projection.
# Used when the `03` appraisal result is absent from the frame (e.g. an assembly that does not
# run the appraisal stage).  These match the default assembly's first-version estimator outputs
# (aggregate 0.7 from the raised FirstVersionAggregateEstimator, novelty 0.6 and uncertainty 0.3
# from FirstVersionDimensionEstimator), so the fallback reproduces the default assembly's real
# appraisal values.  They are defined baselines, not fabricated high stimuli.
_STIMULUS_INTENSITY_COLD_START = 0.7
_NOVELTY_SIGNAL_COLD_START = 0.6
_SENSITIZATION_SIGNAL_COLD_START = 0.3


def _selected_stimuli_from_appraisal(
    frame, tick_id: int
) -> tuple[SelectedStimulusSummary, ...]:
    """Owner: composition (R63). Project real `03` appraisal salience into the gate's selected_stimuli.

    Reads the `03` ``RapidSalienceAppraisalStageResult`` from ``frame.stage_results`` and projects
    batch-max ``aggregate`` → ``stimulus_intensity``, batch-max ``novelty`` → ``novelty_signal``,
    batch-max ``uncertainty`` → ``sensitization_signal``.  Each value is clamped to ``[0, 1]`` and
    rounded for determinism.  Falls back to documented cold-start constants when the appraisal
    result is absent or the batch is empty.

    Notes:
        Owner-neutral glue (R63, mirroring the R61 mismatch bridge pattern).  It reads only
        already-published `03` values and applies no gate semantic; the `09` owner keeps the
        gate weights and decision policy.
    """

    from helios_v2.runtime.stages import RapidSalienceAppraisalStageResult

    stage_results = frame.stage_results or {}
    appraisal = stage_results.get("rapid_salience_appraisal")
    if isinstance(appraisal, RapidSalienceAppraisalStageResult) and appraisal.batch.appraisals:
        batch = appraisal.batch.appraisals
        intensity = _clamp(max(a.salience.aggregate for a in batch), 0.0, 1.0)
        novelty = _clamp(max(a.salience.novelty for a in batch), 0.0, 1.0)
        sensitization = _clamp(max(a.salience.uncertainty for a in batch), 0.0, 1.0)
    else:
        intensity = _STIMULUS_INTENSITY_COLD_START
        novelty = _NOVELTY_SIGNAL_COLD_START
        sensitization = _SENSITIZATION_SIGNAL_COLD_START
    return (
        SelectedStimulusSummary(
            stimulus_id=f"stimulus:runtime:{tick_id}",
            source_kind="external_text",
            source_channel_id="cli",
            stimulus_intensity=round(intensity, 4),
            novelty_signal=round(novelty, 4),
            sensitization_signal=round(sensitization, 4),
        ),
    )


# R60: maximum number of salient tokens projected from a perceived stimulus into the memory
# binding context. A small bound keeps the content packet compact; tokens are real substrings.
_MAX_SALIENT_TOKENS = 8


def _tokens_from(text: str) -> tuple[str, ...]:
    """Owner: composition (R60). Mechanically tokenize real perceived content into salient tokens.

    Lowercases, splits on non-alphanumeric runs, drops empties, de-duplicates preserving first-seen
    order, and caps at `_MAX_SALIENT_TOKENS`. It fabricates nothing: every returned token is a
    substring of the real perceived content (`ARCHITECTURE_PHILOSOPHY` §4.3/§8 forbids inventing
    content). Punctuation-only content yields an empty tuple (the binding context still carries real
    summary/context provenance, so the `MemoryContentPacket` invariant holds).
    """

    import re

    seen: dict[str, None] = {}
    for token in re.findall(r"[0-9a-z]+", text.lower()):
        if token not in seen:
            seen[token] = None
        if len(seen) >= _MAX_SALIENT_TOKENS:
            break
    return tuple(seen.keys())


def _external_stimulus_present(frame) -> bool:
    """Owner: composition (R55). Read whether the current tick carries an external stimulus.

    Reads the `02` sensory batch and returns True when any stimulus has a non-internal modality (an
    external task is present), False otherwise (rest). A missing `02` result is treated as rest (a
    defined reading, consistent with an empty tick). This is a raw situational fact; the rest-to-DMN
    mapping is owned by the `helios_v2.temporal` owner.
    """

    from helios_v2.runtime.stages import SensoryIngressStageResult

    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult):
        return False
    return any(stimulus.modality not in _INTERNAL_MODALITIES for stimulus in sensory.batch.stimuli)


def _temporal_inputs(frame, temporal_source) -> tuple[float, bool]:
    """Owner: composition (R55). Resolve the `09` gate's temporal/DMN inputs.

    When no temporal source is wired, returns the first-version constants `(0.4, True)` byte-for-byte
    so assemblies without a temporal source are unchanged. When a source is wired, returns its bounded
    `temporal_signal` and rest-derived `dmn_available` for the current tick. Owner-neutral glue: it
    forwards raw facts and the source's outputs; the `09` owner keeps the gate weights.
    """

    if temporal_source is None:
        return 0.4, True
    sample = temporal_source.sample(_external_stimulus_present(frame))
    return sample.temporal_signal, sample.dmn_available


@dataclass
class FirstVersionDirectedRetrievalRequestBridge:
    """Owner: composition.

    Purpose:
        Build the directed-retrieval request from the thought-gating result.

    Notes:
        Owner-neutral glue. It preserves the upstream gate-result id and continuation flag
        and forwards a bounded recall intent; it does not decide tiered selection policy.
    """

    def build_request(self, frame, thought_gating_result) -> RetrievalRequest:
        tick_id = frame.tick_id
        return RetrievalRequest(
            request_id=f"retrieval-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            compact_stimuli=thought_gating_result.result.selected_stimuli,
            recall_intent="remember runtime chain context",
            selected_memory_refs=(f"memory:runtime:{tick_id}",),
            target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
            limit=2,
            tick_id=tick_id,
        )


@dataclass
class PriorThoughtRecallHolder:
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Carry the prior tick's `11` internal-thought `MemoryHandoffDirective` projection
        (its `recall_intent` and `selected_memory_refs`) forward to the current tick's `10`
        directed-retrieval request, so the thought owner's saved recall intent steers the next
        tick's retrieval.

    Notes:
        Owner-neutral carry, mirroring `TimelineViewHolder`. The runtime captures the `11`-owned
        directive after each tick (clearing the holder when no directive was saved); the
        directed-retrieval request bridge reads it next tick. It transports `11`-owned values
        verbatim and computes no retrieval policy.
    """

    recall_intent: str | None = None
    selected_memory_refs: tuple[str, ...] = ()

    def set_directive(self, recall_intent: str | None, selected_memory_refs: tuple[str, ...]) -> None:
        """Owner: composition. Store the prior tick's `11` recall directive (or clear it)."""

        self.recall_intent = recall_intent
        self.selected_memory_refs = tuple(selected_memory_refs)

    def clear(self) -> None:
        """Owner: composition. Clear the carry (no prior recall directive for the next tick)."""

        self.recall_intent = None
        self.selected_memory_refs = ()


@dataclass
class ThoughtDirectedRetrievalRequestBridge:
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Build the directed-retrieval request from the thought-gating result, sourcing
        `recall_intent` and `selected_memory_refs` from the prior tick's `11` recall directive
        (carried in the holder) so retrieval is memory-guided by the thought the system chose to
        continue. When the holder carries no directive (the first tick, a non-fired tick, or a
        tick where `11` did not continue), it falls back to the real `09` `compact_stimuli`
        exactly as the first-version bridge, with no recall intent.

    Notes:
        Owner-neutral glue. The carried `recall_intent`/`selected_memory_refs` are `11`-owned
        values transported verbatim; this bridge computes no retrieval policy and decides no
        tiered selection (that stays in `10`). `compact_stimuli` is always the real `09`
        selected-stimulus summaries, so the request stays valid even with no carried intent.
    """

    holder: PriorThoughtRecallHolder

    def build_request(self, frame, thought_gating_result) -> RetrievalRequest:
        tick_id = frame.tick_id
        return RetrievalRequest(
            request_id=f"retrieval-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            compact_stimuli=thought_gating_result.result.selected_stimuli,
            recall_intent=self.holder.recall_intent,
            selected_memory_refs=self.holder.selected_memory_refs,
            target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
            limit=2,
            tick_id=tick_id,
        )


@dataclass
class FirstVersionEmbodiedPromptRequestBridge:
    """Owner: composition.

    Purpose:
        Build the thought and outward-expression embodied-prompt requests for one tick.

    Notes:
        Owner-neutral glue. It forwards bounded current-cycle summaries and preserves the
        upstream conscious-state, gate-result, and retrieval-bundle ids; it does not render
        the prompt or decide prompt-layering policy.
    """

    def build_requests(
        self,
        frame,
        conscious_result,
        thought_gating_result,
        directed_retrieval_result,
    ) -> tuple[EmbodiedPromptRequest, ...]:
        tick_id = frame.tick_id
        stimulus_summary = {
            "present_field": "A cli text stimulus is present in the current sensory field.",
        }
        state_summary = {
            "affective_summary": "arousal is elevated and attention is focused on the current cue",
            "continuation_summary": "continuation pressure is active for the current external stimulus",
        }
        retrieval_summary = {
            "retrieval_context": "short-term context and autobiographical continuity trace are both active",
            "continuity_context": "preserve the current user anchor and current unresolved reply obligation",
        }
        capability_summary = {
            "available_channels": ("cli",),
            "available_ops": ("reply_message",),
            "forbidden_capabilities": ("direct_execution", "invented_channel"),
        }
        identity_boundary_summary = {
            "identity_boundary": "identity revision remains proposal-only and governance-validated",
        }
        conscious_state_id = conscious_result.state.state_id
        gate_result_id = thought_gating_result.result.result_id
        bundle_id = directed_retrieval_result.bundle.bundle_id
        return (
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:thought:runtime:{tick_id}",
                consumer_kind="thought",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:outward-expression:runtime:{tick_id}",
                consumer_kind="outward_expression",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
        )


@dataclass
class FirstVersionInternalThoughtRequestBridge:
    """Owner: composition.

    Purpose:
        Build the internal-thought request from gating, retrieval, and prompt results.

    Notes:
        Owner-neutral glue. It preserves the upstream gate-result and retrieval-bundle ids
        and forwards a bounded prompt-contract summary; it does not perform thought.
    """

    def build_request(
        self,
        frame,
        thought_gating_result,
        directed_retrieval_result,
        prompt_result,
    ) -> InternalThoughtRequest:
        tick_id = frame.tick_id
        thought_contract = next(
            contract for contract in prompt_result.contracts if contract.consumer_kind == "thought"
        )
        return InternalThoughtRequest(
            request_id=f"internal-thought-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            internal_state_summary="runtime state summary",
            prompt_contract_summary={
                "contract_id": thought_contract.contract_id,
                "consumer_kind": thought_contract.consumer_kind,
                "layer_names": tuple(layer.layer_name for layer in thought_contract.layers),
                "supports_external_action_proposal": thought_contract.action_boundary.supports_external_action_proposal,
                "supports_self_revision_proposal": thought_contract.action_boundary.supports_self_revision_proposal,
            },
            tick_id=tick_id,
        )


# ---------------------------------------------------------------------------
# R70: Prompt-to-thought real-state bridges (semantic assembly).
# Under semantic_memory_enabled, these bridges read the real 02-10 owner state
# from the tick frame and project it into bounded English text, replacing the
# constant-shim strings in FirstVersion*Bridge. Owner-neutral: they forward
# bounded raw facts only and derive no cognitive policy.
# ---------------------------------------------------------------------------


def _present_field_text(frame) -> str:
    """Owner: composition (R70). Project the real `02` sensory batch into present_field text.

    Reads the `02` sensory batch and returns a bounded English sentence describing the
    external stimulus content when present, or an honest "no external stimulus" marker when
    absent. Owner-neutral glue: it forwards a raw situational fact; prompt-contract policy
    is owned by `16`.
    """

    from helios_v2.runtime.stages import SensoryIngressStageResult

    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult) or not sensory.batch.stimuli:
        return "No external stimulus this cycle; only internal body signals present."
    external = [s for s in sensory.batch.stimuli if s.modality not in _INTERNAL_MODALITIES]
    if not external:
        return "No external stimulus this cycle; only internal body signals present."
    primary = external[0]
    # Truncate content to keep the text bounded (under 200 chars total).
    content_preview = primary.content[:80]
    return f"External stimulus present: '{content_preview}' (modality: {primary.modality})."


def _affective_summary_text(frame) -> str:
    """Owner: composition (R70). Project the real `05` feeling vector into affective_summary text.

    Reads the `05` InteroceptiveFeelingStageResult and returns a bounded English sentence
    naming the dominant feeling dimensions with their real [0,1] values. Owner-neutral glue:
    it forwards bounded raw facts; affective interpretation is owned by `05`.
    """

    from helios_v2.runtime.stages import InteroceptiveFeelingStageResult

    stage_results = frame.stage_results or {}
    # R78: align with stages.py:1105 "interoceptive_feeling_layer".
    feeling_result = stage_results.get("interoceptive_feeling_layer")
    if not isinstance(feeling_result, InteroceptiveFeelingStageResult):
        return "Affect baseline; no computed feeling state."
    feeling = feeling_result.state.feeling
    # Identify dominant dimensions (above a meaningful threshold).
    dims = {
        "arousal": feeling.arousal,
        "valence": feeling.valence,
        "tension": feeling.tension,
        "comfort": feeling.comfort,
        "fatigue": feeling.fatigue,
        "pain_like": feeling.pain_like,
        "social_safety": feeling.social_safety,
    }
    # Sort by value descending, take top 3 significant dimensions.
    ranked = sorted(dims.items(), key=lambda item: item[1], reverse=True)
    significant = [(name, val) for name, val in ranked if val >= 0.1]
    top = significant[:3]
    if not top:
        return "Affect baseline; all dimensions near zero."
    parts = [f"{name} {val:.2f}" for name, val in top]
    dominant = top[0][0]
    return f"{', '.join(parts)}; dominant: {dominant}."


def _continuation_summary_text(frame, thought_gating_result) -> str:
    """Owner: composition (R70). Project the real `09` gate/continuation state into continuation_summary text.

    Reads the `09` ThoughtGatingStageResult continuation_state and the gate decision to
    produce a bounded English sentence. Owner-neutral glue: it forwards raw facts; gate
    decision semantics are owned by `09`.
    """

    continuation_active = thought_gating_result.continuation_state.active
    decision = thought_gating_result.result.decision
    if continuation_active:
        return f"Continuation pressure active; gate decision: {decision}."
    return f"No continuation pressure; gate decision: {decision}."


def _retrieval_context_text(frame, directed_retrieval_result) -> str:
    """Owner: composition (R70). Project the real `10` retrieval bundle into retrieval_context text.

    Reads the `10` DirectedRetrievalStageResult bundle tier counts and returns a bounded
    English sentence describing which memory tiers are present. Owner-neutral glue: it
    forwards raw tier-presence facts; retrieval policy is owned by `10`.
    """

    bundle = directed_retrieval_result.bundle
    if bundle is None:
        return "No retrieval context available."
    st_count = len(bundle.short_term_context)
    mt_count = len(bundle.mid_term_hits)
    ab_count = len(bundle.autobiographical_hits)
    parts = []
    if st_count > 0:
        parts.append(f"short-term context ({st_count})")
    if mt_count > 0:
        parts.append(f"{mt_count} mid-term hit(s)")
    if ab_count > 0:
        parts.append(f"{ab_count} autobiographical anchor(s)")
    if not parts:
        return "Retrieval context empty; no memory tiers available."
    return f"Retrieval context: {'; '.join(parts)}."


def _continuity_context_text(directed_retrieval_result) -> str:
    """Owner: composition (R70). Project the real `10` retrieval bundle content into continuity_context text.

    Reads the `10` bundle's first available content summary (short-term > autobiographical)
    and returns a bounded English sentence. Returns "no active continuity trace" when
    no content is available. Owner-neutral glue: it forwards raw content facts.
    """

    bundle = directed_retrieval_result.bundle
    if bundle is None:
        return "No active continuity trace this cycle."
    # Prefer short-term context as the most immediate continuity obligation.
    if bundle.short_term_context:
        summary = bundle.short_term_context[0].summary[:80]
        return f"Current continuity: '{summary}'."
    if bundle.autobiographical_hits:
        summary = bundle.autobiographical_hits[0].summary[:80]
        return f"Autobiographical anchor: '{summary}'."
    return "No active continuity trace this cycle."


def _internal_state_text(frame) -> str:
    """Owner: composition (R70). Project the real `03`/`04`/`05` state into internal_state_summary text.

    Reads the `04` NeuromodulatorStageResult levels, `05` InteroceptiveFeelingStageResult feeling,
    and `03` RapidSalienceAppraisalStageResult batch-max salience to produce a bounded English
    projection of the current neuromodulator, feeling, and salience landscape. Owner-neutral glue:
    it forwards bounded raw facts; all interpretation policy is owned by the respective owners.
    """

    from helios_v2.runtime.stages import (
        NeuromodulatorStageResult,
        InteroceptiveFeelingStageResult,
        RapidSalienceAppraisalStageResult,
    )

    stage_results = frame.stage_results or {}

    # Neuromodulator levels.
    # R78: align with stages.py:1044 "neuromodulator_system".
    nm_result = stage_results.get("neuromodulator_system")
    if isinstance(nm_result, NeuromodulatorStageResult):
        levels = nm_result.state.levels
        nm_text = (
            f"DA {levels.dopamine:.2f} NE {levels.norepinephrine:.2f} "
            f"5-HT {levels.serotonin:.2f} ACh {levels.acetylcholine:.2f} "
            f"Cort {levels.cortisol:.2f}"
        )
    else:
        nm_text = "neuromodulators at tonic baseline"

    # Feeling vector.
    # R78: align with stages.py:1105 "interoceptive_feeling_layer".
    feeling_result = stage_results.get("interoceptive_feeling_layer")
    if isinstance(feeling_result, InteroceptiveFeelingStageResult):
        feeling = feeling_result.state.feeling
        feel_text = f"arousal {feeling.arousal:.2f}, valence {feeling.valence:.2f}, tension {feeling.tension:.2f}"
    else:
        feel_text = "feeling at baseline"

    # Salience landscape (batch-max aggregate + top dimension).
    appraisal_result = stage_results.get("rapid_salience_appraisal")
    if isinstance(appraisal_result, RapidSalienceAppraisalStageResult) and appraisal_result.batch.appraisals:
        appraisals = appraisal_result.batch.appraisals
        max_agg = max(a.salience.aggregate for a in appraisals)
        # Find the dimension with the highest value in the max-aggregate appraisal.
        max_appraisal = max(appraisals, key=lambda a: a.salience.aggregate)
        sal_dims = {
            "threat": max_appraisal.salience.threat,
            "reward": max_appraisal.salience.reward,
            "novelty": max_appraisal.salience.novelty,
            "social": max_appraisal.salience.social,
            "uncertainty": max_appraisal.salience.uncertainty,
        }
        top_dim = max(sal_dims, key=sal_dims.get)
        sal_text = f"aggregate {max_agg:.2f}, top dimension: {top_dim}"
    else:
        sal_text = "salience at baseline"

    return f"Neuromodulators: {nm_text}. Feeling: {feel_text}. Salience: {sal_text}."


@dataclass
class SemanticEmbodiedPromptRequestBridge:
    """Owner: composition (R70).

    Purpose:
        Build the thought and outward-expression embodied-prompt requests for one tick,
        deriving summary text from the real `02`/`05`/`09`/`10` owner state in the frame
        instead of constant English sentences.

    Notes:
        Owner-neutral glue. It forwards bounded current-cycle summary text derived from
        published stage results and preserves the upstream conscious-state, gate-result, and
        retrieval-bundle ids; it does not render the prompt or decide prompt-layering policy.
        Activated under `semantic_memory_enabled == True`; `FirstVersionEmbodiedPromptRequestBridge`
        remains available for `legacy_constant` mode.
    """

    def build_requests(
        self,
        frame,
        conscious_result,
        thought_gating_result,
        directed_retrieval_result,
    ) -> tuple[EmbodiedPromptRequest, ...]:
        tick_id = frame.tick_id
        stimulus_summary = {
            "present_field": _present_field_text(frame),
        }
        state_summary = {
            "affective_summary": _affective_summary_text(frame),
            "continuation_summary": _continuation_summary_text(frame, thought_gating_result),
        }
        retrieval_summary = {
            "retrieval_context": _retrieval_context_text(frame, directed_retrieval_result),
            "continuity_context": _continuity_context_text(directed_retrieval_result),
        }
        # capability_summary and identity_boundary_summary remain composition-level
        # constants (not derived from owner state) — they describe available channels,
        # ops, and governance boundaries, which are assembly configuration, not cognition.
        capability_summary = {
            "available_channels": ("cli",),
            "available_ops": ("reply_message",),
            "forbidden_capabilities": ("direct_execution", "invented_channel"),
        }
        identity_boundary_summary = {
            "identity_boundary": "identity revision remains proposal-only and governance-validated",
        }
        conscious_state_id = conscious_result.state.state_id
        gate_result_id = thought_gating_result.result.result_id
        bundle_id = directed_retrieval_result.bundle.bundle_id
        return (
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:thought:runtime:{tick_id}",
                consumer_kind="thought",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:outward-expression:runtime:{tick_id}",
                consumer_kind="outward_expression",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
        )


def _attention_field_from_frame(frame, present_field, directed_retrieval_result) -> dict:
    """Owner: composition (R79). Project a focused/peripheral/filtered attention field.

    First-version owner-neutral projection: focused = the present external field; peripheral =
    active retrieval/continuity cues; filtered = internal body signals present but not in focus.
    A deeper `07`/`08` focal mapping is a later refinement. It forwards bounded raw facts only.
    """

    from helios_v2.runtime.stages import SensoryIngressStageResult

    peripheral: list[str] = []
    bundle = getattr(directed_retrieval_result, "bundle", None)
    if bundle is not None:
        if bundle.short_term_context:
            peripheral.append(f"short-term: {bundle.short_term_context[0].summary[:60]}")
        if bundle.autobiographical_hits:
            peripheral.append(f"recalled: {bundle.autobiographical_hits[0].summary[:60]}")
    filtered: list[str] = []
    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if isinstance(sensory, SensoryIngressStageResult):
        internal = [s for s in sensory.batch.stimuli if s.modality in _INTERNAL_MODALITIES]
        if internal:
            filtered.append("internal body signals present but not in focus this moment")
    return {
        "focused": present_field,
        "peripheral": tuple(peripheral),
        "filtered": tuple(filtered),
    }


def _identity_self_summary_from_carry(carry) -> str:
    """Owner: composition (R79). Render the v3 identity self-summary from the `14` governance carry.

    Identity content is owned by `14`: this projects the prior-tick governed
    `identity_state_snapshot` (`self_definition` / `identity_narrative`) into a bounded
    first-person line, or a continuity cold-start on the first tick (before any `14` carry
    exists). It never asserts a hardcoded persona; the prompt path is a pure formatter of this
    owner-sourced text.
    """

    snapshot = getattr(carry, "identity_state_snapshot", None) if carry is not None else None
    if snapshot:
        snap = dict(snapshot)
        parts: list[str] = []
        self_def = snap.get("self_definition")
        narrative = snap.get("identity_narrative")
        if isinstance(self_def, str) and self_def:
            parts.append(self_def)
        if isinstance(narrative, str) and narrative:
            parts.append(narrative)
        if parts:
            return "Who I am, from my governed identity state: " + " ".join(parts)
    return "Who I am: a continuous presence that carries its state and memory forward across ticks."


@dataclass
class OwnerGroundedEmbodiedPromptRequestBridge:
    """Owner: composition (R79, v3 owner-grounded embodied prompt).

    Purpose:
        Build the v3 thought and outward-expression embodied-prompt requests, filling the
        additive owner-grounded keys the `OwnerGroundedEmbodiedPromptPath` reads:
        `identity_self_summary` (from the prior-tick `14` governance carry), `attention_field`
        (focused/peripheral/filtered from the real frame), and `ready_channels`.

    Notes:
        Owner-neutral glue. It reuses the R70 real-state projections for the present field,
        affect, continuation, and retrieval text; identity content is owned by `14` (this bridge
        only renders the prior-tick snapshot or a continuity cold-start), attention tiers are
        projected from the real frame, and `ready_channels` are the assembly's bound channels.
        It derives no cognitive policy and renders no prompt.
    """

    identity_carry_provider: "Callable[[], GovernanceCarryState | None] | None" = None

    def build_requests(
        self,
        frame,
        conscious_result,
        thought_gating_result,
        directed_retrieval_result,
    ) -> tuple[EmbodiedPromptRequest, ...]:
        tick_id = frame.tick_id
        present_field = _present_field_text(frame)
        attention_field = _attention_field_from_frame(
            frame, present_field, directed_retrieval_result
        )
        carry = (
            self.identity_carry_provider()
            if self.identity_carry_provider is not None
            else None
        )
        identity_self_summary = _identity_self_summary_from_carry(carry)
        stimulus_summary = {
            "present_field": present_field,
            "attention_field": attention_field,
        }
        state_summary = {
            "affective_summary": _affective_summary_text(frame),
            "continuation_summary": _continuation_summary_text(frame, thought_gating_result),
        }
        retrieval_summary = {
            "retrieval_context": _retrieval_context_text(frame, directed_retrieval_result),
            "continuity_context": _continuity_context_text(directed_retrieval_result),
        }
        capability_summary = {
            "available_channels": ("cli",),
            "available_ops": ("reply_message",),
            "forbidden_capabilities": ("direct_execution", "invented_channel"),
            "ready_channels": ("cli",),
        }
        identity_boundary_summary = {
            "identity_boundary": "identity revision remains proposal-only and governance-validated",
            "identity_self_summary": identity_self_summary,
        }
        conscious_state_id = conscious_result.state.state_id
        gate_result_id = thought_gating_result.result.result_id
        bundle_id = directed_retrieval_result.bundle.bundle_id
        return (
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:thought:runtime:{tick_id}",
                consumer_kind="thought",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
            EmbodiedPromptRequest(
                request_id=f"embodied-prompt-request:outward-expression:runtime:{tick_id}",
                consumer_kind="outward_expression",
                source_conscious_state_id=conscious_state_id,
                source_gate_result_id=gate_result_id,
                source_retrieval_bundle_id=bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=tick_id,
            ),
        )


@dataclass
class SemanticInternalThoughtRequestBridge:
    """Owner: composition (R70).

    Purpose:
        Build the internal-thought request from gating, retrieval, and prompt results,
        deriving `internal_state_summary` from the real `03`/`04`/`05` owner state instead
        of the constant string "runtime state summary".

    Notes:
        Owner-neutral glue. It preserves the upstream gate-result and retrieval-bundle ids
        and forwards a bounded prompt-contract summary; it does not perform thought.
        Activated under `semantic_memory_enabled == True`; `FirstVersionInternalThoughtRequestBridge`
        remains available for `legacy_constant` mode.
    """

    def build_request(
        self,
        frame,
        thought_gating_result,
        directed_retrieval_result,
        prompt_result,
    ) -> InternalThoughtRequest:
        tick_id = frame.tick_id
        thought_contract = next(
            contract for contract in prompt_result.contracts if contract.consumer_kind == "thought"
        )
        return InternalThoughtRequest(
            request_id=f"internal-thought-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            internal_state_summary=_internal_state_text(frame),
            prompt_contract_summary={
                "contract_id": thought_contract.contract_id,
                "consumer_kind": thought_contract.consumer_kind,
                "layer_names": tuple(layer.layer_name for layer in thought_contract.layers),
                "supports_external_action_proposal": thought_contract.action_boundary.supports_external_action_proposal,
                "supports_self_revision_proposal": thought_contract.action_boundary.supports_self_revision_proposal,
            },
            tick_id=tick_id,
        )


@dataclass
class FirstVersionThoughtExternalizationRequestBridge:
    """Owner: composition.

    Purpose:
        Build the thought-externalization request from the internal-thought result.

    Notes:
        Owner-neutral glue. It preserves the thought-cycle-result id and whether a proposal
        carrier is present; it does not decide externalization acceptance.
    """

    def build_request(self, frame, internal_thought_result) -> ThoughtExternalizationRequest:
        tick_id = frame.tick_id
        return ThoughtExternalizationRequest(
            request_id=f"externalization-request:runtime:{tick_id}",
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            proposal_carrier_present=internal_thought_result.result.action_proposal is not None,
            target_binding_context={"target_user_id": f"user:runtime:{tick_id}"},
            channel_hint_context={"channel_family": "cli"},
            tick_id=tick_id,
        )


@dataclass
class FirstVersionOutwardExpressionExternalizationRequestBridge:
    """Owner: composition.

    Purpose:
        Build the outward-expression externalization request from the outward-expression draft.

    Notes:
        Owner-neutral glue. It forwards the explicit draft fields verbatim and preserves the
        draft and prompt-contract provenance ids; it does not hold execution authority.
    """

    def build_request(self, frame, outward_expression_result) -> OutwardExpressionExternalizationRequest:
        del frame
        draft = outward_expression_result.draft
        return OutwardExpressionExternalizationRequest(
            request_id=f"outward-expression-externalization-request:{draft.draft_id}",
            source_outward_expression_draft_id=draft.draft_id,
            source_prompt_contract_id=draft.source_prompt_contract_id,
            rendered_prompt=draft.rendered_prompt,
            delivery_channels=draft.delivery_channels,
            delivery_ops=draft.delivery_ops,
            delivery_guidance=draft.delivery_guidance,
            forbidden_capabilities=draft.forbidden_capabilities,
            final_authorities=draft.final_authorities,
            anti_theatrical_constraints=draft.anti_theatrical_constraints,
        )


@dataclass
class FirstVersionPlannerBridgeRequestBridge:
    """Owner: composition.

    Purpose:
        Build the planner-bridge request from the action-externalization result.

    Notes:
        Owner-neutral glue. It preserves the externalization-result id and forwards bounded
        behavior, channel-descriptor, and channel-status snapshots; it does not decide
        acceptance. The snapshots are explicit assembly inputs, not owner judgment.
    """

    def build_request(self, frame, action_externalization_result) -> PlannerBridgeRequest:
        tick_id = frame.tick_id
        return PlannerBridgeRequest(
            request_id=f"planner-bridge-request:runtime:{tick_id}",
            source_externalization_result_id=action_externalization_result.result.result_id,
            normalized_proposal_present=action_externalization_result.result.normalized_proposal is not None,
            behavior_snapshot={
                "registered": True,
                "reviewed": True,
                "minimum_score": 0.5,
                "proposal_score": 0.9,
                "execution_priority": 2,
            },
            channel_descriptor_snapshot={
                "cli": {
                    "supported_ops": ("reply_message",),
                    "output_ops": ("reply_message",),
                }
            },
            channel_status_snapshot={
                "cli": {
                    "available": True,
                    "bound": True,
                    "execute_now": True,
                    "execution_success": True,
                }
            },
            tick_id=tick_id,
        )


@dataclass
class ChannelBackedPlannerBridgeRequestBridge:
    """Owner: composition (channel-bound assembly only).

    Purpose:
        Build the planner-bridge request from the action-externalization result, sourcing the
        channel descriptor/status snapshots from the real channel subsystem state instead of
        the hardcoded shim.

    Notes:
        Owner-neutral glue. It mirrors `FirstVersionPlannerBridgeRequestBridge` for the
        behavior snapshot and provenance, but delegates the channel snapshots to the injected
        `ChannelSubsystemStateProvider`. It does not decide acceptance; the planner still owns
        selection/acceptance, and the real transport happens in the outbound dispatch stage.
    """

    state_provider: ChannelSubsystemStateProvider

    def build_request(self, frame, action_externalization_result) -> PlannerBridgeRequest:
        tick_id = frame.tick_id
        return PlannerBridgeRequest(
            request_id=f"planner-bridge-request:runtime:{tick_id}",
            source_externalization_result_id=action_externalization_result.result.result_id,
            normalized_proposal_present=action_externalization_result.result.normalized_proposal is not None,
            behavior_snapshot={
                "registered": True,
                "reviewed": True,
                "minimum_score": 0.5,
                "proposal_score": 0.9,
                "execution_priority": 2,
            },
            channel_descriptor_snapshot=self.state_provider.channel_descriptor_snapshot(),
            channel_status_snapshot=self.state_provider.channel_status_snapshot(),
            tick_id=tick_id,
        )


@dataclass
class FirstVersionIdentityGovernanceRequestBridge:
    """Owner: composition.

    Purpose:
        Build the identity-governance request from the internal-thought result.

    Notes:
        Owner-neutral glue. It preserves the thought-cycle-result and proposal ids and
        forwards bounded proposal and identity-state snapshots; it does not decide the
        revision outcome. When no self-revision proposal is present, it returns a
        proposal-absent request so governance can still run.

        When a ``carry_state_provider`` is wired by composition, the bridge reads the
        current ``GovernanceCarryState`` at request-build time and injects its identity
        snapshot and trace history into the request. When no provider is set (or the
        provider returns ``None``), the bridge falls back to the cold-start bootstrap
        constant so the first tick is byte-for-byte identical to the pre-carry behavior.
    """

    def __init__(
        self,
        carry_state_provider: Callable[[], GovernanceCarryState | None] | None = None,
    ) -> None:
        self.carry_state_provider = carry_state_provider

    def _resolve_carry_state(self) -> GovernanceCarryState | None:
        if self.carry_state_provider is None:
            return None
        return self.carry_state_provider()

    def _build_identity_state_snapshot(self, carry_state: GovernanceCarryState | None) -> dict:
        if carry_state is not None:
            return dict(carry_state.identity_state_snapshot)
        return {
            "self_definition": "runtime identity definition",
            "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
            "identity_metadata": {},
            "current_revision": "bootstrap",
            "revision_history_length": 0,
        }

    def _build_governance_trace_summary(self, carry_state: GovernanceCarryState | None) -> dict:
        if carry_state is None or not carry_state.recent_governance_trace_history:
            return {}
        history = carry_state.recent_governance_trace_history
        status_counts: dict[str, int] = {}
        for entry in history:
            status = str(entry.get("revision_status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "total_ticks_observed": len(history),
            "revision_status_counts": status_counts,
            "accepted_revision_count": carry_state.accepted_revision_count,
            "rejected_revision_count": carry_state.rejected_revision_count,
        }

    def _build_recent_trace_history(self, carry_state: GovernanceCarryState | None) -> tuple:
        if carry_state is not None:
            return tuple(carry_state.recent_governance_trace_history)
        return ()

    def build_request(self, frame, internal_thought_result) -> IdentityGovernanceRequest:
        tick_id = frame.tick_id
        proposal = internal_thought_result.result.self_revision_proposal
        proposal_present = proposal is not None
        proposal_id = proposal.proposal_id if proposal is not None else ""
        if proposal is not None:
            proposal_snapshot = {
                "owner_path": "self_revision_governance_bridge",
                "revision_type": "autobiographical_identity_narrative_revision",
                "requested_change": {"narrative_summary": proposal.requested_change_summary},
                "confidence": 0.78,
                "reason_trace": (proposal.reason_trace,),
            }
        else:
            proposal_snapshot = {}
        carry_state = self._resolve_carry_state()
        return IdentityGovernanceRequest(
            request_id=f"identity-governance-request:runtime:{tick_id}",
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            source_proposal_id=proposal_id,
            proposal_present=proposal_present,
            proposal_snapshot=proposal_snapshot,
            identity_state_snapshot=self._build_identity_state_snapshot(carry_state),
            governance_trace_summary=self._build_governance_trace_summary(carry_state),
            recent_governance_trace_history=self._build_recent_trace_history(carry_state),
            tick_id=tick_id,
        )


@dataclass
class FirstVersionExperienceWritebackRequestBridge:
    """Owner: composition.

    Purpose:
        Build experience-writeback requests from the planner-bridge and governance results.

    Notes:
        Owner-neutral glue. It preserves planner and governance provenance ids and forwards
        bounded outcome summaries; it does not decide consolidation policy. It only emits a
        request for an outcome that actually has the upstream evidence it references.
    """

    def build_requests(
        self,
        frame,
        planner_bridge_result,
        identity_governance_result,
    ) -> tuple[ExperienceWritebackRequest, ...]:
        tick_id = frame.tick_id
        requests: list[ExperienceWritebackRequest] = []

        planner_decision = planner_bridge_result.result.action_decision
        planner_feedback = planner_bridge_result.execution_feedback
        if planner_decision is not None and planner_feedback is not None:
            requests.append(
                ExperienceWritebackRequest(
                    request_id=f"experience-writeback-request:planner:runtime:{tick_id}",
                    source_outcome_kind="planner_bridge",
                    source_outcome_id=planner_bridge_result.result.result_id,
                    source_outcome_status=planner_bridge_result.result.status,
                    outcome_class="world_changed",
                    source_provenance={
                        "source_request_id": planner_bridge_result.request.request_id,
                        "proposal_id": planner_decision.proposal_id,
                        "decision_id": planner_decision.decision_id,
                        "channel_id": planner_feedback.channel_id,
                        "op_name": planner_feedback.op_name,
                    },
                    requested_effect_summary=(
                        f"{planner_decision.selected_op} via {planner_decision.selected_channel_id}"
                    ),
                    applied_effect_summary=(
                        f"{planner_feedback.op_name} reached {planner_feedback.channel_id} transport"
                    ),
                    reason_trace=("planner bridge executed the normalized external action",),
                    tick_id=tick_id,
                )
            )
        elif planner_bridge_result.result.status == "no_actionable_proposal":
            # Internal-only tick: the thought cycle fired but produced no proposal to route.
            # Record it as an explicit internal-only continuity writeback so the cycle is
            # preserved rather than dropped. Provenance links to the planner result and its
            # source request (which traces to the thought-cycle externalization).
            requests.append(
                ExperienceWritebackRequest(
                    request_id=f"experience-writeback-request:internal:runtime:{tick_id}",
                    source_outcome_kind="internal_thought_cycle",
                    source_outcome_id=planner_bridge_result.result.result_id,
                    source_outcome_status=planner_bridge_result.result.status,
                    outcome_class="internal_only",
                    source_provenance={
                        "source_request_id": planner_bridge_result.request.request_id,
                    },
                    requested_effect_summary="no outward action this cycle",
                    applied_effect_summary="thinking cycle concluded internally without outward action",
                    reason_trace=("thought cycle produced no actionable proposal",),
                    tick_id=tick_id,
                )
            )

        revision_decision = identity_governance_result.result.revision_decision if identity_governance_result.activated else None
        applied_identity_state = (
            identity_governance_result.result.applied_identity_state
            if identity_governance_result.activated
            else None
        )
        if applied_identity_state is not None:
            requests.append(
                ExperienceWritebackRequest(
                    request_id=f"experience-writeback-request:identity:runtime:{tick_id}",
                    source_outcome_kind="identity_governance",
                    source_outcome_id=identity_governance_result.result.result_id,
                    source_outcome_status=revision_decision.status,
                    outcome_class="self_changed",
                    source_provenance={
                        "source_request_id": identity_governance_result.request.request_id,
                        "origin_thought_id": revision_decision.origin_thought_id,
                        "proposal_id": revision_decision.proposal_id,
                        "revision_id": revision_decision.revision_id,
                    },
                    requested_effect_summary="autobiographical identity narrative revision was proposed",
                    applied_effect_summary=(
                        f"identity state advanced to {applied_identity_state.current_revision}"
                    ),
                    reason_trace=revision_decision.reason_trace,
                    tick_id=tick_id,
                )
            )

        return tuple(requests)


@dataclass
class FirstVersionAutonomyRequestBridge:
    """Owner: composition.

    Purpose:
        Build the proactive-drive request from the upstream owner results for one tick by
        extracting the raw cognition facts and delegating the fact-to-drive-input mapping to
        the `18` owner's `AutonomyDriveInputProjection`.

    Notes:
        Owner-neutral glue. It preserves the upstream gate, retrieval, thought, planner,
        governance, writeback, and outward-expression provenance ids and reads the raw
        cognition facts from the published stage results. It does NOT author the
        cognition-to-pressure mapping, the planner executed/blocked classification, the
        retrieval-pull normalization, or the autonomy action threshold — those are the `18`
        owner's policy, recovered into `helios_v2.autonomy` in R57. The bridge only forwards
        raw facts and assembles the request from the owner-derived summaries.
    """

    projection: AutonomyDriveInputProjection = field(default_factory=AutonomyDriveInputProjection)

    def build_request(
        self,
        frame,
        thought_gating_result,
        directed_retrieval_result,
        internal_thought_result,
        planner_bridge_result,
        identity_governance_result,
        experience_writeback_result,
        prompt_result,
        outward_expression_result,
        outward_expression_externalization_result,
    ) -> ProactiveDriveRequest:
        tick_id = frame.tick_id
        # No-fire tick (R54): the thought path did not activate. Build the autonomy request from
        # the gate result id plus deterministic no-fire marker ids for the absent thought/retrieval/
        # outward artifacts (explicit absence, not fabricated cognition). The autonomy owner still
        # runs: it integrates continuation/continuity regardless of whether thought fired. The raw
        # cognition facts (activated=False, continuation_active carried) are forwarded to the owner
        # projection, which owns the no-fire drive-input mapping.
        if not internal_thought_result.activated:
            tick_label = tick_id if tick_id is not None else "na"
            facts = ProactiveCognitionFacts(
                activated=False,
                has_action_proposal=False,
                continuation_requested=False,
                continuation_active=thought_gating_result.continuation_state.active,
                has_self_revision=False,
                planner_status=planner_bridge_result.result.status,
                retrieval_hit_count=0,
            )
            summaries = self.projection.derive_drive_inputs(facts)
            return ProactiveDriveRequest(
                request_id=f"autonomy-request:no-fire:runtime:{tick_id}",
                source_gate_result_id=thought_gating_result.result.result_id,
                source_retrieval_bundle_id=f"no-fire-directed-retrieval:{tick_label}",
                source_thought_cycle_result_id=f"no-fire-internal-thought:{tick_label}",
                source_planner_bridge_result_id=planner_bridge_result.result.result_id,
                source_identity_governance_result_id=f"no-fire-identity-governance:{tick_label}",
                source_writeback_result_ids=tuple(
                    result.result_id for result in experience_writeback_result.results
                ),
                source_outward_expression_draft_id=f"no-fire-outward-expression:{tick_label}",
                source_outward_expression_externalization_draft_id=(
                    f"no-fire-outward-externalization:{tick_label}"
                ),
                continuation_summary=summaries["continuation_summary"],
                retrieval_pull_summary=summaries["retrieval_pull_summary"],
                temporal_pressure_summary=summaries["temporal_pressure_summary"],
                identity_unresolved_summary=summaries["identity_unresolved_summary"],
                outward_readiness_summary=summaries["outward_readiness_summary"],
            )

        bundle = directed_retrieval_result.bundle
        thought = internal_thought_result.result
        facts = ProactiveCognitionFacts(
            activated=True,
            has_action_proposal=thought.action_proposal is not None,
            continuation_requested=bool(thought.continuation_requested),
            continuation_active=thought_gating_result.continuation_state.active,
            has_self_revision=thought.self_revision_proposal is not None,
            planner_status=planner_bridge_result.result.status,
            retrieval_hit_count=len(bundle.mid_term_hits) + len(bundle.autobiographical_hits),
        )
        summaries = self.projection.derive_drive_inputs(facts)

        return ProactiveDriveRequest(
            request_id=f"autonomy-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=bundle.bundle_id,
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            source_planner_bridge_result_id=planner_bridge_result.result.result_id,
            source_identity_governance_result_id=(
                identity_governance_result.result.result_id
                if identity_governance_result.activated
                else (identity_governance_result.inactive_id or f"inactive-identity-governance:{tick_id}")
            ),
            source_writeback_result_ids=tuple(
                result.result_id for result in experience_writeback_result.results
            ),
            source_outward_expression_draft_id=outward_expression_result.draft.draft_id,
            source_outward_expression_externalization_draft_id=(
                outward_expression_externalization_result.draft.draft_id
            ),
            continuation_summary=summaries["continuation_summary"],
            retrieval_pull_summary=summaries["retrieval_pull_summary"],
            temporal_pressure_summary=summaries["temporal_pressure_summary"],
            identity_unresolved_summary=summaries["identity_unresolved_summary"],
            outward_readiness_summary=summaries["outward_readiness_summary"],
        )


@dataclass
class FirstVersionEvaluationRequestBridge:
    """Owner: composition.

    Purpose:
        Build the evaluation request and read-only evidence bundle from upstream results.

    Notes:
        Owner-neutral glue. It assembles a provenance-rich, read-only evidence bundle from
        already-public owner results plus the carried prior-tick execution-timeline view; it
        does not mutate runtime state or score fidelity. The timeline holder is supplied by
        the runtime handle and updated after each completed tick.
    """

    timeline_holder: TimelineViewHolder | None = None
    timeline_bridge: FirstVersionExecutionTimelineEvidenceBridge = field(
        default_factory=FirstVersionExecutionTimelineEvidenceBridge
    )
    prior_claim_bridge: FirstVersionPriorConsequenceClaimEvidenceBridge = field(
        default_factory=FirstVersionPriorConsequenceClaimEvidenceBridge
    )

    def build_request(
        self,
        frame,
        internal_thought_result,
        action_externalization_result,
        planner_bridge_result,
        identity_governance_result,
        experience_writeback_result,
        autonomy_result,
        prompt_result,
        outward_expression_result,
        outward_expression_externalization_result,
    ) -> EvaluationRequest:
        tick_id = frame.tick_id
        return EvaluationRequest(
            request_id=f"evaluation-request:runtime:{tick_id}",
            scenario_kind="runtime_tick",
            time_window_summary={
                "window_label": f"runtime-tick:{tick_id}",
                "current_tick_id": tick_id,
                "late_session_degradation_status": "not_evaluated",
                "specific_recall_persistence_status": "not_evaluated",
                "user_visible_anchoring_drift_status": "not_evaluated",
                "comparison_window_label": f"runtime_tick:{tick_id}",
            },
        )

    def build_evidence_bundle(
        self,
        frame,
        request,
        internal_thought_result,
        action_externalization_result,
        planner_bridge_result,
        identity_governance_result,
        experience_writeback_result,
        autonomy_result,
        prompt_result,
        outward_expression_result,
        outward_expression_externalization_result,
    ) -> EvaluationEvidenceBundle:
        tick_id = frame.tick_id
        tick_label = tick_id if tick_id is not None else "na"
        planner_result = planner_bridge_result.result
        # No-fire tick (R54): the thought-path stages are inactive. Emit explicit no-fire evidence
        # (marker ids + activated=False) rather than reading absent artifacts, so evaluation can
        # reconstruct the no-fire outcome. The planner/writeback/autonomy tail is always present.
        if not internal_thought_result.activated:
            thought_evidence = (
                {"evidence_id": f"no-fire-internal-thought:{tick_label}", "activated": False},
            )
            action_evidence = (
                {"evidence_id": f"no-fire-action-externalization:{tick_label}", "activated": False},
            )
            governance_evidence = (
                {"evidence_id": f"no-fire-identity-governance:{tick_label}", "activated": False},
            )
            prompt_evidence: tuple[dict, ...] = (
                {"evidence_id": f"no-fire-embodied-prompt:{tick_label}", "activated": False},
            )
            outward_expression_evidence = (
                {"evidence_id": f"no-fire-outward-expression:{tick_label}", "activated": False},
            )
            outward_expression_externalization_evidence = (
                {"evidence_id": f"no-fire-outward-externalization:{tick_label}", "activated": False},
            )
        else:
            thought_result = internal_thought_result.result
            action_result = action_externalization_result.result
            thought_evidence = (
                {
                    "evidence_id": thought_result.result_id,
                    "execution_status": thought_result.execution_status,
                    "action_proposal_present": thought_result.action_proposal is not None,
                },
            )
            action_evidence = (
                {
                    "evidence_id": action_result.result_id,
                    "status": action_result.status,
                    "normalized_proposal_present": action_result.normalized_proposal is not None,
                },
            )
            if identity_governance_result.activated:
                governance_result = identity_governance_result.result
                governance_evidence = (
                    {
                        "evidence_id": governance_result.result_id,
                        "status": governance_result.revision_decision.status,
                        "pressure_level": governance_result.pressure_state.pressure_level,
                    },
                )
            else:
                governance_evidence = (
                    {
                        "evidence_id": identity_governance_result.inactive_id or f"inactive-identity-governance:{tick_label}",
                        "activated": False,
                    },
                )
            prompt_evidence = tuple(
                {
                    "evidence_id": contract.contract_id,
                    "status": "published",
                    "consumer_kind": contract.consumer_kind,
                }
                for contract in prompt_result.contracts
            )
            outward_expression_evidence = (
                {
                    "evidence_id": outward_expression_result.draft.draft_id,
                    "status": "prepared",
                    "source_prompt_contract_id": outward_expression_result.draft.source_prompt_contract_id,
                },
            )
            outward_expression_externalization_evidence = (
                {
                    "evidence_id": outward_expression_externalization_result.draft.draft_id,
                    "status": "prepared",
                    "source_prompt_contract_id": outward_expression_externalization_result.draft.source_prompt_contract_id,
                },
            )
        return EvaluationEvidenceBundle(
            bundle_id=f"evaluation-bundle:runtime:{tick_id}",
            source_request_id=request.request_id,
            thought_evidence=thought_evidence,
            action_evidence=action_evidence,
            planner_evidence=(
                {
                    "evidence_id": planner_result.result_id,
                    "status": planner_result.status,
                    "execution_feedback_present": planner_bridge_result.execution_feedback is not None,
                },
            ),
            governance_evidence=governance_evidence,
            writeback_evidence=tuple(
                {
                    "evidence_id": result.result_id,
                    "status": result.status,
                    "continuity_kind": result.continuity_packet.continuity_kind,
                }
                for result in experience_writeback_result.results
            ),
            autonomy_evidence=(
                {
                    "evidence_id": autonomy_result.result.result_id,
                    "dominant_disposition": autonomy_result.result.drive_state.dominant_disposition,
                    "deferred_active": autonomy_result.result.drive_state.deferred_active,
                    "proactive_action_requested": autonomy_result.result.drive_state.proactive_action_requested,
                    **autonomy_result.result.long_horizon_state.to_evidence(),
                },
            ),
            prompt_evidence=prompt_evidence,
            outward_expression_evidence=outward_expression_evidence,
            outward_expression_externalization_evidence=outward_expression_externalization_evidence,
            execution_timeline_evidence=self.timeline_bridge.build_timeline_evidence(
                self.timeline_holder
            ),
            prior_consequence_claim_evidence=self.prior_claim_bridge.build_claim_evidence(
                self.timeline_holder
            ),
        )
