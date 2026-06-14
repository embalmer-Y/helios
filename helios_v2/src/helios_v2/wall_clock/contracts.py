"""Owner: wall-clock capability source.

Owns:

- the bounded `WallClockReading` value contract (one finite, non-negative real-time reading)
- the injected `WallClock` protocol boundary (single `now()` method)
- the reserved `received_at_wall` metadata key string used by transport drivers and `02` to carry
  the per-stimulus arrival time verbatim

Does not own:

- any cognitive policy. How an owner reacts to elapsed seconds (e.g. urgency on the `09` gate,
  decay on `06` memory, or the rendered `last input: X.Xs ago` line in the `11` prompt) lives in
  those owners or in composition; this owner does not interpret the value beyond range validation.
- tick lifecycle (the `01` runtime kernel owns that and merely seeds the value into the frame).
- transport metadata schemas (`30` channel subsystem owns those; this owner contributes only one
  reserved key string the driver may use).
- persistence backends (`33` durable experience store owns those; this owner contributes only one
  additive field and never reads or interprets it).

This owner is a pure-fact capability: it produces one bounded real-time reading per call and is
never an authoritative inter-owner transport. It imports nothing from any cognitive owner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable


# Reserved metadata key for the per-stimulus arrival wall-time, written by transport drivers
# (e.g. the `31` CLI channel driver) into `InboundPacket.metadata` and preserved verbatim by `02`
# sensory normalization onto `Stimulus.metadata`. The value, when present, is a `float` (seconds
# since the Unix epoch on the system clock, or any monotonic origin a `FixedWallClock` defines).
# Absence of the key is equally valid (honest absence; the runtime is in wall-clock-absent mode
# or the driver has no clock injected).
RECEIVED_AT_WALL_METADATA_KEY: Final[str] = "received_at_wall"


class WallClockError(RuntimeError):
    """Owner: wall-clock capability source.

    Hard-stop error raised when a wall-clock invariant fails. There is no degraded path: an
    invalid reading (NaN, +/-Inf, negative) raises; a `FixedWallClock` exhausted of its seeded
    sequence raises; the runtime never papers over a broken clock with a silent default.
    """


@dataclass(frozen=True)
class WallClockReading:
    """Owner: wall-clock capability source.

    Purpose:
        One bounded real-time reading. Produced by `WallClock.now()` and consumed by composition
        as a pure fact: the kernel seeds `wall_seconds` onto `RuntimeFrame.tick_wall_seconds`,
        the CLI driver stamps it into `InboundPacket.metadata[RECEIVED_AT_WALL_METADATA_KEY]`,
        and the persistence carry seam writes it into `PersistedExperienceRecord.created_at_wall`.

    Inputs:
        `wall_seconds` - the reading itself (seconds; finite; non-negative). The natural origin
        is the Unix epoch (`time.time()`), but a deterministic `FixedWallClock` may use any
        non-negative origin it documents internally; consumers must treat the value as opaque
        seconds and never compare two readings produced by different `clock_id` values.

        `clock_id` - an optional opaque provenance string identifying the source (`"system"`,
        `"fixed"`, or any caller-defined label). It is never interpreted as content and never
        forms a cognitive judgment surface; it exists only so a downstream verifier can detect
        a clock swap.

    Failure semantics:
        Construction raises `WallClockError` on `NaN`, `+Inf`, `-Inf`, or `wall_seconds < 0.0`.
        There is no defaulting to `0.0` or to "now"; an invalid reading is a hard stop.

    Notes:
        The dataclass is frozen and hashable; consumers may freely cache it. It carries no
        timezone or calendar semantics; rendering "5 seconds ago" is composition's job.
    """

    wall_seconds: float
    clock_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.wall_seconds, (int, float)):
            raise WallClockError(
                "WallClockReading.wall_seconds must be a real number"
            )
        value = float(self.wall_seconds)
        if math.isnan(value):
            raise WallClockError("WallClockReading.wall_seconds must not be NaN")
        if math.isinf(value):
            raise WallClockError("WallClockReading.wall_seconds must be finite")
        if value < 0.0:
            raise WallClockError(
                "WallClockReading.wall_seconds must be non-negative"
            )
        # Normalize to float so equality is stable between int(10) and 10.0.
        object.__setattr__(self, "wall_seconds", value)


@runtime_checkable
class WallClock(Protocol):
    """Owner: wall-clock capability source.

    Purpose:
        The injected boundary behind which a concrete wall-clock implementation sits, so the
        runtime never hard-depends on a specific clock source. Composition constructs at most
        one instance per `assemble_runtime` call and threads the same instance into every
        consumer (kernel, CLI driver, persistence carry seam).

    Notes:
        Implementations must be O(1), synchronous, and free of I/O beyond the underlying
        platform clock (or its deterministic test substitute). They must produce a fresh
        `WallClockReading` per call (not cache one); a `FixedWallClock` may auto-advance
        between calls. They must raise `WallClockError` rather than fabricate a default when
        the underlying source cannot deliver a valid value.
    """

    def now(self) -> WallClockReading:
        """Owner: wall-clock capability source.

        Purpose:
            Produce one bounded real-time reading for the current call.

        Returns:
            One `WallClockReading` (`wall_seconds` finite, non-negative; `clock_id` opaque).

        Raises:
            `WallClockError` on a structurally invalid underlying source value or, for a
            sequence-based `FixedWallClock`, on sequence exhaustion. Never fabricates.

        Notes:
            Caller treats the reading as a pure fact and forwards it (composition glue is the
            only place that converts it to a human string).
        """

        ...
