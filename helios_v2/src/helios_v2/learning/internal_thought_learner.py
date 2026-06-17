"""R-PROTO-LEARN.14 — owner 11 internal_thought learner.

3 policies:
- thought_generation_policy: 6-dim input (feeling_valence, feeling_arousal,
  feeling_tension, novelty, dopamine, gate_open) -> 1-dim output
  (thought_generation_rate)
- sufficiency_policy: 4-dim input (thought_count, novelty, dopamine,
  continuation_rate) -> 1-dim output (sufficiency_threshold)
- proposal_emission_policy: 5-dim input (dopamine, feeling_valence,
  acetylcholine, novelty, sufficiency) -> 1-dim output (emission_rate)

Academic grounding:
- Kotseruba 2018 self-observation (thought_generation_policy).
- R85 reconsolidation C+D combination (sufficiency_policy).
- dopaminergic emission gating (proposal_emission_policy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


@dataclass(frozen=True)
class InternalThoughtLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.14 config.

    input_dim = 6 (thought_generation has the largest input).
    output_dim = 1 + 1 + 1 = 3.
    """
    input_dim: int = 6
    output_dim: int = 3


class InternalThoughtLearner(LearnerABC):
    """R-PROTO-LEARN.14 owner 11 internal_thought learner.

    Maps 6-dim internal_thought context -> 3-dim output:
    - output[0] thought_generation_rate
    - output[1] sufficiency_threshold
    - output[2] emission_rate
    """

    def __init__(self, config: InternalThoughtLearnerConfig | None = None) -> None:
        super().__init__(config=config or InternalThoughtLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        d = self._extract_internal_thought_fields(state)
        return np.array([
            d["feeling_valence"],
            d["feeling_arousal"],
            d["feeling_tension"],
            d["novelty"],
            d["dopamine"],
            d["gate_open"],
        ], dtype=np.float64)

    def _extract_internal_thought_fields(self, state: Any) -> dict[str, float]:
        defaults = {
            "feeling_valence": 0.5,
            "feeling_arousal": 0.5,
            "feeling_tension": 0.5,
            "novelty": 0.5,
            "dopamine": 0.5,
            "gate_open": 0.5,
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
            return np.array([0.5, 0.5, 0.5], dtype=np.float64)
        v, a, t, c, f, p, s = llm_signal
        # thought_generation_rate: high when arousal + novelty high
        gen = float(np.clip(0.3 + 0.4 * a + 0.3 * novelty, 0.0, 1.0))
        # sufficiency_threshold: high when dopamine high (confident)
        suff = float(np.clip(0.4 + 0.5 * v, 0.0, 1.0))
        # emission_rate: modulated by dopamine + valence
        emi = float(np.clip(0.3 + 0.4 * v + 0.2 * a, 0.0, 1.0))
        return np.array([gen, suff, emi], dtype=np.float64)

    def _dopamine(self, state: Any) -> float:
        d = self._extract_internal_thought_fields(state)
        return d["dopamine"]

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_internal_thought_fields(state)
        return d["novelty"]  # proxy
