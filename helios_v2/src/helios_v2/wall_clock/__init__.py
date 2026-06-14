"""Wall-clock capability source owner package.

Produces one bounded real-time reading per call. Composition threads the same instance into the
runtime kernel (which seeds `RuntimeFrame.tick_wall_seconds`), the CLI channel driver (which
stamps `received_at_wall` in inbound packet metadata at `submit_line` time), and the persistence
carry seam (which writes `created_at_wall` onto each `PersistedExperienceRecord`). It holds no
cognitive policy and imports no cognitive owner; rendering "5 seconds ago" or deciding what
elapsed seconds mean for the gate / memory decay / autonomy lives in those owners or in
composition glue.
"""

from .contracts import (
    RECEIVED_AT_WALL_METADATA_KEY,
    WallClock,
    WallClockError,
    WallClockReading,
)
from .engine import FixedWallClock, SystemWallClock

__all__ = [
    "FixedWallClock",
    "RECEIVED_AT_WALL_METADATA_KEY",
    "SystemWallClock",
    "WallClock",
    "WallClockError",
    "WallClockReading",
]
