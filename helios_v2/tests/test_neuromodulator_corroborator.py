"""R81: hormone-predict corroboration tests (the `04` owner corroborator + biased update path)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.appraisal import RapidAppraisal, RapidAppraisalBatch, RapidSalienceVector
from helios_v2.neuromodulation import (
    CorroborationBiasedNeuromodulatorUpdatePath,
    HormonePredictCorroborator,
    HormonePredictionSource,
    NeuromodulatorConfig,
    NeuromodulatorLevels,
    NeuromodulatorUpdatePath,
)


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


def _build_batch() -> RapidAppraisalBatch:
    return RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:corroborator",
        appraisals=(
            RapidAppraisal(
                appraisal_id="rapid-appraisal:stimulus:cli:001",
                stimulus_id="stimulus:cli:001",
                source_name="cli",
                salience=RapidSalienceVector(
                    threat=0.2, reward=0.4, novelty=0.5, social=0.1, uncertainty=0.3, aggregate=0.4
                ),
                provenance_signal_id="001",
            ),
        ),
    )


# baseline is 0.3 on every channel; a drive of 0.6 is "above", 0.1 is "below".
def _drive_above() -> NeuromodulatorLevels:
    return _build_levels(0.6)


def test_corroborate_biases_channel_toward_agreeing_forecast() -> None:
    corroborator = HormonePredictCorroborator(coupling_gain=0.15)
    drive = _drive_above()  # dopamine 0.6 (above baseline 0.3)
    outcome = corroborator.corroborate({"dopamine": 0.9}, drive, _build_config())
    # corroborate (both above baseline): 0.6 + 0.15 * (0.9 - 0.6) = 0.645
    assert outcome.verdicts["dopamine"] == "corroborate"
    assert outcome.biased_levels.dopamine == pytest.approx(0.645, abs=1e-4)


def test_conflict_leaves_channel_at_drive() -> None:
    corroborator = HormonePredictCorroborator()
    drive = _drive_above()  # 0.6, above baseline
    # forecast below baseline => opposite side => conflict => no bias
    outcome = corroborator.corroborate({"dopamine": 0.05}, drive, _build_config())
    assert outcome.verdicts["dopamine"] == "conflict"
    assert outcome.biased_levels.dopamine == pytest.approx(drive.dopamine)


def test_silent_channel_without_forecast_is_unchanged() -> None:
    corroborator = HormonePredictCorroborator()
    drive = _drive_above()
    outcome = corroborator.corroborate({"dopamine": 0.9}, drive, _build_config())
    # No forecast for cortisol => silent => unchanged.
    assert outcome.verdicts["cortisol"] == "silent"
    assert outcome.biased_levels.cortisol == pytest.approx(drive.cortisol)


def test_null_forecast_returns_drive_byte_for_byte() -> None:
    corroborator = HormonePredictCorroborator()
    drive = _drive_above()
    outcome = corroborator.corroborate(None, drive, _build_config())
    assert outcome.biased_levels == drive
    assert set(outcome.verdicts.values()) == {"silent"}


def test_corroborated_levels_stay_in_legal_range() -> None:
    corroborator = HormonePredictCorroborator(coupling_gain=1.0)
    drive = _build_levels(0.95)  # above baseline on every channel
    forecast = {
        "dopamine": 1.0,
        "norepinephrine": 1.0,
        "serotonin": 1.0,
        "acetylcholine": 1.0,
        "cortisol": 1.0,
        "oxytocin": 1.0,
        "opioid_tone": 1.0,
        "excitation": 1.0,
        "inhibition": 1.0,
    }
    outcome = corroborator.corroborate(forecast, drive, _build_config())
    for channel in (
        "dopamine",
        "norepinephrine",
        "serotonin",
        "acetylcholine",
        "cortisol",
        "oxytocin",
        "opioid_tone",
        "excitation",
        "inhibition",
    ):
        assert 0.0 <= getattr(outcome.biased_levels, channel) <= 1.0


def test_both_near_baseline_is_corroborate_with_tiny_bias() -> None:
    corroborator = HormonePredictCorroborator(coupling_gain=0.15, agreement_deadzone=0.05)
    # drive at baseline (0.3), forecast also near baseline (0.31): both neutral => corroborate.
    drive = _build_levels(0.3)
    outcome = corroborator.corroborate({"dopamine": 0.31}, drive, _build_config())
    assert outcome.verdicts["dopamine"] == "corroborate"
    assert outcome.biased_levels.dopamine == pytest.approx(0.3 + 0.15 * 0.01, abs=1e-4)


@dataclass
class _FixedDrivePath(NeuromodulatorUpdatePath):
    drive_value: float = 0.6

    def update_levels(self, batch, config, tick_id, prior_levels=None):
        del batch, config, tick_id, prior_levels
        return _build_levels(self.drive_value)


@dataclass
class _FixedPredictionSource(HormonePredictionSource):
    prediction: dict | None = None

    def current_prediction(self):
        return self.prediction


def test_biased_path_applies_bias_from_source() -> None:
    path = CorroborationBiasedNeuromodulatorUpdatePath(
        drive_path=_FixedDrivePath(0.6),
        prediction_source=_FixedPredictionSource({"dopamine": 0.9}),
        corroborator=HormonePredictCorroborator(coupling_gain=0.15),
    )
    levels = path.update_levels(_build_batch(), _build_config(), tick_id=1)
    assert levels.dopamine == pytest.approx(0.645, abs=1e-4)
    # No forecast on other channels => they stay at the drive.
    assert levels.serotonin == pytest.approx(0.6)


def test_biased_path_with_no_forecast_equals_inner_drive() -> None:
    inner = _FixedDrivePath(0.6)
    path = CorroborationBiasedNeuromodulatorUpdatePath(
        drive_path=inner,
        prediction_source=_FixedPredictionSource(None),
        corroborator=HormonePredictCorroborator(),
    )
    config = _build_config()
    biased = path.update_levels(_build_batch(), config, tick_id=1)
    drive = inner.update_levels(_build_batch(), config, tick_id=1)
    assert biased == drive


def test_biased_path_over_real_drive_biases_a_corroborated_channel() -> None:
    # Integration with the real R36/R80 drive path: a high-novelty batch drives norepinephrine
    # well above baseline, so a forecast also above baseline corroborates and biases it upward.
    from helios_v2.neuromodulation import AppraisalDerivedNeuromodulatorUpdatePath

    config = _build_config()
    batch = RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:hi-novelty",
        appraisals=(
            RapidAppraisal(
                appraisal_id="a1",
                stimulus_id="s1",
                source_name="cli",
                salience=RapidSalienceVector(
                    threat=0.0, reward=0.0, novelty=0.9, social=0.0, uncertainty=0.5, aggregate=0.9
                ),
                provenance_signal_id="001",
            ),
        ),
    )
    drive = AppraisalDerivedNeuromodulatorUpdatePath().update_levels(batch, config, tick_id=1)
    assert drive.norepinephrine > config.tonic_baseline.norepinephrine  # precondition

    biased_path = CorroborationBiasedNeuromodulatorUpdatePath(
        drive_path=AppraisalDerivedNeuromodulatorUpdatePath(),
        prediction_source=_FixedPredictionSource({"norepinephrine": 1.0}),
        corroborator=HormonePredictCorroborator(coupling_gain=0.15),
    )
    biased = biased_path.update_levels(batch, config, tick_id=1)
    assert biased.norepinephrine > drive.norepinephrine
