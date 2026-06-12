"""R85 unit tests — MemoryRecord schema, migrate, decay, soft_delete."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Allow `from helios_v2...` when running pytest from the project root
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from helios_v2.memory.contracts import (
    MemoryRecord,
    MemoryLayer,
    DoubleConfirmationClass,
    should_persist,
    effective_priority,
    soft_delete_memory_record,
    migrate_persisted_to_memory_v2,
    OUTCOME_CLASS_WEIGHTS,
)


def _make_record(**overrides) -> MemoryRecord:
    base = dict(
        record_id="r-test-1",
        tick_id=10,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        summary="test summary",
        layer="L4_long",
        objective_importance=0.7,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot={"cortisol": 0.6, "dopamine": 0.5},
        feeling_snapshot={"arousal": 0.6, "social_safety": 0.4},
        created_at_tick=10,
        created_at_wall=1000.0,
        last_recall_at_wall=None,
        recall_count=0,
        is_consolidated=False,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=("praise",),
        context_keywords=("first_time",),
        cross_links=(),
    )
    base.update(overrides)
    return MemoryRecord(**base)


# =============================================================================
# T1: schema invariants
# =============================================================================

def test_memoryrecord_basic_construction():
    r = _make_record()
    assert r.record_id == "r-test-1"
    assert r.layer == "L4_long"
    assert r.objective_importance == 0.7
    assert isinstance(r.audit_trail, tuple)
    assert isinstance(r.tags, tuple)


def test_memoryrecord_invalid_layer_raises():
    with pytest.raises(Exception):
        _make_record(layer="L9_garbage")


def test_memoryrecord_invalid_double_confirm_raises():
    with pytest.raises(Exception):
        _make_record(double_confirmation_class="nope")


def test_memoryrecord_negative_recall_count_raises():
    with pytest.raises(Exception):
        _make_record(recall_count=-1)


def test_memoryrecord_soft_deleted_without_gc_after_raises():
    with pytest.raises(Exception):
        _make_record(soft_deleted_at=2000.0, memory_gc_after=None)


def test_memoryrecord_objective_importance_out_of_range_raises():
    with pytest.raises(Exception):
        _make_record(objective_importance=1.5)
    with pytest.raises(Exception):
        _make_record(objective_importance=-0.1)


def test_memoryrecord_hormone_snapshot_is_frozen_mapping():
    r = _make_record()
    # Should be MappingProxyType (frozen)
    assert type(r.hormone_snapshot).__name__ == "mappingproxy"
    with pytest.raises(Exception):
        r.hormone_snapshot["cortisol"] = 0.9  # type: ignore


# =============================================================================
# T3: should_persist
# =============================================================================

def test_should_persist_llm_true_high_score_full():
    assert should_persist(True, 0.7) == "persist_full"


def test_should_persist_llm_true_low_score_low_priority():
    assert should_persist(True, 0.3) == "persist_low_priority"


def test_should_persist_llm_true_zero_low_priority_fallback():
    """AND-fallback: LLM True but score < 0.2 -> persist_low_priority"""
    assert should_persist(True, 0.0) == "persist_low_priority"


def test_should_persist_llm_false_high_score_full_objective_override():
    """Objective override: LLM False but score >= 0.5 -> persist_full"""
    assert should_persist(False, 0.6) == "persist_full"


def test_should_persist_llm_false_low_score_skip():
    assert should_persist(False, 0.3) == "skip"


def test_should_persist_llm_false_zero_skip():
    assert should_persist(False, 0.0) == "skip"


def test_should_persist_boundary_05():
    """Score == 0.5 should be persist_full (>= boundary)"""
    assert should_persist(True, 0.5) == "persist_full"
    assert should_persist(False, 0.5) == "persist_full"


def test_should_persist_invalid_score_raises():
    with pytest.raises(Exception):
        should_persist(True, 1.5)
    with pytest.raises(Exception):
        should_persist(True, -0.1)


# =============================================================================
# T1: effective_priority decay
# =============================================================================

def test_effective_priority_no_decay_at_creation():
    r = _make_record(created_at_wall=1000.0, objective_importance=0.8)
    p = effective_priority(r, 1000.0)
    # At t=0, days_since_creation=0, decay=1.0; days_since_recall=1.0 (clamped), rebound=1.1
    # So 0.8 * 1.0 * 1.1 = 0.88
    assert abs(p - 0.88) < 0.01


def test_effective_priority_decays_over_days():
    r = _make_record(created_at_wall=1000.0, objective_importance=0.8)
    p0 = effective_priority(r, 1000.0)
    p1 = effective_priority(r, 1000.0 + 86400.0)  # 1 day
    p7 = effective_priority(r, 1000.0 + 7 * 86400.0)  # 7 days
    assert p0 > p1 > p7
    # After 1 day, decay=0.95, rebound=1+0.1/1=1.1 (days_since_creation=1, clamped)
    # So 0.8 * 0.95 * 1.1 = 0.836
    assert 0.80 < p1 < 0.86
    # After 7 days, decay=0.95^7 ~= 0.698, rebound=1+0.1/7~=1.014
    # 0.8 * 0.698 * 1.014 ~= 0.567
    assert 0.55 < p7 < 0.60


def test_effective_priority_consolidated_does_not_decay():
    r = _make_record(
        created_at_wall=1000.0,
        objective_importance=0.5,
        is_consolidated=True,
    )
    p_1year = effective_priority(r, 1000.0 + 365 * 86400.0)
    assert p_1year == 0.5


def test_effective_priority_recall_rebound():
    """Recent recall should rebound priority"""
    r = _make_record(
        created_at_wall=1000.0,
        objective_importance=0.5,
        last_recall_at_wall=1099.0,  # recalled 1 second ago
    )
    p = effective_priority(r, 1100.0)
    # Rebound: 1 + 0.1/1 (max 1 day floor) = 1.1
    # Decay: ~1.0 (very fresh)
    assert p > 0.5


def test_effective_priority_clamps_to_unit_interval():
    r = _make_record(created_at_wall=1000.0, objective_importance=0.5)
    p_max = effective_priority(r, 1000.0 + 86400.0)
    assert 0.0 <= p_max <= 1.0
    p_old = effective_priority(r, 1000.0 + 365 * 86400.0)
    assert 0.0 <= p_old <= 1.0


# =============================================================================
# T5: soft_delete
# =============================================================================

def test_soft_delete_sets_timestamps_and_audit():
    r = _make_record(created_at_wall=1000.0)
    deleted = soft_delete_memory_record(
        r,
        reason="user_request",
        justification="user said 'forget this'",
        current_wall=2000.0,
    )
    assert deleted.soft_deleted_at == 2000.0
    assert deleted.memory_gc_after == 2000.0 + 7 * 86400.0
    assert len(deleted.audit_trail) == 1
    audit_entry = deleted.audit_trail[0]
    assert audit_entry["kind"] == "soft_delete"
    assert audit_entry["reason"] == "user_request"
    assert audit_entry["justification"] == "user said 'forget this'"


def test_soft_delete_preserves_other_fields():
    r = _make_record(
        record_id="r-x",
        objective_importance=0.42,
        layer="L3_short",
    )
    deleted = soft_delete_memory_record(r, reason="r", justification="j", current_wall=2000.0)
    assert deleted.record_id == "r-x"
    assert deleted.objective_importance == 0.42
    assert deleted.layer == "L3_short"


def test_soft_delete_empty_reason_raises():
    r = _make_record()
    with pytest.raises(Exception):
        soft_delete_memory_record(r, reason="", justification="j", current_wall=2000.0)


def test_soft_delete_empty_justification_raises():
    r = _make_record()
    with pytest.raises(Exception):
        soft_delete_memory_record(r, reason="r", justification="", current_wall=2000.0)


def test_soft_delete_with_audit_extra():
    r = _make_record()
    deleted = soft_delete_memory_record(
        r,
        reason="r",
        justification="j",
        current_wall=2000.0,
        audit_extra={"actor": "LLM", "session_id": "s1"},
    )
    audit_entry = deleted.audit_trail[0]
    assert audit_entry["actor"] == "LLM"
    assert audit_entry["session_id"] == "s1"


# =============================================================================
# T1: migration
# =============================================================================

def test_migrate_persisted_to_memory_v2_basic():
    from helios_v2.persistence.contracts import PersistedExperienceRecord

    legacy = PersistedExperienceRecord(
        record_id="legacy-1",
        tick_id=42,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        source_outcome_kind="stimulus",
        source_outcome_id="s1",
        writeback_status="applied",
        summary="migrated",
        requested_effect_summary="",
        applied_effect_summary="",
        reason_trace=(),
        linkage={},
        sequence=0,
        embedding=None,
        record_kind="episodic",
        metadata={},
    )
    migrated = migrate_persisted_to_memory_v2(legacy, created_at_wall=5000.0)
    assert migrated.record_id == "legacy-1"
    assert migrated.tick_id == 42
    assert migrated.summary == "migrated"
    assert migrated.layer == "L4_long"  # default
    assert migrated.objective_importance == 0.5  # default
    assert migrated.double_confirmation_class == "persist_full"
    assert migrated.created_at_wall == 5000.0
    assert migrated.is_consolidated is False
    assert migrated.audit_trail == ()


def test_migrate_persisted_uses_default_wall_when_omitted():
    from helios_v2.persistence.contracts import PersistedExperienceRecord
    import time

    legacy = PersistedExperienceRecord(
        record_id="legacy-2",
        tick_id=1,
        continuity_kind="internal_only",
        outcome_class="internal_only",
        source_outcome_kind="stimulus",
        source_outcome_id="s1",
        writeback_status="applied",
        summary="x",
        requested_effect_summary="",
        applied_effect_summary="",
        reason_trace=(),
        linkage={},
        sequence=0,
        embedding=None,
        record_kind="episodic",
        metadata={},
    )
    before = time.time()
    migrated = migrate_persisted_to_memory_v2(legacy)
    after = time.time()
    assert before <= migrated.created_at_wall <= after
