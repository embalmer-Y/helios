"""Unified state object passed through all modules each tick.

HeliosState is the single source of truth for a tick — created fresh at the
start of each tick and progressively populated as the pipeline executes.
"""

import warnings
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class HeliosState:
    """Single source of truth for each tick — created fresh, passed through pipeline.

    The consciousness metric is now called ICRI (Integrated Consciousness Richness
    Index). The legacy ``phi`` field name is retained as a backward-compatible alias
    that reads/writes the same underlying ``icri`` value.
    """

    # Identity
    tick: int = 0
    timestamp: float = 0.0

    # Affect (from DAISY)
    panksepp: Dict[str, float] = field(default_factory=dict)
    valence: float = 0.0
    arousal: float = 0.0
    dominant_system: str = ""

    # Consciousness (ICRI — Integrated Consciousness Richness Index)
    icri: float = 0.0
    consciousness_label: str = "minimal"

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

    # Context
    separation_hours: float = 0.0
    last_action: str = ""
    pending_reply: Optional[str] = None

    # Drives
    drive_dominant: str = ""
    drive_urgency: float = 0.0

    # LLM Temperature Modulation (from ICRI)
    llm_temperature: float = 0.85
    speech_style: str = ""

    @property
    def phi(self) -> float:
        """Deprecated: backward-compatible alias for ``icri``.

        External monitoring tools can still query ``state.phi`` during the
        deprecation period. Internally, all new code should use ``state.icri``.
        """
        return self.icri

    @phi.setter
    def phi(self, value: float):
        """Deprecated setter: writes to ``icri`` for backward compatibility."""
        self.icri = value
