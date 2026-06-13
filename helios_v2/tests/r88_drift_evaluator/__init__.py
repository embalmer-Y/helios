"""R88 behavioral-drift evaluator (tests-only, read-only, offline).

Consumes an R83 long-run JSONL trace and classifies each owner dimension's long-horizon drift
(`drift_positive` / `drift_negative` / `drift_neutral` / `dim_unavailable`) from an
early-window-vs-late-window comparison with an explicit deadband, additionally flagging a dimension
whose drift saturates toward a legal bound (divergent). It asserts nothing and emits no
`print`/`logging` (R21 discipline); a consuming test renders/asserts on the returned `DriftReport`.

This package, like `r83_long_runner`, ensures `tests/` is on `sys.path` so a flat
`from r83_long_runner import TRACKED_FIELD_BOUNDS` resolves alongside the other test modules.
"""

from __future__ import annotations

import os
import sys

# Make the sibling `tests/` directory importable so `from r83_long_runner import ...` resolves when
# this package is imported, mirroring how the R83 package is consumed.
_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from .drift_evaluator import (  # noqa: E402  (path insertion must precede the import)
    DIM_UNAVAILABLE,
    DRIFT_NEGATIVE,
    DRIFT_NEUTRAL,
    DRIFT_POSITIVE,
    DimensionDrift,
    DriftConfig,
    DriftReport,
    evaluate_drift,
    evaluate_trace_file,
    load_samples,
)

__all__ = [
    "DIM_UNAVAILABLE",
    "DRIFT_NEGATIVE",
    "DRIFT_NEUTRAL",
    "DRIFT_POSITIVE",
    "DimensionDrift",
    "DriftConfig",
    "DriftReport",
    "evaluate_drift",
    "evaluate_trace_file",
    "load_samples",
]
