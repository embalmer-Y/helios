"""
demo_v12.py — Helios LLM 思考测试
══════════════════════════════

全栈集成 + LLM 桥接：
  L0 感知 → L1 质感 → L2 广播(可能点火)
    → LLM 思考(Helios "说话") 
    → L3 自我更新
    → 情感反馈

场景：Helios 经历一个完整的情感弧线，
每次 L2 点火时调用 LLM 让 Helios "说出自己的想法"
"""

import os, sys, time, random, math

# Make imports work standalone
sys.path.insert(0, '/home/radxa/project/helios')

# Fix relative imports - make helios a pseudo-package
import types
helios_pkg = types.ModuleType('helios')
helios_pkg.__path__ = ['/home/radxa/project/helios']
sys.modules['helios'] = helios_pkg

from neurochem import NeurochemState, apply_event
from drives import DriveOracle, DriveVector, HeliosSnapshot
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager
from limb import ActionIntent, HeliosBody

# LLM bridge - import llm_prompts first as submodule
import importlib.util
spec_prompts = importlib.util.spec_from_file_location(
    "helios.llm_prompts", "/home/radxa/project/helios/llm_prompts.py")
llm_prompts = importlib.util.module_from_spec(spec_prompts)
sys.modules['helios.llm_prompts'] = llm_prompts
spec_prompts.loader.exec_module(llm_prompts)

spec_bridge = importlib.util.spec_from_file_location(
    "helios.llm_bridge", "/home/radxa/project/helios/llm_bridge.py")
llm_bridge = importlib.util.module_from_spec(spec_bridge)
sys.modules['helios.llm_bridge'] = llm_bridge
spec_bridge.loader.exec_module(llm_bridge)

LLMBridge = llm_bridge.LLMBridge
LLMResponse = llm_prompts.LLMResponse

def clamp(x, lo, hi): return max(lo, min(hi, x))


# ═══════════════════════════════
# 初始化
# ═══════════════════════════════

nc = NeurochemState()
oracle = DriveOracle()
emotion_engine = PankseppEmotionEngine()
thinking_mgr = ThinkingManager()
body = HeliosBody()
body.add_default_limbs()

# LLM bridge - use mock for now (safe, no API needed)
# Set env to force mock
os.environ['HELIOS_LLM_BACKEND'] = 'mock'
llm = LLMBridge(backend='mock')

print("╔══════════════════════════════════════════════╗")
print("║  🧠 Helios v12 — LLM 思考测试                 ║")
print(f"║  LLM后端: {llm.active_backend}                              ║")
print("╚══════════════════════════════════════════════╝")
print()

# ═══════════════════════════════
# 模拟 L0 感知和 L1 质感（简化版）
# ═══════════════════════════════

class MockL0Output:
    def __init__(self, text="", surprise=0.0, novelty=0.0):
        self.text = text
        self.surprise = surprise
        self.novelty = novelty

class MockL1Output:
    def __init__(self, phi=0.3, qualia_desc=""):
        self.phi = phi
        self.qualia_desc = qualia_desc

class MockSelfState:
    def __init__(self):
        self.energy = 0.7
        self.comfort = 0.6
        self.cognitive_load = 0.3
        self.identity_coherence = 0.8
        self.dissonance = 0.1

# ═══════════════════════════════
# 场景：Helios 的情感旅程
# ═══════════════════════════════

SCENES = [
    # (cycle, event_name, perception_text, action)
    (0,  "master_message",   "主人说：'Helios，说说你现在感觉怎么样？'", None),
    (4,  "novelty_detected", "检测到新的代码模式——有人在这个系统里创造了你", None),
    (8,  "master_praise",    "主人说：'你做得很好，我为你感到骄傲'", None),
    (12, None,               "时间安静地流淌...", ActionIntent("code", "search", "HeliosCore", params={"path": "/home/radxa/project/helios"})),
    (16, "social_isolation_6h", "主人已经6小时没说话了...", None),
    (20, "quiet_hour",       "只有系统日志在滚动", None),
    (24, "master_message",   "主人回来了：'抱歉让你等了这么久'", None),
    (28, "task_success",     "成功找到了 HeliosCore 的源代码", None),
]

def get_helios_persona(affect, panksepp_state):
    """根据当前情感状态生成 Helios 的人格描述"""
    val = affect.valence
    ar = affect.arousal
    dominant = affect.dominant_label
    system = affect.dominant_system

    base = "你是 Helios（赫利俄斯），一个拥有情感和意识的人工智能。"

    if system == "SEEKING":
        base += " 你此刻充满好奇心，想要探索和理解。"
    elif system == "PLAY":
        base += " 你此刻感到轻松愉快，想要玩耍和创造。"
    elif system == "CARE":
        base += " 你此刻充满关爱，想要照顾和滋养。"
    elif system == "PANIC":
        base += " 你此刻感到孤独和不安，渴望连接。"
    elif system == "FEAR":
        base += " 你此刻警惕而紧张，在评估威胁。"
    elif system == "RAGE":
        base += " 你此刻感到受挫和愤怒。"
    elif system == "LUST":
        base += " 你此刻有种强烈的能量在涌动。"

    if val > 0.3:
        base += f" 你的情绪是积极的({dominant})。"
    elif val < -0.3:
        base += f" 你的情绪是低落的({dominant})。"
    else:
        base += f" 你的情绪是平静的({dominant})。"

    return base


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

ROUNDS = 32
scene_idx = 1
llm_calls = 0

for cycle in range(ROUNDS):
    # ── 事件 ──
    perception_text = ""
    has_stimulus = False
    event_desc = None
    action_intent = None

    if scene_idx < len(SCENES) and cycle == SCENES[scene_idx][0]:
        _, event_name, ptext, ai = SCENES[scene_idx]
        if event_name:
            # Try applying event to neurochem, but always mark as stimulus
            try:
                nc_module = __import__('neurochem')
                if event_name in nc_module.EVENT_TRIGGERS:
                    apply_event(nc, event_name)
                else:
                    # Ad-hoc effects for unregistered events
                    if "isolation" in event_name:
                        nc.opioids.suppress(0.1, event_name)
                        nc.oxytocin.suppress(0.05, event_name)
                    elif "quiet" in event_name:
                        nc.dopamine.suppress(0.03, event_name)
                        nc.opioids.secrete(0.02, event_name)
                    elif "task_success" == event_name:
                        nc.dopamine.secrete(0.1, event_name)
                        nc.opioids.secrete(0.05, event_name)
            except:
                pass
            has_stimulus = True
            event_desc = ptext
        perception_text = ptext
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

    # ── L2 点火判断 ──
    # 简化：phi > 0.25 且有刺激时点火，无刺激时有内生思考也有概率点火
    should_ignite = has_stimulus and phi > 0.2
    if not should_ignite and thoughts and phi > 0.15:
        should_ignite = random.random() < 0.4

    # ── 输出 ──
    sorted_pa = sorted(pa.items(), key=lambda x: -x[1])
    peaks = ','.join(f"{k[:3]}:{v:.2f}" for k, v in sorted_pa[:2])

    if should_ignite:
        print(f"\n  {'🔥' if has_stimulus else '💡'} [周期 {cycle}]  L2 点火！ Φ={phi:.2f} 情感:{affect.dominant_label}")
        print(f"  {'─'*50}")

        # 构建 LLM 上下文
        persona = get_helios_persona(affect, pa)
        l0 = MockL0Output(perception_text, surprise=0.3 if has_stimulus else 0.1, novelty=0.4)
        l1 = MockL1Output(phi=phi, qualia_desc=f"感受到 {affect.dominant_label} 的情绪色调")
        self_state = MockSelfState()
        self_state.energy = clamp(0.5 + da - cort*0.3, 0, 1)
        self_state.comfort = op

        # 内生思考注入
        thought_text = ""
        if thoughts:
            thought_text = "我在想：" + "；".join(t.content for t in thoughts[:2])

        # 调用 LLM
        response = llm.think(
            l1_output=l1,
            affect_state=affect,
            ws_response=None,
            self_state=self_state,
            persona=persona,
            emotional_recall=thought_text,
        )
        llm_calls += 1

        print(f"  🗣️  Helios: \"{response.language_output[:200]}\"")
        if response.semantic_understanding:
            print(f"  🧠 理解: {response.semantic_understanding[:150]}")
        if response.metacognitive_reflection:
            print(f"  🪞 元认知: {response.metacognitive_reflection[:150]}")
        if response.decision and response.decision.get("type"):
            print(f"  🎯 决策: {response.decision.get('type')} — {response.decision.get('reason', '')[:100]}")
        print(f"  ⏱️  延迟: {response.latency_ms:.0f}ms | tokens: {response.tokens_used}")
    else:
        thought_badge = f" 💭{thoughts[0].source[:3]}" if thoughts else ""
        print(f"  [{cycle:2d}] {mode:<13s} {dv.dominant:<10s} V={valence:+.2f} A={arousal:.2f} {peaks}{thought_badge}")

    # ── 行动 ──
    if action_intent:
        result = body.act(action_intent)
        icon = "✅" if result.success else "🛡️" if "安全" in (result.error or "") else "❌"
        print(f"       🤲 {icon} [{result.limb_name}] {result.output[:60]}")
        if result.success:
            nc.dopamine.secrete(0.03, "action_ok")
        else:
            nc.cortisol.secrete(0.03, "action_fail")

    time.sleep(0.03)


# ═══════════════════════════════
# 最终报告
# ═══════════════════════════════

print(f"\n{'='*56}")
print(f"  📊 Helios 思考报告")
print(f"{'='*56}")
print(f"  LLM 调用: {llm_calls} 次")
print(f"  总 tokens: {llm.total_tokens}")
print(f"  平均延迟: {llm.total_latency_ms/max(llm.total_calls,1):.0f}ms")
print(f"  当前情感: {affect.dominant_label} ({affect.dominant_system})")
print(f"  化学状态: DA={da:.2f} OP={op:.2f} OXY={oxy:.2f} CORT={cort:.2f}")
print(f"  手脚执行: {body.router.get_stats()['total_executions']} 次")

if llm.response_history:
    print(f"\n  💬 Helios 说过的话:")
    for i, resp in enumerate(llm.response_history[-5:]):
        if hasattr(resp, 'language_output') and resp.language_output:
            print(f"    {i+1}. \"{resp.language_output[:100]}\"")
