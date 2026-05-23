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
def test_reply_stage_receives_forward_propagated_state(valence, arousal, phi_value, dominant):
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

        helios._msg_queue.put({"text": "聊聊现在的感受", "user_id": "user-a"})

        helios._tick()

        forwarded_state = helios.response_pipeline.generate_reply.call_args[0][1]
        assert forwarded_state.valence == valence
        assert forwarded_state.arousal == arousal
        assert forwarded_state.dominant_system == dominant
        assert forwarded_state.icri == phi_value
        assert forwarded_state.phi == phi_value
        assert forwarded_state.consciousness_label == "focused"
        assert forwarded_state.panksepp[dominant] == max(arousal, 0.2)
        assert forwarded_state.personality_traits == helios.personality._trait_dict()

        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)