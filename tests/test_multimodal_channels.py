"""Focused tests for task-25 multimodal channels."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.channels import stt_channel as stt_mod
from helios_io.channels import tts_channel as tts_mod
from helios_io.channels import vision_channel as vision_mod
from helios_io.channel import InputChannel, OutputChannel

from helios_main import Helios, HeliosConfig


def test_tts_channel_dormant_without_credentials():
    channel = tts_mod.TTSChannel(access_key="", access_secret="", app_key="", enabled=True)

    assert channel.is_available is False
    assert channel.is_connected() is False


def test_tts_channel_send_uses_injected_synth_and_player():
    played = []
    channel = tts_mod.TTSChannel(
        enabled=True,
        force_available=True,
        synthesize_func=lambda text: f"audio:{text}",
        play_func=lambda audio: played.append(audio) or True,
    )
    channel.connect()

    ok = channel.send(
        tts_mod.ChannelMessage(
            channel_id="tts",
            user_id="speaker",
            text="hello",
            timestamp=time.time(),
            direction="outbound",
        )
    )

    assert ok is True
    assert played == ["audio:hello"]


def test_stt_channel_poll_returns_utterance_messages():
    channel = stt_mod.STTChannel(enabled=True, force_available=True)
    channel.connect()
    channel._on_utterance_complete("hello there")

    messages = channel.poll()

    assert len(messages) == 1
    assert messages[0].channel_id == "stt"
    assert messages[0].text == "hello there"


def test_vision_channel_poll_returns_described_scene_once_per_interval():
    channel = vision_mod.VisionChannel(
        enabled=True,
        force_available=True,
        capture_interval=5.0,
        capture_func=lambda: {"frame": 1},
        vision_describer=lambda _frame: "A person smiles in a sunny room",
    )
    channel.connect()

    first = channel.poll()
    second = channel.poll()

    assert len(first) == 1
    assert first[0].channel_id == "vision"
    assert "cognitive_impact" in first[0].metadata
    assert first[0].metadata["event_triggers"]["CARE"] > 0.0
    assert second == []


def test_helios_registers_only_available_optional_channels(monkeypatch, tmp_path):
    class FakeTTS(OutputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "tts"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def send(self, message):
            return True

    class FakeSTT(InputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "stt"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

    class FakeVision(InputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "vision"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def evaluate_message(self, message, state=None):
            return {}

    monkeypatch.setattr("helios_main.TTSChannel", FakeTTS)
    monkeypatch.setattr("helios_main.STTChannel", FakeSTT)
    monkeypatch.setattr("helios_main.VisionChannel", FakeVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    statuses = helios._channel_gateway.get_channel_status()

    assert "tts" in statuses
    assert "vision" in statuses
    assert "stt" not in statuses

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)