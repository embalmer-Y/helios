"""
demo_v9.py — Helios 内生思考整合演示
═══════════════════════════════════

串联 Phase 1-4 全部模块，Helios 的"内心世界"：

模块链：
  neurochem.py  → 神经调质状态 (DA/OP/OXY/CORT)
  drives.py     → 驱动缺口 (5维)
  emotions.py   → Panksepp 7大情感
  thinking.py   → 四种内生思维模式

场景：
  0-9   平静期 — 驱动低，正面情绪 → 走神(wandering)
  10-19 孤独期 — 社交驱动上升，PANIC激活 → 负面走神
  20-29 探索期 — 好奇驱动高，SEEKING主导 → 计划模式
  30-39 白日梦 — PLAY激活，皮质醇低 → daydreaming
"""

import sys, os, time, random, math
sys.path.insert(0, os.path.dirname(__file__))

import neurochem as nc_module
from neurochem import NeurochemState, apply_event
from drives import DriveOracle, DriveVector, HeliosSnapshot
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager, ThoughtFragment


def clamp(x, lo, hi): return max(lo, min(hi, x))


# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
oracle = DriveOracle()
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()

# Mock a simple memory store for the replay engine
# (thinking_mgr creates its own MemoryReplayEngine internally,
#  which has _mock_memories for when no real store exists)
thinking_mgr.memory_replay.memory_store = None  # will use mocks


# ═══════════════════════════════
# 事件序列
# ═══════════════════════════════

SCENARIOS = [
    # (cycle, event_name, description)
    (0,  "master_message",      "👋 主人打了个招呼"),
    (3,  "novelty_detected",    "🆕 检测到新奇模式"),
    (5,  "safety_confirmed",    "🛡️ 环境安全确认"),
    (10, "social_isolation_6h", "💔 主人6小时没消息"),
    (14, "social_isolation_24h", "😢 主人离开一整天"),
    (17, "task_failure",        "❌ 任务失败"),
    (20, "master_message",      "✨ 主人回来了"),
    (22, "novelty_detected",    "🔍 大量新信息"),
    (25, "discovery",           "💡 发现有趣模式"),
    (27, "task_success",        "✅ 任务成功"),
    (30, "master_praise",       "💕 主人夸奖"),
    (33, "play_context",        "🎮 安全愉快的环境"),
    (36, "creative_burst",       "🌈 创作灵感涌现"),
]

# Extra events not in EVENT_TRIGGERS - add ad-hoc
# discovery → dopamine spike + opioids mild
# play_context → OP + OXY up, CORT down
# creative_burst → DA + OP up


def adhoc_event(nc_local, name):
    """Handle events not in neurochem.EVENT_TRIGGERS"""
    if name == "discovery":
        nc_local.dopamine.secrete(0.25, "discovery")
        nc_local.opioids.secrete(0.05, "discovery")
    elif name == "play_context":
        nc_local.opioids.secrete(0.10, "play")
        nc_local.oxytocin.secrete(0.08, "play")
        nc_local.cortisol.suppress(0.10, "safety")
    elif name == "creative_burst":
        nc_local.dopamine.secrete(0.20, "creativity")
        nc_local.opioids.secrete(0.08, "creativity")


def header(text: str):
    print(f"\n{'='*62}")
    print(f"  {text}")
    print(f"{'='*62}")


def build_triggers(drive_vec, nc_local) -> dict:
    """从驱动和神经化学构造 Panksepp 触发信号（温和版）"""
    t = {}
    # curiosity → SEEKING (capped low)
    t["SEEKING"] = clamp(drive_vec.curiosity * 0.25 + nc_local.dopamine.current * 0.15, 0, 0.5)
    # social → PANIC + CARE
    if drive_vec.social > 0.3:
        t["PANIC"] = clamp(drive_vec.social * 0.3, 0, 0.4)
        t["CARE"] = clamp(drive_vec.social * 0.15, 0, 0.25)
    # achievement → SEEKING
    if drive_vec.achievement > 0.3:
        t["SEEKING"] = clamp(t.get("SEEKING", 0) + drive_vec.achievement * 0.15, 0, 0.5)
    # aesthetic → PLAY
    if drive_vec.aesthetic > 0.2:
        t["PLAY"] = clamp(drive_vec.aesthetic * 0.3, 0, 0.4)
    # cortisol → FEAR
    if nc_local.cortisol.current > 0.5:
        t["FEAR"] = clamp((nc_local.cortisol.current - 0.4) * 1.0, 0, 0.4)
    # opioids low → PANIC
    if nc_local.opioids.current < 0.25:
        t["PANIC"] = clamp(t.get("PANIC", 0) + (0.3 - nc_local.opioids.current) * 0.6, 0, 0.4)
    return t


# ═══════════════════════════════
# 主循环
# ═══════════════════════════════

header("🌌 Helios 内生思考旅程 — Phase 4")

ROUNDS = 40
event_idx = 0

print(f"\n  {'周期':>3s}  {'模式':<13s}  {'驱动':<10s}  {'Val':>5s}  {'Aro':>5s}  {'Panksepp峰值':<18s}  {'思维':>s}")
print(f"  {'─'*3}  {'─'*13}  {'─'*10}  {'─'*5}  {'─'*5}  {'─'*18}  {'─'*20}")

for cycle in range(ROUNDS):
    # ── 事件处理 ──
    has_stimulus = False
    if event_idx < len(SCENARIOS) and cycle == SCENARIOS[event_idx][0]:
        _, event_name, event_desc = SCENARIOS[event_idx]
        if event_name in nc_module.EVENT_TRIGGERS:
            apply_event(nc, event_name)
        else:
            adhoc_event(nc, event_name)
        has_stimulus = True
        event_idx += 1

    # ── 神经化学衰减 ──
    nc.tick(dt=1.0)

    da = nc.dopamine.current
    op = nc.opioids.current
    oxy = nc.oxytocin.current
    cort = nc.cortisol.current

    # ── 驱动计算 ──
    # 简化：直接用神经化学推导驱动
    drive_vec = DriveVector(
        curiosity=clamp(da * 0.8 + random.uniform(-0.05, 0.05), 0, 1),
        social=clamp((1 - op) * 0.7 + oxy * 0.1 + cort * 0.2, 0, 1),
        homeostatic=clamp(cort * 0.3 + random.uniform(0, 0.15), 0, 1),
        achievement=clamp(da * 0.6 + random.uniform(-0.05, 0.1), 0, 1),
        aesthetic=clamp(op * 0.4 + oxy * 0.3, 0, 1),
    )

    # ── 情感系统 ──
    if has_stimulus:
        triggers = build_triggers(drive_vec, nc)
    else:
        triggers = {}  # 无外部刺激：仅自然衰减
    affect = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)

    valence = affect.valence
    arousal = affect.arousal
    phi = affect.phi if affect.phi > 0 else clamp(drive_vec.total * 0.3 + da * 0.3, 0.1, 0.9)

    # Panksepp 峰值
    pank_act = affect.panksepp_activation
    sorted_pank = sorted(pank_act.items(), key=lambda x: -x[1])
    pank_peaks = [f"{k[:4]}:{v:.2f}" for k, v in sorted_pank[:2]]

    # ── 思维模式 ──
    play_act = pank_act.get("PLAY", 0.0)
    mode = thinking_mgr.determine_mode(
        has_external_stimulus=has_stimulus,
        drive_total=drive_vec.total,
        valence=valence,
        arousal=arousal,
        play_activation=play_act,
        cortisol=cort,
    )
    thoughts = thinking_mgr.generate_thoughts(
        valence=valence,
        arousal=arousal,
        drives=drive_vec,
        panksepp_state=pank_act,
        limit=4,
    )

    # ── 输出 ──
    if thoughts:
        tags = '·'.join(t.source[:3] for t in thoughts)
    else:
        tags = '—'

    event_mark = '⚡' if has_stimulus else '  '
    print(f"  {event_mark}[{cycle:2d}] {mode:<13s}  {drive_vec.dominant:<10s}  "
          f"{valence:+.2f}  {arousal:.2f}  {','.join(pank_peaks):<18s}  {tags}")

    # 详细展开（每10周期的0和5）
    if cycle % 10 in (0, 5) and thoughts:
        for t in thoughts:
            print(f"           → {t.describe()}")
        print(f"           🧪 DA:{da:.2f} OP:{op:.2f} OXY:{oxy:.2f} CORT:{cort:.2f} | Φ~{phi:.2f}  "
              f"感情:{affect.dominant_label}({affect.dominant_system})")

    if has_stimulus:
        print(f"           ⚡ {SCENARIOS[event_idx-1][2]}")

    time.sleep(0.02)


# ═══════════════════════════════
# 统计
# ═══════════════════════════════

header("📊 思维统计")

# Re-run for stats (simplified)
mode_counts: dict = {}
source_counts: dict = {}
total_thoughts = 0

nc2 = NeurochemState()
em2 = PankseppEmotionEngine()
tm2 = ThinkingManager()

for cycle in range(ROUNDS):
    has_stim = False
    for c, en, ed in SCENARIOS:
        if c == cycle:
            if en in nc_module.EVENT_TRIGGERS:
                apply_event(nc2, en)
            else:
                adhoc_event(nc2, en)
            has_stim = True
            break

    nc2.tick(1.0)
    da2, op2, oxy2, cort2 = nc2.dopamine.current, nc2.opioids.current, nc2.oxytocin.current, nc2.cortisol.current

    dv2 = DriveVector(
        curiosity=clamp(da2*0.8, 0, 1),
        social=clamp((1-op2)*0.7+oxy2*0.1+cort2*0.2, 0, 1),
        homeostatic=clamp(cort2*0.3, 0, 1),
        achievement=clamp(da2*0.6, 0, 1),
        aesthetic=clamp(op2*0.4+oxy2*0.3, 0, 1),
    )
    trig2 = build_triggers(dv2, nc2)
    aff2 = em2.cycle(triggers=trig2, neurochem=nc2, dt=1.0)
    pa2 = aff2.panksepp_activation

    mode2 = tm2.determine_mode(
        has_stim, dv2.total, aff2.valence, aff2.arousal,
        pa2.get("PLAY", 0), cort2,
    )
    thoughts2 = tm2.generate_thoughts(aff2.valence, aff2.arousal, dv2, pa2, 4)

    mode_counts[mode2] = mode_counts.get(mode2, 0) + 1
    for t in thoughts2:
        source_counts[t.source] = source_counts.get(t.source, 0) + 1
        total_thoughts += 1

print(f"\n  思维模式分布:")
for m, c in sorted(mode_counts.items()):
    bar = "█" * min(c, 40)
    print(f"    {m:<15s} {bar} ({c})")

print(f"\n  思维来源分布:")
for s, c in sorted(source_counts.items()):
    print(f"    {s:<20s} {c} 次")

print(f"\n  总计内生思维: {total_thoughts} 个片段")
print(f"  外部刺激周期: {len(SCENARIOS)} 个")

header("✅ demo_v9 完成 — Phase 4 内生思考就绪")
