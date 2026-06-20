"""Owner: continuous-state wall-clock substrate (R-PROTO-LEARN.P-TEMPORAL).

Provides the first-version `FirstVersionContinuousStateOwner`: tracks
wall-clock elapsed seconds, last-external-stimulus wall-clock, current
episode id, and episode-start wall-clock across ticks. Episode split is
pure arithmetic on wall-clock gap (>NEW_EPISODE_GAP_SECONDS).

This owner reports situational facts only. It holds no cognitive policy
and imports no gate, appraisal, feeling, or neuromodulation owner; cognitive
owners read its `ContinuousStateReading` via composition glue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import (
    NEW_EPISODE_GAP_SECONDS,
    ContinuousStateError,
    ContinuousStateOwner,
    ContinuousStateReading,
)


@dataclass
class FirstVersionContinuousStateOwner(ContinuousStateOwner):
    """Owner: continuous-state wall-clock substrate.

    Purpose:
        First-version cross-tick continuous-state infrastructure owner.
        `observe_tick` advances the cross-tick state from one
        `tick_wall_seconds` reading plus the boolean fired and
        external_stimulus_present facts. `sample` produces one
        `ContinuousStateReading` snapshot.

        Episode split: when the wall-clock delta between the current tick
        and the prior tick exceeds `new_episode_gap_seconds` (default 60s),
        a new episode starts (episode_id increments, episode_start resets).

    Failure semantics:
        Pure deterministic state machine. Out-of-order tick timestamps
        (negative delta) raise `ContinuousStateError`. Cold start is
        defined: first `observe_tick` initializes the prior tick timestamp
        without applying episode-gap logic.

    Notes:
        Wall-clock-absent mode: when `tick_wall_seconds is None` or
        `wall_clock is None`, the state advances with elapsed=0.0 and
        `wall_clock_present=False`. Reading itself is honest absence;
        cognitive owners fall back to legacy tick-counted paths.

        `fired` is part of the API for symmetry with `temporal` owner
        (whose `RestStateTemporalSource.observe_tick` also takes fired),
        but is not consumed by continuous-state arithmetic in this version.
    """

    new_episode_gap_seconds: float = NEW_EPISODE_GAP_SECONDS
    _wall_clock_elapsed_seconds: float = field(default=0.0, init=False, repr=False)
    _last_external_stimulus_wall_seconds: float | None = field(default=None, init=False, repr=False)
    _current_episode_id: int = field(default=0, init=False, repr=False)
    _episode_start_wall_seconds: float | None = field(default=None, init=False, repr=False)
    _previous_tick_wall_seconds: float | None = field(default=None, init=False, repr=False)

    def observe_tick(
        self,
        *,
        fired: bool,
        external_stimulus_present: bool,
        tick_wall_seconds: float | None,
    ) -> None:
        """Owner: continuous-state wall-clock substrate. Advance the cross-tick state post-tick.

        Inputs:
            `fired` — boolean fact for symmetry with `temporal` owner (not
                consumed in this version).
            `external_stimulus_present` — when True and tick_wall_seconds is
                not None, update `last_external_stimulus_wall_seconds`.
            `tick_wall_seconds` — wall-clock seconds since Unix epoch (or
                any monotonic origin a `FixedWallClock` defines). None means
                wall-clock-absent mode: state advances but elapsed stays 0.

        Raises:
            `ContinuousStateError` if `tick_wall_seconds` is negative or if
                a backwards-stepping delta is detected (negative delta).

        Notes:
            Cold-start semantics: the very first call initializes
            `_previous_tick_wall_seconds` and (if external stimulus
            present) `_last_external_stimulus_wall_seconds` and
            `_episode_start_wall_seconds` without applying episode-gap
            arithmetic. Subsequent calls apply the elapsed-delta and
            episode-split logic.
        """

        # wall-clock-absent mode: advance only the episode_id when forced
        # (a stimulus-less cold start still creates episode 0).
        if tick_wall_seconds is None:
            return

        if tick_wall_seconds < 0.0:
            raise ContinuousStateError(
                "tick_wall_seconds must be non-negative"
            )

        # Cold start: establish anchors, no arithmetic.
        if self._previous_tick_wall_seconds is None:
            self._previous_tick_wall_seconds = tick_wall_seconds
            if external_stimulus_present:
                self._last_external_stimulus_wall_seconds = tick_wall_seconds
            if self._episode_start_wall_seconds is None:
                self._episode_start_wall_seconds = tick_wall_seconds
            return

        # Backwards-stepping clock: hard-stop (no silent reuse of last value).
        if tick_wall_seconds < self._previous_tick_wall_seconds:
            raise ContinuousStateError(
                "ContinuousStateOwner observed a backwards-stepping wall-clock "
                f"(prior={self._previous_tick_wall_seconds}, current={tick_wall_seconds})"
            )

        delta = tick_wall_seconds - self._previous_tick_wall_seconds
        self._wall_clock_elapsed_seconds += delta
        self._previous_tick_wall_seconds = tick_wall_seconds

        if external_stimulus_present:
            self._last_external_stimulus_wall_seconds = tick_wall_seconds

        # Episode split on wall-clock gap.
        if (
            self._episode_start_wall_seconds is not None
            and delta > self.new_episode_gap_seconds
        ):
            self._current_episode_id += 1
            self._episode_start_wall_seconds = tick_wall_seconds

    def sample(self) -> ContinuousStateReading:
        """Owner: continuous-state wall-clock substrate. Return the current reading.

        Returns:
            `ContinuousStateReading` snapshot. In wall-clock-absent mode
            (no WallClock wired, no tick_wall_seconds ever observed),
            returns a zero-valued reading with `wall_clock_present=False`.
        """

        wall_clock_present = (
            self._previous_tick_wall_seconds is not None
        )
        last_external_age = None
        episode_elapsed = 0.0
        if wall_clock_present and self._previous_tick_wall_seconds is not None:
            # Use raw absolute timestamps: tick_wall - episode_start_wall.
            if self._last_external_stimulus_wall_seconds is not None:
                last_external_age = round(
                    max(
                        0.0,
                        self._previous_tick_wall_seconds - self._last_external_stimulus_wall_seconds,
                    ),
                    4,
                )
            if self._episode_start_wall_seconds is not None:
                episode_elapsed = round(
                    max(
                        0.0,
                        self._previous_tick_wall_seconds - self._episode_start_wall_seconds,
                    ),
                    4,
                )
        return ContinuousStateReading(
            wall_clock_elapsed_seconds=round(self._wall_clock_elapsed_seconds, 4),
            last_external_stimulus_age_seconds=last_external_age,
            current_episode_id=self._current_episode_id,
            episode_elapsed_seconds=episode_elapsed,
            wall_clock_present=wall_clock_present,
        )

    def _episode_start_wall_seconds_or_zero(self) -> float:
        return self._episode_start_wall_seconds or 0.0



    def seed_tick(self, tick_wall_seconds: float | None) -> None:
        """Owner: continuous-state wall-clock substrate. Cold-start seed.

        Initialize the prior-tick wall-clock anchor without advancing
        elapsed. Used by tests and the assembly bootstrap to set the
        starting timestamp without forcing an episode split.
        """

        if tick_wall_seconds is None:
            return
        if tick_wall_seconds < 0.0:
            raise ContinuousStateError("seed tick_wall_seconds must be non-negative")
        self._previous_tick_wall_seconds = tick_wall_seconds
        if self._episode_start_wall_seconds is None:
            self._episode_start_wall_seconds = tick_wall_seconds
