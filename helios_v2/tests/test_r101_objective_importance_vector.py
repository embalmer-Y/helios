"""R101 T1: ObjectiveImportanceVector + OUTCOME_CLASS_WEIGHTS + DoubleConfirmationResult + PromotionEvent tests."""

from __future__ import annotations

import pytest

from helios_v2.memory import (
    DoubleConfirmationClass,
    DoubleConfirmationResult,
    MemoryAffectReplayError,
    MemoryContentPacket,
    MemoryFamily,
    ObjectiveImportanceVector,
    OUTCOME_CLASS_WEIGHTS,
    OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT,
    PromotionEvent,
    VALID_MEMORY_LAYERS,
)


def _valid_vector() -> ObjectiveImportanceVector:
    return ObjectiveImportanceVector(
        stimulus_intensity=0.5,
        cortisol_response=0.4,
        arousal_response=0.6,
        outcome_class_weight=0.7,
        novelty_score=0.8,
        relationship_risk=0.3,
    )


def test_valid_vector_construction_succeeds() -> None:
    v = _valid_vector()
    assert v.stimulus_intensity == 0.5
    assert v.cortisol_response == 0.4
    assert v.arousal_response == 0.6
    assert v.outcome_class_weight == 0.7
    assert v.novelty_score == 0.8
    assert v.relationship_risk == 0.3


@pytest.mark.parametrize("field,value", [
    ("stimulus_intensity", -0.01),
    ("stimulus_intensity", 1.01),
    ("cortisol_response", -0.5),
    ("cortisol_response", 1.5),
    ("arousal_response", -0.1),
    ("arousal_response", 1.1),
    ("outcome_class_weight", -0.01),
    ("outcome_class_weight", 1.01),
    ("novelty_score", -0.5),
    ("novelty_score", 1.5),
    ("relationship_risk", -0.01),
    ("relationship_risk", 1.01),
])
def test_vector_field_out_of_range_raises(field: str, value: float) -> None:
    kwargs = {
        "stimulus_intensity": 0.5,
        "cortisol_response": 0.4,
        "arousal_response": 0.6,
        "outcome_class_weight": 0.7,
        "novelty_score": 0.8,
        "relationship_risk": 0.3,
    }
    kwargs[field] = value
    with pytest.raises(MemoryAffectReplayError):
        ObjectiveImportanceVector(**kwargs)


def test_vector_boundary_values_accepted() -> None:
    ObjectiveImportanceVector(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    ObjectiveImportanceVector(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def test_vector_to_json_roundtrip() -> None:
    v = _valid_vector()
    j = v.to_json()
    v2 = ObjectiveImportanceVector.from_json(j)
    assert v == v2


def test_vector_to_json_is_deterministic() -> None:
    v = _valid_vector()
    j1 = v.to_json()
    j2 = v.to_json()
    assert j1 == j2  # sort_keys=True ensures determinism


def test_from_json_malformed_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        ObjectiveImportanceVector.from_json("not valid json")


def test_from_json_missing_field_raises() -> None:
    incomplete = '{"stimulus_intensity": 0.5}'
    with pytest.raises(MemoryAffectReplayError):
        ObjectiveImportanceVector.from_json(incomplete)


def test_outcome_class_weights_covers_taxonomy() -> None:
    expected_keys = {
        "self_changed", "world_changed", "continuity_written",
        "executed", "rejected", "blocked",
        "internal_only_decision", "no_outcome",
    }
    assert set(OUTCOME_CLASS_WEIGHTS.keys()) == expected_keys
    assert OUTCOME_CLASS_WEIGHTS["self_changed"] == 0.95
    assert OUTCOME_CLASS_WEIGHTS["no_outcome"] == 0.20


def test_outcome_class_weights_immutable() -> None:
    with pytest.raises(TypeError):
        OUTCOME_CLASS_WEIGHTS["self_changed"] = 1.0  # type: ignore[index]


def test_outcome_class_weights_unknown_returns_neutral() -> None:
    weight = OUTCOME_CLASS_WEIGHTS.get("unknown_class", OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT)
    assert weight == OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT
    assert weight == 0.5


# =============================================================================
# DoubleConfirmationResult tests
# =============================================================================


def test_double_confirmation_result_construction() -> None:
    r = DoubleConfirmationResult(
        classification="both_pass",
        objective_score=0.7,
        subjective_score=0.8,
        confidence=1.0,
    )
    assert r.classification == "both_pass"
    assert r.objective_score == 0.7
    assert r.subjective_score == 0.8
    assert r.confidence == 1.0


@pytest.mark.parametrize("cls", ["both_pass", "objective_only", "subjective_only", "skip"])
def test_double_confirmation_result_all_classes_accepted(cls: DoubleConfirmationClass) -> None:
    r = DoubleConfirmationResult(classification=cls, objective_score=0.5, subjective_score=0.5, confidence=0.5)
    assert r.classification == cls


def test_double_confirmation_result_invalid_class_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        DoubleConfirmationResult(classification="invalid", objective_score=0.5, subjective_score=0.5, confidence=0.5)


def test_double_confirmation_result_out_of_range_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        DoubleConfirmationResult(classification="both_pass", objective_score=1.5, subjective_score=0.5, confidence=0.5)
    with pytest.raises(MemoryAffectReplayError):
        DoubleConfirmationResult(classification="both_pass", objective_score=0.5, subjective_score=-0.1, confidence=0.5)
    with pytest.raises(MemoryAffectReplayError):
        DoubleConfirmationResult(classification="both_pass", objective_score=0.5, subjective_score=0.5, confidence=1.5)


# =============================================================================
# PromotionEvent tests
# =============================================================================


def test_promotion_event_construction() -> None:
    e = PromotionEvent(
        event_id="evt-1",
        from_layer="L3_short",
        to_layer="L4_long",
        tick_id=42,
        wall_seconds=1234567890.0,
        reason="recall_count_threshold",
    )
    assert e.event_id == "evt-1"
    assert e.from_layer == "L3_short"
    assert e.to_layer == "L4_long"
    assert e.tick_id == 42
    assert e.wall_seconds == 1234567890.0
    assert e.reason == "recall_count_threshold"


def test_promotion_event_invalid_layer_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        PromotionEvent(event_id="e1", from_layer="invalid", to_layer="L4_long", tick_id=1, wall_seconds=None, reason="r")
    with pytest.raises(MemoryAffectReplayError):
        PromotionEvent(event_id="e1", from_layer="L3_short", to_layer="invalid", tick_id=1, wall_seconds=None, reason="r")


def test_promotion_event_empty_event_id_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        PromotionEvent(event_id="", from_layer="L3_short", to_layer="L4_long", tick_id=1, wall_seconds=None, reason="r")


def test_promotion_event_empty_reason_raises() -> None:
    with pytest.raises(MemoryAffectReplayError):
        PromotionEvent(event_id="e1", from_layer="L3_short", to_layer="L4_long", tick_id=1, wall_seconds=None, reason="")


# =============================================================================
# Valid MemoryLayer set check
# =============================================================================


def test_valid_memory_layers_includes_all_four() -> None:
    assert VALID_MEMORY_LAYERS == frozenset({"L2_working", "L3_short", "L4_long", "L5_autobiographical"})