"""R89 long-run Turing-style evaluation harness (tests-only, read-only, offline).

Consumes an R83 `LongRunReport` plus an R88 `DriftReport` and scores the six `ARCHITECTURE_PHILOSOPHY`
§13.4 rubric axes (`linguistic_naturalness`, `bio_responsiveness`, `memory_fidelity`, `agency_locking`,
`cross_tick_continuity`, `stimulus_response_coherence`) under the locked dual-similarity criterion
(behavior dimension AND internal causal-chain dimension), evidence-anchored scoring (no provenance ->
0), an injected human/LLM-judge track for the behavior axes, a stubbed `memory_fidelity` (pending R90),
and the conservative anti-theatrical aggregation (both dimensions required, any-axis-collapse fails,
>= 80% pass line). It asserts nothing and emits no `print`/`logging` (R21 discipline); a consuming test
renders/asserts on the returned `TuringVerdict`.

NON-GOAL (honest scope): this is the harness scaffold plus the deterministically-reconstructable
internal axes. The full §13.4 acceptance run (>= 300 real stimuli, real human/LLM judges, real
anthropomorphism scoring, and the R90 real memory probe) is deferred, so on the offline baseline the
behavior dimension is unavailable and the verdict is honestly `incomplete` and not-passing.

This package, like `r83_long_runner` / `r88_drift_evaluator`, ensures `tests/` is on `sys.path` so the
sibling `from r83_long_runner import ...` / `from r88_drift_evaluator import ...` imports resolve.
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from .turing_harness import (  # noqa: E402  (path insertion must precede the import)
    AGENCY_LOCKING,
    AVAILABLE,
    BIO_RESPONSIVENESS,
    CROSS_TICK_CONTINUITY,
    DIMENSION_BEHAVIOR,
    DIMENSION_INTERNAL,
    LINGUISTIC_NATURALNESS,
    MEMORY_FIDELITY,
    RECONSTRUCTED,
    STIMULUS_RESPONSE_COHERENCE,
    STUBBED,
    UNAVAILABLE,
    AxisScore,
    InjectedAxisScore,
    TuringConfig,
    TuringVerdict,
    evaluate_turing,
)

__all__ = [
    "AGENCY_LOCKING",
    "AVAILABLE",
    "BIO_RESPONSIVENESS",
    "CROSS_TICK_CONTINUITY",
    "DIMENSION_BEHAVIOR",
    "DIMENSION_INTERNAL",
    "LINGUISTIC_NATURALNESS",
    "MEMORY_FIDELITY",
    "RECONSTRUCTED",
    "STIMULUS_RESPONSE_COHERENCE",
    "STUBBED",
    "UNAVAILABLE",
    "AxisScore",
    "InjectedAxisScore",
    "TuringConfig",
    "TuringVerdict",
    "evaluate_turing",
]
