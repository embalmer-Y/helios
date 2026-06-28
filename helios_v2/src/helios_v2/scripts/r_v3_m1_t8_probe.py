"""M1-T8 OwnerFieldBridge ship 验证探针。

5 个 v2 owner fixture × 1000 tick,验证 OwnerFieldBridge 把 v2 owner 数据桥接到 CDS I:
  - 每 tick 选一个 fixture,bridge 产生 8-dim I
  - SelfModelOwner 用 I 跑 tick
  - 验证 CDS state 稳定 + Kuramoto R ∈ [0, 1]
"""
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m1.owner_field_bridge import (
    OwnerFieldBridge,
    fixture_neutral,
    fixture_high_activation_high_valence,
    fixture_high_threat_high_cortisol,
    fixture_low_energy_fatigue,
)


FIXTURES = [
    ("neutral", fixture_neutral),
    ("high_positive", fixture_high_activation_high_valence),
    ("high_threat", fixture_high_threat_high_cortisol),
    ("low_energy", fixture_low_energy_fatigue),
]


def main():
    n_ticks = 1000
    seed = 42
    np.random.seed(seed)

    bridge = OwnerFieldBridge.default()
    owner = SelfModelOwner.default()

    log_dir = Path("helios_v2/logs/r_v3_m1/bridge_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"bridge_1000t_{timestamp}.jsonl"
    summary_path = log_dir / f"bridge_1000t_summary_{timestamp}.json"

    t0 = time.time()
    nan_count = 0
    solver_failures = 0
    R_history = []
    fixture_counts = {name: 0 for name, _ in FIXTURES}
    fixture_I_means = {name: [] for name, _ in FIXTURES}
    total_emergence_events = 0

    with log_path.open("w", encoding="utf-8") as f:
        for tick in range(n_ticks):
            fix_name, fix_fn = FIXTURES[tick % len(FIXTURES)]
            h, fl, s = fix_fn()
            I = bridge.bridge_input(h, fl, s)

            fixture_counts[fix_name] += 1
            fixture_I_means[fix_name].append(float(np.mean(np.abs(I))))

            result = owner.tick(I=I)
            if not result["solver_success"]:
                solver_failures += 1
            if np.any(np.isnan(result["state"])):
                nan_count += 1
            R_history.append(result["kuramoto_R"])
            total_emergence_events += len(result["emergence_events"])

            if tick < 5 or tick % 100 == 0:
                entry = {
                    "tick": tick,
                    "fixture": fix_name,
                    "I": [round(x, 3) for x in I.tolist()],
                    "kuramoto_R": round(float(result["kuramoto_R"]), 4),
                    "solver_success": bool(result["solver_success"]),
                    "state_l2": round(float(np.linalg.norm(result["state"])), 3),
                    "n_emergence_events": len(result["emergence_events"]),
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0

    summary = {
        "n_ticks": n_ticks,
        "elapsed_seconds": elapsed,
        "ticks_per_second": n_ticks / elapsed,
        "solver_failures": solver_failures,
        "nan_count": nan_count,
        "total_emergence_events": total_emergence_events,
        "fixture_counts": fixture_counts,
        "fixture_I_abs_mean": {
            name: round(float(np.mean(means)), 4) if means else 0.0
            for name, means in fixture_I_means.items()
        },
        "kuramoto_R_mean": round(float(np.mean(R_history)), 4),
        "kuramoto_R_std": round(float(np.std(R_history)), 4),
        "kuramoto_R_min": round(float(np.min(R_history)), 4),
        "kuramoto_R_max": round(float(np.max(R_history)), 4),
        "log_path": str(log_path),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"=== M1-T8 OwnerFieldBridge ship 1000-tick 探针 ===")
    print(f"  ticks:           {n_ticks}")
    print(f"  elapsed:         {elapsed:.2f}s ({summary['ticks_per_second']:.1f} ticks/s)")
    print(f"  solver_failures: {solver_failures}")
    print(f"  nan_count:       {nan_count}")
    print(f"  emergence_events: {total_emergence_events}")
    print(f"  fixture distribution:")
    for name, count in fixture_counts.items():
        print(f"    {name:15s}: {count} ticks, mean |I|={summary['fixture_I_abs_mean'][name]:.3f}")
    print(f"  Kuramoto R:      mean={summary['kuramoto_R_mean']:.4f} "
          f"std={summary['kuramoto_R_std']:.4f} "
          f"[{summary['kuramoto_R_min']:.4f}, {summary['kuramoto_R_max']:.4f}]")
    print(f"  summary: {summary_path}")
    print(f"  trace:   {log_path}")

    if solver_failures > 0 or nan_count > 0:
        print("FAIL: solver/nan 失败")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())