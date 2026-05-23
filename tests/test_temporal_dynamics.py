"""Focused tests for temporal dynamics slow-variable updates."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.temporal_dynamics import TemporalDynamics, TemporalUpdate


def test_boredom_and_inactivity_rise_under_sustained_quiet():
    dynamics = TemporalDynamics(tick_interval=1.0)
    state = None
    for tick in range(1, 25):
        state = dynamics.update(
            TemporalUpdate(
                tick=tick,
                timestamp=float(tick),
                event_count=0,
                message_count=0,
                external_input_strength=0.0,
                arousal=0.08,
                valence=0.0,
                allostatic_load=0.12,
                is_fatigued=False,
            )
        )

    assert state is not None
    assert state.inactivity_duration >= 24.0
    assert state.boredom > 0.20
    assert state.novelty_hunger > 0.15


def test_excitation_tail_recovers_after_high_stimulation():
    dynamics = TemporalDynamics(tick_interval=1.0)
    activated = dynamics.update(
        TemporalUpdate(
            tick=1,
            timestamp=1.0,
            event_count=3,
            message_count=2,
            external_input_strength=1.2,
            arousal=0.9,
            valence=0.3,
            allostatic_load=0.2,
            is_fatigued=False,
            active_behavior=True,
        )
    )
    restored = activated
    for tick in range(2, 16):
        restored = dynamics.update(
            TemporalUpdate(
                tick=tick,
                timestamp=float(tick),
                event_count=0,
                message_count=0,
                external_input_strength=0.0,
                arousal=0.12,
                valence=0.0,
                allostatic_load=0.08,
                is_fatigued=False,
            )
        )

    assert activated.recent_excitation_tail > 0.3
    assert restored.recent_excitation_tail < activated.recent_excitation_tail
    assert restored.restoration_level > activated.restoration_level
    assert restored.emotional_decay_factor > activated.emotional_decay_factor