"""Owner: runtime interoceptive signal source.

Provides the first-version runtime-pressure sampler (real, cheap, network-free runtime facts
with defined bounded defaults for unavailable facts) and the `RuntimeInteroceptiveSource`, which
projects a `RuntimePressureSample` into bounded interoceptive `RawSignal`s and registers into
sensory ingress through the existing `SensorySource` protocol.

This owner is a peripheral afferent producer. It reports the runtime's real internal condition as
bounded facts; it holds no feeling, salience, or cognitive policy, and it imports no feeling,
appraisal, or neuromodulation owner. Sensory ingress (`02`) owns normalization; the `05` feeling
owner owns how (and whether) these signals shape the felt body-state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from helios_v2.sensory import RawSignal, SensorySource

from .contracts import RuntimePressureSample, RuntimePressureSampler


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# The interoceptive channels emitted as distinct afferent streams (one bounded RawSignal each).
_PRESSURE_CHANNELS: tuple[str, ...] = ("cpu", "memory", "latency", "error")


@dataclass
class StdlibRuntimePressureSampler(RuntimePressureSampler):
    """Owner: runtime interoceptive signal source.

    Purpose:
        Read the runtime's real internal condition from cheap, network-free facts and normalize
        them into a bounded `RuntimePressureSample`. CPU and memory pressure come from real
        process/system telemetry (via `psutil` when importable, else a stdlib-derived fallback,
        else a defined neutral default). Latency and error pressure are first-version injectable
        defaults (real tick-latency / recent-error-rate sourcing is a later slice).

    Failure semantics:
        A merely-unavailable fact (no telemetry library, or a read error for a single fact)
        resolves to the documented bounded default for that channel and never raises -- sampling
        the body must never crash the tick. The default for an unavailable cpu/memory fact is a
        neutral `unknown_default` (a defined "unknown -> neutral" reading, not a fabricated
        specific condition). An outright bug in this sampler may still raise.

    Notes:
        `psutil` is imported lazily inside the read helpers, so importing this module never
        requires it and the network-free test suite never touches it (tests inject a fake
        sampler). The sampler imports no helios owner and computes no feeling/salience.
    """

    default_latency_pressure: float = 0.0
    default_error_pressure: float = 0.0
    unknown_default: float = 0.0

    def sample(self) -> RuntimePressureSample:
        """Owner: runtime interoceptive signal source. Sample the runtime's internal condition."""

        return RuntimePressureSample(
            cpu_pressure=self._cpu_pressure(),
            memory_pressure=self._memory_pressure(),
            latency_pressure=_clamp_unit(self.default_latency_pressure),
            error_pressure=_clamp_unit(self.default_error_pressure),
        )

    def _cpu_pressure(self) -> float:
        """Return real CPU pressure in [0,1], or the neutral default when unavailable."""

        try:
            import psutil  # type: ignore

            return _clamp_unit(psutil.cpu_percent(interval=None) / 100.0)
        except Exception:
            # Fall back to a load-average-derived estimate when available (Unix), else neutral.
            try:
                load1, _, _ = os.getloadavg()
                cpu_count = os.cpu_count() or 1
                return _clamp_unit(load1 / float(cpu_count))
            except (OSError, AttributeError):
                return _clamp_unit(self.unknown_default)

    def _memory_pressure(self) -> float:
        """Return real memory pressure in [0,1], or the neutral default when unavailable."""

        try:
            import psutil  # type: ignore

            return _clamp_unit(psutil.virtual_memory().percent / 100.0)
        except Exception:
            return _clamp_unit(self.unknown_default)


@dataclass
class RuntimeInteroceptiveSource(SensorySource):
    """Owner: runtime interoceptive signal source.

    Purpose:
        Produce real interoceptive `RawSignal`s from the runtime's internal condition and feed
        them into sensory ingress through the standard `SensorySource` protocol, so the `02 -> 05`
        interoceptive afferent path carries real body signals instead of being empty.

    Failure semantics:
        Delegates sampling to the injected sampler. A merely-unavailable fact is the sampler's
        defined default; an outright sampler exception propagates (no fabricated healthy body).

    Notes:
        Owns only the sample-to-signal projection: one bounded interoceptive `RawSignal` per
        pressure channel (distinct afferent streams), with `signal_type="interoceptive"` so
        sensory normalizes them to `modality="interoceptive"` stimuli that the `05` feeling stage
        already filters and validates. It holds no feeling/salience/cognitive policy and imports
        no feeling/appraisal/neuromodulation owner. The numeric pressure value rides metadata for
        a future `05` consumer; the content string is a bounded, deterministic projection.
    """

    sampler: RuntimePressureSampler
    source_name_value: str = "interoception"

    @property
    def source_name(self) -> str:
        """Stable source owner name consumed by sensory ingress registration."""

        return self.source_name_value

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Owner: runtime interoceptive signal source.

        Purpose:
            Sample the runtime condition and emit one bounded interoceptive `RawSignal` per
            pressure channel.

        Returns:
            One immutable tuple of `RawSignal` values (`signal_type="interoceptive"`), one per
            channel, deterministic for a fixed sample.

        Raises:
            Propagates an outright sampler exception; a merely-unavailable fact is the sampler's
            defined default.
        """

        sample = self.sampler.sample()
        channel_values = (
            ("cpu", sample.cpu_pressure),
            ("memory", sample.memory_pressure),
            ("latency", sample.latency_pressure),
            ("error", sample.error_pressure),
        )
        return tuple(
            RawSignal(
                signal_id=f"interoceptive:{channel}",
                source_name=self.source_name_value,
                signal_type="interoceptive",
                content=f"{channel}_pressure={value:.4f}",
                channel="interoception",
                metadata={"pressure_channel": channel, "pressure_value": round(value, 4)},
                required=False,
            )
            for channel, value in channel_values
        )
