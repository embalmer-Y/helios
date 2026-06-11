"""R79-C T2: Verify HormonePredictCouplingConfig + Channel enum + Classification dataclass.

Owner: 04 neuromodulator (R79-C)
"""
from __future__ import annotations

import pytest

from helios_v2.neuromodulation.contracts import NeuromodulatorError
from helios_v2.neuromodulation.corroborator import (
    HormonePredictCouplingChannel,
    HormonePredictCouplingClassification,
    HormonePredictCouplingConfig,
)


def test_corroborate_bonus_too_high_rejected() -> None:
    """corroborate_bonus > 0.2 must be rejected."""
    with pytest.raises(NeuromodulatorError, match="corroborate_bonus"):
        HormonePredictCouplingConfig(corroborate_bonus=0.3)


def test_conflict_penalty_too_negative_rejected() -> None:
    """conflict_penalty < -0.2 must be rejected."""
    with pytest.raises(NeuromodulatorError, match="conflict_penalty"):
        HormonePredictCouplingConfig(conflict_penalty=-0.3)


def test_sign_match_tolerance_out_of_range_rejected() -> None:
    """sign_match_tolerance outside (0.0, 0.5] must be rejected (both 0 and > 0.5)."""
    with pytest.raises(NeuromodulatorError, match="sign_match_tolerance"):
        HormonePredictCouplingConfig(sign_match_tolerance=0.0)
    with pytest.raises(NeuromodulatorError, match="sign_match_tolerance"):
        HormonePredictCouplingConfig(sign_match_tolerance=0.6)


def test_magnitude_match_tolerance_out_of_range_rejected() -> None:
    """magnitude_match_tolerance outside (0.0, 0.5] must be rejected."""
    with pytest.raises(NeuromodulatorError, match="magnitude_match_tolerance"):
        HormonePredictCouplingConfig(magnitude_match_tolerance=0.0)
    with pytest.raises(NeuromodulatorError, match="magnitude_match_tolerance"):
        HormonePredictCouplingConfig(magnitude_match_tolerance=0.6)


def test_default_config_constructs() -> None:
    """Default config must construct without error (sanity check)."""
    config = HormonePredictCouplingConfig()
    assert config.corroborate_bonus == 0.05
    assert config.conflict_penalty == -0.05
    assert config.sign_match_tolerance == 0.1
    assert config.magnitude_match_tolerance == 0.2


def test_channel_enum_values_match_neuromodulator_levels_fields() -> None:
    """Each enum member's .value must match a NeuromodulatorLevels field name."""
    from helios_v2.neuromodulation.contracts import NeuromodulatorLevels

    field_names = set(NeuromodulatorLevels.__dataclass_fields__.keys())
    enum_values = {member.value for member in HormonePredictCouplingChannel}
    assert field_names == enum_values, (
        f"Enum values {enum_values} do not match NeuromodulatorLevels fields {field_names}"
    )


def test_classification_rejects_invalid_verdict() -> None:
    """Classification with a verdict outside the 3 valid values must be rejected."""
    with pytest.raises(NeuromodulatorError, match="verdict"):
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.DOPAMINE,
            verdict="unknown",
            magnitude=0.5,
        )


def test_classification_rejects_magnitude_out_of_range() -> None:
    """Classification magnitude must be in [-1.0, 1.0]."""
    with pytest.raises(NeuromodulatorError, match="magnitude"):
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.DOPAMINE,
            verdict="corroborate",
            magnitude=1.5,
        )
    with pytest.raises(NeuromodulatorError, match="magnitude"):
        HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.DOPAMINE,
            verdict="corroborate",
            magnitude=-1.5,
        )


def test_classification_accepts_boundary_magnitudes() -> None:
    """Magnitudes at -1.0 and +1.0 must be accepted (closed interval)."""
    for m in (-1.0, +1.0, 0.0):
        c = HormonePredictCouplingClassification(
            channel=HormonePredictCouplingChannel.DOPAMINE,
            verdict="silent",
            magnitude=m,
        )
        assert c.magnitude == m
