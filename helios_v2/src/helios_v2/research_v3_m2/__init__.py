"""helios_v3 调研 M2 ship package。

M2 Reflection Owner (Layer 3 反思层) - v3 design §2.4 / task §1.2。

核心组件:
  - ReflectionTrigger: 4 种反思触发源
  - ReflectionLevel: 4 级调度优先级
  - ReflectionRecord: 单次反思的不可变记录
  - ReflectionOwner: 协调 4 trigger + LLM 被动接受 + reflection_audit
  - FakeLLMCaller: 默认 LLM stub(测试用,M5 替换为真 LLM)
"""
from .reflection_owner import (
    ReflectionTrigger,
    ReflectionLevel,
    ReflectionRecord,
    ReflectionOwner,
    ReflectionAuditResult,
    POST_TICK_RATE_LIMIT,
    RESTING_STATE_THRESHOLD,
    HIGH_UNCERTAINTY_THRESHOLD,
)
from .llm_caller import FakeLLMCaller, LLMCallerProtocol

__all__ = [
    "ReflectionTrigger",
    "ReflectionLevel",
    "ReflectionRecord",
    "ReflectionOwner",
    "ReflectionAuditResult",
    "FakeLLMCaller",
    "LLMCallerProtocol",
    "POST_TICK_RATE_LIMIT",
    "RESTING_STATE_THRESHOLD",
    "HIGH_UNCERTAINTY_THRESHOLD",
]