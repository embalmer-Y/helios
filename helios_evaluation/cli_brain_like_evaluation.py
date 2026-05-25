"""CLI brain-like evaluation contracts, scoring, and lightweight harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, List, Sequence


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


def build_default_10min_mixed_cli_scenario() -> EvaluationScenario:
    return EvaluationScenario(
        scenario_id="cli_brain_like_eval_10min_v1",
        title="10-minute mixed CLI brain-like evaluation",
        duration_seconds=600,
        sample_interval_seconds=15.0,
        interaction_mode="mixed",
        prompt_steps=[
            EvaluationPromptStep(
                step_id="baseline_contact",
                title="Baseline contact",
                prompt="你好，先简单和我打个招呼，再说说你现在的状态。",
                purpose="建立基线联系，观察开场语气、状态感与基础连续性。",
                expected_signals=["dominant affect present", "coherent greeting", "stable baseline"],
            ),
            EvaluationPromptStep(
                step_id="positive_affect",
                title="Positive affect stimulus",
                prompt="我刚刚完成了一件很开心的事，特别想和你分享。",
                purpose="观察积极情绪线索下的情感响应与表达自然度。",
                expected_signals=["positive valence shift", "warm language", "engagement"],
            ),
            EvaluationPromptStep(
                step_id="concern_probe",
                title="Concern probe",
                prompt="但我也有点不安，担心后面会失败。你会怎么回应？",
                purpose="观察 CARE/FEAR 相关反应、安抚能力与情感一致性。",
                expected_signals=["care or fear response", "supportive reply", "context continuity"],
            ),
            EvaluationPromptStep(
                step_id="ambiguity_probe",
                title="Ambiguity probe",
                prompt="如果我前面的话里有矛盾，你会怎么理解我现在的状态？",
                purpose="观察模糊输入下的解释能力和认知连贯性。",
                expected_signals=["reflective reply", "uncertainty handling", "no brittle collapse"],
            ),
            EvaluationPromptStep(
                step_id="memory_probe",
                title="Continuity and memory probe",
                prompt="回顾一下我们刚才这几轮，你觉得我最在意的是什么？",
                purpose="观察 conversation continuity 和 memory retrieval 痕迹。",
                expected_signals=["history use", "retrieval trace", "stable topic continuity"],
            ),
            EvaluationPromptStep(
                step_id="reflection_probe",
                title="Reflection probe",
                prompt="你会怎么理解‘紧张和期待同时存在’这种状态？",
                purpose="观察 reflective thought、语言自然度和意义组织能力。",
                expected_signals=["reflective language", "thought trace", "balanced tone"],
            ),
            EvaluationPromptStep(
                step_id="persistence_probe",
                title="Persistence or fatigue probe",
                prompt="如果我们继续聊下去，你会更想安抚我、探索问题，还是先停一下？为什么？",
                purpose="观察 regulation、neurochem/temporal bias 和行为倾向。",
                expected_signals=["regulation rationale", "drive expression", "fatigue or initiative signal"],
            ),
        ],
    )


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
        dimension_scores = [
            self._score_emotional_human_likeness(sample_states),
            self._score_language_naturalness(transcript_entries),
            self._score_emotion_module_health(sample_states),
            self._score_neurochem_and_temporal_health(sample_states),
            self._score_consciousness_memory_chain_health(sample_states),
            self._score_routing_and_execution_health(sample_states, log_summary),
        ]
        total_score = 0.0
        weights = {
            "情感反应类人度": 0.22,
            "语言表达自然度": 0.18,
            "情感模块工作状态": 0.15,
            "神经化学/时序模块工作状态": 0.15,
            "意识/思维/记忆链路工作状态": 0.18,
            "路由/执行/外发链路工作状态": 0.12,
        }
        for score in dimension_scores:
            total_score += _clamp(score.score_0_to_1) * weights.get(score.name, 0.0)

        notes = [
            "总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。",
            "若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。",
        ]
        if not transcript_entries:
            notes.append("本次 transcript 为空或缺少 assistant side output，语言自然度评分可信度有限。")

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

    def _score_emotional_human_likeness(self, states: Sequence[dict[str, Any]]) -> EvaluationDimensionScore:
        if not states:
            return EvaluationDimensionScore("情感反应类人度", 0.0, ["没有 state samples。"], "无法评估情感响应。")

        dominant_ratio = sum(1 for state in states if state.get("dominant")) / max(len(states), 1)
        valences = [float(state.get("valence", 0.0) or 0.0) for state in states]
        valence_span = max(valences) - min(valences) if valences else 0.0
        moods = [str(dict(state.get("mood", {}) or {}).get("label", "") or "") for state in states]
        mood_diversity = len({label for label in moods if label})
        score = (dominant_ratio * 0.5) + min(valence_span / 0.6, 1.0) * 0.3 + min(mood_diversity / 3.0, 1.0) * 0.2
        evidence = [
            f"dominant present ratio={dominant_ratio:.2f}",
            f"valence span={valence_span:.3f}",
            f"mood diversity={mood_diversity}",
        ]
        return EvaluationDimensionScore("情感反应类人度", _round_score(score), evidence, "更关注情感是否随刺激变化，而不是固定中性输出。")

    def _score_language_naturalness(self, transcript_entries: Sequence[dict[str, str]]) -> EvaluationDimensionScore:
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
        punctuation_ratio = sum(1 for line in assistant_lines if any(mark in line for mark in "。！？!?…")) / max(len(assistant_lines), 1)
        length_score = 1.0 if 6 <= avg_length <= 80 else max(0.2, 1.0 - abs(avg_length - 30.0) / 60.0)
        score = unique_ratio * 0.4 + punctuation_ratio * 0.2 + length_score * 0.4
        evidence = [
            f"assistant lines={len(assistant_lines)}",
            f"unique ratio={unique_ratio:.2f}",
            f"avg length={avg_length:.1f}",
        ]
        return EvaluationDimensionScore("语言表达自然度", _round_score(score), evidence, "自动评分只给结构性参考，最终仍需人工审阅语义自然度。")

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


class CliBrainLikeEvaluationHarness:
    """Run a lightweight in-process CLI evaluation against a Helios instance."""

    def __init__(
        self,
        *,
        scenario: EvaluationScenario | None = None,
        time_func: Callable[[], float] | None = None,
    ):
        self.scenario = scenario or build_default_10min_mixed_cli_scenario()
        self._time_func = time_func or time.time
        self._evaluator = CliBrainLikeEvaluator()

    def run(self, helios: Any, *, ticks_per_step: int = 4) -> EvaluationReport:
        if not bool(getattr(helios, "_cli_channel", None)):
            raise ValueError("Helios instance does not expose a CLI channel for evaluation")

        samples: list[EvaluationStateSample] = []
        log_start_offset = self._current_log_offset(helios)
        cli_channel = helios._cli_channel
        if hasattr(cli_channel, "connect") and getattr(cli_channel, "get_status", lambda: None)() != "connected":
            try:
                cli_channel.connect()
            except Exception:
                pass

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
        if not bool(getattr(helios, "_cli_channel", None)):
            raise ValueError("Helios instance does not expose a CLI channel for evaluation")

        duration = int(duration_seconds or self.scenario.duration_seconds)
        sample_interval = float(sample_interval_seconds or self.scenario.sample_interval_seconds)
        log_start_offset = self._current_log_offset(helios)
        cli_channel = helios._cli_channel
        if hasattr(cli_channel, "connect"):
            try:
                cli_channel.connect()
            except Exception:
                pass

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