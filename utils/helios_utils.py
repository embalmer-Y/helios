"""Canonical shared utility functions for Helios."""

import math
from typing import TypeVar


T = TypeVar("T", int, float)


def clamp(x: T, lo: T = 0.0, hi: T = 1.0) -> T:
	"""Clamp a value into the inclusive [lo, hi] interval."""
	return max(lo, min(hi, x))


def safe_div(a: float, b: float, default: float = 0.0) -> float:
	"""Safely divide, returning default when the denominator is near zero."""
	return a / b if abs(b) > 1e-9 else default


def lerp(a: float, b: float, t: float) -> float:
	"""Linear interpolation."""
	return a + (b - a) * clamp(t)


def sigmoid(x: float, k: float = 1.0, x0: float = 0.0) -> float:
	"""Sigmoid activation mapped into (0, 1)."""
	return 1.0 / (1.0 + math.exp(-k * (x - x0)))


def exp_decay(current: float, target: float, rate: float, dt: float = 1.0) -> float:
	"""Exponentially decay current toward target."""
	return target + (current - target) * math.exp(-rate * dt)


__all__ = ["clamp", "safe_div", "lerp", "sigmoid", "exp_decay"]