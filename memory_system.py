"""
Backward-compatibility stub — real implementation moved to memory/memory_system.py

All public APIs are re-exported here so existing imports continue to work:
    from memory_system import MemorySystem, WorkingMemory, EpisodicMemory, ...
"""
# Re-export everything from the new location
from memory.memory_system import *  # noqa: F401, F403
from memory.memory_system import (  # explicit re-exports for type checkers
    MemoryItem,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    AutobiographicalMemory,
    MemoryConsolidator,
    MemoryRetriever,
    MemorySystem,
    EmotionalEpisodicMemory,
    clamp,
    safe_div,
)
