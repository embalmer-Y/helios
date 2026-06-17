"""R-PROTO-LEARN.19 — owner 16a outward_expression learner.

3 policies:
- delivery_guidance_policy: 3-dim output (tone_strength, detail_level,
  persona_emphasis)
- boundary_rendering_policy: 3-dim output (governance_strictness,
  identity_signal, constraint_depth)
- draft_publication_policy: 3-dim output (publication_threshold,
  cooling_off, revision_pressure)

Academic grounding:
- Kotseruba 2018 self-observation: delivery_guidance_policy is the
  observation layer that styles the output.
- Helios R80 governance: boundary_rendering_policy is the
  governance signal that shapes the system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class OutwardExpressionLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.19 config.

    input_dim = 7 (draft_intensity, governance_pressure,
                    identity_strength, dopamine, ach, novelty,
                    last_publish_tick).
    output_dim = 9 (3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 9


class OutwardExpressionLearner(LearnerABC):
    """R-PROTO-LEARN.19 owner 16a outward_expression learner.

    Maps 7-dim outward_expression context -> 9-dim output:
    - output[0:3] delivery_guidance_policy
    - output[3:6] boundary_rendering_policy
    - output[6:9] draft_publication_policy
    """

    def __init__(
        self,
        config: OutwardExpressionLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or OutwardExpressionLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_outward_expression_fields(state)
        return np.array([
            d["draft_intensity"],
            d["governance_pressure"],
            d["identity_strength"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["last_publish_tick"],
        ], dtype=np.float64)

    def _extract_outward_expression_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "draft_intensity": 0.5,
            "governance_pressure": 0.5,
            "identity_strength": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "last_publish_tick": 0.5,
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
        # delivery_guidance_policy: 3 dims
        delivery = np.array([
            np.clip(0.4 + 0.3 * v, 0.0, 1.0),  # tone_strength
            np.clip(0.4 + 0.3 * (novelty - 0.5), 0.0, 1.0),  # detail_level
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # persona_emphasis
        ], dtype=np.float64)
        # boundary_rendering_policy: 3 dims
        boundary = np.array([
            np.clip(0.4 + 0.4 * t, 0.0, 1.0),  # governance_strictness
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # identity_signal
            np.clip(0.4 + 0.3 * p, 0.0, 1.0),  # constraint_depth
        ], dtype=np.float64)
        # draft_publication_policy: 3 dims
        publication = np.array([
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # publication_threshold
            np.clip(0.3 + 0.3 * f, 0.0, 1.0),  # cooling_off
            np.clip(0.4 + 0.3 * a, 0.0, 1.0),  # revision_pressure
        ], dtype=np.float64)
        return np.concatenate([delivery, boundary, publication])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_outward_expression_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_outward_expression_fields(state)
        return d["acetylcholine"]
