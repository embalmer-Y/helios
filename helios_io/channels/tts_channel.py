"""Optional TTS output channel for Helios."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from ..channel import ChannelDescriptor, ChannelMessage, ChannelOpDescriptor, OutputChannel

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
        synthesize_func: Optional[Callable[[str], Any]] = None,
        play_func: Optional[Callable[[Any], bool]] = None,
        force_available: Optional[bool] = None,
    ):
        self._voice = voice
        self._enabled = enabled
        self._synthesize_func = synthesize_func
        self._play_func = play_func
        self._connected = False
        self._available = False
        self._nls = None

        self._access_key = access_key or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        self._access_secret = access_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        self._app_key = app_key or os.getenv("ALIBABA_CLOUD_APP_KEY", "")

        if force_available is not None:
            self._available = bool(force_available)
            return

        if not enabled:
            return
        if not all([self._access_key, self._access_secret, self._app_key]):
            log.debug("TTS credentials missing — remaining dormant")
            return
        try:
            import nls  # type: ignore

            self._nls = nls
            self._available = True
        except ImportError:
            log.debug("nls SDK not installed — TTS channel dormant")

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
                    input_schema={"message": "ChannelMessage(text)"},
                    output_schema={"success": "bool"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("connect", "management", "Enable TTS playback when available."),
                ChannelOpDescriptor("disconnect", "management", "Disable TTS playback."),
            ],
            startup_requirements=["Alibaba Cloud TTS credentials", "nls SDK or injected synthesize function"],
            shutdown_requirements=["disconnect playback channel"],
            health_signals=["is_available", "is_connected"],
            ack_schema={"success": "bool", "playback": "best_effort"},
            limitations=["Current implementation only consumes text and returns bool success."],
        )

    def send(self, message: ChannelMessage) -> bool:
        if not self.is_connected():
            return False
        try:
            audio = self._synthesize(message.text)
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

    def disconnect(self) -> None:
        self._connected = False

    def _synthesize(self, text: str):
        if self._synthesize_func is not None:
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