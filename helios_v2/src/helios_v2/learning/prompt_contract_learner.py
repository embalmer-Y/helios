"""R-PROTO-LEARN.20b — owner prompt_contract learner.

3 policies:
- layering_policy: 3-dim output (layer_count, layer_ordering,
  layer_depth)
- anti_theatrical_policy: 3-dim output (suppression_strength,
  authenticity_weight, risk_threshold)
- action_boundary_policy: 3-dim output (action_strength,
  boundary_strictness, fallback_path)

Academic grounding:
- Helios R79-R80 governance: anti_theatrical_policy directly encodes
  the no-theater constraint.
- Kotseruba 2018 self-regulation: layering_policy decides how to
  structure the prompt layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class PromptContractLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.20b config.

    input_dim = 7 (context_complexity, persona_drift_signal,
                    action_pressure, dopamine, ach, novelty,
                    last_pressure_tick).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class PromptContractLearner(LearnerABC):
    """R-PROTO-LEARN.20b owner prompt_contract learner.

    Maps 7-dim prompt_contract context -> 9-dim output:
    - output[0:3] layering_policy
    - output[3:6] anti_theatrical_policy
    - output[6:9] action_boundary_policy
    """

    def __init__(
        self,
        config: PromptContractLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or PromptContractLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_prompt_contract_fields(state)
        return np.array([
            d["context_complexity"],
            d["persona_drift_signal"],
            d["action_pressure"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["last_pressure_tick"],
        ], dtype=np.float64)

    def _extract_prompt_contract_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "context_complexity": 0.5,
            "persona_drift_signal": 0.5,
            "action_pressure": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "last_pressure_tick": 0.5,
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
        # layering_policy: 3 dims
        layering = np.array([
            np.clip(0.3 + 0.4 * (novelty - 0.5) + 0.2 * a, 0.0, 1.0),  # layer_count
            np.clip(0.4 + 0.3 * c, 0.0, 1.0),  # layer_ordering
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # layer_depth
        ], dtype=np.float64)
        # anti_theatrical_policy: 3 dims
        anti_theatrical = np.array([
            np.clip(0.4 + 0.4 * t, 0.0, 1.0),  # suppression_strength
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # authenticity_weight
            np.clip(0.4 + 0.3 * (1.0 - v), 0.0, 1.0),  # risk_threshold
        ], dtype=np.float64)
        # action_boundary_policy: 3 dims
        action_boundary = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # action_strength
            np.clip(0.4 + 0.4 * t, 0.0, 1.0),  # boundary_strictness
            np.clip(0.3 + 0.3 * a, 0.0, 1.0),  # fallback_path
        ], dtype=np.float64)
        return np.concatenate([layering, anti_theatrical, action_boundary])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_prompt_contract_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_prompt_contract_fields(state)
        return d["acetylcholine"]
