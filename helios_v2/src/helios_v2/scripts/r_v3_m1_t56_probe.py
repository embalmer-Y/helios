"""M1-T5 + M1-T6 ship 验证探针。

1000 tick 跑 SelfModelOwner:
  - 检查 solver 不 NaN
  - 累积 emergence_events
  - 检查 Kuramoto R 合理
"""
import json
import time
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner


def main():
    n_ticks = 1000
    seed = 42
    np.random.seed(seed)

    owner = SelfModelOwner.default()
    t0 = time.time()

    nan_count = 0
    solver_failures = 0
    total_emergence_events = 0
    event_type_counts = {"sync_cluster": 0, "phase_transition": 0, "resonance": 0}
    R_history = []

    log_dir = Path("helios_v2/logs/r_v3_m1/self_model_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"self_model_1000t_{timestamp}.jsonl"

    for tick in range(n_ticks):
        I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
        result = owner.tick(I=I)

        if not result["solver_success"]:
            solver_failures += 1

        if np.any(np.isnan(result["state"])):
            nan_count += 1

        R_history.append(result["kuramoto_R"])
        n_events = len(result["emergence_events"])
        total_emergence_events += n_events
        for ev in result["emergence_events"]:
            event_type_counts[ev["type"]] = event_type_counts.get(ev["type"], 0) + 1

        if tick < 5 or tick % 100 == 0:
            entry = {
                "tick": tick,
                "kuramoto_R": float(result["kuramoto_R"]),
                "solver_success": bool(result["solver_success"]),
                "self_unity": float(result["self_experience"]["self_unity"]),
                "agency_strength": float(result["self_experience"]["agency_strength"]),
                "rochat_level_continuous": float(result["self_experience"]["rochat_level_continuous"]),
                "n_emergence_events_this_tick": n_events,
                "emergence_event_types": [e["type"] for e in result["emergence_events"]],
                "state_l2_norm": float(np.linalg.norm(result["state"])),
                "state_min": float(np.min(result["state"])),
                "state_max": float(np.max(result["state"])),
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0

    summary = {
        "n_ticks": n_ticks,
        "elapsed_seconds": elapsed,
        "ticks_per_second": n_ticks / elapsed,
        "solver_failures": solver_failures,
        "nan_count": nan_count,
        "total_emergence_events": total_emergence_events,
        "event_type_counts": event_type_counts,
        "kuramoto_R_mean": float(np.mean(R_history)),
        "kuramoto_R_std": float(np.std(R_history)),
        "kuramoto_R_min": float(np.min(R_history)),
        "kuramoto_R_max": float(np.max(R_history)),
        "log_path": str(log_path),
    }

    summary_path = log_dir / f"self_model_1000t_summary_{timestamp}.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"=== M1-T5 + M1-T6 ship 1000-tick 探针 ===")
    print(f"  ticks:           {n_ticks}")
    print(f"  elapsed:         {elapsed:.2f}s ({summary['ticks_per_second']:.1f} ticks/s)")
    print(f"  solver_failures: {solver_failures}")
    print(f"  nan_count:       {nan_count}")
    print(f"  emergence_events: {total_emergence_events}")
    print(f"    by type:       {event_type_counts}")
    print(f"  Kuramoto R:      mean={summary['kuramoto_R_mean']:.4f} "
          f"std={summary['kuramoto_R_std']:.4f} "
          f"[{summary['kuramoto_R_min']:.4f}, {summary['kuramoto_R_max']:.4f}]")
    print(f"  summary: {summary_path}")
    print(f"  trace:   {log_path}")

    if solver_failures > 0 or nan_count > 0 or total_emergence_events == 0:
        print("FAIL: 探针失败 (solver/nan/emergence)")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())