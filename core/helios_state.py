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

    def set_continuation(self, continuation: ContinuationPressureState):
        self.continuation = ContinuationPressureState.from_payload(continuation.to_dict())
        self.continuation_pressure = self.continuation.level
        self.continuation_reason = self.continuation.reason

    def clear_continuation(self):
        self.set_continuation(ContinuationPressureState())

    def continuation_payload(self) -> Dict[str, object]:
        return self.continuation.to_dict()
