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


# --- Requirement 51: interoceptive-signal-shaped feeling ---

from helios_v2.feeling import (
    InteroceptiveSignalModulatedFeelingConstructionPath,
    NeuromodulatorDerivedFeelingConstructionPath,
)


def _pressure_signal(channel: str, value: float) -> Stimulus:
    """Build a normalized interoceptive stimulus as the R50 producer + sensory would yield."""

    return Stimulus(
        stimulus_id=f"stimulus:interoception:interoceptive:{channel}",
        source_name="interoception",
        modality="interoceptive",
        content=f"{channel}_pressure={value:.4f}",
        channel="interoception",
        metadata={"pressure_channel": channel, "pressure_value": round(value, 4)},
        provenance_signal_id=f"interoceptive:{channel}",
    )


def _r51_path() -> InteroceptiveSignalModulatedFeelingConstructionPath:
    return InteroceptiveSignalModulatedFeelingConstructionPath(
        target_path=NeuromodulatorDerivedFeelingConstructionPath()
    )


def _r51_feeling(levels: NeuromodulatorLevels, signals: tuple[Stimulus, ...]) -> InteroceptiveFeelingVector:
    return _r51_path().construct_feeling(_state_with(levels), signals, _build_config(), tick_id=1)


def test_r51_empty_internal_signals_reproduces_neuromodulator_target_byte_for_byte() -> None:
    levels = _levels(dopamine=0.6, cortisol=0.3, norepinephrine=0.5)
    target = _derived_feeling(levels)
    with_empty = _r51_feeling(levels, ())
    assert with_empty == target


def test_r51_high_cpu_pressure_raises_arousal_and_tension() -> None:
    levels = _levels(norepinephrine=0.2)
    rest = _r51_feeling(levels, (_pressure_signal("cpu", 0.0),))
    loaded = _r51_feeling(levels, (_pressure_signal("cpu", 0.9),))
    assert loaded.arousal > rest.arousal
    assert loaded.tension >= rest.tension


def test_r51_high_memory_pressure_raises_fatigue_and_tension() -> None:
    levels = _levels()
    rest = _r51_feeling(levels, (_pressure_signal("memory", 0.0),))
    loaded = _r51_feeling(levels, (_pressure_signal("memory", 0.9),))
    assert loaded.fatigue > rest.fatigue
    assert loaded.tension > rest.tension


def test_r51_high_latency_pressure_raises_fatigue() -> None:
    levels = _levels()
    rest = _r51_feeling(levels, (_pressure_signal("latency", 0.0),))
    loaded = _r51_feeling(levels, (_pressure_signal("latency", 0.9),))
    assert loaded.fatigue > rest.fatigue


def test_r51_high_error_pressure_raises_pain_and_tension() -> None:
    levels = _levels()
    rest = _r51_feeling(levels, (_pressure_signal("error", 0.0),))
    loaded = _r51_feeling(levels, (_pressure_signal("error", 0.9),))
    assert loaded.pain_like > rest.pain_like
    assert loaded.tension > rest.tension


def test_r51_pressure_never_lowers_a_dimension_vs_target() -> None:
    levels = _levels(dopamine=0.5, cortisol=0.4, norepinephrine=0.5, opioid_tone=0.3, oxytocin=0.4)
    target = _derived_feeling(levels)
    loaded = _r51_feeling(
        levels,
        (
            _pressure_signal("cpu", 0.8),
            _pressure_signal("memory", 0.7),
            _pressure_signal("latency", 0.6),
            _pressure_signal("error", 0.5),
        ),
    )
    # stress-directional, additive, non-negative: no mapped dimension drops below the target.
    assert loaded.arousal >= target.arousal
    assert loaded.tension >= target.tension
    assert loaded.fatigue >= target.fatigue
    assert loaded.pain_like >= target.pain_like
    # untouched dimensions are exactly the target this slice.
    assert loaded.valence == target.valence
    assert loaded.comfort == target.comfort
    assert loaded.social_safety == target.social_safety


def test_r51_unrecognized_body_signal_contributes_nothing_and_does_not_raise() -> None:
    levels = _levels(norepinephrine=0.5)
    target = _derived_feeling(levels)
    # A body signal with no pressure metadata (e.g. a future producer) is ignored, not an error.
    other_body = Stimulus(
        stimulus_id="stimulus:body:misc",
        source_name="body",
        modality="body",
        content="some_other_body_signal",
        channel="body",
        metadata={"unrelated": "x"},
        provenance_signal_id="misc",
    )
    result = _r51_path().construct_feeling(_state_with(levels), (other_body,), _build_config(), tick_id=1)
    assert result == target


def test_r51_out_of_range_or_non_numeric_pressure_value_is_skipped() -> None:
    levels = _levels()
    target = _derived_feeling(levels)
    bad_high = Stimulus(
        stimulus_id="stimulus:interoception:interoceptive:cpu",
        source_name="interoception",
        modality="interoceptive",
        content="cpu_pressure=bad",
        channel="interoception",
        metadata={"pressure_channel": "cpu", "pressure_value": 1.5},
        provenance_signal_id="interoceptive:cpu",
    )
    bad_bool = Stimulus(
        stimulus_id="stimulus:interoception:interoceptive:memory",
        source_name="interoception",
        modality="interoceptive",
        content="memory_pressure=bad",
        channel="interoception",
        metadata={"pressure_channel": "memory", "pressure_value": True},
        provenance_signal_id="interoceptive:memory",
    )
    result = _r51_path().construct_feeling(
        _state_with(levels), (bad_high, bad_bool), _build_config(), tick_id=1
    )
    assert result == target


def test_r51_is_deterministic_and_bounded_for_extreme_inputs() -> None:
    extreme_levels = _levels(
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
    signals = (
        _pressure_signal("cpu", 1.0),
        _pressure_signal("memory", 1.0),
        _pressure_signal("latency", 1.0),
        _pressure_signal("error", 1.0),
    )
    first = _r51_feeling(extreme_levels, signals)
    second = _r51_feeling(extreme_levels, signals)
    assert first == second
    for dimension in first.__dataclass_fields__:
        assert 0.0 <= getattr(first, dimension) <= 1.0


def test_r51_takes_max_per_channel_across_duplicate_signals() -> None:
    levels = _levels()
    single_low = _r51_feeling(levels, (_pressure_signal("error", 0.2),))
    with_higher_dup = _r51_feeling(
        levels, (_pressure_signal("error", 0.2), _pressure_signal("error", 0.8))
    )
    assert with_higher_dup.pain_like > single_low.pain_like


def test_r51_engine_integration_body_raises_stress_dimensions() -> None:
    engine = InteroceptiveFeelingEngine(
        config=_build_config(),
        construction_path=_r51_path(),
        dominant_dimension_reporter=CountingReporter(),
    )
    levels = _levels(norepinephrine=0.3, cortisol=0.2)
    rest = engine.update_state(_state_with(levels), (_pressure_signal("cpu", 0.0),), tick_id=1)
    loaded = engine.update_state(
        _state_with(levels),
        (
            _pressure_signal("cpu", 0.9),
            _pressure_signal("memory", 0.8),
            _pressure_signal("error", 0.7),
        ),
        tick_id=1,
    )
    assert loaded.feeling.tension > rest.feeling.tension
    assert loaded.feeling.fatigue > rest.feeling.fatigue
    assert loaded.feeling.pain_like > rest.feeling.pain_like


def test_r51_composes_with_persistence_carry() -> None:
    # Nested as persistence(interoceptive(neuromodulator)) — the assembly's real wiring.
    config = _build_config()
    path = PersistentFeelingConstructionPath(
        target_path=_r51_path(), alpha_phasic=0.6, alpha_tonic=0.1
    )
    levels = _levels(norepinephrine=0.3)
    high_signals = (_pressure_signal("cpu", 0.9), _pressure_signal("error", 0.9))
    rest_signals = (_pressure_signal("cpu", 0.0), _pressure_signal("error", 0.0))
    # One integrator step from cold start: the high-pressure body yields higher stress carry.
    high_t1 = path.construct_feeling(_state_with(levels), high_signals, config, tick_id=1, prior_feeling=None)
    rest_t1 = path.construct_feeling(_state_with(levels), rest_signals, config, tick_id=1, prior_feeling=None)
    assert high_t1.tension > rest_t1.tension
    assert high_t1.pain_like > rest_t1.pain_like
