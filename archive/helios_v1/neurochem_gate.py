"""Structured neurochemical gating for interaction and regulation policies."""

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
class NeurochemGate:
    dopamine: float = 0.0
    opioids: float = 0.0
    oxytocin: float = 0.0
    cortisol: float = 0.0
    social_affinity: float = 0.0
    initiative_bias: float = 0.0
    exploration_bias: float = 0.0
    caution_bias: float = 0.0
    soothing_bias: float = 0.0
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


def build_neurochem_gate(
    *,
    dopamine: float = 0.0,
    opioids: float = 0.0,
    oxytocin: float = 0.0,
    cortisol: float = 0.0,
    temporal_state: Any | None = None,
    fatigue_pressure: float = 0.0,
    novelty_hunger: float = 0.0,
    restoration_level: float = 0.5,
    boredom: float = 0.0,
    personality_projection: Any | None = None,
) -> NeurochemGate:
    dopamine = _clamp(_scalar(dopamine))
    opioids = _clamp(_scalar(opioids))
    oxytocin = _clamp(_scalar(oxytocin))
    cortisol = _clamp(_scalar(cortisol))
    boredom = _clamp(_scalar(getattr(temporal_state, "boredom", boredom), boredom))
    novelty_hunger = _clamp(_scalar(getattr(temporal_state, "novelty_hunger", novelty_hunger), novelty_hunger))
    restoration_level = _clamp(_scalar(getattr(temporal_state, "restoration_level", restoration_level), restoration_level))
    fatigue_pressure = _clamp(_scalar(getattr(temporal_state, "fatigue_pressure", fatigue_pressure), fatigue_pressure))
    if personality_projection is None:
        personality_social = 0.0
        personality_novelty = 0.0
        personality_risk = 0.0
        personality_expressivity = 0.0
    else:
        projection = resolve_personality_projection(projection=personality_projection)
        personality_social = projection.social_initiation_bias
        personality_novelty = projection.novelty_bias
        personality_risk = projection.risk_tolerance_bias
        personality_expressivity = projection.expressivity_bias

    social_affinity = _clamp(
        oxytocin * 0.52
        + opioids * 0.24
        + restoration_level * 0.08
        + personality_social * 0.10
        + personality_expressivity * 0.06
        - cortisol * 0.22
        - fatigue_pressure * 0.12,
        -0.4,
        1.0,
    )
    initiative_bias = _clamp(
        dopamine * 0.48
        + novelty_hunger * 0.16
        + personality_novelty * 0.12
        + personality_risk * 0.06
        - cortisol * 0.26
        - fatigue_pressure * 0.14,
        -0.4,
        1.0,
    )
    exploration_bias = _clamp(
        dopamine * 0.54
        + novelty_hunger * 0.20
        + personality_novelty * 0.16
        + personality_risk * 0.04
        - cortisol * 0.20
        - boredom * 0.08,
        -0.4,
        1.0,
    )
    caution_bias = _clamp(
        cortisol * 0.62
        + fatigue_pressure * 0.18
        + boredom * 0.06
        - personality_risk * 0.10
        - oxytocin * 0.10
        - opioids * 0.08,
        0.0,
        1.0,
    )
    soothing_bias = _clamp(
        opioids * 0.46
        + restoration_level * 0.22
        - cortisol * 0.16,
        -0.2,
        1.0,
    )

    reply_threshold_shift = _clamp(caution_bias * 0.18 - social_affinity * 0.10, -0.15, 0.22)
    intimate_threshold_shift = _clamp(caution_bias * 0.28 - oxytocin * 0.12 - opioids * 0.06, -0.18, 0.30)

    action_biases = {
        "reply_message": social_affinity * 0.10 - caution_bias * 0.06,
        "intimate": social_affinity * 0.24 - caution_bias * 0.22,
        "request": initiative_bias * 0.12 + caution_bias * 0.02,
        "speak_care": social_affinity * 0.16 - caution_bias * 0.10,
        "speak_missing": social_affinity * 0.12 - caution_bias * 0.08,
        "speak_share": exploration_bias * 0.18 + initiative_bias * 0.08 - caution_bias * 0.08,
        "browse": exploration_bias * 0.22 + initiative_bias * 0.04,
        "search": exploration_bias * 0.18 + initiative_bias * 0.04,
        "learn": exploration_bias * 0.16 + initiative_bias * 0.02 - caution_bias * 0.04,
        "reflect": soothing_bias * 0.12 + caution_bias * 0.04,
        "check_system": caution_bias * 0.10 + soothing_bias * 0.06,
        "idle": soothing_bias * 0.12 - initiative_bias * 0.08,
    }
    constraints = {
        "avoid_intimate": caution_bias >= 0.42 or cortisol >= 0.78,
        "avoid_high_expression": caution_bias >= 0.54 or cortisol >= 0.84,
        "prefer_exploration": exploration_bias >= 0.28 and caution_bias < 0.55,
    }

    return NeurochemGate(
        dopamine=dopamine,
        opioids=opioids,
        oxytocin=oxytocin,
        cortisol=cortisol,
        social_affinity=social_affinity,
        initiative_bias=initiative_bias,
        exploration_bias=exploration_bias,
        caution_bias=caution_bias,
        soothing_bias=soothing_bias,
        reply_threshold_shift=reply_threshold_shift,
        intimate_threshold_shift=intimate_threshold_shift,
        action_biases=action_biases,
        constraints=constraints,
        personality_influence_trace={
            "active": personality_projection is not None,
            "social_initiation_bias": round(personality_social, 4),
            "novelty_bias": round(personality_novelty, 4),
            "risk_tolerance_bias": round(personality_risk, 4),
            "expressivity_bias": round(personality_expressivity, 4),
        },
    )


def resolve_neurochem_gate(*, gate: Any | None = None, state: Any | None = None) -> NeurochemGate:
    if isinstance(gate, NeurochemGate):
        return gate
    if state is not None:
        existing = getattr(state, "neurochem_gate", None)
        if isinstance(existing, NeurochemGate):
            return existing
        return build_neurochem_gate(
            dopamine=getattr(state, "dopamine", 0.0),
            opioids=getattr(state, "opioids", 0.0),
            oxytocin=getattr(state, "oxytocin", 0.0),
            cortisol=getattr(state, "cortisol", 0.0),
            temporal_state=getattr(state, "temporal_state", None),
            fatigue_pressure=getattr(state, "fatigue_pressure", 0.0),
            novelty_hunger=getattr(state, "novelty_hunger", 0.0),
            restoration_level=getattr(state, "restoration_level", 0.5),
            boredom=getattr(state, "boredom", 0.0),
            personality_projection=getattr(state, "personality_projection", None),
        )
    return build_neurochem_gate()