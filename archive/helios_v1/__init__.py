"""Helios package public surface.

The repo currently mixes legacy modules, refactored modules, and test-only entry
paths. Importing every public symbol eagerly at package import time makes pytest
collection brittle because unrelated legacy dependencies get imported before any
tests run. To keep the package importable while preserving the public API, the
exports below are resolved lazily on first attribute access.
"""

from importlib import import_module


_EXPORTS = {
    "PankseppEmotionEngine": (".daisy_emotion", "DaisySystemEngine"),
    "AffectState": (".daisy_emotion", "AffectState"),
    "DriveOracle": (".cognition", "DriveOracle"),
    "DriveVector": (".cognition", "DriveVector"),
    "NeurochemState": (".neurochem", "NeurochemState"),
    "ThinkingManager": (".cognition", "ThinkingManager"),
    "UnifiedPhi": (".cognition", "UnifiedPhi"),
    "ConsciousnessMoment": (".cognition", "ConsciousnessMoment"),
    "PhiModulator": (".cognition", "PhiModulator"),
    "ConsciousnessDetector": (".cognition", "ConsciousnessDetector"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))

__version__ = "0.2.0"
__all__ = [
    # 情感核心
    "PankseppEmotionEngine",
    "AffectState",
    # 驱动
    "DriveOracle",
    "DriveVector",
    # 神经化学
    "NeurochemState",
    # 思考
    "ThinkingManager",
    # 意识
    "UnifiedPhi",
    "ConsciousnessMoment",
    "PhiModulator",
    "ConsciousnessDetector",
]
