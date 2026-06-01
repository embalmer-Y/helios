from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CognitiveImpactProfile:
    """Normalized impact dimensions for routing external events into ICRI sources."""

    sensory: float
    cognitive: float
    self_: float
    novelty: float