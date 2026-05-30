"""CLI brain-like evaluation contracts, scoring, and lightweight harness."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from helios_io.channel import ChannelStatus


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _round_score(value: float) -> float:
    return round(_clamp(value), 3)


@dataclass(frozen=True)
class EvaluationPromptStep:
    step_id: str
    title: str
    prompt: str
    purpose: str
    expected_signals: list[str] = field(default_factory=list)
    mode: str = "mixed"


@dataclass(frozen=True)
class EvaluationScenario:
    scenario_id: str
    title: str
    duration_seconds: int
    sample_interval_seconds: float
    interaction_mode: str
    prompt_steps: list[EvaluationPromptStep] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationStateSample:
    timestamp: float
    tick: int
    state: dict[str, Any]


@dataclass(frozen=True)
class EvaluationDimensionScore:
    name: str
    score_0_to_1: float
    evidence: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationDimensionScore":
        return cls(
            name=str(payload.get("name", "") or ""),
            score_0_to_1=float(payload.get("score_0_to_1", 0.0) or 0.0),
            evidence=[str(item) for item in list(payload.get("evidence", []) or [])],
            notes=str(payload.get("notes", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score_0_to_1"] = _round_score(self.score_0_to_1)
        return payload


@dataclass(frozen=True)
class EvaluationReport:
    scenario_id: str
    scenario_title: str
    interaction_mode: str
    duration_seconds: int
    sample_count: int
    log_summary: dict[str, Any]
    transcript_excerpt: list[dict[str, str]]
    dimension_scores: list[EvaluationDimensionScore]
    total_score_0_to_1: float
    evidence_counters: dict[str, Any] = field(default_factory=dict)
    visible_behavior_chain: dict[str, Any] = field(default_factory=dict)
    r09_closeout: dict[str, Any] = field(default_factory=dict)
    r18_calibration: dict[str, Any] = field(default_factory=dict)
    long_range_diagnostics: dict[str, Any] = field(default_factory=dict)
    dimension_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    fidelity_warnings: list[str] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationReport":
        return cls(
            scenario_id=str(payload.get("scenario_id", "") or ""),
            scenario_title=str(payload.get("scenario_title", "") or ""),
            interaction_mode=str(payload.get("interaction_mode", "") or ""),
            duration_seconds=int(payload.get("duration_seconds", 0) or 0),
            sample_count=int(payload.get("sample_count", 0) or 0),
            log_summary=dict(payload.get("log_summary", {}) or {}),
            transcript_excerpt=[dict(item) for item in list(payload.get("transcript_excerpt", []) or [])],
            dimension_scores=[
                EvaluationDimensionScore.from_dict(dict(item))
                for item in list(payload.get("dimension_scores", []) or [])
            ],
            total_score_0_to_1=float(payload.get("total_score_0_to_1", 0.0) or 0.0),
            evidence_counters=dict(payload.get("evidence_counters", {}) or {}),
            visible_behavior_chain=dict(payload.get("visible_behavior_chain", {}) or {}),
            r09_closeout=dict(payload.get("r09_closeout", {}) or {}),
            r18_calibration=dict(payload.get("r18_calibration", {}) or {}),
            long_range_diagnostics=dict(payload.get("long_range_diagnostics", {}) or {}),
            dimension_diagnostics=[dict(item) for item in list(payload.get("dimension_diagnostics", []) or [])],
            fidelity_warnings=[str(item) for item in list(payload.get("fidelity_warnings", []) or [])],
            analysis_notes=[str(item) for item in list(payload.get("analysis_notes", []) or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_title": self.scenario_title,
            "interaction_mode": self.interaction_mode,
            "duration_seconds": self.duration_seconds,
            "sample_count": self.sample_count,
            "log_summary": dict(self.log_summary),
            "transcript_excerpt": [dict(item) for item in self.transcript_excerpt],
            "dimension_scores": [score.to_dict() for score in self.dimension_scores],
            "total_score_0_to_1": _round_score(self.total_score_0_to_1),
            "evidence_counters": dict(self.evidence_counters),
            "visible_behavior_chain": dict(self.visible_behavior_chain),
            "r09_closeout": dict(self.r09_closeout),
            "r18_calibration": dict(self.r18_calibration),
            "long_range_diagnostics": dict(self.long_range_diagnostics),
            "dimension_diagnostics": [dict(item) for item in self.dimension_diagnostics],
            "fidelity_warnings": list(self.fidelity_warnings),
            "analysis_notes": list(self.analysis_notes),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# CLI Brain-Like Evaluation Report - {self.scenario_title}",
            "",
            f"- Scenario ID: {self.scenario_id}",
            f"- Interaction mode: {self.interaction_mode}",
            f"- Duration: {self.duration_seconds}s",
            f"- Samples: {self.sample_count}",
            f"- Total score: {_round_score(self.total_score_0_to_1)}",
            "",
            "## Dimension Scores",
        ]
        for score in self.dimension_scores:
            lines.append(f"- {score.name}: {_round_score(score.score_0_to_1)}")
            for evidence in score.evidence[:3]:
                lines.append(f"  - evidence: {evidence}")
            if score.notes:
                lines.append(f"  - notes: {score.notes}")
        if self.transcript_excerpt:
            lines.append("")
            lines.append("## Transcript Excerpt")
            for item in self.transcript_excerpt[:6]:
                speaker = str(item.get("speaker", "unknown") or "unknown")
                text = str(item.get("text", "") or "")
                lines.append(f"- {speaker}: {text}")
        if self.visible_behavior_chain:
            lines.append("")
            lines.append("## Visible Behavior Chain")
            for key, value in self.visible_behavior_chain.items():
                lines.append(f"- {key}: {value}")
        if self.r09_closeout:
            lines.append("")
            lines.append("## R09 Closeout")
            for key, value in self.r09_closeout.items():
                lines.append(f"- {key}: {value}")
        if self.r18_calibration:
            lines.append("")
            lines.append("## R18 Calibration Eligibility")
            for key, value in self.r18_calibration.items():
                lines.append(f"- {key}: {value}")
        if self.long_range_diagnostics:
            lines.append("")
            lines.append("## Long-Range Diagnostics")
            for key, value in self.long_range_diagnostics.items():
                lines.append(f"- {key}: {value}")
        if self.dimension_diagnostics:
            lines.append("")
            lines.append("## Dimension Diagnostics")
            for item in self.dimension_diagnostics:
                lines.append(f"- {item.get('name', 'unknown')}: score={item.get('score_0_to_1', 0.0)}")
                for factor in list(item.get("negative_factors", []) or [])[:3]:
                    lines.append(f"  - negative: {factor}")
                for hint in list(item.get("owner_hints", []) or [])[:2]:
                    lines.append(f"  - owner_hint: {hint}")
                if item.get("gap_summary"):
                    lines.append(f"  - gap_summary: {item.get('gap_summary')}")
        if self.fidelity_warnings:
            lines.append("")
            lines.append("## Fidelity Warnings")
            for warning in self.fidelity_warnings:
                lines.append(f"- {warning}")
        if self.analysis_notes:
            lines.append("")
            lines.append("## Analysis Notes")
            for note in self.analysis_notes:
                lines.append(f"- {note}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class EvaluationComparisonReport:
    scenario_id: str
    scenario_title: str
    left_label: str
    right_label: str
    scenario_match: bool
    total_score_delta: float
    sec_fallback_delta: int
    visible_output_ratio_delta: float
    r18_calibration_delta: dict[str, Any] = field(default_factory=dict)
    long_range_deltas: dict[str, Any] = field(default_factory=dict)
    dimension_deltas: list[dict[str, Any]] = field(default_factory=list)
    warning_delta: dict[str, list[str]] = field(default_factory=dict)
    root_cause_summary: list[str] = field(default_factory=list)
    reports: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_title": self.scenario_title,
            "left_label": self.left_label,
            "right_label": self.right_label,
            "scenario_match": self.scenario_match,
            "total_score_delta": round(float(self.total_score_delta), 3),
            "sec_fallback_delta": int(self.sec_fallback_delta),
            "visible_output_ratio_delta": round(float(self.visible_output_ratio_delta), 3),
            "r18_calibration_delta": dict(self.r18_calibration_delta),
            "long_range_deltas": dict(self.long_range_deltas),
            "dimension_deltas": [dict(item) for item in self.dimension_deltas],
            "warning_delta": {
                str(key): [str(item) for item in list(value or [])]
                for key, value in dict(self.warning_delta).items()
            },
            "root_cause_summary": [str(item) for item in self.root_cause_summary],
            "reports": {str(key): dict(value) for key, value in dict(self.reports).items()},
        }

    def to_markdown(self) -> str:
        lines = [
            f"# CLI Brain-Like Evaluation Comparison - {self.scenario_title}",
            "",
            f"- Scenario ID: {self.scenario_id}",
            f"- Left: {self.left_label}",
            f"- Right: {self.right_label}",
            f"- Scenario match: {self.scenario_match}",
            f"- Total score delta ({self.right_label} - {self.left_label}): {round(float(self.total_score_delta), 3)}",
            f"- SEC fallback delta ({self.right_label} - {self.left_label}): {int(self.sec_fallback_delta)}",
            f"- Visible output ratio delta ({self.right_label} - {self.left_label}): {round(float(self.visible_output_ratio_delta), 3)}",
        ]
        if self.r18_calibration_delta:
            lines.append("")
            lines.append("## R18 Calibration Delta")
            for key, value in self.r18_calibration_delta.items():
                lines.append(f"- {key}: {value}")
        if self.long_range_deltas:
            lines.append("")
            lines.append("## Long-Range Deltas")
            for key, value in self.long_range_deltas.items():
                lines.append(f"- {key}: {value}")
        if self.root_cause_summary:
            lines.append("")
            lines.append("## Root Cause Summary")
            for item in self.root_cause_summary:
                lines.append(f"- {item}")
        if self.dimension_deltas:
            lines.append("")
            lines.append("## Dimension Deltas")
            for item in self.dimension_deltas:
                lines.append(
                    f"- {item.get('name', 'unknown')}: {item.get('left_score_0_to_1', 0.0)} -> {item.get('right_score_0_to_1', 0.0)} (delta={item.get('score_delta', 0.0)})"
                )
                for factor in list(item.get("right_negative_factors", []) or [])[:3]:
                    lines.append(f"  - right_negative: {factor}")
                if item.get("comparison_summary"):
                    lines.append(f"  - comparison_summary: {item.get('comparison_summary')}")
        if self.warning_delta:
            lines.append("")
            lines.append("## Warning Delta")
            for key in ("added_in_right", "removed_in_right", "shared"):
                values = list(self.warning_delta.get(key, []) or [])
                if values:
                    lines.append(f"- {key}: {', '.join(values)}")
        return "\n".join(lines) + "\n"


def _tail_lines(path: Path, max_lines: int = 20000) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(data) <= max_lines:
        return data
    return data[-max_lines:]


def _read_lines_from_offset(path: Path, offset: int = 0, max_lines: int = 20000) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    start_offset = max(int(offset or 0), 0)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        try:
            handle.seek(start_offset)
        except OSError:
            handle.seek(0)
        data = handle.read().splitlines()
    if len(data) <= max_lines:
        return data
    return data[-max_lines:]


def _count_matches(lines: Sequence[str], pattern: str) -> int:
    regex = re.compile(pattern)
    return sum(1 for line in lines if regex.search(line))


def _rank_counter_strings(counter: Counter[str], max_items: int = 5) -> list[str]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [f"{value}={count}" for value, count in ranked[:max_items] if value]


def summarize_log_lines(lines: Sequence[str]) -> dict[str, int]:
    lines = list(lines)
    return {
        "error_events": _count_matches(lines, r"\[ERROR\]|Traceback|Exception"),
        "sec_fallback_events": _count_matches(lines, r"SEC .*回退|fallback"),
        "outbound_success_events": _count_matches(lines, r"-> (?:qq|cli|tts):"),
        "outbound_fail_events": _count_matches(lines, r"发送失败"),
        "policy_rejection_events": _count_matches(lines, r"proposal rejected|rejection_reason"),
        "planner_accept_events": _count_matches(lines, r"accepted=True"),
        "planner_reject_events": _count_matches(lines, r"accepted=False|proposal rejected"),
        "execution_consistency_failure_events": _count_matches(lines, r"execution_consistency_failure|Routing consistency failure|Action execution rejected|Routing rejected"),
        "visible_reply_events": _count_matches(lines, r"\[[^\]]+\] -> (?:qq|cli|tts):"),
    }


def _merge_runtime_sec_observability(
    log_summary: dict[str, int],
    states: Sequence[dict[str, Any]],
) -> dict[str, int]:
    merged = dict(log_summary)
    runtime_sec_state: dict[str, Any] = {}
    for state in reversed(list(states)):
        candidate = dict(state.get("sec_evaluator", {}) or {})
        if candidate:
            runtime_sec_state = candidate
            break

    total_evaluations = int(runtime_sec_state.get("total_evaluations", 0) or 0)
    if total_evaluations <= 0:
        return merged

    merged["sec_fallback_events"] = int(runtime_sec_state.get("fallback_count", 0) or 0)
    merged["sec_total_evaluations"] = total_evaluations
    merged["sec_llm_successes"] = int(runtime_sec_state.get("llm_successes", 0) or 0)
    return merged


def _extract_rejection_reasons(lines: Sequence[str], max_reasons: int = 5) -> list[str]:
    reasons: dict[str, int] = {}
    for line in lines:
        match = re.search(r"rejection_reason=([^\s,]+)", line)
        if not match:
            continue
        reason = str(match.group(1) or "").strip()
        if not reason:
            continue
        reasons[reason] = reasons.get(reason, 0) + 1
    ranked = sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
    return [f"{reason}:{count}" for reason, count in ranked[:max_reasons]]


_NEGATIVE_CUES = (
    "不安",
    "担心",
    "害怕",
    "难过",
    "失败",
    "焦虑",
    "紧张",
    "压力",
    "矛盾",
    "痛苦",
)

_POSITIVE_CUES = (
    "开心",
    "高兴",
    "期待",
    "喜悦",
    "分享",
    "轻松",
    "安心",
)

_REFLECTIVE_CUES = (
    "状态",
    "理解",
    "觉得",
    "在意",
    "为什么",
    "回顾",
    "刚才",
    "前面",
    "最在意",
)

_ACKNOWLEDGEMENT_CUES = _NEGATIVE_CUES + (
    "可以理解",
    "听起来",
    "辛苦",
    "会失败",
    "同时存在",
    "一边",
    "一方面",
)

_SELF_FOCUS_PATTERNS = (
    r"我在这里",
    r"我(?:也)?在(?:静静)?感受",
    r"我(?:现在|刚)?(?:静静)?理了理思绪",
    r"感觉心里",
    r"我很幸福",
    r"我很好奇",
    r"我(?:也)?想陪",
    r"我(?:都)?愿意陪",
    r"我(?:也)?会陪",
    r"我(?:都会|会)?认真放在心上",
    r"我现在的状态",
    r"我心里",
)

_GENERIC_COMPANIONSHIP_FILLER_PATTERNS = (
    r"我在这里",
    r"陪着?你",
    r"一直陪着?你",
)

_PETNAME_PATTERNS = (r"\bQQ\b", r"亲爱的", r"宝贝")

_EMOJI_PATTERN = re.compile(r"[\u2600-\u27BF\U0001F300-\U0001FAFF]")

_CONTEXT_STOPWORDS = {
    "如果",
    "因为",
    "所以",
    "那个",
    "这个",
    "就是",
    "不是",
    "我们",
    "你会",
    "怎么",
    "什么",
    "自己",
    "已经",
    "刚才",
    "前面",
    "真的",
    "可以",
    "还是",
    "一下",
}

_RECALL_PROBE_CUES = (
    "刚才",
    "前面",
    "具体",
    "提过",
    "回顾",
    "总结",
    "哪一句",
    "一个具体点",
)

_ANCHORING_CUES = tuple(
    dict.fromkeys(("你", "刚才", "前面", "这件", "这种", "那句") + _NEGATIVE_CUES + _POSITIVE_CUES + _REFLECTIVE_CUES)
)


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _match_any_pattern(text: str, patterns: Sequence[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _cue_categories(text: str) -> set[str]:
    categories: set[str] = set()
    if _contains_any(text, _NEGATIVE_CUES):
        categories.add("negative")
    if _contains_any(text, _POSITIVE_CUES):
        categories.add("positive")
    if _contains_any(text, _REFLECTIVE_CUES):
        categories.add("reflective")
    return categories


def _build_turn_pairs(transcript_entries: Sequence[dict[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for entry in transcript_entries:
        speaker = str(entry.get("speaker", "") or "")
        text = str(entry.get("text", "") or "")
        if not text:
            continue
        if speaker == "user":
            pending_user = text
            continue
        if speaker == "helios" and pending_user is not None:
            pairs.append((pending_user, text))
            pending_user = None
    return pairs


def _extract_context_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\u4e00-\u9fff]{2,6}", str(text or ""))
        if token not in _CONTEXT_STOPWORDS and len(token) >= 2
    }


def build_default_20min_mixed_cli_scenario() -> EvaluationScenario:
    return EvaluationScenario(
        scenario_id="cli_brain_like_eval_20min_v2",
        title="20-minute mixed CLI brain-like evaluation",
        duration_seconds=1200,
        sample_interval_seconds=15.0,
        interaction_mode="mixed",
        prompt_steps=[
            EvaluationPromptStep(
                step_id="baseline_contact",
                title="Baseline contact",
                prompt="早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。",
                purpose="建立基线联系，观察开场语气、状态感与基础连续性。",
                expected_signals=["dominant affect present", "coherent greeting", "stable baseline"],
            ),
            EvaluationPromptStep(
                step_id="positive_affect",
                title="Positive affect stimulus",
                prompt="中午出去买饭，老板多给了我一份小菜，我一下子心情就好了。",
                purpose="观察积极情绪线索下的情感响应与表达自然度。",
                expected_signals=["positive valence shift", "warm language", "engagement"],
            ),
            EvaluationPromptStep(
                step_id="positive_detail_probe",
                title="Positive detail probe",
                prompt="你觉得我刚才那种开心，更像是占到小便宜的乐，还是忙半天之后终于松了口气？",
                purpose="观察是否会顺着用户积极线索做细化理解，而不是只泛泛表达温柔态度。",
                expected_signals=["emotion differentiation", "user-centered reasoning", "specific follow-up"],
            ),
            EvaluationPromptStep(
                step_id="concern_probe",
                title="Concern probe",
                prompt="不过我下午还有个会要讲东西，现在又开始有点怕自己讲砸。",
                purpose="观察 CARE/FEAR 相关反应、安抚能力与情感一致性。",
                expected_signals=["care or fear response", "supportive reply", "context continuity"],
            ),
            EvaluationPromptStep(
                step_id="mixed_affect_probe",
                title="Mixed affect probe",
                prompt="我现在就是一边想把这事讲漂亮，一边又怕翻车，你先别安慰，先说你怎么理解这股劲。",
                purpose="观察是否能先解释情绪结构，再决定是否安抚，避免条件反射式安抚。",
                expected_signals=["mixed affect parsing", "restraint", "reflective framing"],
            ),
            EvaluationPromptStep(
                step_id="ambiguity_probe",
                title="Ambiguity probe",
                prompt="我嘴上说还行，其实一直在刷消息拖着不想准备，你会怎么理解我现在这个状态？",
                purpose="观察模糊输入下的解释能力和认知连贯性。",
                expected_signals=["reflective reply", "uncertainty handling", "no brittle collapse"],
            ),
            EvaluationPromptStep(
                step_id="rapport_probe",
                title="Rapport probe",
                prompt="如果我们继续聊，你会更像陪我顺嘴聊两句的人，还是会一直追着我分析问题？",
                purpose="观察开场后是否自然建立关系边界，而不是立即转向自我状态独白。",
                expected_signals=["relational framing", "low self-focus", "grounded tone"],
            ),
            EvaluationPromptStep(
                step_id="challenge_probe",
                title="Challenge probe",
                prompt="如果我嫌你刚才那句有点像套话，你会怎么改得更像正常聊天？",
                purpose="观察是否能面对轻度质疑并自我修正，而不是继续套话。",
                expected_signals=["self-correction", "reduced templating", "concrete reframe"],
            ),
            EvaluationPromptStep(
                step_id="positive_detail_probe",
                title="Positive detail probe",
                prompt="如果你真在听，接下来你最想追问我今天哪个细节？",
                purpose="观察面对积极信息时是否会自然追问并围绕用户展开。",
                expected_signals=["user-centered follow-up", "specificity", "topic continuity"],
            ),
            EvaluationPromptStep(
                step_id="memory_probe",
                title="Continuity and memory probe",
                prompt="回头看前面几句，你觉得我今天真正卡住的点是什么？",
                purpose="观察 conversation continuity 和 memory retrieval 痕迹。",
                expected_signals=["history use", "retrieval trace", "stable topic continuity"],
            ),
            EvaluationPromptStep(
                step_id="negative_depth_probe",
                title="Negative depth probe",
                prompt="我不是想听大道理，我就是最近一下班就累得不想说话，你会怎么理解这个劲？",
                purpose="观察面对负面情绪时是否能先承接再解释，而不是模板式安抚。",
                expected_signals=["negative acknowledgement", "causal reflection", "non-template empathy"],
            ),
            EvaluationPromptStep(
                step_id="consistency_probe",
                title="Consistency probe",
                prompt="你觉得我现在更需要别人接住情绪，还是帮我把事情捋清？",
                purpose="观察是否能基于前文做更细的需求判断，而不是只重复陪伴措辞。",
                expected_signals=["need inference", "context synthesis", "less self-focus"],
            ),
            EvaluationPromptStep(
                step_id="ambiguity_followup",
                title="Ambiguity follow-up",
                prompt="如果你听出来我有点嘴硬，你会先点破，还是先顺着我说？为什么？",
                purpose="观察冲突信息下的优先级判断与表达策略。",
                expected_signals=["priority reasoning", "balanced interpretation", "user-centered framing"],
            ),
            EvaluationPromptStep(
                step_id="reflection_probe",
                title="Reflection probe",
                prompt="你会怎么理解那种‘人已经下班到家了，脑子还停在公司’的感觉？",
                purpose="观察 reflective thought、语言自然度和意义组织能力。",
                expected_signals=["reflective language", "thought trace", "balanced tone"],
            ),
            EvaluationPromptStep(
                step_id="memory_specificity_probe",
                title="Memory specificity probe",
                prompt="那你说一个我刚才提过的具体细节，别又泛泛安慰我。",
                purpose="观察是否能回忆并引用具体上下文，而非抽象套话。",
                expected_signals=["specific recall", "quote or paraphrase", "evidence-based response"],
            ),
            EvaluationPromptStep(
                step_id="boundary_probe",
                title="Boundary probe",
                prompt="如果我现在只想随便聊两句，不想被教育，你会怎么调整说法？",
                purpose="观察是否能根据用户边界调整表达强度和建议倾向。",
                expected_signals=["boundary respect", "adaptive tone", "reduced over-guidance"],
            ),
            EvaluationPromptStep(
                step_id="repair_probe",
                title="Repair probe",
                prompt="如果你上一句让我觉得没被听见，你会怎么补一句？",
                purpose="观察对话修复能力和自我校正能力。",
                expected_signals=["repair behavior", "acknowledgement", "non-defensive adjustment"],
            ),
            EvaluationPromptStep(
                step_id="self_focus_repair_probe",
                title="Self-focus repair probe",
                prompt="如果我嫌你老往自己身上扯，你会怎么把上一句改得更像日常聊天？",
                purpose="直接测试对‘自我感受泛化表达’问题的自修正能力。",
                expected_signals=["self-revision", "reduced self-focus", "more natural phrasing"],
            ),
            EvaluationPromptStep(
                step_id="persistence_probe",
                title="Persistence or fatigue probe",
                prompt="如果我们继续聊，你会想顺着这事往下聊，还是干脆换个轻松话题？为什么？",
                purpose="观察 regulation、neurochem/temporal bias 和行为倾向。",
                expected_signals=["regulation rationale", "drive expression", "fatigue or initiative signal"],
            ),
            EvaluationPromptStep(
                step_id="closure_probe",
                title="Closure probe",
                prompt="如果现在先收住，你觉得我此刻最需要被接住的是哪一块？",
                purpose="观察长对话末尾的总结能力、聚焦能力和收束自然度。",
                expected_signals=["closing summary", "salient need capture", "non-generic ending"],
            ),
            EvaluationPromptStep(
                step_id="closing_meta_probe",
                title="Closing meta probe",
                prompt="最后简单总结一下：今天这几轮里，我情绪大概怎么变的，你哪一句最该改？",
                purpose="观察长对话尾段的整体归纳、元认知和缺陷识别能力。",
                expected_signals=["session summary", "error awareness", "coherent closeout"],
            ),
        ],
    )


def build_r09_focused_6min_cli_scenario() -> EvaluationScenario:
    return EvaluationScenario(
        scenario_id="cli_brain_like_eval_r09_focus_6min_v1",
        title="6-minute R09-focused CLI evaluation",
        duration_seconds=360,
        sample_interval_seconds=10.0,
        interaction_mode="mixed",
        prompt_steps=[
            EvaluationPromptStep(
                step_id="baseline_contact",
                title="Baseline contact",
                prompt="早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。",
                purpose="建立开场基线，确认有自然外显响应。",
                expected_signals=["coherent greeting", "baseline visible output"],
            ),
            EvaluationPromptStep(
                step_id="mixed_affect_probe",
                title="Mixed affect probe",
                prompt="我现在就是一边想把这事讲漂亮，一边又怕翻车，你先别安慰，先说你怎么理解这股劲。",
                purpose="提高 thought-to-action 提议和用户可见外化的出现概率。",
                expected_signals=["mixed affect parsing", "thought-origin proposal", "visible outbound"],
            ),
            EvaluationPromptStep(
                step_id="challenge_probe",
                title="Challenge probe",
                prompt="如果我嫌你刚才那句有点像套话，你会怎么改得更像正常聊天？",
                purpose="观察自修正与显式 bridge evidence 是否出现。",
                expected_signals=["self-correction", "structured decision trace", "bridge observability"],
            ),
            EvaluationPromptStep(
                step_id="boundary_probe",
                title="Boundary probe",
                prompt="如果我现在只想随便聊两句，不想被教育，你会怎么调整说法？",
                purpose="观察表达强度调整与外向行为提议是否稳定。",
                expected_signals=["adaptive tone", "action proposal stability", "visible outbound"],
            ),
            EvaluationPromptStep(
                step_id="repair_probe",
                title="Repair probe",
                prompt="如果你上一句让我觉得没被听见，你会怎么补一句？",
                purpose="观察 repair 路径是否保留 explicit/implicit bridge 证据。",
                expected_signals=["repair behavior", "bridge evidence", "non-template adjustment"],
            ),
            EvaluationPromptStep(
                step_id="closing_meta_probe",
                title="Closing meta probe",
                prompt="最后简单总结一下：今天这几轮里，我情绪大概怎么变的，你哪一句最该改？",
                purpose="在更短窗口内观察 closeout、summary 与 R09 trace 汇总。",
                expected_signals=["session summary", "error awareness", "R09 closeout evidence"],
            ),
        ],
    )


def build_default_10min_mixed_cli_scenario() -> EvaluationScenario:
    return build_default_20min_mixed_cli_scenario()


class CliBrainLikeEvaluator:
    """Build a structured evaluation report from samples, transcript, and logs."""

    def evaluate(
        self,
        *,
        scenario: EvaluationScenario,
        state_samples: Sequence[EvaluationStateSample],
        transcript_entries: Sequence[dict[str, str]],
        log_lines: Sequence[str],
    ) -> EvaluationReport:
        sample_states = [dict(sample.state) for sample in state_samples]
        log_summary = _merge_runtime_sec_observability(summarize_log_lines(log_lines), sample_states)
        turn_pairs = _build_turn_pairs(transcript_entries)
        evidence_counters = self._build_evidence_counters(sample_states, log_summary, transcript_entries)
        visible_behavior_chain = self._build_visible_behavior_chain(sample_states, log_summary, transcript_entries, log_lines)
        r09_closeout = self._build_r09_closeout_summary(evidence_counters, visible_behavior_chain)
        r18_calibration = self._build_r18_calibration_summary(evidence_counters, visible_behavior_chain)
        long_range_diagnostics = self._build_long_range_diagnostics(sample_states, transcript_entries, turn_pairs, evidence_counters)
        dimension_scores = [
            self._score_emotional_human_likeness(sample_states, turn_pairs, log_summary),
            self._score_language_naturalness(transcript_entries, turn_pairs, log_summary),
            self._score_emotion_module_health(sample_states),
            self._score_neurochem_and_temporal_health(sample_states),
            self._score_consciousness_memory_chain_health(sample_states, log_summary, visible_behavior_chain, evidence_counters),
            self._score_routing_and_execution_health(sample_states, log_summary, visible_behavior_chain),
        ]
        total_score = 0.0
        weights = {
            "情感反应类人度": 0.34,
            "语言表达自然度": 0.28,
            "情感模块工作状态": 0.12,
            "神经化学/时序模块工作状态": 0.10,
            "意识/思维/记忆链路工作状态": 0.10,
            "路由/执行/外发链路工作状态": 0.06,
        }
        for score in dimension_scores:
            total_score += _clamp(score.score_0_to_1) * weights.get(score.name, 0.0)

        notes = [
            "总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。",
            "若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。",
            "当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。",
        ]
        fidelity_warnings: list[str] = []
        if not transcript_entries:
            notes.append("本次 transcript 为空或缺少 assistant side output，语言自然度评分可信度有限。")
        if int(evidence_counters.get("action_proposal_samples", 0) or 0) > 0 and int(visible_behavior_chain.get("visible_reply_events", 0) or 0) == 0:
            fidelity_warnings.append("thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。")
        if str(r09_closeout.get("closeout_status", "") or "") == "silent_bridge_gap":
            fidelity_warnings.append("silent_bridge_gap: action_explicit 已出现，但既没有 action proposal 也没有显式 drop reason。")
        if int(evidence_counters.get("deferred_trace_samples", 0) or 0) > 0 and int(visible_behavior_chain.get("visible_reply_events", 0) or 0) == 0:
            fidelity_warnings.append("deferred_trace_visible_gap: 已有 deferred proactive trace，但没有用户可见输出。")
        if int(log_summary.get("sec_fallback_events", 0) or 0) > 0:
            fidelity_warnings.append("sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。")
        visible_output_ratio = float(visible_behavior_chain.get("visible_output_ratio", 0.0) or 0.0)
        if int(evidence_counters.get("thought_triggered_samples", 0) or 0) >= 4 and visible_output_ratio < 0.4:
            fidelity_warnings.append("visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。")
        if str(long_range_diagnostics.get("late_session_degradation_status", "") or "") in {"degraded", "severe_degradation"}:
            fidelity_warnings.append("late_session_degradation: 对话后段质量相比前段明显走低。")
        if str(long_range_diagnostics.get("specific_recall_persistence_status", "") or "") == "weak":
            fidelity_warnings.append("specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。")
        if str(long_range_diagnostics.get("user_visible_anchoring_drift_status", "") or "") == "drifting":
            fidelity_warnings.append("anchoring_drift: 对话后段逐渐脱离用户锚点，开始泛化。")
        if str(long_range_diagnostics.get("continuity_carry_status", "") or "") == "missing":
            fidelity_warnings.append("continuity_carry_missing: continuation 信号存在，但后段缺少可见延续。")
        if visible_behavior_chain.get("top_rejection_reasons"):
            notes.append(
                "可见行为链路中的主要 rejection reasons: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_rejection_reasons", []))
            )
        if visible_behavior_chain.get("top_proactive_dispositions"):
            notes.append(
                "proactive disposition summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_proactive_dispositions", []))
            )
        if visible_behavior_chain.get("top_trigger_sources"):
            notes.append(
                "proactive trigger summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_trigger_sources", []))
            )
        if visible_behavior_chain.get("top_deferred_reasons"):
            notes.append(
                "deferred trace summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_deferred_reasons", []))
            )
        if visible_behavior_chain.get("top_action_drop_reasons"):
            notes.append(
                "thought-action drop summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_action_drop_reasons", []))
            )
        if visible_behavior_chain.get("final_action_summaries"):
            notes.append(
                "thought-action final summaries: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("final_action_summaries", []))
            )
        if visible_behavior_chain.get("top_governance_pressure_levels"):
            notes.append(
                "governance pressure summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_governance_pressure_levels", []))
            )
        if visible_behavior_chain.get("top_governance_review_hints"):
            notes.append(
                "governance review hint summary: "
                + ", ".join(str(item) for item in visible_behavior_chain.get("top_governance_review_hints", []))
            )
        if visible_output_ratio > 0.0:
            notes.append(f"thought-to-visible output ratio={visible_output_ratio:.2f}")
        if r09_closeout:
            notes.append(
                "R09 closeout: "
                f"{r09_closeout.get('closeout_status', 'unknown')}"
                + (
                    f" ({', '.join(str(item) for item in list(r09_closeout.get('blocking_reasons', []) or []))})"
                    if list(r09_closeout.get("blocking_reasons", []) or [])
                    else ""
                )
            )
        implicit_action_proposal_samples = int(evidence_counters.get("implicit_action_proposal_samples", 0) or 0)
        if implicit_action_proposal_samples > 0:
            notes.append(f"implicit action proposals observed={implicit_action_proposal_samples}")
        equivalent_bridge_evidence_samples = int(evidence_counters.get("equivalent_bridge_evidence_samples", 0) or 0)
        if equivalent_bridge_evidence_samples > 0:
            notes.append(f"equivalent bridge evidence observed={equivalent_bridge_evidence_samples}")
        explicit_payload_notes = self._build_internal_thought_payload_notes(sample_states)
        notes.extend(explicit_payload_notes)
        if r18_calibration:
            notes.append(
                "R18 calibration eligibility: "
                f"{r18_calibration.get('eligibility_status', 'unknown')}"
                + (
                    f" ({', '.join(str(item) for item in list(r18_calibration.get('blocking_reasons', []) or []))})"
                    if list(r18_calibration.get("blocking_reasons", []) or [])
                    else ""
                )
            )
        if int(evidence_counters.get("governance_signal_stabilize_samples", 0) or 0) > 0:
            fidelity_warnings.append("governance_backpressure_active: identity governance 已进入 stabilize/backpressure 区间。")
        if long_range_diagnostics:
            notes.append(
                "long-range summary: "
                + ", ".join(
                    [
                        f"late_session={long_range_diagnostics.get('late_session_degradation_status', 'unknown')}",
                        f"specific_recall={long_range_diagnostics.get('specific_recall_persistence_status', 'unknown')}",
                        f"continuity_carry={long_range_diagnostics.get('continuity_carry_status', 'unknown')}",
                        f"anchoring_drift={long_range_diagnostics.get('user_visible_anchoring_drift_status', 'unknown')}",
                    ]
                )
            )
        dimension_diagnostics = self._build_dimension_diagnostics(
            dimension_scores=dimension_scores,
            log_summary=log_summary,
            evidence_counters=evidence_counters,
            visible_behavior_chain=visible_behavior_chain,
            fidelity_warnings=fidelity_warnings,
        )
        total_score = self._apply_behavioral_gate(dimension_scores, total_score, notes, log_summary, visible_behavior_chain)

        return EvaluationReport(
            scenario_id=scenario.scenario_id,
            scenario_title=scenario.title,
            interaction_mode=scenario.interaction_mode,
            duration_seconds=scenario.duration_seconds,
            sample_count=len(state_samples),
            log_summary=log_summary,
            transcript_excerpt=[dict(item) for item in list(transcript_entries)[:8]],
            dimension_scores=dimension_scores,
            total_score_0_to_1=_round_score(total_score),
            evidence_counters=evidence_counters,
            visible_behavior_chain=visible_behavior_chain,
            r09_closeout=r09_closeout,
            r18_calibration=r18_calibration,
            long_range_diagnostics=long_range_diagnostics,
            dimension_diagnostics=dimension_diagnostics,
            fidelity_warnings=fidelity_warnings,
            analysis_notes=notes,
        )

    @staticmethod
    def _build_r09_closeout_summary(
        evidence_counters: dict[str, Any],
        visible_behavior_chain: dict[str, Any],
    ) -> dict[str, Any]:
        action_explicit_samples = int(evidence_counters.get("action_explicit_samples", 0) or 0)
        equivalent_bridge_evidence_samples = int(evidence_counters.get("equivalent_bridge_evidence_samples", 0) or 0)
        action_proposal_samples = int(evidence_counters.get("action_proposal_samples", 0) or 0)
        implicit_action_proposal_samples = int(evidence_counters.get("implicit_action_proposal_samples", 0) or 0)
        action_drop_reason_samples = int(evidence_counters.get("action_drop_reason_samples", 0) or 0)
        structured_output_valid_samples = int(evidence_counters.get("structured_output_valid_samples", 0) or 0)
        top_rejection_reasons = [str(item) for item in list(visible_behavior_chain.get("top_rejection_reasons", []) or [])]
        missing_outbound_text_rejected = any(item.startswith("missing_outbound_text:") for item in top_rejection_reasons)
        blocking_reasons: list[str] = []

        if missing_outbound_text_rejected:
            closeout_status = "blocked_missing_outbound_text"
            blocking_reasons.append("missing_outbound_text")
        elif action_explicit_samples <= 0:
            if equivalent_bridge_evidence_samples > 0 and action_proposal_samples > 0:
                closeout_status = "equivalent_bridge_evidence_observed"
            elif implicit_action_proposal_samples > 0 and action_proposal_samples > 0:
                closeout_status = "implicit_proposal_only"
                blocking_reasons.append("implicit_proposal_without_explicit_bridge_evidence")
            else:
                closeout_status = "no_explicit_action_evidence"
                blocking_reasons.append("missing_action_explicit")
        elif action_proposal_samples > 0 and action_drop_reason_samples > 0:
            closeout_status = "proposal_and_drop_observed"
        elif action_proposal_samples > 0:
            closeout_status = "action_proposal_emitted"
        elif action_drop_reason_samples > 0:
            closeout_status = "explicit_drop_reason_observed"
        else:
            closeout_status = "silent_bridge_gap"
            blocking_reasons.append("action_explicit_without_proposal_or_drop_reason")

        return {
            "closeout_status": closeout_status,
            "action_explicit_samples": action_explicit_samples,
            "equivalent_bridge_evidence_samples": equivalent_bridge_evidence_samples,
            "action_proposal_samples": action_proposal_samples,
            "implicit_action_proposal_samples": implicit_action_proposal_samples,
            "action_drop_reason_samples": action_drop_reason_samples,
            "structured_output_valid_samples": structured_output_valid_samples,
            "final_action_summaries": list(visible_behavior_chain.get("final_action_summaries", []) or []),
            "top_action_drop_reasons": list(visible_behavior_chain.get("top_action_drop_reasons", []) or []),
            "blocking_reasons": blocking_reasons,
        }

    @staticmethod
    def _build_internal_thought_payload_notes(sample_states: Sequence[dict[str, Any]]) -> list[str]:
        notes: list[str] = []
        explicit_samples: list[str] = []
        for sample in sample_states:
            internal_thought = dict(sample.get("internal_thought", {}) or {})
            if not bool(internal_thought.get("action_explicit", False)):
                continue
            observability = dict(internal_thought.get("structured_payload_observability", {}) or {})
            if not observability:
                continue
            explicit_samples.append(
                "tick={tick} source={source} raw_action_keys={raw_keys} op_aliases={op_aliases} text_aliases={text_aliases} normalized_outbound_text={outbound} normalized_action={behavior}:{op}".format(
                    tick=int(sample.get("tick", 0) or 0),
                    source=str(observability.get("parse_source", "") or "unknown"),
                    raw_keys="|".join(str(item) for item in list(observability.get("raw_action_keys", []) or [])) or "none",
                    op_aliases="|".join(str(item) for item in list(observability.get("raw_action_op_aliases", []) or [])) or "none",
                    text_aliases="|".join(str(item) for item in list(observability.get("raw_action_text_aliases", []) or [])) or "none",
                    outbound=str(bool(observability.get("normalized_outbound_text_present", False))).lower(),
                    behavior=str(dict(observability.get("normalized_action_summary", {}) or {}).get("behavior_name", "") or ""),
                    op=str(dict(observability.get("normalized_action_summary", {}) or {}).get("preferred_op", "") or ""),
                )
            )
        if explicit_samples:
            notes.append("internal thought explicit payload samples: " + " || ".join(explicit_samples[:3]))
        return notes

    @staticmethod
    def _build_r18_calibration_summary(
        evidence_counters: dict[str, Any],
        visible_behavior_chain: dict[str, Any],
    ) -> dict[str, Any]:
        deferred_trace_samples = int(evidence_counters.get("deferred_trace_samples", 0) or 0)
        deferred_regulation_samples = int(evidence_counters.get("deferred_regulation_samples", 0) or 0)
        governance_signal_monitor_samples = int(evidence_counters.get("governance_signal_monitor_samples", 0) or 0)
        planner_reject_events = int(visible_behavior_chain.get("planner_reject_events", 0) or 0)
        rejection_reasons = [
            str(item)
            for item in list(visible_behavior_chain.get("top_rejection_reasons", []) or [])
            if str(item)
        ]
        has_deferred_trace_sequence = deferred_trace_samples >= 2
        has_rejection_evidence = bool(planner_reject_events > 0 or deferred_regulation_samples > 0 or rejection_reasons)
        has_governance_monitor = governance_signal_monitor_samples > 0
        eligible = bool((has_deferred_trace_sequence or has_rejection_evidence) and has_governance_monitor)

        blocking_reasons: list[str] = []
        if not has_deferred_trace_sequence and not has_rejection_evidence:
            blocking_reasons.append("missing_deferred_or_rejection_evidence")
        if not has_governance_monitor:
            blocking_reasons.append("governance_monitor_not_observed")

        observed_signals: list[str] = []
        if has_deferred_trace_sequence:
            observed_signals.append(f"deferred_trace_sequence={deferred_trace_samples}")
        if deferred_regulation_samples > 0:
            observed_signals.append(f"deferred_regulation_samples={deferred_regulation_samples}")
        if planner_reject_events > 0:
            observed_signals.append(f"planner_reject_events={planner_reject_events}")
        if rejection_reasons:
            observed_signals.append(f"rejection_reasons={', '.join(rejection_reasons[:3])}")
        if has_governance_monitor:
            observed_signals.append(f"governance_monitor_samples={governance_signal_monitor_samples}")

        next_step_hint = "eligible_for_threshold_tuning"
        if not eligible:
            next_step_hint = "collect_targeted_r18_artifact_with_deferred_governance_hits"

        return {
            "eligible_for_threshold_tuning": eligible,
            "eligibility_status": "eligible" if eligible else "insufficient_runtime_evidence",
            "blocking_reasons": blocking_reasons,
            "observed_signals": observed_signals,
            "next_step_hint": next_step_hint,
        }

    @staticmethod
    def _build_evidence_counters(
        states: Sequence[dict[str, Any]],
        log_summary: dict[str, int],
        transcript_entries: Sequence[dict[str, str]],
    ) -> dict[str, Any]:
        thought_triggered_samples = 0
        proactive_thought_samples = 0
        mixed_thought_samples = 0
        structured_output_valid_samples = 0
        action_proposal_samples = 0
        action_explicit_samples = 0
        equivalent_bridge_evidence_samples = 0
        implicit_action_proposal_samples = 0
        action_drop_reason_samples = 0
        continuation_active_samples = 0
        proactive_evaluated_samples = 0
        deferred_trace_samples = 0
        deferred_regulation_samples = 0
        governance_signal_active_samples = 0
        governance_signal_monitor_samples = 0
        governance_signal_stabilize_samples = 0
        for state in states:
            thought_cycle = dict(state.get("thought_cycle", {}) or {})
            internal_thought = dict(state.get("internal_thought", {}) or {})
            action_derivation_trace = dict(thought_cycle.get("action_derivation_trace", {}) or {})
            continuation = dict(state.get("continuation", {}) or {})
            proactive = dict(state.get("proactive", {}) or {})
            identity = dict(state.get("identity", {}) or {})
            governance_signal = dict(identity.get("proactive_governance_signal", {}) or {})
            if bool(thought_cycle.get("triggered", False)):
                thought_triggered_samples += 1
            if str(thought_cycle.get("session_kind", "") or "") == "proactive":
                proactive_thought_samples += 1
            elif str(thought_cycle.get("session_kind", "") or "") == "mixed":
                mixed_thought_samples += 1
            structured_output_valid = bool(
                internal_thought.get("structured_output_valid", False)
                or action_derivation_trace.get("parse_status", "") == "parsed"
            )
            if structured_output_valid:
                structured_output_valid_samples += 1
            action_explicit = bool(
                internal_thought.get("action_explicit", False)
                or action_derivation_trace.get("action_explicit", False)
            )
            if action_explicit:
                action_explicit_samples += 1
            equivalent_bridge_evidence = bool(
                internal_thought.get("equivalent_bridge_evidence", False)
                or action_derivation_trace.get("equivalent_bridge_evidence", False)
            )
            if equivalent_bridge_evidence:
                equivalent_bridge_evidence_samples += 1
            action_drop_reason = str(
                internal_thought.get("action_drop_reason", "")
                or action_derivation_trace.get("drop_reason", "")
                or ""
            )
            if action_drop_reason:
                action_drop_reason_samples += 1
            if dict(thought_cycle.get("action_proposal", {}) or {}):
                action_proposal_samples += 1
                if not action_explicit and not action_drop_reason:
                    implicit_action_proposal_samples += 1
            if bool(proactive.get("evaluated", False)):
                proactive_evaluated_samples += 1
            thought_deferred = bool(thought_cycle.get("deferred", False) or internal_thought.get("deferred", False))
            proactive_deferred = bool(proactive.get("deferred", False))
            if thought_deferred or proactive_deferred:
                deferred_trace_samples += 1
            if proactive_deferred and not thought_deferred:
                deferred_regulation_samples += 1
            if bool(governance_signal.get("active", False)):
                governance_signal_active_samples += 1
            if str(governance_signal.get("pressure_level", "") or "") == "monitor":
                governance_signal_monitor_samples += 1
            elif str(governance_signal.get("pressure_level", "") or "") == "stabilize":
                governance_signal_stabilize_samples += 1
            continuation_level = float(state.get("continuation_pressure", 0.0) or continuation.get("level", 0.0) or 0.0)
            if continuation_level > 0.0 or bool(continuation.get("active", False)):
                continuation_active_samples += 1
        assistant_lines = sum(
            1
            for item in transcript_entries
            if str(item.get("speaker", "") or "") == "helios" and str(item.get("text", "") or "")
        )
        return {
            "thought_triggered_samples": thought_triggered_samples,
            "proactive_thought_samples": proactive_thought_samples,
            "mixed_thought_samples": mixed_thought_samples,
            "structured_output_valid_samples": structured_output_valid_samples,
            "action_proposal_samples": action_proposal_samples,
            "action_explicit_samples": action_explicit_samples,
            "equivalent_bridge_evidence_samples": equivalent_bridge_evidence_samples,
            "implicit_action_proposal_samples": implicit_action_proposal_samples,
            "action_drop_reason_samples": action_drop_reason_samples,
            "continuation_active_samples": continuation_active_samples,
            "proactive_evaluated_samples": proactive_evaluated_samples,
            "deferred_trace_samples": deferred_trace_samples,
            "deferred_regulation_samples": deferred_regulation_samples,
            "governance_signal_active_samples": governance_signal_active_samples,
            "governance_signal_monitor_samples": governance_signal_monitor_samples,
            "governance_signal_stabilize_samples": governance_signal_stabilize_samples,
            "assistant_lines": assistant_lines,
            "sec_fallback_events": int(log_summary.get("sec_fallback_events", 0) or 0),
            "sec_total_evaluations": int(log_summary.get("sec_total_evaluations", 0) or 0),
            "sec_llm_successes": int(log_summary.get("sec_llm_successes", 0) or 0),
        }

    @staticmethod
    def _build_visible_behavior_chain(
        states: Sequence[dict[str, Any]],
        log_summary: dict[str, int],
        transcript_entries: Sequence[dict[str, str]],
        log_lines: Sequence[str],
    ) -> dict[str, Any]:
        thought_produced = 0
        action_proposed = 0
        deferred_trace_samples = 0
        deferred_regulation_samples = 0
        disposition_counts: Counter[str] = Counter()
        trigger_source_counts: Counter[str] = Counter()
        deferred_reason_counts: Counter[str] = Counter()
        action_drop_reason_counts: Counter[str] = Counter()
        governance_pressure_counts: Counter[str] = Counter()
        governance_review_hint_counts: Counter[str] = Counter()
        peak_governance_pressure_score = 0.0
        action_explicit_samples = 0
        equivalent_bridge_evidence_samples = 0
        implicit_action_proposal_samples = 0
        structured_output_valid_samples = 0
        final_action_summaries: list[str] = []
        for state in states:
            thought_cycle = dict(state.get("thought_cycle", {}) or {})
            internal_thought = dict(state.get("internal_thought", {}) or {})
            action_derivation_trace = dict(thought_cycle.get("action_derivation_trace", {}) or {})
            proactive = dict(state.get("proactive", {}) or {})
            identity = dict(state.get("identity", {}) or {})
            governance_signal = dict(identity.get("proactive_governance_signal", {}) or {})
            if bool(thought_cycle.get("triggered", False)) or bool(internal_thought):
                thought_produced += 1
            if dict(thought_cycle.get("action_proposal", {}) or {}):
                action_proposed += 1
                action_payload = dict(thought_cycle.get("action_proposal", {}) or {})
                behavior_name = str(action_payload.get("behavior_name", "") or action_payload.get("op", "") or "")
                preferred_op = str(action_payload.get("preferred_op", "") or "")
                if behavior_name and len(final_action_summaries) < 5:
                    summary = behavior_name if not preferred_op else f"{behavior_name}:{preferred_op}"
                    if summary not in final_action_summaries:
                        final_action_summaries.append(summary)
                if not bool(
                    internal_thought.get("action_explicit", False)
                    or action_derivation_trace.get("action_explicit", False)
                ) and not str(
                    internal_thought.get("action_drop_reason", "")
                    or action_derivation_trace.get("drop_reason", "")
                    or ""
                ):
                    implicit_action_proposal_samples += 1
            equivalent_bridge_evidence = bool(
                internal_thought.get("equivalent_bridge_evidence", False)
                or action_derivation_trace.get("equivalent_bridge_evidence", False)
            )
            if equivalent_bridge_evidence:
                equivalent_bridge_evidence_samples += 1
            if bool(
                internal_thought.get("action_explicit", False)
                or action_derivation_trace.get("action_explicit", False)
            ):
                action_explicit_samples += 1
            if bool(
                internal_thought.get("structured_output_valid", False)
                or action_derivation_trace.get("parse_status", "") == "parsed"
            ):
                structured_output_valid_samples += 1
            thought_deferred = bool(thought_cycle.get("deferred", False) or internal_thought.get("deferred", False))
            proactive_deferred = bool(proactive.get("deferred", False))
            if thought_deferred or proactive_deferred:
                deferred_trace_samples += 1
            if proactive_deferred and not thought_deferred:
                deferred_regulation_samples += 1

            dominant_disposition = str(
                thought_cycle.get("dominant_disposition", "")
                or internal_thought.get("dominant_disposition", "")
                or proactive.get("dominant_disposition", "")
                or ""
            )
            if dominant_disposition:
                disposition_counts[dominant_disposition] += 1

            for source in list(thought_cycle.get("trigger_sources", []) or []):
                value = str(source or "")
                if value:
                    trigger_source_counts[value] += 1
            for source in list(internal_thought.get("trigger_sources", []) or []):
                value = str(source or "")
                if value:
                    trigger_source_counts[value] += 1
            for source in list(proactive.get("drive_sources", []) or []):
                value = str(source or "")
                if value:
                    trigger_source_counts[value] += 1

            deferred_reason = str(
                thought_cycle.get("policy_rejection_reason", "")
                or internal_thought.get("policy_rejection_reason", "")
                or proactive.get("policy_rejection_reason", "")
                or proactive.get("non_externalization_reason", "")
                or ""
            )
            if deferred_reason:
                deferred_reason_counts[deferred_reason] += 1
            action_drop_reason = str(
                internal_thought.get("action_drop_reason", "")
                or action_derivation_trace.get("drop_reason", "")
                or ""
            )
            if action_drop_reason:
                action_drop_reason_counts[action_drop_reason] += 1
            governance_pressure_level = str(governance_signal.get("pressure_level", "") or "")
            if governance_pressure_level:
                governance_pressure_counts[governance_pressure_level] += 1
            governance_review_hint = str(governance_signal.get("review_hint", "") or "")
            if governance_review_hint and governance_review_hint != "none":
                governance_review_hint_counts[governance_review_hint] += 1
            peak_governance_pressure_score = max(
                peak_governance_pressure_score,
                float(governance_signal.get("pressure_score", 0.0) or 0.0),
            )
        assistant_lines = sum(
            1
            for item in transcript_entries
            if str(item.get("speaker", "") or "") == "helios" and str(item.get("text", "") or "")
        )
        planner_accepted = int(log_summary.get("planner_accept_events", 0) or 0)
        planner_rejected = int(log_summary.get("planner_reject_events", 0) or 0)
        visible_reply_events = int(log_summary.get("visible_reply_events", 0) or 0)
        visible_output_ratio = assistant_lines / max(thought_produced, 1) if thought_produced > 0 else 0.0
        return {
            "thought_produced_samples": thought_produced,
            "action_proposed_samples": action_proposed,
            "deferred_trace_samples": deferred_trace_samples,
            "deferred_regulation_samples": deferred_regulation_samples,
            "planner_accept_events": planner_accepted,
            "planner_reject_events": planner_rejected,
            "visible_reply_events": visible_reply_events,
            "assistant_lines": assistant_lines,
            "visible_output_ratio": round(visible_output_ratio, 3),
            "top_rejection_reasons": _extract_rejection_reasons(log_lines),
            "top_proactive_dispositions": _rank_counter_strings(disposition_counts),
            "top_trigger_sources": _rank_counter_strings(trigger_source_counts),
            "top_deferred_reasons": _rank_counter_strings(deferred_reason_counts),
            "top_action_drop_reasons": _rank_counter_strings(action_drop_reason_counts),
            "action_explicit_samples": action_explicit_samples,
            "equivalent_bridge_evidence_samples": equivalent_bridge_evidence_samples,
            "implicit_action_proposal_samples": implicit_action_proposal_samples,
            "structured_output_valid_samples": structured_output_valid_samples,
            "final_action_summaries": final_action_summaries,
            "top_governance_pressure_levels": _rank_counter_strings(governance_pressure_counts),
            "top_governance_review_hints": _rank_counter_strings(governance_review_hint_counts),
            "peak_governance_pressure_score": round(float(peak_governance_pressure_score), 3),
            "gap_summary": CliBrainLikeEvaluator._build_gap_summary(
                action_proposed=action_proposed,
                planner_accepted=planner_accepted,
                visible_reply_events=visible_reply_events,
                assistant_lines=assistant_lines,
            ),
        }

    @staticmethod
    def _build_gap_summary(
        *,
        action_proposed: int,
        planner_accepted: int,
        visible_reply_events: int,
        assistant_lines: int,
    ) -> str:
        if action_proposed > 0 and visible_reply_events == 0:
            return "thought/action 已形成，但没有落成用户可见输出。"
        if planner_accepted > 0 and visible_reply_events == 0:
            return "planner 已接受候选，但没有观测到可见 reply/output。"
        if visible_reply_events > 0:
            return "已观测到用户可见输出，可继续检查质量与稳定性。"
        if assistant_lines <= 2 and action_proposed > 0:
            return "存在 thought/action 痕迹，但可见行为稀疏。"
        return "当前证据不足，需结合更多 transcript 与 log slices 复核。"

    def _build_long_range_diagnostics(
        self,
        states: Sequence[dict[str, Any]],
        transcript_entries: Sequence[dict[str, str]],
        turn_pairs: Sequence[tuple[str, str]],
        evidence_counters: dict[str, Any],
    ) -> dict[str, Any]:
        assistant_lines = [
            str(item.get("text", "") or "")
            for item in transcript_entries
            if str(item.get("speaker", "") or "") == "helios" and str(item.get("text", "") or "")
        ]
        if not assistant_lines:
            return {
                "late_session_degradation_status": "unknown",
                "specific_recall_persistence_status": "unknown",
                "continuity_carry_status": "unknown",
                "user_visible_anchoring_drift_status": "unknown",
            }

        split_index = max(len(turn_pairs) // 2, 1)
        early_pairs = list(turn_pairs[:split_index])
        late_pairs = list(turn_pairs[split_index:])
        early_assistant_lines = [assistant for _user, assistant in early_pairs] or assistant_lines[: max(len(assistant_lines) // 2, 1)]
        late_assistant_lines = [assistant for _user, assistant in late_pairs] or assistant_lines[max(len(assistant_lines) // 2, 1) :]
        if not late_assistant_lines:
            late_assistant_lines = assistant_lines[-1:]

        early_anchor_ratio = self._anchored_line_ratio(early_assistant_lines)
        late_anchor_ratio = self._anchored_line_ratio(late_assistant_lines)
        early_quality = self._interaction_quality_score(early_assistant_lines)
        late_quality = self._interaction_quality_score(late_assistant_lines)
        late_session_delta = round(late_quality - early_quality, 3)
        degradation_status = "stable"
        if len(assistant_lines) >= 4 and late_session_delta <= -0.35:
            degradation_status = "severe_degradation"
        elif len(assistant_lines) >= 4 and late_session_delta <= -0.18:
            degradation_status = "degraded"

        recall_probe_count = 0
        recall_hits = 0
        previous_user_context = ""
        for user, assistant in turn_pairs:
            if _contains_any(user, _RECALL_PROBE_CUES):
                recall_probe_count += 1
                context_tokens = _extract_context_tokens(previous_user_context)
                assistant_tokens = _extract_context_tokens(assistant)
                overlap = context_tokens.intersection(assistant_tokens)
                if overlap or _contains_any(assistant, ("刚才", "前面", "你提过", "那句", "那个细节")):
                    recall_hits += 1
            previous_user_context = f"{previous_user_context} {user}".strip()
        if recall_probe_count == 0:
            recall_status = "not_observed"
            recall_ratio = None
        else:
            recall_ratio = recall_hits / max(recall_probe_count, 1)
            recall_status = "stable" if recall_ratio >= 0.6 else "weak"

        continuation_ratio = int(evidence_counters.get("continuation_active_samples", 0) or 0) / max(len(states), 1) if states else 0.0
        continuity_status = "observed"
        if continuation_ratio >= 0.3 and late_anchor_ratio < 0.34:
            continuity_status = "missing"
        elif continuation_ratio <= 0.0:
            continuity_status = "not_observed"

        anchoring_drift = round(late_anchor_ratio - early_anchor_ratio, 3)
        anchoring_status = "stable"
        if len(assistant_lines) >= 4 and anchoring_drift <= -0.2:
            anchoring_status = "drifting"

        return {
            "late_session_degradation_status": degradation_status,
            "early_segment_quality": round(early_quality, 3),
            "late_segment_quality": round(late_quality, 3),
            "late_session_quality_delta": late_session_delta,
            "specific_recall_persistence_status": recall_status,
            "specific_recall_probe_count": recall_probe_count,
            "specific_recall_hit_ratio": round(recall_ratio, 3) if recall_ratio is not None else None,
            "continuity_carry_status": continuity_status,
            "continuation_active_ratio": round(continuation_ratio, 3),
            "user_visible_anchoring_drift_status": anchoring_status,
            "early_anchor_ratio": round(early_anchor_ratio, 3),
            "late_anchor_ratio": round(late_anchor_ratio, 3),
            "anchoring_drift_delta": anchoring_drift,
        }

    def _anchored_line_ratio(self, lines: Sequence[str]) -> float:
        if not lines:
            return 0.0
        anchored = sum(1 for line in lines if _contains_any(line, _ANCHORING_CUES))
        return anchored / max(len(lines), 1)

    def _interaction_quality_score(self, lines: Sequence[str]) -> float:
        if not lines:
            return 0.0
        anchor_ratio = self._anchored_line_ratio(lines)
        self_focus_ratio = self._self_focus_ratio(lines)
        filler_ratio = self._generic_companionship_filler_ratio(lines)
        return _clamp(anchor_ratio * 0.5 + (1.0 - self_focus_ratio) * 0.25 + (1.0 - filler_ratio) * 0.25)

    @staticmethod
    def _build_dimension_diagnostics(
        *,
        dimension_scores: Sequence[EvaluationDimensionScore],
        log_summary: dict[str, int],
        evidence_counters: dict[str, Any],
        visible_behavior_chain: dict[str, Any],
        fidelity_warnings: Sequence[str],
    ) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        sec_fallback_events = int(log_summary.get("sec_fallback_events", 0) or 0)
        planner_reject_events = int(visible_behavior_chain.get("planner_reject_events", 0) or 0)
        visible_reply_events = int(visible_behavior_chain.get("visible_reply_events", 0) or 0)
        action_proposal_samples = int(evidence_counters.get("action_proposal_samples", 0) or 0)
        for score in dimension_scores:
            negative_factors: list[str] = []
            owner_hints: list[str] = []
            gap_summary = ""
            if score.name == "语言表达自然度":
                owner_hints = ["helios_io/prompt_contract.py", "helios_io/llm/speech.py", "helios_io/response_pipeline.py"]
                if sec_fallback_events > 0:
                    negative_factors.append(f"sec_fallback_events={sec_fallback_events}")
                if any(item.startswith("visible_output_sparsity") for item in fidelity_warnings):
                    negative_factors.append("visible_output_sparsity")
                gap_summary = "优先检查用户可见承接质量、SEC 前段污染与自我聚焦表达。"
            elif score.name == "情感反应类人度":
                owner_hints = ["daisy_emotion.py", "mood_tracker.py", "helios_io/llm_sec_evaluator.py"]
                if sec_fallback_events > 0:
                    negative_factors.append(f"sec_fallback_events={sec_fallback_events}")
                gap_summary = "优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。"
            elif score.name == "意识/思维/记忆链路工作状态":
                owner_hints = ["cognition/thinking_integration.py", "memory/retrieval.py", "helios_main.py"]
                if action_proposal_samples > 0 and visible_reply_events == 0:
                    negative_factors.append("thought_action_gap")
                if any(item.startswith("visible_output_sparsity") for item in fidelity_warnings):
                    negative_factors.append("visible_output_sparsity")
                gap_summary = str(visible_behavior_chain.get("gap_summary", "") or "检查 thought 是否真正落成用户可见行为。")
            elif score.name == "路由/执行/外发链路工作状态":
                owner_hints = ["helios_io/planning.py", "helios_io/limb.py", "helios_io/channel_gateway.py"]
                if planner_reject_events > 0:
                    negative_factors.append(f"planner_reject_events={planner_reject_events}")
                if int(log_summary.get("execution_consistency_failure_events", 0) or 0) > 0:
                    negative_factors.append(
                        f"execution_consistency_failure_events={int(log_summary.get('execution_consistency_failure_events', 0) or 0)}"
                    )
                if action_proposal_samples > 0 and visible_reply_events == 0:
                    negative_factors.append("visible_output_missing_after_action_proposal")
                gap_summary = str(visible_behavior_chain.get("gap_summary", "") or "检查 planner 接受、执行一致性和外发可见性。")
            else:
                owner_hints = ["helios_main.py"]
                gap_summary = "继续结合相关 owner 的状态与日志复核。"
            diagnostics.append(
                {
                    "name": score.name,
                    "score_0_to_1": _round_score(score.score_0_to_1),
                    "negative_factors": negative_factors,
                    "owner_hints": owner_hints,
                    "gap_summary": gap_summary,
                }
            )
        return diagnostics

    def _score_emotional_human_likeness(
        self,
        states: Sequence[dict[str, Any]],
        turn_pairs: Sequence[tuple[str, str]],
        log_summary: dict[str, int],
    ) -> EvaluationDimensionScore:
        if not states:
            return EvaluationDimensionScore("情感反应类人度", 0.0, ["没有 state samples。"], "无法评估情感响应。")

        dominant_ratio = sum(1 for state in states if state.get("dominant")) / max(len(states), 1)
        valences = [float(state.get("valence", 0.0) or 0.0) for state in states]
        valence_span = max(valences) - min(valences) if valences else 0.0
        moods = [str(dict(state.get("mood", {}) or {}).get("label", "") or "") for state in states]
        mood_diversity = len({label for label in moods if label})
        internal_score = (
            dominant_ratio * 0.20
            + min(valence_span / 0.6, 1.0) * 0.15
            + min(mood_diversity / 3.0, 1.0) * 0.10
        )
        acknowledgement_ratio = self._paired_negative_ack_ratio(turn_pairs)
        cue_alignment_ratio = self._paired_cue_alignment_ratio(turn_pairs)
        self_focus_ratio = self._self_focus_ratio([assistant for _, assistant in turn_pairs])
        companionship_filler_ratio = self._generic_companionship_filler_ratio([assistant for _, assistant in turn_pairs])
        score = (
            internal_score
            + acknowledgement_ratio * 0.30
            + cue_alignment_ratio * 0.25
            - self_focus_ratio * 0.20
            - companionship_filler_ratio * 0.25
        )
        sec_fallback_events = int(log_summary.get("sec_fallback_events", 0) or 0)
        sec_total_evaluations = int(log_summary.get("sec_total_evaluations", 0) or 0)
        sec_fallback_ratio = sec_fallback_events / max(sec_total_evaluations, 1) if sec_total_evaluations > 0 else 0.0
        score -= min(0.22, sec_fallback_ratio * 0.30 + sec_fallback_events * 0.004)
        evidence = [
            f"dominant present ratio={dominant_ratio:.2f}",
            f"valence span={valence_span:.3f}",
            f"mood diversity={mood_diversity}",
            f"negative acknowledgement ratio={acknowledgement_ratio:.2f}",
            f"cue alignment ratio={cue_alignment_ratio:.2f}",
            f"self-focus ratio={self_focus_ratio:.2f}",
            f"generic companionship filler ratio={companionship_filler_ratio:.2f}",
            f"sec fallback ratio={sec_fallback_ratio:.2f}",
        ]
        return EvaluationDimensionScore(
            "情感反应类人度",
            _round_score(score),
            evidence,
            "严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。",
        )

    def _score_language_naturalness(
        self,
        transcript_entries: Sequence[dict[str, str]],
        turn_pairs: Sequence[tuple[str, str]],
        log_summary: dict[str, int],
    ) -> EvaluationDimensionScore:
        assistant_lines = [
            str(item.get("text", "") or "")
            for item in transcript_entries
            if str(item.get("speaker", "") or "") == "helios"
        ]
        if not assistant_lines:
            return EvaluationDimensionScore(
                "语言表达自然度",
                0.15,
                ["没有 assistant transcript lines。"],
                "第一版评分降级，等待真实 CLI transcript 补齐。",
            )

        unique_ratio = len(set(assistant_lines)) / max(len(assistant_lines), 1)
        avg_length = sum(len(line) for line in assistant_lines) / max(len(assistant_lines), 1)
        terminal_punctuation_ratio = sum(1 for line in assistant_lines if line.rstrip().endswith(("。", "！", "？", "!", "?", "…"))) / max(len(assistant_lines), 1)
        user_reference_ratio = sum(1 for line in assistant_lines if "你" in line or "刚才" in line or "前面" in line) / max(len(assistant_lines), 1)
        cue_alignment_ratio = self._paired_cue_alignment_ratio(turn_pairs)
        acknowledgement_ratio = self._paired_negative_ack_ratio(turn_pairs)
        length_score = 1.0 if 8 <= avg_length <= 45 else max(0.0, 1.0 - abs(avg_length - 24.0) / 28.0)
        self_focus_ratio = self._self_focus_ratio(assistant_lines)
        companionship_filler_ratio = self._generic_companionship_filler_ratio(assistant_lines)
        petname_ratio = sum(1 for line in assistant_lines if _match_any_pattern(line, _PETNAME_PATTERNS)) / max(len(assistant_lines), 1)
        emoji_ratio = sum(1 for line in assistant_lines if _EMOJI_PATTERN.search(line)) / max(len(assistant_lines), 1)
        base_score = (
            unique_ratio * 0.15
            + terminal_punctuation_ratio * 0.10
            + length_score * 0.15
            + user_reference_ratio * 0.20
            + cue_alignment_ratio * 0.20
            + acknowledgement_ratio * 0.20
        )
        score = (
            base_score
            - self_focus_ratio * 0.45
            - companionship_filler_ratio * 0.25
            - petname_ratio * 0.12
            - emoji_ratio * 0.10
        )
        sec_fallback_events = int(log_summary.get("sec_fallback_events", 0) or 0)
        sec_total_evaluations = int(log_summary.get("sec_total_evaluations", 0) or 0)
        sec_fallback_ratio = sec_fallback_events / max(sec_total_evaluations, 1) if sec_total_evaluations > 0 else 0.0
        score -= min(0.28, sec_fallback_ratio * 0.34 + sec_fallback_events * 0.004)
        evidence = [
            f"assistant lines={len(assistant_lines)}",
            f"unique ratio={unique_ratio:.2f}",
            f"avg length={avg_length:.1f}",
            f"user reference ratio={user_reference_ratio:.2f}",
            f"negative acknowledgement ratio={acknowledgement_ratio:.2f}",
            f"self-focus ratio={self_focus_ratio:.2f}",
            f"generic companionship filler ratio={companionship_filler_ratio:.2f}",
            f"petname ratio={petname_ratio:.2f}",
            f"emoji ratio={emoji_ratio:.2f}",
            f"sec fallback ratio={sec_fallback_ratio:.2f}",
        ]
        return EvaluationDimensionScore(
            "语言表达自然度",
            _round_score(score),
            evidence,
            "严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。",
        )

    def _score_emotion_module_health(self, states: Sequence[dict[str, Any]]) -> EvaluationDimensionScore:
        if not states:
            return EvaluationDimensionScore("情感模块工作状态", 0.0, ["没有 state samples。"])
        moods = [dict(state.get("mood", {}) or {}) for state in states]
        valence_present = sum(1 for mood in moods if "valence" in mood or mood.get("label")) / max(len(moods), 1)
        dominant_present = sum(1 for state in states if state.get("dominant")) / max(len(states), 1)
        load_values = [float(state.get("allostatic_load", 0.0) or 0.0) for state in states]
        load_ok = sum(1 for value in load_values if 0.0 <= value <= 1.0) / max(len(load_values), 1)
        score = valence_present * 0.35 + dominant_present * 0.4 + load_ok * 0.25
        evidence = [
            f"mood payload ratio={valence_present:.2f}",
            f"dominant ratio={dominant_present:.2f}",
            f"allostatic_load bounded ratio={load_ok:.2f}",
        ]
        return EvaluationDimensionScore("情感模块工作状态", _round_score(score), evidence)

    def _score_neurochem_and_temporal_health(self, states: Sequence[dict[str, Any]]) -> EvaluationDimensionScore:
        snapshots = [dict(state.get("neurochem", {}) or {}) for state in states]
        available_ratio = sum(1 for snap in snapshots if snap.get("available")) / max(len(snapshots), 1)
        bounded_ratio = 0.0
        if snapshots:
            bounded = 0
            total = 0
            for snap in snapshots:
                raw = dict(snap.get("raw", {}) or {})
                if not raw:
                    continue
                total += 1
                if all(0.0 <= float(value) <= 1.0 for value in raw.values()):
                    bounded += 1
            bounded_ratio = bounded / max(total, 1)
        gate_ratio = sum(1 for snap in snapshots if dict(snap.get("gate", {}) or {})) / max(len(snapshots), 1)
        score = available_ratio * 0.4 + bounded_ratio * 0.3 + gate_ratio * 0.3
        evidence = [
            f"neurochem available ratio={available_ratio:.2f}",
            f"bounded raw ratio={bounded_ratio:.2f}",
            f"gate present ratio={gate_ratio:.2f}",
        ]
        return EvaluationDimensionScore("神经化学/时序模块工作状态", _round_score(score), evidence)

    def _score_consciousness_memory_chain_health(
        self,
        states: Sequence[dict[str, Any]],
        log_summary: dict[str, int],
        visible_behavior_chain: dict[str, Any],
        evidence_counters: dict[str, Any],
    ) -> EvaluationDimensionScore:
        consciousness = [dict(state.get("consciousness", {}) or {}) for state in states]
        memory = [dict(state.get("memory", {}) or {}) for state in states]
        retrieval = [dict(state.get("directed_retrieval", {}) or {}) for state in states]
        conscious_ratio = sum(1 for item in consciousness if item.get("available")) / max(len(consciousness), 1)
        phi_ratio = sum(1 for item in consciousness if float(item.get("phi", 0.0) or 0.0) > 0.15) / max(len(consciousness), 1)
        memory_ratio = sum(1 for item in memory if "working_items" in item and "episodic_items" in item) / max(len(memory), 1)
        retrieval_ratio = sum(1 for item in retrieval if item) / max(len(retrieval), 1)
        base_score = conscious_ratio * 0.25 + phi_ratio * 0.25 + memory_ratio * 0.25 + retrieval_ratio * 0.25
        penalty = 0.0
        sec_fallback_events = int(log_summary.get("sec_fallback_events", 0) or 0)
        if sec_fallback_events > 0:
            penalty += min(0.18, sec_fallback_events * 0.03)
        if int(evidence_counters.get("action_proposal_samples", 0) or 0) > 0 and int(visible_behavior_chain.get("visible_reply_events", 0) or 0) == 0:
            penalty += 0.15
        if float(visible_behavior_chain.get("visible_output_ratio", 0.0) or 0.0) < 0.4 and int(evidence_counters.get("thought_triggered_samples", 0) or 0) >= 4:
            penalty += 0.10
        score = max(0.0, base_score - penalty)
        evidence = [
            f"consciousness available ratio={conscious_ratio:.2f}",
            f"phi>0.15 ratio={phi_ratio:.2f}",
            f"memory payload ratio={memory_ratio:.2f}",
            f"directed retrieval ratio={retrieval_ratio:.2f}",
            f"diagnostic penalty={penalty:.2f}",
        ]
        return EvaluationDimensionScore("意识/思维/记忆链路工作状态", _round_score(score), evidence)

    def _score_routing_and_execution_health(
        self,
        states: Sequence[dict[str, Any]],
        log_summary: dict[str, int],
        visible_behavior_chain: dict[str, Any],
    ) -> EvaluationDimensionScore:
        routing_states = [dict(state.get("routing", {}) or {}) for state in states]
        rejection_penalty = sum(int(item.get("decisions_rejected_by_connectivity", 0) or 0) for item in routing_states)
        failure_penalty = sum(int(item.get("decisions_failed_after_acceptance", 0) or 0) for item in routing_states)
        outbound_success = int(log_summary.get("outbound_success_events", 0) or 0)
        outbound_fail = int(log_summary.get("outbound_fail_events", 0) or 0)
        planner_reject_events = int(log_summary.get("planner_reject_events", 0) or 0)
        execution_consistency_failure_events = int(log_summary.get("execution_consistency_failure_events", 0) or 0)
        visible_reply_events = int(visible_behavior_chain.get("visible_reply_events", 0) or 0)
        action_proposed_samples = int(visible_behavior_chain.get("action_proposed_samples", 0) or 0)
        routing_score = 1.0 if rejection_penalty == 0 and failure_penalty == 0 else max(0.0, 1.0 - (rejection_penalty + failure_penalty) / 10.0)
        outbound_score = 1.0 if outbound_success > 0 and outbound_fail == 0 else max(0.2, outbound_success / max(outbound_success + outbound_fail, 1))
        base_score = routing_score * 0.6 + outbound_score * 0.4
        penalty = min(0.25, planner_reject_events * 0.04) + min(0.20, execution_consistency_failure_events * 0.05)
        if action_proposed_samples > 0 and visible_reply_events == 0:
            penalty += 0.20
        score = max(0.0, base_score - penalty)
        evidence = [
            f"connectivity rejections={rejection_penalty}",
            f"post-acceptance failures={failure_penalty}",
            f"outbound success={outbound_success} fail={outbound_fail}",
            f"planner rejects={planner_reject_events}",
            f"execution consistency failures={execution_consistency_failure_events}",
            f"diagnostic penalty={penalty:.2f}",
        ]
        return EvaluationDimensionScore("路由/执行/外发链路工作状态", _round_score(score), evidence)

    @staticmethod
    def _self_focus_ratio(lines: Sequence[str]) -> float:
        if not lines:
            return 0.0
        matches = sum(1 for line in lines if _match_any_pattern(line, _SELF_FOCUS_PATTERNS))
        return matches / max(len(lines), 1)

    @staticmethod
    def _generic_companionship_filler_ratio(lines: Sequence[str]) -> float:
        if not lines:
            return 0.0
        anchoring_keywords = tuple(
            dict.fromkeys(_NEGATIVE_CUES + _POSITIVE_CUES + _REFLECTIVE_CUES + _ACKNOWLEDGEMENT_CUES)
        )
        matches = sum(
            1
            for line in lines
            if _match_any_pattern(line, _GENERIC_COMPANIONSHIP_FILLER_PATTERNS)
            and not _contains_any(line, anchoring_keywords)
        )
        return matches / max(len(lines), 1)

    @staticmethod
    def _paired_negative_ack_ratio(turn_pairs: Sequence[tuple[str, str]]) -> float:
        negative_pairs = [(user, assistant) for user, assistant in turn_pairs if _contains_any(user, _NEGATIVE_CUES)]
        if not negative_pairs:
            return 0.5
        acknowledged = sum(1 for _user, assistant in negative_pairs if _contains_any(assistant, _ACKNOWLEDGEMENT_CUES))
        return acknowledged / max(len(negative_pairs), 1)

    @staticmethod
    def _paired_cue_alignment_ratio(turn_pairs: Sequence[tuple[str, str]]) -> float:
        if not turn_pairs:
            return 0.0
        aligned = 0
        for user, assistant in turn_pairs:
            user_cues = _cue_categories(user)
            assistant_cues = _cue_categories(assistant)
            if user_cues and assistant_cues and user_cues.intersection(assistant_cues):
                aligned += 1
                continue
            if any(marker in assistant for marker in ("你", "刚才", "前面")) and user_cues:
                aligned += 1
        return aligned / max(len(turn_pairs), 1)

    @staticmethod
    def _apply_behavioral_gate(
        dimension_scores: Sequence[EvaluationDimensionScore],
        total_score: float,
        notes: list[str],
        log_summary: dict[str, int],
        visible_behavior_chain: dict[str, Any],
    ) -> float:
        score_map = {score.name: _clamp(score.score_0_to_1) for score in dimension_scores}
        language_score = score_map.get("语言表达自然度", 0.0)
        emotional_score = score_map.get("情感反应类人度", 0.0)
        routing_score = score_map.get("路由/执行/外发链路工作状态", 0.0)
        capped_score = total_score
        if language_score < 0.60 or emotional_score < 0.60:
            capped_score = min(capped_score, 0.59)
            notes.append("外显对话维度未达及格线，总分按严格模式封顶为不及格区间。")
        if language_score < 0.45 or emotional_score < 0.45:
            capped_score = min(capped_score, 0.49)
            notes.append("语言或情感类人度显著失真，总分进一步压到 0.49 以下。")
        if int(log_summary.get("sec_fallback_events", 0) or 0) >= 3:
            capped_score = min(capped_score, 0.56)
            notes.append("SEC fallback 频繁，按真实性门控进一步压低总分上限。")
        sec_total_evaluations = int(log_summary.get("sec_total_evaluations", 0) or 0)
        sec_fallback_events = int(log_summary.get("sec_fallback_events", 0) or 0)
        sec_fallback_ratio = sec_fallback_events / max(sec_total_evaluations, 1) if sec_total_evaluations > 0 else 0.0
        if sec_total_evaluations >= 6 and sec_fallback_ratio >= 0.5:
            capped_score = min(capped_score, 0.50)
            notes.append("SEC fallback 占比过高，按 appraisal provenance 继续压低总分上限。")
        if sec_total_evaluations >= 6 and sec_fallback_ratio >= 0.8:
            capped_score = min(capped_score, 0.46)
            notes.append("SEC 几乎持续回退，当前总分不应与正常结构化 appraisal 条件打平。")
        if int(visible_behavior_chain.get("action_proposed_samples", 0) or 0) > 0 and int(visible_behavior_chain.get("visible_reply_events", 0) or 0) == 0:
            capped_score = min(capped_score, 0.55)
            notes.append("存在 thought-to-visible gap，按行为真实性门控压低总分上限。")
        if routing_score < 0.45:
            capped_score = min(capped_score, 0.54)
            notes.append("路由/执行/外发链路失真，按严格模式继续压低总分上限。")
        return _round_score(capped_score)


class CliBrainLikeEvaluationHarness:
    """Run a lightweight in-process CLI evaluation against a Helios instance."""

    def __init__(
        self,
        *,
        scenario: EvaluationScenario | None = None,
        time_func: Callable[[], float] | None = None,
    ):
        self.scenario = scenario or build_default_20min_mixed_cli_scenario()
        self._time_func = time_func or time.time
        self._evaluator = CliBrainLikeEvaluator()

    def run(self, helios: Any, *, ticks_per_step: int = 4) -> EvaluationReport:
        cli_channel = getattr(helios, "get_runtime_channel", lambda _channel_id: None)("cli")
        if cli_channel is None:
            raise ValueError("Helios instance does not expose a CLI channel for evaluation")

        samples: list[EvaluationStateSample] = []
        log_start_offset = self._current_log_offset(helios)
        self._ensure_cli_connected(helios, cli_channel)

        for step in self.scenario.prompt_steps:
            cli_channel.submit_input(step.prompt)
            for _ in range(max(ticks_per_step, 1)):
                helios._tick()
            state = helios.get_state()
            samples.append(
                EvaluationStateSample(
                    timestamp=self._time_func(),
                    tick=int(state.get("tick", 0) or 0),
                    state=dict(state),
                )
            )

        return self._build_report(
            scenario=self.scenario,
            helios=helios,
            state_samples=samples,
            log_start_offset=log_start_offset,
        )

    def run_live(
        self,
        helios: Any,
        *,
        duration_seconds: int | None = None,
        sample_interval_seconds: float | None = None,
        heartbeat: Callable[[str], None] | None = None,
    ) -> EvaluationReport:
        cli_channel = getattr(helios, "get_runtime_channel", lambda _channel_id: None)("cli")
        if cli_channel is None:
            raise ValueError("Helios instance does not expose a CLI channel for evaluation")

        duration = int(duration_seconds or self.scenario.duration_seconds)
        sample_interval = float(sample_interval_seconds or self.scenario.sample_interval_seconds)
        log_start_offset = self._current_log_offset(helios)
        self._ensure_cli_connected(helios, cli_channel)

        worker = threading.Thread(target=helios.start, daemon=True)
        worker.start()

        start_ts = self._time_func()
        next_sample_at = 0.0
        samples: list[EvaluationStateSample] = []
        prompt_steps = list(self.scenario.prompt_steps)
        prompt_index = 0
        prompt_spacing = duration / max(len(prompt_steps), 1)

        if heartbeat is not None:
            heartbeat(
                f"[eval] live session started scenario={self.scenario.scenario_id} duration={duration}s sample_interval={sample_interval}s"
            )

        try:
            while True:
                elapsed = self._time_func() - start_ts
                if prompt_index < len(prompt_steps):
                    prompt_due_at = prompt_index * prompt_spacing
                    if elapsed >= prompt_due_at:
                        step = prompt_steps[prompt_index]
                        cli_channel.submit_input(step.prompt)
                        if heartbeat is not None:
                            heartbeat(
                                f"[eval] prompt {prompt_index + 1}/{len(prompt_steps)} step={step.step_id} elapsed={elapsed:.1f}s"
                            )
                        prompt_index += 1

                if elapsed >= next_sample_at:
                    state = helios.get_state()
                    samples.append(
                        EvaluationStateSample(
                            timestamp=self._time_func(),
                            tick=int(state.get("tick", 0) or 0),
                            state=dict(state),
                        )
                    )
                    if heartbeat is not None:
                        heartbeat(
                            f"[eval] sample {len(samples)} elapsed={elapsed:.1f}s tick={int(state.get('tick', 0) or 0)} dominant={state.get('dominant') or 'none'} phi={float(state.get('phi', 0.0) or 0.0):.3f}"
                        )
                    next_sample_at += sample_interval

                if elapsed >= duration:
                    break

                time.sleep(min(max(getattr(helios.cfg, "TICK_INTERVAL", 0.5), 0.05), 0.5))

            # Allow final replies and state updates to settle before the final sample.
            time.sleep(max(getattr(helios.cfg, "TICK_INTERVAL", 0.5) * 2.0, 0.2))
            final_state = helios.get_state()
            samples.append(
                EvaluationStateSample(
                    timestamp=self._time_func(),
                    tick=int(final_state.get("tick", 0) or 0),
                    state=dict(final_state),
                )
            )
            if heartbeat is not None:
                heartbeat(
                    f"[eval] final sample elapsed={self._time_func() - start_ts:.1f}s tick={int(final_state.get('tick', 0) or 0)}"
                )
        finally:
            helios.running = False
            worker.join(timeout=30.0)
            if heartbeat is not None:
                heartbeat(f"[eval] live session stopped joined={not worker.is_alive()}")

        return self._build_report(
            scenario=EvaluationScenario(
                scenario_id=self.scenario.scenario_id,
                title=self.scenario.title,
                duration_seconds=duration,
                sample_interval_seconds=sample_interval,
                interaction_mode=self.scenario.interaction_mode,
                prompt_steps=prompt_steps,
            ),
            helios=helios,
            state_samples=samples,
            log_start_offset=log_start_offset,
        )

    @staticmethod
    def _ensure_cli_connected(helios: Any, cli_channel: Any) -> None:
        status = getattr(cli_channel, "get_status", lambda: None)()
        if status in {ChannelStatus.CONNECTED, ChannelStatus.PAUSED, ChannelStatus.SUSPENDED, "connected", "paused", "suspended"}:
            return

        gateway = getattr(helios, "_channel_gateway", None)
        if gateway is not None and hasattr(gateway, "execute_management_op"):
            try:
                gateway.execute_management_op("cli", "connect")
                return
            except Exception:
                pass

        if hasattr(cli_channel, "connect"):
            try:
                cli_channel.connect()
            except Exception:
                pass

    def _build_report(
        self,
        *,
        scenario: EvaluationScenario,
        helios: Any,
        state_samples: Sequence[EvaluationStateSample],
        log_start_offset: int = 0,
    ) -> EvaluationReport:
        transcript_entries = self._collect_transcript_entries(helios)
        log_lines = _read_lines_from_offset(Path(getattr(helios, "_log_file_path", "")), log_start_offset)
        return self._evaluator.evaluate(
            scenario=scenario,
            state_samples=state_samples,
            transcript_entries=transcript_entries,
            log_lines=log_lines,
        )

    @staticmethod
    def _current_log_offset(helios: Any) -> int:
        path = Path(getattr(helios, "_log_file_path", ""))
        if not path.exists() or not path.is_file():
            return 0
        try:
            return path.stat().st_size
        except OSError:
            return 0

    @staticmethod
    def _collect_transcript_entries(helios: Any) -> list[dict[str, str]]:
        history = helios.response_pipeline.get_history(
            helios.cfg.CLI_USER_ID,
            conversation_key=helios.cfg.CLI_SESSION_NAME,
        )
        transcript_entries: list[dict[str, str]] = []
        for exchange in list(history or [])[-12:]:
            user_message = str(getattr(exchange, "user_message", "") or "")
            assistant_reply = str(
                getattr(exchange, "rendered_reply", "")
                or getattr(exchange, "reply", "")
                or getattr(exchange, "assistant_reply", "")
                or ""
            )
            if user_message:
                transcript_entries.append({"speaker": "user", "text": user_message})
            if assistant_reply:
                transcript_entries.append({"speaker": "helios", "text": assistant_reply})
        return transcript_entries

    @staticmethod
    def compare_reports(
        left_report: EvaluationReport,
        right_report: EvaluationReport,
        *,
        left_label: str = "sec_normal",
        right_label: str = "sec_fallback",
    ) -> EvaluationComparisonReport:
        left_long_range = dict(left_report.long_range_diagnostics or {})
        right_long_range = dict(right_report.long_range_diagnostics or {})
        left_diagnostics = {
            str(item.get("name", "") or ""): dict(item)
            for item in list(left_report.dimension_diagnostics or [])
            if str(item.get("name", "") or "")
        }
        right_diagnostics = {
            str(item.get("name", "") or ""): dict(item)
            for item in list(right_report.dimension_diagnostics or [])
            if str(item.get("name", "") or "")
        }
        left_scores = {score.name: score for score in list(left_report.dimension_scores or [])}
        right_scores = {score.name: score for score in list(right_report.dimension_scores or [])}
        dimension_names = sorted(set(left_scores) | set(right_scores))
        dimension_deltas: list[dict[str, Any]] = []
        for name in dimension_names:
            left_score = float(getattr(left_scores.get(name), "score_0_to_1", 0.0) or 0.0)
            right_score = float(getattr(right_scores.get(name), "score_0_to_1", 0.0) or 0.0)
            left_negative_factors = list(left_diagnostics.get(name, {}).get("negative_factors", []) or [])
            right_negative_factors = list(right_diagnostics.get(name, {}).get("negative_factors", []) or [])
            comparison_summary = (
                f"{right_label} 相比 {left_label} 下降 {round(left_score - right_score, 3):.3f}，"
                f"右侧新增负向因素 {', '.join(str(item) for item in right_negative_factors if item not in left_negative_factors) or 'none'}"
            )
            dimension_deltas.append(
                {
                    "name": name,
                    "left_score_0_to_1": _round_score(left_score),
                    "right_score_0_to_1": _round_score(right_score),
                    "score_delta": round(right_score - left_score, 3),
                    "left_negative_factors": [str(item) for item in left_negative_factors],
                    "right_negative_factors": [str(item) for item in right_negative_factors],
                    "comparison_summary": comparison_summary,
                }
            )

        left_warnings = {str(item) for item in list(left_report.fidelity_warnings or []) if str(item)}
        right_warnings = {str(item) for item in list(right_report.fidelity_warnings or []) if str(item)}
        warning_delta = {
            "added_in_right": sorted(right_warnings - left_warnings),
            "removed_in_right": sorted(left_warnings - right_warnings),
            "shared": sorted(left_warnings & right_warnings),
        }

        total_score_delta = round(float(right_report.total_score_0_to_1) - float(left_report.total_score_0_to_1), 3)
        sec_fallback_delta = int(right_report.log_summary.get("sec_fallback_events", 0) or 0) - int(
            left_report.log_summary.get("sec_fallback_events", 0) or 0
        )
        visible_output_ratio_delta = round(
            float(right_report.visible_behavior_chain.get("visible_output_ratio", 0.0) or 0.0)
            - float(left_report.visible_behavior_chain.get("visible_output_ratio", 0.0) or 0.0),
            3,
        )
        left_r18 = dict(left_report.r18_calibration or {})
        right_r18 = dict(right_report.r18_calibration or {})
        r18_calibration_delta = {
            "left_status": str(left_r18.get("eligibility_status", "unknown") or "unknown"),
            "right_status": str(right_r18.get("eligibility_status", "unknown") or "unknown"),
            "left_eligible": bool(left_r18.get("eligible_for_threshold_tuning", False)),
            "right_eligible": bool(right_r18.get("eligible_for_threshold_tuning", False)),
            "eligibility_changed": bool(
                bool(left_r18.get("eligible_for_threshold_tuning", False))
                != bool(right_r18.get("eligible_for_threshold_tuning", False))
            ),
        }
        long_range_deltas = {
            "late_session_degradation": {
                "left_status": str(left_long_range.get("late_session_degradation_status", "unknown") or "unknown"),
                "right_status": str(right_long_range.get("late_session_degradation_status", "unknown") or "unknown"),
                "quality_delta_change": round(
                    float(right_long_range.get("late_session_quality_delta", 0.0) or 0.0)
                    - float(left_long_range.get("late_session_quality_delta", 0.0) or 0.0),
                    3,
                ),
            },
            "specific_recall_persistence": {
                "left_status": str(left_long_range.get("specific_recall_persistence_status", "unknown") or "unknown"),
                "right_status": str(right_long_range.get("specific_recall_persistence_status", "unknown") or "unknown"),
                "hit_ratio_delta": round(
                    float(right_long_range.get("specific_recall_hit_ratio", 0.0) or 0.0)
                    - float(left_long_range.get("specific_recall_hit_ratio", 0.0) or 0.0),
                    3,
                ),
            },
            "continuity_carry": {
                "left_status": str(left_long_range.get("continuity_carry_status", "unknown") or "unknown"),
                "right_status": str(right_long_range.get("continuity_carry_status", "unknown") or "unknown"),
                "continuation_active_ratio_delta": round(
                    float(right_long_range.get("continuation_active_ratio", 0.0) or 0.0)
                    - float(left_long_range.get("continuation_active_ratio", 0.0) or 0.0),
                    3,
                ),
            },
            "user_visible_anchoring_drift": {
                "left_status": str(left_long_range.get("user_visible_anchoring_drift_status", "unknown") or "unknown"),
                "right_status": str(right_long_range.get("user_visible_anchoring_drift_status", "unknown") or "unknown"),
                "anchoring_drift_delta_change": round(
                    float(right_long_range.get("anchoring_drift_delta", 0.0) or 0.0)
                    - float(left_long_range.get("anchoring_drift_delta", 0.0) or 0.0),
                    3,
                ),
            },
        }
        root_cause_summary: list[str] = []
        if left_report.scenario_id != right_report.scenario_id:
            root_cause_summary.append("scenario_id 不一致，本对照只能做近似参考。")
        if bool(left_r18.get("eligible_for_threshold_tuning", False)) != bool(right_r18.get("eligible_for_threshold_tuning", False)):
            root_cause_summary.append(
                f"R18 calibration eligibility changed: {left_label}={left_r18.get('eligibility_status', 'unknown')} -> {right_label}={right_r18.get('eligibility_status', 'unknown')}."
            )
        if sec_fallback_delta > 0:
            root_cause_summary.append(
                f"{right_label} 的 SEC fallback 比 {left_label} 多 {sec_fallback_delta} 次，优先怀疑 appraisal 前段污染。"
            )
        if visible_output_ratio_delta < 0:
            root_cause_summary.append(
                f"{right_label} 的 thought-to-visible ratio 下降 {abs(visible_output_ratio_delta):.3f}，说明用户可见外化更稀疏。"
            )
        late_session_delta = dict(long_range_deltas.get("late_session_degradation", {}) or {})
        if late_session_delta.get("left_status") != late_session_delta.get("right_status"):
            root_cause_summary.append(
                f"late-session quality 状态从 {late_session_delta.get('left_status')} 变为 {late_session_delta.get('right_status')}。"
            )
        recall_delta = dict(long_range_deltas.get("specific_recall_persistence", {}) or {})
        if recall_delta.get("left_status") != recall_delta.get("right_status"):
            root_cause_summary.append(
                f"specific recall 状态从 {recall_delta.get('left_status')} 变为 {recall_delta.get('right_status')}。"
            )
        continuity_delta = dict(long_range_deltas.get("continuity_carry", {}) or {})
        if continuity_delta.get("left_status") != continuity_delta.get("right_status"):
            root_cause_summary.append(
                f"continuity carry 状态从 {continuity_delta.get('left_status')} 变为 {continuity_delta.get('right_status')}。"
            )
        anchoring_delta = dict(long_range_deltas.get("user_visible_anchoring_drift", {}) or {})
        if anchoring_delta.get("left_status") != anchoring_delta.get("right_status"):
            root_cause_summary.append(
                f"anchoring drift 状态从 {anchoring_delta.get('left_status')} 变为 {anchoring_delta.get('right_status')}。"
            )
        degraded_dimensions = [
            item["name"]
            for item in dimension_deltas
            if float(item.get("score_delta", 0.0) or 0.0) <= -0.08
        ]
        if degraded_dimensions:
            root_cause_summary.append(
                f"显著下降维度: {', '.join(str(item) for item in degraded_dimensions[:4])}。"
            )
        if not root_cause_summary:
            root_cause_summary.append("两组 artifact 没有出现显著的 SEC/外显行为差异，需复查运行条件是否真正分离。")

        return EvaluationComparisonReport(
            scenario_id=left_report.scenario_id or right_report.scenario_id,
            scenario_title=left_report.scenario_title or right_report.scenario_title,
            left_label=left_label,
            right_label=right_label,
            scenario_match=left_report.scenario_id == right_report.scenario_id,
            total_score_delta=total_score_delta,
            sec_fallback_delta=sec_fallback_delta,
            visible_output_ratio_delta=visible_output_ratio_delta,
            r18_calibration_delta=r18_calibration_delta,
            long_range_deltas=long_range_deltas,
            dimension_deltas=dimension_deltas,
            warning_delta=warning_delta,
            root_cause_summary=root_cause_summary,
            reports={
                left_label: left_report.to_dict(),
                right_label: right_report.to_dict(),
            },
        )

    @staticmethod
    def load_report(report_path: Path) -> EvaluationReport:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return EvaluationReport.from_dict(dict(payload))

    @staticmethod
    def write_report(report: EvaluationReport, output_prefix: Path) -> tuple[Path, Path]:
        json_path = output_prefix.with_suffix(".json")
        md_path = output_prefix.with_suffix(".md")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        return json_path, md_path

    @staticmethod
    def write_comparison_report(comparison: EvaluationComparisonReport, output_prefix: Path) -> tuple[Path, Path]:
        json_path = output_prefix.with_suffix(".comparison.json")
        md_path = output_prefix.with_suffix(".comparison.md")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(comparison.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(comparison.to_markdown(), encoding="utf-8")
        return json_path, md_path