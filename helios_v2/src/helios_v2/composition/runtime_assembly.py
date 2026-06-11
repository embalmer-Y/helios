"""Owner: runtime composition root.

Assembles the critical-dependency gate, the canonical nineteen-stage `01 -> 18` chain
(plus the read-only evaluation owner) with shipped first-version owner-neutral bridges,
and an optional `21` observability recorder into a single runnable runtime handle.

This owner is assembly-only. It holds no cognitive policy. It constructs owner engines,
owner-owned bridges, and the kernel, then registers stages in the canonical brain-aligned
order and validates that order. It never reinterprets, mutates, or bypasses any owner
result, and it provides no degraded or fallback assembly path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Callable, Mapping

if TYPE_CHECKING:
    from .profile import AggressiveRadicalPromptProfile

from helios_v2.action_externalization import (
    ActionExternalizationConfig,
    ActionExternalizationEngine,
    FirstVersionThoughtExternalizationPath,
)
from helios_v2.autonomy import AutonomyConfig, AutonomyEngine, FirstVersionAutonomyPath
from helios_v2.consciousness import (
    ConsciousnessConfig,
    ConsciousnessEngine,
    FirstVersionConsciousCommitmentPath,
    IgnitionFocalSelectionPolicy,
)
from helios_v2.directed_retrieval import (
    DirectedRetrievalConfig,
    DirectedRetrievalEngine,
    FirstVersionDirectedRetrievalPath,
)
from helios_v2.evaluation import EvaluationConfig, EvaluationEngine, FirstVersionEvaluationPath
from helios_v2.experience_writeback import (
    ExperienceWritebackConfig,
    ExperienceWritebackEngine,
    FirstVersionExperienceWritebackPath,
)
from helios_v2.feeling import (
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingEngine,
    FeelingConstructionPath,
    InteroceptiveSignalModulatedFeelingConstructionPath,
    NeuromodulatorDerivedFeelingConstructionPath,
    PersistentFeelingConstructionPath,
)
from helios_v2.identity_governance import (
    FirstVersionIdentityGovernancePath,
    IdentityGovernanceConfig,
    IdentityGovernanceEngine,
)
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    LlmBackedInternalThoughtPath,
)
from helios_v2.llm import (
    LlmGateway,
    LlmGatewayAPI,
    LlmProfile,
    LlmProfileRegistry,
    OpenAICompatibleProvider,
)
from helios_v2.memory import (
    AffectGroundedMemoryFormationPath,
    MemoryAffectReplayConfig,
    MemoryAffectReplayEngine,
    SalienceGatedReplayCandidateSelector,
)
from helios_v2.neuromodulation import (
    AppraisalDerivedNeuromodulatorUpdatePath,
    DualTimescaleNeuromodulatorUpdatePath,
    NeuromodulatorConfig,
    NeuromodulatorEngine,
    NeuromodulatorLevels,
)
from helios_v2.observability import (
    ExecutionTimelineReconstructor,
    InMemoryLogSink,
    RuntimeObservabilityRecorder,
)
from helios_v2.outward_expression import (
    FirstVersionOutwardExpressionPath,
    OutwardExpressionConfig,
    OutwardExpressionEngine,
)
from helios_v2.outward_expression_externalization import (
    FirstVersionOutwardExpressionExternalizationPath,
    OutwardExpressionExternalizationConfig,
    OutwardExpressionExternalizationEngine,
)
from helios_v2.planner_bridge import (
    FirstVersionPlannerBridgePath,
    PlannerBridgeConfig,
    PlannerBridgeEngine,
)
from helios_v2.prompt_contract import (
    AggressiveRadicalEmbodiedPromptPath,
    EmbodiedPromptConfig,
    EmbodiedPromptEngine,
    FirstVersionEmbodiedPromptPath,
)
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.runtime import (
    ActionExternalizationRuntimeStage,
    AutonomyRuntimeStage,
    ChannelInboundDrainRuntimeStage,
    ChannelOutboundDispatchRuntimeStage,
    DirectedRetrievalRuntimeStage,
    EmbodiedPromptRuntimeStage,
    EvaluationRuntimeStage,
    ExperienceWritebackRuntimeStage,
    IdentityGovernanceRuntimeStage,
    InternalThoughtRuntimeStage,
    InteroceptiveFeelingRuntimeStage,
    MemoryAffectReplayRuntimeStage,
    NeuromodulatorRuntimeStage,
    OutwardExpressionExternalizationRuntimeStage,
    OutwardExpressionRuntimeStage,
    PlannerBridgeRuntimeStage,
    RapidSalienceAppraisalRuntimeStage,
    ReportableConsciousContentRuntimeStage,
    RuntimeDependencyProvider,
    RuntimeDependencySpec,
    RuntimeKernel,
    RuntimeTickResult,
    SensoryIngressRuntimeStage,
    ThoughtGatingRuntimeStage,
    WorkspaceCompetitionRuntimeStage,
    WorkspaceConsciousContentMaterialBridge,
)
from helios_v2.appraisal import (
    GroundedDimensionEstimator,
    RapidSalienceAppraisalEngine,
    WeightedAggregateEstimator,
)
from helios_v2.channel import ChannelSubsystem, CliChannelDriver, CliDriverConfig
from helios_v2.embedding import (
    DeterministicHashEmbeddingProvider,
    EmbeddingGateway,
    EmbeddingGatewayAPI,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    EmbeddingRequest,
)
from helios_v2.continuity_checkpoint import ContinuityCheckpointStore
from helios_v2.appraisal.r80_internal_monologue import InternalMonologueAppraisalEstimator
from helios_v2.interoception import RuntimeInteroceptiveSource, RuntimePressureSampler
from helios_v2.sensory import InternalMonologueSource
from helios_v2.temporal import TemporalSource
from helios_v2.persistence import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    SemanticStoreBackedDirectedMemoryCandidateProvider,
    StoreBackedDirectedMemoryCandidateProvider,
)
from helios_v2.sensory import RawSignal, SensoryIngress, SensorySource
from helios_v2.thought_gating import (
    ArousalAwareThoughtGatePath,
    FirstVersionThoughtGatePath,
    ThoughtGatingConfig,
    ThoughtGatingEngine,
)
from helios_v2.workspace import (
    BoundedAttentionRetentionPath,
    SalienceWeightedWorkspaceCompetitionPath,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionEngine,
)

from .bridges import (
    ChannelBackedPlannerBridgeRequestBridge,
    ChannelSubsystemStateProvider,
    ContinuityCheckpointBridge,
    ExperienceRecordBridge,
    FirstVersionActiveChannelReporter,
    FirstVersionAggregateEstimator,
    FirstVersionAutonomyRequestBridge,
    FirstVersionDimensionEstimator,
    FirstVersionDirectedMemoryCandidateProvider,
    FirstVersionDirectedRetrievalRequestBridge,
    FirstVersionDominantDimensionReporter,
    FirstVersionEmbodiedPromptRequestBridge,
    SemanticEmbodiedPromptRequestBridge,
    FirstVersionEvaluationRequestBridge,
    FirstVersionExperienceWritebackRequestBridge,
    FirstVersionFeelingConstructionPath,
    FirstVersionIdentityGovernanceRequestBridge,
    FirstVersionInternalThoughtRequestBridge,
    SemanticInternalThoughtRequestBridge,
    FirstVersionMemoryBindingContextBridge,
    FirstVersionMemoryFormationPath,
    FirstVersionNeuromodulatorUpdatePath,
    FirstVersionOutwardExpressionExternalizationRequestBridge,
    FirstVersionPlannerBridgeRequestBridge,
    FirstVersionPredictionMismatchEvidenceBridge,
    FirstVersionReplayCandidateSelector,
    FirstVersionSensorySource,
    FirstVersionThoughtExternalizationRequestBridge,
    FirstVersionThoughtGateSignalBridge,
    FirstVersionWorkingStateRetentionPath,
    FirstVersionWorkspaceCompetitionPath,
    PriorThoughtRecallHolder,
    PriorDriveUrgencyHolder,
    ThoughtDirectedRetrievalRequestBridge,
    EmbeddingPrototypeSimilaritySource,
    MemoryGroundedSimilaritySource,
    StoreBackedRecalledMemoryProvider,
    MemoryGroundedRetrievalAmbiguitySource,
    MemoryRecordBridge,
    NeuromodulatorAwareThoughtGateSignalBridge,
    SubsystemBackedSensorySource,
    TimelineViewHolder,
    TransportGroundedSocialContextSource,
)
from .dependencies import (
    ChannelReadinessDependencyProvider,
    ContinuityCheckpointReadinessDependencyProvider,
    EmbeddingReadinessDependencyProvider,
    ExperienceStoreReadinessDependencyProvider,
    FirstVersionDependencyProvider,
    LlmReadinessDependencyProvider,
    channel_critical_dependency_spec,
    continuity_checkpoint_critical_dependency_spec,
    default_critical_dependency_specs,
    embedding_profile_critical_dependency_spec,
    experience_store_critical_dependency_spec,
    llm_critical_dependency_spec,
)

# The single source of wiring truth: the canonical brain-aligned stage order. The
# assembly validates the registered stage names equal this tuple exactly.
CANONICAL_STAGE_ORDER: tuple[str, ...] = (
    "sensory_ingress",
    "rapid_salience_appraisal",
    "neuromodulator_system",
    "interoceptive_feeling_layer",
    "memory_affect_and_replay",
    "workspace_competition_and_working_state",
    "reportable_conscious_content",
    "thought_gating_and_continuation_pressure",
    "directed_retrieval_into_thought_window",
    "embodied_subjective_prompt_and_action_autonomy",
    "outward_expression_owner",
    "outward_expression_execution_externalization_owner",
    "internal_thought_loop_owner",
    "action_proposal_externalization_contract",
    "planner_executor_feedback_bridge",
    "identity_governance_self_revision_integration",
    "execution_writeback_and_autobiographical_consolidation",
    "subjective_autonomy_and_proactive_evolution",
    "evaluation_fidelity_and_diagnostic_provenance",
)

# The channel-bound assembly variant inserts two transport stages around the cognition
# chain: the inbound drain runs first (feeding sensory), and the outbound dispatch runs
# right after the planner bridge (transporting the accepted decision). This order is the
# wiring truth for the opt-in channel-bound runtime only; the default runtime keeps
# `CANONICAL_STAGE_ORDER` unchanged.
CHANNEL_BOUND_STAGE_ORDER: tuple[str, ...] = (
    "channel_inbound_drain",
    "sensory_ingress",
    "rapid_salience_appraisal",
    "neuromodulator_system",
    "interoceptive_feeling_layer",
    "memory_affect_and_replay",
    "workspace_competition_and_working_state",
    "reportable_conscious_content",
    "thought_gating_and_continuation_pressure",
    "directed_retrieval_into_thought_window",
    "embodied_subjective_prompt_and_action_autonomy",
    "outward_expression_owner",
    "outward_expression_execution_externalization_owner",
    "internal_thought_loop_owner",
    "action_proposal_externalization_contract",
    "planner_executor_feedback_bridge",
    "channel_outbound_dispatch",
    "identity_governance_self_revision_integration",
    "execution_writeback_and_autobiographical_consolidation",
    "subjective_autonomy_and_proactive_evolution",
    "evaluation_fidelity_and_diagnostic_provenance",
)


class CompositionError(RuntimeError):
    """Hard-stop error raised on composition-time assembly invariant violations."""


def _uniform_neuromodulator_levels(value: float) -> NeuromodulatorLevels:
    return NeuromodulatorLevels(
        dopamine=value,
        norepinephrine=value,
        serotonin=value,
        acetylcholine=value,
        cortisol=value,
        oxytocin=value,
        opioid_tone=value,
        excitation=value,
        inhibition=value,
    )


def _uniform_feeling_vector(value: float) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=value,
        arousal=value,
        tension=value,
        comfort=value,
        fatigue=value,
        pain_like=value,
        social_safety=value,
    )


@dataclass(frozen=True)
class LlmCompositionConfig:
    """Owner: composition.

    Purpose:
        Declare the LLM profile registry and the per-consumer profile bindings used to
        assemble LLM-backed owners.

    Notes:
        `profiles` seeds the `25` `LlmProfileRegistry`. `thought_profile_name` binds the
        internal-thought consumer to one registered profile. Binding is a composition
        concern; the gateway stays ignorant of consumer identity.
    """

    profiles: tuple[LlmProfile, ...]
    thought_profile_name: str

    def __post_init__(self) -> None:
        if not self.profiles:
            raise CompositionError("LlmCompositionConfig must declare at least one profile")
        names = {profile.profile_name for profile in self.profiles}
        if self.thought_profile_name not in names:
            raise CompositionError(
                "LlmCompositionConfig thought_profile_name must reference a declared profile"
            )


@dataclass(frozen=True)
class CompositionConfig:
    """Owner: composition.

    Purpose:
        Bundle the per-owner first-version configs used to assemble the runnable runtime.

    Notes:
        Defaults mirror the values already proven in `tests/test_runtime_stage_chain.py`.
        These are baseline first-version configs, not final owner policy.
    """

    neuromodulator: NeuromodulatorConfig
    feeling: InteroceptiveFeelingConfig
    memory: MemoryAffectReplayConfig
    workspace: WorkspaceCompetitionConfig
    consciousness: ConsciousnessConfig
    thought_gating: ThoughtGatingConfig
    directed_retrieval: DirectedRetrievalConfig
    embodied_prompt: EmbodiedPromptConfig
    outward_expression: OutwardExpressionConfig
    outward_expression_externalization: OutwardExpressionExternalizationConfig
    internal_thought: InternalThoughtConfig
    action_externalization: ActionExternalizationConfig
    planner_bridge: PlannerBridgeConfig
    identity_governance: IdentityGovernanceConfig
    experience_writeback: ExperienceWritebackConfig
    autonomy: AutonomyConfig
    evaluation: EvaluationConfig
    llm: LlmCompositionConfig
    source_signals: tuple[RawSignal, ...] = ()


def default_composition_config() -> CompositionConfig:
    """Owner: composition.

    Purpose:
        Return a valid first-version `CompositionConfig` so the driver and tests can
        assemble a runtime without restating every owner config.

    Returns:
        A `CompositionConfig` whose per-owner configs mirror the proven stage-chain test.
    """

    return CompositionConfig(
        neuromodulator=NeuromodulatorConfig(
            tonic_baseline=_uniform_neuromodulator_levels(0.3),
            legal_min=_uniform_neuromodulator_levels(0.0),
            legal_max=_uniform_neuromodulator_levels(1.0),
            mandatory_learned_parameters=(
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
                "gate_influence_strength",
                "hormone_predict_coupling",
            ),
        ),
        feeling=InteroceptiveFeelingConfig(
            baseline_feeling=_uniform_feeling_vector(0.3),
            legal_min=_uniform_feeling_vector(0.0),
            legal_max=_uniform_feeling_vector(1.0),
            mandatory_learned_parameters=(
                "feeling_mapping_strength",
                "feeling_coupling_strength",
                "feeling_persistence",
            ),
        ),
        memory=MemoryAffectReplayConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            storage_bootstrap_state_id="memory-bootstrap:v1",
            mandatory_learned_parameters=(
                "memory_family_write_policy",
                "replay_priority_policy",
                "consolidation_policy",
            ),
        ),
        workspace=WorkspaceCompetitionConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            working_state_bootstrap_id="workspace-bootstrap:v1",
            mandatory_learned_parameters=(
                "competition_policy",
                "candidate_retention_policy",
                "working_state_update_policy",
            ),
        ),
        consciousness=ConsciousnessConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            conscious_state_bootstrap_id="consciousness-bootstrap:v1",
            max_supporting_context_items=2,
            mandatory_learned_parameters=(
                "commitment_policy",
                "quiet_state_policy",
                "semantic_shaping_policy",
            ),
        ),
        thought_gating=ThoughtGatingConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            continuation_state_bootstrap_id="continuation-bootstrap:v1",
            mandatory_learned_parameters=(
                "gate_policy",
                "continuation_policy",
                "signal_normalization_policy",
            ),
        ),
        directed_retrieval=DirectedRetrievalConfig(
            max_hits_per_tier=2,
            max_short_term_context=1,
            retrieval_bootstrap_id="directed-retrieval-bootstrap:v1",
            mandatory_learned_parameters=(
                "retrieval_planning_policy",
                "tier_selection_policy",
                "thought_window_shaping_policy",
            ),
        ),
        embodied_prompt=EmbodiedPromptConfig(
            max_layer_count=8,
            prompt_bootstrap_id="embodied-prompt-bootstrap:v1",
            mandatory_learned_parameters=(
                "layering_policy",
                "anti_theatrical_policy",
                "action_boundary_policy",
            ),
        ),
        outward_expression=OutwardExpressionConfig(
            outward_expression_bootstrap_id="outward-expression-bootstrap:v1",
            mandatory_learned_parameters=(
                "delivery_guidance_policy",
                "boundary_rendering_policy",
                "draft_publication_policy",
            ),
        ),
        outward_expression_externalization=OutwardExpressionExternalizationConfig(
            externalization_bootstrap_id="outward-expression-externalization-bootstrap:v1",
            mandatory_learned_parameters=(
                "envelope_rendering_policy",
                "delivery_selection_policy",
                "execution_boundary_policy",
            ),
        ),
        internal_thought=InternalThoughtConfig(
            legal_min_sufficiency=0.0,
            legal_max_sufficiency=1.0,
            thought_bootstrap_id="internal-thought-bootstrap:v1",
            mandatory_learned_parameters=(
                "thought_generation_policy",
                "sufficiency_policy",
                "proposal_emission_policy",
            ),
        ),
        action_externalization=ActionExternalizationConfig(
            legal_min_outbound_intensity=0.0,
            legal_max_outbound_intensity=1.0,
            externalization_bootstrap_id="action-externalization-bootstrap:v1",
            mandatory_learned_parameters=(
                "normalization_policy",
                "bridge_evidence_policy",
                "bridge_rejection_policy",
            ),
        ),
        planner_bridge=PlannerBridgeConfig(
            legal_min_intensity=0.0,
            legal_max_intensity=1.0,
            bridge_bootstrap_id="planner-bridge-bootstrap:v1",
            mandatory_learned_parameters=(
                "policy_evaluation_policy",
                "channel_selection_policy",
                "feedback_normalization_policy",
            ),
        ),
        identity_governance=IdentityGovernanceConfig(
            legal_min_confidence=0.0,
            legal_max_confidence=1.0,
            governance_bootstrap_id="identity-governance-bootstrap:v1",
            mandatory_learned_parameters=(
                "governance_evaluation_policy",
                "pressure_interpretation_policy",
                "supported_revision_policy",
                "boundary_check_policy",
            ),
        ),
        experience_writeback=ExperienceWritebackConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            writeback_bootstrap_id="experience-writeback-bootstrap:v1",
            mandatory_learned_parameters=(
                "continuity_classification_policy",
                "consolidation_priority_policy",
                "autobiographical_salience_policy",
            ),
        ),
        autonomy=AutonomyConfig(
            autonomy_bootstrap_id="autonomy-bootstrap:v1",
            mandatory_learned_parameters=(
                "drive_integration_policy",
                "continuity_carry_policy",
                "proactive_externalization_policy",
            ),
        ),
        evaluation=EvaluationConfig(
            evaluation_bootstrap_id="evaluation-bootstrap:v1",
            mandatory_learned_parameters=(
                "fidelity_scoring_policy",
                "gap_analysis_policy",
                "long_range_diagnostic_policy",
            ),
        ),
        llm=LlmCompositionConfig(
            profiles=(
                LlmProfile(
                    profile_name="thought-default",
                    model=os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash"),
                    api_key_env="OPENAI_API_KEY",
                    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                ),
            ),
            thought_profile_name="thought-default",
        ),
    )


@dataclass
class RuntimeHandle:
    """Owner: composition.

    Purpose:
        Expose the assembled runtime lifecycle: startup, single tick, and bounded multi-tick.

    Notes:
        The handle forwards to the wrapped kernel. It exposes the sensory ingress owner so a
        driver can supply per-tick stimuli through the owner API only. When the runtime is
        instrumented (a recorder plus a readable in-memory sink are present), the handle
        reconstructs each completed tick's execution-timeline view through the observability
        owner and carries it forward into the next tick's evaluation evidence assembly. The
        carry is owner-neutral: it transports a formal observability contract only.
    """

    kernel: RuntimeKernel
    ingress: SensoryIngress
    timeline_holder: TimelineViewHolder | None = None
    timeline_sink: InMemoryLogSink | None = None
    channel_subsystem: "ChannelSubsystem | None" = None
    experience_store: ExperienceStore | None = None
    experience_record_bridge: ExperienceRecordBridge | None = None
    memory_record_bridge: "MemoryRecordBridge | None" = None
    prior_thought_recall_holder: "PriorThoughtRecallHolder | None" = None
    drive_urgency_holder: "PriorDriveUrgencyHolder | None" = None
    embed_record: "Callable[[str], tuple[float, ...]] | None" = None
    temporal_source: "TemporalSource | None" = None
    continuity_checkpoint: "ContinuityCheckpointStore | None" = None
    continuity_checkpoint_bridge: "ContinuityCheckpointBridge | None" = None
    thought_gating_stage: "ThoughtGatingRuntimeStage | None" = None
    autonomy_stage: "AutonomyRuntimeStage | None" = None
    neuromodulator_stage: "NeuromodulatorRuntimeStage | None" = None
    feeling_stage: "InteroceptiveFeelingRuntimeStage | None" = None
    identity_governance_stage: "IdentityGovernanceRuntimeStage | None" = None
    _reconstructor: ExecutionTimelineReconstructor = field(
        default_factory=ExecutionTimelineReconstructor
    )

    def startup(self) -> None:
        """Run the fail-fast dependency gate, then restore continuity from the checkpoint.

        The dependency gate runs first, so an un-initializable checkpoint backend fails fast
        through the gate (a `RuntimeStartupError`) before any restore is attempted. Once the
        gate passes, the latest snapshot (if any) seeds the `09` and `18` stages' prior
        cross-tick state so the first post-restart tick resumes from it. A cold store leaves
        the inert defaults untouched.
        """

        self.kernel.startup()
        self._restore_continuity()

    def _restore_continuity(self) -> None:
        """Seed the `09`/`18` stages' prior cross-tick state from the latest checkpoint.

        Owner-neutral restore: it loads the latest `RuntimeContinuitySnapshot` and seeds the
        stages through their explicit owner-neutral seed seams. Reconstruction runs the owners'
        own validation (in the facade decode); a corrupt snapshot fails fast on load. Runs only
        when checkpointing is enabled; otherwise a no-op.
        """

        if (
            self.continuity_checkpoint is None
            or self.thought_gating_stage is None
            or self.autonomy_stage is None
        ):
            return
        snapshot = self.continuity_checkpoint.load_latest()
        if snapshot is None:
            return
        self.thought_gating_stage.seed_prior_continuation_state(snapshot.continuation_state)
        self.autonomy_stage.seed_prior_continuity(
            snapshot.deferred_records,
            snapshot.continuity_threads,
        )
        if self.neuromodulator_stage is not None:
            restored_state = self.continuity_checkpoint_bridge.restore_neuromodulator_state(snapshot)
            if restored_state is not None:
                self.neuromodulator_stage.seed_prior_state(restored_state)
        if self.feeling_stage is not None:
            restored_feeling = self.continuity_checkpoint_bridge.restore_feeling_state(snapshot)
            if restored_feeling is not None:
                self.feeling_stage.seed_prior_state(restored_feeling)

    def tick(self) -> RuntimeTickResult:
        """Execute one runtime tick and carry its completed timeline forward when instrumented."""

        result = self.kernel.tick()
        self._carry_timeline(result.tick_id)
        self._carry_consequence_claim(result)
        self._carry_recall_directive(result)
        self._carry_temporal(result)
        self._carry_drive_urgency(result)
        self._persist_experience(result)
        self._persist_memory(result)
        self._checkpoint_continuity(result)
        return result

    def _carry_timeline(self, tick_id: int) -> None:
        """Reconstruct the just-completed tick's timeline and store it for the next tick.

        This runs only when the runtime is instrumented with a readable sink. The next
        tick's evaluation evidence then consumes the previous tick's timeline view, because
        the current tick is not yet complete when its own evaluation stage runs.
        """

        if self.timeline_holder is None or self.timeline_sink is None:
            return
        view = self._reconstructor.reconstruct(self.timeline_sink.events, tick_id)
        self.timeline_holder.view = view

    def _carry_consequence_claim(self, result: RuntimeTickResult) -> None:
        """Capture the just-completed tick's published consequence claim for the next tick.

        This is owner-neutral carry: it reads the evaluation owner's own published claim
        projection from the evaluation stage result and stores it in the holder, tick-aligned
        with the carried timeline so the next tick can corroborate the self-report against
        execution truth. It computes and re-derives nothing. When the runtime is
        uninstrumented (no holder) or the evaluation stage produced no claim, it carries
        nothing and the next tick reports `unverifiable_no_timeline`.
        """

        if self.timeline_holder is None:
            return
        stage_result = result.stage_results.get("evaluation_fidelity_and_diagnostic_provenance")
        artifact = getattr(stage_result, "artifact", None)
        if artifact is None:
            self.timeline_holder.prior_consequence_claim = None
            return
        claim = artifact.long_range_diagnostics.get("consequence_claim")
        self.timeline_holder.prior_consequence_claim = (
            dict(claim) if isinstance(claim, Mapping) else None
        )

    def _carry_recall_directive(self, result: RuntimeTickResult) -> None:
        """Capture the just-completed tick's `11` recall directive for the next tick's `10` request.

        This is owner-neutral carry (R49): it reads the `11` internal-thought stage result's
        `memory_handoff` and, when the thought owner saved it for the next tick, stores its
        `recall_intent` and `selected_memory_refs` in the holder so the next tick's directed
        retrieval is memory-guided by the thought the system chose to continue. When the gate did
        not fire (no `11` result), or `11` saved no directive, the holder is cleared so the next
        tick falls back to the real `09` `compact_stimuli`. It transports `11`-owned values
        verbatim and computes no retrieval policy. A no-op when the recall carry is disabled.
        """

        if self.prior_thought_recall_holder is None:
            return
        stage_result = result.stage_results.get("internal_thought_loop_owner")
        cycle_result = getattr(stage_result, "result", None)
        handoff = getattr(cycle_result, "memory_handoff", None)
        if handoff is not None and handoff.saved_for_next_tick:
            self.prior_thought_recall_holder.set_directive(
                handoff.recall_intent,
                handoff.selected_memory_refs,
            )
        else:
            self.prior_thought_recall_holder.clear()

    def _carry_temporal(self, result: RuntimeTickResult) -> None:
        """Advance the temporal source's cross-tick elapsed-rest state from this tick's gate decision.

        Owner-neutral carry (R55): it reads the published `09` gate decision and tells the temporal
        source whether a thought fired this tick (fire resets the accumulated rest; no-fire advances
        it), so the next tick's `temporal_signal` genuinely reflects elapsed rest. It computes no
        temporal mapping (the source owns that) and is a no-op when no temporal source is wired.
        """

        if self.temporal_source is None:
            return
        stage_result = result.stage_results.get("thought_gating_and_continuation_pressure")
        gate_result = getattr(stage_result, "result", None)
        decision = getattr(gate_result, "decision", None)
        if decision is None:
            return
        self.temporal_source.observe_tick(fired=(decision == "fire"))

    def _carry_drive_urgency(self, result: RuntimeTickResult) -> None:
        """Advance the prior-tick `18` drive-urgency carry from this tick's autonomy result (R62).

        Owner-neutral carry: it reads the published `18` `ProactiveDriveState` from the autonomy
        stage result and stores its bounded `outward_drive` projection in the holder, so the next
        tick's `09` gate signal reflects the real proactive-drive urgency (since `18` runs after
        `09`). It computes no `18` disposition. A no-op when no holder is wired or the autonomy
        result is absent.
        """

        if self.drive_urgency_holder is None:
            return
        stage_result = result.stage_results.get("subjective_autonomy_and_proactive_evolution")
        autonomy_result = getattr(stage_result, "result", None)
        drive_state = getattr(autonomy_result, "drive_state", None)
        if drive_state is not None:
            self.drive_urgency_holder.set_from_drive_state(drive_state)

    def _persist_experience(self, result: RuntimeTickResult) -> None:
        """Durably append the just-completed tick's `15` continuity records when enabled.

        This is owner-neutral carry: it reads the experience-writeback stage result from the
        completed tick, projects it into durable records through the owner-neutral record
        bridge, and appends them to the durable store. It runs only when persistence is
        enabled (a store and bridge are present); otherwise it is a no-op and the default
        assembly is unchanged. A durability failure propagates as a hard stop (no silent
        fallback to a non-persistent path).
        """

        if self.experience_store is None or self.experience_record_bridge is None:
            return
        writeback_result = result.stage_results.get(
            "execution_writeback_and_autobiographical_consolidation"
        )
        if writeback_result is None:
            return
        records = self.experience_record_bridge.build_records(writeback_result, result.tick_id)
        if self.embed_record is not None:
            # Embed-at-write (semantic memory enabled): embed each record's summary and store
            # the vector with the record. An embedding failure propagates as a hard stop; the
            # store never receives a fabricated vector and never falls back to recency.
            records = tuple(
                record.with_embedding(self.embed_record(record.summary)) for record in records
            )
        self.experience_store.append_records(records)

    def _persist_memory(self, result: RuntimeTickResult) -> None:
        """Durably append the just-completed tick's consolidation-worthy `06` memory when enabled.

        This is owner-neutral carry mirroring `_persist_experience`: it reads the `06` memory
        affect-and-replay stage result from the completed tick, projects exactly the
        consolidation-worthy memory items (those the `06` salience gate marked
        `forced_consolidation`) into durable affect-memory records through the owner-neutral
        memory record bridge, embeds each at write, and appends them to the same durable store.
        It runs only when affect-memory persistence is enabled (a store, the memory bridge, and
        the embed callable are all present); otherwise it is a no-op and the default assembly is
        unchanged. A low-salience tick produces no records (a defined outcome, nothing appended).
        An embedding or durability failure propagates as a hard stop (no non-persistent
        fallback). It re-derives no decision; the `06` owner already decided what is worthy.
        """

        if (
            self.experience_store is None
            or self.memory_record_bridge is None
            or self.embed_record is None
        ):
            return
        memory_result = result.stage_results.get("memory_affect_and_replay")
        if memory_result is None:
            return
        records = self.memory_record_bridge.build_records(memory_result, result.tick_id)
        if not records:
            return
        records = tuple(
            record.with_embedding(self.embed_record(record.summary)) for record in records
        )
        self.experience_store.append_records(records)

    def _checkpoint_continuity(self, result: RuntimeTickResult) -> None:
        """Durably save the just-completed tick's cross-tick continuity state when enabled.

        This is owner-neutral carry: it reads the `09` thought-gating and `18` autonomy stage
        results from the completed tick, projects their published cross-tick continuity state
        (continuation pressure; deferred records + continuity threads) into a latest-state
        `RuntimeContinuitySnapshot` through the owner-neutral checkpoint bridge, and saves it,
        replacing any prior snapshot. It runs only when checkpointing is enabled (a store and
        bridge are present); otherwise it is a no-op and the default assembly is unchanged. A
        save failure propagates as a hard stop (no silent non-persistent fallback). It computes
        and re-derives nothing.
        """

        if self.continuity_checkpoint is None or self.continuity_checkpoint_bridge is None:
            return
        thought_gating_result = result.stage_results.get(
            "thought_gating_and_continuation_pressure"
        )
        autonomy_result = result.stage_results.get(
            "subjective_autonomy_and_proactive_evolution"
        )
        if thought_gating_result is None or autonomy_result is None:
            return
        snapshot = self.continuity_checkpoint_bridge.build_snapshot(
            thought_gating_result,
            autonomy_result,
            result.tick_id,
            neuromodulator_stage_result=result.stage_results.get("neuromodulator_system"),
            feeling_stage_result=result.stage_results.get("interoceptive_feeling_layer"),
        )
        self.continuity_checkpoint.save_latest(snapshot)

    def run_ticks(self, n: int) -> tuple[RuntimeTickResult, ...]:
        """Owner: composition.

        Purpose:
            Run a bounded sequence of `n` ticks and return the ordered results.

        Inputs:
            `n` - a positive integer tick count.

        Returns:
            A tuple of `n` `RuntimeTickResult` objects in tick order.

        Raises:
            ValueError if `n` is not a positive integer.
        """

        if not isinstance(n, int) or n <= 0:
            raise ValueError("run_ticks requires a positive integer tick count")
        return tuple(self.tick() for _ in range(n))


# Sentinel marking a loose `assemble_runtime` keyword argument the caller did not supply, so the
# resolver can distinguish "omitted" from "explicitly passed None" when reconciling with a profile.
_UNSET: object = object()


# The names of the capability/override seams a `RuntimeProfile` carries. Used by the resolver
# to reject combining an explicit profile with overlapping loose `assemble_runtime` kwargs.
_RUNTIME_PROFILE_FIELD_NAMES: tuple[str, ...] = (
    "dependency_specs",
    "dependency_provider",
    "config",
    "recorder",
    "gateway",
    "deterministic_thought",
    "channel_cli",
    "cli_output_sink",
    "experience_store",
    "embedding_gateway",
    "embedding_profile_name",
    "continuity_checkpoint",
    "interoceptive_sampler",
    "temporal_source",
    "external_signal_source",
    "default_signal_mode",
    "internal_monologue_carry_provider",
)


@dataclass(frozen=True)
class RuntimeProfile:
    """Owner: composition.

    Purpose:
        A first-class, introspectable bundle of the capability seams and dependency-surface
        overrides the composition root assembles a runtime with. It groups what were nine
        loose `assemble_runtime` keyword arguments plus the three dependency-surface overrides
        into one validated object, owns the cross-capability validation in one place, and
        exposes the derived capability flags as named properties.

    Failure semantics:
        `__post_init__` raises `CompositionError` on a cross-capability rule violation
        (currently: an embedding gateway without a durable experience store). Validation is
        fail-fast at construction; there is no degraded profile.

    Notes:
        This is a composition-owned capability/configuration bundle. It holds no cognitive
        policy: no salience mapping, no pressure constant, no decision threshold. Adding a new
        capability is one field plus, if needed, one derived property here, instead of another
        loose parameter threaded through `assemble_runtime`. All fields default to the current
        default assembly's capability set, so `RuntimeProfile()` is the default runtime.
    """

    dependency_specs: tuple[RuntimeDependencySpec, ...] | None = None
    dependency_provider: RuntimeDependencyProvider | None = None
    config: "CompositionConfig | None" = None
    recorder: "RuntimeObservabilityRecorder | None" = None
    gateway: "LlmGatewayAPI | None" = None
    deterministic_thought: bool = False
    channel_cli: bool = False
    cli_output_sink: "Callable[[str], None] | None" = None
    experience_store: ExperienceStore | None = None
    embedding_gateway: EmbeddingGatewayAPI | None = None
    embedding_profile_name: str = "experience-embedding"
    continuity_checkpoint: ContinuityCheckpointStore | None = None
    interoceptive_sampler: "RuntimePressureSampler | None" = None
    temporal_source: "TemporalSource | None" = None
    external_signal_source: "SensorySource | None" = None
    default_signal_mode: str = "semantic"
    aggressive_radical_prompt_profile: "AggressiveRadicalPromptProfile | None" = None
    internal_monologue_carry_provider: "Callable[[], Mapping[str, object] | None] | None" = None

    def __post_init__(self) -> None:
        # Validate the signal mode is a known value; unknown modes are a composition error
        # rather than a silent fallback to the wrong assembly path.
        if self.default_signal_mode not in ("semantic", "legacy_constant"):
            raise CompositionError(
                f"default_signal_mode must be 'semantic' or 'legacy_constant', "
                f"got '{self.default_signal_mode}'"
            )
        # Semantic memory (`34`) requires durable persistence (`33`): an embedding gateway
        # without an experience store is a composition error, not a silent no-op.
        if self.embedding_gateway is not None and self.experience_store is None:
            raise CompositionError(
                "Semantic memory requires a durable experience store: "
                "pass experience_store together with embedding_gateway"
            )
        # The injected external afferent source and the channel-bound assembly both own the
        # external afferent position; supplying both would register two competing external
        # sources, so it is a fail-fast composition error rather than a silent precedence bug.
        if self.external_signal_source is not None and self.channel_cli:
            raise CompositionError(
                "external_signal_source and channel_cli both own the external afferent: "
                "pass only one"
            )

    @property
    def semantic_memory_enabled(self) -> bool:
        """Owner: composition.

        Whether the semantic-memory assembly is active: a durable experience store and an
        embedding gateway are both present. This is the single trigger for the `03`-`10`
        de-shim wiring; it is computed once here rather than recomputed in `assemble_runtime`.
        """

        return self.experience_store is not None and self.embedding_gateway is not None


def _resolve_profile(
    profile: "RuntimeProfile | None",
    loose_kwargs: dict[str, object],
) -> "RuntimeProfile":
    """Owner: composition.

    Purpose:
        Resolve the effective `RuntimeProfile` for `assemble_runtime`. When no explicit profile
        is given, build one from the loose keyword arguments (the backward-compatible path).
        When an explicit profile is given, reject any overlapping loose kwarg so configuration
        is never silently sourced from two places.

    Inputs:
        `profile` - an explicit `RuntimeProfile` or `None`.
        `loose_kwargs` - the loose capability/override kwargs `assemble_runtime` received,
            already filtered to those the caller actually supplied (absent ones omitted).

    Returns:
        The effective `RuntimeProfile`.

    Raises:
        CompositionError if an explicit profile is combined with any overlapping loose kwarg.
    """

    if profile is None:
        specs = loose_kwargs.get("dependency_specs")
        if specs is not None:
            loose_kwargs = dict(loose_kwargs)
            loose_kwargs["dependency_specs"] = tuple(specs)
        return RuntimeProfile(**loose_kwargs)  # type: ignore[arg-type]
    overlapping = sorted(loose_kwargs.keys())
    if overlapping:
        raise CompositionError(
            "assemble_runtime received both an explicit profile and overlapping loose "
            f"keyword arguments {overlapping}; pass capabilities through the profile only"
        )
    return profile


def assemble_runtime(
    *,
    profile: "RuntimeProfile | None" = None,
    dependency_specs: list[RuntimeDependencySpec] | None | object = _UNSET,
    dependency_provider: RuntimeDependencyProvider | None | object = _UNSET,
    config: "CompositionConfig | None | object" = _UNSET,
    recorder: "RuntimeObservabilityRecorder | None | object" = _UNSET,
    gateway: "LlmGatewayAPI | None | object" = _UNSET,
    deterministic_thought: bool | object = _UNSET,
    channel_cli: bool | object = _UNSET,
    cli_output_sink: "Callable[[str], None] | None | object" = _UNSET,
    experience_store: ExperienceStore | None | object = _UNSET,
    embedding_gateway: EmbeddingGatewayAPI | None | object = _UNSET,
    embedding_profile_name: str | object = _UNSET,
    continuity_checkpoint: ContinuityCheckpointStore | None | object = _UNSET,
    interoceptive_sampler: "RuntimePressureSampler | None | object" = _UNSET,
    temporal_source: "TemporalSource | None | object" = _UNSET,
    external_signal_source: "SensorySource | None | object" = _UNSET,
    default_signal_mode: str | object = _UNSET,
    aggressive_radical_prompt_profile: "AggressiveRadicalPromptProfile | None | object" = _UNSET,
    internal_monologue_carry_provider: "Callable[[], Mapping[str, object] | None] | None | object" = _UNSET,
) -> RuntimeHandle:
    """Owner: composition.

    Purpose:
        Assemble the full nineteen-stage runtime in canonical order and return a handle.

    Inputs:
        `dependency_specs` - critical dependency specs; defaults to the baseline set plus
            the LLM static-readiness critical dependency.
        `dependency_provider` - availability provider; defaults to the LLM-readiness
            provider wrapping the baseline provider for the bound thought profile.
        `config` - per-owner first-version configs; defaults to `default_composition_config()`.
        `recorder` - optional `21` observability recorder; when omitted the runtime is
            uninstrumented and behaves exactly as the bare kernel.
        `gateway` - optional `25` LLM gateway. When omitted a production gateway backed by
            the OpenAI-compatible provider is built from the config's LLM profiles. Tests
            inject a deterministic fake-provider gateway to stay network-free.
        `deterministic_thought` - when True, assemble the deterministic internal-thought path
            and omit the LLM gateway and the `llm_profiles_ready` critical dependency, for
            explicit offline runs. This is an explicit opt-in assembly choice, never a hidden
            runtime fallback when the LLM is unavailable.

    Returns:
        A `RuntimeHandle` wrapping a fully wired `RuntimeKernel` and the ingress owner.

    Raises:
        CompositionError if the registered stage names do not equal the canonical order.

    Notes:
        This function is the only place that holds the full wiring. It constructs owners,
        owner-neutral bridges, the internal-thought path, and the kernel, then registers the
        nineteen stages in order. By default the internal-thought consumer is bound to a
        named LLM profile and that profile's static readiness is a critical dependency; the
        `deterministic_thought` opt-in assembles the deterministic path without that
        dependency.

        Capabilities may be passed either as the loose keyword arguments above (backward
        compatible) or bundled into an explicit `profile` (`RuntimeProfile`). Supplying both an
        explicit profile and an overlapping loose kwarg raises `CompositionError`.
    """

    _loose: dict[str, object] = {}
    for _name, _value in (
        ("dependency_specs", dependency_specs),
        ("dependency_provider", dependency_provider),
        ("config", config),
        ("recorder", recorder),
        ("gateway", gateway),
        ("deterministic_thought", deterministic_thought),
        ("channel_cli", channel_cli),
        ("cli_output_sink", cli_output_sink),
        ("experience_store", experience_store),
        ("embedding_gateway", embedding_gateway),
        ("embedding_profile_name", embedding_profile_name),
        ("continuity_checkpoint", continuity_checkpoint),
        ("interoceptive_sampler", interoceptive_sampler),
        ("temporal_source", temporal_source),
        ("external_signal_source", external_signal_source),
        ("default_signal_mode", default_signal_mode),
        ("aggressive_radical_prompt_profile", aggressive_radical_prompt_profile),
        ("internal_monologue_carry_provider", internal_monologue_carry_provider),
    ):
        if _value is not _UNSET:
            _loose[_name] = _value
    resolved_profile = _resolve_profile(profile, _loose)

    # Rebind the local capability names from the resolved profile so the assembly body below is
    # unchanged. The profile owns the cross-capability validation (embedding requires store) and
    # the derived `semantic_memory_enabled` flag.
    dependency_specs = (
        list(resolved_profile.dependency_specs)
        if resolved_profile.dependency_specs is not None
        else None
    )
    dependency_provider = resolved_profile.dependency_provider
    config = resolved_profile.config
    recorder = resolved_profile.recorder
    gateway = resolved_profile.gateway
    deterministic_thought = resolved_profile.deterministic_thought
    channel_cli = resolved_profile.channel_cli
    cli_output_sink = resolved_profile.cli_output_sink
    experience_store = resolved_profile.experience_store
    embedding_gateway = resolved_profile.embedding_gateway
    embedding_profile_name = resolved_profile.embedding_profile_name
    continuity_checkpoint = resolved_profile.continuity_checkpoint
    interoceptive_sampler = resolved_profile.interoceptive_sampler
    temporal_source = resolved_profile.temporal_source
    external_signal_source = resolved_profile.external_signal_source
    default_signal_mode = resolved_profile.default_signal_mode
    aggressive_radical_prompt_profile = resolved_profile.aggressive_radical_prompt_profile
    internal_monologue_carry_provider = resolved_profile.internal_monologue_carry_provider

    # R69 auto-provisioning: when default_signal_mode is "semantic" and the caller did not
    # inject an experience store and/or embedding gateway, create fresh in-memory backends so
    # the semantic assembly (the de-shimmed 03-10 chain) is the default behavior. Explicit
    # caller-provided capabilities always take precedence.
    if resolved_profile.default_signal_mode == "semantic":
        _auto_store = experience_store
        _auto_embedding = embedding_gateway
        if _auto_store is None and _auto_embedding is None:
            _auto_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
            _auto_store.initialize()
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model="deterministic-hash",
                api_key_env="HELIOS_AUTO_EMBEDDING_KEY",
                base_url="http://localhost",
            )
            _auto_embedding = EmbeddingGateway(
                provider=DeterministicHashEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"},
            )
        elif _auto_store is None:
            _auto_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
            _auto_store.initialize()
        elif _auto_embedding is None:
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model="deterministic-hash",
                api_key_env="HELIOS_AUTO_EMBEDDING_KEY",
                base_url="http://localhost",
            )
            _auto_embedding = EmbeddingGateway(
                provider=DeterministicHashEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"},
            )
        experience_store = _auto_store
        embedding_gateway = _auto_embedding
        # Rebuild the frozen profile so semantic_memory_enabled reflects the provisioned state.
        resolved_profile = replace(
            resolved_profile,
            experience_store=experience_store,
            embedding_gateway=embedding_gateway,
        )

    resolved_config = config if config is not None else default_composition_config()
    thought_profile_name = resolved_config.llm.thought_profile_name

    # R79-B: when the opt-in v3 prompt capability bundle is present, switch the embodied-prompt
    # bootstrap id to the v3-aggressive-radical variant (selects `AggressiveRadicalEmbodiedPromptPath`
    # in `EmbodiedPromptEngine`) and propagate the bundle`s `ready_channels` to the embodied-prompt
    # request bridges. Default assembly (no v3 bundle) is byte-for-byte unchanged: bootstrap id stays
    # `embodied-prompt-bootstrap:v1` and bridges fall back to the hardcoded `("cli",)` shim.
    if resolved_profile.aggressive_radical_prompt_profile is not None:
        _v3_bundle = resolved_profile.aggressive_radical_prompt_profile
        if resolved_config.embodied_prompt.prompt_bootstrap_id != "embodied-prompt-bootstrap:v1":
            raise CompositionError(
                "aggressive_radical_prompt_profile requires the default "
                "embodied-prompt-bootstrap:v1 bootstrap id on the v1 config; "
                "the v3 path is an additive sibling, not a fork that allows "
                "arbitrary baseline ids."
            )
        resolved_config = replace(
            resolved_config,
            embodied_prompt=replace(
                resolved_config.embodied_prompt,
                prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical",
            ),
        )
    _resolved_ready_channels = (
        _v3_bundle.ready_channels
        if resolved_profile.aggressive_radical_prompt_profile is not None
        else ()
    )

    def _embed_text(text: str) -> tuple[float, ...]:
        """Owner-neutral embed callable bound to the injected embedding gateway.

        Used both for embed-at-write (record summary) and embed-at-query (retrieval query).
        Any embedding failure propagates as a hard stop; there is no recency fallback.
        """

        assert embedding_gateway is not None  # guarded by the semantic-assembly branch
        request = EmbeddingRequest(
            request_id=f"experience-embedding:{abs(hash(text)) % (10**12)}",
            target_profile=embedding_profile_name,
            input_text=text,
            metadata={"consumer": "experience_store"},
        )
        return embedding_gateway.embed(request).vector

    if deterministic_thought:
        # Explicit opt-in offline assembly: deterministic thought path, no LLM dependency.
        resolved_gateway = None
        thought_path = FirstVersionInternalThoughtPath()
        resolved_specs = (
            dependency_specs if dependency_specs is not None else default_critical_dependency_specs()
        )
        resolved_provider = (
            dependency_provider
            if dependency_provider is not None
            else FirstVersionDependencyProvider()
        )
    else:
        resolved_gateway = (
            gateway
            if gateway is not None
            else LlmGateway(
                provider=OpenAICompatibleProvider(),
                registry=LlmProfileRegistry(profiles=resolved_config.llm.profiles),
            )
        )
        thought_path = LlmBackedInternalThoughtPath(
            gateway=resolved_gateway,
            profile_name=thought_profile_name,
        )
        resolved_specs = (
            dependency_specs
            if dependency_specs is not None
            else default_critical_dependency_specs() + [llm_critical_dependency_spec()]
        )
        resolved_provider = (
            dependency_provider
            if dependency_provider is not None
            else LlmReadinessDependencyProvider(
                gateway=resolved_gateway,
                bound_profile_names=(thought_profile_name,),
            )
        )

    ingress = SensoryIngress()
    # Channel-bound assembly: build the subsystem + CLI driver and route inbound through it.
    channel_subsystem: ChannelSubsystem | None = None
    subsystem_sensory_source: SubsystemBackedSensorySource | None = None
    if channel_cli:
        channel_subsystem = ChannelSubsystem()
        sink = cli_output_sink if cli_output_sink is not None else _NullCliSink()
        cli_driver = CliChannelDriver(output_sink=sink, config=CliDriverConfig())
        channel_subsystem.register_driver(cli_driver)
        channel_subsystem.apply_management_op(cli_driver.driver_id, "connect", None)
        subsystem_sensory_source = SubsystemBackedSensorySource(
            source_name_value=cli_driver.driver_id
        )
        ingress.register_source(subsystem_sensory_source)
        # Wire the channel readiness gate when the caller did not override the dependency
        # surface. CLI declares no credential, so it is always ready; the gate still routes
        # through the fail-fast startup so a future critical driver trips it.
        if dependency_specs is None:
            resolved_specs = list(resolved_specs) + [channel_critical_dependency_spec()]
        if dependency_provider is None:
            resolved_provider = ChannelReadinessDependencyProvider(
                subsystem=channel_subsystem,
                bound_driver_ids=(cli_driver.driver_id,),
                baseline_provider=resolved_provider,
            )
    elif external_signal_source is not None:
        # External-afferent assembly (R59): a real, injected `SensorySource` drives the external
        # afferent in place of the constant placeholder. Owner-neutral: composition forwards the
        # source's `RawSignal`s through `02` normalization; it does not interpret or shape content.
        # Mutually exclusive with `channel_cli` (validated on the profile).
        ingress.register_source(external_signal_source)
    else:
        ingress.register_source(FirstVersionSensorySource(signals=resolved_config.source_signals))

    # Interoceptive source (R50): opt-in. When a sampler is provided, register a real
    # interoceptive afferent producer alongside the primary source, so the `02 -> 05` body-signal
    # path carries real compute/runtime-pressure stimuli instead of being empty. Default-off: when
    # no sampler is given, no interoceptive source is registered and the assembly is unchanged.
    if interoceptive_sampler is not None:
        ingress.register_source(RuntimeInteroceptiveSource(sampler=interoceptive_sampler))

    # Internal monologue source (R80): opt-in. When a carry provider is supplied, register a
    # second-order stimulus source that emits the runtime's self-produced internal-monologue
    # content as `signal_type="internal_monologue"` `RawSignal`s, so the rumination / self-talk
    # loop re-enters the `02 -> 03 -> 04` pipeline as a real stimulus rather than just a
    # prompt-time suggestion. Default-off: when no provider is given, the assembly is unchanged.
    if internal_monologue_carry_provider is not None:
        ingress.register_source(
            InternalMonologueSource(monologue_provider=internal_monologue_carry_provider)
        )

    # Persistence-enabled assembly: register the durable experience store readiness gate so
    # an un-initializable/unwritable store fails fast at startup rather than running
    # non-persistently. Owner-neutral: composition holds no store policy. Default-off.
    if experience_store is not None:
        if dependency_specs is None:
            resolved_specs = list(resolved_specs) + [experience_store_critical_dependency_spec()]
        if dependency_provider is None:
            resolved_provider = ExperienceStoreReadinessDependencyProvider(
                store=experience_store,
                baseline_provider=resolved_provider,
            )

    # Semantic-memory assembly: register the embedding-profile static-readiness gate so an
    # unready embedding profile fails fast at startup. There is no recency fallback when
    # semantic memory is enabled. Owner-neutral; default-off.
    if embedding_gateway is not None:
        if dependency_specs is None:
            resolved_specs = list(resolved_specs) + [embedding_profile_critical_dependency_spec()]
        if dependency_provider is None:
            resolved_provider = EmbeddingReadinessDependencyProvider(
                gateway=embedding_gateway,
                bound_profile_names=(embedding_profile_name,),
                baseline_provider=resolved_provider,
            )

    # Checkpoint-enabled assembly (`42`): register the durable continuity-checkpoint readiness
    # gate so an un-initializable/unwritable checkpoint store fails fast at startup rather than
    # running without a resumable continuity checkpoint. Owner-neutral; default-off. Independent
    # of persistence (`33`): it persists a different state (latest cross-tick continuity).
    if continuity_checkpoint is not None:
        if dependency_specs is None:
            resolved_specs = list(resolved_specs) + [continuity_checkpoint_critical_dependency_spec()]
        if dependency_provider is None:
            resolved_provider = ContinuityCheckpointReadinessDependencyProvider(
                store=continuity_checkpoint,
                baseline_provider=resolved_provider,
            )

    # `03` dimension de-shims share one trigger with the `04` neuromodulation de-shim (R36):
    # the semantic-memory assembly (store + embedding gateway both present), where `03`
    # appraisal produces real signals. Deriving neuromodulation from appraisal only matters
    # once appraisal itself is real, so the de-shims activate together. The trigger is owned by
    # the resolved profile (computed once), not recomputed here.
    semantic_memory_enabled = resolved_profile.semantic_memory_enabled

    # `03` dimension de-shims (R35 novelty, R39 uncertainty + social, R40 threat + reward): when
    # enabled, all five `03` dimensions become real signals. The appraisal owner keeps every
    # salience mapping and the threat/reward prototype sets; composition only injects the raw
    # retrieval/transport/prototype fact sources. When off, the deterministic first-version
    # estimator is unchanged.
    if semantic_memory_enabled:
        dimension_estimator = GroundedDimensionEstimator(
            similarity_source=MemoryGroundedSimilaritySource(
                embed_text=_embed_text,
                store=experience_store,
            ),
            ambiguity_source=MemoryGroundedRetrievalAmbiguitySource(
                embed_text=_embed_text,
                store=experience_store,
            ),
            social_source=TransportGroundedSocialContextSource(),
            prototype_source=EmbeddingPrototypeSimilaritySource(embed_text=_embed_text),
        )
    else:
        dimension_estimator = FirstVersionDimensionEstimator()
    # `03` aggregate de-shim (R41): when enabled, the aggregate salience judgment is a real
    # dimension-grounded convex combination of the five real dimensions (owner-owned weights),
    # closing the `03` owner's P3 de-shim (all five dimensions + aggregate real). When off, the
    # constant first-version aggregate (`0.4`) is unchanged, because aggregating still-constant
    # dimensions carries no real signal.
    aggregate_estimator = (
        WeightedAggregateEstimator()
        if semantic_memory_enabled
        else FirstVersionAggregateEstimator()
    )
    # R80: when the internal-monologue source is registered, inject the fixed-dimension
    # estimator so the appraisal engine routes `modality=="internal_monologue"` stimuli to it.
    # The default `dimension_estimator` is unchanged for every other modality, preserving the
    # P3 de-shim path. The estimator is intentionally constructed only when the source is
    # registered (per R80 design section 2.3); the source-registration guard above is the
    # runtime-level opt-in.
    appraisal = RapidSalienceAppraisalEngine(
        dimension_estimator=dimension_estimator,
        aggregate_estimator=aggregate_estimator,
        internal_monologue_estimator=(
            InternalMonologueAppraisalEstimator()
            if internal_monologue_carry_provider is not None
            else None
        ),
    )
    # `04` neuromodulation de-shim (R36) + dual-timescale dynamics (R43): when enabled, levels are
    # derived from the real appraisal batch (R36 instantaneous drive) and then evolved across ticks
    # by an owner-owned dual-timescale leaky-integrator that carries the prior-tick state (R43).
    # When off, the constant first-version update path is unchanged (stateless).
    neuromodulator = NeuromodulatorEngine(
        config=resolved_config.neuromodulator,
        update_path=(
            DualTimescaleNeuromodulatorUpdatePath(
                drive_path=AppraisalDerivedNeuromodulatorUpdatePath()
            )
            if semantic_memory_enabled
            else FirstVersionNeuromodulatorUpdatePath()
        ),
        active_channel_reporter=FirstVersionActiveChannelReporter(),
    )
    # `05` feeling de-shim (R38) + dual-timescale persistence (R44) + interoceptive shaping (R51):
    # when the semantic feeling path is enabled, the instantaneous target is derived from the real
    # `04` state (R38); when an interoceptive sampler is also wired (R50 producer), the R51 path
    # nests between persistence and the neuromodulator target so the real compute/runtime-pressure
    # afferent additively shapes the felt body-state (real machine condition -> feeling -> `07`).
    # The R44 dual-timescale leaky-integrator then carries the combined target across ticks. When
    # off, the constant first-version construction path is unchanged (stateless). The
    # channel->dimension and pressure->dimension mappings are both owned by the `05` owner, not
    # composition.
    if semantic_memory_enabled:
        feeling_target_path: FeelingConstructionPath = NeuromodulatorDerivedFeelingConstructionPath()
        if interoceptive_sampler is not None:
            feeling_target_path = InteroceptiveSignalModulatedFeelingConstructionPath(
                target_path=feeling_target_path
            )
        feeling_construction_path: FeelingConstructionPath = PersistentFeelingConstructionPath(
            target_path=feeling_target_path
        )
    else:
        feeling_construction_path = FirstVersionFeelingConstructionPath()
    feeling = InteroceptiveFeelingEngine(
        config=resolved_config.feeling,
        construction_path=feeling_construction_path,
        dominant_dimension_reporter=FirstVersionDominantDimensionReporter(),
    )
    # `06` memory de-shim (R45): under the semantic-memory assembly, `06` forms affect-tagged
    # memory from the real `05` feeling state and decides consolidation worth through an
    # owner-owned salience gate (replacing the constant first-version formation/selector). When
    # off, the deterministic first-version path is unchanged.
    # `06` workspace-multiplicity source (R52): under the semantic-memory assembly, inject a
    # store-backed recalled-memory provider so `06` surfaces recalled prior affect-memories as
    # additional replay candidates, giving the `07` workspace a genuine multiplicity to arbitrate
    # (exercising R46/R47/R48 end to end). The owner owns the replay-priority mapping; this
    # provider supplies raw recalled facts only. Off when non-semantic (single-candidate path).
    recalled_memory_provider = (
        StoreBackedRecalledMemoryProvider(embed_text=_embed_text, store=experience_store)
        if semantic_memory_enabled
        else None
    )
    memory = MemoryAffectReplayEngine(
        config=resolved_config.memory,
        formation_path=(
            AffectGroundedMemoryFormationPath()
            if semantic_memory_enabled
            else FirstVersionMemoryFormationPath()
        ),
        replay_selector=(
            SalienceGatedReplayCandidateSelector()
            if semantic_memory_enabled
            else FirstVersionReplayCandidateSelector()
        ),
        recalled_memory_provider=recalled_memory_provider,
    )
    # `07` workspace de-shim (R46): under the semantic-memory assembly, `07` runs a real
    # competition (scoring each candidate from the real `06` priority_hint + the real `05`
    # feeling salience) and a bounded attention bottleneck (retaining only the top-K scoring
    # subset into the working state), replacing the constant-score / retain-everything shim.
    # When off, the deterministic first-version paths are unchanged.
    workspace = WorkspaceCompetitionEngine(
        config=resolved_config.workspace,
        competition_path=(
            SalienceWeightedWorkspaceCompetitionPath()
            if semantic_memory_enabled
            else FirstVersionWorkspaceCompetitionPath()
        ),
        retention_path=(
            BoundedAttentionRetentionPath()
            if semantic_memory_enabled
            else FirstVersionWorkingStateRetentionPath()
        ),
    )
    # `08` conscious-content de-shim (R47): under the semantic-memory assembly, `08` ignites the
    # single highest-`workspace_score_hint` retained candidate as focal reportable content
    # (global-workspace winner-take-all), instead of declaring `semantic_conflict_unresolved`
    # whenever the R46 bounded top-K working state retains more than one candidate. When off,
    # the count-based first-version selection policy is unchanged.
    consciousness = ConsciousnessEngine(
        config=resolved_config.consciousness,
        commitment_path=(
            FirstVersionConsciousCommitmentPath(
                focal_selection_policy=IgnitionFocalSelectionPolicy()
            )
            if semantic_memory_enabled
            else FirstVersionConsciousCommitmentPath()
        ),
    )
    thought_gating = ThoughtGatingEngine(
        config=resolved_config.thought_gating,
        gate_path=(
            ArousalAwareThoughtGatePath()
            if semantic_memory_enabled
            else FirstVersionThoughtGatePath()
        ),
    )
    directed_retrieval = DirectedRetrievalEngine(
        config=resolved_config.directed_retrieval,
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=(
            SemanticStoreBackedDirectedMemoryCandidateProvider(
                store=experience_store,
                embed_query=_embed_text,
            )
            if experience_store is not None and embedding_gateway is not None
            else StoreBackedDirectedMemoryCandidateProvider(store=experience_store)
            if experience_store is not None
            else FirstVersionDirectedMemoryCandidateProvider()
        ),
    )
    # R79-B: select v3 path when the bundle is active, otherwise v1 (byte-for-byte unchanged).
    _resolved_prompt_path = (
        AggressiveRadicalEmbodiedPromptPath()
        if resolved_profile.aggressive_radical_prompt_profile is not None
        else FirstVersionEmbodiedPromptPath()
    )
    embodied_prompt = EmbodiedPromptEngine(
        config=resolved_config.embodied_prompt,
        prompt_path=_resolved_prompt_path,
    )
    outward_expression = OutwardExpressionEngine(
        config=resolved_config.outward_expression,
        outward_expression_path=FirstVersionOutwardExpressionPath(),
    )
    outward_expression_externalization = OutwardExpressionExternalizationEngine(
        config=resolved_config.outward_expression_externalization,
        externalization_path=FirstVersionOutwardExpressionExternalizationPath(),
    )
    internal_thought = InternalThoughtEngine(
        config=resolved_config.internal_thought,
        thought_path=thought_path,
    )
    action_externalization = ActionExternalizationEngine(
        config=resolved_config.action_externalization,
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    planner_bridge = PlannerBridgeEngine(
        config=resolved_config.planner_bridge,
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    identity_governance = IdentityGovernanceEngine(
        config=resolved_config.identity_governance,
        governance_path=FirstVersionIdentityGovernancePath(),
    )
    experience_writeback = ExperienceWritebackEngine(
        config=resolved_config.experience_writeback,
        writeback_path=FirstVersionExperienceWritebackPath(),
    )
    autonomy = AutonomyEngine(
        config=resolved_config.autonomy,
        autonomy_path=FirstVersionAutonomyPath(),
    )
    evaluation = EvaluationEngine(
        config=resolved_config.evaluation,
        evaluation_path=FirstVersionEvaluationPath(),
    )

    # Owner-neutral carry for the prior-tick execution-timeline view. When the runtime is
    # instrumented with a readable in-memory sink, the handle updates this holder after each
    # tick and the evaluation bridge reads it when assembling the next tick's evidence.
    timeline_sink = _find_in_memory_sink(recorder)
    timeline_holder = TimelineViewHolder(instrumented=timeline_sink is not None)

    # Owner-neutral carry for the prior-tick `11` recall directive (R49). Under the
    # semantic-memory assembly the handle captures the `11` `memory_handoff` after each tick and
    # the directed-retrieval request bridge reads it next tick, so the thought owner's saved
    # recall intent steers the next tick's `10` retrieval. Default-off: no holder otherwise.
    prior_thought_recall_holder = (
        PriorThoughtRecallHolder() if semantic_memory_enabled else None
    )

    # Owner-neutral carry for the prior-tick `18` proactive-drive urgency (R62). `18` runs after
    # `09` in the tick, so the gate can only see the prior tick's drive; this holder is updated
    # post-tick from the `18` result and read by the gate-signal bridge next tick. Default-on
    # (the gate-signal bridge is in every assembly); cold-starts at the neutral baseline.
    drive_urgency_holder = PriorDriveUrgencyHolder()

    # Owner-neutral carry for the prior-tick `14` governance state (R68). The bridge reads
    # the stage's prior carry state at request-build time; the stage advances it post-tick.
    # The lambda captures `governance_stage_ref` by closure — assigned before the first tick.
    governance_request_bridge = FirstVersionIdentityGovernanceRequestBridge(
        carry_state_provider=lambda: governance_stage_ref.prior_carry_state,
    )

    kernel = RuntimeKernel(
        dependency_specs=resolved_specs,
        dependency_provider=resolved_provider,
        recorder=recorder,
    )
    stages = [
        SensoryIngressRuntimeStage(ingress=ingress),
        RapidSalienceAppraisalRuntimeStage(appraisal=appraisal),
        NeuromodulatorRuntimeStage(neuromodulator_system=neuromodulator),
        InteroceptiveFeelingRuntimeStage(feeling_layer=feeling),
        MemoryAffectReplayRuntimeStage(
            memory_layer=memory,
            binding_context_provider=FirstVersionMemoryBindingContextBridge(),
            mismatch_evidence_provider=FirstVersionPredictionMismatchEvidenceBridge(),
        ),
        WorkspaceCompetitionRuntimeStage(workspace_layer=workspace),
        ReportableConsciousContentRuntimeStage(consciousness_layer=consciousness),
        ThoughtGatingRuntimeStage(
            thought_gating_layer=thought_gating,
            signal_provider=(
                NeuromodulatorAwareThoughtGateSignalBridge(
                    temporal_source=temporal_source,
                    drive_urgency_holder=drive_urgency_holder,
                )
                if semantic_memory_enabled
                else FirstVersionThoughtGateSignalBridge(
                    temporal_source=temporal_source,
                    drive_urgency_holder=drive_urgency_holder,
                )
            ),
        ),
        DirectedRetrievalRuntimeStage(
            directed_retrieval_layer=directed_retrieval,
            request_provider=(
                ThoughtDirectedRetrievalRequestBridge(holder=prior_thought_recall_holder)
                if prior_thought_recall_holder is not None
                else FirstVersionDirectedRetrievalRequestBridge()
            ),
        ),
        EmbodiedPromptRuntimeStage(
            prompt_layer=embodied_prompt,
            # R79-B: forward `_resolved_ready_channels` (set above from the v3 bundle) to the
            # request bridge instance. When the v3 bundle is absent, `_resolved_ready_channels`
            # is `()` and the bridge`s `ready_channels` class field stays `()`, so v1 behavior
            # is byte-for-byte unchanged.
            request_provider=(
                SemanticEmbodiedPromptRequestBridge(
                    ready_channels=_resolved_ready_channels,
                )
                if semantic_memory_enabled
                else FirstVersionEmbodiedPromptRequestBridge(
                    ready_channels=_resolved_ready_channels,
                )
            ),
        ),
        OutwardExpressionRuntimeStage(outward_expression_layer=outward_expression),
        OutwardExpressionExternalizationRuntimeStage(
            externalization_layer=outward_expression_externalization,
            request_provider=FirstVersionOutwardExpressionExternalizationRequestBridge(),
        ),
        InternalThoughtRuntimeStage(
            internal_thought_layer=internal_thought,
            request_provider=(
                SemanticInternalThoughtRequestBridge()
                if semantic_memory_enabled
                else FirstVersionInternalThoughtRequestBridge()
            ),
        ),
        ActionExternalizationRuntimeStage(
            action_externalization_layer=action_externalization,
            request_provider=FirstVersionThoughtExternalizationRequestBridge(),
        ),
        PlannerBridgeRuntimeStage(
            planner_bridge_layer=planner_bridge,
            request_provider=(
                ChannelBackedPlannerBridgeRequestBridge(
                    state_provider=ChannelSubsystemStateProvider(subsystem=channel_subsystem)
                )
                if channel_subsystem is not None
                else FirstVersionPlannerBridgeRequestBridge()
            ),
        ),
        IdentityGovernanceRuntimeStage(
            identity_governance_layer=identity_governance,
            request_provider=governance_request_bridge,
        ),
        ExperienceWritebackRuntimeStage(
            experience_writeback_layer=experience_writeback,
            request_provider=FirstVersionExperienceWritebackRequestBridge(),
        ),
        AutonomyRuntimeStage(
            autonomy_layer=autonomy,
            request_provider=FirstVersionAutonomyRequestBridge(),
        ),
        EvaluationRuntimeStage(
            evaluation_layer=evaluation,
            request_provider=FirstVersionEvaluationRequestBridge(timeline_holder=timeline_holder),
        ),
    ]

    if channel_subsystem is not None and subsystem_sensory_source is not None:
        # Insert the two transport stages: inbound drain first (feeding the subsystem-backed
        # sensory source), outbound dispatch right after the planner bridge. The cognition
        # chain between them is unchanged.
        stages.insert(
            0,
            ChannelInboundDrainRuntimeStage(
                subsystem=channel_subsystem,
                sensory_sink=subsystem_sensory_source.set_pending,
            ),
        )
        planner_index = next(
            index
            for index, stage in enumerate(stages)
            if stage.stage_name == "planner_executor_feedback_bridge"
        )
        stages.insert(
            planner_index + 1,
            ChannelOutboundDispatchRuntimeStage(subsystem=channel_subsystem),
        )
        expected_order = CHANNEL_BOUND_STAGE_ORDER
    else:
        expected_order = CANONICAL_STAGE_ORDER

    registered_order = tuple(stage.stage_name for stage in stages)
    if registered_order != expected_order:
        raise CompositionError(
            "Assembled runtime stage order does not match the expected order: "
            f"expected {expected_order}, got {registered_order}"
        )
    for stage in stages:
        kernel.register_stage(stage)

    # Checkpoint wiring (`42`): build the owner-neutral bridge and capture the `09`/`18` stage
    # refs so the handle can save the latest snapshot after each tick and restore it at startup
    # (after the fail-fast gate passes). Default-off: no bridge/refs when checkpointing is off.
    continuity_checkpoint_bridge: ContinuityCheckpointBridge | None = None
    thought_gating_stage_ref: ThoughtGatingRuntimeStage | None = None
    autonomy_stage_ref: AutonomyRuntimeStage | None = None
    neuromodulator_stage_ref: NeuromodulatorRuntimeStage | None = None
    feeling_stage_ref: InteroceptiveFeelingRuntimeStage | None = None
    if continuity_checkpoint is not None:
        continuity_checkpoint_bridge = ContinuityCheckpointBridge()
        thought_gating_stage_ref = next(
            stage
            for stage in stages
            if stage.stage_name == "thought_gating_and_continuation_pressure"
        )
        autonomy_stage_ref = next(
            stage
            for stage in stages
            if stage.stage_name == "subjective_autonomy_and_proactive_evolution"
        )
        neuromodulator_stage_ref = next(
            stage for stage in stages if stage.stage_name == "neuromodulator_system"
        )
        feeling_stage_ref = next(
            stage for stage in stages if stage.stage_name == "interoceptive_feeling_layer"
        )

    # R68: bind the `14` stage ref so the governance bridge's carry-state provider
    # (a closure over this name) resolves to the live stage at request-build time.
    governance_stage_ref = next(
        stage
        for stage in stages
        if stage.stage_name == "identity_governance_self_revision_integration"
    )

    return RuntimeHandle(
        kernel=kernel,
        ingress=ingress,
        timeline_holder=timeline_holder,
        timeline_sink=timeline_sink,
        channel_subsystem=channel_subsystem,
        experience_store=experience_store,
        experience_record_bridge=(
            ExperienceRecordBridge() if experience_store is not None else None
        ),
        memory_record_bridge=(
            MemoryRecordBridge() if semantic_memory_enabled else None
        ),
        prior_thought_recall_holder=prior_thought_recall_holder,
        drive_urgency_holder=drive_urgency_holder,
        embed_record=_embed_text if embedding_gateway is not None else None,
        temporal_source=temporal_source,
        continuity_checkpoint=continuity_checkpoint,
        continuity_checkpoint_bridge=continuity_checkpoint_bridge,
        thought_gating_stage=thought_gating_stage_ref,
        autonomy_stage=autonomy_stage_ref,
        neuromodulator_stage=neuromodulator_stage_ref,
        feeling_stage=feeling_stage_ref,
        identity_governance_stage=governance_stage_ref,
    )


@dataclass
class _NullCliSink:
    """Owner: composition. A no-op CLI output sink used when no real sink is injected.

    Tests and real entry points inject their own sink (an in-memory collector or a stdout
    writer). This default keeps the assembly total without writing anywhere; it never calls
    `print`.
    """

    def __call__(self, rendered: str) -> None:
        del rendered


def _find_in_memory_sink(
    recorder: RuntimeObservabilityRecorder | None,
) -> InMemoryLogSink | None:
    """Return the first readable in-memory sink on the recorder, if any.

    The timeline carry needs a readable event source. A recorder configured only with
    write-only sinks (for example a JSON-line stream) cannot be read back here, so the
    carry stays inactive and evaluation records explicit timeline absence rather than
    fabricating a view.
    """

    if recorder is None:
        return None
    for sink in recorder.sinks:
        if isinstance(sink, InMemoryLogSink):
            return sink
    return None
