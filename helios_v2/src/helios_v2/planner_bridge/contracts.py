"""Owner: planner executor feedback bridge.

Owns:
- planner-bridge request, result, decision, and feedback contracts
- execution-consistency-failure and rejection contracts
- planner-bridge API and publication ops

Does not own:
- action externalization normalization
- raw channel transport
- feedback persistence
- governance acceptance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.action_externalization import ThoughtExternalizationResult


class PlannerBridgeError(RuntimeError):
    """Hard-stop error raised when planner-bridge owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise PlannerBridgeError(f"{name} must be within [0.0, 1.0]")


BridgeStatus = Literal[
    "accepted",
    "policy_rejected",
    "execution_consistency_failed",
    "executed",
    "execution_failed",
    "no_actionable_proposal",
]
BridgeRejectionReason = Literal[
    "behavior_not_registered",
    "behavior_unreviewed",
    "score_below_threshold",
    "no_channel_available",
    "requested_op_unavailable",
    "missing_requested_op",
    "missing_channel_binding",
    "missing_output_op",
    "missing_op_inputs",
    "risk_class_restricted",
    "governance_required",
    "governance_denied",
]
PlannerBridgeLearnedParameterCategory = Literal[
    "policy_evaluation_policy",
    "channel_selection_policy",
    "feedback_normalization_policy",
]

_BRIDGE_STATUSES = {
    "accepted",
    "policy_rejected",
    "execution_consistency_failed",
    "executed",
    "execution_failed",
    "no_actionable_proposal",
}
_BRIDGE_REJECTION_REASONS = {
    "behavior_not_registered",
    "behavior_unreviewed",
    "score_below_threshold",
    "no_channel_available",
    "requested_op_unavailable",
    "missing_requested_op",
    "missing_channel_binding",
    "missing_output_op",
    "missing_op_inputs",
    "risk_class_restricted",
    "governance_required",
    "governance_denied",
}


@dataclass(frozen=True)
class PlannerBridgeConfig:
    """Expose the confirmed initialization and learned-policy surface for planner bridge."""

    legal_min_intensity: float
    legal_max_intensity: float
    bridge_bootstrap_id: str
    mandatory_learned_parameters: tuple[PlannerBridgeLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "policy_evaluation_policy",
            "channel_selection_policy",
            "feedback_normalization_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise PlannerBridgeError(
                "Planner-bridge config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("PlannerBridgeConfig.legal_min_intensity", self.legal_min_intensity)
        _validate_unit_interval("PlannerBridgeConfig.legal_max_intensity", self.legal_max_intensity)
        if self.legal_min_intensity > self.legal_max_intensity:
            raise PlannerBridgeError("Planner-bridge intensity range is inverted")
        if not self.bridge_bootstrap_id:
            raise PlannerBridgeError("PlannerBridgeConfig must declare a non-empty bridge_bootstrap_id")


@dataclass(frozen=True)
class PlannerBridgeRequest:
    """Explicit bridge input contract for one proposal-to-decision cycle."""

    request_id: str
    source_externalization_result_id: str
    normalized_proposal_present: bool
    behavior_snapshot: Mapping[str, object]
    channel_descriptor_snapshot: Mapping[str, object]
    channel_status_snapshot: Mapping[str, object]
    tick_id: int | None
    governance_approval: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise PlannerBridgeError("PlannerBridgeRequest must declare a non-empty request_id")
        if not self.source_externalization_result_id:
            raise PlannerBridgeError(
                "PlannerBridgeRequest must declare a non-empty source_externalization_result_id"
            )
        for attr_name in (
            "behavior_snapshot",
            "channel_descriptor_snapshot",
            "channel_status_snapshot",
            "governance_approval",
        ):
            mapping = MappingProxyType(dict(getattr(self, attr_name)))
            for key in mapping:
                if not key:
                    raise PlannerBridgeError(
                        f"PlannerBridgeRequest {attr_name} must not contain empty keys"
                    )
            object.__setattr__(self, attr_name, mapping)


@dataclass(frozen=True)
class ActionDecision:
    """Immutable accepted action decision published by the bridge owner."""

    decision_id: str
    proposal_id: str
    selected_channel_id: str
    selected_op: str
    normalized_intensity: float
    validated_params: Mapping[str, object]
    execution_priority: int
    policy_trace: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise PlannerBridgeError("ActionDecision must declare a non-empty decision_id")
        if not self.proposal_id:
            raise PlannerBridgeError("ActionDecision must declare a non-empty proposal_id")
        if not self.selected_channel_id:
            raise PlannerBridgeError("ActionDecision must declare a non-empty selected_channel_id")
        if not self.selected_op:
            raise PlannerBridgeError("ActionDecision must declare a non-empty selected_op")
        _validate_unit_interval("ActionDecision.normalized_intensity", self.normalized_intensity)
        if self.execution_priority < 0:
            raise PlannerBridgeError("ActionDecision.execution_priority must be >= 0")
        object.__setattr__(self, "validated_params", MappingProxyType(dict(self.validated_params)))
        object.__setattr__(self, "policy_trace", MappingProxyType(dict(self.policy_trace)))


@dataclass(frozen=True)
class ExecutionConsistencyFailure:
    """Immutable pre-execution bridge failure contract."""

    decision_id: str
    proposal_id: str
    behavior_name: str
    rejection_reason: BridgeRejectionReason
    selected_channel_id: str
    selected_op: str
    policy_trace: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise PlannerBridgeError("ExecutionConsistencyFailure must declare a non-empty decision_id")
        if not self.proposal_id:
            raise PlannerBridgeError("ExecutionConsistencyFailure must declare a non-empty proposal_id")
        if not self.behavior_name:
            raise PlannerBridgeError("ExecutionConsistencyFailure must declare a non-empty behavior_name")
        if self.rejection_reason not in _BRIDGE_REJECTION_REASONS:
            raise PlannerBridgeError(
                "ExecutionConsistencyFailure rejection_reason must use the fixed taxonomy"
            )
        if not self.selected_channel_id:
            raise PlannerBridgeError(
                "ExecutionConsistencyFailure must declare a non-empty selected_channel_id"
            )
        if not self.selected_op:
            raise PlannerBridgeError("ExecutionConsistencyFailure must declare a non-empty selected_op")
        object.__setattr__(self, "policy_trace", MappingProxyType(dict(self.policy_trace)))


@dataclass(frozen=True)
class PlannerBridgeResult:
    """Immutable published planner-bridge outcome for one evaluated proposal path."""

    result_id: str
    source_request_id: str
    status: BridgeStatus
    action_decision: ActionDecision | None
    rejection_reason: BridgeRejectionReason | None
    execution_consistency_failure: ExecutionConsistencyFailure | None
    tick_id: int | None
    pending_governed_action: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise PlannerBridgeError("PlannerBridgeResult must declare a non-empty result_id")
        if not self.source_request_id:
            raise PlannerBridgeError("PlannerBridgeResult must declare a non-empty source_request_id")
        if self.status not in _BRIDGE_STATUSES:
            raise PlannerBridgeError("PlannerBridgeResult status must use the fixed taxonomy")
        if self.pending_governed_action is not None:
            pending = MappingProxyType(dict(self.pending_governed_action))
            for key in pending:
                if not key:
                    raise PlannerBridgeError(
                        "PlannerBridgeResult pending_governed_action must not contain empty keys"
                    )
            object.__setattr__(self, "pending_governed_action", pending)
        if self.rejection_reason is not None and self.rejection_reason not in _BRIDGE_REJECTION_REASONS:
            raise PlannerBridgeError(
                "PlannerBridgeResult rejection_reason must use the fixed taxonomy"
            )
        if self.status == "accepted":
            if self.action_decision is None:
                raise PlannerBridgeError("Accepted PlannerBridgeResult must publish action_decision")
            if self.rejection_reason is not None or self.execution_consistency_failure is not None:
                raise PlannerBridgeError(
                    "Accepted PlannerBridgeResult must not mix rejection or consistency-failure payloads"
                )
        elif self.status == "policy_rejected":
            if self.rejection_reason is None:
                raise PlannerBridgeError("Policy-rejected PlannerBridgeResult must publish rejection_reason")
            if self.action_decision is not None or self.execution_consistency_failure is not None:
                raise PlannerBridgeError(
                    "Policy-rejected PlannerBridgeResult must not publish action_decision or execution_consistency_failure"
                )
        elif self.status == "execution_consistency_failed":
            if self.execution_consistency_failure is None:
                raise PlannerBridgeError(
                    "Execution-consistency-failed PlannerBridgeResult must publish execution_consistency_failure"
                )
            if self.action_decision is None:
                raise PlannerBridgeError(
                    "Execution-consistency-failed PlannerBridgeResult must preserve action_decision"
                )
            if self.rejection_reason is None:
                raise PlannerBridgeError(
                    "Execution-consistency-failed PlannerBridgeResult must publish rejection_reason"
                )
        elif self.status == "no_actionable_proposal":
            if (
                self.action_decision is not None
                or self.rejection_reason is not None
                or self.execution_consistency_failure is not None
            ):
                raise PlannerBridgeError(
                    "No-actionable-proposal PlannerBridgeResult must not publish action_decision, "
                    "rejection_reason, or execution_consistency_failure"
                )
        else:
            if self.action_decision is None:
                raise PlannerBridgeError(
                    "Executed and execution-failed PlannerBridgeResult must preserve action_decision"
                )
            if self.rejection_reason is not None or self.execution_consistency_failure is not None:
                raise PlannerBridgeError(
                    "Executed and execution-failed PlannerBridgeResult must not publish rejection or consistency-failure payloads"
                )


@dataclass(frozen=True)
class NormalizedExecutionFeedback:
    """Immutable normalized execution outcome published by the bridge owner."""

    proposal_id: str
    decision_id: str
    behavior_name: str
    success: bool
    channel_id: str
    op_name: str
    normalized_intensity: float
    result_details: Mapping[str, object]
    state_effects: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise PlannerBridgeError("NormalizedExecutionFeedback must declare a non-empty proposal_id")
        if not self.decision_id:
            raise PlannerBridgeError("NormalizedExecutionFeedback must declare a non-empty decision_id")
        if not self.behavior_name:
            raise PlannerBridgeError("NormalizedExecutionFeedback must declare a non-empty behavior_name")
        if not self.channel_id:
            raise PlannerBridgeError("NormalizedExecutionFeedback must declare a non-empty channel_id")
        if not self.op_name:
            raise PlannerBridgeError("NormalizedExecutionFeedback must declare a non-empty op_name")
        _validate_unit_interval(
            "NormalizedExecutionFeedback.normalized_intensity",
            self.normalized_intensity,
        )
        object.__setattr__(self, "result_details", MappingProxyType(dict(self.result_details)))
        object.__setattr__(self, "state_effects", MappingProxyType(dict(self.state_effects)))


@dataclass(frozen=True)
class EvaluatePlannerBridgeOp:
    """Runtime-visible request op for one bridge evaluation cycle."""

    op_name: str
    owner: str
    request_id: str
    externalization_result_id: str
    normalized_proposal_present: bool


@dataclass(frozen=True)
class PublishActionDecisionOp:
    """Runtime-visible publication op for one accepted action decision."""

    op_name: str
    owner: str
    decision_id: str
    proposal_id: str
    selected_channel_id: str
    selected_op: str


@dataclass(frozen=True)
class PublishPlannerBridgeRejectionOp:
    """Runtime-visible publication op for one rejected or consistency-failed bridge outcome."""

    op_name: str
    owner: str
    result_id: str
    status: BridgeStatus
    rejection_reason: BridgeRejectionReason


@dataclass(frozen=True)
class PublishExecutionFeedbackOp:
    """Runtime-visible publication op for one normalized execution feedback contract."""

    op_name: str
    owner: str
    decision_id: str
    proposal_id: str
    success: bool


@runtime_checkable
class PlannerBridgeAPI(Protocol):
    """Owner: planner executor feedback bridge API."""

    def evaluate_proposal(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> tuple[PlannerBridgeResult, NormalizedExecutionFeedback | None]:
        """Return one formal bridge result and optional normalized execution feedback."""

    def evaluate_internal_only(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> PlannerBridgeResult:
        """Owner: planner executor feedback bridge.

        Purpose:
            Produce the explicit internal-only bridge result for a fired tick that produced
            no normalized action proposal to route. This represents "the system fired a
            thought and chose not to act" as a first-class outcome rather than an error.

        Inputs:
            `externalization_result` - a non-normalized `ThoughtExternalizationResult`.
            `request` - the planner-bridge request whose `normalized_proposal_present` is False.

        Returns:
            A `PlannerBridgeResult` with status `no_actionable_proposal` and no action
            decision, rejection, or consistency failure.

        Raises:
            PlannerBridgeError if the externalization result is normalized (the externalizing
            path must be used instead) or the request claims a proposal is present.
        """

    def build_evaluate_op(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> EvaluatePlannerBridgeOp:
        """Return one request op describing planner-bridge evaluation."""

    def build_evaluate_op_internal_only(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> EvaluatePlannerBridgeOp:
        """Return one request op describing an internal-only planner-bridge evaluation."""

    def build_publish_decision_op(
        self,
        decision: ActionDecision,
    ) -> PublishActionDecisionOp:
        """Return one publication op describing action-decision publication."""

    def build_publish_rejection_op(
        self,
        result: PlannerBridgeResult,
    ) -> PublishPlannerBridgeRejectionOp:
        """Return one publication op describing rejected or consistency-failed bridge publication."""

    def build_publish_execution_feedback_op(
        self,
        feedback: NormalizedExecutionFeedback,
    ) -> PublishExecutionFeedbackOp:
        """Return one publication op describing execution-feedback publication."""
