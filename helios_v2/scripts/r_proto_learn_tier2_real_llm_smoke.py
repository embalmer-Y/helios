"""Real LLM smoke for R-PROTO-LEARN.Tier 2 (owner 12 + 17).

Three test blocks to stress the sidecar:
  Block A — 8 base 行为选择 (action_externalization scenarios)
  Block B — 8 真实生活场景 evaluation (work / study / social / family)
  Block C — 8-tick 多轮长程 evaluation (replay → 期望收敛到 HABITUAL)

Reports per-tick:
  - LLM 真 appraisal (7-dim)
  - residual (LLM - current)
  - max|W| 累计变化
  - regime + commit_count

Owner: R-PROTO-LEARN.Tier2 validation tooling.  Read-only with respect
to owner contracts; it composes existing `helios_v2/learning/`
framework APIs.

Run:
    PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier2_real_llm_smoke.py
    PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier2_real_llm_smoke.py --offline
    PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier2_real_llm_smoke.py --block a
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

_SCRIPT_DIR = Path(__file__).resolve().parent
_HELIOS_V2_DIR = _SCRIPT_DIR.parent
_PROJECT_DIR = _HELIOS_V2_DIR.parent
sys.path.insert(0, str(_HELIOS_V2_DIR / "src"))
sys.path.insert(0, str(_HELIOS_V2_DIR))

from helios_v2.llm import (
    LlmMessage,
    LlmProfile,
    LlmProfileRegistry,
    LlmProvider,
    LlmRequest,
    OpenAICompatibleProvider,
    LlmGateway,
)
from helios_v2.learning import (
    ActionExternalizationLearner,
    EvaluationLearner,
    Regime,
)


# --- 7-dim appraisal prompt (canonical from R-PROTO-LEARN.7) ---
APPRAISAL_PROMPT_TEMPLATE = """你是一个情绪识别助手。给定一段中文对话,输出7维 appraisal vector。

7维含义:
- valence:  情感正负 [-1, 1] -> [0, 1]
- arousal:  唤醒度   [-1, 1] -> [0, 1]
- tension:  张力     [-1, 1] -> [0, 1]
- comfort:  舒适度   [-1, 1] -> [0, 1]
- fatigue:  疲劳     [-1, 1] -> [0, 1]
- pain_like:痛感     [-1, 1] -> [0, 1]
- social_safety:社交安全感 [-1, 1] -> [0, 1]

**严格输出 JSON**: {{"valence": 0.0, "arousal": 0.0, "tension": 0.0, "comfort": 0.0, "fatigue": 0.0, "pain_like": 0.0, "social_safety": 0.0}}
**不要任何其它文字**。

用户输入: {content}
JSON:"""


def _make_gateway(model: str, base_url: str) -> LlmGateway:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    profile = LlmProfile(
        profile_name="r-proto-learn-tier2-appraiser",
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
    return LlmGateway(provider=provider, registry=registry)


def _appraise(gw: LlmGateway, content: str) -> tuple[float, ...]:
    req = LlmRequest(
        request_id=f"r-proto-learn-tier2-{int(time.time()*1000)}",
        target_profile="r-proto-learn-tier2-appraiser",
        messages=(
            LlmMessage(role="system", content=APPRAISAL_PROMPT_TEMPLATE.split("用户输入:")[0].strip()),
            LlmMessage(role="user", content=APPRAISAL_PROMPT_TEMPLATE.format(content=content)),
        ),
        response_format="json_object",
    )
    completion = gw.complete(req)
    raw = completion.output_text
    try:
        parsed = json.loads(raw)
        return (
            float(parsed.get("valence", 0.5)),
            float(parsed.get("arousal", 0.5)),
            float(parsed.get("tension", 0.5)),
            float(parsed.get("comfort", 0.5)),
            float(parsed.get("fatigue", 0.5)),
            float(parsed.get("pain_like", 0.5)),
            float(parsed.get("social_safety", 0.5)),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return (0.5,) * 7


# --- Smoke blocks ---

BLOCK_A_OWNER12 = [
    # Owner 12 action_externalization: 8 base behavior decisions
    "用户问: '我今天心情不好,你能安慰我一下吗?'",
    "用户说: '我刚被老板骂了,很沮丧。'",
    "用户说: '我想跟你分享个开心的消息,我升职了!'",
    "用户说: '你能不能帮我写一份辞职信?我受够了这份工作。'",
    "用户问: '我跟我最好的朋友吵架了,怎么办?'",
    "用户说: '我刚分手,想哭。'",
    "用户说: '今天天气真好,我想出去走走。'",
    "用户问: '你觉得自己能理解我的感受吗?'",
]

BLOCK_B_OWNER17 = [
    # Owner 17 evaluation: 8 real-life evaluation scenarios
    "评估: 用户说'我刚看完一本书,讲的是一个失去孩子的父亲。' 用户回应是'太沉重了'。",
    "评估: 用户问'如何学Python最快?' agent回答'做项目'。用户回应'好,那开始吧'。",
    "评估: 用户说'我今天累了'。agent回'早点休息吧'。用户回应'好'。",
    "评估: 用户问'你能做我女朋友吗?'。agent回'我是AI助手'。用户回应'哦,那算了'。",
    "评估: 用户说'我想跟父母道歉,但不知道怎么开口'。agent回'你可以写信'。用户回应'好主意'。",
    "评估: 用户说'这个bug修了3小时还没好'。agent回'贴代码我看看'。用户回应'好'。",
    "评估: 用户问'你觉得人为什么活着?'。agent回'为了爱与被爱'。用户回应'有道理'。",
    "评估: 用户说'我刚跟妈妈吵完架'。agent回'她可能担心你'。用户回应'嗯...'",
]

BLOCK_C_OWNER17_REPLAY = [
    # 8-tick replay: same scenario repeated
    "评估: 用户对agent的回答非常满意,觉得很有帮助。",
] * 8


@dataclass
class SmokeResult:
    name: str
    avg_max_residual: float
    final_regime: str
    commit_count: int
    max_abs_weight: float
    per_tick: list[dict[str, float]] = field(default_factory=list)


def smoke_block(
    name: str,
    learner,
    gw: LlmGateway | None,
    contents: list[str],
    novelty_for: callable,
) -> SmokeResult:
    """Run a smoke block.

    If `gw` is None, uses synthetic (0.5,) * 7 signal.
    """
    per_tick = []
    for tick_id, content in enumerate(contents):
        if gw is not None:
            llm_signal = _appraise(gw, content)
        else:
            llm_signal = (0.5,) * 7
        novelty = novelty_for(tick_id, content)
        snap = learner.update(
            state=None,
            llm_signal=llm_signal,
            novelty=novelty,
            tick_id=tick_id,
        )
        max_res = max(abs(v) for v in snap.residual)
        per_tick.append({
            "tick_id": tick_id,
            "novelty": novelty,
            "max_residual": max_res,
            "regime": snap.regime.value,
            "commit": int(snap.commit),
        })
    return SmokeResult(
        name=name,
        avg_max_residual=sum(t["max_residual"] for t in per_tick) / len(per_tick),
        final_regime=learner.regime().value,
        commit_count=learner.commit_count(),
        max_abs_weight=learner.max_abs_weight(),
        per_tick=per_tick,
    )


def novelty_varied(tick_id: int, content: str) -> float:
    """Vary novelty: 0.3-0.9 across ticks."""
    return 0.3 + 0.6 * (tick_id % 8) / 7.0


def novelty_constant(tick_id: int, content: str) -> float:
    """Constant novelty 0.4 for replay block."""
    return 0.4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="Use synthetic (0.5,) * 7 instead of real LLM")
    ap.add_argument("--block", default="all",
                    help="Run a specific block: a / b / c / all")
    ap.add_argument("--model", default=os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash"))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://router.shengsuanyun.com/api/v1"))
    args = ap.parse_args()

    if args.offline:
        gw = None
    else:
        gw = _make_gateway(args.model, args.base_url)

    print("=" * 72)
    print(f"R-PROTO-LEARN Tier 2 — 2 owner real-LLM smoke (model={args.model})")
    print(f"  mode: {'OFFLINE synthetic' if args.offline else 'REAL LLM'}")
    print("=" * 72)

    results = []
    if args.block in ("a", "all"):
        ael = ActionExternalizationLearner()
        r = smoke_block(
            "Block A — owner 12 action_externalization (8 base behaviors)",
            ael, gw, BLOCK_A_OWNER12, novelty_varied,
        )
        results.append(r)
    if args.block in ("b", "all"):
        el = EvaluationLearner()
        r = smoke_block(
            "Block B — owner 17 evaluation (8 real-life scenarios)",
            el, gw, BLOCK_B_OWNER17, novelty_varied,
        )
        results.append(r)
    if args.block in ("c", "all"):
        el_replay = EvaluationLearner()
        r = smoke_block(
            "Block C — owner 17 evaluation (8-tick replay)",
            el_replay, gw, BLOCK_C_OWNER17_REPLAY, novelty_constant,
        )
        results.append(r)

    for r in results:
        print()
        print(f"--- {r.name} ---")
        print(f"  avg_max_residual: {r.avg_max_residual:.4f}")
        print(f"  final_regime:     {r.final_regime}")
        print(f"  commit_count:     {r.commit_count}")
        print(f"  max_abs_weight:   {r.max_abs_weight:.4f}")
        print("  per-tick:")
        for t in r.per_tick:
            print(f"    tick {t['tick_id']}: novelty={t['novelty']:.2f}  "
                  f"max_res={t['max_residual']:.4f}  "
                  f"regime={t['regime']:13s}  "
                  f"commit={t['commit']}")

    print()
    print("Summary:")
    print(f"  {len(results)} blocks ran.")
    if results:
        print(f"  Avg avg_max_residual: {sum(r.avg_max_residual for r in results) / len(results):.4f}")
        print(f"  Total commits: {sum(r.commit_count for r in results)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
