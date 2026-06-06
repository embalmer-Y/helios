"""Runtime interoceptive signal source owner package.

A peripheral afferent producer that reports the runtime's real internal condition
(compute/runtime pressure) as bounded interoceptive `RawSignal`s into sensory ingress, closing
the producer half of `gap_interoceptive_signal_source`. Holds no feeling, salience, or cognitive
policy and imports no feeling/appraisal/neuromodulation owner.
"""

from .contracts import (
    InteroceptionError,
    RuntimePressureSample,
    RuntimePressureSampler,
)
from .engine import RuntimeInteroceptiveSource, StdlibRuntimePressureSampler

__all__ = [
    "InteroceptionError",
    "RuntimeInteroceptiveSource",
    "RuntimePressureSample",
    "RuntimePressureSampler",
    "StdlibRuntimePressureSampler",
]
