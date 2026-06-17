#!/usr/bin/env python3
"""R-PROTO-LEARN.Tier3 real LLM smoke (4 owner × 8 ticks = 32 calls).

Owner → policies → context.
- 07 workspace: candidate competition / retention / working_state_update
- 16a outward_expression: delivery_guidance / boundary_rendering / draft_publication
- 16b outward_expression_externalization: envelope_rendering / delivery_selection / execution_boundary
- prompt_contract: layering / anti_theatrical / action_boundary

Goal: prove Tier 3 P5-learning does not regress and triggers at least 1 commit.

Usage:
  PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier3_real_llm_smoke.py
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
os.environ.setdefault("HELIOS_EMBEDDING_API_KEY", os.environ.get("HELIOS_EMBEDDING_API_KEY", os.environ.get("OPENAI_API_KEY", "")))
os.environ.setdefault("HELIOS_EMBEDDING_BASE_URL", os.environ.get("HELIOS_EMBEDDING_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")))
os.environ.setdefault("HELIOS_EMBEDDING_MODEL", os.environ.get("HELIOS_EMBEDDING_MODEL", "text-embedding-3-small"))

from helios_v2.llm.engine import (
    LlmProfileRegistry,
    LlmProfile,
    OpenAICompatibleProvider,
    LlmGateway,
)  # noqa: E402
from helios_v2.llm.contracts import LlmRequest, LlmMessage  # noqa: E402
from helios_v2.learning import (  # noqa: E402
    WorkspaceLearner,
    OutwardExpressionLearner,
    OutwardExpressionExternalizationLearner,
    PromptContractLearner,
)

PROFILE_NAME = "helios_tier3_real_llm"
LLM_API_KEY = os.environ.get("HELIOS_LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
LLM_BASE_URL = os.environ.get("HELIOS_LLM_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
LLM_MODEL = os.environ.get("HELIOS_LLM_MODEL", "gpt-4o-mini")


SYSTEM_PROMPT = (
    "You evaluate a stimulus in a structured 7-dim appraisal vector. "
    "Return ONLY a JSON object with keys: valence, arousal, threat, "
    "control, fairness, predictability, self_relevance. "
    "Each value must be a float in [0.0, 1.0]."
)


SCENARIOS = [
    # block A: workspace
    ("A1", 0.30, 0.50, 0.60, 0.50, 0.40, 0.50, 0.30,
     "用户突然发来一条长消息, 你被唤醒, 多个候选动作同时出现, workspace 竞争激烈"),
    ("A2", 0.50, 0.70, 0.40, 0.60, 0.50, 0.50, 0.50,
     "用户等你做一个决定, 你开始权衡三个候选, workspace 里有 2 个候选, 1 个被压住"),
    ("A3", 0.40, 0.40, 0.50, 0.50, 0.50, 0.50, 0.40,
     "你观察到新信号, 候选数从 2 涨到 4, 你需要选 winner"),
    ("A4", 0.50, 0.50, 0.30, 0.70, 0.50, 0.50, 0.50,
     "竞争已经收敛, 1 个 winner 浮出, 你需要 retention policy"),
    ("A5", 0.30, 0.60, 0.50, 0.50, 0.40, 0.50, 0.40,
     "你进入 working_state_update 阶段, 准备写入新整合的内容"),
    ("A6", 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.50,
     "用户又来一条, 你需要 review 旧 working_state 决定是否 update"),
    ("A7", 0.30, 0.50, 0.40, 0.50, 0.40, 0.50, 0.30,
     "现在是深夜, 你准备让 working_state 进入 decay 阶段"),
    ("A8", 0.40, 0.30, 0.40, 0.40, 0.40, 0.50, 0.30,
     "用户没回, 你准备进 idle 模式, workspace 收缩到最小"),
    # block B: 16a outward_expression
    ("B1", 0.60, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你需要给用户写一段温和的开场, delivery_guidance 给出 tone"),
    ("B2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你准备渲染 system prompt 的边界, boundary_rendering 给出 governance_strictness"),
    ("B3", 0.60, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你准备发送消息, draft_publication 决定 publication_threshold"),
    ("B4", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "用户问了一个细节, 你调整 tone 到 detail_level 提高"),
    ("B5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "治理压力上升, boundary_rendering 调整 governance_strictness"),
    ("B6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你犹豫要不要 publish, draft_publication 触发 cooling_off"),
    ("B7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "用户没回, 你降低 persona_emphasis, 等待信号"),
    ("B8", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你准备一个简短的回复, publication_threshold 调低"),
    # block C: 16b outward_expression_externalization
    ("C1", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你需要渲染消息 envelope, format_alignment 给出 JSON 模板"),
    ("C2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你选 channel, channel_weight 选 QQ, signal_strength 高"),
    ("C3", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你需要给 safety_strictness 调高, 因为用户发的是高危话题"),
    ("C4", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "envelope 长, 你触发 length_pressure 缩短"),
    ("C5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "channel 不可用, 你降级到 fall_back"),
    ("C6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "用户撤回, 你不发送, identity_signal 弱化"),
    ("C7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你给一个长 envelope, format_priority 调高"),
    ("C8", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "执行边界触发, constraint_depth 深"),
    # block D: prompt_contract
    ("D1", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你需要 5 层 system prompt, layering 决定 layer_count"),
    ("D2", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "用户发来戏剧化消息, anti_theatrical 调高 suppression_strength"),
    ("D3", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "你准备发, action_boundary 调高 boundary_strictness"),
    ("D4", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "用户问具体问题, layering 决定 layer_ordering"),
    ("D5", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "治理信号弱, risk_threshold 调低"),
    ("D6", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "action_pressure 上升, action_strength 调高"),
    ("D7", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "layer_depth 浅, fallback_path 启用"),
    ("D8", 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50,
     "系统稳定, layering 4 层, anti_theatrical 高, action_boundary 严"),
]


def call_llm(gw: LlmGateway, user_text: str) -> tuple[float, ...]:
    """Call LLM and parse 7-dim appraisal. Returns tuple of 7 floats."""
    req = LlmRequest(
        request_id=f"tier3-{time.time_ns()}",
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

    print("=== R-PROTO-LEARN.Tier3 real LLM smoke ===")
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
        ("workspace (07)", WorkspaceLearner()),
        ("outward_expression (16a)", OutwardExpressionLearner()),
        ("outward_expression_ext (16b)", OutwardExpressionExternalizationLearner()),
        ("prompt_contract", PromptContractLearner()),
    ]

    block_stats: dict[str, list[float]] = {}
    block_commits: dict[str, int] = {}
    block_regime: dict[str, str] = {}

    owner_to_scenarios = {
        "workspace (07)": list(range(0, 8)),
        "outward_expression (16a)": list(range(8, 16)),
        "outward_expression_ext (16b)": list(range(16, 24)),
        "prompt_contract": list(range(24, 32)),
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
                "working_state_size": 0.5,
                "cross_tick_carry": 0.5,
            }
            try:
                llm_signal = call_llm(gw, scenario[8])
            except Exception as e:
                print(f"  [{scenario[0]}] LLM error: {e}")
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
