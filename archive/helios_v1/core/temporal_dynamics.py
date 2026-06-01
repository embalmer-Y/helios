"""Temporal dynamics layer for slow-moving runtime variables."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TemporalState:
    boredom: float = 0.0
    fatigue_pressure: float = 0.0
    restoration_level: float = 0.5
    novelty_hunger: float = 0.0
    emotional_decay_factor: float = 1.0
    circadian_phase: float = 0.0
    inactivity_duration: float = 0.0
    recent_excitation_tail: float = 0.0
    quiet_ticks: int = 0
    last_input_tick: int = 0
    stimulation_level: float = 0.0

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalNeurochemSignal:
    stimulation_drive: float = 0.0
    novelty_drive: float = 0.0
    social_drive: float = 0.0
    stress_load: float = 0.0
    recovery_bias: float = 0.0
    isolation_pressure: float = 0.0
    safety_signal: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalUpdate:
    tick: int
    timestamp: float
    event_count: int = 0
    message_count: int = 0
    external_input_strength: float = 0.0
    arousal: float = 0.0
    valence: float = 0.0
    allostatic_load: float = 0.0
    is_fatigued: bool = False
    active_behavior: bool = False
    generated_thought: bool = False


class TemporalDynamics:
    """Maintain slow variables that evolve across ticks."""

    def __init__(
        self,
        *,
        tick_interval: float = 1.0,
        boredom_horizon_ticks: int = 120,
        restoration_horizon_ticks: int = 40,
    ):
        self._tick_interval = max(tick_interval, 0.001)
        self._boredom_horizon = max(boredom_horizon_ticks, 1)
        self._restoration_horizon = max(restoration_horizon_ticks, 1)
        self._state = TemporalState(restoration_level=0.45)
        self._neurochem_signal = TemporalNeurochemSignal(recovery_bias=0.3, safety_signal=0.2)

    @property
    def state(self) -> TemporalState:
        return self._state

    @property
    def neurochem_signal(self) -> TemporalNeurochemSignal:
        return self._neurochem_signal

    def update(self, update: TemporalUpdate) -> TemporalState:
        prev = self._state
        circadian_phase = self._resolve_circadian_phase(update.timestamp)
        stimulation_level = self._resolve_stimulation(update)
        has_external_input = (update.message_count + update.event_count) > 0 or update.external_input_strength > 0.05

        if has_external_input:
            quiet_ticks = 0
            inactivity_duration = 0.0
            last_input_tick = update.tick
        else:
            quiet_ticks = prev.quiet_ticks + 1
            inactivity_duration = prev.inactivity_duration + self._tick_interval
            last_input_tick = prev.last_input_tick

        excitation_target = _clamp(stimulation_level * 0.72 + update.arousal * 0.28)
        excitation_alpha = 0.48 if has_external_input else 0.16
        recent_excitation_tail = _clamp(
            prev.recent_excitation_tail + (excitation_target - prev.recent_excitation_tail) * excitation_alpha
        )

        quiet_ratio = _clamp(quiet_ticks / self._boredom_horizon)
        fatigue_pressure = _clamp(
            update.allostatic_load * 0.72
            + (0.18 if update.is_fatigued else 0.0)
            + recent_excitation_tail * 0.08
        )

        restoration_target = _clamp(
            0.42
            + quiet_ratio * 0.50
            - update.allostatic_load * 0.20
            - recent_excitation_tail * 0.18
            - (0.08 if update.active_behavior else 0.0)
            - (0.05 if has_external_input else 0.0)
            + (0.04 if update.generated_thought else 0.0)
        )
        restoration_level = _clamp(
            prev.restoration_level + (restoration_target - prev.restoration_level) * 0.18
        )

        boredom_target = _clamp(
            quiet_ratio * 0.82
            + restoration_level * 0.20
            - recent_excitation_tail * 0.28
            - update.arousal * 0.10
            - (0.08 if update.generated_thought else 0.0)
        )
        boredom = _clamp(prev.boredom + (boredom_target - prev.boredom) * 0.22)

        novelty_hunger_target = _clamp(
            boredom * 0.58
            + quiet_ratio * 0.18
            + restoration_level * 0.20
            - recent_excitation_tail * 0.22
            - fatigue_pressure * 0.10
        )
        novelty_hunger = _clamp(
            prev.novelty_hunger + (novelty_hunger_target - prev.novelty_hunger) * 0.24
        )

        emotional_decay_factor = _clamp(
            0.88
            + restoration_level * 0.18
            + quiet_ratio * 0.08
            - recent_excitation_tail * 0.20
            - fatigue_pressure * 0.08,
            0.60,
            1.20,
        )

        self._state = TemporalState(
            boredom=boredom,
            fatigue_pressure=fatigue_pressure,
            restoration_level=restoration_level,
            novelty_hunger=novelty_hunger,
            emotional_decay_factor=emotional_decay_factor,
            circadian_phase=circadian_phase,
            inactivity_duration=inactivity_duration,
            recent_excitation_tail=recent_excitation_tail,
            quiet_ticks=quiet_ticks,
            last_input_tick=last_input_tick,
            stimulation_level=stimulation_level,
        )
        self._neurochem_signal = self._build_neurochem_signal(
            update=update,
            state=self._state,
            quiet_ratio=quiet_ratio,
            has_external_input=has_external_input,
        )
        return self._state

    def _build_neurochem_signal(
        self,
        *,
        update: TemporalUpdate,
        state: TemporalState,
        quiet_ratio: float,
        has_external_input: bool,
    ) -> TemporalNeurochemSignal:
        social_drive = _clamp(
            min(update.message_count, 3) * 0.22
            + max(update.valence, 0.0) * 0.12
            + (0.08 if update.generated_thought else 0.0)
        )
        stress_load = _clamp(
            update.allostatic_load * 0.56
            + update.arousal * 0.18
            + state.recent_excitation_tail * 0.12
            + state.fatigue_pressure * 0.10
            - state.restoration_level * 0.10
        )
        recovery_bias = _clamp(
            state.restoration_level * 0.62
            + quiet_ratio * 0.18
            - state.recent_excitation_tail * 0.12
            - stress_load * 0.14
        )
        isolation_pressure = _clamp(
            quiet_ratio * 0.48
            + state.boredom * 0.22
            + state.novelty_hunger * 0.12
            - min(update.message_count, 2) * 0.18
        )
        novelty_drive = _clamp(
            state.novelty_hunger * 0.54
            + state.boredom * 0.20
            + state.stimulation_level * 0.16
            + (0.08 if has_external_input else 0.0)
        )
        safety_signal = _clamp(
            state.restoration_level * 0.42
            + max(update.valence, 0.0) * 0.18
            + (0.10 if update.message_count > 0 else 0.0)
            - stress_load * 0.18
        )
        stimulation_drive = _clamp(
            state.stimulation_level * 0.72
            + state.recent_excitation_tail * 0.18
            + (0.08 if update.active_behavior else 0.0)
        )
        return TemporalNeurochemSignal(
            stimulation_drive=stimulation_drive,
            novelty_drive=novelty_drive,
            social_drive=social_drive,
            stress_load=stress_load,
            recovery_bias=recovery_bias,
            isolation_pressure=isolation_pressure,
            safety_signal=safety_signal,
        )

    @staticmethod
    def _resolve_stimulation(update: TemporalUpdate) -> float:
        message_signal = min(update.message_count, 3) * 0.25
        event_signal = min(update.event_count, 4) * 0.12
        thought_signal = 0.05 if update.generated_thought else 0.0
        behavior_signal = 0.08 if update.active_behavior else 0.0
        return _clamp(update.external_input_strength * 0.65 + message_signal + event_signal + thought_signal + behavior_signal)

    @staticmethod
    def _resolve_circadian_phase(timestamp: float) -> float:
        seconds_per_day = 24 * 60 * 60
        phase = (timestamp % seconds_per_day) / seconds_per_day
        return _clamp(phase)