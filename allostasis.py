"""
Backward-compatibility stub — real implementation moved to regulation/allostasis.py

All public APIs are re-exported here so existing imports continue to work:
    from allostasis import AllostaticRegulator, AllostasisConfig, ...
"""
# Re-export everything from the new location
from regulation.allostasis import *  # noqa: F401, F403
from regulation.allostasis import (  # explicit re-exports for type checkers
    AllostaticRegulator,
    AllostasisConfig,
)
