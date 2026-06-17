"""R-PROTO-LEARN.24 — owner 15 experience_writeback learner.

3 policies:
- continuity_classification_policy: 3-dim output (continuity_threshold,
  classification_threshold, weight)
- consolidation_priority_policy: 3-dim output (priority_threshold,
  weight, decay_rate)
- autobiographical_salience_policy: 3-dim output (salience_threshold,
  weight, integration_strength)

Academic grounding:
- Bhatt 2019 reconsolidation: continuity_classification_policy
  models the memory trace classification window.
- Parisi 2019 consolidation: consolidation_priority_policy is
  the consolidation scheduling decision.
- autobiographical_salience_policy: salience-based prioritization
  for autobiographical memory (Tulving 1985 + Panksepp SEEKING).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class ExperienceWritebackLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.24 config.

    input_dim = 7 (continuity_intensity, evidence_strength, dopamine, ach,
                    novelty, candidate_count, autobiographical_signal).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class ExperienceWritebackLearner(LearnerABC):
    """R-PROTO-LEARN.24 owner 15 experience_writeback learner.

    Maps 7-dim experience_writeback context -> 9-dim output:
    - output[0:3] continuity_classification_policy
    - output[3:6] consolidation_priority_policy
    - output[6:9] autobiographical_salience_policy
    """

    def __init__(
        self,
        config: ExperienceWritebackLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or ExperienceWritebackLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_experience_writeback_fields(state)
        return np.array([
            d["continuity_intensity"],
            d["evidence_strength"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["candidate_count"],
            d["autobiographical_signal"],
        ], dtype=np.float64)

    def _extract_experience_writeback_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "continuity_intensity": 0.5,
            "evidence_strength": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "candidate_count": 0.5,
            "autobiographical_signal": 0.5,
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
        # continuity_classification_policy: 3 dims (Bhatt 2019 reconsolidation)
        continuity = np.array([
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # continuity_threshold
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # classification_threshold
            np.clip(0.4 + 0.3 * v, 0.0, 1.0),  # weight
        ], dtype=np.float64)
        # consolidation_priority_policy: 3 dims (Parisi 2019 consolidation)
        priority = np.array([
            np.clip(0.4 + 0.3 * (1.0 - a), 0.0, 1.0),  # priority_threshold
            np.clip(0.4 + 0.3 * v, 0.0, 1.0),  # weight
            np.clip(0.3 + 0.3 * f, 0.0, 1.0),  # decay_rate
        ], dtype=np.float64)
        # autobiographical_salience_policy: 3 dims (Tulving + Panksepp)
        salience = np.array([
            np.clip(0.4 + 0.4 * s, 0.0, 1.0),  # salience_threshold
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # weight
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # integration_strength
        ], dtype=np.float64)
        return np.concatenate([continuity, priority, salience])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_experience_writeback_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_experience_writeback_fields(state)
        return d["acetylcholine"]
