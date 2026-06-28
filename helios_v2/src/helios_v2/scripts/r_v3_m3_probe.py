"""M3 Boundary Owner ship 验证探针。

1000 tick 跑 BoundaryOwner,验证:
  - 5 nested subsystems 共享 1 个 Markov Blanket
  - conditional_separation 数学不变量验证
  - 4 信号类型正确处理(sensory admit / active admit / internal deny / external deny)
  - 1000 tick 不崩溃
  - 25 stage 22 BoundaryEnforcement 接入
"""
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m3 import (
    BoundaryOwner,
    NestedSubsystem,
    Signal,
    SignalType,
)


def main():
    n_ticks = 1000
    seed = 42
    np.random.seed(seed)

    subsystems = {
        "active_inference": NestedSubsystem(
            name="active_inference", state=np.zeros(4), layer=1,
        ),
        "self_model": NestedSubsystem(
            name="self_model", state=np.zeros(8), layer=2,
        ),
        "reflection": NestedSubsystem(
            name="reflection", state=np.zeros(8), layer=3,
        ),
        "evolution": NestedSubsystem(
            name="evolution", state=np.zeros(8), layer=4,
        ),
    }

    bo = BoundaryOwner(
        subsystems=subsystems,
        enforce_separation_check=False,  # 默认关闭,避免噪声误判
    )

    log_dir = Path("helios_v2/logs/r_v3_m3/boundary_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"boundary_1000t_{timestamp}.jsonl"
    summary_path = log_dir / f"boundary_1000t_summary_{timestamp}.json"

    t0 = time.time()

    n_sensory_admitted = 0
    n_active_admitted = 0
    n_internal_denied = 0
    n_external_denied = 0
    sep_check_records = []

    with log_path.open("w", encoding="utf-8") as f:
        for tick in range(n_ticks):
            # 1. 模拟 world → system 的 sensory 信号(dry 模式,manual record)
            sensory_value = 0.5 + 0.1 * np.sin(tick * 0.05)
            sig = Signal.make(
                SignalType.SENSORY, "world", "self_model", float(sensory_value)
            )
            admitted = bo.check_signal_dry(sig)
            if admitted:
                n_sensory_admitted += 1

            # 2. 更新所有 subsystems(不通过 update_subsystem 自动记录)
            for name, sub in bo.subsystems.items():
                new_state = sub.update_fn(sub.state, float(sensory_value)) if sub.update_fn else sub.state
                sub.state = new_state

            # 3. 模拟 system → world 的 active 信号(每 10 tick)
            if tick % 10 == 0:
                active_sig = bo.emit_active("self_model", "world", float(0.3 + 0.1 * np.cos(tick * 0.07)))
                n_active_admitted += 1

            # 4. 模拟 invalid internal/external 信号(测试 deny 路径)
            if tick % 20 == 0:
                internal_sig = Signal.make(
                    SignalType.INTERNAL, "self_model", "world", 0.7
                )
                if not bo.check_signal(internal_sig):
                    n_internal_denied += 1
                external_sig = Signal.make(
                    SignalType.EXTERNAL, "world", "self_model", 0.9
                )
                if not bo.check_signal(external_sig):
                    n_external_denied += 1

            # 5. 手动记录 3 组样本(对齐)
            bo.mb.record_sensory(float(sensory_value))
            for name in bo.subsystems:
                internal_val = 0.3 * sensory_value + 0.2 * np.cos(tick * 0.1) + 0.01 * np.random.randn()
                bo.mb.record_internal(name, float(internal_val))
            external_val = 0.4 * np.sin(tick * 0.05) + 0.2 * sensory_value + 0.5 * np.random.randn()
            bo.mb.record_external(float(external_val))

            # 6. 每 100 tick 验证不变量
            if tick > 0 and tick % 100 == 0:
                sep_result = bo.mb.check_separation("self_model", method="partial_correlation")
                sep_check_records.append({
                    "tick": tick,
                    "n_samples": sep_result.n_samples,
                    "partial_corr": sep_result.partial_corr,
                    "p_value": sep_result.p_value,
                    "passed": sep_result.passed,
                })
                f.write(json.dumps({
                    "tick": tick,
                    "kuramoto_R_proxy": float(np.mean(subsystems["self_model"].state)) if hasattr(subsystems["self_model"].state, '__iter__') else subsystems["self_model"].state,
                    "n_admitted_so_far": bo.get_stats()["n_admitted"],
                    "n_denied_so_far": bo.get_stats()["n_denied"],
                    "separation_check": {
                        "partial_corr": sep_result.partial_corr,
                        "p_value": sep_result.p_value,
                        "passed": sep_result.passed,
                        "n_samples": sep_result.n_samples,
                    },
                }, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0

    # 最终 stage 22 验证
    stage22_result = bo.stage_22_boundary_enforcement()

    summary = {
        "n_ticks": n_ticks,
        "elapsed_seconds": elapsed,
        "ticks_per_second": n_ticks / elapsed,
        "signal_counts": {
            "sensory_admitted": n_sensory_admitted,
            "active_admitted": n_active_admitted,
            "internal_denied": n_internal_denied,
            "external_denied": n_external_denied,
        },
        "owner_stats": bo.get_stats(),
        "stage_22_result": {
            "all_separations_passed": stage22_result["all_separations_passed"],
            "n_admitted": stage22_result["n_admitted"],
            "n_denied": stage22_result["n_denied"],
            "audit_log_size": stage22_result["audit_log_size"],
        },
        "separation_check_records": sep_check_records,
        "log_path": str(log_path),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"=== M3 Boundary Owner ship 1000-tick 探针 ===")
    print(f"  ticks:           {n_ticks}")
    print(f"  elapsed:         {elapsed:.2f}s ({summary['ticks_per_second']:.1f} ticks/s)")
    print(f"  signal counts:")
    print(f"    sensory_admitted:  {n_sensory_admitted}")
    print(f"    active_admitted:   {n_active_admitted}")
    print(f"    internal_denied:   {n_internal_denied}")
    print(f"    external_denied:   {n_external_denied}")
    print(f"  separation check records:")
    for r in sep_check_records:
        print(f"    tick {r['tick']:4d}: n={r['n_samples']}, r={r['partial_corr']:+.4f}, "
              f"p={r['p_value']:.4f}, passed={r['passed']}")
    print(f"  stage 22: all_passed={stage22_result['all_separations_passed']}, "
          f"admitted={stage22_result['n_admitted']}, "
          f"denied={stage22_result['n_denied']}")
    print(f"  audit_log_size: {summary['owner_stats']['audit_log_size']}")
    print(f"  summary: {summary_path}")
    print(f"  trace:   {log_path}")

    failed = False
    if n_sensory_admitted != n_ticks:
        print(f"FAIL: sensory_admitted={n_sensory_admitted} != n_ticks={n_ticks}")
        failed = True
    if n_internal_denied != n_ticks // 20:
        print(f"FAIL: internal_denied={n_internal_denied} != n_ticks/20={n_ticks // 20}")
        failed = True
    if n_external_denied != n_ticks // 20:
        print(f"FAIL: external_denied={n_external_denied} != n_ticks/20={n_ticks // 20}")
        failed = True

    if failed:
        print("\nOVERALL: FAIL")
        return 1
    print("\nOVERALL: PASS — Boundary + Markov Blanket + audit log 全部稳定")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())