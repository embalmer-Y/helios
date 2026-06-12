"""Owner: 31 memory_tool_channel.

Owns:
- LLM-callable memory tools (memory_save / memory_replay / memory_forget)
- Intent parsing (NL → tool call)
- Sub-driver dispatch
- Quota enforcement (max N tool calls per tick)
- Soft-delete (forget) coordination with L18 governance

Does not own:
- LLM generation (owner 25)
- MemoryRecord schema (owner 06)
- Experience writeback pipeline (owner 15)
- Channel subsystem mechanics (owner 30)
"""

from .contracts import (
    MemoryToolName,
    MemoryToolIntent,
    MemoryToolCall,
    MemoryToolResult,
    MemoryToolQuotaConfig,
    MemoryToolChannelError,
    MEMORY_TOOL_NAMES,
    MAX_TOOL_CALLS_PER_TICK,
    DEFAULT_MEMORY_TOOL_QUOTA,
)
from .engine import (
    MemoryToolIntentParser,
    MemoryToolDispatcher,
    MemoryToolChannelDriver,
    MemoryToolChannelState,
    apply_quota_and_governance,
    QuotaGate,
)

__all__ = [
    # Constants
    "MemoryToolName",
    "MEMORY_TOOL_NAMES",
    "MAX_TOOL_CALLS_PER_TICK",
    "DEFAULT_MEMORY_TOOL_QUOTA",
    # Dataclasses
    "MemoryToolIntent",
    "MemoryToolCall",
    "MemoryToolResult",
    "MemoryToolQuotaConfig",
    "MemoryToolChannelState",
    # Errors
    "MemoryToolChannelError",
    # Engine
    "MemoryToolIntentParser",
    "MemoryToolDispatcher",
    "MemoryToolChannelDriver",
    "apply_quota_and_governance",
    "QuotaGate",
]
