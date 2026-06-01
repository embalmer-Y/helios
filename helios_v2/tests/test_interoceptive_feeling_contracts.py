from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.feeling import (
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingError,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
    validate_internal_body_signal,
)
from helios_v2.sensory import Stimulus


def _build_feeling(value: float = 0.5) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=value,
        arousal=value,
        tension=value,
        comfort=value,
        fatigue=value,
        pain_like=value,
        social_safety=value,
    )


def _build_config() -> InteroceptiveFeelingConfig:
    return InteroceptiveFeelingConfig(
        baseline_feeling=_build_feeling(0.3),
        legal_min=_build_feeling(0.0),
        legal_max=_build_feeling(1.0),
        mandatory_learned_parameters=(
            "feeling_mapping_strength",
            "feeling_coupling_strength",
            "feeling_persistence",
        ),
    )


def test_feeling_vector_is_immutable_and_range_checked() -> None:
    vector = _build_feeling(0.4)

    with pytest.raises(FrozenInstanceError):
        vector.valence = 0.9

    with pytest.raises(InteroceptiveFeelingError, match="Feeling value 'valence'"):
        InteroceptiveFeelingVector(
            valence=1.2,
            arousal=0.1,
            tension=0.1,
            comfort=0.1,
            fatigue=0.1,
            pain_like=0.1,
            social_safety=0.1,
        )


def test_feeling_state_preserves_provenance() -> None:
    state = InteroceptiveFeelingState(
        state_id="interoceptive-feeling-state:neuromodulator-state:1:5",
        source_neuromodulator_state_id="neuromodulator-state:1",
        feeling=_build_feeling(0.2),
        tick_id=5,
    )

    assert state.source_neuromodulator_state_id == "neuromodulator-state:1"
    assert state.feeling.social_safety == 0.2


def test_config_accepts_only_confirmed_learned_parameter_categories() -> None:
    config = _build_config()

    assert config.baseline_feeling.valence == 0.3

    with pytest.raises(InteroceptiveFeelingError, match="mandatory learned-parameter categories"):
        InteroceptiveFeelingConfig(
            baseline_feeling=_build_feeling(0.3),
            legal_min=_build_feeling(0.0),
            legal_max=_build_feeling(1.0),
            mandatory_learned_parameters=(
                "feeling_mapping_strength",
                "feeling_coupling_strength",
            ),
        )


def test_config_rejects_baseline_outside_legal_bounds() -> None:
    with pytest.raises(InteroceptiveFeelingError, match="outside legal bounds"):
        InteroceptiveFeelingConfig(
            baseline_feeling=_build_feeling(0.8),
            legal_min=_build_feeling(0.0),
            legal_max=_build_feeling(0.7),
            mandatory_learned_parameters=(
                "feeling_mapping_strength",
                "feeling_coupling_strength",
                "feeling_persistence",
            ),
        )


def test_internal_body_signal_validation_accepts_only_body_or_interoceptive_modalities() -> None:
    valid_signal = Stimulus(
        stimulus_id="stimulus:body:001",
        source_name="body",
        modality="interoceptive",
        content="heart_rate_high",
        channel="body",
        metadata=None,
        provenance_signal_id="001",
    )
    validate_internal_body_signal(valid_signal)

    invalid_signal = Stimulus(
        stimulus_id="stimulus:cli:001",
        source_name="cli",
        modality="text",
        content="hello",
        channel="cli",
        metadata=None,
        provenance_signal_id="001",
    )
    with pytest.raises(InteroceptiveFeelingError, match="only accepts body/interoceptive signals"):
        validate_internal_body_signal(invalid_signal)