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

from dataclasses import dataclass, field

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
)
from helios_v2.memory import MemoryAffectReplayConfig, MemoryAffectReplayEngine
from helios_v2.neuromodulation import NeuromodulatorConfig, NeuromodulatorEngine, NeuromodulatorLevels
from helios_v2.observability import RuntimeObservabilityRecorder
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
from helios_v2.appraisal import RapidSalienceAppraisalEngine
from helios_v2.sensory import RawSignal, SensoryIngress
from helios_v2.thought_gating import (
    FirstVersionThoughtGatePath,
    ThoughtGatingConfig,
    ThoughtGatingEngine,
)
from helios_v2.workspace import WorkspaceCompetitionConfig, WorkspaceCompetitionEngine

from .bridges import (
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
)
from .dependencies import FirstVersionDependencyProvider, default_critical_dependency_specs

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
    )


@dataclass
class RuntimeHandle:
    """Owner: composition.

    Purpose:
        Expose the assembled runtime lifecycle: startup, single tick, and bounded multi-tick.

    Notes:
        The handle forwards to the wrapped kernel. It exposes the sensory ingress owner so a
        driver can supply per-tick stimuli through the owner API only.
    """

    kernel: RuntimeKernel
    ingress: SensoryIngress

    def startup(self) -> None:
        """Run the fail-fast dependency gate before any tick executes."""

        self.kernel.startup()

    def tick(self) -> RuntimeTickResult:
        """Execute one runtime tick and return its structured per-stage result."""

        return self.kernel.tick()

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
        return tuple(self.kernel.tick() for _ in range(n))


def assemble_runtime(
    *,
    dependency_specs: list[RuntimeDependencySpec] | None = None,
    dependency_provider: RuntimeDependencyProvider | None = None,
    config: CompositionConfig | None = None,
    recorder: RuntimeObservabilityRecorder | None = None,
) -> RuntimeHandle:
    """Owner: composition.

    Purpose:
        Assemble the full nineteen-stage runtime in canonical order and return a handle.

    Inputs:
        `dependency_specs` - critical dependency specs; defaults to the first-version set.
        `dependency_provider` - availability provider; defaults to the first-version provider.
        `config` - per-owner first-version configs; defaults to `default_composition_config()`.
        `recorder` - optional `21` observability recorder; when omitted the runtime is
            uninstrumented and behaves exactly as the bare kernel.

    Returns:
        A `RuntimeHandle` wrapping a fully wired `RuntimeKernel` and the ingress owner.

    Raises:
        CompositionError if the registered stage names do not equal the canonical order.

    Notes:
        This function is the only place that holds the full wiring. It constructs owners,
        owner-neutral bridges, and the kernel, then registers the nineteen stages in order.
    """

    resolved_config = config if config is not None else default_composition_config()
    resolved_specs = (
        dependency_specs if dependency_specs is not None else default_critical_dependency_specs()
    )
    resolved_provider = (
        dependency_provider if dependency_provider is not None else FirstVersionDependencyProvider()
    )

    ingress = SensoryIngress()
    ingress.register_source(FirstVersionSensorySource(signals=resolved_config.source_signals))

    appraisal = RapidSalienceAppraisalEngine(
        dimension_estimator=FirstVersionDimensionEstimator(),
        aggregate_estimator=FirstVersionAggregateEstimator(),
    )
    neuromodulator = NeuromodulatorEngine(
        config=resolved_config.neuromodulator,
        update_path=FirstVersionNeuromodulatorUpdatePath(),
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
        candidate_provider=FirstVersionDirectedMemoryCandidateProvider(),
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
        thought_path=FirstVersionInternalThoughtPath(),
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
            request_provider=FirstVersionPlannerBridgeRequestBridge(),
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
            request_provider=FirstVersionEvaluationRequestBridge(),
        ),
    ]

    registered_order = tuple(stage.stage_name for stage in stages)
    if registered_order != CANONICAL_STAGE_ORDER:
        raise CompositionError(
            "Assembled runtime stage order does not match the canonical order: "
            f"expected {CANONICAL_STAGE_ORDER}, got {registered_order}"
        )
    for stage in stages:
        kernel.register_stage(stage)

    return RuntimeHandle(kernel=kernel, ingress=ingress)
