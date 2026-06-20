"""Owner: continuous-state wall-clock substrate (R-PROTO-LEARN.P-TEMPORAL).

Owns:
- `ContinuousStateOwner` frozen dataclass protocol for the cross-tick
  continuous-state infrastructure owner.
- `ContinuousStateReading` immutable per-tick reading carrying wall-clock
  elapsed seconds, last-external-stimulus age, current episode id,
  episode elapsed seconds, and a wall-clock-present flag.
- `ContinuousStateError` hard-stop exception type.
- `NEW_EPISODE_GAP_SECONDS` first-version constant for episode split
  (60s wall-clock gap; C_engineering_hypothesis first-version).

Does not own:
- any cognitive policy. How an owner reacts to elapsed seconds (e.g. decay
  on `04` neuromodulator, hormone persistence on `05` feeling, time pressure
  on `09` gate, identity boundary on `14`, autobiographical decay on `15`,
  pacing on `temporal`) lives in those owners; this owner only produces the
  bounded reading.
- the actual wall-clock. It receives one `WallClock | None` (R92) at
  construction and reads it once per `observe_tick`. With no clock wired,
  it operates in wall-clock-absent mode: readings still issue but
  `wall_clock_present=False` and elapsed fields stay 0.0 / None (honest
  absence).
- episode-detection LLM judgment. Episode split is pure wall-clock gap
  arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol, runtime_checkable


# C_engineering_hypothesis first-version constant. Below this wall-clock gap,
# consecutive ticks belong to the same episode; at-or-above, a new episode starts.
# Tunable later by P5 learner if needed (not exposed as P5 surface in this slice).
NEW_EPISODE_GAP_SECONDS: Final[float] = 60.0


class ContinuousStateError(RuntimeError):
    """Owner: continuous-state wall-clock substrate.

    Hard-stop error raised when a continuous-state invariant fails. There is
    no degraded path: an invalid wall-clock reading (None where required,
    out-of-order tick timestamps, negative elapsed) raises; the runtime
    never papers over a broken continuous-state with a silent default.
    """


@dataclass(frozen=True)
class ContinuousStateReading:
    """Owner: continuous-state wall-clock substrate.

    Purpose:
        One bounded cross-tick continuous-state reading. Produced by
        `ContinuousStateOwner.sample()` and consumed by cognitive owners as
        a pure fact: `04` neuromodulator wall-clock decay term, `05` feeling
        persistence, `09` thought-gate pacing, `14` identity boundary
        `recent_trace_span_seconds`, `15` autobiographical decay.

    Inputs:
        `wall_clock_elapsed_seconds` — seconds since helios start (cumulative
            wall-clock across all ticks). 0.0 in wall-clock-absent mode.
        `last_external_stimulus_age_seconds` — seconds since the last
            external stimulus arrived. None in wall-clock-absent mode.
        `current_episode_id` — monotonic episode counter; 0 in wall-clock-absent mode.
        `episode_elapsed_seconds` — seconds since the current episode started.
            0.0 in wall-clock-absent mode.
        `wall_clock_present` — True iff a `WallClock` is wired. False means
            honest absence; cognitive owners should fall back to legacy
            (tick-counted) paths.

    Failure semantics:
        All numeric fields are non-negative and finite. Out-of-range values
        raise `ContinuousStateError` in `__post_init__`.

    Notes:
        Frozen dataclass. `wall_clock_present` is a `bool` and is always set.
        Reading itself never mutates state; cross-tick state advances only
        via `observe_tick`.
    """

    wall_clock_elapsed_seconds: float
    last_external_stimulus_age_seconds: float | None
    current_episode_id: int
    episode_elapsed_seconds: float
    wall_clock_present: bool

    def __post_init__(self) -> None:
        if self.wall_clock_elapsed_seconds < 0.0:
            raise ContinuousStateError(
                "ContinuousStateReading.wall_clock_elapsed_seconds must be non-negative"
            )
        if not (self.current_episode_id >= 0):
            raise ContinuousStateError(
                "ContinuousStateReading.current_episode_id must be non-negative"
            )
        if self.episode_elapsed_seconds < 0.0:
            raise ContinuousStateError(
                "ContinuousStateReading.episode_elapsed_seconds must be non-negative"
            )
        if (
            self.last_external_stimulus_age_seconds is not None
            and self.last_external_stimulus_age_seconds < 0.0
        ):
            raise ContinuousStateError(
                "ContinuousStateReading.last_external_stimulus_age_seconds must be non-negative"
            )


@runtime_checkable
@dataclass
class ContinuousStateOwner(Protocol):
    """Owner: continuous-state wall-clock substrate.

    Purpose:
        First-version cross-tick continuous-state infrastructure. Reads
        wall-clock elapsed time and external stimulus presence, advances
        `wall_clock_elapsed_seconds` / `last_external_stimulus_wall_seconds` /
        `current_episode_id` / `episode_start_wall_seconds`, and exposes
        one `ContinuousStateReading` per call.

    Inputs:
        `wall_clock` — optional R92 `WallClock` (None for wall-clock-absent
            mode; honest absence, never fabricated).

    Failure semantics:
        Hard-stop. Out-of-order tick timestamps (negative delta) raise
        `ContinuousStateError`. Backwards-stepping wall-clock raises.
        Cold start (no prior tick) defaults elapsed=0 and episode_id=0
        (defined cold start, not fabricated history).

    Notes:
        Pure deterministic state machine. The owner reads no cognitive owner
        and computes no cognitive decision. It is infrastructure glue that
        every cognitive owner can opt to consume. `observe_tick` is the only
        state mutator; `sample` is pure.
    """

    wall_clock: object | None
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
    ) -> None: ...

    def sample(self) -> ContinuousStateReading: ...

    def seed_tick(self, tick_wall_seconds: float | None) -> None: ...
