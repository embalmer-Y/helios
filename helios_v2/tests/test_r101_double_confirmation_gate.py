"""R101 T4: FirstVersionDoubleConfirmationGate tests."""

from __future__ import annotations

import pytest

from helios_v2.memory import (
    FirstVersionDoubleConfirmationGate,
    OBJECTIVE_PASS_THRESHOLD,
    SUBJECTIVE_PASS_THRESHOLD,
    MemoryAffectReplayError,
)


def test_both_pass_when_both_above_threshold() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.7, subjective_score=0.7, subjective_confidence=1.0, outcome_class="executed")
    assert r.classification == "both_pass"


def test_objective_only_when_only_objective_above() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.7, subjective_score=0.3, subjective_confidence=0.5, outcome_class="executed")
    assert r.classification == "objective_only"


def test_subjective_only_when_only_subjective_above() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.3, subjective_score=0.7, subjective_confidence=0.8, outcome_class="executed")
    assert r.classification == "subjective_only"


def test_skip_when_both_below() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.3, subjective_score=0.3, subjective_confidence=0.5, outcome_class="executed")
    assert r.classification == "skip"


def test_boundary_just_at_objective_threshold() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    # objective_score = 0.50 exactly -> obj_pass = True
    r = gate.evaluate(objective_score=OBJECTIVE_PASS_THRESHOLD, subjective_score=0.7, subjective_confidence=0.5, outcome_class="executed")
    assert r.classification == "both_pass"


def test_boundary_just_below_objective_threshold() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(
        objective_score=OBJECTIVE_PASS_THRESHOLD - 0.01,
        subjective_score=0.7,
        subjective_confidence=0.5,
        outcome_class="executed",
    )
    assert r.classification == "subjective_only"


def test_boundary_just_at_subjective_threshold() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(
        objective_score=0.7,
        subjective_score=SUBJECTIVE_PASS_THRESHOLD,
        subjective_confidence=0.5,
        outcome_class="executed",
    )
    assert r.classification == "both_pass"


def test_boundary_just_below_subjective_threshold() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(
        objective_score=0.7,
        subjective_score=SUBJECTIVE_PASS_THRESHOLD - 0.01,
        subjective_confidence=0.5,
        outcome_class="executed",
    )
    assert r.classification == "objective_only"


def test_default_thresholds_match_constants() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    assert gate.threshold_objective == OBJECTIVE_PASS_THRESHOLD
    assert gate.threshold_subjective == SUBJECTIVE_PASS_THRESHOLD


def test_custom_thresholds() -> None:
    gate = FirstVersionDoubleConfirmationGate(threshold_objective=0.7, threshold_subjective=0.8)
    # With high thresholds, 0.6/0.6 should both fail
    r = gate.evaluate(objective_score=0.6, subjective_score=0.6, subjective_confidence=0.5, outcome_class="executed")
    assert r.classification == "skip"


def test_result_carries_input_scores() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(
        objective_score=0.55,
        subjective_score=0.65,
        subjective_confidence=0.9,
        outcome_class="self_changed",
    )
    assert r.objective_score == 0.55
    assert r.subjective_score == 0.65
    assert r.confidence == 0.9


def test_skip_with_zero_subjective() -> None:
    """Subjective absent -> subjective_score=0.0 -> only objective_only or skip possible."""
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.7, subjective_score=0.0, subjective_confidence=0.0, outcome_class="executed")
    assert r.classification == "objective_only"


def test_skip_with_zero_objective() -> None:
    gate = FirstVersionDoubleConfirmationGate()
    r = gate.evaluate(objective_score=0.0, subjective_score=0.7, subjective_confidence=1.0, outcome_class="executed")
    assert r.classification == "subjective_only"


def test_outcome_class_does_not_affect_decision() -> None:
    """R101 first-version gate: outcome_class is reserved for future use; doesn't affect decision."""
    gate = FirstVersionDoubleConfirmationGate()
    r1 = gate.evaluate(objective_score=0.7, subjective_score=0.7, subjective_confidence=1.0, outcome_class="executed")
    r2 = gate.evaluate(objective_score=0.7, subjective_score=0.7, subjective_confidence=1.0, outcome_class="self_changed")
    assert r1.classification == r2.classification == "both_pass"


def test_p5_threshold_replacement() -> None:
    """P5 hook: a learned gate can replace thresholds via constructor."""
    learned = FirstVersionDoubleConfirmationGate(threshold_objective=0.3, threshold_subjective=0.4)
    r = learned.evaluate(objective_score=0.35, subjective_score=0.45, subjective_confidence=0.5, outcome_class="executed")
    assert r.classification == "both_pass"