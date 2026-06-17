"""R-PROTO-LEARN.22 — owner 13 planner_bridge learner.

3 policies:
- policy_evaluation_policy: 3-dim output (evaluation_threshold,
  exploration_bonus, consistency_score)
- channel_selection_policy: 3-dim output (channel_weight,
  fall_back_score, signal_strength)
- feedback_normalization_policy: 3-dim output (normalization_strength,
  scope_pressure, integration_depth)

Academic grounding:
- Laird 2012 Soar: policy_evaluation_policy is the impasse
  detection + operator selection analog.
- Parisi 2019 transfer learning: feedback_normalization_policy
  models cross-domain transfer normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class PlannerBridgeLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.22 config.

    input_dim = 7 (bridge_intensity, request_count, dopamine, ach,
                    novelty, feedback_volume, decision_confidence).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class PlannerBridgeLearner(LearnerABC):
    """R-PROTO-LEARN.22 owner 13 planner_bridge learner.

    Maps 7-dim planner_bridge context -> 9-dim output:
    - output[0:3] policy_evaluation_policy
    - output[3:6] channel_selection_policy
    - output[6:9] feedback_normalization_policy
    """

    def __init__(
        self,
        config: PlannerBridgeLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or PlannerBridgeLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_planner_bridge_fields(state)
        return np.array([
            d["bridge_intensity"],
            d["request_count"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["feedback_volume"],
            d["decision_confidence"],
        ], dtype=np.float64)

    def _extract_planner_bridge_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "bridge_intensity": 0.5,
            "request_count": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "feedback_volume": 0.5,
            "decision_confidence": 0.5,
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
        # policy_evaluation_policy: 3 dims (Laird 2012 Soar impasse/operator)
        evaluation = np.array([
            np.clip(0.4 + 0.3 * (1.0 - v), 0.0, 1.0),  # evaluation_threshold
            np.clip(0.4 + 0.4 * (novelty - 0.5), 0.0, 1.0),  # exploration_bonus
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # consistency_score
        ], dtype=np.float64)
        # channel_selection_policy: 3 dims (Laird 2012 operator selection)
        channel = np.array([
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # channel_weight
            np.clip(0.3 + 0.3 * a, 0.0, 1.0),  # fall_back_score
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # signal_strength
        ], dtype=np.float64)
        # feedback_normalization_policy: 3 dims (Parisi 2019 transfer)
        feedback = np.array([
            np.clip(0.4 + 0.3 * f, 0.0, 1.0),  # normalization_strength
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # scope_pressure
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # integration_depth
        ], dtype=np.float64)
        return np.concatenate([evaluation, channel, feedback])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_planner_bridge_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_planner_bridge_fields(state)
        return d["acetylcholine"]
