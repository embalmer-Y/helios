"""R83 long-run stability + owner-boundedness harness (tests-only).

A repeatable, network-free long-run harness that drives an assembled runtime for N ticks and
collects crash / uncaught-exception facts, per-owner boundedness (no NaN, no out-of-range, no
divergence) over the run, in-process memory growth, and a sampled cross-tick evolution curve,
producing a `LongRunReport`.

It follows the R21 discipline: the harness emits NO `print`/`logging`; it only collects facts into
structured values and returns the report. A consuming test may render the report. It is read-only:
it exercises the runtime through its public `tick()` and never mutates owner state.
"""

from .long_runner import (
    FieldStat,
    LongRunConfig,
    LongRunReport,
    TRACKED_FIELD_BOUNDS,
    run_long_run,
)

__all__ = [
    "FieldStat",
    "LongRunConfig",
    "LongRunReport",
    "TRACKED_FIELD_BOUNDS",
    "run_long_run",
]
