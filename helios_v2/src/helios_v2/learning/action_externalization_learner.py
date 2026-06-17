"""R-PROTO-LEARN.16 — owner 12 action_externalization learner.

3 policies:
- normalization_policy: 3-dim output (intensity_scaling, scope_decision,
  format_priority)
- bridge_evidence_policy: 3-dim output (minimum_evidence_score,
  equivalent_threshold, signal_strength)
- bridge_rejection_policy: 3-dim output (schema_strictness,
  scope_conflict_sensitivity, rejection_threshold)

Academic grounding:
- Kotseruba 2018 self-regulation (normalization_policy: how to package
  the action for outbound).
- Parisi 2019 intrinsic motivation (bridge_evidence_policy: when low
  evidence is acceptable, curiosity-driven exploration).
- Kotseruba 2018 self-observation (bridge_rejection_policy: hard
  constraint enforcement).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class ActionExternalizationLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.16 config.

    input_dim = 7 (action_intensity, scope, candidate_channels,
                    evidence, dopamine, ach, novelty).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class ActionExternalizationLearner(LearnerABC):
    """R-PROTO-LEARN.16 owner 12 action_externalization learner.

    Maps 7-dim action_externalization context -> 9-dim output:
    - output[0:3] normalization_policy
    - output[3:6] bridge_evidence_policy
    - output[6:9] bridge_rejection_policy
    """

    def __init__(
        self,
        config: ActionExternalizationLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or ActionExternalizationLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_action_ext_fields(state)
        return np.array([
            d["action_intensity"],
            d["scope"],  # 0.0 internal, 1.0 external
            d["candidate_channels"],
            d["evidence"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
        ], dtype=np.float64)

    def _extract_action_ext_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "action_intensity": 0.5,
            "scope": 0.5,  # 0=internal, 1=external
            "candidate_channels": 0.5,
            "evidence": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
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
        # normalization_policy: 3 dims
        # - intensity_scaling: high when action strong (arousal high)
        # - scope_decision: binary internal/external
        # - format_priority: high when comfort (c) high (well-formed)
        normalization = np.array([
            np.clip(0.4 + 0.4 * a, 0.0, 1.0),  # intensity_scaling
            np.clip(0.5 + 0.4 * (s - 0.5), 0.0, 1.0),  # scope_decision
            np.clip(0.4 + 0.4 * c, 0.0, 1.0),  # format_priority
        ], dtype=np.float64)
        # bridge_evidence_policy: 3 dims
        # - minimum_evidence_score: low when novelty high (curiosity)
        # - equivalent_threshold: high when dopamine high
        # - signal_strength: high when valence high
        bridge_evidence = np.array([
            np.clip(0.5 - 0.3 * (novelty - 0.5), 0.0, 1.0),  # min_evidence
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # equivalent_threshold
            np.clip(0.4 + 0.4 * (v - 0.5) + 0.2 * (novelty - 0.5), 0.0, 1.0),  # signal_strength
        ], dtype=np.float64)
        # bridge_rejection_policy: 3 dims
        # - schema_strictness: high when tension high (cautious)
        # - scope_conflict_sensitivity: high when pain_like high
        # - rejection_threshold: high when dopamine high (confident)
        bridge_rejection = np.array([
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # schema_strictness
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # scope_conflict
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # rejection_threshold
        ], dtype=np.float64)
        return np.concatenate([normalization, bridge_evidence, bridge_rejection])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_action_ext_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_action_ext_fields(state)
        return d["acetylcholine"]
