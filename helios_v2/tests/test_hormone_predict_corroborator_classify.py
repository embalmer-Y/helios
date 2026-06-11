"""R79-C T3: Verify HormonePredictCorroborator.classify_predict.

Owner: 04 neuromodulator (R79-C)
"""
from __future__ import annotations

from helios_v2.neuromodulation.contracts import NeuromodulatorLevels
from helios_v2.neuromodulation.corroborator import (
    HormonePredictCorroborator,
    HormonePredictCouplingChannel,
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


def _channel_value(classifications, channel: HormonePredictCouplingChannel):
    """Return the verdict for `channel` from `classifications` (or 'absent')."""
    for c in classifications:
        if c.channel == channel:
            return c.verdict
    return "absent"


# --- 3 silent paths ---


def test_classify_empty_predict_returns_empty_tuple() -> None:
    """Empty predict dict must produce zero classifications (silent across the board)."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    result = corr.classify_predict(formula_drive, {}, tonic)
    assert result == ()


def test_classify_none_predict_returns_empty_tuple() -> None:
    """None predict must produce zero classifications."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    result = corr.classify_predict(formula_drive, None, tonic)
    assert result == ()


def test_classify_all_zero_predict_values_returns_empty_tuple() -> None:
    """Predict values all 0.0 must produce zero classifications."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    predict = {ch.value: 0.0 for ch in HormonePredictCouplingChannel}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert result == ()


# --- 3 corroborate paths ---


def test_classify_sign_match_magnitude_match_emits_corroborate() -> None:
    """Sign match + exact magnitude match must emit 'corroborate'."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    # drive_value = 0.5 - 0.3 = 0.2 (positive), predict_value = +0.2 (positive)
    # |drive - predict| = 0.0 <= 0.2 -> corroborate
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    predict = {"dopamine": 0.2}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert len(result) == 1
    assert result[0].channel == HormonePredictCouplingChannel.DOPAMINE
    assert result[0].verdict == "corroborate"
    assert result[0].magnitude == 0.2


def test_classify_sign_match_magnitude_within_tolerance_emits_corroborate() -> None:
    """Sign match + magnitude within tolerance must emit 'corroborate'."""
    config = HormonePredictCouplingConfig(magnitude_match_tolerance=0.2)
    corr = HormonePredictCorroborator(config=config)
    # drive = 0.5 - 0.3 = 0.2, predict = 0.1
    # |0.2 - 0.1| = 0.1 <= 0.2 -> corroborate
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    predict = {"dopamine": 0.1}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert len(result) == 1
    assert result[0].verdict == "corroborate"
    assert result[0].magnitude == 0.1


def test_classify_sign_match_magnitude_beyond_tolerance_emits_silent() -> None:
    """Sign match + magnitude beyond tolerance must emit 'silent' (absent)."""
    config = HormonePredictCouplingConfig(magnitude_match_tolerance=0.05)
    corr = HormonePredictCorroborator(config=config)
    # drive = 0.5 - 0.3 = 0.2, predict = -0.1 (sign match: both positive)
    # |0.2 - 0.1| = 0.1 > 0.05 -> silent
    formula_drive = _levels(0.5)
    tonic = _levels(0.3)
    predict = {"dopamine": 0.1}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert _channel_value(result, HormonePredictCouplingChannel.DOPAMINE) == "absent"


# --- 3 conflict paths ---


def test_classify_sign_mismatch_magnitude_match_emits_conflict() -> None:
    """Sign mismatch + magnitude match must emit 'conflict'."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    # drive = 0.3 - 0.5 = -0.2 (negative), predict = +0.2 (positive)
    # sign mismatch, |drive + predict| = |0.0| = 0.0 <= 0.2 -> conflict
    formula_drive = _levels(0.3)
    tonic = _levels(0.5)
    predict = {"dopamine": 0.2}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert len(result) == 1
    assert result[0].channel == HormonePredictCouplingChannel.DOPAMINE
    assert result[0].verdict == "conflict"
    assert result[0].magnitude == 0.2


def test_classify_sign_mismatch_magnitude_within_tolerance_emits_conflict() -> None:
    """Sign mismatch + magnitude within tolerance must emit 'conflict'."""
    config = HormonePredictCouplingConfig(magnitude_match_tolerance=0.2)
    corr = HormonePredictCorroborator(config=config)
    # drive = 0.3 - 0.5 = -0.2, predict = +0.1
    # |(-0.2) + 0.1| = 0.1 <= 0.2 -> conflict
    formula_drive = _levels(0.3)
    tonic = _levels(0.5)
    predict = {"dopamine": 0.1}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert len(result) == 1
    assert result[0].verdict == "conflict"
    assert result[0].magnitude == 0.1


def test_classify_sign_mismatch_magnitude_beyond_tolerance_emits_silent() -> None:
    """Sign mismatch + magnitude beyond tolerance must emit 'silent' (absent)."""
    config = HormonePredictCouplingConfig(magnitude_match_tolerance=0.05)
    corr = HormonePredictCorroborator(config=config)
    # drive = 0.3 - 0.5 = -0.2, predict = +0.1
    # |(-0.2) + 0.1| = 0.1 > 0.05 -> silent
    formula_drive = _levels(0.3)
    tonic = _levels(0.5)
    predict = {"dopamine": 0.1}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert _channel_value(result, HormonePredictCouplingChannel.DOPAMINE) == "absent"


# --- Drive-zero edge case ---


def test_classify_drive_zero_with_predict_nonzero_emits_silent() -> None:
    """When formula drive is zero (drive_value == 0) but predict is non-zero,
    the corroborator must emit 'silent' (do not bias a stationary channel)."""
    config = HormonePredictCouplingConfig()
    corr = HormonePredictCorroborator(config=config)
    # drive_value = 0.4 - 0.4 = 0.0 -> drive_sign = 0 -> silent
    formula_drive = _levels(0.4)
    tonic = _levels(0.4)
    predict = {"dopamine": 0.5}
    result = corr.classify_predict(formula_drive, predict, tonic)
    assert _channel_value(result, HormonePredictCouplingChannel.DOPAMINE) == "absent"
