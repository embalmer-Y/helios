"""Integration layer for internal thought generation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from core.helios_state import HeliosState
from personality_projection import resolve_personality_projection

from .thinking import ThinkingManager, ThoughtFragment


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


class ThinkingEngineIntegration:
    GENERATION_INTERVAL = 5.0
    COOLDOWN_PER_TYPE = 30.0
    ICRI_THRESHOLD = 0.10

    def __init__(
        self,
        thinking_engine: Optional[ThinkingManager],
        autobio_store,
        on_thought_recorded: Optional[Callable[[Thought, HeliosState, object], None]] = None,
    ):
        self._engine = thinking_engine or ThinkingManager()
        self._autobio = autobio_store
        self._on_thought_recorded = on_thought_recorded
        self._last_generation = 0.0
        self._type_cooldowns: dict[str, float] = {}

    def should_generate(self, icri: float, dmn_active: bool, now: float) -> bool:
        if icri < self.ICRI_THRESHOLD:
            return False
        if not dmn_active:
            return False
        if (now - self._last_generation) < self.GENERATION_INTERVAL:
            return False
        return True

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
        dmn_active = self._determine_dmn_activity(state)
        state.dmn_active = dmn_active
        state.thought_generated_this_tick = False

        if not self.should_generate(state.icri, dmn_active, now):
            state.last_thought_personality_trace = {}
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
            state.last_thought_personality_trace = personality_trace
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
        thought = Thought(
            type=thought_type,
            content=self._build_content(thought_type, fragment, state),
            timestamp=now,
            triggered_by=state.dominant_system or "DMN",
        )

        self._last_generation = now
        self._type_cooldowns[thought_type] = now
        state.last_thought_type = thought_type
        state.thought_generated_this_tick = True
        state.last_thought_personality_trace = {
            **personality_trace,
            "selected_type": thought_type,
        }
        self._record_thought(thought, state)
        return thought

    def _determine_dmn_activity(self, state: HeliosState) -> bool:
        mode = self._engine.determine_mode(
            has_external_stimulus=False,
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
