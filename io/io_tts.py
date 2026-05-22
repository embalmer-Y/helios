"""io/io_tts.py — Text-to-Speech Synthesis Module

Provides voice output using Alibaba Cloud NLS TTS SDK when available.
Degrades gracefully to text-only operation when SDK or credentials are missing.

Requirements: 30.1, 30.2, 30.3, 30.4
"""

import logging
from typing import Optional

logger = logging.getLogger("helios.io.tts")


class TTSModule:
    """Text-to-speech synthesis using Alibaba Cloud NLS SDK.

    Runtime-pluggable: can be registered/deregistered dynamically.
    Remains dormant when SDK or credentials are unavailable.
    """

    def __init__(self, access_key: str = "", access_secret: str = "", app_key: str = ""):
        self._access_key = access_key
        self._access_secret = access_secret
        self._app_key = app_key
        self._nls = None
        self._available = False
        self._registered = False
        self._init_sdk()

    def _init_sdk(self):
        """Attempt to initialize the NLS SDK."""
        if not self._access_key or not self._access_secret:
            logger.warning("TTS: credentials unavailable, text-only mode")
            return
        try:
            import nls
            self._nls = nls
            self._available = True
            logger.info("TTS: Alibaba NLS SDK initialized")
        except ImportError:
            logger.warning("TTS: nls SDK not installed, text-only mode")

    @property
    def is_available(self) -> bool:
        """Whether TTS hardware/SDK is available for synthesis."""
        return self._available

    def register(self):
        """Register this module for runtime operation."""
        self._registered = True
        logger.info("TTS module registered")

    def deregister(self):
        """Deregister this module from runtime operation."""
        self._registered = False
        logger.info("TTS module deregistered")

    def synthesize_and_play(self, text: str) -> bool:
        """Synthesize text to audio and play through system speaker.

        Args:
            text: The text to synthesize.

        Returns:
            True if synthesis and playback succeeded, False otherwise.
        """
        if not self._available or not self._registered:
            return False

        if not text:
            return False

        try:
            import threading

            completed = threading.Event()
            audio_data = bytearray()

            def on_data(data, *args):
                audio_data.extend(data)

            def on_completed(*args):
                completed.set()

            def on_error(message, *args):
                logger.warning(f"TTS synthesis error: {message}")
                completed.set()

            synthesizer = self._nls.NlsSpeechSynthesizer(
                url="wss://nls-gateway.aliyuncs.com/ws/v1",
                akid=self._access_key,
                aksecret=self._access_secret,
                appkey=self._app_key,
                on_data=on_data,
                on_completed=on_completed,
                on_error=on_error,
            )
            synthesizer.start(text)
            completed.wait(timeout=10)
            synthesizer.shutdown()

            if audio_data:
                self._play_audio(bytes(audio_data))
                return True
            return False

        except Exception as e:
            logger.warning(f"TTS synthesis failed: {e}")
            return False

    def _play_audio(self, data: bytes):
        """Play raw audio data through system speaker."""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True)
            stream.write(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logger.debug(f"Audio playback failed: {e}")
