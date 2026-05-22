"""
io/io_stt.py — Helios STT 语音识别模块 (EventSource)

使用阿里云 NLS ASR SDK 进行实时语音转文字。
硬件可选模块 — 当 SDK、凭证或麦克风不可用时优雅降级为静默模式。

Implements the EventSource interface so transcribed utterances flow into
the Helios tick pipeline as messages for SEC evaluation.

Requirements: 31.1, 31.2, 31.3, 31.4
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Dict, List, Optional

from core.event_source import EventSource
from core.helios_state import HeliosState

logger = logging.getLogger("helios.io.stt")


class STTModule(EventSource):
    """
    Speech-to-text recognition using Alibaba Cloud NLS ASR SDK.

    Implements EventSource so transcribed utterances are delivered as messages
    into the Helios event collection pipeline. Triggers come from SEC evaluation
    of the transcribed text (not directly from this module), so poll() always
    returns an empty dict.

    Operates as a hardware-optional module — gracefully remains dormant when
    the nls SDK, pyaudio, or microphone hardware is unavailable.

    Usage:
        stt = STTModule()
        if stt.is_available:
            stt.start_listening()
        # Each tick:
        triggers = stt.poll(state)   # always {}
        messages = stt.get_messages()  # transcribed utterances

    Runtime pluggability:
        stt.register()    # activate STT input
        stt.deregister()  # deactivate, release resources
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        access_secret: Optional[str] = None,
        app_key: Optional[str] = None,
        enabled: bool = True,
    ):
        self._enabled = enabled
        self._available = False
        self._registered = False
        self._listening = False
        self._nls = None  # lazy reference to nls module
        self._pyaudio = None  # lazy reference to pyaudio module
        self._access_key: Optional[str] = None
        self._access_secret: Optional[str] = None
        self._app_key: Optional[str] = None
        self._lock = threading.Lock()
        self._pending_utterances: List[dict] = []
        self._stream = None
        self._audio_instance = None
        self._recognizer = None
        self._mic_available = False

        if not enabled:
            logger.info("STT module disabled by configuration")
            return

        # Resolve credentials from params or environment
        resolved_key = access_key or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        resolved_secret = access_secret or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
        resolved_app_key = app_key or os.getenv("ALIBABA_NLS_APP_KEY", "")

        if not all([resolved_key, resolved_secret, resolved_app_key]):
            logger.warning(
                "STT credentials missing — operating in dormant mode. "
                "Set ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET, "
                "and ALIBABA_NLS_APP_KEY to enable STT."
            )
            return

        # Try importing the Alibaba NLS SDK
        try:
            import nls  # noqa: F401
            self._nls = nls
        except ImportError:
            logger.warning(
                "nls SDK not installed — STT unavailable. "
                "Install with: pip install alibabacloud-nls"
            )
            return

        # Try importing pyaudio for microphone access
        try:
            import pyaudio  # noqa: F401
            self._pyaudio = pyaudio
        except ImportError:
            logger.warning(
                "pyaudio not installed — STT unavailable. "
                "Install with: pip install pyaudio"
            )
            return

        # Check for microphone hardware
        if not self._check_microphone():
            logger.warning(
                "No microphone device detected — STT unavailable."
            )
            return

        self._access_key = resolved_key
        self._access_secret = resolved_secret
        self._app_key = resolved_app_key
        self._available = True
        logger.info("STT module initialized — ready for voice input")

    def _check_microphone(self) -> bool:
        """Probe for available microphone input device."""
        try:
            pa = self._pyaudio.PyAudio()
            try:
                # Check if there's at least one input device
                input_count = 0
                for i in range(pa.get_device_count()):
                    info = pa.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        input_count += 1
                        break
                self._mic_available = input_count > 0
                return self._mic_available
            finally:
                pa.terminate()
        except Exception as e:
            logger.debug("Microphone probe failed: %s", e)
            return False

    @property
    def is_available(self) -> bool:
        """Runtime hardware probing: True when SDK + credentials + mic + registered."""
        return self._available and self._enabled and self._registered

    def register(self):
        """Register as EventSource input module (activate STT)."""
        self._registered = True
        if self._available:
            logger.info("STT module registered — voice input active")
        else:
            logger.debug("STT module registered but not available (dormant mode)")

    def deregister(self):
        """Deregister and release resources (deactivate STT)."""
        self.stop_listening()
        self._registered = False
        logger.info("STT module deregistered — voice input inactive")

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Return empty trigger dict — STT triggers come from SEC evaluation of text.

        The STTModule does not directly produce Panksepp triggers. Instead,
        transcribed utterances are returned via get_messages() and evaluated
        through the SEC pipeline by the main loop.

        Args:
            state: The current tick's HeliosState (unused by STT).

        Returns:
            Empty dictionary always.
        """
        return {}

    def get_messages(self) -> List[dict]:
        """Return pending transcribed utterances as message dicts.

        Each message dict contains:
            - "text": The transcribed utterance text
            - "source": "stt" to identify the input source
            - "timestamp": When the utterance was completed
            - "user_id": "local_speaker" (local microphone input)

        Returns:
            List of message dicts for pending utterances, empty if none or dormant.
        """
        if not self.is_available:
            return []

        with self._lock:
            messages = self._pending_utterances.copy()
            self._pending_utterances.clear()
            return messages

    def _on_utterance_complete(self, text: str):
        """Callback invoked by ASR SDK when a complete utterance is recognized.

        Buffers the transcribed text as a message dict for retrieval via
        get_messages() on the next tick.

        Args:
            text: The transcribed utterance text from ASR.
        """
        if not text or not text.strip():
            return

        message = {
            "text": text.strip(),
            "source": "stt",
            "timestamp": time.time(),
            "user_id": "local_speaker",
        }

        with self._lock:
            self._pending_utterances.append(message)

        logger.debug("STT utterance complete: %s", text.strip()[:50])

    def start_listening(self) -> bool:
        """Start capturing audio from microphone and transcribing.

        Returns:
            True if listening started successfully, False otherwise.
        """
        if not self.is_available:
            return False

        if self._listening:
            return True

        try:
            token = self._get_token()
            if not token:
                logger.warning("STT: failed to obtain access token")
                return False

            nls = self._nls

            # Create speech recognizer
            self._recognizer = nls.NlsSpeechTranscriber(
                url="wss://nls-gateway.aliyuncs.com/ws/v1",
                token=token,
                appkey=self._app_key,
                on_sentence_end=self._on_sentence_end,
                on_start=self._on_start,
                on_error=self._on_error,
                on_close=self._on_close,
                on_result_changed=self._on_result_changed,
            )

            self._recognizer.start(
                aformat="pcm",
                sample_rate=16000,
                enable_intermediate_result=True,
                enable_punctuation_prediction=True,
                enable_inverse_text_normalization=True,
            )

            # Start audio capture thread
            self._listening = True
            self._capture_thread = threading.Thread(
                target=self._capture_audio_loop,
                daemon=True,
                name="stt-capture",
            )
            self._capture_thread.start()

            logger.info("STT listening started")
            return True

        except Exception as e:
            logger.warning("STT: failed to start listening: %s", e)
            self._listening = False
            return False

    def stop_listening(self):
        """Stop audio capture and transcription."""
        if not self._listening:
            return

        self._listening = False

        if self._recognizer:
            try:
                self._recognizer.stop()
            except Exception as e:
                logger.debug("STT: error stopping recognizer: %s", e)
            self._recognizer = None

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._audio_instance:
            try:
                self._audio_instance.terminate()
            except Exception:
                pass
            self._audio_instance = None

        logger.info("STT listening stopped")

    def _capture_audio_loop(self):
        """Background thread: capture audio from microphone and feed to recognizer."""
        try:
            pa = self._pyaudio.PyAudio()
            self._audio_instance = pa

            stream = pa.open(
                format=self._pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=3200,
            )
            self._stream = stream

            while self._listening:
                try:
                    data = stream.read(3200, exception_on_overflow=False)
                    if self._recognizer and self._listening:
                        self._recognizer.send_audio(data)
                except Exception as e:
                    if self._listening:
                        logger.debug("STT: audio read error: %s", e)
                    break

        except Exception as e:
            logger.warning("STT: audio capture loop error: %s", e)
        finally:
            self._listening = False

    def _on_sentence_end(self, message: str, *args):
        """NLS callback: a complete sentence has been recognized."""
        try:
            import json
            result = json.loads(message)
            text = result.get("payload", {}).get("result", "")
            if text:
                self._on_utterance_complete(text)
        except Exception as e:
            logger.debug("STT: sentence end parse error: %s", e)

    def _on_result_changed(self, message: str, *args):
        """NLS callback: intermediate recognition result (ignored for now)."""
        pass

    def _on_start(self, message: str, *args):
        """NLS callback: transcription session started."""
        logger.debug("STT: transcription session started")

    def _on_error(self, message: str, *args):
        """NLS callback: transcription error."""
        logger.warning("STT: transcription error: %s", message)

    def _on_close(self, *args):
        """NLS callback: connection closed."""
        logger.debug("STT: transcription connection closed")

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
            logger.warning("STT: token acquisition failed: %s", e)
            return None

    def get_state(self) -> dict:
        """Return module state for monitoring/dashboard."""
        return {
            "enabled": self._enabled,
            "available": self._available,
            "registered": self._registered,
            "listening": self._listening,
            "mic_available": self._mic_available,
            "is_available": self.is_available,
            "pending_utterances": len(self._pending_utterances),
        }
