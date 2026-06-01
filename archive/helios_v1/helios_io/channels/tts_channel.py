"""Optional TTS output channel for Helios."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from ..channel import ChannelConfigFieldDescriptor, ChannelConfigSnapshot, ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelOpDescriptor, ChannelStatus, OutputChannel
from ..expression_modulation import modulate_outbound_expression
from ..optional_channel_contract import OptionalChannelBootstrapFactory, OptionalChannelBootstrapSpec

log = logging.getLogger("helios.helios_io.channels.tts_channel")


class TTSChannel(OutputChannel):
    CHANNEL_ID = "tts"

    def __init__(
        self,
        access_key: str = "",
        access_secret: str = "",
        app_key: str = "",
        voice: str = "xiaoyun",
        enabled: bool = True,
        synthesize_func: Optional[Callable[..., Any]] = None,
        play_func: Optional[Callable[[Any], bool]] = None,
        force_available: Optional[bool] = None,
    ):
        self._voice = voice
        self._enabled = enabled
        self._synthesize_func = synthesize_func
        self._play_func = play_func
        self._connected = False
        self._available = False
        self._status = ChannelStatus.UNINITIALIZED
        self._paused = False
        self._suspended = False
        self._nls = None

        self._access_key = access_key or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        self._access_secret = access_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        self._app_key = app_key or os.getenv("ALIBABA_CLOUD_APP_KEY", "")

        if force_available is not None:
            self._available = bool(force_available)
            self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            return

        if not enabled:
            self._status = ChannelStatus.DISCONNECTED
            return
        if not all([self._access_key, self._access_secret, self._app_key]):
            log.debug("TTS credentials missing — remaining dormant")
            self._status = ChannelStatus.DISCONNECTED
            return
        try:
            import nls  # type: ignore

            self._nls = nls
            self._available = True
            self._status = ChannelStatus.INITIALIZED
        except ImportError:
            log.debug("nls SDK not installed — TTS channel dormant")
            self._status = ChannelStatus.DISCONNECTED

    @property
    def channel_id(self) -> str:
        return self.CHANNEL_ID

    @property
    def is_available(self) -> bool:
        return self._available and self._enabled

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self.CHANNEL_ID,
            display_name="TTS Channel",
            input_types=[],
            output_types=["speech_audio"],
            input_formats=[],
            output_formats=["audio/playback", "speech"],
            capabilities=["send", "speech_output", "audio_playback"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="send",
                    direction="output",
                    description="Synthesize outbound text and optionally play it through the speaker.",
                    input_schema={"message": "ChannelMessage(text, metadata[normalized_intensity|outbound_intensity|voice])"},
                    output_schema={"success": "bool"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("init", "management", "Initialize the TTS channel runtime state."),
                ChannelOpDescriptor("deinit", "management", "Deinitialize the TTS channel runtime state."),
                ChannelOpDescriptor("connect", "management", "Enable TTS playback when available."),
                ChannelOpDescriptor("disconnect", "management", "Disable TTS playback."),
                ChannelOpDescriptor("pause", "management", "Pause TTS playback without dropping configuration."),
                ChannelOpDescriptor("resume", "management", "Resume TTS playback after pause."),
                ChannelOpDescriptor("suspend", "management", "Suspend TTS channel activity."),
                ChannelOpDescriptor("unsuspend", "management", "Unsuspend TTS channel activity."),
                ChannelOpDescriptor("get_config", "management", "Return the TTS channel config snapshot."),
                ChannelOpDescriptor("update_config", "management", "Update mutable TTS channel config fields.", input_schema={"config": "dict"}, output_schema={"snapshot": "ChannelConfigSnapshot"}),
                ChannelOpDescriptor("health_check", "management", "Return the TTS channel health snapshot."),
            ],
            startup_requirements=["Alibaba Cloud TTS credentials", "nls SDK or injected synthesize function"],
            shutdown_requirements=["disconnect playback channel"],
            health_signals=["is_available", "is_connected"],
            ack_schema={"success": "bool", "playback": "best_effort"},
            config_fields=[
                ChannelConfigFieldDescriptor("voice", "Default TTS voice.", required=True, mutable_at_runtime=True, default_value="xiaoyun", schema_hint="str"),
                ChannelConfigFieldDescriptor("enabled", "Whether the TTS channel is enabled.", required=True, mutable_at_runtime=True, default_value=True, schema_hint="bool"),
            ],
            limitations=["Current implementation only consumes text and returns bool success."],
        )

    def send(self, message: ChannelMessage) -> bool:
        if not self.is_connected() or self._paused or self._suspended:
            return False
        try:
            metadata = dict(message.metadata or {})
            modulation = modulate_outbound_expression(message.text, metadata)
            expression_profile = modulation.to_metadata()
            message.metadata["original_text"] = message.text
            message.metadata["rendered_text"] = modulation.rendered_text
            message.metadata["expression_profile"] = expression_profile
            metadata.setdefault("expression_profile", expression_profile)
            audio = self._synthesize(
                modulation.rendered_text,
                intensity=modulation.normalized_intensity,
                metadata=metadata,
            )
            if audio is False:
                return False
            if self._play_func is not None:
                return bool(self._play_func(audio))
            return True
        except Exception as exc:
            log.warning("TTS send failed: %s", exc)
            return False

    def is_connected(self) -> bool:
        return self._connected and self.is_available

    def connect(self) -> None:
        if self.is_available:
            self._connected = True
            self._paused = False
            self._suspended = False
            self._status = ChannelStatus.CONNECTED

    def disconnect(self) -> None:
        self._connected = False
        self._status = ChannelStatus.DISCONNECTED

    def get_status(self) -> ChannelStatus:
        if self._suspended:
            return ChannelStatus.SUSPENDED
        if self._paused:
            return ChannelStatus.PAUSED
        if self._connected and self.is_available:
            return ChannelStatus.CONNECTED
        return self._status

    def get_config_snapshot(self) -> ChannelConfigSnapshot:
        return ChannelConfigSnapshot(
            channel_id=self.channel_id,
            status=self.get_status().value,
            config_values={"voice": self._voice, "enabled": self._enabled},
            mutable_fields=["voice", "enabled"],
            validation_errors=[],
        )

    def update_config(self, updates: Optional[dict[str, Any]] = None) -> ChannelConfigSnapshot:
        updates = dict(updates or {})
        if "voice" in updates:
            self._voice = str(updates["voice"] or self._voice)
        if "enabled" in updates:
            self._enabled = bool(updates["enabled"])
        return self.get_config_snapshot()

    def execute_management_op(self, op_name: str, payload: Optional[dict[str, Any]] = None) -> ChannelManagementResult:
        payload = dict(payload or {})
        if op_name == "init":
            if self._status == ChannelStatus.UNINITIALIZED:
                self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, "TTS channel initialized.")
        if op_name == "deinit":
            self.disconnect()
            self._status = ChannelStatus.DEINITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "TTS channel deinitialized.")
        if op_name == "pause":
            self._paused = True
            self._status = ChannelStatus.PAUSED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "TTS channel paused.")
        if op_name == "resume":
            self._paused = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "TTS channel resumed.")
        if op_name == "suspend":
            self._suspended = True
            self._status = ChannelStatus.SUSPENDED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "TTS channel suspended.")
        if op_name == "unsuspend":
            self._suspended = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "TTS channel unsuspended.")
        if op_name == "get_config":
            snapshot = self.get_config_snapshot()
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "update_config":
            snapshot = self.update_config(dict(payload.get("config", {}) or {}))
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "health_check":
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload=self.health_check())
        return super().execute_management_op(op_name, payload)

    def _synthesize(self, text: str, *, intensity: float = 0.0, metadata: Optional[dict[str, Any]] = None):
        if self._synthesize_func is not None:
            try:
                return self._synthesize_func(
                    text=text,
                    intensity=float(intensity),
                    metadata=dict(metadata or {}),
                    voice=str((metadata or {}).get("voice", self._voice) or self._voice),
                )
            except TypeError:
                try:
                    return self._synthesize_func(text=text)
                except TypeError:
                    return self._synthesize_func(text)
        if self._nls is None:
            return False

        synthesizer_cls = getattr(self._nls, "NlsSpeechSynthesizer", None)
        if synthesizer_cls is None:
            log.warning("nls SDK does not expose NlsSpeechSynthesizer — TTS send skipped")
            return False

        synthesizer = synthesizer_cls(
            token=None,
            appkey=self._app_key,
            on_data=lambda data, *_args, **_kwargs: data,
        )
        start = getattr(synthesizer, "start", None)
        if callable(start):
            return start(text=text, voice=self._voice)
        return False


def build_tts_bootstrap_factory(*, cfg: object) -> OptionalChannelBootstrapFactory:
    return lambda: OptionalChannelBootstrapSpec(
        channel_id="tts",
        factory=TTSChannel,
        payload={
            "access_key": getattr(cfg, "ALI_ACCESS_KEY", ""),
            "access_secret": getattr(cfg, "ALI_SECRET_KEY", ""),
            "app_key": getattr(cfg, "ALI_APP_KEY", ""),
            "enabled": bool(getattr(cfg, "TTS_ENABLED", False)),
        },
    )