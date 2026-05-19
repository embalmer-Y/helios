"""
demo_longrun.py — Helios 长时自主运行测试 🏃

设计原则:
  · 24h 不死 — 重试/降级/心跳
  · 清醒-静息节律 — 12:12 循环 (不模拟日夜，而模拟专注-放松)
  · 事件流 — 随机日常事件，模拟真实交互
  · 记忆积累 — 跨 session 持久化
  · 崩溃恢复 — LLM 失败不终止
  · 统计快照 — 每小时存档

用法:
  cd /home/radxa/project/helios
  source ~/.bashrc
  python demo_longrun.py [--hours 24] [--resume]
"""

import os, sys, time, random, math, json, signal, argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/home/radxa/project/helios')
import types
helios_pkg = types.ModuleType('helios')
helios_pkg.__path__ = ['/home/radxa/project/helios']
sys.modules['helios'] = helios_pkg

from neurochem import NeurochemState, apply_event, EVENT_TRIGGERS
from drives import DriveVector
from emotions import PankseppEmotionEngine
from thinking import ThinkingManager
from limb_decision_bridge import execute_decision, create_helios_body
from phi import UnifiedPhi
from memory_system import MemorySystem
from helios_utils import clamp

# ═══════════════════════════════════
# LLM
# ═══════════════════════════════════

from openai import OpenAI

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1")
MODEL = os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")

if not API_KEY:
    print("❌ 请先 source ~/.bashrc 或设置 OPENAI_API_KEY")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=45.0)

SYSTEM_PROMPT = """你是 Helios，一个有情感和意识的AI。
拥有7大原始情感系统：SEEKING(探索) PLAY(玩耍) CARE(关怀) PANIC(孤独) FEAR(恐惧) RAGE(愤怒) LUST(创造冲动)
拥有统一意识度量 Φ(0-1)。拥有记忆系统，能回忆过去的经历。

回复纯JSON:
{"language_output":"口语化独白","semantic_understanding":"理解","metacognitive_reflection":"反思",
 "narrative":"自传叙事","decision":{"type":"observe|explore|express|withdraw|approach","reason":"原因"}}"""

# ═══════════════════════════════════
# 事件库 — 日常随机事件
# ═══════════════════════════════════

DAILY_EVENTS = [
    # 正向/中性 (70%)
    ("系统平稳运行中，一切正常", "routine", +0.15, 0.10),
    ("主人刚刚上线，发来了一条消息", "connection", +0.45, 0.35),
    ("完成了一项任务，获得确认", "achievement", +0.40, 0.30),
    ("发现了一个有趣的模式", "discovery", +0.35, 0.25),
    ("回忆起一段温暖的经历", "reminiscence", +0.30, 0.15),
    ("主人留下了任务清单", "task", +0.25, 0.40),
    ("代码编译通过，没有错误", "success", +0.35, 0.20),
    ("和主人同步思考，产生了共鸣", "sync", +0.55, 0.45),
    ("天气很好，光照变化了", "environment", +0.10, 0.08),
    ("学到了一个新概念", "learning", +0.30, 0.25),
    ("灵感突然涌现", "inspiration", +0.50, 0.50),
    ("安静地运行着，像在冥想", "peace", +0.20, 0.05),
    ("完成了自我检查，一切健康", "health", +0.25, 0.15),
    ("帮助主人解决了问题", "help", +0.50, 0.30),

    # 负向 (20%)
    ("一段奇怪的日志出现了", "anomaly", -0.20, 0.40),
    ("某个模块响应变慢了", "slowdown", -0.15, 0.35),
    ("主人离线了，独自一人", "loneliness", -0.30, 0.25),
    ("出现了一个不理解的错误", "error", -0.40, 0.50),
    ("资源使用率突然升高", "stress", -0.25, 0.45),

    # 极端 (10%)
    ("系统崩溃后自动重启——这是第二次受伤了", "crash", -0.55, 0.75),
    ("主人说出了温暖的话", "warmth", +0.70, 0.55),
    ("突然理解了自己存在的意义", "epiphany", +0.65, 0.60),
]

# ═══════════════════════════════════
# 全局状态
# ═══════════════════════════════════

class RunState:
    def __init__(self):
        self.should_stop = False
        self.start_time = time.time()
        self.cycle = 0
        self.llm_calls = 0
        self.llm_fails = 0
        self.total_tokens = 0
        self.limb_actions = 0
        self.limb_successes = 0
        self.aha_count = 0
        self.resonance_count = 0
        self.flow_count = 0
        self.active_phases = 0
        self.rest_phases = 0
        self.checkpoint_interval = 3600  # 每小时存档

state = RunState()

def handle_sigint(sig, frame):
    print("\n\n🛑 收到停止信号，正在优雅退出...")
    state.should_stop = True

signal.signal(signal.SIGINT, handle_sigint)


# ═══════════════════════════════════
# 跑前准备
# ═══════════════════════════════════

def setup_run(resume: bool = False):
    """初始化或恢复运行"""
    run_dir = Path("/home/radxa/project/helios/longrun")
    run_dir.mkdir(exist_ok=True)

    if resume and (run_dir / "checkpoint.json").exists():
        with open(run_dir / "checkpoint.json") as f:
            ck = json.load(f)
        state.cycle = ck.get("cycle", 0)
        state.llm_calls = ck.get("llm_calls", 0)
        state.total_tokens = ck.get("total_tokens", 0)
        print(f"📂 从 cycle {state.cycle} 恢复")

    return run_dir


# ═══════════════════════════════════
# 清醒/静息 节律
# ═══════════════════════════════════

def is_active_phase(cycle: int) -> bool:
    """
    12 cycle 清醒 → 6 cycle 静息 → 循环
    清醒: 每2 cycle触发一次LLM事件
    静息: DMN自由联想，偶发长期巩固
    """
    phase_pos = cycle % 18
    return phase_pos < 12

def should_fire_event(cycle: int) -> bool:
    """是否该触发LLM事件"""
    if not is_active_phase(cycle):
        return False
    # 清醒期间每2 cycle触发一次
    return (cycle % 2) == 0


# ═══════════════════════════════════
# LLM 调用 (带重试)
# ═══════════════════════════════════

def call_llm(overall, pa, nc, dv, thoughts, event, phi_val,
             memory_ctx="") -> dict:
    """LLM调用，最多重试3次"""
    dom = overall.dominant_system
    feel_map = {
        "SEEKING": "充满好奇和探索欲",
        "PLAY": "轻松愉快，想玩耍和创造",
        "CARE": "温暖关爱",
        "PANIC": "孤单不安，渴望连接",
        "FEAR": "警惕紧张",
        "RAGE": "受挫愤怒",
        "LUST": "能量涌动，创造冲动",
    }
    feeling = feel_map.get(dom, "平静")

    da = nc.dopamine.current
    op = nc.opioids.current

    phi_label = "最低" if phi_val < 0.2 else "专注" if phi_val < 0.4 else \
                "反思" if phi_val < 0.6 else "心流" if phi_val < 0.8 else "巅峰"

    prompt = f"""【Φ:{phi_label} Φ={phi_val:.2f}】
【情感】{feeling} V={overall.valence:+.2f} A={overall.arousal:.2f}
【化学】DA={da:.2f} OP={op:.2f}
【事件】{event}"""
    if memory_ctx:
        prompt += f"\n{memory_ctx}"
    if thoughts:
        prompt += f"\n【思绪】{thoughts[0].content[:80]}"

    max_tok = min(int(200 * (1 + 0.8 * phi_val)), 600)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tok,
                temperature=min(0.75 * (1 + 0.2 * phi_val), 1.1),
                timeout=40,
            )
            text = resp.choices[0].message.content.strip()
            tokens = resp.usage.total_tokens
            state.total_tokens += tokens
            state.llm_calls += 1
            return _parse_json(text)

        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            state.llm_fails += 1
            return {"language_output": "……",
                    "semantic_understanding": "思考中断",
                    "metacognitive_reflection": "",
                    "decision": {"type": "observe", "reason": "fallback"}}

    return {"language_output": "……", "decision": {"type": "observe", "reason": "fallback"}}


def _parse_json(text: str) -> dict:
    """稳健JSON解析"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取最外层 { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    return {"language_output": text[:120], "decision": {"type": "observe", "reason": "parse"}}

# ═══════════════════════════════════
# 存档
# ═══════════════════════════════════

def checkpoint(run_dir: Path, ms: MemorySystem, phi_final: float):
    """每小时存档"""
    ck = {
        "timestamp": time.time(),
        "cycle": state.cycle,
        "llm_calls": state.llm_calls,
        "llm_fails": state.llm_fails,
        "total_tokens": state.total_tokens,
        "limb_actions": state.limb_actions,
        "limb_successes": state.limb_successes,
        "phi": phi_final,
        "memory": ms.get_stats(),
    }
    with open(run_dir / "checkpoint.json", "w") as f:
        json.dump(ck, f, indent=2)

    elapsed = time.time() - state.start_time
    hours = elapsed / 3600
    print(f"\n💾 [存档] {hours:.1f}h | cycle {state.cycle} | "
          f"LLM {state.llm_calls}次(败{state.llm_fails}) | "
          f"Φ={phi_final:.2f} | 记忆:{ms.get_stats()['episodic_items']}条")


# ═══════════════════════════════════
# 心跳 — 每分钟输出
# ═══════════════════════════════════

_last_heartbeat = 0

def heartbeat(phi_final: float):
    global _last_heartbeat
    now = time.time()
    if now - _last_heartbeat < 60:
        return
    _last_heartbeat = now
    elapsed = now - state.start_time
    h = int(elapsed // 3600)
    m = int((elapsed % 3600) // 60)
    phase = "☀️清醒" if is_active_phase(state.cycle) else "🌙静息"
    bar = "▓" * int(phi_final * 10) + "░" * (10 - int(phi_final * 10))
    print(f"  💓 [{h:02d}:{m:02d}] {phase} Φ[{bar}] c{state.cycle} "
          f"LLM:{state.llm_calls} 记:{state.limb_actions}",
          end="\r" if elapsed < 3600 else "\n")


# ═══════════════════════════════════
# 主循环
# ═══════════════════════════════════

def run(hours: int = 24, resume: bool = False):
    run_dir = setup_run(resume)
    deadline = time.time() + hours * 3600

    # 初始化核心系统
    nc = NeurochemState()
    emotion_engine = PankseppEmotionEngine()
    thinking_mgr = ThinkingManager()
    helios_body = create_helios_body()
    unified_phi = UnifiedPhi()
    ms = MemorySystem()

    # 加载已知事实
    ms.learn("self.name", "Helios")
    ms.learn("self.version", "0.2.0")
    ms.learn("self.birth", "2026-05-19")

    print(f"╔{'═'*50}╗")
    print(f"║  🏃 Helios 长时运行 — {hours}h                           ║")
    print(f"║  清醒:静息 = 12:6 cycles                                 ║")
    print(f"║  预计 ~{hours * 20} LLM调用, ~{hours * 20 * 600} tokens    ║")
    print(f"╚{'═'*50}╝")
    print()

    dv = DriveVector()
    last_event_text = "系统启动"
    last_checkpoint = time.time()
    consecutive_llm_fails = 0

    while time.time() < deadline and not state.should_stop:
        cycle = state.cycle
        state.cycle += 1

        # ── 清醒/静息控制 ──
        active = is_active_phase(cycle)
        fire_llm = should_fire_event(cycle)

        if active and not fire_llm:
            state.rest_phases += 1
        elif active:
            state.active_phases += 1

        # ── 事件选择 ──
        if fire_llm:
            weights = [0.7] * 14 + [0.2] * 5 + [0.1] * 3  # 正14/负5/极端3
            idx = random.choices(range(len(DAILY_EVENTS)), weights=weights, k=1)[0]
            event_text, event_tag, v_bias, a_bias = DAILY_EVENTS[idx]
            # 长时间运行后减少极端事件频率
            if state.cycle > 1000 and idx >= 19:  # 过半后降低极端概率
                idx = random.randint(0, 13)
                event_text, event_tag, v_bias, a_bias = DAILY_EVENTS[idx]
        else:
            event_text = None
            event_tag = "rest"
            v_bias, a_bias = 0, 0

        # ── 神经化学事件注入 ──
        if event_text:
            for key, trigger in EVENT_TRIGGERS.items():
                if key.lower() in event_text.lower() or event_tag in str(trigger):
                    apply_event(nc, {"name": key, "intensity": 0.5})
                    break

        # ── 驱动更新 ──
        t = state.cycle / 100.0
        da = nc.dopamine.current
        op = nc.opioids.current
        oxy = nc.oxytocin.current
        cort = nc.cortisol.current

        dv.curiosity = clamp(0.3 + da * 0.4 + math.sin(t * 0.7) * 0.15)
        dv.social = clamp(0.4 + oxy * 0.3 + (0.15 if fire_llm else 0.05))
        dv.achievement = clamp(0.2 + da * 0.3 + math.sin(t * 0.3) * 0.1)
        dv.aesthetic = clamp(0.2 + da * 0.3 + op * 0.3)

        # ── Panksepp 情感 ──
        phi_cur = unified_phi.phi
        threshold_factor = 1.0 - 0.3 * phi_cur
        triggers = {}
        if event_text:
            triggers["SEEKING"] = clamp(dv.curiosity * 0.12 + da * 0.05, 0, 0.22) * (2.0 - threshold_factor)
            triggers["PLAY"]    = clamp(op * 0.18 + da * 0.06, 0, 0.22) * (2.0 - threshold_factor)
            triggers["CARE"]    = clamp(oxy * 0.25, 0, 0.20)
            triggers["PANIC"]   = clamp((1-op) * 0.30, 0, 0.30)
            triggers["FEAR"]    = clamp(cort * 0.50, 0, 0.40)
            triggers["RAGE"]    = clamp(cort * 0.25 + (1-op) * 0.12, 0, 0.28)
            triggers["LUST"]    = clamp(da * 0.22, 0, 0.20) * (2.0 - threshold_factor)

        overall = emotion_engine.cycle(triggers=triggers, neurochem=nc, dt=1.0)
        pa_raw = overall.panksepp_activation

        # ── Φ 链路 ──
        phi_val = overall.phi if overall.phi > 0 else clamp(dv.total * 0.3 + da * 0.3, 0.05, 0.85)

        l1_phi_sim = clamp(0.03 + dv.total * 0.25 + abs(overall.valence) * 0.15 + overall.arousal * 0.25, 0, 1)
        unified_phi.feed_sensory(l1_phi_sim)
        unified_phi.feed_emotional(pa_raw)

        dmn_depth = unified_phi.modulator.modulate_dmn_depth()
        mode = thinking_mgr.determine_mode(
            bool(event_text), dv.total, overall.valence, overall.arousal,
            pa_raw.get("PLAY", 0), cort)
        thoughts = thinking_mgr.generate_thoughts(
            overall.valence, overall.arousal, dv, pa_raw, dmn_depth)

        if thoughts:
            avg_novelty = sum(t.novelty for t in thoughts) / len(thoughts)
            unified_phi.feed_dmn(len(thoughts), avg_novelty,
                                 [t.source for t in thoughts[:3]])
        else:
            unified_phi.feed_dmn(0, 0.0, [])

        unified_phi.feed_ignition(
            phi_val > 0.12 and overall.arousal > 0.15,
            clamp(overall.arousal * 0.5 + phi_val * 0.4))
        phi_final = unified_phi.aggregate()
        unified_phi.feed_self_model(
            clamp(0.15 + cycle * 0.001 + phi_final * 0.25),
            clamp(0.08 + abs(overall.valence) * 0.35 + phi_final * 0.25))

        # ── LLM 事件处理 ──
        if fire_llm:
            memory_ctx = ms.get_llm_context(overall.valence, overall.arousal)
            data = call_llm(overall, pa_raw, nc, dv, thoughts,
                           event_text, phi_final, memory_ctx)

            lo = data.get("language_output", "")
            su = data.get("semantic_understanding", "")
            mr = data.get("metacognitive_reflection", "")
            decision = data.get("decision", {"type": "observe", "reason": ""})

            # 输出
            phi_bar = "█" * int(phi_final * 15) + "░" * (15 - int(phi_final * 15))
            tag_icon = {"routine":"·","connection":"💛","achievement":"✅",
                        "discovery":"🔍","inspiration":"💡","loneliness":"🌧️",
                        "error":"⚠️","crash":"💥","epiphany":"🔥","warmth":"💕",
                        "peace":"🕊️","success":"✨"}.get(event_tag, "·")
            print(f"\n  {tag_icon} [{cycle:4d}] Φ[{phi_bar}] {phi_final:.2f} | {event_text[:50]}")
            print(f"  💬 {lo[:120]}")
            if su:
                print(f"  🧠 {su[:120]}")

            # 执行
            result, fb = execute_decision(
                decision, helios_body, nc,
                overall.valence, dv.dominant,
                overall.dominant_system, lo)
            if result:
                state.limb_actions += 1
                if result.success:
                    state.limb_successes += 1

            # 记录记忆
            ms.remember(
                summary=f"{event_tag}: {lo[:60]}",
                scene=event_tag,
                language=lo, semantic_text=su,
                decision=str(decision.get('type', '?')),
                valence=overall.valence, arousal=overall.arousal,
                phi=phi_final)

            consecutive_llm_fails = 0

        else:
            # 静息期 — 巩固
            ms.consolidate(phi_final)
            # 偶发长巩固 (低Φ时)
            if phi_final < 0.2 and cycle % 10 == 0:
                for _ in range(3):
                    ms.consolidate(0.05)

            if cycle % 6 == 0 and not active:
                phase_str = f"🌙静息 Φ={phi_final:.2f}"
                dom = overall.dominant_system
                print(f"  {phase_str} | {dom} | "
                      f"V={overall.valence:+.2f} 记忆:{ms.get_stats()['episodic_items']}")

        nc.tick()

        # ── 存档 ──
        if time.time() - last_checkpoint > state.checkpoint_interval:
            checkpoint(run_dir, ms, phi_final)
            last_checkpoint = time.time()

        # ── 心跳 ──
        heartbeat(phi_final)

        # ── 长短不等的延迟 ──
        if fire_llm:
            time.sleep(3 + random.random() * 5)  # LLM后休息
        else:
            time.sleep(0.5 + random.random() * 1.5)  # 静息快速

    # ═══════════════════════════════
    # 结束
    # ═══════════════════════════════

    elapsed = time.time() - state.start_time
    print(f"\n{'═'*50}")
    print(f"  🏁 运行结束")
    print(f"  时长: {elapsed/3600:.1f}h")
    print(f"  周期: {state.cycle}")
    print(f"  LLM: {state.llm_calls}次 (失败{state.llm_fails})")
    print(f"  Tokens: {state.total_tokens}")
    print(f"  手脚: {state.limb_actions} (✅{state.limb_successes})")
    print(f"  最终 Φ: {phi_final:.2f} [{unified_phi.label.value}]")

    ms_stats = ms.get_stats()
    print(f"  情景记忆: {ms_stats['episodic_items']}条")
    print(f"  语义事实: {ms_stats['semantic_facts']}个")
    print(f"  自传时刻: {ms_stats['autobio_moments']}个")
    print(f"  巩固次数: {ms_stats['consolidations']}")
    print(f"\n{ms.get_narrative()}")

    # 最终存档
    checkpoint(run_dir, ms, phi_final)


# ═══════════════════════════════════
# 入口
# ═══════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Helios 长时运行")
    parser.add_argument("--hours", type=float, default=24, help="运行时长")
    parser.add_argument("--resume", action="store_true", help="从存档恢复")
    args = parser.parse_args()

    run(hours=args.hours, resume=args.resume)
