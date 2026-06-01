"""Focused tests for task-25 multimodal channels."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.channels import cli_channel as cli_mod
from helios_io.channels import stt_channel as stt_mod
from helios_io.channels import tts_channel as tts_mod
from helios_io.channels import vision_channel as vision_mod
from helios_io.channel import ChannelManagementResult, ChannelStatus, InputChannel, OutputChannel
from helios_io import optional_channel_bootstrap as optional_bootstrap_mod
from helios_io.optional_channel_bootstrap import OptionalChannelBootstrapManager, OptionalChannelBootstrapRegistry, OptionalChannelBootstrapSpec

from helios_main import Helios, HeliosConfig


def _patch_optional_bootstrap_channels(
    monkeypatch,
    *,
    tts=None,
    cli=None,
    stt=None,
    vision=None,
):
    if tts is not None:
        monkeypatch.setattr("helios_main.TTSChannel", tts)
        monkeypatch.setattr(tts_mod, "TTSChannel", tts)
    if cli is not None:
        monkeypatch.setattr("helios_main.CLIChannel", cli)
        monkeypatch.setattr(cli_mod, "CLIChannel", cli)
    if stt is not None:
        monkeypatch.setattr("helios_main.STTChannel", stt)
        monkeypatch.setattr(stt_mod, "STTChannel", stt)
    if vision is not None:
        monkeypatch.setattr("helios_main.VisionChannel", vision)
        monkeypatch.setattr(vision_mod, "VisionChannel", vision)


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


def test_tts_channel_management_ops_expose_config_and_pause_state():
    channel = tts_mod.TTSChannel(enabled=True, force_available=True)

    config_result = channel.execute_management_op("get_config")
    channel.connect()
    pause_result = channel.execute_management_op("pause")
    resume_result = channel.execute_management_op("resume")

    assert config_result.success is True
    assert config_result.payload["snapshot"]["voice"] == "xiaoyun"
    assert pause_result.status == "paused"
    assert resume_result.success is True


def test_tts_channel_send_passes_intensity_and_metadata_when_supported():
    captured = {}

    def synthesize(*, text, intensity=0.0, metadata=None, voice=""):
        captured["text"] = text
        captured["intensity"] = intensity
        captured["metadata"] = dict(metadata or {})
        captured["voice"] = voice
        return f"audio:{text}:{intensity:.2f}"

    played = []
    channel = tts_mod.TTSChannel(
        enabled=True,
        force_available=True,
        synthesize_func=synthesize,
        play_func=lambda audio: played.append(audio) or True,
    )
    channel.connect()

    channel_message = tts_mod.ChannelMessage(
        channel_id="tts",
        user_id="speaker",
        text="hello",
        timestamp=time.time(),
        metadata={"normalized_intensity": 0.72, "outbound_intensity": 0.72},
        direction="outbound",
    )

    ok = channel.send(channel_message)

    assert ok is True
    assert captured["text"] == "hello!"
    assert captured["intensity"] == 0.72
    assert captured["metadata"]["outbound_intensity"] == 0.72
    assert captured["metadata"]["expression_profile"]["tone"] == "direct"
    assert channel_message.metadata["rendered_text"] == "hello!"
    assert played == ["audio:hello!:0.72"]


def test_tts_channel_softens_text_when_outbound_intensity_is_low():
    captured = {}

    def synthesize(*, text, intensity=0.0, metadata=None, voice=""):
        captured["text"] = text
        captured["intensity"] = intensity
        captured["metadata"] = dict(metadata or {})
        return f"audio:{text}:{intensity:.2f}"

    channel = tts_mod.TTSChannel(
        enabled=True,
        force_available=True,
        synthesize_func=synthesize,
        play_func=lambda _audio: True,
    )
    channel.connect()

    ok = channel.send(
        tts_mod.ChannelMessage(
            channel_id="tts",
            user_id="speaker",
            text="hello!!!",
            timestamp=time.time(),
            metadata={"outbound_intensity": 0.18},
            direction="outbound",
        )
    )

    assert ok is True
    assert captured["text"] == "hello."
    assert captured["metadata"]["expression_profile"]["tone"] == "measured"


def test_stt_channel_poll_returns_utterance_messages():
    channel = stt_mod.STTChannel(enabled=True, force_available=True)
    channel.connect()
    channel._on_utterance_complete("hello there")

    messages = channel.poll()

    assert len(messages) == 1
    assert messages[0].channel_id == "stt"
    assert messages[0].text == "hello there"


def test_stt_channel_management_ops_update_config():
    channel = stt_mod.STTChannel(enabled=True, force_available=True)

    result = channel.execute_management_op("update_config", {"config": {"enabled": False}})

    assert result.success is True
    assert result.payload["snapshot"]["enabled"] is False


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


def test_vision_channel_management_ops_validate_capture_interval():
    channel = vision_mod.VisionChannel(enabled=True, force_available=True)

    bad = channel.execute_management_op("update_config", {"config": {"capture_interval": 0}})
    good = channel.execute_management_op("update_config", {"config": {"capture_interval": 2.5}})

    assert bad.success is False
    assert "capture_interval must be > 0" in bad.payload["validation_errors"]
    assert good.success is True
    assert good.payload["snapshot"]["capture_interval"] == 2.5


def test_helios_registers_only_available_optional_channels(monkeypatch, tmp_path):
    created: dict[str, object] = {}

    class FakeTTS(OutputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False
            created["tts"] = self

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
            created["stt"] = self

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
            created["vision"] = self

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

    _patch_optional_bootstrap_channels(monkeypatch, tts=FakeTTS, stt=FakeSTT, vision=FakeVision)

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


def test_helios_respects_configured_default_optional_channel_roster(monkeypatch, tmp_path):
    created: dict[str, object] = {}

    class FakeTTS(OutputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False
            created["tts"] = self

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

    class FakeCLI(InputChannel, OutputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False
            created["cli"] = self

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def send(self, message):
            return True

    class FakeSTT(InputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False
            created["stt"] = self

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
            created["vision"] = self

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

    _patch_optional_bootstrap_channels(monkeypatch, tts=FakeTTS, cli=FakeCLI, stt=FakeSTT, vision=FakeVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False
    config.OPTIONAL_CHANNEL_BOOTSTRAP_IDS = ("cli", "vision")

    helios = Helios(config)

    assert helios.optional_channels.get_factory_ids() == ("cli", "vision")
    assert set(helios.optional_channels.get_specs()) == {"cli", "vision"}
    assert helios.get_runtime_channel("cli") is created["cli"]
    assert helios.get_runtime_channel("vision") is created["vision"]
    assert helios.get_runtime_channel("tts") is None
    assert helios.get_runtime_channel("stt") is None
    assert "tts" not in created
    assert "stt" not in created

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_helios_optional_channel_activity_follows_gateway_registry(monkeypatch, tmp_path):
    created: dict[str, object] = {}

    class FakeTTS(OutputChannel):
        is_available = True

        def __init__(self, *args, **kwargs):
            self.connected = False
            created["tts"] = self

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
            created["stt"] = self

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
            created["vision"] = self

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

    _patch_optional_bootstrap_channels(monkeypatch, tts=FakeTTS, stt=FakeSTT, vision=FakeVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    tts_channel = helios.get_runtime_channel("tts")

    assert helios.optional_channels.is_runtime_active("tts") is True
    assert helios.optional_channels.is_runtime_active("vision") is True
    assert helios.optional_channels.is_runtime_active("stt") is False
    assert tts_channel is not None

    helios._channel_gateway.deregister_channel("tts")

    assert helios.optional_channels.is_runtime_active("tts") is False
    assert helios.get_runtime_channel("tts") is None
    assert created["tts"].is_available is True

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_helios_builds_optional_channels_from_bootstrap_payloads(monkeypatch, tmp_path):
    captured: dict[str, dict] = {}

    class FakeTTS(OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            captured["tts"] = dict(kwargs)
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

    class FakeCLI(InputChannel, OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            captured["cli"] = dict(kwargs)
            self.connected = False

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def send(self, message):
            return True

    class FakeSTT(InputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            captured["stt"] = dict(kwargs)
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
        is_available = False

        def __init__(self, *args, **kwargs):
            captured["vision"] = dict(kwargs)
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

    _patch_optional_bootstrap_channels(monkeypatch, tts=FakeTTS, cli=FakeCLI, stt=FakeSTT, vision=FakeVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False
    config.ALI_ACCESS_KEY = "ak"
    config.ALI_SECRET_KEY = "sk"
    config.ALI_APP_KEY = "app"
    config.TTS_ENABLED = True
    config.STT_ENABLED = False
    config.VISION_CAPTURE_INTERVAL = 7.5
    config.VISION_ENABLED = True
    config.CLI_ENABLED = True
    config.CLI_USER_ID = "operator"
    config.CLI_SESSION_NAME = "local-session"

    helios = Helios(config)
    optional_specs = helios.optional_channels.get_specs()

    assert set(helios.optional_channels.get_factory_ids()) == {"tts", "cli", "stt", "vision"}
    assert set(optional_specs) == {"tts", "cli", "stt", "vision"}
    assert optional_specs["tts"].channel_id == "tts"
    assert optional_specs["vision"].payload["capture_interval"] == 7.5
    assert optional_specs["tts"].payload["enabled"] is True
    assert optional_specs["vision"].payload["capture_interval"] == 7.5
    assert captured["tts"]["access_key"] == "ak"
    assert captured["stt"]["enabled"] is False
    assert captured["vision"]["enabled"] is True
    assert captured["cli"]["user_id"] == "operator"
    assert captured["cli"]["session_name"] == "local-session"
    assert callable(captured["cli"]["state_provider"])
    assert callable(captured["cli"]["history_provider"])
    assert captured["cli"]["sec_evaluator"] is helios.sec_evaluator

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_helios_get_state_exposes_optional_channel_runtime_snapshot(monkeypatch, tmp_path):
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

    class FakeCLI(InputChannel, OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

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
        is_available = False

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

    _patch_optional_bootstrap_channels(monkeypatch, tts=FakeTTS, cli=FakeCLI, stt=FakeSTT, vision=FakeVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    state = helios.get_state()

    assert state["optional_channels"]["factory_ids"] == ["tts", "cli", "stt", "vision"]
    assert state["optional_channels"]["spec_ids"] == ["tts", "cli", "stt", "vision"]
    assert state["optional_channels"]["runtime_active_channel_ids"] == ["tts"]
    assert state["optional_channels"]["bootstrap_summary"] == {
        "active_channel_ids": ["tts"],
        "dormant_channel_ids": ["cli", "stt", "vision"],
        "failed_channel_ids": [],
    }

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_default_optional_channel_bootstrap_builder_registry_can_add_and_remove_dynamic_builder():
    builder_ids_before = set(optional_bootstrap_mod.get_default_optional_channel_bootstrap_factory_builders())

    def dynamic_builder(**kwargs):
        return lambda: OptionalChannelBootstrapSpec(
            channel_id="dynamic_default",
            factory=dict,
            payload={
                "enabled": True,
                "has_state_provider": kwargs["state_provider"] is not None,
                "has_history_provider": kwargs["history_provider"] is not None,
                "sec_evaluator": kwargs["sec_evaluator"],
            },
        )

    optional_bootstrap_mod.register_default_optional_channel_bootstrap_factory_builder("dynamic_default", dynamic_builder)
    try:
        factories = optional_bootstrap_mod.build_default_optional_channel_bootstrap_factories(
            cfg=object(),
            state_provider=lambda: {},
            history_provider=lambda _user_id, _conversation_key: [],
            sec_evaluator="sec",
        )
        spec = factories["dynamic_default"]()

        assert "dynamic_default" in optional_bootstrap_mod.get_default_optional_channel_bootstrap_factory_builders()
        assert set(factories) == builder_ids_before | {"dynamic_default"}
        assert spec.channel_id == "dynamic_default"
        assert spec.payload["enabled"] is True
        assert spec.payload["has_state_provider"] is True
        assert spec.payload["has_history_provider"] is True
        assert spec.payload["sec_evaluator"] == "sec"
    finally:
        removed = optional_bootstrap_mod.deregister_default_optional_channel_bootstrap_factory_builder("dynamic_default")
        assert removed is True
        assert set(optional_bootstrap_mod.get_default_optional_channel_bootstrap_factory_builders()) == builder_ids_before


def test_optional_channel_bootstrap_registry_manages_factories_and_specs():
    registry = OptionalChannelBootstrapRegistry(
        {
            "alpha": lambda: OptionalChannelBootstrapSpec(
                channel_id="alpha",
                factory=dict,
                payload={"enabled": True},
            )
        }
    )

    rebuilt_specs = registry.rebuild_specs()

    assert set(registry.get_factory_ids()) == {"alpha"}
    assert set(rebuilt_specs) == {"alpha"}
    assert rebuilt_specs["alpha"].payload["enabled"] is True

    dynamic_spec = registry.register_factory(
        "beta",
        lambda: OptionalChannelBootstrapSpec(
            channel_id="beta",
            factory=list,
            payload={"enabled": False},
        ),
    )

    assert dynamic_spec.channel_id == "beta"
    assert registry.has_spec("beta") is True
    assert set(registry.get_specs()) == {"alpha", "beta"}

    removed_spec = registry.deregister_spec("beta")

    assert removed_spec is not None
    assert removed_spec.channel_id == "beta"
    assert registry.has_spec("beta") is False
    assert registry.deregister_factory("beta") is True
    assert set(registry.get_factory_ids()) == {"alpha"}


def test_optional_channel_bootstrap_manager_delegates_bootstrap_and_runtime_cleanup():
    runtime_channels = {"alpha"}
    deregistered = []

    manager = OptionalChannelBootstrapManager(
        registry=OptionalChannelBootstrapRegistry(
            {
                "alpha": lambda: OptionalChannelBootstrapSpec(
                    channel_id="alpha",
                    factory=dict,
                    payload={"enabled": True},
                )
            }
        ),
        bootstrap_spec=lambda spec: ChannelManagementResult(
            channel_id=spec.channel_id,
            op_name="bootstrap_optional_channel_spec",
            success=True,
            status=ChannelStatus.CONNECTED.value,
            payload={"runtime_registered": True, "spec_registered": True},
        ),
        runtime_channel_active=lambda channel_id: channel_id in runtime_channels,
        deregister_runtime_channel=lambda channel_id, disconnect: deregistered.append((channel_id, disconnect)) or runtime_channels.discard(channel_id) or ChannelManagementResult(
            channel_id=channel_id,
            op_name="deregister",
            success=True,
            status=ChannelStatus.DEINITIALIZED.value,
            message="Channel deregistered.",
        ),
    )
    manager._registry.rebuild_specs()

    bootstrap_results = manager.bootstrap_all()

    assert len(bootstrap_results) == 1
    assert bootstrap_results[0][0].channel_id == "alpha"
    assert bootstrap_results[0][1].payload["runtime_registered"] is True

    deregister_result = manager.deregister_spec("alpha")

    assert deregister_result.success is True
    assert deregistered == [("alpha", True)]
    assert manager.get_specs() == {}


def test_optional_channel_runtime_bootstrap_summary_tracks_active_dormant_and_failures():
    warnings = []
    debugs = []
    runtime = optional_bootstrap_mod.OptionalChannelRuntime(
        manager=OptionalChannelBootstrapManager(
            registry=OptionalChannelBootstrapRegistry(
                {
                    "alpha": lambda: OptionalChannelBootstrapSpec(
                        channel_id="alpha",
                        factory=dict,
                        payload={"enabled": True},
                    ),
                    "beta": lambda: OptionalChannelBootstrapSpec(
                        channel_id="beta",
                        factory=dict,
                        payload={"enabled": False},
                    ),
                }
            ),
            bootstrap_spec=lambda spec: ChannelManagementResult(
                channel_id=spec.channel_id,
                op_name="bootstrap_optional_channel_spec",
                success=spec.channel_id != "beta",
                status=ChannelStatus.CONNECTED.value if spec.channel_id == "alpha" else ChannelStatus.ERROR.value,
                message="Channel connected." if spec.channel_id == "alpha" else "Connect failed.",
                payload={"runtime_registered": spec.channel_id == "alpha", "spec_registered": True},
            ),
            runtime_channel_active=lambda channel_id: channel_id == "alpha",
            deregister_runtime_channel=lambda channel_id, disconnect: ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister",
                success=True,
                status=ChannelStatus.DEINITIALIZED.value,
            ),
        ),
        register_runtime_channel=lambda _channel: ChannelManagementResult(
            channel_id="unused",
            op_name="register",
            success=True,
            status=ChannelStatus.CONNECTED.value,
        ),
    )
    runtime._manager._registry.rebuild_specs()

    class FakeLogger:
        def warning(self, message, *args):
            warnings.append(message % args)

        def debug(self, message, *args):
            debugs.append(message % args)

    summary = runtime.bootstrap_defaults(logger=FakeLogger())

    assert summary.active_channel_ids == ("alpha",)
    assert summary.dormant_channel_ids == ("beta",)
    assert summary.failed_channel_ids == ("beta",)
    assert runtime.get_last_bootstrap_summary() == summary
    assert warnings == ["Optional channel beta connect failed during bootstrap: Connect failed."]
    assert debugs == ["Active optional channels: alpha", "Dormant optional channels: beta"]


def test_optional_channel_runtime_invalidates_cached_bootstrap_summary_after_runtime_mutation():
    runtime = optional_bootstrap_mod.OptionalChannelRuntime(
        manager=OptionalChannelBootstrapManager(
            registry=OptionalChannelBootstrapRegistry(
                {
                    "alpha": lambda: OptionalChannelBootstrapSpec(
                        channel_id="alpha",
                        factory=dict,
                        payload={"enabled": True},
                    )
                }
            ),
            bootstrap_spec=lambda spec: ChannelManagementResult(
                channel_id=spec.channel_id,
                op_name="bootstrap_optional_channel_spec",
                success=True,
                status=ChannelStatus.CONNECTED.value,
                payload={"runtime_registered": True, "spec_registered": True},
            ),
            runtime_channel_active=lambda _channel_id: True,
            deregister_runtime_channel=lambda channel_id, disconnect: ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister",
                success=True,
                status=ChannelStatus.DEINITIALIZED.value,
            ),
        ),
        register_runtime_channel=lambda _channel: ChannelManagementResult(
            channel_id="unused",
            op_name="register",
            success=True,
            status=ChannelStatus.CONNECTED.value,
        ),
    )
    runtime._manager._registry.rebuild_specs()

    bootstrap_summary = runtime.bootstrap_defaults()
    register_result = runtime.register_spec(
        OptionalChannelBootstrapSpec(
            channel_id="beta",
            factory=dict,
            payload={"enabled": False},
        ),
        bootstrap=False,
    )

    assert bootstrap_summary.active_channel_ids == ("alpha",)
    assert register_result.success is True
    assert runtime.get_last_bootstrap_summary() is None


def test_helios_optional_channel_factory_registry_can_add_and_remove_dynamic_factories(tmp_path, monkeypatch):
    class DormantTTS(OutputChannel):
        is_available = False

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

    class DormantCLI(InputChannel, OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def send(self, message):
            return True

    class DormantSTT(InputChannel):
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

    class DormantVision(InputChannel):
        is_available = False

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

    created = []

    class DynamicFactoryChannel(OutputChannel):
        is_available = True

        def __init__(self, enabled=True):
            self.enabled = enabled
            self.connected = False
            created.append(self)

        @property
        def channel_id(self):
            return "dynamic_factory"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def send(self, message):
            return True

        def execute_management_op(self, op_name: str, payload=None):
            if op_name == "connect":
                self.connect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.CONNECTED.value)
            if op_name == "disconnect":
                self.disconnect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.DISCONNECTED.value)
            return ChannelManagementResult(self.channel_id, op_name, False, ChannelStatus.ERROR.value, error_code="unsupported")

    _patch_optional_bootstrap_channels(monkeypatch, tts=DormantTTS, cli=DormantCLI, stt=DormantSTT, vision=DormantVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    register_result = helios.optional_channels.register_factory(
        "dynamic_factory",
        lambda: OptionalChannelBootstrapSpec(
            channel_id="dynamic_factory",
            factory=DynamicFactoryChannel,
            payload={"enabled": True},
        ),
    )

    assert register_result.success is True
    assert "dynamic_factory" in helios.optional_channels.get_factory_ids()
    assert "dynamic_factory" in helios.optional_channels.get_specs()
    assert helios.get_runtime_channel("dynamic_factory") is created[-1]

    deregister_result = helios.optional_channels.deregister_factory("dynamic_factory")

    assert deregister_result.success is True
    assert "dynamic_factory" not in helios.optional_channels.get_factory_ids()
    assert "dynamic_factory" not in helios.optional_channels.get_specs()
    assert helios.get_runtime_channel("dynamic_factory") is None

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_helios_runtime_channel_owner_api_registers_and_deregisters(monkeypatch, tmp_path):
    class DormantTTS(OutputChannel):
        is_available = False

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

    class DormantCLI(InputChannel, OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def send(self, message):
            return True

    class DormantSTT(InputChannel):
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

    class DormantVision(InputChannel):
        is_available = False

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

    class DynamicStub(OutputChannel):
        def __init__(self):
            self.connected = False
            self.disconnect_calls = 0

        @property
        def channel_id(self):
            return "dynamic"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.disconnect_calls += 1
            self.connected = False

        def is_connected(self):
            return self.connected

        def send(self, message):
            return True

        def evaluate_message(self, message, state=None):
            return {"CARE": 0.2}

        def execute_management_op(self, op_name: str, payload=None):
            if op_name == "connect":
                self.connect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.CONNECTED.value)
            if op_name == "disconnect":
                self.disconnect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.DISCONNECTED.value)
            return ChannelManagementResult(self.channel_id, op_name, False, ChannelStatus.ERROR.value, error_code="unsupported")

    _patch_optional_bootstrap_channels(monkeypatch, tts=DormantTTS, cli=DormantCLI, stt=DormantSTT, vision=DormantVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    channel = DynamicStub()

    register_result = helios.register_runtime_channel(channel)

    assert register_result.success is True
    assert helios._channel_gateway.has_channel("dynamic") is True
    assert helios._channel_gateway.get_channel_status()["dynamic"] == ChannelStatus.CONNECTED

    deregister_result = helios.deregister_runtime_channel("dynamic")

    assert deregister_result.success is True
    assert channel.disconnect_calls == 1
    assert helios._channel_gateway.has_channel("dynamic") is False

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def test_helios_optional_channel_spec_registry_can_add_and_remove_dynamic_specs(monkeypatch, tmp_path):
    class DormantTTS(OutputChannel):
        is_available = False

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

    class DormantCLI(InputChannel, OutputChannel):
        is_available = False

        def __init__(self, *args, **kwargs):
            self.connected = False

        @property
        def channel_id(self):
            return "cli"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        def poll(self):
            return []

        def send(self, message):
            return True

    class DormantSTT(InputChannel):
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

    class DormantVision(InputChannel):
        is_available = False

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

    class DynamicOptional(OutputChannel):
        is_available = True

        def __init__(self, enabled=True):
            self.enabled = enabled
            self.connected = False
            self.disconnect_calls = 0

        @property
        def channel_id(self):
            return "dynamic_optional"

        def connect(self):
            self.connected = True

        def disconnect(self):
            self.disconnect_calls += 1
            self.connected = False

        def is_connected(self):
            return self.connected

        def send(self, message):
            return True

        def execute_management_op(self, op_name: str, payload=None):
            if op_name == "connect":
                self.connect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.CONNECTED.value)
            if op_name == "disconnect":
                self.disconnect()
                return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.DISCONNECTED.value)
            return ChannelManagementResult(self.channel_id, op_name, False, ChannelStatus.ERROR.value, error_code="unsupported")

    _patch_optional_bootstrap_channels(monkeypatch, tts=DormantTTS, cli=DormantCLI, stt=DormantSTT, vision=DormantVision)

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    spec = OptionalChannelBootstrapSpec(
        channel_id="dynamic_optional",
        factory=DynamicOptional,
        payload={"enabled": True},
    )

    register_result = helios.optional_channels.register_spec(spec)

    assert register_result.success is True
    assert "dynamic_optional" in helios.optional_channels.get_specs()
    assert helios.get_runtime_channel("dynamic_optional") is not None

    deregister_result = helios.optional_channels.deregister_spec("dynamic_optional")

    assert deregister_result.success is True
    assert "dynamic_optional" not in helios.optional_channels.get_specs()
    assert helios.get_runtime_channel("dynamic_optional") is None

    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)