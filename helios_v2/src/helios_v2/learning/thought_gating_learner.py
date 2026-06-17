"""R-PROTO-LEARN.12 — owner 09 thought_gating learner.

3 policies:
- signal_normalization_policy: 6-dim input (norepinephrine, dopamine,
  acetylcholine, novelty, task_demand, signal_magnitude) -> 6-dim output
  (normalized signal weights, sum=1)
- continuation_policy: 4-dim input (curriculum_stage, novelty, dopamine,
  signal_normalized) -> 1-dim output (continuation_rate)
- gate_policy: 5-dim input (dopamine, acetylcholine, novelty,
  continuation_rate, signal_normalized) -> 1-dim output
  (gate_open_probability)

Academic grounding:
- Einhauser 2018: pupil dilation = cognitive effort (signal_normalization).
- Parisi 2019: curriculum learning (continuation_policy).
- dopaminergic 信心门 (gate_policy).
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
class ThoughtGatingLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.12 config.

    input_dim = 6 (signal_normalization has the largest input).
    output_dim = 6 + 1 + 1 = 8.
    """
    input_dim: int = 6
    output_dim: int = 8


class ThoughtGatingLearner(LearnerABC):
    """R-PROTO-LEARN.12 owner 09 thought_gating learner.

    Maps 6-dim thought_gating context -> 8-dim output:
    - output[0:6] signal_normalization_policy: 6 normalized signal weights
    - output[6] continuation_policy: continuation rate
    - output[7] gate_policy: gate open probability
    """

    def __init__(self, config: ThoughtGatingLearnerConfig | None = None) -> None:
        super().__init__(config=config or ThoughtGatingLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_thought_gating_fields(state)
        return np.array([
            d["norepinephrine"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["task_demand"],
            d["signal_magnitude"],
        ], dtype=np.float64)

    def _extract_thought_gating_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "norepinephrine": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "task_demand": 0.5,
            "signal_magnitude": 0.5,
        }
        if state is None:
            return defaults
        if isinstance(state, dict):
            for k in defaults:
                if k in state:
                    try:
                        v = float(state[k])
                        if 0.0 <= v <= 1.0:
                            defaults[k] = v
                    except (TypeError, ValueError):
                        pass
            return defaults
        for k in defaults:
            if hasattr(state, k):
                try:
                    v = float(getattr(state, k))
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
            return np.array([0.5] * 8, dtype=np.float64)
        # 7-dim: (valence, arousal, tension, comfort, fatigue, pain_like, social_safety)
        v, a, t, c, f, p, s = llm_signal
        # signal_normalization: 6 linear weights in [0, 1]
        signal_norm = np.array([
            np.clip(0.5 + 0.3 * a, 0.0, 1.0),
            np.clip(0.5 + 0.3 * (a + novelty - 0.5), 0.0, 1.0),
            np.clip(0.4 + 0.5 * novelty, 0.0, 1.0),
            np.clip(0.4 + 0.4 * novelty, 0.0, 1.0),
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),
            np.clip(0.5 + 0.3 * (a - 0.5), 0.0, 1.0),
        ], dtype=np.float64)
        # continuation_rate: linear combination of valence + novelty
        continuation = float(np.clip(0.5 + 0.4 * (v - 0.5) + 0.3 * (novelty - 0.5), 0.0, 1.0))
        # gate_open_probability: linear combination of valence - tension
        gate_open = float(np.clip(0.5 + 0.3 * (v - 0.5) - 0.2 * (t - 0.5), 0.0, 1.0))
        return np.concatenate([signal_norm, [continuation, gate_open]])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_thought_gating_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_thought_gating_fields(state)
        return d["acetylcholine"]
