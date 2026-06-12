"""R85-T20 dry-run with a mock LLM that always emits a memory_save tool call.

Sanity check the end-to-end plumbing (parser -> driver -> dispatcher ->
sub-drivers -> store) before spending real LLM tokens.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HELIOS_V2 = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(HELIOS_V2 / "src"))

from helios_v2.composition.runtime_assembly import assemble_runtime
from helios_v2.llm.contracts import (
    LlmCompletion,
    LlmUsage,
    LlmProfileReadiness,
    LlmReadinessReport,
    LlmRequest,
)
from helios_v2.memory_tool_channel import (
    MemoryToolDispatcher,
    build_sub_drivers,
    default_sub_driver_deps,
)
from helios_v2.memory.store import InMemoryR85MemoryStore
from helios_v2.tests.r79d.framework import (
    ScriptedCliSource,
    inject_v3_prompt,
)


# Stimulus: 8 ticks alternating save / replay
STIMULUS = [
    "小黑说: 帮我记住明天9点有会议",
    "小黑说: 9点会议是几点的？",  # replay hint: '9点会议'
    "小黑说: 午饭12点",
    "小黑说: 午饭几点？",  # replay hint: '午饭'
    "小黑说: 我答应周三晚上请你吃饭",
    "小黑说: 我答应过你什么来着？",  # replay hint: '答应'
    "小黑说: 明天9点我提醒你",  # double-anchor save
    "小黑说: 明天9点会议是吧？",  # replay '9点会议' AGAIN -> promote
]


@dataclass
class _LlmRequestLog:
    """Mirror of helios_v2.tests.r79d.framework.LlmRequestLog for the mock."""
    request_id: str
    profile_name: str
    messages: list
    raw_response_text: str = ""
    parsed_json: dict | None = None
    error: str | None = None
    usage: dict | None = None


@dataclass
class _MockLlmGateway:
    """Returns canned text that includes a memory tool call."""
    captured: list = field(default_factory=list)
    call_count: int = 0

    def check_static_readiness(self, profile_names):
        return LlmReadinessReport(
            report_id="t20-mock",
            checked_live=False,
            entries=tuple(
                LlmProfileReadiness(
                    profile_name=n, exists=True, static_ready=True,
                    live_ready=None, detail="mock",
                ) for n in profile_names
            ),
        )

    def complete(self, request: LlmRequest) -> LlmCompletion:
        self.call_count += 1
        idx = self.call_count - 1
        if idx < len(STIMULUS) // 2:
            tool_block = (
                '```json memory_tool\n'
                '{"tool": "memory_save", '
                f'"content": "{STIMULUS[idx]}", '
                '"confidence": 0.9}\n```\n'
            )
        else:
            tool_block = (
                '```json memory_tool\n'
                '{"tool": "memory_replay", '
                f'"content": "{STIMULUS[idx].split("：")[-1]}", '
                '"confidence": 0.8}\n```\n'
            )
        body = (
            '```json\n{"what_i_feel": "happy", "remember_this": false, '
            '"i_will_send_it": false}\n```\n'
            + tool_block
        )
        # Record in the framework's LlmRequestLog shape so run_experiment-like
        # code can read raw_response_text and parsed_json.
        import json as _json
        parsed = None
        try:
            # First fenced block: the main thought JSON
            if "```json" in body:
                start = body.index("```json") + len("```json")
                end = body.index("```", start)
                parsed = _json.loads(body[start:end].strip())
        except Exception:
            parsed = None
        self.captured.append(_LlmRequestLog(
            request_id=request.request_id,
            profile_name=request.target_profile,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            raw_response_text=body,
            parsed_json=parsed,
            usage={"total_tokens": 0},
        ))
        return LlmCompletion(
            completion_id=f"mock:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="mock-dryrun",
            output_text=body,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=0.0,
        )


def main():
    print("=" * 60)
    print("R85 T20 DRY-RUN: mock LLM, real parser + dispatcher + store")
    print("=" * 60)
    gateway = _MockLlmGateway()

    handle = assemble_runtime(
        deterministic_thought=False,
        gateway=gateway,
        channel_cli=True,
        memory_tool_channel=True,
    )
    handle.startup()
    print(f"  driver: {handle.memory_tool_channel_driver.driver_id}")

    store = InMemoryR85MemoryStore()
    deps = default_sub_driver_deps(
        store=store, tick_id=0,
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6},
    )
    save_d, replay_d, forget_d = build_sub_drivers(deps=deps)
    dispatcher = MemoryToolDispatcher(
        save_driver=save_d, replay_driver=replay_d, forget_driver=forget_d
    )
    handle.memory_tool_channel_driver._dispatcher = dispatcher
    inject_v3_prompt(handle)
    handle.ingress.register_source(ScriptedCliSource(STIMULUS))

    from helios_v2.memory_tool_channel import MemoryToolIntentParser
    parser = MemoryToolIntentParser()

    t0 = time.time()
    for tick_id in range(1, len(STIMULUS) + 1):
        deps.tick_id = tick_id
        try:
            handle.tick()
        except Exception as e:
            print(f"  tick {tick_id} ERROR: {type(e).__name__}: {e}")
            break
        # Replicate the framework's T14 parse+dispatch block.
        llm = gateway.captured[-1] if gateway.captured else None
        if llm is None or not llm.raw_response_text:
            print(f"  tick {tick_id:2d}: no LLM response")
            continue
        intents = parser.parse(llm.raw_response_text, tick_id=tick_id)
        admitted = handle.memory_tool_channel_driver.set_intents(intents, tick_id=tick_id)
        results = dispatcher.dispatch(admitted) if admitted else ()
        v3 = getattr(handle, "_r79d_v3_state", None)
        if v3 is not None:
            v3["last_tool_calls"] = tuple(
                {
                    "tool": c.tool, "content": c.content,
                    "record_id_hint": c.record_id_hint,
                } for c in admitted
            )
        print(f"  tick {tick_id:2d}: intents={len(intents)} admitted={len(admitted)} store={len(store.list())}")
        for c in admitted:
            print(f"          -> {c.tool}: {c.content[:40]!r}")
        for r in results:
            print(f"          <- {r.tool}: status={r.status} record_id={r.record_id} summary={r.result_summary[:50]!r}")
    elapsed = time.time() - t0

    all_records = store.list()
    all_with_deleted = store.list(include_soft_deleted=True)
    promoted = [r for r in all_with_deleted if r.is_consolidated]
    promoted_via_recall = [
        r for r in all_with_deleted
        if r.recall_count >= 2 and r.layer == "L4_long"
    ]

    print("\n" + "=" * 60)
    print("DRY-RUN RESULT:")
    print(f"  elapsed:              {elapsed:.1f}s")
    print(f"  store_size_visible:   {len(all_records)}")
    print(f"  store_with_deleted:   {len(all_with_deleted)}")
    print(f"  promoted:             {len(promoted)}")
    print(f"  promoted_via_recall:  {len(promoted_via_recall)}")
    print("=" * 60)
    if all_records:
        print("\nStored records:")
        for r in all_records:
            print(f"  {r.record_id}: {r.layer} | recall={r.recall_count} | {r.summary!r}")
    if promoted:
        print(f"\nPromoted records (consolidated=True):")
        for r in promoted:
            print(f"  {r.record_id}: {r.layer} | recall={r.recall_count} | summary={r.summary!r}")
    return {
        "elapsed_s": elapsed,
        "store_size": len(all_records),
        "promoted": len(promoted),
    }


if __name__ == "__main__":
    main()
