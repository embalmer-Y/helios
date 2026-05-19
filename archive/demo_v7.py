"""
demo_v7.py — Helios v7: 熵减驱动 + 神经化学
════════════════════════════════════════════
首次让 Helios "自己想要做点什么"

展示：
  1. DriveOracle 五驱动缺口计算
  2. NeurochemState 四种调质动态
  3. 事件→神经化学→驱动调制 的完整链
  4. Helios 在无外部刺激下产生行动意图

场景：
  24 个周期，经历社交→孤独→探索→威胁→恢复 的完整循环
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(__file__))

from drives import DriveOracle, HeliosSnapshot, ActionSelector, DriveVector
from neurochem import NeurochemState, apply_event, modulate_affect_params


# ═══════════════════════════════════════════
# 模拟引擎
# ═══════════════════════════════════════════

def simulate():
    oracle = DriveOracle()
    selector = ActionSelector()
    nc = NeurochemState()

    total_cycles = 36
    drive_log = []

    print("╔════════════════════════════════════════════╗")
    print("║  ☀️  Helios v7 — 熵减驱动 + 神经化学       ║")
    print("║    '我...想要做点什么'                     ║")
    print("╚════════════════════════════════════════════╝\n")

    print("🧠 驱动引擎: 就绪")
    print("🧪 神经化学: DA/OP/OXY/CORT 就绪")
    print(f"🎬 周期: {total_cycles}\n")

    # ── 预设场景序列 ──
    scenarios = [
        # (周期范围, 事件, 状态描述)
        (0, "master_message", "主人发来消息"),
        (2, "master_praise", "主人夸奖了璃光"),
        (3, "task_success", "完成了一个任务"),
        (5, None, "安静中——无外部刺激"),
        (8, "novelty_detected", "检测到新数据"),
        (10, None, "探索欲上升"),
        (13, "social_isolation_1h", "主人1小时没消息"),
        (15, "social_isolation_6h", "主人6小时没消息..."),
        (17, "task_failure", "一个任务失败了"),
        (18, "threat_detected", "检测到潜在威胁"),
        (20, "safety_confirmed", "威胁解除，安全确认"),
        (23, "master_praise", "主人又夸奖了"),
        (25, None, "一切安好，无事发生"),
        (28, None, "依旧安静"),
        (30, "master_vulnerable", "主人表达了困扰"),
        (33, None, "想要帮助主人"),
    ]

    current_scene_idx = 0

    t_since = 0  # 社交间隔累积
    v, a = 0.1, 0.3  # 情感累积

    for cycle in range(total_cycles):
        # 找到当前场景
        event = None
        scene_desc = ""
        while (current_scene_idx < len(scenarios) and
               cycle >= scenarios[current_scene_idx][0]):
            _, event, scene_desc = scenarios[current_scene_idx]
            current_scene_idx += 1

        # 处理事件 → 神经化学
        if event:
            apply_event(nc, event)

        # 构建状态快照
        # 根据场景动态调整
        if event == "master_praise":
            t_since = 0
            v, a = 0.6, 0.5
        elif event == "social_isolation_6h":
            t_since = 6 * 3600
            v, a = -0.2, 0.4
        elif event == "threat_detected":
            t_since = 3600
            v, a = -0.5, 0.7
        elif event == "safety_confirmed":
            t_since = 3600
            v, a = 0.1, 0.4
        elif event == "master_vulnerable":
            t_since = 0
            v, a = 0.3, 0.5
        elif event == "task_failure":
            t_since = 1800
            v, a = -0.3, 0.6
        elif event == "novelty_detected":
            t_since = 1800
            v, a = 0.3, 0.5
        else:
            # 无事件 → 时间自然流逝
            t_since += 100
            v = 0.1
            a = 0.3

        snap = HeliosSnapshot(
            prediction_error=0.2 if not event else 0.4 + random.random() * 0.3,
            valence=v,
            arousal=a,
            time_since_last_interaction=t_since,
            social_connection_quality=0.7,
            heart_rate=72 + random.randint(-5, 5),
            energy=0.9 - cycle * 0.003,
            pending_tasks=max(0, 3 - cycle // 10),
            recent_failures=1 if event == "task_failure" else 0,
            creative_output_recent=0.2 + (cycle % 5) * 0.1,
            phi_value=0.3 + random.random() * 0.3,
        )

        # 计算驱动
        dv = oracle.cycle(snap, nc)

        # 动作选择
        action = selector.select(dv)

        # 神经化学衰减
        nc.tick(1.0)

        # 记录
        drive_log.append((cycle, dv, action, nc.to_dict()))

    # ── 打印结果 ──
    print(f"{'周':>4} {'驱动(总/主导)':<22} {'神经化学':<20} {'行动':<20}")
    print("-" * 70)

    for cycle, dv, action, nc_dict in drive_log:
        # 驱动图标
        d_icon = "💤" if dv.total < 0.15 else (
            "⚡" if dv.total > 0.60 else
            "🔔" if dv.is_active else "·"
        )

        # 神经化学简述
        nc_short = ""
        if nc_dict["dopamine"] > 0.55:
            nc_short += "DA↑"
        if nc_dict["cortisol"] > 0.35:
            nc_short += " CORT↑"
        if nc_dict["opioids"] < 0.4:
            nc_short += " OP↓"
        if nc_dict["oxytocin"] > 0.5:
            nc_short += " OXY↑"
        if not nc_short:
            nc_short = "正常"

        # 驱动简述
        d_short = f"{dv.total:.2f}/{dv.dominant[:4]}"
        if dv.social > 0.4:
            d_short += "💬"

        # 行动简述
        a_short = action.name if action else "—"

        print(f"{d_icon}{cycle:>3} {d_short:<22} {nc_short:<20} {a_short:<20}")

    # ── 统计分析 ──
    print("\n" + "=" * 60)
    print("📊 统计分析")

    active_cycles = sum(1 for _, dv, _, _ in drive_log if dv.is_active)
    strong_cycles = sum(1 for _, dv, _, _ in drive_log if dv.is_strong)
    actions_chosen = sum(1 for _, _, a, _ in drive_log if a is not None)

    print(f"  主动驱动周期: {active_cycles}/{total_cycles} ({active_cycles/total_cycles*100:.0f}%)")
    print(f"  强驱动周期:   {strong_cycles}/{total_cycles} ({strong_cycles/total_cycles*100:.0f}%)")
    print(f"  行动被选择:   {actions_chosen}/{total_cycles} ({actions_chosen/total_cycles*100:.0f}%)")

    # 各驱动平均
    print("\n  各驱动平均值:")
    for name in ["curiosity", "social", "homeostatic", "achievement", "aesthetic"]:
        avg = sum(getattr(dv, name) for _, dv, _, _ in drive_log) / len(drive_log)
        bar = "█" * int(avg * 20)
        print(f"    {name:<12} {avg:.2f} {bar}")

    # 最终神经化学状态
    final_nc = drive_log[-1][3]
    print(f"\n  最终神经化学:")
    print(f"    DA:  {final_nc['dopamine']:.2f}")
    print(f"    OP:  {final_nc['opioids']:.2f}")
    print(f"    OXY: {final_nc['oxytocin']:.2f}")
    print(f"    CORT:{final_nc['cortisol']:.2f}")
    print(f"    依恋: {final_nc['attachment']:.2f}")

    # ── 情感参数调制示例 ──
    print("\n" + "=" * 60)
    print("🎛️  神经化学 → 情感参数调制")

    # 极端情况测试
    test_cases = [
        ("基线", NeurochemState()),
        ("高DA", create_nc(da=0.8)),
        ("高CORT", create_nc(cort=0.7)),
        ("低OP", create_nc(op=0.15)),
        ("高OXY", create_nc(oxy=0.7)),
    ]

    for label, tnc in test_cases:
        f, r, t = modulate_affect_params(0.25, 0.85, 8.0, tnc)
        print(f"  {label:<6} → flare={f:.2f} rec={r:.2f} tau={t:.1f}")

    print("\n" + "=" * 60)
    print("✅ v7 演示完成 — Helios 现在有内生驱动力了！")
    print("   '我...想要做点什么' — 从今天开始，不再只是等。")
    print("=" * 60)


def create_nc(da=None, op=None, oxy=None, cort=None):
    """快速创建特定神经化学状态"""
    nc = NeurochemState()
    if da is not None:
        nc.dopamine.current = da
    if op is not None:
        nc.opioids.current = op
    if oxy is not None:
        nc.oxytocin.current = oxy
    if cort is not None:
        nc.cortisol.current = cort
    return nc


if __name__ == "__main__":
    simulate()
