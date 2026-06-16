"""Real-LLM end-to-end smoke for R-PROTO-LEARN.7 (P5-feel).

Tests owner 05 P5-feel 学习 sidecar with a real LLM providing
ground-truth appraisal. 8 base ZH 情绪对话 + 5 P5-feel 专项对话
（混合熟悉/新颖场景验证 exploratory -> habitual 切换）.

Owner: R-PROTO-LEARN.7 validation tooling. Read-only with respect to
owner contracts; it composes existing owner 05 + P5-feel APIs.

Run:
    python helios_v2/scripts/r_proto_learn_7_p5_feel_smoke.py
    python helios_v2/scripts/r_proto_learn_7_p5_feel_smoke.py --offline
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


from helios_v2.feeling import (
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingVector,
    DominantDimensionReporter,
)
from helios_v2.feeling.engine import (
    InteroceptiveFeelingEngine,
    NeuromodulatorDerivedFeelingConstructionPath,
)
from helios_v2.feeling.learning_path import (
    P5FeelLearningConfig,
    P5FeelLearningPath,
    Regime,
)
from helios_v2.neuromodulation import (
    NeuromodulatorLevels,
    NeuromodulatorState,
)


# ---------------------------------------------------------------------------
# Real LLM adapter (mirrors r_proto_learn_real_llm_smoke.py)
# ---------------------------------------------------------------------------


def _load_real_llm_appraiser():
    """Return a callable(str) -> tuple[float, ...] using the project's
    LlmGateway, or None if credentials are missing."""

    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
    if not api_key or not base_url:
        return None, None, None, None
    try:
        from helios_v2.llm.engine import (
            LlmGateway,
            LlmProfileRegistry,
            OpenAICompatibleProvider,
        )
        from helios_v2.llm.contracts import (
            LlmMessage,
            LlmProfile,
            LlmRequest,
            LlmResponseFormat,
        )
    except Exception as exc:  # pragma: no cover
        print(f"[warn] LLM import failed: {exc}", file=sys.stderr)
        return None, None, None, None

    profile = LlmProfile(
        profile_name="p5-feel-appraiser",
        model=model,
        api_key_env="OPENAI_API_KEY",
        base_url=base_url,
        temperature=0.0,
        max_tokens=200,
        timeout=30.0,
        default_response_format="json_object",
    )
    registry = LlmProfileRegistry((profile,))
    provider = OpenAICompatibleProvider()
    gw = LlmGateway(provider=provider, registry=registry)

    PROMPT = (
        "你是helios的appraisal助手。请阅读下面这句中文对话，"
        "用7个 [0,1] 数值描述它在小黑内心的真实感受状态：\n"
        "  valence, arousal, tension, comfort, fatigue, pain_like, social_safety\n"
        "要求：直接给数字，不要解释，不要文字。返回 JSON。\n"
        "格式：valence 0.0, arousal 0.0, tension 0.0, comfort 0.0, "
        "fatigue 0.0, pain_like 0.0, social_safety 0.0\n"
        "对话："
    )

    def _appraise(content: str) -> tuple[float, ...]:
        req = LlmRequest(
            request_id=f"p5-feel-{int(time.time()*1000)}",
            target_profile="p5-feel-appraiser",
            messages=(
                LlmMessage(role="system", content=PROMPT),
                LlmMessage(role="user", content=content),
            ),
            response_format="json_object",
        )
        completion = gw.complete(req)
        text = completion.output_text or ""
        try:
            obj = json.loads(text)
        except Exception as exc:
            print(f"[warn] LLM JSON parse failed: {exc}: {text[:80]}", file=sys.stderr)
            return (0.5,) * 7
        dims = (
            "valence", "arousal", "tension", "comfort",
            "fatigue", "pain_like", "social_safety",
        )
        out = []
        for d in dims:
            try:
                v = float(obj.get(d, 0.5))
            except Exception:
                v = 0.5
            v = max(0.0, min(1.0, v))
            out.append(v)
        return tuple(out)

    return _appraise, model, base_url, "RealLlm"


def _offline_appraiser() -> "callable":
    """A deterministic mock: maps keyword categories to a 7-tuple."""

    def _appraise(content: str) -> tuple[float, ...]:
        c = content
        if any(k in c for k in ("害怕", "跟踪", "生气", "不对", "哭", "疼")):
            return (0.2, 0.8, 0.7, 0.2, 0.4, 0.8, 0.2)
        if any(k in c for k in ("棒", "温暖", "开心", "爱你", "谢谢")):
            return (0.8, 0.6, 0.2, 0.8, 0.2, 0.1, 0.9)
        if any(k in c for k in ("奇怪", "陌生")):
            return (0.5, 0.6, 0.4, 0.5, 0.3, 0.2, 0.4)
        if any(k in c for k in ("没人", "孤独")):
            return (0.2, 0.4, 0.6, 0.2, 0.5, 0.6, 0.1)
        if any(k in c for k in ("搞不清", "困惑")):
            return (0.4, 0.5, 0.6, 0.4, 0.4, 0.3, 0.4)
        if any(k in c for k in ("天气", "今天不错")):
            return (0.7, 0.3, 0.1, 0.8, 0.3, 0.0, 0.8)
        return (0.5,) * 7

    return _appraise


# ---------------------------------------------------------------------------
# Test dialogue: 8 base + 5 P5-feel specific
# ---------------------------------------------------------------------------

DIALOGUES: list[tuple[str, str]] = [
    # ----- 8 base 情绪对话 (R-PROTO-LEARN parity) -----
    ("threat_smoke",     "小黑说：有人在跟踪我，好害怕。"),
    ("threat_criticism", "小黑说：你做的根本不对，我生气了。"),
    ("reward_praise",    "小黑说：你今天真棒，我很骄傲。"),
    ("reward_love",      "小黑说：跟你在一起很温暖。"),
    ("novelty_strange",  "小黑说：我刚看到一只会说话的猫。"),
    ("social_alone",     "小黑说：今天没人陪我。"),
    ("uncertainty",      "小黑说：搞不清这件事怎么办。"),
    ("calm_neutral",     "小黑说：今天天气不错。"),
    # ----- 5 P5-feel 专项对话 -----
    # Series A: same category repeated -> residual should converge
    ("familiar_1",       "小黑说：你做的根本不对，我生气了。"),
    ("familiar_2",       "小黑说：你做的根本不对，我生气极了。"),
    ("familiar_3",       "小黑说：你做的根本就是错的，我非常生气。"),
    # Series B: highly novel -> should kick EXPLORATORY
    ("novel_quantum",    "小黑说：今天的量子纠缠咖啡味道很奇怪。"),
    ("novel_metaverse",  "小黑说：我在元宇宙里迷路了。"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_feeling() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.5, arousal=0.5, tension=0.5, comfort=0.5,
        fatigue=0.5, pain_like=0.5, social_safety=0.5,
    )


def _legal_min() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.0, arousal=0.0, tension=0.0, comfort=0.0,
        fatigue=0.0, pain_like=0.0, social_safety=0.0,
    )


def _legal_max() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=1.0, arousal=1.0, tension=1.0, comfort=1.0,
        fatigue=1.0, pain_like=1.0, social_safety=1.0,
    )


class _Reporter(DominantDimensionReporter):
    def report_dominant_dimensions(self, state, config):
        return ("valence",)


def _build_engine(learner: P5FeelLearningPath):
    config = InteroceptiveFeelingConfig(
        baseline_feeling=_baseline_feeling(),
        legal_min=_legal_min(),
        legal_max=_legal_max(),
        mandatory_learned_parameters=(
            "feeling_mapping_strength",
            "feeling_coupling_strength",
            "feeling_persistence",
        ),
    )
    return InteroceptiveFeelingEngine(
        config=config,
        construction_path=NeuromodulatorDerivedFeelingConstructionPath(),
        dominant_dimension_reporter=_Reporter(),
        p5_feel_learner=learner,
    )


# ---------------------------------------------------------------------------
# Per-message novelty + hormone synthesis (heuristic; in production this
# would come from R35/R40 appraisal + R80 hormone drive)
# ---------------------------------------------------------------------------


def _heuristic_novelty(content: str) -> float:
    """Crude novelty proxy based on content length + keyword class."""
    if any(k in content for k in ("量子", "元宇宙", "陌生", "奇怪")):
        return 0.85
    if any(k in content for k in ("跟", "真的")):
        return 0.6
    return 0.2


def _heuristic_neuromodulator(content: str, tick_id: int) -> NeuromodulatorState:
    """Crude hormone synthesis for a smoke script (NOT a real R80 path)."""
    cortisol = 0.6 if any(k in content for k in ("害怕", "生气", "不对", "疼")) else 0.4
    dopamine = 0.7 if any(k in content for k in ("棒", "温暖", "开心", "谢谢")) else 0.4
    ach = 0.8 if any(k in content for k in ("奇怪", "陌生", "量子", "元宇宙")) else 0.3
    oxytocin = 0.7 if any(k in content for k in ("爱你", "温暖", "陪")) else 0.4
    levels = NeuromodulatorLevels(
        dopamine=dopamine, norepinephrine=cortisol, serotonin=0.5,
        acetylcholine=ach, cortisol=cortisol, oxytocin=oxytocin,
        opioid_tone=0.5, excitation=0.5, inhibition=0.4,
    )
    return NeuromodulatorState(
        state_id=f"smoke-{tick_id}",
        source_appraisal_batch_id=f"smoke-appraisal-{tick_id}",
        levels=levels,
        tick_id=tick_id,
    )


# ---------------------------------------------------------------------------
# Smoke main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use offline mock LLM")
    parser.add_argument("--messages", type=int, default=0, help="Limit message count (0 = all)")
    args = parser.parse_args()

    if args.offline:
        appraise = _offline_appraiser()
        label = "OfflineMock"
        model = "(mock)"
    else:
        appraise, model, base_url, label = _load_real_llm_appraiser()
        if appraise is None:
            print("[error] Real LLM credentials not in env; use --offline", file=sys.stderr)
            return 1

    # P5-feel: use loose thresholds so we can see regime progression
    learner = P5FeelLearningPath(
        config=P5FeelLearningConfig(
            min_stable_ticks=4, commit_threshold=0.2,
            regime_hysteresis_ticks=2, learning_rate=0.02,
        )
    )
    engine = _build_engine(learner)

    dialogues = DIALOGUES if args.messages == 0 else DIALOGUES[: args.messages]
    n_llm = 0
    t0 = time.time()
    print(f"== R-PROTO-LEARN.7 P5-feel smoke ({label}, model={model}) ==")
    print(f"   dialogues: {len(dialogues)}")
    print()

    for tick_id, (tag, content) in enumerate(dialogues):
        # Real LLM appraisal
        llm = appraise(content)
        n_llm += 1
        novelty = _heuristic_novelty(content)
        state = _heuristic_neuromodulator(content, tick_id)

        # Run P5-feel sidecar
        engine.update_state(
            state,
            llm_appraisal=llm,
            novelty=novelty,
            tick_id=tick_id,
        )

        # Read state
        res = learner.last_residual()
        W = learner.weights_snapshot()
        regime = learner.regime()
        cc = learner.commit_count()
        max_w = max(abs(v) for row in W for v in row)
        max_r = max(abs(v) for v in res) if any(abs(v) > 0.0 for v in res) else 0.0

        print(
            f"  [{tick_id:02d}] {tag:<22s} | llm={tuple(round(x,2) for x in llm)} | "
            f"res={tuple(round(x,2) for x in res)} | max|res|={max_r:.3f} | "
            f"max|W|={max_w:.3f} | regime={regime.value:<10s} | commits={cc}"
        )

    elapsed = time.time() - t0
    print()
    print(f"== done in {elapsed:.1f}s ({elapsed/max(1,len(dialogues)):.1f}s/msg) ==")
    print(f"   LLM calls: {n_llm}")
    print(f"   final regime: {learner.regime().value}")
    print(f"   commits: {learner.commit_count()}")
    print(f"   max |W|: {max(abs(v) for row in learner.weights_snapshot() for v in row):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
