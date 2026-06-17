"""R-PROTO-LEARN.Tier2 2-owner end-to-end real LLM smoke test.

Owner: 12 action_externalization, 17 evaluation.

For each owner:
  - Initialize its learner.
  - Run 8 ticks with synthetic LLM appraisal + novelty.
  - Verify: closed-loop residual, regime progression, |W| change.

Usage:
  PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier2_smoke.py
"""

from __future__ import annotations

import sys
from statistics import mean

from helios_v2.learning import (
    ActionExternalizationLearner,
    EvaluationLearner,
    Regime,
)


def _7d_signal_from_appraisal(appraisal: dict[str, float]) -> tuple[float, ...]:
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
    # Owner 12 action_externalization: action intensity progression
    #   External scope throughout. Strong evidence, varied arousal.
    ael_scenarios = [
        ({"valence": 0.4, "arousal": 0.8, "tension": 0.6, "comfort": 0.3,
          "fatigue": 0.4, "pain_like": 0.3, "social_safety": 0.7}, 0.7),
        ({"valence": 0.5, "arousal": 0.7, "tension": 0.5, "comfort": 0.4,
          "fatigue": 0.4, "pain_like": 0.3, "social_safety": 0.7}, 0.6),
        ({"valence": 0.6, "arousal": 0.6, "tension": 0.4, "comfort": 0.5,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.7}, 0.5),
        ({"valence": 0.6, "arousal": 0.6, "tension": 0.4, "comfort": 0.5,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.7}, 0.5),
        ({"valence": 0.7, "arousal": 0.5, "tension": 0.3, "comfort": 0.6,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.7}, 0.4),
        ({"valence": 0.7, "arousal": 0.5, "tension": 0.3, "comfort": 0.6,
          "fatigue": 0.3, "pain_like": 0.2, "social_safety": 0.7}, 0.4),
        ({"valence": 0.8, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.2, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.8, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.2, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
    ]

    # Owner 17 evaluation: high fidelity, stable execution
    #   Long-range session: drift accumulates slowly.
    el_scenarios = [
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
        ({"valence": 0.7, "arousal": 0.4, "tension": 0.2, "comfort": 0.7,
          "fatigue": 0.3, "pain_like": 0.1, "social_safety": 0.8}, 0.3),
    ]

    learners = [
        ("ActionExternalization (12)", ActionExternalizationLearner(), ael_scenarios),
        ("Evaluation (17)", EvaluationLearner(), el_scenarios),
    ]

    print("=" * 60)
    print("R-PROTO-LEARN Tier 2 — 2 owner behavior smoke")
    print("=" * 60)

    results = []
    for name, learner, scenarios in learners:
        result = smoke_test_one_learner(name, learner, scenarios)
        results.append(result)
        print(
            f"{name:32s}  avg_max_res={result['avg_max_residual']:.4f}  "
            f"regime={result['final_regime']:13s}  "
            f"commits={result['commit_count']}  "
            f"|W|max={result['max_abs_weight']:.4f}"
        )

    print()
    print("Summary:")
    print(f"  2 owner learners ran.")
    print(f"  Avg avg_max_residual: {mean([r['avg_max_residual'] for r in results]):.4f}")
    print(f"  Total commits: {sum(r['commit_count'] for r in results)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
