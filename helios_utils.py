"""
Helios 公共工具函数

统一 clamp、数值安全等基础操作，消除模块间重复定义。
"""

import math
from typing import TypeVar

T = TypeVar("T", int, float)


def clamp(x: T, lo: T = 0.0, hi: T = 1.0) -> T:
    """将值限制在 [lo, hi] 区间"""
    return max(lo, min(hi, x))


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """安全除法，除零返回 default"""
    return a / b if abs(b) > 1e-9 else default


def lerp(a: float, b: float, t: float) -> float:
    """线性插值"""
    return a + (b - a) * clamp(t)


def sigmoid(x: float, k: float = 1.0, x0: float = 0.0) -> float:
    """Sigmoid 激活，映射到 (0,1)"""
    return 1.0 / (1.0 + math.exp(-k * (x - x0)))


def exp_decay(current: float, target: float, rate: float, dt: float = 1.0) -> float:
    """指数衰减逼近 target"""
    return target + (current - target) * math.exp(-rate * dt)


__all__ = ["clamp", "safe_div", "lerp", "sigmoid", "exp_decay"]
