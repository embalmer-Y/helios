"""Tests for R-PROTO-LEARN.P-TEMPORAL ContinuousStateOwner.

Phase 2 acceptance: 8 unit + 4 integration = 12 tests pass.
"""

from __future__ import annotations

import pytest

from helios_v2.temporal_continuous_state import (
    ContinuousStateError,
    ContinuousStateReading,
    FirstVersionContinuousStateOwner,
)
from helios_v2.wall_clock.engine import FixedWallClock


# =============================================================================
# Unit tests (8)
# =============================================================================


def test_continuous_state_cold_start_returns_zero_reading():
    owner = FirstVersionContinuousStateOwner(wall_clock=None)
    reading = owner.sample()
    assert reading.wall_clock_present is False
    assert reading.wall_clock_elapsed_seconds == 0.0
    assert reading.last_external_stimulus_age_seconds is None
    assert reading.current_episode_id == 0
    assert reading.episode_elapsed_seconds == 0.0


def test_continuous_state_advances_with_fixed_wall_clock():
    clk = FixedWallClock(seconds=1000.0, advance=1.0)
    owner = FirstVersionContinuousStateOwner(wall_clock=clk)
    for tick in range(5):
        ts = clk.now().wall_seconds
        owner.observe_tick(
            fired=False,
            external_stimulus_present=(tick == 1),
            tick_wall_seconds=ts,
        )
    reading = owner.sample()
    # 5 ticks × 1.0s advance = 5.0s elapsed (after cold-start init at tick 0)
    # tick 0: cold-start (no delta). tick 1-4: 4 deltas of 1.0s each = 4.0s
    assert reading.wall_clock_present is True
    assert reading.wall_clock_elapsed_seconds == pytest.approx(4.0, abs=1e-4)
    assert reading.current_episode_id == 0


def test_continuous_state_records_external_stimulus_age():
    clk = FixedWallClock(seconds=1000.0, advance=1.0)
    owner = FirstVersionContinuousStateOwner(wall_clock=clk)
    # tick 0: external stimulus arrives
    ts0 = clk.now().wall_seconds
    owner.observe_tick(
        fired=False,
        external_stimulus_present=True,
        tick_wall_seconds=ts0,
    )
    # tick 1-4: no external stimulus, 1s each
    for _ in range(4):
        ts = clk.now().wall_seconds
        owner.observe_tick(
            fired=False,
            external_stimulus_present=False,
            tick_wall_seconds=ts,
        )
    reading = owner.sample()
    # 4 ticks after stimulus = 4.0s age
    assert reading.last_external_stimulus_age_seconds == pytest.approx(4.0, abs=1e-4)


def test_continuous_state_episode_split_on_large_gap():
    owner = FirstVersionContinuousStateOwner(
        wall_clock=None,
        new_episode_gap_seconds=10.0,
    )
    # tick 0: cold-start at t=0
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=0.0)
    # tick 1: +1s (same episode)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=1.0)
    # tick 2: +15s gap (NEW episode)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=16.0)
    # tick 3: +1s (same new episode)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=17.0)
    reading = owner.sample()
    assert reading.current_episode_id == 1   # episode split detected
    assert reading.episode_elapsed_seconds == pytest.approx(1.0, abs=1e-4)


def test_continuous_state_no_episode_split_on_small_gap():
    owner = FirstVersionContinuousStateOwner(
        wall_clock=None,
        new_episode_gap_seconds=60.0,
    )
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=0.0)
    for tick in range(1, 11):
        owner.observe_tick(
            fired=False,
            external_stimulus_present=False,
            tick_wall_seconds=tick * 5.0,   # 5s gaps, all < 60s
        )
    reading = owner.sample()
    assert reading.current_episode_id == 0
    assert reading.episode_elapsed_seconds == pytest.approx(50.0, abs=1e-4)  # 11th tick at t=50, episode start at t=0


def test_continuous_state_backwards_clock_raises():
    owner = FirstVersionContinuousStateOwner(wall_clock=None)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=10.0)
    with pytest.raises(ContinuousStateError, match="backwards-stepping"):
        owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=5.0)


def test_continuous_state_negative_tick_raises():
    owner = FirstVersionContinuousStateOwner(wall_clock=None)
    with pytest.raises(ContinuousStateError, match="must be non-negative"):
        owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=-1.0)


def test_continuous_state_reading_rejects_negative_fields():
    with pytest.raises(ContinuousStateError):
        ContinuousStateReading(
            wall_clock_elapsed_seconds=-1.0,
            last_external_stimulus_age_seconds=None,
            current_episode_id=0,
            episode_elapsed_seconds=0.0,
            wall_clock_present=True,
        )


# =============================================================================
# Integration tests (4)
# =============================================================================


def test_integration_50_tick_deterministic_replay():
    """50-tick deterministic replay: elapsed accumulates, episode_id monotonic."""
    clk = FixedWallClock(seconds=0.0, advance=1.0)
    owner = FirstVersionContinuousStateOwner(wall_clock=clk)
    elapsed_history = []
    for _ in range(50):
        ts = clk.now().wall_seconds
        owner.observe_tick(
            fired=False,
            external_stimulus_present=False,
            tick_wall_seconds=ts,
        )
        elapsed_history.append(owner.sample().wall_clock_elapsed_seconds)
    # Strictly non-decreasing, ends at 49.0s (50 ticks - 1 cold start = 49 deltas)
    for prev, curr in zip(elapsed_history, elapsed_history[1:]):
        assert curr >= prev
    assert elapsed_history[-1] == pytest.approx(49.0, abs=1e-4)
    assert owner.sample().current_episode_id == 0


def test_integration_episode_id_monotonic_across_splits():
    """3 episode splits across 100 ticks (every 25 ticks a 100s gap)."""
    owner = FirstVersionContinuousStateOwner(
        wall_clock=None,
        new_episode_gap_seconds=50.0,
    )
    # Tick 0 cold-start at t=0
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=0.0)
    # 24 ticks +1s each (within first episode)
    for tick in range(1, 25):
        owner.observe_tick(
            fired=False,
            external_stimulus_present=False,
            tick_wall_seconds=float(tick),
        )
    assert owner.sample().current_episode_id == 0
    # Now a 100s gap → episode split
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=125.0)
    assert owner.sample().current_episode_id == 1
    # Another gap → episode 2
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=230.0)
    assert owner.sample().current_episode_id == 2


def test_integration_wall_clock_absent_mode_still_safe():
    """With wall_clock=None and tick_wall_seconds=None, no crash, no fake data."""
    owner = FirstVersionContinuousStateOwner(wall_clock=None)
    for _ in range(10):
        owner.observe_tick(
            fired=True,
            external_stimulus_present=False,
            tick_wall_seconds=None,
        )
    reading = owner.sample()
    assert reading.wall_clock_present is False
    assert reading.wall_clock_elapsed_seconds == 0.0
    assert reading.last_external_stimulus_age_seconds is None
    assert reading.current_episode_id == 0


def test_integration_seed_tick_initializes_anchor():
    """seed_tick sets prior-tick anchor without forcing episode arithmetic."""
    owner = FirstVersionContinuousStateOwner(wall_clock=None)
    owner.seed_tick(tick_wall_seconds=100.0)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=100.5)
    owner.observe_tick(fired=False, external_stimulus_present=False, tick_wall_seconds=101.0)
    reading = owner.sample()
    assert reading.wall_clock_present is True
    assert reading.wall_clock_elapsed_seconds == pytest.approx(1.0, abs=1e-4)
    assert reading.current_episode_id == 0   # 0.5s gap, no split
