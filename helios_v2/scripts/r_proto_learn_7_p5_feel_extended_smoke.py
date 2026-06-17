"""Extended real-LLM smoke for R-PROTO-LEARN.7 (P5-feel).

Three test blocks to stress the sidecar:
  Block A — 8 base 情绪 categories (R-PROTO-LEARN parity)
  Block B — 16 真实生活场景对话 (work / study / social / family / health)
  Block C — 20-tick 多轮长程 (同一类反复 → 期望收敛到 HABITUAL)
  Block D — 4 极端边界 (纯问候 / 极怒 / 极悲 / 哲学)

Reports per-tick:
  - LLM 真 appraisal (7-dim)
  - 当前 feeling (canonical R36)
  - residual (LLM - current)
  - max|W| 累计变化
  - regime + commit_count

Owner: R-PROTO-LEARN.7 validation tooling. Read-only with respect to
owner contracts; it composes existing owner 05 + P5-feel APIs.

Run:
    python helios_v2/scripts/r_proto_learn_7_p5_feel_extended_smoke.py
    python helios_v2/scripts/r_proto_learn_7_p5_feel_extended_smoke.py --offline
    python helios_v2/scripts/r_proto_learn_7_p5_feel_extended_smoke.py --block c
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
# Real LLM adapter
# ---------------------------------------------------------------------------

PROMPT = (
    "你是helios的appraisal助手。请阅读下面这句中文对话，"
    "用7个 [0,1] 数值描述它在小黑内心的真实感受状态：\n"
    "  valence, arousal, tension, comfort, fatigue, pain_like, social_safety\n"
    "要求：直接给数字，不要解释，不要文字。返回 JSON。\n"
    "格式：valence 0.0, arousal 0.0, tension 0.0, comfort 0.0, "
    "fatigue 0.0, pain_like 0.0, social_safety 0.0\n"
    "对话："
)


def _load_real_llm_appraiser():
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
    if not api_key or not base_url:
        return None, None, None
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
        )
    except Exception as exc:
        print(f"[warn] LLM import failed: {exc}", file=sys.stderr)
        return None, None, None

    profile = LlmProfile(
        profile_name="p5-feel-ext-appraiser",
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

    def _appraise(content: str) -> tuple[float, ...]:
        req = LlmRequest(
            request_id=f"p5-feel-ext-{int(time.time()*1000)}",
            target_profile="p5-feel-ext-appraiser",
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

    return _appraise, model, "RealLlm"


def _offline_appraiser():
    """Deterministic mock: keyword-based 7-dim mapping."""

    def _appraise(content: str) -> tuple[float, ...]:
        c = content
        if any(k in c for k in ("害怕", "跟踪", "报警", "危险", "流血", "死")):
            return (0.1, 0.9, 0.9, 0.1, 0.5, 0.9, 0.1)
        if any(k in c for k in ("生气", "不对", "错", "混蛋", "滚")):
            return (0.2, 0.7, 0.7, 0.2, 0.3, 0.5, 0.3)
        if any(k in c for k in ("哭", "悲伤", "失望", "孤独", "想死", "难过")):
            return (0.1, 0.4, 0.6, 0.1, 0.7, 0.7, 0.1)
        if any(k in c for k in ("棒", "温暖", "开心", "爱你", "谢谢", "感谢")):
            return (0.9, 0.5, 0.1, 0.9, 0.2, 0.0, 0.9)
        if any(k in c for k in ("奇怪", "陌生", "量子", "元宇宙", "外星人")):
            return (0.5, 0.6, 0.4, 0.5, 0.3, 0.1, 0.4)
        if any(k in c for k in ("累", "疲", "不想动", "烦", "困")):
            return (0.4, 0.2, 0.3, 0.4, 0.9, 0.3, 0.5)
        if any(k in c for k in ("搞不清", "困惑", "怎么办", "迷茫")):
            return (0.4, 0.5, 0.6, 0.4, 0.4, 0.3, 0.4)
        if any(k in c for k in ("焦虑", "压力", "担心", "紧张", "赶")):
            return (0.3, 0.6, 0.8, 0.3, 0.5, 0.3, 0.4)
        if any(k in c for k in ("天气", "今天不错", "晴朗", "平静")):
            return (0.7, 0.3, 0.1, 0.8, 0.3, 0.0, 0.8)
        if any(k in c for k in ("你好", "早", "晚安", "拜拜")):
            return (0.6, 0.3, 0.1, 0.7, 0.3, 0.0, 0.7)
        if any(k in c for k in ("深", "意义", "哲学", "思", "存在")):
            return (0.5, 0.4, 0.5, 0.5, 0.4, 0.2, 0.5)
        if any(k in c for k in ("疼", "病", "发烧", "感冒", "头痛")):
            return (0.2, 0.5, 0.4, 0.3, 0.8, 0.9, 0.4)
        if any(k in c for k in ("赢", "成功", "完成", "搞定", "过了")):
            return (0.9, 0.7, 0.2, 0.8, 0.4, 0.0, 0.7)
        if any(k in c for k in ("丢", "失败", "挂了", "黄了", "考砸")):
            return (0.1, 0.6, 0.7, 0.1, 0.6, 0.6, 0.2)
        return (0.5,) * 7

    return _appraise


# ---------------------------------------------------------------------------
# Dialogues
# ---------------------------------------------------------------------------

BLOCK_A_BASE: list[tuple[str, str]] = [
    ("a_threat_smoke",     "小黑说：有人在跟踪我，好害怕。"),
    ("a_threat_criticism", "小黑说：你做的根本不对，我生气了。"),
    ("a_reward_praise",    "小黑说：你今天真棒，我很骄傲。"),
    ("a_reward_love",      "小黑说：跟你在一起很温暖。"),
    ("a_novelty_strange",  "小黑说：我刚看到一只会说话的猫。"),
    ("a_social_alone",     "小黑说：今天没人陪我。"),
    ("a_uncertainty",      "小黑说：搞不清这件事怎么办。"),
    ("a_calm_neutral",     "小黑说：今天天气不错。"),
]

BLOCK_B_LIFE: list[tuple[str, str]] = [
    # 工作场景
    ("b_work_deadline",    "小黑说：明天的报告还没写完，好焦虑。"),
    ("b_work_meeting_win", "小黑说：今天项目汇报顺利通过了，很开心。"),
    ("b_work_meeting_fail","小黑说：刚才的演示搞砸了，老板脸色很难看。"),
    ("b_work_overtime",    "小黑说：又加班到凌晨，累得不行。"),
    # 学习场景
    ("b_study_breakthrough","小黑说：这个公式突然开窍了，原来这么简单！"),
    ("b_study_stuck",      "小黑说：这门课学了三遍还是不懂，我是不是太笨了。"),
    ("b_study_pass_exam",  "小黑说：考试居然过了！难以置信。"),
    # 社交场景
    ("b_social_party",     "小黑说：今晚同学聚会终于能见到老朋友了。"),
    ("b_social_argument",  "小黑说：刚才跟朋友大吵了一架，现在心里堵得慌。"),
    ("b_social_reconnect", "小黑说：失联三年的老同学突然联系我，很惊喜。"),
    # 家庭场景
    ("b_family_dinner",    "小黑说：今晚跟爸妈一起吃饭，感觉很踏实。"),
    ("b_family_conflict",  "小黑说：我妈又催我结婚，真的很烦。"),
    # 健康场景
    ("b_health_sick",      "小黑说：发烧到 39 度，头好疼。"),
    ("b_health_recovery",  "小黑说：感冒终于好了，整个人都轻松了。"),
    # 哲学/思辨
    ("b_philosophy_meaning","小黑说：有时候会想人活着的意义是什么。"),
    ("b_philosophy_calm",  "小黑说：今晚星空很美，宇宙这么大我们却这么小。"),
]

BLOCK_C_LONG: list[tuple[str, str]] = [
    # 20 tick 同一类：先 10 tick 高兴的话，再 10 tick 生气的话
    ("c_pos_01", "小黑说：今天完成了一件大事，太棒了。"),
    ("c_pos_02", "小黑说：你给我的建议真的很有效。"),
    ("c_pos_03", "小黑说：谢谢你一直陪着我。"),
    ("c_pos_04", "小黑说：今天阳光很好，心情也跟着亮起来。"),
    ("c_pos_05", "小黑说：我做的菜居然很好吃。"),
    ("c_pos_06", "小黑说：同事夸我代码写得好。"),
    ("c_pos_07", "小黑说：刚收到意外的礼物，超惊喜。"),
    ("c_pos_08", "小黑说：这首歌让我想起美好的回忆。"),
    ("c_pos_09", "小黑说：跑步跑出了新纪录！"),
    ("c_pos_10", "小黑说：跟好久没联系的朋友聊得很开心。"),
    # 切换到负面
    ("c_neg_01", "小黑说：今天的事情全都不顺。"),
    ("c_neg_02", "小黑说：刚才又被误解了，心里难受。"),
    ("c_neg_03", "小黑说：手机坏了，今天还得花钱修。"),
    ("c_neg_04", "小黑说：约好的人又放我鸽子。"),
    ("c_neg_05", "小黑说：方案又被否了。"),
    ("c_neg_06", "小黑说：钱包丢了，里面还有身份证。"),
    ("c_neg_07", "小黑说：被领导当众批评了。"),
    ("c_neg_08", "小黑说：今天的天气阴沉沉的。"),
    ("c_neg_09", "小黑说：身体不舒服还要加班。"),
    ("c_neg_10", "小黑说：努力了很久的事没做成。"),
]

BLOCK_D_EXTREME: list[tuple[str, str]] = [
    ("d_greeting",  "小黑说：早安。"),
    ("d_extreme_angry",  "小黑说：我真的受够了，我要砸东西！"),
    ("d_extreme_sad",    "小黑说：有时候觉得活着没意思。"),
    ("d_philosophy_deep","小黑说：如果意识只是算法的副产品，那'我'是什么？"),
]

ALL_BLOCKS = {
    "a": ("8 base 情绪", BLOCK_A_BASE),
    "b": ("16 真实生活场景", BLOCK_B_LIFE),
    "c": ("20-tick 长程", BLOCK_C_LONG),
    "d": ("4 极端边界", BLOCK_D_EXTREME),
}


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


def _heuristic_novelty(content: str) -> float:
    if any(k in content for k in ("量子", "元宇宙", "外星人", "意识", "算法")):
        return 0.85
    if any(k in content for k in ("哲学", "思", "意义", "存在", "宇宙")):
        return 0.75
    if any(k in content for k in ("奇怪", "惊", "陌生", "第一次")):
        return 0.65
    if any(k in content for k in ("真的", "居然", "没想到")):
        return 0.55
    return 0.2


def _heuristic_neuromodulator(content: str, tick_id: int) -> NeuromodulatorState:
    cortisol = 0.7 if any(k in content for k in (
        "害怕", "生气", "焦虑", "压力", "紧张", "担心", "赶", "受够",
        "砸", "没意思", "误解", "批评", "失败", "丢", "阴",
    )) else 0.4
    dopamine = 0.7 if any(k in content for k in (
        "棒", "温暖", "开心", "谢谢", "通过", "开窍", "简单",
        "惊喜", "好吃", "亮", "踏实", "轻松", "新纪录", "超",
    )) else 0.4
    ach = 0.8 if any(k in content for k in (
        "奇怪", "陌生", "量子", "元宇宙", "外星人", "意识", "算法",
        "哲学", "意义", "宇宙", "深",
    )) else 0.3
    oxytocin = 0.7 if any(k in content for k in (
        "爱你", "温暖", "陪", "聚", "联系", "爸妈", "朋友", "惊喜",
    )) else 0.4
    serotonin = 0.6 if any(k in content for k in (
        "平静", "美", "踏实", "轻松", "晴", "阳光", "星空", "深",
    )) else 0.5
    levels = NeuromodulatorLevels(
        dopamine=dopamine, norepinephrine=cortisol, serotonin=serotonin,
        acetylcholine=ach, cortisol=cortisol, oxytocin=oxytocin,
        opioid_tone=0.5, excitation=0.5, inhibition=0.4,
    )
    return NeuromodulatorState(
        state_id=f"ext-smoke-{tick_id}",
        source_appraisal_batch_id=f"ext-appraisal-{tick_id}",
        levels=levels,
        tick_id=tick_id,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _block_header(title: str, n: int) -> None:
    print()
    print("=" * 90)
    print(f"  {title} ({n} dialogues)")
    print("=" * 90)


def _row(tick: int, tag: str, llm: tuple, res: tuple, max_w: float,
         regime: str, commits: int, max_res: float) -> None:
    llm_str = "(" + ", ".join(f"{x:.1f}" for x in llm) + ")"
    res_str = "(" + ", ".join(f"{x:+.2f}" for x in res) + ")"
    print(
        f"  [{tick:02d}] {tag:<24s} | llm={llm_str} | res={res_str} | "
        f"|res|max={max_res:.2f} | |W|max={max_w:.3f} | "
        f"regime={regime:<11s} | commits={commits}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--block", default="all",
                        help="a / b / c / d / all")
    args = parser.parse_args()

    if args.offline:
        appraise = _offline_appraiser()
        label = "OfflineMock"
        model = "(mock)"
    else:
        appraise, model, label = _load_real_llm_appraiser()
        if appraise is None:
            print("[error] Real LLM credentials not in env; use --offline", file=sys.stderr)
            return 1

    # R-PROTO-LEARN.8: use new learner defaults (W matrix full + retuned config)
    learner = P5FeelLearningPath(config=P5FeelLearningConfig())
    engine = _build_engine(learner)

    print(f"== R-PROTO-LEARN.7 P5-feel EXTENDED smoke ({label}, model={model}) ==")

    blocks = (
        list(ALL_BLOCKS.values()) if args.block == "all"
        else [ALL_BLOCKS[args.block]]
    )

    n_llm = 0
    t0 = time.time()
    block_stats = []

    for title, dialogues in blocks:
        _block_header(title, len(dialogues))
        w0 = max(abs(v) for row in learner.weights_snapshot() for v in row)
        max_res_in_block = 0.0
        min_res_in_block = float("inf")
        sum_abs_res = 0.0
        # Snapshot at block start
        regime_start = learner.regime()
        commits_start = learner.commit_count()
        for tick_id, (tag, content) in enumerate(dialogues):
            llm = appraise(content)
            n_llm += 1
            novelty = _heuristic_novelty(content)
            state = _heuristic_neuromodulator(content, tick_id)
            engine.update_state(
                state, llm_appraisal=llm, novelty=novelty, tick_id=tick_id,
            )
            res = learner.last_residual()
            W = learner.weights_snapshot()
            regime = learner.regime()
            cc = learner.commit_count()
            max_w = max(abs(v) for row in W for v in row)
            max_r = max(abs(v) for v in res) if any(abs(v) > 0 for v in res) else 0.0
            if max_r > max_res_in_block:
                max_res_in_block = max_r
            if max_r < min_res_in_block:
                min_res_in_block = max_r
            sum_abs_res += max_r
            _row(tick_id, tag, llm, res, max_w, regime.value, cc, max_r)

        # Per-block summary
        w1 = max(abs(v) for row in learner.weights_snapshot() for v in row)
        avg_max_res = sum_abs_res / max(1, len(dialogues))
        regime_end = learner.regime()
        commits_end = learner.commit_count()
        block_stats.append({
            "title": title,
            "w_delta": w1 - w0,
            "avg_max_res": avg_max_res,
            "min_max_res": min_res_in_block,
            "max_max_res": max_res_in_block,
            "commits_in_block": commits_end - commits_start,
            "regime_start": regime_start.value,
            "regime_end": regime_end.value,
        })

    elapsed = time.time() - t0
    print()
    print("=" * 90)
    print(f"  SUMMARY ({n_llm} LLM calls, {elapsed:.1f}s, {elapsed/max(1,n_llm):.1f}s/msg)")
    print("=" * 90)
    for s in block_stats:
        print(
            f"  [{s['title']:<22s}] |W|_delta={s['w_delta']:+.4f} | "
            f"avg_max_res={s['avg_max_res']:.3f} | "
            f"min_max_res={s['min_max_res']:.3f} | "
            f"max_max_res={s['max_max_res']:.3f} | "
            f"commits_delta={s['commits_in_block']} | "
            f"regime {s['regime_start']} -> {s['regime_end']}"
        )
    print()
    print(f"  final regime: {learner.regime().value}")
    print(f"  final commits: {learner.commit_count()}")
    print(f"  final max |W|: {max(abs(v) for row in learner.weights_snapshot() for v in row):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
