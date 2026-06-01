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
    """Immutable runtime-owned input contract passed into one stage execution."""

    tick_id: int
    stage_results: Mapping[str, object] | None = None

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