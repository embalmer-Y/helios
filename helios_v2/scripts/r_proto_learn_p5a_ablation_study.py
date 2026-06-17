"""P5-A ablation study — H0 (LLM) vs H1 (RealRPE) vs H2 (mixed).

Owner: R-PROTO-LEARN.P5-A signal layer.

Compares three learning signal sources for 5 representative owner
learners across the unified helios_v2/learning/ framework:

  H0 — LLM appraisal only (baseline, current Tier 1-4 ship signal source)
  H1 — RealRPE only (P5-A new signal source from runtime consequences)
  H2 — Mixed 0.7 RealRPE + 0.3 LLM appraisal

5 representative owners (across 4 tiers and 4 different W shapes):
  R11 owner 06 memory            — 5x5 W (full rank)
  R13 owner 10 directed_retrieval — 11x6 W (rank-6 limit)
  R14 owner 11 internal_thought  — 3x6 W (underdetermined)
  R17 owner 17 evaluation        — 8x7 W (near full rank)
  R21 owner 08 consciousness     — 9x7 W (rank-7 limit)

Each run: 100 ticks, 5 seeds (42, 43, 44, 45, 46).
Total runs: 5 owners x 3 groups x 5 seeds = 75 runs.

Recorded per run:
  - regime_switch_count
  - commit_count
  - avg_max_residual
  - dopamine_trace (H1, H2 only)

Statistical tests:
  A2: t-test regime_switch_count H1 vs H0, expect H1 > 2*H0
  A3: t-test commit_count H1 vs H0, expect H0 > 3*H1
  A4: Pearson r dopamine_trace H2 vs H1, expect r > 0.5
  A5: per-owner residual diff H1 vs H0 > 0.1

Usage:
  PYTHONPATH=src python scripts/r_proto_learn_p5a_ablation_study.py [--quick]
  --quick: 3 owners x 1 seed x 20 ticks (smoke)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

import numpy as np
from scipy.stats import pearsonr, ttest_ind

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from helios_v2.learning import (
    MemoryLearner,
    RetrievalLearner,
    InternalThoughtLearner,
    EvaluationLearner,
    ConsciousnessLearner,
)
from helios_v2.rpe import (
    RealRPEConfig,
    compute_rpe,
    mock_environment_tick,
    phase_label,
)


@dataclass
class RunResult:
    owner: str
    group: str  # "H0" / "H1" / "H2"
    seed: int
    ticks: int
    regime_switches: int
    commit_count: int
    avg_max_residual: float
    regime_trace: list = field(default_factory=list)
    dopamine_trace: list = field(default_factory=list)
    phase_counts: dict = field(default_factory=dict)


def _rpe_to_7d(rpe_dopamine: float, rpe_ne: float, rpe_ser: float, rpe_cor: float) -> Tuple[float, ...]:
    """Project 4-channel RPE into 7-dim Panksepp-style appraisal.

    Mapping (R-PROTO-LEARN.10 + Panksepp 7 systems + Kotseruba 2018):
      dim0 valence      = ser - cor            (stability - threat)
      dim1 arousal      = ne                   (effort / engagement)
      dim2 dominance     = 1.0 - cor            (safety from threat)
      dim3 tension       = cor + (1 - ser)      (stress + instability)
      dim4 comfort       = ser                  (stability)
      dim5 social_safety = ser                  (proxy)
      dim6 baseline_arousal = ne                (effort baseline)
    """
    valence = max(0.0, min(1.0, rpe_ser - rpe_cor + 0.5))
    arousal = rpe_ne
    dominance = max(0.0, min(1.0, 1.0 - rpe_cor))
    tension = max(0.0, min(1.0, rpe_cor + (1.0 - rpe_ser)))
    comfort = rpe_ser
    social_safety = rpe_ser
    baseline_arousal = rpe_ne
    return (valence, arousal, dominance, tension, comfort, social_safety, baseline_arousal)


def _llm_target_vec_mock(tick: int) -> Tuple[float, ...]:
    """Mock 7-dim LLM appraisal (H0 baseline signal source).

    Independent of mock_environment_tick — uses random walk instead so
    H0 and H1 carry genuinely different signal distributions.
    """
    rng = np.random.default_rng(tick)
    return tuple(float(x) for x in rng.uniform(0.2, 0.8, size=7))


def _build_learner(owner_id: str):
    if owner_id == "R11":
        return MemoryLearner()
    if owner_id == "R13":
        return RetrievalLearner()
    if owner_id == "R14":
        return InternalThoughtLearner()
    if owner_id == "R17":
        return EvaluationLearner()
    if owner_id == "R21":
        return ConsciousnessLearner()
    raise ValueError(f"Unknown owner {owner_id}")


def _run(owner_id: str, group: str, seed: int, ticks: int) -> RunResult:
    rng = np.random.default_rng(seed)
    learner = _build_learner(owner_id)
    rpe_config = RealRPEConfig()
    predicted_reward = 0.5

    last_regime = None
    regime_switches = 0
    commit_count = 0
    residuals = []
    regime_trace = []
    dopamine_trace = []
    phase_counts = {"easy": 0, "medium": 0, "hard": 0}

    for tick in range(ticks):
        outcome, continuity, conflict = mock_environment_tick(tick, owner_id)
        phase = phase_label(tick)
        phase_counts[phase] += 1
        novelty = float(rng.uniform(0.0, 1.0))

        if group == "H0":
            llm_signal = _llm_target_vec_mock(tick + seed * 1000)
            signal_7d = llm_signal
        elif group == "H1":
            rpe = compute_rpe(predicted_reward, outcome, continuity, conflict, rpe_config, tick)
            signal_7d = _rpe_to_7d(rpe.dopamine, rpe.norepinephrine, rpe.serotonin, rpe.cortisol)
            dopamine_trace.append(rpe.dopamine)
            predicted_reward = max(0.0, min(1.0, predicted_reward - rpe.dopamine * 0.1))
        elif group == "H2":
            rpe = compute_rpe(predicted_reward, outcome, continuity, conflict, rpe_config, tick)
            rpe_7d = _rpe_to_7d(rpe.dopamine, rpe.norepinephrine, rpe.serotonin, rpe.cortisol)
            llm_7d = _llm_target_vec_mock(tick + seed * 1000)
            signal_7d = tuple(0.7 * r + 0.3 * l for r, l in zip(rpe_7d, llm_7d))
            dopamine_trace.append(rpe.dopamine)
            predicted_reward = max(0.0, min(1.0, predicted_reward - rpe.dopamine * 0.1))
        else:
            raise ValueError(f"Unknown group {group}")

        snap = learner.update(None, signal_7d, novelty=novelty, tick_id=tick)
        residuals.append(max(abs(v) for v in snap.residual))
        regime_trace.append(snap.regime.value)
        if last_regime is not None and snap.regime.value != last_regime:
            regime_switches += 1
        last_regime = snap.regime.value
        if snap.commit:
            commit_count += 1

    return RunResult(
        owner=owner_id,
        group=group,
        seed=seed,
        ticks=ticks,
        regime_switches=regime_switches,
        commit_count=commit_count,
        avg_max_residual=float(np.mean(residuals)),
        regime_trace=regime_trace,
        dopamine_trace=dopamine_trace,
        phase_counts=phase_counts,
    )


def _aggregate(results: list) -> dict:
    """Aggregate RunResult list into per-group summary stats."""
    by_group = {"H0": [], "H1": [], "H2": []}
    for r in results:
        by_group[r.group].append(r)
    summary = {}
    for group, runs in by_group.items():
        summary[group] = {
            "n_runs": len(runs),
            "regime_switches_mean": float(np.mean([r.regime_switches for r in runs])),
            "regime_switches_std": float(np.std([r.regime_switches for r in runs])),
            "commit_count_mean": float(np.mean([r.commit_count for r in runs])),
            "commit_count_std": float(np.std([r.commit_count for r in runs])),
            "avg_max_residual_mean": float(np.mean([r.avg_max_residual for r in runs])),
            "avg_max_residual_std": float(np.std([r.avg_max_residual for r in runs])),
        }
    return summary


def _stat_tests(results: list) -> dict:
    """Statistical tests A2/A3/A4/A5."""
    h0 = [r for r in results if r.group == "H0"]
    h1 = [r for r in results if r.group == "H1"]
    h2 = [r for r in results if r.group == "H2"]
    tests = {}

    # A2: regime_switch H1 vs H0
    h0_switches = [r.regime_switches for r in h0]
    h1_switches = [r.regime_switches for r in h1]
    if len(h0_switches) >= 2 and len(h1_switches) >= 2:
        t, p = ttest_ind(h1_switches, h0_switches, equal_var=False)
        tests["A2_regime_switch_H1_vs_H0"] = {
            "H0_mean": float(np.mean(h0_switches)),
            "H1_mean": float(np.mean(h1_switches)),
            "t_stat": float(t),
            "p_value": float(p),
            "ratio": float(np.mean(h1_switches)) / max(1e-6, np.mean(h0_switches)),
            "pass": bool(p < 0.05 and np.mean(h1_switches) >= 2 * np.mean(h0_switches) - 1e-6),
        }

    # A3: commit_count H1 vs H0
    h0_commits = [r.commit_count for r in h0]
    h1_commits = [r.commit_count for r in h1]
    if len(h0_commits) >= 2 and len(h1_commits) >= 2:
        t, p = ttest_ind(h0_commits, h1_commits, equal_var=False)
        tests["A3_commit_H1_vs_H0"] = {
            "H0_mean": float(np.mean(h0_commits)),
            "H1_mean": float(np.mean(h1_commits)),
            "t_stat": float(t),
            "p_value": float(p),
            "ratio": float(np.mean(h0_commits)) / max(1e-6, np.mean(h1_commits)),
            "pass": bool(p < 0.05 and np.mean(h0_commits) >= 3 * np.mean(h1_commits) - 1e-6),
        }

    # A4: dopamine trace H2 vs H1 correlation
    h1_traces = [r.dopamine_trace for r in h1 if r.dopamine_trace]
    h2_traces = [r.dopamine_trace for r in h2 if r.dopamine_trace]
    if h1_traces and h2_traces:
        h1_avg = np.mean([np.array(t) for t in h1_traces], axis=0)
        h2_avg = np.mean([np.array(t) for t in h2_traces], axis=0)
        if len(h1_avg) >= 3:
            r, p = pearsonr(h1_avg, h2_avg)
            tests["A4_dopamine_H2_vs_H1_corr"] = {
                "r": float(r),
                "p_value": float(p),
                "pass": bool(r > 0.5 and p < 0.05),
            }

    # A5: per-owner residual diff H1 vs H0
    owners = sorted({r.owner for r in results})
    a5 = {}
    for owner in owners:
        h0_res = [r.avg_max_residual for r in h0 if r.owner == owner]
        h1_res = [r.avg_max_residual for r in h1 if r.owner == owner]
        if h0_res and h1_res:
            diff = float(np.mean(h1_res) - np.mean(h0_res))
            a5[owner] = {
                "H0_mean": float(np.mean(h0_res)),
                "H1_mean": float(np.mean(h1_res)),
                "diff": diff,
                "pass": bool(abs(diff) > 0.1),
            }
    tests["A5_per_owner_residual_diff"] = a5

    return tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="3 owners x 1 seed x 20 ticks smoke")
    parser.add_argument("--output", default="/tmp/p5a_ablation_results.json")
    args = parser.parse_args()

    if args.quick:
        owners = ["R11", "R14", "R21"]
        seeds = [42]
        ticks = 20
    else:
        owners = ["R11", "R13", "R14", "R17", "R21"]
        seeds = [42, 43, 44, 45, 46]
        ticks = 100

    groups = ["H0", "H1", "H2"]
    results = []
    total = len(owners) * len(groups) * len(seeds)
    print(f"[P5-A ablation] running {total} runs ({len(owners)} owners x {len(groups)} groups x {len(seeds)} seeds, {ticks} ticks each)")
    t0 = time.time()
    for owner_id in owners:
        for group in groups:
            for seed in seeds:
                r = _run(owner_id, group, seed, ticks)
                results.append(r)
                print(f"  [{owner_id} {group} seed={seed}] switches={r.regime_switches} commits={r.commit_count} residual={r.avg_max_residual:.3f}")

    elapsed = time.time() - t0
    print(f"\n[P5-A ablation] done in {elapsed:.1f}s")
    summary = _aggregate(results)
    tests = _stat_tests(results)

    print("\n=== Summary ===")
    for group, stats in summary.items():
        print(f"  {group}: switches={stats['regime_switches_mean']:.1f}±{stats['regime_switches_std']:.1f} commits={stats['commit_count_mean']:.1f}±{stats['commit_count_std']:.1f} residual={stats['avg_max_residual_mean']:.3f}±{stats['avg_max_residual_std']:.3f}")

    print("\n=== Statistical tests ===")
    for k, v in tests.items():
        if isinstance(v, dict) and "pass" in v:
            status = "✅ PASS" if v["pass"] else "❌ FAIL"
            print(f"  {k}: {status}")
            for kk, vv in v.items():
                if kk != "pass":
                    print(f"    {kk} = {vv}")

    out = {
        "config": {"owners": owners, "seeds": seeds, "ticks": ticks, "groups": groups},
        "summary": summary,
        "tests": tests,
        "n_runs": len(results),
        "elapsed_seconds": elapsed,
    }
    Path(args.output).write_text(json.dumps(out, indent=2, default=str))
    print(f"\n[P5-A ablation] results written to {args.output}")


if __name__ == "__main__":
    main()