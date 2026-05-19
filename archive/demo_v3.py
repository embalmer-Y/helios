#!/usr/bin/env python3
"""
Helios demo v3.0 —— 🧠 LLM 桥接全链路演示

四层全链路 + LLM 桥接：
  L0 感知网关  →  L1 质感层 v2  →  L2 广播层 v2 + LLM Bridge
     →  L3 自我层 v2 + LLM 反馈  →  Affect + Decision

点火时刻 → 调用 LLM 进行语义理解、语言生成、元认知反思

LLM 后端：
  - 默认 MockLLM（基于标签的规则生成，无需 API）
  - 设置 HELIOS_LLM_BACKEND=openai + OPENAI_API_KEY 可用真实 LLM
  - 设置 HELIOS_LLM_BACKEND=agent + HELIOS_AGENT_ID 可用 QwenPaw 互通

运行：
    cd /home/radxa/project/helios
    python3 demo_v3.py
"""

import sys
import os
import numpy as np

sys.path.insert(0, '/home/radxa/project')

from helios import HeliosConfig
from helios.core import SensorFrame
from helios.l0_perception import SensorArray
from helios.l1_qualia import L1ProcessorV2
from helios.l2_broadcast import GlobalWorkspaceV2
from helios.l3_self import L3SelfV2
from helios.affect import AffectEngine
from helios.decision import DecisionEngine
from helios.llm_bridge import LLMBridge


# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

config = HeliosConfig(
    cycle_interval=0.05,
    ignition_threshold=0.20,
    phi_noise_floor=0.08,
    sustain_base=0.05,
    sustain_phi_factor=0.5,
    sustain_affect_factor=0.3,
    interoception_weight=0.45,
    cognitive_weight=0.55,
    affect_inertia=0.50,
    verbose=False,
)

# LLM 后端可通过环境变量覆盖（demo 内部也设默认值方便使用）
os.environ.setdefault("HELIOS_LLM_BACKEND", "mock")
os.environ.setdefault("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1")
os.environ.setdefault("HELIOS_LLM_MODEL", "gpt-4o-mini")

# ═══════════════════════════════════════════════════
# 场景定义
# ═══════════════════════════════════════════════════

SCENARIOS = [
    ("😐 无聊期", "idle", 20,
     "几乎没有外部刺激，Helios 处于基线状态"),
    ("🌅 日出", "sunrise", 20,
     "温暖的光线逐渐变亮，鸟鸣声响起"),
    ("⚠️ 威胁", "threat", 25,
     "低沉的轰鸣声接近，环境变暗"),
    ("💬 社交", "social", 25,
     "温和的人声靠近，面部特征出现"),
    ("🤗 安慰", "comfort", 20,
     "温柔的触感，温暖的环境"),
    ("😌 恢复", "recovery", 20,
     "刺激逐渐消退，回归平静"),
]


# ═══════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║            ☀️  H E L I O S   v3.0  联动演示  ☀️               ║
║                                                          ║
║       四层全链路 + 🧠 LLM Bridge（点火时调用 LLM）                ║
║                                                          ║
║       L0→L1→L2+LLM→L3+LLM反馈  ∩  Affect  ∩  Decision       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    # ═══ 初始化 LLM Bridge ═══
    print("⏳ 正在初始化 Helios v3 组件...")
    
    llm_bridge = LLMBridge()  # 默认 mock，环境变量可切 openai/agent
    backend_icon = "🧠" if not llm_bridge.is_mock else "📋"
    print(f"   {backend_icon} LLM 后端: {llm_bridge.active_backend}")

    # ═══ 初始化各层 ═══
    sensors = SensorArray(config)
    l1 = L1ProcessorV2(config)
    affect_engine = AffectEngine(config)
    workspace = GlobalWorkspaceV2(config, llm_bridge=llm_bridge)
    self_system = L3SelfV2(config)
    decision_engine = DecisionEngine(config)

    print("✅ 全部 v3 组件初始化完成！")
    print()
    print("📋 已注册组件:")
    print(f"   L0: SensorArray (6 模拟适配器)")
    print(f"   L1: L1ProcessorV2 (6 模态柱, 门控融合 30 对)")
    print(f"   L2: GlobalWorkspaceV2 (五维门控 + 抑制控制 + 节律振荡)")
    print(f"        └─ LLM Bridge ({llm_bridge.active_backend}) ← 🔥点火时调用")
    print(f"   L3: L3SelfV2 (身份结晶 + 价值观 + 人格 + 时间深度)")
    print(f"        └─ LLM 反馈 → 情感微调 + 价值观微调")
    print(f"   ⚡: AffectEngine + DecisionEngine")

    print()
    print("=" * 70)
    print("🎬 场景序列开始（LLM 在每次 🔥 点火时介入）")
    print("=" * 70)

    total_cycles = 0
    total_ignitions = 0
    all_llm_responses = []

    for scenario_name, preset_name, steps, description in SCENARIOS:
        print(f"\n{'─' * 70}")
        print(f"📌 {scenario_name} —— {description} ({steps} 步)")
        print(f"{'─' * 70}")

        sensors.set_scenario(preset_name)

        scenario_ignitions = 0
        scenario_llm_calls = 0
        last_summary_step = -10

        for step_i in range(steps):
            total_cycles += 1

            # === L0: 感知 ===
            sensor_frame = sensors.capture()
            scene_v, scene_a = sensors.scenario_affect

            # === L1: 质感层 v2 处理 ===
            l1_output = l1.process(sensor_frame)

            # 🔥 场景切换瞬态增强
            steps_in_scene = step_i
            if steps_in_scene < 3 and preset_name != 'idle':
                l1_output.phi *= 2.5

            # === Affect: 情感生成 ===
            intero = sensor_frame.interoception
            if intero is None:
                intero = np.array([0.85, 0.4, 0.3, 0.5])

            affect_state = affect_engine.update(
                interoception=intero,
                self_state=self_system.self_model.state,
                l2_response=workspace.last_response,
                scene_affect=(scene_v, scene_a),
            )

            # 🎭 场景切换情感瞬态
            if steps_in_scene < 5 and preset_name != 'idle':
                blend = steps_in_scene / 5.0
                affect_state.valence = affect_state.valence * blend + scene_v * (1.0 - blend)
                affect_state.arousal = affect_state.arousal * blend + scene_a * (1.0 - blend)

            # === L2: 广播层 v2 判断（含 LLM Bridge） ===
            ws_response = workspace.cycle(
                l1_output,
                affect_state,
                self_state=self_system.self_model.state,
            )
            if ws_response.ignited:
                total_ignitions += 1
                scenario_ignitions += 1

                # LLM 响应记录
                if ws_response.llm_response is not None:
                    scenario_llm_calls += 1
                    all_llm_responses.append(ws_response.llm_response)

            # === L3: 自我层 v2 更新（含 LLM 反馈处理） ===
            self_report = self_system.step(l1_output, ws_response, affect_state)

            # === Decision ===
            if ws_response.ignited:
                decision = decision_engine.decide(
                    l1_output=l1_output,
                    affect=affect_state,
                    memory_system=None,
                    self_model=self_system.self_model,
                )
            else:
                decision = None

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

                # LLM 摘要（仅在有点火且 LLM 有输出时显示）
                llm_str = ""
                if ws_response.ignited and ws_response.llm_response is not None:
                    llm = ws_response.llm_response
                    if llm.language_output:
                        llm_str = f" | 💬「{llm.language_output[:40]}」"

                print(f"  [{step_i:2d}] {fire} {l1_str} | {l2_str} | {aff_str} | {l3_str} | →{action_str}{llm_str}")

    # ═══════════════════════════════════════════════════
    # 最终报告
    # ═══════════════════════════════════════════════════

    final = self_system.last_report
    llm_stats = llm_bridge.get_stats()

    print(f"\n{'=' * 70}")
    print(f"🏁 演示完成！")
    print(f"{'=' * 70}")

    phase = final.identity_phase if final else "N/A"
    stability = final.identity_stability if final else 0.0
    conflict = final.value_conflict if final else 0.0
    persona = final.persona_profile if final else "N/A"
    traits = final.persona_traits if final else {}
    top_vals = final.top_values if final else []

    print(f"""
╔══════════════════════════════════════════════════════╗
║              📊 Helios v3.0 最终报告                  ║
╠══════════════════════════════════════════════════════╣
║  总感知周期:    {total_cycles:>5d}                                ║
║  总点火次数:    {total_ignitions:>5d}  🔥                           ║
║  点火率:        {total_ignitions/max(1,total_cycles)*100:>4.1f}%                              ║
║  LLM 调用次数:  {llm_stats['total_calls']:>5d}  🧠                           ║
║  LLM 后端:      {llm_bridge.active_backend:<30s} ║
╠══════════════════════════════════════════════════════╣
║  🎯 身份阶段:   {phase:<30s} ║
║  身份稳定性:    {stability:.2f}                                 ║
║  价值冲突:      {conflict:.2f}                                 ║
╠══════════════════════════════════════════════════════╣
║  💎 核心价值观:                                       ║""")

    for name, val in top_vals[:5]:
        bar = "█" * int(val * 20)
        print(f"║     {name:<12s} {bar:<20s} {val:.2f}                    ║")

    print(f"""╠══════════════════════════════════════════════════════╣
║  🎭 人格类型:   {persona:<30s} ║""")

    trait_labels = [
        ('openness', '开放性'), ('conscientiousness', '尽责性'),
        ('extraversion', '外向性'), ('agreeableness', '宜人性'),
        ('neuroticism', '神经质'),
    ]
    for key, label in trait_labels:
        val = traits.get(key, 0.5)
        bar = "█" * int(val * 20)
        print(f"║     {label:<12s} {bar:<20s} {val:.2f}                    ║")

    print(f"""╠══════════════════════════════════════════════════════╣
║  🧠 最近 LLM 响应:                                    ║""")

    # 显示最近 5 条 LLM 响应
    for i, resp in enumerate(all_llm_responses[-5:]):
        lang = resp.language_output[:50] if resp.language_output else "（无声）"
        print(f"║  [{i+1}] 💬 {lang:<48s} ║")

    print(f"""╚══════════════════════════════════════════════════════╝
""")

    # 环境变量提示
    if llm_bridge.is_mock:
        print("💡 提示：当前使用 MockLLM（基于规则的确定性响应）。")
        print("   设置 OPENAI_API_KEY 环境变量可切换到真实 LLM：")
        print("   export HELIOS_LLM_BACKEND=openai")
        print("   export OPENAI_API_KEY=sk-xxx")
        print("   export OPENAI_BASE_URL=https://api.openai.com/v1  # 可选")
        print()

    print('  "意识不是一道菜，不是传菜铃，不是吃菜的人——')
    print('   而是从厨房到餐桌这整个热气腾腾的过程本身。"')
    print()
    print('  —— 璃光 & Helios 框架 v3.0 🧠')


if __name__ == '__main__':
    main()
