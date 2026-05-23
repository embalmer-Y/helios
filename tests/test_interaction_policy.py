"""Focused tests for structured passive interaction policy."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from helios_io.interaction_policy import InteractionPolicy
from neurochem_gate import build_neurochem_gate
from personality_projection import build_personality_projection
from temporal_gate import build_temporal_gate


@dataclass
class MockState:
    tick: int = 7
    timestamp: float = 77.0
    dominant_system: str = "CARE"
    valence: float = 0.3
    arousal: float = 0.4
    oxytocin: float = 0.5
    cortisol: float = 0.2
    allostatic_load: float = 0.1
    is_fatigued: bool = False
    behavior_queue_depth: int = 0
    current_behavior: str = ""
    drive_urgency: float = 0.0
    personality_traits: dict = field(
        default_factory=lambda: {
            "agreeableness": 1.0,
            "extraversion": 1.0,
            "neuroticism": 1.0,
            "openness": 1.0,
        }
    )


def test_interaction_policy_declines_low_signal_message():
    policy = InteractionPolicy()

    proposals = policy.propose(
        {"text": "ok", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.05, "novelty": 0.04},
        MockState(allostatic_load=0.35, is_fatigued=True),
        available_channels=["qq"],
        recent_history=[],
    )

    assert proposals == []


def test_interaction_policy_prefers_reply_message_for_normal_prompt():
    policy = InteractionPolicy()

    proposals = policy.propose(
        {"text": "今天过得怎么样？", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.42, "novelty": 0.26},
        MockState(),
        available_channels=["qq", "tts"],
        recent_history=[],
    )

    assert proposals
    assert proposals[0].behavior_name == "reply_message"
    assert proposals[0].candidate_channels == ["qq", "tts"]


def test_interaction_policy_can_escalate_to_non_reply_behavior():
    policy = InteractionPolicy()
    state = MockState(
        dominant_system="CARE",
        valence=0.45,
        arousal=0.55,
        oxytocin=0.8,
        personality_traits={
            "agreeableness": 1.3,
            "extraversion": 1.2,
            "neuroticism": 1.0,
            "openness": 1.0,
        },
    )

    proposals = policy.propose(
        {"text": "我想你了，能陪陪我吗", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.75, "novelty": 0.34},
        state,
        available_channels=["qq", "tts"],
        recent_history=[],
    )

    assert proposals
    assert proposals[0].behavior_name == "intimate"
    assert any(proposal.behavior_name == "reply_message" for proposal in proposals)


def test_interaction_policy_high_cortisol_gate_blocks_intimate_escalation():
    policy = InteractionPolicy()
    state = MockState(
        dominant_system="CARE",
        valence=0.35,
        arousal=0.6,
        oxytocin=0.82,
        cortisol=0.88,
        personality_traits={
            "agreeableness": 1.3,
            "extraversion": 1.2,
            "neuroticism": 1.0,
            "openness": 1.0,
        },
    )
    state.neurochem_gate = build_neurochem_gate(
        dopamine=0.35,
        opioids=0.38,
        oxytocin=0.82,
        cortisol=0.88,
        fatigue_pressure=0.2,
        novelty_hunger=0.1,
        restoration_level=0.35,
        boredom=0.1,
    )

    proposals = policy.propose(
        {"text": "我想你了，能陪陪我吗", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.78, "novelty": 0.30},
        state,
        available_channels=["qq", "tts"],
        recent_history=[],
    )

    assert proposals
    assert proposals[0].behavior_name == "reply_message"
    assert all(proposal.behavior_name != "intimate" for proposal in proposals)


def test_interaction_policy_temporal_gate_suppresses_high_expression_when_fatigued():
    policy = InteractionPolicy()
    state = MockState(
        dominant_system="CARE",
        valence=0.30,
        arousal=0.22,
        oxytocin=0.78,
        cortisol=0.22,
    )

    class TemporalStateStub:
        boredom = 0.10
        fatigue_pressure = 0.82
        restoration_level = 0.22
        novelty_hunger = 0.08
        inactivity_duration = 10.0
        recent_excitation_tail = 0.18

    state.temporal_state = TemporalStateStub()
    state.temporal_gate = build_temporal_gate(temporal_state=state.temporal_state)

    proposals = policy.propose(
        {"text": "我想你了，能陪陪我吗", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.74, "novelty": 0.18},
        state,
        available_channels=["qq", "tts"],
        recent_history=[],
    )

    assert proposals
    assert proposals[0].behavior_name == "reply_message"
    assert all(proposal.behavior_name != "intimate" for proposal in proposals)


def test_interaction_policy_provenance_includes_personality_influence_trace():
    policy = InteractionPolicy()
    state = MockState()
    state.personality_projection = build_personality_projection(
        traits={
            "openness": 1.25,
            "extraversion": 1.2,
            "agreeableness": 1.1,
            "neuroticism": 0.9,
            "conscientiousness": 1.0,
        }
    )

    proposals = policy.propose(
        {"text": "今天过得怎么样？", "user_id": "u1", "channel_id": "qq"},
        {"goal_relevance": 0.42, "novelty": 0.26},
        state,
        available_channels=["qq", "tts"],
        recent_history=[],
    )

    assert proposals
    trace = proposals[0].provenance["personality_influence_trace"]
    assert trace["projection"]["novelty_bias"] >= 0.0
    assert "temporal_gate" in trace
    assert "neurochem_gate" in trace