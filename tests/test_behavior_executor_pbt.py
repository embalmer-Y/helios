"""Tests for task-23 behavior execution abstraction."""

from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

from helios_io import limb as limb_mod
from helios_io import limb_decision_bridge as bridge_mod

BehaviorCommand = limb_mod.BehaviorCommand
BehaviorExecutor = limb_mod.BehaviorExecutor
BehaviorStatus = limb_mod.BehaviorStatus
LimbDecisionBridge = bridge_mod.LimbDecisionBridge
from helios_main import Helios, HeliosConfig


@settings(max_examples=50, deadline=None)
@given(
    low_priority=st.integers(min_value=1, max_value=50),
    high_priority=st.integers(min_value=51, max_value=100),
)
def test_priority_preemption(low_priority: int, high_priority: int):
    executor = BehaviorExecutor()

    low = executor.enqueue(BehaviorCommand(priority=low_priority, name="low", action="reflect"))
    high = executor.enqueue(BehaviorCommand(priority=high_priority, name="high", action="search"))

    assert low.status == BehaviorStatus.PAUSED
    assert high.status == BehaviorStatus.EXECUTING
    assert executor.current is high


@settings(max_examples=50, deadline=None)
@given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
def test_completion_feedback_and_priority_mapping(score: float):
    executor = BehaviorExecutor()
    callback = MagicMock()
    executor.set_result_callback(callback)
    bridge = LimbDecisionBridge(executor)

    command = bridge.convert_and_enqueue("browse", score)
    completed = executor.complete_current({"success": True, "action": command.action})

    assert completed is not None
    assert completed.status == BehaviorStatus.COMPLETED
    callback.assert_called_once()
    called_command, called_result = callback.call_args[0]
    assert called_command.action == "browse"
    assert called_result["success"] is True


def test_tick_enqueues_and_executes_behavior():
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
        helios._collect_events = MagicMock(return_value=({}, []))
        helios.daisy.cycle = MagicMock(
            return_value=SimpleNamespace(
                panksepp_activation={"PANIC": 0.8},
                valence=-0.4,
                arousal=0.6,
                dominant_system="PANIC",
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
        helios.thinking_integration = MagicMock(generate=MagicMock(return_value=None))
        helios.regulation.tick = MagicMock(return_value="reflect")
        helios.regulation.last_selected_score = 0.7
        helios.regulation.on_behavior_result = MagicMock()
        helios._handle_action = MagicMock(return_value=True)

        helios._tick_once()

        helios._handle_action.assert_called_once()
        helios.regulation.on_behavior_result.assert_called_once()

        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)