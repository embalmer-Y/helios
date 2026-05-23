"""Focused tests for the SQLite-backed behavior registry."""

from __future__ import annotations

import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from behavior_registry import BehaviorExecutionRecord, BehaviorSourceRecord, FeedbackEventRecord, SQLiteBehaviorRegistry
from helios_io.action_models import BehaviorSpec


def test_registry_initialize_creates_expected_tables(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)

    registry.initialize()

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "schema_migrations" in tables
    assert "behaviors" in tables
    assert "behavior_sources" in tables
    assert "behavior_execution_log" in tables
    assert "feedback_events" in tables


def test_registry_round_trips_behavior_spec(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)
    spec = BehaviorSpec(
        behavior_id="bootstrap.reply_message",
        name="reply_message",
        display_name="Reply Message",
        description="Reply to an inbound interaction.",
        category="interaction",
        execution_mode="channel",
        parameter_schema={
            "target_user_id": {"required": False, "default": ""},
            "outbound_text": {"required": False, "default": ""},
        },
        applicable_context={"interaction_required": True},
        cooldown_policy={"seconds": 0},
        cost_policy={"cost": 0.1},
        allowed_channel_ids=["qq", "tts"],
        required_capabilities=["send"],
        supported_modalities=["text", "speech"],
        source_kind="bootstrap",
        source_detail={"phase": "transition"},
        review_state="approved",
    )

    registry.upsert_behavior(spec)
    loaded = registry.get_behavior("reply_message")

    assert loaded is not None
    assert loaded.behavior_id == spec.behavior_id
    assert loaded.name == spec.name
    assert loaded.parameter_schema == spec.parameter_schema
    assert loaded.allowed_channel_ids == spec.allowed_channel_ids
    assert loaded.supported_modalities == spec.supported_modalities


def test_registry_lists_behaviors_by_filters(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)
    registry.import_behaviors(
        [
            BehaviorSpec(
                behavior_id="bootstrap.reply_message",
                name="reply_message",
                display_name="Reply Message",
                description="Reply",
                category="interaction",
                execution_mode="channel",
                status="active",
                review_state="approved",
            ),
            BehaviorSpec(
                behavior_id="bootstrap.reflect",
                name="reflect",
                display_name="Reflect",
                description="Reflect internally",
                category="internal",
                execution_mode="internal",
                status="draft",
                review_state="pending",
            ),
        ]
    )

    active = registry.list_behaviors(status="active")
    pending = registry.list_behaviors(review_state="pending")

    assert [spec.name for spec in active] == ["reply_message"]
    assert [spec.name for spec in pending] == ["reflect"]


def test_registry_records_behavior_sources_and_execution_feedback(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)
    spec = BehaviorSpec(
        behavior_id="bootstrap.reflect",
        name="reflect",
        display_name="Reflect",
        description="Reflect internally",
        category="internal",
        execution_mode="internal",
    )
    registry.upsert_behavior(spec)
    registry.record_behavior_source(
        BehaviorSourceRecord(
            source_id="source::bootstrap::bootstrap.reflect",
            behavior_id="bootstrap.reflect",
            source_kind="bootstrap",
            source_summary="Imported from bootstrap specs",
            captured_at=123.0,
        )
    )
    registry.record_execution_feedback(
        BehaviorExecutionRecord(
            execution_id="execution::1",
            behavior_id="bootstrap.reflect",
            proposal_id="proposal::1",
            decision_id="decision::1",
            success=True,
            result_details={"success": True, "tick": 5},
            feedback_details={"state_effects": {"phi": 0.1}},
            created_at=124.0,
        )
    )

    sources = registry.list_behavior_sources(behavior_id="bootstrap.reflect")
    executions = registry.list_execution_feedback(behavior_id="bootstrap.reflect")

    assert len(sources) == 1
    assert sources[0].source_kind == "bootstrap"
    assert len(executions) == 1
    assert executions[0].proposal_id == "proposal::1"
    assert executions[0].result_details["tick"] == 5


def test_registry_propose_behavior_normalizes_pending_state_and_records_source(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)

    proposed = registry.propose_behavior(
        BehaviorSpec(
            behavior_id="proposal.compose_poem",
            name="compose_poem",
            display_name="Compose Poem",
            description="Compose a short poem for the user.",
            category="social",
            execution_mode="channel",
            allowed_channel_ids=["qq"],
            required_capabilities=["send"],
        ),
        source_summary="LLM proposed a poem behavior",
        source_uri="llm://draft/compose_poem",
    )

    loaded = registry.get_behavior("compose_poem")
    sources = registry.list_behavior_sources(behavior_id="proposal.compose_poem")

    assert proposed.status == "draft"
    assert proposed.review_state == "pending"
    assert proposed.source_kind == "llm_proposal"
    assert loaded is not None
    assert loaded.review_state == "pending"
    assert len(sources) == 1
    assert sources[0].source_uri == "llm://draft/compose_poem"


def test_registry_records_and_filters_feedback_events(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    registry = SQLiteBehaviorRegistry(db_path)

    registry.record_feedback_event(
        FeedbackEventRecord(
            event_id="feedback::1",
            event_kind="user_feedback",
            source_path="passive_inbound",
            channel_id="qq",
            payload={"user_id": "user1", "text": "hello"},
            created_at=10.0,
        )
    )
    registry.record_feedback_event(
        FeedbackEventRecord(
            event_id="feedback::2",
            event_kind="memory_write",
            source_path="preconscious_thought",
            memory_id="moment::1",
            payload={"thought_type": "future_projection"},
            created_at=11.0,
        )
    )
    registry.record_feedback_event(
        FeedbackEventRecord(
            event_id="feedback::3",
            event_kind="channel_receipt",
            source_path="interaction",
            decision_id="decision::1",
            behavior_id="bootstrap.reply_message",
            channel_id="qq",
            payload={"success": True},
            created_at=12.0,
        )
    )

    user_events = registry.list_feedback_events(event_kind="user_feedback")
    thought_events = registry.list_feedback_events(source_path="preconscious_thought")
    decision_events = registry.list_feedback_events(decision_id="decision::1")

    assert len(user_events) == 1
    assert user_events[0].payload["user_id"] == "user1"
    assert len(thought_events) == 1
    assert thought_events[0].memory_id == "moment::1"
    assert len(decision_events) == 1
    assert decision_events[0].behavior_id == "bootstrap.reply_message"