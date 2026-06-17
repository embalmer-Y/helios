"""R-PROTO-LEARN.21 — owner 08 consciousness learner.

3 policies:
- commitment_policy: 3-dim output (commitment_threshold,
  confidence_required, retention_ticks)
- quiet_state_policy: 3-dim output (quiet_threshold, recovery_rate,
  idle_decay)
- semantic_shaping_policy: 3-dim output (semantic_alignment,
  conflict_resolution_strength, depth_score)

Academic grounding:
- Tononi 2004 IIT (integrated information theory): commitment_policy
  models the Φ-threshold for conscious access.
- Dehaene 2014 GNW (global neuronal workspace): quiet_state_policy
  models the ignition threshold / deactivation.
- semantic_shaping_policy models the long-range cortical reentry
  that GNW requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class ConsciousnessLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.21 config.

    input_dim = 7 (candidate_count, signal_strength, dopamine, ach,
                    novelty, conscious_state_size, semantic_drift).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class ConsciousnessLearner(LearnerABC):
    """R-PROTO-LEARN.21 owner 08 consciousness learner.

    Maps 7-dim conscious context -> 9-dim output:
    - output[0:3] commitment_policy
    - output[3:6] quiet_state_policy
    - output[6:9] semantic_shaping_policy
    """

    def __init__(
        self,
        config: ConsciousnessLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or ConsciousnessLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_consciousness_fields(state)
        return np.array([
            d["candidate_count"],
            d["signal_strength"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["conscious_state_size"],
            d["semantic_drift"],
        ], dtype=np.float64)

    def _extract_consciousness_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "candidate_count": 0.5,
            "signal_strength": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "conscious_state_size": 0.5,
            "semantic_drift": 0.5,
        }
        if state is None:
            return defaults
        src = state if isinstance(state, dict) else vars(state) if hasattr(state, "__dict__") else {}
        for k in defaults:
            if k in src:
                try:
                    v = float(src[k])
                    if 0.0 <= v <= 1.0:
                        defaults[k] = v
                except (TypeError, ValueError):
                    pass
        return defaults

    def _llm_signal_to_target_vec(
        self,
        llm_signal: tuple[float, ...] | None,
        novelty: float,
    ) -> np.ndarray:
        if llm_signal is None:
            return np.array([0.5] * 9, dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # commitment_policy: 3 dims (Tononi 2004 IIT Φ-threshold)
        commitment = np.array([
            np.clip(0.4 + 0.3 * v, 0.0, 1.0),  # commitment_threshold
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # confidence_required
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # retention_ticks
        ], dtype=np.float64)
        # quiet_state_policy: 3 dims (Dehaene 2014 GNW ignition/deactivation)
        quiet = np.array([
            np.clip(0.4 + 0.4 * (1.0 - v), 0.0, 1.0),  # quiet_threshold
            np.clip(0.3 + 0.3 * f, 0.0, 1.0),  # recovery_rate
            np.clip(0.3 + 0.3 * (1.0 - a), 0.0, 1.0),  # idle_decay
        ], dtype=np.float64)
        # semantic_shaping_policy: 3 dims (GNW long-range cortical reentry)
        shaping = np.array([
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # semantic_alignment
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # conflict_resolution_strength
            np.clip(0.4 + 0.4 * (novelty - 0.5), 0.0, 1.0),  # depth_score
        ], dtype=np.float64)
        return np.concatenate([commitment, quiet, shaping])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_consciousness_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_consciousness_fields(state)
        return d["acetylcholine"]
