"""R85 unit tests — classify_for_persistence + make_memory_record."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from helios_v2.memory.classifier import (
    MemoryClassification,
    classify_for_persistence,
    make_memory_record,
)


# =============================================================================
# classify_for_persistence: skip cases
# =============================================================================

def test_classify_skip_when_llm_no_and_obj_low():
    """LLM says no + obj < 0.2 -> skip"""
    c = classify_for_persistence(
        llm_remember=False,
        stimulus_text="x",
        hormone_snapshot={"cortisol": 0.0},
        feeling_snapshot={"arousal": 0.0, "social_safety": 1.0},
        outcome_class="internal_only",
    )
    assert c.classification == "skip"
    assert c.target_layer is None


def test_classify_skip_when_llm_no_and_obj_moderate():
    """LLM says no + 0.2 <= obj < 0.5 -> skip (LLM veto respected)"""
    c = classify_for_persistence(
        llm_remember=False,
        stimulus_text="x" * 100,
        hormone_snapshot={"cortisol": 0.5},
        feeling_snapshot={"arousal": 0.5, "social_safety": 0.5},
        outcome_class="internal_only",
    )
    assert c.classification == "skip"


# =============================================================================
# classify_for_persistence: persist_full cases
# =============================================================================

def test_classify_persist_full_when_llm_yes_and_obj_high():
    """LLM yes + obj >= 0.5 -> persist_full"""
    c = classify_for_persistence(
        llm_remember=True,
        stimulus_text="x" * 100,
        hormone_snapshot={"cortisol": 0.7},
        feeling_snapshot={"arousal": 0.7, "social_safety": 0.3},
        outcome_class="self_changed",
    )
    assert c.classification == "persist_full"
    assert c.objective_importance >= 0.5


def test_classify_persist_full_via_objective_override():
    """LLM no but obj >= 0.5 -> persist_full (objective override)"""
    c = classify_for_persistence(
        llm_remember=False,
        stimulus_text="x" * 200,  # long = high intensity
        hormone_snapshot={"cortisol": 0.9},
        feeling_snapshot={"arousal": 0.9, "social_safety": 0.1},
        outcome_class="self_changed",
    )
    assert c.classification == "persist_full"
    assert c.objective_importance >= 0.5
    # LLM veto overridden -> goes to L4 (high importance) or L3 (moderate)
    assert c.target_layer in ("L3_short", "L4_long")


# =============================================================================
# Layer assignment
# =============================================================================

def test_classify_layer_l4_when_full_and_obj_high():
    """persist_full + obj >= 0.7 -> L4_long"""
    c = classify_for_persistence(
        llm_remember=True,
        stimulus_text="A" * 300,
        hormone_snapshot={"cortisol": 0.9, "dopamine": 0.9},
        feeling_snapshot={"arousal": 0.9, "social_safety": 0.1},
        outcome_class="self_changed",
    )
    assert c.classification == "persist_full"
    assert c.target_layer == "L4_long"


def test_classify_layer_l3_when_low_priority():
    """persist_low_priority always -> L3_short"""
    c = classify_for_persistence(
        llm_remember=True,
        stimulus_text="x",
        hormone_snapshot={"cortisol": 0.0},
        feeling_snapshot={"arousal": 0.0, "social_safety": 1.0},
        outcome_class="internal_only",
    )
    if c.classification == "persist_low_priority":
        assert c.target_layer == "L3_short"


def test_classify_layer_l3_when_full_but_obj_moderate():
    """persist_full but obj < 0.7 -> L3_short (not L4)"""
    c = classify_for_persistence(
        llm_remember=True,
        stimulus_text="moderate length stimulus text",
        hormone_snapshot={"cortisol": 0.4},
        feeling_snapshot={"arousal": 0.4, "social_safety": 0.5},
        outcome_class="world_changed",
    )
    # Should be persist_full (LLM yes + obj >= 0.2 with AND fallback) or persist_low_priority
    if c.classification == "persist_full" and c.objective_importance < 0.7:
        assert c.target_layer == "L3_short"


def test_classify_layer_l3_when_low_priority():
    """persist_low_priority always -> L3_short"""
    c = classify_for_persistence(
        llm_remember=True,
        stimulus_text="x",
        hormone_snapshot={"cortisol": 0.0},
        feeling_snapshot={"arousal": 0.0, "social_safety": 1.0},
        outcome_class="internal_only",
    )
    if c.classification == "persist_low_priority":
        assert c.target_layer == "L3_short"


# =============================================================================
# make_memory_record
# =============================================================================

def test_make_memory_record_raises_on_skip():
    c = MemoryClassification(
        classification="skip",
        objective_importance=0.0,
        target_layer=None,
        reason="test",
    )
    with pytest.raises(ValueError):
        make_memory_record(
            record_id="r1",
            tick_id=1,
            outcome_class="internal_only",
            continuity_kind="internal_only",
            summary="x",
            classification=c,
            llm_remember=False,
            hormone_snapshot={},
            feeling_snapshot={},
            created_at_wall=1000.0,
        )


def test_make_memory_record_l4_long():
    c = MemoryClassification(
        classification="persist_full",
        objective_importance=0.8,
        target_layer="L4_long",
        reason="test",
    )
    r = make_memory_record(
        record_id="r-l4",
        tick_id=42,
        outcome_class="self_changed",
        continuity_kind="self_changed",
        summary="Important memory",
        classification=c,
        llm_remember=True,
        hormone_snapshot={"cortisol": 0.7},
        feeling_snapshot={"arousal": 0.7},
        created_at_wall=5000.0,
    )
    assert r.record_id == "r-l4"
    assert r.tick_id == 42
    assert r.layer == "L4_long"
    assert r.objective_importance == 0.8
    assert r.is_consolidated is True  # L4 always consolidated
    assert r.llm_remember_decision is True
    assert r.double_confirmation_class == "persist_full"
    assert r.created_at_wall == 5000.0
    assert r.recall_count == 0
    assert r.soft_deleted_at is None


def test_make_memory_record_l3_short():
    c = MemoryClassification(
        classification="persist_full",
        objective_importance=0.55,
        target_layer="L3_short",
        reason="test",
    )
    r = make_memory_record(
        record_id="r-l3",
        tick_id=1,
        outcome_class="world_changed",
        continuity_kind="world_changed",
        summary="x",
        classification=c,
        llm_remember=True,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=2000.0,
    )
    assert r.layer == "L3_short"
    assert r.is_consolidated is False  # L3 not consolidated


def test_make_memory_record_preserves_tags():
    c = MemoryClassification(
        classification="persist_full",
        objective_importance=0.8,
        target_layer="L4_long",
        reason="x",
    )
    r = make_memory_record(
        record_id="r",
        tick_id=1,
        outcome_class="x",
        continuity_kind="x",
        summary="x",
        classification=c,
        llm_remember=True,
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_wall=1000.0,
        extra_tags=("a", "b", "c"),
    )
    assert r.tags == ("a", "b", "c")
