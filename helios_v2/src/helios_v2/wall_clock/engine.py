"""Owner: wall-clock capability source.

Provides the two first-version `WallClock` implementations:

- `SystemWallClock` reads `time.time()` and is the production default wired by
  `assemble_production_runtime()`. It imports `time` lazily inside `now()` so importing this
  module never hard-depends on the call (consistent with the lazy-import discipline used by the
  `25` LLM gateway and the `34` embedding gateway).
- `FixedWallClock` is the deterministic test substitute. It supports three modes: a constant
  reading (`seconds`), an auto-advancing reading (`seconds + advance * call_index`), and an
  explicit caller-supplied sequence (`sequence=(...)`); it also exposes `manual_advance(delta)`
  for tests that want to step the clock between calls. Sequence exhaustion raises
  `WallClockError` (no silent reuse of the last value).

Both implementations are stateless w.r.t. external owners; they read no other owner and compute
no cognitive decision. They never cache a reading: every `now()` returns a fresh
`WallClockReading`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import WallClock, WallClockError, WallClockReading


@dataclass
class SystemWallClock(WallClock):
    """Owner: wall-clock capability source.

    Purpose:
        First-version production `WallClock`. Returns one `WallClockReading` per call, sourced
        from `time.time()` (the platform wall-clock). It is wired into the production assembly
        by default through `assemble_production_runtime(wall_clock=...)`; the default
        `assemble_runtime()` does not wire it, so legacy and unit-test paths remain
        wall-clock-absent.

    Failure semantics:
        Pure thin wrapper. `time.time()` returning a structurally invalid value (`NaN`/`Inf`/
        negative) surfaces through `WallClockReading.__post_init__` as `WallClockError`; this
        owner does not catch or substitute. The platform `time.time()` is robust on every
        supported platform; the failure mode exists for defensive correctness.

    Notes:
        `time` is imported lazily inside `now()` so importing this module is free; tests can
        import it without touching the system clock. The `clock_id` defaults to `"system"` so
        a downstream verifier can distinguish a real-clock reading from a `FixedWallClock` one.
    """

    clock_id: str = "system"

    def now(self) -> WallClockReading:
        """Owner: wall-clock capability source. Read the platform wall-clock once."""

        import time as _time  # lazy import; mirrors the `25`/`34` gateway pattern

        return WallClockReading(
            wall_seconds=_time.time(),
            clock_id=self.clock_id,
        )


@dataclass
class FixedWallClock(WallClock):
    """Owner: wall-clock capability source.

    Purpose:
        Deterministic test `WallClock`. Used by every network-free test that exercises any
        wall-time behavior so test outcomes are reproducible regardless of the host's actual
        wall-clock.

    Modes (mutually exclusive):

    - **constant** (default): `seconds` is returned forever.
    - **auto-advance**: the i-th `now()` call returns `seconds + advance * i` (so the first
      call returns `seconds`, the second returns `seconds + advance`, etc.).
    - **sequence**: `sequence` overrides everything; the i-th call returns `sequence[i]`,
      and the (`len(sequence)`)-th call raises `WallClockError` (sequence exhausted).

    `manual_advance(delta)` adds `delta` to the auto-advance / constant base after the next
    call (it is independent of `advance`); it is a no-op for the sequence mode.

    Failure semantics:
        - Construction rejects `advance < 0.0` (`WallClockError`; a backward-stepping
          deterministic clock is meaningless and would mask test mistakes).
        - Construction rejects `seconds < 0.0` (must produce a valid `WallClockReading`).
        - `now()` after sequence exhaustion raises `WallClockError`.
        - A reading that would itself be invalid (e.g. `seconds + advance * i` going negative
          via a custom `manual_advance`) surfaces through `WallClockReading.__post_init__`.

    Notes:
        The clock is mutable across calls (it carries a step counter) but constructs a fresh
        `WallClockReading` each call (the reading itself is frozen). The `clock_id` defaults
        to `"fixed"` so tests can distinguish it from a real `SystemWallClock` reading.
    """

    seconds: float = 0.0
    advance: float = 0.0
    sequence: tuple[float, ...] | None = None
    clock_id: str = "fixed"
    _step: int = field(default=0, init=False, repr=False)
    _manual_offset: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.seconds, (int, float)):
            raise WallClockError("FixedWallClock.seconds must be a real number")
        if not isinstance(self.advance, (int, float)):
            raise WallClockError("FixedWallClock.advance must be a real number")
        if float(self.advance) < 0.0:
            raise WallClockError(
                "FixedWallClock.advance must be non-negative (a deterministic clock cannot step backwards)"
            )
        if float(self.seconds) < 0.0:
            raise WallClockError("FixedWallClock.seconds must be non-negative")
        if self.sequence is not None:
            normalized = tuple(float(value) for value in self.sequence)
            if len(normalized) == 0:
                raise WallClockError(
                    "FixedWallClock.sequence must contain at least one reading when supplied"
                )
            for index, value in enumerate(normalized):
                if value < 0.0:
                    raise WallClockError(
                        f"FixedWallClock.sequence[{index}] must be non-negative"
                    )
            object.__setattr__(self, "sequence", normalized)
        # Normalize to float so equality remains stable.
        object.__setattr__(self, "seconds", float(self.seconds))
        object.__setattr__(self, "advance", float(self.advance))

    def now(self) -> WallClockReading:
        """Owner: wall-clock capability source. Produce the next deterministic reading."""

        if self.sequence is not None:
            if self._step >= len(self.sequence):
                raise WallClockError(
                    "FixedWallClock.sequence is exhausted; the test must seed more readings"
                )
            value = self.sequence[self._step]
        else:
            value = self.seconds + self.advance * self._step + self._manual_offset
        self._step += 1
        return WallClockReading(wall_seconds=value, clock_id=self.clock_id)

    def manual_advance(self, delta: float) -> None:
        """Owner: wall-clock capability source.

        Purpose:
            Step the clock forward by `delta` seconds for the next and subsequent `now()`
            calls. Independent of the `advance` auto-step. No-op for sequence mode (which
            is fully scripted by the seeded sequence).

        Failure semantics:
            Rejects `delta < 0.0` (`WallClockError`). The clock cannot step backwards.
        """

        if not isinstance(delta, (int, float)):
            raise WallClockError("FixedWallClock.manual_advance(delta) must be a real number")
        if float(delta) < 0.0:
            raise WallClockError("FixedWallClock.manual_advance(delta) must be non-negative")
        if self.sequence is not None:
            return
        self._manual_offset += float(delta)
