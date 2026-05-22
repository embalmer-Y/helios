"""io/io_vision.py — Camera-based Visual Input Module

Captures frames from a camera, generates scene descriptions via a vision LLM,
and converts descriptions into emotional event triggers. Implements EventSource.

Remains dormant when camera hardware or OpenCV is unavailable.

Requirements: 32.1, 32.2, 32.3, 32.4
"""

import logging
import time
from typing import Dict, List, Optional

from core.event_source import EventSource
from core.helios_state import HeliosState

logger = logging.getLogger("helios.io.vision")


class VisionModule(EventSource):
    """Camera-based visual input implementing EventSource.

    Captures frames at a configurable interval (default 5 seconds), generates
    scene descriptions via a vision LLM, and converts descriptions into
    Panksepp triggers. Remains dormant when hardware is unavailable.
    """

    def __init__(self, capture_interval: float = 5.0, api_key: str = "",
                 base_url: str = "", model: str = ""):
        self._capture_interval = capture_interval
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._available = False
        self._cap = None
        self._last_capture_time: float = 0.0
        self._pending_messages: List[dict] = []
        self._last_triggers: Dict[str, float] = {}
        self._init_hardware()

    def _init_hardware(self):
        """Check for OpenCV and camera availability."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                self._available = True
                cap.release()
                logger.info("Vision: camera device available")
            else:
                logger.warning("Vision: no camera device found, remaining dormant")
        except ImportError:
            logger.warning("Vision: OpenCV not installed, remaining dormant")

    @property
    def is_available(self) -> bool:
        """Whether camera hardware is available."""
        return self._available

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Capture and analyze a frame if interval has elapsed.

        Args:
            state: Current tick HeliosState.

        Returns:
            Panksepp trigger dict derived from scene description.
        """
        self._pending_messages = []
        self._last_triggers = {}

        if not self._available:
            return {}

        now = time.time()
        if now - self._last_capture_time < self._capture_interval:
            return {}

        self._last_capture_time = now
        description = self._capture_and_analyze()
        if description:
            self._pending_messages.append({
                "text": f"[vision] {description}",
                "user_id": "vision_local",
                "source": "vision",
            })
            self._last_triggers = self._description_to_triggers(description)

        return self._last_triggers

    def get_messages(self) -> List[dict]:
        """Return scene descriptions for awareness logging."""
        return self._pending_messages

    def _capture_and_analyze(self) -> Optional[str]:
        """Capture a frame and generate a scene description via vision LLM."""
        try:
            import cv2
            import base64

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return None

            # Encode frame as JPEG for LLM
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            b64_image = base64.b64encode(buffer).decode('utf-8')

            # Call vision LLM
            return self._query_vision_llm(b64_image)

        except Exception as e:
            logger.debug(f"Vision capture/analysis failed: {e}")
            return None

    def _query_vision_llm(self, b64_image: str) -> Optional[str]:
        """Query vision LLM for scene description."""
        if not self._api_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            response = client.chat.completions.create(
                model=self._model or "gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "简短描述这个场景（20字以内），关注情感氛围。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                    ],
                }],
                max_tokens=50,
                timeout=5,
            )
            return response.choices[0].message.content or None
        except Exception as e:
            logger.debug(f"Vision LLM query failed: {e}")
            return None

    def _description_to_triggers(self, description: str) -> Dict[str, float]:
        """Convert scene description to Panksepp triggers via keyword matching."""
        desc_lower = description.lower()
        triggers: Dict[str, float] = {}

        positive_words = ["温暖", "明亮", "阳光", "笑", "花", "美", "温馨", "舒适"]
        negative_words = ["黑暗", "阴", "脏", "乱", "空旷", "荒凉", "冷"]
        novel_words = ["新", "奇", "陌生", "特别", "不同", "变化"]

        for w in positive_words:
            if w in desc_lower:
                triggers["CARE"] = max(triggers.get("CARE", 0.0), 0.3)
                triggers["PLAY"] = max(triggers.get("PLAY", 0.0), 0.2)

        for w in negative_words:
            if w in desc_lower:
                triggers["FEAR"] = max(triggers.get("FEAR", 0.0), 0.2)

        for w in novel_words:
            if w in desc_lower:
                triggers["SEEKING"] = max(triggers.get("SEEKING", 0.0), 0.3)

        return triggers
