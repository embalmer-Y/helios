"""Property and focused tests for task-22 thinking integration."""

from __future__ import annotations

import os
import sys
import time
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cognition.thinking import ThoughtFragment, ThinkingManager
from cognition.thinking_integration import EMOTION_THOUGHT_BIAS, ThinkingEngineIntegration
from core.helios_state import HeliosState
from helios_main import Helios, HeliosConfig
from personality_projection import build_personality_projection


class FakeAutobioStore:
    def __init__(self):
        self.records: list[dict] = []

    def record(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


class FakeThinkingEngine:
    def __init__(self, mode: str = ThinkingManager.MODE_WANDERING):
        self.mode = mode

    def determine_mode(self, **kwargs):
        return self.mode

    def generate_thoughts(self, **kwargs):
        return [
            ThoughtFragment(
                content="一个还在扩散的念头",
                source="free_association",
                valence_bias=0.1,
                arousal_bias=0.2,
                novelty=0.4,
                phi_prediction=0.3,
            )
        ]


def make_state(**overrides) -> HeliosState:
    state = HeliosState(
        tick=42,
        icri=0.5,
        valence=0.2,
        arousal=0.3,
        dominant_system="SEEKING",
        panksepp={"PLAY": 0.1, "SEEKING": 0.6},
        drive_dominant="curiosity",
        drive_urgency=0.1,
        cortisol=0.2,
        mood_label="curious",
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


@settings(max_examples=20, deadline=None)
@given(dominant_system=st.sampled_from(sorted(EMOTION_THOUGHT_BIAS)))
def test_emotion_biased_thought_generation(dominant_system: str):
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    thought = integration.generate(make_state(dominant_system=dominant_system))

    assert thought is not None
    assert thought.type in EMOTION_THOUGHT_BIAS[dominant_system]


@settings(max_examples=20, deadline=None)
@given(icri=st.floats(min_value=0.0, max_value=0.099, allow_nan=False, allow_infinity=False))
def test_thought_suppression_below_icri_threshold(icri: float):
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())

    assert integration.should_generate(icri, True, time.time() + 100.0) is False
    assert integration.should_generate(0.5, False, time.time() + 100.0) is False


def test_thought_type_cooldown_enforcement():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(dominant_system="PANIC")

    first = integration.generate(state)
    assert first is not None

    integration._last_generation = 0.0
    second = integration.generate(state)

    assert second is not None
    assert second.type != first.type


def test_personality_novelty_bias_prioritizes_exploratory_thought_types():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    projection = build_personality_projection(
        traits={
            "openness": 1.5,
            "extraversion": 1.3,
            "agreeableness": 1.0,
            "neuroticism": 0.9,
            "conscientiousness": 0.9,
        }
    )

    ranked = integration.get_ranked_types("SEEKING", projection)

    assert ranked[0] in {"self_question", "free_association"}
    assert ranked.index("self_question") < ranked.index("rumination")


def test_personality_persistence_bias_prioritizes_reflective_thought_types():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    projection = build_personality_projection(
        traits={
            "openness": 0.9,
            "extraversion": 0.8,
            "agreeableness": 1.0,
            "neuroticism": 1.4,
            "conscientiousness": 1.5,
        }
    )

    ranked = integration.get_ranked_types("PANIC", projection)

    assert ranked[0] == "rumination"
    assert ranked.index("counterfactual") < ranked.index("free_association")


def test_thinking_integration_exposes_personality_trace_on_state():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(
        dominant_system="SEEKING",
        personality_projection=build_personality_projection(
            traits={
                "openness": 1.5,
                "extraversion": 1.2,
                "agreeableness": 1.0,
                "neuroticism": 0.8,
                "conscientiousness": 0.9,
            }
        ),
    )

    thought = integration.generate(state)

    assert thought is not None
    assert state.last_thought_personality_trace["selected_type"] == thought.type
    assert state.last_thought_personality_trace["novelty_bias"] > 0.0
    assert state.last_thought_personality_trace["ranked_types"][0] == thought.type


def test_tick_updates_forwarded_state_with_thought_metadata():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        helios.log.info = MagicMock()
        helios.log.warning = MagicMock()
        helios.daisy.cycle = MagicMock(
            return_value=SimpleNamespace(
                panksepp_activation={"SEEKING": 0.7},
                valence=0.4,
                arousal=0.5,
                dominant_system="SEEKING",
            )
        )
        helios.phi_engine = SimpleNamespace(
            label=SimpleNamespace(value="focused"),
            feed_sensory=lambda *args, **kwargs: None,
            feed_emotional=lambda *args, **kwargs: None,
            feed_ignition_from_panksepp=lambda *args, **kwargs: None,
            feed_self_model_from_personality=lambda *args, **kwargs: None,
            feed_dmn_from_thinking=lambda *args, **kwargs: None,
            aggregate=lambda: 0.55,
        )
        helios.sec_evaluator.evaluate = MagicMock(
            return_value={"goal_relevance": 0.8, "novelty": 0.4, "pleasantness": 0.2}
        )
        helios.response_pipeline.should_reply = MagicMock(return_value=True)
        helios.response_pipeline.generate_reply = MagicMock(return_value="reply")
        helios.response_pipeline.record_exchange = MagicMock()
        helios._channel_gateway.route_outbound = MagicMock(return_value=True)
        helios.thinking_integration = MagicMock(
            generate=MagicMock(
                side_effect=lambda state: (
                    setattr(state, "dmn_active", True),
                    setattr(state, "thought_generated_this_tick", True),
                    setattr(state, "last_thought_type", "free_association"),
                    SimpleNamespace(type="free_association", content="一个念头", timestamp=time.time(), triggered_by="SEEKING"),
                )[-1]
            )
        )

        helios._msg_queue.put({"text": "聊聊你刚刚在想什么", "user_id": "user-a"})

        helios._tick()

        forwarded_state = helios.response_pipeline.generate_reply.call_args[0][1]
        assert forwarded_state.dmn_active is True
        assert forwarded_state.thought_generated_this_tick is True
        assert forwarded_state.last_thought_type == "free_association"

        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)