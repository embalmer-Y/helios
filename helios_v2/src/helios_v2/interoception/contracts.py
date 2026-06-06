"""Owner: runtime interoceptive signal source.

Owns:
- the bounded runtime-pressure sample contract (the runtime's real internal condition)
- the injected runtime-pressure sampler protocol boundary

Does not own:
- feeling construction (owned by `05` interoceptive feeling)
- salience scoring (owned by `03` appraisal)
- neuromodulator state (owned by `04`)
- sensory normalization (owned by `02` sensory ingress)

This owner is a peripheral afferent producer, analogous to interoceptive receptors reporting
the body's internal condition. It reports the runtime's real internal condition (compute/runtime
pressure) as bounded facts; it interprets nothing and makes no cognitive decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class InteroceptionError(RuntimeError):
    """Hard-stop error raised when runtime interoceptive-source invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise InteroceptionError(f"{name} must be within [0.0, 1.0]")


@dataclass(frozen=True)
class RuntimePressureSample:
    """Owner: runtime interoceptive signal source.

    Purpose:
        One bounded snapshot of the runtime's real internal condition. Each channel is a
        normalized pressure in `[0.0, 1.0]`: `0.0` is "no pressure / at rest" and `1.0` is
        "maximum pressure". This is a transport fact, not a feeling: it reports the machine's
        internal condition the way an interoceptive afferent reports the body's.

    Failure semantics:
        Construction raises `InteroceptionError` if any channel is outside `[0.0, 1.0]`.

    Notes:
        `cpu_pressure`/`memory_pressure` reflect real compute/memory load; `latency_pressure`
        and `error_pressure` are first-version injectable channels (real tick-latency and
        recent-error-rate sourcing is a later slice). The owner that produced this sample owns
        only the runtime-fact-to-pressure normalization; it never interprets the sample as a
        feeling or a salience.
    """

    cpu_pressure: float
    memory_pressure: float
    latency_pressure: float
    error_pressure: float

    def __post_init__(self) -> None:
        _validate_unit_interval("RuntimePressureSample.cpu_pressure", self.cpu_pressure)
        _validate_unit_interval("RuntimePressureSample.memory_pressure", self.memory_pressure)
        _validate_unit_interval("RuntimePressureSample.latency_pressure", self.latency_pressure)
        _validate_unit_interval("RuntimePressureSample.error_pressure", self.error_pressure)


@runtime_checkable
class RuntimePressureSampler(Protocol):
    """Owner: runtime interoceptive signal source.

    Purpose:
        The injected boundary behind which a concrete runtime-condition sampler is provided, so
        the interoceptive source never hard-depends on a specific telemetry backend.

    Notes:
        Implementations must be cheap and synchronous (no blocking I/O, no network) and must
        return a bounded `RuntimePressureSample`. A merely-unavailable fact must resolve to a
        defined bounded default rather than raising; an outright sampler bug may raise.
    """

    def sample(self) -> RuntimePressureSample:
        """Owner: runtime interoceptive signal source.

        Purpose:
            Sample the runtime's current internal condition into one bounded `RuntimePressureSample`.

        Inputs:
            None.

        Returns:
            One `RuntimePressureSample` with every channel in `[0.0, 1.0]`.

        Raises:
            May raise on an outright sampling fault; a merely-unavailable fact must instead
            resolve to a defined bounded default.

        Notes:
            Must be cheap, synchronous, and network-free.
        """

        ...
