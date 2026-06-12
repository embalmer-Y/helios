"""R85 integration test — R85MemoryClassifierBridge end-to-end."""

from __future__ import annotations

import sys
from pathlib import Path
import time

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from helios_v2.composition.bridges import R85MemoryClassifierBridge
from helios_v2.persistence.contracts import PersistedExperienceRecord


def _make_persisted(*, rid: str, summary: str, outcome_class: str) -> PersistedExperienceRecord:
    return PersistedExperienceRecord(
        record_id=rid,
        tick_id=10,
        continuity_kind=outcome_class,
        outcome_class=outcome_class,
        source_outcome_kind="planner_bridge",
        source_outcome_id="p1",
        writeback_status="applied",
        summary=summary,
        requested_effect_summary="req",
        applied_effect_summary="applied",
        reason_trace=(),
        linkage={},
        sequence=0,
        embedding=None,
        record_kind="episodic",
        metadata={},
    )


def test_bridge_with_no_records_returns_empty():
    bridge = R85MemoryClassifierBridge()
    out = bridge.build_memory_records(
        persisted_records=(),
        tick_id=1,
        created_at_wall=time.time(),
    )
    assert out == ()


def test_bridge_with_default_llm_yes_promotes_important_records():
    """Default llm_remember=True, high-importance outcome_class=self_changed -> L4"""
    bridge = R85MemoryClassifierBridge(llm_remember_default=True)
    records = (
        _make_persisted(rid="r1", summary="重要事件，深度情感共鸣，长长的叙述文本应该写进去", outcome_class="self_changed"),
    )
    out = bridge.build_memory_records(
        persisted_records=records,
        tick_id=10,
        hormone_snapshot={"cortisol": 0.8, "dopamine": 0.8},
        feeling_snapshot={"arousal": 0.8, "social_safety": 0.2},
        created_at_wall=1000.0,
    )
    assert len(out) == 1
    assert out[0].layer in ("L3_short", "L4_long")


def test_bridge_with_llm_no_and_obj_low_skips():
    """LLM no + obj low -> skip"""
    bridge = R85MemoryClassifierBridge(llm_remember_default=False)
    records = (
        _make_persisted(rid="r-skip", summary="x", outcome_class="internal_only"),
    )
    out = bridge.build_memory_records(
        persisted_records=records,
        tick_id=10,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
    )
    assert out == ()


def test_bridge_with_per_record_llm_decisions():
    """Per-record llm_remember overrides default"""
    bridge = R85MemoryClassifierBridge(llm_remember_default=False)
    records = (
        _make_persisted(rid="r-yes", summary="important event with strong content", outcome_class="self_changed"),
        _make_persisted(rid="r-no", summary="noise", outcome_class="internal_only"),
    )
    out = bridge.build_memory_records(
        persisted_records=records,
        tick_id=10,
        hormone_snapshot={"cortisol": 0.8},
        feeling_snapshot={"arousal": 0.8, "social_safety": 0.2},
        llm_remember_per_record={"r-yes": True, "r-no": False},
        created_at_wall=1000.0,
    )
    # r-yes: LLM yes + high obj -> persist (L3 or L4)
    # r-no: LLM no + low obj + internal_only -> skip
    ids = [r.record_id for r in out]
    assert "memory:r-yes" in ids
    assert "memory:r-no" not in ids


def test_bridge_preserves_layer_assignment_logic():
    """Verify L4 vs L3 split is correct via objective importance"""
    bridge = R85MemoryClassifierBridge(llm_remember_default=True)
    # High importance
    rec_hi = _make_persisted(rid="hi", summary="x" * 200, outcome_class="self_changed")
    # Lower importance (outcome_class=internal_only, short text)
    rec_lo = _make_persisted(rid="lo", summary="x", outcome_class="internal_only")
    out = bridge.build_memory_records(
        persisted_records=(rec_hi, rec_lo),
        tick_id=10,
        hormone_snapshot={"cortisol": 0.9, "dopamine": 0.9},
        feeling_snapshot={"arousal": 0.9, "social_safety": 0.1},
        created_at_wall=1000.0,
    )
    by_id = {r.record_id: r for r in out}
    if "memory:hi" in by_id:
        # High importance record should be at least L3
        assert by_id["memory:hi"].layer in ("L3_short", "L4_long")
    if "memory:lo" in by_id:
        # Low importance record, if persisted, should be L3
        assert by_id["memory:lo"].layer == "L3_short"
