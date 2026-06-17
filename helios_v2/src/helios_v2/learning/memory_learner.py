"""R-PROTO-LEARN.11 — owner 06 memory learner.

3 policies (mandatory_learned_parameter categories):
- memory_family_write_policy: 3-dim input (episodic/semantic/autobiographical
  signals) -> 3-dim output (family weights, softmax-normalized)
- replay_priority_policy: 5-dim input (affect_intensity, prediction_mismatch,
  autobiographical_salience, time_since_last_replay, novelty) -> 1-dim
  output (replay priority)
- consolidation_policy: 4-dim input (sleep_phase, affect_intensity,
  replay_count, time_since_formation) -> 1-dim output (consolidation rate)

Academic grounding:
- De Lange 2021: replay-based is the only CL approach that works in all
  scenarios (replay_priority_policy).
- Bhatt 2019: reconsolidation is a learning window, not just consolidation
  (consolidation_policy).
- Parisi 2019: memory replay + structural plasticity are 2 of the 6
  lifelong learning mechanisms (memory_family_write_policy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.learning.contracts import LearnerConfig
from helios_v2.learning.framework import LearnerABC


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    shifted = x - np.max(x)
    e = np.exp(shifted)
    return e / np.sum(e)


@dataclass(frozen=True)
class MemoryLearnerConfig(LearnerConfig):
    """R-PROTO-LEARN.11 config.

    3 policies -> total output_dim = 1 (replay priority) + 1 (consolidation) +
    3 (family weights) = 5.
    input_dim = max(5, 4, 3) = 5 (replay_priority has the largest input).
    """
    input_dim: int = 5  # max input across 3 policies
    output_dim: int = 5  # 1 + 1 + 3 policies


class MemoryLearner(LearnerABC):
    """R-PROTO-LEARN.11 owner 06 memory learner.

    Maps 5-dim memory context (affect_intensity, prediction_mismatch,
    autobiographical_salience, time_since_last_replay, novelty) ->
    5-dim output (replay_priority[0] + consolidation_rate[1] +
    episodic_weight[2] + semantic_weight[3] + autobiographical_weight[4]).

    The 3 policies are:
    - replay_priority_policy (output[0]): higher when LLM signal says
      memory should be replayed now.
    - consolidation_policy (output[1]): higher when LLM signal says
      the memory should be consolidated into long-term store.
    - memory_family_write_policy (output[2:5]): softmax-normalized
      weights for episodic vs semantic vs autobiographical families.
    """

    def __init__(self, config: MemoryLearnerConfig | None = None) -> None:
        super().__init__(config=config or MemoryLearnerConfig())

    def _state_to_vec(self, state: Any) -> np.ndarray:
        """Convert memory state -> 5-dim input vector.

        The 5 dims are: affect_intensity, prediction_mismatch,
        autobiographical_salience, time_since_last_replay (decayed),
        novelty. If the state is a dict / dataclass with these fields,
        we read them; otherwise we use 0.5 defaults.

        Defensive: if the state has no recognizable fields, use 0.5.
        """
        d = self._extract_memory_state_fields(state)
        return np.array([
            d["affect_intensity"],
            d["prediction_mismatch"],
            d["autobiographical_salience"],
            d["time_since_last_replay"],
            d["novelty"],
        ], dtype=np.float64)

    def _extract_memory_state_fields(self, state: Any) -> dict[str, float]:
        """Extract 5 fields from owner 06 memory state.

        Defensive: missing fields default to 0.5.
        """
        defaults = {
            "affect_intensity": 0.5,
            "prediction_mismatch": 0.5,
            "autobiographical_salience": 0.5,
            "time_since_last_replay": 0.5,
            "novelty": 0.5,
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
        # Dataclass or object with attributes
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
        """Map 7-dim LLM appraisal -> 5-dim target output.

        Mapping (Panksepp + Parisi inspired):
        - output[0] replay_priority: high when affect intensity is high
          (use LLM signal dim 1 = arousal as proxy)
        - output[1] consolidation_rate: high when feeling is stable
          (use LLM signal dim 0 = valence, low arousal)
        - output[2:5] family weights: episodic / semantic / autobiographical
          (use 3 LLM dims as proxy: novelty -> episodic, valence -> semantic,
          social_safety -> autobiographical)
        """
        if llm_signal is None:
            return np.array([0.5, 0.5, 0.33, 0.33, 0.34], dtype=np.float64)
        # llm_signal is 7-dim: (valence, arousal, tension, comfort, fatigue,
        # pain_like, social_safety)
        v, a, t, c, f, p, s = llm_signal
        replay_priority = float(np.clip(a * 0.6 + (1.0 - c) * 0.4, 0.0, 1.0))
        consolidation_rate = float(np.clip(
            0.5 + 0.5 * (1.0 - a) * c, 0.0, 1.0,
        ))
        # Family weights (3 raw, softmax)
        family_raw = np.array([novelty, v, s], dtype=np.float64)
        family = _softmax(family_raw * 2.0)  # sharpen
        return np.array(
            [replay_priority, consolidation_rate, family[0], family[1], family[2]],
            dtype=np.float64,
        )

    def _dopamine(self, state: Any) -> float:
        d = self._extract_memory_state_fields(state)
        return d["novelty"]  # novelty ~ dopamine proxy

    def _acetylcholine(self, state: Any) -> float:
        d = self._extract_memory_state_fields(state)
        return d["time_since_last_replay"]  # time since last replay ~ ACh proxy
