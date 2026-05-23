"""Focused tests for proposal adapters introduced in response and regulation layers."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from helios_io.action_models import ActionDecision
from helios_io.response_pipeline import ResponsePipeline
from neurochem_gate import build_neurochem_gate
from personality_projection import build_personality_projection
from regulation.regulation import RegulationEngine
from temporal_gate import build_temporal_gate


@dataclass
class MockHeliosState:
    tick: int = 12
    timestamp: float = 123.0
    valence: float = 0.2
    arousal: float = 0.4
    dominant_system: str = "CARE"
    icri: float = 0.5
    phi: float = 0.5
    mood_label: str = "content"
    personality_traits: dict = field(default_factory=dict)


def test_response_pipeline_build_reply_proposal_returns_structured_proposal():
    pipeline = ResponsePipeline()
    state = MockHeliosState()

    proposal = pipeline.build_reply_proposal(
        {
            "text": "你好",
            "user_id": "u1",
            "channel_id": "qq",
            "message_id": "m1",
        },
        {"goal_relevance": 0.4, "novelty": 0.2},
        state,
        available_channels=["qq", "tts"],
    )

    assert proposal is not None
    assert proposal.behavior_name == "reply_message"
    assert proposal.candidate_channels == ["qq", "tts"]
    assert proposal.parameters["target_user_id"] == "u1"


def test_response_pipeline_build_interaction_proposals_can_surface_non_reply_behavior():
    pipeline = ResponsePipeline()
    state = MockHeliosState(
        dominant_system="CARE",
        valence=0.45,
        arousal=0.55,
        personality_traits={
            "agreeableness": 1.3,
            "extraversion": 1.2,
            "neuroticism": 1.0,
            "openness": 1.0,
        },
    )
    state.oxytocin = 0.8
    state.cortisol = 0.2
    state.allostatic_load = 0.05
    state.is_fatigued = False
    state.behavior_queue_depth = 0
    state.current_behavior = ""
    state.drive_urgency = 0.0

    proposals = pipeline.build_interaction_proposals(
        {
            "text": "我想你了，能陪陪我吗",
            "user_id": "u1",
            "channel_id": "qq",
            "message_id": "m1",
        },
        {"goal_relevance": 0.75, "novelty": 0.34},
        state,
        available_channels=["qq", "tts"],
    )

    assert proposals
    assert proposals[0].behavior_name == "intimate"


def test_response_pipeline_populate_reply_decision_injects_outbound_text():
    pipeline = ResponsePipeline(api_key="")
    pipeline.generate_reply = lambda *args, **kwargs: "reply-text"
    decision = ActionDecision(
        decision_id="decision::1",
        proposal_id="proposal::1",
        behavior_name="reply_message",
        selected_channel_id="qq",
        selected_op="send",
        execution_priority=50,
    )

    hydrated = pipeline.populate_reply_decision(
        decision,
        {"text": "hi", "user_id": "u1", "message_id": "m1"},
        MockHeliosState(),
        {"goal_relevance": 0.5, "novelty": 0.4},
    )

    assert hydrated is not None
    assert hydrated.validated_params["outbound_text"] == "reply-text"
    assert hydrated.validated_params["target_user_id"] == "u1"


def test_regulation_build_action_proposal_preserves_score_and_channels(tmp_path):
    engine = RegulationEngine(data_dir=str(tmp_path))
    projection = build_personality_projection(
        traits={
            "openness": 1.2,
            "extraversion": 1.35,
            "agreeableness": 1.0,
            "neuroticism": 0.85,
            "conscientiousness": 0.95,
        }
    )

    proposal = engine.build_action_proposal(
        "speak_share",
        score=0.72,
        tick=99,
        candidate_channels=["qq", "tts"],
        params={"tick": 99},
        drive_dominant="social",
        drive_urgency=0.8,
        dominant_emotions=["CARE", "PANIC"],
        personality_projection=projection,
    )

    assert proposal.behavior_name == "speak_share"
    assert proposal.score_bundle["base"] == 0.72
    assert proposal.score_bundle["final"] > 0.72
    assert proposal.candidate_channels[0] in {"qq", "tts"}
    assert proposal.created_at_tick == 99


def test_regulation_neurochem_gate_biases_exploration_candidates(tmp_path):
    engine = RegulationEngine(data_dir=str(tmp_path))
    exploratory_gate = build_neurochem_gate(
        dopamine=0.86,
        opioids=0.42,
        oxytocin=0.32,
        cortisol=0.18,
        fatigue_pressure=0.08,
        novelty_hunger=0.72,
        restoration_level=0.58,
        boredom=0.22,
    )
    inhibited_gate = build_neurochem_gate(
        dopamine=0.28,
        opioids=0.36,
        oxytocin=0.30,
        cortisol=0.86,
        fatigue_pressure=0.28,
        novelty_hunger=0.10,
        restoration_level=0.30,
        boredom=0.12,
    )

    exploratory = engine.build_action_proposal(
        "browse",
        score=0.52,
        tick=3,
        candidate_channels=["qq"],
        drive_dominant="curiosity",
        drive_urgency=0.6,
        neurochem_gate=exploratory_gate,
    )
    inhibited = engine.build_action_proposal(
        "browse",
        score=0.52,
        tick=3,
        candidate_channels=["qq"],
        drive_dominant="curiosity",
        drive_urgency=0.6,
        neurochem_gate=inhibited_gate,
    )

    assert exploratory.score_bundle["neurochem_behavior_bias"] > 0.0
    assert inhibited.score_bundle["neurochem_behavior_bias"] < 0.0
    assert exploratory.score_bundle["final"] > inhibited.score_bundle["final"]


def test_regulation_temporal_gate_biases_restoration_and_exploration(tmp_path):
    engine = RegulationEngine(data_dir=str(tmp_path))

    class ExploratoryTemporalState:
        boredom = 0.58
        fatigue_pressure = 0.12
        restoration_level = 0.60
        novelty_hunger = 0.76
        inactivity_duration = 220.0
        recent_excitation_tail = 0.08

    class RestorativeTemporalState:
        boredom = 0.08
        fatigue_pressure = 0.82
        restoration_level = 0.18
        novelty_hunger = 0.10
        inactivity_duration = 18.0
        recent_excitation_tail = 0.26

    exploratory_gate = build_temporal_gate(temporal_state=ExploratoryTemporalState())
    restorative_gate = build_temporal_gate(temporal_state=RestorativeTemporalState())

    browse_proposal = engine.build_action_proposal(
        "browse",
        score=0.50,
        tick=8,
        candidate_channels=["qq"],
        temporal_gate=exploratory_gate,
    )
    idle_proposal = engine.build_action_proposal(
        "idle",
        score=0.50,
        tick=8,
        candidate_channels=["qq"],
        temporal_gate=restorative_gate,
    )

    assert browse_proposal.score_bundle["temporal_behavior_bias"] > 0.0
    assert idle_proposal.score_bundle["temporal_behavior_bias"] > 0.0
    assert browse_proposal.provenance["temporal_gate"]["exploration_pressure"] > idle_proposal.provenance["temporal_gate"]["exploration_pressure"]
    assert idle_proposal.provenance["temporal_gate"]["restorative_pull"] > browse_proposal.provenance["temporal_gate"]["restorative_pull"]