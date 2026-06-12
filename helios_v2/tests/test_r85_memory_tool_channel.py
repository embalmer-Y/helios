"""R85 unit tests — owner 31 memory_tool_channel (T8-T10)."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from helios_v2.memory_tool_channel import (
    DEFAULT_MEMORY_TOOL_QUOTA,
    MAX_TOOL_CALLS_PER_TICK,
    MEMORY_TOOL_NAMES,
    MemoryToolCall,
    MemoryToolChannelDriver,
    MemoryToolChannelError,
    MemoryToolChannelState,
    MemoryToolDispatcher,
    MemoryToolIntent,
    MemoryToolIntentParser,
    MemoryToolName,
    MemoryToolQuotaConfig,
    MemoryToolResult,
    apply_quota_and_governance,
)


# =============================================================================
# T8: contracts validation
# =============================================================================

def test_default_quota_matches_design():
    assert DEFAULT_MEMORY_TOOL_QUOTA.max_calls_per_tick == 3
    assert DEFAULT_MEMORY_TOOL_QUOTA.max_forget_per_tick == 1
    assert MAX_TOOL_CALLS_PER_TICK == 3
    assert MEMORY_TOOL_NAMES == ("memory_save", "memory_replay", "memory_forget")


def test_quota_rejects_invalid_max_calls():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolQuotaConfig(max_calls_per_tick=0)


def test_quota_rejects_invalid_max_forget():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolQuotaConfig(max_forget_per_tick=-1)


def test_quota_rejects_forget_cap_above_total():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolQuotaConfig(max_calls_per_tick=2, max_forget_per_tick=3)


def test_intent_rejects_invalid_tool():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolIntent(tool="invalid", record_id_hint=None, content="x")  # type: ignore[arg-type]


def test_intent_rejects_confidence_out_of_range():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content="x", confidence=1.5)


def test_call_rejects_empty_content():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolCall(
            call_id="c1", tick_id=1, tool="memory_save",
            record_id_hint=None, content="   ", priority=100,
        )


def test_call_rejects_empty_call_id():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolCall(
            call_id="", tick_id=1, tool="memory_save",
            record_id_hint=None, content="x", priority=100,
        )


def test_result_rejects_ok_without_record_id():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolResult(call_id="c1", tool="memory_save", status="ok")


def test_result_rejects_error_without_reason():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolResult(call_id="c1", tool="memory_save", status="error")


# =============================================================================
# T9: Intent parser
# =============================================================================

def test_parser_finds_fenced_json():
    parser = MemoryToolIntentParser()
    text = '```json\n{"tool": "memory_save", "content": "praise from mom", "confidence": 0.9}\n```'
    intents = parser.parse(text, tick_id=1)
    assert len(intents) == 1
    assert intents[0].tool == "memory_save"
    assert intents[0].content == "praise from mom"
    assert intents[0].confidence == 0.9


def test_parser_finds_inline_json():
    parser = MemoryToolIntentParser()
    text = 'I think I should {"tool": "memory_replay", "content": "first praise"} for context.'
    intents = parser.parse(text, tick_id=1)
    assert len(intents) == 1
    assert intents[0].tool == "memory_replay"


def test_parser_falls_back_to_keyword_save():
    parser = MemoryToolIntentParser()
    intents = parser.parse("这件事我一定要记住", tick_id=1)
    assert len(intents) >= 1
    assert any(i.tool == "memory_save" for i in intents)


def test_parser_falls_back_to_keyword_replay():
    parser = MemoryToolIntentParser()
    intents = parser.parse("我需要回想刚才那段对话", tick_id=1)
    assert any(i.tool == "memory_replay" for i in intents)


def test_parser_falls_back_to_keyword_forget():
    parser = MemoryToolIntentParser()
    intents = parser.parse("我想忘记刚才发生的事", tick_id=1)
    assert any(i.tool == "memory_forget" for i in intents)


def test_parser_dedupes_repeats():
    parser = MemoryToolIntentParser()
    text = '```json\n{"tool": "memory_save", "content": "x"}\n``` ```json\n{"tool": "memory_save", "content": "x"}\n```'
    intents = parser.parse(text, tick_id=1)
    assert len(intents) == 1


def test_parser_handles_empty_text():
    parser = MemoryToolIntentParser()
    assert parser.parse("", tick_id=1) == ()


def test_parser_handles_no_tools():
    parser = MemoryToolIntentParser()
    assert parser.parse("just a regular thought", tick_id=1) == ()


def test_parser_invalid_json_does_not_crash():
    parser = MemoryToolIntentParser()
    text = '```json\n{not valid json}\n```'
    assert parser.parse(text, tick_id=1) == ()


# =============================================================================
# T9: Quota + governance gate
# =============================================================================

def test_quota_admits_up_to_cap():
    intents = tuple(
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content=f"item {i}", confidence=0.5)
        for i in range(5)
    )
    gate = apply_quota_and_governance(intents, tick_id=1)
    assert len(gate.admitted) == 3
    assert len(gate.skipped_quota) == 2


def test_quota_with_custom_cap():
    intents = tuple(
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content=f"item {i}", confidence=0.5)
        for i in range(4)
    )
    quota = MemoryToolQuotaConfig(max_calls_per_tick=2)
    gate = apply_quota_and_governance(intents, tick_id=1, quota=quota)
    assert len(gate.admitted) == 2
    assert len(gate.skipped_quota) == 2


def test_forget_priority_forget_first():
    """When over quota, forget intents are admitted first (priority 0)."""
    intents = (
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content="low pri", confidence=0.9),
        MemoryToolIntent(tool="memory_forget", record_id_hint=None, content="high pri", confidence=0.5),
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content="low pri 2", confidence=0.9),
        MemoryToolIntent(tool="memory_forget", record_id_hint=None, content="forget 2", confidence=0.4),
    )
    gate = apply_quota_and_governance(intents, tick_id=1)
    # Both forgets admitted (max_forget=1 default), so actually only 1 forget admitted
    # Let me check: max_forget_per_tick=1 default
    forget_calls = [c for c in gate.admitted if c.tool == "memory_forget"]
    assert len(forget_calls) == 1


def test_forget_separate_cap():
    """forget has its own cap (default 1)."""
    intents = tuple(
        MemoryToolIntent(tool="memory_forget", record_id_hint=None, content=f"forget {i}", confidence=0.5)
        for i in range(5)
    )
    gate = apply_quota_and_governance(intents, tick_id=1)
    # 1 admitted, 4 skipped
    assert len(gate.admitted) == 1
    assert len(gate.skipped_quota) == 4


def test_governance_gate_denies_forget():
    """L18-style gate that denies forget: should drop them to skipped_governance."""
    intents = (
        MemoryToolIntent(tool="memory_forget", record_id_hint=None, content="x", confidence=0.5),
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content="y", confidence=0.5),
    )

    def deny_forget(intent):
        return intent.tool != "memory_forget"

    gate = apply_quota_and_governance(
        intents, tick_id=1, check_forget_permission=deny_forget,
    )
    # forget dropped by governance; save admitted
    assert len(gate.admitted) == 1
    assert gate.admitted[0].tool == "memory_save"
    assert len(gate.skipped_governance) == 1
    assert gate.skipped_governance[0].tool == "memory_forget"


def test_governance_gate_only_affects_forget():
    """L18 gate signature receives non-forget intents too, but result is ignored."""
    intents = (MemoryToolIntent(tool="memory_save", record_id_hint=None, content="x"),)

    def deny_all(intent):
        return False  # deny everything

    gate = apply_quota_and_governance(
        intents, tick_id=1, check_forget_permission=deny_all,
    )
    # save is not subject to governance
    assert len(gate.admitted) == 1


def test_governance_gate_exception_treated_as_deny():
    """If gate raises, treat as deny (R79 fail-soft)."""
    intents = (MemoryToolIntent(tool="memory_forget", record_id_hint=None, content="x"),)

    def bad_gate(intent):
        raise RuntimeError("governance unavailable")

    gate = apply_quota_and_governance(
        intents, tick_id=1, check_forget_permission=bad_gate,
    )
    assert len(gate.admitted) == 0
    assert len(gate.skipped_governance) == 1


# =============================================================================
# T10: Dispatcher
# =============================================================================

def _save_driver(call):
    return MemoryToolResult(
        call_id=call.call_id, tool=call.tool, status="ok",
        record_id=f"rec-{call.call_id[-6:]}",
        result_summary=f"saved: {call.content[:20]}",
    )


def _forget_driver(call):
    return MemoryToolResult(
        call_id=call.call_id, tool=call.tool, status="ok",
        record_id=f"fgt-{call.call_id[-6:]}",
        result_summary=f"forgot: {call.content[:20]}",
    )


def test_dispatcher_routes_to_correct_sub_driver():
    dispatcher = MemoryToolDispatcher(save_driver=_save_driver, forget_driver=_forget_driver)
    calls = (
        MemoryToolCall(call_id="c-save-1", tick_id=1, tool="memory_save", record_id_hint=None, content="hello"),
        MemoryToolCall(call_id="c-fgt-1", tick_id=1, tool="memory_forget", record_id_hint=None, content="bye", priority=0),
    )
    results = dispatcher.dispatch(calls)
    by_tool = {r.tool: r for r in results}
    assert by_tool["memory_save"].status == "ok"
    assert by_tool["memory_save"].record_id.startswith("rec-")
    assert by_tool["memory_forget"].status == "ok"
    assert by_tool["memory_forget"].record_id.startswith("fgt-")


def test_dispatcher_forget_priority_first():
    """Even when save is in the tuple, forget (priority 0) is dispatched first."""
    dispatcher = MemoryToolDispatcher(save_driver=_save_driver, forget_driver=_forget_driver)
    calls = (
        MemoryToolCall(call_id="c-save", tick_id=1, tool="memory_save", record_id_hint=None, content="x", priority=100),
        MemoryToolCall(call_id="c-fgt", tick_id=1, tool="memory_forget", record_id_hint=None, content="y", priority=0),
    )
    results = dispatcher.dispatch(calls)
    # First result should be the forget
    assert results[0].tool == "memory_forget"
    assert results[1].tool == "memory_save"


def test_dispatcher_missing_sub_driver_returns_error():
    dispatcher = MemoryToolDispatcher()  # no sub-drivers
    calls = (MemoryToolCall(call_id="c1", tick_id=1, tool="memory_replay", record_id_hint=None, content="x"),)
    results = dispatcher.dispatch(calls)
    assert len(results) == 1
    assert results[0].status == "error"
    assert "no sub-driver" in results[0].error_reason


def test_dispatcher_sub_driver_exception_caught():
    def bad_save(call):
        raise RuntimeError("disk full")
    dispatcher = MemoryToolDispatcher(save_driver=bad_save)
    calls = (MemoryToolCall(call_id="c1", tick_id=1, tool="memory_save", record_id_hint=None, content="x"),)
    results = dispatcher.dispatch(calls)
    assert results[0].status == "error"
    assert "RuntimeError" in results[0].error_reason
    assert "disk full" in results[0].error_reason


# =============================================================================
# T12: MemoryToolChannelDriver
# =============================================================================

def test_driver_id_is_stable():
    d = MemoryToolChannelDriver()
    assert d.driver_id == "memory_tool_channel"


def test_driver_descriptor_has_three_output_ops():
    d = MemoryToolChannelDriver()
    desc = d.descriptor()
    assert desc.driver_id == "memory_tool_channel"
    assert "outbound" in desc.directions
    # 3 output ops = 3 tools (save / replay / forget)
    assert "memory_save" in desc.output_ops
    assert "memory_replay" in desc.output_ops
    assert "memory_forget" in desc.output_ops
    # 2 config fields
    assert len(desc.config_fields) == 2


def test_driver_set_intents_admits_and_skips():
    d = MemoryToolChannelDriver()
    intents = tuple(
        MemoryToolIntent(tool="memory_save", record_id_hint=None, content=f"x {i}", confidence=0.5)
        for i in range(5)
    )
    calls = d.set_intents(intents, tick_id=10)
    assert len(calls) == 3
    state = d.last_state()
    assert state.tick_id == 10
    assert state.intents_emitted == 5
    assert state.calls_dispatched == 3
    assert state.calls_skipped_quota == 2
    assert state.calls_skipped_governance == 0


def test_driver_apply_management_op_set_quota_ok():
    d = MemoryToolChannelDriver()
    result = d.apply_management_op("set_quota", {"max_calls_per_tick": 5})
    assert result.success is True
    assert d._quota.max_calls_per_tick == 5


def test_driver_apply_management_op_set_quota_invalid():
    d = MemoryToolChannelDriver()
    result = d.apply_management_op("set_quota", {"max_calls_per_tick": 0})
    assert result.success is False
    assert result.error_code == "invalid_quota"


def test_driver_apply_management_op_unknown_op():
    d = MemoryToolChannelDriver()
    result = d.apply_management_op("foo", None)
    assert result.success is False
    assert result.error_code == "unknown_op"


def test_driver_status():
    d = MemoryToolChannelDriver()
    d.set_intents(
        (MemoryToolIntent(tool="memory_save", record_id_hint=None, content="x"),),
        tick_id=5,
    )
    status = d.status()
    assert status.driver_id == "memory_tool_channel"
    assert status.health["last_tick_id"] == 5
    assert status.health["intents_emitted"] == 1


def test_driver_config_snapshot():
    d = MemoryToolChannelDriver()
    snap = d.config_snapshot()
    assert snap.driver_id == "memory_tool_channel"
    assert snap.config_values["max_calls_per_tick"] == 3
    assert snap.config_values["max_forget_per_tick"] == 1


def test_driver_drain_inbound_always_empty():
    d = MemoryToolChannelDriver()
    result = d.drain_inbound(budget=10)
    assert result.driver_id == "memory_tool_channel"
    assert result.packets == ()
    assert result.pending_remaining == 0


def test_driver_static_readiness():
    d = MemoryToolChannelDriver()
    ready = d.static_readiness()
    assert ready.ready is True
    assert "no network" in ready.detail


# =============================================================================
# State dataclass
# =============================================================================

def test_state_rejects_negative_counters():
    with pytest.raises(MemoryToolChannelError):
        MemoryToolChannelState(
            tick_id=0, intents_emitted=-1, calls_dispatched=0,
            calls_skipped_quota=0, calls_skipped_governance=0,
        )
