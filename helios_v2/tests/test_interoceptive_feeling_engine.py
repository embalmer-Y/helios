from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.feeling import (
    DominantDimensionReporter,
    FeelingConstructionPath,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingEngine,
    InteroceptiveFeelingError,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
)
from helios_v2.neuromodulation import NeuromodulatorLevels, NeuromodulatorState
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


def _build_neuromodulator_state() -> NeuromodulatorState:
    return NeuromodulatorState(
        state_id="neuromodulator-state:rapid-appraisal-batch:abc:7",
        source_appraisal_batch_id="rapid-appraisal-batch:abc",
        levels=NeuromodulatorLevels(
            dopamine=0.6,
            norepinephrine=0.4,
            serotonin=0.3,
            acetylcholine=0.7,
            cortisol=0.2,
            oxytocin=0.1,
            opioid_tone=0.1,
            excitation=0.8,
            inhibition=0.3,
        ),
        tick_id=7,
    )


def _build_internal_signal() -> Stimulus:
    return Stimulus(
        stimulus_id="stimulus:body:001",
        source_name="body",
        modality="interoceptive",
        content="breathing_shallow",
        channel="body",
        metadata={"sensor": "respiration"},
        provenance_signal_id="001",
    )


@dataclass
class CountingConstructionPath(FeelingConstructionPath):
    calls: int = 0

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        self.calls += 1
        assert neuromodulator_state.state_id == "neuromodulator-state:rapid-appraisal-batch:abc:7"
        assert len(internal_signals) == 1
        assert config.baseline_feeling.valence == 0.3
        assert tick_id == 9
        return InteroceptiveFeelingVector(
            valence=0.4,
            arousal=0.7,
            tension=0.6,
            comfort=0.2,
            fatigue=0.5,
            pain_like=0.1,
            social_safety=0.3,
        )


@dataclass
class CountingReporter(DominantDimensionReporter):
    calls: int = 0

    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        self.calls += 1
        assert state.source_neuromodulator_state_id == "neuromodulator-state:rapid-appraisal-batch:abc:7"
        return ("arousal", "tension")


@dataclass
class UnavailableConstructionPath(FeelingConstructionPath):
    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        raise InteroceptiveFeelingError("Required feeling construction capability is unavailable")


def test_engine_rejects_malformed_neuromodulator_state_before_construction_invocation() -> None:
    construction_path = CountingConstructionPath()
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=construction_path,
        dominant_dimension_reporter=CountingReporter(),
    )

    @dataclass
    class MalformedNeuromodulatorState:
        state_id: str = ""
        source_appraisal_batch_id: str = "rapid-appraisal-batch:abc"
        levels: NeuromodulatorLevels = _build_neuromodulator_state().levels
        tick_id: int | None = 7

    malformed_state = MalformedNeuromodulatorState()

    with pytest.raises(InteroceptiveFeelingError, match="non-empty state_id"):
        engine.update_state(malformed_state, (_build_internal_signal(),), tick_id=9)  # type: ignore[arg-type]

    assert construction_path.calls == 0


def test_engine_updates_feeling_state_with_injected_construction_path() -> None:
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=CountingConstructionPath(),
        dominant_dimension_reporter=CountingReporter(),
    )

    state = engine.update_state(_build_neuromodulator_state(), (_build_internal_signal(),), tick_id=9)

    assert state.state_id == "interoceptive-feeling-state:neuromodulator-state:rapid-appraisal-batch:abc:7:9"
    assert state.feeling.arousal == 0.7
    assert state.tick_id == 9


def test_engine_builds_update_request_op_from_valid_inputs() -> None:
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=CountingConstructionPath(),
        dominant_dimension_reporter=CountingReporter(),
    )

    op = engine.build_update_op(_build_neuromodulator_state(), (_build_internal_signal(),))

    assert op.op_name == "update_interoceptive_feeling"
    assert op.owner == "interoceptive_feeling_layer"
    assert op.internal_signal_count == 1


def test_engine_builds_publish_op_from_valid_state() -> None:
    reporter = CountingReporter()
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=CountingConstructionPath(),
        dominant_dimension_reporter=reporter,
    )
    state = engine.update_state(_build_neuromodulator_state(), (_build_internal_signal(),), tick_id=9)

    op = engine.build_publish_state_op(state)

    assert reporter.calls == 1
    assert op.op_name == "publish_interoceptive_feeling_state"
    assert op.owner == "interoceptive_feeling_layer"
    assert op.dominant_dimensions == ("arousal", "tension")


def test_engine_fails_explicitly_when_required_construction_capability_is_unavailable() -> None:
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=UnavailableConstructionPath(),
        dominant_dimension_reporter=CountingReporter(),
    )

    with pytest.raises(InteroceptiveFeelingError, match="construction capability is unavailable"):
        engine.update_state(_build_neuromodulator_state(), (_build_internal_signal(),), tick_id=9)


def test_engine_rejects_non_body_internal_signal() -> None:
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=CountingConstructionPath(),
        dominant_dimension_reporter=CountingReporter(),
    )
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
        engine.build_update_op(_build_neuromodulator_state(), (invalid_signal,))


# --- R38: neuromodulator-derived feeling (NeuromodulatorDerivedFeelingConstructionPath) ---


def _levels(
    *,
    dopamine: float = 0.0,
    norepinephrine: float = 0.0,
    serotonin: float = 0.0,
    acetylcholine: float = 0.0,
    cortisol: float = 0.0,
    oxytocin: float = 0.0,
    opioid_tone: float = 0.0,
    excitation: float = 0.0,
    inhibition: float = 0.0,
) -> NeuromodulatorLevels:
    return NeuromodulatorLevels(
        dopamine=dopamine,
        norepinephrine=norepinephrine,
        serotonin=serotonin,
        acetylcholine=acetylcholine,
        cortisol=cortisol,
        oxytocin=oxytocin,
        opioid_tone=opioid_tone,
        excitation=excitation,
        inhibition=inhibition,
    )


def _state_with(levels: NeuromodulatorLevels) -> NeuromodulatorState:
    return NeuromodulatorState(
        state_id="neuromodulator-state:rapid-appraisal-batch:r38:1",
        source_appraisal_batch_id="rapid-appraisal-batch:r38",
        levels=levels,
        tick_id=1,
    )


def _derived_feeling(levels: NeuromodulatorLevels) -> InteroceptiveFeelingVector:
    from helios_v2.feeling import NeuromodulatorDerivedFeelingConstructionPath

    path = NeuromodulatorDerivedFeelingConstructionPath()
    return path.construct_feeling(_state_with(levels), (), _build_config(), tick_id=1)


def test_derived_high_cortisol_raises_tension_and_pain_lowers_valence_and_comfort() -> None:
    high = _derived_feeling(_levels(cortisol=0.9))
    low = _derived_feeling(_levels(cortisol=0.1))

    assert high.tension > low.tension
    assert high.pain_like > low.pain_like
    assert high.valence < low.valence
    assert high.comfort < low.comfort


def test_derived_high_dopamine_raises_valence() -> None:
    high = _derived_feeling(_levels(dopamine=0.9))
    low = _derived_feeling(_levels(dopamine=0.1))

    assert high.valence > low.valence


def test_derived_high_norepinephrine_raises_arousal() -> None:
    high = _derived_feeling(_levels(norepinephrine=0.9))
    low = _derived_feeling(_levels(norepinephrine=0.1))

    assert high.arousal > low.arousal


def test_derived_high_oxytocin_raises_social_safety() -> None:
    high = _derived_feeling(_levels(oxytocin=0.9))
    low = _derived_feeling(_levels(oxytocin=0.1))

    assert high.social_safety > low.social_safety


def test_derived_opioid_tone_lowers_pain_like() -> None:
    high_opioid = _derived_feeling(_levels(cortisol=0.5, opioid_tone=0.9))
    low_opioid = _derived_feeling(_levels(cortisol=0.5, opioid_tone=0.0))

    assert high_opioid.pain_like < low_opioid.pain_like


def test_derived_feeling_is_within_legal_range_for_extreme_state() -> None:
    # Every channel maxed out: clamping must keep every dimension within [0, 1].
    extreme = _levels(
        dopamine=1.0,
        norepinephrine=1.0,
        serotonin=1.0,
        acetylcholine=1.0,
        cortisol=1.0,
        oxytocin=1.0,
        opioid_tone=1.0,
        excitation=1.0,
        inhibition=1.0,
    )
    feeling = _derived_feeling(extreme)
    for dimension in feeling.__dataclass_fields__:
        value = getattr(feeling, dimension)
        assert 0.0 <= value <= 1.0


def test_derived_feeling_is_deterministic() -> None:
    levels = _levels(dopamine=0.6, cortisol=0.3, norepinephrine=0.5)
    first = _derived_feeling(levels)
    second = _derived_feeling(levels)

    assert first == second


def test_derived_feeling_differs_from_constant_shim_for_nonbaseline_state() -> None:
    # The de-shim is real: a non-baseline neuromodulator state yields a feeling vector that is
    # not the fixed first-version constant (valence=0.4, arousal=0.7, ...).
    constant = InteroceptiveFeelingVector(
        valence=0.4, arousal=0.7, tension=0.5, comfort=0.2, fatigue=0.3, pain_like=0.1, social_safety=0.4
    )
    derived = _derived_feeling(_levels(dopamine=0.9, cortisol=0.8, norepinephrine=0.6))

    assert derived != constant


def test_derived_feeling_engine_integration_uses_real_state() -> None:
    # Through the real 05 engine: the derived feeling differs across two states differing in
    # cortisol, and flows through the unchanged InteroceptiveFeelingState contract.
    from helios_v2.feeling import NeuromodulatorDerivedFeelingConstructionPath

    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=NeuromodulatorDerivedFeelingConstructionPath(),
        dominant_dimension_reporter=CountingReporter(),
    )
    high = engine.update_state(_state_with(_levels(cortisol=0.9)), (), tick_id=1)
    low = engine.update_state(_state_with(_levels(cortisol=0.1)), (), tick_id=1)

    assert high.feeling.tension > low.feeling.tension
    assert high.source_neuromodulator_state_id == "neuromodulator-state:rapid-appraisal-batch:r38:1"


# --- Requirement 44: dual-timescale feeling persistence ---

from helios_v2.feeling import PersistentFeelingConstructionPath


@dataclass
class _FixedTargetPath(FeelingConstructionPath):
    """Inner target path returning a fixed feeling vector regardless of input (test double)."""

    target_value: float = 0.9

    def construct_feeling(self, neuromodulator_state, internal_signals, config, tick_id, prior_feeling=None):
        del neuromodulator_state, internal_signals, config, tick_id, prior_feeling
        return _build_feeling(self.target_value)


def test_persistent_feeling_cold_start_is_one_step_from_baseline() -> None:
    path = PersistentFeelingConstructionPath(
        target_path=_FixedTargetPath(0.9), alpha_phasic=0.6, alpha_tonic=0.1
    )
    config = _build_config()
    feeling = path.construct_feeling(
        _build_neuromodulator_state(), (), config, tick_id=1, prior_feeling=None
    )
    # next = 0.3 + 0.6*(0.9-0.3) + 0.1*(0.3-0.3) = 0.66
    assert feeling.valence == pytest.approx(0.66, abs=1e-4)


def test_persistent_feeling_phasic_carry_then_tonic_regression() -> None:
    config = _build_config()
    high = PersistentFeelingConstructionPath(
        target_path=_FixedTargetPath(0.9), alpha_phasic=0.6, alpha_tonic=0.1
    )
    t1 = high.construct_feeling(_build_neuromodulator_state(), (), config, tick_id=1, prior_feeling=None)
    low = PersistentFeelingConstructionPath(
        target_path=_FixedTargetPath(0.3), alpha_phasic=0.6, alpha_tonic=0.1
    )
    t2 = low.construct_feeling(_build_neuromodulator_state(), (), config, tick_id=2, prior_feeling=t1)
    assert t2.valence < t1.valence                          # decays toward the lower target
    assert t2.valence > config.baseline_feeling.valence     # but still above baseline (carry)
    t3 = low.construct_feeling(_build_neuromodulator_state(), (), config, tick_id=3, prior_feeling=t2)
    assert config.baseline_feeling.valence <= t3.valence < t2.valence


def test_persistent_feeling_stays_bounded_over_many_ticks() -> None:
    config = _build_config()
    path = PersistentFeelingConstructionPath(
        target_path=_FixedTargetPath(1.0), alpha_phasic=0.9, alpha_tonic=0.2
    )
    prior = None
    for tick in range(1, 50):
        feeling = path.construct_feeling(_build_neuromodulator_state(), (), config, tick_id=tick, prior_feeling=prior)
        for dimension in ("valence", "arousal", "tension", "comfort", "fatigue", "pain_like", "social_safety"):
            assert 0.0 <= getattr(feeling, dimension) <= 1.0
        prior = feeling


def test_persistent_feeling_rejects_unstable_alpha() -> None:
    with pytest.raises(InteroceptiveFeelingError, match="alpha"):
        PersistentFeelingConstructionPath(target_path=_FixedTargetPath(), alpha_phasic=0.1, alpha_tonic=0.6)
    with pytest.raises(InteroceptiveFeelingError, match="alpha"):
        PersistentFeelingConstructionPath(target_path=_FixedTargetPath(), alpha_phasic=0.6, alpha_tonic=0.0)


def test_persistent_feeling_engine_carries_prior_state_across_calls() -> None:
    config = _build_config()
    engine = InteroceptiveFeelingEngine(
        config=config,
        construction_path=PersistentFeelingConstructionPath(
            target_path=_FixedTargetPath(0.9), alpha_phasic=0.6, alpha_tonic=0.1
        ),
        dominant_dimension_reporter=CountingReporter(),
    )
    s1 = engine.update_state(_build_neuromodulator_state(), (), tick_id=1, prior_state=None)
    s2 = engine.update_state(_build_neuromodulator_state(), (), tick_id=2, prior_state=s1)
    assert s2.feeling.valence > s1.feeling.valence  # rises further on tick 2 toward the target
