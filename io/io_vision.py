"""
io/io_vision.py — Helios 视觉输入模块 (EventSource)

使用 OpenCV 进行摄像头帧捕获，通过视觉 LLM 生成场景描述，
并将描述转换为情感触发器和认知影响配置。

硬件可选模块 — 当 OpenCV 或摄像头不可用时优雅降级为静默模式。

Implements the EventSource interface so visual scene descriptions flow into
the Helios tick pipeline as emotional triggers and awareness messages.

Requirements: 32.1, 32.2, 32.3, 32.4
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Dict, List, Optional

from core.event_source import EventSource
from core.helios_state import HeliosState

logger = logging.getLogger("helios.io.vision")


class VisionModule(EventSource):
    """
    Camera-based visual input using OpenCV + vision LLM.

    Implements EventSource so scene descriptions and emotional triggers are
    delivered into the Helios event collection pipeline. Captures frames at
    a configurable interval and analyzes them via a vision LLM to produce
    Panksepp triggers and CognitiveImpactProfile data.

    Operates as a hardware-optional module — gracefully remains dormant when
    OpenCV is not installed or no camera device is detected.

    Usage:
        vision = VisionModule()
        if vision.is_available:
            vision.register()
        # Each tick:
        triggers = vision.poll(state)   # Panksepp triggers from scene
        messages = vision.get_messages()  # scene descriptions

    Runtime pluggability:
        vision.register()    # activate vision input
        vision.deregister()  # deactivate, release resources
    """

    DEFAULT_CAPTURE_INTERVAL = 5.0  # seconds

    def __init__(
        self,
        capture_interval: float = DEFAULT_CAPTURE_INTERVAL,
        vision_llm_model: Optional[str] = None,
        camera_index: int = 0,
        enabled: bool = True,
    ):
        self._enabled = enabled
        self._available = False
        self._registered = False
        self._capture_interval = capture_interval
        self._vision_llm_model = vision_llm_model or "deepseek-chat"
        self._camera_index = camera_index
        self._last_capture: float = 0.0
        self._cv2 = None  # lazy reference to cv2 module
        self._lock = threading.Lock()
        self._pending_descriptions: List[dict] = []
        self._last_triggers: Dict[str, float] = {}
        self._last_impact: Optional[object] = None  # CognitiveImpactProfile

        if not enabled:
            logger.info("Vision module disabled by configuration")
            return

        # Try importing OpenCV
        try:
            import cv2  # noqa: F401
            self._cv2 = cv2
        except ImportError:
            logger.warning(
                "OpenCV (cv2) not installed — vision unavailable. "
                "Install with: pip install opencv-python"
            )
            return

        # Check for camera device availability
        if not self._check_camera():
            logger.warning(
                "Camera device unavailable — vision module dormant"
            )
            return

        self._available = True
        logger.info(
            "Vision module initialized — capture interval: %.1fs, camera index: %d",
            self._capture_interval,
            self._camera_index,
        )

    def _check_camera(self) -> bool:
        """Probe for available camera device."""
        try:
            cv2 = self._cv2
            cap = cv2.VideoCapture(self._camera_index)
            if cap.isOpened():
                cap.release()
                return True
            return False
        except Exception as e:
            logger.debug("Camera probe failed: %s", e)
            return False

    @property
    def is_available(self) -> bool:
        """Runtime hardware probing: True when OpenCV + camera + registered."""
        return self._available and self._enabled and self._registered

    @property
    def capture_interval(self) -> float:
        """Current capture interval in seconds."""
        return self._capture_interval

    @capture_interval.setter
    def capture_interval(self, value: float):
        """Set capture interval (minimum 1.0 second)."""
        self._capture_interval = max(1.0, value)

    @property
    def last_impact(self) -> Optional[object]:
        """Last CognitiveImpactProfile generated from scene analysis."""
        return self._last_impact

    def register(self):
        """Register as EventSource input module (activate vision)."""
        self._registered = True
        if self._available:
            logger.info("Vision module registered — visual input active")
        else:
            logger.debug("Vision module registered but not available (dormant mode)")

    def deregister(self):
        """Deregister and release resources (deactivate vision)."""
        self._registered = False
        logger.info("Vision module deregistered — visual input inactive")

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Capture frame if interval elapsed, return emotional triggers.

        Only captures a new frame when the configured capture interval has
        elapsed since the last capture. Between captures, returns an empty dict.

        Args:
            state: The current tick's HeliosState for context-aware polling.

        Returns:
            Dictionary mapping Panksepp system names to trigger intensity
            values in [0.0, 1.0]. Empty dict if dormant, interval not elapsed,
            or capture fails.
        """
        if not self.is_available:
            return {}

        now = time.time()
        if (now - self._last_capture) < self._capture_interval:
            return {}

        self._last_capture = now
        triggers = self._capture_and_analyze()
        return triggers

    def get_messages(self) -> List[dict]:
        """Return pending scene descriptions as message dicts.

        Each message dict contains:
            - "text": The scene description from vision LLM
            - "source": "vision" to identify the input source
            - "timestamp": When the frame was captured
            - "user_id": "camera" (local camera input)

        Returns:
            List of message dicts for pending scene descriptions, empty if
            none or dormant.
        """
        with self._lock:
            messages = self._pending_descriptions.copy()
            self._pending_descriptions.clear()
            return messages

    def _capture_and_analyze(self) -> Dict[str, float]:
        """Capture a frame, describe with vision LLM, convert to Panksepp triggers.

        Workflow:
        1. Open camera and capture a single frame
        2. Encode frame as base64 JPEG for LLM input
        3. Send to vision LLM for scene description
        4. Parse description into CognitiveImpactProfile + Panksepp triggers
        5. Buffer scene description as a message for awareness logging

        Returns:
            Panksepp trigger dictionary, empty on failure.
        """
        cv2 = self._cv2
        if cv2 is None:
            return {}

        try:
            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                logger.debug("Vision: camera not available for capture")
                self._available = False
                return {}

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logger.debug("Vision: frame capture failed")
                return {}

            # Encode frame as JPEG for LLM
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buffer).decode("utf-8")

            # Get scene description from vision LLM
            description = self._describe_scene(frame_b64)
            if not description:
                return {}

            # Convert description to triggers and impact profile
            triggers, impact = self._description_to_triggers(description)

            # Store impact profile for ICRI feeding
            self._last_impact = impact
            self._last_triggers = triggers

            # Buffer scene description as awareness message
            message = {
                "text": f"[视觉] {description}",
                "source": "vision",
                "timestamp": time.time(),
                "user_id": "camera",
            }
            with self._lock:
                self._pending_descriptions.append(message)

            logger.debug("Vision: captured scene — %s", description[:60])
            return triggers

        except Exception as e:
            logger.warning("Vision capture/analysis failed: %s", e)
            return {}

    def _describe_scene(self, frame_b64: str) -> str:
        """Send frame to vision LLM and get scene description.

        Uses a lightweight prompt asking for emotional scene description
        suitable for converting to Panksepp triggers.

        Args:
            frame_b64: Base64-encoded JPEG frame data.

        Returns:
            Scene description string, or empty string on failure.
        """
        try:
            from openai import OpenAI
            import os

            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
            )

            response = client.chat.completions.create(
                model=self._vision_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个视觉场景分析器。描述你看到的场景，"
                            "重点关注情感相关的元素（人物表情、氛围、活动、"
                            "危险信号、温馨场景等）。用一两句话简洁描述。"
                            "同时评估场景的感官丰富度(sensory)、认知复杂度(cognitive)、"
                            "自我相关性(self_relevance)和新奇度(novelty)，"
                            "每个维度0-1分。格式：描述|sensory:X|cognitive:X|self:X|novelty:X"
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_b64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": "请描述这个场景并评估其认知影响维度。",
                            },
                        ],
                    },
                ],
                max_tokens=200,
                timeout=10.0,
            )

            result = response.choices[0].message.content
            return result.strip() if result else ""

        except ImportError:
            logger.warning("Vision: openai package not installed for LLM description")
            return ""
        except Exception as e:
            logger.warning("Vision: LLM scene description failed: %s", e)
            return ""

    def _description_to_triggers(
        self, description: str
    ) -> tuple:
        """Convert scene description to Panksepp triggers + CognitiveImpactProfile.

        Parses the structured LLM response to extract:
        1. CognitiveImpactProfile dimensions from the formatted output
        2. Panksepp triggers inferred from scene content keywords

        Args:
            description: Scene description from vision LLM (may include
                        structured dimension scores).

        Returns:
            Tuple of (triggers_dict, CognitiveImpactProfile or None).
        """
        from cognition.phi import CognitiveImpactProfile

        triggers: Dict[str, float] = {}
        sensory = 0.3
        cognitive = 0.2
        self_ = 0.1
        novelty = 0.3

        # Parse structured dimensions from LLM response
        # Format: "描述|sensory:X|cognitive:X|self:X|novelty:X"
        parts = description.split("|")
        text_description = parts[0].strip()

        for part in parts[1:]:
            part = part.strip().lower()
            try:
                if part.startswith("sensory:"):
                    sensory = float(part.split(":")[1])
                elif part.startswith("cognitive:"):
                    cognitive = float(part.split(":")[1])
                elif part.startswith("self:"):
                    self_ = float(part.split(":")[1])
                elif part.startswith("novelty:"):
                    novelty = float(part.split(":")[1])
            except (ValueError, IndexError):
                continue

        # Clamp values to [0, 1]
        sensory = max(0.0, min(1.0, sensory))
        cognitive = max(0.0, min(1.0, cognitive))
        self_ = max(0.0, min(1.0, self_))
        novelty = max(0.0, min(1.0, novelty))

        # Create CognitiveImpactProfile
        impact = CognitiveImpactProfile(
            sensory=sensory,
            cognitive=cognitive,
            self_=self_,
            novelty=novelty,
        )

        # Derive Panksepp triggers from scene content via keyword heuristics
        text_lower = text_description.lower()

        # SEEKING: curiosity, exploration, interesting objects
        seeking_keywords = ["有趣", "新奇", "探索", "发现", "interesting", "curious", "novel"]
        if any(kw in text_lower for kw in seeking_keywords):
            triggers["SEEKING"] = min(1.0, novelty * 0.8 + 0.2)

        # CARE: warmth, nurturing, people together
        care_keywords = ["温馨", "关爱", "拥抱", "微笑", "孩子", "warm", "caring", "smile", "child"]
        if any(kw in text_lower for kw in care_keywords):
            triggers["CARE"] = min(1.0, self_ * 0.6 + 0.3)

        # PLAY: fun, playful, games, laughter
        play_keywords = ["玩耍", "游戏", "欢笑", "快乐", "playful", "fun", "game", "laugh"]
        if any(kw in text_lower for kw in play_keywords):
            triggers["PLAY"] = min(1.0, sensory * 0.5 + 0.3)

        # FEAR: danger, threat, dark, scary
        fear_keywords = ["危险", "威胁", "黑暗", "恐怖", "danger", "threat", "dark", "scary"]
        if any(kw in text_lower for kw in fear_keywords):
            triggers["FEAR"] = min(1.0, novelty * 0.7 + 0.2)

        # PANIC: alone, abandoned, empty, loss
        panic_keywords = ["孤独", "空旷", "离别", "失去", "alone", "empty", "loss", "abandoned"]
        if any(kw in text_lower for kw in panic_keywords):
            triggers["PANIC"] = min(1.0, self_ * 0.5 + 0.2)

        # RAGE: conflict, anger, frustration
        rage_keywords = ["冲突", "愤怒", "争吵", "破坏", "conflict", "anger", "fight", "destroy"]
        if any(kw in text_lower for kw in rage_keywords):
            triggers["RAGE"] = min(1.0, cognitive * 0.5 + 0.2)

        # Default: if no keywords matched but scene has high novelty, add mild SEEKING
        if not triggers and novelty > 0.4:
            triggers["SEEKING"] = novelty * 0.5

        return triggers, impact

    def get_state(self) -> dict:
        """Return module state for monitoring/dashboard."""
        return {
            "enabled": self._enabled,
            "available": self._available,
            "registered": self._registered,
            "is_available": self.is_available,
            "capture_interval": self._capture_interval,
            "camera_index": self._camera_index,
            "last_capture": self._last_capture,
            "pending_descriptions": len(self._pending_descriptions),
        }
