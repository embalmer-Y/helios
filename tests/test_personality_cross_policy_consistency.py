"""Cross-policy regression tests for personality slow-prior consistency."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from behavior_registry import RuntimeBehaviorCatalog
from cognition.thinking_integration import ThinkingEngineIntegration
from helios_io.interaction_policy import InteractionPolicy
from neurochem_gate import build_neurochem_gate
from personality_projection import build_personality_projection
from regulation import RegulationPolicy
from temporal_gate import build_temporal_gate


@dataclass
class MockTemporalState:
    boredom: float = 0.46
    fatigue_pressure: float = 0.16
    restoration_level: float = 0.58
    novelty_hunger: float = 0.54
    inactivity_duration: float = 96.0
    recent_excitation_tail: float = 0.12


@dataclass
class MockCrossPolicyState:
    personality_projection: object
    personality_traits: dict[str, float]
    temporal_state: MockTemporalState = field(default_factory=MockTemporalState)
    tick: int = 19
    timestamp: float = 190.0
    dominant_system: str = "SEEKING"
    valence: float = 0.24
    arousal: float = 0.42
    oxytocin: float = 0.48
    cortisol: float = 0.22
    dopamine: float = 0.64
    opioids: float = 0.40
    allostatic_load: float = 0.08
    is_fatigued: bool = False
    behavior_queue_depth: int = 0
    current_behavior: str = ""
    drive_urgency: float = 0.72


def _exploratory_projection():
    return build_personality_projection(
        traits={
            "openness": 1.45,
            "extraversion": 1.35,
            "agreeableness": 1.02,
            "neuroticism": 0.82,
            "conscientiousness": 1.02,
        }
    )


def _reflective_projection():
    return build_personality_projection(
        traits={
            "openness": 1.30,
            "extraversion": 0.90,
            "agreeableness": 1.04,
            "neuroticism": 1.40,
            "conscientiousness": 1.70,
        }
    )


def _make_state(projection) -> MockCrossPolicyState:
    return MockCrossPolicyState(
        personality_projection=projection,
        personality_traits=dict(projection.raw_traits),
    )


def test_personality_cross_policy_consistency_for_exploration_bias(tmp_path):
    exploratory = _exploratory_projection()
    reflective = _reflective_projection()
    temporal_state = MockTemporalState()
    thinking = ThinkingEngineIntegration(None, object())

    exploratory_ranked, exploratory_trace = thinking.explain_ranked_types("SEEKING", exploratory)
    reflective_ranked, reflective_trace = thinking.explain_ranked_types("SEEKING", reflective)
    assert exploratory_trace["novelty_bias"] > reflective_trace["novelty_bias"]
    assert exploratory_trace["scores"]["free_association"] > reflective_trace["scores"]["free_association"]
    assert exploratory_ranked.index("free_association") <= reflective_ranked.index("free_association")

    exploratory_temporal = build_temporal_gate(
        temporal_state=temporal_state,
        personality_projection=exploratory,
    )
    reflective_temporal = build_temporal_gate(
        temporal_state=temporal_state,
        personality_projection=reflective,
    )
    assert exploratory_temporal.exploration_pressure > reflective_temporal.exploration_pressure
    assert exploratory_temporal.bias_for_behavior("browse") > reflective_temporal.bias_for_behavior("browse")

    exploratory_neurochem = build_neurochem_gate(
        dopamine=0.64,
        opioids=0.40,
        oxytocin=0.48,
        cortisol=0.22,
        temporal_state=temporal_state,
        personality_projection=exploratory,
    )
    reflective_neurochem = build_neurochem_gate(
        dopamine=0.64,
        opioids=0.40,
        oxytocin=0.48,
        cortisol=0.22,
        temporal_state=temporal_state,
        personality_projection=reflective,
    )
    assert exploratory_neurochem.exploration_bias > reflective_neurochem.exploration_bias
    assert exploratory_neurochem.initiative_bias > reflective_neurochem.initiative_bias

    interaction_policy = InteractionPolicy()
    message = {"text": "要不要一起试试一个新想法？", "user_id": "u1", "channel_id": "qq"}
    sec_result = {"goal_relevance": 0.46, "novelty": 0.74}
    exploratory_assessment = interaction_policy.assess(
        message,
        interaction_policy.collect_signals(
            message,
            sec_result,
            _make_state(exploratory),
            available_channels=["qq", "tts"],
            recent_history=[],
        ),
    )
    reflective_assessment = interaction_policy.assess(
        message,
        interaction_policy.collect_signals(
            message,
            sec_result,
            _make_state(reflective),
            available_channels=["qq", "tts"],
            recent_history=[],
        ),
    )
    assert exploratory_assessment.feature_bundle["request_score"] > reflective_assessment.feature_bundle["request_score"]
    assert exploratory_assessment.feature_bundle["interaction_score"] > reflective_assessment.feature_bundle["interaction_score"]

    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    regulation_policy = RegulationPolicy(behavior_catalog=catalog)
    exploratory_browse = regulation_policy.build_action_proposal(
        "browse",
        score=0.50,
        tick=19,
        candidate_channels=["qq", "tts"],
        drive_dominant="curiosity",
        drive_urgency=0.72,
        personality_projection=exploratory,
        neurochem_gate=exploratory_neurochem,
        temporal_gate=exploratory_temporal,
    )
    reflective_browse = regulation_policy.build_action_proposal(
        "browse",
        score=0.50,
        tick=19,
        candidate_channels=["qq", "tts"],
        drive_dominant="curiosity",
        drive_urgency=0.72,
        personality_projection=reflective,
        neurochem_gate=reflective_neurochem,
        temporal_gate=reflective_temporal,
    )
    assert exploratory_browse.score_bundle["final"] > reflective_browse.score_bundle["final"]
    assert exploratory_browse.provenance["personality_influence_trace"]["novelty_bias"] > reflective_browse.provenance["personality_influence_trace"]["novelty_bias"]


def test_personality_cross_policy_consistency_for_reflective_bias(tmp_path):
    exploratory = _exploratory_projection()
    reflective = _reflective_projection()
    temporal_state = MockTemporalState()
    thinking = ThinkingEngineIntegration(None, object())

    _exploratory_ranked, exploratory_trace = thinking.explain_ranked_types("PANIC", exploratory)
    _reflective_ranked, reflective_trace = thinking.explain_ranked_types("PANIC", reflective)
    assert reflective_trace["persistence_bias"] > exploratory_trace["persistence_bias"]
    assert reflective_trace["scores"]["rumination"] > exploratory_trace["scores"]["rumination"]

    exploratory_temporal = build_temporal_gate(
        temporal_state=temporal_state,
        personality_projection=exploratory,
    )
    reflective_temporal = build_temporal_gate(
        temporal_state=temporal_state,
        personality_projection=reflective,
    )
    assert reflective_temporal.restorative_pull > exploratory_temporal.restorative_pull
    assert reflective_temporal.bias_for_behavior("reflect") > exploratory_temporal.bias_for_behavior("reflect")

    exploratory_neurochem = build_neurochem_gate(
        dopamine=0.64,
        opioids=0.40,
        oxytocin=0.48,
        cortisol=0.22,
        temporal_state=temporal_state,
        personality_projection=exploratory,
    )
    reflective_neurochem = build_neurochem_gate(
        dopamine=0.64,
        opioids=0.40,
        oxytocin=0.48,
        cortisol=0.22,
        temporal_state=temporal_state,
        personality_projection=reflective,
    )
    assert reflective_neurochem.caution_bias > exploratory_neurochem.caution_bias

    interaction_policy = InteractionPolicy()
    message = {"text": "我有点想你了，你在吗？", "user_id": "u1", "channel_id": "qq"}
    sec_result = {"goal_relevance": 0.42, "novelty": 0.28}
    exploratory_signals = interaction_policy.collect_signals(
        message,
        sec_result,
        _make_state(exploratory),
        available_channels=["qq", "tts"],
        recent_history=[],
    )
    reflective_signals = interaction_policy.collect_signals(
        message,
        sec_result,
        _make_state(reflective),
        available_channels=["qq", "tts"],
        recent_history=[],
    )
    assert reflective_signals.protective_pull > exploratory_signals.protective_pull

    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    regulation_policy = RegulationPolicy(behavior_catalog=catalog)
    exploratory_reflect = regulation_policy.build_action_proposal(
        "reflect",
        score=0.50,
        tick=19,
        candidate_channels=["qq", "tts"],
        drive_dominant="stability",
        drive_urgency=0.72,
        personality_projection=exploratory,
        neurochem_gate=exploratory_neurochem,
        temporal_gate=exploratory_temporal,
    )
    reflective_reflect = regulation_policy.build_action_proposal(
        "reflect",
        score=0.50,
        tick=19,
        candidate_channels=["qq", "tts"],
        drive_dominant="stability",
        drive_urgency=0.72,
        personality_projection=reflective,
        neurochem_gate=reflective_neurochem,
        temporal_gate=reflective_temporal,
    )
    assert reflective_reflect.score_bundle["final"] > exploratory_reflect.score_bundle["final"]
    assert reflective_reflect.provenance["personality_influence_trace"]["persistence_bias"] > exploratory_reflect.provenance["personality_influence_trace"]["persistence_bias"]