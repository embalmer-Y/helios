"""Runtime-owned stage adapters for explicit owner-to-owner execution chains."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Protocol, TypeVar, runtime_checkable

from helios_v2.consciousness import (
    CommitConsciousContentOp,
    ConsciousContentAPI,
    ConsciousContentMaterial,
    ConsciousContentMaterialSet,
    ConsciousState,
    PublishConsciousStateOp,
    PublishReportableConsciousContentOp,
)
from helios_v2.action_externalization import (
    ActionExternalizationAPI,
    PublishThoughtExternalizationOp,
    PublishThoughtExternalizationRejectionOp,
    RequestThoughtExternalizationOp,
    ThoughtExternalizationRequest,
    ThoughtExternalizationResult,
)
from helios_v2.autonomy import (
    AutonomyAPI,
    AutonomyResult,
    DeferredContinuityRecord,
    EvaluateProactiveDriveOp,
    ProactiveDriveRequest,
    PublishAutonomyResultOp,
)
from helios_v2.planner_bridge import (
    EvaluatePlannerBridgeOp,
    NormalizedExecutionFeedback,
    PlannerBridgeAPI,
    PlannerBridgeRequest,
    PlannerBridgeResult,
    PublishActionDecisionOp,
    PublishExecutionFeedbackOp,
    PublishPlannerBridgeRejectionOp,
)
from helios_v2.identity_governance import (
    EvaluateIdentityGovernanceOp,
    IdentityGovernanceAPI,
    IdentityGovernanceRequest,
    IdentityGovernanceResult,
    PublishAppliedIdentityStateOp,
    PublishGovernancePressureOp,
    PublishRevisionDecisionOp,
)
from helios_v2.experience_writeback import (
    ExperienceWritebackAPI,
    ExperienceWritebackRequest,
    ExperienceWritebackResult,
    PublishConsolidationCandidateOp,
    PublishExperienceWritebackOp,
)
from helios_v2.evaluation import (
    EvaluateEvidenceBundleOp,
    EvaluationAPI,
    EvaluationArtifact,
    EvaluationEvidenceBundle,
    EvaluationRequest,
    PublishEvaluationArtifactOp,
)
from helios_v2.prompt_contract import (
    BuildEmbodiedPromptOp,
    EmbodiedPromptAPI,
    EmbodiedPromptContract,
    EmbodiedPromptRequest,
    OutwardExpressionPromptView,
    PublishEmbodiedPromptContractOp,
    PublishOutwardExpressionPromptViewOp,
)
from helios_v2.outward_expression import (
    BuildOutwardExpressionRequestOp,
    OutwardExpressionAPI,
    OutwardExpressionDraft,
    OutwardExpressionRequest,
    PrepareOutwardExpressionOp,
    PublishOutwardExpressionDraftOp,
)
from helios_v2.outward_expression_externalization import (
    OutwardExpressionExternalizationAPI,
    OutwardExpressionExternalizationDraft,
    OutwardExpressionExternalizationRequest,
    PublishOutwardExpressionExternalizationDraftOp,
    RequestOutwardExpressionExternalizationOp,
)
from helios_v2.directed_retrieval import (
    DirectedRetrievalAPI,
    PlanDirectedRetrievalOp,
    PublishThoughtWindowBundleOp,
    RetrievalQueryPlan,
    RetrievalRequest,
    ThoughtWindowBundle,
)
from helios_v2.internal_thought import (
    InternalThoughtAPI,
    InternalThoughtRequest,
    InternalThoughtTrace,
    PublishThoughtCycleResultOp,
    RunInternalThoughtOp,
    ThoughtCycleResult,
)
from helios_v2.appraisal import (
    AssessStimulusBatchOp,
    PublishRapidAppraisalBatchOp,
    RapidAppraisalBatch,
    RapidSalienceAppraisalAPI,
)
from helios_v2.feeling import (
    InteroceptiveFeelingAPI,
    InteroceptiveFeelingState,
    PublishInteroceptiveFeelingStateOp,
    UpdateInteroceptiveFeelingOp,
    validate_internal_body_signal,
)
from helios_v2.memory import (
    MemoryAffectReplayAPI,
    MemoryBindingContext,
    MemoryFormationState,
    PredictionMismatchEvidence,
    PublishMemoryFormationStateOp,
    PublishReplayCandidatesOp,
    RecordMemoryOp,
)
from helios_v2.neuromodulation import (
    NeuromodulatorState,
    NeuromodulatorSystemAPI,
    PublishNeuromodulatorStateOp,
    UpdateNeuromodulatorsOp,
)
from helios_v2.sensory import PublishStimulusBatchOp, SensoryIngressAPI, Stimulus, StimulusBatch
from helios_v2.thought_gating import (
    ContinuationPressureState,
    EvaluateThoughtGateOp,
    PublishContinuationPressureOp,
    PublishThoughtGateResultOp,
    ThoughtGateResult,
    ThoughtGateSignalSnapshot,
    ThoughtGatingAPI,
)
from helios_v2.workspace import (
    PublishWorkingStateOp,
    PublishWorkspaceCandidateSetOp,
    RunWorkspaceCompetitionOp,
    WorkingStateSnapshot,
    WorkspaceCandidateSet,
    WorkspaceCompetitionAPI,
)

from .contracts import RuntimeFrame, RuntimeStage

TStageResult = TypeVar("TStageResult")


class RuntimeStageExecutionError(RuntimeError):
    """Hard-stop error raised when a runtime stage cannot satisfy its declared upstream contract."""


@dataclass(frozen=True)
class SensoryIngressStageResult:
    """Structured runtime-visible result emitted by the sensory ingress stage adapter."""

    batch: StimulusBatch
    publish_op: PublishStimulusBatchOp


@dataclass(frozen=True)
class RapidSalienceAppraisalStageResult:
    """Structured runtime-visible result emitted by the rapid appraisal stage adapter."""

    assess_op: AssessStimulusBatchOp
    batch: RapidAppraisalBatch
    publish_op: PublishRapidAppraisalBatchOp


@dataclass(frozen=True)
class NeuromodulatorStageResult:
    """Structured runtime-visible result emitted by the neuromodulator stage adapter."""

    update_op: UpdateNeuromodulatorsOp
    state: NeuromodulatorState
    publish_op: PublishNeuromodulatorStateOp


@dataclass(frozen=True)
class InteroceptiveFeelingStageResult:
    """Structured runtime-visible result emitted by the interoceptive feeling stage adapter."""

    update_op: UpdateInteroceptiveFeelingOp
    state: InteroceptiveFeelingState
    publish_op: PublishInteroceptiveFeelingStateOp


@dataclass(frozen=True)
class MemoryAffectReplayStageResult:
    """Structured runtime-visible result emitted by the memory affect and replay stage adapter."""

    record_op: RecordMemoryOp
    state: MemoryFormationState
    publish_replay_candidates_op: PublishReplayCandidatesOp
    publish_state_op: PublishMemoryFormationStateOp


@dataclass(frozen=True)
class WorkspaceCompetitionStageResult:
    """Structured runtime-visible result emitted by the workspace competition stage adapter."""

    run_op: RunWorkspaceCompetitionOp
    candidate_set: WorkspaceCandidateSet
    working_state: WorkingStateSnapshot
    publish_candidate_set_op: PublishWorkspaceCandidateSetOp
    publish_working_state_op: PublishWorkingStateOp


@dataclass(frozen=True)
class ConsciousContentStageResult:
    """Structured runtime-visible result emitted by the reportable conscious-content stage adapter."""

    commit_op: CommitConsciousContentOp
    material_set: ConsciousContentMaterialSet
    state: ConsciousState
    publish_state_op: PublishConsciousStateOp
    publish_reportable_content_op: PublishReportableConsciousContentOp | None


@dataclass(frozen=True)
class ThoughtGatingStageResult:
    """Structured runtime-visible result emitted by the thought-gating stage adapter."""

    evaluate_op: EvaluateThoughtGateOp
    signal_snapshot: ThoughtGateSignalSnapshot
    result: ThoughtGateResult
    publish_gate_result_op: PublishThoughtGateResultOp
    continuation_state: ContinuationPressureState
    publish_continuation_op: PublishContinuationPressureOp


@dataclass(frozen=True)
class DirectedRetrievalStageResult:
    """Structured runtime-visible result emitted by the directed-retrieval stage adapter."""

    plan_op: PlanDirectedRetrievalOp
    request: RetrievalRequest
    plan: RetrievalQueryPlan
    bundle: ThoughtWindowBundle
    publish_bundle_op: PublishThoughtWindowBundleOp


@dataclass(frozen=True)
class EmbodiedPromptStageResult:
    """Structured runtime-visible result emitted by the embodied-prompt stage adapter."""

    requests: tuple[EmbodiedPromptRequest, ...]
    build_ops: tuple[BuildEmbodiedPromptOp, ...]
    contracts: tuple[EmbodiedPromptContract, ...]
    publish_ops: tuple[PublishEmbodiedPromptContractOp, ...]
    outward_expression_view: OutwardExpressionPromptView | None
    publish_outward_expression_view_op: PublishOutwardExpressionPromptViewOp | None
    outward_expression_request: OutwardExpressionRequest | None
    build_outward_expression_request_op: BuildOutwardExpressionRequestOp | None


@dataclass(frozen=True)
class OutwardExpressionStageResult:
    """Structured runtime-visible result emitted by the outward-expression owner stage adapter."""

    request: OutwardExpressionRequest
    prepare_op: PrepareOutwardExpressionOp
    draft: OutwardExpressionDraft
    publish_draft_op: PublishOutwardExpressionDraftOp


@dataclass(frozen=True)
class OutwardExpressionExternalizationStageResult:
    """Structured runtime-visible result emitted by the outward-expression externalization stage adapter."""

    request_op: RequestOutwardExpressionExternalizationOp
    request: OutwardExpressionExternalizationRequest
    draft: OutwardExpressionExternalizationDraft
    publish_draft_op: PublishOutwardExpressionExternalizationDraftOp


@dataclass(frozen=True)
class InternalThoughtStageResult:
    """Structured runtime-visible result emitted by the internal-thought stage adapter."""

    run_op: RunInternalThoughtOp
    request: InternalThoughtRequest
    result: ThoughtCycleResult
    trace: InternalThoughtTrace
    publish_result_op: PublishThoughtCycleResultOp


@dataclass(frozen=True)
class ActionExternalizationStageResult:
    """Structured runtime-visible result emitted by the action-externalization stage adapter."""

    request_op: RequestThoughtExternalizationOp
    request: ThoughtExternalizationRequest
    result: ThoughtExternalizationResult
    publish_externalization_op: PublishThoughtExternalizationOp | None
    publish_rejection_op: PublishThoughtExternalizationRejectionOp | None


@dataclass(frozen=True)
class PlannerBridgeStageResult:
    """Structured runtime-visible result emitted by the planner-bridge stage adapter."""

    evaluate_op: EvaluatePlannerBridgeOp
    request: PlannerBridgeRequest
    result: PlannerBridgeResult
    execution_feedback: NormalizedExecutionFeedback | None
    publish_decision_op: PublishActionDecisionOp | None
    publish_rejection_op: PublishPlannerBridgeRejectionOp | None
    publish_feedback_op: PublishExecutionFeedbackOp | None


@dataclass(frozen=True)
class IdentityGovernanceStageResult:
    """Structured runtime-visible result emitted by the identity-governance stage adapter."""

    evaluate_op: EvaluateIdentityGovernanceOp
    request: IdentityGovernanceRequest
    result: IdentityGovernanceResult
    publish_pressure_op: PublishGovernancePressureOp
    publish_revision_decision_op: PublishRevisionDecisionOp
    publish_applied_identity_state_op: PublishAppliedIdentityStateOp | None


@dataclass(frozen=True)
class ExperienceWritebackStageResult:
    """Structured runtime-visible result emitted by the experience-writeback stage adapter."""

    requests: tuple[ExperienceWritebackRequest, ...]
    results: tuple[ExperienceWritebackResult, ...]
    publish_writeback_ops: tuple[PublishExperienceWritebackOp, ...]
    publish_candidate_ops: tuple[PublishConsolidationCandidateOp, ...]


@dataclass(frozen=True)
class AutonomyStageResult:
    """Structured runtime-visible result emitted by the autonomy stage adapter."""

    request: ProactiveDriveRequest
    evaluate_op: EvaluateProactiveDriveOp
    result: AutonomyResult
    publish_result_op: PublishAutonomyResultOp


@dataclass(frozen=True)
class EvaluationStageResult:
    """Structured runtime-visible result emitted by the evaluation stage adapter."""

    request: EvaluationRequest
    evaluate_op: EvaluateEvidenceBundleOp
    evidence_bundle: EvaluationEvidenceBundle
    artifact: EvaluationArtifact
    publish_artifact_op: PublishEvaluationArtifactOp


@runtime_checkable
class MemoryBindingContextProvider(Protocol):
    """Runtime-owned provider for explicit binding-context bridging into the memory stage."""

    def build_binding_context(
        self,
        frame: RuntimeFrame,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> MemoryBindingContext | None:
        """Return the explicit binding context to pass into the memory owner for one runtime tick."""

        ...


@runtime_checkable
class PredictionMismatchEvidenceProvider(Protocol):
    """Runtime-owned provider for explicit mismatch-evidence bridging into the memory stage."""

    def build_mismatch_evidence(
        self,
        frame: RuntimeFrame,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> PredictionMismatchEvidence | None:
        """Return the explicit mismatch evidence to pass into the memory owner for one runtime tick."""

        ...


@runtime_checkable
class ConsciousContentMaterialProvider(Protocol):
    """Runtime-owned provider for explicit current-cycle material bridging into the consciousness stage."""

    def build_material_set(
        self,
        frame: RuntimeFrame,
        workspace_result: WorkspaceCompetitionStageResult,
        memory_result: MemoryAffectReplayStageResult,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> ConsciousContentMaterialSet:
        """Return the explicit conscious-content material set for one runtime tick."""

        ...


@runtime_checkable
class ThoughtGateSignalProvider(Protocol):
    """Runtime-owned provider for explicit normalized gate signals bridging into the thought-gating stage."""

    def build_signal_snapshot(
        self,
        frame: RuntimeFrame,
        conscious_result: ConsciousContentStageResult,
    ) -> ThoughtGateSignalSnapshot:
        """Return the explicit thought-gate signal snapshot for one runtime tick."""

        ...


@runtime_checkable
class DirectedRetrievalRequestProvider(Protocol):
    """Runtime-owned provider for explicit retrieval demand bridging into the directed-retrieval stage."""

    def build_request(
        self,
        frame: RuntimeFrame,
        thought_gating_result: ThoughtGatingStageResult,
    ) -> RetrievalRequest:
        """Return the explicit directed-retrieval request for one runtime tick."""

        ...


@runtime_checkable
class EmbodiedPromptRequestProvider(Protocol):
    """Runtime-owned provider for explicit prompt-assembly bridging into the prompt stage."""

    def build_requests(
        self,
        frame: RuntimeFrame,
        conscious_result: ConsciousContentStageResult,
        thought_gating_result: ThoughtGatingStageResult,
        directed_retrieval_result: DirectedRetrievalStageResult,
    ) -> tuple[EmbodiedPromptRequest, ...]:
        """Return one or more explicit embodied-prompt requests for one runtime tick."""

        ...


@runtime_checkable
class InternalThoughtRequestProvider(Protocol):
    """Runtime-owned provider for explicit fired-path thought input bridging into the internal-thought stage."""

    def build_request(
        self,
        frame: RuntimeFrame,
        thought_gating_result: ThoughtGatingStageResult,
        directed_retrieval_result: DirectedRetrievalStageResult,
        prompt_result: EmbodiedPromptStageResult,
    ) -> InternalThoughtRequest:
        """Return the explicit internal-thought request for one runtime tick."""

        ...


@runtime_checkable
class ThoughtExternalizationRequestProvider(Protocol):
    """Runtime-owned provider for explicit externalization demand bridging into the action-externalization stage."""

    def build_request(
        self,
        frame: RuntimeFrame,
        internal_thought_result: InternalThoughtStageResult,
    ) -> ThoughtExternalizationRequest:
        """Return the explicit thought-externalization request for one runtime tick."""

        ...


@runtime_checkable
class PlannerBridgeRequestProvider(Protocol):
    """Runtime-owned provider for explicit planner-bridge input bridging into the planner stage."""

    def build_request(
        self,
        frame: RuntimeFrame,
        action_externalization_result: ActionExternalizationStageResult,
    ) -> PlannerBridgeRequest:
        """Return the explicit planner-bridge request for one runtime tick."""

        ...


@runtime_checkable
class IdentityGovernanceRequestProvider(Protocol):
    """Runtime-owned provider for explicit identity-governance input bridging into the governance stage."""

    def build_request(
        self,
        frame: RuntimeFrame,
        internal_thought_result: InternalThoughtStageResult,
    ) -> IdentityGovernanceRequest:
        """Return the explicit identity-governance request for one runtime tick."""

        ...


@runtime_checkable
class ExperienceWritebackRequestProvider(Protocol):
    """Runtime-owned provider for explicit continuity writeback bridging into the writeback stage."""

    def build_requests(
        self,
        frame: RuntimeFrame,
        planner_bridge_result: PlannerBridgeStageResult,
        identity_governance_result: IdentityGovernanceStageResult,
    ) -> tuple[ExperienceWritebackRequest, ...]:
        """Return zero or more explicit writeback requests for one runtime tick."""

        ...


@runtime_checkable
class AutonomyRequestProvider(Protocol):
    """Runtime-owned provider for explicit bridging into the autonomy owner."""

    def build_request(
        self,
        frame: RuntimeFrame,
        thought_gating_result: ThoughtGatingStageResult,
        directed_retrieval_result: DirectedRetrievalStageResult,
        internal_thought_result: InternalThoughtStageResult,
        planner_bridge_result: PlannerBridgeStageResult,
        identity_governance_result: IdentityGovernanceStageResult,
        experience_writeback_result: ExperienceWritebackStageResult,
        prompt_result: EmbodiedPromptStageResult,
        outward_expression_result: OutwardExpressionStageResult,
        outward_expression_externalization_result: OutwardExpressionExternalizationStageResult,
    ) -> ProactiveDriveRequest:
        """Return the explicit request to pass into the autonomy owner."""

        ...


@runtime_checkable
class EvaluationRequestProvider(Protocol):
    """Runtime-owned provider for explicit bridging into the evaluation owner."""

    def build_request(
        self,
        frame: RuntimeFrame,
        internal_thought_result: InternalThoughtStageResult,
        action_externalization_result: ActionExternalizationStageResult,
        planner_bridge_result: PlannerBridgeStageResult,
        identity_governance_result: IdentityGovernanceStageResult,
        experience_writeback_result: ExperienceWritebackStageResult,
        autonomy_result: AutonomyStageResult,
        prompt_result: EmbodiedPromptStageResult,
        outward_expression_result: OutwardExpressionStageResult,
        outward_expression_externalization_result: OutwardExpressionExternalizationStageResult,
    ) -> EvaluationRequest:
        """Return the explicit request to pass into the evaluation owner."""

        ...

    def build_evidence_bundle(
        self,
        frame: RuntimeFrame,
        request: EvaluationRequest,
        internal_thought_result: InternalThoughtStageResult,
        action_externalization_result: ActionExternalizationStageResult,
        planner_bridge_result: PlannerBridgeStageResult,
        identity_governance_result: IdentityGovernanceStageResult,
        experience_writeback_result: ExperienceWritebackStageResult,
        autonomy_result: AutonomyStageResult,
        prompt_result: EmbodiedPromptStageResult,
        outward_expression_result: OutwardExpressionStageResult,
        outward_expression_externalization_result: OutwardExpressionExternalizationStageResult,
    ) -> EvaluationEvidenceBundle:
        """Return the explicit evidence bundle to pass into the evaluation owner."""

        ...


def _build_material_summary(memory_content_kind: str, salient_tokens: tuple[str, ...]) -> str:
    if salient_tokens:
        return f"{memory_content_kind}: {', '.join(salient_tokens)}"
    return f"{memory_content_kind}: current-cycle memory context"


@dataclass
class WorkspaceConsciousContentMaterialBridge(ConsciousContentMaterialProvider):
    """Runtime-owned bridge that assembles explicit current-cycle conscious material from workspace and memory outputs."""

    material_id_prefix: str = "conscious-material"
    material_set_id_prefix: str = "conscious-material-set"

    def build_material_set(
        self,
        frame: RuntimeFrame,
        workspace_result: WorkspaceCompetitionStageResult,
        memory_result: MemoryAffectReplayStageResult,
        feeling_result: InteroceptiveFeelingStageResult,
    ) -> ConsciousContentMaterialSet:
        candidate_set = workspace_result.candidate_set
        working_state = workspace_result.working_state
        if candidate_set.source_feeling_state_id != feeling_result.state.state_id:
            raise RuntimeStageExecutionError(
                "Workspace candidate set must preserve the upstream feeling-state provenance for consciousness bridging"
            )
        replay_candidate_map = {
            candidate.candidate_id: candidate for candidate in memory_result.state.replay_candidates
        }
        memory_item_map = {item.memory_id: item for item in memory_result.state.memory_items}
        materials: list[ConsciousContentMaterial] = []
        for workspace_candidate in candidate_set.candidates:
            replay_candidate = replay_candidate_map.get(workspace_candidate.source_memory_candidate_id)
            if replay_candidate is None:
                raise RuntimeStageExecutionError(
                    "Runtime consciousness bridge requires every workspace candidate to map to a current-cycle replay candidate"
                )
            memory_item = memory_item_map.get(replay_candidate.memory_id)
            if memory_item is None:
                raise RuntimeStageExecutionError(
                    "Runtime consciousness bridge requires every replay candidate to map to a published memory item"
                )
            if replay_candidate.source_feeling_state_id != feeling_result.state.state_id:
                raise RuntimeStageExecutionError(
                    "Runtime consciousness bridge requires replay candidates to preserve current-cycle feeling provenance"
                )
            if memory_item.source_feeling_state_id != feeling_result.state.state_id:
                raise RuntimeStageExecutionError(
                    "Runtime consciousness bridge requires memory items to preserve current-cycle feeling provenance"
                )
            materials.append(
                ConsciousContentMaterial(
                    material_id=f"{self.material_id_prefix}:{workspace_candidate.candidate_id}",
                    source_workspace_candidate_id=workspace_candidate.candidate_id,
                    source_memory_candidate_id=workspace_candidate.source_memory_candidate_id,
                    source_memory_id=memory_item.memory_id,
                    source_feeling_state_id=workspace_candidate.source_feeling_state_id,
                    content_kind=memory_item.content.content_kind,
                    material_summary=_build_material_summary(
                        memory_item.content.content_kind,
                        memory_item.content.salient_tokens,
                    ),
                    summary_ref=memory_item.content.summary_ref,
                    context_ref=memory_item.content.context_ref,
                    salient_tokens=memory_item.content.salient_tokens,
                    affect_tag=memory_item.affect_tag,
                    forced_consolidation=workspace_candidate.forced_consolidation,
                    workspace_score_hint=workspace_candidate.workspace_score_hint,
                    priority_hint=workspace_candidate.priority_hint,
                )
            )
        return ConsciousContentMaterialSet(
            set_id=f"{self.material_set_id_prefix}:{candidate_set.set_id}",
            source_workspace_candidate_set_id=candidate_set.set_id,
            source_working_state_id=working_state.state_id,
            materials=tuple(materials),
            tick_id=frame.tick_id,
        )


def _require_stage_result(frame: RuntimeFrame, stage_name: str, expected_type: type[TStageResult]) -> TStageResult:
    stage_results = frame.stage_results or {}
    stage_result = stage_results.get(stage_name)
    if stage_result is None:
        raise RuntimeStageExecutionError(
            f"Runtime stage requires upstream result from '{stage_name}' before execution"
        )
    if not isinstance(stage_result, expected_type):
        raise RuntimeStageExecutionError(
            f"Runtime stage expected upstream result '{stage_name}' to be {expected_type.__name__}"
        )
    return stage_result


@dataclass
class SensoryIngressRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes the sensory ingress owner within the kernel lifecycle."""

    ingress: SensoryIngressAPI

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for sensory ingress execution."""

        return "sensory_ingress"

    def run(self, frame: RuntimeFrame) -> SensoryIngressStageResult:
        """Execute the sensory ingress owner and expose a structured runtime result."""

        del frame
        batch = self.ingress.collect_stimuli()
        publish_op = self.ingress.build_publish_batch_op(batch)
        return SensoryIngressStageResult(batch=batch, publish_op=publish_op)


@dataclass
class RapidSalienceAppraisalRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes rapid appraisal from the upstream sensory stage result."""

    appraisal: RapidSalienceAppraisalAPI
    upstream_stage_name: str = "sensory_ingress"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for rapid appraisal execution."""

        return "rapid_salience_appraisal"

    def run(self, frame: RuntimeFrame) -> RapidSalienceAppraisalStageResult:
        """Execute rapid appraisal against the declared upstream sensory stage result."""

        sensory_result = _require_stage_result(frame, self.upstream_stage_name, SensoryIngressStageResult)
        assess_op = self.appraisal.build_assess_batch_op(sensory_result.batch)
        batch = self.appraisal.assess_batch(sensory_result.batch)
        publish_op = self.appraisal.build_publish_batch_op(batch)
        return RapidSalienceAppraisalStageResult(
            assess_op=assess_op,
            batch=batch,
            publish_op=publish_op,
        )


@dataclass
class NeuromodulatorRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes neuromodulator update from the upstream appraisal stage result."""

    neuromodulator_system: NeuromodulatorSystemAPI
    upstream_stage_name: str = "rapid_salience_appraisal"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for neuromodulator execution."""

        return "neuromodulator_system"

    def run(self, frame: RuntimeFrame) -> NeuromodulatorStageResult:
        """Execute neuromodulator update against the declared upstream appraisal stage result."""

        appraisal_result = _require_stage_result(frame, self.upstream_stage_name, RapidSalienceAppraisalStageResult)
        update_op = self.neuromodulator_system.build_update_op(appraisal_result.batch)
        state = self.neuromodulator_system.update_state(appraisal_result.batch, tick_id=frame.tick_id)
        publish_op = self.neuromodulator_system.build_publish_state_op(state)
        return NeuromodulatorStageResult(
            update_op=update_op,
            state=state,
            publish_op=publish_op,
        )


@dataclass
class InteroceptiveFeelingRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes feeling update from upstream neuromodulator state."""

    feeling_layer: InteroceptiveFeelingAPI
    upstream_stage_name: str = "neuromodulator_system"
    internal_signal_stage_name: str | None = "sensory_ingress"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for interoceptive feeling execution."""

        return "interoceptive_feeling_layer"

    def run(self, frame: RuntimeFrame) -> InteroceptiveFeelingStageResult:
        """Execute feeling update against the declared upstream neuromodulator stage result."""

        neuromodulator_result = _require_stage_result(frame, self.upstream_stage_name, NeuromodulatorStageResult)
        internal_signals: tuple[Stimulus, ...] = ()
        stage_results = frame.stage_results or {}
        if self.internal_signal_stage_name and self.internal_signal_stage_name in stage_results:
            sensory_result = _require_stage_result(frame, self.internal_signal_stage_name, SensoryIngressStageResult)
            internal_signal_list: list[Stimulus] = []
            for signal in sensory_result.batch.stimuli:
                if signal.modality not in {"body", "interoceptive"}:
                    continue
                validate_internal_body_signal(signal)
                internal_signal_list.append(signal)
            internal_signals = tuple(internal_signal_list)
        update_op = self.feeling_layer.build_update_op(neuromodulator_result.state, internal_signals)
        state = self.feeling_layer.update_state(
            neuromodulator_result.state,
            internal_signals,
            tick_id=frame.tick_id,
        )
        publish_op = self.feeling_layer.build_publish_state_op(state)
        return InteroceptiveFeelingStageResult(
            update_op=update_op,
            state=state,
            publish_op=publish_op,
        )


@dataclass
class MemoryAffectReplayRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes memory affect/replay from upstream feeling state."""

    memory_layer: MemoryAffectReplayAPI
    binding_context_provider: MemoryBindingContextProvider | None = None
    mismatch_evidence_provider: PredictionMismatchEvidenceProvider | None = None
    upstream_stage_name: str = "interoceptive_feeling_layer"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for memory affect and replay execution."""

        return "memory_affect_and_replay"

    def run(self, frame: RuntimeFrame) -> MemoryAffectReplayStageResult:
        """Execute memory affect/replay against the declared upstream feeling stage result."""

        feeling_result = _require_stage_result(frame, self.upstream_stage_name, InteroceptiveFeelingStageResult)
        binding_context = None
        if self.binding_context_provider is not None:
            binding_context = self.binding_context_provider.build_binding_context(frame, feeling_result)
        mismatch_evidence = None
        if self.mismatch_evidence_provider is not None:
            mismatch_evidence = self.mismatch_evidence_provider.build_mismatch_evidence(frame, feeling_result)
        record_op = self.memory_layer.build_record_op(
            feeling_result.state,
            binding_context,
            mismatch_evidence,
        )
        state = self.memory_layer.record_state(
            feeling_result.state,
            binding_context,
            mismatch_evidence,
            tick_id=frame.tick_id,
        )
        publish_replay_candidates_op = self.memory_layer.build_publish_replay_candidates_op(state)
        publish_state_op = self.memory_layer.build_publish_state_op(state)
        return MemoryAffectReplayStageResult(
            record_op=record_op,
            state=state,
            publish_replay_candidates_op=publish_replay_candidates_op,
            publish_state_op=publish_state_op,
        )


@dataclass
class WorkspaceCompetitionRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes workspace competition from upstream memory and feeling state."""

    workspace_layer: WorkspaceCompetitionAPI
    memory_stage_name: str = "memory_affect_and_replay"
    feeling_stage_name: str = "interoceptive_feeling_layer"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for workspace competition execution."""

        return "workspace_competition_and_working_state"

    def run(self, frame: RuntimeFrame) -> WorkspaceCompetitionStageResult:
        """Execute workspace competition against declared upstream memory and feeling stage results."""

        memory_result = _require_stage_result(frame, self.memory_stage_name, MemoryAffectReplayStageResult)
        feeling_result = _require_stage_result(frame, self.feeling_stage_name, InteroceptiveFeelingStageResult)
        run_op = self.workspace_layer.build_run_competition_op(
            memory_result.state.replay_candidates,
            feeling_result.state,
        )
        candidate_set, working_state = self.workspace_layer.compete(
            memory_result.state.replay_candidates,
            feeling_result.state,
            tick_id=frame.tick_id,
        )
        publish_candidate_set_op = self.workspace_layer.build_publish_candidate_set_op(candidate_set)
        publish_working_state_op = self.workspace_layer.build_publish_working_state_op(working_state)
        return WorkspaceCompetitionStageResult(
            run_op=run_op,
            candidate_set=candidate_set,
            working_state=working_state,
            publish_candidate_set_op=publish_candidate_set_op,
            publish_working_state_op=publish_working_state_op,
        )


@dataclass
class ReportableConsciousContentRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes reportable conscious-content commitment from upstream workspace outputs."""

    consciousness_layer: ConsciousContentAPI
    material_provider: ConsciousContentMaterialProvider = field(
        default_factory=WorkspaceConsciousContentMaterialBridge
    )
    workspace_stage_name: str = "workspace_competition_and_working_state"
    memory_stage_name: str = "memory_affect_and_replay"
    feeling_stage_name: str = "interoceptive_feeling_layer"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for reportable conscious-content execution."""

        return "reportable_conscious_content"

    def run(self, frame: RuntimeFrame) -> ConsciousContentStageResult:
        """Execute reportable conscious-content commitment against declared upstream stage results."""

        workspace_result = _require_stage_result(
            frame,
            self.workspace_stage_name,
            WorkspaceCompetitionStageResult,
        )
        memory_result = _require_stage_result(frame, self.memory_stage_name, MemoryAffectReplayStageResult)
        feeling_result = _require_stage_result(frame, self.feeling_stage_name, InteroceptiveFeelingStageResult)
        material_set = self.material_provider.build_material_set(
            frame,
            workspace_result,
            memory_result,
            feeling_result,
        )
        commit_op = self.consciousness_layer.build_commit_op(
            workspace_result.candidate_set,
            workspace_result.working_state,
            material_set,
        )
        state = self.consciousness_layer.commit_content(
            workspace_result.candidate_set,
            workspace_result.working_state,
            material_set,
            tick_id=frame.tick_id,
        )
        publish_state_op = self.consciousness_layer.build_publish_state_op(state)
        publish_reportable_content_op = None
        if state.commit_status == "committed":
            publish_reportable_content_op = self.consciousness_layer.build_publish_reportable_content_op(state)
        return ConsciousContentStageResult(
            commit_op=commit_op,
            material_set=material_set,
            state=state,
            publish_state_op=publish_state_op,
            publish_reportable_content_op=publish_reportable_content_op,
        )


@dataclass
class ThoughtGatingRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes thought gating from the upstream conscious-content stage result."""

    thought_gating_layer: ThoughtGatingAPI
    signal_provider: ThoughtGateSignalProvider
    upstream_stage_name: str = "reportable_conscious_content"
    _prior_continuation_state: ContinuationPressureState = field(
        default_factory=ContinuationPressureState.inactive,
        init=False,
        repr=False,
    )

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for thought-gating execution."""

        return "thought_gating_and_continuation_pressure"

    def run(self, frame: RuntimeFrame) -> ThoughtGatingStageResult:
        """Execute thought gating against the declared upstream conscious stage result."""

        conscious_result = _require_stage_result(frame, self.upstream_stage_name, ConsciousContentStageResult)
        signal_snapshot = self.signal_provider.build_signal_snapshot(frame, conscious_result)
        if signal_snapshot.source_conscious_state_id != conscious_result.state.state_id:
            raise RuntimeStageExecutionError(
                "Thought-gate signal snapshots must preserve the upstream conscious-state provenance"
            )
        evaluate_op = self.thought_gating_layer.build_evaluate_op(
            conscious_result.state,
            signal_snapshot,
            self._prior_continuation_state,
        )
        result, continuation_state = self.thought_gating_layer.evaluate_gate(
            conscious_result.state,
            signal_snapshot,
            self._prior_continuation_state,
            tick_id=frame.tick_id,
        )
        publish_gate_result_op = self.thought_gating_layer.build_publish_gate_result_op(result)
        publish_continuation_op = self.thought_gating_layer.build_publish_continuation_op(continuation_state)
        self._prior_continuation_state = continuation_state
        return ThoughtGatingStageResult(
            evaluate_op=evaluate_op,
            signal_snapshot=signal_snapshot,
            result=result,
            publish_gate_result_op=publish_gate_result_op,
            continuation_state=continuation_state,
            publish_continuation_op=publish_continuation_op,
        )


@dataclass
class DirectedRetrievalRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes directed retrieval from the upstream thought-gating stage result."""

    directed_retrieval_layer: DirectedRetrievalAPI
    request_provider: DirectedRetrievalRequestProvider
    upstream_stage_name: str = "thought_gating_and_continuation_pressure"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for directed-retrieval execution."""

        return "directed_retrieval_into_thought_window"

    def run(self, frame: RuntimeFrame) -> DirectedRetrievalStageResult:
        """Execute directed retrieval against the declared upstream thought-gating stage result."""

        thought_gating_result = _require_stage_result(frame, self.upstream_stage_name, ThoughtGatingStageResult)
        request = self.request_provider.build_request(frame, thought_gating_result)
        if request.source_gate_result_id != thought_gating_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Directed-retrieval requests must preserve the upstream thought-gate result provenance"
            )
        plan_op = self.directed_retrieval_layer.build_plan_op(thought_gating_result.result, request)
        plan, bundle = self.directed_retrieval_layer.retrieve_for_thought_window(
            thought_gating_result.result,
            thought_gating_result.continuation_state,
            request,
        )
        publish_bundle_op = self.directed_retrieval_layer.build_publish_bundle_op(bundle)
        return DirectedRetrievalStageResult(
            plan_op=plan_op,
            request=request,
            plan=plan,
            bundle=bundle,
            publish_bundle_op=publish_bundle_op,
        )


@dataclass
class EmbodiedPromptRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that assembles shared embodied prompt contracts for current-cycle consumers."""

    prompt_layer: EmbodiedPromptAPI
    request_provider: EmbodiedPromptRequestProvider
    conscious_stage_name: str = "reportable_conscious_content"
    gate_stage_name: str = "thought_gating_and_continuation_pressure"
    retrieval_stage_name: str = "directed_retrieval_into_thought_window"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for embodied prompt assembly."""

        return "embodied_subjective_prompt_and_action_autonomy"

    def run(self, frame: RuntimeFrame) -> EmbodiedPromptStageResult:
        """Assemble prompt contracts against the declared upstream conscious, gate, and retrieval results."""

        conscious_result = _require_stage_result(frame, self.conscious_stage_name, ConsciousContentStageResult)
        thought_gating_result = _require_stage_result(frame, self.gate_stage_name, ThoughtGatingStageResult)
        directed_retrieval_result = _require_stage_result(
            frame,
            self.retrieval_stage_name,
            DirectedRetrievalStageResult,
        )
        requests = tuple(
            self.request_provider.build_requests(
                frame,
                conscious_result,
                thought_gating_result,
                directed_retrieval_result,
            )
        )
        build_ops: list[BuildEmbodiedPromptOp] = []
        contracts: list[EmbodiedPromptContract] = []
        publish_ops: list[PublishEmbodiedPromptContractOp] = []
        outward_expression_view = None
        publish_outward_expression_view_op = None
        outward_expression_request = None
        build_outward_expression_request_op = None
        for request in requests:
            if request.source_conscious_state_id != conscious_result.state.state_id:
                raise RuntimeStageExecutionError(
                    "Embodied-prompt requests must preserve the upstream conscious-state provenance"
                )
            if request.source_gate_result_id != thought_gating_result.result.result_id:
                raise RuntimeStageExecutionError(
                    "Embodied-prompt requests must preserve the upstream thought-gate result provenance"
                )
            if request.source_retrieval_bundle_id != directed_retrieval_result.bundle.bundle_id:
                raise RuntimeStageExecutionError(
                    "Embodied-prompt requests must preserve the upstream retrieval-bundle provenance"
                )
            build_op = self.prompt_layer.build_request_op(request)
            contract = self.prompt_layer.build_prompt_contract(request)
            publish_op = self.prompt_layer.build_publish_op(contract)
            build_ops.append(build_op)
            contracts.append(contract)
            publish_ops.append(publish_op)
            if contract.consumer_kind == "outward_expression":
                outward_expression_view = self.prompt_layer.build_outward_expression_view(contract)
                publish_outward_expression_view_op = (
                    self.prompt_layer.build_publish_outward_expression_view_op(outward_expression_view)
                )
                outward_expression_request = self.prompt_layer.build_outward_expression_request(
                    outward_expression_view
                )
                build_outward_expression_request_op = self.prompt_layer.build_outward_expression_request_op(
                    outward_expression_request
                )
        return EmbodiedPromptStageResult(
            requests=requests,
            build_ops=tuple(build_ops),
            contracts=tuple(contracts),
            publish_ops=tuple(publish_ops),
            outward_expression_view=outward_expression_view,
            publish_outward_expression_view_op=publish_outward_expression_view_op,
            outward_expression_request=outward_expression_request,
            build_outward_expression_request_op=build_outward_expression_request_op,
        )


@dataclass
class OutwardExpressionRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes outward-expression draft assembly from the prompt stage output."""

    outward_expression_layer: OutwardExpressionAPI
    prompt_stage_name: str = "embodied_subjective_prompt_and_action_autonomy"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for outward-expression draft assembly."""

        return "outward_expression_owner"

    def run(self, frame: RuntimeFrame) -> OutwardExpressionStageResult:
        """Execute outward-expression draft assembly against the declared upstream prompt stage result."""

        prompt_result = _require_stage_result(frame, self.prompt_stage_name, EmbodiedPromptStageResult)
        request = prompt_result.outward_expression_request
        view = prompt_result.outward_expression_view
        if request is None or view is None:
            raise RuntimeStageExecutionError(
                "Outward-expression runtime stage requires an upstream outward-expression request and view"
            )
        if request.source_prompt_view_id != view.view_id:
            raise RuntimeStageExecutionError(
                "Outward-expression requests must preserve the upstream prompt-view provenance"
            )
        if request.source_prompt_contract_id != view.source_contract_id:
            raise RuntimeStageExecutionError(
                "Outward-expression requests must preserve the upstream prompt-contract provenance"
            )
        prepare_op = self.outward_expression_layer.build_prepare_op(request)
        draft = self.outward_expression_layer.prepare_draft(request)
        publish_draft_op = self.outward_expression_layer.build_publish_draft_op(draft)
        return OutwardExpressionStageResult(
            request=request,
            prepare_op=prepare_op,
            draft=draft,
            publish_draft_op=publish_draft_op,
        )


@runtime_checkable
class OutwardExpressionExternalizationRequestProvider(Protocol):
    """Runtime-owned provider for explicit bridging into the outward-expression externalization owner."""

    def build_request(
        self,
        frame: RuntimeFrame,
        outward_expression_result: OutwardExpressionStageResult,
    ) -> OutwardExpressionExternalizationRequest:
        """Return the explicit request to pass into the outward-expression externalization owner."""

        ...


@dataclass
class OutwardExpressionExternalizationRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes outward-expression externalization draft assembly."""

    externalization_layer: OutwardExpressionExternalizationAPI
    request_provider: OutwardExpressionExternalizationRequestProvider
    outward_expression_stage_name: str = "outward_expression_owner"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for outward-expression externalization draft assembly."""

        return "outward_expression_execution_externalization_owner"

    def run(self, frame: RuntimeFrame) -> OutwardExpressionExternalizationStageResult:
        """Execute outward-expression externalization draft assembly against the declared outward-expression stage result."""

        outward_expression_result = _require_stage_result(
            frame,
            self.outward_expression_stage_name,
            OutwardExpressionStageResult,
        )
        request = self.request_provider.build_request(frame, outward_expression_result)
        if request.source_outward_expression_draft_id != outward_expression_result.draft.draft_id:
            raise RuntimeStageExecutionError(
                "Outward-expression externalization requests must preserve the upstream outward-expression draft provenance"
            )
        if request.source_prompt_contract_id != outward_expression_result.draft.source_prompt_contract_id:
            raise RuntimeStageExecutionError(
                "Outward-expression externalization requests must preserve the upstream prompt-contract provenance"
            )
        request_op = self.externalization_layer.build_request_op(request)
        draft = self.externalization_layer.prepare_externalization_draft(request)
        publish_draft_op = self.externalization_layer.build_publish_draft_op(draft)
        return OutwardExpressionExternalizationStageResult(
            request_op=request_op,
            request=request,
            draft=draft,
            publish_draft_op=publish_draft_op,
        )


@dataclass
class InternalThoughtRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes internal thought from the upstream gate and retrieval stage results."""

    internal_thought_layer: InternalThoughtAPI
    request_provider: InternalThoughtRequestProvider
    gate_stage_name: str = "thought_gating_and_continuation_pressure"
    retrieval_stage_name: str = "directed_retrieval_into_thought_window"
    prompt_stage_name: str = "embodied_subjective_prompt_and_action_autonomy"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for internal-thought execution."""

        return "internal_thought_loop_owner"

    def run(self, frame: RuntimeFrame) -> InternalThoughtStageResult:
        """Execute internal thought against the declared upstream gate and retrieval stage results."""

        thought_gating_result = _require_stage_result(frame, self.gate_stage_name, ThoughtGatingStageResult)
        directed_retrieval_result = _require_stage_result(
            frame,
            self.retrieval_stage_name,
            DirectedRetrievalStageResult,
        )
        prompt_result = _require_stage_result(frame, self.prompt_stage_name, EmbodiedPromptStageResult)
        request = self.request_provider.build_request(
            frame,
            thought_gating_result,
            directed_retrieval_result,
            prompt_result,
        )
        if request.source_gate_result_id != thought_gating_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Internal-thought requests must preserve the upstream thought-gate result provenance"
            )
        if request.source_retrieval_bundle_id != directed_retrieval_result.bundle.bundle_id:
            raise RuntimeStageExecutionError(
                "Internal-thought requests must preserve the upstream retrieval-bundle provenance"
            )
        run_op = self.internal_thought_layer.build_run_op(
            thought_gating_result.result,
            directed_retrieval_result.bundle,
            request,
        )
        result, trace = self.internal_thought_layer.run_thought_cycle(
            thought_gating_result.result,
            directed_retrieval_result.bundle,
            thought_gating_result.continuation_state,
            request,
        )
        publish_result_op = self.internal_thought_layer.build_publish_result_op(result)
        return InternalThoughtStageResult(
            run_op=run_op,
            request=request,
            result=result,
            trace=trace,
            publish_result_op=publish_result_op,
        )


@dataclass
class ActionExternalizationRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes action externalization from the upstream internal-thought stage result."""

    action_externalization_layer: ActionExternalizationAPI
    request_provider: ThoughtExternalizationRequestProvider
    upstream_stage_name: str = "internal_thought_loop_owner"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for action externalization execution."""

        return "action_proposal_externalization_contract"

    def run(self, frame: RuntimeFrame) -> ActionExternalizationStageResult:
        """Execute action externalization against the declared upstream internal-thought stage result."""

        internal_thought_result = _require_stage_result(frame, self.upstream_stage_name, InternalThoughtStageResult)
        request = self.request_provider.build_request(frame, internal_thought_result)
        if request.source_thought_cycle_result_id != internal_thought_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Thought-externalization requests must preserve the upstream thought-cycle result provenance"
            )
        request_op = self.action_externalization_layer.build_request_op(internal_thought_result.result, request)
        result = self.action_externalization_layer.externalize_action_proposal(
            internal_thought_result.result,
            request,
        )
        publish_externalization_op = None
        publish_rejection_op = None
        if result.status == "normalized":
            publish_externalization_op = self.action_externalization_layer.build_publish_externalization_op(result)
        if result.status == "bridge_rejected":
            publish_rejection_op = self.action_externalization_layer.build_publish_rejection_op(result)
        return ActionExternalizationStageResult(
            request_op=request_op,
            request=request,
            result=result,
            publish_externalization_op=publish_externalization_op,
            publish_rejection_op=publish_rejection_op,
        )


@dataclass
class PlannerBridgeRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes planner bridge from the upstream externalization stage result."""

    planner_bridge_layer: PlannerBridgeAPI
    request_provider: PlannerBridgeRequestProvider
    upstream_stage_name: str = "action_proposal_externalization_contract"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for planner-bridge execution."""

        return "planner_executor_feedback_bridge"

    def run(self, frame: RuntimeFrame) -> PlannerBridgeStageResult:
        """Execute planner bridge against the declared upstream externalization stage result."""

        action_externalization_result = _require_stage_result(
            frame,
            self.upstream_stage_name,
            ActionExternalizationStageResult,
        )
        request = self.request_provider.build_request(frame, action_externalization_result)
        if request.source_externalization_result_id != action_externalization_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Planner-bridge requests must preserve the upstream externalization-result provenance"
            )
        evaluate_op = self.planner_bridge_layer.build_evaluate_op(action_externalization_result.result, request)
        result, execution_feedback = self.planner_bridge_layer.evaluate_proposal(
            action_externalization_result.result,
            request,
        )
        publish_decision_op = None
        publish_rejection_op = None
        publish_feedback_op = None
        if result.action_decision is not None:
            publish_decision_op = self.planner_bridge_layer.build_publish_decision_op(result.action_decision)
        if result.status in {"policy_rejected", "execution_consistency_failed"}:
            publish_rejection_op = self.planner_bridge_layer.build_publish_rejection_op(result)
        if execution_feedback is not None:
            publish_feedback_op = self.planner_bridge_layer.build_publish_execution_feedback_op(execution_feedback)
        return PlannerBridgeStageResult(
            evaluate_op=evaluate_op,
            request=request,
            result=result,
            execution_feedback=execution_feedback,
            publish_decision_op=publish_decision_op,
            publish_rejection_op=publish_rejection_op,
            publish_feedback_op=publish_feedback_op,
        )


@dataclass
class IdentityGovernanceRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes identity governance from the upstream internal-thought stage result."""

    identity_governance_layer: IdentityGovernanceAPI
    request_provider: IdentityGovernanceRequestProvider
    upstream_stage_name: str = "internal_thought_loop_owner"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for identity-governance execution."""

        return "identity_governance_self_revision_integration"

    def run(self, frame: RuntimeFrame) -> IdentityGovernanceStageResult:
        """Execute identity governance against the declared upstream internal-thought stage result."""

        internal_thought_result = _require_stage_result(frame, self.upstream_stage_name, InternalThoughtStageResult)
        request = self.request_provider.build_request(frame, internal_thought_result)
        if request.source_thought_cycle_result_id != internal_thought_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Identity-governance requests must preserve the upstream thought-cycle result provenance"
            )
        evaluate_op = self.identity_governance_layer.build_evaluate_op(internal_thought_result.result, request)
        result = self.identity_governance_layer.evaluate_self_revision(internal_thought_result.result, request)
        publish_pressure_op = self.identity_governance_layer.build_publish_pressure_op(
            request,
            result.pressure_state,
        )
        publish_revision_decision_op = self.identity_governance_layer.build_publish_revision_decision_op(
            result.revision_decision,
        )
        publish_applied_identity_state_op = None
        if result.applied_identity_state is not None:
            publish_applied_identity_state_op = self.identity_governance_layer.build_publish_applied_identity_state_op(
                result.applied_identity_state,
            )
        return IdentityGovernanceStageResult(
            evaluate_op=evaluate_op,
            request=request,
            result=result,
            publish_pressure_op=publish_pressure_op,
            publish_revision_decision_op=publish_revision_decision_op,
            publish_applied_identity_state_op=publish_applied_identity_state_op,
        )


@dataclass
class ExperienceWritebackRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes continuity writeback from planner and governance outcomes."""

    experience_writeback_layer: ExperienceWritebackAPI
    request_provider: ExperienceWritebackRequestProvider
    planner_upstream_stage_name: str = "planner_executor_feedback_bridge"
    governance_upstream_stage_name: str = "identity_governance_self_revision_integration"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for experience-writeback execution."""

        return "execution_writeback_and_autobiographical_consolidation"

    def run(self, frame: RuntimeFrame) -> ExperienceWritebackStageResult:
        """Execute continuity writeback against the declared planner and governance stage results."""

        planner_bridge_result = _require_stage_result(
            frame,
            self.planner_upstream_stage_name,
            PlannerBridgeStageResult,
        )
        identity_governance_result = _require_stage_result(
            frame,
            self.governance_upstream_stage_name,
            IdentityGovernanceStageResult,
        )
        requests = tuple(
            self.request_provider.build_requests(
                frame,
                planner_bridge_result,
                identity_governance_result,
            )
        )
        results: list[ExperienceWritebackResult] = []
        publish_writeback_ops: list[PublishExperienceWritebackOp] = []
        publish_candidate_ops: list[PublishConsolidationCandidateOp] = []
        expected_outcome_ids = {
            "planner_bridge": planner_bridge_result.result.result_id,
            "identity_governance": identity_governance_result.result.result_id,
        }
        for request in requests:
            expected_outcome_id = expected_outcome_ids[request.source_outcome_kind]
            if request.source_outcome_id != expected_outcome_id:
                raise RuntimeStageExecutionError(
                    "Experience-writeback requests must preserve the declared upstream outcome provenance"
                )
            result = self.experience_writeback_layer.write_experience(request)
            results.append(result)
            publish_writeback_ops.append(
                self.experience_writeback_layer.build_publish_experience_writeback_op(result)
            )
            for candidate in result.consolidation_candidates:
                publish_candidate_ops.append(
                    self.experience_writeback_layer.build_publish_consolidation_candidate_op(
                        result,
                        candidate,
                    )
                )
        return ExperienceWritebackStageResult(
            requests=requests,
            results=tuple(results),
            publish_writeback_ops=tuple(publish_writeback_ops),
            publish_candidate_ops=tuple(publish_candidate_ops),
        )


@dataclass
class AutonomyRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes autonomy from explicit upstream owner outputs."""

    autonomy_layer: AutonomyAPI
    request_provider: AutonomyRequestProvider
    thought_gating_stage_name: str = "thought_gating_and_continuation_pressure"
    directed_retrieval_stage_name: str = "directed_retrieval_into_thought_window"
    internal_thought_stage_name: str = "internal_thought_loop_owner"
    planner_bridge_stage_name: str = "planner_executor_feedback_bridge"
    identity_governance_stage_name: str = "identity_governance_self_revision_integration"
    experience_writeback_stage_name: str = "execution_writeback_and_autobiographical_consolidation"
    prompt_stage_name: str = "embodied_subjective_prompt_and_action_autonomy"
    outward_expression_stage_name: str = "outward_expression_owner"
    outward_expression_externalization_stage_name: str = "outward_expression_execution_externalization_owner"
    _prior_deferred_records: tuple[DeferredContinuityRecord, ...] = field(
        default_factory=tuple,
        init=False,
        repr=False,
    )

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for autonomy execution."""

        return "subjective_autonomy_and_proactive_evolution"

    def run(self, frame: RuntimeFrame) -> AutonomyStageResult:
        """Execute autonomy against the declared upstream owner outputs."""

        thought_gating_result = _require_stage_result(
            frame,
            self.thought_gating_stage_name,
            ThoughtGatingStageResult,
        )
        directed_retrieval_result = _require_stage_result(
            frame,
            self.directed_retrieval_stage_name,
            DirectedRetrievalStageResult,
        )
        internal_thought_result = _require_stage_result(
            frame,
            self.internal_thought_stage_name,
            InternalThoughtStageResult,
        )
        planner_bridge_result = _require_stage_result(
            frame,
            self.planner_bridge_stage_name,
            PlannerBridgeStageResult,
        )
        identity_governance_result = _require_stage_result(
            frame,
            self.identity_governance_stage_name,
            IdentityGovernanceStageResult,
        )
        experience_writeback_result = _require_stage_result(
            frame,
            self.experience_writeback_stage_name,
            ExperienceWritebackStageResult,
        )
        prompt_result = _require_stage_result(frame, self.prompt_stage_name, EmbodiedPromptStageResult)
        outward_expression_result = _require_stage_result(
            frame,
            self.outward_expression_stage_name,
            OutwardExpressionStageResult,
        )
        outward_expression_externalization_result = _require_stage_result(
            frame,
            self.outward_expression_externalization_stage_name,
            OutwardExpressionExternalizationStageResult,
        )
        request = self.request_provider.build_request(
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
        )
        request = replace(
            request,
            prior_deferred_records=self._prior_deferred_records,
        )
        if request.source_gate_result_id != thought_gating_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream thought-gate result provenance"
            )
        if request.source_retrieval_bundle_id != directed_retrieval_result.bundle.bundle_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream retrieval-bundle provenance"
            )
        if request.source_thought_cycle_result_id != internal_thought_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream thought-cycle result provenance"
            )
        if request.source_planner_bridge_result_id != planner_bridge_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream planner-bridge result provenance"
            )
        if request.source_identity_governance_result_id != identity_governance_result.result.result_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream identity-governance result provenance"
            )
        expected_writeback_result_ids = tuple(result.result_id for result in experience_writeback_result.results)
        if request.source_writeback_result_ids != expected_writeback_result_ids:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream writeback-result provenance"
            )
        if request.source_outward_expression_draft_id != outward_expression_result.draft.draft_id:
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream outward-expression draft provenance"
            )
        if (
            request.source_outward_expression_externalization_draft_id
            != outward_expression_externalization_result.draft.draft_id
        ):
            raise RuntimeStageExecutionError(
                "Autonomy requests must preserve the upstream outward-expression externalization draft provenance"
            )
        evaluate_op = self.autonomy_layer.build_evaluate_op(request)
        result = self.autonomy_layer.evaluate(request)
        self._prior_deferred_records = result.deferred_records
        publish_result_op = self.autonomy_layer.build_publish_result_op(result)
        return AutonomyStageResult(
            request=request,
            evaluate_op=evaluate_op,
            result=result,
            publish_result_op=publish_result_op,
        )


@dataclass
class EvaluationRuntimeStage(RuntimeStage):
    """Runtime-owned adapter that executes read-only evaluation from explicit owner outputs."""

    evaluation_layer: EvaluationAPI
    request_provider: EvaluationRequestProvider
    internal_thought_stage_name: str = "internal_thought_loop_owner"
    action_externalization_stage_name: str = "action_proposal_externalization_contract"
    planner_bridge_stage_name: str = "planner_executor_feedback_bridge"
    identity_governance_stage_name: str = "identity_governance_self_revision_integration"
    experience_writeback_stage_name: str = "execution_writeback_and_autobiographical_consolidation"
    autonomy_stage_name: str = "subjective_autonomy_and_proactive_evolution"
    prompt_stage_name: str = "embodied_subjective_prompt_and_action_autonomy"
    outward_expression_stage_name: str = "outward_expression_owner"
    outward_expression_externalization_stage_name: str = "outward_expression_execution_externalization_owner"

    @property
    def stage_name(self) -> str:
        """Stable runtime stage name for evaluation execution."""

        return "evaluation_fidelity_and_diagnostic_provenance"

    def run(self, frame: RuntimeFrame) -> EvaluationStageResult:
        """Execute read-only evaluation against the declared upstream stage results."""

        internal_thought_result = _require_stage_result(
            frame,
            self.internal_thought_stage_name,
            InternalThoughtStageResult,
        )
        action_externalization_result = _require_stage_result(
            frame,
            self.action_externalization_stage_name,
            ActionExternalizationStageResult,
        )
        planner_bridge_result = _require_stage_result(
            frame,
            self.planner_bridge_stage_name,
            PlannerBridgeStageResult,
        )
        identity_governance_result = _require_stage_result(
            frame,
            self.identity_governance_stage_name,
            IdentityGovernanceStageResult,
        )
        experience_writeback_result = _require_stage_result(
            frame,
            self.experience_writeback_stage_name,
            ExperienceWritebackStageResult,
        )
        autonomy_result = _require_stage_result(frame, self.autonomy_stage_name, AutonomyStageResult)
        prompt_result = _require_stage_result(
            frame,
            self.prompt_stage_name,
            EmbodiedPromptStageResult,
        )
        outward_expression_result = _require_stage_result(
            frame,
            self.outward_expression_stage_name,
            OutwardExpressionStageResult,
        )
        outward_expression_externalization_result = _require_stage_result(
            frame,
            self.outward_expression_externalization_stage_name,
            OutwardExpressionExternalizationStageResult,
        )
        request = self.request_provider.build_request(
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
        )
        evidence_bundle = self.request_provider.build_evidence_bundle(
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
        )
        if evidence_bundle.source_request_id != request.request_id:
            raise RuntimeStageExecutionError(
                "Evaluation evidence bundles must preserve the source request id"
            )
        evaluate_op = self.evaluation_layer.build_evaluate_op(request, evidence_bundle)
        artifact = self.evaluation_layer.evaluate(request, evidence_bundle)
        publish_artifact_op = self.evaluation_layer.build_publish_artifact_op(artifact)
        return EvaluationStageResult(
            request=request,
            evaluate_op=evaluate_op,
            evidence_bundle=evidence_bundle,
            artifact=artifact,
            publish_artifact_op=publish_artifact_op,
        )