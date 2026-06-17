"""R-PROTO-LEARN.23 — owner 14 identity_governance learner.

4 policies:
- governance_evaluation_policy: 3-dim output (evaluation_threshold,
  alignment_strictness, weight)
- pressure_interpretation_policy: 3-dim output (pressure_threshold,
  signal_strength, interpretation_bias)
- supported_revision_policy: 3-dim output (revision_threshold,
  support_weight, alignment_strictness)
- boundary_check_policy: 3-dim output (boundary_strictness,
  safety_margin, fall_back_score)

Academic grounding:
- Kotseruba 2018 self-regulation: governance_evaluation_policy is
  the performance monitor; pressure_interpretation_policy is the
  state evaluator; supported_revision_policy is the controller.
- R79-R80 governance: boundary_check_policy enforces the
  no-theater constraint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class IdentityGovernanceLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.23 config.

    input_dim = 7 (pressure_intensity, signal_strength, dopamine, ach,
                    novelty, proposal_count, boundary_risk).
    output_dim = 12 (3 + 3 + 3 + 3 policies).
    """
    input_dim: int = 7
    output_dim: int = 12


class IdentityGovernanceLearner(LearnerABC):
    """R-PROTO-LEARN.23 owner 14 identity_governance learner.

    Maps 7-dim identity context -> 12-dim output:
    - output[0:3] governance_evaluation_policy
    - output[3:6] pressure_interpretation_policy
    - output[6:9] supported_revision_policy
    - output[9:12] boundary_check_policy
    """

    def __init__(
        self,
        config: IdentityGovernanceLearnerConfig | None = None,
    ) -> None:
        super().__init__(config=config or IdentityGovernanceLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_identity_governance_fields(state)
        return np.array([
            d["pressure_intensity"],
            d["signal_strength"],
            d["dopamine"],
            d["acetylcholine"],
            d["novelty"],
            d["proposal_count"],
            d["boundary_risk"],
        ], dtype=np.float64)

    def _extract_identity_governance_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "pressure_intensity": 0.5,
            "signal_strength": 0.5,
            "dopamine": 0.5,
            "acetylcholine": 0.5,
            "novelty": 0.5,
            "proposal_count": 0.5,
            "boundary_risk": 0.5,
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
            return np.array([0.5] * 12, dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # governance_evaluation_policy: 3 dims (Kotseruba 2018 monitor)
        evaluation = np.array([
            np.clip(0.4 + 0.4 * (1.0 - v), 0.0, 1.0),  # evaluation_threshold
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # alignment_strictness
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # weight
        ], dtype=np.float64)
        # pressure_interpretation_policy: 3 dims (Kotseruba 2018 evaluator)
        pressure = np.array([
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # pressure_threshold
            np.clip(0.4 + 0.4 * v, 0.0, 1.0),  # signal_strength
            np.clip(0.3 + 0.3 * a, 0.0, 1.0),  # interpretation_bias
        ], dtype=np.float64)
        # supported_revision_policy: 3 dims (Kotseruba 2018 controller)
        revision = np.array([
            np.clip(0.4 + 0.3 * (1.0 - v), 0.0, 1.0),  # revision_threshold
            np.clip(0.4 + 0.3 * s, 0.0, 1.0),  # support_weight
            np.clip(0.4 + 0.3 * t, 0.0, 1.0),  # alignment_strictness
        ], dtype=np.float64)
        # boundary_check_policy: 3 dims (R79-R80 governance)
        boundary = np.array([
            np.clip(0.4 + 0.4 * t, 0.0, 1.0),  # boundary_strictness
            np.clip(0.4 + 0.3 * f, 0.0, 1.0),  # safety_margin
            np.clip(0.3 + 0.3 * a, 0.0, 1.0),  # fall_back_score
        ], dtype=np.float64)
        return np.concatenate([evaluation, pressure, revision, boundary])

    def _dopamine(self, state: Any) -> float:
        d = self._extract_identity_governance_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_identity_governance_fields(state)
        return d["acetylcholine"]
