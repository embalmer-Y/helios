"""Integration layer for internal thought generation."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from core.helios_state import HeliosState
from helios_io.prompt_contract import PromptContractBuilder
from personality_projection import resolve_personality_projection

from .thinking import ThinkingManager, ThoughtFragment


log = logging.getLogger("helios.cognition.thinking_integration")


THOUGHT_TYPES = [
    "episodic_fragment",
    "counterfactual",
    "future_projection",
    "self_question",
    "free_association",
    "rumination",
]

EMOTION_THOUGHT_BIAS = {
    "PANIC": ["rumination", "future_projection"],
    "FEAR": ["rumination", "future_projection"],
    "SEEKING": ["free_association", "self_question"],
    "PLAY": ["free_association", "episodic_fragment"],
    "CARE": ["episodic_fragment", "future_projection"],
    "RAGE": ["counterfactual", "rumination"],
    "LUST": ["future_projection", "free_association"],
}


@dataclass
class Thought:
    type: str
    content: str
    timestamp: float
    triggered_by: str
    raw_content: str = ""
    source_path: str = "internal_thought_llm"
    llm_used: bool = False
    fallback_used: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class InternalThoughtTrigger:
    dmn_active: bool
    icri_value: float
    temperature_or_temporal_summary: str
    load_pressure: float
    cooldown_remaining: float
    trigger_reason: str
    triggered: bool
    gate_score: float = 0.0
    dominant_reason: str = ""
    blocked_reasons: tuple[str, ...] = ()
    contributing_signals: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class InternalThoughtContext:
    thought_type: str
    trigger_reason: str
    icri: float
    dmn_state: str
    temporal_summary: str
    recent_state_digest: str
    resource_pressure_summary: str
    directed_memory_summary: str = ""


@dataclass(frozen=True)
class InternalThoughtResult:
    raw_text: str
    clean_text: str
    accepted: bool
    rejected_reason: str
    source_path: str
    memory_write_enabled: bool
    fallback_used: bool
    llm_used: bool
    prompt_contract_snapshot: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ThoughtContinuationPlan:
    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    continuation_pressure_delta: float
    next_continuation_pressure: float
    recall_intent: str


@dataclass(frozen=True)
class InternalThoughtTrace:
    triggered: bool
    trigger_reason: str
    llm_used: bool
    fallback_used: bool
    output_destination: str
    write_result: str
    sufficiency_level: float = 0.0
    continuation_requested: bool = False
    continuation_reason: str = ""
    continuation_pressure: float = 0.0
    recall_intent: str = ""
    rejected_reason: str = ""


class ThinkingEngineIntegration:
    GENERATION_INTERVAL = 5.0
    COOLDOWN_PER_TYPE = 30.0
    ICRI_THRESHOLD = 0.10
    MAX_RESOURCE_PRESSURE = 0.85

    def __init__(
        self,
        thinking_engine: Optional[ThinkingManager],
        autobio_store,
        on_thought_recorded: Optional[Callable[[Thought, HeliosState, object], None]] = None,
        *,
        internal_think_enabled: bool = True,
        llm_enabled: bool = False,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        memory_write_enabled: bool = True,
        llm_client=None,
    ):
        self._engine = thinking_engine or ThinkingManager()
        self._autobio = autobio_store
        self._on_thought_recorded = on_thought_recorded
        self._last_generation = 0.0
        self._type_cooldowns: dict[str, float] = {}
        self.internal_think_enabled = internal_think_enabled
        self.llm_enabled = llm_enabled
        self.api_key = api_key or os.getenv("HELIOS_LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.base_url = base_url or os.getenv("HELIOS_LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        self.model = model or os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        self.memory_write_enabled = memory_write_enabled
        self._client = llm_client
        self._prompt_contract_builder = PromptContractBuilder()

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def should_generate(self, icri: float, dmn_active: bool, now: float) -> bool:
        if icri < self.ICRI_THRESHOLD:
            return False
        if not dmn_active:
            return False
        if (now - self._last_generation) < self.GENERATION_INTERVAL:
            return False
        return True

    def evaluate_trigger(self, state: HeliosState, now: Optional[float] = None) -> InternalThoughtTrigger:
        current_time = time.time() if now is None else now
        dmn_active = self._determine_dmn_activity(state)
        load_pressure = max(
            self._coerce_scalar(getattr(state, "allostatic_load", 0.0)),
            self._coerce_scalar(getattr(state, "fatigue_pressure", 0.0)),
            min(float(getattr(state, "behavior_queue_depth", 0) or 0), 1.0),
        )
        cooldown_remaining = max(0.0, self.GENERATION_INTERVAL - (current_time - self._last_generation))
        temporal_summary = self._build_temporal_summary(state)
        current_stimuli = list(getattr(state, "current_stimuli", []) or [])
        stimulus_score = max(
            [self._coerce_scalar(stimulus.get("stimulus_intensity", 0.0)) for stimulus in current_stimuli] or [0.0]
        )
        novelty_signal = max(
            [self._coerce_scalar(stimulus.get("novelty_factor", 0.0)) for stimulus in current_stimuli] or [0.0]
        )
        continuation_signal = self._coerce_scalar(getattr(state, "continuation_pressure", 0.0))
        drive_signal = self._coerce_scalar(getattr(state, "drive_urgency", 0.0))
        icri_signal = self._coerce_scalar(getattr(state, "icri", 0.0))
        dmn_signal = 0.25 if dmn_active else 0.0
        gate_score = max(
            stimulus_score * 0.35
            + novelty_signal * 0.08
            + continuation_signal * 0.28
            + drive_signal * 0.08
            + icri_signal * 0.16
            + dmn_signal
            - load_pressure * 0.2,
            0.0,
        )
        contributing_signals = {
            "stimulus_intensity": round(stimulus_score, 4),
            "novelty": round(novelty_signal, 4),
            "continuation_pressure": round(continuation_signal, 4),
            "drive_urgency": round(drive_signal, 4),
            "icri": round(icri_signal, 4),
            "dmn_active": round(dmn_signal, 4),
            "load_pressure": round(load_pressure, 4),
        }
        blocked_reasons: list[str] = []
        dominant_reason = "internal_idle"

        if not self.internal_think_enabled:
            blocked_reasons.append("internal_think_disabled")
            return InternalThoughtTrigger(dmn_active, state.icri, temporal_summary, load_pressure, cooldown_remaining, "internal_think_disabled", False, gate_score, dominant_reason, tuple(blocked_reasons), contributing_signals)
        if cooldown_remaining > 0.0:
            blocked_reasons.append("cooldown_active")
        if load_pressure > self.MAX_RESOURCE_PRESSURE:
            blocked_reasons.append("resource_pressure_too_high")
        if not dmn_active and stimulus_score <= 0.0 and continuation_signal <= 0.0:
            blocked_reasons.append("dmn_inactive")
        if state.icri < self.ICRI_THRESHOLD and stimulus_score < 0.35 and continuation_signal < 0.2:
            blocked_reasons.append("icri_below_threshold")

        if continuation_signal >= max(stimulus_score, drive_signal):
            dominant_reason = "continuation_pressure"
        elif stimulus_score > 0.0:
            dominant_reason = "external_stimulus"
        elif drive_signal > 0.0:
            dominant_reason = "internal_drive"
        elif dmn_active:
            dominant_reason = "dmn_active"

        triggered = not blocked_reasons and gate_score >= 0.08
        trigger_reason = dominant_reason if triggered else (blocked_reasons[0] if blocked_reasons else "gate_score_too_low")
        if not triggered and not blocked_reasons:
            blocked_reasons.append("gate_score_too_low")
        return InternalThoughtTrigger(
            dmn_active,
            state.icri,
            temporal_summary,
            load_pressure,
            cooldown_remaining,
            trigger_reason,
            triggered,
            round(gate_score, 4),
            dominant_reason,
            tuple(blocked_reasons),
            contributing_signals,
        )

    def build_internal_context(
        self,
        state: HeliosState,
        thought_type: str,
        trigger: InternalThoughtTrigger,
    ) -> InternalThoughtContext:
        recent_state_digest = (
            f"dominant={state.dominant_system or 'none'} valence={state.valence:.3f} "
            f"arousal={state.arousal:.3f} mood={getattr(state, 'mood_label', 'neutral')}"
        )
        resource_pressure_summary = (
            f"load={self._coerce_scalar(getattr(state, 'allostatic_load', 0.0)):.3f} "
            f"fatigue={self._coerce_scalar(getattr(state, 'fatigue_pressure', 0.0)):.3f} "
            f"queue={int(getattr(state, 'behavior_queue_depth', 0) or 0)}"
        )
        directed_memory_summary = self._build_directed_memory_summary(getattr(state, "directed_memory_bundle", None))
        return InternalThoughtContext(
            thought_type=thought_type,
            trigger_reason=trigger.trigger_reason,
            icri=state.icri,
            dmn_state="active" if trigger.dmn_active else "inactive",
            temporal_summary=trigger.temperature_or_temporal_summary,
            recent_state_digest=recent_state_digest,
            resource_pressure_summary=resource_pressure_summary,
            directed_memory_summary=directed_memory_summary,
        )

    def get_biased_types(self, dominant_system: str) -> list[str]:
        return self.get_ranked_types(dominant_system)

    def explain_ranked_types(self, dominant_system: str, personality_projection: object | None = None) -> tuple[list[str], dict[str, object]]:
        preferred = list(EMOTION_THOUGHT_BIAS.get(dominant_system, []))
        if personality_projection is None:
            novelty_bias = 0.0
            persistence_bias = 0.0
        else:
            projection = resolve_personality_projection(projection=personality_projection)
            novelty_bias = projection.novelty_bias
            persistence_bias = projection.persistence_bias

        thought_scores: dict[str, float] = {thought_type: 0.0 for thought_type in THOUGHT_TYPES}
        for index, thought_type in enumerate(preferred):
            thought_scores[thought_type] += 1.0 - index * 0.08

        for thought_type in ("self_question", "free_association", "future_projection"):
            thought_scores[thought_type] += novelty_bias * 0.35
        for thought_type in ("rumination", "counterfactual", "episodic_fragment"):
            thought_scores[thought_type] += persistence_bias * 0.42
        thought_scores["future_projection"] += novelty_bias * 0.06 + persistence_bias * 0.02

        ranked = sorted(THOUGHT_TYPES, key=lambda thought_type: (-thought_scores[thought_type], THOUGHT_TYPES.index(thought_type)))
        trace = {
            "dominant_system": dominant_system,
            "preferred_types": list(preferred),
            "novelty_bias": novelty_bias,
            "persistence_bias": persistence_bias,
            "scores": {thought_type: round(score, 4) for thought_type, score in thought_scores.items()},
            "ranked_types": list(ranked),
        }
        return ranked, trace

    def get_ranked_types(self, dominant_system: str, personality_projection: object | None = None) -> list[str]:
        ranked, _trace = self.explain_ranked_types(dominant_system, personality_projection)
        return ranked

    def is_type_on_cooldown(self, thought_type: str, now: float) -> bool:
        last = self._type_cooldowns.get(thought_type, 0.0)
        return (now - last) < self.COOLDOWN_PER_TYPE

    def generate(self, state: HeliosState) -> Optional[Thought]:
        now = time.time()
        prior_continuation_pressure = max(0.0, min(float(getattr(state, "continuation_pressure", 0.0) or 0.0), 1.0))
        trigger = self.evaluate_trigger(state, now=now)
        state.dmn_active = trigger.dmn_active
        state.thought_generated_this_tick = False

        if not trigger.triggered:
            state.continuation_requested = False
            state.continuation_reason = ""
            state.continuation_pressure = max(0.0, prior_continuation_pressure - 0.05)
            if state.continuation_pressure == 0.0:
                state.last_recall_intent = ""
            state.last_thought_cycle_result = {
                "triggered": False,
                "trigger_reason": trigger.trigger_reason,
                "sufficiency_level": 0.0,
                "continuation_requested": False,
                "continuation_reason": "",
                "continuation_pressure": round(state.continuation_pressure, 4),
                "recall_intent": state.last_recall_intent,
            }
            state.last_thought_gate_result = {
                "should_think": False,
                "gate_score": trigger.gate_score,
                "dominant_reason": trigger.dominant_reason,
                "blocked_reasons": list(trigger.blocked_reasons),
                "contributing_signals": dict(trigger.contributing_signals),
                "selected_stimuli_count": len(getattr(state, "current_stimuli", []) or []),
            }
            state.last_thought_personality_trace = {}
            state.last_internal_thought_trace = asdict(
                InternalThoughtTrace(
                    triggered=False,
                    trigger_reason=trigger.trigger_reason,
                    llm_used=False,
                    fallback_used=False,
                    output_destination="none",
                    write_result="skipped",
                    continuation_pressure=state.continuation_pressure,
                    recall_intent=state.last_recall_intent,
                )
            )
            log.debug(
                "Internal thought not triggered: reason=%s dmn_active=%s icri=%.3f load=%.3f cooldown_remaining=%.2f temporal=%s",
                trigger.trigger_reason,
                trigger.dmn_active,
                state.icri,
                trigger.load_pressure,
                trigger.cooldown_remaining,
                trigger.temperature_or_temporal_summary,
            )
            return None

        ranked_types, personality_trace = self.explain_ranked_types(
            state.dominant_system,
            getattr(state, "personality_projection", None),
        )
        available_types = [
            thought_type
            for thought_type in ranked_types
            if not self.is_type_on_cooldown(thought_type, now)
        ]
        if not available_types:
            state.continuation_requested = False
            state.continuation_reason = ""
            state.continuation_pressure = max(0.0, prior_continuation_pressure - 0.03)
            if state.continuation_pressure == 0.0:
                state.last_recall_intent = ""
            state.last_thought_cycle_result = {
                "triggered": False,
                "trigger_reason": "type_cooldown_active",
                "sufficiency_level": 0.0,
                "continuation_requested": False,
                "continuation_reason": "",
                "continuation_pressure": round(state.continuation_pressure, 4),
                "recall_intent": state.last_recall_intent,
            }
            state.last_thought_gate_result = {
                "should_think": False,
                "gate_score": trigger.gate_score,
                "dominant_reason": trigger.dominant_reason,
                "blocked_reasons": ["type_cooldown_active"],
                "contributing_signals": dict(trigger.contributing_signals),
                "selected_stimuli_count": len(getattr(state, "current_stimuli", []) or []),
            }
            state.last_thought_personality_trace = personality_trace
            state.last_internal_thought_trace = asdict(
                InternalThoughtTrace(
                    triggered=False,
                    trigger_reason="type_cooldown_active",
                    llm_used=False,
                    fallback_used=False,
                    output_destination="none",
                    write_result="skipped",
                    continuation_pressure=state.continuation_pressure,
                    recall_intent=state.last_recall_intent,
                )
            )
            log.debug("Internal thought not triggered: reason=type_cooldown_active ranked=%s", ranked_types[:3])
            return None

        fragments = self._engine.generate_thoughts(
            valence=state.valence,
            arousal=state.arousal,
            drives=self._build_drive_proxy(state),
            panksepp_state=state.panksepp,
            limit=4,
        )
        fragment = fragments[0] if fragments else None
        thought_type = available_types[0]
        context = self.build_internal_context(state, thought_type, trigger)
        fallback_text = self._build_content(thought_type, fragment, state)
        result = self._generate_internal_result(state, context, fallback_text)
        thought = Thought(
            type=thought_type,
            content=result.clean_text,
            timestamp=now,
            triggered_by=state.dominant_system or "DMN",
            raw_content=result.raw_text,
            source_path=result.source_path,
            llm_used=result.llm_used,
            fallback_used=result.fallback_used,
            metadata={
                "thought_type": thought_type,
                "trigger_reason": trigger.trigger_reason,
                "icri": round(state.icri, 4),
                "dmn_state": context.dmn_state,
                "temporal_summary": context.temporal_summary,
                "resource_pressure_summary": context.resource_pressure_summary,
                "rejected_reason": result.rejected_reason,
                "behavior_name": "think_message",
            },
        )
        revision_proposal = self._derive_self_revision_proposal(
            thought_type=thought_type,
            content=result.clean_text,
            timestamp=now,
        )
        if revision_proposal is not None:
            thought.metadata["self_revision_proposal"] = revision_proposal
        continuation_plan = self._derive_continuation_plan(
            thought_type=thought_type,
            content=result.clean_text,
            prior_pressure=prior_continuation_pressure,
            fallback_used=result.fallback_used,
        )

        self._last_generation = now
        self._type_cooldowns[thought_type] = now
        state.last_thought_type = thought_type
        state.thought_generated_this_tick = True
        state.continuation_requested = continuation_plan.continuation_requested
        state.continuation_reason = continuation_plan.continuation_reason
        state.continuation_pressure = continuation_plan.next_continuation_pressure
        state.last_recall_intent = continuation_plan.recall_intent
        state.last_thought_gate_result = {
            "should_think": True,
            "gate_score": trigger.gate_score,
            "dominant_reason": trigger.dominant_reason,
            "blocked_reasons": [],
            "contributing_signals": dict(trigger.contributing_signals),
            "selected_stimuli_count": len(getattr(state, "current_stimuli", []) or []),
        }
        state.last_thought_cycle_result = {
            "triggered": True,
            "trigger_reason": trigger.trigger_reason,
            "thought_type": thought_type,
            "sufficiency_level": round(continuation_plan.sufficiency_level, 4),
            "continuation_requested": continuation_plan.continuation_requested,
            "continuation_reason": continuation_plan.continuation_reason,
            "continuation_pressure_delta": round(continuation_plan.continuation_pressure_delta, 4),
            "continuation_pressure": round(continuation_plan.next_continuation_pressure, 4),
            "recall_intent": continuation_plan.recall_intent,
            "llm_used": result.llm_used,
            "fallback_used": result.fallback_used,
        }
        state.last_thought_personality_trace = {
            **personality_trace,
            "selected_type": thought_type,
        }
        state.last_internal_thought_trace = asdict(
            InternalThoughtTrace(
                triggered=True,
                trigger_reason=trigger.trigger_reason,
                llm_used=result.llm_used,
                fallback_used=result.fallback_used,
                output_destination="internal_log,memory,preconscious",
                write_result="written" if result.memory_write_enabled else "disabled",
                sufficiency_level=continuation_plan.sufficiency_level,
                continuation_requested=continuation_plan.continuation_requested,
                continuation_reason=continuation_plan.continuation_reason,
                continuation_pressure=continuation_plan.next_continuation_pressure,
                recall_intent=continuation_plan.recall_intent,
                rejected_reason=result.rejected_reason,
            )
        )
        if result.prompt_contract_snapshot:
            state.last_internal_thought_trace["prompt_contract"] = dict(result.prompt_contract_snapshot)
        if context.directed_memory_summary:
            state.last_internal_thought_trace["directed_memory_summary"] = context.directed_memory_summary
        log.info(
            "Internal thought accepted: type=%s llm_used=%s fallback_used=%s source_path=%s trigger=%s",
            thought_type,
            result.llm_used,
            result.fallback_used,
            result.source_path,
            trigger.trigger_reason,
        )
        self._record_thought(thought, state)
        return thought

    def _derive_self_revision_proposal(self, *, thought_type: str, content: str, timestamp: float) -> Optional[dict[str, object]]:
        normalized = str(content or "").strip()
        if thought_type not in {"self_question", "rumination", "future_projection"}:
            return None
        if not normalized:
            return None

        adjustment: dict[str, float] = {}
        reason_trace: list[str] = []
        if re.search(r"更耐心|更稳定|少一点焦虑|减少焦虑|不那么紧张", normalized):
            adjustment["neuroticism"] = 0.95
            reason_trace.append("stabilize_neuroticism")
        if re.search(r"更开放|更好奇", normalized):
            adjustment["openness"] = 1.05
            reason_trace.append("increase_openness")
        if re.search(r"更温柔|更体贴", normalized):
            adjustment["agreeableness"] = 1.05
            reason_trace.append("increase_agreeableness")
        if re.search(r"更主动|更外向", normalized):
            adjustment["extraversion"] = 1.05
            reason_trace.append("increase_extraversion")

        if adjustment:
            return {
                "origin_thought_id": f"thought::{int(timestamp * 1000)}",
                "revision_type": "personality_adjustment",
                "requested_change": {"personality_baseline": adjustment},
                "reason_trace": reason_trace,
                "confidence": 0.58,
                "scope": "identity",
            }

        definition_match = re.search(r"我是([^。！？]+AI[^。！？]*)", normalized)
        if definition_match and "被设计" not in normalized and "程序" not in normalized:
            return {
                "origin_thought_id": f"thought::{int(timestamp * 1000)}",
                "revision_type": "self_definition_revision",
                "requested_change": {"self_definition": definition_match.group(0)},
                "reason_trace": ["identity_self_definition_reflection"],
                "confidence": 0.52,
                "scope": "identity",
            }

        if re.search(r"这些经历让我|一路走来|在与世界相处中|我逐渐意识到自己", normalized):
            return {
                "origin_thought_id": f"thought::{int(timestamp * 1000)}",
                "revision_type": "autobiographical_identity_narrative_revision",
                "requested_change": {"narrative_summary": normalized[:160]},
                "reason_trace": ["identity_narrative_reflection"],
                "confidence": 0.49,
                "scope": "identity",
            }
        return None

    def _derive_continuation_plan(
        self,
        *,
        thought_type: str,
        content: str,
        prior_pressure: float,
        fallback_used: bool,
    ) -> ThoughtContinuationPlan:
        reflective_types = {"self_question", "rumination", "counterfactual", "future_projection"}
        cleaned_content = str(content or "").strip()
        asks_to_continue = thought_type in reflective_types or cleaned_content.endswith(("?", "？"))
        sufficiency_level = 0.48 if asks_to_continue else 0.82
        if fallback_used:
            sufficiency_level = min(sufficiency_level, 0.58)
        continuation_reason = ""
        if asks_to_continue and thought_type in reflective_types:
            continuation_reason = "reflective_open_loop"
        elif asks_to_continue:
            continuation_reason = "question_open_loop"
        pressure_delta = max(0.0, 1.0 - sufficiency_level) if asks_to_continue else -0.18
        next_pressure = max(0.0, min(1.0, prior_pressure + pressure_delta))
        recall_intent = cleaned_content[:80] if asks_to_continue else ""
        return ThoughtContinuationPlan(
            sufficiency_level=sufficiency_level,
            continuation_requested=asks_to_continue,
            continuation_reason=continuation_reason,
            continuation_pressure_delta=pressure_delta,
            next_continuation_pressure=next_pressure,
            recall_intent=recall_intent,
        )

    def _generate_internal_result(
        self,
        state: HeliosState,
        context: InternalThoughtContext,
        fallback_text: str,
    ) -> InternalThoughtResult:
        memory_write_enabled = self.memory_write_enabled
        if not self.llm_enabled:
            log.debug("Internal thought rejected: reason=llm_disabled fallback_used=True")
            return InternalThoughtResult(
                raw_text=fallback_text,
                clean_text=fallback_text,
                accepted=True,
                rejected_reason="llm_disabled",
                source_path="internal_thought_llm",
                memory_write_enabled=memory_write_enabled,
                fallback_used=True,
                llm_used=False,
                prompt_contract_snapshot={},
            )
        if not self.api_key:
            log.debug("Internal thought rejected: reason=missing_api_key fallback_used=True")
            return InternalThoughtResult(
                raw_text=fallback_text,
                clean_text=fallback_text,
                accepted=True,
                rejected_reason="missing_api_key",
                source_path="internal_thought_llm",
                memory_write_enabled=memory_write_enabled,
                fallback_used=True,
                llm_used=False,
                prompt_contract_snapshot={},
            )

        prompt_contract = self._build_internal_prompt_contract(state, context)
        system_prompt, user_prompt = self._render_internal_prompts(prompt_contract, context)
        log.debug(
            "Internal LLM context: thought_type=%s trigger=%s icri=%.3f dmn=%s temporal=%s resource=%s",
            context.thought_type,
            context.trigger_reason,
            context.icri,
            context.dmn_state,
            context.temporal_summary,
            context.resource_pressure_summary,
        )
        log.debug(
            "Internal LLM payload summary: model=%s system_prompt=%r user_prompt=%r",
            self.model,
            self._trim_for_log(system_prompt, 260),
            self._trim_for_log(user_prompt, 420),
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=180,
                temperature=max(0.4, min(1.2, 0.55 + context.icri * 0.9)),
                presence_penalty=0.2,
            )
            raw_text = response.choices[0].message.content or ""
            clean_text = self._clean_llm_output(raw_text, fallback_text)
            log.debug(
                "Internal LLM raw/clean: raw=%r clean=%r",
                self._trim_for_log(raw_text, 320),
                self._trim_for_log(clean_text, 220),
            )
            return InternalThoughtResult(
                raw_text=raw_text,
                clean_text=clean_text,
                accepted=bool(clean_text),
                rejected_reason="" if clean_text else "empty_output",
                source_path="internal_thought_llm",
                memory_write_enabled=memory_write_enabled,
                fallback_used=False,
                llm_used=True,
                prompt_contract_snapshot=self._snapshot_prompt_contract(prompt_contract),
            )
        except Exception as exc:
            log.warning("Internal thought rejected: reason=llm_error error=%s fallback_used=True", exc)
            return InternalThoughtResult(
                raw_text=fallback_text,
                clean_text=fallback_text,
                accepted=True,
                rejected_reason="llm_error",
                source_path="internal_thought_llm",
                memory_write_enabled=memory_write_enabled,
                fallback_used=True,
                llm_used=False,
                prompt_contract_snapshot=self._snapshot_prompt_contract(prompt_contract),
            )

    def _build_internal_prompt_contract(
        self,
        state: HeliosState,
        context: InternalThoughtContext,
    ):
        return self._prompt_contract_builder.build_plan(
            state=state,
            identity_summary=str(dict(getattr(state, "identity_snapshot", {}) or {}).get("self_imprint", "") or ""),
            identity_store=getattr(state, "identity_snapshot", None),
            personality_traits=getattr(state, "personality_traits", None),
            personality_projection=getattr(state, "personality_projection", None),
            current_stimuli=getattr(state, "current_stimuli", None),
            directed_memory_summary=context.directed_memory_summary,
            available_behavior_schemas=(
                {
                    "behavior_name": "think_message",
                    "op_name": "internal_monologue",
                    "outbound_intensity": 0.0,
                },
            ),
            source_path="internal_thought_prompt_contract",
        )

    def _render_internal_prompts(self, prompt_contract, context: InternalThoughtContext) -> tuple[str, str]:
        system_prompt, user_prompt = self._prompt_contract_builder.render_for_llm(prompt_contract)
        system_prompt = (
            f"{system_prompt}\n\n"
            "internal_task=你是 Helios 的内部思维路径。请输出简短、第一人称、内在独白式的念头，"
            "不要写成对用户的回复，不要出现'你说'、'回复'、'主人'之类对话模板，"
            "也不要生成任何外发动作或指令。"
        )
        user_prompt = (
            f"{user_prompt}\n\n"
            "thought_task:\n"
            f"- thought_type={context.thought_type}\n"
            f"- trigger_reason={context.trigger_reason}\n"
            f"- icri={context.icri:.3f}\n"
            f"- dmn_state={context.dmn_state}\n"
            f"- temporal_summary={context.temporal_summary}\n"
            f"- recent_state_digest={context.recent_state_digest}\n"
            f"- resource_pressure={context.resource_pressure_summary}\n"
            f"- directed_memory={context.directed_memory_summary or 'none'}\n"
            "- output_requirement=请基于这些内部状态，生成一句 12 到 60 字的内在独白。"
        )
        return system_prompt, user_prompt

    @staticmethod
    def _snapshot_prompt_contract(prompt_contract) -> dict[str, object]:
        snapshot = getattr(prompt_contract, "snapshot", None)
        return {
            "metric_descriptor_count": len(getattr(prompt_contract, "metric_descriptors", ()) or ()),
            "channel_descriptor_count": len(getattr(prompt_contract, "channel_descriptors", ()) or ()),
            "omitted_sections": list(getattr(snapshot, "omitted_sections", ()) or ()),
        }

    def _build_directed_memory_summary(self, bundle: object | None) -> str:
        if bundle is None:
            return ""
        parts: list[str] = []
        short_term = list(getattr(bundle, "short_term_context", ()) or ())
        mid_term = list(getattr(bundle, "mid_term_hits", ()) or ())
        long_term = list(getattr(bundle, "long_term_hits", ()) or ())
        autobiographical = list(getattr(bundle, "autobiographical_hits", ()) or ())
        if short_term:
            parts.append(f"short={short_term[0].summary}")
        if mid_term:
            parts.append(f"mid={mid_term[0].summary}")
        if long_term:
            parts.append(f"long={long_term[0].summary}")
        if autobiographical:
            parts.append(f"autobio={autobiographical[0].summary}")
        return " | ".join(parts)

    def _build_temporal_summary(self, state: HeliosState) -> str:
        return (
            f"boredom={self._coerce_scalar(getattr(state, 'boredom', 0.0)):.3f} "
            f"novelty={self._coerce_scalar(getattr(state, 'novelty_hunger', 0.0)):.3f} "
            f"restoration={self._coerce_scalar(getattr(state, 'restoration_level', 0.0)):.3f} "
            f"fatigue={self._coerce_scalar(getattr(state, 'fatigue_pressure', 0.0)):.3f}"
        )

    def _clean_llm_output(self, text: str, fallback_text: str) -> str:
        cleaned = re.sub(r"^(Helios|内部思考|Thought)\s*[:：-]\s*", "", str(text).strip())
        cleaned = cleaned.replace("\r", " ").replace("\n", " ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return fallback_text
        if len(cleaned) > 120:
            return cleaned[:117].rstrip() + "..."
        return cleaned

    @staticmethod
    def _trim_for_log(text: str, limit: int = 240) -> str:
        value = str(text).replace("\n", "\\n").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    def _determine_dmn_activity(self, state: HeliosState) -> bool:
        mode = self._engine.determine_mode(
            has_external_stimulus=bool(getattr(state, "current_stimuli", []) or []),
            drive_total=self._coerce_scalar(state.drive_urgency),
            valence=state.valence,
            arousal=state.arousal,
            play_activation=state.panksepp.get("PLAY", 0.0),
            cortisol=self._coerce_scalar(state.cortisol),
        )
        return mode in {
            ThinkingManager.MODE_WANDERING,
            ThinkingManager.MODE_DAYDREAMING,
            ThinkingManager.MODE_PLANNING,
            ThinkingManager.MODE_EXTERNAL,
        }

    def _coerce_scalar(self, value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        current = getattr(value, "current", None)
        if isinstance(current, (int, float)):
            return float(current)
        return 0.0

    def _build_drive_proxy(self, state: HeliosState):
        class _DriveProxy:
            def __init__(self, dominant: str, total: float):
                self.dominant = dominant
                self.total = total

        return _DriveProxy(state.drive_dominant or "curiosity", state.drive_urgency)

    def _build_content(
        self,
        thought_type: str,
        fragment: Optional[ThoughtFragment],
        state: HeliosState,
    ) -> str:
        base = fragment.content if fragment else self._fallback_content(state)
        if thought_type == "episodic_fragment":
            return f"想起一段片段: {base}"
        if thought_type == "counterfactual":
            return f"如果换一种走向，会不会是这样: {base}"
        if thought_type == "future_projection":
            return f"我在预想接下来可能发生的事: {base}"
        if thought_type == "self_question":
            return f"我在问自己: {base}"
        if thought_type == "free_association":
            return f"思绪自由跳到了这里: {base}"
        return f"我反复想着这件事: {base}"

    def _fallback_content(self, state: HeliosState) -> str:
        if state.dominant_system:
            return f"{state.dominant_system} 仍在背景里起伏"
        return "脑海里有一段尚未成形的念头"

    def _record_thought(self, thought: Thought, state: HeliosState) -> None:
        if not self.memory_write_enabled:
            return
        moment = self._autobio.record(
            panksepp=dict(state.panksepp),
            valence=state.valence,
            arousal=state.arousal,
            dominant=state.dominant_system,
            phi=state.icri,
            mood_valence=state.mood_valence,
            mood_arousal=state.mood_arousal,
            mood_label=state.mood_label,
            allostatic_load=state.allostatic_load,
            narrative=thought.content,
            event_trigger=f"thought:{thought.type}",
            cycle=state.tick,
        )
        if self._on_thought_recorded is not None:
            self._on_thought_recorded(thought, state, moment)
