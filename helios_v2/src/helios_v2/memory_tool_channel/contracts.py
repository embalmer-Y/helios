"""Owner: 31 memory_tool_channel — contracts.

Defines:
- 3 LLM-callable memory tool names
- Intent, call, result dataclasses
- Quota config
- Error class

All dataclasses use frozen=True + post_init validation (R79 fail-fast convention).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

# =============================================================================
# Constants
# =============================================================================

MemoryToolName = Literal["memory_save", "memory_replay", "memory_forget"]

MEMORY_TOOL_NAMES: tuple[MemoryToolName, ...] = (
    "memory_save",
    "memory_replay",
    "memory_forget",
)

# Quota: even if LLM emits 10 tool calls in one tick, only 3 are dispatched
MAX_TOOL_CALLS_PER_TICK: int = 3


class MemoryToolChannelError(ValueError):
    """Raised on any contract violation in owner 31."""


# =============================================================================
# Quota config
# =============================================================================

@dataclass(frozen=True)
class MemoryToolQuotaConfig:
    """Per-tick quota for memory tool calls.

    Attributes:
        max_calls_per_tick: hard cap (default 3 per design §6.4)
        forget_priority: when over-quota, the forget tool is always allowed (governance)
        max_forget_per_tick: separate cap for forget (default 1)
    """
    max_calls_per_tick: int = MAX_TOOL_CALLS_PER_TICK
    forget_priority: bool = True
    max_forget_per_tick: int = 1

    def __post_init__(self) -> None:
        if self.max_calls_per_tick < 1:
            raise MemoryToolChannelError(
                f"max_calls_per_tick must be >= 1, got {self.max_calls_per_tick}"
            )
        if self.max_forget_per_tick < 0:
            raise MemoryToolChannelError(
                f"max_forget_per_tick must be >= 0, got {self.max_forget_per_tick}"
            )
        if self.max_forget_per_tick > self.max_calls_per_tick:
            raise MemoryToolChannelError(
                f"max_forget_per_tick ({self.max_forget_per_tick}) must be <= max_calls_per_tick ({self.max_calls_per_tick})"
            )


DEFAULT_MEMORY_TOOL_QUOTA = MemoryToolQuotaConfig()


# =============================================================================
# Intent: parsed LLM-natural-language output for one tool
# =============================================================================

@dataclass(frozen=True)
class MemoryToolIntent:
    """One parsed intent emitted by the LLM in a given tick.

    Attributes:
        tool: which tool
        record_id_hint: optional id (used by replay/forget to reference a target)
        content: free-form text payload (save: memory content; replay: query; forget: reason)
        confidence: LLM self-reported confidence in [0, 1]
    """
    tool: MemoryToolName
    record_id_hint: str | None
    content: str
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if self.tool not in MEMORY_TOOL_NAMES:
            raise MemoryToolChannelError(
                f"MemoryToolIntent tool must be one of {MEMORY_TOOL_NAMES}, got {self.tool!r}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise MemoryToolChannelError(
                f"MemoryToolIntent confidence must be in [0, 1], got {self.confidence}"
            )


# =============================================================================
# Call: a tool invocation that has passed quota + parsing
# =============================================================================

@dataclass(frozen=True)
class MemoryToolCall:
    """A tool call that has been validated, quota-cleared, and is ready to dispatch.

    Attributes:
        call_id: stable id (typically f"memory-tool-call:{tick_id}:{n}")
        tick_id: which tick
        tool: which tool
        record_id_hint: from intent
        content: from intent (always non-empty after validation)
        priority: dispatch priority (lower = earlier); forget is 0
    """
    call_id: str
    tick_id: int
    tool: MemoryToolName
    record_id_hint: str | None
    content: str
    priority: int = 100

    def __post_init__(self) -> None:
        if not self.call_id:
            raise MemoryToolChannelError("MemoryToolCall call_id must be non-empty")
        if self.tick_id < 0:
            raise MemoryToolChannelError(
                f"MemoryToolCall tick_id must be >= 0, got {self.tick_id}"
            )
        if self.tool not in MEMORY_TOOL_NAMES:
            raise MemoryToolChannelError(
                f"MemoryToolCall tool must be one of {MEMORY_TOOL_NAMES}, got {self.tool!r}"
            )
        if not self.content.strip():
            raise MemoryToolChannelError(
                "MemoryToolCall content must be non-empty after stripping"
            )


# =============================================================================
# Result: tool dispatch outcome
# =============================================================================

@dataclass(frozen=True)
class MemoryToolResult:
    """Outcome of one tool dispatch.

    Attributes:
        call_id: which call this is the result of
        tool: which tool
        status: ok / skipped / error
        record_id: created or touched record id (save/forget); replayed record id (replay)
        result_summary: human-readable summary
        error_reason: when status == "error"
    """
    call_id: str
    tool: MemoryToolName
    status: Literal["ok", "skipped", "error"]
    record_id: str | None = None
    result_summary: str = ""
    error_reason: str = ""

    def __post_init__(self) -> None:
        if not self.call_id:
            raise MemoryToolChannelError("MemoryToolResult call_id must be non-empty")
        if self.tool not in MEMORY_TOOL_NAMES:
            raise MemoryToolChannelError(
                f"MemoryToolResult tool must be one of {MEMORY_TOOL_NAMES}, got {self.tool!r}"
            )
        if self.status not in ("ok", "skipped", "error"):
            raise MemoryToolChannelError(
                f"MemoryToolResult status must be 'ok'/'skipped'/'error', got {self.status!r}"
            )
        if self.status == "ok" and not self.record_id:
            raise MemoryToolChannelError(
                "MemoryToolResult with status=ok must carry a non-empty record_id"
            )
        if self.status == "error" and not self.error_reason:
            raise MemoryToolChannelError(
                "MemoryToolResult with status=error must carry a non-empty error_reason"
            )


# =============================================================================
# Channel state (for status / config_snapshot)
# =============================================================================

@dataclass(frozen=True)
class MemoryToolChannelState:
    """Per-tick runtime state of the memory tool channel.

    Attributes:
        tick_id: most recent tick that touched this state
        intents_emitted: total parsed intents this tick
        calls_dispatched: calls that passed quota
        calls_skipped_quota: calls dropped due to quota
        calls_skipped_governance: calls dropped by L18 governance (forget only)
        last_results: tuple of recent results (bounded at quota size)
    """
    tick_id: int
    intents_emitted: int
    calls_dispatched: int
    calls_skipped_quota: int
    calls_skipped_governance: int
    last_results: tuple[MemoryToolResult, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.tick_id < 0:
            raise MemoryToolChannelError(
                f"MemoryToolChannelState tick_id must be >= 0, got {self.tick_id}"
            )
        if self.intents_emitted < 0 or self.calls_dispatched < 0:
            raise MemoryToolChannelError("intents/calls counters must be >= 0")
        if self.calls_skipped_quota < 0 or self.calls_skipped_governance < 0:
            raise MemoryToolChannelError("skipped counters must be >= 0")
        # Freeze the tuple
        object.__setattr__(self, "last_results", tuple(self.last_results))
