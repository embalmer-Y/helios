from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.planner_bridge import (
    ActionDecision,
    ExecutionConsistencyFailure,
    NormalizedExecutionFeedback,
    PlannerBridgeConfig,
    PlannerBridgeError,
    PlannerBridgeRequest,
    PlannerBridgeResult,
)


def test_planner_bridge_request_is_immutable_and_snapshots_are_read_only() -> None:
    request = PlannerBridgeRequest(
        request_id="planner-bridge-request:001",
        source_externalization_result_id="thought-externalization-result:001",
        normalized_proposal_present=True,
        behavior_snapshot={"registered": True},
        channel_descriptor_snapshot={"cli": {"supported_ops": ("reply_message",)}},
        channel_status_snapshot={"cli": {"available": True}},
        tick_id=1,
    )

    with pytest.raises(FrozenInstanceError):
        request.normalized_proposal_present = False

    with pytest.raises(TypeError):
        request.behavior_snapshot["registered"] = False


def test_planner_bridge_config_requires_fixed_learned_policy_surface() -> None:
    config = PlannerBridgeConfig(
        legal_min_intensity=0.0,
        legal_max_intensity=1.0,
        bridge_bootstrap_id="planner-bridge-bootstrap:v1",
        mandatory_learned_parameters=(
            "policy_evaluation_policy",
            "channel_selection_policy",
            "feedback_normalization_policy",
        ),
    )

    assert config.bridge_bootstrap_id == "planner-bridge-bootstrap:v1"

    with pytest.raises(PlannerBridgeError, match="mandatory learned-parameter categories"):
        PlannerBridgeConfig(
            legal_min_intensity=0.0,
            legal_max_intensity=1.0,
            bridge_bootstrap_id="planner-bridge-bootstrap:v1",
            mandatory_learned_parameters=("policy_evaluation_policy",),
        )


def test_execution_consistency_failure_and_rejected_result_remain_distinct() -> None:
    decision = ActionDecision(
        decision_id="action-decision:001",
        proposal_id="normalized-proposal:001",
        selected_channel_id="cli",
        selected_op="reply_message",
        normalized_intensity=0.8,
        validated_params={"outbound_text": "hello"},
        execution_priority=1,
        policy_trace={"score": 0.9},
    )
    failure = ExecutionConsistencyFailure(
        decision_id=decision.decision_id,
        proposal_id=decision.proposal_id,
        behavior_name="reply_message",
        rejection_reason="missing_output_op",
        selected_channel_id=decision.selected_channel_id,
        selected_op=decision.selected_op,
        policy_trace=decision.policy_trace,
    )
    result = PlannerBridgeResult(
        result_id="planner-bridge-result:001",
        source_request_id="planner-bridge-request:001",
        status="execution_consistency_failed",
        action_decision=decision,
        rejection_reason="missing_output_op",
        execution_consistency_failure=failure,
        tick_id=1,
    )

    assert result.execution_consistency_failure is failure


def test_normalized_execution_feedback_is_immutable() -> None:
    feedback = NormalizedExecutionFeedback(
        proposal_id="normalized-proposal:001",
        decision_id="action-decision:001",
        behavior_name="reply_message",
        success=True,
        channel_id="cli",
        op_name="reply_message",
        normalized_intensity=0.8,
        result_details={"transport_status": "ok"},
        state_effects={"visible_action_attempted": True},
    )

    with pytest.raises(TypeError):
        feedback.result_details["transport_status"] = "failed"
