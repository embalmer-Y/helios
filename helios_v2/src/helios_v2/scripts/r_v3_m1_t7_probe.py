"""M1-T7 CDS 跟 LLM 异步鲁棒性 ship 验证探针。

5 个场景 × 1000 tick,验证 SelfModelOwner 跟 LLM 异步交互时仍然稳定。
"""
import json
import time
from datetime import datetime
from pathlib import Path

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m1.async_loop import (
    simulate_async_loop,
    pattern_synchronous,
    pattern_fast_async,
    pattern_slow_async,
    pattern_random_jitter,
    pattern_with_timeouts,
)


SCENARIOS = [
    ("a_synchronous", pattern_synchronous),
    ("b_fast_async_1to2ticks", pattern_fast_async),
    ("c_slow_async_5ticks", pattern_slow_async),
    ("d_random_jitter_0to8ticks", pattern_random_jitter),
    ("e_with_timeouts_10pct", pattern_with_timeouts),
]


def main():
    n_ticks = 1000
    seed = 42

    log_dir = Path("helios_v2/logs/r_v3_m1/async_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_results = []
    t0 = time.time()
    for name, pattern in SCENARIOS:
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=n_ticks, reflect_pattern=pattern, seed=seed
        )
        d = stats.to_dict()
        d["scenario"] = name
        all_results.append(d)
        print(f"  {name}: solver_failures={d['n_solver_failures']}, "
              f"nan={d['n_nan']}, R_mean={d['R_mean']:.4f}, "
              f"state_abs_max={d['state_abs_max']:.4f}, "
              f"reflect_applied={d['n_reflect_applied']}, "
              f"timeouts={d['n_reflect_timeout']}")

    elapsed = time.time() - t0

    summary = {
        "n_ticks_per_scenario": n_ticks,
        "n_scenarios": len(SCENARIOS),
        "total_ticks": n_ticks * len(SCENARIOS),
        "elapsed_seconds": elapsed,
        "scenarios": all_results,
    }

    summary_path = log_dir / f"async_robustness_5x1000t_summary_{timestamp}.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n=== M1-T7 ship 异步鲁棒性 5 场景 × {n_ticks} tick 探针 ===")
    print(f"  total ticks:  {n_ticks * len(SCENARIOS)}")
    print(f"  elapsed:      {elapsed:.2f}s")
    print(f"  summary:      {summary_path}")

    # 全局断言
    failed = False
    for d in all_results:
        if d["n_solver_failures"] > 0:
            print(f"FAIL: {d['scenario']} has {d['n_solver_failures']} solver failures")
            failed = True
        if d["n_nan"] > 0:
            print(f"FAIL: {d['scenario']} has {d['n_nan']} NaN")
            failed = True
        if d["state_abs_max"] > 30.0:
            print(f"FAIL: {d['scenario']} state diverged: {d['state_abs_max']}")
            failed = True
        if not (0.0 <= d["R_min"] <= d["R_max"] <= 1.0):
            print(f"FAIL: {d['scenario']} R out of range: [{d['R_min']}, {d['R_max']}]")
            failed = True

    if failed:
        print("\nOVERALL: FAIL")
        return 1
    print("\nOVERALL: PASS — 5 场景全部稳定 (0 failure, 0 NaN, R ∈ [0, 1])")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())