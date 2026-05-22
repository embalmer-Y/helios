"""
Backward-compatibility stub — real implementation moved to regulation/regulation.py

All public APIs are re-exported here so existing imports continue to work:
    from regulation import RegulationEngine, ActionCandidate, ...
"""
# Re-export everything from the new location
from regulation.regulation import *  # noqa: F401, F403
from regulation.regulation import (  # explicit re-exports for type checkers
    RegulationEngine,
    RegulationMemory,
    ActionCandidate,
)
