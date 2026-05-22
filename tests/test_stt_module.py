"""
Tests for STTModule graceful degradation, EventSource interface, and runtime pluggability.

Validates Requirements 31.1, 31.2, 31.3, 31.4
"""

import logging
import time
from unittest.mock import patch, MagicMock

import pytest

# Load the STTModule via importlib to avoid 'io' stdlib conflict
import importlib.util
from pathlib import Path

_pkg_dir = Path(__file__).parent.parent / "io"
_stt_spec = importlib.util.spec_from_file_location(
    "helios_io_stt_test", str(_pkg_dir / "io_stt.py")
)
_stt_mod = importlib.util.module_from_spec(_stt_spec)
_stt_spec.loader.exec_module(_stt_mod)
STTModule = _stt_mod.STTModule

# Also load HeliosState for poll() testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.helios_state import HeliosState


class TestSTTModuleGracefulDegradation:
    """Test that STTModule degrades gracefully when SDK, pyaudio, or mic is missing."""

    def test_disabled_by_config(self):
        """When enabled=False, module is not available and remains dormant."""
        stt = STTModule(enabled=False)
        assert not stt._available
        assert not stt.is_available

    def test_missing_credentials_logs_warning(self, caplog):
        """When credentials are missing, logs warning and remains dormant."""
        with patch.dict("os.environ", {}, clear=True):
            with caplog.at_level(logging.WARNING):
                stt = STTModule(
                    access_key="",
                    access_secret="",
                    app_key="",
                    enabled=True,
                )
        assert not stt._available
        assert not stt.is_available
        assert "credentials missing" in caplog.text.lower() or "dormant" in caplog.text.lower()

    def test_missing_nls_sdk_logs_warning(self, caplog):
        """When nls SDK is not importable, logs warning and remains dormant."""
        with patch.dict("sys.modules", {"nls": None}):
            with patch("builtins.__import__", side_effect=_import_mock_no_nls):
                with caplog.at_level(logging.WARNING):
                    stt = STTModule(
                        access_key="test_key",
                        access_secret="test_secret",
                        app_key="test_app_key",
                        enabled=True,
                    )
        assert not stt._available
        assert not stt.is_available

    def test_missing_pyaudio_logs_warning(self, caplog):
        """When pyaudio is not importable, logs warning and remains dormant."""
        mock_nls = MagicMock()
        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": None}):
            with patch("builtins.__import__", side_effect=_import_mock_no_pyaudio(mock_nls)):
                with caplog.at_level(logging.WARNING):
                    stt = STTModule(
                        access_key="test_key",
                        access_secret="test_secret",
                        app_key="test_app_key",
                        enabled=True,
                    )
        assert not stt._available

    def test_no_microphone_logs_warning(self, caplog):
        """When no microphone device is detected, logs warning and remains dormant."""
        mock_nls = MagicMock()
        mock_pyaudio = MagicMock()
        # Simulate no input devices
        mock_pa_instance = MagicMock()
        mock_pa_instance.get_device_count.return_value = 1
        mock_pa_instance.get_device_info_by_index.return_value = {"maxInputChannels": 0}
        mock_pyaudio.PyAudio.return_value = mock_pa_instance

        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": mock_pyaudio}):
            with patch("builtins.__import__", side_effect=_import_mock_all(mock_nls, mock_pyaudio)):
                with caplog.at_level(logging.WARNING):
                    stt = STTModule(
                        access_key="test_key",
                        access_secret="test_secret",
                        app_key="test_app_key",
                        enabled=True,
                    )
        assert not stt._available

    def test_full_init_with_microphone(self):
        """When all deps and mic are available, module is available."""
        mock_nls = MagicMock()
        mock_pyaudio = MagicMock()
        # Simulate a microphone device
        mock_pa_instance = MagicMock()
        mock_pa_instance.get_device_count.return_value = 2
        mock_pa_instance.get_device_info_by_index.side_effect = [
            {"maxInputChannels": 0},  # output device
            {"maxInputChannels": 1},  # input device (mic)
        ]
        mock_pyaudio.PyAudio.return_value = mock_pa_instance

        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": mock_pyaudio}):
            with patch("builtins.__import__", side_effect=_import_mock_all(mock_nls, mock_pyaudio)):
                stt = STTModule(
                    access_key="test_key",
                    access_secret="test_secret",
                    app_key="test_app_key",
                    enabled=True,
                )
        assert stt._available
        # Not yet registered
        assert not stt.is_available


class TestSTTModuleEventSourceInterface:
    """Test EventSource interface implementation (poll + get_messages)."""

    def _make_available_stt(self):
        """Helper to create an available and registered STTModule."""
        mock_nls = MagicMock()
        mock_pyaudio = MagicMock()
        mock_pa_instance = MagicMock()
        mock_pa_instance.get_device_count.return_value = 1
        mock_pa_instance.get_device_info_by_index.return_value = {"maxInputChannels": 1}
        mock_pyaudio.PyAudio.return_value = mock_pa_instance

        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": mock_pyaudio}):
            with patch("builtins.__import__", side_effect=_import_mock_all(mock_nls, mock_pyaudio)):
                stt = STTModule(
                    access_key="key",
                    access_secret="secret",
                    app_key="app_key",
                    enabled=True,
                )
        stt.register()
        return stt

    def test_poll_returns_empty_dict(self):
        """poll() always returns empty dict — triggers come from SEC evaluation."""
        stt = self._make_available_stt()
        state = HeliosState(tick=1, timestamp=time.time())
        result = stt.poll(state)
        assert result == {}

    def test_poll_returns_empty_when_dormant(self):
        """poll() returns empty dict even when module is dormant."""
        stt = STTModule(enabled=False)
        state = HeliosState(tick=1, timestamp=time.time())
        result = stt.poll(state)
        assert result == {}

    def test_get_messages_returns_empty_when_no_utterances(self):
        """get_messages() returns empty list when no utterances pending."""
        stt = self._make_available_stt()
        messages = stt.get_messages()
        assert messages == []

    def test_get_messages_returns_empty_when_dormant(self):
        """get_messages() returns empty list when module is dormant."""
        stt = STTModule(enabled=False)
        messages = stt.get_messages()
        assert messages == []

    def test_get_messages_returns_buffered_utterances(self):
        """get_messages() returns utterances buffered by _on_utterance_complete."""
        stt = self._make_available_stt()

        # Simulate ASR callback
        stt._on_utterance_complete("你好世界")
        stt._on_utterance_complete("今天天气怎么样")

        messages = stt.get_messages()
        assert len(messages) == 2
        assert messages[0]["text"] == "你好世界"
        assert messages[0]["source"] == "stt"
        assert messages[0]["user_id"] == "local_speaker"
        assert "timestamp" in messages[0]
        assert messages[1]["text"] == "今天天气怎么样"

    def test_get_messages_clears_buffer(self):
        """get_messages() clears the buffer after returning."""
        stt = self._make_available_stt()

        stt._on_utterance_complete("hello")
        messages = stt.get_messages()
        assert len(messages) == 1

        # Second call should be empty
        messages = stt.get_messages()
        assert messages == []

    def test_on_utterance_complete_ignores_empty_text(self):
        """_on_utterance_complete ignores empty or whitespace-only text."""
        stt = self._make_available_stt()

        stt._on_utterance_complete("")
        stt._on_utterance_complete("   ")
        stt._on_utterance_complete(None)

        messages = stt.get_messages()
        assert messages == []

    def test_on_utterance_complete_strips_whitespace(self):
        """_on_utterance_complete strips leading/trailing whitespace."""
        stt = self._make_available_stt()

        stt._on_utterance_complete("  hello world  ")

        messages = stt.get_messages()
        assert len(messages) == 1
        assert messages[0]["text"] == "hello world"


class TestSTTModuleRuntimePluggability:
    """Test register/deregister runtime pluggability."""

    def _make_available_stt(self):
        """Helper to create an available STTModule (not yet registered)."""
        mock_nls = MagicMock()
        mock_pyaudio = MagicMock()
        mock_pa_instance = MagicMock()
        mock_pa_instance.get_device_count.return_value = 1
        mock_pa_instance.get_device_info_by_index.return_value = {"maxInputChannels": 1}
        mock_pyaudio.PyAudio.return_value = mock_pa_instance

        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": mock_pyaudio}):
            with patch("builtins.__import__", side_effect=_import_mock_all(mock_nls, mock_pyaudio)):
                stt = STTModule(
                    access_key="key",
                    access_secret="secret",
                    app_key="app_key",
                    enabled=True,
                )
        return stt

    def test_register_activates_module(self):
        """After register(), is_available becomes True (when hardware available)."""
        stt = self._make_available_stt()
        assert not stt.is_available
        stt.register()
        assert stt.is_available

    def test_deregister_deactivates_module(self):
        """After deregister(), is_available becomes False."""
        stt = self._make_available_stt()
        stt.register()
        assert stt.is_available
        stt.deregister()
        assert not stt.is_available

    def test_register_when_unavailable_is_noop(self):
        """Registering when hardware unavailable doesn't crash."""
        stt = STTModule(enabled=True, access_key="", access_secret="", app_key="")
        stt.register()
        assert not stt.is_available

    def test_get_messages_not_available_after_deregister(self):
        """After deregister, get_messages returns empty even with buffered data."""
        stt = self._make_available_stt()
        stt.register()
        stt._on_utterance_complete("hello")
        stt.deregister()
        # Module is no longer available, so get_messages returns empty
        messages = stt.get_messages()
        assert messages == []


class TestSTTModuleGetState:
    """Test get_state() method."""

    def test_get_state_dormant(self):
        """get_state reflects dormant state."""
        stt = STTModule(enabled=False)
        state = stt.get_state()
        assert state["enabled"] is False
        assert state["available"] is False
        assert state["registered"] is False
        assert state["listening"] is False
        assert state["is_available"] is False

    def test_get_state_available_registered(self):
        """get_state reflects available + registered state."""
        mock_nls = MagicMock()
        mock_pyaudio = MagicMock()
        mock_pa_instance = MagicMock()
        mock_pa_instance.get_device_count.return_value = 1
        mock_pa_instance.get_device_info_by_index.return_value = {"maxInputChannels": 1}
        mock_pyaudio.PyAudio.return_value = mock_pa_instance

        with patch.dict("sys.modules", {"nls": mock_nls, "pyaudio": mock_pyaudio}):
            with patch("builtins.__import__", side_effect=_import_mock_all(mock_nls, mock_pyaudio)):
                stt = STTModule(
                    access_key="key",
                    access_secret="secret",
                    app_key="app_key",
                    enabled=True,
                )
        stt.register()
        state = stt.get_state()
        assert state["enabled"] is True
        assert state["available"] is True
        assert state["registered"] is True
        assert state["is_available"] is True
        assert state["pending_utterances"] == 0


# --- Import mock helpers ---

def _import_mock_no_nls(name, *args, **kwargs):
    """Mock import that raises ImportError for 'nls'."""
    if name == "nls":
        raise ImportError("No module named 'nls'")
    return _original_import(name, *args, **kwargs)


def _import_mock_no_pyaudio(mock_nls):
    """Return a mock import that provides nls but raises ImportError for pyaudio."""
    def _mock(name, *args, **kwargs):
        if name == "nls":
            return mock_nls
        if name == "pyaudio":
            raise ImportError("No module named 'pyaudio'")
        return _original_import(name, *args, **kwargs)
    return _mock


def _import_mock_all(mock_nls, mock_pyaudio):
    """Return a mock import that provides both nls and pyaudio."""
    def _mock(name, *args, **kwargs):
        if name == "nls":
            return mock_nls
        if name == "pyaudio":
            return mock_pyaudio
        return _original_import(name, *args, **kwargs)
    return _mock


_original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
