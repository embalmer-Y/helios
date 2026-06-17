"""R-PROTO-LEARN.13 — owner 10 directed_retrieval learner.

3 policies:
- tier_selection_policy: 6-dim input (L2_episodic_signal, L3_semantic_signal,
  L4_autobiographical_signal, L5_immutable_signal, dopaminergic_signal,
  time_decay) -> 4-dim output (tier weights, softmax)
- retrieval_planning_policy: 5-dim input (curiosity_signal, transfer_signal,
  retrieval_count, novelty, dopamine) -> 3-dim output
  (episodic/semantic/autobiographical planning, softmax)
- thought_window_shaping_policy: 4-dim input (dopamine, retrieved_count,
  acetylcholine, continuation_rate) -> 4-dim output (window_shape)

Academic grounding:
- Parisi 2019: transfer learning (retrieval_planning_policy).
- R85 4-layer L2-L5 store (tier_selection_policy).
- Panksepp SEEKING active inference (thought_window_shaping_policy).
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
class RetrievalLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.13 config.

    input_dim = 6 (tier_selection has the largest input).
    output_dim = 4 + 3 + 4 = 11.
    """
    input_dim: int = 6
    output_dim: int = 11


class RetrievalLearner(LearnerABC):
    """R-PROTO-LEARN.13 owner 10 directed_retrieval learner.

    Maps 6-dim retrieval context -> 11-dim output:
    - output[0:4] tier_selection_policy: 4 tier weights
    - output[4:7] retrieval_planning_policy: 3 planning weights
    - output[7:11] thought_window_shaping_policy: 4 window shape dims
    """

    def __init__(self, config: RetrievalLearnerConfig | None = None) -> None:
        super().__init__(config=config or RetrievalLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_retrieval_fields(state)
        return np.array([
            d["l2_episodic"],
            d["l3_semantic"],
            d["l4_autobiographical"],
            d["l5_immutable"],
            d["dopaminergic_signal"],
            d["time_decay"],
        ], dtype=np.float64)

    def _extract_retrieval_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "l2_episodic": 0.5,
            "l3_semantic": 0.5,
            "l4_autobiographical": 0.5,
            "l5_immutable": 0.5,
            "dopaminergic_signal": 0.5,
            "time_decay": 0.5,
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
            return np.array([0.25] * 4 + [0.33, 0.33, 0.34] + [0.5] * 4, dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # tier_selection: 4 linear weights in [0, 1]
        tier = np.array([
            np.clip((1.0 - v) * novelty + 0.3, 0.0, 1.0),  # episodic
            np.clip(v * (1.0 - novelty) + 0.3, 0.0, 1.0),  # semantic
            np.clip(s, 0.0, 1.0),  # autobiographical
            np.clip(0.1 + 0.1 * a, 0.0, 1.0),  # immutable
        ], dtype=np.float64)
        # retrieval_planning: 3 linear weights
        plan = np.array([
            np.clip(novelty, 0.0, 1.0),
            np.clip(v, 0.0, 1.0),
            np.clip(s, 0.0, 1.0),
        ], dtype=np.float64)
        # thought_window_shaping: 4 linear dims
        window = np.array([
            np.clip(0.5 + 0.3 * (v - 0.5), 0.0, 1.0),
            np.clip(0.5 + 0.3 * (a - 0.5), 0.0, 1.0),
            np.clip(0.5 + 0.3 * (novelty - 0.5), 0.0, 1.0),
            np.clip(0.5 + 0.3 * (c - 0.5), 0.0, 1.0),
        ], dtype=np.float64)
        return np.concatenate([tier, plan, window])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_retrieval_fields(state)
        return d["dopaminergic_signal"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_retrieval_fields(state)
        return d["time_decay"]  # proxy
