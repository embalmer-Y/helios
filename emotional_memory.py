"""
Backward-compatibility stub — real implementation moved to memory/emotional_memory.py

All public APIs are re-exported here so existing imports continue to work:
    from emotional_memory import EmotionalEpisode, ...
"""
# Re-export everything from the new location
from memory.emotional_memory import *  # noqa: F401, F403
