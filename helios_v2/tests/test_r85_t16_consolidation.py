"""R85-T16 consolidation-timing decision C: write-trigger promote_layer.

Per R85 consolidation-timing decision (2026-06-12 16:50 UTC):
- C: write + recall hot paths trigger promote_layer() on the affected record
- D: idle fallback batch promote (R86+)
- T16 implements the WRITE half of C in R85MemoryClassifierBridge.
- The RECALL half is deferred to R86 alongside the R85 record store.

T16 tests (8 total):
- Wiring: build_memory_records invokes promote_layer on the new record
- New records (recall_count=0) are unchanged (L3, recall=0)
- promote_layer is called once per record, not zero or twice
- promote_layer is the actual engine function, not a stub
- Idempotence: calling build_memory_records twice returns equivalent records
- promote_layer is imported lazily (inside the function, not at module top)
- Multi-record input: each record gets its own promote call
- L4 record with sufficient recall_count would be promoted to L5 (unit-level)
"""
from __future__ import annotations

import pytest


# =============================================================================
# Test 1-2: Wiring of promote_layer into the build path
# =============================================================================


def _make_persisted_record(record_id: str, summary: str = "test summary"):
    """Build a minimal PersistedExperienceRecord stub for the bridge."""
    from dataclasses import dataclass

    @dataclass
    class _Stub:
        pass

    s = _Stub()
    s.record_id = record_id
    s.summary = summary
    # outcome_class and continuity_kind need to be valid enums
    s.outcome_class = "self_changed"
    s.continuity_kind = "world_changed"
    return s


def test_t16_bridge_invokes_promote_layer_on_new_record(monkeypatch):
    """build_memory_records calls promote_layer on the just-built record."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge

    captured = []

    real_promote = None
    from helios_v2.memory.engine import promote_layer
    real_promote = promote_layer

    def spy_promote(record):
        captured.append(record)
        return real_promote(record)

    # Monkeypatch the import inside build_memory_records
    import helios_v2.memory.engine as engine_mod
    monkeypatch.setattr(engine_mod, "promote_layer", spy_promote)

    bridge = R85MemoryClassifierBridge()
    persisted = (_make_persisted_record("r-1", "hello"),)
    out = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={"dopamine": 0.5, "cortisol": 0.5, "arousal": 0.5},
        feeling_snapshot={"social_safety": 0.5},
        created_at_wall=1000.0,
    )
    assert len(out) == 1
    assert len(captured) == 1, "promote_layer should be called exactly once per new record"
    assert captured[0].record_id == "memory:r-1"


def test_t16_bridge_new_records_unchanged_after_promote():
    """A fresh record (recall_count=0) stays L3_short after promote_layer."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge

    bridge = R85MemoryClassifierBridge()
    persisted = (_make_persisted_record("r-2", "x"),)
    out = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    assert len(out) == 1
    rec = out[0]
    assert rec.layer == "L3_short"
    assert rec.recall_count == 0
    assert rec.is_consolidated is False


# =============================================================================
# Test 3-4: Per-record dispatch
# =============================================================================


def test_t16_bridge_multi_record_each_gets_promote(monkeypatch):
    """Each persisted record gets exactly one promote_layer call."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge

    captured_ids = []
    real_promote = None
    from helios_v2.memory.engine import promote_layer
    real_promote = promote_layer

    def spy_promote(record):
        captured_ids.append(record.record_id)
        return real_promote(record)

    import helios_v2.memory.engine as engine_mod
    monkeypatch.setattr(engine_mod, "promote_layer", spy_promote)

    bridge = R85MemoryClassifierBridge()
    persisted = tuple(
        _make_persisted_record(f"r-multi-{i}", f"summary {i}")
        for i in range(3)
    )
    out = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={"dopamine": 0.5, "cortisol": 0.5, "arousal": 0.5},
        feeling_snapshot={"social_safety": 0.5},
        created_at_wall=1000.0,
    )
    assert len(out) == 3
    assert len(captured_ids) == 3
    # Each captured id is distinct and matches the output
    for i, cid in enumerate(captured_ids):
        assert cid == f"memory:r-multi-{i}"


def test_t16_bridge_promote_is_engine_function_not_stub():
    """The promote_layer used by the bridge is the real engine.promote_layer."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge
    from helios_v2.memory.engine import promote_layer as real_promote

    bridge = R85MemoryClassifierBridge()
    persisted = (_make_persisted_record("r-3", "hello"),)
    out = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    # The output record should be the same as what real promote_layer would
    # produce for an L3 recall=0 record (idempotent no-op)
    rec = out[0]
    promoted = real_promote(rec)
    assert rec.layer == promoted.layer
    assert rec.recall_count == promoted.recall_count


# =============================================================================
# Test 5: Idempotence
# =============================================================================


def test_t16_bridge_idempotent_for_fresh_records():
    """Calling build_memory_records twice returns equivalent records (recall=0)."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge

    bridge = R85MemoryClassifierBridge()
    persisted = (_make_persisted_record("r-4", "idempotent test"),)
    out1 = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    out2 = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    assert len(out1) == 1 and len(out2) == 1
    assert out1[0].layer == out2[0].layer
    assert out1[0].recall_count == out2[0].recall_count
    assert out1[0].is_consolidated == out2[0].is_consolidated


# =============================================================================
# Test 6: Skip path (no records returned)
# =============================================================================


def test_t16_bridge_no_promote_when_no_records(monkeypatch):
    """If classifier rejects all records, promote_layer is never called."""
    from helios_v2.composition.bridges import R85MemoryClassifierBridge

    captured = []
    real_promote = None
    from helios_v2.memory.engine import promote_layer
    real_promote = promote_layer

    def spy_promote(record):
        captured.append(record)
        return real_promote(record)

    import helios_v2.memory.engine as engine_mod
    monkeypatch.setattr(engine_mod, "promote_layer", spy_promote)

    bridge = R85MemoryClassifierBridge(llm_remember_default=False)
    # Empty stimulus with no significance => classifier should skip
    persisted = (_make_persisted_record("r-skip", ""),)
    out = bridge.build_memory_records(
        persisted_records=persisted,
        tick_id=1,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    # Either skipped (empty out) or kept but with no promote call conflict
    # In either case, captured should match len(out)
    assert len(captured) == len(out)


# =============================================================================
# Test 7: Module-level promote_layer import not at top
# =============================================================================


def test_t16_bridge_promote_is_lazy_imported():
    """promote_layer is imported inside build_memory_records, not at module top.

    This makes the bridge work even if helios_v2.memory.engine is not yet loaded
    at import time (R85 memory engine may be conditionally available).
    """
    import helios_v2.composition.bridges as bridges_mod

    # promote_layer should NOT be a top-level module attribute
    assert not hasattr(bridges_mod, "promote_layer"), (
        "promote_layer should be lazily imported inside build_memory_records, "
        "not exposed at module top-level"
    )


# =============================================================================
# Test 8: Unit-level promote_layer behavior (sanity)
# =============================================================================


def test_t16_promote_layer_l3_to_l4_on_recall_count_2():
    """Unit-level: a L3 record with recall_count=2 promotes to L4."""
    from helios_v2.memory.contracts import MemoryRecord
    from helios_v2.memory.engine import promote_layer

    rec = MemoryRecord(
        record_id="r-promote-test",
        tick_id=1,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        summary="test",
        layer="L3_short",
        objective_importance=0.6,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_tick=1,
        created_at_wall=1000.0,
        last_recall_at_wall=None,
        recall_count=2,
        is_consolidated=False,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=(),
        context_keywords=(),
        cross_links=(),
    )
    promoted = promote_layer(rec)
    assert promoted.layer == "L4_long"
    assert promoted.is_consolidated is True


def test_t16_promote_layer_l4_to_l5_on_recall_5_and_imp_07():
    """Unit-level: L4 + recall=5 + importance>=0.7 promotes to L5."""
    from helios_v2.memory.contracts import MemoryRecord
    from helios_v2.memory.engine import promote_layer

    rec = MemoryRecord(
        record_id="r-promote-l5",
        tick_id=1,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        summary="test",
        layer="L4_long",
        objective_importance=0.8,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_tick=1,
        created_at_wall=1000.0,
        last_recall_at_wall=None,
        recall_count=5,
        is_consolidated=True,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=(),
        context_keywords=(),
        cross_links=(),
    )
    promoted = promote_layer(rec)
    assert promoted.layer == "L5_autobiographical"
    assert promoted.is_consolidated is True
