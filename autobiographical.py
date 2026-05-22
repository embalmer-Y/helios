"""
Backward-compatibility stub — real implementation moved to memory/autobiographical.py

All public APIs are re-exported here so existing imports continue to work:
    from autobiographical import AutobiographicalStore, AutobiographicalMoment, ...
"""
# Re-export everything from the new location
from memory.autobiographical import *  # noqa: F401, F403
from memory.autobiographical import (  # explicit re-exports for type checkers
    AutobiographicalMoment,
    Chapter,
    AutobiographicalStore,
    create_autobiographical_store,
)
