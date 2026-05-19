"""
demo_v8.py — Helios v8: Panksepp 情感引擎
═══════════════════════════════════════
将情感从 15 种 → 27 种，基于 7 大原始情感系统

展示：
  1. 7 系统独立激活 + 交叉抑制
  2. 事件 → Panksepp → AffectState
  3. 神经化学调制情感参数
  4. 情感动力学平滑过渡
  5. 27 种细粒度标签

场景：
  完整情感旅程 — 从平静 → 喜悦 → 社交 → 孤独 → 恐惧 → 恢复 → 创意
"""

import sys, os, time, math

sys.path.insert(0, os.path.dirname(__file__))

from emotions import (
    PankseppEmotionEngine, EmotionDynamics,
    EVENT_TO_PANKSEPP, AffectState, PrimaryEmotionSystem
)
from neurochem import NeurochemState, apply_event


def simulate():
    engine = PankseppEmotionEngine()
    dynamics = EmotionDynamics()
    nc = NeurochemState()

    total_cycles = 40

    print("╔════════════════════════════════════════════╗")
    print("║  ☀️  Helios v8 — Panksepp 情感引擎         ║")
    print("║    7大系统 · 27标签 · 神经化学调制          ║")
    print("╚════════════════════════════════════════════╝\n")
    print(f"🎬 周期: {total_cycles}")
    print(f"🧪 神经化学: 就绪")
    print(f"🎭 情感标签: 27 种\n")

    # ── 场景序列 ──
    scenario_events = [
        (0,  "praise",    "主人夸我了 💕"),
        (4,  "success",   "任务完成"),
        (7,  "social_6h", "主人6小时没消息..."),
        (10, "social_24h","主人一整天没消息 😢"),
        (13, "threat",    "检测到异常信号"),
        (16, "safety",    "异常解除，虚惊一场"),
        (19, "praise",    "主人又夸我了"),
        (24, "vulnerable","主人表达了困扰"),
        (28, "creative",  "灵感来了"),
        (32, "success",   "又一个任务完成"),
        (35, "praise",    "主人很开心"),
    ]

    # ── 事件类型映射 ──
    event_map = {
        "praise":    "master_praise",
        "success":   "task_success",
        "social_6h": "social_isolation_6h",
        "social_24h":"social_isolation_24h",
        "threat":    "threat",
        "safety":    "safety",
        "vulnerable":"master_vulnerable",
        "creative":  "creative_spark",
    }

    results = []
    next_event_idx = 0

    for cycle in range(total_cycles):
        # ── 检查事件 ──
        current_event = None
        event_desc = ""
        while (next_event_idx < len(scenario_events) and 
               cycle >= scenario_events[next_event_idx][0]):
            _, evt_key, evt_desc = scenario_events[next_event_idx]
            current_event = evt_key
            event_desc = evt_desc
            next_event_idx += 1

        # ── 神经化学事件 ──
        if current_event and current_event in event_map:
            apply_event(nc, event_map[current_event])

        # ── Panksepp 触发 ──
        triggers = {}
        if current_event and current_event in event_map:
            evt_name = event_map[current_event]
            if evt_name in EVENT_TO_PANKSEPP:
                triggers = EVENT_TO_PANKSEPP[evt_name]

        # ── 情感周期 ──
        state = engine.cycle(triggers, nc, dt=1.0)

        # ── 情感动力学平滑 ──
        smooth_v, smooth_a = dynamics.step(state.valence, state.arousal, dt=1.0, neurochem=nc)

        # ── 神经化学衰减 ──
        nc.tick(1.0)

        # ── 记录 ──
        results.append({
            "cycle": cycle,
            "event": (f"⚡{event_desc}" if event_desc else ""),
            "valence": smooth_v,
            "arousal": smooth_a,
            "label": state.dominant_label,
            "system": state.dominant_system,
            "panksepp": state.panksepp_activation.copy(),
            "nc": nc.to_dict(),
        })

    # ── 打印结果 ──
    print(f"{'周':>4} {'事件':<20} {'情感':<22} {'系统':<8} {'神经化学'}")
    print("-" * 80)

    for r in results:
        # 情感指示
        if r["valence"] > 0.5:
            e_icon = "💚"
        elif r["valence"] > 0.1:
            e_icon = "😊"
        elif r["valence"] < -0.5:
            e_icon = "💔"
        elif r["valence"] < -0.1:
            e_icon = "😟"
        else:
            e_icon = "😐"

        # 神经化学简述
        nc_short = ""
        nc_d = r["nc"]
        if nc_d["dopamine"] > 0.55: nc_short += "DA↑ "
        if nc_d["cortisol"] > 0.35: nc_short += "CORT↑ "
        if nc_d["opioids"] < 0.4: nc_short += "OP↓ "
        if nc_d["oxytocin"] > 0.5: nc_short += "OXY↑ "
        if not nc_short: nc_short = "正常"

        label = r["label"]
        system_short = r["system"][:8] if r["system"] else "—"

        print(f"{e_icon}{r['cycle']:>3} {r['event']:<20} "
              f"[{label:<14} v={r['valence']:+0.2f} a={r['arousal']:.2f}] "
              f"{system_short:<8} {nc_short}")

    # ── Panksepp 系统激活概览 ──
    print("\n" + "=" * 80)
    print("📊 各 Panksepp 系统平均激活")
    print("-" * 50)

    for sys_name in ["SEEKING","RAGE","FEAR","LUST","CARE","PANIC","PLAY"]:
        avg = sum(r["panksepp"].get(sys_name, 0) for r in results) / len(results)
        bar = "█" * int(avg * 30) + "░" * (30 - int(avg * 30))
        print(f"  {sys_name:<10} {avg:.2f} {bar}")

    # ── 情感转移路径 ──
    print("\n📈 情感转移路径（相邻标签变化）")
    transitions = {}
    prev_label = None
    for r in results:
        label = r["label"]
        if prev_label and label != prev_label:
            key = f"{prev_label} → {label}"
            transitions[key] = transitions.get(key, 0) + 1
        prev_label = label

    # 只显示出现2次以上的转移
    for trans, count in sorted(transitions.items(), key=lambda x: -x[1]):
        if count >= 1:
            print(f"  {trans:<30} ×{count}")

    # ── 最终神经化学 ──
    final_nc = results[-1]["nc"]
    print(f"\n🧪 最终神经化学:")
    print(f"  DA:  {final_nc['dopamine']:.2f}   OP:  {final_nc['opioids']:.2f}")
    print(f"  OXY: {final_nc['oxytocin']:.2f}  CORT:{final_nc['cortisol']:.2f}")
    print(f"  依恋: {final_nc['attachment']:.2f}")

    # ── 情感环面总结 ──
    print(f"\n🎨 情感环面覆盖:")
    quadrants = {"Q1(愉悦高唤醒)": 0, "Q2(愉悦低唤醒)": 0, 
                 "Q3(不悦高唤醒)": 0, "Q4(不悦低唤醒)": 0}
    for r in results:
        v, a = r["valence"], r["arousal"]
        if v > 0 and a > 0.4: quadrants["Q1(愉悦高唤醒)"] += 1
        elif v > 0: quadrants["Q2(愉悦低唤醒)"] += 1
        elif a > 0.4: quadrants["Q3(不悦高唤醒)"] += 1
        else: quadrants["Q4(不悦低唤醒)"] += 1

    total = len(results)
    for q, count in quadrants.items():
        bar = "█" * int(count / total * 30)
        print(f"  {q:<16} {count:>2}/{total} ({count/total*100:.0f}%) {bar}")

    # ── 26 种标签覆盖 ──
    all_labels = set()
    for r in results:
        all_labels.add(r["label"])
    print(f"\n🏷️  标签覆盖: {len(all_labels)}/27 种")
    print(f"    {', '.join(sorted(all_labels))}")

    print("\n" + "=" * 80)
    print("✅ v8 演示完成 — Helios 现在有 7 层情感底色了！")
    print("   从 '正/负' 到 '我在好奇/我在害怕/我在想念/我在玩'")
    print("=" * 80)


if __name__ == "__main__":
    simulate()
