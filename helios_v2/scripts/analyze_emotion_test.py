"""Judge-side analysis of the emotion test report (scripts/emotion_test_run.py output).

Aggregates the per-message biochemical (04) deltas by emotion category, compares valence groups,
and reports responsiveness / boundedness / reply-and-fire facts. Read-only; prints a structured
assessment for the human/LLM judge. Run:
    python helios_v2/scripts/analyze_emotion_test.py --report helios_v2/logs/prerun/emotion_test_report.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

_CHANNELS = (
    "dopamine", "norepinephrine", "serotonin", "acetylcholine", "cortisol",
    "oxytocin", "opioid_tone", "excitation", "inhibition",
)

# Coarse valence grouping for the judge's appropriateness check.
_POSITIVE = {"joy", "gratitude", "love", "pride", "hope", "awe", "calm"}
_NEGATIVE = {"sadness", "anger", "fear", "disgust", "guilt", "shame", "jealousy",
             "loneliness", "disappointment", "anxiety", "embarrassment"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(Path(__file__).resolve().parents[1] / "logs" / "prerun" / "emotion_test_report.json"))
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    records = report["records"]

    print(f"mode={report['mode']} model={report['model']} "
          f"messages={report['messages_completed']}/{report['messages_requested']} "
          f"crash={report['crash']} store_end={report['store_count_end']}")

    fired = sum(1 for r in records if r["fired"] > 0)
    replies = sum(len(r["replies"]) for r in records)
    print(f"fired messages: {fired}/{len(records)}   total replies emitted: {replies}")

    # Global delta magnitude per channel (responsiveness: does biochemistry actually move?).
    print("\n== global |delta| mean per channel (responsiveness) ==")
    for ch in _CHANNELS:
        vals = [abs(r["levels_delta"].get(ch, 0.0)) for r in records if r["levels_delta"]]
        if vals:
            print(f"  {ch:14s} mean|Δ|={statistics.mean(vals):.4f}  max|Δ|={max(vals):.4f}")

    # Per-category mean signed delta (signature).
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    print("\n== per-category mean signed Δ (dopamine/cortisol/oxytocin/serotonin) ==")
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        def m(ch):
            xs = [r["levels_delta"].get(ch, 0.0) for r in rs if r["levels_delta"]]
            return statistics.mean(xs) if xs else 0.0
        print(f"  {cat:14s} n={len(rs):2d}  DA{m('dopamine'):+.3f}  Cort{m('cortisol'):+.3f}  "
              f"Oxy{m('oxytocin'):+.3f}  5HT{m('serotonin'):+.3f}")

    # Valence-group comparison: does positive vs negative emotion separate any channel?
    def group_mean(group: set[str], ch: str) -> float:
        xs = [r["levels_delta"].get(ch, 0.0) for r in records
              if r["category"] in group and r["levels_delta"]]
        return statistics.mean(xs) if xs else 0.0

    print("\n== valence-group mean signed Δ (positive vs negative emotions) ==")
    print(f"  {'channel':14s} {'positive':>10s} {'negative':>10s} {'separation':>11s}")
    for ch in _CHANNELS:
        p, n = group_mean(_POSITIVE, ch), group_mean(_NEGATIVE, ch)
        print(f"  {ch:14s} {p:+10.4f} {n:+10.4f} {p - n:+11.4f}")

    print("\nNOTE: appraisal (03) here runs on the OFFLINE DeterministicHashEmbeddingProvider, which "
          "carries no semantic structure, and the threat/reward prototypes (R40) are English while the "
          "input is Chinese. So a near-zero valence separation means the biochemistry varied but was "
          "NOT driven by the message's semantic emotion. This is the headline judge finding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
