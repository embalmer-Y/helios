"""Structured temporal gating for interaction and regulation policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from personality_projection import resolve_personality_projection


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _scalar(value: Any, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    current = getattr(value, "current", value)
    try:
        return float(current)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class TemporalGate:
    interaction_readiness: float = 0.0
    exploration_pressure: float = 0.0
    restorative_pull: float = 0.0
    expression_window: float = 0.0
    reply_threshold_shift: float = 0.0
    intimate_threshold_shift: float = 0.0
    action_biases: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, bool] = field(default_factory=dict)
    personality_influence_trace: Dict[str, object] = field(default_factory=dict)

    def bias_for_behavior(self, behavior_name: str) -> float:
        return float(self.action_biases.get(behavior_name, 0.0))

    def constrained(self, name: str) -> bool:
        return bool(self.constraints.get(name, False))

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_temporal_gate(*, temporal_state: Any | None = None, personality_projection: Any | None = None) -> TemporalGate:
    boredom = _clamp(_scalar(getattr(temporal_state, "boredom", 0.0)))
    fatigue_pressure = _clamp(_scalar(getattr(temporal_state, "fatigue_pressure", 0.0)))
    restoration_level = _clamp(_scalar(getattr(temporal_state, "restoration_level", 0.5)))
    novelty_hunger = _clamp(_scalar(getattr(temporal_state, "novelty_hunger", 0.0)))
    inactivity_duration = max(_scalar(getattr(temporal_state, "inactivity_duration", 0.0)), 0.0)
    recent_excitation_tail = _clamp(_scalar(getattr(temporal_state, "recent_excitation_tail", 0.0)))
    if personality_projection is None:
        personality_novelty = 0.0
        personality_persistence = 0.0
        personality_expressivity = 0.0
        personality_social = 0.0
    else:
        projection = resolve_personality_projection(projection=personality_projection)
        personality_novelty = projection.novelty_bias
        personality_persistence = projection.persistence_bias
        personality_expressivity = projection.expressivity_bias
        personality_social = projection.social_initiation_bias

    inactivity_ratio = _clamp(inactivity_duration / 180.0)
    interaction_readiness = _clamp(
        restoration_level * 0.34
        + boredom * 0.16
        + novelty_hunger * 0.12
        + personality_social * 0.08
        + personality_expressivity * 0.04
        - fatigue_pressure * 0.34
        - recent_excitation_tail * 0.08,
        -0.4,
        1.0,
    )
    exploration_pressure = _clamp(
        boredom * 0.42
        + novelty_hunger * 0.38
        + inactivity_ratio * 0.10
        + personality_novelty * 0.16
        - personality_persistence * 0.06
        - fatigue_pressure * 0.18
        - recent_excitation_tail * 0.08,
        -0.4,
        1.0,
    )
    restorative_pull = _clamp(
        fatigue_pressure * 0.48
        + recent_excitation_tail * 0.14
        + max(0.45 - restoration_level, 0.0) * 0.28
        + personality_persistence * 0.10
        - personality_novelty * 0.06
        - novelty_hunger * 0.10,
        0.0,
        1.0,
    )
    expression_window = _clamp(
        restoration_level * 0.30
        + boredom * 0.12
        + personality_expressivity * 0.12
        + personality_social * 0.04
        - fatigue_pressure * 0.34
        - recent_excitation_tail * 0.16,
        -0.4,
        1.0,
    )

    reply_threshold_shift = _clamp(restorative_pull * 0.16 - interaction_readiness * 0.10, -0.14, 0.22)
    intimate_threshold_shift = _clamp(restorative_pull * 0.24 - expression_window * 0.10, -0.12, 0.26)

    action_biases = {
        "reply_message": interaction_readiness * 0.08 - restorative_pull * 0.06,
        "intimate": expression_window * 0.12 - restorative_pull * 0.12,
        "request": interaction_readiness * 0.04 + exploration_pressure * 0.04,
        "browse": exploration_pressure * 0.18 - restorative_pull * 0.08,
        "search": exploration_pressure * 0.16 - restorative_pull * 0.06,
        "learn": exploration_pressure * 0.14 - restorative_pull * 0.08,
        "speak_share": exploration_pressure * 0.12 + expression_window * 0.06 - restorative_pull * 0.08,
        "reflect": restorative_pull * 0.14,
        "check_system": restorative_pull * 0.16,
        "idle": restorative_pull * 0.18 - exploration_pressure * 0.06,
    }
    constraints = {
        "avoid_high_expression": restorative_pull >= 0.42,
        "prefer_restoration": restorative_pull >= 0.50,
        "prefer_exploration": exploration_pressure >= 0.28 and restorative_pull < 0.50,
    }

    return TemporalGate(
        interaction_readiness=interaction_readiness,
        exploration_pressure=exploration_pressure,
        restorative_pull=restorative_pull,
        expression_window=expression_window,
        reply_threshold_shift=reply_threshold_shift,
        intimate_threshold_shift=intimate_threshold_shift,
        action_biases=action_biases,
        constraints=constraints,
        personality_influence_trace={
            "active": personality_projection is not None,
            "novelty_bias": round(personality_novelty, 4),
            "persistence_bias": round(personality_persistence, 4),
            "expressivity_bias": round(personality_expressivity, 4),
            "social_initiation_bias": round(personality_social, 4),
        },
    )


def resolve_temporal_gate(*, gate: Any | None = None, state: Any | None = None) -> TemporalGate:
    if isinstance(gate, TemporalGate):
        return gate
    if state is not None:
        existing = getattr(state, "temporal_gate", None)
        if isinstance(existing, TemporalGate):
            return existing
        return build_temporal_gate(
            temporal_state=getattr(state, "temporal_state", None),
            personality_projection=getattr(state, "personality_projection", None),
        )
    return build_temporal_gate()