"""io/io_stt.py — Speech-to-Text Recognition Module

Provides voice input via Alibaba Cloud NLS ASR SDK. Implements the EventSource
interface for integration into the Helios event collection system.

Remains dormant when SDK, pyaudio, or microphone hardware is unavailable.

Requirements: 31.1, 31.2, 31.3, 31.4
"""

import logging
import queue
import threading
from typing import Dict, List

from core.event_source import EventSource
from core.helios_state import HeliosState

logger = logging.getLogger("helios.io.stt")


class STTModule(EventSource):
    """Speech-to-text recognition using Alibaba Cloud NLS ASR SDK.

    Implements EventSource: poll() returns empty triggers (emotional evaluation
    happens via SEC on the transcribed text), get_messages() returns pending
    transcribed utterances.

    Remains dormant when hardware/dependencies are unavailable.
    """

    def __init__(self, access_key: str = "", access_secret: str = "", app_key: str = ""):
        self._access_key = access_key
        self._access_secret = access_secret
        self._app_key = app_key
        self._available = False
        self._running = False
        self._pending_utterances: List[dict] = []
        self._utterance_queue: queue.Queue = queue.Queue()
        self._thread = None
        self._init_hardware()

    def _init_hardware(self):
        """Check for SDK and microphone availability."""
        if not self._access_key or not self._access_secret:
            logger.warning("STT: credentials unavailable, remaining dormant")
            return
        try:
            import nls
            import pyaudio
            p = pyaudio.PyAudio()
            if p.get_device_count() == 0:
                logger.warning("STT: no microphone detected, remaining dormant")
                p.terminate()
                return
            p.terminate()
            self._available = True
            logger.info("STT: hardware and SDK available")
        except ImportError as e:
            logger.warning(f"STT: dependency unavailable ({e}), remaining dormant")

    @property
    def is_available(self) -> bool:
        """Whether STT hardware/SDK is available."""
        return self._available

    def start(self):
        """Start the ASR recognition loop in a background thread."""
        if not self._available or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self._thread.start()
        logger.info("STT recognition started")

    def stop(self):
        """Stop the ASR recognition loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("STT recognition stopped")

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Return empty triggers — emotional evaluation is done via SEC on text.

        Drains the utterance queue into pending messages buffer.
        """
        self._pending_utterances = []
        while True:
            try:
                utterance = self._utterance_queue.get_nowait()
                self._pending_utterances.append(utterance)
            except queue.Empty:
                break
        return {}

    def get_messages(self) -> List[dict]:
        """Return pending transcribed utterances as message dicts."""
        return self._pending_utterances

    def _on_utterance_complete(self, text: str):
        """Callback from ASR SDK when a complete utterance is transcribed."""
        if text and text.strip():
            self._utterance_queue.put({
                "text": text.strip(),
                "user_id": "voice_local",
                "source": "stt",
            })
            logger.debug(f"STT utterance: {text[:60]}")

    def _recognition_loop(self):
        """Background thread running continuous ASR."""
        try:
            import nls
            import pyaudio

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16, channels=1, rate=16000,
                input=True, frames_per_buffer=3200
            )

            def on_result(message, *args):
                import json
                try:
                    result = json.loads(message)
                    if result.get("header", {}).get("name") == "SentenceEnd":
                        text = result.get("payload", {}).get("result", "")
                        self._on_utterance_complete(text)
                except Exception:
                    pass

            while self._running:
                try:
                    recognizer = nls.NlsSpeechTranscriber(
                        url="wss://nls-gateway.aliyuncs.com/ws/v1",
                        akid=self._access_key,
                        aksecret=self._access_secret,
                        appkey=self._app_key,
                        on_sentence_end=on_result,
                    )
                    recognizer.start(
                        enable_intermediate_result=False,
                        enable_punctuation_prediction=True,
                    )

                    while self._running:
                        data = stream.read(3200, exception_on_overflow=False)
                        recognizer.send_audio(data)

                    recognizer.stop()
                except Exception as e:
                    logger.debug(f"STT recognition error: {e}")
                    if self._running:
                        import time
                        time.sleep(1)

            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            logger.warning(f"STT recognition loop failed: {e}")
            self._running = False
