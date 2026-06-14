"""Owner: channel driver subsystem (first concrete driver).

A local CLI `ChannelDriver`: it receives operator text through an injected input source
into a bounded inbound backlog (asynchronous relative to the tick), drains queued lines as
transport-intrinsic-QoS-tagged `InboundPacket` objects, and sends Helios outbound decisions
to an injected output sink. It is local, requires no credential, and has no network blast
radius.

Boundary: this driver is transport only. It does not normalize into stimuli, score salience,
re-select channels, or semantically shape outward content. It writes only through its injected
sink and reads only from its injected input; it never calls `print` or touches real stdio
itself (a reader/writer adapter chosen by the entry point owns real stdio).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Mapping

from helios_v2.wall_clock import RECEIVED_AT_WALL_METADATA_KEY, WallClock

from ..contracts import (
    ChannelConfigField,
    ChannelConfigSnapshot,
    ChannelDriver,
    ChannelDriverDescriptor,
    ChannelDriverReadiness,
    ChannelDriverStatus,
    ChannelDriverStatusReport,
    ChannelError,
    ChannelManagementResult,
    ChannelOpSpec,
    InboundDrainResult,
    InboundPacket,
    OutboundDispatchOutcome,
    OutboundPacket,
)

CLI_DRIVER_ID = "cli"
CLI_INPUT_PACKET_TYPE = "text"
CLI_OUTPUT_OP = "reply_message"

# CLI operator text is transport-tagged as interactive: it is local, low-frequency,
# operator-driven traffic. The class is transport-intrinsic and is set without reading
# the line content for meaning.
_CLI_QOS_CLASS = "interactive"

# Lifecycle ops and their resulting status, modeled on a device driver lifecycle. The
# subsystem calls "teardown" on deregister; CLI maps it to disconnected.
_LIFECYCLE_TRANSITIONS: dict[str, ChannelDriverStatus] = {
    "init": "disconnected",
    "connect": "connected",
    "disconnect": "disconnected",
    "deinit": "uninitialized",
    "pause": "paused",
    "resume": "connected",
    "teardown": "disconnected",
}


@dataclass(frozen=True)
class CliDriverConfig:
    """Owner: channel driver subsystem (CLI driver).

    Purpose:
        Declare the CLI driver's local configuration.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id or a non-positive backlog.

    Notes:
        Labels are operator-facing only and carry no cognitive meaning. `max_backlog` bounds
        the inbound deque; overflow is counted, never unbounded.
    """

    driver_id: str = CLI_DRIVER_ID
    user_label: str = "operator"
    session_label: str = "local-cli"
    banner_enabled: bool = True
    max_backlog: int = 64

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("CliDriverConfig must declare a non-empty driver_id")
        if self.max_backlog <= 0:
            raise ChannelError("CliDriverConfig max_backlog must be a positive integer")


def _cli_descriptor(config: CliDriverConfig) -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        driver_id=config.driver_id,
        display_name="Local CLI Channel",
        directions=("inbound", "outbound"),
        input_packet_types=(CLI_INPUT_PACKET_TYPE,),
        output_ops=(CLI_OUTPUT_OP,),
        management_ops=(
            "init",
            "connect",
            "disconnect",
            "deinit",
            "pause",
            "resume",
            "health_check",
            "get_config",
            "update_config",
        ),
        config_fields=(
            ChannelConfigField(
                key="user_label",
                description="operator label shown on rendered output",
                required=False,
                mutable_at_runtime=True,
                schema_hint="str",
            ),
            ChannelConfigField(
                key="session_label",
                description="local session label",
                required=False,
                mutable_at_runtime=True,
                schema_hint="str",
            ),
            ChannelConfigField(
                key="banner_enabled",
                description="whether the output sink receives a rendered banner prefix",
                required=False,
                mutable_at_runtime=True,
                schema_hint="bool",
            ),
            ChannelConfigField(
                key="max_backlog",
                description="bounded inbound backlog capacity",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
        ),
        health_signals=("pending_inbound", "overflow_count"),
        output_op_specs=(
            ChannelOpSpec(
                op_name=CLI_OUTPUT_OP,
                required_params=("outbound_text", "target_user_id"),
                user_visible=True,
                effect_class="external_world",
                risk_class="unrestricted",
                # R93 Phase 2: the CLI driver is a wildcard operator-facing channel; it
                # serves any user id. An empty frozenset is the documented "serves everyone"
                # sentinel; the planner treats it as a pass-through for the user-binding
                # filter in `_select_channel`.
                bound_user_ids=frozenset(),
            ),
        ),
    )


@dataclass
class CliChannelDriver(ChannelDriver):
    """Owner: channel driver subsystem (CLI driver).

    Purpose:
        The first concrete `ChannelDriver`: a local bidirectional CLI transport with injected
        in-memory I/O. Operator lines enter through `submit_line` into a bounded backlog and
        drain as QoS-tagged text packets; outbound decisions render to the injected sink.

    Failure semantics:
        Backlog overflow is bounded and counted (never raised). A send while not connected
        returns an explicit non-delivered outcome rather than writing.

    Notes:
        `submit_line` models the driver's asynchronous receive: a production reader adapter (a
        background thread reading real stdin) calls it, while tests call it directly. The
        driver writes only through `output_sink`; it never calls `print`.
    """

    output_sink: Callable[[str], None]
    config: CliDriverConfig = field(default_factory=CliDriverConfig)
    wall_clock: WallClock | None = None
    _status: ChannelDriverStatus = field(default="uninitialized", init=False)
    _backlog: deque[tuple[str, float | None]] = field(default_factory=deque, init=False)
    _overflow_count: int = field(default=0, init=False)

    @property
    def driver_id(self) -> str:
        return self.config.driver_id

    def submit_line(self, text: str) -> bool:
        """Owner: channel driver subsystem (CLI driver).

        Purpose:
            Enqueue one operator line into the bounded inbound backlog (async relative to the
            tick).

        Inputs:
            `text` - one raw operator line.

        Returns:
            True when the line was accepted; False when the bounded backlog was full and the
            overflow policy dropped it (the overflow counter is incremented).

        Notes:
            Empty/whitespace-only lines are accepted into the backlog but skipped at drain
            time, matching the framework's empty-signal handling.

            R92: when an injected `wall_clock` is wired, this method captures the line's
            arrival wall-time at receive time (not at drain time) and stamps it under the
            reserved `received_at_wall` metadata key on the eventual `InboundPacket`.
            Capturing here, not in `drain_inbound`, preserves the real arrival fact even when
            ticks are delayed; without a clock, no metadata key is written (honest absence).
        """

        if len(self._backlog) >= self.config.max_backlog:
            self._overflow_count += 1
            return False
        received_at: float | None = None
        if self.wall_clock is not None:
            received_at = self.wall_clock.now().wall_seconds
        self._backlog.append((text, received_at))
        return True

    def descriptor(self) -> ChannelDriverDescriptor:
        return _cli_descriptor(self.config)

    def apply_management_op(
        self,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        if op_name == "health_check":
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message="cli driver healthy",
                payload={
                    "pending_inbound": len(self._backlog),
                    "overflow_count": self._overflow_count,
                },
            )
        if op_name == "get_config":
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message="cli driver config",
                payload=self._config_values(),
            )
        if op_name == "update_config":
            return self._apply_update_config(payload)
        if op_name in _LIFECYCLE_TRANSITIONS:
            self._status = _LIFECYCLE_TRANSITIONS[op_name]
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message=f"cli driver applied '{op_name}'",
            )
        return ChannelManagementResult(
            driver_id=self.driver_id,
            op_name=op_name,
            success=False,
            status=self._status,
            message=f"unsupported cli management op '{op_name}'",
            error_code="unsupported_op",
        )

    def _apply_update_config(
        self,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        if not payload:
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name="update_config",
                success=False,
                status=self._status,
                message="update_config requires a non-empty payload",
                error_code="missing_payload",
            )
        mutable_keys = {"user_label", "session_label", "banner_enabled"}
        unknown = tuple(key for key in payload if key not in mutable_keys)
        if unknown:
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name="update_config",
                success=False,
                status=self._status,
                message=f"update_config rejected immutable/unknown fields: {', '.join(sorted(unknown))}",
                error_code="invalid_config_field",
            )
        updated = {
            "user_label": payload.get("user_label", self.config.user_label),
            "session_label": payload.get("session_label", self.config.session_label),
            "banner_enabled": bool(payload.get("banner_enabled", self.config.banner_enabled)),
            "driver_id": self.config.driver_id,
            "max_backlog": self.config.max_backlog,
        }
        self.config = CliDriverConfig(**updated)
        return ChannelManagementResult(
            driver_id=self.driver_id,
            op_name="update_config",
            success=True,
            status=self._status,
            message="cli driver config updated",
            payload=self._config_values(),
        )

    def status(self) -> ChannelDriverStatusReport:
        return ChannelDriverStatusReport(
            driver_id=self.driver_id,
            status=self._status,
            connected=self._status == "connected",
            pending_inbound=len(self._backlog),
            health={"overflow_count": self._overflow_count},
        )

    def config_snapshot(self) -> ChannelConfigSnapshot:
        return ChannelConfigSnapshot(
            driver_id=self.driver_id,
            status=self._status,
            config_values=self._config_values(),
            mutable_fields=("user_label", "session_label", "banner_enabled"),
        )

    def _config_values(self) -> dict[str, object]:
        return {
            "user_label": self.config.user_label,
            "session_label": self.config.session_label,
            "banner_enabled": self.config.banner_enabled,
            "max_backlog": self.config.max_backlog,
        }

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        if budget < 0:
            raise ChannelError("CliChannelDriver drain budget must be >= 0")
        packets: list[InboundPacket] = []
        consumed = 0
        while self._backlog and len(packets) < budget:
            line, received_at = self._backlog.popleft()
            consumed += 1
            if not line.strip():
                # Empty operator lines are skipped (no stimulus), matching framework
                # empty-signal handling; they still count against the budget consumed.
                continue
            metadata: dict[str, object] = {
                "user_label": self.config.user_label,
                "session_label": self.config.session_label,
            }
            # R92: stamp the real arrival time captured at `submit_line` (not the drain time)
            # under the reserved `received_at_wall` metadata key. Absent when no clock was
            # wired (honest absence).
            if received_at is not None:
                metadata[RECEIVED_AT_WALL_METADATA_KEY] = received_at
            packets.append(
                InboundPacket(
                    packet_id=f"cli-line:{self.config.session_label}:{id(line)}:{consumed}",
                    driver_id=self.driver_id,
                    packet_type=CLI_INPUT_PACKET_TYPE,
                    content=line,
                    qos_class=_CLI_QOS_CLASS,
                    metadata=metadata,
                )
            )
        overflow = self._overflow_count
        self._overflow_count = 0
        return InboundDrainResult(
            driver_id=self.driver_id,
            packets=tuple(packets),
            pending_remaining=len(self._backlog),
            overflow_count=overflow,
        )

    def send_outbound(self, packet: OutboundPacket) -> OutboundDispatchOutcome:
        if self._status != "connected":
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail=f"cli driver not connected (status={self._status})",
            )
        text = packet.payload.get("outbound_text")
        if not isinstance(text, str) or not text:
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail="outbound packet missing non-empty outbound_text",
            )
        rendered = self._render(text)
        self.output_sink(rendered)
        return OutboundDispatchOutcome(
            packet_id=packet.packet_id,
            target_driver_id=self.driver_id,
            status="delivered",
            detail=f"rendered op '{packet.op_name}' to cli sink",
        )

    def _render(self, text: str) -> str:
        if self.config.banner_enabled:
            return f"[{self.config.user_label}] {text}"
        return text

    def static_readiness(self) -> ChannelDriverReadiness:
        # CLI declares no external credential; it is always statically ready.
        return ChannelDriverReadiness(
            driver_id=self.driver_id,
            ready=True,
            detail="cli driver requires no external credential",
        )
