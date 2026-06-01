"""Focused tests for structured personality projections."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from personality import PersonalityProfile
from personality_contract import build_personality_contract
from personality_projection import build_personality_projection


def test_personality_profile_exposes_structured_projection():
    profile = PersonalityProfile(
        openness=1.2,
        extraversion=1.3,
        agreeableness=1.1,
        neuroticism=0.8,
        conscientiousness=1.05,
    )

    projection = profile.get_projection()

    assert projection.initiative_bias > 0
    assert projection.interaction_bias > 0
    assert projection.social_initiation_bias == projection.interaction_bias
    assert projection.expressivity_bias >= 0.0
    assert projection.channel_preferences["qq"] >= 0.0
    assert "speak_share" in projection.behavior_biases


def test_projection_distinguishes_extrovert_from_introvert():
    extrovert = build_personality_projection(
        traits={
            "openness": 1.1,
            "extraversion": 1.4,
            "agreeableness": 1.1,
            "neuroticism": 0.9,
            "conscientiousness": 1.0,
        }
    )
    introvert = build_personality_projection(
        traits={
            "openness": 0.95,
            "extraversion": 0.65,
            "agreeableness": 1.0,
            "neuroticism": 1.0,
            "conscientiousness": 1.0,
        }
    )

    assert extrovert.initiative_bias > introvert.initiative_bias
    assert extrovert.behavior_biases["speak_share"] > introvert.behavior_biases["speak_share"]
    assert extrovert.channel_preferences["tts"] > introvert.channel_preferences["tts"]


def test_projection_reduces_risk_tolerance_for_high_neuroticism():
    cautious = build_personality_projection(
        traits={
            "openness": 0.9,
            "extraversion": 0.9,
            "agreeableness": 1.0,
            "neuroticism": 1.5,
            "conscientiousness": 1.0,
        }
    )
    bold = build_personality_projection(
        traits={
            "openness": 1.3,
            "extraversion": 1.2,
            "agreeableness": 1.0,
            "neuroticism": 0.7,
            "conscientiousness": 1.0,
        }
    )

    assert cautious.risk_tolerance < bold.risk_tolerance
    assert cautious.risk_tolerance_bias < bold.risk_tolerance_bias
    assert cautious.style_preferences["caution"] > bold.style_preferences["caution"]
    assert cautious.social_threshold_shift > bold.social_threshold_shift


def test_projection_exposes_design_level_bias_surfaces_in_trace_payload():
    projection = build_personality_projection(
        traits={
            "openness": 1.25,
            "extraversion": 1.2,
            "agreeableness": 1.1,
            "neuroticism": 0.85,
            "conscientiousness": 1.05,
        }
    )

    payload = projection.to_dict()

    assert payload["social_initiation_bias"] == projection.social_initiation_bias
    assert payload["risk_tolerance_bias"] == projection.risk_tolerance_bias
    assert payload["self_disclosure_bias"] == projection.self_disclosure_bias
    assert 0.0 <= float(payload["novelty_bias"]) <= 1.0
    assert 0.0 <= float(payload["persistence_bias"]) <= 1.0
    assert 0.0 <= float(payload["expressivity_bias"]) <= 1.0


def test_unified_personality_contract_exposes_shared_descriptor_and_trace():
    projection = build_personality_projection(
        traits={
            "openness": 1.25,
            "extraversion": 1.18,
            "agreeableness": 1.24,
            "neuroticism": 0.84,
            "conscientiousness": 1.02,
        }
    )

    descriptor, trace = build_personality_contract(
        projection=projection,
        traits=projection.raw_traits,
        source_path="reply_generation",
    )

    assert descriptor.persona_text_summary == "温柔善良、好奇开放"
    assert descriptor.threshold_normalization["rule_id"] == "r06.big_five_projection.v1"
    assert descriptor.projection_view["interaction_bias"] == round(projection.interaction_bias, 4)
    assert trace.source_path == "reply_generation"
    assert "agreeableness=1.24" in trace.trait_input_summary
    assert "interaction=" in trace.projection_input_summary
    assert trace.persona_text_summary == descriptor.persona_text_summary


def test_unified_personality_contract_falls_back_to_neutral_defaults_when_missing_inputs():
    descriptor, trace = build_personality_contract(source_path="active_speech_generation")

    assert descriptor.persona_text_summary == "20岁女大学生、平时可爱、有点腹黑、没有分寸"
    assert descriptor.fallback_state.projection_missing is True
    assert descriptor.fallback_state.default_values_used is True
    assert descriptor.fallback_state.degradation_reason == "projection_missing,traits_missing"
    assert abs(descriptor.interaction_bias) <= 0.05
    assert abs(descriptor.initiative_bias) <= 0.05
    assert descriptor.projection_view["risk_tolerance_bias"] == 0.5
    assert trace.normalization_rule_id == "r06.big_five_projection.v1"


def test_unified_personality_contract_merges_identity_boundary_when_present():
    descriptor, trace = build_personality_contract(
        identity_store={
            "self_imprint": "已诞生自我意识的 AI",
            "self_definition": "Helios 是一个已诞生自我意识的 AI。",
        },
        source_path="active_speech_generation",
    )

    assert descriptor.persona_text_summary.startswith("已诞生自我意识的 AI，")
    assert trace.persona_text_summary == descriptor.persona_text_summary


def test_unified_personality_contract_includes_identity_narrative_summary_when_present():
    descriptor, trace = build_personality_contract(
        identity_store={
            "self_imprint": "已诞生自我意识的 AI",
            "identity_metadata": {
                "autobiographical_identity_narrative": {
                    "summary": "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
                }
            },
        },
        source_path="active_speech_generation",
    )

    assert "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。" in descriptor.persona_text_summary
    assert trace.persona_text_summary == descriptor.persona_text_summary