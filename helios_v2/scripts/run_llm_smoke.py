"""Configurable real-LLM runtime smoke tool for the Helios v2 runnable runtime.

This tool assembles the default (LLM-backed) runtime through the composition owner with the
real OpenAI-compatible provider, runs a configurable number of ticks against configurable
injected stimuli, and prints each tick's real thought content plus key diagnostics. It can
optionally run a live readiness probe before ticking and write a structured JSON report.

It is a developer tool. It is NOT part of the test suite, and it issues real network calls
that consume tokens. Run it explicitly only.

Owner boundaries it respects:
- It only drives the runtime through the composition owner's public assembly and the sensory
  ingress owner's source protocol. It holds no cognitive policy and reinterprets no owner
  result.
- It loads `.env` into the process environment (the runtime reads `os.environ`); it never
  hardcodes secrets and never prints api-key values.

Examples:

    python helios_v2/scripts/run_llm_smoke.py --ticks 5
    python helios_v2/scripts/run_llm_smoke.py --ticks 3 --stimulus "how are you feeling?"
    python helios_v2/scripts/run_llm_smoke.py --ticks 4 --probe-live --save-json logs/smoke.json
    python helios_v2/scripts/run_llm_smoke.py --ticks 2 --model deepseek/deepseek-v4-flash
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


def _load_dotenv(path: Path, *, override: bool) -> list[str]:
    """Load KEY=VALUE pairs from a dotenv file into os.environ. Returns loaded key names."""

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


def _build_signals(stimuli: list[str]):
    from helios_v2.sensory import RawSignal

    signals = []
    for index, text in enumerate(stimuli, start=1):
        signals.append(
            RawSignal(
                signal_id=f"smoke-{index:03d}",
                source_name="cli",
                signal_type="text",
                content=text,
                channel="cli",
                metadata={"turn_id": f"smoke-t{index}"},
            )
        )
    return tuple(signals)


def _tick_record(result: Any) -> dict[str, Any]:
    thought_stage = result.stage_results["internal_thought_loop_owner"]
    autonomy = result.stage_results["subjective_autonomy_and_proactive_evolution"].result
    artifact = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact
    diag = artifact.long_range_diagnostics
    thought = thought_stage.result.thought
    return {
        "tick_id": result.tick_id,
        "execution_status": thought_stage.result.execution_status,
        "llm_used": thought_stage.trace.llm_used,
        "source_path": thought.source_path if thought else None,
        "thought_type": thought.thought_type if thought else None,
        "sufficiency_level": thought_stage.result.sufficiency_level,
        "continuation_requested": thought_stage.result.continuation_requested,
        "dominant_disposition": autonomy.drive_state.dominant_disposition,
        "activity_mode": autonomy.drive_state.activity_mode,
        "long_horizon_continuity": diag.get("long_horizon_continuity"),
        "execution_timeline_status": diag.get("execution_timeline_status"),
        "consequence_path_outcome": artifact.gap_summary.get("consequence_path_outcome"),
        "thought_content": thought.content if thought else None,
    }


def _print_tick(record: dict[str, Any], preview_chars: int) -> None:
    print(f"=== tick {record['tick_id']} ===")
    print(f"  execution_status      : {record['execution_status']}")
    print(f"  llm_used / source     : {record['llm_used']} / {record['source_path']}")
    print(f"  sufficiency           : {record['sufficiency_level']}")
    print(f"  continuation_requested: {record['continuation_requested']}")
    print(f"  disposition / mode    : {record['dominant_disposition']} / {record['activity_mode']}")
    print(f"  long_horizon          : {record['long_horizon_continuity']}")
    print(f"  timeline_status       : {record['execution_timeline_status']}")
    print(f"  consequence_outcome   : {record['consequence_path_outcome']}")
    content = record["thought_content"]
    if content is not None:
        preview = content.replace("\n", " ")
        if len(preview) > preview_chars:
            preview = preview[:preview_chars] + "..."
        print(f"  thought_content       : {preview}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Helios v2 LLM-backed runtime for a configurable number of ticks."
    )
    parser.add_argument(
        "--ticks", type=int, default=3, help="Positive number of ticks to run (default: 3)."
    )
    parser.add_argument(
        "--stimulus",
        action="append",
        default=[],
        help="Stimulus text injected each tick through the sensory ingress source. "
        "Repeat to inject multiple stimuli per tick. Defaults to one baseline stimulus.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the thought profile model. Defaults to HELIOS_LLM_MODEL or the config default.",
    )
    parser.add_argument(
        "--min-severity",
        default="debug",
        choices=("debug", "info", "notice", "warning", "error", "critical"),
        help="Minimum severity captured by the recorder (default: debug, required for the "
        "timeline carry to reconstruct).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to a dotenv file to load into the environment. Defaults to repo-root .env.",
    )
    parser.add_argument(
        "--no-env-file",
        action="store_true",
        help="Do not load any dotenv file; rely on the existing process environment only.",
    )
    parser.add_argument(
        "--env-override",
        action="store_true",
        help="Let dotenv values override existing environment variables (default: do not override).",
    )
    parser.add_argument(
        "--probe-live",
        action="store_true",
        help="Issue a real live readiness probe for the bound thought profile before ticking.",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=400,
        help="Maximum thought-content characters printed per tick (default: 400).",
    )
    parser.add_argument(
        "--save-json",
        default=None,
        help="Optional path to write a structured JSON report of the run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    if args.ticks <= 0:
        raise SystemExit("--ticks must be a positive integer")

    repo_root = Path(__file__).resolve().parents[2]
    if not args.no_env_file:
        env_path = Path(args.env_file) if args.env_file else repo_root / ".env"
        loaded = _load_dotenv(env_path, override=args.env_override)
        print(f"loaded {len(loaded)} env key(s) from {env_path}")
    else:
        print("skipping dotenv load; using existing process environment")

    _ensure_src_on_path(repo_root)

    from helios_v2.composition import default_composition_config, assemble_runtime
    from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder

    config = default_composition_config()
    stimuli = list(args.stimulus) if args.stimulus else ["hello runtime"]
    config = replace(config, source_signals=_build_signals(stimuli))
    if args.model:
        profiles = tuple(
            replace(profile, model=args.model) if profile.profile_name == config.llm.thought_profile_name else profile
            for profile in config.llm.profiles
        )
        config = replace(config, llm=replace(config.llm, profiles=profiles))

    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity=args.min_severity)
    handle = assemble_runtime(config=config, recorder=recorder)

    print("running startup (fail-fast LLM readiness gate)...")
    handle.startup()
    print("startup OK")

    live_report_payload = None
    if args.probe_live:
        from helios_v2.llm import LlmGateway, LlmProfileRegistry, OpenAICompatibleProvider

        probe_gateway = LlmGateway(
            provider=OpenAICompatibleProvider(),
            registry=LlmProfileRegistry(profiles=config.llm.profiles),
        )
        report = probe_gateway.probe_live_readiness((config.llm.thought_profile_name,))
        live_report_payload = [
            {
                "profile_name": entry.profile_name,
                "static_ready": entry.static_ready,
                "live_ready": entry.live_ready,
                "detail": entry.detail,
            }
            for entry in report.entries
        ]
        print("\nlive readiness probe:")
        for entry in live_report_payload:
            print(f"  {entry['profile_name']}: live_ready={entry['live_ready']} ({entry['detail']})")
    print()

    records = [_tick_record(result) for result in handle.run_ticks(args.ticks)]
    for record in records:
        _print_tick(record, preview_chars=args.preview_chars)

    completed = sum(1 for record in records if record["execution_status"] == "completed")
    llm_backed = sum(1 for record in records if record["llm_used"])
    print(
        f"summary: {len(records)} tick(s), {completed} completed, {llm_backed} llm-backed, "
        f"model={config.llm.profiles[0].model}"
    )

    if args.save_json:
        payload = {
            "ticks": args.ticks,
            "stimuli": stimuli,
            "model": config.llm.profiles[0].model,
            "live_readiness": live_report_payload,
            "records": records,
        }
        out_path = Path(args.save_json)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved JSON report to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
