"""Structured personality projection outputs for interaction and regulation policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping, Optional, Sequence


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PersonalityProjection:
    interaction_bias: float
    initiative_bias: float
    risk_tolerance: float
    channel_preferences: dict[str, float] = field(default_factory=dict)
    style_preferences: dict[str, float] = field(default_factory=dict)
    behavior_biases: dict[str, float] = field(default_factory=dict)
    restlessness_bias: float = 0.0
    social_threshold_shift: float = 0.0
    raw_traits: dict[str, float] = field(default_factory=dict)
    neuro_gains: dict[str, float] = field(default_factory=dict)

    def bias_for_behavior(self, behavior_name: str) -> float:
        return float(self.behavior_biases.get(behavior_name, 0.0))

    def channel_preference(self, channel_id: str) -> float:
        return float(self.channel_preferences.get(channel_id, 0.0))

    def style(self, style_name: str) -> float:
        return float(self.style_preferences.get(style_name, 0.0))

    def rank_channels(self, channel_ids: Sequence[str]) -> list[str]:
        unique_ids = list(dict.fromkeys(channel_ids))
        return sorted(unique_ids, key=lambda channel_id: (-self.channel_preference(channel_id), channel_id))

    @property
    def social_initiation_bias(self) -> float:
        return float(self.interaction_bias)

    @property
    def novelty_bias(self) -> float:
        return float(_clamp(self.style("curiosity") * 0.65 + self.restlessness_bias * 0.35, 0.0, 1.0))

    @property
    def persistence_bias(self) -> float:
        return float(_clamp(self.style("directness") * 0.45 + self.style("introspection") * 0.35 + max(self.initiative_bias, 0.0) * 0.20, 0.0, 1.0))

    @property
    def risk_tolerance_bias(self) -> float:
        return float(self.risk_tolerance)

    @property
    def expressivity_bias(self) -> float:
        return float(_clamp(self.style("warmth") * 0.35 + self.style("playfulness") * 0.35 + max(self.initiative_bias, 0.0) * 0.30, 0.0, 1.0))

    @property
    def self_disclosure_bias(self) -> float:
        return float(self.style("self_disclosure"))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.update(
            {
                "social_initiation_bias": self.social_initiation_bias,
                "novelty_bias": self.novelty_bias,
                "persistence_bias": self.persistence_bias,
                "risk_tolerance_bias": self.risk_tolerance_bias,
                "expressivity_bias": self.expressivity_bias,
                "self_disclosure_bias": self.self_disclosure_bias,
            }
        )
        return payload


def build_personality_projection(
    traits: Optional[Mapping[str, float]] = None,
    neuro_gains: Optional[Mapping[str, float]] = None,
) -> PersonalityProjection:
    traits = dict(traits or {})
    neuro_gains = dict(neuro_gains or {})

    openness = _as_float(traits.get("openness", 1.0), 1.0) - 1.0
    extraversion = _as_float(traits.get("extraversion", 1.0), 1.0) - 1.0
    agreeableness = _as_float(traits.get("agreeableness", 1.0), 1.0) - 1.0
    neuroticism = _as_float(traits.get("neuroticism", 1.0), 1.0) - 1.0
    conscientiousness = _as_float(traits.get("conscientiousness", 1.0), 1.0) - 1.0

    seeking_gain = _as_float(neuro_gains.get("SEEKING", 1.0), 1.0) - 1.0
    play_gain = _as_float(neuro_gains.get("PLAY", 1.0), 1.0) - 1.0
    care_gain = _as_float(neuro_gains.get("CARE", 1.0), 1.0) - 1.0
    fear_gain = _as_float(neuro_gains.get("FEAR", 1.0), 1.0) - 1.0
    panic_gain = _as_float(neuro_gains.get("PANIC", 1.0), 1.0) - 1.0

    interaction_bias = _clamp(
        agreeableness * 0.52
        + extraversion * 0.34
        - neuroticism * 0.22
        + care_gain * 0.18,
        -0.5,
        0.5,
    )
    initiative_bias = _clamp(
        extraversion * 0.42
        + openness * 0.26
        + conscientiousness * 0.16
        - neuroticism * 0.12
        + seeking_gain * 0.18
        + play_gain * 0.08,
        -0.5,
        0.5,
    )
    risk_tolerance = _clamp(
        0.5
        + openness * 0.22
        + extraversion * 0.16
        + conscientiousness * 0.08
        - neuroticism * 0.24
        - fear_gain * 0.08,
        0.0,
        1.0,
    )
    restlessness_bias = _clamp(
        0.35
        + openness * 0.20
        + extraversion * 0.12
        + neuroticism * 0.16
        + seeking_gain * 0.22
        + panic_gain * 0.08,
        0.0,
        1.0,
    )
    social_threshold_shift = _clamp(
        neuroticism * 0.12
        - agreeableness * 0.16
        - extraversion * 0.12
        - care_gain * 0.10,
        -0.35,
        0.35,
    )

    channel_preferences = {
        "qq": _clamp(0.58 + interaction_bias * 0.35 + conscientiousness * 0.10, 0.0, 1.0),
        "tts": _clamp(0.42 + initiative_bias * 0.28 + extraversion * 0.12 - conscientiousness * 0.08, 0.0, 1.0),
    }
    style_preferences = {
        "warmth": _clamp(0.52 + agreeableness * 0.30 + care_gain * 0.18 - neuroticism * 0.08, 0.0, 1.0),
        "directness": _clamp(0.45 + conscientiousness * 0.18 + extraversion * 0.12 - agreeableness * 0.05, 0.0, 1.0),
        "playfulness": _clamp(0.36 + extraversion * 0.26 + openness * 0.10 + play_gain * 0.18, 0.0, 1.0),
        "caution": _clamp(0.40 + neuroticism * 0.28 + fear_gain * 0.18 + conscientiousness * 0.08 - openness * 0.05, 0.0, 1.0),
        "introspection": _clamp(0.38 + openness * 0.18 + neuroticism * 0.16 + conscientiousness * 0.12, 0.0, 1.0),
        "curiosity": _clamp(0.48 + openness * 0.28 + seeking_gain * 0.24 - fear_gain * 0.08, 0.0, 1.0),
        "self_disclosure": _clamp(0.36 + agreeableness * 0.16 + extraversion * 0.18 - neuroticism * 0.06, 0.0, 1.0),
    }
    behavior_biases = {
        "reply_message": _clamp(interaction_bias * 0.85 + style_preferences["warmth"] * 0.12, -0.4, 0.4),
        "intimate": _clamp(interaction_bias * 0.90 + style_preferences["self_disclosure"] * 0.18 - style_preferences["caution"] * 0.10, -0.4, 0.4),
        "request": _clamp(style_preferences["directness"] * 0.20 + style_preferences["curiosity"] * 0.10 + neuroticism * 0.08, -0.4, 0.4),
        "speak_care": _clamp(interaction_bias * 0.75 + care_gain * 0.20, -0.4, 0.4),
        "speak_missing": _clamp(interaction_bias * 0.35 + neuroticism * 0.16 + panic_gain * 0.18, -0.4, 0.4),
        "speak_play": _clamp(style_preferences["playfulness"] * 0.24 + extraversion * 0.12 + play_gain * 0.16, -0.4, 0.4),
        "speak_share": _clamp(initiative_bias * 0.42 + style_preferences["curiosity"] * 0.18, -0.4, 0.4),
        "browse": _clamp(style_preferences["curiosity"] * 0.24 + restlessness_bias * 0.12, -0.4, 0.4),
        "search": _clamp(style_preferences["curiosity"] * 0.20 + conscientiousness * 0.12, -0.4, 0.4),
        "learn": _clamp(style_preferences["curiosity"] * 0.16 + style_preferences["introspection"] * 0.10 + conscientiousness * 0.14, -0.4, 0.4),
        "reflect": _clamp(style_preferences["introspection"] * 0.24 + neuroticism * 0.12 + conscientiousness * 0.10, -0.4, 0.4),
        "idle": _clamp(-initiative_bias * 0.25 + style_preferences["caution"] * 0.08, -0.4, 0.4),
    }

    return PersonalityProjection(
        interaction_bias=interaction_bias,
        initiative_bias=initiative_bias,
        risk_tolerance=risk_tolerance,
        channel_preferences=channel_preferences,
        style_preferences=style_preferences,
        behavior_biases=behavior_biases,
        restlessness_bias=restlessness_bias,
        social_threshold_shift=social_threshold_shift,
        raw_traits={key: round(_as_float(value, 1.0), 4) for key, value in traits.items()},
        neuro_gains={key: round(_as_float(value, 1.0), 4) for key, value in neuro_gains.items()},
    )


def resolve_personality_projection(
    *,
    projection: Optional[object] = None,
    traits: Optional[Mapping[str, float]] = None,
    neuro_gains: Optional[Mapping[str, float]] = None,
) -> PersonalityProjection:
    if isinstance(projection, PersonalityProjection):
        return projection
    if isinstance(projection, Mapping) and (
        "interaction_bias" in projection or "social_initiation_bias" in projection
    ):
        interaction_bias = _as_float(
            projection.get("interaction_bias", projection.get("social_initiation_bias", 0.0))
        )
        risk_tolerance = _as_float(
            projection.get("risk_tolerance", projection.get("risk_tolerance_bias", 0.5)),
            0.5,
        )
        return PersonalityProjection(
            interaction_bias=interaction_bias,
            initiative_bias=_as_float(projection.get("initiative_bias", 0.0)),
            risk_tolerance=risk_tolerance,
            channel_preferences=dict(projection.get("channel_preferences", {}) or {}),
            style_preferences=dict(projection.get("style_preferences", {}) or {}),
            behavior_biases=dict(projection.get("behavior_biases", {}) or {}),
            restlessness_bias=_as_float(projection.get("restlessness_bias", 0.0)),
            social_threshold_shift=_as_float(projection.get("social_threshold_shift", 0.0)),
            raw_traits=dict(projection.get("raw_traits", {}) or {}),
            neuro_gains=dict(projection.get("neuro_gains", {}) or {}),
        )
    return build_personality_projection(traits=traits, neuro_gains=neuro_gains)