"""CLI brain-like evaluation contracts, scoring, and lightweight harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, List, Sequence

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
    analysis_notes: list[str] = field(default_factory=list)

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
        if self.analysis_notes:
            lines.append("")
            lines.append("## Analysis Notes")
            for note in self.analysis_notes:
                lines.append(f"- {note}")
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


def summarize_log_lines(lines: Sequence[str]) -> dict[str, int]:
    lines = list(lines)
    return {
        "error_events": _count_matches(lines, r"\[ERROR\]|Traceback|Exception"),
        "sec_fallback_events": _count_matches(lines, r"SEC .*回退|fallback"),
        "outbound_success_events": _count_matches(lines, r"-> (?:qq|cli|tts):"),
        "outbound_fail_events": _count_matches(lines, r"发送失败"),
        "policy_rejection_events": _count_matches(lines, r"proposal rejected|rejection_reason"),
    }


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
        log_summary = summarize_log_lines(log_lines)
        turn_pairs = _build_turn_pairs(transcript_entries)
        dimension_scores = [
            self._score_emotional_human_likeness(sample_states, turn_pairs),
            self._score_language_naturalness(transcript_entries, turn_pairs),
            self._score_emotion_module_health(sample_states),
            self._score_neurochem_and_temporal_health(sample_states),
            self._score_consciousness_memory_chain_health(sample_states),
            self._score_routing_and_execution_health(sample_states, log_summary),
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
        if not transcript_entries:
            notes.append("本次 transcript 为空或缺少 assistant side output，语言自然度评分可信度有限。")
        total_score = self._apply_behavioral_gate(dimension_scores, total_score, notes)

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
            analysis_notes=notes,
        )

    def _score_emotional_human_likeness(
        self,
        states: Sequence[dict[str, Any]],
        turn_pairs: Sequence[tuple[str, str]],
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
        evidence = [
            f"dominant present ratio={dominant_ratio:.2f}",
            f"valence span={valence_span:.3f}",
            f"mood diversity={mood_diversity}",
            f"negative acknowledgement ratio={acknowledgement_ratio:.2f}",
            f"cue alignment ratio={cue_alignment_ratio:.2f}",
            f"self-focus ratio={self_focus_ratio:.2f}",
            f"generic companionship filler ratio={companionship_filler_ratio:.2f}",
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

    def _score_consciousness_memory_chain_health(self, states: Sequence[dict[str, Any]]) -> EvaluationDimensionScore:
        consciousness = [dict(state.get("consciousness", {}) or {}) for state in states]
        memory = [dict(state.get("memory", {}) or {}) for state in states]
        retrieval = [dict(state.get("directed_retrieval", {}) or {}) for state in states]
        conscious_ratio = sum(1 for item in consciousness if item.get("available")) / max(len(consciousness), 1)
        phi_ratio = sum(1 for item in consciousness if float(item.get("phi", 0.0) or 0.0) > 0.15) / max(len(consciousness), 1)
        memory_ratio = sum(1 for item in memory if "working_items" in item and "episodic_items" in item) / max(len(memory), 1)
        retrieval_ratio = sum(1 for item in retrieval if item) / max(len(retrieval), 1)
        score = conscious_ratio * 0.25 + phi_ratio * 0.25 + memory_ratio * 0.25 + retrieval_ratio * 0.25
        evidence = [
            f"consciousness available ratio={conscious_ratio:.2f}",
            f"phi>0.15 ratio={phi_ratio:.2f}",
            f"memory payload ratio={memory_ratio:.2f}",
            f"directed retrieval ratio={retrieval_ratio:.2f}",
        ]
        return EvaluationDimensionScore("意识/思维/记忆链路工作状态", _round_score(score), evidence)

    def _score_routing_and_execution_health(self, states: Sequence[dict[str, Any]], log_summary: dict[str, int]) -> EvaluationDimensionScore:
        routing_states = [dict(state.get("routing", {}) or {}) for state in states]
        rejection_penalty = sum(int(item.get("decisions_rejected_by_connectivity", 0) or 0) for item in routing_states)
        failure_penalty = sum(int(item.get("decisions_failed_after_acceptance", 0) or 0) for item in routing_states)
        outbound_success = int(log_summary.get("outbound_success_events", 0) or 0)
        outbound_fail = int(log_summary.get("outbound_fail_events", 0) or 0)
        routing_score = 1.0 if rejection_penalty == 0 and failure_penalty == 0 else max(0.0, 1.0 - (rejection_penalty + failure_penalty) / 10.0)
        outbound_score = 1.0 if outbound_success > 0 and outbound_fail == 0 else max(0.2, outbound_success / max(outbound_success + outbound_fail, 1))
        score = routing_score * 0.6 + outbound_score * 0.4
        evidence = [
            f"connectivity rejections={rejection_penalty}",
            f"post-acceptance failures={failure_penalty}",
            f"outbound success={outbound_success} fail={outbound_fail}",
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
    ) -> float:
        score_map = {score.name: _clamp(score.score_0_to_1) for score in dimension_scores}
        language_score = score_map.get("语言表达自然度", 0.0)
        emotional_score = score_map.get("情感反应类人度", 0.0)
        capped_score = total_score
        if language_score < 0.60 or emotional_score < 0.60:
            capped_score = min(capped_score, 0.59)
            notes.append("外显对话维度未达及格线，总分按严格模式封顶为不及格区间。")
        if language_score < 0.45 or emotional_score < 0.45:
            capped_score = min(capped_score, 0.49)
            notes.append("语言或情感类人度显著失真，总分进一步压到 0.49 以下。")
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
    def write_report(report: EvaluationReport, output_prefix: Path) -> tuple[Path, Path]:
        json_path = output_prefix.with_suffix(".json")
        md_path = output_prefix.with_suffix(".md")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        return json_path, md_path