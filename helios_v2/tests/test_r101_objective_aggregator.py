"""R101 T2: ConvexWeightedObjectiveAggregator tests."""

from __future__ import annotations

import pytest

from helios_v2.memory import (
    ConvexWeightedObjectiveAggregator,
    DEFAULT_OBJECTIVE_WEIGHTS,
    MemoryAffectReplayError,
    ObjectiveImportanceVector,
)


def _vec(stim=0.5, cort=0.5, arous=0.5, oc=0.5, nov=0.5, rr=0.5) -> ObjectiveImportanceVector:
    return ObjectiveImportanceVector(
        stimulus_intensity=stim,
        cortisol_response=cort,
        arousal_response=arous,
        outcome_class_weight=oc,
        novelty_score=nov,
        relationship_risk=rr,
    )


def test_default_weights_sum_to_one() -> None:
    agg = ConvexWeightedObjectiveAggregator()
    assert sum(DEFAULT_OBJECTIVE_WEIGHTS) == pytest.approx(1.0)
    assert agg.declared_weights() == DEFAULT_OBJECTIVE_WEIGHTS


def test_weights_must_have_length_6() -> None:
    with pytest.raises(MemoryAffectReplayError):
        ConvexWeightedObjectiveAggregator(weights=(0.5, 0.5))
    with pytest.raises(MemoryAffectReplayError):
        ConvexWeightedObjectiveAggregator(weights=(0.2, 0.2, 0.2, 0.2, 0.2))  # length 5


def test_weights_must_sum_to_one_within_epsilon() -> None:
    # Sum too high
    with pytest.raises(MemoryAffectReplayError):
        ConvexWeightedObjectiveAggregator(weights=(0.3, 0.3, 0.3, 0.3, 0.3, 0.0))
    # Sum too low
    with pytest.raises(MemoryAffectReplayError):
        ConvexWeightedObjectiveAggregator(weights=(0.1, 0.1, 0.1, 0.1, 0.1, 0.1))


def test_weights_epsilon_tolerance() -> None:
    # Sum within 1e-6 should pass
    ConvexWeightedObjectiveAggregator(weights=(1/6, 1/6, 1/6, 1/6, 1/6 - 1e-7, 1/6 + 1e-7))


def test_weights_must_be_non_negative() -> None:
    with pytest.raises(MemoryAffectReplayError):
        ConvexWeightedObjectiveAggregator(weights=(-0.1, 0.2, 0.2, 0.2, 0.2, 0.3))


def test_aggregate_default_weights() -> None:
    agg = ConvexWeightedObjectiveAggregator()
    v = _vec(stim=1.0, cort=1.0, arous=1.0, oc=1.0, nov=1.0, rr=1.0)
    # All 1.0 -> 1.0 (sum of weights)
    assert agg.aggregate(v) == pytest.approx(1.0)


def test_aggregate_all_zeros() -> None:
    agg = ConvexWeightedObjectiveAggregator()
    v = _vec(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert agg.aggregate(v) == pytest.approx(0.0)


def test_aggregate_weighted_contribution() -> None:
    # Use simple weights to verify computation
    agg = ConvexWeightedObjectiveAggregator(weights=(0.6, 0.4, 0.0, 0.0, 0.0, 0.0))
    v = _vec(stim=0.5, cort=0.5, arous=1.0, oc=1.0, nov=1.0, rr=1.0)
    # 0.6*0.5 + 0.4*0.5 = 0.5
    assert agg.aggregate(v) == pytest.approx(0.5)


def test_aggregate_output_clamped_to_unit_interval() -> None:
    agg = ConvexWeightedObjectiveAggregator(weights=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    # Test upper bound
    assert agg.aggregate(_vec(stim=1.0, cort=0.5, arous=0.5, oc=0.5, nov=0.5, rr=0.5)) == pytest.approx(1.0)
    # Test lower bound
    assert agg.aggregate(_vec(stim=0.0, cort=0.5, arous=0.5, oc=0.5, nov=0.5, rr=0.5)) == pytest.approx(0.0)


def test_aggregate_rejects_non_vector_input() -> None:
    agg = ConvexWeightedObjectiveAggregator()
    with pytest.raises(MemoryAffectReplayError):
        agg.aggregate("not a vector")


def test_declared_weights_returns_immutable_tuple() -> None:
    agg = ConvexWeightedObjectiveAggregator(weights=(0.5, 0.1, 0.1, 0.1, 0.1, 0.1))
    weights = agg.declared_weights()
    assert weights == (0.5, 0.1, 0.1, 0.1, 0.1, 0.1)
    assert isinstance(weights, tuple)


def test_p5_introspection_weights_length_matches_vector() -> None:
    """P5 hook: declared_weights() length must equal vector dimensionality (6)."""
    agg = ConvexWeightedObjectiveAggregator()
    assert len(agg.declared_weights()) == 6