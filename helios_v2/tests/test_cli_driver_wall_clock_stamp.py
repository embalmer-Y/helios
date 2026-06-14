"""R92: tests for `CliChannelDriver` arrival-time stamping under an injected `WallClock`.

Asserts:
  - Without a `wall_clock`, packets carry NO `received_at_wall` metadata key (legacy unchanged).
  - With a `FixedWallClock`, `submit_line` captures the arrival time and `drain_inbound`
    surfaces it on the resulting packet's metadata.
  - The stamp reflects ARRIVAL time (when `submit_line` was called), not DRAIN time.
  - Two lines submitted at different clock readings get distinct stamps.
  - Empty/whitespace lines are still skipped at drain (their slot is consumed but no packet
    emitted), even when a clock is wired.
  - Overflow path does not consume a clock reading (the line is rejected before storage).
"""

from __future__ import annotations

import pytest

from helios_v2.channel.drivers.cli import CliChannelDriver, CliDriverConfig
from helios_v2.wall_clock import RECEIVED_AT_WALL_METADATA_KEY, FixedWallClock


def _make_driver(*, wall_clock=None, max_backlog: int = 16) -> CliChannelDriver:
    captured_output: list[str] = []
    return CliChannelDriver(
        output_sink=captured_output.append,
        config=CliDriverConfig(max_backlog=max_backlog),
        wall_clock=wall_clock,
    )


# ---------------------------------------------------------------------------
# Honest absence: no clock => no metadata key
# ---------------------------------------------------------------------------


def test_cli_driver_without_clock_omits_received_at_wall_metadata() -> None:
    driver = _make_driver()
    assert driver.submit_line("hello") is True
    result = driver.drain_inbound(budget=8)
    assert len(result.packets) == 1
    metadata = dict(result.packets[0].metadata or {})
    assert RECEIVED_AT_WALL_METADATA_KEY not in metadata
    # Existing metadata keys still present (regression).
    assert metadata["user_label"] == "operator"
    assert metadata["session_label"] == "local-cli"


# ---------------------------------------------------------------------------
# Wired clock: arrival time stamped on the packet
# ---------------------------------------------------------------------------


def test_cli_driver_with_clock_stamps_received_at_wall_on_packet() -> None:
    clock = FixedWallClock(seconds=10.0, advance=0.0)  # constant clock
    driver = _make_driver(wall_clock=clock)
    assert driver.submit_line("hello") is True

    result = driver.drain_inbound(budget=8)
    assert len(result.packets) == 1
    metadata = dict(result.packets[0].metadata or {})
    assert metadata[RECEIVED_AT_WALL_METADATA_KEY] == 10.0


# ---------------------------------------------------------------------------
# Arrival time, not drain time
# ---------------------------------------------------------------------------


def test_cli_driver_stamp_is_arrival_time_not_drain_time() -> None:
    """The clock reading captured at `submit_line` must be the one written into metadata,
    even though `drain_inbound` may run much later."""

    clock = FixedWallClock(seconds=5.0, advance=10.0)
    # First call to clock.now() will return 5.0 (the arrival time at submit_line).
    driver = _make_driver(wall_clock=clock)
    assert driver.submit_line("first") is True

    # Without further submits, the next clock reading would be 15.0; we will burn a few
    # readings to simulate "time has passed" before drain. (drain_inbound itself does NOT
    # call now().)
    clock.now()  # 15.0 (consumed by something external; just to advance the step counter)
    clock.now()  # 25.0
    # Drain happens "later" — the captured 5.0 must still be what's reported.
    result = driver.drain_inbound(budget=8)
    assert len(result.packets) == 1
    assert dict(result.packets[0].metadata or {})[RECEIVED_AT_WALL_METADATA_KEY] == 5.0


# ---------------------------------------------------------------------------
# Multiple lines: each gets its own stamp
# ---------------------------------------------------------------------------


def test_cli_driver_multiple_lines_get_distinct_stamps() -> None:
    clock = FixedWallClock(seconds=10.0, advance=1.0)  # 10, 11, 12, ...
    driver = _make_driver(wall_clock=clock)
    driver.submit_line("a")  # arrives at t=10
    driver.submit_line("b")  # arrives at t=11
    driver.submit_line("c")  # arrives at t=12

    result = driver.drain_inbound(budget=8)
    assert len(result.packets) == 3
    stamps = [dict(p.metadata or {})[RECEIVED_AT_WALL_METADATA_KEY] for p in result.packets]
    assert stamps == [10.0, 11.0, 12.0]


# ---------------------------------------------------------------------------
# Whitespace lines: consumed but skipped at drain
# ---------------------------------------------------------------------------


def test_cli_driver_whitespace_line_does_not_emit_packet_even_with_clock() -> None:
    clock = FixedWallClock(seconds=10.0, advance=1.0)
    driver = _make_driver(wall_clock=clock)
    driver.submit_line("  \t  ")  # arrives at t=10 but is whitespace
    driver.submit_line("hello")  # arrives at t=11

    result = driver.drain_inbound(budget=8)
    # Only the non-empty line emits a packet; the whitespace was still consumed (so its slot
    # in the backlog is gone), but no packet exists for it.
    assert len(result.packets) == 1
    assert dict(result.packets[0].metadata or {})[RECEIVED_AT_WALL_METADATA_KEY] == 11.0


# ---------------------------------------------------------------------------
# Overflow path: no clock reading consumed when rejected
# ---------------------------------------------------------------------------


def test_cli_driver_overflow_does_not_consume_clock_reading() -> None:
    clock = FixedWallClock(seconds=100.0, advance=1.0)
    driver = _make_driver(wall_clock=clock, max_backlog=2)

    assert driver.submit_line("a") is True   # accepted at t=100
    assert driver.submit_line("b") is True   # accepted at t=101
    assert driver.submit_line("c") is False  # overflow (rejected)
    # The next accepted line should get t=102 (not t=103), proving the overflow path did
    # not consume a clock reading.
    assert driver.submit_line("d") is False  # still full (backlog still 2)
    result = driver.drain_inbound(budget=8)
    assert len(result.packets) == 2
    stamps = [dict(p.metadata or {})[RECEIVED_AT_WALL_METADATA_KEY] for p in result.packets]
    assert stamps == [100.0, 101.0]
    # Now backlog is empty; submit one more.
    assert driver.submit_line("e") is True  # arrives at t=102
    second = driver.drain_inbound(budget=8)
    assert len(second.packets) == 1
    assert dict(second.packets[0].metadata or {})[RECEIVED_AT_WALL_METADATA_KEY] == 102.0


# ---------------------------------------------------------------------------
# Boundary: driver does not call WallClock.now() in drain_inbound
# ---------------------------------------------------------------------------


def test_cli_driver_drain_does_not_call_wall_clock() -> None:
    """`submit_line` calls `now()` once per line; `drain_inbound` must not call `now()`."""

    class _CountingClock:
        def __init__(self) -> None:
            self.calls = 0

        def now(self):
            self.calls += 1
            return FixedWallClock(seconds=1.0).now()

    clock = _CountingClock()
    driver = _make_driver(wall_clock=clock)
    driver.submit_line("a")
    driver.submit_line("b")
    driver.submit_line("c")
    assert clock.calls == 3  # three submits

    driver.drain_inbound(budget=8)
    assert clock.calls == 3  # still three; drain did not call now()
