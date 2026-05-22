"""
Backward-compatibility stub — real implementation moved to cognition/agent_awareness.py

All public APIs are re-exported here so existing imports continue to work:
    from agent_awareness import AgentAwareness, ...
"""
# Re-export everything from the new location
from cognition.agent_awareness import *  # noqa: F401, F403
