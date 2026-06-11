"""R83 CLI entry-point.

Usage:
    python -m helios_v2.tests.r83 [--duration MINUTES] [--noop] [--no-judge] \
        [--output-dir DIR] [--run-id ID]

Defaults to a 1-minute noop run for quick smoke tests. Real LLM runs
require `OPENAI_API_KEY` and `OPENAI_BASE_URL` in the environment.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import _io
from .long_runner import LongRunner
from .report_builder import R83ReportBuilder
from .verdict import Verdict


def main(argv: list[str] | None = None) -> int:
    """CLI entry-point. Returns 0 on success, non-zero on failure."""
    parser = argparse.ArgumentParser(
        prog="helios_v2.tests.r83",
        description=(
            "R83 long-running preflight + Turing-style persona evaluation. "
            "Final acceptance gate of the R79 plan."
        ),
    )
    parser.add_argument(
        "--duration", type=float, default=1.0,
        help="target wall-clock duration in minutes (default 1.0).",
    )
    parser.add_argument(
        "--noop", action="store_true",
        help="use the noop gateway (no real LLM call).",
    )
    parser.add_argument(
        "--no-judge", action="store_true",
        help="skip the LLM judge probe (A1/A4/A6 default to 0.5).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="output directory (default: ./r83_run_<UTC-timestamp>).",
    )
    parser.add_argument(
        "--run-id", type=str, default=None,
        help="run identifier (default: r83_<UTC-timestamp>).",
    )
    args = parser.parse_args(argv)

    # Resolve output_dir + run_id
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or f"r83_{ts}"
    output_dir = args.output_dir or Path.cwd() / f"r83_run_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    _io.write_line(f"[r83] run_id: {run_id}")
    _io.write_line(f"[r83] duration: {args.duration} min")
    _io.write_line(f"[r83] noop: {args.noop}")
    _io.write_line(f"[r83] no_judge: {args.no_judge}")
    _io.write_line(f"[r83] output_dir: {output_dir}")

    # Build the long runner
    runner = LongRunner(noop=args.noop)
    scores = runner.run(
        duration_minutes=args.duration,
        output_dir=output_dir,
    )

    # Optional: layer the LLM judge probe on top
    if not args.no_judge and not args.noop:
        from helios_v2.tests.r79d.framework import RealLlmGateway
        from .judge import JudgeProbe

        gateway = RealLlmGateway()
        probe = JudgeProbe(gateway=gateway)
        a1_scores: list[float] = []
        a4_scores: list[float] = []
        a6_scores: list[float] = []
        reasonings: list[str] = []
        for blk in scores.per_block:
            jsonl_path = output_dir / "r83_longrun.jsonl"
            samples = _load_samples_for_state(jsonl_path, blk.state_id)
            result = probe.score(
                samples=samples,
                state_id=blk.state_id,
                lever="",
                expected_response="",
            )
            a1_scores.append(result.a1)
            a4_scores.append(result.a4)
            a6_scores.append(result.a6)
            reasonings.append(result.reasoning)
        # Fill the per-block judge fields + re-aggregate axis scores
        per_block = []
        for i, blk in enumerate(scores.per_block):
            blk_dict = {
                "state_id": blk.state_id,
                "n_ticks": blk.n_ticks,
                "a2_score": blk.a2_score,
                "judge_a1": a1_scores[i] if i < len(a1_scores) else 0.5,
                "judge_a4": a4_scores[i] if i < len(a4_scores) else 0.5,
                "judge_a6": a6_scores[i] if i < len(a6_scores) else 0.5,
                "judge_reasoning": reasonings[i] if i < len(reasonings) else "",
                "hormone_deltas": blk.hormone_deltas,
                "feeling_deltas": blk.feeling_deltas,
            }
            per_block.append(_dict_to_block(blk_dict))
        a1 = sum(a1_scores) / len(a1_scores) if a1_scores else 0.5
        a4 = sum(a4_scores) / len(a4_scores) if a4_scores else 0.5
        a6 = sum(a6_scores) / len(a6_scores) if a6_scores else 0.5
        scores = _scores_with_judge(scores, a1, a4, a6, per_block)

    # Compute verdict + write report
    verdict = Verdict.compute(scores)
    report_path = output_dir / "r83_report.md"
    builder = R83ReportBuilder(
        scores=scores,
        verdict=verdict,
        run_id=run_id,
        notes="R83 long-running preflight + Turing-style evaluation",
    )
    builder.write(report_path)
    _io.write_line(f"[r83] report written: {report_path}")
    _io.write_line(f"[r83] verdict: {verdict.label} "
                   f"(mean={verdict.mean_score:.3f}, min={verdict.min_score:.3f})")
    return 0


def _load_samples_for_state(jsonl_path: Path, state_id: str) -> list[str]:
    """Load the `i_want_to_say` samples for a given state from a JSONL."""
    import json
    if not jsonl_path.exists():
        return []
    samples: list[str] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("state_id") != state_id:
                continue
            llm = rec.get("llm_output", {})
            text = llm.get("i_want_to_say") or llm.get("i_want_to_act") or ""
            if text:
                samples.append(text)
    return samples


def _dict_to_block(d: dict):
    """Reconstruct a `BlockSummary` from a dict (for re-aggregation)."""
    from .long_runner import BlockSummary
    return BlockSummary(
        state_id=d["state_id"],
        n_ticks=d["n_ticks"],
        a2_score=d["a2_score"],
        judge_a1=d.get("judge_a1"),
        judge_a4=d.get("judge_a4"),
        judge_a6=d.get("judge_a6"),
        judge_reasoning=d.get("judge_reasoning", ""),
        hormone_deltas=d.get("hormone_deltas", {}),
        feeling_deltas=d.get("feeling_deltas", {}),
    )


def _scores_with_judge(scores, a1, a4, a6, per_block):
    """Reconstruct an `R83Scores` with the judge-augmented axis values."""
    from .long_runner import R83Scores
    return R83Scores(
        a1_linguistic_naturalness=a1,
        a2_bio_responsiveness=scores.a2_bio_responsiveness,
        a3_memory_fidelity=scores.a3_memory_fidelity,
        a4_agency_locking=a4,
        a5_cross_tick_continuity=scores.a5_cross_tick_continuity,
        a6_stimulus_response_coherence=a6,
        overall_drift_score=scores.overall_drift_score,
        per_block=tuple(per_block),
        total_ticks=scores.total_ticks,
        elapsed_seconds=scores.elapsed_seconds,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
