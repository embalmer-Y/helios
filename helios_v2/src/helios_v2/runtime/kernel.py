from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .contracts import RuntimeDependencyProvider, RuntimeFrame, RuntimeStage
from .dependencies import RuntimeDependencySpec, validate_critical_dependencies


@dataclass(frozen=True)
class RuntimeTickResult:
    """Structured snapshot of per-stage outputs for one kernel tick."""

    tick_id: int
    stage_results: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_results", MappingProxyType(dict(self.stage_results)))


@dataclass
class RuntimeKernel:
    """Narrow runtime owner for startup gating and ordered stage dispatch."""

    dependency_specs: list[RuntimeDependencySpec]
    dependency_provider: RuntimeDependencyProvider
    _stages: list[RuntimeStage] = field(default_factory=list)
    _tick_id: int = 0

    def register_stage(self, stage: RuntimeStage) -> None:
        """Register one stage owner by stable name and reject duplicate stage ownership."""

        stage_name = stage.stage_name
        if any(existing.stage_name == stage_name for existing in self._stages):
            raise ValueError(f"Duplicate runtime stage: {stage_name}")
        self._stages.append(stage)

    def startup(self) -> None:
        """Run the fail-fast startup gate before any runtime stage executes."""

        validate_critical_dependencies(self.dependency_specs, self.dependency_provider)

    def tick(self) -> RuntimeTickResult:
        """Execute all registered stages in order and aggregate their owner outputs."""

        stage_results: dict[str, object] = {}
        next_tick_id = self._tick_id + 1
        for stage in self._stages:
            frame = RuntimeFrame(tick_id=next_tick_id, stage_results=stage_results)
            stage_results[stage.stage_name] = stage.run(frame)
        self._tick_id = next_tick_id
        return RuntimeTickResult(tick_id=next_tick_id, stage_results=stage_results)