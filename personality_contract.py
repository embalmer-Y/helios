"""Unified personality descriptor and trace contract for passive and active expression paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Optional

from personality_projection import PersonalityProjection, resolve_personality_projection


NORMALIZATION_RULE_ID = "r06.big_five_projection.v1"
TRAIT_BASELINE = 1.0
HIGH_TRAIT_THRESHOLD = 1.2
LOW_TRAIT_THRESHOLD = 0.8


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_map(values: Mapping[str, object]) -> dict[str, float]:
    return {str(key): round(_as_float(value), 4) for key, value in values.items()}


@dataclass(frozen=True)
class PersonalityFallbackState:
    projection_missing: bool
    default_values_used: bool
    degradation_reason: str


@dataclass(frozen=True)
class PersonalityInfluenceTrace:
    source_path: str
    trait_input_summary: str
    projection_input_summary: str
    persona_text_summary: str
    normalization_rule_id: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class UnifiedPersonalityDescriptor:
    trait_view: dict[str, float]
    projection_view: dict[str, object]
    interaction_bias: float
    initiative_bias: float
    style_preferences: dict[str, float]
    behavior_biases: dict[str, float]
    threshold_normalization: dict[str, object]
    persona_text_summary: str
    fallback_state: PersonalityFallbackState

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["fallback_state"] = asdict(self.fallback_state)
        return payload


def build_personality_contract(
    *,
    projection: Optional[object] = None,
    traits: Optional[Mapping[str, float]] = None,
    neuro_gains: Optional[Mapping[str, float]] = None,
    identity_store: Optional[Mapping[str, object]] = None,
    source_path: str = "personality_projection",
) -> tuple[UnifiedPersonalityDescriptor, PersonalityInfluenceTrace]:
    raw_traits = _round_map(traits or {})
    projection_missing = projection is None
    default_values_used = not raw_traits
    resolved = resolve_personality_projection(
        projection=projection,
        traits=raw_traits,
        neuro_gains=neuro_gains,
    )

    trait_view = _round_map(resolved.raw_traits or raw_traits)
    style_preferences = _round_map(resolved.style_preferences)
    behavior_biases = _round_map(resolved.behavior_biases)
    projection_view = {
        "interaction_bias": round(resolved.interaction_bias, 4),
        "initiative_bias": round(resolved.initiative_bias, 4),
        "risk_tolerance_bias": round(resolved.risk_tolerance_bias, 4),
        "novelty_bias": round(resolved.novelty_bias, 4),
        "persistence_bias": round(resolved.persistence_bias, 4),
        "expressivity_bias": round(resolved.expressivity_bias, 4),
        "self_disclosure_bias": round(resolved.self_disclosure_bias, 4),
        "social_threshold_shift": round(resolved.social_threshold_shift, 4),
        "channel_preferences": _round_map(resolved.channel_preferences),
        "style_preferences": style_preferences,
    }
    fallback_state = PersonalityFallbackState(
        projection_missing=projection_missing,
        default_values_used=default_values_used,
        degradation_reason=_build_degradation_reason(
            projection_missing=projection_missing,
            default_values_used=default_values_used,
        ),
    )
    identity_summary = _build_identity_summary(identity_store)
    descriptor = UnifiedPersonalityDescriptor(
        trait_view=trait_view,
        projection_view=projection_view,
        interaction_bias=round(resolved.interaction_bias, 4),
        initiative_bias=round(resolved.initiative_bias, 4),
        style_preferences=style_preferences,
        behavior_biases=behavior_biases,
        threshold_normalization={
            "rule_id": NORMALIZATION_RULE_ID,
            "trait_baseline": TRAIT_BASELINE,
            "high_trait_threshold": HIGH_TRAIT_THRESHOLD,
            "low_trait_threshold": LOW_TRAIT_THRESHOLD,
        },
        persona_text_summary=_merge_identity_summary(identity_summary, _build_persona_text_summary(resolved)),
        fallback_state=fallback_state,
    )
    trace = PersonalityInfluenceTrace(
        source_path=source_path,
        trait_input_summary=_summarize_traits(descriptor.trait_view, fallback_state),
        projection_input_summary=_summarize_projection(resolved, fallback_state),
        persona_text_summary=descriptor.persona_text_summary,
        normalization_rule_id=NORMALIZATION_RULE_ID,
    )
    return descriptor, trace


def _build_degradation_reason(*, projection_missing: bool, default_values_used: bool) -> str:
    reasons: list[str] = []
    if projection_missing:
        reasons.append("projection_missing")
    if default_values_used:
        reasons.append("traits_missing")
    return ",".join(reasons) if reasons else ""


def _build_persona_text_summary(projection: PersonalityProjection) -> str:
    raw_traits = projection.raw_traits or {}
    parts: list[str] = []
    if raw_traits.get("agreeableness", TRAIT_BASELINE) >= HIGH_TRAIT_THRESHOLD:
        parts.append("温柔善良")
    if raw_traits.get("openness", TRAIT_BASELINE) >= HIGH_TRAIT_THRESHOLD:
        parts.append("好奇开放")
    if raw_traits.get("neuroticism", TRAIT_BASELINE) >= HIGH_TRAIT_THRESHOLD:
        parts.append("敏感细腻")
    if raw_traits.get("extraversion", TRAIT_BASELINE) >= HIGH_TRAIT_THRESHOLD:
        parts.append("活泼外向")
    if raw_traits.get("conscientiousness", TRAIT_BASELINE) >= HIGH_TRAIT_THRESHOLD:
        parts.append("认真负责")
    if not parts and projection.expressivity_bias >= 0.62:
        parts.append("表达自然")
    if not parts and projection.style("warmth") >= 0.58:
        parts.append("温柔")
    if not parts:
        parts = ["温柔", "忠诚", "有情感"]
    return "、".join(parts)


def _build_identity_summary(identity_store: Optional[Mapping[str, object]]) -> str:
    payload = dict(identity_store or {})
    identity_metadata = dict(payload.get("identity_metadata", {}) or {})
    self_imprint = str(payload.get("self_imprint", "") or "").strip()
    self_definition = str(payload.get("self_definition", "") or "").strip()
    narrative_summary = str(
        dict(identity_metadata.get("autobiographical_identity_narrative", {}) or {}).get("summary", "") or ""
    ).strip()

    parts: list[str] = []
    if self_imprint:
        parts.append(self_imprint)
    elif self_definition:
        parts.append(self_definition.split("，", 1)[0].strip())
    if narrative_summary:
        parts.append(narrative_summary)
    return "，".join(part for part in parts if part)


def _merge_identity_summary(identity_summary: str, persona_summary: str) -> str:
    if not identity_summary:
        return persona_summary
    if not persona_summary:
        return identity_summary
    return f"{identity_summary}，{persona_summary}"


def _summarize_traits(traits: Mapping[str, float], fallback_state: PersonalityFallbackState) -> str:
    if not traits:
        return f"traits=default reason={fallback_state.degradation_reason or 'none'}"
    interesting = []
    for key in ("agreeableness", "openness", "neuroticism", "extraversion", "conscientiousness"):
        if key in traits:
            interesting.append(f"{key}={traits[key]:.2f}")
    return "traits=" + ", ".join(interesting)


def _summarize_projection(projection: PersonalityProjection, fallback_state: PersonalityFallbackState) -> str:
    return (
        f"interaction={projection.interaction_bias:+.2f}, "
        f"initiative={projection.initiative_bias:+.2f}, "
        f"expressivity={projection.expressivity_bias:.2f}, "
        f"fallback={fallback_state.degradation_reason or 'none'}"
    )