"""Real-LLM end-to-end smoke for R-PROTO-LEARN 6-layer emotion system.

Sends a category-tagged Chinese dialogue set through the 6-layer
appraisal pipeline (Layer 1 fallback + description + interoception +
Layer 2 LLM + Layer 3 prediction + Layer 4 affect-memory + Layer 5
Bayesian) and reports:
  - Per-message Layer 1 baseline (R40 + R97/R98 + R-PROTO-LEARN.6)
  - Per-message full 6-layer final appraisal
  - Per-message Layer 5 top concepts (Bayesian prior read)
  - LLM usage (request count, token estimate)

This is the operational validation for the 5/6-shipped layers
(.6 / .5 / .1 / .2 / .3 / .4). The script compares baseline
(only Layer 1 + .5 + .1) vs full pipeline (.6 + .1 + .5 + .2 + .3 + .4).

Owner: R-PROTO-LEARN validation tooling. Read-only with respect to
owner contracts; it composes existing owner APIs only.

Run:
    python helios_v2/scripts/r_proto_learn_real_llm_smoke.py
    python helios_v2/scripts/r_proto_learn_real_llm_smoke.py --messages 5
    python helios_v2/scripts/r_proto_learn_real_llm_smoke.py --offline  # mock LLM
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

# ----- path setup so this works from anywhere -----
_SCRIPT_DIR = Path(__file__).resolve().parent
_HELIOS_V2_DIR = _SCRIPT_DIR.parent
_PROJECT_DIR = _HELIOS_V2_DIR.parent
sys.path.insert(0, str(_HELIOS_V2_DIR / "src"))
sys.path.insert(0, str(_HELIOS_V2_DIR))  # for `tests.r79d.framework`
sys.path.insert(0, str(_PROJECT_DIR / "scripts"))


from helios_v2.appraisal.concept_state import (
    DEFAULT_CONCEPTS,
    normalize,
    top_concepts,
)
from helios_v2.appraisal.engine import (
    AffectMemoryRecallSource,
    GroundedDimensionEstimator,
    InteroceptionSource,
    LlmAppraisalSource,
    PredictionSource,
    RapidDimensionEstimate,
)
from helios_v2.sensory import Stimulus


# --------------------------------------------------------------------------- #
# Dialogue set: 8 ZH emotion-tagged messages, 2 per emotion dimension.        #
# Categories follow the R97/R98 hardcode tags.                                #
# --------------------------------------------------------------------------- #

DIALOGUE_ZH = (
    # threat
    ("threat_smoke", "有人在跟踪我，我好害怕"),
    ("threat_criticism", "你做的根本不对，我很生气"),
    # reward
    ("reward_praise", "你今天表现真棒，我为你骄傲"),
    ("reward_love", "跟你在一起的感觉很温暖"),
    # novelty
    ("novelty_strange", "今天街上出现了一只会说话的猫"),
    # social
    ("social_alone", "今天一个人在家，没人陪我"),
    # uncertainty
    ("uncertainty_confused", "这个问题的答案到底是什么？我完全搞不清"),
    # low-emotion
    ("calm_neutral", "今天天气不错"),
)


# --------------------------------------------------------------------------- #
# Stub Sources (all optional injection points)                                #
# --------------------------------------------------------------------------- #


class _StubHormone(InteroceptionSource):
    """Stub hormone state — rotates through 4 deterministic states for the test."""

    _STATES = (
        # baseline (calm)
        {"cortisol": 0.3, "oxytocin": 0.4, "serotonin": 0.6,
         "dopamine": 0.5, "norepinephrine": 0.4, "inhibition": 0.5},
        # stressed
        {"cortisol": 0.8, "oxytocin": 0.3, "serotonin": 0.4,
         "dopamine": 0.4, "norepinephrine": 0.7, "inhibition": 0.5},
        # bonded
        {"cortisol": 0.3, "oxytocin": 0.8, "serotonin": 0.7,
         "dopamine": 0.6, "norepinephrine": 0.4, "inhibition": 0.5},
        # excited
        {"cortisol": 0.5, "oxytocin": 0.5, "serotonin": 0.5,
         "dopamine": 0.8, "norepinephrine": 0.6, "inhibition": 0.4},
    )

    def __init__(self) -> None:
        self._i = 0

    def hormone_state_snapshot(self) -> Mapping[str, float]:
        s = self._STATES[self._i % len(self._STATES)]
        self._i += 1
        return dict(s)


class _StubPredictor(PredictionSource):
    """Stub predictor: returns the rolling mean of the last 3 actual estimates."""

    def __init__(self) -> None:
        self._history: list[RapidDimensionEstimate] = []

    def record(self, actual: RapidDimensionEstimate) -> None:
        self._history.append(actual)
        if len(self._history) > 3:
            self._history.pop(0)

    def predict(self, content: str) -> RapidDimensionEstimate | None:  # noqa: ARG002
        if not self._history:
            return None
        n = len(self._history)
        return RapidDimensionEstimate(
            threat=sum(e.threat for e in self._history) / n,
            reward=sum(e.reward for e in self._history) / n,
            novelty=sum(e.novelty for e in self._history) / n,
            uncertainty=sum(e.uncertainty for e in self._history) / n,
            social=sum(e.social for e in self._history) / n,
        )


class _StubAffectMemory(AffectMemoryRecallSource):
    """Stub affect-memory: hardcoded per-emotion-tag means (simulates R85 recall)."""

    _REPLAY = {
        "threat_smoke": (0.85, 0.05),
        "threat_criticism": (0.65, 0.10),
        "reward_praise": (0.05, 0.85),
        "reward_love": (0.05, 0.80),
        "novelty_strange": (0.30, 0.45),
        "social_alone": (0.45, 0.10),
        "uncertainty_confused": (0.40, 0.05),
        "calm_neutral": (0.10, 0.30),
    }

    def __init__(self) -> None:
        self._seen: list[str] = []

    def record_seen(self, tag: str) -> None:
        self._seen.append(tag)

    def recall_affect(self, content: str) -> tuple[float | None, float | None]:  # noqa: ARG002
        # Use the LAST seen tag's replay (simulates: "we just learned
        # about a similar input; what was its affect?"). This
        # produces a strong pattern-completion signal for repeat
        # categories and a mild prior for new ones.
        if not self._seen:
            return (None, None)
        last = self._seen[-1]
        return self._REPLAY.get(last, (None, None))


# --------------------------------------------------------------------------- #
# Real LLM source (composition glue; uses RealLlmGateway if available)         #
# --------------------------------------------------------------------------- #


class _RealLlmAppraisalSource(LlmAppraisalSource):
    """LlmAppraisalSource backed by the R82 `LlmGateway` (production gateway)."""

    def __init__(self) -> None:
        # Lazy import: this script's offline mode should not require
        # the gateway module to load.
        from helios_v2.llm.engine import (  # type: ignore
            LlmGateway, LlmProfileRegistry, OpenAICompatibleProvider,
        )
        from helios_v2.llm.contracts import (  # type: ignore
            LlmMessage, LlmProfile, LlmRequest, LlmResponseFormat,
        )
        # Build a 1-profile registry from the .env-configured model.
        model = os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1")
        api_key_env = os.environ.get("HELIOS_LLM_API_KEY_ENV", "OPENAI_API_KEY")
        profile = LlmProfile(
            profile_name="r_proto_learn_appraisal",
            model=model,
            api_key_env=api_key_env,
            base_url=base_url,
            temperature=0.0,  # deterministic for stable JSON output
            max_tokens=200,
            timeout=30.0,
            default_response_format="json_object",
        )
        registry = LlmProfileRegistry(profiles=(profile,))
        provider = OpenAICompatibleProvider()
        self._gw = LlmGateway(provider=provider, registry=registry)
        self._LlmMessage = LlmMessage
        self._LlmRequest = LlmRequest
        self._LlmResponseFormat = LlmResponseFormat
        self._profile = profile.profile_name
        self.call_count = 0
        self.total_latency_ms = 0.0

    def llm_appraise(self, content: str) -> Mapping[str, float] | None:
        self.call_count += 1
        user_prompt = (
            "你是一个情绪评估器。对下面这句中文, 直接给出 5 个 0~1 之间的浮点数 "
            "(用 JSON: {\"threat\": 0.x, \"reward\": 0.x, \"novelty\": 0.x, "
            "\"social\": 0.x, \"uncertainty\": 0.x}).\n"
            f"文本: {content}\n"
            "只输出 JSON, 不要任何额外文字。"
        )
        req = self._LlmRequest(
            request_id=f"rpl_appraise_{self.call_count}",
            target_profile=self._profile,
            messages=(self._LlmMessage(
                role="user", content=user_prompt
            ),),
            response_format="json_object",
            metadata={"purpose": "r_proto_learn_smoke"},
        )
        t0 = time.time()
        try:
            completion = self._gw.complete(req)
        except Exception as e:  # pragma: no cover - real LLM path
            print(f"[LLM ERROR] {type(e).__name__}: {e}", file=sys.stderr)
            return None
        self.total_latency_ms += (time.time() - t0) * 1000
        try:
            text = completion.output_text or ""
            # Find first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end < 0 or end <= start:
                return None
            obj = json.loads(text[start:end + 1])
            return {
                k: float(v) for k, v in obj.items()
                if k in ("threat", "reward", "novelty", "social", "uncertainty")
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:  # pragma: no cover
            print(f"[LLM PARSE ERROR] {e}: {completion.output_text[:200]}", file=sys.stderr)
            return None


class _OfflineLlmAppraisalSource(LlmAppraisalSource):
    """Offline mock: returns hardcoded 5-dim reads per content (no LLM)."""

    def __init__(self) -> None:
        self.call_count = 0

    def llm_appraise(self, content: str) -> Mapping[str, float] | None:
        self.call_count += 1
        # Heuristic: keyword-based, deterministic
        threat_kw = ("害怕", "跟踪", "生气", "不对", "危险", "怕")
        reward_kw = ("棒", "骄傲", "温暖", "喜欢", "开心")
        novelty_kw = ("奇怪", "会说话", "第一次", "新颖")
        social_kw = ("一起", "陪我", "孤独", "没人")
        uncertainty_kw = ("搞不清", "到底", "为什么", "不懂")
        c = content
        return {
            "threat": 0.8 if any(k in c for k in threat_kw) else 0.05,
            "reward": 0.8 if any(k in c for k in reward_kw) else 0.05,
            "novelty": 0.7 if any(k in c for k in novelty_kw) else 0.2,
            "social": 0.7 if any(k in c for k in social_kw) else 0.1,
            "uncertainty": 0.7 if any(k in c for k in uncertainty_kw) else 0.1,
        }


# --------------------------------------------------------------------------- #
# Estimator builders                                                          #
# --------------------------------------------------------------------------- #


def _build_baseline_estimator() -> GroundedDimensionEstimator:
    """Layer 1 + R97/R98 + R-PROTO-LEARN.6 + .1 (no LLM, no prediction, no memory)."""

    class _MemSrc:
        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 0.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    class _ProtoSrc:
        def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
            return 0.0

    return GroundedDimensionEstimator(
        similarity_source=_MemSrc(),
        ambiguity_source=_MemSrc(),
        social_source=_SocSrc(),
        prototype_source=_ProtoSrc(),
        description_threshold=1.0,  # .6 default — always description fallback
    )


def _build_full_estimator(
    *,
    llm_source: LlmAppraisalSource | None,
    predictor: _StubPredictor,
    memory: _StubAffectMemory,
    hormone: _StubHormone,
) -> GroundedDimensionEstimator:
    """6-layer pipeline: .6 + .1 + .5 + .2 + .3 + .4."""

    class _MemSrc:
        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 0.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    class _ProtoSrc:
        def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
            return 0.0

    return GroundedDimensionEstimator(
        similarity_source=_MemSrc(),
        ambiguity_source=_MemSrc(),
        social_source=_SocSrc(),
        prototype_source=_ProtoSrc(),
        description_threshold=1.0,
        interoception_source=hormone,
        interoception_gain=0.5,  # slightly higher for end-to-end visibility
        llm_appraisal_source=llm_source,
        llm_appraisal_threshold=0.4,
        llm_appraisal_blend_alpha=0.5,
        prediction_source=predictor,
        surprise_gain=0.3,
        affect_memory_source=memory,
        affect_memory_gain=0.3,
    )


# --------------------------------------------------------------------------- #
# Per-message record                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class MessageRecord:
    tag: str
    content: str
    layer1: RapidDimensionEstimate
    full: RapidDimensionEstimate
    top_concepts: list[tuple[str, float]] = field(default_factory=list)
    pred_error: float = 0.0


def _seed_predictor(
    predictor: _StubPredictor,
    baseline: GroundedDimensionEstimator,
    warmup: tuple[str, str, str, str] = (
        "warmup1", "warmup2", "warmup3", "warmup4",
    ),
) -> None:
    """Pre-seed the predictor's history with warmup estimates."""
    for tag in warmup:
        s = Stimulus(
            stimulus_id=tag,
            source_name="warmup",
            modality="text",
            content=f"warmup-{tag}",
            channel=None,
            metadata=None,
            provenance_signal_id="warmup",
        )
        e = baseline.estimate_dimensions(s)
        predictor.record(e)


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=len(DIALOGUE_ZH))
    parser.add_argument("--offline", action="store_true",
                        help="Use mock LLM (no real gateway call).")
    parser.add_argument("--out", type=str, default="/tmp/r_proto_learn_real_llm_report.json")
    args = parser.parse_args()

    msgs = DIALOGUE_ZH[: args.messages]
    print(f"=== R-PROTO-LEARN real-LLM smoke ===")
    print(f"Mode: {'OFFLINE (mock LLM)' if args.offline else 'REAL LLM'}")
    print(f"Messages: {len(msgs)}")
    print()

    if args.offline:
        llm = _OfflineLlmAppraisalSource()
    else:
        llm = _RealLlmAppraisalSource()

    predictor = _StubPredictor()
    memory = _StubAffectMemory()
    hormone = _StubHormone()

    baseline = _build_baseline_estimator()
    baseline.seed_prior()
    full = _build_full_estimator(
        llm_source=llm, predictor=predictor, memory=memory, hormone=hormone
    )
    full.seed_prior()

    # Warm up predictor so the first real message has history.
    _seed_predictor(predictor, baseline)

    records: list[MessageRecord] = []
    for i, (tag, content) in enumerate(msgs):
        s = Stimulus(
            stimulus_id=f"m{i}",
            source_name="smoke",
            modality="text",
            content=content,
            channel=None,
            metadata=None,
            provenance_signal_id="smoke",
        )
        layer1 = baseline.estimate_dimensions(s)
        full_out = full.estimate_dimensions(s)

        # Compute prediction error (post-Layer-3, what Layer 3 saw)
        # The full pipeline already includes Layer 3; we report the
        # uncertainty difference as a proxy.
        pred = predictor.predict(content)
        if pred is not None:
            err = (
                abs(full_out.threat - pred.threat)
                + abs(full_out.reward - pred.reward)
                + abs(full_out.novelty - pred.novelty)
                + abs(full_out.uncertainty - pred.uncertainty)
                + abs(full_out.social - pred.social)
            ) / 5.0
        else:
            err = 0.0

        # Top concepts from Layer 5
        prior = full.concept_prior[0]
        norm = normalize(prior)
        top = top_concepts(prior, k=3)
        top_list = [(name, round(prob, 3)) for name, prob in top]

        records.append(
            MessageRecord(
                tag=tag,
                content=content,
                layer1=layer1,
                full=full_out,
                top_concepts=top_list,
                pred_error=round(err, 4),
            )
        )

        # Feed predictor with the actual full result.
        predictor.record(full_out)
        # Feed memory with this message's tag.
        memory.record_seen(tag)

    # Print summary table
    print(f"{'tag':22s}  {'L1.threat':9s} {'L1.reward':9s}  "
          f"{'F.threat':9s} {'F.reward':9s}  {'top_concept':30s} {'pred_err':8s}")
    print("-" * 110)
    for r in records:
        top_str = r.top_concepts[0][0] if r.top_concepts else "—"
        top_str = f"{top_str} ({r.top_concepts[0][1]:.2f})" if r.top_concepts else "—"
        print(
            f"{r.tag:22s}  "
            f"{r.layer1.threat:9.3f} {r.layer1.reward:9.3f}  "
            f"{r.full.threat:9.3f} {r.full.reward:9.3f}  "
            f"{top_str:30s} {r.pred_error:8.4f}"
        )
    print()
    print(f"LLM call count: {llm.call_count}")
    if isinstance(llm, _RealLlmAppraisalSource):
        print(f"LLM total latency: {llm.total_latency_ms:.0f} ms "
              f"({llm.total_latency_ms / max(1, llm.call_count):.0f} ms/call avg)")
    print()

    # Layer 5 prior summary (after all messages)
    final_prior = full.concept_prior[0]
    final_norm = normalize(final_prior)
    print("Final Layer 5 prior (top 5 concepts, Laplace-smoothed):")
    for name, prob in sorted(final_norm.items(), key=lambda x: -x[1])[:5]:
        print(f"  {name:18s}  {prob:.3f}")
    print()

    # Persist
    out = {
        "mode": "offline" if args.offline else "real_llm",
        "messages": len(records),
        "llm_calls": llm.call_count,
        "records": [
            {
                "tag": r.tag,
                "content": r.content,
                "layer1": {
                    "threat": r.layer1.threat,
                    "reward": r.layer1.reward,
                    "novelty": r.layer1.novelty,
                    "social": r.layer1.social,
                    "uncertainty": r.layer1.uncertainty,
                },
                "full": {
                    "threat": r.full.threat,
                    "reward": r.full.reward,
                    "novelty": r.full.novelty,
                    "social": r.full.social,
                    "uncertainty": r.full.uncertainty,
                },
                "top_concepts": [
                    {"name": n, "prob": p} for n, p in r.top_concepts
                ],
                "pred_error": r.pred_error,
            }
            for r in records
        ],
        "final_prior_top5": sorted(
            [{"name": k, "prob": v} for k, v in final_norm.items()],
            key=lambda x: -x["prob"],
        )[:5],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Report written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())