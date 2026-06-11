from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.neuromodulation import NeuromodulatorConfig, NeuromodulatorError, NeuromodulatorLevels, NeuromodulatorState


def _build_levels(value: float = 0.5) -> NeuromodulatorLevels:
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


def _build_config() -> NeuromodulatorConfig:
    return NeuromodulatorConfig(
        tonic_baseline=_build_levels(0.3),
        legal_min=_build_levels(0.0),
        legal_max=_build_levels(1.0),
        mandatory_learned_parameters=(
            "channel_gain_sensitivity",
            "cross_channel_coupling_strength",
            "decay_speed_persistence",
            "gate_influence_strength",
            "hormone_predict_coupling",
        ),
    )


def test_neuromodulator_levels_are_immutable_and_range_checked() -> None:
    levels = _build_levels(0.4)

    with pytest.raises(FrozenInstanceError):
        levels.dopamine = 0.9

    with pytest.raises(NeuromodulatorError, match="Neuromodulator level 'dopamine'"):
        NeuromodulatorLevels(
            dopamine=1.2,
            norepinephrine=0.1,
            serotonin=0.1,
            acetylcholine=0.1,
            cortisol=0.1,
            oxytocin=0.1,
            opioid_tone=0.1,
            excitation=0.1,
            inhibition=0.1,
        )


def test_neuromodulator_state_preserves_provenance() -> None:
    state = NeuromodulatorState(
        state_id="neuromodulator-state:rapid-appraisal-batch:1:3",
        source_appraisal_batch_id="rapid-appraisal-batch:1",
        levels=_build_levels(0.2),
        tick_id=3,
    )

    assert state.source_appraisal_batch_id == "rapid-appraisal-batch:1"
    assert state.levels.serotonin == 0.2


def test_config_accepts_only_confirmed_learned_parameter_categories() -> None:
    config = _build_config()

    assert config.decay_family == "dual_timescale_tonic_phasic"
    assert config.hard_gate_eligibility_channels == ("cortisol", "inhibition")

    with pytest.raises(NeuromodulatorError, match="mandatory learned-parameter categories"):
        NeuromodulatorConfig(
            tonic_baseline=_build_levels(0.3),
            legal_min=_build_levels(0.0),
            legal_max=_build_levels(1.0),
            mandatory_learned_parameters=(
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
            ),
        )


def test_config_rejects_baseline_outside_legal_bounds() -> None:
    with pytest.raises(NeuromodulatorError, match="outside legal bounds"):
        NeuromodulatorConfig(
            tonic_baseline=_build_levels(0.8),
            legal_min=_build_levels(0.0),
            legal_max=_build_levels(0.7),
            mandatory_learned_parameters=(
                "channel_gain_sensitivity",
                "cross_channel_coupling_strength",
                "decay_speed_persistence",
                "gate_influence_strength",
                "hormone_predict_coupling",
            ),
        )