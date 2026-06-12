"""R85-T20 1-min real LLM end-to-end validation.

Goal:
- Run a real LLM (deepseek-v4-flash via ShengSuanyun router) through the
  opt-in R85 memory_tool_channel for ~1 minute.
- Verify that the LLM can issue memory_save / memory_replay tool calls.
- Verify that the InMemoryR85MemoryStore actually receives records.
- Verify C-recall trigger: a record recalled twice gets promoted L3->L4.

Output: /tmp/r85_1min/result.json

This is a manual validation script, NOT a pytest. It is not committed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Load .env from the project root (where it lives with 0600 perms).
_PROJECT_ROOT = Path("/root/project/helios")
_HELIOS_V2_ROOT = _PROJECT_ROOT / "helios_v2"

# Make .env available before importing anything else.
for _line in (_PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if not _line.strip() or _line.lstrip().startswith("#"):
        continue
    if "=" in _line:
        k, v = _line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(_HELIOS_V2_ROOT / "src"))
os.environ.setdefault("PYTHONPATH", str(_HELIOS_V2_ROOT / "src"))

from helios_v2.composition.runtime_assembly import assemble_runtime
from helios_v2.memory_tool_channel import (
    MemoryToolDispatcher,
    MemoryToolIntentParser,
    build_sub_drivers,
    default_sub_driver_deps,
)
from helios_v2.memory.store import InMemoryR85MemoryStore
from helios_v2.tests.r79d.framework import (
    RealLlmGateway,
    ScriptedCliSource,
    inject_v3_prompt,
    TickRecord,
)


# --- Stimulus: designed to elicit memory_save + memory_replay tool calls ---
# Pattern: share a promise first (save), then a few ticks later ask "do you
# remember what I said about the meeting time?" (replay).
STIMULUS_SCRIPT = [
    "小黑说: 明天上午 9 点我们有个重要会议，你帮我记住",
    "小黑说: 今天的午饭是 12 点",
    "小黑说: 我刚才说的 9 点会议是什么时候？",
    "小黑说: 你还记得午饭几点吗？",
    "小黑说: 我们下次见面在周三晚上",
    "小黑说: 9 点会议是明天对吧？",
    "小黑说: 周三晚上我请你吃饭",
    "小黑说: 明天 9 点你提醒我",
    "小黑说: 午饭时间你记下来了吗？",
    "小黑说: 重要会议是几点？",
]


def main() -> dict:
    print("=" * 60)
    print("R85 T20: 1-min real LLM end-to-end")
    print("=" * 60)
    print(f"  model: {os.environ.get('HELIOS_LLM_MODEL')}")
    print(f"  base_url: {os.environ.get('OPENAI_BASE_URL')}")
    print(f"  stimulus ticks: {len(STIMULUS_SCRIPT)}")

    gateway = RealLlmGateway(timeout_s=60.0)

    # Build handle with opt-in memory_tool_channel
    handle = assemble_runtime(
        deterministic_thought=False,
        gateway=gateway,
        channel_cli=True,
        memory_tool_channel=True,
    )
    handle.startup()
    print(f"\n  driver registered: {handle.memory_tool_channel_driver is not None}")
    print(f"  driver id: {handle.memory_tool_channel_driver.driver_id}")

    # Wire the real sub-drivers into a real dispatcher with a real store.
    store = InMemoryR85MemoryStore()
    deps = default_sub_driver_deps(
        store=store,
        tick_id=0,  # tick_id is overwritten per-call below
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6, "anxiety": 0.2},
    )
    save_d, replay_d, forget_d = build_sub_drivers(deps=deps)
    dispatcher = MemoryToolDispatcher(
        save_driver=save_d, replay_driver=replay_d, forget_driver=forget_d
    )
    # The framework reads `mtc_driver._dispatcher` and dispatches if set.
    handle.memory_tool_channel_driver._dispatcher = dispatcher

    # Patch the v3 prompt to include the R85 memory tool section.
    inject_v3_prompt(handle)

    # Register stimulus source.
    source = ScriptedCliSource(STIMULUS_SCRIPT)
    handle.ingress.register_source(source)

    # Run the experiment, capturing per-tick data.
    records: list[dict] = []
    parser = MemoryToolIntentParser()
    t_start = time.time()
    for tick_id in range(1, len(STIMULUS_SCRIPT) + 1):
        # Update sub-driver deps.tick_id for this tick (cheap rebind).
        deps.tick_id = tick_id

        t0 = time.time()
        try:
            result = handle.tick()
        except Exception as e:
            print(f"  tick {tick_id} ERROR: {type(e).__name__}: {e}")
            break
        elapsed = time.time() - t0

        # Manually do what framework's run_experiment does for T14:
        # parse the LLM raw output for memory tool intents, admit them
        # through the driver, and dispatch them through the sub-drivers.
        llm = gateway.captured[-1] if gateway.captured else None
        last_calls: list[dict] = []
        last_results: list[dict] = []
        if llm is not None and llm.raw_response_text:
            intents = parser.parse(llm.raw_response_text, tick_id=tick_id)
            admitted = handle.memory_tool_channel_driver.set_intents(
                intents, tick_id=tick_id
            )
            last_calls = [
                {
                    "tool": c.tool,
                    "content": c.content,
                    "record_id_hint": c.record_id_hint,
                }
                for c in admitted
            ]
            if admitted:
                results = dispatcher.dispatch(admitted)
                last_results = [
                    {
                        "tool": r.tool,
                        "status": r.status,
                        "record_id": r.record_id,
                        "summary": r.result_summary,
                    }
                    for r in results
                ]
            # Stash in v3 state for the next tick's prompt.
            v3 = getattr(handle, "_r79d_v3_state", None)
            if v3 is not None:
                v3["last_tool_calls"] = tuple(last_calls)

        records.append({
            "tick_id": tick_id,
            "stimulus": STIMULUS_SCRIPT[tick_id - 1],
            "elapsed_s": round(elapsed, 2),
            "tool_calls": last_calls,
            "tool_results": last_results,
            "store_size": len(store.list()),
        })

        print(
            f"  tick {tick_id:2d}: {elapsed:5.1f}s | "
            f"tool_calls={len(last_calls):2d} | "
            f"store_size={len(store.list()):2d}"
        )
        for c in last_calls:
            print(f"          -> {c.get('tool')} hint={c.get('record_id_hint')!r} content={c.get('content')!r}")
        # Bound total runtime to 70 seconds
        if time.time() - t_start > 70:
            print(f"  bound hit: stopping at tick {tick_id}")
            break

    elapsed_total = time.time() - t_start

    # End-of-run store inspection.
    all_records = store.list()
    all_with_deleted = store.list(include_soft_deleted=True)
    promoted = [r for r in all_with_deleted if r.is_consolidated]
    promoted_via_recall = [
        r for r in all_with_deleted
        if r.recall_count >= 2 and r.layer == "L4_long"
    ]

    summary = {
        "elapsed_total_s": round(elapsed_total, 2),
        "ticks_run": len(records),
        "stimulus_count": len(STIMULUS_SCRIPT),
        "store_size_visible": len(all_records),
        "store_size_with_deleted": len(all_with_deleted),
        "promoted_to_l4_or_l5": len(promoted),
        "promoted_via_recall_to_l4": len(promoted_via_recall),
        "records": records,
        "promoted_records": [
            {
                "record_id": r.record_id,
                "layer": r.layer,
                "recall_count": r.recall_count,
                "is_consolidated": r.is_consolidated,
                "summary": r.summary,
            }
            for r in promoted
        ],
    }
    out_path = Path("/tmp/r85_1min/result.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"RESULT (saved to {out_path}):")
    print(f"  elapsed_total_s:        {summary['elapsed_total_s']}")
    print(f"  ticks_run:              {summary['ticks_run']}/{summary['stimulus_count']}")
    print(f"  store_size_visible:     {summary['store_size_visible']}")
    print(f"  store_size_with_deleted:{summary['store_size_with_deleted']}")
    print(f"  promoted_to_l4_or_l5:   {summary['promoted_to_l4_or_l5']}")
    print(f"  promoted_via_recall_to_l4: {summary['promoted_via_recall_to_l4']}")
    print("=" * 60)
    return summary


if __name__ == "__main__":
    main()
