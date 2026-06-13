"""Owner: channel driver subsystem.

Owns:
- the uniform `ChannelDriver` protocol every concrete driver implements
- driver-facing descriptor, config, management, status, and readiness contracts
- transport-intrinsic QoS taxonomy and inbound packet/drain contracts
- outbound packet and dispatch-outcome contracts
- the subsystem (`ChannelSubsystemAPI`) protocol and `ChannelError`

Does not own:
- raw-signal normalization (owned by `02` sensory; the framework emits `RawSignal`)
- salience / cognitive importance (owned by `03` appraisal; QoS is transport-intrinsic)
- channel selection or acceptance (owned by `13` planner)
- outward content shaping (owned by `16`)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.sensory.contracts import RawSignal

# Reserved metadata key carrying the transport-intrinsic QoS class across the owner
# boundary. The framework writes it onto `RawSignal.metadata`; `02` sensory preserves it
# onto `Stimulus.metadata` verbatim; only `03` appraisal reads it as a salience input.
# Carriage is a reserved string-valued key, not a typed field, so `02` sensory does not
# need to reference this `30`-owned taxonomy (see design 5.4).
CHANNEL_QOS_METADATA_KEY = "channel_qos"


class ChannelError(RuntimeError):
    """Hard-stop error raised when channel driver subsystem invariants fail.

    This covers an empty driver identity, a duplicate driver registration, an unknown
    target driver on dispatch, an out-of-taxonomy QoS class or status, a negative budget,
    and any malformed driver-supplied contract. The subsystem never fabricates transport
    to mask a failure.
    """


ChannelDirection = Literal["inbound", "outbound"]
ChannelDriverStatus = Literal[
    "uninitialized",
    "connected",
    "disconnected",
    "paused",
    "error",
]
# Transport-intrinsic QoS taxonomy. These classes describe transport-visible delivery
# expectations only; they are never a statement about cognitive importance.
ChannelQosClass = Literal["control", "interactive", "bulk", "background"]
# Per-op property taxonomies (R85). Each output op a driver offers self-describes these
# properties. `effect_class` says where the op's consequence lands (consumed by `17`/`23`
# consequence classification, R87). `risk_class` says whether the op needs governance review
# (declared in R85, enforced by the `13`+`14` fail-closed gate in R86). Cognition never sets
# these; the owning driver declares them and the planner/governance/evaluation owners read them.
OpEffectClass = Literal["internal_cognitive", "local_host", "external_world"]
OpRiskClass = Literal["unrestricted", "governed", "restricted"]
OutboundDispatchStatus = Literal[
    "delivered",
    "failed",
    "driver_unavailable",
    "dropped_overflow",
]

_DIRECTIONS = {"inbound", "outbound"}
_DRIVER_STATUSES = {"uninitialized", "connected", "disconnected", "paused", "error"}
_QOS_CLASSES = {"control", "interactive", "bulk", "background"}
_OP_EFFECT_CLASSES = {"internal_cognitive", "local_host", "external_world"}
_OP_RISK_CLASSES = {"unrestricted", "governed", "restricted"}
_DISPATCH_STATUSES = {"delivered", "failed", "driver_unavailable", "dropped_overflow"}


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(mapping))
    for key in frozen:
        if not key:
            raise ChannelError("Channel mappings must not contain empty keys")
    return frozen


@dataclass(frozen=True)
class ChannelConfigField:
    """Immutable declaration of one driver configuration field.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty key.
    """

    key: str
    description: str
    required: bool
    mutable_at_runtime: bool
    schema_hint: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ChannelError("ChannelConfigField must declare a non-empty key")


@dataclass(frozen=True)
class ChannelOpSpec:
    """Immutable per-op self-description for one of a driver's output ops.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty op name, an empty required-param key, or an
        out-of-taxonomy effect/risk class.

    Notes:
        The owning driver declares each output op's properties; cognition never sets them. Axis
        consumers (R85): `required_params` and `user_visible` are validated/used by the `13` planner
        (generic op-input validation; user-visible reply/target handling); `effect_class` is declared
        in R85 and consumed by `17`/`23` consequence classification in R87; `risk_class` is declared in
        R85 and enforced by the `13`+`14` fail-closed gate in R86. Declaring `effect_class`/`risk_class`
        now is honest forward self-description, not an enforced gate yet.
    """

    op_name: str
    required_params: tuple[str, ...] = ()
    user_visible: bool = False
    effect_class: OpEffectClass = "external_world"
    risk_class: OpRiskClass = "unrestricted"

    def __post_init__(self) -> None:
        if not self.op_name:
            raise ChannelError("ChannelOpSpec must declare a non-empty op_name")
        for key in self.required_params:
            if not key:
                raise ChannelError("ChannelOpSpec required_params must not contain empty keys")
        if self.effect_class not in _OP_EFFECT_CLASSES:
            raise ChannelError("ChannelOpSpec effect_class must use the fixed taxonomy")
        if self.risk_class not in _OP_RISK_CLASSES:
            raise ChannelError("ChannelOpSpec risk_class must use the fixed taxonomy")


@dataclass(frozen=True)
class ChannelDriverDescriptor:
    """Immutable self-description of one channel driver.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id or display name, an empty
        directions tuple, an out-of-taxonomy direction, or a duplicate config-field key.

    Notes:
        The descriptor declares what a driver transports (packet types, output ops),
        what it can be managed by (management ops), how it is configured (config fields),
        what health signals it exposes, and which directions it serves. It declares no
        cognitive policy.
    """

    driver_id: str
    display_name: str
    directions: tuple[ChannelDirection, ...]
    input_packet_types: tuple[str, ...] = ()
    output_ops: tuple[str, ...] = ()
    management_ops: tuple[str, ...] = ()
    config_fields: tuple[ChannelConfigField, ...] = ()
    health_signals: tuple[str, ...] = ()
    output_op_specs: tuple[ChannelOpSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("ChannelDriverDescriptor must declare a non-empty driver_id")
        if not self.display_name:
            raise ChannelError("ChannelDriverDescriptor must declare a non-empty display_name")
        if not self.directions:
            raise ChannelError("ChannelDriverDescriptor must declare at least one direction")
        for direction in self.directions:
            if direction not in _DIRECTIONS:
                raise ChannelError("ChannelDriverDescriptor directions must use the fixed taxonomy")
        seen_fields: set[str] = set()
        for config_field in self.config_fields:
            if not isinstance(config_field, ChannelConfigField):
                raise ChannelError(
                    "ChannelDriverDescriptor config_fields must contain ChannelConfigField values"
                )
            if config_field.key in seen_fields:
                raise ChannelError(
                    f"ChannelDriverDescriptor config_fields must be unique: '{config_field.key}'"
                )
            seen_fields.add(config_field.key)
        seen_ops: set[str] = set()
        for spec in self.output_op_specs:
            if not isinstance(spec, ChannelOpSpec):
                raise ChannelError(
                    "ChannelDriverDescriptor output_op_specs must contain ChannelOpSpec values"
                )
            if spec.op_name not in self.output_ops:
                raise ChannelError(
                    f"ChannelDriverDescriptor output_op_specs op_name must be a declared output op: "
                    f"'{spec.op_name}'"
                )
            if spec.op_name in seen_ops:
                raise ChannelError(
                    f"ChannelDriverDescriptor output_op_specs must be unique per op: '{spec.op_name}'"
                )
            seen_ops.add(spec.op_name)

    def op_spec(self, op_name: str) -> "ChannelOpSpec | None":
        """Owner: channel driver subsystem.

        Purpose:
            Return the per-op self-description for `op_name`, or `None` when the op declares none.

        Returns:
            The matching `ChannelOpSpec`, else `None` (an op with no declared spec has no required
            params and is treated as non-user-visible by default).
        """

        for spec in self.output_op_specs:
            if spec.op_name == op_name:
                return spec
        return None

    def supports_direction(self, direction: ChannelDirection) -> bool:
        """Owner: channel driver subsystem.

        Purpose:
            Report whether this driver serves the given transport direction.

        Returns:
            True when `direction` is among the declared directions.
        """

        return direction in self.directions


@dataclass(frozen=True)
class ChannelConfigSnapshot:
    """Immutable snapshot of one driver's current configuration state.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id or out-of-taxonomy status.
    """

    driver_id: str
    status: ChannelDriverStatus
    config_values: Mapping[str, object] = field(default_factory=dict)
    mutable_fields: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("ChannelConfigSnapshot must declare a non-empty driver_id")
        if self.status not in _DRIVER_STATUSES:
            raise ChannelError("ChannelConfigSnapshot status must use the fixed taxonomy")
        object.__setattr__(self, "config_values", _freeze_mapping(self.config_values))


@dataclass(frozen=True)
class ChannelManagementResult:
    """Immutable structured result of one driver lifecycle/management op.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id, op name, status, or on a
        failed result that omits an error code.

    Notes:
        Lifecycle transitions (register, deregister, connect, pause, ...) and config edits
        return this structured result rather than raising for expected operational outcomes.
        `ChannelError` is reserved for invariant violations.
    """

    driver_id: str
    op_name: str
    success: bool
    status: ChannelDriverStatus
    message: str
    error_code: str | None = None
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("ChannelManagementResult must declare a non-empty driver_id")
        if not self.op_name:
            raise ChannelError("ChannelManagementResult must declare a non-empty op_name")
        if self.status not in _DRIVER_STATUSES:
            raise ChannelError("ChannelManagementResult status must use the fixed taxonomy")
        if not self.success and not self.error_code:
            raise ChannelError("A failed ChannelManagementResult must declare a non-empty error_code")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))


@dataclass(frozen=True)
class ChannelDriverStatusReport:
    """Immutable runtime status report for one driver.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id, out-of-taxonomy status,
        or a negative pending-inbound count.
    """

    driver_id: str
    status: ChannelDriverStatus
    connected: bool
    pending_inbound: int
    health: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("ChannelDriverStatusReport must declare a non-empty driver_id")
        if self.status not in _DRIVER_STATUSES:
            raise ChannelError("ChannelDriverStatusReport status must use the fixed taxonomy")
        if self.pending_inbound < 0:
            raise ChannelError("ChannelDriverStatusReport pending_inbound must be >= 0")
        object.__setattr__(self, "health", _freeze_mapping(self.health))


@dataclass(frozen=True)
class ChannelDriverReadiness:
    """Immutable per-driver static-readiness fact.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id or empty detail.

    Notes:
        Static readiness is deterministic and network-free: a driver reports whether a
        declared credential/resource is present, not whether a live connection succeeds.
    """

    driver_id: str
    ready: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("ChannelDriverReadiness must declare a non-empty driver_id")
        if not self.detail:
            raise ChannelError("ChannelDriverReadiness must declare a non-empty detail")


@dataclass(frozen=True)
class ChannelReadinessReport:
    """Immutable subsystem-level static-readiness report.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty report id or duplicate driver entries.
    """

    report_id: str
    entries: tuple[ChannelDriverReadiness, ...]

    def __post_init__(self) -> None:
        if not self.report_id:
            raise ChannelError("ChannelReadinessReport must declare a non-empty report_id")
        seen: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, ChannelDriverReadiness):
                raise ChannelError("ChannelReadinessReport entries must be ChannelDriverReadiness values")
            if entry.driver_id in seen:
                raise ChannelError("ChannelReadinessReport entries must be keyed by unique driver ids")
            seen.add(entry.driver_id)

    def all_ready(self) -> bool:
        """Owner: channel driver subsystem.

        Purpose:
            Report whether every entry in the report is statically ready.

        Returns:
            True when there is at least one entry and all entries are ready; False otherwise
            (including an empty report).
        """

        return bool(self.entries) and all(entry.ready for entry in self.entries)


@dataclass(frozen=True)
class ChannelStateSnapshot:
    """Immutable real per-driver channel state for the planner.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on duplicate driver ids across descriptors or
        statuses.

    Notes:
        This is the real-state replacement for the planner's hardcoded channel snapshot. It
        carries transport facts only (descriptors + status), never a channel-selection
        recommendation; selection remains the planner's responsibility.
    """

    descriptors: tuple[ChannelDriverDescriptor, ...]
    statuses: tuple[ChannelDriverStatusReport, ...]

    def __post_init__(self) -> None:
        descriptor_ids: set[str] = set()
        for descriptor in self.descriptors:
            if descriptor.driver_id in descriptor_ids:
                raise ChannelError("ChannelStateSnapshot descriptors must have unique driver ids")
            descriptor_ids.add(descriptor.driver_id)
        status_ids: set[str] = set()
        for status in self.statuses:
            if status.driver_id in status_ids:
                raise ChannelError("ChannelStateSnapshot statuses must have unique driver ids")
            status_ids.add(status.driver_id)


@dataclass(frozen=True)
class InboundPacket:
    """Immutable transport-received packet emitted by a driver before normalization.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty packet id, driver id, or packet type,
        or an out-of-taxonomy QoS class.

    Notes:
        The QoS class is derived only from transport-visible facts (the source lane, packet
        type, connection class); it is never derived by reading `content` for meaning. The
        framework, not the driver, decides how to carry the QoS marker onto `RawSignal`.
    """

    packet_id: str
    driver_id: str
    packet_type: str
    content: str
    qos_class: ChannelQosClass
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.packet_id:
            raise ChannelError("InboundPacket must declare a non-empty packet_id")
        if not self.driver_id:
            raise ChannelError("InboundPacket must declare a non-empty driver_id")
        if not self.packet_type:
            raise ChannelError("InboundPacket must declare a non-empty packet_type")
        if self.qos_class not in _QOS_CLASSES:
            raise ChannelError("InboundPacket qos_class must use the fixed QoS taxonomy")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class InboundDrainResult:
    """Immutable driver-level result of one bounded inbound drain.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` when more packets are returned than the budget
        allowed, when pending or overflow counts are negative, or when a packet's driver id
        does not match the draining driver.

    Notes:
        `pending_remaining` is the driver's own count of packets still queued after this
        drain; the framework uses it to decide whether the driver stays in the ready set.
    """

    driver_id: str
    packets: tuple[InboundPacket, ...]
    pending_remaining: int
    overflow_count: int = 0

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("InboundDrainResult must declare a non-empty driver_id")
        if self.pending_remaining < 0:
            raise ChannelError("InboundDrainResult pending_remaining must be >= 0")
        if self.overflow_count < 0:
            raise ChannelError("InboundDrainResult overflow_count must be >= 0")
        for packet in self.packets:
            if not isinstance(packet, InboundPacket):
                raise ChannelError("InboundDrainResult packets must contain InboundPacket values")
            if packet.driver_id != self.driver_id:
                raise ChannelError("InboundDrainResult packets must originate from the draining driver")


@dataclass(frozen=True)
class SubsystemDrainResult:
    """Immutable framework-level result of one NAPI-style bounded drain across drivers.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on a negative pending or drained count.

    Notes:
        `raw_signals` are already mapped from inbound packets, each carrying the QoS marker
        under `CHANNEL_QOS_METADATA_KEY` in its metadata. `pending_remaining` is the total
        across all drivers still queued after this drain (the NAPI poll-list remainder).
    """

    raw_signals: tuple[RawSignal, ...]
    pending_remaining: int
    drained_count: int
    overflow_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pending_remaining < 0:
            raise ChannelError("SubsystemDrainResult pending_remaining must be >= 0")
        if self.drained_count < 0:
            raise ChannelError("SubsystemDrainResult drained_count must be >= 0")
        for signal in self.raw_signals:
            if not isinstance(signal, RawSignal):
                raise ChannelError("SubsystemDrainResult raw_signals must contain RawSignal values")
        overflow = MappingProxyType(dict(self.overflow_counts))
        for key, value in overflow.items():
            if not key:
                raise ChannelError("SubsystemDrainResult overflow_counts must not contain empty keys")
            if not isinstance(value, int) or value < 0:
                raise ChannelError("SubsystemDrainResult overflow_counts values must be >= 0 integers")
        object.__setattr__(self, "overflow_counts", overflow)


@dataclass(frozen=True)
class OutboundPacket:
    """Immutable transport request for one planner-accepted action decision.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty packet id, target driver id, or op
        name, or a negative execution priority.

    Notes:
        `execution_priority` is planner-provided and carried verbatim; the framework orders
        dispatch by it but never recomputes it. `provenance` carries the originating
        decision/proposal ids for writeback/evaluation.
    """

    packet_id: str
    target_driver_id: str
    op_name: str
    payload: Mapping[str, object] = field(default_factory=dict)
    execution_priority: int = 0
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.packet_id:
            raise ChannelError("OutboundPacket must declare a non-empty packet_id")
        if not self.target_driver_id:
            raise ChannelError("OutboundPacket must declare a non-empty target_driver_id")
        if not self.op_name:
            raise ChannelError("OutboundPacket must declare a non-empty op_name")
        if self.execution_priority < 0:
            raise ChannelError("OutboundPacket execution_priority must be >= 0")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))


@dataclass(frozen=True)
class OutboundDispatchOutcome:
    """Immutable explicit outcome of dispatching one outbound packet.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on an empty packet id, target driver id, out-of-
        taxonomy status, or empty detail.
    """

    packet_id: str
    target_driver_id: str
    status: OutboundDispatchStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.packet_id:
            raise ChannelError("OutboundDispatchOutcome must declare a non-empty packet_id")
        if not self.target_driver_id:
            raise ChannelError("OutboundDispatchOutcome must declare a non-empty target_driver_id")
        if self.status not in _DISPATCH_STATUSES:
            raise ChannelError("OutboundDispatchOutcome status must use the fixed taxonomy")
        if not self.detail:
            raise ChannelError("OutboundDispatchOutcome must declare a non-empty detail")


@dataclass(frozen=True)
class SubsystemDispatchResult:
    """Immutable framework-level result of one bounded outbound dispatch.

    Owner: channel driver subsystem.

    Failure semantics:
        Construction raises `ChannelError` on a negative dispatched or deferred count.

    Notes:
        `deferred_count` is the number of decisions that exceeded the dispatch budget and
        are carried to the next tick; deferral is never silent loss.
    """

    outcomes: tuple[OutboundDispatchOutcome, ...]
    dispatched_count: int
    deferred_count: int

    def __post_init__(self) -> None:
        if self.dispatched_count < 0:
            raise ChannelError("SubsystemDispatchResult dispatched_count must be >= 0")
        if self.deferred_count < 0:
            raise ChannelError("SubsystemDispatchResult deferred_count must be >= 0")
        for outcome in self.outcomes:
            if not isinstance(outcome, OutboundDispatchOutcome):
                raise ChannelError(
                    "SubsystemDispatchResult outcomes must contain OutboundDispatchOutcome values"
                )


@runtime_checkable
class ChannelDriver(Protocol):
    """Owner: channel driver subsystem (driver seam).

    Purpose:
        The one uniform driver API every concrete driver implements, modeled on a Linux
        kernel device driver: it describes itself, accepts management ops, reports status
        and config, drains its own bounded inbound backlog under a budget, sends one
        already-accepted outbound packet, and reports network-free static readiness.

    Notes:
        Asynchronous receive lives inside the driver. The drain is synchronous and bounded;
        the framework owns the tick-boundary schedule, the driver owns its own backlog.
    """

    @property
    def driver_id(self) -> str:
        """Return the stable unique driver id."""

        ...

    def descriptor(self) -> ChannelDriverDescriptor:
        """Return the driver's immutable self-description."""

        ...

    def apply_management_op(
        self,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        """Apply one lifecycle/management op and return its structured result."""

        ...

    def status(self) -> ChannelDriverStatusReport:
        """Return the driver's current runtime status report."""

        ...

    def config_snapshot(self) -> ChannelConfigSnapshot:
        """Return the driver's current configuration snapshot."""

        ...

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        """Drain at most `budget` packets from the driver's bounded backlog."""

        ...

    def send_outbound(self, packet: OutboundPacket) -> OutboundDispatchOutcome:
        """Send one already-accepted outbound packet and return an explicit outcome."""

        ...

    def static_readiness(self) -> ChannelDriverReadiness:
        """Return deterministic, network-free static readiness for this driver."""

        ...


@runtime_checkable
class ChannelSubsystemAPI(Protocol):
    """Owner: channel driver subsystem API.

    Purpose:
        The public framework interface: a runtime-pluggable driver registry plus two
        tick-boundary schedulers (NAPI-style bounded inbound drain, bounded outbound
        dispatch), a real per-driver state snapshot for the planner, and a network-free
        static-readiness report.
    """

    def register_driver(self, driver: ChannelDriver) -> ChannelManagementResult:
        """Register one driver at runtime and return the structured result."""

        ...

    def deregister_driver(self, driver_id: str) -> ChannelManagementResult:
        """Tear down then remove one driver, returning the structured result."""

        ...

    def apply_management_op(
        self,
        driver_id: str,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        """Route one management op to the named driver."""

        ...

    def drain_inbound(self, budget: int) -> SubsystemDrainResult:
        """Run one NAPI-style bounded fair drain across ready drivers."""

        ...

    def dispatch_outbound(
        self,
        decisions: tuple[OutboundPacket, ...],
        budget: int,
    ) -> SubsystemDispatchResult:
        """Dispatch outbound packets under a budget, respecting execution priority."""

        ...

    def channel_state_snapshot(self) -> ChannelStateSnapshot:
        """Return the real per-driver descriptor/status snapshot for the planner."""

        ...

    def check_static_readiness(self, driver_ids: tuple[str, ...]) -> ChannelReadinessReport:
        """Return a deterministic, network-free static-readiness report."""

        ...
