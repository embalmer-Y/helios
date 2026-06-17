"""R-PROTO-LEARN.17 — owner 17 evaluation learner.

3 policies:
- fidelity_scoring_policy: 3-dim output (execution_match,
  signal_alignment, temporal_fidelity)
- gap_analysis_policy: 2-dim output (missing_threshold, partial_threshold)
- long_range_diagnostic_policy: 3-dim output (window_size,
  trend_sensitivity, drift_threshold)

Academic grounding:
- Kotseruba 2018 self-observation (fidelity_scoring_policy: the
  observation layer).
- Kotseruba 2018 self-analysis (gap_analysis_policy: classifies where
  the gap is).
- Parisi 2019 continual learning (long_range_diagnostic_policy: "did
  the system regress" detector).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class EvaluationLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.17 config.

    input_dim = 7 (execution_fidelity, evidence, dopamine, ach,
                    novelty, session_tick, cross_session_drift).
    output_dim = 8 (3 + 2 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 8


class EvaluationLearner(LearnerABC):
    """R-PROTO-LEARN.17 owner 17 evaluation learner.

    Maps 7-dim evaluation context -> 8-dim output:
    - output[0:3] fidelity_scoring_policy
    - output[3:5] gap_analysis_policy
    - output[5:8] long_range_diagnostic_policy
    """

    def __init__(
        self,
        config: EvaluationLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or EvaluationLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_evaluation_fields(state)
        return np.array([
            d["execution_fidelity"],
            d["evidence"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["session_tick"],
            d["cross_session_drift"],
        ], dtype=np.float64)

    def _extract_evaluation_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "execution_fidelity": 0.5,
            "evidence": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "session_tick": 0.5,
            "cross_session_drift": 0.5,
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
            return np.array([0.5] * 8, dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # fidelity_scoring_policy: 3 dims
        # - execution_match: high when valence high
        # - signal_alignment: high when dopamine high
        # - temporal_fidelity: high when comfort (c) high
        fidelity = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # execution_match
            np.clip(0.4 + 0.4 * (v - 0.5) + 0.2 * a, 0.0, 1.0),  # signal_alignment
            np.clip(0.4 + 0.4 * c, 0.0, 1.0),  # temporal_fidelity
        ], dtype=np.float64)
        # gap_analysis_policy: 2 dims
        # - missing_threshold: high when tension high
        # - partial_threshold: high when novelty high
        gap = np.array([
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # missing_threshold
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # partial_threshold
        ], dtype=np.float64)
        # long_range_diagnostic_policy: 3 dims
        # - window_size: high when dopamine high (more history)
        # - trend_sensitivity: high when novelty high
        # - drift_threshold: high when pain_like high (cautious)
        long_range = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # window_size
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # trend_sensitivity
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # drift_threshold
        ], dtype=np.float64)
        return np.concatenate([fidelity, gap, long_range])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_evaluation_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_evaluation_fields(state)
        return d["acetylcholine"]
