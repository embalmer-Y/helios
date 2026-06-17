"""R-PROTO-LEARN.15 — owner 18 autonomy learner.

3 policies:
- drive_integration_policy: 7-dim input (6 pressure + 1 threshold) ->
  7-dim output (drive weights, normalized)
- continuity_carry_policy: 4-dim input (cross_tick_signal,
  autobiographical_salience, time_decay, identity_strength) -> 1-dim
  output (carry_strength)
- proactive_externalization_policy: 5-dim input (autonomy_drive, gate_open,
  novelty, dopamine, continuity_carry) -> 1-dim output
  (proactive_probability)

Academic grounding:
- Parisi 2019 intrinsic motivation (drive_integration_policy).
- R85 phase 1 cross-tick carry state (continuity_carry_policy).
- Kotseruba 2018 self-regulation / **P6 entry point**
  (proactive_externalization_policy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - np.max(x)
    e = np.exp(shifted)
    return e / np.sum(e)


@dataclass(frozen=True)
class AutonomyLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.15 config.

    input_dim = 7 (drive_integration has 7 inputs).
    output_dim = 7 + 1 + 1 = 9.
    """
    input_dim: int = 7
    output_dim: int = 9


class AutonomyLearner(LearnerABC):
    """R-PROTO-LEARN.15 owner 18 autonomy learner.

    Maps 7-dim autonomy context -> 9-dim output:
    - output[0:7] drive_integration_policy: 7 drive weights
    - output[7] continuity_carry_policy: carry strength
    - output[8] proactive_externalization_policy: proactive probability
    """

    def __init__(self, config: AutonomyLearnerConfig | None = None) -> None:
        super().__init__(config=config or AutonomyLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_autonomy_fields(state)
        return np.array([
            d["pressure_1"],
            d["pressure_2"],
            d["pressure_3"],
            d["pressure_4"],
            d["pressure_5"],
            d["pressure_6"],
            d["threshold"],
        ], dtype=np.float64)

    def _extract_autonomy_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "pressure_1": 0.5,
            "pressure_2": 0.5,
            "pressure_3": 0.5,
            "pressure_4": 0.5,
            "pressure_5": 0.5,
            "pressure_6": 0.5,
            "threshold": 0.5,
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
            return np.array([1/7] * 7 + [0.5, 0.5], dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # drive weights: 7 linear dims in [0, 1]
        drive = np.array([
            np.clip(0.3 + 0.5 * a, 0.0, 1.0),
            np.clip(0.3 + 0.5 * novelty, 0.0, 1.0),
            np.clip(0.3 + 0.5 * (1.0 - c), 0.0, 1.0),
            np.clip(0.3 + 0.5 * v, 0.0, 1.0),
            np.clip(0.3 + 0.5 * s, 0.0, 1.0),
            np.clip(0.3 + 0.5 * t, 0.0, 1.0),
            np.clip(0.3 + 0.5 * v, 0.0, 1.0),
        ], dtype=np.float64)
        # continuity_carry: linear
        carry = float(np.clip(0.4 + 0.3 * (v - 0.5) + 0.3 * (s - 0.5), 0.0, 1.0))
        # proactive_externalization: linear
        proactive = float(np.clip(0.3 + 0.4 * (novelty - 0.5) + 0.2 * (a - 0.5), 0.0, 1.0))
        return np.concatenate([drive, [carry, proactive]])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_autonomy_fields(state)
        return d["threshold"]  # proxy

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_autonomy_fields(state)
        return d["pressure_3"]  # proxy
