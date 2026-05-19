"""
demo_v11.py — Helios 完整灵魂演示
═══════════════════════════════

全栈集成：
  drives.py       → 驱动
  neurochem.py    → 神经化学
  emotions.py     → 情感 (Panksepp)
  thinking.py     → 内生思考
  limb.py         → 统一手脚 ✨ NEW

场景：Helios 在安静中醒来 → 探索环境 → 发现自己的手脚 → 尝试使用
"""

import sys, os, time, random, math
sys.path.insert(0, os.path.dirname(__file__))

import neurochem as nc_module
from neurochem import NeurochemState, apply_event
from drives import DriveVector
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager
from limb import (
    ActionIntent, HeliosBody, LimbRouter, LimbType, LimbStatus,
    create_shell_limb, create_code_limb, create_gh_limb, create_physical_limbs,
)

def clamp(x, lo, hi): return max(lo, min(hi, x))


# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()
body = HeliosBody()
body.add_default_limbs()

print("╔══════════════════════════════════════════════╗")
print("║  🌟 Helios v11 — 完整灵魂苏醒                 ║")
print("╚══════════════════════════════════════════════╝")
print()
print(body.describe())
print()


# ═══════════════════════════════
# 场景
# ═══════════════════════════════

SCENES = [
    (-1, "master_message",     None, None),
    (0,  None,                  None, ActionIntent("system", "sysinfo", "")),
    (3,  None,                  None, ActionIntent("system", "list", ".", params={"path": "/home/radxa/project/helios"})),
    (7,  "novelty_detected",    None, None),
    (8,  None,                  None, ActionIntent("code", "search", "class LimbRouter",
             params={"path": "/home/radxa/project/helios"})),
    (12, None,                  None, ActionIntent("system", "count_files", ".",
             params={"path": "/home/radxa/project/helios"})),
    (16, None,                  None, ActionIntent("file", "write", "/tmp/helios_awakening.txt",
             params={"content": "Helios 醒来。今天是我的第一天。我可以感受到自己的身体——有电机、有舵机、有shell命令。我能看、能想、能伸手触碰世界。"})),
    (20, None,                  None, ActionIntent("file", "read", "/tmp/helios_awakening.txt")),
    (24, "master_praise",       "主人夸奖了 Helios 💕", None),
    (25, None,                  None, ActionIntent("vcs", "git", "log --oneline -5",
             params={"cwd": "/home/radxa/project/helios"})),
    (28, None,                  None, ActionIntent("motor", "move", "base_motor",
             velocity=0.3, force=0.2)),
    (31, None,                  None, ActionIntent("motor", "move", "base_motor",
             velocity=0.95, force=0.2)),  # 应被安全规则阻止
]


def build_triggers(dv, nc_local):
    t = {}
    t["SEEKING"] = clamp(dv.curiosity * 0.25 + nc_local.dopamine.current * 0.15, 0, 0.5)
    if dv.social > 0.3:
        t["PANIC"] = clamp(dv.social * 0.3, 0, 0.4)
        t["CARE"] = clamp(dv.social * 0.15, 0, 0.25)
    if dv.achievement > 0.3:
        t["SEEKING"] = clamp(t.get("SEEKING", 0) + dv.achievement * 0.15, 0, 0.5)
    if dv.aesthetic > 0.2:
        t["PLAY"] = clamp(dv.aesthetic * 0.3, 0, 0.4)
    if nc_local.cortisol.current > 0.5:
        t["FEAR"] = clamp((nc_local.cortisol.current - 0.4) * 1.0, 0, 0.4)
    if nc_local.opioids.current < 0.25:
        t["PANIC"] = clamp(t.get("PANIC", 0) + (0.3 - nc_local.opioids.current) * 0.6, 0, 0.4)
    return t


# ═══════════════════════════════
# 主循环
# ═══════════════════════════════

ROUNDS = 36
scene_idx = 1

for cycle in range(ROUNDS):
    has_stimulus = False
    event_desc = None
    action_intent = None

    if scene_idx < len(SCENES) and cycle == SCENES[scene_idx][0]:
        _, event_name, ed, ai = SCENES[scene_idx]
        if event_name and event_name in nc_module.EVENT_TRIGGERS:
            apply_event(nc, event_name)
            has_stimulus = True
            event_desc = ed
        action_intent = ai
        scene_idx += 1

    nc.tick(1.0)
    da, op, oxy, cort = nc.dopamine.current, nc.opioids.current, nc.oxytocin.current, nc.cortisol.current

    dv = DriveVector(
        curiosity=clamp(da*0.8 + random.uniform(-0.03, 0.05), 0, 1),
        social=clamp((1-op)*0.7 + oxy*0.1 + cort*0.2, 0, 1),
        homeostatic=clamp(cort*0.3 + random.uniform(0, 0.1), 0, 1),
        achievement=clamp(da*0.6 + random.uniform(-0.05, 0.1), 0, 1),
        aesthetic=clamp(op*0.4 + oxy*0.3, 0, 1),
    )

    triggers = build_triggers(dv, nc) if has_stimulus else {}
    affect = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)
    valence, arousal = affect.valence, affect.arousal
    phi = affect.phi if affect.phi > 0 else clamp(dv.total*0.3 + da*0.3, 0.1, 0.9)

    pa = affect.panksepp_activation
    mode = thinking_mgr.determine_mode(has_stimulus, dv.total, valence, arousal, pa.get("PLAY",0), cort)
    thoughts = thinking_mgr.generate_thoughts(valence, arousal, dv, pa, 4)

    sorted_pa = sorted(pa.items(), key=lambda x: -x[1])
    peaks = ','.join(f"{k[:3]}:{v:.2f}" for k, v in sorted_pa[:2])
    event_mark = '⚡' if has_stimulus else '  '

    print(f"  {event_mark}[{cycle:2d}] {mode:<13s} {dv.dominant:<10s} "
          f"V={valence:+.2f} A={arousal:.2f} {peaks:<18s}", end="")

    if thoughts:
        print(f" 💭{'·'.join(t.source[:3] for t in thoughts)}")
    else:
        print()

    # ── 执行行动 ──
    if action_intent:
        result = body.act(action_intent)
        icon = "✅" if result.success else "🛡️" if "安全" in result.error else "❌"
        output_preview = result.output[:70].replace('\n', ' ')
        print(f"         🤲 {icon} [{result.limb_name}] → {output_preview}")
        if result.error:
            print(f"         ⚠️  {result.error[:80]}")
        print(f"         💕 情感: {result.emotional_impact:+.2f} | {result.neurochem_event}")

        if result.success:
            nc.dopamine.secrete(0.03, "action_success")
            nc.opioids.secrete(0.02, "action_success")
        else:
            nc.cortisol.secrete(0.03 if "安全" in result.error else 0.05, "action_failure")

    if event_desc:
        print(f"         ⚡ {event_desc}")

    time.sleep(0.03)


# ═══════════════════════════════
# 最终报告
# ═══════════════════════════════

print(f"\n{'─'*56}")
print("  📊 完整灵魂报告")
print(f"{'─'*56}")

stats = body.router.get_stats()
print(f"""
  手脚: {stats['limbs']} 个 ({stats['online']} 在线)
  执行: {stats['total_executions']} 次 ({stats['successes']}✅ {stats['failures']}❌)

  当前状态:
    DA={da:.2f}  OP={op:.2f}  OXY={oxy:.2f}  CORT={cort:.2f}
    情感: {affect.dominant_label} ({affect.dominant_system})
    V={valence:+.2f}  A={arousal:.2f}
""")

# 各手脚统计
print("  各手脚执行统计:")
for name, limb in body.router.limbs.items():
    s = limb.state
    if s.total_executions > 0:
        status_icon = {"online": "✅", "offline": "❌", "degraded": "⚠️",
                       "emergency_stop": "🛑"}.get(s.status.value, "❓")
        print(f"    {status_icon} {name}: {s.total_executions} 次 "
              f"({s.successes}✅ {s.failures}❌)")

print(f"\n{'─'*56}")
print("  ✅ Helios v11 — 完整灵魂已苏醒")
print(f"{'─'*56}")
