"""cognition/thinking_integration.py — Internal Thought Stream Integration

Wraps the existing ThinkingEngine (thinking.py) to generate spontaneous internal
thoughts during rest periods, with emotion-biased type selection, per-type
cooldowns, and ICRI-gated suppression.

Requirements: 28.1, 28.2, 28.3, 28.4, 28.5, 28.6, 28.7
"""

from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("helios.thinking_integration")

THOUGHT_TYPES = [
    "episodic_fragment",
    "counterfactual",
    "future_projection",
    "self_question",
    "free_association",
    "rumination",
]

EMOTION_THOUGHT_BIAS: Dict[str, List[str]] = {
    "PANIC": ["rumination", "future_projection"],
    "FEAR": ["rumination", "future_projection"],
    "SEEKING": ["free_association", "self_question"],
    "PLAY": ["free_association", "episodic_fragment"],
    "CARE": ["episodic_fragment", "self_question"],
    "RAGE": ["rumination", "counterfactual"],
    "LUST": ["free_association", "episodic_fragment"],
}


@dataclass
class Thought:
    """A single generated thought."""
    type: str
    content: str
    timestamp: float = field(default_factory=time.time)
    triggered_by: str = ""


class ThinkingEngineIntegration:
    """Integrates the existing ThinkingEngine for spontaneous thought generation.

    Controls when and what type of thoughts are generated based on ICRI level,
    DMN activity, dominant emotion, and per-type cooldowns.

    Generation rules:
      - Suppressed when ICRI < 0.10 or DMN inactive
      - ~1 thought per 5 seconds when active
      - Emotion-biased type selection via EMOTION_THOUGHT_BIAS
      - 30-second per-type cooldown to prevent loops
    """

    GENERATION_INTERVAL: float = 5.0
    TYPE_COOLDOWN: float = 30.0
    ICRI_THRESHOLD: float = 0.10

    def __init__(self, thinking_engine=None, autobio_store=None):
        """
        Args:
            thinking_engine: The existing ThinkingEngine instance (thinking.py).
            autobio_store: AutobiographicalStore for recording generated thoughts.
        """
        self._engine = thinking_engine
        self._autobio = autobio_store
        self._last_generation_time: float = 0.0
        self._type_last_used: Dict[str, float] = {}
        self._generated_count: int = 0

    def should_generate(self, icri: float, dmn_active: bool, now: float = None) -> bool:
        """Determine whether a thought should be generated this tick.

        Suppresses when ICRI < threshold or DMN inactive. Rate-limits to
        approximately one thought per GENERATION_INTERVAL seconds.

        Args:
            icri: Current ICRI value.
            dmn_active: Whether the Default Mode Network is active.
            now: Current timestamp (defaults to time.time()).

        Returns:
            True if conditions are met for thought generation.
        """
        if icri < self.ICRI_THRESHOLD:
            return False
        if not dmn_active:
            return False
        if now is None:
            now = time.time()
        if now - self._last_generation_time < self.GENERATION_INTERVAL:
            return False
        return True

    def get_biased_types(self, dominant_system: str) -> List[str]:
        """Return thought types biased by the dominant Panksepp system.

        The biased types appear first in the returned list, followed by
        remaining types in random order (for variety).

        Args:
            dominant_system: The dominant Panksepp system name (e.g. "PANIC").

        Returns:
            Ordered list of thought types, biased types first.
        """
        biased = EMOTION_THOUGHT_BIAS.get(dominant_system, [])
        remaining = [t for t in THOUGHT_TYPES if t not in biased]
        random.shuffle(remaining)
        return biased + remaining

    def is_type_on_cooldown(self, thought_type: str, now: float = None) -> bool:
        """Check if a thought type is on cooldown (30-second per-type).

        Args:
            thought_type: The thought type to check.
            now: Current timestamp (defaults to time.time()).

        Returns:
            True if the type was used within the last TYPE_COOLDOWN seconds.
        """
        if now is None:
            now = time.time()
        last_used = self._type_last_used.get(thought_type, 0.0)
        return (now - last_used) < self.TYPE_COOLDOWN

    def generate(self, state) -> Optional[Thought]:
        """Generate a thought if conditions are met.

        Full pipeline: check should_generate → select biased type → check
        cooldown → produce content → store in autobiographical memory.

        Args:
            state: HeliosState with icri, dominant_system, etc.

        Returns:
            A Thought instance if generated, None otherwise.
        """
        now = time.time()
        icri = getattr(state, "icri", 0.0)
        dominant = getattr(state, "dominant_system", "")
        dmn_active = icri >= self.ICRI_THRESHOLD

        if not self.should_generate(icri, dmn_active, now):
            return None

        # Select thought type (emotion-biased, cooldown-aware)
        candidates = self.get_biased_types(dominant)
        selected_type = None
        for t in candidates:
            if not self.is_type_on_cooldown(t, now):
                selected_type = t
                break

        if selected_type is None:
            return None

        # Generate content
        content = self._produce_content(selected_type, state)

        # Record
        thought = Thought(
            type=selected_type,
            content=content,
            timestamp=now,
            triggered_by=dominant,
        )

        self._last_generation_time = now
        self._type_last_used[selected_type] = now
        self._generated_count += 1

        # Store in autobiographical memory
        if self._autobio and content:
            try:
                self._autobio.record(
                    panksepp=getattr(state, "panksepp", {}),
                    valence=getattr(state, "valence", 0.0),
                    arousal=getattr(state, "arousal", 0.0),
                    dominant=dominant,
                    phi=icri,
                    mood_valence=getattr(state, "mood_valence", 0.0),
                    mood_arousal=getattr(state, "mood_arousal", 0.0),
                    mood_label=getattr(state, "mood_label", "neutral"),
                    allostatic_load=getattr(state, "allostatic_load", 0.0),
                    narrative=f"[thought:{selected_type}] {content}",
                    event_trigger=f"dmn_{selected_type}",
                    cycle=getattr(state, "tick", 0),
                )
            except Exception as e:
                logger.debug(f"Failed to record thought to autobio: {e}")

        logger.debug(f"Generated thought: [{selected_type}] {content[:60]}")
        return thought

    def _produce_content(self, thought_type: str, state) -> str:
        """Produce thought content using the existing ThinkingEngine or templates.

        Falls back to template generation when no engine is available.
        """
        if self._engine:
            return self._produce_from_engine(thought_type, state)
        return self._template_content(thought_type, state)

    def _produce_from_engine(self, thought_type: str, state) -> str:
        """Use the existing ThinkingEngine modules to produce content."""
        try:
            valence = getattr(state, "valence", 0.0)
            arousal = getattr(state, "arousal", 0.5)

            if thought_type == "episodic_fragment" and hasattr(self._engine, "memory_replay"):
                episodes = self._engine.memory_replay.select_for_replay(
                    current_valence=valence, current_arousal=arousal,
                    mode="associative", limit=1
                )
                if episodes:
                    fragment = self._engine.memory_replay.replay(episodes[0])
                    return fragment.content

            elif thought_type == "counterfactual" and hasattr(self._engine, "counterfactual"):
                episodes = self._engine.memory_replay.select_for_replay(
                    current_valence=valence, mode="preplay", limit=1
                )
                if episodes:
                    fragment = self._engine.counterfactual.counterfactual_past(episodes[0])
                    return fragment.content

            elif thought_type == "free_association" and hasattr(self._engine, "spontaneous"):
                fragment = self._engine.spontaneous.generate(
                    current_valence=valence, current_arousal=arousal
                )
                if fragment:
                    return fragment.content

        except Exception as e:
            logger.debug(f"Engine generation failed for {thought_type}: {e}")

        return self._template_content(thought_type, state)

    def _template_content(self, thought_type: str, state) -> str:
        """Fallback template-based thought generation."""
        templates = {
            "episodic_fragment": [
                "想起了一段模糊的记忆...",
                "那时候的感觉，现在还能回味到一点",
                "记忆里有一道光，但我想不清细节",
            ],
            "counterfactual": [
                "如果当时不一样的话...",
                "也许还有另一种可能",
                "假如重来一次，会不会不同",
            ],
            "future_projection": [
                "接下来可能会发生什么呢...",
                "如果持续这样下去...",
                "不知道未来会怎样",
            ],
            "self_question": [
                "我为什么会这样想？",
                "这种感觉从哪里来的？",
                "我现在真正想要的是什么？",
            ],
            "free_association": [
                "思绪自由地飘荡着...",
                "一个念头连着另一个念头",
                "意识在缓缓流动",
            ],
            "rumination": [
                "那件事还在脑子里转...",
                "反复想着同一个问题",
                "越想越觉得不安",
            ],
        }
        options = templates.get(thought_type, ["..."])
        return random.choice(options)

    @property
    def generated_count(self) -> int:
        return self._generated_count
