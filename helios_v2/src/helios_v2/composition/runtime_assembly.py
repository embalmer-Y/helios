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
from dataclasses import dataclass, field
from typing import Callable, Mapping

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
from helios_v2.feeling import InteroceptiveFeelingConfig, InteroceptiveFeelingEngine
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
from helios_v2.memory import MemoryAffectReplayConfig, MemoryAffectReplayEngine
from helios_v2.neuromodulation import NeuromodulatorConfig, NeuromodulatorEngine, NeuromodulatorLevels
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
from helios_v2.appraisal import MemoryGroundedDimensionEstimator, RapidSalienceAppraisalEngine
from helios_v2.channel import ChannelSubsystem, CliChannelDriver, CliDriverConfig
from helios_v2.embedding import EmbeddingGatewayAPI, EmbeddingRequest
from helios_v2.persistence import (
    ExperienceStore,
    SemanticStoreBackedDirectedMemoryCandidateProvider,
    StoreBackedDirectedMemoryCandidateProvider,
)
from helios_v2.sensory import RawSignal, SensoryIngress
from helios_v2.thought_gating import (
    FirstVersionThoughtGatePath,
    ThoughtGatingConfig,
    ThoughtGatingEngine,
)
from helios_v2.workspace import WorkspaceCompetitionConfig, WorkspaceCompetitionEngine

from .bridges import (
    AppraisalDerivedNeuromodulatorUpdatePath,
    ChannelBackedPlannerBridgeRequestBridge,
    ChannelSubsystemStateProvider,
    ExperienceRecordBridge,
    FirstVersionActiveChannelReporter,
    FirstVersionAggregateEstimator,
    FirstVersionAutonomyRequestBridge,
    FirstVersionDimensionEstimator,
    FirstVersionDirectedMemoryCandidateProvider,
    FirstVersionDirectedRetrievalRequestBridge,
    FirstVersionDominantDimensionReporter,
    FirstVersionEmbodiedPromptRequestBridge,
    FirstVersionEvaluationRequestBridge,
    FirstVersionExperienceWritebackRequestBridge,
    FirstVersionFeelingConstructionPath,
    FirstVersionIdentityGovernanceRequestBridge,
    FirstVersionInternalThoughtRequestBridge,
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
    MemoryGroundedSimilaritySource,
    SubsystemBackedSensorySource,
    TimelineViewHolder,
)
from .dependencies import (
    ChannelReadinessDependencyProvider,
    EmbeddingReadinessDependencyProvider,
    ExperienceStoreReadinessDependencyProvider,
    FirstVersionDependencyProvider,
    LlmReadinessDependencyProvider,
    channel_critical_dependency_spec,
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
    embed_record: "Callable[[str], tuple[float, ...]] | None" = None
    _reconstructor: ExecutionTimelineReconstructor = field(
        default_factory=ExecutionTimelineReconstructor
    )

    def startup(self) -> None:
        """Run the fail-fast dependency gate before any tick executes."""

        self.kernel.startup()

    def tick(self) -> RuntimeTickResult:
        """Execute one runtime tick and carry its completed timeline forward when instrumented."""

        result = self.kernel.tick()
        self._carry_timeline(result.tick_id)
        self._carry_consequence_claim(result)
        self._persist_experience(result)
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


def assemble_runtime(
    *,
    dependency_specs: list[RuntimeDependencySpec] | None = None,
    dependency_provider: RuntimeDependencyProvider | None = None,
    config: CompositionConfig | None = None,
    recorder: RuntimeObservabilityRecorder | None = None,
    gateway: LlmGatewayAPI | None = None,
    deterministic_thought: bool = False,
    channel_cli: bool = False,
    cli_output_sink: "Callable[[str], None] | None" = None,
    experience_store: ExperienceStore | None = None,
    embedding_gateway: EmbeddingGatewayAPI | None = None,
    embedding_profile_name: str = "experience-embedding",
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
    """

    resolved_config = config if config is not None else default_composition_config()
    thought_profile_name = resolved_config.llm.thought_profile_name

    # Semantic memory (`34`) requires durable persistence (`33`): an embedding gateway without
    # an experience store is a composition error, not a silent no-op.
    if embedding_gateway is not None and experience_store is None:
        raise CompositionError(
            "Semantic memory requires a durable experience store: "
            "pass experience_store together with embedding_gateway"
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
    else:
        ingress.register_source(FirstVersionSensorySource(signals=resolved_config.source_signals))

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

    # `03` novelty de-shim (R35) and `04` neuromodulation de-shim (R36) share one trigger:
    # the semantic-memory assembly (store + embedding gateway both present), where `03`
    # appraisal produces real signals. Deriving neuromodulation from appraisal only matters
    # once appraisal itself is real, so both de-shims activate together.
    semantic_memory_enabled = experience_store is not None and embedding_gateway is not None

    # `03` novelty de-shim (R35): when enabled, novelty becomes a real memory-grounded signal.
    # The appraisal owner keeps the novelty salience semantic; composition only injects the
    # retrieval-fact source. When off, the deterministic first-version estimator is unchanged.
    if semantic_memory_enabled:
        dimension_estimator = MemoryGroundedDimensionEstimator(
            similarity_source=MemoryGroundedSimilaritySource(
                embed_text=_embed_text,
                store=experience_store,
            )
        )
    else:
        dimension_estimator = FirstVersionDimensionEstimator()
    appraisal = RapidSalienceAppraisalEngine(
        dimension_estimator=dimension_estimator,
        aggregate_estimator=FirstVersionAggregateEstimator(),
    )
    # `04` neuromodulation de-shim (R36): when enabled, levels are derived deterministically
    # from the real appraisal batch around the tonic baseline (stateless; no prior-tick carry).
    # When off, the constant first-version update path is unchanged.
    neuromodulator = NeuromodulatorEngine(
        config=resolved_config.neuromodulator,
        update_path=(
            AppraisalDerivedNeuromodulatorUpdatePath()
            if semantic_memory_enabled
            else FirstVersionNeuromodulatorUpdatePath()
        ),
        active_channel_reporter=FirstVersionActiveChannelReporter(),
    )
    feeling = InteroceptiveFeelingEngine(
        config=resolved_config.feeling,
        construction_path=FirstVersionFeelingConstructionPath(),
        dominant_dimension_reporter=FirstVersionDominantDimensionReporter(),
    )
    memory = MemoryAffectReplayEngine(
        config=resolved_config.memory,
        formation_path=FirstVersionMemoryFormationPath(),
        replay_selector=FirstVersionReplayCandidateSelector(),
    )
    workspace = WorkspaceCompetitionEngine(
        config=resolved_config.workspace,
        competition_path=FirstVersionWorkspaceCompetitionPath(),
        retention_path=FirstVersionWorkingStateRetentionPath(),
    )
    consciousness = ConsciousnessEngine(
        config=resolved_config.consciousness,
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    thought_gating = ThoughtGatingEngine(
        config=resolved_config.thought_gating,
        gate_path=FirstVersionThoughtGatePath(),
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
    embodied_prompt = EmbodiedPromptEngine(
        config=resolved_config.embodied_prompt,
        prompt_path=FirstVersionEmbodiedPromptPath(),
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
            signal_provider=FirstVersionThoughtGateSignalBridge(),
        ),
        DirectedRetrievalRuntimeStage(
            directed_retrieval_layer=directed_retrieval,
            request_provider=FirstVersionDirectedRetrievalRequestBridge(),
        ),
        EmbodiedPromptRuntimeStage(
            prompt_layer=embodied_prompt,
            request_provider=FirstVersionEmbodiedPromptRequestBridge(),
        ),
        OutwardExpressionRuntimeStage(outward_expression_layer=outward_expression),
        OutwardExpressionExternalizationRuntimeStage(
            externalization_layer=outward_expression_externalization,
            request_provider=FirstVersionOutwardExpressionExternalizationRequestBridge(),
        ),
        InternalThoughtRuntimeStage(
            internal_thought_layer=internal_thought,
            request_provider=FirstVersionInternalThoughtRequestBridge(),
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
            request_provider=FirstVersionIdentityGovernanceRequestBridge(),
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
        embed_record=_embed_text if embedding_gateway is not None else None,
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
