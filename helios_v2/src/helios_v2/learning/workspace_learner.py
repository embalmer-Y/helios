"""R-PROTO-LEARN.18 — owner 07 workspace learner.

3 policies:
- competition_policy: 3-dim output (activation_threshold, novelty_boost,
  conflict_penalty)
- candidate_retention_policy: 3-dim output (retention_score, decay_rate,
  promotion_threshold)
- working_state_update_policy: 3-dim output (integration_strength,
  signal_decay, revision_threshold)

Academic grounding:
- Kotseruba 2018 global workspace theory (Baars 1988): competition
  is the activation competition dynamic.
- Parisi 2019 transfer learning: candidate_retention is the
  cross-tick carry decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class WorkspaceLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.18 config.

    input_dim = 7 (candidate_count, signal_strength, dopamine, ach,
                    novelty, working_state_size, cross_tick_carry).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class WorkspaceLearner(LearnerABC):
    """R-PROTO-LEARN.18 owner 07 workspace learner.

    Maps 7-dim workspace context -> 9-dim output:
    - output[0:3] competition_policy
    - output[3:6] candidate_retention_policy
    - output[6:9] working_state_update_policy
    """

    def __init__(
        self,
        config: WorkspaceLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or WorkspaceLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_workspace_fields(state)
        return np.array([
            d["candidate_count"],
            d["signal_strength"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["working_state_size"],
            d["cross_tick_carry"],
        ], dtype=np.float64)

    def _extract_workspace_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "candidate_count": 0.5,
            "signal_strength": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "working_state_size": 0.5,
            "cross_tick_carry": 0.5,
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
        # competition_policy: 3 dims
        competition = np.array([
            np.clip(0.4 + 0.3 * (1.0 - v), 0.0, 1.0),  # activation_threshold
            np.clip(0.4 + 0.4 * (novelty - 0.5), 0.0, 1.0),  # novelty_boost
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # conflict_penalty
        ], dtype=np.float64)
        # candidate_retention_policy: 3 dims
        retention = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # retention_score
            np.clip(0.3 + 0.3 * f, 0.0, 1.0),  # decay_rate
            np.clip(0.4 + 0.3 * a, 0.0, 1.0),  # promotion_threshold
        ], dtype=np.float64)
        # working_state_update_policy: 3 dims
        update = np.array([
            np.clip(0.4 + 0.4 * (novelty - 0.5) + 0.2 * v, 0.0, 1.0),  # integration
            np.clip(0.4 + 0.3 * f, 0.0, 1.0),  # signal_decay
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # revision_threshold
        ], dtype=np.float64)
        return np.concatenate([competition, retention, update])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_workspace_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_workspace_fields(state)
        return d["acetylcholine"]
