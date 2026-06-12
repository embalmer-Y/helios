"""Owner: 31 memory_tool_channel — engine.

Provides:
- MemoryToolIntentParser: extracts tool intents from LLM natural-language output
- MemoryToolDispatcher: applies quota + governance, returns a list of MemoryToolCall
- MemoryToolChannelDriver: the ChannelDriver Protocol implementation
- MemoryToolChannelState: tick-scoped state
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Mapping

from helios_v2.channel.contracts import (
    ChannelConfigField,
    ChannelConfigSnapshot,
    ChannelDriver,
    ChannelDriverDescriptor,
    ChannelDriverReadiness,
    ChannelDriverStatusReport,
    ChannelManagementResult,
    InboundDrainResult,
    InboundPacket,
    OutboundDispatchOutcome,
    OutboundPacket,
)

from .contracts import (
    DEFAULT_MEMORY_TOOL_QUOTA,
    MEMORY_TOOL_NAMES,
    MAX_TOOL_CALLS_PER_TICK,
    MemoryToolCall,
    MemoryToolChannelError,
    MemoryToolChannelState,
    MemoryToolIntent,
    MemoryToolName,
    MemoryToolQuotaConfig,
    MemoryToolResult,
)


# =============================================================================
# Intent parser
# =============================================================================

class MemoryToolIntentParser:
    """Extract MemoryToolIntent from LLM natural-language output.

    Strategy:
    1. Look for a fenced JSON block tagged `memory_tool_calls`
    2. If not found, look for inline JSON `{...}` containing a `tool` field
    3. If neither, fall back to keyword matching for the tool name (3 categories)

    Notes:
        Pure function (no I/O). Caller passes the LLM output text and the current tick_id.
        Returns a tuple of intents; empty tuple when nothing parseable.
    """

    # JSON fenced block: ```json ... ``` or ``` ... ```
    _FENCED_RE = re.compile(
        r"```(?:json)?\s*(\{[\s\S]*?\"tool\"\s*:\s*\"(?:memory_save|memory_replay|memory_forget)\"[\s\S]*?\})\s*```",
        re.MULTILINE,
    )

    # Inline JSON object containing "tool" key
    _INLINE_RE = re.compile(
        r"\{[^{}]*\"tool\"\s*:\s*\"(memory_save|memory_replay|memory_forget)\"[^{}]*\}"
    )

    def parse(self, llm_output_text: str, tick_id: int) -> tuple[MemoryToolIntent, ...]:
        """Parse LLM output for tool intents.

        Returns a tuple of MemoryToolIntent (max 8 per tick to bound).
        """
        if not llm_output_text:
            return ()

        found: list[MemoryToolIntent] = []
        seen_keys: set[tuple[str, str, str]] = set()  # dedup by (tool, content[:64], hint)

        # Strategy 1: fenced JSON block
        for m in self._FENCED_RE.finditer(llm_output_text):
            blob = m.group(1)
            intent = self._try_parse_blob(blob)
            if intent is None:
                continue
            key = (intent.tool, intent.content[:64], intent.record_id_hint or "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            found.append(intent)
            if len(found) >= 8:
                break

        if found:
            return tuple(found)

        # Strategy 2: inline JSON
        for m in self._INLINE_RE.finditer(llm_output_text):
            blob = m.group(0)
            intent = self._try_parse_blob(blob)
            if intent is None:
                continue
            key = (intent.tool, intent.content[:64], intent.record_id_hint or "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            found.append(intent)
            if len(found) >= 8:
                break

        if found:
            return tuple(found)

        # Strategy 3: keyword fallback (3 categories)
        text_lower = llm_output_text.lower()
        for keyword, tool in (
            ("save this memory", "memory_save"),
            ("save this", "memory_save"),
            ("remember this", "memory_save"),
            ("记下来", "memory_save"),
            ("记住", "memory_save"),
            ("保存", "memory_save"),
            ("replay this", "memory_replay"),
            ("recall this", "memory_replay"),
            ("回想", "memory_replay"),
            ("调取", "memory_replay"),
            ("forget this", "memory_forget"),
            ("delete this", "memory_forget"),
            ("forget it", "memory_forget"),
            ("忘记", "memory_forget"),
            ("删除", "memory_forget"),
        ):
            if keyword in text_lower:
                found.append(MemoryToolIntent(
                    tool=tool,  # type: ignore[arg-type]
                    record_id_hint=None,
                    content=llm_output_text.strip()[:512],
                    confidence=0.4,  # keyword fallback is low confidence
                ))
                if len(found) >= 8:
                    break

        return tuple(found)

    def _try_parse_blob(self, blob: str) -> MemoryToolIntent | None:
        """Try to parse a JSON blob as a MemoryToolIntent. Returns None on any failure."""
        try:
            obj = json.loads(blob)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(obj, dict):
            return None
        tool = obj.get("tool")
        if tool not in MEMORY_TOOL_NAMES:
            return None
        content = obj.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        record_id_hint = obj.get("record_id")
        if record_id_hint is not None and not isinstance(record_id_hint, str):
            record_id_hint = str(record_id_hint)
        confidence = obj.get("confidence", 0.7)
        if not isinstance(confidence, (int, float)):
            confidence = 0.7
        try:
            return MemoryToolIntent(
                tool=tool,  # type: ignore[arg-type]
                record_id_hint=record_id_hint,
                content=content,
                confidence=float(confidence),
            )
        except MemoryToolChannelError:
            return None


# =============================================================================
# Quota gate
# =============================================================================

@dataclass(frozen=True)
class QuotaGate:
    """Result of the quota+governance gate.

    Attributes:
        admitted: tool calls that may dispatch
        skipped_quota: dropped because over quota
        skipped_governance: dropped because L18 governance denied
    """
    admitted: tuple[MemoryToolCall, ...]
    skipped_quota: tuple[MemoryToolIntent, ...] = ()
    skipped_governance: tuple[MemoryToolIntent, ...] = ()


def apply_quota_and_governance(
    intents: tuple[MemoryToolIntent, ...],
    *,
    tick_id: int,
    quota: MemoryToolQuotaConfig = DEFAULT_MEMORY_TOOL_QUOTA,
    check_forget_permission: object = None,  # L18 gate; signature: (intent) -> bool
) -> QuotaGate:
    """Apply quota + governance, return admitted calls + skipped intents.

    Sort order: forget first (priority 0), then save/replay in confidence order.

    Args:
        intents: parsed intents from parser
        tick_id: which tick
        quota: per-tick cap
        check_forget_permission: optional L18 gate; signature (intent) -> bool
    """
    if not intents:
        return QuotaGate(admitted=())

    # Sort: forget first (priority 0), then save/replay by confidence desc
    def sort_key(i: MemoryToolIntent) -> tuple[int, float]:
        if i.tool == "memory_forget":
            return (0, -i.confidence)
        return (1, -i.confidence)

    sorted_intents = sorted(intents, key=sort_key)

    admitted: list[MemoryToolCall] = []
    skipped_quota: list[MemoryToolIntent] = []
    skipped_governance: list[MemoryToolIntent] = []
    forget_count = 0
    total_count = 0

    for i, intent in enumerate(sorted_intents):
        # Governance gate (forget only)
        if intent.tool == "memory_forget" and check_forget_permission is not None:
            try:
                allowed = bool(check_forget_permission(intent))
            except Exception:
                allowed = False
            if not allowed:
                skipped_governance.append(intent)
                continue

        # Quota
        if total_count >= quota.max_calls_per_tick:
            skipped_quota.append(intent)
            continue
        if intent.tool == "memory_forget" and forget_count >= quota.max_forget_per_tick:
            skipped_quota.append(intent)
            continue

        priority = 0 if intent.tool == "memory_forget" else 100
        call = MemoryToolCall(
            call_id=f"memory-tool-call:{tick_id}:{i}",
            tick_id=tick_id,
            tool=intent.tool,
            record_id_hint=intent.record_id_hint,
            content=intent.content.strip(),
            priority=priority,
        )
        admitted.append(call)
        total_count += 1
        if intent.tool == "memory_forget":
            forget_count += 1

    return QuotaGate(
        admitted=tuple(admitted),
        skipped_quota=tuple(skipped_quota),
        skipped_governance=tuple(skipped_governance),
    )


# =============================================================================
# Channel driver
# =============================================================================

DRIVER_ID = "memory_tool_channel"


class MemoryToolChannelDriver:
    """ChannelDriver Protocol implementation for owner 31.

    The driver holds:
    - the parsed intents for the current tick (set via `set_intents`)
    - the quota config
    - the last tick's results (for status / config_snapshot)
    - the L18 forget-permission gate (callable)

    Note: This driver is a *sink* for LLM intents (outbound-only) — it accepts
    intents from the LLM layer via set_intents, applies quota + governance,
    and produces a list of `MemoryToolCall` (consumed by the dispatcher later).
    For the ChannelDriver Protocol we still implement drain_inbound / send_outbound
    so the driver can be registered with the channel subsystem.
    """

    def __init__(
        self,
        *,
        quota: MemoryToolQuotaConfig | None = None,
        check_forget_permission=None,
    ) -> None:
        self._quota = quota or DEFAULT_MEMORY_TOOL_QUOTA
        self._check_forget_permission = check_forget_permission
        self._intents_this_tick: tuple[MemoryToolIntent, ...] = ()
        self._state = MemoryToolChannelState(
            tick_id=0,
            intents_emitted=0,
            calls_dispatched=0,
            calls_skipped_quota=0,
            calls_skipped_governance=0,
        )

    # --- ChannelDriver protocol ---

    @property
    def driver_id(self) -> str:
        return DRIVER_ID

    def descriptor(self) -> ChannelDriverDescriptor:
        return ChannelDriverDescriptor(
            driver_id=DRIVER_ID,
            display_name="Memory Tool Channel (R85 mandatory driver)",
            directions=("outbound",),
            output_ops=("memory_save", "memory_replay", "memory_forget"),
            management_ops=("set_quota",),
            config_fields=(
                ChannelConfigField(
                    key="max_calls_per_tick",
                    description="Hard cap on tool calls per tick (default 3)",
                    required=False,
                    mutable_at_runtime=True,
                    schema_hint="int",
                ),
                ChannelConfigField(
                    key="max_forget_per_tick",
                    description="Cap on forget calls per tick (default 1)",
                    required=False,
                    mutable_at_runtime=True,
                    schema_hint="int",
                ),
            ),
            health_signals=("intents_emitted", "calls_dispatched", "calls_skipped_quota"),
        )

    def apply_management_op(
        self,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        if op_name == "set_quota":
            if payload is None:
                return ChannelManagementResult(
                    driver_id=DRIVER_ID,
                    op_name=op_name,
                    success=False,
                    status="error",
                    message="set_quota requires payload",
                    error_code="missing_payload",
                )
            try:
                self._quota = MemoryToolQuotaConfig(
                    max_calls_per_tick=int(payload.get("max_calls_per_tick", self._quota.max_calls_per_tick)),  # type: ignore[arg-type]
                    max_forget_per_tick=int(payload.get("max_forget_per_tick", self._quota.max_forget_per_tick)),  # type: ignore[arg-type]
                    forget_priority=bool(payload.get("forget_priority", self._quota.forget_priority)),
                )
            except (MemoryToolChannelError, TypeError, ValueError) as e:
                return ChannelManagementResult(
                    driver_id=DRIVER_ID,
                    op_name=op_name,
                    success=False,
                    status="error",
                    message=f"set_quota failed: {e}",
                    error_code="invalid_quota",
                )
            return ChannelManagementResult(
                driver_id=DRIVER_ID,
                op_name=op_name,
                success=True,
                status="connected",
                message=f"quota updated: {self._quota}",
            )
        return ChannelManagementResult(
            driver_id=DRIVER_ID,
            op_name=op_name,
            success=False,
            status="error",
            message=f"unknown op: {op_name}",
            error_code="unknown_op",
        )

    def status(self) -> ChannelDriverStatusReport:
        s = self._state
        return ChannelDriverStatusReport(
            driver_id=DRIVER_ID,
            status="connected",
            connected=True,
            pending_inbound=0,
            health={
                "last_tick_id": s.tick_id,
                "intents_emitted": s.intents_emitted,
                "calls_dispatched": s.calls_dispatched,
                "calls_skipped_quota": s.calls_skipped_quota,
                "calls_skipped_governance": s.calls_skipped_governance,
            },
        )

    def config_snapshot(self) -> ChannelConfigSnapshot:
        return ChannelConfigSnapshot(
            driver_id=DRIVER_ID,
            status="connected",
            config_values={
                "max_calls_per_tick": self._quota.max_calls_per_tick,
                "max_forget_per_tick": self._quota.max_forget_per_tick,
                "forget_priority": self._quota.forget_priority,
            },
            mutable_fields=("max_calls_per_tick", "max_forget_per_tick", "forget_priority"),
        )

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        # Memory tool channel is outbound-only; inbound is always empty
        return InboundDrainResult(
            driver_id=DRIVER_ID,
            packets=(),
            pending_remaining=0,
            overflow_count=0,
        )

    def send_outbound(self, packet: OutboundPacket) -> OutboundDispatchOutcome:
        # Accept and ack; the dispatcher will pull the calls separately
        return OutboundDispatchOutcome(
            packet_id=packet.packet_id,
            driver_id=DRIVER_ID,
            status="delivered",
            message="memory_tool_channel accepts packet; dispatcher pulls from intents",
        )

    def static_readiness(self) -> ChannelDriverReadiness:
        return ChannelDriverReadiness(
            driver_id=DRIVER_ID,
            ready=True,
            detail="memory_tool_channel is a pure in-process driver; no network",
        )

    # --- Memory tool specifics ---

    def set_intents(
        self,
        intents: tuple[MemoryToolIntent, ...],
        *,
        tick_id: int,
    ) -> tuple[MemoryToolCall, ...]:
        """Set the current tick's intents and apply quota + governance.

        Returns the list of admitted MemoryToolCall (ready to dispatch).
        Updates the driver's internal state.
        """
        gate = apply_quota_and_governance(
            intents,
            tick_id=tick_id,
            quota=self._quota,
            check_forget_permission=self._check_forget_permission,
        )
        self._intents_this_tick = intents
        self._state = MemoryToolChannelState(
            tick_id=tick_id,
            intents_emitted=len(intents),
            calls_dispatched=len(gate.admitted),
            calls_skipped_quota=len(gate.skipped_quota),
            calls_skipped_governance=len(gate.skipped_governance),
        )
        return gate.admitted

    def last_state(self) -> MemoryToolChannelState:
        return self._state


# =============================================================================
# Dispatcher
# =============================================================================

class MemoryToolDispatcher:
    """Dispatch admitted MemoryToolCall to the appropriate sub-driver.

    For R85, the dispatcher is a thin router: it calls one of three sub-drivers
    (save / replay / forget) and collects the results.

    Sub-drivers are injected as callables taking (MemoryToolCall) -> MemoryToolResult.
    """

    def __init__(
        self,
        *,
        save_driver=None,
        replay_driver=None,
        forget_driver=None,
    ) -> None:
        self._save = save_driver
        self._replay = replay_driver
        self._forget = forget_driver

    def dispatch(self, calls: tuple[MemoryToolCall, ...]) -> tuple[MemoryToolResult, ...]:
        out: list[MemoryToolResult] = []
        for call in sorted(calls, key=lambda c: c.priority):  # priority 0 first
            driver = self._select_driver(call.tool)
            if driver is None:
                out.append(MemoryToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    status="error",
                    error_reason=f"no sub-driver registered for {call.tool}",
                ))
                continue
            try:
                result = driver(call)
            except Exception as e:
                out.append(MemoryToolResult(
                    call_id=call.call_id,
                    tool=call.tool,
                    status="error",
                    error_reason=f"sub-driver raised: {type(e).__name__}: {e}",
                ))
                continue
            out.append(result)
        return tuple(out)

    def _select_driver(self, tool: MemoryToolName):
        if tool == "memory_save":
            return self._save
        if tool == "memory_replay":
            return self._replay
        if tool == "memory_forget":
            return self._forget
        return None
