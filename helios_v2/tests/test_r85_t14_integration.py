"""R85-C T14 integration tests: v3 prompt extension + intent dispatcher.

12 tests covering:
- v3 prompt section constant exists and is non-empty
- v3 prompt section includes fenced-JSON + Chinese keyword fallback
- AggressiveRadicalEmbodiedPromptPath appends section when flag=True
- v3 prompt omits section when flag=False
- v3 prompt omits section when flag absent
- MemoryToolIntentParser parses fenced JSON correctly
- MemoryToolIntentParser parses Chinese keyword fallback
- TickRecord has tool_calls + tool_results fields
- TickRecord defaults to empty tool calls/results
- v3 build_messages includes tool-call section when present
- v3 build_messages omits tool-call section when empty
- end-to-end: opt-in driver + parser + dispatch (no LLM)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest


# =============================================================================
# Test 1-2: v3 prompt section constant
# =============================================================================


def test_t14_v3_section_constant_exists():
    """The R85 memory-tool section constant exists in prompt_contract.engine."""
    from helios_v2.prompt_contract.engine import _R85_MEMORY_TOOL_PROMPT_SECTION

    text = _R85_MEMORY_TOOL_PROMPT_SECTION
    assert "memory_save" in text
    assert "memory_replay" in text
    assert "memory_forget" in text
    assert 200 <= len(text) <= 3000


def test_t14_v3_section_includes_json_and_chinese_fallback():
    """Section includes both fenced-JSON example and Chinese keyword fallback."""
    from helios_v2.prompt_contract.engine import _R85_MEMORY_TOOL_PROMPT_SECTION

    text = _R85_MEMORY_TOOL_PROMPT_SECTION
    assert "```json" in text
    assert "记住" in text
    assert "回想" in text
    assert "忘记" in text


# =============================================================================
# Test 3-5: AggressiveRadicalEmbodiedPromptPath appends section based on flag
# =============================================================================


def _make_request(*, flag_value, request_id):
    """Build a minimal EmbodiedPromptRequest with the given memory_tool_channel_enabled flag."""
    from helios_v2.prompt_contract.contracts import EmbodiedPromptRequest

    cap = {
        "available_channels": ("cli",),
        "available_ops": ("reply_message",),
        "forbidden_capabilities": ("direct_execution", "invented_channel"),
    }
    if flag_value != "absent":
        cap["memory_tool_channel_enabled"] = (flag_value == "true")

    return EmbodiedPromptRequest(
        request_id=request_id,
        consumer_kind="thought",
        source_conscious_state_id="c1",
        source_gate_result_id="g1",
        source_retrieval_bundle_id="b1",
        stimulus_summary={"present_field": "test"},
        state_summary={
            "affective_summary": "neutral",
            "continuation_summary": "low",
        },
        retrieval_summary={
            "retrieval_context": "short-term",
            "continuity_context": "preserve",
        },
        capability_summary=cap,
        identity_boundary_summary={"identity_boundary": "preserved"},
        tick_id=1,
    )


def _build_config():
    from helios_v2.prompt_contract.contracts import EmbodiedPromptConfig

    return EmbodiedPromptConfig(
        max_layer_count=8,
        prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )


def test_t14_prompt_appends_section_when_flag_true():
    from helios_v2.prompt_contract.engine import AggressiveRadicalEmbodiedPromptPath

    path = AggressiveRadicalEmbodiedPromptPath()
    request = _make_request(flag_value="true", request_id="r1")
    config = _build_config()
    contract = path.build(request, config)
    full = "\n".join(layer.content for layer in contract.layers)
    assert "memory_save" in full
    assert "Memory tools (R85)" in full


def test_t14_prompt_omits_section_when_flag_false():
    from helios_v2.prompt_contract.engine import AggressiveRadicalEmbodiedPromptPath

    path = AggressiveRadicalEmbodiedPromptPath()
    request = _make_request(flag_value="false", request_id="r2")
    config = _build_config()
    contract = path.build(request, config)
    full = "\n".join(layer.content for layer in contract.layers)
    assert "Memory tools (R85)" not in full


def test_t14_prompt_omits_section_when_flag_absent():
    from helios_v2.prompt_contract.engine import AggressiveRadicalEmbodiedPromptPath

    path = AggressiveRadicalEmbodiedPromptPath()
    request = _make_request(flag_value="absent", request_id="r3")
    config = _build_config()
    contract = path.build(request, config)
    full = "\n".join(layer.content for layer in contract.layers)
    assert "Memory tools (R85)" not in full


# =============================================================================
# Test 6-7: Intent parser produces correct intents from LLM output
# =============================================================================


def test_t14_intent_parser_fenced_json():
    from helios_v2.memory_tool_channel import MemoryToolIntentParser

    parser = MemoryToolIntentParser()
    raw = (
        '```json\n{"what_i_feel": "happy"}\n```\n'
        '```json memory_tool\n'
        '[{"tool": "memory_save", "content": "first meeting", "confidence": 0.9},'
        ' {"tool": "memory_replay", "content": "the user", "confidence": 0.7}]\n'
        '```\n'
    )
    intents = parser.parse(raw, tick_id=42)
    assert len(intents) == 2
    assert intents[0].tool == "memory_save"
    assert intents[0].content == "first meeting"
    assert intents[1].tool == "memory_replay"


def test_t14_intent_parser_chinese_keywords():
    from helios_v2.memory_tool_channel import MemoryToolIntentParser

    parser = MemoryToolIntentParser()
    raw = "我想把这个记下来: 用户第一次叫我的名字\n回想: 之前的对话\n"
    intents = parser.parse(raw, tick_id=1)
    tools = {i.tool for i in intents}
    assert "memory_save" in tools or "memory_replay" in tools


# =============================================================================
# Test 8-9: TickRecord has the new fields
# =============================================================================


def test_t14_tickrecord_has_tool_fields():
    from helios_v2.tests.r79d.framework import TickRecord

    rec = TickRecord(
        tick_id=1,
        stimulus_text="hi",
        hormone_state={},
        feeling_state={},
        salience={},
        llm_output={},
        delta={},
        tool_calls=({"tool": "memory_save", "content": "x"},),
        tool_results=({"tool": "memory_save", "status": "ok"},),
    )
    assert len(rec.tool_calls) == 1
    assert rec.tool_calls[0]["tool"] == "memory_save"
    assert len(rec.tool_results) == 1
    assert rec.tool_results[0]["status"] == "ok"


def test_t14_tickrecord_default_empty():
    from helios_v2.tests.r79d.framework import TickRecord

    rec = TickRecord(
        tick_id=1,
        stimulus_text="hi",
        hormone_state={},
        feeling_state={},
        salience={},
        llm_output={},
        delta={},
    )
    assert rec.tool_calls == ()
    assert rec.tool_results == ()


# =============================================================================
# Test 10-11: v3_build_messages includes/omits tool-call summary
# =============================================================================


def _make_continuation_state():
    from helios_v2.thought_gating.contracts import ContinuationPressureState

    return ContinuationPressureState(
        active=False,
        level=0.0,
        origin_thought_id="",
        reason="",
        expires_at_tick=0,
        carry_count=0,
    )


def _make_bundle():
    from helios_v2.directed_retrieval.contracts import (
        ThoughtWindowBundle,
        RetrievalSelectionTrace,
    )

    selection_traces = tuple(
        RetrievalSelectionTrace(
            tier_name=tier,
            candidate_count=0,
            selected_count=0,
            query_source="compact_stimuli",
        )
        for tier in ("short_term", "mid_term", "long_term", "autobiographical")
    )
    return ThoughtWindowBundle(
        bundle_id="b1",
        source_plan_id="p1",
        short_term_context=(),
        mid_term_hits=(),
        long_term_hits=(),
        autobiographical_hits=(),
        selection_trace=selection_traces,
        retrieval_sec_trace=(),
        tick_id=1,
    )


def test_t14_v3_build_messages_with_tool_calls():
    from helios_v2.tests.r79d.framework import inject_v3_prompt
    from helios_v2.llm.contracts import LlmMessage, LlmRequest

    @dataclass
    class _DummyHandle:
        _r79d_v3_state: dict = field(default_factory=dict)

    h = _DummyHandle()
    h._r79d_v3_state = {"last_result": None, "last_tool_calls": ()}
    inject_v3_prompt(h, v3_prompt_text="system prompt here")
    h._r79d_v3_state["last_tool_calls"] = (
        {"tool": "memory_save", "content": "the user said hi"},
    )
    bundle = _make_bundle()
    request = LlmRequest(
        request_id="r1",
        target_profile="r85-test",
        messages=[LlmMessage(role="user", content="hello")],
    )
    import helios_v2.internal_thought.engine as ite
    fn = ite.LlmBackedInternalThoughtPath._build_messages
    continuation_state = _make_continuation_state()
    msgs = fn(None, request, bundle, continuation_state)
    user_msg = next((m for m in msgs if m.role == "user"), None)
    assert user_msg is not None
    assert "Memory tool calls admitted last tick" in user_msg.content
    assert "memory_save" in user_msg.content
    assert "the user said hi" in user_msg.content


def test_t14_v3_build_messages_no_tool_calls():
    from helios_v2.tests.r79d.framework import inject_v3_prompt
    from helios_v2.llm.contracts import LlmMessage, LlmRequest

    @dataclass
    class _DummyHandle:
        _r79d_v3_state: dict = field(default_factory=dict)

    h = _DummyHandle()
    h._r79d_v3_state = {"last_result": None, "last_tool_calls": ()}
    inject_v3_prompt(h, v3_prompt_text="system prompt")
    bundle = _make_bundle()
    request = LlmRequest(
        request_id="r2",
        target_profile="r85-test",
        messages=[LlmMessage(role="user", content="hello")],
    )
    import helios_v2.internal_thought.engine as ite
    fn = ite.LlmBackedInternalThoughtPath._build_messages
    continuation_state = _make_continuation_state()
    msgs = fn(None, request, bundle, continuation_state)
    user_msg = next((m for m in msgs if m.role == "user"), None)
    assert user_msg is not None
    assert "Memory tool calls admitted last tick" not in user_msg.content


# =============================================================================
# Test 12: end-to-end pipeline (parser → driver → dispatch, no LLM)
# =============================================================================


def test_t14_end_to_end_parser_driver_dispatch():
    """Full pipeline: parse LLM text → set_intents → dispatch via dispatcher."""
    from helios_v2.memory_tool_channel import (
        MemoryToolIntentParser,
        MemoryToolChannelDriver,
        MemoryToolDispatcher,
        MemoryToolResult,
    )

    # Sub-drivers are functions: f(call) -> MemoryToolResult
    def _save_driver(call):
        return MemoryToolResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            record_id=f"rec-{call.call_id[-6:]}",
            result_summary=f"saved: {call.content[:20]}",
        )

    def _replay_driver(call):
        return MemoryToolResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            record_id=f"replay-{call.call_id[-6:]}",
            result_summary=f"replayed: {call.content[:20]}",
        )

    dispatcher = MemoryToolDispatcher(
        save_driver=_save_driver,
        replay_driver=_replay_driver,
    )

    driver = MemoryToolChannelDriver(quota=None, check_forget_permission=None)
    driver._dispatcher = dispatcher  # type: ignore[attr-defined]

    parser = MemoryToolIntentParser()
    raw = (
        '```json memory_tool\n'
        '{"tool": "memory_save", "content": "xiaohei is back", "confidence": 0.9}\n'
        '```'
    )
    intents = parser.parse(raw, tick_id=1)
    assert len(intents) == 1
    assert intents[0].tool == "memory_save"

    calls = driver.set_intents(intents, tick_id=1)
    assert len(calls) == 1
    assert calls[0].tool == "memory_save"

    results = dispatcher.dispatch(calls)
    assert len(results) == 1
    assert results[0].tool == "memory_save"
    assert results[0].status == "ok"
    assert results[0].record_id.startswith("rec-")
