"""Focused tests for structured temporal gating."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from temporal_gate import build_temporal_gate
from personality_projection import build_personality_projection


class ExploratoryTemporalState:
    boredom = 0.62
    fatigue_pressure = 0.10
    restoration_level = 0.62
    novelty_hunger = 0.74
    inactivity_duration = 240.0
    recent_excitation_tail = 0.06


class RestorativeTemporalState:
    boredom = 0.10
    fatigue_pressure = 0.84
    restoration_level = 0.18
    novelty_hunger = 0.08
    inactivity_duration = 20.0
    recent_excitation_tail = 0.24


def test_temporal_gate_prefers_exploration_under_boredom_and_novelty():
    gate = build_temporal_gate(temporal_state=ExploratoryTemporalState())

    assert gate.exploration_pressure > 0.28
    assert gate.constrained("prefer_exploration") is True
    assert gate.bias_for_behavior("browse") > gate.bias_for_behavior("idle")


def test_temporal_gate_prefers_restoration_under_fatigue():
    gate = build_temporal_gate(temporal_state=RestorativeTemporalState())

    assert gate.restorative_pull > 0.50
    assert gate.constrained("prefer_restoration") is True
    assert gate.constrained("avoid_high_expression") is True
    assert gate.bias_for_behavior("idle") > gate.bias_for_behavior("intimate")


def test_temporal_gate_personality_novelty_bias_raises_exploration_pressure():
    base_gate = build_temporal_gate(temporal_state=ExploratoryTemporalState())
    novelty_projection = build_personality_projection(
        traits={
            "openness": 1.5,
            "extraversion": 1.2,
            "agreeableness": 1.0,
            "neuroticism": 0.9,
            "conscientiousness": 0.9,
        }
    )

    biased_gate = build_temporal_gate(
        temporal_state=ExploratoryTemporalState(),
        personality_projection=novelty_projection,
    )

    assert biased_gate.exploration_pressure > base_gate.exploration_pressure
    assert biased_gate.bias_for_behavior("browse") > base_gate.bias_for_behavior("browse")
    assert biased_gate.personality_influence_trace["active"] is True
    assert biased_gate.personality_influence_trace["novelty_bias"] > 0.0


def test_temporal_gate_personality_persistence_bias_raises_restoration_pull():
    base_gate = build_temporal_gate(temporal_state=RestorativeTemporalState())
    persistent_projection = build_personality_projection(
        traits={
            "openness": 0.9,
            "extraversion": 0.8,
            "agreeableness": 1.0,
            "neuroticism": 1.4,
            "conscientiousness": 1.5,
        }
    )

    biased_gate = build_temporal_gate(
        temporal_state=RestorativeTemporalState(),
        personality_projection=persistent_projection,
    )

    assert biased_gate.restorative_pull > base_gate.restorative_pull
    assert biased_gate.bias_for_behavior("reflect") > base_gate.bias_for_behavior("reflect")
    assert biased_gate.personality_influence_trace["persistence_bias"] > 0.0