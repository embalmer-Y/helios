"""Optional STT input channel for Helios."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

from ..channel import ChannelConfigFieldDescriptor, ChannelConfigSnapshot, ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelOpDescriptor, ChannelStatus, InputChannel
from ..optional_channel_contract import OptionalChannelBootstrapFactory, OptionalChannelBootstrapSpec
from .inbound_text_annotation import annotate_inbound_text_message, evaluate_text_triggers

log = logging.getLogger("helios.helios_io.channels.stt_channel")


class STTChannel(InputChannel):
    CHANNEL_ID = "stt"

    def __init__(
        self,
        access_key: str = "",
        access_secret: str = "",
        app_key: str = "",
        enabled: bool = True,
        sec_evaluator=None,
        force_available: Optional[bool] = None,
        microphone_probe: Optional[Callable[[], bool]] = None,
    ):
        self._enabled = enabled
        self._available = False
        self._connected = False
        self._status = ChannelStatus.UNINITIALIZED
        self._paused = False
        self._suspended = False
        self._pending_utterances: List[str] = []
        self._sec_evaluator = sec_evaluator
        self._microphone_probe = microphone_probe

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
            log.debug("STT credentials missing — remaining dormant")
            self._status = ChannelStatus.DISCONNECTED
            return

        try:
            import nls  # type: ignore  # noqa: F401
            import pyaudio  # type: ignore

            if self._probe_microphone(pyaudio):
                self._available = True
                self._status = ChannelStatus.INITIALIZED
            else:
                log.debug("STT microphone unavailable — remaining dormant")
                self._status = ChannelStatus.DISCONNECTED
        except ImportError:
            log.debug("STT dependencies missing (nls/pyaudio) — remaining dormant")
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
            display_name="STT Channel",
            input_types=["speech_audio"],
            output_types=["text_message", "event_triggers"],
            input_formats=["microphone", "audio_stream"],
            output_formats=["text/plain", "trigger_dict"],
            capabilities=["poll", "speech_input", "text_output", "sec_annotation"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description="Poll completed speech utterances normalized as ChannelMessage objects.",
                    output_schema={"messages": "list[ChannelMessage]"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("init", "management", "Initialize the STT channel runtime state."),
                ChannelOpDescriptor("deinit", "management", "Deinitialize the STT channel runtime state."),
                ChannelOpDescriptor("connect", "management", "Enable microphone-backed STT when available."),
                ChannelOpDescriptor("disconnect", "management", "Disable microphone-backed STT."),
                ChannelOpDescriptor("pause", "management", "Pause STT utterance polling without dropping config."),
                ChannelOpDescriptor("resume", "management", "Resume STT utterance polling."),
                ChannelOpDescriptor("suspend", "management", "Suspend STT activity."),
                ChannelOpDescriptor("unsuspend", "management", "Unsuspend STT activity."),
                ChannelOpDescriptor("get_config", "management", "Return the STT channel config snapshot."),
                ChannelOpDescriptor("update_config", "management", "Update mutable STT channel config fields.", input_schema={"config": "dict"}, output_schema={"snapshot": "ChannelConfigSnapshot"}),
                ChannelOpDescriptor("health_check", "management", "Return the STT channel health snapshot."),
            ],
            startup_requirements=["Alibaba Cloud STT credentials", "nls SDK", "microphone availability"],
            shutdown_requirements=["disconnect STT capture"],
            health_signals=["is_available", "is_connected"],
            ack_schema={"messages": "list[ChannelMessage]"},
            config_fields=[
                ChannelConfigFieldDescriptor("enabled", "Whether the STT channel is enabled.", required=True, mutable_at_runtime=True, default_value=True, schema_hint="bool"),
            ],
            limitations=["Current implementation buffers completed utterances only."],
        )

    def poll(self) -> List[ChannelMessage]:
        if not self.is_connected() or self._paused or self._suspended or not self._pending_utterances:
            return []

        utterances = list(self._pending_utterances)
        self._pending_utterances.clear()
        return [self._build_message(text) for text in utterances]

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
            config_values={"enabled": self._enabled},
            mutable_fields=["enabled"],
            validation_errors=[],
        )

    def update_config(self, updates: Optional[Dict[str, Any]] = None) -> ChannelConfigSnapshot:
        updates = dict(updates or {})
        if "enabled" in updates:
            self._enabled = bool(updates["enabled"])
        return self.get_config_snapshot()

    def execute_management_op(self, op_name: str, payload: Optional[Dict[str, Any]] = None) -> ChannelManagementResult:
        payload = dict(payload or {})
        if op_name == "init":
            if self._status == ChannelStatus.UNINITIALIZED:
                self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, "STT channel initialized.")
        if op_name == "deinit":
            self.disconnect()
            self._status = ChannelStatus.DEINITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "STT channel deinitialized.")
        if op_name == "pause":
            self._paused = True
            self._status = ChannelStatus.PAUSED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "STT channel paused.")
        if op_name == "resume":
            self._paused = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "STT channel resumed.")
        if op_name == "suspend":
            self._suspended = True
            self._status = ChannelStatus.SUSPENDED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "STT channel suspended.")
        if op_name == "unsuspend":
            self._suspended = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "STT channel unsuspended.")
        if op_name == "get_config":
            snapshot = self.get_config_snapshot()
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "update_config":
            snapshot = self.update_config(dict(payload.get("config", {}) or {}))
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "health_check":
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload=self.health_check())
        return super().execute_management_op(op_name, payload)

    def _on_utterance_complete(self, text: str):
        if text and text.strip():
            self._pending_utterances.append(text.strip())

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        return evaluate_text_triggers(message, self._sec_evaluator, log, "STTChannel")

    def _build_message(self, text: str) -> ChannelMessage:
        return annotate_inbound_text_message(
            ChannelMessage(
                channel_id=self.CHANNEL_ID,
                user_id="microphone",
                text=text,
                timestamp=time.time(),
                metadata={"source": "stt"},
                direction="inbound",
            ),
            self._sec_evaluator,
            log,
            "STTChannel",
        )

    def _probe_microphone(self, pyaudio_module) -> bool:
        if self._microphone_probe is not None:
            return bool(self._microphone_probe())
        try:
            pa = pyaudio_module.PyAudio()
            try:
                return pa.get_device_count() > 0
            finally:
                if hasattr(pa, "terminate"):
                    pa.terminate()
        except Exception:
            return False


def build_stt_bootstrap_factory(*, cfg: object, sec_evaluator=None) -> OptionalChannelBootstrapFactory:
    return lambda: OptionalChannelBootstrapSpec(
        channel_id="stt",
        factory=STTChannel,
        payload={
            "access_key": getattr(cfg, "ALI_ACCESS_KEY", ""),
            "access_secret": getattr(cfg, "ALI_SECRET_KEY", ""),
            "app_key": getattr(cfg, "ALI_APP_KEY", ""),
            "enabled": bool(getattr(cfg, "STT_ENABLED", False)),
            "sec_evaluator": sec_evaluator,
        },
    )