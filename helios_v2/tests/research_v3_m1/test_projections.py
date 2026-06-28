"""v2 owner → AspectState 投影测试。"""
import math
import pytest
import numpy as np

from helios_v2.research_v3_m1.aspect_state import (
    AspectState,
    FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY,
)
from helios_v2.research_v3_m1.projections import (
    Hormone9D,
    Feeling7D,
    Salience5D,
    project_v2_to_aspect_state,
    project_v2_to_aspect_state_default,
)


def _all_field_values(s):
    return [
        s.activation, s.valence, s.arousal, s.certainty,
        s.salience, s.precision, s.novelty, s.coherence,
        s.stability, s.resonance,
    ]


class TestProjectionCompleteness:
    def test_projection_from_default_returns_legal_state(self):
        s = project_v2_to_aspect_state_default()
        assert isinstance(s, AspectState)
        for v in _all_field_values(s):
            assert not (math.isnan(v) or math.isinf(v))
            assert -1.0 <= v <= 1.0

    def test_projection_with_high_DA_NE_yields_high_activation(self):
        s = project_v2_to_aspect_state(
            hormone=Hormone9D(
                dopamine=0.9, norepinephrine=0.9, serotonin=0.5,
                acetylcholine=0.5, cortisol=0.5, oxytocin=0.5,
                opioid_tone=0.5, excitation=0.5, inhibition=0.5,
            ),
            feeling=Feeling7D(
                valence=0.0, arousal=0.5, tension=0.5, comfort=0.5,
                pain_like=0.5, social_safety=0.5, fatigue=0.5,
            ),
            salience=Salience5D(
                threat=0.5, reward=0.5, novelty=0.5, uncertainty=0.5,
                social=0.5, aggregate=0.5,
            ),
        )
        assert s.activation > 0.7

    def test_projection_with_high_uncertainty_yields_low_certainty(self):
        s = project_v2_to_aspect_state(
            hormone=Hormone9D(
                dopamine=0.5, norepinephrine=0.5, serotonin=0.5,
                acetylcholine=0.5, cortisol=0.5, oxytocin=0.5,
                opioid_tone=0.5, excitation=0.5, inhibition=0.5,
            ),
            feeling=Feeling7D(
                valence=0.0, arousal=0.5, tension=0.5, comfort=0.5,
                pain_like=0.5, social_safety=0.5, fatigue=0.5,
            ),
            salience=Salience5D(
                threat=0.5, reward=0.5, novelty=0.5, uncertainty=0.9,
                social=0.5, aggregate=0.5,
            ),
        )
        assert s.certainty < 0.2

    def test_projection_with_high_novelty_preserved(self):
        s = project_v2_to_aspect_state(
            hormone=Hormone9D(
                dopamine=0.5, norepinephrine=0.5, serotonin=0.5,
                acetylcholine=0.5, cortisol=0.5, oxytocin=0.5,
                opioid_tone=0.5, excitation=0.5, inhibition=0.5,
            ),
            feeling=Feeling7D(
                valence=0.0, arousal=0.5, tension=0.5, comfort=0.5,
                pain_like=0.5, social_safety=0.5, fatigue=0.5,
            ),
            salience=Salience5D(
                threat=0.5, reward=0.5, novelty=0.9, uncertainty=0.5,
                social=0.5, aggregate=0.5,
            ),
        )
        assert s.novelty > 0.7


class TestProjectionHistory:
    def test_resonance_with_no_history_is_neutral(self):
        s = project_v2_to_aspect_state_default()
        assert s.resonance == 0.5

    def test_resonance_with_identical_history_is_high(self):
        s1 = project_v2_to_aspect_state_default()
        s2 = project_v2_to_aspect_state(
            hormone=Hormone9D(
                dopamine=0.5, norepinephrine=0.5, serotonin=0.5,
                acetylcholine=0.5, cortisol=0.5, oxytocin=0.5,
                opioid_tone=0.5, excitation=0.5, inhibition=0.5,
            ),
            feeling=Feeling7D(
                valence=0.0, arousal=0.5, tension=0.5, comfort=0.5,
                pain_like=0.5, social_safety=0.5, fatigue=0.5,
            ),
            salience=Salience5D(
                threat=0.5, reward=0.5, novelty=0.5, uncertainty=0.5,
                social=0.5, aggregate=0.5,
            ),
            history_state=s1,
        )
        assert s2.resonance > 0.9

    def test_resonance_with_orthogonal_history_is_low(self):
        s = project_v2_to_aspect_state(
            hormone=Hormone9D(
                dopamine=0.0, norepinephrine=0.0, serotonin=0.8,
                acetylcholine=0.5, cortisol=0.3, oxytocin=0.7,
                opioid_tone=0.7, excitation=0.5, inhibition=0.5,
            ),
            feeling=Feeling7D(
                valence=0.7, arousal=0.2, tension=0.3, comfort=0.8,
                pain_like=0.1, social_safety=0.8, fatigue=0.3,
            ),
            salience=Salience5D(
                threat=0.1, reward=0.7, novelty=0.2, uncertainty=0.2,
                social=0.7, aggregate=0.5,
            ),
            history_state=FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY,
        )
        assert s.resonance < 0.5


class TestProjectionDeterminism:
    def test_default_projection_is_deterministic(self):
        s1 = project_v2_to_aspect_state_default()
        s2 = project_v2_to_aspect_state_default()
        assert s1 == s2
