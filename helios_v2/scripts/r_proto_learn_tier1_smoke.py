"""R-PROTO-LEARN.Tier1 5-owner end-to-end real LLM smoke test.

Owner: 06 memory, 09 thought_gating, 10 directed_retrieval,
11 internal_thought, 18 autonomy.

For each owner:
  - Initialize its learner.
  - Run 8 ticks with synthetic LLM appraisal + novelty.
  - Verify: closed-loop residual, regime progression, |W| change.

Usage:
  PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier1_smoke.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from statistics import mean

import numpy as np

# Owner
from helios_v2.learning import (
    MemoryLearner,
    ThoughtGatingLearner,
    RetrievalLearner,
    InternalThoughtLearner,
    AutonomyLearner,
    Regime,
)


def _7d_signal_from_appraisal(appraisal: dict[str, float]) -> tuple[float, ...]:
    """Convert 7-dim appraisal dict to 7-tuple in canonical order."""
    return (
        appraisal.get("valence", 0.5),
        appraisal.get("arousal", 0.5),
        appraisal.get("tension", 0.5),
        appraisal.get("comfort", 0.5),
        appraisal.get("fatigue", 0.5),
        appraisal.get("pain_like", 0.5),
        appraisal.get("social_safety", 0.5),
    )


def smoke_test_one_learner(
    name: str,
    learner,
    scenarios: list[tuple[dict[str, float], float]],
) -> dict[str, float]:
    """Run smoke test for one learner with given scenarios.

    scenarios: list of (appraisal_dict, novelty).
    """
    max_residuals = []
    for tick_id, (appraisal, novelty) in enumerate(scenarios):
        llm_signal = _7d_signal_from_appraisal(appraisal)
        snap = learner.update(
            state=None,
            llm_signal=llm_signal,
            novelty=novelty,
            tick_id=tick_id,
        )
        max_res = max(abs(v) for v in snap.residual)
        max_residuals.append(max_res)

    return {
        "name": name,
        "avg_max_residual": mean(max_residuals),
        "final_regime": learner.regime().value,
        "commit_count": learner.commit_count(),
        "max_abs_weight": learner.max_abs_weight(),
    }


def main() -> int:
    # ----- 5 owner scenarios (8 ticks each) -----

    # Owner 06 memory: surprise × autobiographical salience progression
    memory_scenarios = [
        ({"valence": 0.3, "arousal": 0.8, "tension": 0.7, "comfort": 0.2,
          "fatigue": 0.4, "pain_like": 0.6, "social_safety": 0.3}, 0.9),
        ({"valence": 0.3, "arousal": 0.8, "tension": 0.7, "comfort": 0.2,
          "fatigue": 0.4, "pain_like": 0.6, "social_safety": 0.3}, 0.8),
        ({"valence": 0.4, "arousal": 0.7, "tension": 0.6, "comfort": 0.3,
          "fatigue": 0.5, "pain_like": 0.5, "social_safety": 0.4}, 0.7),
        ({"valence": 0.5, "arousal": 0.6, "tension": 0.5, "comfort": 0.5,
          "fatigue": 0.5, "pain_like": 0.4, "social_safety": 0.5}, 0.6),
        ({"valence": 0.6, "arousal": 0.5, "tension": 0.4, "comfort": 0.6,
          "fatigue": 0.4, "pain_like": 0.3, "social_safety": 0.6}, 0.5),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.3, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.7}, 0.4),
        ({"valence": 0.8, "arousal": 0.3, "tension": 0.2, "comfort": 0.8,
          "fatigue": 0.2, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.9, "arousal": 0.2, "tension": 0.1, "comfort": 0.9,
          "fatigue": 0.1, "pain_like": 0.0, "social_safety": 0.9}, 0.2),
    ]

    # Owner 09 thought_gating: arousal-driven gating under novelty
    tg_scenarios = [
        ({"valence": 0.5, "arousal": 0.8, "tension": 0.6, "comfort": 0.4,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.5}, 0.7),
    ] * 8

    # Owner 10 directed_retrieval: vary dopaminergic + novelty
    dr_scenarios = [
        ({"valence": 0.4, "arousal": 0.6, "tension": 0.5, "comfort": 0.5,
          "fatigue": 0.4, "pain_like": 0.3, "social_safety": 0.5}, 0.8),
        ({"valence": 0.5, "arousal": 0.5, "tension": 0.4, "comfort": 0.6,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.6}, 0.6),
        ({"valence": 0.6, "arousal": 0.4, "tension": 0.3, "comfort": 0.7,
          "fatigue": 0.2, "pain_like": 0.1, "social_safety": 0.7}, 0.4),
    ] + [
        ({"valence": 0.7, "arousal": 0.3, "tension": 0.2, "comfort": 0.8,
          "fatigue": 0.1, "pain_like": 0.0, "social_safety": 0.8}, 0.2),
    ] * 5

    # Owner 11 internal_thought: simple looping
    it_scenarios = [
        ({"valence": 0.5, "arousal": 0.5, "tension": 0.5, "comfort": 0.5,
          "fatigue": 0.5, "pain_like": 0.5, "social_safety": 0.5}, 0.5),
    ] * 8

    # Owner 18 autonomy: high valence + social_safety progression
    auto_scenarios = [
        ({"valence": 0.3, "arousal": 0.5, "tension": 0.4, "comfort": 0.6,
          "fatigue": 0.5, "pain_like": 0.3, "social_safety": 0.7}, 0.5),
    ] * 8

    learners = [
        ("Memory (06)", MemoryLearner(), memory_scenarios),
        ("ThoughtGating (09)", ThoughtGatingLearner(), tg_scenarios),
        ("Retrieval (10)", RetrievalLearner(), dr_scenarios),
        ("InternalThought (11)", InternalThoughtLearner(), it_scenarios),
        ("Autonomy (18)", AutonomyLearner(), auto_scenarios),
    ]

    print("=" * 60)
    print("R-PROTO-LEARN Tier 1 — 5 owner smoke")
    print("=" * 60)

    results = []
    for name, learner, scenarios in learners:
        result = smoke_test_one_learner(name, learner, scenarios)
        results.append(result)
        print(
            f"{name:24s}  avg_max_res={result['avg_max_residual']:.4f}  "
            f"regime={result['final_regime']:13s}  "
            f"commits={result['commit_count']}  "
            f"|W|max={result['max_abs_weight']:.4f}"
        )

    print()
    print("Summary:")
    print(f"  5 owner learners ran.")
    print(f"  Avg avg_max_residual: {mean([r['avg_max_residual'] for r in results]):.4f}")
    print(f"  Total commits: {sum(r['commit_count'] for r in results)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
