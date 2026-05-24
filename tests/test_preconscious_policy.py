"""Focused tests for the bounded preconscious proposal policy."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from cognition.preconscious import PreconsciousPolicy
from core.helios_state import HeliosState
from helios_io.action_models import ActionDecision, ExecutionFeedback
from helios_io.limb import BehaviorCommand
from memory import MemorySearchHit
from personality_projection import build_personality_projection
from temporal_gate import build_temporal_gate
from neurochem_gate import build_neurochem_gate


def make_state(**overrides) -> HeliosState:
    state = HeliosState(
        tick=7,
        timestamp=123.0,
        icri=0.45,
        valence=0.1,
        arousal=0.3,
        dominant_system="SEEKING",
        drive_urgency=0.35,
        boredom=0.3,
        novelty_hunger=0.45,
        fatigue_pressure=0.1,
        restoration_level=0.35,
        dmn_active=True,
        thought_generated_this_tick=True,
        last_thought_type="self_question",
    )
    state.personality_projection = build_personality_projection(
        traits={
            "openness": 1.2,
            "extraversion": 1.1,
            "agreeableness": 1.0,
            "neuroticism": 0.9,
            "conscientiousness": 1.1,
        }
    )
    state.temporal_state = SimpleNamespace(
        boredom=state.boredom,
        fatigue_pressure=state.fatigue_pressure,
        restoration_level=state.restoration_level,
        novelty_hunger=state.novelty_hunger,
        inactivity_duration=0.0,
        recent_excitation_tail=0.0,
    )
    state.temporal_gate = build_temporal_gate(temporal_state=state.temporal_state)
    state.neurochem_gate = build_neurochem_gate(
        dopamine=0.4,
        opioids=0.5,
        oxytocin=0.3,
        cortisol=0.2,
        temporal_state=state.temporal_state,
        fatigue_pressure=state.fatigue_pressure,
        novelty_hunger=state.novelty_hunger,
        restoration_level=state.restoration_level,
        boredom=state.boredom,
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_preconscious_policy_suppresses_when_salience_is_weak():
    policy = PreconsciousPolicy()
    state = make_state(icri=0.05, dmn_active=False, thought_generated_this_tick=False, last_thought_type="")

    proposals = policy.propose(state=state, thought=None, memory_hits=[])

    assert proposals == []


def test_preconscious_policy_prefers_reflection_for_rumination_with_memory_hits():
    policy = PreconsciousPolicy()
    state = make_state(last_thought_type="rumination")
    thought = SimpleNamespace(type="rumination", content="我反复想着刚才的经历")
    hits = [
        MemorySearchHit(
            memory_id="episode::1",
            memory_type="episodic",
            score=0.62,
            summary="A remembered stressful exchange",
            source="episodic_memory",
        )
    ]

    proposals = policy.propose(state=state, thought=thought, memory_hits=hits)

    assert proposals
    assert proposals[0].behavior_name == "reflect"
    assert proposals[0].source_type == "preconscious"
    assert proposals[0].origin_type == "thought"
    assert proposals[0].constraints["requires_deliberate_review"] is True


def test_preconscious_policy_prefers_learning_for_self_question_under_novelty_pressure():
    policy = PreconsciousPolicy()
    state = make_state(last_thought_type="self_question", novelty_hunger=0.7, drive_urgency=0.5)
    thought = SimpleNamespace(type="self_question", content="我在问自己接下来还缺什么信息")

    proposals = policy.propose(state=state, thought=thought, memory_hits=[])

    assert proposals
    assert proposals[0].behavior_name == "learn"
    assert proposals[0].score_bundle["final"] <= 0.72


def test_preconscious_policy_can_emit_thought_origin_external_candidate_from_current_stimulus():
    policy = PreconsciousPolicy()
    state = make_state(last_thought_type="rumination")
    state.current_stimuli = [
        {
            "source_channel_id": "qq",
            "stimulus_intensity": 0.74,
            "payload": {"user_id": "master"},
        }
    ]
    state.personality_projection = build_personality_projection(
        traits={
            "openness": 1.1,
            "extraversion": 1.5,
            "agreeableness": 1.0,
            "neuroticism": 0.8,
            "conscientiousness": 1.0,
        }
    )
    thought = SimpleNamespace(type="rumination", content="我想把这段感受说出来", timestamp=1.0)

    proposals = policy.propose(state=state, thought=thought, memory_hits=[])

    outward = next(proposal for proposal in proposals if proposal.behavior_name == "speak_share")
    assert outward.origin_type == "thought"
    assert outward.op_name == "send"
    assert outward.candidate_channels == ["qq"]
    assert outward.parameters["target_user_id"] == "master"
    assert 0.0 < outward.outbound_intensity <= 1.0


def test_preconscious_policy_exposes_observability_snapshot_with_recent_outcomes():
    policy = PreconsciousPolicy()
    state = make_state(last_thought_type="rumination")
    thought = SimpleNamespace(type="rumination", content="我反复想着刚才的经历")
    hits = [
        MemorySearchHit(
            memory_id="episode::1",
            memory_type="episodic",
            score=0.62,
            summary="A remembered stressful exchange",
            source="episodic_memory",
        )
    ]

    proposals = policy.propose(state=state, thought=thought, memory_hits=hits)

    decision = ActionDecision(
        decision_id="decision::reject",
        proposal_id=proposals[0].proposal_id,
        behavior_name=proposals[0].behavior_name,
        rejection_reason="execution_scope_constraint",
    )
    policy.on_decision_rejected(proposals[0], decision)

    command = BehaviorCommand(
        priority=1,
        name="decision::accept",
        action=proposals[0].behavior_name,
        proposal_id=proposals[0].proposal_id,
        decision_id="decision::accept",
        provenance={"source_type": "preconscious"},
        params={"preconscious_context": {"thought_type": "rumination"}},
    )
    feedback = ExecutionFeedback(
        proposal_id=proposals[0].proposal_id,
        decision_id="decision::accept",
        behavior_name=proposals[0].behavior_name,
        success=True,
        observed_at_tick=state.tick,
    )
    policy.on_execution_feedback(command, feedback)

    snapshot = policy.get_observability_snapshot()

    assert snapshot["active"] is True
    assert snapshot["signals"]["thought_type"] == "rumination"
    assert snapshot["assessment"]["primary_behavior"] == "reflect"
    assert snapshot["assessment"]["rationale"]
    assert snapshot["proposals"][0]["behavior_name"] == "reflect"
    assert snapshot["latest_rejection"]["rejection_reason"] == "execution_scope_constraint"
    assert snapshot["latest_feedback"]["success"] is True
    assert snapshot["rejection_count"] == 1
    assert snapshot["feedback_count"] == 1