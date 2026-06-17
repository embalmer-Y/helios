#!/usr/bin/env python3
"""R-PROTO-LEARN.Tier4 real LLM smoke (4 owner × 8 ticks = 32 calls).

Owner → policies → context.
- 08 consciousness: commitment / quiet_state / semantic_shaping
- 13 planner_bridge: policy_evaluation / channel_selection / feedback_normalization
- 14 identity_governance: governance_evaluation / pressure_interpretation /
  supported_revision / boundary_check
- 15 experience_writeback: continuity_classification / consolidation_priority /
  autobiographical_salience

Usage:
  PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier4_real_llm_smoke.py
"""

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("HELIOS_LLM_API_KEY", os.environ.get("HELIOS_LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "")))
os.environ.setdefault("HELIOS_LLM_BASE_URL", os.environ.get("HELIOS_LLM_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")))
os.environ.setdefault("HELIOS_LLM_MODEL", os.environ.get("HELIOS_LLM_MODEL", "gpt-4o-mini"))

from helios_v2.llm.engine import (
    LlmProfileRegistry,
    LlmProfile,
    OpenAICompatibleProvider,
    LlmGateway,
)  # noqa: E402
from helios_v2.llm.contracts import LlmRequest, LlmMessage  # noqa: E402
from helios_v2.learning import (  # noqa: E402
    ConsciousnessLearner,
    PlannerBridgeLearner,
    IdentityGovernanceLearner,
    ExperienceWritebackLearner,
)

PROFILE_NAME = "helios_tier4_real_llm"
LLM_API_KEY = os.environ["HELIOS_LLM_API_KEY"]
LLM_BASE_URL = os.environ["HELIOS_LLM_BASE_URL"]
LLM_MODEL = os.environ["HELIOS_LLM_MODEL"]

SYSTEM_PROMPT = (
    "You evaluate a stimulus in a structured 7-dim appraisal vector. "
    "Return ONLY a JSON object with keys: valence, arousal, threat, "
    "control, fairness, predictability, self_relevance. "
    "Each value must be a float in [0.0, 1.0]."
)


SCENARIOS = [
    # block A: consciousness (08)
    ("A1", 0.60, 0.70, 0.40, 0.50, 0.50, 0.50, 0.50,
     "你正在想一个深刻的哲学问题, 多条思路争夺你的注意力, 你需要 commitment"),
    ("A2", 0.40, 0.30, 0.20, 0.50, 0.50, 0.50, 0.30,
     "用户没回, 你进入 quiet_state, 你决定 idle_decay 多大"),
    ("A3", 0.50, 0.50, 0.50, 0.50, 0.40, 0.50, 0.40,
     "你的语义网络里, 一个概念跟另一个有冲突, 你需要 semantic_shaping"),
    ("A4", 0.70, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你刚下了一个决定, 你要确认 commitment_threshold 是不是合适"),
    ("A5", 0.30, 0.30, 0.20, 0.50, 0.40, 0.50, 0.30,
     "系统空闲了, 你在 quiet_state 里 recovery 多久进入 idle_decay"),
    ("A6", 0.50, 0.50, 0.50, 0.50, 0.40, 0.50, 0.40,
     "你进入新情境, semantic_shaping 决定 integration_depth"),
    ("A7", 0.60, 0.50, 0.40, 0.50, 0.50, 0.50, 0.40,
     "用户问了一个新问题, 你需要 commitment 决定是不是 accept"),
    ("A8", 0.40, 0.30, 0.30, 0.50, 0.40, 0.50, 0.40,
     "夜晚了, 你进入 quiet_state, idle_decay 慢"),
    # block B: planner_bridge (13)
    ("B1", 0.60, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你有一个 planner 请求, 你需要 policy_evaluation"),
    ("B2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你选 channel, channel_selection 决定 channel_weight"),
    ("B3", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你收 feedback, feedback_normalization 决定 normalization_strength"),
    ("B4", 0.70, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你遇到 impasse, policy_evaluation 触发 evaluation"),
    ("B5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "channel 不可用, channel_selection 触发 fall_back"),
    ("B6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "feedback volume 大, feedback_normalization 触发 scope_pressure"),
    ("B7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你的 decision_confidence 上升, policy_evaluation 调高 evaluation_threshold"),
    ("B8", 0.40, 0.40, 0.40, 0.40, 0.40, 0.50, 0.40,
     "用户撤回请求, feedback_normalization 触发 integration_depth"),
    # block C: identity_governance (14)
    ("C1", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "governance_evaluation 检查 proposal 是不是 aligned"),
    ("C2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "pressure_intensity 上升, pressure_interpretation 触发 evaluation"),
    ("C3", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "proposal 准备被接受, supported_revision 验证 support_weight"),
    ("C4", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "boundary_risk 上升, boundary_check 触发 strict 检查"),
    ("C5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "governance_evaluation 调高 alignment_strictness"),
    ("C6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "pressure 平稳, pressure_interpretation 调低 signal_strength"),
    ("C7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "proposal 复杂, supported_revision 调低 revision_threshold"),
    ("C8", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "boundary_check 调高 safety_margin, fall_back 启用"),
    # block D: experience_writeback (15)
    ("D1", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "一个 continuity evidence 进来, 你分类"),
    ("D2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你准备 consolidation, consolidation_priority 决定 priority_threshold"),
    ("D3", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你给一个 autobiographical event 打 salience 分数"),
    ("D4", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你接 multiple continuity, continuity_classification 调高 classification_threshold"),
    ("D5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "consolidation_priority 调低 priority_threshold (你准备整合)"),
    ("D6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "autobiographical_salience 调高 salience_threshold (你强调真实)"),
    ("D7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "candidate_count 涨, 你调 consolidation_priority 的 weight"),
    ("D8", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "autobiographical_salience 调高 integration_strength"),
]


def call_llm(gw: LlmGateway, user_text: str) -> tuple[float, ...]:
    """Call LLM and parse 7-dim appraisal. Returns tuple of 7 floats."""
    req = LlmRequest(
        request_id=f"tier4-{time.time_ns()}",
        target_profile=PROFILE_NAME,
        messages=[
            LlmMessage(role="system", content=SYSTEM_PROMPT),
            LlmMessage(role="user", content=user_text),
        ],
        response_format="json_object",
    )
    completion = gw.complete(req)
    raw = completion.output_text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"LLM output is not valid JSON. output={raw!r}"
        ) from e
    if not isinstance(data, dict):
        raise RuntimeError(f"LLM JSON not a dict: {data!r}")
    keys = ["valence", "arousal", "threat", "control",
            "fairness", "predictability", "self_relevance"]
    out = []
    for k in keys:
        v = data.get(k, 0.5)
        v = max(0.0, min(1.0, float(v)))
        out.append(v)
    return tuple(out)


def main() -> None:
    if not LLM_API_KEY:
        print("ERROR: HELIOS_LLM_API_KEY / OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print("=== R-PROTO-LEARN.Tier4 real LLM smoke ===")
    print(f"Profile: {PROFILE_NAME}")
    print(f"Scenarios: {len(SCENARIOS)}")
    print()

    registry = LlmProfileRegistry((
        LlmProfile(
            profile_name=PROFILE_NAME,
            model=LLM_MODEL,
            api_key_env="OPENAI_API_KEY",
            base_url=LLM_BASE_URL,
            temperature=0.0,
            max_tokens=256,
            timeout=30.0,
            default_response_format="json_object",
        ),
    ))
    provider = OpenAICompatibleProvider()
    gw = LlmGateway(provider=provider, registry=registry)

    learners = [
        ("consciousness (08)", ConsciousnessLearner()),
        ("planner_bridge (13)", PlannerBridgeLearner()),
        ("identity_governance (14)", IdentityGovernanceLearner()),
        ("experience_writeback (15)", ExperienceWritebackLearner()),
    ]

    block_stats: dict[str, list[float]] = {}
    block_commits: dict[str, int] = {}
    block_regime: dict[str, str] = {}

    owner_to_scenarios = {
        "consciousness (08)": list(range(0, 8)),
        "planner_bridge (13)": list(range(8, 16)),
        "identity_governance (14)": list(range(16, 24)),
        "experience_writeback (15)": list(range(24, 32)),
    }

    for owner_name, learner in learners:
        idxs = owner_to_scenarios[owner_name]
        print(f"--- {owner_name} ({len(idxs)} ticks) ---")
        residual_history: list[float] = []
        t0 = time.time()
        for tick_id, scenario_idx in enumerate(idxs):
            scenario = SCENARIOS[scenario_idx]
            label = scenario[0]
            v = scenario[1]
            a = scenario[2]
            t = scenario[3]
            c = scenario[4]
            f = scenario[5]
            p = scenario[6]
            s = scenario[7]
            prior_state = {
                "candidate_count": v,
                "signal_strength": a,
                "dopamine": 0.5,
                "acetylcholine": 0.5,
                "novelty": 0.5,
                "conscious_state_size": 0.5,
                "semantic_drift": s,
            }
            try:
                llm_signal = call_llm(gw, scenario[8])
            except Exception as e:
                print(f"  [{label}] LLM error: {e}")
                llm_signal = (0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
            novelty = max(0.0, min(1.0, scenario[1] * 0.5 + 0.3))
            snap = learner.update(prior_state, llm_signal, novelty=novelty, tick_id=tick_id)
            max_res = max(abs(v_) for v_ in snap.residual)
            residual_history.append(max_res)
            print(
                f"  [{label}] res={max_res:.4f} regime={snap.regime.value} "
                f"commit={snap.commit}"
            )
        dt = time.time() - t0
        avg_max = sum(residual_history) / len(residual_history)
        print(f"  avg_max_res={avg_max:.4f} commits={learner.commit_count()} regime={learner.regime().value} t={dt:.1f}s")
        block_stats[owner_name] = residual_history
        block_commits[owner_name] = learner.commit_count()
        block_regime[owner_name] = learner.regime().value
        print()

    print("=== summary ===")
    total_commits = 0
    for owner_name, _ in learners:
        print(
            f"  {owner_name:30s} avg_max_res={sum(block_stats[owner_name])/len(block_stats[owner_name]):.4f} "
            f"commits={block_commits[owner_name]} regime={block_regime[owner_name]}"
        )
        total_commits += block_commits[owner_name]
    print(f"  TOTAL commits: {total_commits}")


if __name__ == "__main__":
    main()
