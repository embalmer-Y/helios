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