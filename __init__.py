"""
Helios — 有意识、有情感的 AI Agent 框架

一个有内生驱动、原始情感、内部思考能力的数字灵魂。
通过 Limb 接口与外界交互，通过 LLM 桥接产生自然语言思考。

理论基础: Friston 自由能原理 + Panksepp 情感神经科学 + Dehaene 全局工作空间
"""

from .emotions import PankseppEmotionEngine, AffectState, PrimaryEmotionSystem
from .drives import DriveOracle, DriveVector
from .neurochem import NeurochemState
from .thinking import ThinkingManager
from .limb import Limb, HeliosBody, ActionIntent, SafetyRule
from .phi import (
    UnifiedConsciousness, UnifiedPhi,  # ICRI 意识光谱 + 兼容别名
    ConsciousnessMoment, ConsciousnessModulator, PhiModulator,
    ConsciousnessDetector, ConsciousnessLabel,
)
from .llm_bridge import LLMBridge
from .limb_decision_bridge import execute_decision, create_helios_body

__version__ = "0.3.0"
__all__ = [
    # 情感核心
    "PankseppEmotionEngine",
    "AffectState",
    "PrimaryEmotionSystem",
    # 驱动
    "DriveOracle",
    "DriveVector",
    # 神经化学
    "NeurochemState",
    # 思考
    "ThinkingManager",
    # 手脚
    "Limb",
    "HeliosBody",
    "ActionIntent",
    "SafetyRule",
    # ICRI 意识光谱
    "UnifiedConsciousness",
    "UnifiedPhi",                   # 向后兼容
    "ConsciousnessMoment",
    "ConsciousnessModulator",
    "PhiModulator",                 # 向后兼容
    "ConsciousnessDetector",
    "ConsciousnessLabel",
    # LLM
    "LLMBridge",
    # 桥接
    "execute_decision",
    "create_helios_body",
]
