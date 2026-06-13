"""CLI-fed real-LLM long pre-run harness (operational tooling, not part of the test suite).

Feeds a series of authored simulated-dialogue lines through the R31 CLI channel driver (a real
local afferent transport) into a durable, semantic, channel-bound runtime whose `11` thinking is
done by a REAL LLM (the production OpenAI-compatible gateway from `.env`). Each operator line is a
real, varying external afferent, so `03` novelty/threat/reward/social vary and `04`/`05` affect
responds across the run — a real-signal long pre-run, ahead of the P4 network drivers.

It is operational tooling: it adds no owner/contract and only orchestrates existing public assembly
(`assemble_runtime`, the SQLite experience store + R42 checkpoint, the CLI driver). It writes an
R83-format JSONL trace (so `tests/r88_drift_evaluator` can analyze the run's owner drift afterward)
plus a plain-text transcript of operator line -> agent reply.

Run (real LLM, requires `.env` with OPENAI_API_KEY etc.):
    python helios_v2/scripts/cli_dialogue_prerun.py --ticks 200

Run (offline plumbing smoke, deterministic fake gateway, network-free):
    python helios_v2/scripts/cli_dialogue_prerun.py --offline --ticks 30

Analyze the emitted trace for owner drift:
    $env:PYTHONPATH="helios_v2/src"
    python -c "import sys; sys.path.insert(0,'helios_v2/tests'); from r88_drift_evaluator import evaluate_trace_file; print(evaluate_trace_file('helios_v2/logs/prerun/cli_prerun.jsonl').summary())"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tracemalloc
from collections.abc import Mapping
from pathlib import Path


def _load_env() -> None:
    """Populate os.environ from the repo `.env` (setdefault; never prints values)."""

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _ensure_src_on_path() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


# R83 JSONL trace field schema: the tracked owner facts a drift evaluator (R88) consumes.
def _extract_fields(result) -> dict[str, float]:
    fields: dict[str, float] = {}
    stage_results = getattr(result, "stage_results", {}) or {}

    neuro = stage_results.get("neuromodulator_system")
    levels = getattr(getattr(neuro, "state", None), "levels", None)
    if levels is not None:
        for channel in (
            "dopamine", "norepinephrine", "serotonin", "acetylcholine", "cortisol",
            "oxytocin", "opioid_tone", "excitation", "inhibition",
        ):
            value = getattr(levels, channel, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                fields[f"04.{channel}"] = float(value)

    feeling_state = stage_results.get("interoceptive_feeling_layer")
    feeling = getattr(getattr(feeling_state, "state", None), "feeling", None)
    if feeling is not None:
        for dimension in (
            "valence", "arousal", "tension", "comfort", "fatigue", "pain_like", "social_safety",
        ):
            value = getattr(feeling, dimension, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                fields[f"05.{dimension}"] = float(value)

    gating = stage_results.get("thought_gating_and_continuation_pressure")
    gate_score = getattr(getattr(gating, "result", None), "gate_score", None)
    if isinstance(gate_score, (int, float)) and not isinstance(gate_score, bool):
        fields["09.gate_score"] = float(gate_score)
    level = getattr(getattr(gating, "continuation_state", None), "level", None)
    if isinstance(level, (int, float)) and not isinstance(level, bool):
        fields["09.continuation_level"] = float(level)

    autonomy = stage_results.get("subjective_autonomy_and_proactive_evolution")
    components = getattr(
        getattr(getattr(autonomy, "result", None), "drive_state", None), "pressure_components", None
    )
    if isinstance(components, Mapping):
        outward = components.get("outward_drive")
        if isinstance(outward, (int, float)) and not isinstance(outward, bool):
            fields["18.outward_drive"] = float(outward)

    return fields


def _offline_gateway():
    """A deterministic, network-free fake LLM gateway (for the --offline plumbing smoke)."""

    from helios_v2.composition import default_composition_config
    from helios_v2.llm import LlmGateway, LlmProfileRegistry
    from helios_v2.llm.contracts import ProviderCompletion

    class _FakeProvider:
        def complete(self, profile, request, api_key) -> "ProviderCompletion":
            envelope = {
                "thought": "an internal thought during the offline plumbing smoke",
                "sufficiency": 0.85,
                "wants_to_continue": False,
                "continue_reason": "",
                "proposed_action": {"intends_action": True, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "i_want_to_say": "Acknowledged.",
                "hormone_response_i_predict": {"dopamine": 0.6, "serotonin": 0.55},
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    config = default_composition_config()
    return LlmGateway(
        provider=_FakeProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-offline"},
    )


def _offline_embedding_gateway():
    from helios_v2.embedding import (
        DeterministicHashEmbeddingProvider,
        EmbeddingGateway,
        EmbeddingProfile,
        EmbeddingProfileRegistry,
    )

    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="deterministic-hash",
        api_key_env="HELIOS_PRERUN_EMBEDDING_KEY",
        base_url="http://localhost",
    )
    return EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"HELIOS_PRERUN_EMBEDDING_KEY": "prerun-offline"},
    )


def _load_dialogue(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def _build_handle(args, replies: list[str]):
    from helios_v2.channel import CliChannelDriver, CliDriverConfig
    from helios_v2.composition import assemble_runtime
    from helios_v2.continuity_checkpoint import ContinuityCheckpointStore, SqliteCheckpointBackend
    from helios_v2.persistence import ExperienceStore, SqliteExperienceStoreBackend

    base = Path(args.data_dir)
    base.mkdir(parents=True, exist_ok=True)
    store = ExperienceStore(
        backend=SqliteExperienceStoreBackend(db_path=str(base / "experience_store.sqlite3"))
    )
    store.initialize()
    checkpoint = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=str(base / "continuity_checkpoint.sqlite3"))
    )
    checkpoint.initialize()

    cli = CliChannelDriver(output_sink=replies.append, config=CliDriverConfig())

    gateway = _offline_gateway() if args.offline else None  # None -> real OpenAI-compatible from env
    handle = assemble_runtime(
        gateway=gateway,
        experience_store=store,
        embedding_gateway=_offline_embedding_gateway(),
        continuity_checkpoint=checkpoint,
        channel_drivers=(cli,),
        default_signal_mode="semantic",
    )
    return handle, cli, store


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI-fed real-LLM long pre-run harness")
    parser.add_argument("--ticks", type=int, default=200, help="total tick budget")
    parser.add_argument("--ticks-per-line", type=int, default=3, help="ticks between operator lines")
    parser.add_argument(
        "--data",
        type=str,
        default=str(Path(__file__).resolve().parent / "sim_dialogue.txt"),
        help="path to the simulated dialogue file (one operator line per non-comment line)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data" / "cli_prerun"),
        help="durable data directory (git-ignored data/ tree)",
    )
    parser.add_argument(
        "--jsonl",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "logs" / "prerun" / "cli_prerun.jsonl"),
        help="R83-format JSONL trace output (consumable by R88 drift evaluator)",
    )
    parser.add_argument("--offline", action="store_true", help="use a deterministic fake gateway")
    parser.add_argument("--loop", action="store_true", help="loop the dialogue when exhausted")
    args = parser.parse_args()

    _load_env()
    _ensure_src_on_path()

    dialogue = _load_dialogue(Path(args.data))
    if not dialogue:
        print(f"[prerun] no dialogue lines in {args.data}; aborting", flush=True)
        return 2

    replies: list[str] = []
    handle, cli, store = _build_handle(args, replies)

    model = os.environ.get("HELIOS_LLM_MODEL", "<default>")
    mode = "OFFLINE (fake gateway)" if args.offline else f"REAL LLM (model={model})"
    print(
        f"[prerun] mode={mode} ticks={args.ticks} ticks_per_line={args.ticks_per_line} "
        f"dialogue_lines={len(dialogue)} data_dir={args.data_dir}",
        flush=True,
    )

    handle.startup()
    jsonl_path = Path(args.jsonl)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    store_start = store.count()
    sample_every = max(1, args.ticks // 200)
    line_index = 0
    fed = 0
    replies_emitted = 0
    crash: str | None = None

    tracing = not tracemalloc.is_tracing()
    if tracing:
        tracemalloc.start()

    with open(jsonl_path, "w", encoding="utf-8") as trace:
        for tick_index in range(args.ticks):
            # Feed an operator line at the start of every Nth tick.
            if tick_index % args.ticks_per_line == 0:
                if line_index < len(dialogue):
                    line = dialogue[line_index]
                    cli.submit_line(line)
                    line_index += 1
                    fed += 1
                    print(f"[prerun] tick {tick_index} >> operator: {line}", flush=True)
                elif args.loop:
                    line_index = 0

            before_replies = len(replies)
            tick_started = time.perf_counter()
            try:
                result = handle.tick()
            except Exception as error:  # noqa: BLE001 - capture the crash, stop the run
                crash = f"tick {tick_index}: {type(error).__name__}: {error}"
                print(f"[prerun] CRASH {crash}", flush=True)
                break
            duration_ms = (time.perf_counter() - tick_started) * 1000.0

            for reply in replies[before_replies:]:
                replies_emitted += 1
                print(f"[prerun] tick {tick_index} << helios: {reply}", flush=True)

            if tick_index % sample_every == 0:
                current_mem, _ = tracemalloc.get_traced_memory()
                sample = {
                    "tick": float(tick_index),
                    "tick_duration_ms": round(duration_ms, 4),
                    "store_count": float(store.count()),
                    "memory_mb": round(current_mem / (1024 * 1024), 4),
                }
                sample.update(_extract_fields(result))
                trace.write(json.dumps(sample) + "\n")
                trace.flush()

    peak = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
    if tracing:
        tracemalloc.stop()

    store_end = store.count()
    print("\n[prerun] ===== summary =====", flush=True)
    print(f"[prerun] crash: {crash or 'none'}", flush=True)
    print(f"[prerun] dialogue lines fed: {fed}", flush=True)
    print(f"[prerun] agent replies emitted: {replies_emitted}", flush=True)
    print(f"[prerun] durable store: {store_start} -> {store_end} records", flush=True)
    print(f"[prerun] memory peak: {peak:.1f} MB", flush=True)
    print(f"[prerun] trace: {jsonl_path}", flush=True)
    print(
        "[prerun] analyze drift: from r88_drift_evaluator import evaluate_trace_file; "
        f"evaluate_trace_file(r'{jsonl_path}').summary()",
        flush=True,
    )
    return 1 if crash else 0


if __name__ == "__main__":
    raise SystemExit(main())
