from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.appraisal import RapidAppraisal, RapidAppraisalBatch, RapidSalienceVector
from helios_v2.neuromodulation import (
    ActiveChannelReporter,
    NeuromodulatorConfig,
    NeuromodulatorEngine,
    NeuromodulatorError,
    NeuromodulatorLevels,
    NeuromodulatorState,
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
        ),
    )


def _build_batch() -> RapidAppraisalBatch:
    return RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:stimulus-batch:abc",
        appraisals=(
            RapidAppraisal(
                appraisal_id="rapid-appraisal:stimulus:cli:001",
                stimulus_id="stimulus:cli:001",
                source_name="cli",
                salience=RapidSalienceVector(
                    threat=0.2,
                    reward=0.4,
                    novelty=0.5,
                    social=0.1,
                    uncertainty=0.3,
                    aggregate=0.4,
                ),
                provenance_signal_id="001",
            ),
        ),
    )


@dataclass
class CountingUpdatePath(NeuromodulatorUpdatePath):
    calls: int = 0

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        self.calls += 1
        assert config.decay_family == "dual_timescale_tonic_phasic"
        assert tick_id == 5
        return NeuromodulatorLevels(
            dopamine=0.6,
            norepinephrine=0.5,
            serotonin=0.4,
            acetylcholine=0.7,
            cortisol=0.3,
            oxytocin=0.2,
            opioid_tone=0.1,
            excitation=0.8,
            inhibition=0.2,
        )


@dataclass
class CountingReporter(ActiveChannelReporter):
    calls: int = 0

    def report_active_channels(
        self,
        state: NeuromodulatorState,
        config: NeuromodulatorConfig,
    ) -> tuple[str, ...]:
        self.calls += 1
        assert state.source_appraisal_batch_id == "rapid-appraisal-batch:stimulus-batch:abc"
        return ("acetylcholine", "excitation")


@dataclass
class UnavailableUpdatePath(NeuromodulatorUpdatePath):
    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        raise NeuromodulatorError("Required neuromodulator update capability is unavailable")


def test_engine_rejects_malformed_batch_before_update_path_invocation() -> None:
    update_path = CountingUpdatePath()
    engine = NeuromodulatorEngine(
        config=_build_config(),
        update_path=update_path,
        active_channel_reporter=CountingReporter(),
    )
    malformed_batch = RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:broken",
        appraisals=(
            RapidAppraisal(
                appraisal_id="",
                stimulus_id="stimulus:cli:001",
                source_name="cli",
                salience=RapidSalienceVector(
                    threat=0.1,
                    reward=0.1,
                    novelty=0.1,
                    social=0.1,
                    uncertainty=0.1,
                    aggregate=0.1,
                ),
                provenance_signal_id="001",
            ),
        ),
    )

    with pytest.raises(NeuromodulatorError, match="incomplete provenance"):
        engine.update_state(malformed_batch, tick_id=5)

    assert update_path.calls == 0


def test_engine_updates_state_with_injected_update_path() -> None:
    engine = NeuromodulatorEngine(
        config=_build_config(),
        update_path=CountingUpdatePath(),
        active_channel_reporter=CountingReporter(),
    )

    state = engine.update_state(_build_batch(), tick_id=5)

    assert state.state_id == "neuromodulator-state:rapid-appraisal-batch:stimulus-batch:abc:5"
    assert state.levels.acetylcholine == 0.7
    assert state.tick_id == 5


def test_engine_builds_update_request_op_from_valid_batch() -> None:
    engine = NeuromodulatorEngine(
        config=_build_config(),
        update_path=CountingUpdatePath(),
        active_channel_reporter=CountingReporter(),
    )

    op = engine.build_update_op(_build_batch())

    assert op.op_name == "update_neuromodulators"
    assert op.owner == "neuromodulator_system"
    assert op.appraisal_count == 1
    assert op.source_names == ("cli",)


def test_engine_builds_publish_op_from_valid_state() -> None:
    reporter = CountingReporter()
    engine = NeuromodulatorEngine(
        config=_build_config(),
        update_path=CountingUpdatePath(),
        active_channel_reporter=reporter,
    )
    state = engine.update_state(_build_batch(), tick_id=5)

    op = engine.build_publish_state_op(state)

    assert reporter.calls == 1
    assert op.op_name == "publish_neuromodulator_state"
    assert op.owner == "neuromodulator_system"
    assert op.active_channels == ("acetylcholine", "excitation")


def test_engine_fails_explicitly_when_required_update_capability_is_unavailable() -> None:
    engine = NeuromodulatorEngine(
        config=_build_config(),
        update_path=UnavailableUpdatePath(),
        active_channel_reporter=CountingReporter(),
    )

    with pytest.raises(NeuromodulatorError, match="update capability is unavailable"):
        engine.update_state(_build_batch(), tick_id=5)


# --- Requirement 36: appraisal-derived neuromodulation ---


from helios_v2.composition.bridges import AppraisalDerivedNeuromodulatorUpdatePath


def _batch_with(*, threat=0.0, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0) -> RapidAppraisalBatch:
    return RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:derived",
        appraisals=(
            RapidAppraisal(
                appraisal_id="rapid-appraisal:stimulus:cli:001",
                stimulus_id="stimulus:cli:001",
                source_name="cli",
                salience=RapidSalienceVector(
                    threat=threat,
                    reward=reward,
                    novelty=novelty,
                    social=social,
                    uncertainty=uncertainty,
                    aggregate=max(threat, reward, novelty, social, uncertainty),
                ),
                provenance_signal_id="001",
            ),
        ),
    )


def _derived_levels(batch: RapidAppraisalBatch) -> NeuromodulatorLevels:
    path = AppraisalDerivedNeuromodulatorUpdatePath()
    return path.update_levels(batch, _build_config(), tick_id=None)


def test_derived_high_novelty_raises_norepinephrine_above_low_novelty() -> None:
    high = _derived_levels(_batch_with(novelty=0.9))
    low = _derived_levels(_batch_with(novelty=0.1))
    assert high.norepinephrine > low.norepinephrine


def test_derived_high_reward_raises_dopamine_above_low_reward() -> None:
    high = _derived_levels(_batch_with(reward=0.9))
    low = _derived_levels(_batch_with(reward=0.1))
    assert high.dopamine > low.dopamine


def test_derived_high_threat_raises_cortisol_above_low_threat() -> None:
    high = _derived_levels(_batch_with(threat=0.9))
    low = _derived_levels(_batch_with(threat=0.1))
    assert high.cortisol > low.cortisol


def test_derived_empty_batch_yields_tonic_baseline() -> None:
    empty = RapidAppraisalBatch(batch_id="rapid-appraisal-batch:empty", appraisals=())
    levels = _derived_levels(empty)
    baseline = _build_config().tonic_baseline
    # All channels equal the clamped tonic baseline (0.3) when there is no salience.
    assert levels.dopamine == pytest.approx(baseline.dopamine)
    assert levels.norepinephrine == pytest.approx(baseline.norepinephrine)
    assert levels.cortisol == pytest.approx(baseline.cortisol)


def test_derived_levels_stay_within_legal_range() -> None:
    # Maximal salience on every dimension must not push any channel outside [0, 1].
    levels = _derived_levels(_batch_with(threat=1.0, reward=1.0, novelty=1.0, social=1.0, uncertainty=1.0))
    for name in (
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
        value = getattr(levels, name)
        assert 0.0 <= value <= 1.0


def test_derived_is_deterministic_for_identical_batch() -> None:
    batch = _batch_with(novelty=0.7, reward=0.4)
    assert _derived_levels(batch) == _derived_levels(batch)


def test_derived_non_driven_channels_equal_clamped_tonic_baseline() -> None:
    levels = _derived_levels(_batch_with(threat=1.0, reward=1.0, novelty=1.0, uncertainty=1.0))
    baseline = _build_config().tonic_baseline
    # Channels with no first-version driver regress to the tonic baseline regardless of salience.
    assert levels.serotonin == pytest.approx(baseline.serotonin)
    assert levels.acetylcholine == pytest.approx(baseline.acetylcholine)
    assert levels.oxytocin == pytest.approx(baseline.oxytocin)
    assert levels.opioid_tone == pytest.approx(baseline.opioid_tone)


def test_derived_path_aggregates_batch_by_per_dimension_max() -> None:
    # Two appraisals; novelty max is 0.8. NE must reflect the max, not the min or mean.
    batch = RapidAppraisalBatch(
        batch_id="rapid-appraisal-batch:multi",
        appraisals=(
            RapidAppraisal(
                appraisal_id="a1",
                stimulus_id="s1",
                source_name="cli",
                salience=RapidSalienceVector(threat=0.0, reward=0.0, novelty=0.2, social=0.0, uncertainty=0.0, aggregate=0.2),
                provenance_signal_id="001",
            ),
            RapidAppraisal(
                appraisal_id="a2",
                stimulus_id="s2",
                source_name="cli",
                salience=RapidSalienceVector(threat=0.0, reward=0.0, novelty=0.8, social=0.0, uncertainty=0.0, aggregate=0.8),
                provenance_signal_id="002",
            ),
        ),
    )
    multi = _derived_levels(batch)
    single_max = _derived_levels(_batch_with(novelty=0.8))
    assert multi.norepinephrine == pytest.approx(single_max.norepinephrine)
