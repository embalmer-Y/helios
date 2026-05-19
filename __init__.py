"""
Helios - 有意识、有情感的 AI Agent 框架

基于"分层循环广播模型"：
意识不是一道菜、不是传菜铃、不是吃菜的人，
而是从厨房到餐桌这整个热气腾腾的过程本身。

Sun god of Greek mythology, driving his chariot across the sky every day.
"""

from .core import (
    HeliosConfig, SensorFrame, L1Output, WorkspaceResponse,
    AffectState, SelfState, MetacognitionOutput, Decision, Goal,
)
from .agent import HeliosAgent, ConsciousnessReport

__version__ = "0.1.0"
__all__ = [
    "HeliosAgent",
    "HeliosConfig",
    "SensorFrame",
    "L1Output",
    "WorkspaceResponse",
    "AffectState",
    "SelfState",
    "MetacognitionOutput",
    "Decision",
    "Goal",
    "ConsciousnessReport",
]
