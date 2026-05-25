"""Focused tests for unified execution feedback recording."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from behavior_registry import RuntimeBehaviorCatalog
from helios_io.feedback_recorder import FeedbackRecorder
from helios_io.limb import BehaviorCommand


def test_feedback_recorder_persists_execution_log(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)
    command = BehaviorCommand(
        priority=75,
        name="decision::1",
        action="speak_share",
        behavior_id="bootstrap.speak_share",
        proposal_id="proposal::1",
        decision_id="decision::1",
        channel_id="qq",
        op_name="send",
        normalized_intensity=0.68,
        modality="text",
        provenance={
            "source_type": "thought_action_bridge",
            "origin_type": "thought",
            "origin_id": "thought::7::rumination::1000",
            "owner_path": "thought_action_bridge",
            "requested_op": "send",
            "candidate_channels": ["qq"],
            "personality_influence_trace": {
                "behavior_bias": 0.18,
                "novelty_bias": 0.62,
                "ranked_channels": ["qq"],
            },
        },
        policy_trace={"resolved_score": 0.7},
    )

    feedback = recorder.record_command_result(
        command,
        {"success": True, "tick": 12, "reply_text": "hello"},
        observed_at_tick=12,
        observed_at_ts=456.0,
    )

    rows = catalog.registry.list_execution_feedback(behavior_id="bootstrap.speak_share")
    assert feedback.success
    assert feedback.behavior_name == "speak_share"
    assert len(rows) == 1
    assert rows[0].decision_id == "decision::1"
    assert rows[0].feedback_details["policy_trace"]["resolved_score"] == 0.7
    assert rows[0].feedback_details["provenance"]["personality_influence_trace"]["behavior_bias"] == 0.18
    assert rows[0].feedback_details["normalized_intensity"] == 0.68
    assert rows[0].feedback_details["owner_path"] == "thought_action_bridge"

    events = catalog.registry.list_feedback_events(decision_id="decision::1")
    assert len(events) == 1
    assert events[0].event_kind == "execution_result"
    assert events[0].payload["success"] is True
    assert events[0].payload["provenance"]["personality_influence_trace"]["novelty_bias"] == 0.62
    assert events[0].payload["origin_id"] == "thought::7::rumination::1000"
    assert events[0].payload["normalized_intensity"] == 0.68
    assert events[0].payload["owner_path"] == "thought_action_bridge"
    assert events[0].payload["requested_op"] == "send"
    assert events[0].payload["selected_channel_id"] == "qq"


def test_feedback_recorder_persists_user_channel_and_memory_events(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)

    recorder.record_user_feedback(
        source_path="passive_inbound",
        channel_id="qq",
        user_id="user1",
        text="hello helios",
        sec_result={"novelty": 0.6},
        metadata={"channel_id": "qq"},
        observed_at_ts=10.0,
    )
    recorder.record_channel_receipt(
        source_path="interaction",
        channel_id="qq",
        action_name="reply_message",
        success=True,
        proposal_id="proposal::2",
        decision_id="decision::2",
        behavior_id="bootstrap.reply_message",
        op_name="send",
        normalized_intensity=0.51,
        provenance={
            "origin_type": "thought",
            "origin_id": "thought::1::self_question::1000",
            "owner_path": "thought_action_bridge",
            "requested_op": "send",
            "candidate_channels": ["qq"],
        },
        original_text="你好。",
        rendered_text="你好！",
        expression_profile={"tone": "direct", "compactness": "compact", "applied": True},
        metadata={"user_id": "user1"},
        observed_at_ts=11.0,
    )
    recorder.record_memory_write(
        source_path="preconscious_thought",
        memory_type="autobiographical",
        memory_id="moment::1",
        summary="我在预想接下来可能发生的事",
        payload={"thought_type": "future_projection"},
        observed_at_ts=12.0,
    )

    events = catalog.registry.list_feedback_events()
    assert [event.event_kind for event in events] == ["user_feedback", "channel_receipt", "memory_write"]
    assert events[0].payload["user_id"] == "user1"
    assert events[1].behavior_id == "bootstrap.reply_message"
    assert events[1].payload["op_name"] == "send"
    assert events[1].payload["origin_id"] == "thought::1::self_question::1000"
    assert events[1].payload["owner_path"] == "thought_action_bridge"
    assert events[1].payload["candidate_channels"] == ["qq"]
    assert events[1].payload["original_text"] == "你好。"
    assert events[1].payload["rendered_text"] == "你好！"
    assert events[1].payload["expression_profile"]["tone"] == "direct"
    assert events[2].memory_id == "moment::1"


def test_feedback_recorder_persists_policy_rejection_event(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)

    recorder.record_policy_rejection(
        source_path="thought_action_bridge",
        proposal_id="proposal::reject::1",
        decision_id="decision::proposal::reject::1",
        behavior_name="speak_share",
        rejection_reason="execution_scope_constraint",
        op_name="send",
        normalized_intensity=0.74,
        provenance={
            "origin_type": "thought",
            "origin_id": "thought::1::rumination::1000",
            "owner_path": "thought_action_bridge",
            "requested_op": "send",
            "candidate_channels": ["qq"],
        },
        payload={"policy_trace": {"execution_scope": "internal"}},
        observed_at_ts=20.0,
    )

    events = catalog.registry.list_feedback_events(event_kind="policy_rejection")
    assert len(events) == 1
    assert events[0].source_path == "thought_action_bridge"
    assert events[0].payload["rejection_reason"] == "execution_scope_constraint"
    assert events[0].payload["policy_trace"]["execution_scope"] == "internal"
    assert events[0].payload["op_name"] == "send"
    assert events[0].payload["origin_id"] == "thought::1::rumination::1000"
    assert events[0].payload["owner_path"] == "thought_action_bridge"
    assert events[0].payload["candidate_channels"] == ["qq"]


def test_feedback_recorder_persists_execution_consistency_failure_event(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)

    recorder.record_execution_consistency_failure(
        source_path="thought_action_bridge",
        proposal_id="proposal::consistency::1",
        decision_id="decision::consistency::1",
        behavior_id="bootstrap.speak_share",
        behavior_name="speak_share",
        channel_id="qq",
        op_name="send",
        normalized_intensity=0.61,
        provenance={
            "origin_type": "thought",
            "origin_id": "thought::2::future_projection::1000",
            "owner_path": "thought_action_bridge",
            "requested_op": "send",
            "candidate_channels": ["qq"],
        },
        payload={"rejection_reason": "channel_status:disconnected"},
        observed_at_ts=22.0,
    )

    events = catalog.registry.list_feedback_events(event_kind="execution_consistency_failure")
    assert len(events) == 1
    assert events[0].channel_id == "qq"
    assert events[0].payload["behavior_name"] == "speak_share"
    assert events[0].payload["rejection_reason"] == "channel_status:disconnected"
    assert events[0].payload["normalized_intensity"] == 0.61
    assert events[0].payload["origin_id"] == "thought::2::future_projection::1000"
    assert events[0].payload["owner_path"] == "thought_action_bridge"
    assert events[0].payload["candidate_channels"] == ["qq"]


def test_feedback_recorder_persists_identity_revision_event(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)

    recorder.record_identity_revision(
        source_path="internal_thought_llm",
        revision_id="identity_revision::1",
        origin_thought_id="thought::1000",
        result="accepted",
        payload={"applied_change": {"personality_baseline": {"openness": 1.05}}},
        observed_at_ts=25.0,
    )

    events = catalog.registry.list_feedback_events(event_kind="identity_revision")
    assert len(events) == 1
    assert events[0].source_path == "internal_thought_llm"
    assert events[0].payload["revision_id"] == "identity_revision::1"
    assert events[0].payload["origin_thought_id"] == "thought::1000"
    assert events[0].payload["result"] == "accepted"