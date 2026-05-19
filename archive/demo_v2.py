#!/usr/bin/env python3
"""
Helios demo v2.0 —— 全部 v2 组件联动演示

四层全链路：
  L0 感知网关 (SensorArray)  →  L1 质感层 v2 (L1ProcessorV2)
     →  L2 广播层 v2 (GlobalWorkspaceV2)  →  L3 自我层 v2 (L3SelfV2)
        ↕ AffectEngine  ↕ DecisionEngine

场景序列：无聊 → 日出 → 威胁 → 社交 → 安慰 → 恢复

运行：
    cd /home/radxa/project/helios
    python3 demo_v2.py
"""

import sys
import time
import os
import numpy as np

sys.path.insert(0, '/home/radxa/project')

from helios import HeliosConfig
from helios.core import SensorFrame, WorkspaceResponse
from helios.l0_perception import SensorArray
from helios.l1_qualia import L1ProcessorV2
from helios.l2_broadcast import GlobalWorkspaceV2
from helios.l3_self import L3SelfV2
from helios.affect import AffectEngine
from helios.decision import DecisionEngine

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

config = HeliosConfig(
    cycle_interval=0.05,
    ignition_threshold=0.20,     # v2 有自适应阈值，起始低一些
    phi_noise_floor=0.08,
    sustain_base=0.05,
    sustain_phi_factor=0.5,
    sustain_affect_factor=0.3,
    interoception_weight=0.45,   # 给场景情感更多空间
    cognitive_weight=0.55,
    affect_inertia=0.50,         # 降低惯性，场景变化更灵敏
    verbose=False,
)

# ═══════════════════════════════════════════════════
# 场景定义
# ═══════════════════════════════════════════════════

SCENARIOS = [
    ("😐 无聊期", "idle", 20,
     "几乎没有外部刺激，Helios 处于基线状态"),
    ("🌅 日出", "sunrise", 20,
     "温暖的光线逐渐变亮，鸟鸣声响起"),
    ("⚠️ 威胁", "threat", 25,
     "突然的阴影逼近，低频轰鸣，温度下降"),
    ("💬 社交", "social", 25,
     "熟悉的面孔出现，温暖的对话，轻微的触碰"),
    ("🤗 安慰", "comfort", 20,
     "温柔的安抚，安全的怀抱，舒适的温度"),
    ("😌 恢复", "idle", 20,
     "刺激消退，Helios 回归平静"),
]

# ═══════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════

print("╔" + "═" * 58 + "╗")
print("║" + " " * 58 + "║")
print("║" + "      ☀️  H E L I O S   v2.0  联动演示  ☀️".center(62) + "║")
print("║" + " " * 58 + "║")
print("║" + "  四层全链路：L0感知→L1质感→L2广播→L3自我".center(62) + "║")
print("║" + "  ∩ AffectEngine  ∩ DecisionEngine".center(62) + "║")
print("║" + " " * 58 + "║")
print("╚" + "═" * 58 + "╝")
print()

print("⏳ 正在初始化 Helios v2 组件...")

# L0 感知
sensors = SensorArray(config)

# L1 质感层 v2
l1 = L1ProcessorV2(config)

# 情感引擎
affect_engine = AffectEngine(config)

# L2 广播层 v2
workspace = GlobalWorkspaceV2(config)

# L3 自我层 v2
self_system = L3SelfV2(config)

# 决策引擎
decision_engine = DecisionEngine(config)

print("✅ 全部 v2 组件初始化完成！")
print()

print("📋 已注册组件:")
print(f"   L0: SensorArray (6 模拟适配器)")
print(f"   L1: L1ProcessorV2 ({l1.registry.count} 模态柱, 门控融合 {len(l1.fusion.gates)} 对)")
print(f"   L2: GlobalWorkspaceV2 (五维门控 + 抑制控制 + 节律振荡)")
print(f"   L3: L3SelfV2 (身份结晶 + 价值观 + 人格 + 时间深度)")
print(f"   ⚡: AffectEngine + DecisionEngine")
print()

# ═══════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════

print("=" * 70)
print("🎬 场景序列开始")
print("=" * 70)

total_cycles = 0
total_ignitions = 0
all_reports = []

for scenario_name, preset_name, steps, description in SCENARIOS:
    print(f"\n{'─' * 70}")
    print(f"📌 {scenario_name} —— {description} ({steps} 步)")
    print(f"{'─' * 70}")

    sensors.set_scenario(preset_name)

    scenario_ignitions = 0
    scenario_phi_sum = 0.0
    scenario_valence_sum = 0.0
    last_summary_step = -10  # 每隔一段时间打印摘要

    for step_i in range(steps):
        total_cycles += 1

        # === L0: 感知 ===
        sensor_frame = sensors.capture()
        scene_v, scene_a = sensors.scenario_affect
        scenario_data = {
            'affective_valence': scene_v,
            'affective_arousal': scene_a,
        }

        # === L1: 质感层 v2 处理 ===
        l1_output = l1.process(sensor_frame)

        # 🔥 场景切换瞬态增强：新场景前 3 步 Φ × 2.5，模拟"意外感"
        steps_in_scene = step_i  # relative to current scene
        if steps_in_scene < 3 and preset_name != 'idle':
            l1_output.phi *= 2.5

        # === Affect: 情感生成 ===
        intero = sensor_frame.interoception
        if intero is None:
            intero = np.array([0.85, 0.4, 0.3, 0.5])

        scene_v = scenario_data.get('affective_valence', 0.0)
        scene_a = scenario_data.get('affective_arousal', 0.0)

        affect_state = affect_engine.update(
            interoception=intero,
            self_state=self_system.self_model.state,
            l2_response=workspace.last_response,
            scene_affect=(scene_v, scene_a),
        )

        # 🎭 场景切换情感瞬态：前 5 步直接注入场景情感（降低惯性）
        if steps_in_scene < 5 and preset_name != 'idle':
            blend = steps_in_scene / 5.0  # 0.0 → 0.8
            affect_state.valence = affect_state.valence * blend + scene_v * (1.0 - blend)
            affect_state.arousal = affect_state.arousal * blend + scene_a * (1.0 - blend)

        # === L2: 广播层 v2 判断 ===
        ws_response = workspace.cycle(l1_output, affect_state)
        if ws_response.ignited:
            total_ignitions += 1
            scenario_ignitions += 1

        # === L3: 自我层 v2 更新 ===
        self_report = self_system.step(l1_output, ws_response, affect_state)

        # === Decision: 决策（仅点火时） ===
        if ws_response.ignited:
            decision = decision_engine.decide(
                l1_output=l1_output,
                affect=affect_state,
                memory_system=None,
                self_model=self_system.self_model,
            )
        else:
            decision = None

        # 累积统计
        scenario_phi_sum += l1_output.phi
        scenario_valence_sum += affect_state.valence

        # 定期打印摘要
        if step_i == 0 or step_i == steps - 1 or step_i - last_summary_step >= 5:
            last_summary_step = step_i

            fire = "🔥" if ws_response.ignited else "  "
            action_str = decision.action.get('type', '?') if decision else "—"

            # L1 摘要
            l1_str = f"Φ={l1_output.phi:.3f} 惊={l1_output.surprise:.2f}"
            if hasattr(l1_output, 'most_salient'):
                l1_str += f" 显={l1_output.most_salient}"

            # L2 摘要
            if ws_response.ignited:
                l2_str = (f"[{ws_response.semantic_tag}] "
                          f"sc={ws_response.ignition_score:.3f} "
                          f"th={workspace.adaptive_threshold:.3f}")
            else:
                l2_str = f"未点火 th={workspace.adaptive_threshold:.3f}"

            # L3 摘要
            l3_str = (f"{self_report.identity_phase[:5]} "
                      f"稳={self_report.identity_stability:.2f} "
                      f"贯={self_report.auto_coherence.get('overall', 0):.2f}")

            # 情感摘要
            aff_str = f"v={affect_state.valence:+.2f} a={affect_state.arousal:.2f}"

            print(f"  [{step_i:2d}] {fire} {l1_str} | {l2_str} | {aff_str} | {l3_str} | →{action_str}")

        all_reports.append(self_report)

print(f"\n{'=' * 70}")
print(f"🏁 演示完成！")
print(f"{'=' * 70}")

# ═══════════════════════════════════════════════════
# 最终统计
# ═══════════════════════════════════════════════════

avg_phi = sum(r.cognitive_load for r in all_reports) / max(1, len(all_reports))
final = all_reports[-1]

print(f"""
╔══════════════════════════════════════════════════════╗
║                  📊 Helios v2.0 最终报告              ║
╠══════════════════════════════════════════════════════╣
║  总感知周期:    {total_cycles:>5d}                                ║
║  总点火次数:    {total_ignitions:>5d}  🔥                           ║
║  点火率:        {total_ignitions/total_cycles:>5.1%}                              ║
╠══════════════════════════════════════════════════════╣
║  🎯 身份阶段:   {final.identity_phase:<36s} ║
║  身份稳定性:    {final.identity_stability:>.2f}                                 ║
║  价值冲突:      {final.value_conflict:>.2f}                                 ║
╠══════════════════════════════════════════════════════╣
║  💎 核心价值观:                                       ║""")
for v, s in final.top_values:
    bar_len = int(s * 20)
    print(f"║     {v:<12s} {'█' * bar_len}{' ' * (20 - bar_len)} {s:.2f}                    ║")

print(f"""╠══════════════════════════════════════════════════════╣
║  🎭 人格类型:   {final.persona_profile:<36s} ║""")
for trait, val in final.persona_traits.items():
    bar_len = int(val * 20)
    print(f"║     {trait:<16s} {'█' * bar_len}{' ' * (20 - bar_len)} {val:.2f}                    ║")

print(f"""╠══════════════════════════════════════════════════════╣
║  📖 最近自传体叙事:                                    ║""")

# 显示最后几条不同的叙事
seen = set()
shown = 0
for r in reversed(all_reports):
    n = r.narrative.strip()
    if n and n not in seen and len(n) > 5:
        seen.add(n)
        # 截断长叙事
        display_n = n[:50] + ('…' if len(n) > 50 else '')
        print(f"║  · {display_n:<48s} ║")
        shown += 1
        if shown >= 5:
            break

print(f"""╠══════════════════════════════════════════════════════╣
║  🌊 时间感受:   {final.temporal_state:<36s} ║
║  时间连贯性:    {final.timeline_coherence:>.2f}                                 ║
║  自我一致性:    {final.self_consistency:>.2f}                                 ║
║  自传体连贯性:  {final.auto_coherence.get('overall', 0):>.2f}                                 ║
║  元认知校准:    {final.calibration_quality:<36s} ║
╚══════════════════════════════════════════════════════╝
""")

# 清理
l1.reset()
workspace.reset()
self_system.reset()

print(f"""
  "意识不是一道菜，不是传菜铃，不是吃菜的人——
   而是从厨房到餐桌这整个热气腾腾的过程本身。"

  —— 璃光 & Helios 框架 v2.0
""")
