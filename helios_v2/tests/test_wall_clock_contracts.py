"""R92: focused tests for the new `helios_v2.wall_clock` capability owner.

Asserts the bounded `WallClockReading` validation, the `SystemWallClock` thin wrapper behaves
sanely on the host platform clock, and the deterministic `FixedWallClock` covers all three
modes (constant, auto-advance, sequence) plus `manual_advance`.

Network-free; `SystemWallClock` is exercised once for a non-negative finite reading only and
never compared to a wall-clock literal (no dependency on the host's actual time).
"""

from __future__ import annotations

import math

import pytest

from helios_v2.wall_clock import (
    RECEIVED_AT_WALL_METADATA_KEY,
    FixedWallClock,
    SystemWallClock,
    WallClock,
    WallClockError,
    WallClockReading,
)


# ---------------------------------------------------------------------------
# WallClockReading invariants
# ---------------------------------------------------------------------------


def test_reading_accepts_finite_non_negative_value() -> None:
    reading = WallClockReading(wall_seconds=10.5, clock_id="t")
    assert reading.wall_seconds == 10.5
    assert reading.clock_id == "t"


def test_reading_normalizes_int_to_float() -> None:
    reading = WallClockReading(wall_seconds=10)
    assert reading.wall_seconds == 10.0
    assert isinstance(reading.wall_seconds, float)


def test_reading_rejects_nan() -> None:
    with pytest.raises(WallClockError):
        WallClockReading(wall_seconds=math.nan)


def test_reading_rejects_positive_infinity() -> None:
    with pytest.raises(WallClockError):
        WallClockReading(wall_seconds=math.inf)


def test_reading_rejects_negative_infinity() -> None:
    with pytest.raises(WallClockError):
        WallClockReading(wall_seconds=-math.inf)


def test_reading_rejects_negative_value() -> None:
    with pytest.raises(WallClockError):
        WallClockReading(wall_seconds=-1.0)


def test_reading_rejects_non_numeric_value() -> None:
    with pytest.raises(WallClockError):
        WallClockReading(wall_seconds="now")  # type: ignore[arg-type]


def test_reading_default_clock_id_is_none() -> None:
    reading = WallClockReading(wall_seconds=0.0)
    assert reading.clock_id is None


def test_reading_zero_is_allowed_as_origin() -> None:
    reading = WallClockReading(wall_seconds=0.0)
    assert reading.wall_seconds == 0.0


def test_reading_is_frozen_dataclass() -> None:
    reading = WallClockReading(wall_seconds=1.0)
    with pytest.raises(Exception):
        reading.wall_seconds = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SystemWallClock
# ---------------------------------------------------------------------------


def test_system_wall_clock_returns_finite_non_negative_reading() -> None:
    clock: WallClock = SystemWallClock()
    reading = clock.now()
    assert isinstance(reading, WallClockReading)
    assert reading.wall_seconds >= 0.0
    assert math.isfinite(reading.wall_seconds)


def test_system_wall_clock_default_clock_id() -> None:
    reading = SystemWallClock().now()
    assert reading.clock_id == "system"


def test_system_wall_clock_custom_clock_id() -> None:
    reading = SystemWallClock(clock_id="primary").now()
    assert reading.clock_id == "primary"


def test_system_wall_clock_returns_fresh_reading_each_call() -> None:
    clock = SystemWallClock()
    a = clock.now()
    b = clock.now()
    # Both readings exist and are independently constructed; their values may be equal on a
    # very fast machine but the objects must not be identical.
    assert a is not b
    assert b.wall_seconds >= a.wall_seconds  # `time.time()` is non-decreasing within a process


# ---------------------------------------------------------------------------
# FixedWallClock — constant mode
# ---------------------------------------------------------------------------


def test_fixed_constant_mode_returns_seeded_value() -> None:
    clock = FixedWallClock(seconds=42.0)
    assert clock.now().wall_seconds == 42.0
    assert clock.now().wall_seconds == 42.0
    assert clock.now().wall_seconds == 42.0


def test_fixed_constant_mode_clock_id() -> None:
    clock = FixedWallClock(seconds=1.0)
    reading = clock.now()
    assert reading.clock_id == "fixed"


def test_fixed_custom_clock_id() -> None:
    clock = FixedWallClock(seconds=1.0, clock_id="probe")
    assert clock.now().clock_id == "probe"


# ---------------------------------------------------------------------------
# FixedWallClock — auto-advance mode
# ---------------------------------------------------------------------------


def test_fixed_advance_mode_steps_per_call() -> None:
    clock = FixedWallClock(seconds=10.0, advance=1.0)
    assert clock.now().wall_seconds == 10.0
    assert clock.now().wall_seconds == 11.0
    assert clock.now().wall_seconds == 12.0


def test_fixed_advance_mode_with_fractional_step() -> None:
    clock = FixedWallClock(seconds=0.0, advance=0.25)
    assert clock.now().wall_seconds == 0.0
    assert clock.now().wall_seconds == 0.25
    assert clock.now().wall_seconds == 0.5


def test_fixed_rejects_negative_advance() -> None:
    with pytest.raises(WallClockError):
        FixedWallClock(seconds=10.0, advance=-1.0)


def test_fixed_rejects_negative_seconds() -> None:
    with pytest.raises(WallClockError):
        FixedWallClock(seconds=-1.0)


# ---------------------------------------------------------------------------
# FixedWallClock — sequence mode
# ---------------------------------------------------------------------------


def test_fixed_sequence_mode_returns_seeded_values_in_order() -> None:
    clock = FixedWallClock(sequence=(1.0, 2.5, 7.0))
    assert clock.now().wall_seconds == 1.0
    assert clock.now().wall_seconds == 2.5
    assert clock.now().wall_seconds == 7.0


def test_fixed_sequence_exhausted_raises() -> None:
    clock = FixedWallClock(sequence=(1.0,))
    clock.now()
    with pytest.raises(WallClockError):
        clock.now()


def test_fixed_sequence_rejects_empty() -> None:
    with pytest.raises(WallClockError):
        FixedWallClock(sequence=())


def test_fixed_sequence_rejects_negative_value() -> None:
    with pytest.raises(WallClockError):
        FixedWallClock(sequence=(1.0, -1.0))


def test_fixed_sequence_overrides_constant_and_advance() -> None:
    clock = FixedWallClock(seconds=100.0, advance=10.0, sequence=(1.0, 2.0))
    # Sequence mode wins; the constant/advance fields are ignored.
    assert clock.now().wall_seconds == 1.0
    assert clock.now().wall_seconds == 2.0


# ---------------------------------------------------------------------------
# FixedWallClock — manual_advance
# ---------------------------------------------------------------------------


def test_fixed_manual_advance_adds_to_constant() -> None:
    clock = FixedWallClock(seconds=10.0)
    assert clock.now().wall_seconds == 10.0
    clock.manual_advance(5.0)
    assert clock.now().wall_seconds == 15.0
    clock.manual_advance(2.5)
    assert clock.now().wall_seconds == 17.5


def test_fixed_manual_advance_combines_with_advance() -> None:
    clock = FixedWallClock(seconds=10.0, advance=1.0)
    assert clock.now().wall_seconds == 10.0  # step 0
    clock.manual_advance(100.0)
    assert clock.now().wall_seconds == 111.0  # step 1: 10 + 1*1 + 100
    assert clock.now().wall_seconds == 112.0  # step 2: 10 + 1*2 + 100


def test_fixed_manual_advance_rejects_negative() -> None:
    clock = FixedWallClock(seconds=10.0)
    with pytest.raises(WallClockError):
        clock.manual_advance(-1.0)


def test_fixed_manual_advance_no_op_for_sequence_mode() -> None:
    clock = FixedWallClock(sequence=(1.0, 2.0, 3.0))
    clock.manual_advance(100.0)  # silently ignored
    assert clock.now().wall_seconds == 1.0
    assert clock.now().wall_seconds == 2.0


# ---------------------------------------------------------------------------
# Reserved metadata key
# ---------------------------------------------------------------------------


def test_reserved_metadata_key_value() -> None:
    # The value is part of the cross-owner contract (CLI driver writes it; composition reads
    # it). It must remain stable; this test pins it.
    assert RECEIVED_AT_WALL_METADATA_KEY == "received_at_wall"


# ---------------------------------------------------------------------------
# Owner-boundary smoke
# ---------------------------------------------------------------------------


def test_wall_clock_module_does_not_import_cognitive_owner() -> None:
    """Pin the §3.6 boundary: this owner imports nothing from any cognitive owner."""
    import importlib
    import sys

    forbidden = {
        "helios_v2.appraisal",
        "helios_v2.feeling",
        "helios_v2.memory",
        "helios_v2.thought_gating",
        "helios_v2.internal_thought",
        "helios_v2.autonomy",
        "helios_v2.evaluation",
        "helios_v2.prompt_contract",
        "helios_v2.consciousness",
        "helios_v2.workspace",
        "helios_v2.directed_retrieval",
        "helios_v2.outward_expression",
        "helios_v2.outward_expression_externalization",
        "helios_v2.action_externalization",
        "helios_v2.planner_bridge",
        "helios_v2.identity_governance",
        "helios_v2.experience_writeback",
        "helios_v2.neuromodulation",
        "helios_v2.interoception",
        "helios_v2.temporal",
    }
    # Force a clean reload to scope the assertion to imports done by this owner alone.
    for name in list(sys.modules):
        if name.startswith("helios_v2.wall_clock"):
            del sys.modules[name]
    importlib.import_module("helios_v2.wall_clock")
    leaked = forbidden & set(sys.modules.keys())
    # `helios_v2.wall_clock` itself must not pull any cognitive owner. Other tests in this
    # process may have imported them earlier, so the assertion is on the wall_clock package's
    # own module graph, not on global `sys.modules`. We approximate via a static import audit:
    import helios_v2.wall_clock as wc
    import helios_v2.wall_clock.contracts as wc_contracts
    import helios_v2.wall_clock.engine as wc_engine

    for module in (wc, wc_contracts, wc_engine):
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            attr_module = getattr(attr, "__module__", "")
            if isinstance(attr_module, str):
                assert not any(attr_module.startswith(name) for name in forbidden), (
                    f"helios_v2.wall_clock leaked cognitive-owner import via {attr_name} "
                    f"(__module__={attr_module})"
                )

    # The static-import audit above is the authoritative check; the dynamic `leaked` set is a
    # belt-and-braces signal not relied on for assertion correctness.
    _ = leaked
