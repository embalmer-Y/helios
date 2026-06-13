"""Real-LLM emotional-response test runner (operational tooling; executor side of the test).

Sends a category-tagged Chinese dialogue set (scripts/sim_dialogue_zh.txt) through the R31 CLI
channel driver into a durable, semantic, channel-bound runtime whose `11` thinking is a REAL LLM
(production gateway from `.env`). Each message is fed at a RANDOM tick interval; after each message it
records, as a structured per-message record:
  - the operator line + its intended emotion category,
  - the LLM internal thought(s) produced (`11`) and any CLI reply emitted,
  - the `04` neuromodulator levels (9 channels) and `05` feeling (7 dims) BEFORE -> AFTER, plus deltas.

It writes a JSON report (the evidence the judge analyzes) + a readable transcript. Operational tooling
only: no owner/contract change. Real-LLM run (default) needs `.env` with OPENAI_API_KEY etc.

Run:
    python helios_v2/scripts/emotion_test_run.py                  # full set, real LLM
    python helios_v2/scripts/emotion_test_run.py --messages 5     # short real-LLM smoke
    python helios_v2/scripts/emotion_test_run.py --offline --messages 8   # network-free plumbing
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections.abc import Mapping
from pathlib import Path

_CHANNELS = (
    "dopamine", "norepinephrine", "serotonin", "acetylcholine", "cortisol",
    "oxytocin", "opioid_tone", "excitation", "inhibition",
)
_FEELING = ("valence", "arousal", "tension", "comfort", "fatigue", "pain_like", "social_safety")


def _load_env() -> None:
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


def _levels(result) -> dict | None:
    state = getattr(result.stage_results.get("neuromodulator_system"), "state", None)
    levels = getattr(state, "levels", None)
    if levels is None:
        return None
    out = {}
    for ch in _CHANNELS:
        v = getattr(levels, ch, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[ch] = round(float(v), 4)
    return out or None


def _feeling(result) -> dict | None:
    state = getattr(result.stage_results.get("interoceptive_feeling_layer"), "state", None)
    feeling = getattr(state, "feeling", None)
    if feeling is None:
        return None
    out = {}
    for d in _FEELING:
        v = getattr(feeling, d, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[d] = round(float(v), 4)
    return out or None


def _thought(result) -> dict | None:
    stage = result.stage_results.get("internal_thought_loop_owner")
    if stage is None or not getattr(stage, "activated", False):
        return None
    res = getattr(stage, "result", None)
    thought = getattr(res, "thought", None)
    content = getattr(thought, "content", None)
    return {
        "execution_status": getattr(res, "execution_status", None),
        "llm_used": getattr(thought, "llm_used", None),
        "content": content,
    }


def _delta(before: dict | None, after: dict | None) -> dict:
    if not before or not after:
        return {}
    return {k: round(after[k] - before[k], 4) for k in after if k in before}


def _offline_gateway():
    from helios_v2.composition import default_composition_config
    from helios_v2.llm import LlmGateway, LlmProfileRegistry
    from helios_v2.llm.contracts import ProviderCompletion

    class _FakeProvider:
        def complete(self, profile, request, api_key):
            envelope = {
                "thought": "（离线占位思考）", "sufficiency": 0.85, "wants_to_continue": False,
                "continue_reason": "", "proposed_action": {"intends_action": True, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "i_want_to_say": "我在听。",
                "hormone_response_i_predict": {"dopamine": 0.6, "serotonin": 0.55},
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    config = default_composition_config()
    return LlmGateway(
        provider=_FakeProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-offline"},
    )


def _embedding_gateway():
    from helios_v2.embedding import (
        DeterministicHashEmbeddingProvider, EmbeddingGateway, EmbeddingProfile,
        EmbeddingProfileRegistry,
    )
    profile = EmbeddingProfile(
        profile_name="experience-embedding", model="deterministic-hash",
        api_key_env="HELIOS_EMO_EMBEDDING_KEY", base_url="http://localhost",
    )
    return EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"HELIOS_EMO_EMBEDDING_KEY": "emo-offline"},
    )


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
    handle = assemble_runtime(
        gateway=_offline_gateway() if args.offline else None,
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=checkpoint,
        channel_drivers=(cli,),
        default_signal_mode="semantic",
    )
    return handle, cli, store


def _load_dialogue(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "|" not in s:
            continue
        cat, text = s.split("|", 1)
        out.append((cat.strip(), text.strip()))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-LLM emotional-response test runner")
    parser.add_argument("--data", default=str(Path(__file__).resolve().parent / "sim_dialogue_zh.txt"))
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[1] / "data" / "emotion_test"))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "logs" / "prerun" / "emotion_test_report.json"))
    parser.add_argument("--transcript", default=str(Path(__file__).resolve().parents[1] / "logs" / "prerun" / "emotion_test_transcript.txt"))
    parser.add_argument("--messages", type=int, default=0, help="cap messages (0 = all)")
    parser.add_argument("--min-ticks", type=int, default=1)
    parser.add_argument("--max-ticks", type=int, default=4)
    parser.add_argument("--max-sleep", type=float, default=0.3, help="max random wall sleep per message (s)")
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    _load_env()
    _ensure_src_on_path()
    rng = random.Random(args.seed)

    dialogue = _load_dialogue(Path(args.data))
    if args.messages > 0:
        dialogue = dialogue[: args.messages]
    if not dialogue:
        print(f"[emo] no dialogue in {args.data}", flush=True)
        return 2

    replies: list[str] = []
    handle, cli, store = _build_handle(args, replies)
    model = os.environ.get("HELIOS_LLM_MODEL", "<default>")
    mode = "OFFLINE(fake)" if args.offline else f"REAL LLM(model={model})"
    print(f"[emo] mode={mode} messages={len(dialogue)} ticks=[{args.min_ticks},{args.max_ticks}] seed={args.seed}", flush=True)

    handle.startup()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    # Warm-up tick to seed baseline biochemistry (no message).
    last_levels = last_feeling = None
    try:
        warm = handle.tick()
        last_levels, last_feeling = _levels(warm), _feeling(warm)
    except Exception as error:  # noqa: BLE001
        print(f"[emo] WARMUP CRASH {type(error).__name__}: {error}", flush=True)
        return 1

    records: list[dict] = []
    crash: str | None = None
    transcript_lines: list[str] = []

    for idx, (category, text) in enumerate(dialogue):
        ticks = rng.randint(args.min_ticks, args.max_ticks)
        sleep_s = round(rng.uniform(0.0, args.max_sleep), 3)
        before_levels, before_feeling = last_levels, last_feeling
        before_reply_n = len(replies)

        cli.submit_line(text)
        thoughts: list[dict] = []
        fired = 0
        for _ in range(ticks):
            if sleep_s:
                time.sleep(sleep_s / max(1, ticks))
            try:
                result = handle.tick()
            except Exception as error:  # noqa: BLE001 - capture partial, stop
                crash = f"message {idx} ({category}): {type(error).__name__}: {error}"
                break
            last_levels, last_feeling = _levels(result) or last_levels, _feeling(result) or last_feeling
            th = _thought(result)
            if th is not None:
                fired += 1
                thoughts.append(th)
        if crash:
            break

        new_replies = replies[before_reply_n:]
        rec = {
            "index": idx, "category": category, "text": text,
            "ticks": ticks, "sleep_s": sleep_s, "fired": fired,
            "levels_before": before_levels, "levels_after": last_levels,
            "levels_delta": _delta(before_levels, last_levels),
            "feeling_before": before_feeling, "feeling_after": last_feeling,
            "feeling_delta": _delta(before_feeling, last_feeling),
            "thoughts": thoughts, "replies": new_replies,
        }
        records.append(rec)

        # Live transcript.
        line_in = f"[{idx:03d}|{category}] >> {text}"
        print(line_in, flush=True)
        transcript_lines.append(line_in)
        for th in thoughts:
            tline = f"        ~think({th.get('execution_status')},llm={th.get('llm_used')}): {th.get('content')}"
            print(tline, flush=True)
            transcript_lines.append(tline)
        for rep in new_replies:
            rline = f"        << {rep}"
            print(rline, flush=True)
            transcript_lines.append(rline)
        dl = rec["levels_delta"]
        if dl:
            top = sorted(dl.items(), key=lambda kv: -abs(kv[1]))[:4]
            dline = "        04Δ: " + ", ".join(f"{k}{v:+.3f}" for k, v in top)
            print(dline, flush=True)
            transcript_lines.append(dline)

    report = {
        "mode": mode, "model": model, "seed": args.seed,
        "messages_requested": len(dialogue), "messages_completed": len(records),
        "crash": crash, "store_count_end": store.count(),
        "records": records,
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.transcript).write_text("\n".join(transcript_lines), encoding="utf-8")

    print(f"\n[emo] ===== done: {len(records)}/{len(dialogue)} messages, crash={crash or 'none'} =====", flush=True)
    print(f"[emo] report:     {args.out}", flush=True)
    print(f"[emo] transcript: {args.transcript}", flush=True)
    return 1 if crash else 0


if __name__ == "__main__":
    raise SystemExit(main())
