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
        modality="text",
        provenance={
            "source_type": "regulation",
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

    events = catalog.registry.list_feedback_events(decision_id="decision::1")
    assert len(events) == 1
    assert events[0].event_kind == "execution_result"
    assert events[0].payload["success"] is True
    assert events[0].payload["provenance"]["personality_influence_trace"]["novelty_bias"] == 0.62


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
    assert events[2].memory_id == "moment::1"


def test_feedback_recorder_persists_policy_rejection_event(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    recorder = FeedbackRecorder(catalog)

    recorder.record_policy_rejection(
        source_path="preconscious",
        proposal_id="proposal::reject::1",
        decision_id="decision::proposal::reject::1",
        behavior_name="speak_share",
        rejection_reason="internal_only_constraint",
        payload={"policy_trace": {"internal_only": True}},
        observed_at_ts=20.0,
    )

    events = catalog.registry.list_feedback_events(event_kind="policy_rejection")
    assert len(events) == 1
    assert events[0].source_path == "preconscious"
    assert events[0].payload["rejection_reason"] == "internal_only_constraint"
    assert events[0].payload["policy_trace"]["internal_only"] is True