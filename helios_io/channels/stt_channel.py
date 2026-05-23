"""Optional STT input channel for Helios."""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Dict, List, Optional

from ..channel import ChannelMessage, InputChannel
from .qq_channel import QQChannel

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
        self._pending_utterances: List[str] = []
        self._sec_evaluator = sec_evaluator
        self._microphone_probe = microphone_probe

        self._access_key = access_key or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        self._access_secret = access_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        self._app_key = app_key or os.getenv("ALIBABA_CLOUD_APP_KEY", "")

        if force_available is not None:
            self._available = bool(force_available)
            return

        if not enabled:
            return
        if not all([self._access_key, self._access_secret, self._app_key]):
            log.warning("STT credentials missing — remaining dormant")
            return

        try:
            import nls  # type: ignore  # noqa: F401
            import pyaudio  # type: ignore

            if self._probe_microphone(pyaudio):
                self._available = True
            else:
                log.warning("STT microphone unavailable — remaining dormant")
        except ImportError:
            log.warning("STT dependencies missing (nls/pyaudio) — remaining dormant")

    @property
    def channel_id(self) -> str:
        return self.CHANNEL_ID

    @property
    def is_available(self) -> bool:
        return self._available and self._enabled

    def poll(self) -> List[ChannelMessage]:
        if not self.is_connected() or not self._pending_utterances:
            return []

        utterances = list(self._pending_utterances)
        self._pending_utterances.clear()
        return [self._build_message(text) for text in utterances]

    def is_connected(self) -> bool:
        return self._connected and self.is_available

    def connect(self) -> None:
        if self.is_available:
            self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def _on_utterance_complete(self, text: str):
        if text and text.strip():
            self._pending_utterances.append(text.strip())

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        cached_triggers = dict(message.metadata.get("event_triggers", {}) or {})
        if cached_triggers:
            return cached_triggers
        if self._sec_evaluator is None:
            return {}
        try:
            result = self._sec_evaluator.evaluate(message.text)
            if QQChannel._looks_like_sec_result(result):
                return QQChannel._sec_to_triggers(result)
            return dict(result or {})
        except Exception as exc:
            log.warning("STT SEC evaluation failed: %s", exc)
            return {}

    def _build_message(self, text: str) -> ChannelMessage:
        metadata: Dict[str, object] = {"source": "stt"}
        if self._sec_evaluator is not None:
            try:
                evaluation = self._sec_evaluator.evaluate(text)
            except Exception as exc:
                log.warning("STT annotation failed: %s", exc)
                evaluation = {}
            if QQChannel._looks_like_sec_result(evaluation):
                metadata["sec_result"] = dict(evaluation)
                metadata["event_triggers"] = QQChannel._sec_to_triggers(evaluation)
                metadata["cognitive_impact"] = QQChannel._build_cognitive_impact(
                    text,
                    dict(evaluation),
                    dict(metadata["event_triggers"]),
                )
            elif evaluation:
                metadata["event_triggers"] = dict(evaluation)
        return ChannelMessage(
            channel_id=self.CHANNEL_ID,
            user_id="microphone",
            text=text,
            timestamp=time.time(),
            metadata=dict(metadata),
            direction="inbound",
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