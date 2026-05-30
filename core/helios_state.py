"""Unified state object passed through all modules each tick.

HeliosState is the single source of truth for a tick — created fresh at the
start of each tick and progressively populated as the pipeline executes.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class ContinuationPressureState:
    """Formal multi-tick continuation owner carried across thought cycles."""

    active: bool = False
    level: float = 0.0
    origin_thought_id: str = ""
    reason: str = ""
    expires_at_tick: int = 0
    carry_count: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "active": bool(self.active and self.level > 0.0),
            "level": round(float(self.level), 4),
            "origin_thought_id": self.origin_thought_id,
            "reason": self.reason,
            "expires_at_tick": int(self.expires_at_tick or 0),
            "carry_count": int(self.carry_count or 0),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ContinuationPressureState":
        if not isinstance(payload, dict):
            return cls()
        level = max(0.0, min(float(payload.get("level", 0.0) or 0.0), 1.0))
        return cls(
            active=bool(payload.get("active", level > 0.0)),
            level=level,
            origin_thought_id=str(payload.get("origin_thought_id", "") or ""),
            reason=str(payload.get("reason", "") or ""),
            expires_at_tick=int(payload.get("expires_at_tick", 0) or 0),
            carry_count=max(0, int(payload.get("carry_count", 0) or 0)),
        )


@dataclass(frozen=True)
class ProactiveObservabilityState:
    """Formal runtime export for the proactive-drive path."""

    evaluated: bool = False
    drive_score: float = 0.0
    drive_dominant: str = ""
    drive_urgency: float = 0.0
    drive_sources: list[str] = field(default_factory=list)
    wants_regulation: bool = False
    selected_action: str = ""
    selected_score: float = 0.0
    reason_summary: str = ""
    candidate_count: int = 0
    candidate_actions: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    dominant_emotions: list[str] = field(default_factory=list)
    deviation_sources: list[str] = field(default_factory=list)
    dominant_disposition: str = ""
    social_outward_pressure: float = 0.0
    exploration_pressure: float = 0.0
    internal_reflection_pressure: float = 0.0
    caution_pressure: float = 0.0
    accepted: bool = False
    accepted_behavior: str = ""
    selected_channel_id: str = ""
    non_externalization_reason: str = ""
    policy_rejection_reason: str = ""
    deferred: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "evaluated": bool(self.evaluated),
            "drive_score": round(float(self.drive_score or 0.0), 4),
            "drive_dominant": self.drive_dominant,
            "drive_urgency": round(float(self.drive_urgency or 0.0), 4),
            "drive_sources": [str(item) for item in list(self.drive_sources or []) if str(item)],
            "wants_regulation": bool(self.wants_regulation),
            "selected_action": self.selected_action,
            "selected_score": round(float(self.selected_score or 0.0), 4),
            "reason_summary": self.reason_summary,
            "candidate_count": max(0, int(self.candidate_count or 0)),
            "candidate_actions": [str(item) for item in list(self.candidate_actions or []) if str(item)],
            "recommended_actions": [str(item) for item in list(self.recommended_actions or []) if str(item)],
            "dominant_emotions": [str(item) for item in list(self.dominant_emotions or []) if str(item)],
            "deviation_sources": [str(item) for item in list(self.deviation_sources or []) if str(item)],
            "dominant_disposition": self.dominant_disposition,
            "social_outward_pressure": round(float(self.social_outward_pressure or 0.0), 4),
            "exploration_pressure": round(float(self.exploration_pressure or 0.0), 4),
            "internal_reflection_pressure": round(float(self.internal_reflection_pressure or 0.0), 4),
            "caution_pressure": round(float(self.caution_pressure or 0.0), 4),
            "accepted": bool(self.accepted),
            "accepted_behavior": self.accepted_behavior,
            "selected_channel_id": self.selected_channel_id,
            "non_externalization_reason": self.non_externalization_reason,
            "policy_rejection_reason": self.policy_rejection_reason,
            "deferred": bool(self.deferred),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ProactiveObservabilityState":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            evaluated=bool(payload.get("evaluated", False)),
            drive_score=max(0.0, min(float(payload.get("drive_score", 0.0) or 0.0), 1.5)),
            drive_dominant=str(payload.get("drive_dominant", "") or ""),
            drive_urgency=max(0.0, min(float(payload.get("drive_urgency", 0.0) or 0.0), 1.0)),
            drive_sources=[str(item) for item in list(payload.get("drive_sources", []) or []) if str(item)],
            wants_regulation=bool(payload.get("wants_regulation", False)),
            selected_action=str(payload.get("selected_action", "") or ""),
            selected_score=max(0.0, min(float(payload.get("selected_score", 0.0) or 0.0), 1.5)),
            reason_summary=str(payload.get("reason_summary", "") or ""),
            candidate_count=max(0, int(payload.get("candidate_count", 0) or 0)),
            candidate_actions=[str(item) for item in list(payload.get("candidate_actions", []) or []) if str(item)],
            recommended_actions=[str(item) for item in list(payload.get("recommended_actions", []) or []) if str(item)],
            dominant_emotions=[str(item) for item in list(payload.get("dominant_emotions", []) or []) if str(item)],
            deviation_sources=[str(item) for item in list(payload.get("deviation_sources", []) or []) if str(item)],
            dominant_disposition=str(payload.get("dominant_disposition", "") or ""),
            social_outward_pressure=max(0.0, min(float(payload.get("social_outward_pressure", 0.0) or 0.0), 1.5)),
            exploration_pressure=max(0.0, min(float(payload.get("exploration_pressure", 0.0) or 0.0), 1.5)),
            internal_reflection_pressure=max(0.0, min(float(payload.get("internal_reflection_pressure", 0.0) or 0.0), 1.5)),
            caution_pressure=max(0.0, min(float(payload.get("caution_pressure", 0.0) or 0.0), 1.5)),
            accepted=bool(payload.get("accepted", False)),
            accepted_behavior=str(payload.get("accepted_behavior", "") or ""),
            selected_channel_id=str(payload.get("selected_channel_id", "") or ""),
            non_externalization_reason=str(payload.get("non_externalization_reason", "") or ""),
            policy_rejection_reason=str(payload.get("policy_rejection_reason", "") or ""),
            deferred=bool(payload.get("deferred", False)),
        )


@dataclass
class HeliosState:
    """Single source of truth for each tick — created fresh, passed through pipeline."""

    # Identity
    tick: int = 0
    timestamp: float = 0.0

    # Affect (from DAISY)
    panksepp: Dict[str, float] = field(default_factory=dict)
    valence: float = 0.0
    arousal: float = 0.0
    dominant_system: str = ""

    # Consciousness (from Phi / ICRI)
    icri: float = 0.0
    consciousness_label: str = "minimal"

    # LLM modulation
    llm_temperature: float = 0.85
    speech_style: str = "neutral"

    # Thinking
    dmn_active: bool = False
    last_thought_type: str = ""
    thought_generated_this_tick: bool = False
    continuation_requested: bool = False
    continuation_pressure: float = 0.0
    continuation_reason: str = ""
    continuation: ContinuationPressureState = field(default_factory=ContinuationPressureState)
    last_recall_intent: str = ""
    last_memory_handoff: Dict[str, object] = field(default_factory=dict)
    current_thought_cycle_result: object | None = None
    last_thought_cycle_result: Dict[str, object] = field(default_factory=dict)
    current_stimuli: list[Dict[str, object]] = field(default_factory=list)
    last_thought_gate_result: Dict[str, object] = field(default_factory=dict)
    last_thought_personality_trace: Dict[str, object] = field(default_factory=dict)
    last_internal_thought_trace: Dict[str, object] = field(default_factory=dict)
    directed_memory_bundle: object | None = None
    last_directed_retrieval_trace: Dict[str, object] = field(default_factory=dict)
    last_preconscious_trace: Dict[str, object] = field(default_factory=dict)
    last_identity_revision_trace: Dict[str, object] = field(default_factory=dict)
    proactive: ProactiveObservabilityState = field(default_factory=ProactiveObservabilityState)

    # Mood (from MoodTracker)
    mood_valence: float = 0.0
    mood_arousal: float = 0.0
    mood_label: str = "neutral"

    # Neurochemistry (from NeurochemState)
    dopamine: float = 0.3
    opioids: float = 0.5
    oxytocin: float = 0.3
    cortisol: float = 0.2

    # Allostasis
    allostatic_load: float = 0.0
    is_fatigued: bool = False

    # Personality
    personality_traits: Dict[str, float] = field(default_factory=dict)
    identity_snapshot: Dict[str, object] = field(default_factory=dict)
    personality_projection: object | None = None
    temporal_state: object | None = None
    temporal_gate: object | None = None
    neurochem_gate: object | None = None

    # Context
    separation_hours: float = 0.0
    last_action: str = ""
    pending_reply: Optional[str] = None
    pending_rendered_reply: Optional[str] = None
    boredom: float = 0.0
    fatigue_pressure: float = 0.0
    restoration_level: float = 0.5
    novelty_hunger: float = 0.0
    emotional_decay_factor: float = 1.0
    circadian_phase: float = 0.0
    inactivity_duration: float = 0.0
    recent_excitation_tail: float = 0.0

    # Drives
    drive_dominant: str = ""
    drive_urgency: float = 0.0

    # Behavior execution
    behavior_queue_depth: int = 0
    current_behavior: str = ""

    # Hardware IO status
    channel_availability: Dict[str, bool] = field(default_factory=dict)
    tts_available: bool = False
    stt_available: bool = False
    vision_available: bool = False

    # Stability
    rss_mb: float = 0.0
    uptime_hours: float = 0.0

    @property
    def phi(self) -> float:
        """Deprecated compatibility alias for icri."""
        return self.icri

    @phi.setter
    def phi(self, value: float):
        self.icri = value

    def __post_init__(self):
        self._sync_continuation_fields()
        self._sync_channel_availability_fields()

    def _sync_continuation_fields(self):
        if self.continuation.active or self.continuation.level > 0.0 or self.continuation.reason:
            normalized = ContinuationPressureState.from_payload(self.continuation.to_dict())
        elif self.continuation_pressure > 0.0 or self.continuation_reason:
            normalized = ContinuationPressureState(
                active=self.continuation_pressure > 0.0,
                level=max(0.0, min(float(self.continuation_pressure or 0.0), 1.0)),
                reason=str(self.continuation_reason or ""),
            )
        else:
            normalized = ContinuationPressureState()
        self.continuation = normalized
        self.continuation_pressure = normalized.level
        self.continuation_reason = normalized.reason

    def _sync_channel_availability_fields(self):
        normalized = {
            str(channel_id): bool(is_available)
            for channel_id, is_available in dict(self.channel_availability or {}).items()
        }
        if not normalized:
            normalized = {
                "tts": bool(self.tts_available),
                "stt": bool(self.stt_available),
                "vision": bool(self.vision_available),
            }
        self.channel_availability = normalized
        self.tts_available = normalized.get("tts", False)
        self.stt_available = normalized.get("stt", False)
        self.vision_available = normalized.get("vision", False)

    def set_continuation(self, continuation: ContinuationPressureState):
        self.continuation = ContinuationPressureState.from_payload(continuation.to_dict())
        self.continuation_pressure = self.continuation.level
        self.continuation_reason = self.continuation.reason

    def clear_continuation(self):
        self.set_continuation(ContinuationPressureState())

    def continuation_payload(self) -> Dict[str, object]:
        return self.continuation.to_dict()

    def is_channel_available(self, channel_id: str) -> bool:
        return bool(self.channel_availability.get(str(channel_id), False))
