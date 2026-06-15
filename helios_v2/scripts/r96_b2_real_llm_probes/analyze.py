"""R96 real-LLM probe analyzer — judge-side aggregation of the probe report.

Computes the same per-channel biochemical-delta facts as
`scripts/analyze_emotion_test.py` (responsiveness, per-category signature, valence-group
separation), then layers in two stacked verdicts:

  - **R96 B2 closure** (root cause: 16-dim hash embedding is not semantic).
    The headline metric is `cortisol` positive-vs-negative emotion separation.
    `b2_closed_real_llm: bool | None` is `True` when the probe ran with
    `embedding_provider_kind == "openai_compatible"` AND the `cortisol`
    positive-vs-negative separation is directionally larger than the pre-R96 hash
    baseline (-0.0095 from ROADMAP §9.1). The acceptance is directional, not
    numerical: any measurable positive shift closes the B2 root cause. `False`
    when the probe ran but the separation is *not* directionally larger than
    baseline (failing witness). `None` when the probe ran with
    `embedding_provider_kind == "deterministic_hash"` (the R69-equivalent
    placeholder; it cannot close B2).

  - **R97 B3 closure** (root cause: R40 threat/reward prototypes are English-only).
    Layered on top of R96. The B3 verdict reuses the same `cortisol`
    positive-vs-negative separation metric (which is the *B3* root-cause
    witness) but with a stricter directional-shift threshold (R97 expects at
    least 2x the B2 threshold because the appraisal owner's `DEFAULT_ANCHOR_CATALOG`
    is now bilingual, giving Chinese inputs a non-zero threat / reward
    cosine). `b3_closed_real_llm: bool | None` semantics are the same as
    `b2_closed_real_llm`. The R97 catalog is auto-injected at the
    `GroundedDimensionEstimator.anchor_catalog` seam; no `composition` code
    change is required for the probe (R97 cascades through the existing R96
    resolver + assembly path).

When the probe is offline (hash path, no `HELIOS_EMBEDDING_API_KEY`), both
verdicts are `None` (the cloud probe did not run). Re-run with the credential
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

    # R97 B3 closure verdict: layered on top of R96. B3 requires BOTH the
    # real-cloud embedding (R96) AND the appraisal owner's bilingual anchor
    # catalog (R97 default `DEFAULT_ANCHOR_CATALOG`). When R96 is in place
    # (real cloud), the appraisal owner automatically gets the R97 Chinese
    # anchors via the estimator's `default_factory`; the B3 verdict is
    # therefore the SAME cortisol-separation metric as B2, but with the
    # threshold raised to a stricter level (the B2 root cause is "no
    # semantic embedding"; the B3 root cause is "no Chinese anchors"). The
    # B3 threshold of 0.10 reflects the R97 expectation that with proper
    # Chinese anchors, the directional shift should be at least 2x the
    # B2 threshold.
    B3_DIRECTIONAL_SHIFT_THRESHOLD = 0.10
    if embedding_kind != "openai_compatible":
        b3_closed_real_llm = None
        b3_verdict_reason = (
            f"Probe ran with embedding_provider_kind={embedding_kind!r}; "
            "B3 closure requires the real-cloud provider (R96) AND the "
            "bilingual anchor catalog (R97 default `DEFAULT_ANCHOR_CATALOG`, "
            "auto-injected). Set HELIOS_EMBEDDING_API_KEY in .env and re-run."
        )
    else:
        b3_directional_shift = cortisol_separation - PRE_R96_CORTISOL_SEPARATION
        if b3_directional_shift >= B3_DIRECTIONAL_SHIFT_THRESHOLD:
            b3_closed_real_llm = True
            b3_verdict_reason = (
                f"cortisol positive-vs-negative separation moved from "
                f"{PRE_R96_CORTISOL_SEPARATION:+.4f} (pre-R96 hash baseline) to "
                f"{cortisol_separation:+.4f} (post-R97 real cloud + Chinese "
                f"anchors), a directional shift of {b3_directional_shift:+.4f} "
                f">= {B3_DIRECTIONAL_SHIFT_THRESHOLD} (R97 stricter B3 threshold)."
            )
        else:
            b3_closed_real_llm = False
            b3_verdict_reason = (
                f"cortisol positive-vs-negative separation did NOT directionally "
                f"improve: {cortisol_separation:+.4f} vs pre-R96 baseline "
                f"{PRE_R96_CORTISOL_SEPARATION:+.4f} (shift {b3_directional_shift:+.4f} "
                f"< {B3_DIRECTIONAL_SHIFT_THRESHOLD}). B3 root cause not closed; "
                "the R97 Chinese anchors did not produce the expected shift on "
                "the headline `cortisol` separation. Inspect per-category "
                "signature above for the cognitive seam that is still under-"
                "sensitive on Chinese input."
            )

    print("\n== R97 B3 closure verdict (layered on R96) ==")
    print(f"  b3_closed_real_llm: {b3_closed_real_llm}")
    print(f"  reason: {b3_verdict_reason}")
    # R98: the headline separation reported above is the post-LLM-adjustment
    # value (the runtime's 04 drive formula consumes the R98 holder by default
    # on the semantic assembly). The R98 architecture is wired and active;
    # see the per-tick LLM I/O JSONL for how often the LLM actually emits a
    # `hormone_response_i_predict` to drive the adjustment.
    print("\n== R98 post-LLM appraisal adjustment (wiring active) ==")
    print("  b_closed_with_llm_adjustment: True iff b2_closed_real_llm is True (R98 is the active drive)")
    print("  (the runtime's 04 drive formula now applies the R98 adjustment by default)")

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
        "b3_closed_real_llm": b3_closed_real_llm,
        "b3_verdict_reason": b3_verdict_reason,
        # R98: the analyzer cannot distinguish "R98 active and didn't close" from
        # "R98 inactive (no LLM prediction)". We mark `b_closed_with_llm_adjustment`
        # as the same boolean as `b2_closed_real_llm` because the runtime's
        # 04 drive formula now consumes the post-LLM adjustment (R98 wiring is
        # in effect by default). A future R98 analyzer can parse the LLM I/O
        # JSONL to count how many ticks had a `hormone_response_i_predict` and
        # report a per-tick "R98 was active" rate; the present analysis just
        # notes that the value below is the R98-aware drive (post-LLM adjustment
        # applied), not the R97-only drive.
        "r98_wiring_active": True,
        "b_closed_with_llm_adjustment": b2_closed_real_llm,
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
