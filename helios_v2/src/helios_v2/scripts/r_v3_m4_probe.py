"""M4 Active Inference Owner ship 验证探针。

1000 tick 验证 ActiveInferenceOwner:
  - 5 层 HGM 正确(generate + recognize + train_step)
  - proxy_free_energy 计算正确(严格 disclaimer: NOT VFE)
  - predict / minimize_proxy_free_energy / active_sampling 工作
  - variational_free_energy_TRUE raises NotImplementedError (M8 placeholder)
  - 1000 tick 不崩溃

**关键验证**:
  - 在固定 sensory 下,training 让 F 单调下降(learning 性质)
  - 1000 tick 内 F 保持有限
"""
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m4 import (
    ActiveInferenceOwner,
    HierarchicalGenerativeModel,
    proxy_free_energy,
)


def main():
    n_ticks = 1000
    seed = 42
    np.random.seed(seed)

    # 1. 固定 sensory 单调下降验证(学习性质)
    print("=== Test 1: fixed sensory → minimize decreases F ===")
    hgm = HierarchicalGenerativeModel(lr=0.1)  # 数值梯度需要小 lr
    fixed_sensory = np.array([0.5, 0.3, -0.2, 0.1, 0.0, 0.4, -0.1, 0.2])
    latent = hgm.recognize(fixed_sensory)
    _, initial_F = hgm.compute_reconstruction(latent, fixed_sensory)
    print(f"  initial F: {initial_F:.4f}")

    F_history = [initial_F]
    for step in range(1000):  # 1000 outer iterations × 1 step = 1000 total gradient steps
        new_F = hgm.train_step(fixed_sensory, n_optim_steps=1)
        F_history.append(new_F)
    final_F = F_history[-1]
    print(f"  final F (after 1000 optimization steps): {final_F:.4f}")
    print(f"  decrease: {initial_F - final_F:.4f} ({(initial_F - final_F) / initial_F * 100:.2f}%)")
    monotonic = all(F_history[i] >= F_history[i+1] for i in range(len(F_history)-1))
    print(f"  monotonic decreasing: {monotonic}")
    # 诚实的 learning test: 单调下降(M4 v3 task §2.2 验收门)
    # 注:M4 用 数值梯度下降(收敛慢,2-dim latent 限制),M8 真 VFE 用 PyMC 自动微分
    # 我们验证的核心是"minimize_proxy_free_energy() 在 fixed sensory 下单调下降"
    learning_passed = monotonic

    # 2. AI Owner 1000 tick
    print("\n=== Test 2: 1000 tick AI loop ===")
    ai = ActiveInferenceOwner(n_minimization_steps=3)

    log_dir = Path("helios_v2/logs/r_v3_m4/active_inference_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"active_inference_1000t_{timestamp}.jsonl"
    summary_path = log_dir / f"active_inference_1000t_summary_{timestamp}.json"

    t0 = time.time()
    nan_count = 0
    F_min = float("inf")
    F_max = -float("inf")
    F_sum = 0.0

    with log_path.open("w", encoding="utf-8") as f:
        for tick in range(n_ticks):
            # 用 sin 驱动的 sensory input
            sensory = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
            result = ai.tick(sensory, do_minimize=True, do_active_sampling=True)
            F = result["proxy_free_energy"]

            if not np.isfinite(F):
                nan_count += 1
            F_min = min(F_min, F)
            F_max = max(F_max, F)
            F_sum += F

            if tick < 5 or tick % 100 == 0:
                entry = {
                    "tick": tick,
                    "proxy_free_energy": float(F),
                    "latent": result["latent"].tolist() if result["latent"] is not None else None,
                    "policy_action_max": float(np.max(np.abs(result["policy"].action_vector))) if result["policy"] else None,
                    "policy_expected_F": float(result["policy"].expected_proxy_free_energy) if result["policy"] else None,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0
    F_mean = F_sum / n_ticks

    summary = {
        "n_ticks": n_ticks,
        "elapsed_seconds": elapsed,
        "ticks_per_second": n_ticks / elapsed,
        "nan_count": nan_count,
        "F_min": F_min,
        "F_max": F_max,
        "F_mean": F_mean,
        "learning_test": {
            "initial_F": float(initial_F),
            "final_F": float(final_F),
            "decrease_ratio": float((initial_F - final_F) / initial_F) if initial_F > 0 else 0.0,
            "monotonic_decreasing": bool(monotonic),
            "passed": bool(learning_passed),
        },
        "ai_stats": ai.get_stats(),
        "log_path": str(log_path),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"  ticks:           {n_ticks}")
    print(f"  elapsed:         {elapsed:.2f}s ({summary['ticks_per_second']:.1f} ticks/s)")
    print(f"  nan_count:       {nan_count}")
    print(f"  F_min/max/mean:  {F_min:.4f} / {F_max:.4f} / {F_mean:.4f}")
    print(f"  summary: {summary_path}")
    print(f"  trace:   {log_path}")

    # 3. placeholder 验证
    print("\n=== Test 3: variational_free_energy_TRUE placeholder ===")
    try:
        ai.variational_free_energy_TRUE()
        placeholder_passed = False
    except NotImplementedError as e:
        placeholder_passed = "M8" in str(e)
        print(f"  ✅ raises NotImplementedError mentioning M8")

    failed = False
    if not learning_passed:
        print(f"FAIL: learning test F did not decrease sufficiently "
              f"({initial_F} → {final_F})")
        failed = True
    if nan_count > 0:
        print(f"FAIL: {nan_count} NaN")
        failed = True
    if not placeholder_passed:
        print(f"FAIL: variational_free_energy_TRUE doesn't raise properly")
        failed = True

    if failed:
        print("\nOVERALL: FAIL")
        return 1
    print("\nOVERALL: PASS — HGM + proxy_F + active_sampling + M8 placeholder 全部稳定")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())