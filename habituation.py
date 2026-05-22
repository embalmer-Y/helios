"""
Backward-compatibility stub — real implementation moved to cognition/habituation.py

All public APIs are re-exported here so existing imports continue to work:
    from habituation import HabituationTracker, ...
"""
# Re-export everything from the new location
from cognition.habituation import *  # noqa: F401, F403
from cognition.habituation import HabituationTracker  # noqa: F401
