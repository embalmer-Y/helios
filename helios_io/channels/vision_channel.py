"""Optional vision input channel for Helios."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..channel import ChannelMessage, InputChannel

log = logging.getLogger("helios.helios_io.channels.vision_channel")


class VisionChannel(InputChannel):
    CHANNEL_ID = "vision"

    def __init__(
        self,
        capture_interval: float = 5.0,
        enabled: bool = True,
        vision_describer: Optional[Callable[[Any], str]] = None,
        capture_func: Optional[Callable[[], Any]] = None,
        force_available: Optional[bool] = None,
    ):
        self._enabled = enabled
        self._available = False
        self._connected = False
        self._capture_interval = capture_interval
        self._vision_describer = vision_describer
        self._capture_func = capture_func
        self._last_capture = 0.0
        self._cv2 = None

        if force_available is not None:
            self._available = bool(force_available)
            return

        if not enabled:
            return
        try:
            import cv2  # type: ignore

            cap = cv2.VideoCapture(0)
            try:
                self._available = bool(cap.isOpened())
            finally:
                cap.release()
            self._cv2 = cv2
            if not self._available:
                log.warning("Vision camera unavailable — remaining dormant")
        except ImportError:
            log.warning("OpenCV not installed — vision channel dormant")
        except Exception as exc:
            log.warning("Vision availability check failed: %s", exc)

    @property
    def channel_id(self) -> str:
        return self.CHANNEL_ID

    @property
    def is_available(self) -> bool:
        return self._available and self._enabled

    def poll(self) -> List[ChannelMessage]:
        if not self.is_connected():
            return []

        now = time.time()
        if (now - self._last_capture) < self._capture_interval:
            return []
        self._last_capture = now

        message = self._capture_and_analyze()
        if message is None:
            return []
        return [message]

    def is_connected(self) -> bool:
        return self._connected and self.is_available

    def connect(self) -> None:
        if self.is_available:
            self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        return dict(message.metadata.get("event_triggers", {}) or {})

    def _capture_and_analyze(self) -> Optional[ChannelMessage]:
        try:
            frame = self._capture_frame()
            if frame is None:
                return None
            description = self._describe_frame(frame)
            if not description:
                return None
            triggers = self._description_to_triggers(description)
            impact = self._build_cognitive_impact(description, triggers)
            return ChannelMessage(
                channel_id=self.CHANNEL_ID,
                user_id="camera",
                text=description,
                timestamp=time.time(),
                metadata={
                    "source": "vision",
                    "event_triggers": triggers,
                    "cognitive_impact": impact,
                },
                direction="inbound",
            )
        except Exception as exc:
            log.warning("Vision capture failed: %s", exc)
            return None

    def _capture_frame(self):
        if self._capture_func is not None:
            return self._capture_func()
        if self._cv2 is None:
            return None
        cap = self._cv2.VideoCapture(0)
        try:
            ok, frame = cap.read()
            if not ok:
                return None
            return frame
        finally:
            cap.release()

    def _describe_frame(self, frame) -> str:
        if self._vision_describer is not None:
            return str(self._vision_describer(frame))
        return "A visual scene was captured with uncertain content"

    def _description_to_triggers(self, description: str) -> Dict[str, float]:
        text = description.lower()
        triggers: Dict[str, float] = {
            "SEEKING": min(1.0, 0.2 + len(description) / 240.0),
        }
        if any(word in text for word in ["person", "face", "human", "child", "family"]):
            triggers["CARE"] = 0.6
        if any(word in text for word in ["danger", "dark", "weapon", "blood", "fire", "threat"]):
            triggers["FEAR"] = 0.75
        if any(word in text for word in ["play", "toy", "cat", "dog", "smile", "sunny"]):
            triggers["PLAY"] = 0.55
        return triggers

    def _build_cognitive_impact(self, description: str, triggers: Dict[str, float]) -> Dict[str, float]:
        text_density = min(1.0, len(description) / 160.0)
        urgency = min(1.0, max(triggers.values(), default=0.0))
        return {
            "sensory": min(1.0, 0.35 + text_density * 0.45),
            "cognitive": min(1.0, 0.25 + text_density * 0.35),
            "self_": min(1.0, 0.10 + urgency * 0.30),
            "novelty": min(1.0, 0.20 + urgency * 0.50),
        }