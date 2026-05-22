"""
Backward-compatibility stub — real implementation moved to cognition/emotions.py

All public APIs are re-exported here so existing imports continue to work:
    from emotions import PankseppEmotionEngine, AffectState, ...
"""
# Re-export everything from the new location
from cognition.emotions import *  # noqa: F401, F403
