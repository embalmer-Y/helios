"""
Tests for TTSModule graceful degradation and runtime pluggability.

Validates Requirements 30.1, 30.2, 30.3, 30.4
"""

import logging
import sys
from unittest.mock import patch, MagicMock

import pytest


# Load the TTSModule via importlib to avoid 'io' stdlib conflict
import importlib.util
from pathlib import Path

_pkg_dir = Path(__file__).parent.parent / "io"
_tts_spec = importlib.util.spec_from_file_location(
    "helios_io_tts_test", str(_pkg_dir / "io_tts.py")
)
_tts_mod = importlib.util.module_from_spec(_tts_spec)
_tts_spec.loader.exec_module(_tts_mod)
TTSModule = _tts_mod.TTSModule


class TestTTSModuleGracefulDegradation:
    """Test that TTSModule degrades gracefully when SDK or credentials are missing."""

    def test_disabled_by_config(self):
        """When enabled=False, module is not available."""
        tts = TTSModule(enabled=False)
        assert not tts._available
        assert not tts.is_available

    def test_missing_credentials_logs_warning(self, caplog):
        """When credentials are missing, logs warning and is not available."""
        with patch.dict("os.environ", {}, clear=True):
            with caplog.at_level(logging.WARNING):
                tts = TTSModule(
                    access_key="",
                    access_secret="",
                    app_key="",
                    enabled=True,
                )
        assert not tts._available
        assert not tts.is_available
        assert "credentials missing" in caplog.text.lower() or "text-only" in caplog.text.lower()

    def test_missing_sdk_logs_warning(self, caplog):
        """When nls SDK is not importable, logs warning and is not available."""
        # Temporarily make nls unimportable
        with patch.dict("sys.modules", {"nls": None}):
            with patch("builtins.__import__", side_effect=_import_mock_no_nls):
                with caplog.at_level(logging.WARNING):
                    tts = TTSModule(
                        access_key="test_key",
                        access_secret="test_secret",
                        app_key="test_app_key",
                        enabled=True,
                    )
        assert not tts._available
        assert not tts.is_available

    def test_credentials_from_env(self):
        """When credentials are in env vars, module initializes (if SDK available)."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "env_key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "env_secret",
            "ALIBABA_NLS_APP_KEY": "env_app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True)
        assert tts._available
        # Not yet registered
        assert not tts.is_available

    def test_synthesize_and_play_noop_when_unavailable(self):
        """synthesize_and_play is a no-op when not available."""
        tts = TTSModule(enabled=False)
        result = tts.synthesize_and_play("hello")
        assert result is False

    def test_synthesize_and_play_noop_when_not_registered(self):
        """synthesize_and_play is a no-op when available but not registered."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "secret",
            "ALIBABA_NLS_APP_KEY": "app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True)
        assert tts._available
        assert not tts.is_available  # not registered
        result = tts.synthesize_and_play("hello")
        assert result is False

    def test_synthesize_empty_text_returns_false(self):
        """synthesize_and_play returns False for empty text."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "secret",
            "ALIBABA_NLS_APP_KEY": "app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True)
        tts.register()
        result = tts.synthesize_and_play("")
        assert result is False
        result = tts.synthesize_and_play("   ")
        assert result is False


class TestTTSModuleRuntimePluggability:
    """Test register/deregister runtime pluggability."""

    def test_register_activates_module(self):
        """After register(), is_available becomes True (when SDK available)."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "secret",
            "ALIBABA_NLS_APP_KEY": "app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True)
        assert not tts.is_available
        tts.register()
        assert tts.is_available

    def test_deregister_deactivates_module(self):
        """After deregister(), is_available becomes False."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "secret",
            "ALIBABA_NLS_APP_KEY": "app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True)
        tts.register()
        assert tts.is_available
        tts.deregister()
        assert not tts.is_available

    def test_register_when_unavailable_is_noop(self):
        """Registering when SDK unavailable doesn't crash."""
        tts = TTSModule(enabled=True, access_key="", access_secret="", app_key="")
        tts.register()
        assert not tts.is_available  # still not available

    def test_get_state_reflects_status(self):
        """get_state() returns correct module status."""
        tts = TTSModule(enabled=False)
        state = tts.get_state()
        assert state["enabled"] is False
        assert state["available"] is False
        assert state["registered"] is False
        assert state["is_available"] is False


class TestTTSModuleGetState:
    """Test get_state() method."""

    def test_get_state_with_available_module(self):
        """get_state reflects available + registered state."""
        mock_nls = MagicMock()
        with patch.dict("os.environ", {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "secret",
            "ALIBABA_NLS_APP_KEY": "app_key",
        }):
            with patch.dict("sys.modules", {"nls": mock_nls}):
                tts = TTSModule(enabled=True, voice="zhiyan")
        tts.register()
        state = tts.get_state()
        assert state["enabled"] is True
        assert state["available"] is True
        assert state["registered"] is True
        assert state["is_available"] is True
        assert state["voice"] == "zhiyan"


def _import_mock_no_nls(name, *args, **kwargs):
    """Mock import that raises ImportError for 'nls'."""
    if name == "nls":
        raise ImportError("No module named 'nls'")
    return original_import(name, *args, **kwargs)


original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
