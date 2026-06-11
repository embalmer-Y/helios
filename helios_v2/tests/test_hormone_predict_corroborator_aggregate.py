"""R79-C T4: Verify HormonePredictCorroborator.aggregate_coupling_bias.

Owner: 04 neuromodulator (R79-C)
"""
from __future__ import annotations

from helios_v2.neuromodulation.contracts import NeuromodulatorLevels
from helios_v2.neuromodulation.corroborator import (
    HormonePredictCorroborator,
    HormonePredictCouplingChannel,
    HormonePredictCouplingClassification,
    HormonePredictCouplingConfig,
)


def _levels(value: float) -> NeuromodulatorLevels:
    return NeuromodulatorLevels(
        dopamine=value,
        norepinephrine=value,
        serotonin=value,
        acetylcholine=value,
        cortisol=value,
        oxytocin=value,
        opioid_tone=value,
        excitation=value,
        inhibition=value,
    )


def test_aggregate_empty_classifications_returns_all_zero_bias() -> None:
    """Empty classifications tuple must produce an all-zero bias vector."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    bias = corr.aggregate_coupling_bias(
        classifications=(),
        tonic_baseline=_levels(0.3),
        legal_min=_levels(0.0),
        legal_max=_levels(1.0),
    )
    assert bias["dopamine"] == 0.0
    assert bias["norepinephrine"] == 0.0
    assert bias["serotonin"] == 0.0
    assert bias["acetylcholine"] == 0.0
    assert bias["cortisol"] == 0.0
    assert bias["oxytocin"] == 0.0
    assert bias["opioid_tone"] == 0.0
    assert bias["excitation"] == 0.0
    assert bias["inhibition"] == 0.0


def test_aggregate_corroborate_emits_positive_bonus() -> None:
    """A corroborate classification must emit corroborate_bonus * magnitude on the right channel."""
    config = HormonePredictCouplingConfig(corroborate_bonus=0.1, conflict_penalty=-0.1)
    corr = HormonePredictCorroborator(config=config)
    classifications = (
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.SEROTONIN,
            verdict="corroborate",
            magnitude=0.5,
        ),
    )
    bias = corr.aggregate_coupling_bias(
        classifications=classifications,
        tonic_baseline=_levels(0.3),
        legal_min=_levels(0.0),
        legal_max=_levels(1.0),
    )
    # bias = 0.1 * 0.5 = 0.05
    assert bias["serotonin"] == pytest.approx(0.05)
    # Other channels stay at 0
    assert bias["dopamine"] == 0.0
    assert bias["oxytocin"] == 0.0


def test_aggregate_conflict_emits_negative_penalty() -> None:
    """A conflict classification must emit conflict_penalty * magnitude on the right channel."""
    config = HormonePredictCouplingConfig(corroborate_bonus=0.1, conflict_penalty=-0.1)
    corr = HormonePredictCorroborator(config=config)
    classifications = (
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.CORTISOL,
            verdict="conflict",
            magnitude=-0.5,
        ),
    )
    bias = corr.aggregate_coupling_bias(
        classifications=classifications,
        tonic_baseline=_levels(0.3),
        legal_min=_levels(0.0),
        legal_max=_levels(1.0),
    )
    # bias = -0.1 * (-0.5) = +0.05
    assert bias["cortisol"] == pytest.approx(0.05)


def test_aggregate_mixed_classifications_aggregates_per_channel() -> None:
    """Mixed corroborate/conflict/silent across multiple channels must aggregate correctly."""
    config = HormonePredictCouplingConfig(corroborate_bonus=0.1, conflict_penalty=-0.1)
    corr = HormonePredictCorroborator(config=config)
    classifications = (
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.DOPAMINE,
            verdict="corroborate",
            magnitude=0.5,
        ),
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.SEROTONIN,
            verdict="conflict",
            magnitude=0.4,
        ),
        # Note: silent classifications do not appear in the classifications tuple
        # (they are filtered out by classify_predict). So we only test corroborate
        # and conflict here. Silent = absence.
    )
    bias = corr.aggregate_coupling_bias(
        classifications=classifications,
        tonic_baseline=_levels(0.3),
        legal_min=_levels(0.0),
        legal_max=_levels(1.0),
    )
    # bias = 0.1 * 0.5 = 0.05 (dopamine, corroborate)
    assert bias["dopamine"] == pytest.approx(0.05)
    # bias = -0.1 * 0.4 = -0.04 (serotonin, conflict)
    assert bias["serotonin"] == pytest.approx(-0.04)
    # Other channels stay at 0
    assert bias["cortisol"] == 0.0


def test_aggregate_bias_clamps_to_legal_range() -> None:
    """Per-channel bias must be clamped to [legal_min - tonic_baseline, legal_max - tonic_baseline]."""
    # Configure a tight legal range and a large bonus to force a clamp.
    config = HormonePredictCouplingConfig(corroborate_bonus=0.2, conflict_penalty=-0.2)
    corr = HormonePredictCorroborator(config=config)
    classifications = (
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.OXYTOCIN,
            verdict="corroborate",
            magnitude=1.0,  # would yield bias = 0.2 * 1.0 = 0.2
        ),
    )
    # Tight range: legal_min = 0.0, legal_max = 0.4 -> bias clamp range = [-0.3, 0.1]
    bias = corr.aggregate_coupling_bias(
        classifications=classifications,
        tonic_baseline=_levels(0.3),
        legal_min=_levels(0.0),
        legal_max=_levels(0.4),
    )
    # bias = 0.2, but clamped to 0.4 - 0.3 = 0.1
    assert bias["oxytocin"] == pytest.approx(0.1)


import pytest  # noqa: E402  (import at end so other tests in this file don't need it)
