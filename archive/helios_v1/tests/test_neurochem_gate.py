"""Focused tests for structured neurochemical gating."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from neurochem_gate import build_neurochem_gate
from personality_projection import build_personality_projection


def test_high_cortisol_gate_raises_caution_and_blocks_intimate():
    gate = build_neurochem_gate(
        dopamine=0.30,
        opioids=0.34,
        oxytocin=0.82,
        cortisol=0.90,
        fatigue_pressure=0.24,
        novelty_hunger=0.08,
        restoration_level=0.32,
        boredom=0.10,
    )

    assert gate.caution_bias > 0.48
    assert gate.constrained("avoid_intimate") is True
    assert gate.bias_for_behavior("intimate") < 0.0


def test_high_dopamine_gate_prefers_exploration():
    gate = build_neurochem_gate(
        dopamine=0.88,
        opioids=0.42,
        oxytocin=0.28,
        cortisol=0.14,
        fatigue_pressure=0.05,
        novelty_hunger=0.75,
        restoration_level=0.56,
        boredom=0.22,
    )

    assert gate.exploration_bias > 0.28
    assert gate.constrained("prefer_exploration") is True
    assert gate.bias_for_behavior("browse") > gate.bias_for_behavior("idle")


def test_neurochem_gate_personality_novelty_and_risk_raise_exploration_bias():
    base_gate = build_neurochem_gate(
        dopamine=0.55,
        opioids=0.42,
        oxytocin=0.28,
        cortisol=0.18,
        fatigue_pressure=0.08,
        novelty_hunger=0.35,
        restoration_level=0.56,
        boredom=0.22,
    )
    projection = build_personality_projection(
        traits={
            "openness": 1.5,
            "extraversion": 1.2,
            "agreeableness": 1.0,
            "neuroticism": 0.8,
            "conscientiousness": 0.9,
        }
    )

    biased_gate = build_neurochem_gate(
        dopamine=0.55,
        opioids=0.42,
        oxytocin=0.28,
        cortisol=0.18,
        fatigue_pressure=0.08,
        novelty_hunger=0.35,
        restoration_level=0.56,
        boredom=0.22,
        personality_projection=projection,
    )

    assert biased_gate.exploration_bias > base_gate.exploration_bias
    assert biased_gate.initiative_bias > base_gate.initiative_bias
    assert biased_gate.personality_influence_trace["active"] is True
    assert biased_gate.personality_influence_trace["risk_tolerance_bias"] > 0.0


def test_neurochem_gate_personality_social_bias_raises_social_affinity():
    base_gate = build_neurochem_gate(
        dopamine=0.30,
        opioids=0.50,
        oxytocin=0.40,
        cortisol=0.24,
        fatigue_pressure=0.16,
        novelty_hunger=0.10,
        restoration_level=0.44,
        boredom=0.12,
    )
    projection = build_personality_projection(
        traits={
            "openness": 1.0,
            "extraversion": 1.4,
            "agreeableness": 1.4,
            "neuroticism": 0.8,
            "conscientiousness": 1.0,
        }
    )

    biased_gate = build_neurochem_gate(
        dopamine=0.30,
        opioids=0.50,
        oxytocin=0.40,
        cortisol=0.24,
        fatigue_pressure=0.16,
        novelty_hunger=0.10,
        restoration_level=0.44,
        boredom=0.12,
        personality_projection=projection,
    )

    assert biased_gate.social_affinity > base_gate.social_affinity
    assert biased_gate.bias_for_behavior("reply_message") > base_gate.bias_for_behavior("reply_message")
    assert biased_gate.personality_influence_trace["social_initiation_bias"] > 0.0