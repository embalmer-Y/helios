"""R-PROTO-LEARN.20 — owner 16b outward_expression_externalization learner.

3 policies:
- envelope_rendering_policy: 3-dim output (format_alignment,
  length_pressure, format_priority)
- delivery_selection_policy: 3-dim output (channel_weight,
  signal_strength, fall_back_score)
- execution_boundary_policy: 3-dim output (safety_strictness,
  identity_signal, constraint_depth)

Academic grounding:
- Parisi 2019 transfer learning: delivery_selection_policy is the
  transfer of internal representation to a public channel.
- Helios R80 governance: execution_boundary_policy is the safety
  bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class OutwardExpressionExternalizationLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.20 config.

    input_dim = 7 (envelope_priority, channel_availability,
                    safety_pressure, dopamine, ach, novelty,
                    last_execution_tick).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class OutwardExpressionExternalizationLearner(LearnerABC):
    """R-PROTO-LEARN.20 owner 16b outward_expression_externalization learner.

    Maps 7-dim externalization context -> 9-dim output:
    - output[0:3] envelope_rendering_policy
    - output[3:6] delivery_selection_policy
    - output[6:9] execution_boundary_policy
    """

    def __init__(
        self,
        config: OutwardExpressionExternalizationLearnerConfig | None = None,
    ) -> None:
        super().__init__(
            config=config or OutwardExpressionExternalizationLearnerConfig(),
        )

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_externalization_fields(state)
        return np.array([
            d["envelope_priority"],
            d["channel_availability"],
            d["safety_pressure"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["last_execution_tick"],
        ], dtype=np.float64)

    def _extract_externalization_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "envelope_priority": 0.5,
            "channel_availability": 0.5,
            "safety_pressure": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "last_execution_tick": 0.5,
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
        # envelope_rendering_policy: 3 dims
        envelope = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # format_alignment
            np.clip(0.4 + 0.3 * f, 0.0, 1.0),  # length_pressure
            np.clip(0.4 + 0.3 * a, 0.0, 1.0),  # format_priority
        ], dtype=np.float64)
        # delivery_selection_policy: 3 dims
        delivery = np.array([
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # channel_weight
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # signal_strength
            np.clip(0.3 + 0.3 * a, 0.0, 1.0),  # fall_back_score
        ], dtype=np.float64)
        # execution_boundary_policy: 3 dims
        boundary = np.array([
            np.clip(0.4 + 0.4 * t, 0.0, 1.0),  # safety_strictness
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # identity_signal
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # constraint_depth
        ], dtype=np.float64)
        return np.concatenate([envelope, delivery, boundary])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_externalization_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_externalization_fields(state)
        return d["acetylcholine"]
