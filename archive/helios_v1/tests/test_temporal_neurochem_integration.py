"""Focused tests for temporal dynamics driving neurochemical updates."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.temporal_dynamics import TemporalDynamics, TemporalUpdate
from neurochem import NeurochemState, NeurochemUpdate


def test_quiet_recovery_bias_reduces_reward_and_stress_tone():
    dynamics = TemporalDynamics(tick_interval=1.0)
    temporal_state = None
    for tick in range(1, 41):
        temporal_state = dynamics.update(
            TemporalUpdate(
                tick=tick,
                timestamp=float(tick),
                event_count=0,
                message_count=0,
                external_input_strength=0.0,
                arousal=0.06,
                valence=0.0,
                allostatic_load=0.10,
                is_fatigued=False,
            )
        )

    assert temporal_state is not None
    neurochem = NeurochemState()
    dopamine_before = neurochem.dopamine.current
    opioids_before = neurochem.opioids.current
    cortisol_before = neurochem.cortisol.current

    neurochem.advance(
        NeurochemUpdate(
            dt=1.0,
            temporal_state=temporal_state,
            temporal_signal=dynamics.neurochem_signal,
            valence=0.0,
            arousal=0.06,
            dominant_system="SEEKING",
            allostatic_load=0.10,
            separation_hours=2.0,
            drive_urgency=0.2,
            event_count=0,
            message_count=0,
            external_input_strength=0.0,
            active_behavior=False,
            generated_thought=False,
        )
    )

    assert neurochem.dopamine.current < dopamine_before
    assert neurochem.opioids.current < opioids_before
    assert neurochem.cortisol.current <= cortisol_before + 0.01


def test_high_stimulation_and_load_raise_cortisol_without_collapsing_dopamine():
    dynamics = TemporalDynamics(tick_interval=1.0)
    temporal_state = dynamics.update(
        TemporalUpdate(
            tick=1,
            timestamp=1.0,
            event_count=4,
            message_count=1,
            external_input_strength=1.3,
            arousal=0.92,
            valence=0.1,
            allostatic_load=0.84,
            is_fatigued=True,
            active_behavior=True,
            generated_thought=True,
        )
    )

    neurochem = NeurochemState()
    dopamine_before = neurochem.dopamine.current
    cortisol_before = neurochem.cortisol.current

    neurochem.advance(
        NeurochemUpdate(
            dt=1.0,
            temporal_state=temporal_state,
            temporal_signal=dynamics.neurochem_signal,
            valence=0.1,
            arousal=0.92,
            dominant_system="FEAR",
            allostatic_load=0.84,
            separation_hours=0.5,
            drive_urgency=0.8,
            event_count=4,
            message_count=1,
            external_input_strength=1.3,
            active_behavior=True,
            generated_thought=True,
        )
    )

    assert neurochem.cortisol.current > cortisol_before
    assert neurochem.dopamine.current >= dopamine_before