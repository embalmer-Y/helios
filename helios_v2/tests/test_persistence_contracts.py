from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.persistence import (
    PersistedExperienceRecord,
    PersistenceError,
    PriorExistenceSnapshot,
    UNASSIGNED_SEQUENCE,
)


def _record(**overrides) -> PersistedExperienceRecord:
    base = dict(
        record_id="experience:writeback-result:001",
        tick_id=1,
        continuity_kind="external_action",
        outcome_class="world_changed",
        source_outcome_kind="planner_bridge",
        source_outcome_id="planner-bridge-result:1",
        writeback_status="written",
        summary="replied to the operator",
        requested_effect_summary="send reply",
        applied_effect_summary="reply sent",
        reason_trace=("planner accepted", "executed"),
        linkage={"source_request_id": "planner-bridge-result:1"},
    )
    base.update(overrides)
    return PersistedExperienceRecord(**base)


def test_record_defaults_to_unassigned_sequence() -> None:
    record = _record()
    assert record.sequence == UNASSIGNED_SEQUENCE


def test_record_rejects_empty_required_fields() -> None:
    with pytest.raises(PersistenceError, match="record_id"):
        _record(record_id="")
    with pytest.raises(PersistenceError, match="source_outcome_id"):
        _record(source_outcome_id="")
    with pytest.raises(PersistenceError, match="summary"):
        _record(summary="")
    with pytest.raises(PersistenceError, match="continuity_kind"):
        _record(continuity_kind="")


def test_record_rejects_empty_reason_trace_items() -> None:
    with pytest.raises(PersistenceError, match="reason_trace"):
        _record(reason_trace=("ok", ""))


def test_record_freezes_linkage_mapping() -> None:
    record = _record(linkage={"origin_thought_id": "thought:1"})
    with pytest.raises(TypeError):
        record.linkage["origin_thought_id"] = "mutated"


def test_record_rejects_non_string_linkage_value() -> None:
    with pytest.raises(PersistenceError, match="linkage"):
        _record(linkage={"origin_thought_id": 123})


def test_record_is_immutable() -> None:
    record = _record()
    with pytest.raises(FrozenInstanceError):
        record.summary = "changed"


def test_with_sequence_stamps_positive_sequence() -> None:
    record = _record()
    stamped = record.with_sequence(7)
    assert stamped.sequence == 7
    assert stamped.record_id == record.record_id
    # The original record is unchanged (immutable copy semantics).
    assert record.sequence == UNASSIGNED_SEQUENCE


def test_with_sequence_rejects_non_positive() -> None:
    record = _record()
    with pytest.raises(PersistenceError, match="positive integer"):
        record.with_sequence(0)
    with pytest.raises(PersistenceError, match="positive integer"):
        record.with_sequence(-3)


def test_prior_existence_snapshot_rejects_negative_count() -> None:
    with pytest.raises(PersistenceError, match="total_record_count"):
        PriorExistenceSnapshot(
            total_record_count=-1,
            most_recent_sequence=None,
            most_recent_tick_id=None,
        )


def test_prior_existence_snapshot_holds_bounded_summary() -> None:
    snapshot = PriorExistenceSnapshot(
        total_record_count=3,
        most_recent_sequence=3,
        most_recent_tick_id=3,
        recent_summaries=("a", "b", "c"),
    )
    assert snapshot.total_record_count == 3
    assert snapshot.most_recent_sequence == 3
    assert snapshot.recent_summaries == ("a", "b", "c")
