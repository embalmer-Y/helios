"""
io/io_tts.py — Helios TTS 语音合成模块 (G5)

使用阿里云 NLS TTS SDK 将文本合成为语音并播放。
硬件可选模块 — 当 SDK 或凭证不可用时优雅降级为纯文本模式。

Requirements: 30.1, 30.2, 30.3, 30.4
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger("helios.io.tts")


class TTSModule:
    """
    Text-to-speech synthesis using Alibaba Cloud NLS TTS SDK.

    Operates as an optional output module — gracefully degrades when
    the nls SDK is not installed or credentials are missing.

    Usage:
        tts = TTSModule()
        if tts.is_available:
            tts.synthesize_and_play("你好世界")

    Runtime pluggability:
        tts.register()    # activate TTS output
        tts.deregister()  # deactivate, release resources
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        access_secret: Optional[str] = None,
        app_key: Optional[str] = None,
        voice: str = "xiaoyun",
        enabled: bool = True,
    ):
        self._enabled = enabled
        self._available = False
        self._registered = False
        self._voice = voice
        self._nls = None  # lazy reference to nls module
        self._access_key: Optional[str] = None
        self._access_secret: Optional[str] = None
        self._app_key: Optional[str] = None
        self._lock = threading.Lock()

        if not enabled:
            logger.info("TTS module disabled by configuration")
            return

        # Resolve credentials from params or environment
        resolved_key = access_key or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        resolved_secret = access_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        resolved_app_key = app_key or os.getenv("ALIBABA_NLS_APP_KEY", "")

        if not all([resolved_key, resolved_secret, resolved_app_key]):
            logger.warning(
                "TTS credentials missing — operating in text-only mode. "
                "Set ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET, "
                "and ALIBABA_NLS_APP_KEY to enable TTS."
            )
            return

        # Try importing the Alibaba NLS SDK
        try:
            import nls  # noqa: F401
            self._nls = nls
            self._access_key = resolved_key
            self._access_secret = resolved_secret
            self._app_key = resolved_app_key
            self._available = True
            logger.info("TTS module initialized — voice: %s", self._voice)
        except ImportError:
            logger.warning(
                "nls SDK not installed — TTS unavailable. "
                "Install with: pip install alibabacloud-nls"
            )

    @property
    def is_available(self) -> bool:
        """Runtime hardware probing: True when SDK + credentials + registered."""
        return self._available and self._enabled and self._registered

    def register(self):
        """Register as runtime-pluggable output module (activate TTS)."""
        self._registered = True
        if self._available:
            logger.info("TTS module registered — voice output active")
        else:
            logger.debug("TTS module registered but not available (no-op mode)")

    def deregister(self):
        """Deregister and release resources (deactivate TTS)."""
        self._registered = False
        logger.info("TTS module deregistered — voice output inactive")

    def synthesize_and_play(self, text: str) -> bool:
        """
        Synthesize text to speech and play through system speaker.

        This is a no-op when TTS is not available (returns False silently).
        Non-fatal: logs warning on synthesis failure and returns False.

        Args:
            text: The text to synthesize into speech audio.

        Returns:
            True on successful synthesis and playback, False otherwise.
        """
        if not self.is_available:
            return False

        if not text or not text.strip():
            return False

        with self._lock:
            try:
                return self._do_synthesize(text)
            except Exception as e:
                logger.warning("TTS synthesis failed: %s", e)
                return False

    def _do_synthesize(self, text: str) -> bool:
        """Internal synthesis implementation wrapping nls.NlsSpeechSynthesizer."""
        nls = self._nls
        if nls is None:
            return False

        # Audio buffer to collect synthesized audio data
        audio_data = bytearray()
        synthesis_complete = threading.Event()
        synthesis_error: list = []

        def on_data(data: bytes, *args):
            """Callback: receive audio data chunks."""
            audio_data.extend(data)

        def on_completed(*args):
            """Callback: synthesis completed."""
            synthesis_complete.set()

        def on_error(message: str, *args):
            """Callback: synthesis error."""
            synthesis_error.append(message)
            synthesis_complete.set()

        def on_close(*args):
            """Callback: connection closed."""
            synthesis_complete.set()

        # Create NLS token (simplified — production would use token service)
        token = self._get_token()
        if not token:
            logger.warning("TTS: failed to obtain access token")
            return False

        # Create synthesizer
        synthesizer = nls.NlsSpeechSynthesizer(
            url="wss://nls-gateway.aliyuncs.com/ws/v1",
            token=token,
            appkey=self._app_key,
            on_data=on_data,
            on_completed=on_completed,
            on_error=on_error,
            on_close=on_close,
        )

        # Start synthesis
        synthesizer.start(
            text=text,
            voice=self._voice,
            aformat="pcm",
            sample_rate=16000,
        )

        # Wait for completion (timeout 30s)
        synthesis_complete.wait(timeout=30.0)

        if synthesis_error:
            logger.warning("TTS synthesis error: %s", synthesis_error[0])
            return False

        if not audio_data:
            logger.warning("TTS: no audio data received")
            return False

        # Play audio through system speaker
        return self._play_audio(bytes(audio_data))

    def _get_token(self) -> Optional[str]:
        """Obtain NLS access token from Alibaba Cloud credentials."""
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest

            client = AcsClient(
                self._access_key,
                self._access_secret,
                "cn-shanghai",
            )
            request = CommonRequest()
            request.set_method("POST")
            request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
            request.set_version("2019-02-28")
            request.set_action_name("CreateToken")

            response = client.do_action_with_exception(request)
            import json
            result = json.loads(response)
            return result.get("Token", {}).get("Id", "")
        except Exception as e:
            logger.warning("TTS: token acquisition failed: %s", e)
            return None

    def _play_audio(self, audio_data: bytes) -> bool:
        """Play PCM audio data through system speaker using pyaudio."""
        try:
            import pyaudio

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                output=True,
            )
            stream.write(audio_data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            return True
        except ImportError:
            logger.warning("pyaudio not installed — cannot play audio")
            return False
        except Exception as e:
            logger.warning("TTS audio playback failed: %s", e)
            return False

    def get_state(self) -> dict:
        """Return module state for monitoring/dashboard."""
        return {
            "enabled": self._enabled,
            "available": self._available,
            "registered": self._registered,
            "voice": self._voice,
            "is_available": self.is_available,
        }
