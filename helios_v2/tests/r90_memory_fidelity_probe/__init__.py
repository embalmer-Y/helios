"""R90 memory-fidelity probe (tests-only, read-only, offline).

Drives a real durable production-shaped runtime and measures the R10+R15 memory loop end to end:
  - recall_hit_rate: fired ticks whose published `10` thought-window bundle contained a store-sourced
    hit, over fired ticks where the store was non-empty (recall was possible),
  - writeback_persistence_rate: this-run `15` records that survive a process restart against the same
    durable `33` store,
  - latency_score: bounded `34`/`33` `search_similar` recall latency.

It composes these into a `MemoryFidelityReport` with a bounded `fidelity_score` that the R89 Turing
harness consumes to turn its `memory_fidelity` axis from the stub into a real reconstructed axis. It
asserts nothing and emits no `print`/`logging` (R21 discipline); a consuming test renders/asserts.

This package, like the sibling R83/R88/R89 packages, ensures `tests/` is on `sys.path`.
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from .memory_fidelity_probe import (  # noqa: E402  (path insertion must precede the import)
    MemoryFidelityConfig,
    MemoryFidelityReport,
    run_memory_fidelity_probe,
)

__all__ = [
    "MemoryFidelityConfig",
    "MemoryFidelityReport",
    "run_memory_fidelity_probe",
]
