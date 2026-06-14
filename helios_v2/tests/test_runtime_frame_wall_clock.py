"""R92: tests for `RuntimeFrame.tick_wall_seconds` + kernel seeding.

Asserts:
  - The default `RuntimeFrame` has `tick_wall_seconds=None` (legacy-byte-for-byte).
  - With a `FixedWallClock` wired into the kernel, every stage of one tick reads the same
    `tick_wall_seconds`, and successive ticks advance by the clock's auto-step.
  - With no clock injected, every frame carries `tick_wall_seconds=None` (the kernel does not
    fall back to `time.time()`).
  - `RuntimeTickResult.tick_wall_seconds` mirrors the seeded value.
  - The kernel calls `WallClock.now()` exactly once per tick (not per stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pytest

from helios_v2.runtime.contracts import RuntimeDependencyStatus, RuntimeFrame
from helios_v2.runtime.dependencies import RuntimeDependencySpec
from helios_v2.runtime.kernel import RuntimeKernel, RuntimeTickResult
from helios_v2.wall_clock import FixedWallClock


# ---------------------------------------------------------------------------
# RuntimeFrame additive field
# ---------------------------------------------------------------------------


def test_runtime_frame_default_tick_wall_seconds_is_none() -> None:
    frame = RuntimeFrame(tick_id=1)
    assert frame.tick_wall_seconds is None


def test_runtime_frame_accepts_explicit_tick_wall_seconds() -> None:
    frame = RuntimeFrame(tick_id=1, tick_wall_seconds=10.5)
    assert frame.tick_wall_seconds == 10.5


def test_runtime_frame_is_still_frozen() -> None:
    frame = RuntimeFrame(tick_id=1, tick_wall_seconds=5.0)
    with pytest.raises(Exception):
        frame.tick_wall_seconds = 10.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Kernel seeding — fixtures
# ---------------------------------------------------------------------------


class _AlwaysAvailableProvider:
    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        return RuntimeDependencyStatus(name=name, available=True, detail=None)


@dataclass
class _RecordingStage:
    """Captures the `RuntimeFrame` it was passed each call."""

    stage_name: str
    captured_frames: List[RuntimeFrame] = field(default_factory=list)

    def run(self, frame: RuntimeFrame) -> object:
        self.captured_frames.append(frame)
        return {"stage": self.stage_name, "tick_wall_seconds": frame.tick_wall_seconds}


def _build_kernel(*stages: _RecordingStage, wall_clock=None) -> RuntimeKernel:
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=_AlwaysAvailableProvider(),
        wall_clock=wall_clock,
    )
    for stage in stages:
        kernel.register_stage(stage)
    kernel.startup()
    return kernel


# ---------------------------------------------------------------------------
# Default behavior (no wall_clock): every frame carries None
# ---------------------------------------------------------------------------


def test_kernel_without_wall_clock_seeds_none_into_every_frame() -> None:
    s1 = _RecordingStage(stage_name="alpha")
    s2 = _RecordingStage(stage_name="beta")
    kernel = _build_kernel(s1, s2)

    result_1 = kernel.tick()
    result_2 = kernel.tick()

    for stage in (s1, s2):
        for frame in stage.captured_frames:
            assert frame.tick_wall_seconds is None

    assert isinstance(result_1, RuntimeTickResult)
    assert result_1.tick_wall_seconds is None
    assert result_2.tick_wall_seconds is None


# ---------------------------------------------------------------------------
# Wired wall_clock: same value across stages of one tick
# ---------------------------------------------------------------------------


def test_kernel_with_fixed_clock_seeds_same_value_across_stages() -> None:
    clock = FixedWallClock(seconds=100.0, advance=1.0)
    s1 = _RecordingStage(stage_name="alpha")
    s2 = _RecordingStage(stage_name="beta")
    s3 = _RecordingStage(stage_name="gamma")
    kernel = _build_kernel(s1, s2, s3, wall_clock=clock)

    result = kernel.tick()

    # All three stages of the same tick must see the same `tick_wall_seconds`.
    assert s1.captured_frames[0].tick_wall_seconds == 100.0
    assert s2.captured_frames[0].tick_wall_seconds == 100.0
    assert s3.captured_frames[0].tick_wall_seconds == 100.0
    assert result.tick_wall_seconds == 100.0


# ---------------------------------------------------------------------------
# Wired wall_clock: successive ticks advance
# ---------------------------------------------------------------------------


def test_kernel_with_fixed_clock_advances_between_ticks() -> None:
    clock = FixedWallClock(seconds=10.0, advance=1.0)
    stage = _RecordingStage(stage_name="alpha")
    kernel = _build_kernel(stage, wall_clock=clock)

    r1 = kernel.tick()
    r2 = kernel.tick()
    r3 = kernel.tick()

    assert r1.tick_wall_seconds == 10.0
    assert r2.tick_wall_seconds == 11.0
    assert r3.tick_wall_seconds == 12.0
    # Per-stage frames record the same value as the result.
    assert [f.tick_wall_seconds for f in stage.captured_frames] == [10.0, 11.0, 12.0]


# ---------------------------------------------------------------------------
# Wired wall_clock: now() called exactly once per tick (not per stage)
# ---------------------------------------------------------------------------


def test_kernel_calls_wall_clock_now_once_per_tick() -> None:
    @dataclass
    class _CountingClock:
        clock: FixedWallClock = field(default_factory=lambda: FixedWallClock(seconds=0.0, advance=1.0))
        call_count: int = 0

        def now(self):
            self.call_count += 1
            return self.clock.now()

    counting = _CountingClock()
    s1 = _RecordingStage(stage_name="alpha")
    s2 = _RecordingStage(stage_name="beta")
    s3 = _RecordingStage(stage_name="gamma")
    kernel = _build_kernel(s1, s2, s3, wall_clock=counting)

    kernel.tick()
    assert counting.call_count == 1, "WallClock.now() must be called once per tick, not per stage"

    kernel.tick()
    assert counting.call_count == 2

    kernel.tick()
    assert counting.call_count == 3


# ---------------------------------------------------------------------------
# Honest absence: no fabrication when clock is absent
# ---------------------------------------------------------------------------


def test_kernel_without_clock_does_not_call_time_time_for_seeding() -> None:
    """Negative control: with no `wall_clock`, no captured frame can have a non-None tick_wall_seconds.

    This is the §3.2 honest-absence rule pinned as a test.
    """
    stage = _RecordingStage(stage_name="alpha")
    kernel = _build_kernel(stage)
    kernel.tick()
    kernel.tick()

    for frame in stage.captured_frames:
        assert frame.tick_wall_seconds is None
