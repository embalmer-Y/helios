"""Unified state object passed through all modules each tick.

HeliosState is the single source of truth for a tick — created fresh at the
start of each tick and progressively populated as the pipeline executes.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


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
    last_recall_intent: str = ""
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
