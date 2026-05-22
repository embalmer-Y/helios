"""
tests/test_vision_module.py — Unit tests for VisionModule (io/io_vision.py)

Tests graceful degradation, EventSource interface compliance, capture interval
logic, description-to-trigger conversion, and dormant behavior.

Requirements: 32.1, 32.2, 32.3, 32.4
"""

import sys
import time
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Load io_vision module using importlib to avoid 'io' stdlib conflict
_pkg_dir = Path(__file__).parent.parent / "io"
_spec = importlib.util.spec_from_file_location("helios_io_vision_test", str(_pkg_dir / "io_vision.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
VisionModule = _mod.VisionModule

from core.helios_state import HeliosState
from cognition.phi import CognitiveImpactProfile


class TestVisionModuleInit:
    """Test graceful initialization and degradation."""

    def test_disabled_by_config(self):
        """When enabled=False, module stays dormant."""
        v = VisionModule(enabled=False)
        assert not v._available
        assert not v.is_available

    def test_dormant_without_opencv(self):
        """When cv2 is not importable, module stays dormant."""
        # VisionModule tries to import cv2 — if not installed, it's dormant
        v = VisionModule(enabled=True)
        # On test machines without OpenCV, this should be False
        # We test the behavior regardless of actual cv2 availability
        if v._cv2 is None:
            assert not v._available
            assert not v.is_available

    @patch.dict(sys.modules, {"cv2": MagicMock()})
    def test_dormant_without_camera(self):
        """When cv2 is available but camera is not, module stays dormant."""
        mock_cv2 = sys.modules["cv2"]
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap

        v = VisionModule.__new__(VisionModule)
        v._enabled = True
        v._available = False
        v._registered = False
        v._capture_interval = 5.0
        v._vision_llm_model = "deepseek-chat"
        v._camera_index = 0
        v._last_capture = 0.0
        v._cv2 = mock_cv2
        v._lock = __import__("threading").Lock()
        v._pending_descriptions = []
        v._last_triggers = {}
        v._last_impact = None

        # Camera check should fail
        assert not v._check_camera()
        assert not v._available

    @patch.dict(sys.modules, {"cv2": MagicMock()})
    def test_available_with_opencv_and_camera(self):
        """When cv2 and camera are both available, module is ready."""
        mock_cv2 = sys.modules["cv2"]
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap

        v = VisionModule.__new__(VisionModule)
        v._enabled = True
        v._available = False
        v._registered = False
        v._capture_interval = 5.0
        v._vision_llm_model = "deepseek-chat"
        v._camera_index = 0
        v._last_capture = 0.0
        v._cv2 = mock_cv2
        v._lock = __import__("threading").Lock()
        v._pending_descriptions = []
        v._last_triggers = {}
        v._last_impact = None

        assert v._check_camera()


class TestVisionModuleRegistration:
    """Test register/deregister runtime pluggability."""

    def test_register_activates(self):
        """register() sets _registered to True."""
        v = VisionModule(enabled=False)
        v.register()
        assert v._registered

    def test_deregister_deactivates(self):
        """deregister() sets _registered to False."""
        v = VisionModule(enabled=False)
        v.register()
        v.deregister()
        assert not v._registered

    def test_is_available_requires_all_three(self):
        """is_available requires _available AND _enabled AND _registered."""
        v = VisionModule(enabled=False)
        assert not v.is_available

        v._enabled = True
        v._available = True
        assert not v.is_available  # not registered

        v._registered = True
        assert v.is_available


class TestVisionModulePoll:
    """Test poll() behavior and capture interval logic."""

    def test_poll_returns_empty_when_dormant(self):
        """poll() returns {} when module is not available."""
        v = VisionModule(enabled=False)
        state = HeliosState()
        assert v.poll(state) == {}

    def test_poll_respects_capture_interval(self):
        """poll() only captures when interval has elapsed."""
        v = VisionModule(enabled=False)
        v._enabled = True
        v._available = True
        v._registered = True
        v._capture_interval = 5.0
        v._last_capture = time.time()  # just captured

        state = HeliosState()
        # Should not capture — interval not elapsed
        with patch.object(v, "_capture_and_analyze", return_value={}) as mock_cap:
            result = v.poll(state)
            mock_cap.assert_not_called()
            assert result == {}

    def test_poll_captures_when_interval_elapsed(self):
        """poll() captures when interval has elapsed."""
        v = VisionModule(enabled=False)
        v._enabled = True
        v._available = True
        v._registered = True
        v._capture_interval = 5.0
        v._last_capture = time.time() - 10.0  # 10 seconds ago

        state = HeliosState()
        with patch.object(v, "_capture_and_analyze", return_value={"SEEKING": 0.5}) as mock_cap:
            result = v.poll(state)
            mock_cap.assert_called_once()
            assert result == {"SEEKING": 0.5}

    def test_poll_captures_on_first_call(self):
        """poll() captures on first call (last_capture=0)."""
        v = VisionModule(enabled=False)
        v._enabled = True
        v._available = True
        v._registered = True
        v._capture_interval = 5.0
        v._last_capture = 0.0

        state = HeliosState()
        with patch.object(v, "_capture_and_analyze", return_value={}) as mock_cap:
            v.poll(state)
            mock_cap.assert_called_once()


class TestVisionModuleGetMessages:
    """Test get_messages() behavior."""

    def test_get_messages_empty_when_dormant(self):
        """get_messages() returns [] when not available."""
        v = VisionModule(enabled=False)
        assert v.get_messages() == []

    def test_get_messages_returns_and_clears_buffer(self):
        """get_messages() returns buffered descriptions and clears them."""
        v = VisionModule(enabled=False)
        v._pending_descriptions = [
            {"text": "[视觉] 温馨的场景", "source": "vision", "timestamp": 1.0, "user_id": "camera"}
        ]
        messages = v.get_messages()
        assert len(messages) == 1
        assert messages[0]["source"] == "vision"
        assert v._pending_descriptions == []


class TestVisionModuleDescriptionToTriggers:
    """Test _description_to_triggers() conversion logic."""

    def _make_module(self):
        """Create a VisionModule instance for testing."""
        v = VisionModule(enabled=False)
        return v

    def test_parses_structured_dimensions(self):
        """Parses sensory/cognitive/self/novelty from structured format."""
        v = self._make_module()
        description = "一个温馨的家庭场景|sensory:0.6|cognitive:0.3|self:0.7|novelty:0.2"
        triggers, impact = v._description_to_triggers(description)

        assert isinstance(impact, CognitiveImpactProfile)
        assert abs(impact.sensory - 0.6) < 0.01
        assert abs(impact.cognitive - 0.3) < 0.01
        assert abs(impact.self_ - 0.7) < 0.01
        assert abs(impact.novelty - 0.2) < 0.01

    def test_care_trigger_from_warm_scene(self):
        """Warm/caring keywords produce CARE trigger."""
        v = self._make_module()
        description = "温馨的家庭聚会，大家都在微笑|sensory:0.5|cognitive:0.3|self:0.6|novelty:0.2"
        triggers, impact = v._description_to_triggers(description)

        assert "CARE" in triggers
        assert triggers["CARE"] > 0.0

    def test_fear_trigger_from_danger_scene(self):
        """Danger keywords produce FEAR trigger."""
        v = self._make_module()
        description = "一个危险的场景，有威胁|sensory:0.7|cognitive:0.5|self:0.4|novelty:0.8"
        triggers, impact = v._description_to_triggers(description)

        assert "FEAR" in triggers
        assert triggers["FEAR"] > 0.0

    def test_seeking_trigger_from_novel_scene(self):
        """Novel/interesting keywords produce SEEKING trigger."""
        v = self._make_module()
        description = "一个有趣的新奇发现|sensory:0.4|cognitive:0.6|self:0.3|novelty:0.9"
        triggers, impact = v._description_to_triggers(description)

        assert "SEEKING" in triggers
        assert triggers["SEEKING"] > 0.0

    def test_default_seeking_for_high_novelty_no_keywords(self):
        """High novelty without keywords still produces mild SEEKING."""
        v = self._make_module()
        description = "普通的室内环境|sensory:0.3|cognitive:0.2|self:0.1|novelty:0.7"
        triggers, impact = v._description_to_triggers(description)

        assert "SEEKING" in triggers
        assert triggers["SEEKING"] > 0.0

    def test_no_triggers_for_low_novelty_no_keywords(self):
        """Low novelty without keywords produces no triggers."""
        v = self._make_module()
        description = "普通的室内环境|sensory:0.3|cognitive:0.2|self:0.1|novelty:0.2"
        triggers, impact = v._description_to_triggers(description)

        assert triggers == {}

    def test_clamps_dimensions_to_valid_range(self):
        """Dimensions are clamped to [0, 1]."""
        v = self._make_module()
        description = "场景|sensory:1.5|cognitive:-0.3|self:0.5|novelty:2.0"
        triggers, impact = v._description_to_triggers(description)

        assert impact.sensory == 1.0
        assert impact.cognitive == 0.0
        assert impact.self_ == 0.5
        assert impact.novelty == 1.0

    def test_handles_malformed_dimensions_gracefully(self):
        """Malformed dimension strings use defaults."""
        v = self._make_module()
        description = "场景|sensory:abc|cognitive:|self:0.5"
        triggers, impact = v._description_to_triggers(description)

        # sensory and cognitive should use defaults, self_ parsed correctly
        assert impact.sensory == 0.3  # default
        assert impact.cognitive == 0.2  # default
        assert impact.self_ == 0.5
        assert impact.novelty == 0.3  # default (not in string)

    def test_handles_no_pipe_separators(self):
        """Plain description without structured dimensions uses defaults."""
        v = self._make_module()
        description = "一个普通的场景描述没有结构化数据"
        triggers, impact = v._description_to_triggers(description)

        assert impact.sensory == 0.3
        assert impact.cognitive == 0.2
        assert impact.self_ == 0.1
        assert impact.novelty == 0.3


class TestVisionModuleCaptureInterval:
    """Test configurable capture interval."""

    def test_default_interval(self):
        """Default capture interval is 5 seconds."""
        v = VisionModule(enabled=False)
        assert v.capture_interval == 5.0

    def test_custom_interval(self):
        """Custom capture interval is respected."""
        v = VisionModule(capture_interval=10.0, enabled=False)
        assert v.capture_interval == 10.0

    def test_interval_setter_minimum(self):
        """Capture interval cannot be set below 1 second."""
        v = VisionModule(enabled=False)
        v.capture_interval = 0.1
        assert v.capture_interval == 1.0


class TestVisionModuleGetState:
    """Test get_state() monitoring output."""

    def test_get_state_returns_all_fields(self):
        """get_state() returns complete module status."""
        v = VisionModule(enabled=False)
        state = v.get_state()

        assert "enabled" in state
        assert "available" in state
        assert "registered" in state
        assert "is_available" in state
        assert "capture_interval" in state
        assert "camera_index" in state
        assert "last_capture" in state
        assert "pending_descriptions" in state


class TestHeliosStateVisionField:
    """Test that HeliosState has vision_available field."""

    def test_vision_available_default_false(self):
        """HeliosState.vision_available defaults to False."""
        state = HeliosState()
        assert state.vision_available is False

    def test_vision_available_settable(self):
        """HeliosState.vision_available can be set to True."""
        state = HeliosState()
        state.vision_available = True
        assert state.vision_available is True
