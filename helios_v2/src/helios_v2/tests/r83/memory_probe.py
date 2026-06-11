"""R83 memory-fidelity probe (Axis 3).

The R83 axis 3 ("memory-fidelity") score is computed by issuing
**directed-retrieval probes** via owner 10 (`retrieval.contracts` /
`retrieval.directed`) and verifying that the persona's `remember_this`
field is consistent with what was stored.

This is a stub implementation. The full memory-fidelity evaluation
depends on owner 10 (`retrieval`) and owner 15 (`writeback`) being
wired into the runtime, which they are not yet (P5 unblocker).
For now, `MemoryProbe.score()` returns 0.5 with reasoning
`"memory-fidelity-not-implemented"`.

When P5 ships (R79 plan closure), this stub will be replaced with
the real probe that:
  1. Issues a retrieval probe every 5 ticks
  2. Measures retrieval latency (A3 sub-metric 1)
  3. Measures recall hit rate (A3 sub-metric 2)
  4. Verifies `remember_this` + `remember_because` fields
     have a non-trivial correlation with prior stimuli
     (A3 sub-metric 3)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryProbeResult:
    """Result of the A3 memory-fidelity probe."""

    score: float
    reasoning: str
    retrieval_latency_ms: float | None = None
    recall_hit_rate: float | None = None
    writeback_persistence_rate: float | None = None


class MemoryProbe:
    """A3 memory-fidelity probe (stub)."""

    def __init__(self, gateway=None, handle=None) -> None:  # noqa: ANN001
        self.gateway = gateway
        self.handle = handle

    def score(self) -> MemoryProbeResult:
        """Return the A3 score. Stub: 0.5 with 'not-implemented' reason."""
        return MemoryProbeResult(
            score=0.5,
            reasoning="memory-fidelity-not-implemented: P5 unblocker pending",
            retrieval_latency_ms=None,
            recall_hit_rate=None,
            writeback_persistence_rate=None,
        )
