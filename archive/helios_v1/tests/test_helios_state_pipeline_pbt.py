"""Property-based tests for HeliosState pipeline forward propagation.

Property 27: HeliosState Pipeline Forward Propagation
Validates Requirement 9.4
"""

from __future__ import annotations

from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

from helios_main import Helios, HeliosConfig


class FakePhiEngine:
    def __init__(self, phi_value: float, label: str):
        self._phi_value = phi_value
        self.label = SimpleNamespace(value=label)

    def feed_sensory(self, *args, **kwargs):
        pass

    def feed_emotional(self, *args, **kwargs):
        pass

    def feed_ignition_from_panksepp(self, *args, **kwargs):
        pass

    def feed_self_model_from_personality(self, *args, **kwargs):
        pass

    def feed_dmn_from_thinking(self, *args, **kwargs):
        pass

    def aggregate(self) -> float:
        return self._phi_value


@settings(max_examples=4, deadline=None)
@given(
    valence=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    arousal=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    phi_value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    dominant=st.sampled_from(["CARE", "SEEKING", "PANIC", "PLAY", "FEAR"]),
)
def test_no_thought_tick_retains_forward_propagated_state_without_passive_fallback(valence, arousal, phi_value, dominant):
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
        helios.phi_engine = FakePhiEngine(phi_value=phi_value, label="focused")
        helios.daisy.cycle = MagicMock(
            return_value=SimpleNamespace(
                panksepp_activation={dominant: max(arousal, 0.2)},
                valence=valence,
                arousal=arousal,
                dominant_system=dominant,
            )
        )
        helios.sec_evaluator.evaluate = MagicMock(
            return_value={"goal_relevance": 0.8, "novelty": 0.4, "pleasantness": valence}
        )
        helios.response_pipeline.should_reply = MagicMock(return_value=True)
        helios.response_pipeline.generate_reply = MagicMock(return_value="reply")
        helios.response_pipeline.record_exchange = MagicMock()
        helios._channel_gateway.route_outbound = MagicMock(return_value=True)
        observed_state = {}
        helios.thinking_integration.generate = MagicMock(
            side_effect=lambda state: (
            observed_state.setdefault("state", state),
                setattr(state, "dmn_active", True),
                setattr(state, "thought_generated_this_tick", False),
                setattr(state, "last_thought_type", ""),
                setattr(state, "last_thought_cycle_result", {"triggered": False, "trigger_reason": "test_no_thought"}),
                SimpleNamespace(
                    triggered=False,
                    thought=None,
                    action_proposal={},
                ),
            )[-1]
        )

        helios._msg_queue.put({"text": "聊聊现在的感受", "user_id": "user-a"})

        try:
            helios._tick()

            forwarded_state = observed_state["state"]
            assert forwarded_state.valence == valence
            assert forwarded_state.arousal == arousal
            assert forwarded_state.dominant_system == dominant
            assert forwarded_state.icri == phi_value
            assert forwarded_state.phi == phi_value
            assert forwarded_state.consciousness_label == "focused"
            assert forwarded_state.panksepp[dominant] == max(arousal, 0.2)
            assert forwarded_state.personality_traits == helios.personality._trait_dict()
            assert forwarded_state.temporal_state is not None
            assert 0.0 <= forwarded_state.boredom <= 1.0
            assert 0.0 <= forwarded_state.restoration_level <= 1.0
            assert isinstance(forwarded_state.channel_availability, dict)
            assert forwarded_state.channel_availability.get("tts", False) == forwarded_state.tts_available
            assert forwarded_state.channel_availability.get("stt", False) == forwarded_state.stt_available
            assert forwarded_state.channel_availability.get("vision", False) == forwarded_state.vision_available
            assert forwarded_state.is_channel_available("tts") == forwarded_state.tts_available
            helios.response_pipeline.generate_reply.assert_not_called()
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)