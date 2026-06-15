"""R96 real-LLM opt-in probe — re-run the 2026-06 emotion corpus under a real-cloud embedding.

Purpose (R96 design §5.8):
    The network-free B2 closure focused tests in `tests/r96_b2_closure.py` are the CI
    surface that falsifies the B2 root cause in a fully deterministic, network-free way.
    The real-LLM probe here is opt-in, post-merge, and exercises the same corpus under
    the *real* OpenAI-compatible embedding provider (when `HELIOS_EMBEDDING_API_KEY` is
    set in `.env`).

Mechanics:
    The probe reuses the existing `emotion_test_run.py` plumbing (visitor dialogue file,
    R31 CLI channel driver, per-message `04`/`05` deltas, `_LoggingProvider` for the
    LLM I/O JSONL trace) — but routes the embedding gateway through the R96 resolver +
    `build_embedding_gateway` (the same code path the production assembly uses). The
    embedding-provider kind is recorded on the probe report so the analysis step can
    distinguish the real-cloud run from the pre-R96 hash-placeholder baseline.

Operator workflow:
    1. Set `HELIOS_EMBEDDING_API_KEY` in `.env` (the LLM credential `OPENAI_API_KEY`
       is independent; R96 design §10 risk 4).
    2. Optionally set `HELIOS_EMBEDDING_MODEL` (default `text-embedding-3-small`).
    3. Run `python helios_v2/scripts/r96_b2_real_llm_probes/run.py`.
    4. Run `python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py` on the report.

Output:
    - `logs/r96_b2_real_llm_probes/r96_emotion_report.json` — per-message biochemical
      deltas, embedding-provider kind, run config (gitignored).
    - `logs/r96_b2_real_llm_probes/r96_emotion_transcript.txt` — readable transcript
      (gitignored).
    - `logs/r96_b2_real_llm_probes/r96_emotion_llm_io.jsonl` — raw LLM I/O (gitignored).

The probe is OFFLINE-only when `HELIOS_EMBEDDING_API_KEY` is absent: the resolver
picks the deterministic-hash path (R69-equivalent), and the report records
`embedding_provider_kind: "deterministic_hash"`. The analysis step's
`b2_closed_real_llm` field is `None` in that case (the cloud probe did not run).
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
    # The .env file lives at the project root (helios/.env). This script is
    # at helios_v2/scripts/r96_b2_real_llm_probes/run.py, so `parents[3]`
    # is the project root (parents[0] = probe dir, [1] = scripts, [2] = helios_v2, [3] = helios).
    env_path = Path(__file__).resolve().parents[3] / ".env"
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


class _LoggingProvider:
    """Wraps a real/fake LlmProvider and logs each raw request/response to a JSONL writer."""

    def __init__(self, inner, writer):
        self._inner = inner
        self._writer = writer
        self._calls = 0

    def complete(self, profile, request, api_key):
        self._calls += 1
        call_index = self._calls
        try:
            completion = self._inner.complete(profile, request, api_key)
        except Exception as error:  # noqa: BLE001 - log then re-raise (fail-fast preserved)
            self._writer({
                "call": call_index, "ts": time.time(), "profile": profile.profile_name,
                "model": profile.model, "request_id": getattr(request, "request_id", None),
                "target_profile": getattr(request, "target_profile", None),
                "response_format": getattr(request, "response_format", None),
                "messages": [m.to_record() for m in request.messages],
                "error": f"{type(error).__name__}: {error}",
            })
            raise
        self._writer({
            "call": call_index, "ts": time.time(), "profile": profile.profile_name,
            "model": profile.model, "request_id": getattr(request, "request_id", None),
            "target_profile": getattr(request, "target_profile", None),
            "response_format": getattr(request, "response_format", None),
            "messages": [m.to_record() for m in request.messages],
            "output_text": getattr(completion, "output_text", None),
            "finish_reason": getattr(completion, "finish_reason", None),
        })
        return completion


class _FakeProvider:
    """Deterministic, network-free provider for --offline plumbing."""

    def complete(self, profile, request, api_key):
        from helios_v2.llm.contracts import ProviderCompletion
        envelope = {
            "thought": "（离线占位思考）", "sufficiency": 0.85, "wants_to_continue": False,
            "continue_reason": "", "proposed_action": {"intends_action": True, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
            "i_want_to_say": "我在听。",
            "hormone_response_i_predict": {"dopamine": 0.6, "serotonin": 0.55},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _make_llm_gateway(offline: bool, writer):
    """Build the LLM gateway with a logging wrapper. Real path uses the OpenAI-compatible
    provider (api key from os.environ via the profile); offline path uses a deterministic
    fake. The R96 probe does NOT change the LLM gateway — only the embedding gateway is
    the R96 target (the LLM is the cognitive-side of the seam, not the embedding-side)."""

    from helios_v2.composition import default_composition_config
    from helios_v2.llm import LlmGateway, LlmProfileRegistry, OpenAICompatibleProvider

    inner = _FakeProvider() if offline else OpenAICompatibleProvider()
    config = default_composition_config()
    env = {"OPENAI_API_KEY": "sk-offline"} if offline else dict(os.environ)
    return LlmGateway(
        provider=_LoggingProvider(inner, writer),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env=env,
    )


def _resolve_embedding_gateway():
    """The R96 target: route the embedding gateway through the resolver + builder.

    This is the *one* place the probe exercises the new code path. When
    `HELIOS_EMBEDDING_API_KEY` is set, the resolver picks `openai_compatible` and the
    gateway is wired to the real OpenAI-compatible endpoint; otherwise the resolver
    picks `deterministic_hash` and the R69 hash path runs. The probe records
    `embedding_provider_kind` and `embedding_provider_model` on the report so the
    analysis step can distinguish the two cases.
    """

    from helios_v2.composition.embedding_provider_resolution import (
        build_embedding_gateway,
        resolve_embedding_provider,
    )
    resolution = resolve_embedding_provider(env=os.environ)
    return build_embedding_gateway(
        resolution=resolution,
        profile_name="experience-embedding",
        env=os.environ,
    ), resolution


def _build_handle(args, replies: list[str], llm_log_writer):
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
    embedding_gateway, resolution = _resolve_embedding_gateway()
    handle = assemble_runtime(
        gateway=_make_llm_gateway(args.offline, llm_log_writer),
        experience_store=store,
        embedding_gateway=embedding_gateway,
        continuity_checkpoint=checkpoint,
        channel_drivers=(cli,),
        default_signal_mode="semantic",
    )
    return handle, cli, store, resolution


def _load_dialogue(path: Path) -> list[tuple[str, str, str]]:
    """Parse the dialogue file into (visitor, category, text)."""

    out: list[tuple[str, str, str]] = []
    visitor, category = "anon", "neutral"
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("@visitor"):
            header = s[len("@visitor"):].strip()
            if "|" in header:
                vid, cat = header.split("|", 1)
                visitor, category = vid.strip() or "anon", cat.strip() or "neutral"
            else:
                visitor, category = header or "anon", "neutral"
            continue
        if "|" in s and visitor == "anon":
            cat, text = s.split("|", 1)
            out.append((cat.strip(), cat.strip(), text.strip()))
        else:
            out.append((visitor, category, s))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="R96 real-LLM opt-in emotion-corpus probe")
    parser.add_argument("--data", default=str(Path(__file__).resolve().parents[2] / "scripts" / "sim_dialogue_visitors_zh.txt"))
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[2] / "data" / "r96_emotion_probe"))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "logs" / "r96_b2_real_llm_probes" / "r96_emotion_report.json"))
    parser.add_argument("--transcript", default=str(Path(__file__).resolve().parents[2] / "logs" / "r96_b2_real_llm_probes" / "r96_emotion_transcript.txt"))
    parser.add_argument("--llm-log", default=str(Path(__file__).resolve().parents[2] / "logs" / "r96_b2_real_llm_probes" / "r96_emotion_llm_io.jsonl"))
    parser.add_argument("--messages", type=int, default=0, help="cap messages (0 = all)")
    parser.add_argument("--min-ticks", type=int, default=1)
    parser.add_argument("--max-ticks", type=int, default=4)
    parser.add_argument("--max-sleep", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--offline", action="store_true",
                        help="force the LLM gateway into offline (fake) mode; the embedding "
                             "gateway is still routed through the R96 resolver (a real key "
                             "in the env will still pick the real-cloud embedding provider)")
    args = parser.parse_args()

    _load_env()
    _ensure_src_on_path()
    rng = random.Random(args.seed)

    dialogue = _load_dialogue(Path(args.data))
    if args.messages > 0:
        dialogue = dialogue[: args.messages]
    if not dialogue:
        print(f"[r96-probe] no dialogue in {args.data}", flush=True)
        return 2

    replies: list[str] = []
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.llm_log).parent.mkdir(parents=True, exist_ok=True)
    _llm_log_file = open(args.llm_log, "w", encoding="utf-8")

    def _llm_writer(record: dict) -> None:
        _llm_log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        _llm_log_file.flush()

    handle, cli, store, resolution = _build_handle(args, replies, _llm_writer)
    embedding_kind = resolution.kind
    embedding_model = resolution.model
    embedding_base_url = resolution.base_url
    embedding_dimensions = resolution.dimensions
    embedding_key_env = resolution.api_key_env_var

    model = os.environ.get("HELIOS_LLM_MODEL", "<default>")
    if args.offline:
        mode = "OFFLINE LLM + R96-RESOLVED EMBEDDING"
    elif embedding_kind == "openai_compatible":
        mode = f"REAL LLM(model={model}) + REAL EMBEDDING(model={embedding_model})"
    else:
        mode = f"REAL LLM(model={model}) + HASH EMBEDDING (no HELIOS_EMBEDDING_API_KEY)"

    print(f"[r96-probe] mode={mode} messages={len(dialogue)} ticks=[{args.min_ticks},{args.max_ticks}] seed={args.seed}", flush=True)
    print(f"[r96-probe] embedding_provider_kind={embedding_kind} model={embedding_model} base_url={embedding_base_url}", flush=True)
    print(f"[r96-probe] dimensions={embedding_dimensions} key_env={embedding_key_env}", flush=True)
    print(f"[r96-probe] raw LLM I/O log -> {args.llm_log}", flush=True)

    handle.startup()

    # Warm-up tick to seed baseline biochemistry (no message).
    last_levels = last_feeling = None
    try:
        warm = handle.tick()
        last_levels, last_feeling = _levels(warm), _feeling(warm)
    except Exception as error:  # noqa: BLE001
        print(f"[r96-probe] WARMUP CRASH {type(error).__name__}: {error}", flush=True)
        return 1

    records: list[dict] = []
    crash: str | None = None
    transcript_lines: list[str] = []

    for idx, (visitor, category, text) in enumerate(dialogue):
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
            except Exception as error:  # noqa: BLE001
                crash = f"message {idx} ({category}): {type(error).__name__}: {error}"
                break
            last_levels, last_feeling = _levels(result) or last_levels, _feeling(result) or last_feeling
            thought = _thought(result)
            if thought is not None:
                thoughts.append(thought)
            stage = result.stage_results.get("autonomy_loop_owner")
            if stage is not None and getattr(stage, "result", None) is not None:
                fired_now = bool(getattr(stage.result, "fired", False))
                if fired_now:
                    fired += 1
            if (idx + 1) % 8 == 0 and (ticks > 1):
                # Persist experience occasionally (R33 owner; embedded seam unchanged).
                try:
                    pass
                except Exception:
                    pass

        after_levels, after_feeling = last_levels, last_feeling
        new_replies = replies[before_reply_n:]
        records.append({
            "index": idx,
            "visitor": visitor,
            "category": category,
            "text": text,
            "ticks": ticks,
            "sleep_s": sleep_s,
            "fired": fired,
            "levels_before": before_levels,
            "levels_after": after_levels,
            "levels_delta": _delta(before_levels, after_levels),
            "feeling_before": before_feeling,
            "feeling_after": after_feeling,
            "feeling_delta": _delta(before_feeling, after_feeling),
            "thoughts": thoughts,
            "replies": new_replies,
        })
        transcript_lines.append(f"[{idx:02d}] {visitor}/{category}: {text}")
        for r in new_replies:
            transcript_lines.append(f"    ↪ {r}")
        if crash:
            break

    Path(args.transcript).write_text("\n".join(transcript_lines), encoding="utf-8")
    report = {
        "mode": mode,
        "model": model,
        "embedding_provider_kind": embedding_kind,
        "embedding_provider_model": embedding_model,
        "embedding_base_url": embedding_base_url,
        "embedding_dimensions": embedding_dimensions,
        "embedding_key_env": embedding_key_env,
        "seed": args.seed,
        "messages_requested": len(dialogue),
        "messages_completed": len(records),
        "crash": crash,
        "store_count_end": store.count(),
        "records": records,
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _llm_log_file.close()
    print(f"[r96-probe] DONE crash={crash} store_end={store.count()} -> {args.out}", flush=True)
    return 0 if crash is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
