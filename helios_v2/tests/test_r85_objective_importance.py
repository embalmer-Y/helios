"""R85 unit tests — objective_importance function."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from helios_v2.memory.engine import (
    objective_importance,
    promote_layer,
)
from helios_v2.memory.contracts import (
    MemoryRecord,
    OUTCOME_CLASS_WEIGHTS,
)


# =============================================================================
# T2: objective_importance basic range
# =============================================================================

def test_objective_importance_zero_length_stimulus():
    s = objective_importance(
        stimulus_text="",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="internal_only",
    )
    assert s == 0.0


def test_objective_importance_in_unit_interval():
    """Always returns a value in [0.0, 1.0] regardless of inputs"""
    for oc in ["self_changed", "world_blocked", "world_changed", "world_failed",
               "self_blocked", "internal_only", "unknown_class"]:
        for cortisol in [0.0, 0.3, 0.5, 0.8, 1.0]:
            for arousal in [0.0, 0.3, 0.5, 0.8, 1.0]:
                s = objective_importance(
                    stimulus_text="Test stimulus text",
                    hormone_snapshot={"cortisol": cortisol},
                    feeling_snapshot={"arousal": arousal, "social_safety": 0.5},
                    outcome_class=oc,
                )
                assert 0.0 <= s <= 1.0, f"out of range for oc={oc}, c={cortisol}, a={arousal}"


def test_objective_importance_self_changed_highest_outcome_weight():
    """self_changed has highest weight (0.95)"""
    s_self = objective_importance(
        stimulus_text="x",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="self_changed",
    )
    s_internal = objective_importance(
        stimulus_text="x",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="internal_only",
    )
    assert s_self > s_internal


def test_objective_importance_outcome_class_weights_applied():
    """All 6 weights must be applied per OUTCOME_CLASS_WEIGHTS table"""
    # Same inputs, different outcome_class
    args = dict(
        stimulus_text="Test stimulus of moderate length",
        hormone_snapshot={"cortisol": 0.5, "dopamine": 0.5},
        feeling_snapshot={"arousal": 0.5, "social_safety": 0.5},
    )
    scores = {}
    for oc, w in OUTCOME_CLASS_WEIGHTS.items():
        scores[oc] = objective_importance(outcome_class=oc, **args)
    # Scores should be ordered by outcome weight
    assert scores["self_changed"] > scores["world_blocked"]
    assert scores["world_blocked"] > scores["world_changed"]
    assert scores["world_changed"] > scores["world_failed"]
    assert scores["world_failed"] > scores["self_blocked"]
    assert scores["self_blocked"] > scores["internal_only"]


# =============================================================================
# T2: each dimension's contribution
# =============================================================================

def test_objective_importance_cortisol_contributes():
    """Higher cortisol -> higher score"""
    base_args = dict(
        stimulus_text="Test",
        feeling_snapshot={"arousal": 0.5, "social_safety": 0.5},
        outcome_class="world_changed",
    )
    s_low = objective_importance(hormone_snapshot={"cortisol": 0.0}, **base_args)
    s_high = objective_importance(hormone_snapshot={"cortisol": 1.0}, **base_args)
    assert s_high > s_low


def test_objective_importance_arousal_contributes():
    """Higher arousal -> higher score"""
    base_args = dict(
        stimulus_text="Test",
        hormone_snapshot={"cortisol": 0.5},
        outcome_class="world_changed",
    )
    s_low = objective_importance(feeling_snapshot={"arousal": 0.0, "social_safety": 0.5}, **base_args)
    s_high = objective_importance(feeling_snapshot={"arousal": 1.0, "social_safety": 0.5}, **base_args)
    assert s_high > s_low


def test_objective_importance_social_safety_inverse():
    """Lower social_safety (i.e. more relationship risk) -> higher score"""
    base_args = dict(
        stimulus_text="Test",
        hormone_snapshot={"cortisol": 0.5},
        outcome_class="world_changed",
    )
    s_safe = objective_importance(feeling_snapshot={"arousal": 0.5, "social_safety": 1.0}, **base_args)
    s_unsafe = objective_importance(feeling_snapshot={"arousal": 0.5, "social_safety": 0.0}, **base_args)
    assert s_unsafe > s_safe


def test_objective_importance_stimulus_intensity():
    """Longer stimulus -> higher intensity (until cap)"""
    base_args = dict(
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
    )
    s_short = objective_importance(stimulus_text="hi", **base_args)
    s_long = objective_importance(stimulus_text="x" * 200, **base_args)
    s_huge = objective_importance(stimulus_text="x" * 1000, **base_args)
    assert s_short < s_long
    # 200+ chars should be saturated
    assert abs(s_long - s_huge) < 0.01


# =============================================================================
# T2: novelty
# =============================================================================

def test_objective_importance_novelty_with_empty_recent():
    s = objective_importance(
        stimulus_text="Brand new stimulus",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
        recent_summaries=(),
    )
    # No history -> novelty = 0.5 (neutral)
    # All other dims contribute normally
    assert 0.0 <= s <= 1.0


def test_objective_importance_novelty_with_embed_callable():
    """When embed_callable is provided, novelty = 1 - max cosine similarity"""
    # Constant embed: similarity is 1.0 -> novelty = 0
    constant_embed = lambda text: [1.0, 0.0, 0.0]
    s = objective_importance(
        stimulus_text="New stimulus",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
        recent_summaries=["old1", "old2"],
        embed_callable=constant_embed,
    )
    # Novelty should be 0 since cosine is 1.0
    # Score should be lower than without history (which had novelty=0.5)
    s_no_history = objective_importance(
        stimulus_text="New stimulus",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
    )
    assert s < s_no_history


def test_objective_importance_novelty_embed_callable_exception_falls_back():
    """If embed_callable raises, novelty falls back to 0.5 (neutral)"""
    def bad_embed(text):
        raise RuntimeError("embed failed")
    s = objective_importance(
        stimulus_text="Test",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
        recent_summaries=["old"],
        embed_callable=bad_embed,
    )
    assert 0.0 <= s <= 1.0


# =============================================================================
# T2: missing fields default to 0.5 (neutral)
# =============================================================================

def test_objective_importance_missing_cortisol_defaults_to_0_5():
    s_with = objective_importance(
        stimulus_text="x",
        hormone_snapshot={"cortisol": 0.5},
        feeling_snapshot={},
        outcome_class="world_changed",
    )
    s_without = objective_importance(
        stimulus_text="x",
        hormone_snapshot={},
        feeling_snapshot={},
        outcome_class="world_changed",
    )
    assert abs(s_with - s_without) < 0.001


# =============================================================================
# T7: promote_layer
# =============================================================================

def _make_record(**overrides) -> MemoryRecord:
    base = dict(
        record_id="r-test-1",
        tick_id=10,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        summary="test",
        layer="L3_short",
        objective_importance=0.5,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot={},
        feeling_snapshot={},
        created_at_tick=10,
        created_at_wall=1000.0,
        last_recall_at_wall=1000.0,
        recall_count=0,
        is_consolidated=False,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=(),
        context_keywords=(),
        cross_links=(),
    )
    base.update(overrides)
    return MemoryRecord(**base)


def test_promote_layer_l3_to_l4_on_recall_count_2():
    r = _make_record(layer="L3_short", recall_count=2)
    promoted = promote_layer(r)
    assert promoted.layer == "L4_long"
    assert promoted.is_consolidated is True


def test_promote_layer_l3_no_promote_below_recall_count_2():
    r = _make_record(layer="L3_short", recall_count=1)
    promoted = promote_layer(r)
    # No promotion, no change -> returns same record
    assert promoted is r or promoted.layer == "L3_short"


def test_promote_layer_l4_to_l5_on_recall_count_5_and_obj_0_7():
    r = _make_record(layer="L4_long", recall_count=5, objective_importance=0.7)
    promoted = promote_layer(r)
    assert promoted.layer == "L5_autobiographical"
    assert promoted.is_consolidated is True


def test_promote_layer_l4_no_promote_when_obj_below_0_7():
    r = _make_record(layer="L4_long", recall_count=10, objective_importance=0.6)
    promoted = promote_layer(r)
    # L4_long should not promote to L5 if obj < 0.7
    assert promoted.layer == "L4_long"


def test_promote_layer_l5_no_further_promotion():
    """L5 is terminal — promote is no-op"""
    r = _make_record(layer="L5_autobiographical", recall_count=100, objective_importance=1.0)
    promoted = promote_layer(r)
    assert promoted.layer == "L5_autobiographical"
    assert promoted.recall_count == 100


def test_promote_layer_preserves_other_fields():
    r = _make_record(
        record_id="r-x",
        layer="L3_short",
        recall_count=2,
        objective_importance=0.42,
        tags=("a", "b"),
    )
    promoted = promote_layer(r)
    assert promoted.record_id == "r-x"
    assert promoted.objective_importance == 0.42
    assert promoted.tags == ("a", "b")
