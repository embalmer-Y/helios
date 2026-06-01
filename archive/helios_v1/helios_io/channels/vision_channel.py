"""Optional vision input channel for Helios."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..channel import ChannelConfigFieldDescriptor, ChannelConfigSnapshot, ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelOpDescriptor, ChannelStatus, InputChannel
from ..optional_channel_contract import OptionalChannelBootstrapFactory, OptionalChannelBootstrapSpec

log = logging.getLogger("helios.helios_io.channels.vision_channel")


class VisionChannel(InputChannel):
    CHANNEL_ID = "vision"
    _cached_available: Optional[bool] = None
    _cached_cv2: Any = None

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
        self._status = ChannelStatus.UNINITIALIZED
        self._paused = False
        self._suspended = False
        self._capture_interval = capture_interval
        self._vision_describer = vision_describer
        self._capture_func = capture_func
        self._last_capture = 0.0
        self._cv2 = None

        if force_available is not None:
            self._available = bool(force_available)
            self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            return

        if not enabled:
            self._status = ChannelStatus.DISCONNECTED
            return
        if self._capture_func is None and VisionChannel._cached_available is not None:
            self._available = bool(VisionChannel._cached_available)
            self._cv2 = VisionChannel._cached_cv2
            return
        try:
            import cv2  # type: ignore

            cap = cv2.VideoCapture(0)
            try:
                self._available = bool(cap.isOpened())
            finally:
                cap.release()
            self._cv2 = cv2
            if self._capture_func is None:
                VisionChannel._cached_available = self._available
                VisionChannel._cached_cv2 = cv2
            self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            if not self._available:
                log.debug("Vision camera unavailable — remaining dormant")
        except ImportError:
            if self._capture_func is None:
                VisionChannel._cached_available = False
            log.debug("OpenCV not installed — vision channel dormant")
            self._status = ChannelStatus.DISCONNECTED
        except Exception as exc:
            if self._capture_func is None:
                VisionChannel._cached_available = False
            log.debug("Vision availability check failed: %s", exc)
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
            display_name="Vision Channel",
            input_types=["image_frame"],
            output_types=["scene_description", "event_triggers"],
            input_formats=["camera"],
            output_formats=["text/plain", "trigger_dict"],
            capabilities=["poll", "vision_input", "scene_description", "trigger_extraction"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description="Capture and describe a frame, then emit a ChannelMessage.",
                    output_schema={"messages": "list[ChannelMessage]"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("init", "management", "Initialize the vision channel runtime state."),
                ChannelOpDescriptor("deinit", "management", "Deinitialize the vision channel runtime state."),
                ChannelOpDescriptor("connect", "management", "Enable periodic vision capture when available."),
                ChannelOpDescriptor("disconnect", "management", "Disable periodic vision capture."),
                ChannelOpDescriptor("pause", "management", "Pause vision polling without dropping configuration."),
                ChannelOpDescriptor("resume", "management", "Resume vision polling after pause."),
                ChannelOpDescriptor("suspend", "management", "Suspend vision activity."),
                ChannelOpDescriptor("unsuspend", "management", "Unsuspend vision activity."),
                ChannelOpDescriptor("get_config", "management", "Return the vision channel config snapshot."),
                ChannelOpDescriptor("update_config", "management", "Update mutable vision channel config fields.", input_schema={"config": "dict"}, output_schema={"snapshot": "ChannelConfigSnapshot"}),
                ChannelOpDescriptor("health_check", "management", "Return the vision channel health snapshot."),
            ],
            startup_requirements=["camera availability or injected capture function"],
            shutdown_requirements=["disconnect capture loop"],
            health_signals=["is_available", "is_connected"],
            ack_schema={"messages": "list[ChannelMessage]"},
            config_fields=[
                ChannelConfigFieldDescriptor("capture_interval", "Minimum interval between frame captures in seconds.", required=True, mutable_at_runtime=True, default_value=5.0, schema_hint="float"),
                ChannelConfigFieldDescriptor("enabled", "Whether the vision channel is enabled.", required=True, mutable_at_runtime=True, default_value=True, schema_hint="bool"),
            ],
            limitations=["Current implementation uses one-shot capture and heuristic trigger extraction."],
        )

    def poll(self) -> List[ChannelMessage]:
        if not self.is_connected() or self._paused or self._suspended:
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
            config_values={"capture_interval": self._capture_interval, "enabled": self._enabled},
            mutable_fields=["capture_interval", "enabled"],
            validation_errors=[],
        )

    def update_config(self, updates: Optional[Dict[str, Any]] = None) -> ChannelConfigSnapshot:
        updates = dict(updates or {})
        errors: List[str] = []
        if "capture_interval" in updates:
            try:
                capture_interval = float(updates["capture_interval"])
                if capture_interval <= 0.0:
                    raise ValueError()
                self._capture_interval = capture_interval
            except Exception:
                errors.append("capture_interval must be > 0")
        if "enabled" in updates:
            self._enabled = bool(updates["enabled"])
        snapshot = self.get_config_snapshot()
        if errors:
            return ChannelConfigSnapshot(snapshot.channel_id, snapshot.status, snapshot.config_values, snapshot.mutable_fields, errors)
        return snapshot

    def execute_management_op(self, op_name: str, payload: Optional[Dict[str, Any]] = None) -> ChannelManagementResult:
        payload = dict(payload or {})
        if op_name == "init":
            if self._status == ChannelStatus.UNINITIALIZED:
                self._status = ChannelStatus.INITIALIZED if self._available else ChannelStatus.DISCONNECTED
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, "Vision channel initialized.")
        if op_name == "deinit":
            self.disconnect()
            self._status = ChannelStatus.DEINITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "Vision channel deinitialized.")
        if op_name == "pause":
            self._paused = True
            self._status = ChannelStatus.PAUSED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "Vision channel paused.")
        if op_name == "resume":
            self._paused = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "Vision channel resumed.")
        if op_name == "suspend":
            self._suspended = True
            self._status = ChannelStatus.SUSPENDED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "Vision channel suspended.")
        if op_name == "unsuspend":
            self._suspended = False
            self._status = ChannelStatus.CONNECTED if self._connected and self.is_available else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "Vision channel unsuspended.")
        if op_name == "get_config":
            snapshot = self.get_config_snapshot()
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "update_config":
            snapshot = self.update_config(dict(payload.get("config", {}) or {}))
            return ChannelManagementResult(self.channel_id, op_name, not snapshot.validation_errors, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)}, error_code="config_validation_failed" if snapshot.validation_errors else "")
        if op_name == "health_check":
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload=self.health_check())
        return super().execute_management_op(op_name, payload)

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


def build_vision_bootstrap_factory(*, cfg: object) -> OptionalChannelBootstrapFactory:
    return lambda: OptionalChannelBootstrapSpec(
        channel_id="vision",
        factory=VisionChannel,
        payload={
            "capture_interval": getattr(cfg, "VISION_CAPTURE_INTERVAL", 5.0),
            "enabled": bool(getattr(cfg, "VISION_ENABLED", False)),
        },
    )