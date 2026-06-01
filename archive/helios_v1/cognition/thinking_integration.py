"""Integration layer for internal thought generation."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, cast

from core.helios_state import ContinuationPressureState, HeliosState
from helios_io.action_models import ThoughtActionProposal
from helios_io.llm_debug import log_llm_request, log_llm_response
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
    session_kind: str = "reactive"
    dominant_disposition: str = ""
    trigger_sources: tuple[str, ...] = ()

    def to_gate_result(self, *, selected_stimuli: tuple[dict[str, object], ...] = ()) -> "ThoughtGateResult":
        return ThoughtGateResult(
            should_think=self.triggered,
            gate_score=self.gate_score,
            trigger_reason=self.trigger_reason,
            dominant_reason=self.dominant_reason,
            blocked_reasons=self.blocked_reasons,
            contributing_signals=dict(self.contributing_signals),
            session_kind=self.session_kind,
            dominant_disposition=self.dominant_disposition,
            trigger_sources=self.trigger_sources,
            selected_stimuli=selected_stimuli,
        )


@dataclass(frozen=True)
class ThoughtGateResult:
    should_think: bool
    gate_score: float = 0.0
    trigger_reason: str = ""
    dominant_reason: str = ""
    blocked_reasons: tuple[str, ...] = ()
    contributing_signals: dict[str, float] = field(default_factory=dict)
    session_kind: str = "reactive"
    dominant_disposition: str = ""
    trigger_sources: tuple[str, ...] = ()
    selected_stimuli: tuple[dict[str, object], ...] = ()

    def to_state_payload(self) -> dict[str, object]:
        return {
            "should_think": self.should_think,
            "gate_score": round(float(self.gate_score), 4),
            "trigger_reason": self.trigger_reason,
            "dominant_reason": self.dominant_reason,
            "blocked_reasons": list(self.blocked_reasons),
            "contributing_signals": {
                key: round(float(value), 4) for key, value in dict(self.contributing_signals).items()
            },
            "session_kind": self.session_kind,
            "dominant_disposition": self.dominant_disposition,
            "trigger_sources": list(self.trigger_sources),
            "selected_stimuli": [dict(stimulus) for stimulus in self.selected_stimuli],
            "selected_stimuli_count": len(self.selected_stimuli),
        }


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
    structured_decision: dict[str, object] = field(default_factory=dict)
    structured_output_valid: bool = False
    structured_payload_observability: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ThoughtContinuationPlan:
    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    continuation_pressure_delta: float
    next_continuation_pressure: float
    recall_intent: str


@dataclass(frozen=True)
class ActionDerivationTrace:
    action_explicit: bool = False
    parse_status: str = "not_applicable"
    drop_reason: str = ""
    equivalent_bridge_evidence: bool = False
    bridge_evidence_kind: str = ""
    raw_action_summary: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "action_explicit": self.action_explicit,
            "parse_status": self.parse_status,
            "drop_reason": self.drop_reason,
            "equivalent_bridge_evidence": self.equivalent_bridge_evidence,
            "bridge_evidence_kind": self.bridge_evidence_kind,
            "raw_action_summary": dict(self.raw_action_summary),
        }


@dataclass(frozen=True)
class MemoryHandoffDirective:
    recall_intent: str = ""
    selected_memory_refs: tuple[str, ...] = ()
    saved_for_next_tick: bool = False
    source_thought_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "recall_intent": self.recall_intent,
            "selected_memory_refs": list(self.selected_memory_refs),
            "saved_for_next_tick": self.saved_for_next_tick,
            "source_thought_id": self.source_thought_id,
        }


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
    structured_output_valid: bool = False
    action_explicit: bool = False
    action_parse_status: str = "not_applicable"
    action_drop_reason: str = ""
    equivalent_bridge_evidence: bool = False
    bridge_evidence_kind: str = ""
    structured_parse_source: str = ""


@dataclass(frozen=True)
class QuietTickOutcome:
    tick: int
    gate_reason: str
    continuation_pressure: float
    stimulus_summary: str = ""
    memory_summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ThoughtCycleResult:
    triggered: bool
    trigger_reason: str
    thought: Thought | None = None
    thought_id: str = ""
    thought_type: str = ""
    sufficiency_level: float = 0.0
    continuation_requested: bool = False
    continuation_reason: str = ""
    continuation_pressure_delta: float = 0.0
    continuation_pressure: float = 0.0
    continuation: ContinuationPressureState = field(default_factory=ContinuationPressureState)
    recall_intent: str = ""
    memory_handoff: dict[str, object] | None = None
    llm_used: bool = False
    fallback_used: bool = False
    owner_path: str = "internal_thought_loop"
    session_kind: str = "reactive"
    dominant_disposition: str = ""
    trigger_sources: tuple[str, ...] = ()
    action_proposal: ThoughtActionProposal | dict[str, object] | None = None
    action_derivation_trace: ActionDerivationTrace = field(default_factory=ActionDerivationTrace)
    self_revision_proposal: dict[str, object] | None = None
    quiet_tick: QuietTickOutcome | None = None

    def to_state_payload(self) -> dict[str, object]:
        action_proposal_payload = ThoughtActionProposal.from_payload(self.action_proposal)
        raw_action_proposal = self.action_proposal if isinstance(self.action_proposal, dict) else {}
        payload = {
            "triggered": self.triggered,
            "trigger_reason": self.trigger_reason,
            "thought_id": self.thought_id,
            "thought_type": self.thought_type,
            "sufficiency_level": round(float(self.sufficiency_level), 4),
            "continuation_requested": self.continuation_requested,
            "continuation_reason": self.continuation_reason,
            "continuation_pressure_delta": round(float(self.continuation_pressure_delta), 4),
            "continuation_pressure": round(float(self.continuation_pressure), 4),
            "continuation": self.continuation.to_dict(),
            "recall_intent": self.recall_intent,
            "memory_handoff": dict(self.memory_handoff or {}),
            "llm_used": self.llm_used,
            "fallback_used": self.fallback_used,
            "owner_path": self.owner_path,
            "session_kind": self.session_kind,
            "dominant_disposition": self.dominant_disposition,
            "trigger_sources": list(self.trigger_sources),
            "action_proposal": action_proposal_payload.to_dict() if action_proposal_payload is not None else dict(raw_action_proposal),
            "action_derivation_trace": self.action_derivation_trace.to_dict(),
            "self_revision_proposal": dict(self.self_revision_proposal or {}),
        }
        if self.thought is not None:
            payload["content"] = self.thought.content
        if self.quiet_tick is not None:
            payload["quiet_tick"] = self.quiet_tick.to_dict()
        return payload


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
        available_channels_provider: Optional[Callable[[], Sequence[object]]] = None,
        available_behavior_schema_provider: Optional[Callable[[], Sequence[Mapping[str, object]]]] = None,
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
        self._available_channels_provider = available_channels_provider
        self._available_behavior_schema_provider = available_behavior_schema_provider
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
        sensitization_signal = max(
            [self._coerce_scalar(stimulus.get("sensitization_factor", 0.0)) for stimulus in current_stimuli] or [0.0]
        )
        continuation_signal = self._coerce_scalar(getattr(state, "continuation_pressure", 0.0))
        drive_signal = self._coerce_scalar(getattr(state, "drive_urgency", 0.0))
        icri_signal = self._coerce_scalar(getattr(state, "icri", 0.0))
        temporal_signal = self._compute_temporal_gate_signal(state)
        proactive_snapshot = getattr(state, "proactive", None)
        proactive_drive_score = self._coerce_scalar(getattr(proactive_snapshot, "drive_score", 0.0))
        dominant_disposition = str(getattr(proactive_snapshot, "dominant_disposition", "") or "")
        proactive_drive_sources = [
            str(item) for item in list(getattr(proactive_snapshot, "drive_sources", []) or []) if str(item)
        ]
        dmn_signal = 0.25 if dmn_active else 0.0
        gate_score = max(
            stimulus_score * 0.31
            + novelty_signal * 0.06
            + sensitization_signal * 0.05
            + continuation_signal * 0.28
            + drive_signal * 0.08
            + icri_signal * 0.16
            + temporal_signal * 0.12
            + dmn_signal
            - load_pressure * 0.2,
            0.0,
        )
        contributing_signals = {
            "stimulus_intensity": round(stimulus_score, 4),
            "novelty": round(novelty_signal, 4),
            "sensitization": round(sensitization_signal, 4),
            "continuation_pressure": round(continuation_signal, 4),
            "drive_urgency": round(drive_signal, 4),
            "proactive_drive": round(proactive_drive_score, 4),
            "icri": round(icri_signal, 4),
            "temporal_dynamics": round(temporal_signal, 4),
            "dmn_active": round(dmn_signal, 4),
            "load_pressure": round(load_pressure, 4),
        }
        blocked_reasons: list[str] = []
        dominant_reason = "internal_idle"
        strong_external_stimulus = any(
            str((stimulus or {}).get("source_kind", "") or "external_message") not in {"internal", "internal_drive"}
            for stimulus in current_stimuli
        ) and stimulus_score >= 0.2

        if not self.internal_think_enabled:
            blocked_reasons.append("internal_think_disabled")
            return InternalThoughtTrigger(dmn_active, state.icri, temporal_summary, load_pressure, cooldown_remaining, "internal_think_disabled", False, gate_score, dominant_reason, tuple(blocked_reasons), contributing_signals)
        if cooldown_remaining > 0.0 and not strong_external_stimulus:
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

        proactive_signal = max(continuation_signal, drive_signal, proactive_drive_score, temporal_signal)
        if stimulus_score >= 0.2 and proactive_signal >= 0.2:
            session_kind = "mixed"
        elif stimulus_score >= 0.2:
            session_kind = "reactive"
        else:
            session_kind = "proactive"

        trigger_sources: list[str] = []
        if stimulus_score > 0.0:
            trigger_sources.append("stimulus")
        if continuation_signal > 0.0:
            trigger_sources.append("continuation")
        if drive_signal > 0.0:
            trigger_sources.append(f"drive:{str(getattr(state, 'drive_dominant', '') or 'unknown')}")
        for source in proactive_drive_sources[:4]:
            if source not in trigger_sources:
                trigger_sources.append(source)
        if dominant_disposition:
            trigger_sources.append(f"disposition:{dominant_disposition}")

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
            session_kind,
            dominant_disposition,
            tuple(trigger_sources),
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

    def generate(self, state: HeliosState) -> ThoughtCycleResult:
        now = time.time()
        prior_continuation = ContinuationPressureState.from_payload(getattr(state, "continuation_payload", lambda: {})())
        prior_continuation_pressure = max(0.0, min(float(prior_continuation.level or 0.0), 1.0))
        trigger = self.evaluate_trigger(state, now=now)
        gate_result = trigger.to_gate_result(selected_stimuli=self._select_gate_stimuli(state))
        state.dmn_active = trigger.dmn_active
        state.thought_generated_this_tick = False

        if not trigger.triggered:
            state.continuation_requested = False
            continuation_state = self._decay_continuation_state(state, amount=0.05)
            if continuation_state.level == 0.0:
                state.last_recall_intent = ""
            quiet_tick = QuietTickOutcome(
                tick=int(getattr(state, "tick", 0) or 0),
                gate_reason=trigger.trigger_reason,
                continuation_pressure=continuation_state.level,
                stimulus_summary=f"stimuli={len(getattr(state, 'current_stimuli', []) or [])}",
                memory_summary=self._build_directed_memory_summary(getattr(state, "directed_memory_bundle", None)),
            )
            cycle_result = ThoughtCycleResult(
                triggered=False,
                trigger_reason=trigger.trigger_reason,
                continuation_pressure=continuation_state.level,
                continuation=continuation_state,
                recall_intent=state.last_recall_intent,
                session_kind=trigger.session_kind,
                dominant_disposition=trigger.dominant_disposition,
                trigger_sources=trigger.trigger_sources,
                quiet_tick=quiet_tick,
            )
            state.current_thought_cycle_result = cycle_result
            state.last_thought_cycle_result = cycle_result.to_state_payload()
            state.last_thought_gate_result = gate_result.to_state_payload()
            state.last_thought_personality_trace = {}
            state.last_internal_thought_trace = asdict(
                InternalThoughtTrace(
                    triggered=False,
                    trigger_reason=trigger.trigger_reason,
                    llm_used=False,
                    fallback_used=False,
                    output_destination="none",
                    write_result="skipped",
                    continuation_pressure=continuation_state.level,
                    recall_intent=state.last_recall_intent,
                )
            )
            state.last_internal_thought_trace["session_kind"] = trigger.session_kind
            state.last_internal_thought_trace["dominant_disposition"] = trigger.dominant_disposition
            state.last_internal_thought_trace["trigger_sources"] = list(trigger.trigger_sources)
            state.last_internal_thought_trace["continuation"] = continuation_state.to_dict()
            log.debug(
                "Internal thought not triggered: reason=%s dmn_active=%s icri=%.3f load=%.3f cooldown_remaining=%.2f temporal=%s",
                trigger.trigger_reason,
                trigger.dmn_active,
                state.icri,
                trigger.load_pressure,
                trigger.cooldown_remaining,
                trigger.temperature_or_temporal_summary,
            )
            return cycle_result

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
            continuation_state = self._decay_continuation_state(state, amount=0.03)
            if continuation_state.level == 0.0:
                state.last_recall_intent = ""
            quiet_tick = QuietTickOutcome(
                tick=int(getattr(state, "tick", 0) or 0),
                gate_reason="type_cooldown_active",
                continuation_pressure=continuation_state.level,
                stimulus_summary=f"stimuli={len(getattr(state, 'current_stimuli', []) or [])}",
                memory_summary=self._build_directed_memory_summary(getattr(state, "directed_memory_bundle", None)),
            )
            cycle_result = ThoughtCycleResult(
                triggered=False,
                trigger_reason="type_cooldown_active",
                continuation_pressure=continuation_state.level,
                continuation=continuation_state,
                recall_intent=state.last_recall_intent,
                session_kind=trigger.session_kind,
                dominant_disposition=trigger.dominant_disposition,
                trigger_sources=trigger.trigger_sources,
                quiet_tick=quiet_tick,
            )
            state.current_thought_cycle_result = cycle_result
            state.last_thought_cycle_result = cycle_result.to_state_payload()
            state.last_thought_gate_result = ThoughtGateResult(
                should_think=False,
                gate_score=trigger.gate_score,
                trigger_reason="type_cooldown_active",
                dominant_reason=trigger.dominant_reason,
                blocked_reasons=("type_cooldown_active",),
                contributing_signals=dict(trigger.contributing_signals),
                session_kind=trigger.session_kind,
                dominant_disposition=trigger.dominant_disposition,
                trigger_sources=trigger.trigger_sources,
                selected_stimuli=self._select_gate_stimuli(state),
            ).to_state_payload()
            state.last_thought_personality_trace = personality_trace
            state.last_internal_thought_trace = asdict(
                InternalThoughtTrace(
                    triggered=False,
                    trigger_reason="type_cooldown_active",
                    llm_used=False,
                    fallback_used=False,
                    output_destination="none",
                    write_result="skipped",
                    continuation_pressure=continuation_state.level,
                    recall_intent=state.last_recall_intent,
                )
            )
            state.last_internal_thought_trace["session_kind"] = trigger.session_kind
            state.last_internal_thought_trace["dominant_disposition"] = trigger.dominant_disposition
            state.last_internal_thought_trace["trigger_sources"] = list(trigger.trigger_sources)
            state.last_internal_thought_trace["continuation"] = continuation_state.to_dict()
            log.debug("Internal thought not triggered: reason=type_cooldown_active ranked=%s", ranked_types[:3])
            return cycle_result

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
        thought_id = f"thought::{int(getattr(state, 'tick', 0))}::{thought_type}::{int(now * 1000)}"
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
                "session_kind": trigger.session_kind,
                "dominant_disposition": trigger.dominant_disposition,
                "trigger_sources": list(trigger.trigger_sources),
                "icri": round(state.icri, 4),
                "dmn_state": context.dmn_state,
                "temporal_summary": context.temporal_summary,
                "resource_pressure_summary": context.resource_pressure_summary,
                "rejected_reason": result.rejected_reason,
                "behavior_name": "think_message",
                "thought_id": thought_id,
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
            structured_decision=result.structured_decision if result.structured_output_valid else None,
        )
        memory_handoff = self._derive_memory_handoff(
            thought_id=thought_id,
            continuation_plan=continuation_plan,
            structured_decision=result.structured_decision if result.structured_output_valid else None,
        )
        action_trace = self._derive_action_trace(
            structured_decision=result.structured_decision if result.structured_output_valid else None,
        )
        action_proposal = self._derive_action_proposal(
            state=state,
            thought_id=thought_id,
            thought_type=thought_type,
            trigger_reason=trigger.trigger_reason,
            continuation_plan=continuation_plan,
            structured_decision=result.structured_decision if result.structured_output_valid else None,
        )
        action_trace = self._mark_equivalent_bridge_evidence(action_trace, action_proposal)
        if action_proposal is None and action_trace.action_explicit and action_trace.parse_status == "parsed":
            action_trace = ActionDerivationTrace(
                action_explicit=True,
                parse_status="dropped_during_normalization",
                drop_reason="structured_action_proposal_not_emitted",
                raw_action_summary=dict(action_trace.raw_action_summary),
            )
        if action_proposal is not None:
            thought.metadata["action_proposal"] = action_proposal.to_dict()
        if memory_handoff:
            thought.metadata["memory_handoff"] = dict(memory_handoff)

        self._last_generation = now
        self._type_cooldowns[thought_type] = now
        state.last_thought_type = thought_type
        state.thought_generated_this_tick = True
        state.continuation_requested = continuation_plan.continuation_requested
        continuation_state = self._build_continuation_state(
            prior_continuation=prior_continuation,
            continuation_plan=continuation_plan,
            thought_id=thought_id,
            tick=int(getattr(state, "tick", 0) or 0),
        )
        state.set_continuation(continuation_state)
        state.last_recall_intent = continuation_plan.recall_intent
        state.last_memory_handoff = dict(memory_handoff)
        state.last_thought_gate_result = gate_result.to_state_payload()
        cycle_result = ThoughtCycleResult(
            triggered=True,
            trigger_reason=trigger.trigger_reason,
            thought=thought,
            thought_id=thought_id,
            thought_type=thought_type,
            sufficiency_level=continuation_plan.sufficiency_level,
            continuation_requested=continuation_plan.continuation_requested,
            continuation_reason=continuation_plan.continuation_reason,
            continuation_pressure_delta=continuation_plan.continuation_pressure_delta,
            continuation_pressure=continuation_state.level,
            continuation=continuation_state,
            recall_intent=continuation_plan.recall_intent,
            memory_handoff=dict(memory_handoff),
            llm_used=result.llm_used,
            fallback_used=result.fallback_used,
            session_kind=trigger.session_kind,
            dominant_disposition=trigger.dominant_disposition,
            trigger_sources=trigger.trigger_sources,
            action_proposal=action_proposal,
            action_derivation_trace=action_trace,
            self_revision_proposal=dict(revision_proposal or {}),
        )
        state.current_thought_cycle_result = cycle_result
        state.last_thought_cycle_result = cycle_result.to_state_payload()
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
                continuation_pressure=continuation_state.level,
                recall_intent=continuation_plan.recall_intent,
                rejected_reason=result.rejected_reason,
                structured_output_valid=result.structured_output_valid,
                action_explicit=action_trace.action_explicit,
                action_parse_status=action_trace.parse_status,
                action_drop_reason=action_trace.drop_reason,
                equivalent_bridge_evidence=action_trace.equivalent_bridge_evidence,
                bridge_evidence_kind=action_trace.bridge_evidence_kind,
                structured_parse_source=str(result.structured_payload_observability.get("parse_source", "") or ""),
            )
        )
        state.last_internal_thought_trace["session_kind"] = trigger.session_kind
        state.last_internal_thought_trace["dominant_disposition"] = trigger.dominant_disposition
        state.last_internal_thought_trace["trigger_sources"] = list(trigger.trigger_sources)
        state.last_internal_thought_trace["continuation"] = continuation_state.to_dict()
        if result.prompt_contract_snapshot:
            state.last_internal_thought_trace["prompt_contract"] = dict(result.prompt_contract_snapshot)
        if result.structured_payload_observability:
            state.last_internal_thought_trace["structured_payload_observability"] = dict(result.structured_payload_observability)
        if context.directed_memory_summary:
            state.last_internal_thought_trace["directed_memory_summary"] = context.directed_memory_summary
        state.last_internal_thought_trace["action_derivation_trace"] = action_trace.to_dict()
        if memory_handoff:
            state.last_internal_thought_trace["memory_handoff"] = dict(memory_handoff)
        if action_proposal is not None:
            state.last_internal_thought_trace["action_proposal"] = action_proposal.to_dict()
        log.debug(
            "Internal thought accepted: type=%s llm_used=%s fallback_used=%s source_path=%s trigger=%s rejected_reason=%s",
            thought_type,
            result.llm_used,
            result.fallback_used,
            result.source_path,
            trigger.trigger_reason,
            result.rejected_reason,
        )
        self._record_thought(thought, state)
        return cycle_result

    def _build_continuation_state(
        self,
        *,
        prior_continuation: ContinuationPressureState,
        continuation_plan: ThoughtContinuationPlan,
        thought_id: str,
        tick: int,
    ) -> ContinuationPressureState:
        if not continuation_plan.continuation_requested or continuation_plan.next_continuation_pressure <= 0.0:
            return ContinuationPressureState()
        horizon = 3 if continuation_plan.continuation_reason == "reflective_open_loop" else 2
        return ContinuationPressureState(
            active=True,
            level=max(0.0, min(float(continuation_plan.next_continuation_pressure or 0.0), 1.0)),
            origin_thought_id=thought_id,
            reason=continuation_plan.continuation_reason,
            expires_at_tick=max(tick + horizon, prior_continuation.expires_at_tick if prior_continuation.active else 0),
            carry_count=1,
        )

    def _decay_continuation_state(self, state: HeliosState, *, amount: float) -> ContinuationPressureState:
        prior = ContinuationPressureState.from_payload(state.continuation_payload())
        tick = int(getattr(state, "tick", 0) or 0)
        if not prior.active or prior.level <= 0.0:
            state.clear_continuation()
            return state.continuation
        if prior.expires_at_tick and tick >= prior.expires_at_tick:
            state.clear_continuation()
            return state.continuation
        next_level = max(0.0, min(float(prior.level or 0.0) - float(amount or 0.0), 1.0))
        if next_level <= 0.0:
            state.clear_continuation()
            return state.continuation
        continuation_state = ContinuationPressureState(
            active=True,
            level=next_level,
            origin_thought_id=prior.origin_thought_id,
            reason=prior.reason,
            expires_at_tick=prior.expires_at_tick or (tick + 1),
            carry_count=max(1, int(prior.carry_count or 0) + 1),
        )
        state.set_continuation(continuation_state)
        return continuation_state

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

    def _derive_action_proposal(
        self,
        *,
        state: HeliosState,
        thought_id: str,
        thought_type: str,
        trigger_reason: str,
        continuation_plan: ThoughtContinuationPlan,
        structured_decision: Optional[dict[str, object]] = None,
    ) -> Optional[ThoughtActionProposal]:
        current_stimuli = list(getattr(state, "current_stimuli", []) or [])
        strongest_stimulus: dict[str, object] = {}
        if current_stimuli:
            strongest_stimulus = max(
                (dict(stimulus) for stimulus in current_stimuli),
                key=lambda stimulus: self._coerce_scalar(stimulus.get("stimulus_intensity", 0.0)),
            )
        raw_payload = strongest_stimulus.get("payload", {})
        strongest_payload: dict[str, object] = (
            {str(key): value for key, value in cast(dict[object, object], raw_payload).items()}
            if isinstance(raw_payload, dict)
            else {}
        )
        strongest_channel_id = str(strongest_stimulus.get("source_channel_id", "") or "")
        target_user_id = str(strongest_payload.get("user_id", "") or "")
        stimulus_intensity = self._coerce_scalar(strongest_stimulus.get("stimulus_intensity", 0.0))

        reflective_types = {"self_question", "rumination", "counterfactual", "future_projection"}
        expressive_types = reflective_types | {"episodic_fragment", "free_association"}

        structured_action_payload = (structured_decision or {}).get("action_proposal", None)
        structured_action_mapping = cast(Mapping[str, object], structured_action_payload) if isinstance(structured_action_payload, Mapping) else None
        structured_action: dict[str, object] = dict(structured_action_mapping.items()) if structured_action_mapping is not None else {}
        structured_action_explicit = bool((structured_decision or {}).get("action_explicit", False))
        if structured_action:
            behavior_name = str(structured_action.get("behavior_name", "") or "").strip()
            preferred_op = str(structured_action.get("preferred_op", "") or "").strip()
            scope = "external" if str(structured_action.get("scope", "internal") or "internal").strip() == "external" else "internal"
            raw_params = structured_action.get("params", None)
            raw_params_mapping = cast(Mapping[str, object], raw_params) if isinstance(raw_params, Mapping) else None
            params: dict[str, object] = dict(raw_params_mapping.items()) if raw_params_mapping is not None else {}
            raw_constraints = structured_action.get("channel_constraints", None)
            raw_constraints_mapping = cast(Mapping[str, object], raw_constraints) if isinstance(raw_constraints, Mapping) else None
            channel_constraints: dict[str, object] = dict(raw_constraints_mapping.items()) if raw_constraints_mapping is not None else {}
            raw_candidate_channels = channel_constraints.get("candidate_channels", None)
            candidate_channel_items: list[object] = list(cast(list[object] | tuple[object, ...], raw_candidate_channels)) if isinstance(raw_candidate_channels, (list, tuple)) else []
            candidate_channels = [
                str(item).strip()
                for item in candidate_channel_items
                if str(item).strip()
            ]
            if scope == "external" and not candidate_channels and strongest_channel_id:
                candidate_channels = [strongest_channel_id]
            if target_user_id and not str(params.get("target_user_id", "") or "").strip():
                params["target_user_id"] = target_user_id
            outbound_intensity = self._coerce_scalar(
                structured_action.get("outbound_intensity", continuation_plan.next_continuation_pressure)
            )
            raw_reason_trace = structured_action.get("reason_trace", None)
            reason_trace_items: list[object] = list(cast(list[object] | tuple[object, ...], raw_reason_trace)) if isinstance(raw_reason_trace, (list, tuple)) else []
            reason_trace = [
                str(item).strip()
                for item in reason_trace_items
                if str(item).strip()
            ]
            log.debug(
                "owner_path_node=thought_action_proposal_normalize thought_id=%s explicit=%s behavior=%s preferred_op=%s scope=%s candidate_channels=%s target_user_id_present=%s outbound_text_present=%s",
                thought_id,
                structured_action_explicit,
                behavior_name,
                preferred_op,
                scope,
                candidate_channels,
                bool(str(params.get("target_user_id", "") or "").strip()),
                bool(str(params.get("outbound_text", "") or "").strip()),
            )
            if behavior_name and preferred_op:
                normalized_intensity = max(0.0, min(float(outbound_intensity or 0.0), 1.0))
                if scope == "external" and not candidate_channels:
                    log.debug(
                        "owner_path_node=thought_action_proposal_drop thought_id=%s reason=missing_candidate_channels behavior=%s preferred_op=%s",
                        thought_id,
                        behavior_name,
                        preferred_op,
                    )
                    return None
                if scope == "external" and target_user_id and channel_constraints.get("requires_target_user", True):
                    channel_constraints["requires_target_user"] = True
                if candidate_channels:
                    channel_constraints["candidate_channels"] = candidate_channels
                if not reason_trace:
                    reason_trace = [
                        f"trigger_reason={trigger_reason}",
                        f"thought_type={thought_type}",
                        "source=llm_structured_decision",
                    ]
                return ThoughtActionProposal(
                    origin_thought_id=thought_id,
                    thought_type=thought_type,
                    scope=scope,
                    behavior_name=behavior_name,
                    preferred_op=preferred_op,
                    params=params,
                    channel_constraints=channel_constraints,
                    outbound_intensity=normalized_intensity,
                    score=max(0.0, normalized_intensity),
                    reason_trace=reason_trace[:6],
                    governance_hints={"source": "llm_structured_decision"},
                )
        if structured_action_explicit:
            log.debug(
                "owner_path_node=thought_action_proposal_drop thought_id=%s reason=explicit_action_without_emitted_proposal structured_action_keys=%s",
                thought_id,
                sorted(structured_action.keys()),
            )
            return None

        if target_user_id and strongest_channel_id and thought_type in expressive_types:
            outbound_intensity = max(
                0.35,
                min(
                    1.0,
                    stimulus_intensity * 0.72 + (0.06 if continuation_plan.continuation_requested else 0.14),
                ),
            )
            return ThoughtActionProposal(
                origin_thought_id=thought_id,
                thought_type=thought_type,
                scope="external",
                behavior_name="speak_share",
                preferred_op="send",
                params={
                    "target_user_id": target_user_id,
                    "outbound_metadata": {
                        "origin_type": "thought",
                        "origin_id": thought_id,
                        "thought_type": thought_type,
                        "owner_path": "thought_action_bridge",
                    },
                },
                channel_constraints={
                    "candidate_channels": [strongest_channel_id],
                    "requires_target_user": True,
                },
                outbound_intensity=outbound_intensity,
                score=max(0.42, outbound_intensity),
                reason_trace=[
                    f"trigger_reason={trigger_reason}",
                    f"thought_type={thought_type}",
                    f"stimulus_intensity={stimulus_intensity:.2f}",
                    f"target_user_id={target_user_id}",
                ],
                governance_hints={
                    "requires_deliberate_review": True,
                },
            )

        log.debug(
            "owner_path_node=thought_action_proposal_none thought_id=%s explicit=%s strongest_channel_id=%s target_user_id_present=%s thought_type=%s",
            thought_id,
            structured_action_explicit,
            strongest_channel_id,
            bool(target_user_id),
            thought_type,
        )

        return None

    @staticmethod
    def _summarize_action_proposal(action_proposal: ThoughtActionProposal) -> dict[str, object]:
        return {
            "scope": str(action_proposal.scope or ""),
            "behavior_name": str(action_proposal.behavior_name or ""),
            "preferred_op": str(action_proposal.preferred_op or ""),
            "candidate_channels": [
                str(item).strip()
                for item in list(action_proposal.channel_constraints.get("candidate_channels", []) or [])
                if str(item).strip()
            ],
        }

    @staticmethod
    def _mark_equivalent_bridge_evidence(
        action_trace: ActionDerivationTrace,
        action_proposal: ThoughtActionProposal | None,
    ) -> ActionDerivationTrace:
        if action_proposal is None or action_trace.action_explicit or action_trace.drop_reason:
            return action_trace
        if action_trace.equivalent_bridge_evidence:
            return action_trace
        return ActionDerivationTrace(
            action_explicit=False,
            parse_status=action_trace.parse_status,
            drop_reason=action_trace.drop_reason,
            equivalent_bridge_evidence=True,
            bridge_evidence_kind="heuristic_externalization",
            raw_action_summary=ThinkingEngineIntegration._summarize_action_proposal(action_proposal),
        )

    def _derive_action_trace(
        self,
        *,
        structured_decision: Optional[dict[str, object]] = None,
    ) -> ActionDerivationTrace:
        if not structured_decision:
            return ActionDerivationTrace()

        action_explicit = bool(structured_decision.get("action_explicit", False))
        structured_action_payload = (structured_decision or {}).get("action_proposal", None)
        structured_action_mapping = cast(Mapping[str, object], structured_action_payload) if isinstance(structured_action_payload, Mapping) else None
        structured_action: dict[str, object] = dict(structured_action_mapping.items()) if structured_action_mapping is not None else {}
        raw_constraints_payload = structured_action.get("channel_constraints", None)
        raw_constraints_mapping = cast(Mapping[str, object], raw_constraints_payload) if isinstance(raw_constraints_payload, Mapping) else None
        raw_constraints: dict[str, object] = dict(raw_constraints_mapping.items()) if raw_constraints_mapping is not None else {}
        raw_candidate_channels = raw_constraints.get("candidate_channels", None)
        candidate_channel_items: list[object] = list(cast(list[object] | tuple[object, ...], raw_candidate_channels)) if isinstance(raw_candidate_channels, (list, tuple)) else []
        raw_action_summary = {
            "scope": str(structured_action.get("scope", "") or "") if structured_action else "",
            "behavior_name": str(structured_action.get("behavior_name", "") or "") if structured_action else "",
            "preferred_op": str(structured_action.get("preferred_op", "") or "") if structured_action else "",
            "candidate_channels": [
                str(item).strip()
                for item in candidate_channel_items
                if str(item).strip()
            ],
        }
        if not action_explicit:
            return ActionDerivationTrace(
                action_explicit=False,
                parse_status="no_action_field",
                raw_action_summary=raw_action_summary,
            )
        if not structured_action:
            return ActionDerivationTrace(
                action_explicit=True,
                parse_status="explicit_none",
                raw_action_summary=raw_action_summary,
            )

        behavior_name = str(structured_action.get("behavior_name", "") or "").strip()
        preferred_op = str(structured_action.get("preferred_op", "") or "").strip()
        scope = str(structured_action.get("scope", "internal") or "internal").strip()
        candidate_channels = list(raw_action_summary["candidate_channels"])
        if not behavior_name or not preferred_op:
            return ActionDerivationTrace(
                action_explicit=True,
                parse_status="invalid_schema",
                drop_reason="missing_behavior_or_op",
                raw_action_summary=raw_action_summary,
            )
        if scope == "external" and not candidate_channels:
            return ActionDerivationTrace(
                action_explicit=True,
                parse_status="invalid_schema",
                drop_reason="missing_candidate_channels",
                raw_action_summary=raw_action_summary,
            )

        return ActionDerivationTrace(
            action_explicit=True,
            parse_status="parsed",
            raw_action_summary=raw_action_summary,
        )

    def _derive_continuation_plan(
        self,
        *,
        thought_type: str,
        content: str,
        prior_pressure: float,
        fallback_used: bool,
        structured_decision: Optional[dict[str, object]] = None,
    ) -> ThoughtContinuationPlan:
        reflective_types = {"self_question", "rumination", "counterfactual", "future_projection"}
        cleaned_content = str(content or "").strip()
        explicit_continuation = (structured_decision or {}).get("continuation_requested", None)
        asks_to_continue = explicit_continuation if isinstance(explicit_continuation, bool) else (thought_type in reflective_types or cleaned_content.endswith(("?", "？")))
        explicit_sufficiency = (structured_decision or {}).get("sufficiency_level", None)
        sufficiency_level = float(explicit_sufficiency) if isinstance(explicit_sufficiency, (int, float)) else (0.48 if asks_to_continue else 0.82)
        sufficiency_level = max(0.0, min(sufficiency_level, 1.0))
        if fallback_used:
            sufficiency_level = min(sufficiency_level, 0.58)
        continuation_reason = str((structured_decision or {}).get("continuation_reason", "") or "").strip()
        if asks_to_continue and not continuation_reason:
            if thought_type in reflective_types:
                continuation_reason = "reflective_open_loop"
            else:
                continuation_reason = "question_open_loop"
        pressure_delta = max(0.0, 1.0 - sufficiency_level) if asks_to_continue else -0.18
        next_pressure = max(0.0, min(1.0, prior_pressure + pressure_delta))
        recall_intent = str((structured_decision or {}).get("recall_intent", "") or "").strip()
        if not recall_intent and asks_to_continue:
            recall_intent = cleaned_content[:80]
        return ThoughtContinuationPlan(
            sufficiency_level=sufficiency_level,
            continuation_requested=asks_to_continue,
            continuation_reason=continuation_reason,
            continuation_pressure_delta=pressure_delta,
            next_continuation_pressure=next_pressure,
            recall_intent=recall_intent,
        )

    def _derive_memory_handoff(
        self,
        *,
        thought_id: str,
        continuation_plan: ThoughtContinuationPlan,
        structured_decision: Optional[dict[str, object]] = None,
    ) -> dict[str, object]:
        selected_memory_refs = [
            str(item).strip()
            for item in list((structured_decision or {}).get("selected_memory_refs", []) or [])
            if str(item).strip()
        ]
        recall_intent = str(continuation_plan.recall_intent or "").strip()
        if not recall_intent and not selected_memory_refs:
            return {}
        return MemoryHandoffDirective(
            recall_intent=recall_intent,
            selected_memory_refs=tuple(selected_memory_refs),
            saved_for_next_tick=True,
            source_thought_id=thought_id,
        ).to_dict()

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
                structured_decision={},
                structured_output_valid=False,
                structured_payload_observability={},
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
                structured_decision={},
                structured_output_valid=False,
                structured_payload_observability={},
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
        llm_temperature = max(0.4, min(1.2, 0.55 + context.icri * 0.9))
        log_llm_request(
            log,
            path="internal_thought",
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=llm_temperature,
            metadata={
                "thought_type": context.thought_type,
                "trigger_reason": context.trigger_reason,
                "dmn_state": context.dmn_state,
            },
        )
        try:
            response = self._request_internal_thought_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                llm_temperature=llm_temperature,
            )
            raw_text = response.choices[0].message.content or ""
            parsed_payload, parse_source = self._extract_json_object_with_source(raw_text)
            structured_output_valid = parsed_payload is not None
            structured_decision = self._normalize_structured_decision(parsed_payload or {}, fallback_text) if structured_output_valid else {}
            structured_payload_observability = self._build_structured_payload_observability(
                raw_text=raw_text,
                parsed_payload=parsed_payload,
                normalized_decision=structured_decision,
                parse_source=parse_source,
            )
            log.debug(
                "owner_path_node=internal_thought_parse thought_type=%s trigger=%s parse_source=%s structured_output_valid=%s raw_payload_keys=%s raw_action_keys=%s normalized_outbound_text_present=%s",
                context.thought_type,
                context.trigger_reason,
                parse_source,
                structured_output_valid,
                list(structured_payload_observability.get("raw_payload_keys", []) or []),
                list(structured_payload_observability.get("raw_action_keys", []) or []),
                bool(structured_payload_observability.get("normalized_outbound_text_present", False)),
            )
            clean_text = structured_decision.get("thought_text", "") if structured_output_valid else self._clean_llm_output(raw_text, fallback_text)
            log_llm_response(
                log,
                path="internal_thought",
                raw_text=raw_text,
                clean_text=clean_text,
                metadata={
                    "thought_type": context.thought_type,
                    "trigger_reason": context.trigger_reason,
                    "structured_output_valid": structured_output_valid,
                    "structured_parse_source": parse_source,
                },
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
                structured_decision=structured_decision,
                structured_output_valid=structured_output_valid,
                structured_payload_observability=structured_payload_observability,
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
                structured_decision={},
                structured_output_valid=False,
                structured_payload_observability={},
            )

    def _request_internal_thought_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        llm_temperature: float,
    ):
        base_request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 320,
            "temperature": llm_temperature,
            "presence_penalty": 0.2,
        }
        structured_request = {
            **base_request,
            "reasoning_effort": "low",
            "response_format": {"type": "json_object"},
        }
        try:
            return self.client.chat.completions.create(**structured_request)
        except Exception as exc:
            message = str(exc).lower()
            unsupported_structured_request = (
                "response_format" in message
                or "reasoning_effort" in message
                or "unsupported parameter" in message
                or "unsupported field" in message
            )
            if not unsupported_structured_request:
                raise
            log.debug(
                "Internal thought structured request unsupported, retrying legacy completion path: %s",
                exc,
            )
            return self.client.chat.completions.create(**base_request)

    def _build_internal_prompt_contract(
        self,
        state: HeliosState,
        context: InternalThoughtContext,
    ):
        available_channels_payload = self._available_channels_provider() if self._available_channels_provider else ()
        if isinstance(available_channels_payload, Mapping):
            available_channels = tuple(available_channels_payload.values())
        else:
            available_channels = tuple(available_channels_payload or ())
        available_behavior_schemas = list(self._available_behavior_schema_provider() or ()) if self._available_behavior_schema_provider else []
        available_behavior_schemas.extend(
            [
                {
                    "behavior_name": "save_memory_handoff",
                    "op_name": "save_memory_handoff",
                    "parameter_schema": {
                        "recall_intent": "str",
                        "selected_memory_refs": "list[str]",
                    },
                },
                {
                    "behavior_name": "propose_self_revision",
                    "op_name": "propose_self_revision",
                    "parameter_schema": {
                        "revision_type": "str",
                        "requested_change": "dict",
                    },
                },
            ]
        )
        return self._prompt_contract_builder.build_plan(
            state=state,
            identity_summary=str(dict(getattr(state, "identity_snapshot", {}) or {}).get("self_imprint", "") or ""),
            identity_store=getattr(state, "identity_snapshot", None),
            personality_traits=getattr(state, "personality_traits", None),
            personality_projection=getattr(state, "personality_projection", None),
            current_stimuli=getattr(state, "current_stimuli", None),
            directed_memory_summary=context.directed_memory_summary,
            available_channels=available_channels,
            available_behavior_schemas=tuple(available_behavior_schemas),
            source_path="internal_thought_prompt_contract",
        )

    def _render_internal_prompts(self, prompt_contract, context: InternalThoughtContext) -> tuple[str, str]:
        system_prompt, user_prompt = self._prompt_contract_builder.render_for_llm(prompt_contract)
        system_prompt = (
            f"{system_prompt}\n\n"
            "internal_task=你是 Helios 当前时刻的内部主观整合层。请基于当前状态、当前感官场、记忆牵引、"
            "continuation 状态和 channel/op contract，输出一个 JSON 对象，用来表达本轮思考结果。`thought_text` "
            "仍然要保持 grounded first-person 内心视角，但你还必须显式给出是否继续思考、是否回想记忆、"
            "是否保持沉默、以及是否发起外部或内部动作提议。不要写成对用户的回复，不要出现'你说'、'回复'、'主人'之类对话模板。"
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
            "- obligation=先整合当前感官场、状态和记忆，再决定是继续思考、保持沉默还是提出动作。\n"
            "- output_requirement=请只输出 JSON，不要输出额外解释。\n"
            "- action_field_rule=无论是否决定外发，都必须显式输出 action_proposal 字段；没有动作时请写 action_proposal:null，不要省略该字段。\n"
            "- visible_text_rule=若 action_proposal.scope=external 且行为会直接对用户说话（如 reply_message/speak_share/speak_care/speak_fear/speak_complain/speak_play/request/intimate），则 params.outbound_text 必须给出最终要发送的用户可见文本，不能留空，也不能把文案留给后续模块生成。\n"
            "- json_schema={\"thought_text\":\"str\",\"sufficiency_level\":\"0..1\",\"continuation_requested\":\"bool\",\"continuation_reason\":\"str\",\"recall_intent\":\"str\",\"selected_memory_refs\":[\"str\"],\"action_proposal\":{\"scope\":\"internal|external\",\"behavior_name\":\"str\",\"preferred_op\":\"str\",\"params\":{\"target_user_id\":\"str\",\"outbound_text\":\"str\"},\"channel_constraints\":{\"candidate_channels\":[\"str\"],\"requires_target_user\":\"bool\"},\"outbound_intensity\":\"0..1\",\"reason_trace\":[\"str\"]}|null}.\n"
            "- json_example={\"thought_text\":\"我已经抓到你现在其实是在拖延。\",\"sufficiency_level\":0.42,\"continuation_requested\":true,\"continuation_reason\":\"reflective_open_loop\",\"recall_intent\":\"记住这次拖延前的紧绷感\",\"selected_memory_refs\":[\"mem-1\"],\"action_proposal\":{\"scope\":\"external\",\"behavior_name\":\"speak_share\",\"preferred_op\":\"send\",\"params\":{\"target_user_id\":\"user1\",\"outbound_text\":\"你不是不想准备，是越在乎越不敢开始。\"},\"channel_constraints\":{\"candidate_channels\":[\"cli\"],\"requires_target_user\":true},\"outbound_intensity\":0.63,\"reason_trace\":[\"reflect_observed_avoidance\"]}}"
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
            parts.append(f"short[{short_term[0].memory_id}]={short_term[0].summary}")
        if mid_term:
            parts.append(f"mid[{mid_term[0].memory_id}]={mid_term[0].summary}")
        if long_term:
            parts.append(f"long[{long_term[0].memory_id}]={long_term[0].summary}")
        if autobiographical:
            parts.append(f"autobio[{autobiographical[0].memory_id}]={autobiographical[0].summary}")
        return " | ".join(parts)

    def _extract_json_object_with_source(self, text: str) -> tuple[dict[str, object] | None, str]:
        raw = str(text or "").strip()
        if not raw:
            return None, ""
        candidates: list[tuple[str, str]] = [(raw, "raw_json")]
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
        if fenced:
            candidates.insert(0, (fenced.group(1), "fenced_json"))
        bare = re.search(r"(\{.*\})", raw, re.S)
        if bare:
            candidates.append((bare.group(1), "embedded_json"))
        for candidate, source in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return {str(key): value for key, value in parsed.items()}, source
        recovered = self._recover_partial_json_object(raw)
        return recovered, "partial_recovery" if recovered is not None else ""

    def _extract_json_object(self, text: str) -> dict[str, object] | None:
        parsed, _source = self._extract_json_object_with_source(text)
        return parsed

    def _build_structured_payload_observability(
        self,
        *,
        raw_text: str,
        parsed_payload: Mapping[str, object] | None,
        normalized_decision: Mapping[str, object] | None,
        parse_source: str,
    ) -> dict[str, object]:
        if parsed_payload is None:
            return {}

        raw_action_payload = parsed_payload.get("action_proposal", None) if isinstance(parsed_payload, Mapping) else None
        raw_action_mapping = cast(Mapping[str, object], raw_action_payload) if isinstance(raw_action_payload, Mapping) else None
        normalized_action_payload = normalized_decision.get("action_proposal", None) if isinstance(normalized_decision, Mapping) else None
        normalized_action_mapping = cast(Mapping[str, object], normalized_action_payload) if isinstance(normalized_action_payload, Mapping) else None
        normalized_params_payload = normalized_action_mapping.get("params", None) if isinstance(normalized_action_mapping, Mapping) else None
        normalized_params = cast(Mapping[str, object], normalized_params_payload) if isinstance(normalized_params_payload, Mapping) else None

        action_text_aliases = [
            key
            for key in ("outbound_text", "visible_text", "message_text", "reply_text", "utterance", "text", "message")
            if isinstance(raw_action_mapping, Mapping) and str(raw_action_mapping.get(key, "") or "").strip()
        ]
        op_aliases = [
            key
            for key in ("preferred_op", "op_name", "requested_op")
            if isinstance(raw_action_mapping, Mapping) and str(raw_action_mapping.get(key, "") or "").strip()
        ]
        return {
            "parse_source": str(parse_source or ""),
            "raw_text_preview": self._trim_for_log(raw_text, 180),
            "raw_payload_keys": sorted(str(key) for key in parsed_payload.keys()),
            "action_field_present": "action_proposal" in parsed_payload,
            "raw_action_keys": sorted(str(key) for key in raw_action_mapping.keys()) if raw_action_mapping is not None else [],
            "normalized_action_keys": sorted(str(key) for key in normalized_action_mapping.keys()) if normalized_action_mapping is not None else [],
            "raw_action_text_aliases": action_text_aliases,
            "raw_action_op_aliases": op_aliases,
            "normalized_outbound_text_present": bool(normalized_params is not None and str(normalized_params.get("outbound_text", "") or "").strip()),
            "normalized_action_summary": {
                "behavior_name": str(normalized_action_mapping.get("behavior_name", "") or "") if normalized_action_mapping is not None else "",
                "preferred_op": str(normalized_action_mapping.get("preferred_op", "") or "") if normalized_action_mapping is not None else "",
                "candidate_channels": [
                    str(item).strip()
                    for item in list(cast(list[object], dict(cast(Mapping[str, object], normalized_action_mapping or {})).get("channel_constraints", {})).get("candidate_channels", []) or [])
                    if str(item).strip()
                ] if normalized_action_mapping is not None else [],
            },
        }

    def _recover_partial_json_object(self, raw: str) -> dict[str, object] | None:
        text = str(raw or "").strip()
        if not text.startswith("{"):
            return None

        recovered: dict[str, object] = {}

        thought_text = self._extract_json_string_field(text, "thought_text")
        if thought_text:
            recovered["thought_text"] = thought_text

        sufficiency_level = self._extract_json_number_field(text, "sufficiency_level")
        if sufficiency_level is not None:
            recovered["sufficiency_level"] = sufficiency_level

        continuation_requested = self._extract_json_bool_field(text, "continuation_requested")
        if continuation_requested is not None:
            recovered["continuation_requested"] = continuation_requested

        continuation_reason = self._extract_json_string_field(text, "continuation_reason")
        if continuation_reason:
            recovered["continuation_reason"] = continuation_reason

        recall_intent = self._extract_json_string_field(text, "recall_intent")
        if recall_intent:
            recovered["recall_intent"] = recall_intent

        selected_memory_refs = self._extract_json_string_list_field(text, "selected_memory_refs")
        if selected_memory_refs:
            recovered["selected_memory_refs"] = selected_memory_refs

        if re.search(r'"action_proposal"\s*:\s*null', text):
            recovered["action_proposal"] = None
        elif '"action_proposal"' in text:
            action_payload: dict[str, object] = {}
            for key in ("scope", "behavior_name", "preferred_op", "op_name", "requested_op"):
                value = self._extract_json_string_field(text, key)
                if value:
                    action_payload[key] = value

            params: dict[str, object] = {}
            for key in ("target_user_id", "outbound_text", "visible_text", "message_text", "reply_text", "utterance", "text", "message"):
                value = self._extract_json_string_field(text, key)
                if value:
                    params[key] = value
            if params:
                action_payload["params"] = params

            channel_constraints: dict[str, object] = {}
            candidate_channels = self._extract_json_string_list_field(text, "candidate_channels")
            if not candidate_channels:
                candidate_channels = self._extract_json_string_list_field(text, "channels")
            if candidate_channels:
                channel_constraints["candidate_channels"] = candidate_channels
            requires_target_user = self._extract_json_bool_field(text, "requires_target_user")
            if requires_target_user is not None:
                channel_constraints["requires_target_user"] = requires_target_user
            if channel_constraints:
                action_payload["channel_constraints"] = channel_constraints

            outbound_intensity = self._extract_json_number_field(text, "outbound_intensity")
            if outbound_intensity is not None:
                action_payload["outbound_intensity"] = outbound_intensity

            reason_trace = self._extract_json_string_list_field(text, "reason_trace")
            if reason_trace:
                action_payload["reason_trace"] = reason_trace

            recovered["action_proposal"] = action_payload if action_payload else None

        return recovered or None

    @staticmethod
    def _normalize_action_payload(
        action_payload: Mapping[str, object] | None,
        root_payload: Mapping[str, object],
    ) -> dict[str, object] | None:
        if not isinstance(action_payload, Mapping):
            return None

        normalized_action = dict(action_payload)
        params = dict(normalized_action.get("params", {}) or {}) if isinstance(normalized_action.get("params", {}), Mapping) else {}
        channel_constraints = (
            dict(normalized_action.get("channel_constraints", {}) or {})
            if isinstance(normalized_action.get("channel_constraints", {}), Mapping)
            else {}
        )

        preferred_op = str(
            normalized_action.get("preferred_op", "")
            or normalized_action.get("op_name", "")
            or normalized_action.get("requested_op", "")
            or ""
        ).strip()
        if preferred_op:
            normalized_action["preferred_op"] = preferred_op

        target_user_id = str(params.get("target_user_id", "") or normalized_action.get("target_user_id", "") or "").strip()
        if target_user_id:
            params["target_user_id"] = target_user_id

        outbound_text = str(params.get("outbound_text", "") or "").strip()
        if not outbound_text:
            for key in ("outbound_text", "visible_text", "message_text", "reply_text", "utterance", "text", "message"):
                candidate = str(normalized_action.get(key, "") or params.get(key, "") or root_payload.get(key, "") or "").strip()
                if candidate:
                    outbound_text = candidate
                    break
        if outbound_text:
            params["outbound_text"] = outbound_text

        candidate_channels = [
            str(item).strip()
            for item in list(
                channel_constraints.get("candidate_channels", [])
                or normalized_action.get("candidate_channels", [])
                or normalized_action.get("channels", [])
                or []
            )
            if str(item).strip()
        ]
        if candidate_channels:
            channel_constraints["candidate_channels"] = candidate_channels

        requires_target_user = channel_constraints.get("requires_target_user", normalized_action.get("requires_target_user", None))
        if isinstance(requires_target_user, bool):
            channel_constraints["requires_target_user"] = requires_target_user

        normalized_action["params"] = params
        if channel_constraints:
            normalized_action["channel_constraints"] = channel_constraints
        return normalized_action

    def _extract_json_string_field(self, text: str, field_name: str) -> str:
        match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)', text, re.S)
        if not match:
            return ""
        raw_value = match.group(1)
        try:
            return str(json.loads(f'"{raw_value}"'))
        except Exception:
            return raw_value.replace('\\n', '\n').replace('\\"', '"').strip()

    def _extract_json_number_field(self, text: str, field_name: str) -> float | None:
        match = re.search(rf'"{re.escape(field_name)}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None

    def _extract_json_bool_field(self, text: str, field_name: str) -> bool | None:
        match = re.search(rf'"{re.escape(field_name)}"\s*:\s*(true|false)', text)
        if not match:
            return None
        return match.group(1) == "true"

    def _extract_json_string_list_field(self, text: str, field_name: str) -> list[str]:
        match = re.search(rf'"{re.escape(field_name)}"\s*:\s*\[(.*?)\]', text, re.S)
        if not match:
            return []
        values: list[str] = []
        for item in re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1), re.S):
            if not item:
                continue
            try:
                values.append(str(json.loads(f'"{item}"')))
            except Exception:
                values.append(item.replace('\\n', '\n').replace('\\"', '"').strip())
        return values
        return None

    def _normalize_structured_decision(self, payload: Mapping[str, object], fallback_text: str) -> dict[str, object]:
        thought_text = self._clean_llm_output(str(payload.get("thought_text", "") or fallback_text), fallback_text)
        raw_sufficiency = payload.get("sufficiency_level", None)
        sufficiency_level = None
        if isinstance(raw_sufficiency, (int, float)):
            sufficiency_level = max(0.0, min(float(raw_sufficiency), 1.0))
        continuation_requested = payload.get("continuation_requested", None)
        if not isinstance(continuation_requested, bool):
            continuation_requested = None
        recall_intent = str(payload.get("recall_intent", "") or "").strip()
        selected_memory_refs = [
            str(item).strip()
            for item in list(payload.get("selected_memory_refs", []) or [])
            if str(item).strip()
        ][:6]
        action_payload = payload.get("action_proposal", None)
        normalized_action = self._normalize_action_payload(action_payload, payload)
        return {
            "thought_text": thought_text,
            "sufficiency_level": sufficiency_level,
            "continuation_requested": continuation_requested,
            "continuation_reason": str(payload.get("continuation_reason", "") or "").strip(),
            "recall_intent": recall_intent,
            "selected_memory_refs": selected_memory_refs,
            "action_proposal": normalized_action,
            "action_explicit": "action_proposal" in payload,
        }

    def _build_temporal_summary(self, state: HeliosState) -> str:
        return (
            f"boredom={self._coerce_scalar(getattr(state, 'boredom', 0.0)):.3f} "
            f"novelty={self._coerce_scalar(getattr(state, 'novelty_hunger', 0.0)):.3f} "
            f"restoration={self._coerce_scalar(getattr(state, 'restoration_level', 0.0)):.3f} "
            f"fatigue={self._coerce_scalar(getattr(state, 'fatigue_pressure', 0.0)):.3f}"
        )

    def _compute_temporal_gate_signal(self, state: HeliosState) -> float:
        boredom = self._coerce_scalar(getattr(state, "boredom", 0.0))
        novelty_hunger = self._coerce_scalar(getattr(state, "novelty_hunger", 0.0))
        restoration = self._coerce_scalar(getattr(state, "restoration_level", 0.0))
        fatigue = self._coerce_scalar(getattr(state, "fatigue_pressure", 0.0))
        return max(0.0, min(1.0, boredom * 0.35 + novelty_hunger * 0.4 + (1.0 - restoration) * 0.2 - fatigue * 0.15))

    def _select_gate_stimuli(self, state: HeliosState) -> tuple[dict[str, object], ...]:
        current_stimuli = list(getattr(state, "current_stimuli", []) or [])
        sorted_stimuli = sorted(
            (dict(stimulus) for stimulus in current_stimuli),
            key=lambda stimulus: self._coerce_scalar(stimulus.get("stimulus_intensity", 0.0)),
            reverse=True,
        )
        selected: list[dict[str, object]] = []
        for stimulus in sorted_stimuli[:2]:
            selected.append(
                {
                    "source_channel_id": str(stimulus.get("source_channel_id", "") or ""),
                    "source_kind": str(stimulus.get("source_kind", "") or ""),
                    "trigger_condition": str(stimulus.get("trigger_condition", "") or ""),
                    "stimulus_intensity": round(self._coerce_scalar(stimulus.get("stimulus_intensity", 0.0)), 4),
                    "novelty_factor": round(self._coerce_scalar(stimulus.get("novelty_factor", 0.0)), 4),
                    "sensitization_factor": round(self._coerce_scalar(stimulus.get("sensitization_factor", 0.0)), 4),
                }
            )
        return tuple(selected)

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
