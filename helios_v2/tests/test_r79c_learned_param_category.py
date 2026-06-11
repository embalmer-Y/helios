"""R79-C T1: Verify the 5th LearnedParameterCategory literal 'hormone_predict_coupling'
is accepted and required by NeuromodulatorConfig.__post_init__.

Owner: 04 neuromodulator (R79-C)
"""
from __future__ import annotations

import pytest

from helios_v2.neuromodulation.contracts import (
    LearnedParameterCategory,
    NeuromodulatorConfig,
    NeuromodulatorError,
    NeuromodulatorLevels,
)


def _build_levels(value: float) -> NeuromodulatorLevels:
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


def _build_config_with_categories(
    categories: tuple[str, ...],
) -> NeuromodulatorConfig:
    return NeuromodulatorConfig(
        tonic_baseline=_build_levels(0.3),
        legal_min=_build_levels(0.0),
        legal_max=_build_levels(1.0),
        mandatory_learned_parameters=categories,
    )


def test_learned_param_category_literal_accepts_hormone_predict_coupling() -> None:
    """The Literal type must accept 'hormone_predict_coupling' as a value."""
    # Runtime assertion: passing it must work and the field must round-trip.
    config = _build_config_with_categories(
        (
            "channel_gain_sensitivity",
            "cross_channel_coupling_strength",
            "decay_speed_persistence",
            "gate_influence_strength",
            "hormone_predict_coupling",
        )
    )
    assert "hormone_predict_coupling" in config.mandatory_learned_parameters


def test_learned_param_category_rejects_missing_hormone_predict_coupling() -> None:
    """Any mandatory_learned_parameters tuple missing 'hormone_predict_coupling'
    must be rejected with a clear NeuromodulatorError."""
    with pytest.raises(NeuromodulatorError, match="mandatory learned-parameter categories"):
        _build_config_with_categories(
            (
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
                "gate_influence_strength",
                # missing "hormone_predict_coupling"
            )
        )


def test_learned_param_category_rejects_extra_unknown_category() -> None:
    """A tuple with the 5th category plus an extra unknown must be rejected."""
    with pytest.raises(NeuromodulatorError, match="mandatory learned-parameter categories"):
        _build_config_with_categories(
            (
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
                "gate_influence_strength",
                "hormone_predict_coupling",
                "some_future_unknown_category",
            )
        )


def test_learned_param_category_rejects_hormone_predict_coupling_alone() -> None:
    """A tuple with only the new category (and missing the 4 legacy) must be rejected."""
    with pytest.raises(NeuromodulatorError, match="mandatory learned-parameter categories"):
        _build_config_with_categories(
            (
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
                "gate_influence_strength",
                # no hormone_predict_coupling
                # tuple is the 4 legacy only
            )[:0] + ("hormone_predict_coupling",)
        )
