"""
Helios Phase 8 — LLM 决策 ↔ Limb 执行桥接层
══════════════════════════════════════════

将 Helios 的 LLM 思考输出（"我想探索"、"我想表达"）映射为
具体的 ActionIntent，通过 limb.py 的安全规则和手脚执行，
然后将 ActionResult 反馈回神经化学层。

核心流:
  LLM think → Decision dict → ActionIntent → Limb.execute()
      └─ neurochem event ←── ActionResult ← safety rules ←─┘
"""

import os
import time
from typing import Dict, Any, Optional, Tuple

from limb import (
    ActionIntent, ActionResult,
    HeliosBody, create_shell_limb,
    CommandAllowlistRule, RateLimitRule, DryRunRule,
)
from neurochem import NeurochemState, apply_event, EVENT_TRIGGERS


# ═══════════════════════════════════════════════
# 决策 → ActionIntent 映射
# ═══════════════════════════════════════════════

# LLM 决策类型 → (domain, verb, target_generator)
DECISION_MAP = {
    "observe": {
        "domain": "file",
        "verb": "list",
        "target": "journal/",
        "desc": "审视日记目录",
    },
    "explore": {
        "domain": "file",
        "verb": "list",
        "target": ".",
        "desc": "探索文件系统",
    },
    "express": {
        "domain": "file",
        "verb": "write",
        "target": None,  # 动态: journal/YYYY-MM-DD_HHMM.md
        "desc": "向日记倾诉",
    },
    "withdraw": {
        "domain": None,
        "verb": None,
        "target": None,
        "desc": "暂时退缩静养",
    },
    "approach": {
        "domain": "file",
        "verb": "write",
        "target": None,  # 动态: journal/creation_HHMMSS.txt
        "desc": "靠近并创造",
    },
}


def build_intent(decision: Dict, valence: float, drive_name: str,
                 emotion_dominant: str = "",
                 language_output: str = "") -> Optional[ActionIntent]:
    """
    将 LLM 决策翻译为 ActionIntent。

    Args:
        decision: LLM 返回的 decision dict (type, reason)
        valence: 当前情感效价 (-1~1)
        drive_name: 当前主导驱动名
        emotion_dominant: 当前主导情感系统

    Returns:
        ActionIntent 或 None (如果决策不需执行动作)
    """
    dtype = decision.get("type", "observe").lower()
    reason = decision.get("reason", "")

    entry = DECISION_MAP.get(dtype)
    if entry is None:
        return None

    domain = entry["domain"]
    verb = entry["verb"]

    # withdraw 不需要执行
    if domain is None or verb is None:
        return None

    target = entry["target"]

    # 动态 target
    if target is None:
        if verb == "write":
            ts = time.strftime("%Y-%m-%d_%H%M")
            target = f"journal/{ts}.md"
        elif verb == "list" and entry.get("desc", "") == "探索文件系统":
            if valence > 0.3:
                target = "journal/"
            else:
                target = "."
        else:
            target = "journal/"
    elif target is None:
        target = "."

    params = {
        "reason": reason,
        "emotion": emotion_dominant,
        "drive": drive_name,
    }
    # 写入操作：带上 Helios 的语言输出作为内容
    if verb == "write":
        params["content"] = language_output[:500]

    # 优先级：积极情绪 + 主导驱动 = 高优先级
    priority = 0.5 + 0.2 * max(0, valence) + 0.1 * (1 if drive_name else 0)

    return ActionIntent(
        domain=domain,
        verb=verb,
        target=target,
        params=params,
        priority=clamp(priority, 0.1, 1.0),
        source_drive=drive_name,
        source_emotion=emotion_dominant,
    )


from helios_utils import clamp


# ═══════════════════════════════════════════════
# 执行结果 → 神经化学反馈
# ═══════════════════════════════════════════════

def feed_result_to_neurochem(result: ActionResult, nc: NeurochemState) -> str:
    """
    将 ActionResult 转换为 neurochem 事件。

    Returns:
        反馈摘要字符串
    """
    event = result.neurochem_event or ("task_success" if result.success else "task_failure")

    # 获取事件值用于显示
    triggers = {k: v for k, v in EVENT_TRIGGERS.get(event, {}).items()}

    # 应用神经化学调制
    apply_event(nc, event)

    da_d = triggers.get("dopamine", 0)
    op_d = triggers.get("opioids", 0)
    cort_d = triggers.get("cortisol", 0)

    if result.success:
        return (f"✅ {result.limb_name}: {result.output[:100] if result.output else 'ok'} "
                f"(DA{da_d:+.0%} OP{op_d:+.0%})")
    else:
        return (f"❌ {result.limb_name}: {result.error[:100]} "
                f"(CORT{cort_d:+.0%})")


# ═══════════════════════════════════════════════
# 主桥接函数
# ═══════════════════════════════════════════════

def execute_decision(decision: Dict, body: HeliosBody, nc: NeurochemState,
                     valence: float, drive_name: str,
                     emotion_dominant: str = "",
                     language_output: str = "") -> Tuple[Optional[ActionResult], str]:
    """
    Phase 8 核心桥接：决策 → 执行 → 反馈

    Args:
        decision: LLM 返回的 decision dict
        body: HeliosBody 实例（已注册手脚）
        nc: 神经化学状态
        valence: 当前效价
        drive_name: 主导驱动
        emotion_dominant: 主导情感系统
        language_output: Helios 的 LLM 语言输出（用于表达型写入）

    Returns:
        (ActionResult or None, 人类可读的反馈行)
    """
    intent = build_intent(decision, valence, drive_name, emotion_dominant, language_output)
    if intent is None:
        return None, f"  🧘 决策 '{decision.get('type','?')}' 不需执行动作"

    # 执行
    result = body.act(intent)

    # 反馈到神经化学
    feedback = feed_result_to_neurochem(result, nc)

    # 生成人类可读行
    icon = "🔧" if result.success else "⚠️"
    desc = DECISION_MAP.get(decision.get("type", "").lower(), {}).get("desc", decision.get("type", "?"))
    line = f"  {icon} {desc} → {feedback}"

    return result, line


# ═══════════════════════════════════════════════
# Helios 身体工厂
# ═══════════════════════════════════════════════

def create_helios_body(work_dir: str = "/home/radxa/project/helios") -> HeliosBody:
    """
    为 Helios 创建安全配置的身体。

    包含:
    - shell 手脚 (sh, 受限)
    - 安全规则: 命令白名单, 路径控制, 频率限制
    """
    body = HeliosBody()

    # 核心 shell 手脚
    shell = create_shell_limb(work_dir=work_dir)

    # 严格安全规则
    shell.add_safety_rule(
        CommandAllowlistRule(allowed_commands=["ls", "list", "cat", "head", "tail", "wc",
                                                "echo", "printf", "date", "whoami",
                                                "uname", "uptime", "touch", "mkdir", "write",
                                                "find", "grep", "pwd", "stat", "read"],
                             blocked_commands=["rm", "wget", "curl", "chmod", "chown"]))

    shell.add_safety_rule(RateLimitRule(max_per_minute=20))
    shell.add_safety_rule(
        DryRunRule(risky_verbs=["rm", "delete", "drop"]))

    body.router.register(shell)

    return body


