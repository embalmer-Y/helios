"""Owner: temporal pacing and rest-state source.

Provides the first-version `RestStateTemporalSource`: it reports the default-mode network as
engaged at rest (no external stimulus) and suppressed during an external task, and accumulates a
bounded spontaneous-thought pacing signal across consecutive ticks in which no thought fired,
resetting it when a thought fires.

This owner reports situational facts only. It holds no gate/salience/feeling/cognitive policy and
imports no gate, appraisal, feeling, or neuromodulation owner; the `09` thought-gating owner keeps
the gate weights that turn these facts into a gate-score contribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import TemporalPacingSample, TemporalSource


@dataclass
class RestStateTemporalSource(TemporalSource):
    """Owner: temporal pacing and rest-state source.

    Purpose:
        First-version temporal/rest-state source. `dmn_available` is the rest fact (the default-mode
        network engages at rest, is suppressed on an external task): `dmn_available = not
        external_stimulus_present`. `temporal_signal` is the spontaneous-thought pacing accumulated
        from elapsed rest: `clamp(per_tick_increment * ticks_since_last_fire, 0, max_signal)`, which
        rises across consecutive no-fire ticks and resets to 0 the tick after a thought fires.

    Failure semantics:
        Pure deterministic state machine. `temporal_signal` is clamped to `[0, max_signal]` and
        `max_signal <= 1.0`, so the produced sample always satisfies the `TemporalPacingSample`
        range invariant. It never raises for a normal observation.

    Notes:
        The `ticks_since_last_fire` count is the owner's cross-tick state, advanced only by
        `observe_tick`. Cold start is 0 (no accumulated rest; the first tick's `temporal_signal` is
        0 — a defined cold start, not a fabricated history). The `per_tick_increment`/`max_signal`
        are explicit bounded first-version constants (P5-learnable later). The source reads no other
        owner and computes no gate decision.
    """

    per_tick_increment: float = 0.2
    max_signal: float = 1.0
    _ticks_since_last_fire: int = field(default=0, init=False, repr=False)

    def sample(self, external_stimulus_present: bool) -> TemporalPacingSample:
        """Owner: temporal pacing and rest-state source. Produce the current tick's sample."""

        signal = min(self.max_signal, self.per_tick_increment * self._ticks_since_last_fire)
        return TemporalPacingSample(
            temporal_signal=round(max(0.0, signal), 4),
            dmn_available=not external_stimulus_present,
        )

    def observe_tick(self, fired: bool) -> None:
        """Owner: temporal pacing and rest-state source. Advance the elapsed-rest state post-tick."""

        if fired:
            self._ticks_since_last_fire = 0
        else:
            self._ticks_since_last_fire += 1

    def seed_ticks_since_last_fire(self, ticks: int) -> None:
        """Owner: temporal pacing and rest-state source (composition-time restore seam).

        Purpose:
            Seed the cross-tick elapsed-rest count (for a future checkpoint/restore path), so a
            restarted runtime can resume its accumulated rest instead of starting at 0.

        Inputs:
            `ticks` - a non-negative elapsed-rest count to resume from.

        Notes:
            One-shot seed point, not a per-tick mutator; `observe_tick` still advances it each tick.
            A negative value is clamped to 0 (no fabricated negative history).
        """

        self._ticks_since_last_fire = max(0, int(ticks))
