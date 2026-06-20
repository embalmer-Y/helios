"""Owner: continuous-state wall-clock substrate (R-PROTO-LEARN.P-TEMPORAL).

Public surface for the cross-tick wall-clock-driven continuous-state owner.
It holds one cross-tick continuous state (wall-clock elapsed seconds since
helios start, last external stimulus wall-clock, current episode id, episode
start wall-clock) and exposes one bounded reading per tick. It is
infrastructure, like `wall_clock` / `observability` / `persistence`; it holds
no cognitive policy and imports no cognitive owner.
"""

from .contracts import (
    ContinuousStateError,
    ContinuousStateOwner,
    ContinuousStateReading,
)
from .engine import FirstVersionContinuousStateOwner

__all__ = [
    "ContinuousStateError",
    "ContinuousStateOwner",
    "ContinuousStateReading",
    "FirstVersionContinuousStateOwner",
]
