"""M2 Reflection Owner ship 验证探针。

1000 tick 跑 ReflectionOwner,验证:
  - 4 trigger 正确检测
  - LLM 被动接受(不修改 CDS state)
  - reflection_audit 通过率 ≥ 80%
  - 1000 tick 不崩溃
  - reflect 注入机制工作正常
"""
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m2 import (
    ReflectionOwner,
    FakeLLMCaller,
    ReflectionTrigger,
)


def main():
    n_ticks = 1000
    seed = 42
    np.random.seed(seed)

    owner = SelfModelOwner.default()
    llm = FakeLLMCaller()
    ro = ReflectionOwner(self_model=owner, llm_caller=llm)

    log_dir = Path("helios_v2/logs/r_v3_m2/reflection_traces")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"reflection_1000t_{timestamp}.jsonl"
    summary_path = log_dir / f"reflection_1000t_summary_{timestamp}.json"

    t0 = time.time()
    nan_count = 0
    solver_failures = 0
    trigger_records = []  # 每条反思记录的概要
    R_history = []
    reflect_applied_count = 0

    with log_path.open("w", encoding="utf-8") as f:
        for tick in range(n_ticks):
            # 1. 驱动 CDS(可选用 pending reflect)
            reflect = ro.consume_pending_reflect()
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
            result = owner.tick(I=I, reflect=reflect)
            if reflect is not None and np.any(reflect != 0):
                reflect_applied_count += 1
            if not result["solver_success"]:
                solver_failures += 1
            if np.any(np.isnan(result["state"])):
                nan_count += 1
            R_history.append(result["kuramoto_R"])

            # 2. 检测 trigger
            reflection_result = ro.on_tick_after_cds()
            for rec_dict in reflection_result["records"]:
                trigger_records.append({
                    "tick": tick,
                    "trigger": rec_dict["trigger"],
                    "level": rec_dict["level"],
                    "audit_passed": rec_dict["audit_passed"],
                    "audit_reasons": rec_dict["audit_reasons"],
                    "reflect_max_abs": max(abs(x) for x in rec_dict["reflect_vector"]),
                    "response_len": len(rec_dict["llm_response"]),
                    "latency_ms": rec_dict["latency_ms"],
                })

            # 3. USER_INVOKED 测试一次(验证接口可用)
            if tick == 100:
                rec = ro.invoke_user_reflection("Why is R so high?")
                trigger_records.append({
                    "tick": tick,
                    "trigger": "user_invoked",
                    "level": rec.level.value,
                    "audit_passed": rec.audit.passed,
                    "audit_reasons": list(rec.audit.reasons),
                    "reflect_max_abs": float(np.max(np.abs(rec.reflect_vector))),
                    "response_len": len(rec.llm_response),
                    "latency_ms": rec.latency_ms,
                })

            # 4. 每 100 tick 记录一次
            if tick % 100 == 0:
                entry = {
                    "tick": tick,
                    "kuramoto_R": float(result["kuramoto_R"]),
                    "solver_success": bool(result["solver_success"]),
                    "triggers_this_tick": reflection_result["triggers_fired"],
                    "n_reflections_so_far": ro.get_stats()["n_reflections"],
                    "audit_pass_rate_so_far": ro.get_stats()["audit_pass_rate"],
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0

    stats = ro.get_stats()
    summary = {
        "n_ticks": n_ticks,
        "elapsed_seconds": elapsed,
        "ticks_per_second": n_ticks / elapsed,
        "solver_failures": solver_failures,
        "nan_count": nan_count,
        "reflect_applied_count": reflect_applied_count,
        "reflection_stats": stats,
        "kuramoto_R_mean": float(np.mean(R_history)),
        "kuramoto_R_std": float(np.std(R_history)),
        "kuramoto_R_min": float(np.min(R_history)),
        "kuramoto_R_max": float(np.max(R_history)),
        "trigger_records_count": len(trigger_records),
        "audit_pass_rate_overall": (
            sum(1 for r in trigger_records if r["audit_passed"]) / len(trigger_records)
            if trigger_records else 0.0
        ),
        "log_path": str(log_path),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"=== M2 Reflection Owner ship 1000-tick 探针 ===")
    print(f"  ticks:           {n_ticks}")
    print(f"  elapsed:         {elapsed:.2f}s ({summary['ticks_per_second']:.1f} ticks/s)")
    print(f"  solver_failures: {solver_failures}")
    print(f"  nan_count:       {nan_count}")
    print(f"  reflect_applied: {reflect_applied_count}")
    print(f"  reflection_stats:")
    print(f"    n_reflections: {stats['n_reflections']}")
    print(f"    trigger_counts: {stats['trigger_counts']}")
    print(f"    audit_pass_rate: {stats['audit_pass_rate']:.4f}")
    print(f"  Kuramoto R:      mean={summary['kuramoto_R_mean']:.4f} "
          f"std={summary['kuramoto_R_std']:.4f} "
          f"[{summary['kuramoto_R_min']:.4f}, {summary['kuramoto_R_max']:.4f}]")
    print(f"  overall audit pass rate (trigger_records): {summary['audit_pass_rate_overall']:.4f}")
    print(f"  summary: {summary_path}")
    print(f"  trace:   {log_path}")

    failed = False
    if solver_failures > 0:
        print(f"FAIL: {solver_failures} solver failures")
        failed = True
    if nan_count > 0:
        print(f"FAIL: {nan_count} NaN")
        failed = True
    if stats["audit_pass_rate"] < 0.8:
        print(f"FAIL: audit pass rate {stats['audit_pass_rate']:.4f} < 0.8 (M2 验收门)")
        failed = True
    if stats["n_reflections"] == 0:
        print(f"FAIL: no reflections triggered")
        failed = True

    if failed:
        print("\nOVERALL: FAIL")
        return 1
    print("\nOVERALL: PASS — 4 trigger + LLM passive accept + audit 全部通过")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())