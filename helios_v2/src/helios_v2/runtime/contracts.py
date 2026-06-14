from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class RuntimeDependencyStatus:
    """Structured availability report returned by the dependency owner API."""

    name: str
    available: bool
    detail: str | None = None


@runtime_checkable
class RuntimeDependencyProvider(Protocol):
    """Owner-facing API for critical dependency availability checks."""

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Return current status for a declared dependency."""


def _freeze_stage_results(stage_results: Mapping[str, object] | None) -> Mapping[str, object]:
    frozen = dict(stage_results or {})
    return MappingProxyType(frozen)


@dataclass(frozen=True)
class RuntimeFrame:
    """Immutable runtime-owned input contract passed into one stage execution.

    Carries the per-tick context every stage owner consumes.

    Fields:
        `tick_id` — monotonic per-process tick number; the canonical tick provenance handle.
        `stage_results` — frozen mapping of already-completed stages this tick.
        `tick_wall_seconds` — R92 additive optional wall-time fact for the current tick. When
            the runtime kernel has an injected `helios_v2.wall_clock.WallClock`, this is the
            value of one `WallClock.now()` call performed at the start of the tick (the same
            value is seeded into every frame of the same tick). When no wall-clock is injected,
            this is `None` (honest absence). Owners do not interpret this field; rendering and
            persistence read it as a pure fact.
    """

    tick_id: int
    stage_results: Mapping[str, object] | None = None
    tick_wall_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_results", _freeze_stage_results(self.stage_results))


@runtime_checkable
class RuntimeStage(Protocol):
    """Owner-facing lifecycle contract exposed to the runtime kernel."""

    @property
    def stage_name(self) -> str:
        """Stable stage owner name."""

    def run(self, frame: RuntimeFrame) -> object:
        """Execute one lifecycle slice against the current immutable runtime frame."""