"""
Backward-compatibility stub — real implementation moved to regulation/conation.py

All public APIs are re-exported here so existing imports continue to work:
    from conation import IntentType, ...
"""
# Re-export everything from the new location
from regulation.conation import *  # noqa: F401, F403
