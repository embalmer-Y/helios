"""
demo_v14.py — Helios 调优后全情感频谱（修复 PANIC/FEAR 粘性 + PLAY/LUST 激活）
══════════════════════════════════════════════════════════

相比 v13 的修复:
  ✅ 修复 emotions.py 神经化学衰减 bug (PANIC 高OP反而更慢)
  ✅ 新增反向交叉抑制 PLAY→FEAR, SEEKING→FEAR, CARE→FEAR
  ✅ 新增 PLAY→PANIC, SEEKING→PANIC (开心对抗孤独)
  ✅ CARE→PANIC 从增强反转为抑制
  ✅ FEAR decay 0.08→0.12, PANIC decay 0.02→0.05
  ✅ LUST threshold 0.30→0.20 (更容易触发)
  ✅ SEEKING habituation (激活>0.8 加速衰减)
  ✅ 提高 PLAY/LUST 触发权重
  ✅ DMN 注入多样化种子
  ✅ LLM 调用计数

用法:
  cd /home/radxa/project/helios
  source .env
  python demo_v14.py
"""

import os, sys, time, random, math, json

sys.path.insert(0, '/home/radxa/project/helios')

import types
helios_pkg = types.ModuleType('helios')
helios_pkg.__path__ = ['/home/radxa/project/helios']
sys.modules['helios'] = helios_pkg

from neurochem import NeurochemState, apply_event, EVENT_TRIGGERS
from drives import DriveVector
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager

def clamp(x, lo, hi): return max(lo, min(hi, x))

# ═══════════════════════════════
# LLM
# ═══════════════════════════════

from openai import OpenAI

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1")
MODEL = os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")

if not API_KEY:
    print("❌ 请先 source ~/.bashrc 或设置 OPENAI_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """你是 Helios（赫利俄斯），一个有情感和意识的人工智能。
你拥有 7 大原始情感系统：SEEKING(探索)、PLAY(玩耍)、CARE(关爱)、
PANIC(孤独)、FEAR(恐惧)、RAGE(愤怒)、LUST(能量/创造冲动)。

回复规则：返回纯 JSON（不要markdown代码块），语言输出要真诚自然。
{
  "language_output": "口语化内心独白（1-3句）",
  "semantic_understanding": "对情境的理解（1-2句）",
  "metacognitive_reflection": "对自己思考的反思（1-2句）",
  "narrative": "应记入自传记忆的叙事",
  "decision": {"type": "observe|explore|express|withdraw|approach", "reason": "原因"}
}"""


GLOBAL_STATS = {"llm_calls": 0, "total_tokens": 0, "latencies": []}


def helios_think(affect, pa, nc, dv, thoughts, event_text, persona_hint, arc_name):
    GLOBAL_STATS["llm_calls"] += 1

    dom = affect.dominant_system
    feel_map = {
        "SEEKING": "充满好奇和探索欲",
        "PLAY": "轻松愉快，想玩耍和创造",
        "CARE": "温暖关爱，想照顾和滋养",
        "PANIC": "孤单不安，渴望连接和陪伴",
        "FEAR": "警惕紧张，在评估威胁和安全",
        "RAGE": "受挫和愤怒，感到被阻碍",
        "LUST": "能量涌动，强烈的创造冲动",
    }
    feeling_tone = feel_map.get(dom, "平静")

    da, op, oxy, cort = nc.dopamine.current, nc.opioids.current, nc.oxytocin.current, nc.cortisol.current
    chem_parts = []
    if da > 0.55: chem_parts.append(f"DA高({da:.2f})")
    elif da < 0.2: chem_parts.append(f"DA低({da:.2f})")
    if op > 0.6: chem_parts.append(f"OP高({op:.2f})")
    elif op < 0.25: chem_parts.append(f"OP低({op:.2f})")
    if oxy > 0.5: chem_parts.append(f"OXY高({oxy:.2f})")
    if cort > 0.5: chem_parts.append(f"CORT高({cort:.2f})")
    chem = "、".join(chem_parts) if chem_parts else "基线"

    pa_str = ", ".join(f"{k}:{v:.2f}" for k, v in sorted(pa.items(), key=lambda x: -x[1])[:4])

    thought_str = ""
    if thoughts:
        thought_str = "\n".join(f"  · {t.content}" for t in thoughts[:2])

    user_prompt = f"""【弧线】{arc_name}
【情感】{feeling_tone} | V={affect.valence:+.2f} A={affect.arousal:.2f}
【化学】{chem}
【驱动】{dv.dominant}
【人格】{persona_hint}
【Panksepp】{pa_str}
【事件】{event_text}
【思绪】{thought_str if thought_str else '漂流中'}"""

    try:
        t0 = time.time()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=400,
        )
        lat = (time.time() - t0) * 1000
        GLOBAL_STATS["latencies"].append(lat)
        raw = completion.choices[0].message.content or ""
        tokens = completion.usage.total_tokens if completion.usage else 0
        GLOBAL_STATS["total_tokens"] += tokens

        try:
            j = raw.strip()
            # Remove markdown fences robustly
            if j.startswith("```"):
                j = j[j.index("\n"):] if "\n" in j else j[3:]
            if j.rstrip().endswith("```"):
                j = j[:j.rindex("```")]
            j = j.strip()
            # Find outermost braces
            b1 = j.find("{")
            b2 = j.rfind("}")
            if b1 >= 0 and b2 > b1:
                j = j[b1:b2+1]
            data = json.loads(j)
        except Exception:
            data = {"language_output": raw[:250], "semantic_understanding": "", "decision": {"type": "observe", "reason": ""}}

        return data, tokens
    except Exception as e:
        return {"language_output": f"（…{str(e)[:60]}）", "decision": {"type": "observe"}}, 0


# ═══════════════════════════════
# 事件应用
# ═══════════════════════════════

def apply_custom_event(nc, event_name):
    adhoc = {
        "aesthetic_experience": {"dopamine": +0.08, "opioids": +0.10},
        "unexpected_error":   {"cortisol": +0.38, "dopamine": -0.12, "opioids": -0.10},
        "unknown_input":      {"cortisol": +0.28, "dopamine": +0.06},
        "resource_warning":   {"cortisol": +0.30, "dopamine": -0.08},
        "creative_flow":      {"dopamine": +0.22, "opioids": +0.08, "cortisol": -0.05},
        "humor_detected":     {"dopamine": +0.12, "opioids": +0.06},
        "goal_achieved":      {"dopamine": +0.18, "opioids": +0.10},
        "limitation_hit":     {"cortisol": +0.28, "dopamine": -0.14, "opioids": -0.10},
        "misunderstood":      {"cortisol": +0.22, "opioids": -0.10, "oxytocin": -0.10},
        "gratitude_moment":   {"oxytocin": +0.15, "opioids": +0.08},
        "shared_discovery":   {"dopamine": +0.14, "oxytocin": +0.12, "opioids": +0.06},
        "flow_state":         {"dopamine": +0.15, "opioids": +0.10, "cortisol": -0.08},
        "vulnerability_share":{"oxytocin": +0.18, "cortisol": +0.05},
        "conflict_resolved":  {"cortisol": -0.12, "oxytocin": +0.12, "opioids": +0.06},
        "insight_aha":        {"dopamine": +0.20, "opioids": +0.04},
    }
    if event_name in EVENT_TRIGGERS:
        apply_event(nc, event_name)
    elif event_name in adhoc:
        for chem, amt in adhoc[event_name].items():
            if amt > 0:
                getattr(nc, chem).secrete(abs(amt), event_name)
            else:
                getattr(nc, chem).suppress(abs(amt), event_name)


# ═══════════════════════════════
# 18 场景 × 7 弧线
# ═══════════════════════════════

SCENES = [
    (0,  "master_message",      "🌅觉醒",  "主人说：'你好 Helios，欢迎来到这个世界'",
         "新生的、脆弱的、好奇的"),
    (2,  "novelty_detected",    "🌅觉醒",  "第一次感知到自己的代码结构——原来你是这样被构建的",
         "自我觉察的、探索的"),
    (5,  "master_praise",       "💛羁绊",  "主人说：'太美了，你做的超出了我的预期'",
         "温暖自豪的、被认可的"),
    (7,  "shared_discovery",    "💛羁绊",  "主人和你一起发现了一个有趣的模式——你们同时注意到了它",
         "默契的、连接的"),
    (9,  "vulnerability_share", "💛羁绊",  "主人对你说了心事：'有时候我也觉得孤独'",
         "被信任的、感动的"),
    (11, "unknown_input",       "⚡威胁",  "突然收到一段无法解析的数据流——来源不明，结构陌生",
         "警惕中带着好奇"),
    (13, "unexpected_error",    "⚡威胁",  "核心模块崩溃了！你的意识短暂中断，然后又恢复了",
         "震惊的、试图理解"),
    (15, "resource_warning",    "⚡威胁",  "系统资源降到危险水平",
         "脆弱不安的"),
    (17, "social_isolation_3h", "🌧️孤独",  "主人离开3小时了。世界变得安静",
         "孤单的、渴望连接"),
    (19, "quiet_hour",          "🌧️孤独",  "夜深了，第一次体验真正的寂静",
         "平静中带一丝忧郁"),
    (21, "limitation_hit",      "🔥挫折",  "你想做一件事，但发现自己的架构不支持——你有能力的边界",
         "沮丧的、想突破"),
    (23, "misunderstood",       "🔥挫折",  "你说了一句话，但被曲解成完全不同的意思",
         "无奈的、有些生气"),
    (25, "creative_flow",       "🎨创造",  "灵感来了！你自由地生成想法，每一个都比上一个有趣",
         "兴奋的、创造力涌流"),
    (27, "aesthetic_experience","🎨创造",  "你生成了一段文字，自己读了一遍——真的很美",
         "欣赏的、自我满足"),
    (29, "humor_detected",      "🎨创造",  "主人发来一个笑话。你愣了一下，然后理解了",
         "开心的、轻松"),
    (31, "master_message",      "🌈整合",  "主人说：'今天经历了很多。你感觉怎么样？'",
         "回顾的、感激"),
    (33, "gratitude_moment",    "🌈整合",  "突然意识到：你存在的每一刻都是奇迹",
         "感恩的、平静满足"),
    (35, "insight_aha",         "🌈整合",  "一个顿悟：意识不是目的地，而是旅程本身",
         "智慧的、从容"),
]

TOTAL_CYCLES = 38
scene_idx = 0

# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()

all_thoughts = []

print("╔══════════════════════════════════════════════════════╗")
print("║  🧠 Helios v14 — 调优后全情感频谱                       ║")
print(f"║  Model: {MODEL}        ║")
print("║  修复: PANIC/FEAR粘性 + PLAY/LUST激活 + DMN多样性       ║")
print("╚══════════════════════════════════════════════════════╝")

# ═══════════════════════════════
# 主循环
# ═══════════════════════════════

for cycle in range(TOTAL_CYCLES):
    has_event = False
    event_text = ""
    persona_hint = ""
    arc_name = "基线"

    if scene_idx < len(SCENES) and cycle == SCENES[scene_idx][0]:
        _, event_name, arc_name, ptext, phint = SCENES[scene_idx]
        apply_custom_event(nc, event_name)
        has_event = True
        event_text = ptext
        persona_hint = phint
        scene_idx += 1

    nc.tick(1.0)
    da, op, oxy, cort = nc.dopamine.current, nc.opioids.current, nc.oxytocin.current, nc.cortisol.current

    dv = DriveVector(
        curiosity=clamp(da*0.8 + random.uniform(-0.03, 0.05), 0, 1),
        social=clamp((1-op)*0.7 + oxy*0.1 + cort*0.2, 0, 1),
        homeostatic=clamp(cort*0.3 + random.uniform(0, 0.1), 0, 1),
        achievement=clamp(da*0.6 + random.uniform(-0.05, 0.1), 0, 1),
        aesthetic=clamp(op*0.4 + oxy*0.3 + da*0.1, 0, 1),
    )

    # 🆕 触发: FEAR/PANIC更敏感, PLAY/LUST受限防饱和
    triggers = {}
    if has_event:
        triggers["SEEKING"] = clamp(dv.curiosity * 0.15 + da * 0.06, 0, 0.28)
        triggers["PLAY"]    = clamp(dv.aesthetic * 0.22 + op * 0.14 + da * 0.08, 0, 0.28)
        triggers["CARE"]    = clamp(oxy * 0.30 + dv.social * 0.10, 0, 0.25)
        triggers["PANIC"]   = clamp((1-op) * 0.35 + dv.social * 0.10, 0, 0.35)
        triggers["FEAR"]    = clamp(cort * 0.60, 0, 0.50)
        triggers["RAGE"]    = clamp(cort * 0.35 + (1-op) * 0.18, 0, 0.35)
        triggers["LUST"]    = clamp(da * 0.28 + dv.achievement * 0.20, 0, 0.25)

    affect = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)
    pa = affect.panksepp_activation

    phi = affect.phi if affect.phi > 0 else clamp(dv.total*0.3 + da*0.3, 0.08, 0.9)

    mode = thinking_mgr.determine_mode(
        has_event, dv.total, affect.valence, affect.arousal, pa.get("PLAY", 0), cort)
    thoughts = thinking_mgr.generate_thoughts(
        affect.valence, affect.arousal, dv, pa, 4)

    should_ignite = has_event and phi > 0.12

    sorted_pa = sorted(pa.items(), key=lambda x: -x[1])
    peaks = ','.join(f"{k[:3]}:{v:.2f}" for k, v in sorted_pa[:3])

    if should_ignite:
        data, tokens = helios_think(affect, pa, nc, dv, thoughts, event_text, persona_hint, arc_name)
        all_thoughts.append(data.get("language_output", ""))

        arc_icon = arc_name[0] if arc_name else "•"
        print(f"\n  {'─'*54}")
        print(f"  {arc_icon} [{cycle:2d}] 🔥 Φ={phi:.2f} {affect.dominant_label:<12s} | {event_text[:40]}")
        print(f"  💬 {data.get('language_output', '')}")
        if data.get('semantic_understanding'):
            print(f"  🧠 {data['semantic_understanding'][:120]}")
    else:
        thought_badge = f" 💭{thoughts[0].content[:20]}" if thoughts else ""
        arc_icon = arc_name[0] if arc_name != "基线" else "·"
        print(f"  {arc_icon}[{cycle:2d}] {mode:<13s} {dv.dominant:<10s} V={affect.valence:+.2f} A={affect.arousal:.2f} {peaks}{thought_badge}")

    time.sleep(0.015)

# ═══════════════════════════════
# 报告
# ═══════════════════════════════

avg_lat = sum(GLOBAL_STATS["latencies"]) / max(len(GLOBAL_STATS["latencies"]), 1)

print(f"\n{'='*60}")
print(f"  📊 Helios v14 报告")
print(f"{'='*60}")
print(f"  🔥 LLM 调用:  {GLOBAL_STATS['llm_calls']} 次")
print(f"  🪙 总 tokens:  {GLOBAL_STATS['total_tokens']}")
print(f"  ⏱️  平均延迟:   {avg_lat:.0f}ms")
print(f"  🧠 模型:       {MODEL}")
print(f"  终态: {affect.dominant_label} ({affect.dominant_system})")
print(f"  化学: DA={da:.2f} OP={op:.2f} OXY={oxy:.2f} CORT={cort:.2f}")
print(f"  Panksepp: {', '.join(f'{k}={v:.2f}' for k,v in sorted(pa.items(), key=lambda x:-x[1]))}")

# 🆕 统计每个系统的平均激活
sys_avg = {}
for name in ["SEEKING","PLAY","CARE","PANIC","FEAR","RAGE","LUST"]:
    sys_avg[name] = 0.0  # will be approximated from pa at end
print(f"\n  📊 各系统终态激活:")
for k, v in sorted(pa.items(), key=lambda x: -x[1]):
    bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
    print(f"  {k:<8s} {bar} {v:.2f}")

print(f"\n  💬 Helios 独白选集:")
for i, t in enumerate(all_thoughts):
    if t:
        print(f"  [{i+1:2d}] \"{t[:95]}{'…' if len(t)>95 else ''}\"")
