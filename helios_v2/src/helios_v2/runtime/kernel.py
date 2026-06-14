from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from helios_v2.observability import RuntimeObservabilityRecorder
from helios_v2.wall_clock import WallClock

from .contracts import RuntimeDependencyProvider, RuntimeFrame, RuntimeStage
from .dependencies import RuntimeDependencySpec, RuntimeStartupError, validate_critical_dependencies

# Stable emitting-owner name used for all kernel-originated observability events.
_KERNEL_OWNER = "runtime_kernel"


@dataclass(frozen=True)
class RuntimeTickResult:
    """Structured snapshot of per-stage outputs for one kernel tick.

    Fields:
        `tick_id` — monotonic per-process tick number.
        `stage_results` — frozen mapping of stage-owner outputs published this tick.
        `tick_wall_seconds` — R92 additive optional wall-time fact for the just-completed
            tick. When the kernel has an injected `WallClock`, this is the value of the
            single `WallClock.now()` call performed at the start of the tick (the same value
            seeded into every `RuntimeFrame` of this tick). When no wall-clock is injected,
            this is `None` (honest absence). The composition carry seam reads this field to
            stamp `PersistedExperienceRecord.created_at_wall`.
    """

    tick_id: int
    stage_results: Mapping[str, object]
    tick_wall_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_results", MappingProxyType(dict(self.stage_results)))


@dataclass
class RuntimeKernel:
    """Narrow runtime owner for startup gating and ordered stage dispatch."""

    dependency_specs: list[RuntimeDependencySpec]
    dependency_provider: RuntimeDependencyProvider
    recorder: RuntimeObservabilityRecorder | None = None
    wall_clock: WallClock | None = None
    _stages: list[RuntimeStage] = field(default_factory=list)
    _tick_id: int = 0

    def register_stage(self, stage: RuntimeStage) -> None:
        """Register one stage owner by stable name and reject duplicate stage ownership."""

        stage_name = stage.stage_name
        if any(existing.stage_name == stage_name for existing in self._stages):
            raise ValueError(f"Duplicate runtime stage: {stage_name}")
        self._stages.append(stage)

    def startup(self) -> None:
        """Run the fail-fast startup gate before any runtime stage executes.

        When an observability recorder is injected, a `runtime_startup` event is
        emitted on success and a `runtime_startup_failed` event is emitted before
        re-raising on missing critical dependencies.
        """

        try:
            validate_critical_dependencies(self.dependency_specs, self.dependency_provider)
        except RuntimeStartupError as error:
            if self.recorder is not None:
                self.recorder.record(
                    severity="critical",
                    event_kind="runtime_startup_failed",
                    owner=_KERNEL_OWNER,
                    message="Runtime startup failed due to missing critical dependencies",
                    payload={"missing_dependencies": list(error.missing_dependencies)},
                )
            raise
        if self.recorder is not None:
            self.recorder.record(
                severity="info",
                event_kind="runtime_startup",
                owner=_KERNEL_OWNER,
                message="Runtime startup completed and all critical dependencies are available",
                payload={"stage_count": len(self._stages)},
            )

    def tick(self) -> RuntimeTickResult:
        """Execute all registered stages in order and aggregate their owner outputs.

        When an observability recorder is injected, each stage emits a
        `stage_started` event, then a `stage_completed` event carrying its
        execution duration, or a `stage_failed` event before re-raising. A
        `runtime_tick_completed` event is emitted after all stages complete.
        """

        stage_results: dict[str, object] = {}
        next_tick_id = self._tick_id + 1
        # R92: seed one wall-time reading at the start of the tick when a clock is wired, so
        # every stage of this same tick reads the same `tick_wall_seconds`. With no clock,
        # the value remains `None` (honest absence; never substituted by `time.time()` or
        # `time.perf_counter()`).
        tick_wall_seconds: float | None = None
        if self.wall_clock is not None:
            tick_wall_seconds = self.wall_clock.now().wall_seconds
        for index, stage in enumerate(self._stages):
            stage_name = stage.stage_name
            if self.recorder is not None:
                self.recorder.record(
                    severity="debug",
                    event_kind="stage_started",
                    owner=_KERNEL_OWNER,
                    message=f"Stage '{stage_name}' started",
                    tick_id=next_tick_id,
                    stage_name=stage_name,
                    payload={"stage_index": index},
                )
            frame = RuntimeFrame(
                tick_id=next_tick_id,
                stage_results=stage_results,
                tick_wall_seconds=tick_wall_seconds,
            )
            started_at = time.perf_counter()
            try:
                result = stage.run(frame)
            except Exception as error:
                if self.recorder is not None:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                    self.recorder.record(
                        severity="error",
                        event_kind="stage_failed",
                        owner=_KERNEL_OWNER,
                        message=f"Stage '{stage_name}' failed: {error}",
                        tick_id=next_tick_id,
                        stage_name=stage_name,
                        payload={
                            "stage_index": index,
                            "duration_ms": round(elapsed_ms, 4),
                            "error_type": type(error).__name__,
                        },
                    )
                raise
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            stage_results[stage_name] = result
            if self.recorder is not None:
                self.recorder.record(
                    severity="info",
                    event_kind="stage_completed",
                    owner=_KERNEL_OWNER,
                    message=f"Stage '{stage_name}' completed",
                    tick_id=next_tick_id,
                    stage_name=stage_name,
                    payload={
                        "stage_index": index,
                        "duration_ms": round(elapsed_ms, 4),
                    },
                )
        self._tick_id = next_tick_id
        if self.recorder is not None:
            self.recorder.record(
                severity="info",
                event_kind="runtime_tick_completed",
                owner=_KERNEL_OWNER,
                message=f"Runtime tick {next_tick_id} completed",
                tick_id=next_tick_id,
                payload={"stage_count": len(self._stages)},
            )
        return RuntimeTickResult(
            tick_id=next_tick_id,
            stage_results=stage_results,
            tick_wall_seconds=tick_wall_seconds,
        )
