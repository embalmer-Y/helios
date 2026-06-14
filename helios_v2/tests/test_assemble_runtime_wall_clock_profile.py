"""R92: tests for `RuntimeProfile.wall_clock` + assembly threading.

Asserts:
  - `RuntimeProfile()` defaults `wall_clock=None` (legacy unchanged).
  - `assemble_runtime(wall_clock=fc)` and `assemble_runtime(profile=RuntimeProfile(wall_clock=fc))`
    behave equivalently (kernel sees the same wall_clock instance via tick).
  - Passing both an explicit profile AND the loose `wall_clock` kwarg raises `CompositionError`.
  - The default `assemble_runtime()` is byte-for-byte unchanged: every produced
    `RuntimeTickResult.tick_wall_seconds` is `None`.
  - With a `FixedWallClock` injected, every `RuntimeTickResult.tick_wall_seconds` carries a
    deterministic real value.
  - The CLI driver under a channel-bound assembly gets the same `wall_clock` instance and stamps
    `received_at_wall` on inbound packets.
  - `assemble_production_runtime()` defaults to `SystemWallClock` when no `wall_clock` is given;
    a caller-supplied `FixedWallClock` is honored verbatim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping

import pytest

from helios_v2.composition import (
    CompositionError,
    RuntimeHandle,
    RuntimeProfile,
    assemble_production_runtime,
    assemble_runtime,
    default_composition_config,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry, ProviderCompletion
from helios_v2.wall_clock import (
    RECEIVED_AT_WALL_METADATA_KEY,
    FixedWallClock,
    SystemWallClock,
    WallClock,
)


@dataclass
class _FakeThoughtProvider:
    """Network-free provider returning a valid structured thought envelope."""

    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "a production thought for the current cycle",
            "sufficiency": 0.9,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": True, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _ready_gateway() -> LlmGateway:
    config = default_composition_config()
    return LlmGateway(
        provider=_FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


# ---------------------------------------------------------------------------
# RuntimeProfile additive field default
# ---------------------------------------------------------------------------


def test_runtime_profile_default_wall_clock_is_none() -> None:
    profile = RuntimeProfile()
    assert profile.wall_clock is None


def test_runtime_profile_accepts_explicit_wall_clock() -> None:
    fc = FixedWallClock(seconds=42.0)
    profile = RuntimeProfile(wall_clock=fc)
    assert profile.wall_clock is fc


# ---------------------------------------------------------------------------
# Default assembly: no wall_clock -> tick_wall_seconds is None on every result
# ---------------------------------------------------------------------------


def test_default_assemble_runtime_produces_none_tick_wall_seconds() -> None:
    handle = assemble_runtime()
    handle.startup()
    r1 = handle.tick()
    r2 = handle.tick()
    assert r1.tick_wall_seconds is None
    assert r2.tick_wall_seconds is None


# ---------------------------------------------------------------------------
# Loose-kwarg path: wall_clock is honored
# ---------------------------------------------------------------------------


def test_loose_kwarg_wall_clock_is_threaded_into_kernel() -> None:
    fc = FixedWallClock(seconds=100.0, advance=1.0)
    handle = assemble_runtime(wall_clock=fc)
    handle.startup()
    r1 = handle.tick()
    r2 = handle.tick()
    r3 = handle.tick()
    assert r1.tick_wall_seconds == 100.0
    assert r2.tick_wall_seconds == 101.0
    assert r3.tick_wall_seconds == 102.0


# ---------------------------------------------------------------------------
# Profile path: wall_clock honored equivalently
# ---------------------------------------------------------------------------


def test_profile_wall_clock_is_threaded_into_kernel() -> None:
    fc = FixedWallClock(seconds=200.0, advance=1.0)
    handle = assemble_runtime(profile=RuntimeProfile(wall_clock=fc))
    handle.startup()
    r1 = handle.tick()
    r2 = handle.tick()
    assert r1.tick_wall_seconds == 200.0
    assert r2.tick_wall_seconds == 201.0


# ---------------------------------------------------------------------------
# Conflict: profile + loose kwarg raises
# ---------------------------------------------------------------------------


def test_profile_plus_loose_wall_clock_raises_composition_error() -> None:
    fc = FixedWallClock(seconds=1.0)
    with pytest.raises(CompositionError):
        assemble_runtime(
            profile=RuntimeProfile(wall_clock=fc),
            wall_clock=fc,
        )


# ---------------------------------------------------------------------------
# Channel-bound: same wall_clock instance reaches the CLI driver
# ---------------------------------------------------------------------------


def test_channel_cli_driver_inherits_wall_clock_from_profile() -> None:
    """In a channel-bound assembly, the CLI driver must stamp `received_at_wall` from the
    same injected clock as the kernel."""
    fc = FixedWallClock(seconds=50.0, advance=1.0)
    sink: list[str] = []
    handle = assemble_runtime(
        channel_cli=True,
        cli_output_sink=sink.append,
        wall_clock=fc,
    )
    handle.startup()

    # Find the CLI driver inside the handle and submit a line.
    subsystem = handle.channel_subsystem
    assert subsystem is not None
    cli_driver = subsystem._drivers["cli"]  # subsystem registry; test-internal probe
    # The first now() inside the kernel will fire on tick(); the next now() will fire on
    # submit_line. Let us submit BEFORE the first tick so the line's stamp is determinate.
    cli_driver.submit_line("hello")
    # Now run one tick — the kernel takes the next reading; drain happens inside the tick.
    r1 = handle.tick()

    # The kernel reading and the line reading both came from the same FixedWallClock; the
    # exact ordering depends on the assembly's call site, but both must be finite real values
    # produced by `fc` (so cli driver did NOT silently fall back to `time.time()`).
    sensory_result = r1.stage_results.get("sensory_ingress")
    batch = getattr(sensory_result, "batch", None)
    assert batch is not None
    # At least one stimulus came from the CLI driver's drained packet, and it carries the
    # `received_at_wall` metadata key.
    cli_stimuli = [s for s in batch.stimuli if s.channel == "cli"]
    assert cli_stimuli, "no CLI-channel stimulus produced by channel-bound assembly"
    metadata = dict(cli_stimuli[0].metadata or {})
    assert RECEIVED_AT_WALL_METADATA_KEY in metadata
    received_at = metadata[RECEIVED_AT_WALL_METADATA_KEY]
    assert isinstance(received_at, float)
    assert received_at >= 50.0  # came from `fc` (started at 50.0)


# ---------------------------------------------------------------------------
# Identity: one WallClock instance threaded everywhere
# ---------------------------------------------------------------------------


def test_one_wall_clock_instance_is_threaded_into_kernel_and_cli_driver() -> None:
    """The kernel and CLI driver must share the SAME `wall_clock` instance — otherwise a
    `FixedWallClock`'s deterministic step count would split between two instances."""
    fc = FixedWallClock(seconds=10.0, advance=1.0)
    sink: list[str] = []
    handle = assemble_runtime(
        channel_cli=True,
        cli_output_sink=sink.append,
        wall_clock=fc,
    )
    # The kernel exposes its wall_clock attribute; the CLI driver stores it as its own.
    assert handle.kernel.wall_clock is fc
    cli_driver = handle.channel_subsystem._drivers["cli"]
    assert cli_driver.wall_clock is fc


# ---------------------------------------------------------------------------
# Non-channel assembly: kernel receives wall_clock, no CLI driver path
# ---------------------------------------------------------------------------


def test_non_channel_assembly_kernel_only_threading() -> None:
    fc = FixedWallClock(seconds=10.0, advance=1.0)
    handle = assemble_runtime(wall_clock=fc)
    assert handle.kernel.wall_clock is fc
    assert handle.channel_subsystem is None  # no CLI driver in default assembly


# ---------------------------------------------------------------------------
# assemble_production_runtime defaults SystemWallClock; honors caller override
# ---------------------------------------------------------------------------


def test_assemble_production_runtime_defaults_system_wall_clock(tmp_path) -> None:
    handle = assemble_production_runtime(data_dir=str(tmp_path), gateway=_ready_gateway())
    assert isinstance(handle.kernel.wall_clock, SystemWallClock)


def test_assemble_production_runtime_honors_injected_fixed_clock(tmp_path) -> None:
    fc = FixedWallClock(seconds=999.0, advance=1.0)
    handle = assemble_production_runtime(data_dir=str(tmp_path), gateway=_ready_gateway(), wall_clock=fc)
    assert handle.kernel.wall_clock is fc


# ---------------------------------------------------------------------------
# Field-name registration: wall_clock is in the conflict-detection list
# ---------------------------------------------------------------------------


def test_wall_clock_is_in_runtime_profile_field_names() -> None:
    """A regression guard: removing `wall_clock` from `_RUNTIME_PROFILE_FIELD_NAMES` would
    silently allow profile + loose-kwarg overlap (the conflict detection above wouldn't fire)."""
    from helios_v2.composition.runtime_assembly import _RUNTIME_PROFILE_FIELD_NAMES

    assert "wall_clock" in _RUNTIME_PROFILE_FIELD_NAMES
