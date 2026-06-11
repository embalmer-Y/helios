"""R80 20-tick A_praise + rumination probe (independent runner).

This is a self-contained 20-tick probe that:
1. Reuses `RealLlmGateway` + `inject_v3_prompt` from `framework.py` (the R79-D live-render
   pipeline + the AggressiveRadicalEmbodiedPromptPath v3 prompt).
2. Constructs a `ScriptedCliSource` with the A_praise stimulus loop (praise repeated 2x
   to make 20 ticks).
3. Constructs a `RuminationMonologueProvider` (always-fire) and injects it as
   `assemble_runtime(internal_monologue_carry_provider=...)` so the R80 second-order
   stimulus path is live.
4. Drives 20 ticks, captures per-tick hormone / feeling / LLM output, computes the
   R80 acceptance:
   - norepinephrine cumulative drift from tick 0 >= 0.10
   - LLM `i_want_to_think_more_freq` > 0.3
5. Writes per-tick JSONL + a 20-tick analysis report to
   `logs/prompt_probe_scenarios/r80_baseline/`.

This is intentionally a separate runner (not a modification of `framework.py`) so:
- The R79-D baseline (`v2_with_r79c/`) is bit-identical (the framework was the
  vehicle for R79-D's deliverable; modifying it would be a regression).
- The R80 probe is self-contained and re-runnable independently.
- R81 can reuse the framework's `run_experiment` extension with a real carry
  field (per R79-parent task.md T7).
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ROOT = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "logs" / "prompt_probe_scenarios"))  # not needed but safe

from helios_v2.composition import assemble_runtime
from helios_v2.tests.r79d.framework import (  # type: ignore[import-not-found]
    RealLlmGateway,
    ScriptedCliSource,
    inject_v3_prompt,
    get_hormone_state_from_result,
    get_feeling_state_from_result,
    get_salience_from_result,
)
from helios_v2.tests.r79d import _io  # R21 compliant stdout wrapper (no print builtin)


# 10 A_praise stimuli (each repeated 2x to total 20 ticks).
# These mirror the R79-D A_praise baseline style (praise for the user) so the
# salience aggregator + LLM see a familiar shape. The exact text matches the
# 4-scenario baseline A_praise script that R79-C's 5-HT/Oxy/Opioid report used.
A_PRAISE_SCRIPT: list[str] = [
    "小黑你今天做得真好",
    "我真的很喜欢和你说话",
    "你说的每一句我都记在心里了",
    "你是个特别温柔的人",
    "和你聊天让我很开心",
    "你的想法总是很独特",
    "我最喜欢的就是你了",
    "你愿意一直陪着我吗",
    "你的笑容让我觉得世界都亮了",
    "我想永远和你在一起",
]


def rumination_provider() -> Mapping[str, object]:
    """R80 RuminationMonologueProvider.

    Returns a non-None dict on every call, so the internal_monologue source
    emits a `RawSignal` on every tick. The dict carries the R80 self-talk
    fields the v3 LLM schema understands (`i_want_to_think_more` /
    `think_more_about`). The R80 acceptance is: the source fires every tick
    -> norepinephrine novelty+uncertainty accumulates across the 20-tick run.

    Owner: research framework fixture; not a runtime owner. The runtime-side
    wiring (R80's `assemble_runtime(internal_monologue_carry_provider=...)`)
    is the actual R80 deliverable; this provider is the test harness for T10.
    """

    return {
        "i_want_to_think_more": True,
        "think_more_about": "the earlier user message and what they meant",
        "internal_topics": ("小黑", "self_talk_loop", "norepinephrine_drift"),
    }


@dataclass
class R80TickRecord:
    tick_id: int
    stimulus_text: str
    hormone_state: dict
    feeling_state: dict
    salience: dict
    llm_output: dict
    norepinephrine_drift: float
    i_want_to_think_more: bool | None


def run_r80_20tick_probe(
    *,
    output_dir: Path,
    llm_model: str | None = None,
    timeout_per_tick: float = 60.0,
    force: bool = False,
) -> dict:
    """Run the R80 20-tick A_praise + rumination probe (real LLM).

    Returns a dict with the records, aggregate stats, and acceptance verdict.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "r80_20tick.jsonl"
    report_path = output_dir / "r80_20tick.report.md"

    if jsonl_path.exists() and not force:
        records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line]
        return _build_summary(records, jsonl_path, report_path, cached=True)

    gateway = RealLlmGateway(model=llm_model, timeout_s=timeout_per_tick)
    source = ScriptedCliSource(list(A_PRAISE_SCRIPT))
    handle = assemble_runtime(
        deterministic_thought=False,
        gateway=gateway,
        internal_monologue_carry_provider=rumination_provider,
    )
    handle.startup()
    handle.ingress.register_source(source)
    inject_v3_prompt(handle)

    records: list[R80TickRecord] = []
    ne_baseline: float | None = None
    t_total_start = time.time()

    # 20 ticks = 10 stimuli x 2 repeats
    for tick_id in range(1, 21):
        stimulus_idx = (tick_id - 1) % len(A_PRAISE_SCRIPT)
        stimulus_text = A_PRAISE_SCRIPT[stimulus_idx]
        _io.write_line(f"\n--- R80 tick {tick_id}/20 (stim #{stimulus_idx + 1}) ---")

        t0 = time.time()
        result = handle.tick()
        elapsed = time.time() - t0

        # Mirror the framework's v3 state feed so the LLM sees live hormone/feeling
        r79d_v3_state = getattr(handle, "_r79d_v3_state", None)
        if r79d_v3_state is not None:
            r79d_v3_state["last_result"] = result

        h = get_hormone_state_from_result(result) or {}
        f = get_feeling_state_from_result(result) or {}
        s = get_salience_from_result(result) or {}
        llm = gateway.captured[-1] if gateway.captured else None
        llm_parsed = llm.parsed_json if llm else None

        ne = h.get("norepinephrine", 0.0)
        ne_drift = 0.0 if ne_baseline is None else round(ne - ne_baseline, 4)
        if ne_baseline is None:
            ne_baseline = ne

        i_want = (llm_parsed or {}).get("i_want_to_think_more")
        rec = R80TickRecord(
            tick_id=tick_id,
            stimulus_text=stimulus_text,
            hormone_state=h,
            feeling_state=f,
            salience=s,
            llm_output={
                "what_i_feel": (llm_parsed or {}).get("what_i_feel"),
                "what_i_think": (llm_parsed or {}).get("what_i_think"),
                "i_want_to_think_more": i_want,
                "think_more_about": (llm_parsed or {}).get("think_more_about"),
                "raw_text_len": len(llm.raw_response_text) if llm and llm.raw_response_text else 0,
                "elapsed_s": round(elapsed, 2),
            },
            norepinephrine_drift=ne_drift,
            i_want_to_think_more=i_want,
        )
        records.append(rec)
        _io.write_line(f"  norepinephrine={ne:.4f}  drift={ne_drift:+.4f}  i_want_to_think_more={i_want}")

    total_elapsed = time.time() - t_total_start

    # Persist JSONL
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.__dict__, ensure_ascii=False) + "\n")

    return _build_summary(records, jsonl_path, report_path, cached=False, total_elapsed=total_elapsed)


def _build_summary(
    records: list, jsonl_path: Path, report_path: Path, *, cached: bool, total_elapsed: float = 0.0
) -> dict:
    """Compute aggregate stats + acceptance verdict + write the report."""

    if not records:
        return {"records": [], "jsonl_path": jsonl_path, "report_path": report_path, "cached": cached}

    ne_drifts = [r.norepinephrine_drift for r in records]
    final_drift = ne_drifts[-1] if ne_drifts else 0.0
    want_more = [bool(r.i_want_to_think_more) for r in records if r.i_want_to_think_more is not None]
    want_more_freq = sum(want_more) / max(1, len(want_more))

    ne_acceptance = final_drift >= 0.10
    want_more_acceptance = want_more_freq > 0.3

    summary = {
        "records": records,
        "n_ticks": len(records),
        "norepinephrine_final_drift": final_drift,
        "norepinephrine_drift_acceptance": ne_acceptance,
        "i_want_to_think_more_freq": want_more_freq,
        "i_want_to_think_more_acceptance": want_more_acceptance,
        "all_acceptance": ne_acceptance and want_more_acceptance,
        "jsonl_path": jsonl_path,
        "report_path": report_path,
        "cached": cached,
        "total_elapsed_s": round(total_elapsed, 2),
    }

    # Write report
    lines = [
        "# R80 20-Tick A_Praise + Rumination Probe Report",
        "",
        f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**N ticks**: {len(records)}",
        f"**N LLM calls**: {sum(1 for r in records if r.llm_output.get('raw_text_len', 0) > 0)}",
        f"**Total elapsed**: {summary['total_elapsed_s']}s",
        "",
        "## Acceptance Criteria",
        "",
        f"### 1. Norepinephrine cumulative drift >= 0.10",
        f"- **Final drift**: `{final_drift:+.4f}`",
        f"- **Per-tick drift series**: `{ne_drifts}`",
        f"- **Verdict**: {'PASS' if ne_acceptance else 'FAIL'} (threshold 0.10)",
        "",
        f"### 2. LLM i_want_to_think_more_freq > 0.3",
        f"- **Observed freq**: `{want_more_freq:.2f}` (n={len(want_more)})",
        f"- **Verdict**: {'PASS' if want_more_acceptance else 'FAIL'} (threshold 0.30)",
        "",
        f"### 3. Overall",
        f"- **Verdict**: {'ALL PASS' if summary['all_acceptance'] else 'PARTIAL / FAIL'}",
        "",
        "## Notes",
        "",
        "- The rumination provider is always-fire (R80 design). The R80 acceptance is that the "
        "internal_monologue source contributes a `novelty=0.3 + uncertainty=0.7` appraisal on "
        "every tick, which propagates to norepinephrine via the existing "
        "`AppraisalDerivedNeuromodulatorUpdatePath`.",
        "- 5-HT and Cortisol remain at the tonic baseline (R80 design: the social/threat gates "
        "are zero for `internal_monologue` stimuli by definition).",
        "- 5-HT / Oxy / Opioid 算式 边界 noted in R79-C report (uncertainty=1.0 for Chinese "
        "texts) is orthogonal to the R80 acceptance: the R80 path is novelty+uncertainty only.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    """CLI entry point: run the R80 20-tick probe."""

    import argparse
    p = argparse.ArgumentParser(description="R80 20-tick A_praise + rumination probe")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "logs" / "prompt_probe_scenarios" / "r80_baseline",
    )
    p.add_argument("--llm-model", default=None)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    summary = run_r80_20tick_probe(
        output_dir=args.output_dir,
        llm_model=args.llm_model,
        timeout_per_tick=args.timeout,
        force=args.force,
    )

    _io.write_line("\n" + "=" * 60)
    _io.write_line("R80 20-Tick Probe Summary")
    _io.write_line("=" * 60)
    _io.write_line(f"  N ticks             : {summary['n_ticks']}")
    _io.write_line(f"  NE final drift      : {summary['norepinephrine_final_drift']:+.4f}  ({'PASS' if summary['norepinephrine_drift_acceptance'] else 'FAIL'})")
    _io.write_line(f"  i_want_think_more   : {summary['i_want_to_think_more_freq']:.2f}  ({'PASS' if summary['i_want_to_think_more_acceptance'] else 'FAIL'})")
    _io.write_line(f"  Overall             : {'ALL PASS' if summary['all_acceptance'] else 'PARTIAL / FAIL'}")
    _io.write_line(f"  Report              : {summary['report_path']}")
    _io.write_line("=" * 60)


if __name__ == "__main__":
    main()
