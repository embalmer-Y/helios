"""Focused tests for structured action proposal models."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.action_models import ActionDecision, ActionProposal, ExecutionFeedback


def test_action_proposal_defaults_and_fields():
    proposal = ActionProposal(
        proposal_id="p-1",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="speak_share",
    )

    assert proposal.proposal_id == "p-1"
    assert proposal.score_bundle == {}
    assert proposal.candidate_channels == []
    assert proposal.origin_type == ""
    assert proposal.op_name == ""
    assert proposal.outbound_intensity == 0.0


def test_action_decision_accepted_tracks_rejection_reason():
    accepted = ActionDecision(
        decision_id="d-1",
        proposal_id="p-1",
        behavior_name="speak_share",
        selected_channel_id="qq",
        selected_op="send",
    )
    rejected = ActionDecision(
        decision_id="d-2",
        proposal_id="p-2",
        behavior_name="speak_share",
        rejection_reason="channel unavailable",
    )

    assert accepted.accepted is True
    assert rejected.accepted is False
    assert accepted.normalized_intensity == 0.0


def test_action_proposal_supports_thought_origin_op_payload_and_intensity():
    proposal = ActionProposal(
        proposal_id="p-thought",
        source_type="preconscious",
        source_module="preconscious_policy",
        origin_type="thought",
        origin_id="thought::7::rumination::1000",
        intent_type="thought_action",
        behavior_name="speak_share",
        op_name="send",
        op_params={"target_user_id": "master"},
        outbound_intensity=0.66,
    )

    assert proposal.origin_type == "thought"
    assert proposal.origin_id.startswith("thought::7")
    assert proposal.op_name == "send"
    assert proposal.op_params["target_user_id"] == "master"
    assert proposal.outbound_intensity == 0.66


def test_execution_feedback_captures_structured_result_details():
    feedback = ExecutionFeedback(
        proposal_id="p-1",
        decision_id="d-1",
        behavior_name="speak_share",
        success=True,
        channel_id="tts",
        op_name="send",
        result_details={"played": True},
        state_effects={"valence_delta": 0.1},
    )

    assert feedback.success is True
    assert feedback.result_details["played"] is True
    assert feedback.state_effects["valence_delta"] == 0.1