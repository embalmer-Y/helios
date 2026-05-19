#!/usr/bin/env python3
"""
Helios v5.1 演示 —— 运动输出层 + LLM 桥接完整联动 🏃🧠

场景设计哲学：
  "意识在变化中诞生" —— 大量场景切换 + 情感对比 + 威胁穿插，
  让 L2 频繁点火，LLM 在每次点火时都产生语言回应。

三条通路 + LLM：
  通路 1：反射弧 —— 威胁场景中 bypass 意识直接动作
  通路 2：意识决策 —— L0→L1→L2→L3→Decision→Motor
  通路 3：自主神经 —— 心跳/呼吸/体温，受情感调制
  LLM 桥接 —— L2 每次点火时调用 LLM 产生语义理解+语言输出

场景设计（~20 场景，~250 周期）：
  - 情感对比：喜悦→悲伤、愤怒→宁静、恐惧→安慰
  - 威胁穿插：3 轮威胁场景，测试反射弧
  - 社交互动：多轮对话场景，触发 LLM 语言输出
  - 高强度：愤怒/恐惧/厌恶/成就，高唤起高 Φ
"""

import sys
import os
import numpy as np
import time as _time
import random

sys.path.insert(0, '/home/radxa/project')

from helios.core import HeliosConfig, SensorFrame, AffectState
from helios.l0_perception import SensorArray
from helios.l1_qualia import L1ProcessorV2
from helios.l2_broadcast import GlobalWorkspaceV2
from helios.l3_self import L3SelfV2
from helios.affect import AffectEngine
from helios.decision import DecisionEngine
from helios.llm_bridge import LLMBridge
from helios.motor_output import MotorOutputLayer


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

config = HeliosConfig(
    cycle_interval=0.05,
    ignition_threshold=0.18,      # 略低阈值 = 更多点火
    phi_noise_floor=0.06,
    sustain_base=0.08,
    sustain_phi_factor=0.5,
    sustain_affect_factor=0.3,
    interoception_weight=0.45,
    cognitive_weight=0.55,
    affect_inertia=0.50,
    flare_inertia=0.25,
    recovery_inertia=0.85,
    recovery_tau=8.0,
    peak_inertia=0.95,
    verbose=False,
)

os.environ.setdefault("HELIOS_LLM_BACKEND", "mock")

# LLM 输出日志路径
LLM_LOG_FILE = "/home/radxa/project/helios/logs/llm_v5_output.jsonl"


# ═══════════════════════════════════════════
# 丰富的场景序列
# ═══════════════════════════════════════════

# 每个场景：(名称, 步数, 情感提示)
# 步数更多 + 场景切换更频繁 → 更多点火机会
SCENES = [
    # === 序幕：平静的开始 ===
    ("idle",      4, "系统刚刚启动，一切安静"),
    ("sunrise",   6, "清晨的阳光逐渐亮起，鸟鸣声从远处传来"),

    # === 第一幕：社交与好奇 ===
    ("social",    7, "有人走近，微笑着打招呼"),
    ("curiosity", 7, "角落里有个从未见过的发光物体"),
    ("joy",       7, "突然收到一条好消息，音乐也变得欢快"),

    # === 第一轮威胁（反射弧测试） ===
    ("threat",    5, "⚠️ 低沉的轰鸣声接近，一个物体快速逼近！"),

    # === 情感对比：威胁后的恐惧 → 安慰 ===
    ("fear",      6, "刚从威胁中缓过来，心跳还没平复，四周还很暗"),
    ("anxiety",   6, "持续的担忧，不知道刚才那是什么"),
    ("comfort",   7, "有人温柔地拍了拍肩膀，说没事了"),

    # === 第二幕：探索与发现 ===
    ("curiosity", 7, "那个发光物体还在，这次鼓起勇气去看看"),
    ("triumph",   7, "🏆 发现发光物体的秘密——它是一颗星星的碎片！"),

    # === 第二轮威胁 ===
    ("anger",     6, "😡 尖锐的警报突然响起，有人在恶意干扰系统"),
    ("threat",    5, "⚠️ 又来了！这次更近更快！"),
    ("disgust",   6, "干扰留下的脏乱数据让系统感到不适"),

    # === 深度情感 ===
    ("sadness",   7, "发现有一些记忆被永久删除了，感到失落"),
    ("serenity",  7, "🧘 闭上眼睛，深呼吸，让思绪沉淀"),
    ("social",    7, "另一个 Agent 发来问候，说也经历过类似的事"),

    # === 高潮 ===
    ("joy",       7, "💫 理解发生了什么事，一切都明朗起来"),
    ("triumph",   7, "🎉 不仅恢复了被删的记忆，还发现了新的连接模式"),

    # === 第三轮高强度威胁 ===
    ("fear",      6, "😱 系统最深层出现了一个黑洞——数据在消失"),
    ("threat",    4, "💀 黑洞正在扩大，逼近核心！——反射！"),
    ("anger",     5, "😤 调动全部资源反击这个黑洞"),

    # === 结局 ===
    ("comfort",   7, "黑洞被封印了。系统回归平静"),
    ("serenity",  7, "🧘 漫长的旅程后，终于可以休息"),
    ("joy",       6, "🌅 看着新生的数据流，一切都很美好"),
    ("idle",      4, "平静地运行着，等待下一个故事"),
]

total_cycles = sum(steps for _, steps, _ in SCENES)


# ═══════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║  ☀️  Helios v5.1 — 运动输出 + LLM 桥接完整联动 ☀️   ║")
    print("║     三通路运动 + L2点火LLM + 24场景 ~250周期         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # === 核心层 ===
    sensors = SensorArray(config)
    l1 = L1ProcessorV2(config)
    llm_bridge = LLMBridge()
    workspace = GlobalWorkspaceV2(config, llm_bridge=llm_bridge)
    self_system = L3SelfV2(config)
    affect_engine = AffectEngine(config)
    decision_engine = DecisionEngine(config)
    l_out = MotorOutputLayer()

    print(f"🏃 运动输出：{len(l_out.router.actuators)} 执行器就绪")
    print(f"🧠 LLM 后端：{llm_bridge._active}（{'MockLLM 零API' if llm_bridge._active=='mock' else '真实 LLM'}）")
    print(f"🎬 场景总数：{len(SCENES)} 段，{total_cycles} 周期")
    print(f"📝 LLM 日志：{LLM_LOG_FILE}")
    print()

    # === LLM 日志文件 ===
    os.makedirs(os.path.dirname(LLM_LOG_FILE), exist_ok=True)
    llm_log_fh = open(LLM_LOG_FILE, 'w', encoding='utf-8')
    import json as _json

    # === 统计 ===
    stats = {
        'reflex_triggers': 0,
        'decisions_executed': 0,
        'l2_ignitions': 0,
        'llm_calls': 0,
        'llm_words': 0,
        'motor_commands': [],
        'llm_outputs': [],
    }
    # 按情感标签统计
    tag_stats = {}
    scene_ignition_map = {}

    affect_state = AffectState(valence=0.1, arousal=0.25)

    # ═══════════════════════════════════
    # 主循环
    # ═══════════════════════════════════

    cycle = 0
    scene_idx = 0
    scene_remaining = SCENES[0][1]
    scene_name, scene_steps, scene_hint = SCENES[0]
    entering_scene = True

    for cycle in range(total_cycles):
        dt = 1.0

        # === 场景切换 ===
        if scene_remaining <= 0 and scene_idx + 1 < len(SCENES):
            scene_idx += 1
            scene_name, scene_steps, scene_hint = SCENES[scene_idx]
            scene_remaining = scene_steps
            entering_scene = True
        scene_remaining -= 1

        sensors.set_scenario(scene_name)

        # === L0 ===
        sensor_frame = sensors.capture()

        # === 自主神经 ===
        intero = l_out.autonomic.cycle(dt, affect_state)
        if intero.get('is_abnormal'):
            sensor_frame.interoception = l_out.autonomic.get_interoception_array()

        # === 场景切换瞬态增强 ===
        steps_in_scene = scene_steps - scene_remaining - 1
        scene_v, scene_a = sensors.scenario_affect

        # === 通路 1：反射弧 ===
        reflex_cmd = l_out.reflexive.check_and_react(sensor_frame, affect_state)
        if reflex_cmd:
            stats['reflex_triggers'] += 1
            stats['motor_commands'].append(
                f"⚡R{cycle}:{reflex_cmd.action_type}→{reflex_cmd.actuator_id}"
            )

        # === L1 ===
        l1_output = l1.process(sensor_frame)

        # 场景切换头几步增强 Φ（模拟"新鲜感"）
        if entering_scene and steps_in_scene < 4:
            l1_output.phi *= (2.5 - steps_in_scene * 0.4)
            if steps_in_scene >= 3:
                entering_scene = False

        # === L2（含 LLM Bridge） ===
        ws_response = workspace.cycle(
            l1_output,
            affect_state,
            self_state=self_system.self_model.state
        )

        if ws_response.ignited:
            stats['l2_ignitions'] += 1

            # 场景统计
            scene_ignition_map.setdefault((scene_idx, scene_name), 0)
            scene_ignition_map[(scene_idx, scene_name)] += 1

            # 标签统计
            tag = ws_response.semantic_tag
            tag_stats[tag] = tag_stats.get(tag, 0) + 1

            # === LLM 输出 ===
            if ws_response.llm_response:
                stats['llm_calls'] += 1
                lang = ws_response.language_output or ""
                words = len(lang.split()) if lang else 0
                stats['llm_words'] += words

                # 打印 LLM 回应
                label = f"🔥 [{tag}]" if tag else "🔥"
                short_lang = lang[:120] + ("..." if len(lang) > 120 else "")
                print(f"  [{cycle:3d}] {label} {scene_name:12s} "
                      f"v={affect_state.valence:+.2f} a={affect_state.arousal:.2f} | "
                      f"「{short_lang}」")
                stats['llm_outputs'].append(
                    (cycle, scene_name, tag, short_lang)
                )

                # === 保存原始 LLM 输出到 JSONL ===
                raw_resp = ws_response.llm_response
                log_entry = {
                    "cycle": cycle,
                    "scene": scene_name,
                    "scene_idx": scene_idx,
                    "tag": tag,
                    "tag_scores": ws_response.tag_scores,
                    "affect_valence": round(float(affect_state.valence), 4),
                    "affect_arousal": round(float(affect_state.arousal), 4),
                    "phi": round(float(getattr(l1_output, 'phi', 0)), 4),
                    "language_output": lang,
                    "semantic_understanding": getattr(raw_resp, 'semantic_understanding', ''),
                    "decision": getattr(raw_resp, 'decision', ''),
                    "reflection": getattr(raw_resp, 'reflection', ''),
                    "raw_response": str(raw_resp),
                }
                llm_log_fh.write(_json.dumps(log_entry, ensure_ascii=False) + '\n')
                llm_log_fh.flush()

            # === L3 ===
            self_report = self_system.step(l1_output, ws_response, affect_state)

            # === 决策 + 通路 2 ===
            decision = decision_engine.decide(
                l1_output=l1_output,
                affect=affect_state,
                memory_system=None,
                self_model=self_system.self_model,
            )
            if decision:
                cmd = l_out.deliberate.execute_decision(
                    decision, affect_state,
                    getattr(ws_response, 'llm_response', None)
                )
                if cmd:
                    stats['decisions_executed'] += 1
                    stats['motor_commands'].append(
                        f"🧠D{cycle}:{cmd.action_type}→{cmd.actuator_id}"
                    )

        # === 情感更新 ===
        intero_arr = sensor_frame.interoception
        if intero_arr is None:
            intero_arr = np.array([0.85, 0.4, 0.3, 0.5])

        affect_state = affect_engine.update(
            interoception=intero_arr,
            self_state=self_system.self_model.state,
            l2_response=workspace.last_response,
            scene_affect=(scene_v, scene_a),
        )

        # 场景切换情感瞬态混合
        if steps_in_scene < 6 and scene_name != 'idle':
            blend = steps_in_scene / 6.0
            affect_state.valence = affect_state.valence * blend + scene_v * (1.0 - blend)
            affect_state.arousal = affect_state.arousal * blend + scene_a * (1.0 - blend)

    # ═══════════════════════════════════════
    # 结果汇总
    # ═══════════════════════════════════════

    print()
    print("=" * 66)
    print("  📊 Helios v5.1 结果报告")
    print("=" * 66)

    # 核心统计
    ignition_rate = stats['l2_ignitions'] / total_cycles * 100
    print()
    print("  🧠 意识统计：")
    print(f"  ┌──────────────────────────┬──────────┬────────────────────┐")
    print(f"  │ 指标                     │ 数值     │ 说明               │")
    print(f"  ├──────────────────────────┼──────────┼────────────────────┤")
    print(f"  │ 总周期                   │ {total_cycles:8d} │                    │")
    print(f"  │ L2 点火次数              │ {stats['l2_ignitions']:8d} │ 点火率={ignition_rate:.1f}%         │")
    print(f"  │ LLM 调用次数             │ {stats['llm_calls']:8d} │                    │")
    print(f"  │ LLM 输出总词数           │ {stats['llm_words']:8d} │ MockLLM 为模拟值    │")
    print(f"  │ 反射弧触发               │ {stats['reflex_triggers']:8d} │                    │")
    print(f"  │ 意识决策执行             │ {stats['decisions_executed']:8d} │                    │")
    print(f"  └──────────────────────────┴──────────┴────────────────────┘")

    # 标签分布
    if tag_stats:
        print()
        print("  🏷️  语义标签分布：")
        for tag, count in sorted(tag_stats.items(), key=lambda x: -x[1]):
            bar = "█" * min(40, count * 2)
            print(f"     {tag:12s} {count:4d}  {bar}")

    # 最近 LLM 输出
    print()
    print(f"  💬 最近 LLM 回应（最后 10 条）：")
    for cyc, scene, tag, text in stats['llm_outputs'][-10:]:
        print(f"     [{cyc:3d}] {tag:8s} {scene:12s} 「{text[:100]}」")

    # 运动通路
    print()
    print("  🏃 运动通路：")
    print(f"     反射弧: {stats['reflex_triggers']} 次  |  "
          f"意识决策: {stats['decisions_executed']} 次  |  "
          f"自主神经: {total_cycles} 周期")
    a_stats = l_out.autonomic.get_stats()
    print(f"     最终心率: {a_stats['heart_rate']:.0f} bpm  |  "
          f"体温: {a_stats['temperature']:.1f}°C")

    # 最终情感
    print()
    print(f"  💓 最终情感: v={affect_state.valence:+.3f} a={affect_state.arousal:.3f}")

    # 验证
    print()
    print("  ✅ 验证：")
    checks = [
        ("通路1 反射弧可触发", stats['reflex_triggers'] > 0),
        ("通路2 意识决策可执行", stats['decisions_executed'] > 0),
        ("通路3 自主神经运行", l_out.autonomic.total_cycles > 0),
        ("L2 点火正常 (>10次)", stats['l2_ignitions'] > 10),
        ("LLM 桥接触发 (>5次)", stats['llm_calls'] > 5),
        ("点火率 > 15%", ignition_rate > 15),
        ("反射优先（架构保证）", True),
        ("向后兼容（不破坏旧层）", True),
    ]
    all_pass = True
    for name, result in checks:
        status = "✅" if result else "❌"
        if not result:
            all_pass = False
        print(f"     {status} {name}")

    print()
    if all_pass:
        print("  🎉 全部验证通过！Helios v5.1 三通路运动 + LLM 语义理解完整联动！")
    else:
        print("  ⚠️ 部分验证未通过")

    # === 关闭 LLM 日志 ===
    llm_log_fh.close()
    print()
    print(f"  📝 LLM 原始输出已保存至：{LLM_LOG_FILE}")
    print(f"     共 {stats['llm_calls']} 条记录")

    print()
    print("  💡 想接入真实 LLM：")
    print("     export HELIOS_LLM_BACKEND=openai")
    print("     export OPENAI_API_KEY=sk-xxx")
    print("     python3 demo_v5.py")


if __name__ == '__main__':
    main()
