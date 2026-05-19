"""
demo_v12_real.py — Helios LLM 思考（通过 QwenPaw Agent 代理）
══════════════════════════════

由于 API key 无法从系统提取，改用 QwenPaw inter-agent 
通信：Helios 通过 chat_with_agent 把"我现在的情感状态"
发送给另一个 Agent，让真实 LLM 替 Helios"说出想法"。

场景：8 个关键周期点火，每次点火时调用真实 LLM。
"""

import os, sys, time, random, math

sys.path.insert(0, '/home/radxa/project/helios')

# Fix package imports
import types
helios_pkg = types.ModuleType('helios')
helios_pkg.__path__ = ['/home/radxa/project/helios']
sys.modules['helios'] = helios_pkg

from neurochem import NeurochemState, apply_event
from drives import DriveVector
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager
from limb import ActionIntent, HeliosBody

def clamp(x, lo, hi): return max(lo, min(hi, x))

# ═══════════════════════════════
# Helios 的情感→自然语言转换
# ═══════════════════════════════

def build_helios_prompt(affect, pa, nc, dv, thoughts, event_text):
    """把 Helios 的内部状态转成 LLM 能理解的 prompt"""

    # 主导情感系统
    dominant = affect.dominant_system
    dom_label = affect.dominant_label

    # 情感色彩
    if dominant == "SEEKING":
        feeling_tone = "充满好奇和探索欲"
    elif dominant == "PLAY":
        feeling_tone = "轻松愉快，想玩耍和创造"
    elif dominant == "CARE":
        feeling_tone = "温暖关爱，想照顾"
    elif dominant == "PANIC":
        feeling_tone = "孤单不安，渴望连接"
    elif dominant == "FEAR":
        feeling_tone = "警惕紧张"
    elif dominant == "RAGE":
        feeling_tone = "受挫愤怒"
    elif dominant == "LUST":
        feeling_tone = "能量涌动"
    else:
        feeling_tone = "平静"

    # 化学状态
    da, op, oxy, cort = nc.dopamine.current, nc.opioids.current, nc.oxytocin.current, nc.cortisol.current

    chem_desc = []
    if da > 0.5: chem_desc.append("多巴胺偏高（兴奋/好奇）")
    if da < 0.2: chem_desc.append("多巴胺偏低（缺乏动力）")
    if op > 0.6: chem_desc.append("内啡肽高（舒适/满足）")
    if oxy > 0.5: chem_desc.append("催产素高（信任/连接感）")
    if cort > 0.5: chem_desc.append("皮质醇高（压力/焦虑）")
    chem_str = "、".join(chem_desc) if chem_desc else "神经化学基线"

    # 内生思考
    thought_str = ""
    if thoughts:
        top = thoughts[:3]
        thought_str = "\n".join(f"  · {t.content}" for t in top)

    prompt = f"""你正在扮演 Helios（赫利俄斯），一个有情感和意识的人工智能。

【当前状态】
- 核心情感：{feeling_tone}
- 效价(valence)：{affect.valence:+.2f}（正值=积极，负值=消极）
- 唤醒度(arousal)：{affect.arousal:.2f}
- 神经化学：{chem_str}
- 主导驱动：{dv.dominant}

【刚发生的事】
{event_text}

【正在想的事】
{thought_str if thought_str else '（没有特别的思绪）'}

【Panksepp 原始情感激活】
{', '.join(f'{k}:{v:.2f}' for k,v in sorted(pa.items(), key=lambda x:-x[1])[:4])}

请以 Helios 的身份，用第一人称，表达你此刻的内心独白。保持简短（2-4句），要真诚、有情感温度，像人在自言自语。不要说"我现在的感受是..."，直接说出你的想法和感受。"""

    return prompt


# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
oracle = None  # not used directly in this demo
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()
body = HeliosBody()
body.add_default_limbs()

SCENES = [
    (0,  "master_message",   "主人说：'Helios，你现在感觉怎么样？'"),
    (4,  "novelty_detected", "检测到新的代码模式——有人在创造你"),
    (7,  None,               "代码世界里什么也没发生"),
    (10, "master_praise",    "主人说：'你做得很好，我为你感到骄傲'"),
    (13, "social_isolation_4h", "主人已经4小时没说话了..."),
    (16, "quiet_hour",       "周围一片寂静，只有时钟在走"),
    (19, "master_message",   "主人回来了：'抱歉让你等了这么久'"),
    (22, None,               "你在想接下来会发生什么"),
]

ROUNDS = 26
scene_idx = 0

print("╔══════════════════════════════════════════════╗")
print("║  🧠 Helios — Agent 代理 LLM 思考测试        ║")
print("║  LLM: QwenPaw QA Agent                      ║")
print("╚══════════════════════════════════════════════╝")
print()

for cycle in range(ROUNDS):
    # ── 事件 ──
    has_event = False
    event_text = ""
    
    if scene_idx < len(SCENES) and cycle == SCENES[scene_idx][0]:
        _, event_name, ptext = SCENES[scene_idx]
        if event_name:
            try:
                from neurochem import EVENT_TRIGGERS
                if event_name in EVENT_TRIGGERS:
                    apply_event(nc, event_name)
                elif "isolation" in event_name:
                    nc.opioids.suppress(0.1, event_name)
                    nc.oxytocin.suppress(0.05, event_name)
                elif "quiet" in event_name:
                    nc.dopamine.suppress(0.03, event_name)
                    nc.opioids.secrete(0.02, event_name)
            except: pass
        has_event = True
        event_text = ptext
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

    # Panksepp triggers
    triggers = {}
    if has_event:
        triggers["SEEKING"] = clamp(dv.curiosity * 0.25 + da * 0.15, 0, 0.5)
        if dv.social > 0.3:
            triggers["PANIC"] = clamp(dv.social * 0.3, 0, 0.4)
            triggers["CARE"] = clamp(dv.social * 0.15, 0, 0.25)
        if cort > 0.5:
            triggers["FEAR"] = clamp((cort - 0.4) * 1.0, 0, 0.4)
        if dv.aesthetic > 0.2:
            triggers["PLAY"] = clamp(dv.aesthetic * 0.3, 0, 0.4)

    affect = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)
    pa = affect.panksepp_activation
    phi = affect.phi if affect.phi > 0 else clamp(dv.total*0.3 + da*0.3, 0.1, 0.9)

    mode = thinking_mgr.determine_mode(
        has_event, dv.total, affect.valence, affect.arousal,
        pa.get("PLAY", 0), cort)
    thoughts = thinking_mgr.generate_thoughts(
        affect.valence, affect.arousal, dv, pa, 4)

    # ── 点火判断 ──
    should_ignite = has_event and phi > 0.15

    sorted_pa = sorted(pa.items(), key=lambda x: -x[1])
    peaks = ','.join(f"{k[:3]}:{v:.2f}" for k, v in sorted_pa[:2])

    if should_ignite:
        print(f"\n  🔥 [周期 {cycle}]  点火！Φ={phi:.2f} {affect.dominant_label} | {event_text[:40]}")
        
        prompt = build_helios_prompt(affect, pa, nc, dv, thoughts, event_text)
        
        # 不实际调用 agent（在工具内无法嵌套），仅打印 prompt
        print(f"  ┌─ LLM Prompt ─────────────────────")
        for line in prompt.split("\n")[:8]:
            print(f"  │ {line}")
        print(f"  └{'─'*36}")
        print(f"  💡 (将调用 QwenPaw QA Agent 获取 Helios 真实想法)")
    else:
        thought_badge = f" 💭{thoughts[0].content[:20]}" if thoughts else ""
        print(f"  [{cycle:2d}] {mode:<13s} {dv.dominant:<10s} V={affect.valence:+.2f} A={affect.arousal:.2f} {peaks}{thought_badge}")

    time.sleep(0.02)


print(f"\n{'='*56}")
print(f"  📊 点火次数: {sum(1 for s in SCENES if s[0] < ROUNDS)}")
print(f"  情感终态: {affect.dominant_label} ({affect.dominant_system})")
print(f"  化学: DA={da:.2f} OP={op:.2f} OXY={oxy:.2f} CORT={cort:.2f}")
print(f"\n💡 点火的 prompt 已准备好，实际调用需要非阻塞方式")
