"""Emotional memory compatibility types under the new memory package."""

from dataclasses import dataclass, field
from typing import cast
from memory.memory_system import EmotionalEpisodicMemory


@dataclass
class EmotionalEpisode:
	"""Legacy emotional episode shape kept for API compatibility."""

	timestamp: float = 0.0
	cycle: int = 0
	scene: str = ""
	valence: float = 0.0
	arousal: float = 0.0
	phi: float = 0.0
	tag: str = "ROUTINE"
	language_output: str = ""
	semantic_understanding: str = ""
	decision: str = ""
	self_narrative: str = ""
	intensity: float = 0.0
	significance: float = 0.0
	tags: list[str] = field(default_factory=lambda: cast(list[str], []))


__all__ = ["EmotionalEpisode", "EmotionalEpisodicMemory"]