"""Structured interaction policy for passive expressive behavior selection."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Dict, List, Optional, Sequence
from uuid import uuid4

from .action_models import ActionProposal
from neurochem_gate import NeurochemGate, resolve_neurochem_gate
from personality_projection import PersonalityProjection, resolve_personality_projection
from temporal_gate import TemporalGate, resolve_temporal_gate


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scalar(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    current = getattr(value, "current", value)
    try:
        return float(current)
    except (TypeError, ValueError):
        return default


@dataclass
class InteractionSignals:
    goal_relevance: float
    novelty: float
    urgency: float
    positive_affinity: float
    protective_pull: float
    fatigue_pressure: float
    resource_pressure: float
    direct_message: bool
    message_is_question: bool
    source_channel_id: str
    available_channels: List[str] = field(default_factory=list)
    available_modalities: List[str] = field(default_factory=list)
    recent_exchange_count: int = 0
    recent_reply_gap: int = 0
    dominant_system: str = ""
    valence: float = 0.0
    arousal: float = 0.0
    oxytocin: float = 0.0
    cortisol: float = 0.0
    allostatic_load: float = 0.0
    drive_urgency: float = 0.0
    personality_traits: Dict[str, float] = field(default_factory=dict)
    personality_projection: Optional[PersonalityProjection] = None
    temporal_gate: Optional[TemporalGate] = None
    neurochem_gate: Optional[NeurochemGate] = None


@dataclass
class InteractionAssessment:
    wants_response: bool
    interaction_score: float
    primary_behavior: str
    candidate_behaviors: List[str] = field(default_factory=list)
    preferred_modalities: List[str] = field(default_factory=list)
    candidate_channels: List[str] = field(default_factory=list)
    reason_summary: str = ""
    feature_bundle: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, object] = field(default_factory=dict)
    rationale: List[str] = field(default_factory=list)


class InteractionPolicy:
    """Choose passive expressive behaviors from structured interaction state."""

    QUESTION_RE = re.compile(r"\?|？|吗$|嘛$|呢$|what|why|how|when|where|who", re.IGNORECASE)

    def __init__(
        self,
        *,
        reply_threshold: float = 0.34,
        intimate_threshold: float = 0.92,
        request_threshold: float = 0.84,
    ):
        self._reply_threshold = reply_threshold
        self._intimate_threshold = intimate_threshold
        self._request_threshold = request_threshold

    def collect_signals(
        self,
        message: dict,
        sec_result: dict,
        state,
        *,
        available_channels: Optional[Sequence[str]] = None,
        recent_history: Optional[Sequence[object]] = None,
    ) -> InteractionSignals:
        traits = dict(getattr(state, "personality_traits", {}) or {})
        projection = resolve_personality_projection(
            projection=getattr(state, "personality_projection", None),
            traits=traits,
        )
        temporal_gate = resolve_temporal_gate(state=state)
        neurochem_gate = resolve_neurochem_gate(state=state)
        goal_relevance = float(sec_result.get("goal_relevance", 0.0))
        novelty = float(sec_result.get("novelty", 0.0))
        urgency = _clamp(goal_relevance * 0.62 + novelty * 0.38, 0.0, 1.0)
        available_channel_ids = [channel_id for channel_id in (available_channels or []) if channel_id]
        source_channel = str(message.get("channel_id") or "")
        if source_channel and source_channel not in available_channel_ids:
            available_channel_ids.insert(0, source_channel)

        available_modalities = ["text"]
        if "tts" in available_channel_ids:
            available_modalities.append("speech")

        recent_exchange_count = len(list(recent_history or []))
        recent_reply_gap = 0
        for exchange in reversed(list(recent_history or [])):
            reply_text = getattr(exchange, "assistant_reply", None)
            if reply_text:
                break
            recent_reply_gap += 1

        positive_affinity = _clamp(
            projection.interaction_bias * 0.55
            + projection.style("warmth") * 0.14
            + max(_scalar(getattr(state, "valence", 0.0)), 0.0) * 0.18
            + _scalar(getattr(state, "oxytocin", 0.0)) * 0.18
            + min(recent_exchange_count, 4) * 0.03,
            -0.25,
            0.55,
        )
        protective_pull = _clamp(
            projection.style("caution") * 0.18
            + max(_scalar(getattr(state, "cortisol", 0.0)) - 0.25, 0.0) * 0.35
            + (0.12 if str(getattr(state, "dominant_system", "")).upper() in {"CARE", "PANIC"} else 0.0)
            + (0.08 if self._message_mentions_connection(str(message.get("text", ""))) else 0.0),
            0.0,
            0.6,
        )
        fatigue_pressure = _clamp(
            _scalar(getattr(state, "allostatic_load", 0.0)) * 0.42
            + (0.22 if bool(getattr(state, "is_fatigued", False)) else 0.0),
            0.0,
            0.7,
        )
        resource_pressure = _clamp(
            max(int(getattr(state, "behavior_queue_depth", 0)) - 1, 0) * 0.12
            + (0.08 if getattr(state, "current_behavior", "") else 0.0),
            0.0,
            0.45,
        )

        return InteractionSignals(
            goal_relevance=goal_relevance,
            novelty=novelty,
            urgency=urgency,
            positive_affinity=positive_affinity,
            protective_pull=protective_pull,
            fatigue_pressure=fatigue_pressure,
            resource_pressure=resource_pressure,
            direct_message=not bool(message.get("is_group", False)),
            message_is_question=bool(self.QUESTION_RE.search(str(message.get("text", "")))),
            source_channel_id=source_channel,
            available_channels=available_channel_ids,
            available_modalities=available_modalities,
            recent_exchange_count=recent_exchange_count,
            recent_reply_gap=recent_reply_gap,
            dominant_system=str(getattr(state, "dominant_system", "") or ""),
            valence=_scalar(getattr(state, "valence", 0.0)),
            arousal=_scalar(getattr(state, "arousal", 0.0)),
            oxytocin=_scalar(getattr(state, "oxytocin", 0.0)),
            cortisol=_scalar(getattr(state, "cortisol", 0.0)),
            allostatic_load=_scalar(getattr(state, "allostatic_load", 0.0)),
            drive_urgency=_scalar(getattr(state, "drive_urgency", 0.0)),
            personality_traits=projection.raw_traits or traits,
            personality_projection=projection,
            temporal_gate=temporal_gate,
            neurochem_gate=neurochem_gate,
        )

    def assess(self, message: dict, signals: InteractionSignals) -> InteractionAssessment:
        projection = signals.personality_projection or resolve_personality_projection(traits=signals.personality_traits)
        temporal_gate = signals.temporal_gate or resolve_temporal_gate()
        neurochem_gate = signals.neurochem_gate or resolve_neurochem_gate()
        message_mentions_connection = self._message_mentions_connection(str(message.get("text", "")))
        interaction_score = _clamp(
            signals.urgency
            + signals.positive_affinity
            + signals.protective_pull
            + min(signals.recent_reply_gap, 3) * 0.05
            - projection.social_threshold_shift
            - temporal_gate.reply_threshold_shift
            - neurochem_gate.reply_threshold_shift
            - signals.fatigue_pressure
            - signals.resource_pressure,
            0.0,
            1.5,
        )
        semantic_signal = signals.goal_relevance + signals.novelty + signals.protective_pull
        semantic_gate_open = (
            semantic_signal >= 0.30
            or signals.message_is_question
            or message_mentions_connection
        )

        wants_response = bool(signals.available_channels) and semantic_gate_open and interaction_score >= self._reply_threshold
        preferred_modalities = list(signals.available_modalities or ["text"])
        candidate_channels = list(signals.available_channels)
        reasons = [
            f"urgency={signals.urgency:.2f}",
            f"affinity={signals.positive_affinity:.2f}",
            f"protective={signals.protective_pull:.2f}",
            f"fatigue={signals.fatigue_pressure:.2f}",
            f"resource={signals.resource_pressure:.2f}",
        ]

        candidate_behaviors: List[str] = []
        primary_behavior = ""
        reply_score = interaction_score + neurochem_gate.bias_for_behavior("reply_message") + temporal_gate.bias_for_behavior("reply_message")
        intimate_score = interaction_score + neurochem_gate.bias_for_behavior("intimate") + temporal_gate.bias_for_behavior("intimate")
        intimate_eligible = (message_mentions_connection or signals.protective_pull > 0.24) and not neurochem_gate.constrained("avoid_intimate") and not temporal_gate.constrained("avoid_high_expression")
        if signals.direct_message:
            intimate_score += signals.protective_pull * 0.5
            intimate_score += 0.08 if signals.dominant_system.upper() in {"CARE", "PANIC"} else 0.0
            intimate_score += projection.bias_for_behavior("intimate") * 0.35
            intimate_score += projection.style("self_disclosure") * 0.08
            intimate_score -= 0.18 if signals.message_is_question else 0.0
        request_score = interaction_score
        request_score += 0.16 if signals.message_is_question else 0.0
        request_score += 0.10 if signals.novelty > 0.55 else 0.0
        request_score += projection.bias_for_behavior("request") * 0.35
        request_score += neurochem_gate.bias_for_behavior("request")
        request_score += temporal_gate.bias_for_behavior("request")
        request_score += projection.style("directness") * 0.05
        request_eligible = (signals.message_is_question and signals.novelty > 0.45) or signals.novelty > 0.70
        intimate_threshold = self._intimate_threshold + neurochem_gate.intimate_threshold_shift + temporal_gate.intimate_threshold_shift
        request_threshold = self._request_threshold + max(neurochem_gate.caution_bias * 0.05 - neurochem_gate.initiative_bias * 0.04, -0.06)

        if wants_response:
            if signals.direct_message and intimate_eligible and intimate_score >= intimate_threshold:
                primary_behavior = "intimate"
                candidate_behaviors.append("intimate")
                reasons.append(f"intimate_score={intimate_score:.2f}")
            elif request_eligible and request_score >= request_threshold:
                primary_behavior = "request"
                candidate_behaviors.append("request")
                reasons.append(f"request_score={request_score:.2f}")
            else:
                primary_behavior = "reply_message"
                candidate_behaviors.append("reply_message")
                reasons.append(f"reply_score={reply_score:.2f}")

            if primary_behavior != "reply_message":
                candidate_behaviors.append("reply_message")
            if request_eligible and primary_behavior != "request" and request_score >= request_threshold - 0.08:
                candidate_behaviors.append("request")
            if primary_behavior != "intimate" and signals.direct_message and intimate_eligible and intimate_score >= intimate_threshold - 0.08:
                candidate_behaviors.append("intimate")

        candidate_behaviors = list(dict.fromkeys(candidate_behaviors))

        personality_trace = {
            "interaction_bias": projection.interaction_bias,
            "initiative_bias": projection.initiative_bias,
            "risk_tolerance_bias": projection.risk_tolerance_bias,
            "social_threshold_shift": projection.social_threshold_shift,
            "novelty_bias": projection.novelty_bias,
            "persistence_bias": projection.persistence_bias,
            "expressivity_bias": projection.expressivity_bias,
            "self_disclosure_bias": projection.self_disclosure_bias,
        }

        return InteractionAssessment(
            wants_response=wants_response,
            interaction_score=interaction_score,
            primary_behavior=primary_behavior,
            candidate_behaviors=candidate_behaviors,
            preferred_modalities=preferred_modalities,
            candidate_channels=candidate_channels,
            reason_summary=(
                "Structured interaction policy accepted the inbound message."
                if wants_response
                else "Structured interaction policy declined to respond."
            ),
            feature_bundle={
                "goal_relevance": signals.goal_relevance,
                "novelty": signals.novelty,
                "urgency": signals.urgency,
                "positive_affinity": signals.positive_affinity,
                "protective_pull": signals.protective_pull,
                "fatigue_pressure": signals.fatigue_pressure,
                "resource_pressure": signals.resource_pressure,
                "personality_interaction_bias": projection.interaction_bias,
                "personality_initiative_bias": projection.initiative_bias,
                "personality_risk_tolerance": projection.risk_tolerance,
                "personality_social_threshold_shift": projection.social_threshold_shift,
                "temporal_interaction_readiness": temporal_gate.interaction_readiness,
                "temporal_exploration_pressure": temporal_gate.exploration_pressure,
                "temporal_restorative_pull": temporal_gate.restorative_pull,
                "temporal_reply_threshold_shift": temporal_gate.reply_threshold_shift,
                "temporal_intimate_threshold_shift": temporal_gate.intimate_threshold_shift,
                "neurochem_social_affinity": neurochem_gate.social_affinity,
                "neurochem_initiative_bias": neurochem_gate.initiative_bias,
                "neurochem_caution_bias": neurochem_gate.caution_bias,
                "neurochem_reply_threshold_shift": neurochem_gate.reply_threshold_shift,
                "neurochem_intimate_threshold_shift": neurochem_gate.intimate_threshold_shift,
                "interaction_score": interaction_score,
                "reply_score": reply_score,
                "request_score": request_score,
                "intimate_score": intimate_score,
            },
            constraints={
                "reply_required": wants_response,
                "direct_message": signals.direct_message,
                "message_is_question": signals.message_is_question,
                "source_channel_id": signals.source_channel_id,
                "required_capabilities": ["send"],
                "avoid_high_expression": temporal_gate.constrained("avoid_high_expression"),
                "avoid_intimate": neurochem_gate.constrained("avoid_intimate"),
            },
            rationale=reasons + [f"personality_trace={personality_trace}"],
        )

    def propose(
        self,
        message: dict,
        sec_result: dict,
        state,
        *,
        available_channels: Optional[Sequence[str]] = None,
        recent_history: Optional[Sequence[object]] = None,
    ) -> List[ActionProposal]:
        signals = self.collect_signals(
            message,
            sec_result,
            state,
            available_channels=available_channels,
            recent_history=recent_history,
        )
        projection = signals.personality_projection or resolve_personality_projection(traits=signals.personality_traits)
        temporal_gate = signals.temporal_gate or resolve_temporal_gate(state=state)
        neurochem_gate = signals.neurochem_gate or resolve_neurochem_gate(state=state)
        assessment = self.assess(message, signals)
        if not assessment.wants_response:
            return []

        proposals: List[ActionProposal] = []
        behavior_offsets = {
            "reply_message": 0.0,
            "request": 0.05,
            "intimate": 0.07,
        }
        for behavior_name in assessment.candidate_behaviors:
            final_score = _clamp(
                assessment.feature_bundle["interaction_score"]
                + behavior_offsets.get(behavior_name, 0.0)
                + temporal_gate.bias_for_behavior(behavior_name)
                + neurochem_gate.bias_for_behavior(behavior_name),
                0.0,
                1.5,
            )
            proposals.append(
                ActionProposal(
                    proposal_id=f"proposal::interaction::{uuid4().hex}",
                    source_type="interaction",
                    source_module="interaction_policy",
                    intent_type="respond",
                    behavior_name=behavior_name,
                    reason_summary=assessment.reason_summary,
                    score_bundle={
                        **assessment.feature_bundle,
                        "final": final_score,
                    },
                    constraints={
                        **assessment.constraints,
                        "message_id": message.get("message_id", ""),
                    },
                    suggested_modalities=list(assessment.preferred_modalities),
                    candidate_channels=list(assessment.candidate_channels),
                    parameters={
                        "target_user_id": message.get("user_id", "unknown"),
                        "outbound_metadata": {
                            "message_id": message.get("message_id", ""),
                            "is_group": message.get("is_group", False),
                            "group_id": message.get("group_id", ""),
                        },
                        "source_message_text": message.get("text", ""),
                        "tick": int(getattr(state, "tick", 0)),
                    },
                    provenance={
                        "message_text": message.get("text", ""),
                        "user_id": message.get("user_id", "unknown"),
                        "sec_result": dict(sec_result),
                        "signals": assessment.feature_bundle,
                        "rationale": list(assessment.rationale),
                        "personality_influence_trace": {
                            "projection": {
                                "interaction_bias": projection.interaction_bias,
                                "initiative_bias": projection.initiative_bias,
                                "risk_tolerance_bias": projection.risk_tolerance_bias,
                                "novelty_bias": projection.novelty_bias,
                                "persistence_bias": projection.persistence_bias,
                                "expressivity_bias": projection.expressivity_bias,
                                "self_disclosure_bias": projection.self_disclosure_bias,
                            },
                            "temporal_gate": dict(temporal_gate.personality_influence_trace),
                            "neurochem_gate": dict(neurochem_gate.personality_influence_trace),
                        },
                        "personality_projection": projection.to_dict(),
                        "temporal_gate": temporal_gate.to_dict(),
                        "neurochem_gate": neurochem_gate.to_dict(),
                    },
                    created_at_tick=int(getattr(state, "tick", 0)),
                    created_at_ts=float(getattr(state, "timestamp", time.time())),
                )
            )

        proposals.sort(key=lambda proposal: proposal.score_bundle.get("final", 0.0), reverse=True)
        return proposals

    @staticmethod
    def _message_mentions_connection(text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in ["想你", "miss", "陪", "在吗", "在么", "抱抱", "想念"])