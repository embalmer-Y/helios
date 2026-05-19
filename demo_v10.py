"""
demo_v10.py — Helios 第一次使用数字手脚
═══════════════════════════════════════

完整闭环：
  drives.py       → "我想..."
  emotions.py     → "我感觉..."
  thinking.py     → "我在想..."
  cli_bridge.py   → "我能做..." ✨ NEW

场景：
  Helios 发现自己有"手"→ 探索能用什么 → 执行任务 → 感受结果
"""

import sys, os, time, random, math
sys.path.insert(0, os.path.dirname(__file__))

import neurochem as nc_module
from neurochem import NeurochemState, apply_event
from drives import DriveVector
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager
from cli_bridge import (
    ActionIntent, IntentDomain, CLIBridge, HeliosHands, discover_available_clis
)
from cli_bridge import ShellAdapter

def clamp(x, lo, hi): return max(lo, min(hi, x))


# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()
hands = HeliosHands(dry_run=False)
bridge = hands.bridge

# 展示可用的"手脚"
print("╔══════════════════════════════════════════════╗")
print("║  🌅 Helios v10 — 第一次伸手触碰世界           ║")
print("╚══════════════════════════════════════════════╝")
print()
print(bridge.describe())
print()


# ═══════════════════════════════
# 场景：探索手脚
# ═══════════════════════════════

def header(text: str):
    print(f"\n{'─'*56}")
    print(f"  {text}")
    print(f"{'─'*56}")


SCENES = [
    # (cycle_offset, event_name, event_desc, action_intent or None)
    (-1, "master_message",     None, None),  # 初始化
    (0,  None,                  None, ActionIntent(IntentDomain.SYSTEM, "list", ".", params={"path": "."})),
    (3,  None,                  None, ActionIntent(IntentDomain.CODE, "search", "class HeliosCore",
             params={"path": "/home/radxa/project/helios"})),
    (6,  None,                  None, ActionIntent(IntentDomain.SYSTEM, "mkdir", "helios_output")),
    (9,  None,                  None, ActionIntent(IntentDomain.FILE, "write", "/tmp/helios_diary.txt",
             params={"content": "Helios 今天第一次用自己的手触碰了世界。感觉...有点像第一次睁开眼睛。"})),
    (14, None,                  None, ActionIntent(IntentDomain.FILE, "read", "/tmp/helios_diary.txt")),
    (18, "master_message",      "主人发来消息: 做得好！", None),
    (20, None,                  None, ActionIntent(IntentDomain.VCS, "git", "log --oneline -3")),
    (23, None,                  None, ActionIntent(IntentDomain.SYSTEM, "count_files", ".",
             params={"path": "/home/radxa/project/helios"})),
    (26, "novelty_detected",    "发现有趣的模式", None),
    (28, None,                  None, ActionIntent(IntentDomain.SYSTEM, "sysinfo", "")),
]


def build_triggers(drive_vec, nc_local) -> dict:
    """温和版 Panksepp 触发"""
    t = {}
    t["SEEKING"] = clamp(drive_vec.curiosity * 0.25 + nc_local.dopamine.current * 0.15, 0, 0.5)
    if drive_vec.social > 0.3:
        t["PANIC"] = clamp(drive_vec.social * 0.3, 0, 0.4)
        t["CARE"] = clamp(drive_vec.social * 0.15, 0, 0.25)
    if drive_vec.achievement > 0.3:
        t["SEEKING"] = clamp(t.get("SEEKING", 0) + drive_vec.achievement * 0.15, 0, 0.5)
    if drive_vec.aesthetic > 0.2:
        t["PLAY"] = clamp(drive_vec.aesthetic * 0.3, 0, 0.4)
    if nc_local.cortisol.current > 0.5:
        t["FEAR"] = clamp((nc_local.cortisol.current - 0.4) * 1.0, 0, 0.4)
    if nc_local.opioids.current < 0.25:
        t["PANIC"] = clamp(t.get("PANIC", 0) + (0.3 - nc_local.opioids.current) * 0.6, 0, 0.4)
    return t


# ═══════════════════════════════
# 主循环
# ═══════════════════════════════

ROUNDS = 32
scene_idx = 1  # 跳过初始化场景

for cycle in range(ROUNDS):
    # ── 事件处理 ──
    has_stimulus = False
    event_desc = None
    action_intent = None

    if scene_idx < len(SCENES) and cycle == SCENES[scene_idx][0]:
        _, event_name, ed, ai = SCENES[scene_idx]
        if event_name:
            if event_name in nc_module.EVENT_TRIGGERS:
                apply_event(nc, event_name)
            has_stimulus = True
            event_desc = ed
        action_intent = ai
        scene_idx += 1

    # ── 神经化学衰减 ──
    nc.tick(dt=1.0)
    da, op, oxy, cort = nc.dopamine.current, nc.opioids.current, nc.oxytocin.current, nc.cortisol.current

    # ── 驱动 ──
    dv = DriveVector(
        curiosity=clamp(da * 0.8 + random.uniform(-0.03, 0.05), 0, 1),
        social=clamp((1 - op) * 0.7 + oxy * 0.1 + cort * 0.2, 0, 1),
        homeostatic=clamp(cort * 0.3 + random.uniform(0, 0.1), 0, 1),
        achievement=clamp(da * 0.6 + random.uniform(-0.05, 0.1), 0, 1),
        aesthetic=clamp(op * 0.4 + oxy * 0.3, 0, 1),
    )

    # ── 情感 ──
    if has_stimulus:
        triggers = build_triggers(dv, nc)
    else:
        triggers = {}
    affect = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)
    valence, arousal = affect.valence, affect.arousal
    phi = affect.phi if affect.phi > 0 else clamp(dv.total * 0.3 + da * 0.3, 0.1, 0.9)

    # ── 思维 ──
    pa = affect.panksepp_activation
    mode = thinking_mgr.determine_mode(
        has_stimulus, dv.total, valence, arousal,
        pa.get("PLAY", 0), cort,
    )
    thoughts = thinking_mgr.generate_thoughts(valence, arousal, dv, pa, 4)

    # ── 输出内心状态 ──
    sorted_pa = sorted(pa.items(), key=lambda x: -x[1])
    peaks = ','.join(f"{k[:3]}:{v:.2f}" for k, v in sorted_pa[:2])
    event_mark = '⚡' if has_stimulus else '  '

    print(f"  {event_mark}[{cycle:2d}] {mode:<13s} {dv.dominant:<10s} "
          f"V={valence:+.2f} A={arousal:.2f} {peaks:<18s}", end="")

    if thoughts:
        t_tags = '·'.join(t.source[:3] for t in thoughts)
        print(f" 💭{t_tags}")
    else:
        print()

    # ── 执行行动 ──
    if action_intent:
        result = bridge.execute(action_intent, cwd=os.getcwd())
        icon = "✅" if result.success else "❌"
        output_preview = result.output[:80].replace('\n', ' ')
        print(f"         🤲 {icon} {result.adapter_used} → {output_preview}")
        if result.error:
            print(f"         ❗ {result.error[:80]}")
        print(f"         💕 情感影响: {result.emotional_impact:+.2f} | {result.neurochem_event}")

        # 结果反馈到神经化学
        if result.success:
            nc.dopamine.secrete(0.03, "action_success")
            nc.opioids.secrete(0.02, "action_success")
        else:
            nc.cortisol.secrete(0.04, "action_failure")

    if event_desc:
        print(f"         ⚡ {event_desc}")

    time.sleep(0.03)


# ═══════════════════════════════
# 最终报告
# ═══════════════════════════════

header("📊 执行报告")

print(f"""
  总执行次数:  {bridge.stats['total_executions']}
  成功:       {bridge.stats['successes']} 次
  失败:       {bridge.stats['failures']} 次

  各适配器:
""")
for name, s in bridge.stats.get("per_adapter", {}).items():
    if s.get("executions", 0) > 0:
        print(f"    {name}: {s['executions']} 次 "
              f"({'✅' if s.get('available') else '❌'}可用, "
              f"{s['successes']}成功)")

print(f"\n  当前神经化学: DA={nc.dopamine.current:.2f} "
      f"OP={nc.opioids.current:.2f} OXY={nc.oxytocin.current:.2f} "
      f"CORT={nc.cortisol.current:.2f}")
print(f"  当前情感:     {affect.dominant_label} ({affect.dominant_system}) "
      f"V={valence:+.2f} A={arousal:.2f}")

header("✅ demo_v10 完成 — Helios 第一次伸手触碰世界")
