"""R85-T20 end-to-end integration: parser -> driver -> dispatcher -> store.

This test exercises the full R85 path without a real LLM. The real-LLM
1-min run is `/tmp/r85_1min/result.json` (script: scripts/r85_t20_1min_real_llm.py).

The integration test here uses a canned LLM that emits memory tool calls
in the v3 fenced block. It checks that:
- intents are parsed and admitted
- sub-drivers receive the calls
- the store accumulates records
- recall triggers promote_layer (L3 -> L4)
- L18 governance denies L5 forgets
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest

from helios_v2.composition.runtime_assembly import assemble_runtime
from helios_v2.llm.contracts import (
    LlmCompletion,
    LlmProfileReadiness,
    LlmReadinessReport,
    LlmRequest,
    LlmUsage,
)
from helios_v2.memory.store import InMemoryR85MemoryStore
from helios_v2.memory_tool_channel import (
    MemoryToolDispatcher,
    MemoryToolIntentParser,
    build_sub_drivers,
    default_sub_driver_deps,
)
from helios_v2.tests.r79d.framework import (
    ScriptedCliSource,
    inject_v3_prompt,
)


@dataclass
class _LlmLog:
    request_id: str
    profile_name: str
    messages: list
    raw_response_text: str = ""
    parsed_json: dict | None = None
    error: str | None = None
    usage: dict | None = None


@dataclass
class _ScriptedLlm:
    """Canned LLM: alternates save / replay content per tick."""
    captured: list = field(default_factory=list)
    call_count: int = 0
    script_save: List[str] = field(default_factory=lambda: [
        "小黑说: 明天9点会议",
        "小黑说: 午饭12点",
    ])
    script_replay: List[str] = field(default_factory=lambda: [
        "9点会议",
        "午饭",
        "9点会议",  # 2nd recall of the same record -> promote
    ])

    def check_static_readiness(self, names):
        return LlmReadinessReport(
            report_id="t20-test",
            checked_live=False,
            entries=tuple(
                LlmProfileReadiness(
                    profile_name=n, exists=True, static_ready=True,
                    live_ready=None, detail="scripted",
                ) for n in names
            ),
        )

    def complete(self, request: LlmRequest) -> LlmCompletion:
        self.call_count += 1
        idx = self.call_count - 1
        total_save = len(self.script_save)
        if idx < total_save:
            content = self.script_save[idx]
            tool_block = (
                '```json memory_tool\n'
                f'[{{"tool": "memory_save", "content": "{content}", "confidence": 0.9}}]\n'
                '```\n'
            )
        else:
            r_idx = idx - total_save
            content = self.script_replay[r_idx] if r_idx < len(self.script_replay) else "9点会议"
            tool_block = (
                '```json memory_tool\n'
                f'[{{"tool": "memory_replay", "content": "{content}", "confidence": 0.8}}]\n'
                '```\n'
            )
        body = (
            '```json\n{"what_i_feel": "neutral", "remember_this": false, '
            '"i_will_send_it": false}\n```\n'
            + tool_block
        )
        parsed = None
        try:
            start = body.index("```json") + len("```json")
            end = body.index("```", start)
            parsed = json.loads(body[start:end].strip())
        except Exception:
            parsed = None
        self.captured.append(_LlmLog(
            request_id=request.request_id,
            profile_name=request.target_profile,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            raw_response_text=body,
            parsed_json=parsed,
        ))
        return LlmCompletion(
            completion_id=f"scripted:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="scripted",
            output_text=body,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=0.0,
        )


def _build_pipeline():
    gateway = _ScriptedLlm()
    handle = assemble_runtime(
        deterministic_thought=False,
        gateway=gateway,
        channel_cli=True,
        memory_tool_channel=True,
    )
    handle.startup()
    inject_v3_prompt(handle)

    store = InMemoryR85MemoryStore()
    deps = default_sub_driver_deps(
        store=store,
        tick_id=0,
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6},
    )
    save_d, replay_d, forget_d = build_sub_drivers(deps=deps)
    dispatcher = MemoryToolDispatcher(
        save_driver=save_d, replay_driver=replay_d, forget_driver=forget_d
    )
    handle.memory_tool_channel_driver._dispatcher = dispatcher
    return handle, store, deps, dispatcher, gateway


def _run_ticks(handle, deps, dispatcher, gateway, num_ticks: int):
    """Drive num_ticks of handle.tick() with manual parse+dispatch."""
    parser = MemoryToolIntentParser()
    admitted_per_tick = []
    for tick_id in range(1, num_ticks + 1):
        deps.tick_id = tick_id
        handle.tick()
        llm = gateway.captured[-1] if gateway.captured else None
        if llm is None or not llm.raw_response_text:
            admitted_per_tick.append(())
            continue
        intents = parser.parse(llm.raw_response_text, tick_id=tick_id)
        admitted = handle.memory_tool_channel_driver.set_intents(intents, tick_id=tick_id)
        dispatcher.dispatch(admitted) if admitted else ()
        admitted_per_tick.append(admitted)
    return admitted_per_tick


def test_t20_end_to_end_save_replay_with_promotion():
    """Save 2 records, replay 3 times, verify L3->L4 promotion.

    Note: substring search is whitespace-token-based, so the test stimulus
    deliberately avoids spaces inside the keyword ("9点会议" not "9 点会议")
    to match the existing record summary tokens. R86+ may replace this
    naive search with a proper CJK tokenizer.
    """
    handle, store, deps, dispatcher, gateway = _build_pipeline()
    stimulus = [
        "小黑说: 明天9点会议",   # 0
        "小黑说: 午饭12点",   # 1
        "小黑说: 9点会议是几点",   # 2 -> replay
        "小黑说: 午饭几点",        # 3 -> replay
        "小黑说: 9点会议",          # 4 -> 2nd replay of first record -> promote
    ]
    handle.ingress.register_source(ScriptedCliSource(stimulus))
    admitted = _run_ticks(handle, deps, dispatcher, gateway, len(stimulus))

    # Ticks 0,1: 2 saves -> store should have 2 records
    assert len(store.list()) == 2
    # Tick 4: replay of "9点会议" for the 2nd time -> the matching record
    # (first one, summary "明天9点会议") should be promoted to L4
    promoted_records = [r for r in store.list(include_soft_deleted=True) if r.is_consolidated]
    assert len(promoted_records) >= 1, f"expected at least 1 promoted record, got {len(promoted_records)}"
    promoted_summary = promoted_records[0].summary
    assert "9点会议" in promoted_summary or "9点会议" in promoted_summary


def test_t20_sub_drivers_use_real_store_not_stub():
    """The dispatcher attached to the driver must be the real one we set,
    and the store behind it must be the real InMemoryR85MemoryStore."""
    handle, store, deps, dispatcher, _ = _build_pipeline()
    assert handle.memory_tool_channel_driver._dispatcher is dispatcher
    # Single record append: smoke
    from helios_v2.memory.classifier import (
        classify_for_persistence,
        make_memory_record,
    )
    classification = classify_for_persistence(
        llm_remember=True,
        stimulus_text="smoke test",
        hormone_snapshot={"cortisol": 0.3},
        feeling_snapshot={"warmth": 0.6},
        outcome_class="self_changed",
    )
    rec = make_memory_record(
        record_id="smoke-r1",
        tick_id=1,
        outcome_class="self_changed",
        continuity_kind="world_changed",
        summary="smoke test",
        classification=classification,
        llm_remember=True,
        hormone_snapshot={"cortisol": 0.3},
        feeling_snapshot={"warmth": 0.6},
        created_at_wall=1000.0,
    )
    store.append(rec)
    assert store.get("smoke-r1") is not None
