import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helios_main import Helios, HeliosConfig


def _tail_lines(path: Path, max_lines: int = 20000) -> list[str]:
    if not path.exists():
        return []
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(data) <= max_lines:
        return data
    return data[-max_lines:]


def _count_matches(lines: list[str], pattern: str) -> int:
    rx = re.compile(pattern)
    return sum(1 for line in lines if rx.search(line))


def _build_thought_action_bridge_observation(state: dict) -> dict:
    thought_cycle = dict(state.get("thought_cycle", {}) or {})
    internal_thought = dict(state.get("internal_thought", {}) or {})
    action_trace = dict(thought_cycle.get("action_derivation_trace", {}) or {})
    action_proposal = dict(thought_cycle.get("action_proposal", {}) or {})

    return {
        "triggered": bool(thought_cycle.get("triggered", False)),
        "thought_type": str(thought_cycle.get("thought_type", "") or ""),
        "llm_used": bool(thought_cycle.get("llm_used", False)),
        "structured_output_valid": bool(internal_thought.get("structured_output_valid", False)),
        "action_explicit": bool(action_trace.get("action_explicit", False)),
        "action_parse_status": str(action_trace.get("parse_status", "") or ""),
        "action_drop_reason": str(action_trace.get("drop_reason", "") or ""),
        "action_behavior_name": str(action_proposal.get("behavior_name", "") or ""),
        "action_preferred_op": str(action_proposal.get("preferred_op", "") or ""),
        "candidate_channels": list(action_proposal.get("channel_constraints", {}).get("candidate_channels", []) or []),
        "has_action_proposal": bool(action_proposal),
        "thought_content_preview": str(thought_cycle.get("content", "") or "")[:240],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live Helios evaluation window")
    parser.add_argument("--duration", type=int, default=1800, help="Duration in seconds")
    parser.add_argument("--sample-interval", type=float, default=5.0, help="Sampling interval in seconds")
    parser.add_argument(
        "--report",
        type=str,
        default="tests/reports/live_eval_30min_2026-05-24.json",
        help="Output report path",
    )
    args = parser.parse_args()

    cfg = HeliosConfig()
    helios = Helios(cfg)

    worker = threading.Thread(target=helios.start, daemon=True)
    start_ts = time.time()
    worker.start()

    status_samples: list[str] = []
    tick_samples: list[int] = []
    rss_samples: list[float] = []

    while time.time() - start_ts < args.duration:
        try:
            if helios._qq_channel is not None:
                status_samples.append(str(helios._qq_channel.get_status()))
            tick_samples.append(int(helios.tick_count))
            rss_samples.append(float(helios.last_rss_mb))
        except Exception:
            pass
        time.sleep(max(0.2, args.sample_interval))

    helios.running = False
    worker.join(timeout=30)

    end_ts = time.time()
    elapsed = end_ts - start_ts
    state = helios.get_state()
    log_path = Path(getattr(helios, "_log_file_path", ""))
    lines = _tail_lines(log_path)

    qq_connected_ratio = 0.0
    if status_samples:
        qq_connected_ratio = sum(1 for s in status_samples if "connected" in s.lower()) / len(status_samples)

    tick_delta = 0
    if len(tick_samples) >= 2:
        tick_delta = tick_samples[-1] - tick_samples[0]

    approx_expected_ticks = int(elapsed / max(cfg.TICK_INTERVAL, 1e-6))
    tick_progress_ratio = (tick_delta / approx_expected_ticks) if approx_expected_ticks > 0 else 0.0

    errors = _count_matches(lines, r"\[ERROR\]|Traceback|Exception")
    qq_reconnect = _count_matches(lines, r"QQ WebSocket .*重连|QQ WebSocket .*reconnect")
    outbound_success = _count_matches(lines, r"-> qq:")
    outbound_fail = _count_matches(lines, r"发送失败")
    sec_fallback = _count_matches(lines, r"SEC .*回退|fallback")

    functionality = {
        "runtime_alive": bool(worker.is_alive() is False or tick_delta > 0),
        "tick_progress_ratio": round(tick_progress_ratio, 3),
        "qq_connected_ratio": round(qq_connected_ratio, 3),
        "error_events": errors,
        "qq_reconnect_events": qq_reconnect,
        "outbound_success_count": outbound_success,
        "outbound_fail_count": outbound_fail,
        "sec_fallback_count": sec_fallback,
    }

    # Soul-likeness is partly subjective; this script gives a quantitative scaffold.
    soul_score = 0.0
    soul_components = {}

    continuity = min(1.0, max(0.0, tick_progress_ratio))
    soul_components["continuity"] = round(continuity, 3)
    soul_score += continuity * 0.25

    emotional_presence = 1.0 if state.get("dominant") else 0.0
    soul_components["emotional_presence"] = round(emotional_presence, 3)
    soul_score += emotional_presence * 0.20

    memory_growth = 1.0 if state.get("autobio_moments", 0) > 0 else 0.4
    soul_components["memory_presence"] = round(memory_growth, 3)
    soul_score += memory_growth * 0.20

    relational_engagement = 1.0 if outbound_success > 0 else 0.3
    soul_components["relational_engagement"] = round(relational_engagement, 3)
    soul_score += relational_engagement * 0.20

    resilience = 1.0 if errors == 0 else max(0.2, 1.0 - min(1.0, errors / 30.0))
    soul_components["resilience"] = round(resilience, 3)
    soul_score += resilience * 0.15

    report = {
        "window": {
            "started_at": start_ts,
            "ended_at": end_ts,
            "elapsed_seconds": round(elapsed, 2),
            "requested_duration_seconds": args.duration,
        },
        "config": {
            "tick_interval": cfg.TICK_INTERVAL,
            "qq_sandbox": cfg.QQ_SANDBOX,
            "llm_backend": cfg.LLM_BACKEND,
            "qq_target_set": bool(cfg.QQ_TARGET_ID),
        },
        "functionality": functionality,
        "thought_action_bridge_observation": _build_thought_action_bridge_observation(state),
        "state_snapshot": state,
        "soul_assessment": {
            "score_0_to_1": round(soul_score, 3),
            "components": soul_components,
            "note": "This score is heuristic. Final judgement requires human dialogue review for coherence, empathy, and identity continuity.",
        },
        "manual_review_prompts": [
            "During the window, send at least 10 mixed-emotion QQ messages and record reply relevance.",
            "Check whether Helios references recent context or memory in a coherent way.",
            "Check if tone remains emotionally congruent without collapsing into repetitive template outputs.",
        ],
    }

    out_path = Path(args.report)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"report": str(out_path), "soul_score": report["soul_assessment"]["score_0_to_1"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
