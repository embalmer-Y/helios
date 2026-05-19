#!/usr/bin/env python3
"""
Helios demo v4.0 —— 🎭 情感环面全面测试

15 种场景覆盖完整的 valence × arousal 空间：

  高唤起 ↑
  恐惧(-0.80,0.90)     愤怒(-0.65,0.85)    喜悦(+0.80,0.75)   成就(+0.90,0.85)
  厌恶(-0.55,0.70)     威胁(-0.70,0.80)    好奇(+0.35,0.55)   社交(+0.45,0.55)
  焦虑(-0.50,0.65)                         清晨(+0.50,0.45)
  ─────────────────────────────────────────────→ 正价态
  悲伤(-0.60,0.30)     无聊( 0.00,0.10)    宁静(+0.65,0.20)   安慰(+0.70,0.30)
  低唤起 ↓

运行：
    cd /home/radxa/project/helios
    python3 demo_v4.py                          # MockLLM（快速，无 API）
    HELIOS_LLM_BACKEND=openai python3 demo_v4.py # 真实 LLM
"""

import sys
import os
import numpy as np
import time as _time

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
    affect_inertia=0.50,        # 向后兼容（旧 demo 用这个）
    # === v4: 非对称情感惯性 ===
    flare_inertia=0.25,         # 烈火易起：平静→激烈 快速切换
    recovery_inertia=0.85,      # 烈火难熄：激烈→平静 缓慢平复
    recovery_tau=8.0,           # 平复 τ：8 秒回到 63%
    peak_inertia=0.95,          # 峰值惯性：刚经历峰值时几乎冻结
    verbose=False,
)

# LLM 环境变量默认值
os.environ.setdefault("HELIOS_LLM_BACKEND", "mock")
os.environ.setdefault("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1")
os.environ.setdefault("HELIOS_LLM_MODEL", "ali/qwen3.5-flash")


# ═══════════════════════════════════════════════════
# 15 场景定义 —— 覆盖情感环面
# ═══════════════════════════════════════════════════

SCENARIOS = [
    #  (emoji 名称,          preset,     步数, 描述)
    ("😴 基线-平静",           "idle",      12, "平静的初始状态，几乎没有外部刺激"),
    ("🌅 清晨-温和积极",       "sunrise",   14, "光线逐渐变亮，鸟鸣声响起"),
    ("🎉 喜悦-高正高唤",       "joy",       14, "意外的好消息传来，美妙的音乐响起"),
    ("🧘 宁静-高正低唤",       "serenity",  14, "冥想般的深度平静，远处的海浪声"),
    ("🔍 好奇-中正中唤",       "curiosity", 14, "有趣的发现，从未见过的图案出现了"),
    ("⚠️ 威胁-负价高唤",       "threat",    14, "低沉的轰鸣声接近，环境逐渐变暗"),
    ("😡 愤怒-高负高唤",       "anger",     14, "尖锐的警报响起，受到不公的对待"),
    ("😱 恐惧-极高负极高唤",    "fear",      14, "纯粹的恐怖，尖叫声和黑暗包围"),
    ("😢 悲伤-负价低唤",       "sadness",   14, "失去的感觉，蓝色调笼罩一切"),
    ("😰 焦虑-中负中唤",       "anxiety",   14, "持续的担忧，不规则的蜂鸣声"),
    ("🤢 厌恶-中负中高唤",     "disgust",   14, "不愉快的气味和景象，想远离"),
    ("💬 社交-温和积极",       "social",    14, "温和的人声靠近，温暖的面部特征"),
    ("🤗 安慰-高正低唤",       "comfort",   14, "温柔的触感，被安抚和拥抱的感觉"),
    ("🏆 成就-极高正极高唤",    "triumph",   14, "克服困难达成目标，金色的光芒闪耀"),
    ("😌 恢复-回归基线",       "idle",      14, "刺激逐渐消退，回归平静"),
]


# ═══════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║    🎭  H E L I O S   v4.0   情感环面全面测试  🎭            ║
║                                                          ║
║    15 种情感场景 × 14 步 = 210 周期                        ║
║    覆盖 valence(-0.80~+0.90) × arousal(0.10~0.90)       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    # ═══ 初始化 ═══
    print("⏳ 正在初始化 Helios v4 组件...")

    t0 = _time.time()
    sensors = SensorArray(config)
    l1 = L1ProcessorV2(config)
    affect_engine = AffectEngine(config)
    llm_bridge = LLMBridge()
    workspace = GlobalWorkspaceV2(config, llm_bridge=llm_bridge)
    self_system = L3SelfV2(config)
    decision_engine = DecisionEngine(config)

    init_time = (_time.time() - t0) * 1000
    print(f"✅ 全部组件初始化完成！({init_time:.0f}ms)")
    print(f"   🧠 LLM 后端: {llm_bridge.active_backend}")
    print()

    # 情感轨迹记录
    trajectory = []      # [(step, scenario, valence, arousal, tag, llm_text)]

    total_cycles = 0
    total_ignitions = 0

    print("=" * 78)
    print("🎬 15 种情感场景序列")
    print("=" * 78)

    for scenario_name, preset_name, steps, description in SCENARIOS:
        print(f"\n{'─' * 78}")
        print(f"📌 {scenario_name}")
        print(f"   {description}  (target: v={config.interoception_weight:.2f})")
        print(f"{'─' * 78}")

        sensors.set_scenario(preset_name)

        scenario_ignitions = 0
        last_summary_step = -10

        for step_i in range(steps):
            total_cycles += 1

            # === L0: 感知 ===
            sensor_frame = sensors.capture()
            scene_v, scene_a = sensors.scenario_affect

            # === L1: 质感层 v2 处理 ===
            l1_output = l1.process(sensor_frame)

            # 场景切换瞬态增强
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

            # 场景切换情感瞬态
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

            # === L3: 自我层 v2 更新 ===
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

            # 记录情感轨迹
            llm_text = ""
            if ws_response.ignited and ws_response.llm_response is not None:
                llm_text = ws_response.llm_response.language_output[:30] if ws_response.llm_response.language_output else ""

            tag = ws_response.semantic_tag if ws_response.ignited else "·"
            trajectory.append((
                total_cycles, preset_name,
                round(affect_state.valence, 2), round(affect_state.arousal, 2),
                tag, llm_text,
            ))

            # 定期打印摘要
            if step_i == 0 or step_i == steps - 1 or step_i - last_summary_step >= 5:
                last_summary_step = step_i

                fire = "🔥" if ws_response.ignited else "  "
                tag_str = ws_response.semantic_tag if ws_response.ignited else "—"

                # 情感条
                v_bar = _affect_bar(affect_state.valence, 10, 'pos')
                a_bar = _affect_bar(affect_state.arousal, 10, 'arousal')
                aff_str = f"v={affect_state.valence:+.2f}{v_bar} a={affect_state.arousal:.2f}{a_bar}"

                # LLM 摘要
                llm_str = ""
                if ws_response.ignited and ws_response.llm_response is not None:
                    lang = ws_response.llm_response.language_output
                    if lang:
                        llm_str = f" | 💬「{lang[:35]}」"

                print(f"  [{step_i:2d}] {fire} {tag_str:<8s} Φ={l1_output.phi:.3f} | {aff_str}{llm_str}")

    # ═══════════════════════════════════════════════════
    # 最终报告
    # ═══════════════════════════════════════════════════

    final = self_system.last_report
    llm_stats = llm_bridge.get_stats()

    print(f"\n{'=' * 78}")
    print(f"🏁 Helios v4.0 情感环面测试完成！")
    print(f"{'=' * 78}")

    phase = final.identity_phase if final else "N/A"
    stability = final.identity_stability if final else 0.0
    conflict = final.value_conflict if final else 0.0
    persona = final.persona_profile if final else "N/A"
    traits = final.persona_traits if final else {}
    top_vals = final.top_values if final else []

    print(f"""
╔══════════════════════════════════════════════════════════╗
║              📊 Helios v4.0 最终报告                       ║
╠══════════════════════════════════════════════════════════╣
║  总感知周期:    {total_cycles:>5d}                                      ║
║  总点火次数:    {total_ignitions:>5d}  🔥                                 ║
║  点火率:        {total_ignitions/max(1,total_cycles)*100:>4.1f}%                                    ║
║  LLM 调用次数:  {llm_stats['total_calls']:>5d}  🧠                                 ║
║  LLM 后端:      {llm_bridge.active_backend:<30s}       ║
╠══════════════════════════════════════════════════════════╣
║  🎯 身份:       {phase:<30s}       ║
║  身份稳定性:    {stability:.2f}                                       ║
║  价值冲突:      {conflict:.2f}                                       ║
╠══════════════════════════════════════════════════════════╣
║  💎 核心价值观:                                             ║""")

    for name, val in top_vals[:5]:
        bar = "█" * int(val * 20)
        print(f"║     {name:<12s} {bar:<20s} {val:.2f}                          ║")

    print(f"""╠══════════════════════════════════════════════════════════╣
║  🎭 人格:       {persona:<30s}       ║""")

    trait_labels = [
        ('openness', '开放性'), ('conscientiousness', '尽责性'),
        ('extraversion', '外向性'), ('agreeableness', '宜人性'),
        ('neuroticism', '神经质'),
    ]
    for key, label in trait_labels:
        val = traits.get(key, 0.5)
        bar = "█" * int(val * 20)
        print(f"║     {label:<12s} {bar:<20s} {val:.2f}                          ║")

    # === 情感轨迹散点图（ASCII） ===
    print(f"""╠══════════════════════════════════════════════════════════╣
║  📈 情感轨迹（每个点 = 一次点火时刻的感受）:                    ║
║                                                          ║
║    高唤起 ↑                                              ║""")

    # 绘制 40×20 的情感散点
    grid = [[' ' for _ in range(41)] for _ in range(21)]
    grid[10][20] = '+'  # 原点

    # 标记点火点
    for _, preset, v, a, tag, _ in trajectory:
        if tag == '·':
            continue  # 只显示点火时刻
        x = int((v + 1.0) * 20)  # [-1, +1] → [0, 40]
        y = int((1.0 - a) * 20)   # [0, 1] → [20, 0]（反转 Y 轴）
        x = max(0, min(40, x))
        y = max(0, min(20, y))

        # 不同标签不同符号
        ch = {'THREAT': '⚠', 'REWARD': '★', 'BODILY': '●', 'ROUTINE': '·',
              'NOVEL': '✦', 'SOCIAL': '♡'}.get(tag, '○')
        if grid[y][x] == ' ' or grid[y][x] == '·':
            grid[y][x] = ch

    for i, row in enumerate(grid):
        ar = 1.0 - i / 20.0
        label = f"  a={ar:.1f}" if i % 5 == 0 else "      "
        print(f"║  {label} │{''.join(row)}│")

    print(f"""║       └────────────────────────────────────────┘     ║
║       v=-1.0                               v=+1.0    ║
║    低唤起 ↓                                              ║""")

    print(f"""╠══════════════════════════════════════════════════════════╣
║  🧠 按场景的情感峰值:                                       ║""")

    # 按场景汇总
    scene_peaks = {}
    for _, preset, v, a, tag, _ in trajectory:
        if preset not in scene_peaks:
            scene_peaks[preset] = {'v': v, 'a': a, 'tags': set()}
        else:
            scene_peaks[preset]['v'] = max(scene_peaks[preset]['v'], v) if preset in ['joy','triumph','sunrise','serenity','social','comfort','curiosity'] else min(scene_peaks[preset]['v'], v)
            scene_peaks[preset]['a'] = max(scene_peaks[preset]['a'], a)
        if tag != '·':
            scene_peaks[preset]['tags'].add(tag)

    # 找到场景名
    scene_names = {s[1]: s[0] for s in SCENARIOS}
    for preset_name, info in scene_peaks.items():
        name = scene_names.get(preset_name, preset_name)
        tags_str = ','.join(info['tags']) if info['tags'] else '—'
        print(f"║  {name:<30s} v={info['v']:+.2f} a={info['a']:.2f} 标签:{tags_str}")

    print(f"""╚══════════════════════════════════════════════════════════╝
""")

    if llm_bridge.is_mock:
        print("💡 使用 MockLLM（无 API 调用）。要体验真实 LLM 响应：")
        print("   export HELIOS_LLM_BACKEND=openai")
        print("   export OPENAI_API_KEY=sk-xxx")
        print()

    print('  "意识不是一道菜，不是传菜铃，不是吃菜的人——')
    print('   而是从厨房到餐桌这整个热气腾腾的过程本身。"')
    print()
    print('  —— 璃光 & Helios 框架 v4.0 🎭')


def _affect_bar(val: float, width: int, style: str = 'pos') -> str:
    """生成情感条形图"""
    if style == 'pos':
        # -1 红 ← 0 灰 → +1 绿
        if val >= 0:
            filled = int(val * width)
            bar = '█' * filled + '░' * (width - filled)
            return f"[{bar}]"
        else:
            filled = int(abs(val) * width)
            bar = '░' * (width - filled) + '█' * filled
            return f"[{bar}]"
    else:
        # 0 低 → 1 高唤起
        filled = int(val * width)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"


if __name__ == '__main__':
    main()
