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
    RapidDimensionEstimate,
    RapidDimensionEstimator,
)
from helios_v2.action_externalization import ThoughtExternalizationRequest
from helios_v2.autonomy import ProactiveDriveRequest
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
from helios_v2.identity_governance import IdentityGovernanceRequest
from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFormationPath,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
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
from helios_v2.persistence import ExperienceStore, PersistedExperienceRecord
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
    """Owner: composition. First-version aggregate salience estimator (deterministic)."""

    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        del stimulus, dimensions
        return 0.4


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
class FirstVersionNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: composition. First-version neuromodulator update path (deterministic)."""

    def update_levels(
        self,
        batch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        del batch, config, tick_id
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


@dataclass(frozen=True)
class _AggregatedSalience:
    """Owner: composition. Per-dimension max salience aggregated across an appraisal batch."""

    threat: float
    reward: float
    novelty: float
    social: float
    uncertainty: float


def _aggregate_salience(batch) -> _AggregatedSalience:
    """Owner: composition. Aggregate a rapid-appraisal batch into one coarse salience vector.

    Per-dimension maximum across the batch's appraisals (the most salient stimulus drives
    modulation). An empty batch yields all-zero salience, so derivation reduces to the tonic
    baseline. Reads only the public `RapidSalienceVector` fields.
    """

    appraisals = batch.appraisals
    if not appraisals:
        return _AggregatedSalience(0.0, 0.0, 0.0, 0.0, 0.0)
    vectors = [appraisal.salience for appraisal in appraisals]
    return _AggregatedSalience(
        threat=max(vector.threat for vector in vectors),
        reward=max(vector.reward for vector in vectors),
        novelty=max(vector.novelty for vector in vectors),
        social=max(vector.social for vector in vectors),
        uncertainty=max(vector.uncertainty for vector in vectors),
    )


def _clamp(value: float, low: float, high: float) -> float:
    """Owner: composition. Clamp a value into [low, high]."""

    return round(min(high, max(low, value)), 4)


@dataclass
class AppraisalDerivedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Derive the next neuromodulator levels from the real rapid-appraisal batch around the
        configured tonic baseline, replacing the constant first-version path so real `03`
        salience (especially the R35 novelty signal) shapes the `04` state.

    Failure semantics:
        A malformed batch is rejected by the `04` engine before this path runs. This path is a
        total deterministic function of the batch + config; it never branches into a degraded
        mode and never diverges outside the legal range (every channel is clamped).

    Notes:
        Owner-neutral glue conforming to the owner's `NeuromodulatorUpdatePath` protocol; the
        `04` engine is unchanged. Stateless by design: it reads no prior-tick levels (true
        dual-timescale decay is a later slice). The per-channel sensitivity coefficients are
        explicit bounded first-version constants organized under the config's declared
        learned-parameter categories; a later P5 slice tunes them without changing the equation
        shape. The mapping is a fixed linear combination plus clamp -- no NN, no hidden branch.
    """

    novelty_to_norepinephrine: float = 0.5
    uncertainty_to_norepinephrine: float = 0.3
    reward_to_dopamine: float = 0.5
    novelty_to_dopamine: float = 0.15
    threat_to_cortisol: float = 0.5

    def update_levels(
        self,
        batch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        del tick_id
        salience = _aggregate_salience(batch)
        base = config.tonic_baseline
        low = config.legal_min
        high = config.legal_max
        return NeuromodulatorLevels(
            dopamine=_clamp(
                base.dopamine
                + self.reward_to_dopamine * salience.reward
                + self.novelty_to_dopamine * salience.novelty,
                low.dopamine,
                high.dopamine,
            ),
            norepinephrine=_clamp(
                base.norepinephrine
                + self.novelty_to_norepinephrine * salience.novelty
                + self.uncertainty_to_norepinephrine * salience.uncertainty,
                low.norepinephrine,
                high.norepinephrine,
            ),
            cortisol=_clamp(
                base.cortisol + self.threat_to_cortisol * salience.threat,
                low.cortisol,
                high.cortisol,
            ),
            # Remaining channels regress to the tonic baseline (clamped) in this slice; their
            # real drivers are later de-shim slices.
            serotonin=_clamp(base.serotonin, low.serotonin, high.serotonin),
            acetylcholine=_clamp(base.acetylcholine, low.acetylcholine, high.acetylcholine),
            oxytocin=_clamp(base.oxytocin, low.oxytocin, high.oxytocin),
            opioid_tone=_clamp(base.opioid_tone, low.opioid_tone, high.opioid_tone),
            excitation=_clamp(base.excitation, low.excitation, high.excitation),
            inhibition=_clamp(base.inhibition, low.inhibition, high.inhibition),
        )


@dataclass
class FirstVersionFeelingConstructionPath(FeelingConstructionPath):
    """Owner: composition. First-version interoceptive feeling construction (deterministic)."""

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        del neuromodulator_state, internal_signals, config, tick_id
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
        Build the explicit memory binding context for one tick from the feeling result.

    Notes:
        Owner-neutral glue. It forwards a bounded situational content packet and preserves
        the current tick identity; it does not decide memory formation policy.
    """

    def build_binding_context(self, frame, feeling_result) -> MemoryBindingContext | None:
        tick_id = frame.tick_id
        return MemoryBindingContext(
            context_id=f"binding:runtime:{tick_id}",
            source_kind="runtime_chain",
            content=MemoryContentPacket(
                content_kind="situational-summary",
                summary_ref=f"summary:runtime:{tick_id}",
                context_ref=f"context:runtime:{tick_id}",
                salient_tokens=("hello", "novelty"),
            ),
        )


@dataclass
class FirstVersionPredictionMismatchEvidenceBridge:
    """Owner: composition.

    Purpose:
        Build explicit prediction-mismatch evidence for one tick from the feeling result.

    Notes:
        Owner-neutral glue. It preserves the upstream feeling-state id as the source
        reference and does not decide memory replay policy.
    """

    def build_mismatch_evidence(self, frame, feeling_result) -> PredictionMismatchEvidence | None:
        tick_id = frame.tick_id
        return PredictionMismatchEvidence(
            evidence_id=f"mismatch:runtime:{tick_id}",
            source_reference_id=feeling_result.state.state_id,
            mismatch_score=0.8,
            anomaly_score=0.85,
            confidence=0.9,
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

    def build_signal_snapshot(self, frame, conscious_result) -> ThoughtGateSignalSnapshot:
        tick_id = frame.tick_id
        return ThoughtGateSignalSnapshot(
            snapshot_id=f"gate-snapshot:runtime:{tick_id}",
            source_conscious_state_id=conscious_result.state.state_id,
            workload_pressure=0.1,
            global_activation_level=0.9,
            temporal_signal=0.4,
            drive_urgency_signal=0.7,
            dmn_available=True,
            selected_stimuli=(
                SelectedStimulusSummary(
                    stimulus_id=f"stimulus:runtime:{tick_id}",
                    source_kind="external_text",
                    source_channel_id="cli",
                    stimulus_intensity=0.9,
                    novelty_signal=0.6,
                    sensitization_signal=0.2,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class NeuromodulatorAwareThoughtGateSignalBridge:
    """Owner: composition (semantic-memory assembly only).

    Purpose:
        Build the normalized thought-gate signal snapshot exactly like the first-version
        bridge, but additionally forward the real `04` norepinephrine level (already computed
        this tick and present in the frame's stage results) as the raw `neuromodulatory_arousal`
        fact.

    Failure semantics:
        The `04` neuromodulator stage runs before `09` in the canonical order, so its result must
        be present. A missing or wrong-typed neuromodulator result is a hard fail (the existing
        runtime stage error), never a silent uncoupled snapshot.

    Notes:
        Owner-neutral glue. It forwards the raw norepinephrine level verbatim; it computes no
        gate score and no activation mapping. The arousal-to-gate semantic is owned by the `09`
        `ArousalAwareThoughtGatePath`, exactly as R35 keeps the novelty salience semantic in `03`
        while composition only forwards the raw retrieval fact.
    """

    neuromodulator_stage_name: str = "neuromodulator_system"

    def build_signal_snapshot(self, frame, conscious_result) -> ThoughtGateSignalSnapshot:
        from helios_v2.runtime.stages import (
            NeuromodulatorStageResult,
            RuntimeStageExecutionError,
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
        return ThoughtGateSignalSnapshot(
            snapshot_id=f"gate-snapshot:runtime:{tick_id}",
            source_conscious_state_id=conscious_result.state.state_id,
            workload_pressure=0.1,
            global_activation_level=0.9,
            temporal_signal=0.4,
            drive_urgency_signal=0.7,
            dmn_available=True,
            selected_stimuli=(
                SelectedStimulusSummary(
                    stimulus_id=f"stimulus:runtime:{tick_id}",
                    source_kind="external_text",
                    source_channel_id="cli",
                    stimulus_intensity=0.9,
                    novelty_signal=0.6,
                    sensitization_signal=0.2,
                ),
            ),
            tick_id=tick_id,
            neuromodulatory_arousal=norepinephrine,
        )


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
    """

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
        return IdentityGovernanceRequest(
            request_id=f"identity-governance-request:runtime:{tick_id}",
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            source_proposal_id=proposal_id,
            proposal_present=proposal_present,
            proposal_snapshot=proposal_snapshot,
            identity_state_snapshot={
                "self_definition": "runtime identity definition",
                "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
                "identity_metadata": {},
                "current_revision": "bootstrap",
                "revision_history_length": 0,
            },
            governance_trace_summary={},
            recent_governance_trace_history=(),
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

        revision_decision = identity_governance_result.result.revision_decision
        applied_identity_state = identity_governance_result.result.applied_identity_state
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
        Build the proactive-drive request from the upstream owner results for one tick,
        deriving the autonomy drive inputs from the thought owner's real fired-cycle
        decision plus the planner and continuation results.

    Notes:
        Owner-neutral glue. It preserves the upstream gate, retrieval, thought, planner,
        governance, writeback, and outward-expression provenance ids and translates the
        thought owner's decision into the bounded drive inputs the autonomy owner consumes.
        It does NOT select the proactive disposition; the autonomy owner applies its own rule
        to these inputs. The mapping below is a deterministic translation table from
        cognition outcome to bounded pressures, not a disposition decision.

    Derivation constants (explicit, documented; see requirement 29):
        - An action-bearing tick raises continuation/temporal/identity pressure so the
          autonomy owner's `outward_drive >= 1.6` action threshold is reachable when the
          planner executed (externalize) or blocked (defer with a blocked-outward record).
        - A continue/no-action tick keeps outward_drive below the action threshold so the
          autonomy owner falls through to reflect/explore/defer, and keeps continuation
          pressure high enough on a continue decision that a carry-forward deferral forms
          (which is what activates the 24 continuity-thread layer on repeated continue ticks).
    """

    # Action-bearing tick pressures (chosen so outward_drive = 0.9+0.4+0.4 = 1.7 >= 1.6).
    _ACTION_CONTINUATION_PRESSURE: float = 0.9
    _ACTION_TEMPORAL_PRESSURE: float = 0.4
    _ACTION_IDENTITY_PRESSURE: float = 0.4
    # Non-action tick pressures (kept below the 1.6 action threshold).
    _CONTINUE_CONTINUATION_PRESSURE: float = 0.8
    _CONCLUDED_CONTINUATION_PRESSURE: float = 0.3
    _BASELINE_TEMPORAL_PRESSURE: float = 0.3
    _UNRESOLVED_IDENTITY_PRESSURE: float = 0.6
    _RESOLVED_IDENTITY_PRESSURE: float = 0.2

    _PLANNER_EXECUTED_STATUSES = ("executed", "accepted")
    _PLANNER_BLOCKED_STATUSES = (
        "policy_rejected",
        "execution_consistency_failed",
        "execution_failed",
    )

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
        bundle = directed_retrieval_result.bundle
        retrieval_pull = float(len(bundle.mid_term_hits) + len(bundle.autobiographical_hits)) / 4.0

        thought = internal_thought_result.result
        planner_status = planner_bridge_result.result.status
        continuation_active = thought_gating_result.continuation_state.active

        has_action = thought.action_proposal is not None
        planner_executed = planner_status in self._PLANNER_EXECUTED_STATUSES
        planner_blocked = planner_status in self._PLANNER_BLOCKED_STATUSES
        wants_continue = bool(thought.continuation_requested) or bool(continuation_active)
        has_self_revision = thought.self_revision_proposal is not None

        # Outward readiness derives only from whether the thought owner produced an action
        # proposal and how the planner handled it. No action proposal -> neither ready nor
        # blocked, so the autonomy owner cannot externalize this tick.
        outward_ready = has_action and planner_executed
        externalization_blocked = has_action and planner_blocked

        if has_action:
            continuation_pressure = self._ACTION_CONTINUATION_PRESSURE
            temporal_pressure = self._ACTION_TEMPORAL_PRESSURE
            identity_unresolved_pressure = self._ACTION_IDENTITY_PRESSURE
        else:
            continuation_pressure = (
                self._CONTINUE_CONTINUATION_PRESSURE
                if wants_continue
                else self._CONCLUDED_CONTINUATION_PRESSURE
            )
            temporal_pressure = self._BASELINE_TEMPORAL_PRESSURE
            identity_unresolved_pressure = (
                self._UNRESOLVED_IDENTITY_PRESSURE
                if has_self_revision
                else self._RESOLVED_IDENTITY_PRESSURE
            )

        return ProactiveDriveRequest(
            request_id=f"autonomy-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=bundle.bundle_id,
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            source_planner_bridge_result_id=planner_bridge_result.result.result_id,
            source_identity_governance_result_id=identity_governance_result.result.result_id,
            source_writeback_result_ids=tuple(
                result.result_id for result in experience_writeback_result.results
            ),
            source_outward_expression_draft_id=outward_expression_result.draft.draft_id,
            source_outward_expression_externalization_draft_id=(
                outward_expression_externalization_result.draft.draft_id
            ),
            continuation_summary={"continuation_pressure": round(min(1.0, max(0.0, continuation_pressure)), 4)},
            retrieval_pull_summary={"retrieval_pull": round(min(1.0, max(0.0, retrieval_pull)), 4)},
            temporal_pressure_summary={"temporal_pressure": round(min(1.0, max(0.0, temporal_pressure)), 4)},
            identity_unresolved_summary={
                "identity_unresolved_pressure": round(min(1.0, max(0.0, identity_unresolved_pressure)), 4)
            },
            outward_readiness_summary={
                "outward_ready": outward_ready,
                "externalization_blocked": externalization_blocked,
            },
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
        thought_result = internal_thought_result.result
        action_result = action_externalization_result.result
        planner_result = planner_bridge_result.result
        governance_result = identity_governance_result.result
        return EvaluationEvidenceBundle(
            bundle_id=f"evaluation-bundle:runtime:{tick_id}",
            source_request_id=request.request_id,
            thought_evidence=(
                {
                    "evidence_id": thought_result.result_id,
                    "execution_status": thought_result.execution_status,
                    "action_proposal_present": thought_result.action_proposal is not None,
                },
            ),
            action_evidence=(
                {
                    "evidence_id": action_result.result_id,
                    "status": action_result.status,
                    "normalized_proposal_present": action_result.normalized_proposal is not None,
                },
            ),
            planner_evidence=(
                {
                    "evidence_id": planner_result.result_id,
                    "status": planner_result.status,
                    "execution_feedback_present": planner_bridge_result.execution_feedback is not None,
                },
            ),
            governance_evidence=(
                {
                    "evidence_id": governance_result.result_id,
                    "status": governance_result.revision_decision.status,
                    "pressure_level": governance_result.pressure_state.pressure_level,
                },
            ),
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
            prompt_evidence=tuple(
                {
                    "evidence_id": contract.contract_id,
                    "status": "published",
                    "consumer_kind": contract.consumer_kind,
                }
                for contract in prompt_result.contracts
            ),
            outward_expression_evidence=(
                {
                    "evidence_id": outward_expression_result.draft.draft_id,
                    "status": "prepared",
                    "source_prompt_contract_id": outward_expression_result.draft.source_prompt_contract_id,
                },
            ),
            outward_expression_externalization_evidence=(
                {
                    "evidence_id": outward_expression_externalization_result.draft.draft_id,
                    "status": "prepared",
                    "source_prompt_contract_id": outward_expression_externalization_result.draft.source_prompt_contract_id,
                },
            ),
            execution_timeline_evidence=self.timeline_bridge.build_timeline_evidence(
                self.timeline_holder
            ),
            prior_consequence_claim_evidence=self.prior_claim_bridge.build_claim_evidence(
                self.timeline_holder
            ),
        )
