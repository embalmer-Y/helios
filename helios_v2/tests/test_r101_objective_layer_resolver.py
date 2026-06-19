"""R101 T5: ObjectiveImportanceLayerResolver + FirstVersionRecallUtilityTracker tests."""

from __future__ import annotations

import pytest

from helios_v2.memory import (
    DEMOTE_THRESHOLD,
    DoubleConfirmationResult,
    FirstVersionRecallUtilityTracker,
    MemoryAffectReplayError,
    MemoryContentPacket,
    MemoryFamily,
    MemoryLayer,
    MemoryRecord,
    ObjectiveImportanceLayerResolver,
    PROMOTE_THRESHOLD,
    RECALL_EMA_ALPHA,
)


def _make_record(layer: MemoryLayer = "L3_short") -> MemoryRecord:
    return MemoryRecord(
        memory_id="m1",
        layer=layer,
        affect_intensity_at_write=0.5,
        outcome_class_at_write="executed",
        source_feeling_state_id="f1",
        family="episodic",
        content=MemoryContentPacket(
            content_kind="perceived-stimulus-summary",
            summary_ref="s1",
            context_ref=None,
            salient_tokens=("hello",),
        ),
        binding_context_id="c1",
        tick_id=1,
        created_at_wall=1234567890.0,
    )


# =============================================================================
# ObjectiveImportanceLayerResolver tests
# =============================================================================


def test_skip_always_returns_L2_working() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L5_autobiographical",
        objective_score=0.95,
        double_confirmation_class="skip",
        outcome_class="self_changed",
    )
    assert result == "L2_working"


def test_no_r101_signals_preserves_initial_layer() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L4_long",
        objective_score=None,
        double_confirmation_class=None,
        outcome_class="executed",
    )
    assert result == "L4_long"


def test_both_pass_keeps_L5() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L5_autobiographical",
        objective_score=0.95,
        double_confirmation_class="both_pass",
        outcome_class="self_changed",
    )
    assert result == "L5_autobiographical"


def test_both_pass_keeps_L4() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L4_long",
        objective_score=0.95,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L4_long"


def test_both_pass_promotes_L3_to_L4() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L3_short",
        objective_score=PROMOTE_THRESHOLD + 0.01,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L4_long"


def test_both_pass_keeps_L3_below_promote_threshold() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L3_short",
        objective_score=PROMOTE_THRESHOLD - 0.05,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L3_short"


def test_both_pass_promotes_L2_to_L5_for_self_changed() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L2_working",
        objective_score=DEMOTE_THRESHOLD + 0.01,
        double_confirmation_class="both_pass",
        outcome_class="self_changed",
    )
    assert result == "L5_autobiographical"


def test_both_pass_does_not_promote_L2_for_non_identity_outcome() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L2_working",
        objective_score=DEMOTE_THRESHOLD + 0.01,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L2_working"


def test_objective_only_demotes_L5_to_L4_below_demote_threshold() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L5_autobiographical",
        objective_score=DEMOTE_THRESHOLD - 0.01,
        double_confirmation_class="objective_only",
        outcome_class="self_changed",
    )
    assert result == "L4_long"


def test_objective_only_demotes_L4_to_L3_below_promote_threshold() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L4_long",
        objective_score=PROMOTE_THRESHOLD - 0.01,
        double_confirmation_class="objective_only",
        outcome_class="executed",
    )
    assert result == "L3_short"


def test_objective_only_keeps_L4_above_promote_threshold() -> None:
    r = ObjectiveImportanceLayerResolver()
    result = r.resolve(
        initial_layer="L4_long",
        objective_score=PROMOTE_THRESHOLD + 0.1,
        double_confirmation_class="objective_only",
        outcome_class="executed",
    )
    assert result == "L4_long"


def test_subjective_only_preserves_initial_layer() -> None:
    r = ObjectiveImportanceLayerResolver()
    for initial in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
        result = r.resolve(
            initial_layer=initial,
            objective_score=0.5,
            double_confirmation_class="subjective_only",
            outcome_class="executed",
        )
        assert result == initial


def test_default_thresholds_match_constants() -> None:
    r = ObjectiveImportanceLayerResolver()
    assert r.promote_threshold == PROMOTE_THRESHOLD
    assert r.demote_threshold == DEMOTE_THRESHOLD


def test_custom_thresholds() -> None:
    r = ObjectiveImportanceLayerResolver(promote_threshold=0.5, demote_threshold=0.95)
    # With promote=0.5, L3 + obj=0.55 should promote to L4
    result = r.resolve(
        initial_layer="L3_short",
        objective_score=0.55,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L4_long"


def test_p5_threshold_replacement() -> None:
    """P5 hook: a learned resolver can replace thresholds via constructor."""
    learned = ObjectiveImportanceLayerResolver(promote_threshold=0.4, demote_threshold=0.6)
    # L3 + obj=0.5 -> promote to L4 (with learned threshold 0.4)
    result = learned.resolve(
        initial_layer="L3_short",
        objective_score=0.5,
        double_confirmation_class="both_pass",
        outcome_class="executed",
    )
    assert result == "L4_long"


# =============================================================================
# FirstVersionRecallUtilityTracker tests
# =============================================================================


def test_record_recall_increments_count() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    updated = tracker.record_recall(rec, current_tick=5)
    assert updated.recall_count == 1
    assert updated.last_recall_at_tick == 5


def test_record_recall_multiple_times() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    updated = tracker.record_recall(rec, current_tick=5)
    updated = tracker.record_recall(updated, current_tick=10)
    updated = tracker.record_recall(updated, current_tick=15)
    assert updated.recall_count == 3
    assert updated.last_recall_at_tick == 15


def test_record_recall_returns_new_instance() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    updated = tracker.record_recall(rec, current_tick=5)
    assert updated is not rec  # immutable, returns new instance


def test_record_utility_initializes_from_none() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    updated = tracker.record_utility(rec, utility=0.8, current_tick=2)
    assert updated.recall_utility_score == 0.8


def test_record_utility_uses_ema() -> None:
    tracker = FirstVersionRecallUtilityTracker(ema_alpha=0.5)
    rec = _make_record()
    rec1 = tracker.record_utility(rec, utility=1.0, current_tick=1)
    assert rec1.recall_utility_score == 1.0
    rec2 = tracker.record_utility(rec1, utility=0.0, current_tick=2)
    # EMA: 0.5 * 0.0 + 0.5 * 1.0 = 0.5
    assert rec2.recall_utility_score == pytest.approx(0.5)
    rec3 = tracker.record_utility(rec2, utility=0.0, current_tick=3)
    # EMA: 0.5 * 0.0 + 0.5 * 0.5 = 0.25
    assert rec3.recall_utility_score == pytest.approx(0.25)


def test_record_utility_default_alpha() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    assert tracker.ema_alpha == RECALL_EMA_ALPHA
    assert tracker.ema_alpha == 0.3


def test_record_utility_clamps_to_unit_interval() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    rec1 = tracker.record_utility(rec, utility=1.0, current_tick=1)
    rec2 = tracker.record_utility(rec1, utility=1.0, current_tick=2)
    # EMA approaches 1.0 but never exceeds
    assert 0.0 <= rec2.recall_utility_score <= 1.0


def test_record_utility_rejects_out_of_range() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    with pytest.raises(MemoryAffectReplayError):
        tracker.record_utility(rec, utility=1.5, current_tick=1)
    with pytest.raises(MemoryAffectReplayError):
        tracker.record_utility(rec, utility=-0.1, current_tick=1)


def test_record_recall_then_utility_combines() -> None:
    tracker = FirstVersionRecallUtilityTracker()
    rec = _make_record()
    rec1 = tracker.record_recall(rec, current_tick=5)
    rec2 = tracker.record_utility(rec1, utility=0.6, current_tick=6)
    assert rec2.recall_count == 1
    assert rec2.last_recall_at_tick == 6  # utility updates last_recall_at_tick
    assert rec2.recall_utility_score == 0.6