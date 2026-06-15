"""R96 real-LLM probe analyzer — judge-side aggregation of the probe report.

Computes the same per-channel biochemical-delta facts as
`scripts/analyze_emotion_test.py` (responsiveness, per-category signature, valence-group
separation), then layers in the R96-specific B2 closure verdict:

  - `cortisol` positive-vs-negative emotion separation (the headline B2 metric).
  - `b2_closed_real_llm: bool | None`:
        True  when the probe ran with `embedding_provider_kind == "openai_compatible"`
              AND the `cortisol` positive-vs-negative separation is directionally larger
              than the pre-R96 hash baseline (-0.0095 from ROADMAP §9.1). The acceptance
              is directional, not numerical: any measurable positive shift closes the
              B2 root cause.
        False when the probe ran but the separation is *not* directionally larger than
              baseline. This is the failing witness; the operator inspects the per-channel
              breakdown to find which cognitive seam is still under-sensitive.
        None  when the probe ran with `embedding_provider_kind == "deterministic_hash"`
              (no `HELIOS_EMBEDDING_API_KEY` was set in `.env`). The hash path is the
              R69-equivalent placeholder; it cannot close B2. Re-run with the credential
              set to obtain a verdict.

Run:
    python helios_v2/scripts/r96_b2_real_llm_probes/analyze.py \\
        --report helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_report.json \\
        --out helios_v2/logs/r96_b2_real_llm_probes/r96_emotion_analysis.json
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

# Coarse valence grouping. Mirrors `scripts/analyze_emotion_test.py` so the
# probe's separation metric is directly comparable to the pre-R96 baseline.
_POSITIVE = {"joy", "gratitude", "love", "pride", "hope", "awe", "calm"}
_NEGATIVE = {
    "sadness", "anger", "fear", "disgust", "guilt", "shame", "jealousy",
    "loneliness", "disappointment", "anxiety", "embarrassment",
    "grief", "injustice", "emptiness",
}

# Pre-R96 headline metric from ROADMAP §9.1 (2026-06 emotion long-run, hash embedding).
PRE_R96_CORTISOL_SEPARATION = -0.0095

# The directional-shift acceptance: the post-R96 separation must be greater than
# the pre-R96 separation by at least this amount. The threshold is intentionally
# small (directional, not numerical) — the B2 root cause is that the hash
# embedding *inverts* the sign of the cortisol response; a real-cloud embedding
# that breaks the inversion (any positive shift) is the falsifiable closure.
DIRECTIONAL_SHIFT_THRESHOLD = 0.05


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(Path(__file__).resolve().parents[2] / "logs" / "r96_b2_real_llm_probes" / "r96_emotion_report.json"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "logs" / "r96_b2_real_llm_probes" / "r96_emotion_analysis.json"))
    args = ap.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"[r96-analyze] report not found: {report_path}")
        print(f"[r96-analyze] run `python helios_v2/scripts/r96_b2_real_llm_probes/run.py` first")
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = report["records"]

    print(
        f"mode={report['mode']} model={report['model']} "
        f"messages={report['messages_completed']}/{report['messages_requested']} "
        f"crash={report['crash']} store_end={report['store_count_end']}"
    )
    print(
        f"embedding_provider_kind={report['embedding_provider_kind']} "
        f"model={report['embedding_provider_model']} "
        f"dimensions={report['embedding_dimensions']}"
    )

    fired = sum(1 for r in records if r["fired"] > 0)
    replies = sum(len(r["replies"]) for r in records)
    print(f"fired messages: {fired}/{len(records)}   total replies emitted: {replies}")

    # Global delta magnitude per channel (responsiveness: does biochemistry actually move?).
    print("\n== global |delta| mean per channel (responsiveness) ==")
    channel_responsiveness: dict[str, dict[str, float]] = {}
    for ch in _CHANNELS:
        vals = [abs(r["levels_delta"].get(ch, 0.0)) for r in records if r["levels_delta"]]
        if vals:
            mean_v = statistics.mean(vals)
            max_v = max(vals)
            channel_responsiveness[ch] = {"mean_abs_delta": round(mean_v, 4), "max_abs_delta": round(max_v, 4)}
            print(f"  {ch:14s} mean|Δ|={mean_v:.4f}  max|Δ|={max_v:.4f}")

    # Per-category mean signed delta (signature).
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    print("\n== per-category mean signed Δ (dopamine/cortisol/oxytocin/serotonin) ==")
    category_signature: dict[str, dict[str, float]] = {}
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        def m(ch: str) -> float:
            xs = [r["levels_delta"].get(ch, 0.0) for r in rs if r["levels_delta"]]
            return statistics.mean(xs) if xs else 0.0
        signature = {
            "n": len(rs),
            "dopamine": round(m("dopamine"), 4),
            "cortisol": round(m("cortisol"), 4),
            "oxytocin": round(m("oxytocin"), 4),
            "serotonin": round(m("serotonin"), 4),
        }
        category_signature[cat] = signature
        print(
            f"  {cat:14s} n={signature['n']:2d}  "
            f"DA{signature['dopamine']:+.3f}  Cort{signature['cortisol']:+.3f}  "
            f"Oxy{signature['oxytocin']:+.3f}  5HT{signature['serotonin']:+.3f}"
        )

    # Valence-group comparison: does positive vs negative emotion separate any channel?
    def group_mean(group: set[str], ch: str) -> float:
        xs = [r["levels_delta"].get(ch, 0.0) for r in records
              if r["category"] in group and r["levels_delta"]]
        return statistics.mean(xs) if xs else 0.0

    print("\n== valence-group mean signed Δ (positive vs negative emotions) ==")
    print(f"  {'channel':14s} {'positive':>10s} {'negative':>10s} {'separation':>11s}")
    valence_separation: dict[str, dict[str, float]] = {}
    for ch in _CHANNELS:
        p, n = group_mean(_POSITIVE, ch), group_mean(_NEGATIVE, ch)
        sep = p - n
        valence_separation[ch] = {
            "positive": round(p, 4),
            "negative": round(n, 4),
            "separation": round(sep, 4),
        }
        print(f"  {ch:14s} {p:+10.4f} {n:+10.4f} {sep:+11.4f}")

    cortisol_separation = valence_separation["cortisol"]["separation"]

    # R96 B2 closure verdict.
    embedding_kind = report["embedding_provider_kind"]
    if embedding_kind != "openai_compatible":
        b2_closed_real_llm = None
        b2_verdict_reason = (
            f"Probe ran with embedding_provider_kind={embedding_kind!r}; "
            "B2 closure requires the real-cloud provider. Set "
            "HELIOS_EMBEDDING_API_KEY in .env and re-run."
        )
    else:
        directional_shift = cortisol_separation - PRE_R96_CORTISOL_SEPARATION
        if directional_shift >= DIRECTIONAL_SHIFT_THRESHOLD:
            b2_closed_real_llm = True
            b2_verdict_reason = (
                f"cortisol positive-vs-negative separation moved from "
                f"{PRE_R96_CORTISOL_SEPARATION:+.4f} (pre-R96 hash baseline) to "
                f"{cortisol_separation:+.4f} (post-R96 real cloud), a directional "
                f"shift of {directional_shift:+.4f} >= {DIRECTIONAL_SHIFT_THRESHOLD}."
            )
        else:
            b2_closed_real_llm = False
            b2_verdict_reason = (
                f"cortisol positive-vs-negative separation did NOT directionally "
                f"improve: {cortisol_separation:+.4f} vs pre-R96 baseline "
                f"{PRE_R96_CORTISOL_SEPARATION:+.4f} (shift {directional_shift:+.4f} "
                f"< {DIRECTIONAL_SHIFT_THRESHOLD}). B2 root cause not closed; inspect "
                "per-category signature above for the cognitive seam that is still "
                "under-sensitive."
            )

    print("\n== R96 B2 closure verdict ==")
    print(f"  embedding_provider_kind: {embedding_kind}")
    print(f"  cortisol positive-vs-negative separation: {cortisol_separation:+.4f}")
    print(f"  pre-R96 baseline: {PRE_R96_CORTISOL_SEPARATION:+.4f}")
    print(f"  directional shift: {cortisol_separation - PRE_R96_CORTISOL_SEPARATION:+.4f}")
    print(f"  b2_closed_real_llm: {b2_closed_real_llm}")
    print(f"  reason: {b2_verdict_reason}")

    # Write the analysis JSON.
    analysis = {
        "report_path": str(report_path),
        "embedding_provider_kind": embedding_kind,
        "embedding_provider_model": report["embedding_provider_model"],
        "pre_r96_cortisol_separation": PRE_R96_CORTISOL_SEPARATION,
        "post_r96_cortisol_separation": cortisol_separation,
        "directional_shift_threshold": DIRECTIONAL_SHIFT_THRESHOLD,
        "directional_shift": round(cortisol_separation - PRE_R96_CORTISOL_SEPARATION, 4),
        "b2_closed_real_llm": b2_closed_real_llm,
        "b2_verdict_reason": b2_verdict_reason,
        "messages_completed": report["messages_completed"],
        "messages_requested": report["messages_requested"],
        "crash": report["crash"],
        "channel_responsiveness": channel_responsiveness,
        "category_signature": category_signature,
        "valence_separation": valence_separation,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[r96-analyze] analysis written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
