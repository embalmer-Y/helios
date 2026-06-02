from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.action_externalization import (
    ActionExternalizationConfig,
    ActionExternalizationEngine,
    FirstVersionThoughtExternalizationPath,
    ThoughtExternalizationRequest,
)
from helios_v2.autonomy import (
    AutonomyConfig,
    AutonomyEngine,
    FirstVersionAutonomyPath,
    ProactiveDriveRequest,
)
from helios_v2.planner_bridge import (
    FirstVersionPlannerBridgePath,
    PlannerBridgeConfig,
    PlannerBridgeEngine,
    PlannerBridgeRequest,
)
from helios_v2.prompt_contract import (
    EmbodiedPromptConfig,
    EmbodiedPromptEngine,
    EmbodiedPromptRequest,
    FirstVersionEmbodiedPromptPath,
)
from helios_v2.experience_writeback import (
    ExperienceWritebackConfig,
    ExperienceWritebackEngine,
    ExperienceWritebackRequest,
    FirstVersionExperienceWritebackPath,
)
from helios_v2.identity_governance import (
    FirstVersionIdentityGovernancePath,
    IdentityGovernanceConfig,
    IdentityGovernanceEngine,
    IdentityGovernanceRequest,
)
from helios_v2.appraisal import RapidSalienceAppraisalEngine
from helios_v2.appraisal.engine import AggregateJudgmentEstimator, RapidDimensionEstimate, RapidDimensionEstimator
from helios_v2.consciousness import (
    ConsciousnessConfig,
    ConsciousnessEngine,
    FirstVersionConsciousCommitmentPath,
)
from helios_v2.directed_retrieval import (
    DirectedMemoryCandidateProvider,
    DirectedRetrievalConfig,
    DirectedRetrievalEngine,
    FirstVersionDirectedRetrievalPath,
    MemoryRetrievalCandidate,
    RetrievalQueryPlan,
    RetrievalRequest,
)
from helios_v2.evaluation import (
    EvaluationConfig,
    EvaluationEngine,
    EvaluationEvidenceBundle,
    EvaluationRequest,
    FirstVersionEvaluationPath,
)
from helios_v2.feeling import (
    DominantDimensionReporter,
    FeelingConstructionPath,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingEngine,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
)
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtRequest,
)
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryAffectReplayEngine,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFormationPath,
    MemoryFormationState,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    ReplayCandidateSelector,
)
from helios_v2.neuromodulation import (
    ActiveChannelReporter,
    NeuromodulatorConfig,
    NeuromodulatorEngine,
    NeuromodulatorLevels,
    NeuromodulatorState,
    NeuromodulatorUpdatePath,
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
    OutwardExpressionExternalizationRequest,
)
from helios_v2.thought_gating import (
    FirstVersionThoughtGatePath,
    SelectedStimulusSummary,
    ThoughtGateSignalSnapshot,
    ThoughtGatingConfig,
    ThoughtGatingEngine,
)
from helios_v2.runtime import (
    ActionExternalizationRuntimeStage,
    ActionExternalizationStageResult,
    AutonomyRequestProvider,
    AutonomyRuntimeStage,
    AutonomyStageResult,
    ConsciousContentStageResult,
    DirectedRetrievalRequestProvider,
    DirectedRetrievalRuntimeStage,
    DirectedRetrievalStageResult,
    EmbodiedPromptRequestProvider,
    EmbodiedPromptRuntimeStage,
    EmbodiedPromptStageResult,
    EvaluationRequestProvider,
    EvaluationRuntimeStage,
    EvaluationStageResult,
    OutwardExpressionExternalizationRequestProvider,
    OutwardExpressionExternalizationRuntimeStage,
    OutwardExpressionExternalizationStageResult,
    OutwardExpressionRuntimeStage,
    OutwardExpressionStageResult,
    ExperienceWritebackRequestProvider,
    ExperienceWritebackRuntimeStage,
    ExperienceWritebackStageResult,
    IdentityGovernanceRequestProvider,
    IdentityGovernanceRuntimeStage,
    IdentityGovernanceStageResult,
    InternalThoughtRequestProvider,
    InternalThoughtRuntimeStage,
    InternalThoughtStageResult,
    InteroceptiveFeelingRuntimeStage,
    InteroceptiveFeelingStageResult,
    MemoryAffectReplayRuntimeStage,
    MemoryAffectReplayStageResult,
    MemoryBindingContextProvider,
    NeuromodulatorRuntimeStage,
    NeuromodulatorStageResult,
    PlannerBridgeRequestProvider,
    PlannerBridgeRuntimeStage,
    PlannerBridgeStageResult,
    PredictionMismatchEvidenceProvider,
    RapidSalienceAppraisalRuntimeStage,
    RapidSalienceAppraisalStageResult,
    ReportableConsciousContentRuntimeStage,
    RuntimeDependencyProvider,
    RuntimeKernel,
    RuntimeStageExecutionError,
    SensoryIngressRuntimeStage,
    SensoryIngressStageResult,
    ThoughtExternalizationRequestProvider,
    WorkspaceCompetitionRuntimeStage,
    WorkspaceCompetitionStageResult,
    ThoughtGateSignalProvider,
    ThoughtGatingRuntimeStage,
    ThoughtGatingStageResult,
)
from helios_v2.runtime.contracts import RuntimeFrame
from helios_v2.sensory import RawSignal, SensoryIngress, Stimulus
from helios_v2.workspace import (
    WorkingStateRetentionPath,
    WorkingStateSnapshot,
    WorkspaceCandidate,
    WorkspaceCandidateSet,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionEngine,
    WorkspaceCompetitionPath,
)


@dataclass
class NullDependencyProvider(RuntimeDependencyProvider):
    def get_dependency_status(self, name: str):
        raise AssertionError(f"Unexpected dependency lookup for {name}")


@dataclass
class FixedDimensionEstimator(RapidDimensionEstimator):
    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        return RapidDimensionEstimate(
            threat=0.2,
            reward=0.1,
            novelty=0.6,
            social=0.0,
            uncertainty=0.3,
        )


@dataclass
class FixedAggregateEstimator(AggregateJudgmentEstimator):
    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        return 0.4


def _build_neuromodulator_config() -> NeuromodulatorConfig:
    baseline = NeuromodulatorLevels(
        dopamine=0.3,
        norepinephrine=0.3,
        serotonin=0.3,
        acetylcholine=0.3,
        cortisol=0.3,
        oxytocin=0.3,
        opioid_tone=0.3,
        excitation=0.3,
        inhibition=0.3,
    )
    minimum = NeuromodulatorLevels(
        dopamine=0.0,
        norepinephrine=0.0,
        serotonin=0.0,
        acetylcholine=0.0,
        cortisol=0.0,
        oxytocin=0.0,
        opioid_tone=0.0,
        excitation=0.0,
        inhibition=0.0,
    )
    maximum = NeuromodulatorLevels(
        dopamine=1.0,
        norepinephrine=1.0,
        serotonin=1.0,
        acetylcholine=1.0,
        cortisol=1.0,
        oxytocin=1.0,
        opioid_tone=1.0,
        excitation=1.0,
        inhibition=1.0,
    )
    return NeuromodulatorConfig(
        tonic_baseline=baseline,
        legal_min=minimum,
        legal_max=maximum,
        mandatory_learned_parameters=(
            "channel_gain_sensitivity",
            "cross_channel_coupling_strength",
            "decay_speed_persistence",
            "gate_influence_strength",
        ),
    )


@dataclass
class FixedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    def update_levels(
        self,
        batch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        assert batch.batch_id.startswith("rapid-appraisal-batch:")
        assert config.decay_family == "dual_timescale_tonic_phasic"
        assert tick_id == 1
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
class FixedActiveChannelReporter(ActiveChannelReporter):
    def report_active_channels(
        self,
        state: NeuromodulatorState,
        config: NeuromodulatorConfig,
    ) -> tuple[str, ...]:
        assert state.tick_id == 1
        assert config.hard_gate_eligibility_channels == ("cortisol", "inhibition")
        return ("acetylcholine", "excitation")


def _build_feeling_config() -> InteroceptiveFeelingConfig:
    baseline = InteroceptiveFeelingVector(
        valence=0.3,
        arousal=0.3,
        tension=0.3,
        comfort=0.3,
        fatigue=0.3,
        pain_like=0.3,
        social_safety=0.3,
    )
    minimum = InteroceptiveFeelingVector(
        valence=0.0,
        arousal=0.0,
        tension=0.0,
        comfort=0.0,
        fatigue=0.0,
        pain_like=0.0,
        social_safety=0.0,
    )
    maximum = InteroceptiveFeelingVector(
        valence=1.0,
        arousal=1.0,
        tension=1.0,
        comfort=1.0,
        fatigue=1.0,
        pain_like=1.0,
        social_safety=1.0,
    )
    return InteroceptiveFeelingConfig(
        baseline_feeling=baseline,
        legal_min=minimum,
        legal_max=maximum,
        mandatory_learned_parameters=(
            "feeling_mapping_strength",
            "feeling_coupling_strength",
            "feeling_persistence",
        ),
    )


@dataclass
class FixedFeelingConstructionPath(FeelingConstructionPath):
    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        assert neuromodulator_state.state_id.startswith("neuromodulator-state:")
        assert config.baseline_feeling.valence == 0.3
        assert tick_id == 1
        assert internal_signals == ()
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
class FixedDominantDimensionReporter(DominantDimensionReporter):
    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        assert state.tick_id == 1
        assert config.baseline_feeling.comfort == 0.3
        return ("arousal", "tension")


def _build_memory_config() -> MemoryAffectReplayConfig:
    return MemoryAffectReplayConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        storage_bootstrap_state_id="memory-bootstrap:v1",
        mandatory_learned_parameters=(
            "memory_family_write_policy",
            "replay_priority_policy",
            "consolidation_policy",
        ),
    )


@dataclass
class FixedMemoryFormationPath(MemoryFormationPath):
    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        assert feeling_state.state_id.startswith("interoceptive-feeling-state:")
        assert binding_context is not None
        assert binding_context.context_id == "binding:runtime:1"
        assert mismatch_evidence is not None
        assert mismatch_evidence.evidence_id == "mismatch:runtime:1"
        assert config.storage_bootstrap_state_id == "memory-bootstrap:v1"
        assert tick_id == 1
        return (
            AffectTaggedMemoryItem(
                memory_id="memory:runtime:1",
                family="episodic",
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


@dataclass
class FixedReplayCandidateSelector(ReplayCandidateSelector):
    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        assert len(memory_items) == 1
        assert feeling_state.tick_id == 1
        assert mismatch_evidence is not None
        assert config.legal_max_priority == 1.0
        return (
            MemoryReplayCandidate(
                candidate_id="candidate:runtime:1",
                memory_id=memory_items[0].memory_id,
                family=memory_items[0].family,
                source_feeling_state_id=feeling_state.state_id,
                replay_reasons=(
                    "high_affect_intensity",
                    "prediction_mismatch_or_surprise",
                ),
                forced_consolidation=True,
                priority_hint=0.9,
            ),
        )


@dataclass
class FixedBindingContextProvider(MemoryBindingContextProvider):
    def build_binding_context(
        self,
        frame,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> MemoryBindingContext | None:
        assert frame.tick_id == 1
        assert feeling_result.state.tick_id == 1
        return MemoryBindingContext(
            context_id="binding:runtime:1",
            source_kind="runtime_chain",
            content=MemoryContentPacket(
                content_kind="situational-summary",
                summary_ref="summary:runtime:1",
                context_ref="context:runtime:1",
                salient_tokens=("hello", "novelty"),
            ),
        )


@dataclass
class FixedMismatchEvidenceProvider(PredictionMismatchEvidenceProvider):
    def build_mismatch_evidence(
        self,
        frame,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> PredictionMismatchEvidence | None:
        assert frame.tick_id == 1
        assert feeling_result.publish_op.state_id == feeling_result.state.state_id
        return PredictionMismatchEvidence(
            evidence_id="mismatch:runtime:1",
            source_reference_id=feeling_result.state.state_id,
            mismatch_score=0.8,
            anomaly_score=0.85,
            confidence=0.9,
        )


def _build_workspace_config() -> WorkspaceCompetitionConfig:
    return WorkspaceCompetitionConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        working_state_bootstrap_id="workspace-bootstrap:v1",
        mandatory_learned_parameters=(
            "competition_policy",
            "candidate_retention_policy",
            "working_state_update_policy",
        ),
    )


def _build_consciousness_config() -> ConsciousnessConfig:
    return ConsciousnessConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        conscious_state_bootstrap_id="consciousness-bootstrap:v1",
        max_supporting_context_items=2,
        mandatory_learned_parameters=(
            "commitment_policy",
            "quiet_state_policy",
            "semantic_shaping_policy",
        ),
    )


def _build_thought_gating_config() -> ThoughtGatingConfig:
    return ThoughtGatingConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        continuation_state_bootstrap_id="continuation-bootstrap:v1",
        mandatory_learned_parameters=(
            "gate_policy",
            "continuation_policy",
            "signal_normalization_policy",
        ),
    )


def _build_directed_retrieval_config() -> DirectedRetrievalConfig:
    return DirectedRetrievalConfig(
        max_hits_per_tier=2,
        max_short_term_context=1,
        retrieval_bootstrap_id="directed-retrieval-bootstrap:v1",
        mandatory_learned_parameters=(
            "retrieval_planning_policy",
            "tier_selection_policy",
            "thought_window_shaping_policy",
        ),
    )


def _build_internal_thought_config() -> InternalThoughtConfig:
    return InternalThoughtConfig(
        legal_min_sufficiency=0.0,
        legal_max_sufficiency=1.0,
        thought_bootstrap_id="internal-thought-bootstrap:v1",
        mandatory_learned_parameters=(
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        ),
    )


def _build_embodied_prompt_config() -> EmbodiedPromptConfig:
    return EmbodiedPromptConfig(
        max_layer_count=8,
        prompt_bootstrap_id="embodied-prompt-bootstrap:v1",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )


def _build_action_externalization_config() -> ActionExternalizationConfig:
    return ActionExternalizationConfig(
        legal_min_outbound_intensity=0.0,
        legal_max_outbound_intensity=1.0,
        externalization_bootstrap_id="action-externalization-bootstrap:v1",
        mandatory_learned_parameters=(
            "normalization_policy",
            "bridge_evidence_policy",
            "bridge_rejection_policy",
        ),
    )


def _build_planner_bridge_config() -> PlannerBridgeConfig:
    return PlannerBridgeConfig(
        legal_min_intensity=0.0,
        legal_max_intensity=1.0,
        bridge_bootstrap_id="planner-bridge-bootstrap:v1",
        mandatory_learned_parameters=(
            "policy_evaluation_policy",
            "channel_selection_policy",
            "feedback_normalization_policy",
        ),
    )


def _build_identity_governance_config() -> IdentityGovernanceConfig:
    return IdentityGovernanceConfig(
        legal_min_confidence=0.0,
        legal_max_confidence=1.0,
        governance_bootstrap_id="identity-governance-bootstrap:v1",
        mandatory_learned_parameters=(
            "governance_evaluation_policy",
            "pressure_interpretation_policy",
            "supported_revision_policy",
            "boundary_check_policy",
        ),
    )


def _build_experience_writeback_config() -> ExperienceWritebackConfig:
    return ExperienceWritebackConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        writeback_bootstrap_id="experience-writeback-bootstrap:v1",
        mandatory_learned_parameters=(
            "continuity_classification_policy",
            "consolidation_priority_policy",
            "autobiographical_salience_policy",
        ),
    )


def _build_outward_expression_config() -> OutwardExpressionConfig:
    return OutwardExpressionConfig(
        outward_expression_bootstrap_id="outward-expression-bootstrap:v1",
        mandatory_learned_parameters=(
            "delivery_guidance_policy",
            "boundary_rendering_policy",
            "draft_publication_policy",
        ),
    )


def _build_outward_expression_externalization_config() -> OutwardExpressionExternalizationConfig:
    return OutwardExpressionExternalizationConfig(
        externalization_bootstrap_id="outward-expression-externalization-bootstrap:v1",
        mandatory_learned_parameters=(
            "envelope_rendering_policy",
            "delivery_selection_policy",
            "execution_boundary_policy",
        ),
    )


def _build_evaluation_config() -> EvaluationConfig:
    return EvaluationConfig(
        evaluation_bootstrap_id="evaluation-bootstrap:v1",
        mandatory_learned_parameters=(
            "fidelity_scoring_policy",
            "gap_analysis_policy",
            "long_range_diagnostic_policy",
        ),
    )


def _build_autonomy_config() -> AutonomyConfig:
    return AutonomyConfig(
        autonomy_bootstrap_id="autonomy-bootstrap:v1",
        mandatory_learned_parameters=(
            "drive_integration_policy",
            "continuity_carry_policy",
            "proactive_externalization_policy",
        ),
    )


@dataclass
class FixedWorkspaceCompetitionPath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        assert len(replay_candidates) == 1
        assert replay_candidates[0].forced_consolidation is True
        assert feeling_state.state_id.startswith("interoceptive-feeling-state:")
        assert config.working_state_bootstrap_id == "workspace-bootstrap:v1"
        assert tick_id == 1
        return WorkspaceCandidateSet(
            set_id="workspace-set:runtime:1",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:runtime:1",
                    source_memory_candidate_id=replay_candidates[0].candidate_id,
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=replay_candidates[0].priority_hint,
                    forced_consolidation=replay_candidates[0].forced_consolidation,
                    workspace_score_hint=0.95,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class FixedWorkingStateRetentionPath(WorkingStateRetentionPath):
    def retain_working_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkingStateSnapshot:
        assert candidate_set.set_id == "workspace-set:runtime:1"
        assert config.legal_max_score == 1.0
        assert tick_id == 1
        return WorkingStateSnapshot(
            state_id="working-state:runtime:1",
            source_candidate_set_id=candidate_set.set_id,
            retained_candidate_ids=("workspace-candidate:runtime:1",),
            tick_id=tick_id,
        )


@dataclass
class FixedThoughtGateSignalProvider(ThoughtGateSignalProvider):
    def build_signal_snapshot(
        self,
        frame,
        conscious_result: ConsciousContentStageResult,
    ) -> ThoughtGateSignalSnapshot:
        assert frame.tick_id == 1
        assert conscious_result.state.state_id.startswith("conscious-state:")
        return ThoughtGateSignalSnapshot(
            snapshot_id="gate-snapshot:runtime:1",
            source_conscious_state_id=conscious_result.state.state_id,
            workload_pressure=0.1,
            global_activation_level=0.9,
            temporal_signal=0.4,
            drive_urgency_signal=0.7,
            dmn_available=True,
            selected_stimuli=(
                SelectedStimulusSummary(
                    stimulus_id="stimulus:runtime:1",
                    source_kind="external_text",
                    source_channel_id="cli",
                    stimulus_intensity=0.9,
                    novelty_signal=0.6,
                    sensitization_signal=0.2,
                ),
            ),
            tick_id=frame.tick_id,
        )


@dataclass
class FixedDirectedRetrievalRequestProvider(DirectedRetrievalRequestProvider):
    def build_request(self, frame, thought_gating_result) -> RetrievalRequest:
        assert frame.tick_id == 1
        return RetrievalRequest(
            request_id="retrieval-request:runtime:1",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            compact_stimuli=thought_gating_result.result.selected_stimuli,
            recall_intent="remember runtime chain context",
            selected_memory_refs=("memory:runtime:1",),
            target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
            limit=2,
            tick_id=frame.tick_id,
        )


@dataclass
class FixedDirectedMemoryCandidateProvider(DirectedMemoryCandidateProvider):
    def collect_candidates(self, plan: RetrievalQueryPlan) -> tuple[MemoryRetrievalCandidate, ...]:
        assert plan.plan_id == "retrieval-plan:retrieval-request:runtime:1"
        return (
            MemoryRetrievalCandidate(
                candidate_id="candidate:short:runtime:1",
                tier="short_term",
                memory_id="memory:short:runtime:1",
                memory_type="short_term_context",
                summary="current runtime stimulus context",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
            MemoryRetrievalCandidate(
                candidate_id="candidate:mid:runtime:1",
                tier="mid_term",
                memory_id="memory:runtime:1",
                memory_type="episodic",
                summary="situational-summary: hello, novelty",
                score=0.85,
                source="memory_affect_and_replay",
                tags=("episodic",),
            ),
            MemoryRetrievalCandidate(
                candidate_id="candidate:auto:runtime:1",
                tier="autobiographical",
                memory_id="memory:auto:runtime:1",
                memory_type="autobiographical",
                summary="runtime continuity trace",
                score=0.65,
                source="memory_affect_and_replay",
                tags=("continuity",),
            ),
        )


@dataclass
class FixedInternalThoughtRequestProvider(InternalThoughtRequestProvider):
    def build_request(
        self,
        frame,
        thought_gating_result,
        directed_retrieval_result,
        prompt_result,
    ) -> InternalThoughtRequest:
        assert frame.tick_id == 1
        thought_contract = next(
            contract for contract in prompt_result.contracts if contract.consumer_kind == "thought"
        )
        return InternalThoughtRequest(
            request_id="internal-thought-request:runtime:1",
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
            tick_id=frame.tick_id,
        )


@dataclass
class FixedEmbodiedPromptRequestProvider(EmbodiedPromptRequestProvider):
    def build_requests(
        self,
        frame,
        conscious_result,
        thought_gating_result,
        directed_retrieval_result,
    ) -> tuple[EmbodiedPromptRequest, ...]:
        assert frame.tick_id == 1
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
        return (
            EmbodiedPromptRequest(
                request_id="embodied-prompt-request:thought:runtime:1",
                consumer_kind="thought",
                source_conscious_state_id=conscious_result.state.state_id,
                source_gate_result_id=thought_gating_result.result.result_id,
                source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=frame.tick_id,
            ),
            EmbodiedPromptRequest(
                request_id="embodied-prompt-request:outward-expression:runtime:1",
                consumer_kind="outward_expression",
                source_conscious_state_id=conscious_result.state.state_id,
                source_gate_result_id=thought_gating_result.result.result_id,
                source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
                stimulus_summary=stimulus_summary,
                state_summary=state_summary,
                retrieval_summary=retrieval_summary,
                capability_summary=capability_summary,
                identity_boundary_summary=identity_boundary_summary,
                tick_id=frame.tick_id,
            ),
        )


@dataclass
class FixedThoughtExternalizationRequestProvider(ThoughtExternalizationRequestProvider):
    def build_request(self, frame, internal_thought_result) -> ThoughtExternalizationRequest:
        assert frame.tick_id == 1
        return ThoughtExternalizationRequest(
            request_id="externalization-request:runtime:1",
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            proposal_carrier_present=internal_thought_result.result.action_proposal is not None,
            target_binding_context={"target_user_id": "user:runtime:1"},
            channel_hint_context={"channel_family": "cli"},
            tick_id=frame.tick_id,
        )


@dataclass
class FixedOutwardExpressionExternalizationRequestProvider(
    OutwardExpressionExternalizationRequestProvider
):
    def build_request(
        self,
        frame,
        outward_expression_result,
    ) -> OutwardExpressionExternalizationRequest:
        assert frame.tick_id == 1
        draft = outward_expression_result.draft
        return OutwardExpressionExternalizationRequest(
            request_id="outward-expression-externalization-request:runtime:1",
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
class FixedEvaluationRequestProvider(EvaluationRequestProvider):
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
        assert frame.tick_id == 1
        assert internal_thought_result.result.result_id.startswith("thought-cycle-result:")
        assert action_externalization_result.result.result_id.startswith("thought-externalization-result:")
        assert planner_bridge_result.result.result_id.startswith("planner-bridge-result:")
        assert identity_governance_result.result.result_id.startswith("identity-governance-result:")
        assert len(experience_writeback_result.results) == 2
        assert autonomy_result.result.result_id.startswith("autonomy-result:")
        assert prompt_result.outward_expression_request is not None
        assert outward_expression_result.draft.draft_id.startswith("outward-expression-draft:")
        assert outward_expression_externalization_result.draft.draft_id.startswith(
            "outward-expression-externalization-draft:"
        )
        return EvaluationRequest(
            request_id="evaluation-request:runtime:1",
            scenario_kind="runtime_tick",
            time_window_summary={
                "window_label": "runtime-tick:1",
                "late_session_degradation_status": "not_evaluated",
                "specific_recall_persistence_status": "not_evaluated",
                "user_visible_anchoring_drift_status": "not_evaluated",
                "comparison_window_label": "runtime_tick:1",
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
        assert frame.tick_id == 1
        thought_result = internal_thought_result.result
        action_result = action_externalization_result.result
        planner_result = planner_bridge_result.result
        governance_result = identity_governance_result.result
        return EvaluationEvidenceBundle(
            bundle_id="evaluation-bundle:runtime:1",
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
        )


@dataclass
class FixedAutonomyRequestProvider(AutonomyRequestProvider):
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
        assert frame.tick_id == 1
        assert prompt_result.outward_expression_view is not None
        return ProactiveDriveRequest(
            request_id="autonomy-request:runtime:1",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
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
            continuation_summary={"continuation_pressure": 0.8},
            retrieval_pull_summary={
                "retrieval_pull": float(
                    len(directed_retrieval_result.bundle.mid_term_hits)
                    + len(directed_retrieval_result.bundle.autobiographical_hits)
                )
                / 4.0,
            },
            temporal_pressure_summary={"temporal_pressure": 0.7},
            identity_unresolved_summary={"identity_unresolved_pressure": 0.6},
            outward_readiness_summary={
                "outward_ready": True,
                "externalization_blocked": False,
            },
        )


@dataclass
class TickSequencedAutonomyRequestProvider(AutonomyRequestProvider):
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
        if frame.tick_id == 1:
            continuation_pressure = 0.8
            retrieval_pull = 0.3
            temporal_pressure = 0.7
            identity_unresolved_pressure = 0.6
            outward_ready = True
            externalization_blocked = True
        else:
            continuation_pressure = 0.1
            retrieval_pull = 0.1
            temporal_pressure = 0.1
            identity_unresolved_pressure = 0.1
            outward_ready = False
            externalization_blocked = False

        return ProactiveDriveRequest(
            request_id=f"autonomy-request:carry:{frame.tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_retrieval_bundle_id=directed_retrieval_result.bundle.bundle_id,
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
            continuation_summary={"continuation_pressure": continuation_pressure},
            retrieval_pull_summary={"retrieval_pull": retrieval_pull},
            temporal_pressure_summary={"temporal_pressure": temporal_pressure},
            identity_unresolved_summary={"identity_unresolved_pressure": identity_unresolved_pressure},
            outward_readiness_summary={
                "outward_ready": outward_ready,
                "externalization_blocked": externalization_blocked,
            },
        )


@dataclass
class FixedPlannerBridgeRequestProvider(PlannerBridgeRequestProvider):
    def build_request(self, frame, action_externalization_result) -> PlannerBridgeRequest:
        assert frame.tick_id == 1
        return PlannerBridgeRequest(
            request_id="planner-bridge-request:runtime:1",
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
            tick_id=frame.tick_id,
        )


@dataclass
class FixedIdentityGovernanceRequestProvider(IdentityGovernanceRequestProvider):
    def build_request(self, frame, internal_thought_result) -> IdentityGovernanceRequest:
        assert frame.tick_id == 1
        proposal = internal_thought_result.result.self_revision_proposal
        assert proposal is not None
        return IdentityGovernanceRequest(
            request_id="identity-governance-request:runtime:1",
            source_thought_cycle_result_id=internal_thought_result.result.result_id,
            source_proposal_id=proposal.proposal_id,
            proposal_present=True,
            proposal_snapshot={
                "owner_path": "self_revision_governance_bridge",
                "revision_type": "autobiographical_identity_narrative_revision",
                "requested_change": {"narrative_summary": proposal.requested_change_summary},
                "confidence": 0.78,
                "reason_trace": (proposal.reason_trace,),
            },
            identity_state_snapshot={
                "self_definition": "runtime identity definition",
                "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
                "identity_metadata": {},
                "current_revision": "bootstrap",
                "revision_history_length": 0,
            },
            governance_trace_summary={},
            recent_governance_trace_history=(),
            tick_id=frame.tick_id,
        )


@dataclass
class FixedExperienceWritebackRequestProvider(ExperienceWritebackRequestProvider):
    def build_requests(
        self,
        frame,
        planner_bridge_result,
        identity_governance_result,
    ) -> tuple[ExperienceWritebackRequest, ...]:
        assert frame.tick_id == 1
        planner_decision = planner_bridge_result.result.action_decision
        planner_feedback = planner_bridge_result.execution_feedback
        assert planner_decision is not None
        assert planner_feedback is not None
        revision_decision = identity_governance_result.result.revision_decision
        applied_identity_state = identity_governance_result.result.applied_identity_state
        assert applied_identity_state is not None
        return (
            ExperienceWritebackRequest(
                request_id="experience-writeback-request:planner:runtime:1",
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
                reason_trace=(
                    "planner bridge executed the normalized external action",
                ),
                tick_id=frame.tick_id,
            ),
            ExperienceWritebackRequest(
                request_id="experience-writeback-request:identity:runtime:1",
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
                tick_id=frame.tick_id,
            ),
        )


@dataclass
class FakeSource:
    @property
    def source_name(self) -> str:
        return "cli"

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        return (
            RawSignal(
                signal_id="001",
                source_name="cli",
                signal_type="text",
                content="hello runtime chain",
                channel="cli",
                metadata={"turn_id": "t1"},
            ),
        )


def _build_runtime_chain() -> RuntimeKernel:
    ingress = SensoryIngress()
    ingress.register_source(FakeSource())
    appraisal = RapidSalienceAppraisalEngine(
        dimension_estimator=FixedDimensionEstimator(),
        aggregate_estimator=FixedAggregateEstimator(),
    )
    neuromodulator = NeuromodulatorEngine(
        config=_build_neuromodulator_config(),
        update_path=FixedNeuromodulatorUpdatePath(),
        active_channel_reporter=FixedActiveChannelReporter(),
    )
    feeling = InteroceptiveFeelingEngine(
        config=_build_feeling_config(),
        construction_path=FixedFeelingConstructionPath(),
        dominant_dimension_reporter=FixedDominantDimensionReporter(),
    )
    memory = MemoryAffectReplayEngine(
        config=_build_memory_config(),
        formation_path=FixedMemoryFormationPath(),
        replay_selector=FixedReplayCandidateSelector(),
    )
    workspace = WorkspaceCompetitionEngine(
        config=_build_workspace_config(),
        competition_path=FixedWorkspaceCompetitionPath(),
        retention_path=FixedWorkingStateRetentionPath(),
    )
    consciousness = ConsciousnessEngine(
        config=_build_consciousness_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    thought_gating = ThoughtGatingEngine(
        config=_build_thought_gating_config(),
        gate_path=FirstVersionThoughtGatePath(),
    )
    directed_retrieval = DirectedRetrievalEngine(
        config=_build_directed_retrieval_config(),
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=FixedDirectedMemoryCandidateProvider(),
    )
    embodied_prompt = EmbodiedPromptEngine(
        config=_build_embodied_prompt_config(),
        prompt_path=FirstVersionEmbodiedPromptPath(),
    )
    outward_expression = OutwardExpressionEngine(
        config=_build_outward_expression_config(),
        outward_expression_path=FirstVersionOutwardExpressionPath(),
    )
    outward_expression_externalization = OutwardExpressionExternalizationEngine(
        config=_build_outward_expression_externalization_config(),
        externalization_path=FirstVersionOutwardExpressionExternalizationPath(),
    )
    evaluation = EvaluationEngine(
        config=_build_evaluation_config(),
        evaluation_path=FirstVersionEvaluationPath(),
    )
    autonomy = AutonomyEngine(
        config=_build_autonomy_config(),
        autonomy_path=FirstVersionAutonomyPath(),
    )
    internal_thought = InternalThoughtEngine(
        config=_build_internal_thought_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    action_externalization = ActionExternalizationEngine(
        config=_build_action_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    planner_bridge = PlannerBridgeEngine(
        config=_build_planner_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    identity_governance = IdentityGovernanceEngine(
        config=_build_identity_governance_config(),
        governance_path=FirstVersionIdentityGovernancePath(),
    )
    experience_writeback = ExperienceWritebackEngine(
        config=_build_experience_writeback_config(),
        writeback_path=FirstVersionExperienceWritebackPath(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(SensoryIngressRuntimeStage(ingress=ingress))
    kernel.register_stage(RapidSalienceAppraisalRuntimeStage(appraisal=appraisal))
    kernel.register_stage(NeuromodulatorRuntimeStage(neuromodulator_system=neuromodulator))
    kernel.register_stage(InteroceptiveFeelingRuntimeStage(feeling_layer=feeling))
    kernel.register_stage(
        MemoryAffectReplayRuntimeStage(
            memory_layer=memory,
            binding_context_provider=FixedBindingContextProvider(),
            mismatch_evidence_provider=FixedMismatchEvidenceProvider(),
        )
    )
    kernel.register_stage(WorkspaceCompetitionRuntimeStage(workspace_layer=workspace))
    kernel.register_stage(ReportableConsciousContentRuntimeStage(consciousness_layer=consciousness))
    kernel.register_stage(
        ThoughtGatingRuntimeStage(
            thought_gating_layer=thought_gating,
            signal_provider=FixedThoughtGateSignalProvider(),
        )
    )
    kernel.register_stage(
        DirectedRetrievalRuntimeStage(
            directed_retrieval_layer=directed_retrieval,
            request_provider=FixedDirectedRetrievalRequestProvider(),
        )
    )
    kernel.register_stage(
        EmbodiedPromptRuntimeStage(
            prompt_layer=embodied_prompt,
            request_provider=FixedEmbodiedPromptRequestProvider(),
        )
    )
    kernel.register_stage(
        OutwardExpressionRuntimeStage(
            outward_expression_layer=outward_expression,
        )
    )
    kernel.register_stage(
        OutwardExpressionExternalizationRuntimeStage(
            externalization_layer=outward_expression_externalization,
            request_provider=FixedOutwardExpressionExternalizationRequestProvider(),
        )
    )
    kernel.register_stage(
        InternalThoughtRuntimeStage(
            internal_thought_layer=internal_thought,
            request_provider=FixedInternalThoughtRequestProvider(),
        )
    )
    kernel.register_stage(
        ActionExternalizationRuntimeStage(
            action_externalization_layer=action_externalization,
            request_provider=FixedThoughtExternalizationRequestProvider(),
        )
    )
    kernel.register_stage(
        PlannerBridgeRuntimeStage(
            planner_bridge_layer=planner_bridge,
            request_provider=FixedPlannerBridgeRequestProvider(),
        )
    )
    kernel.register_stage(
        IdentityGovernanceRuntimeStage(
            identity_governance_layer=identity_governance,
            request_provider=FixedIdentityGovernanceRequestProvider(),
        )
    )
    kernel.register_stage(
        ExperienceWritebackRuntimeStage(
            experience_writeback_layer=experience_writeback,
            request_provider=FixedExperienceWritebackRequestProvider(),
        )
    )
    kernel.register_stage(
        AutonomyRuntimeStage(
            autonomy_layer=autonomy,
            request_provider=FixedAutonomyRequestProvider(),
        )
    )
    kernel.register_stage(
        EvaluationRuntimeStage(
            evaluation_layer=evaluation,
            request_provider=FixedEvaluationRequestProvider(),
        )
    )
    return kernel


def test_runtime_chain_executes_sensory_ingress_then_rapid_appraisal_then_neuromodulator_then_feeling_then_memory_then_workspace_then_consciousness() -> None:
    kernel = _build_runtime_chain()

    result = kernel.tick()

    sensory_result = result.stage_results["sensory_ingress"]
    appraisal_result = result.stage_results["rapid_salience_appraisal"]
    neuromodulator_result = result.stage_results["neuromodulator_system"]
    feeling_result = result.stage_results["interoceptive_feeling_layer"]
    memory_result = result.stage_results["memory_affect_and_replay"]
    workspace_result = result.stage_results["workspace_competition_and_working_state"]
    consciousness_result = result.stage_results["reportable_conscious_content"]
    thought_gating_result = result.stage_results["thought_gating_and_continuation_pressure"]
    directed_retrieval_result = result.stage_results["directed_retrieval_into_thought_window"]
    prompt_result = result.stage_results["embodied_subjective_prompt_and_action_autonomy"]
    outward_expression_result = result.stage_results["outward_expression_owner"]
    outward_expression_externalization_result = result.stage_results[
        "outward_expression_execution_externalization_owner"
    ]
    internal_thought_result = result.stage_results["internal_thought_loop_owner"]
    action_externalization_result = result.stage_results["action_proposal_externalization_contract"]
    planner_bridge_result = result.stage_results["planner_executor_feedback_bridge"]
    identity_governance_result = result.stage_results["identity_governance_self_revision_integration"]
    experience_writeback_result = result.stage_results[
        "execution_writeback_and_autobiographical_consolidation"
    ]
    autonomy_result = result.stage_results["subjective_autonomy_and_proactive_evolution"]
    evaluation_result = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"]
    assert isinstance(sensory_result, SensoryIngressStageResult)
    assert isinstance(appraisal_result, RapidSalienceAppraisalStageResult)
    assert isinstance(neuromodulator_result, NeuromodulatorStageResult)
    assert isinstance(feeling_result, InteroceptiveFeelingStageResult)
    assert isinstance(memory_result, MemoryAffectReplayStageResult)
    assert isinstance(workspace_result, WorkspaceCompetitionStageResult)
    assert isinstance(consciousness_result, ConsciousContentStageResult)
    assert isinstance(thought_gating_result, ThoughtGatingStageResult)
    assert isinstance(directed_retrieval_result, DirectedRetrievalStageResult)
    assert isinstance(prompt_result, EmbodiedPromptStageResult)
    assert isinstance(outward_expression_result, OutwardExpressionStageResult)
    assert isinstance(
        outward_expression_externalization_result,
        OutwardExpressionExternalizationStageResult,
    )
    assert isinstance(internal_thought_result, InternalThoughtStageResult)
    assert isinstance(action_externalization_result, ActionExternalizationStageResult)
    assert isinstance(planner_bridge_result, PlannerBridgeStageResult)
    assert isinstance(identity_governance_result, IdentityGovernanceStageResult)
    assert isinstance(experience_writeback_result, ExperienceWritebackStageResult)
    assert isinstance(autonomy_result, AutonomyStageResult)
    assert isinstance(evaluation_result, EvaluationStageResult)
    assert len(sensory_result.batch.stimuli) == 1
    assert sensory_result.publish_op.batch_id == sensory_result.batch.batch_id
    assert appraisal_result.assess_op.stimulus_batch_id == sensory_result.batch.batch_id
    assert appraisal_result.batch.batch_id == f"rapid-appraisal-batch:{sensory_result.batch.batch_id}"
    assert appraisal_result.publish_op.appraisal_batch_id == appraisal_result.batch.batch_id
    assert appraisal_result.batch.appraisals[0].provenance_signal_id == "001"
    assert appraisal_result.batch.appraisals[0].salience.aggregate == 0.4
    assert neuromodulator_result.update_op.appraisal_batch_id == appraisal_result.batch.batch_id
    assert neuromodulator_result.state.source_appraisal_batch_id == appraisal_result.batch.batch_id
    assert neuromodulator_result.state.tick_id == 1
    assert neuromodulator_result.state.levels.acetylcholine == 0.7
    assert neuromodulator_result.publish_op.state_id == neuromodulator_result.state.state_id
    assert neuromodulator_result.publish_op.active_channels == ("acetylcholine", "excitation")
    assert feeling_result.update_op.neuromodulator_state_id == neuromodulator_result.state.state_id
    assert feeling_result.update_op.internal_signal_count == 0
    assert feeling_result.state.source_neuromodulator_state_id == neuromodulator_result.state.state_id
    assert feeling_result.state.tick_id == 1
    assert feeling_result.state.feeling.arousal == 0.7
    assert feeling_result.publish_op.state_id == feeling_result.state.state_id
    assert feeling_result.publish_op.dominant_dimensions == ("arousal", "tension")
    assert memory_result.record_op.feeling_state_id == feeling_result.state.state_id
    assert memory_result.record_op.binding_context_id == "binding:runtime:1"
    assert memory_result.record_op.mismatch_evidence_id == "mismatch:runtime:1"
    assert memory_result.state.source_feeling_state_id == feeling_result.state.state_id
    assert memory_result.state.tick_id == 1
    assert memory_result.state.memory_items[0].binding_context_id == "binding:runtime:1"
    assert memory_result.state.replay_candidates[0].source_feeling_state_id == feeling_result.state.state_id
    assert memory_result.state.replay_candidates[0].replay_reasons == (
        "high_affect_intensity",
        "prediction_mismatch_or_surprise",
    )
    assert memory_result.publish_replay_candidates_op.candidate_count == 1
    assert memory_result.publish_replay_candidates_op.families == ("episodic",)
    assert memory_result.publish_state_op.state_id == memory_result.state.state_id
    assert memory_result.publish_state_op.memory_count == 1
    assert workspace_result.run_op.candidate_count == 1
    assert workspace_result.run_op.feeling_state_id == feeling_result.state.state_id
    assert workspace_result.candidate_set.source_feeling_state_id == feeling_result.state.state_id
    assert workspace_result.candidate_set.candidates[0].source_memory_candidate_id == "candidate:runtime:1"
    assert workspace_result.candidate_set.candidates[0].forced_consolidation is True
    assert workspace_result.working_state.source_candidate_set_id == workspace_result.candidate_set.set_id
    assert workspace_result.working_state.retained_candidate_ids == ("workspace-candidate:runtime:1",)
    assert workspace_result.publish_candidate_set_op.candidate_count == 1
    assert workspace_result.publish_candidate_set_op.forced_candidate_count == 1
    assert workspace_result.publish_working_state_op.state_id == workspace_result.working_state.state_id
    assert workspace_result.publish_working_state_op.retained_candidate_count == 1
    assert consciousness_result.commit_op.workspace_candidate_count == 1
    assert consciousness_result.commit_op.retained_candidate_count == 1
    assert consciousness_result.commit_op.material_count == 1
    assert consciousness_result.commit_op.forced_material_count == 1
    assert consciousness_result.material_set.source_workspace_candidate_set_id == workspace_result.candidate_set.set_id
    assert consciousness_result.material_set.source_working_state_id == workspace_result.working_state.state_id
    assert consciousness_result.material_set.materials[0].source_workspace_candidate_id == "workspace-candidate:runtime:1"
    assert consciousness_result.material_set.materials[0].source_memory_candidate_id == "candidate:runtime:1"
    assert consciousness_result.material_set.materials[0].source_memory_id == "memory:runtime:1"
    assert consciousness_result.material_set.materials[0].material_summary == "situational-summary: hello, novelty"
    assert consciousness_result.state.commit_status == "committed"
    assert consciousness_result.state.focal_content is not None
    assert consciousness_result.state.focal_content.source_workspace_candidate_id == "workspace-candidate:runtime:1"
    assert consciousness_result.state.focal_content.focal_summary == (
        "Current focal content from situational-summary: situational-summary: hello, novelty. "
        "Salient cues: hello, novelty"
    )
    assert consciousness_result.publish_state_op.state_id == consciousness_result.state.state_id
    assert consciousness_result.publish_state_op.commit_status == "committed"
    assert consciousness_result.publish_reportable_content_op is not None
    assert consciousness_result.publish_reportable_content_op.content_id == (
        "conscious-content:conscious-material:workspace-candidate:runtime:1"
    )
    assert thought_gating_result.signal_snapshot.source_conscious_state_id == consciousness_result.state.state_id
    assert directed_retrieval_result.request.source_gate_result_id == thought_gating_result.result.result_id
    assert directed_retrieval_result.bundle.short_term_context[0].summary == "current runtime stimulus context"
    assert len(prompt_result.requests) == 2
    assert len(prompt_result.contracts) == 2
    assert prompt_result.contracts[0].consumer_kind == "thought"
    assert prompt_result.contracts[1].consumer_kind == "outward_expression"
    assert tuple(layer.layer_name for layer in prompt_result.contracts[0].layers) == tuple(
        layer.layer_name for layer in prompt_result.contracts[1].layers
    )
    assert prompt_result.contracts[0].action_boundary.supports_internal_action is True
    assert prompt_result.contracts[1].action_boundary.supports_internal_action is False
    assert prompt_result.outward_expression_view is not None
    assert prompt_result.outward_expression_view.available_channels == ("cli",)
    assert prompt_result.outward_expression_view.available_ops == ("reply_message",)
    assert prompt_result.publish_outward_expression_view_op is not None
    assert prompt_result.publish_outward_expression_view_op.channel_count == 1
    assert prompt_result.outward_expression_request is not None
    assert prompt_result.outward_expression_request.source_prompt_view_id == prompt_result.outward_expression_view.view_id
    assert prompt_result.outward_expression_request.available_channels == ("cli",)
    assert prompt_result.outward_expression_request.available_ops == ("reply_message",)
    assert prompt_result.build_outward_expression_request_op is not None
    assert prompt_result.build_outward_expression_request_op.source_prompt_view_id == prompt_result.outward_expression_view.view_id
    assert outward_expression_result.request.request_id == prompt_result.outward_expression_request.request_id
    assert outward_expression_result.prepare_op.channel_count == 1
    assert outward_expression_result.draft.source_prompt_view_id == prompt_result.outward_expression_view.view_id
    assert outward_expression_result.draft.delivery_channels == ("cli",)
    assert outward_expression_result.draft.delivery_ops == ("reply_message",)
    assert "Final authorities remain: planner, channel, identity_governance." in outward_expression_result.draft.delivery_guidance
    assert outward_expression_result.publish_draft_op.draft_id == outward_expression_result.draft.draft_id
    assert (
        outward_expression_externalization_result.request.source_outward_expression_draft_id
        == outward_expression_result.draft.draft_id
    )
    assert outward_expression_externalization_result.request_op.channel_count == 1
    assert outward_expression_externalization_result.draft.candidate_channels == ("cli",)
    assert outward_expression_externalization_result.draft.candidate_ops == ("reply_message",)
    assert "[execution_boundary]" in outward_expression_externalization_result.draft.externalization_prompt
    assert (
        outward_expression_externalization_result.publish_draft_op.draft_id
        == outward_expression_externalization_result.draft.draft_id
    )
    assert internal_thought_result.request.source_gate_result_id == thought_gating_result.result.result_id
    assert internal_thought_result.request.source_retrieval_bundle_id == directed_retrieval_result.bundle.bundle_id
    assert internal_thought_result.request.prompt_contract_summary["consumer_kind"] == "thought"
    assert internal_thought_result.request.prompt_contract_summary["supports_external_action_proposal"] is True
    assert internal_thought_result.result.source_request_id == internal_thought_result.request.request_id
    assert internal_thought_result.result.execution_status == "completed"
    assert internal_thought_result.result.thought is not None
    assert internal_thought_result.publish_result_op.result_id == internal_thought_result.result.result_id
    assert internal_thought_result.result.action_proposal is not None
    assert internal_thought_result.result.action_proposal.outbound_text == internal_thought_result.result.thought.content
    assert internal_thought_result.result.self_revision_proposal is not None
    assert action_externalization_result.request.source_thought_cycle_result_id == internal_thought_result.result.result_id
    assert action_externalization_result.result.status == "normalized"
    assert action_externalization_result.result.normalized_proposal is not None
    assert action_externalization_result.result.normalized_proposal.origin_thought_id == internal_thought_result.result.thought.thought_id
    assert action_externalization_result.publish_externalization_op is not None
    assert action_externalization_result.publish_externalization_op.behavior_name == "reply_message"
    assert action_externalization_result.publish_rejection_op is None
    assert planner_bridge_result.request.source_externalization_result_id == action_externalization_result.result.result_id
    assert planner_bridge_result.result.status == "executed"
    assert planner_bridge_result.result.action_decision is not None
    assert planner_bridge_result.result.action_decision.selected_channel_id == "cli"
    assert planner_bridge_result.execution_feedback is not None
    assert planner_bridge_result.execution_feedback.success is True
    assert planner_bridge_result.publish_decision_op is not None
    assert planner_bridge_result.publish_feedback_op is not None
    assert planner_bridge_result.publish_rejection_op is None
    assert identity_governance_result.request.source_thought_cycle_result_id == internal_thought_result.result.result_id
    assert identity_governance_result.result.revision_decision.status == "accepted"
    assert identity_governance_result.result.applied_identity_state is not None
    assert identity_governance_result.result.applied_identity_state.identity_state_snapshot["current_revision"] == identity_governance_result.result.revision_decision.revision_id
    assert identity_governance_result.publish_pressure_op.pressure_level == "none"
    assert identity_governance_result.publish_revision_decision_op.status == "accepted"
    assert identity_governance_result.publish_applied_identity_state_op is not None
    assert len(experience_writeback_result.requests) == 2
    assert len(experience_writeback_result.results) == 2
    assert experience_writeback_result.results[0].status == "written"
    assert experience_writeback_result.results[0].continuity_packet.continuity_kind == "external_action"
    assert experience_writeback_result.results[1].status == "written_identity_change"
    assert experience_writeback_result.results[1].continuity_packet.continuity_kind == "identity_change"
    assert len(experience_writeback_result.publish_writeback_ops) == 2
    assert len(experience_writeback_result.publish_candidate_ops) == 6
    assert autonomy_result.request.request_id == "autonomy-request:runtime:1"
    assert autonomy_result.request.source_gate_result_id == thought_gating_result.result.result_id
    assert autonomy_result.evaluate_op.request_id == autonomy_result.request.request_id
    assert autonomy_result.result.drive_state.dominant_disposition == "externalize"
    assert autonomy_result.result.drive_state.activity_mode == "outward_proactive"
    assert autonomy_result.result.drive_state.proactive_action_requested is True
    assert autonomy_result.result.drive_state.deferred_active is False
    assert autonomy_result.publish_result_op.result_id == autonomy_result.result.result_id
    assert autonomy_result.publish_result_op.deferred_count == 0
    assert evaluation_result.request.request_id == "evaluation-request:runtime:1"
    assert evaluation_result.evidence_bundle.source_request_id == evaluation_result.request.request_id
    assert len(evaluation_result.evidence_bundle.autonomy_evidence) == 1
    assert len(evaluation_result.evidence_bundle.prompt_evidence) == 2
    assert len(evaluation_result.evidence_bundle.outward_expression_evidence) == 1
    assert len(evaluation_result.evidence_bundle.outward_expression_externalization_evidence) == 1
    assert evaluation_result.artifact.gap_summary["autonomy_continuity_gap"] == "no_gap"
    assert evaluation_result.artifact.dimension_scores["autonomy_fidelity"] == 1.0
    assert evaluation_result.artifact.gap_summary["outward_expression_artifact_gap"] == "no_gap"
    assert evaluation_result.artifact.dimension_scores["continuity_fidelity"] == 1.0
    # This chain assembles without timeline evidence (the FixedEvaluationRequestProvider
    # supplies none), so evaluation emits exactly the explicit missing-timeline warning and
    # reports the timeline as absent rather than inferring execution fidelity.
    assert evaluation_result.publish_artifact_op.warning_count == 1
    assert evaluation_result.artifact.fidelity_warnings[0].warning_id == "warning:missing-execution-timeline"
    assert (
        evaluation_result.artifact.long_range_diagnostics["execution_timeline_status"]
        == "absent_uninstrumented"
    )
    assert evaluation_result.artifact.gap_summary["consequence_path_outcome"] == "continuity_written"
    assert evaluation_result.artifact.dimension_scores["internal_to_visible_consequence"] == 1.0
    assert thought_gating_result.result.source_signal_snapshot_id == thought_gating_result.signal_snapshot.snapshot_id
    assert thought_gating_result.result.decision == "fire"
    assert thought_gating_result.publish_gate_result_op.result_id == thought_gating_result.result.result_id
    assert thought_gating_result.publish_continuation_op.level == thought_gating_result.continuation_state.level
    assert directed_retrieval_result.request.source_gate_result_id == thought_gating_result.result.result_id
    assert directed_retrieval_result.plan.source_request_id == directed_retrieval_result.request.request_id
    assert directed_retrieval_result.bundle.source_plan_id == directed_retrieval_result.plan.plan_id
    assert len(directed_retrieval_result.bundle.short_term_context) == 1
    assert len(directed_retrieval_result.bundle.mid_term_hits) == 1
    assert len(directed_retrieval_result.bundle.autobiographical_hits) == 1
    assert directed_retrieval_result.publish_bundle_op.bundle_id == directed_retrieval_result.bundle.bundle_id


def test_autonomy_runtime_stage_carries_deferred_continuity_across_ticks() -> None:
    upstream_tick = _build_runtime_chain().tick()
    stage = AutonomyRuntimeStage(
        autonomy_layer=AutonomyEngine(
            config=_build_autonomy_config(),
            autonomy_path=FirstVersionAutonomyPath(),
        ),
        request_provider=TickSequencedAutonomyRequestProvider(),
    )

    first_result = stage.run(RuntimeFrame(tick_id=1, stage_results=upstream_tick.stage_results))
    second_result = stage.run(RuntimeFrame(tick_id=2, stage_results=upstream_tick.stage_results))

    assert first_result.result.drive_state.dominant_disposition == "defer"
    assert first_result.result.drive_state.deferred_active is True
    assert len(first_result.result.deferred_records) == 1
    assert first_result.result.deferred_records[0].expires_after_ticks == 3
    assert second_result.request.prior_deferred_records == first_result.result.deferred_records
    assert second_result.result.drive_state.dominant_disposition == "defer"
    assert second_result.result.drive_state.activity_mode == "deferred_continuity"
    assert second_result.result.drive_state.deferred_active is True
    assert second_result.result.drive_state.pressure_components["prior_deferred_count"] == 1.0
    assert len(second_result.result.deferred_records) == 1
    assert second_result.result.deferred_records[0].carry_reason == (
        "carried_forward:blocked_outward_externalization"
    )
    assert second_result.result.deferred_records[0].expires_after_ticks == 2


def test_runtime_chain_fails_explicitly_when_upstream_sensory_stage_result_is_missing() -> None:
    appraisal = RapidSalienceAppraisalEngine(
        dimension_estimator=FixedDimensionEstimator(),
        aggregate_estimator=FixedAggregateEstimator(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(RapidSalienceAppraisalRuntimeStage(appraisal=appraisal))

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'sensory_ingress'",
    ):
        kernel.tick()


def test_runtime_chain_fails_explicitly_when_upstream_appraisal_stage_result_is_missing() -> None:
    neuromodulator = NeuromodulatorEngine(
        config=_build_neuromodulator_config(),
        update_path=FixedNeuromodulatorUpdatePath(),
        active_channel_reporter=FixedActiveChannelReporter(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(NeuromodulatorRuntimeStage(neuromodulator_system=neuromodulator))

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'rapid_salience_appraisal'",
    ):
        kernel.tick()


def test_runtime_chain_fails_explicitly_when_upstream_neuromodulator_stage_result_is_missing() -> None:
    feeling = InteroceptiveFeelingEngine(
        config=_build_feeling_config(),
        construction_path=FixedFeelingConstructionPath(),
        dominant_dimension_reporter=FixedDominantDimensionReporter(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(InteroceptiveFeelingRuntimeStage(feeling_layer=feeling))

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'neuromodulator_system'",
    ):
        kernel.tick()


def test_runtime_chain_fails_explicitly_when_upstream_feeling_stage_result_is_missing() -> None:
    memory = MemoryAffectReplayEngine(
        config=_build_memory_config(),
        formation_path=FixedMemoryFormationPath(),
        replay_selector=FixedReplayCandidateSelector(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(
        MemoryAffectReplayRuntimeStage(
            memory_layer=memory,
            binding_context_provider=FixedBindingContextProvider(),
            mismatch_evidence_provider=FixedMismatchEvidenceProvider(),
        )
    )

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'interoceptive_feeling_layer'",
    ):
        kernel.tick()


def test_runtime_chain_fails_explicitly_when_upstream_memory_stage_result_is_missing() -> None:
    workspace = WorkspaceCompetitionEngine(
        config=_build_workspace_config(),
        competition_path=FixedWorkspaceCompetitionPath(),
        retention_path=FixedWorkingStateRetentionPath(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(WorkspaceCompetitionRuntimeStage(workspace_layer=workspace))

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'memory_affect_and_replay'",
    ):
        kernel.tick()


def test_runtime_chain_fails_explicitly_when_upstream_workspace_stage_result_is_missing() -> None:
    consciousness = ConsciousnessEngine(
        config=_build_consciousness_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    kernel = RuntimeKernel(dependency_specs=[], dependency_provider=NullDependencyProvider())
    kernel.register_stage(ReportableConsciousContentRuntimeStage(consciousness_layer=consciousness))

    with pytest.raises(
        RuntimeStageExecutionError,
        match="requires upstream result from 'workspace_competition_and_working_state'",
    ):
        kernel.tick()