"""Turing-style system-level real LLM evaluation runner for helios v2.

Drives the helios_v2 runtime through the full Turing-style stimulus set
(1129 stimuli across 10 blocks × 72 scenarios), captures structured trace per tick
(regime, hormone, RPE, thought_content, response, learner updates), and writes a
JSONL trace file for downstream scoring.

It is a developer tool. It is NOT part of the test suite, and it issues real network
calls that consume tokens. Run it explicitly only.

Owner boundaries:
- Drives the runtime through composition owner public assembly + sensory ingress
- Loads `.env` for OPENAI_API_KEY/OPENAI_BASE_URL
- Writes structured per-tick trace to JSONL
- Designed for 8h real-LLM runs (~125 tick/h budget)

Usage:
    python helios_v2/scripts/helios_turing_system_runner.py --limit 3
    python helios_v2/scripts/helios_turing_system_runner.py --limit 100
    python helios_v2/scripts/helios_turing_system_runner.py  # full 1129
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any


def _load_dotenv(path: Path, *, override: bool) -> list[str]:
    loaded: list[str] = []
    if not path.exists():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _ensure_src_on_path(repo_root: Path) -> None:
    src_path = str(repo_root / "helios_v2" / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _load_stimuli(path: Path) -> list[dict[str, Any]]:
    stimuli: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            stimuli.append(json.loads(line))
    return stimuli


def _build_signals(stimuli: list[dict[str, Any]]):
    from helios_v2.sensory import RawSignal

    signals = []
    for record in stimuli:
        text = record.get("stimulus_text", "")
        signals.append(
            RawSignal(
                signal_id=f"turing-{record.get('tick_id', 0):04d}",
                source_name="turing_eval",
                signal_type="text",
                content=text,
                channel="turing",
                metadata={
                    "block": record.get("block"),
                    "scenario": record.get("scenario"),
                    "sub_tick": record.get("sub_tick"),
                    "tick_id": record.get("tick_id"),
                    "expected_emotion_hint": record.get("expected_emotion_hint"),
                    "dimension_focus": record.get("dimension_focus"),
                    "role": record.get("role"),
                },
            )
        )
    return tuple(signals)


def _tick_record(stimulus: dict[str, Any], result: Any) -> dict[str, Any]:
    thought_stage = result.stage_results["internal_thought_loop_owner"]
    autonomy = result.stage_results["subjective_autonomy_and_proactive_evolution"]
    artifact = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact
    diag = artifact.long_range_diagnostics
    thought = thought_stage.result.thought

    # Extract hormone from neuromodulator stage
    hormone_snapshot: dict[str, float] = {}
    try:
        neuro_stage = result.stage_results.get("neuromodulator_system")
        if neuro_stage is not None and hasattr(neuro_stage, "state") and neuro_stage.state is not None:
            state = neuro_stage.state
            if hasattr(state, "levels") and state.levels is not None:
                # levels is a NeuromodulatorLevels dataclass
                hormone_snapshot = {k: float(v) for k, v in state.levels.__dict__.items()}
    except Exception:
        pass

    return {
        "tick_id": result.tick_id,
        "stimulus_tick_id": stimulus.get("tick_id"),
        "block": stimulus.get("block"),
        "scenario": stimulus.get("scenario"),
        "sub_tick": stimulus.get("sub_tick"),
        "dimension_focus": stimulus.get("dimension_focus"),
        "expected_emotion_hint": stimulus.get("expected_emotion_hint"),
        "execution_status": thought_stage.result.execution_status,
        "llm_used": thought_stage.trace.llm_used,
        "source_path": thought.source_path if thought else None,
        "thought_type": thought.thought_type if thought else None,
        "sufficiency_level": thought_stage.result.sufficiency_level,
        "continuation_requested": thought_stage.result.continuation_requested,
        "dominant_disposition": autonomy.result.drive_state.dominant_disposition,
        "activity_mode": autonomy.result.drive_state.activity_mode,
        "hormone_snapshot": hormone_snapshot,
        "long_horizon_continuity": diag.get("long_horizon_continuity"),
        "execution_timeline_status": diag.get("execution_timeline_status"),
        "consequence_path_outcome": artifact.gap_summary.get("consequence_path_outcome"),
        "thought_content": thought.content if thought else None,
        "elapsed_seconds": getattr(result, "elapsed_seconds", None),
    }


def run_eval(
    *,
    repo_root: Path,
    stimuli_path: Path,
    output_path: Path,
    limit: int | None = None,
    probe_live: bool = False,
    production: bool = False,
    data_dir: str | None = None,
) -> dict[str, Any]:
    from helios_v2.composition import (
        assemble_runtime,
        assemble_production_runtime,
        default_composition_config,
    )
    from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder
    from helios_v2.llm import LlmGateway, LlmProfileRegistry, OpenAICompatibleProvider

    config = default_composition_config()
    stimuli = _load_stimuli(stimuli_path)
    if limit is not None:
        stimuli = stimuli[:limit]
    print(f"[runner] loaded {len(stimuli)} stimuli from {stimuli_path}", flush=True)

    # Replace source signals with turing stimuli
    config = replace(config, source_signals=_build_signals(stimuli))

    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    if production:
        # R-PROTO-LEARN.P-TEMPORAL.Phase3: production path = real SQLite + real
        # embedding gateway + SystemWallClock + semantic_memory_enabled=True.
        # P-TEMPORAL wire only fires in this mode (cso + half-life decay). Without
        # this, `cso.sample().wall_clock_elapsed_seconds` stays 0 forever and D2/D10
        # never improve. Small黑 2026-06-20 20:24+: 不走 force flag 过渡实现,
        # 走 assemble_production_runtime 真生产路径.
        if data_dir is None:
            data_dir = str(repo_root / "helios_v2" / ".data" / "turing_eval")
        print(f"[runner] production mode: data_dir={data_dir}", flush=True)
        os.makedirs(data_dir, exist_ok=True)
        handle = assemble_production_runtime(
            data_dir=data_dir,
            config=config,
            recorder=recorder,
        )
    else:
        handle = assemble_runtime(config=config, recorder=recorder)

    print("[runner] running startup (fail-fast LLM readiness gate)...", flush=True)
    handle.startup()
    print("[runner] startup OK", flush=True)

    if probe_live:
        probe_gateway = LlmGateway(
            provider=OpenAICompatibleProvider(),
            registry=LlmProfileRegistry(profiles=config.llm.profiles),
        )
        report = probe_gateway.probe_live_readiness((config.llm.thought_profile_name,))
        for entry in report.entries:
            print(
                f"[probe] {entry.profile_name}: live_ready={entry.live_ready} "
                f"({entry.detail})",
                flush=True,
            )

    # We need 1 stimulus per tick. handle.run_ticks(n) returns tuple (eager),
    # so we use handle.tick() in a loop for streaming progress.
    n_ticks = len(stimuli)
    print(f"[runner] running {n_ticks} ticks (streaming)...", flush=True)

    start = time.time()
    tick_records: list[dict[str, Any]] = []
    error_count = 0
    try:
        stim_by_idx = {i: s for i, s in enumerate(stimuli)}
        for tick_idx in range(n_ticks):
            tick_start = time.time()
            try:
                result = handle.tick()
                stim = stim_by_idx.get(tick_idx, {})
                rec = _tick_record(stim, result)
                rec["tick_elapsed_seconds"] = time.time() - tick_start
                tick_records.append(rec)
            except Exception as exc:
                error_count += 1
                tick_records.append({
                    "tick_id": tick_idx,
                    "error": str(exc),
                    "stimulus_tick_id": stim_by_idx.get(tick_idx, {}).get("tick_id"),
                    "tick_elapsed_seconds": time.time() - tick_start,
                })
            if (tick_idx + 1) % 20 == 0:
                elapsed = time.time() - start
                rate = (tick_idx + 1) / (elapsed / 3600.0) if elapsed > 0 else 0
                eta_h = (n_ticks - tick_idx - 1) / rate if rate > 0 else 0
                print(
                    f"[runner] {tick_idx + 1}/{n_ticks} ticks, errors={error_count}, "
                    f"elapsed={elapsed:.1f}s, rate={rate:.1f}/h, eta={eta_h:.1f}h",
                    flush=True,
                )
    except KeyboardInterrupt:
        print(f"[runner] interrupted at {len(tick_records)}/{n_ticks}", flush=True)

    total_elapsed = time.time() - start
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for rec in tick_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    summary = {
        "trace_path": str(output_path),
        "total_ticks": len(tick_records),
        "error_count": error_count,
        "elapsed_seconds": total_elapsed,
        "ticks_per_hour": len(tick_records) / (total_elapsed / 3600.0) if total_elapsed > 0 else 0,
    }
    print(
        f"[runner] wrote {len(tick_records)} trace records to {output_path}, "
        f"elapsed={total_elapsed:.1f}s, errors={error_count}, rate={summary['ticks_per_hour']:.1f}/h",
        flush=True,
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Turing system eval runner")
    parser.add_argument("--stimuli-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--probe-live", action="store_true")
    parser.add_argument(
        "--production",
        action="store_true",
        help="R-PROTO-LEARN.P-TEMPORAL: use assemble_production_runtime (real SQLite + "
        "real embedding + SystemWallClock + semantic_memory_enabled=True). Without "
        "this, P-TEMPORAL wire does not fire and D2/D10 stay at 0.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Required when --production: where to put the SQLite store. Default: "
        "helios_v2/.data/turing_eval/",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent.parent
    _load_dotenv(repo_root / ".env", override=False)
    _ensure_src_on_path(repo_root)

    stimuli_path = args.stimuli_path or (Path(__file__).parent / "turing_eval_2026_06_18_stimuli.jsonl")
    output_path = args.output or (Path(__file__).parent / "turing_eval_2026_06_18_trace.jsonl")

    print(f"[runner] repo_root={repo_root}", flush=True)
    print(f"[runner] stimuli={stimuli_path}", flush=True)
    print(f"[runner] output={output_path}", flush=True)
    if args.limit:
        print(f"[runner] limit={args.limit}", flush=True)
    if args.production:
        print(f"[runner] mode=PRODUCTION (semantic_memory enabled + cso wired)", flush=True)

    summary = run_eval(
        repo_root=repo_root,
        stimuli_path=stimuli_path,
        output_path=output_path,
        limit=args.limit,
        probe_live=args.probe_live,
        production=args.production,
        data_dir=args.data_dir,
    )
    print(f"[runner] summary: {json.dumps(summary, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
