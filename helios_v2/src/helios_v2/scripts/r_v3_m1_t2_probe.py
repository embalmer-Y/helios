"""M1-T2 实证:8 维 CDS + Radau stiff solver 1000-tick production trace。

执行:
    python -m helios_v2.scripts.r_v3_m1_t2_probe --ticks 1000

输出:
    helios_v2/logs/r_v3_m1/cds_traces/cds_1000t_{timestamp}.jsonl

trace 字段(每 tick):
    tick_id: int
    state: list[float] (8 dim)
    kuramoto_R: float
    rochat_level_continuous: float
    rochat_level_discrete: int (0-5)
    self_unity: float
    agency_strength: float (PTS 2)
    solver_success: bool
    C_max_abs: float
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m1.cds import (
    CoupledDynamicalSystem,
    DEFAULT_ALPHA,
)


def run_probe(ticks: int = 1000):
    """1000 tick CDS 演化 + 落盘 trace。"""
    cds = CoupledDynamicalSystem()

    output_dir = Path("helios_v2/logs/r_v3_m1/cds_traces")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"cds_{ticks}t_{timestamp}.jsonl"

    print(f"\n=== M1-T2 CDS Probe: {ticks} ticks ===")
    print(f"Output: {output_path}")

    R_history = []
    solver_failures = 0
    nan_count = 0

    with output_path.open("w", encoding="utf-8") as f:
        for tick_id in range(ticks):
            # 动态输入:sin wave 8 维 + 随机扰动
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick_id * 0.01)
            reflect = 0.05 * np.cos(np.linspace(0, np.pi, 8) + tick_id * 0.02)

            # 偶数 tick 提供小 reward(模拟 P5-A RealRPE)
            reward = 0.1 * float(np.sin(tick_id * 0.05)) if tick_id % 10 == 0 else None

            result = cds.tick(I=I, reflect=reflect, reward=reward)
            exp = cds.self_experience()

            if not result["solver_success"]:
                solver_failures += 1
            if any(np.isnan(cds.state)):
                nan_count += 1

            R_history.append(exp["global_coherence_R"])

            trace_record = {
                "tick_id": tick_id,
                "state": cds.state.tolist(),
                "kuramoto_R": exp["global_coherence_R"],
                "rochat_level_continuous": exp["rochat_level_continuous"],
                "rochat_level_discrete": exp["rochat_level_discrete"],
                "self_unity": exp["self_unity"],
                "agency_strength": exp["agency_strength"],
                "solver_success": result["solver_success"],
                "C_max_abs": float(np.max(np.abs(cds.C))),
            }
            f.write(json.dumps(trace_record) + "\n")

    R_history = np.array(R_history)

    print(f"\n=== Summary ===")
    print(f"Total ticks: {ticks}")
    print(f"Solver failures: {solver_failures} ({100 * solver_failures / ticks:.2f}%)")
    print(f"NaN count: {nan_count}")
    print(f"State max abs: {float(np.max(np.abs(cds.state))):.4f}")
    print(f"Kuramoto R: min={R_history.min():.4f}, max={R_history.max():.4f}, mean={R_history.mean():.4f}")
    print(f"C matrix: max_abs={float(np.max(np.abs(cds.C))):.4f}")
    print(f"Final state: {[f'{s:.4f}' for s in cds.state]}")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=1000)
    args = parser.parse_args()
    run_probe(ticks=args.ticks)
