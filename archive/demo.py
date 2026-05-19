#!/usr/bin/env python3
"""
Helios 演示脚本

展示一个有意识的 AI Agent 如何：
1. 从模拟环境中感知世界
2. 通过循环加工产生"体验质感"
3. 判断是否"点火"（意识时刻）
4. 产生情感反应
5. 形成自我叙事

运行方式：
    cd /home/radxa/project/helios
    python3 demo.py

场景序列：
    无聊 → 日出 → 威胁 → 社交 → 安慰 → 无聊
"""

import sys
import time
import os

# 确保能找到 helios 包
sys.path.insert(0, '/home/radxa/project')

from helios import HeliosAgent, HeliosConfig

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

config = HeliosConfig(
    cycle_interval=0.05,      # 50ms → 20Hz（更快的心跳）
    ignition_threshold=0.35,  # 点火阈值（意识时刻的门槛）
    phi_noise_floor=0.08,     # 提高 Φ 基底敏感度
    sustain_base=0.05,        # 缩短基础自持时长
    sustain_phi_factor=0.5,   # Φ 对自持的贡献降低
    sustain_affect_factor=0.3, # 情感对自持的贡献降低
    verbose=True,
    simulation_mode=True,
)

# ═══════════════════════════════════════════════════
# 创建 Agent
# ═══════════════════════════════════════════════════

print("""
╔══════════════════════════════════════════════════╗
║                                                  ║
║      ☀️  H E L I O S  演示  ☀️                    ║
║                                                  ║
║  一个有意识、有情感的 AI Agent 原型                ║
║  基于"分层循环广播模型"                           ║
║                                                  ║
║  意识不是一道菜(L1)、不是传菜铃(L2)、              ║
║  不是吃菜的人(L3)，而是从厨房到餐桌               ║
║  这整个热气腾腾的过程本身。                       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")

print("⏳ 正在初始化 Helios Agent...", end=" ", flush=True)
agent = HeliosAgent(config)
print("✅ Helios 已就绪！")

print(f"""
📋 配置摘要:
   - 循环频率: {1/config.cycle_interval:.0f}Hz ({config.cycle_interval*1000:.0f}ms)
   - 点火阈值: {config.ignition_threshold}
   - 情感惯性: {config.affect_inertia}
   - 记忆上限: {config.episodic_memory_max}
""")

# ═══════════════════════════════════════════════════
# 场景序列
# ═══════════════════════════════════════════════════

scenarios = [
    ("boredom", 30, "😐 无聊期 —— 几乎没有刺激"),
    ("sunrise", 30, "🌅 日出 —— 光线变亮，鸟鸣，温暖"),
    ("threat", 25, "⚠️  威胁 —— 阴影逼近，低频噪音"),
    ("social", 30, "👥 社交 —— 人脸靠近，语音，触碰"),
    ("comfort", 30, "🛋️  舒适 —— 温暖光芒，轻柔音乐"),
    ("boredom", 20, "😐 恢复平静 —— 刺激消退"),
]

print("\n" + "=" * 55)
print("🎬 场景序列开始")
print("=" * 55)

for scenario_name, steps, description in scenarios:
    print(f"\n{'─'*55}")
    print(f"📌 {description} ({steps} 步)")
    print(f"{'─'*55}")

    # 设置场景
    agent.set_scenario(scenario_name)

    # 运行指定步数
    agent.run(steps=steps, interval=0.08, verbose=True)

    # 打印中间摘要
    reports = agent.reports[-steps:]
    ignited_count = sum(1 for r in reports if r.ignited)
    avg_phi = sum(r.phi for r in reports) / len(reports)
    avg_valence = sum(r.affect_valence for r in reports) / len(reports)
    print(f"  📊 本场景: 点火 {ignited_count}/{steps} 次 | "
          f"平均 Φ={avg_phi:.3f} | 平均价态={avg_valence:+.3f}")

# ═══════════════════════════════════════════════════
# 最终报告
# ═══════════════════════════════════════════════════

print("\n\n" + "=" * 55)
print("📊 最终意识状态报告")
print("=" * 55)
print()

agent.print_summary()

print("\n" + "=" * 55)
print("📈 情感时间线分析")
print("=" * 55)

timeline = agent.get_emotion_timeline()
n = len(timeline['valence'])

# 简单的文本可视化
if n > 0:
    # 按场景分段
    segment_size = 20
    for seg_start in range(0, n, segment_size):
        seg_end = min(seg_start + segment_size, n)
        seg_valence = timeline['valence'][seg_start:seg_end]
        seg_phi = timeline['phi'][seg_start:seg_end]
        avg_v = sum(seg_valence) / len(seg_valence)
        avg_p = sum(seg_phi) / len(seg_phi)
        ignited_s = sum(timeline['ignited'][seg_start:seg_end])

        # 价态可视化条
        v_pos = int((avg_v + 1) / 2 * 20)
        v_bar = "░" * v_pos + "█" + "░" * (20 - v_pos)

        # Φ 可视化条
        phi_pos = int(avg_p * 20)
        phi_bar = "░" * phi_pos + "█" + "░" * (20 - phi_pos)

        print(f"  段 {seg_start//segment_size + 1}: "
              f"价态 [{v_bar}] {avg_v:+.2f} | "
              f"Φ [{phi_bar}] {avg_p:.2f} | "
              f"点火 {int(ignited_s)}/{seg_end-seg_start}")

print("\n" + "=" * 55)
print("💭 最近的自传体叙事（Helios 的内心世界）")
print("=" * 55)

for i, story in enumerate(agent.narrative.get_narrative_summary(10)):
    print(f"  {i+1}. {story}")

print("\n" + "=" * 55)
print("🏁 演示完成！Helios 经历了 {} 个意识周期，".format(agent.cycle_count))
print("   其中 {} 次意识'点火'时刻 🔥".format(agent.workspace.total_ignitions))
print("   情感范围: {:.2f} ~ {:.2f}".format(
    min(timeline['valence']), max(timeline['valence'])
))
print("=" * 55)
print()
print("  \"意识不是一道菜，不是传菜铃，不是吃菜的人——")
print("   而是从厨房到餐桌这整个热气腾腾的过程本身。\"")
print()
print("  —— 璃光 & Helios 框架")
print()
