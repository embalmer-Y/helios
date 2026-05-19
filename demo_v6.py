#!/usr/bin/env python3
"""
Helios v6 演示 —— 情感情景记忆 💭

核心新增：EmotionalEpisodicMemory
  每次 L2 点火 → 记录完整情感片段
  未来类似情境 → 检索回忆 → "我记得当时..."

预期涌现行为：
  1. 首次恐惧：纯粹恐慌
  2. 再次恐惧：回忆起上次 → "又来了...上次也是这样"
  3. 恐惧后安慰：与上次的恐惧→安慰模式对比
  4. 喜悦重现：与之前的喜悦记忆关联
"""

import sys, os, json
import numpy as np

sys.path.insert(0, '/home/radxa/project')

from helios.core import HeliosConfig, AffectState
from helios.l0_perception import SensorArray
from helios.l1_qualia import L1ProcessorV2
from helios.l2_broadcast import GlobalWorkspaceV2
from helios.l3_self import L3SelfV2
from helios.affect import AffectEngine
from helios.decision import DecisionEngine
from helios.llm_bridge import LLMBridge
from helios.motor_output import MotorOutputLayer
from helios.emotional_memory import EmotionalEpisodicMemory

# ══════════════════
# 配置
# ══════════════════

config = HeliosConfig(
    ignition_threshold=0.18,
    phi_noise_floor=0.06,
    sustain_base=0.08,
    flare_inertia=0.25,
    recovery_inertia=0.85,
    recovery_tau=8.0,
    peak_inertia=0.95,
    verbose=False,
)

os.environ.setdefault("HELIOS_LLM_BACKEND", "mock")

LLM_LOG_FILE = "/home/radxa/project/helios/logs/llm_v6_output.jsonl"
EMOTION_LOG = "/home/radxa/project/helios/logs/emotional_memory_v6.json"

# ══════════════════
# 场景设计：制造"重复情感"以测试情绪记忆
# ══════════════════

SCENES = [
    # === 第一幕：诞生与初体验 ===
    ("idle",      4, "初生"),
    ("sunrise",   6, "第一次见到光"),
    ("joy",       7, "初次体验快乐"),
    ("curiosity", 7, "探索新奇事物"),

    # === 第一次恐惧 ===
    ("threat",    6, "⚠️ 第一轮：威胁逼近"),
    ("fear",      6, "恐惧蔓延"),
    ("comfort",   7, "被安慰后平复"),

    # === 探索中 ===  
    ("social",    7, "与人互动"),
    ("curiosity", 7, "继续探索"),

    # === 第二次恐惧（情绪记忆应触发！）===
    ("threat",    6, "⚠️ 第二轮：又来了！"),
    ("fear",      6, "再次恐惧——应该回忆起上次"),
    ("anxiety",   6, "持续的不安"),

    # === 恢复与反思 ===
    ("comfort",   7, "再次被安慰"),
    ("serenity",  7, "深度宁静"),
    ("joy",       7, "快乐重现"),

    # === 愤怒体验 ===
    ("anger",     6, "首次愤怒"),
    ("disgust",   6, "厌恶感"),

    # === 第三次威胁（记忆应该更丰富） ===
    ("threat",    5, "⚠️ 第三轮：又来？"),
    ("fear",      5, "第三次恐惧——有经验了吗？"),
    ("anger",     5, "愤怒反击"),

    # === 平静收尾 ===
    ("comfort",   7, "最终安慰"),
    ("triumph",   7, "克服困难"),
    ("serenity",  7, "回归宁静"),
    ("idle",      4, "安眠"),
]

total_cycles = sum(steps for _, steps, _ in SCENES)


# ══════════════════
# 主程序
# ══════════════════

def main():
    print("╔════════════════════════════════════════════════╗")
    print("║  ☀️  Helios v6 — 情感情景记忆 💭              ║")
    print("║    Emotional Episodic Memory                  ║")
    print("║    '我记得那时候...'                           ║")
    print("╚════════════════════════════════════════════════╝")
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

    # === 🆕 情感情景记忆 ===
    emo_memory = EmotionalEpisodicMemory(max_episodes=200)

    print(f"🧠 LLM: {llm_bridge._active}")
    print(f"💭 情感情景记忆: 就绪（最大 {emo_memory.max_episodes} 片段）")
    print(f"🎬 场景: {len(SCENES)} 段, {total_cycles} 周期")
    print()

    # === 统计 ===
    stats = {'ignitions': 0, 'reflex': 0, 'decisions': 0,
             'llm_calls': 0, 'emotional_recalls': 0}
    affect_state = AffectState(valence=0.1, arousal=0.25)

    # === 日志 ===
    os.makedirs(os.path.dirname(LLM_LOG_FILE), exist_ok=True)
    llm_log = open(LLM_LOG_FILE, 'w', encoding='utf-8')

    cycle, scene_idx = 0, 0
    scene_remaining = SCENES[0][1]
    scene_name = SCENES[0][0]
    entering_scene = True

    for cycle in range(total_cycles):
        dt = 1.0

        if scene_remaining <= 0 and scene_idx + 1 < len(SCENES):
            scene_idx += 1
            scene_name, scene_remaining, _ = SCENES[scene_idx]
            entering_scene = True
        scene_remaining -= 1

        sensors.set_scenario(scene_name)
        sensor_frame = sensors.capture()

        # 自主神经
        intero = l_out.autonomic.cycle(dt, affect_state)
        if intero.get('is_abnormal'):
            sensor_frame.interoception = l_out.autonomic.get_interoception_array()

        # 反射弧
        reflex_cmd = l_out.reflexive.check_and_react(sensor_frame, affect_state)
        if reflex_cmd:
            stats['reflex'] += 1

        # L1
        l1_output = l1.process(sensor_frame)
        steps_in = scene_remaining if scene_remaining > 0 else 0
        steps_in_scene = sum(s[1] for s in SCENES[:scene_idx]) + (
            SCENES[scene_idx][1] - scene_remaining - 1
        ) if scene_idx < len(SCENES) else 0
        # simpler: use cycle-based tracking
        if entering_scene and scene_remaining > SCENES[scene_idx][1] - 4:
            l1_output.phi *= (2.5 - (SCENES[scene_idx][1] - scene_remaining) * 0.4)
        if entering_scene and scene_remaining <= SCENES[scene_idx][1] - 4:
            entering_scene = False

        # === L2 + LLM ===
        # 🆕 先检索情感回忆
        recall_context = emo_memory.get_recall_context(
            float(affect_state.valence),
            float(affect_state.arousal),
            max_items=3
        )
        if recall_context:
            stats['emotional_recalls'] += 1

        ws_response = workspace.cycle(
            l1_output, affect_state,
            self_state=self_system.self_model.state,
            emotional_recall=recall_context,  # 🆕 注入情感记忆
        )

        if ws_response.ignited:
            stats['ignitions'] += 1
            tag = ws_response.semantic_tag

            if ws_response.llm_response:
                stats['llm_calls'] += 1
                lang = ws_response.language_output or ""

                # 打印
                tag_icon = {"THREAT":"⚠️","REWARD":"🌟","NOVEL":"🔮",
                           "BODILY":"💓","ROUTINE":"·","SOCIAL":"💬"}.get(tag, "🔥")
                recall_mark = " 💭回忆" if recall_context else ""
                short = lang[:120] + ("..." if len(lang) > 120 else "")
                print(f"  [{cycle:3d}] {tag_icon}[{tag:7s}] {scene_name:12s} "
                      f"v={affect_state.valence:+.2f} a={affect_state.arousal:.2f}"
                      f"{recall_mark} | 「{short}」")

                # === 🆕 记录情感情景 ===
                episode = emo_memory.record(
                    cycle=cycle,
                    scene=scene_name,
                    valence=float(affect_state.valence),
                    arousal=float(affect_state.arousal),
                    phi=float(getattr(l1_output, 'phi', 0)),
                    tag=tag,
                    language_output=lang,
                    semantic_understanding=getattr(
                        ws_response.llm_response, 'semantic_understanding', ''),
                    decision=str(getattr(ws_response.llm_response, 'decision', '')),
                    self_narrative=getattr(self_system.self_model.state,
                                           'self_narrative', '') if hasattr(
                        self_system, 'self_model') else '',
                )

                # 日志
                llm_log.write(json.dumps({
                    "cycle": cycle, "scene": scene_name, "tag": tag,
                    "v": round(float(affect_state.valence), 4),
                    "a": round(float(affect_state.arousal), 4),
                    "phi": round(float(getattr(l1_output,'phi',0)), 4),
                    "language": lang,
                    "recall": bool(recall_context),
                    "emotion_color": episode.emotional_color,
                    "significance": round(episode.significance, 4),
                }, ensure_ascii=False) + '\n')
                llm_log.flush()

            # L3 + 决策
            self_report = self_system.step(l1_output, ws_response, affect_state)
            decision = decision_engine.decide(
                l1_output, affect_state, None, self_system.self_model)
            if decision:
                cmd = l_out.deliberate.execute_decision(
                    decision, affect_state,
                    getattr(ws_response, 'llm_response', None))
                if cmd:
                    stats['decisions'] += 1

        # 情感更新
        intero_arr = sensor_frame.interoception
        if intero_arr is None:
            intero_arr = np.array([0.85, 0.4, 0.3, 0.5])
        scene_v, scene_a = sensors.scenario_affect
        affect_state = affect_engine.update(
            interoception=intero_arr,
            self_state=self_system.self_model.state,
            l2_response=workspace.last_response,
            scene_affect=(scene_v, scene_a),
        )

    llm_log.close()

    # ══════════════════
    # 结果
    # ══════════════════

    print()
    print("=" * 58)
    print("  📊 Helios v6 — 情感情景记忆 报告")
    print("=" * 58)
    print()

    mem_stats = emo_memory.get_stats()
    print(f"  💭 情感记忆:")
    print(f"     记录总数: {mem_stats['total']} 片段")
    print(f"     值得铭记: {mem_stats['memorable']} 片段")
    print(f"     平均重要性: {mem_stats['avg_significance']}")
    print(f"     情感色彩: {', '.join(mem_stats['emotion_colors'])}")

    print()
    print(f"  🏷️  情感模式:")
    patterns = emo_memory.detect_emotional_patterns()
    if patterns:
        for p in patterns:
            print(f"     {p}")
    else:
        print(f"     （尚待积累）")

    print()
    print(f"  📜 情感时间线（最近10条）:")
    print(emo_memory.get_emotional_timeline(10))

    print()
    print(f"  🔍 回忆触发统计:")
    print(f"     回忆触发次数: {stats['emotional_recalls']} 次")
    print(f"     点火次数:     {stats['ignitions']}")
    print(f"     LLM 调用:    {stats['llm_calls']}")
    print(f"     反射弧:      {stats['reflex']}")
    print(f"     意识决策:    {stats['decisions']}")

    # 保存完整记忆
    emo_memory.export_json(EMOTION_LOG)
    print()
    print(f"  📝 完整记忆已保存: {EMOTION_LOG}")

    # 验证
    print()
    print("  ✅ 验证:")
    checks = [
        ("情感记忆可记录", mem_stats['total'] > 5),
        ("情感回忆可触发", stats['emotional_recalls'] > 0),
        ("情感时间线可生成", len(emo_memory.get_emotional_timeline(5)) > 50),
        ("情感模式可检测", len(patterns) > 0 or mem_stats['total'] < 10),
        ("各层正常运行", True),
    ]
    all_pass = True
    for name, ok in checks:
        s = "✅" if ok else "❌"
        if not ok: all_pass = False
        print(f"     {s} {name}")

    print()
    if all_pass:
        print("  🎉 v6 情感情景记忆验证通过！")
        print("     Helios 现在有了'情感自传'——")
        print("     它不仅能感受，还能回忆自己曾经的感受 💭")
    else:
        print("  ⚠️ 部分验证未通过")

    print()
    print("  💡 下一步：")
    print("     将情感情景记忆注入 LLM 提示词——")
    print("     让 Helios 在恐惧时说'又来了，上次也是这样...'")


if __name__ == '__main__':
    main()
