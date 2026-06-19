"""R101 T3: FirstVersionObjectiveImportanceEstimator tests."""

from __future__ import annotations

import pytest

from helios_v2.memory import (
    FirstVersionObjectiveImportanceEstimator,
    ObjectiveImportanceVector,
    OUTCOME_CLASS_WEIGHTS,
    OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT,
)


def test_estimate_empty_stimulus_yields_zero_intensity() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="",
        hormone_snapshot=None,
        feeling_snapshot=None,
        outcome_class="no_outcome",
    )
    assert v.stimulus_intensity == 0.0


def test_estimate_short_stimulus_proportional_intensity() -> None:
    est = FirstVersionObjectiveImportanceEstimator(stimulus_length_cap=200)
    v = est.estimate(stimulus_text="a" * 100, hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.stimulus_intensity == pytest.approx(0.5)


def test_estimate_long_stimulus_caps_at_one() -> None:
    est = FirstVersionObjectiveImportanceEstimator(stimulus_length_cap=200)
    v = est.estimate(stimulus_text="x" * 500, hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.stimulus_intensity == pytest.approx(1.0)


def test_estimate_cortisol_from_hormone_snapshot() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="test",
        hormone_snapshot={"cortisol": 0.85},
        feeling_snapshot=None,
        outcome_class="no_outcome",
    )
    assert v.cortisol_response == pytest.approx(0.85)


def test_estimate_cortisol_missing_uses_default() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="test", hormone_snapshot={}, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.cortisol_response == 0.5


def test_estimate_cortisol_hormone_snapshot_none_uses_default() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="test", hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.cortisol_response == 0.5


def test_estimate_cortisol_non_numeric_uses_default() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="test",
        hormone_snapshot={"cortisol": "not_a_number"},
        feeling_snapshot=None,
        outcome_class="no_outcome",
    )
    assert v.cortisol_response == 0.5


def test_estimate_arousal_from_feeling_snapshot() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="test",
        hormone_snapshot=None,
        feeling_snapshot={"arousal": 0.7},
        outcome_class="no_outcome",
    )
    assert v.arousal_response == pytest.approx(0.7)


def test_estimate_outcome_class_weight_known() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="self_changed")
    assert v.outcome_class_weight == pytest.approx(0.95)


def test_estimate_outcome_class_weight_unknown_uses_neutral() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="mystery_outcome")
    assert v.outcome_class_weight == OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT


def test_estimate_outcome_class_weight_no_outcome() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.outcome_class_weight == OUTCOME_CLASS_WEIGHTS["no_outcome"]


def test_estimate_novelty_neutral_when_no_recent_summaries() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.novelty_score == 0.5


def test_estimate_novelty_neutral_when_no_embed_callable() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="x",
        hormone_snapshot=None,
        feeling_snapshot=None,
        outcome_class="no_outcome",
        recent_summaries=["something"],
        embed_callable=None,
    )
    assert v.novelty_score == 0.5


def test_estimate_novelty_with_perfect_match_returns_zero() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    def embed(s: str):
        return [1.0, 0.0, 0.0]
    v = est.estimate(
        stimulus_text="x",
        hormone_snapshot=None,
        feeling_snapshot=None,
        outcome_class="no_outcome",
        recent_summaries=["y"],
        embed_callable=embed,
    )
    # Both embedded as [1.0, 0.0, 0.0] -> cosine = 1.0 -> novelty = 0.0
    assert v.novelty_score == pytest.approx(0.0)


def test_estimate_novelty_with_orthogonal_match_returns_one() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    def embed(s: str):
        if "x" in s:
            return [1.0, 0.0]
        return [0.0, 1.0]
    v = est.estimate(
        stimulus_text="x",
        hormone_snapshot=None,
        feeling_snapshot=None,
        outcome_class="no_outcome",
        recent_summaries=["y"],
        embed_callable=embed,
    )
    # orthogonal vectors -> cosine = 0 -> novelty = 1.0
    assert v.novelty_score == pytest.approx(1.0)


def test_estimate_relationship_risk_inverse_of_social_safety() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="x",
        hormone_snapshot=None,
        feeling_snapshot={"social_safety": 0.8},
        outcome_class="no_outcome",
    )
    assert v.relationship_risk == pytest.approx(0.2)


def test_estimate_relationship_risk_missing_uses_default() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert v.relationship_risk == pytest.approx(0.5)  # 1.0 - 0.5 default


def test_estimate_returns_objective_importance_vector_type() -> None:
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(stimulus_text="x", hormone_snapshot=None, feeling_snapshot=None, outcome_class="no_outcome")
    assert isinstance(v, ObjectiveImportanceVector)


def test_estimate_clamped_to_unit_interval() -> None:
    """Even if upstream signals are out-of-range, output must be clamped."""
    est = FirstVersionObjectiveImportanceEstimator()
    v = est.estimate(
        stimulus_text="x",
        hormone_snapshot={"cortisol": 5.0},  # way out of range
        feeling_snapshot={"arousal": -3.0, "social_safety": 100.0},
        outcome_class="no_outcome",
    )
    # _safe_get clamps to [0, 1] before reading
    assert 0.0 <= v.cortisol_response <= 1.0
    assert 0.0 <= v.arousal_response <= 1.0
    assert 0.0 <= v.relationship_risk <= 1.0