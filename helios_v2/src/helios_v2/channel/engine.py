"""Owner: channel driver subsystem.

Provides the framework owner (`ChannelSubsystem`) and a deterministic in-memory fake
driver (`InMemoryChannelDriver`) used for validation. The framework is a Linux-driver-
style registry plus two tick-boundary schedulers: a NAPI-style bounded fair inbound drain
that maps transport packets into `RawSignal` values (carrying the transport-intrinsic QoS
marker under the reserved metadata key), and a bounded outbound dispatch that respects
planner-provided execution priority. The framework holds no cognitive policy: it never
normalizes, scores salience, re-selects channels, or shapes content. The first real driver
is requirement `31`; this fake driver exists only for tests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Mapping

from helios_v2.sensory.contracts import RawSignal

from .contracts import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelConfigSnapshot,
    ChannelDriver,
    ChannelDriverDescriptor,
    ChannelDriverReadiness,
    ChannelDriverStatus,
    ChannelDriverStatusReport,
    ChannelError,
    ChannelManagementResult,
    ChannelQosClass,
    ChannelReadinessReport,
    ChannelStateSnapshot,
    ChannelSubsystemAPI,
    InboundDrainResult,
    InboundPacket,
    OutboundDispatchOutcome,
    OutboundPacket,
    SubsystemDispatchResult,
    SubsystemDrainResult,
)


def _raw_signal_from_packet(packet: InboundPacket) -> RawSignal:
    """Owner: channel driver subsystem.

    Map one inbound transport packet to a `RawSignal`, carrying the transport-intrinsic
    QoS class under the reserved metadata key. The framework does not normalize; it only
    transports the QoS marker forward for `02` sensory to preserve and `03` appraisal to
    interpret.
    """

    metadata = dict(packet.metadata)
    metadata[CHANNEL_QOS_METADATA_KEY] = packet.qos_class
    return RawSignal(
        signal_id=packet.packet_id,
        source_name=packet.driver_id,
        signal_type=packet.packet_type,
        content=packet.content,
        channel=packet.driver_id,
        metadata=metadata,
        required=False,
    )


@dataclass
class ChannelSubsystem(ChannelSubsystemAPI):
    """Owner: channel driver subsystem.

    Purpose:
        Own a runtime-pluggable driver registry plus two tick-boundary schedulers. Drivers
        receive asynchronously into their own bounded backlogs; the framework drains them
        fairly under a global budget at the tick boundary and dispatches planner-accepted
        decisions under a separate budget.

    Failure semantics:
        Raises `ChannelError` on a duplicate registration, an unknown driver for a routed
        op, a negative budget, or a malformed driver-supplied contract. Expected operational
        outcomes (driver unavailable on dispatch, overflow) are reported as structured
        results, not raised.

    Notes:
        Drain fairness is deterministic round-robin over the ready set in registration
        order. Outbound dispatch order is deterministic: higher execution priority first,
        ties broken by submission order.
    """

    _drivers: dict[str, ChannelDriver] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    _drain_cursor: int = field(default=0, init=False, repr=False)

    def register_driver(self, driver: ChannelDriver) -> ChannelManagementResult:
        """Owner: channel driver subsystem.

        Purpose:
            Register one driver at runtime, making its descriptor/status discoverable and
            its backlog drainable.

        Inputs:
            `driver` - a `ChannelDriver` with a stable unique `driver_id`.

        Returns:
            A successful `ChannelManagementResult` for the register op.

        Raises:
            ChannelError on an empty driver id or a duplicate registration.
        """

        driver_id = driver.driver_id
        if not driver_id:
            raise ChannelError("Cannot register a driver with an empty driver_id")
        if driver_id in self._drivers:
            raise ChannelError(f"Duplicate channel driver registration: '{driver_id}'")
        self._drivers[driver_id] = driver
        self._order.append(driver_id)
        status = driver.status()
        return ChannelManagementResult(
            driver_id=driver_id,
            op_name="register_driver",
            success=True,
            status=status.status,
            message=f"driver '{driver_id}' registered",
        )

    def deregister_driver(self, driver_id: str) -> ChannelManagementResult:
        """Owner: channel driver subsystem.

        Purpose:
            Tear down then remove one registered driver.

        Inputs:
            `driver_id` - the id of a registered driver.

        Returns:
            A `ChannelManagementResult` for the deregister op; the driver's own teardown op
            result is folded into the payload.

        Raises:
            ChannelError when no driver is registered under `driver_id`.

        Notes:
            Teardown is attempted before removal so a driver can release resources. Removal
            proceeds even if teardown reports a non-fatal failure, but the failure is
            surfaced in the returned result.
        """

        driver = self._require_driver(driver_id)
        teardown = driver.apply_management_op("teardown", None)
        self._drivers.pop(driver_id)
        self._order.remove(driver_id)
        return ChannelManagementResult(
            driver_id=driver_id,
            op_name="deregister_driver",
            success=teardown.success,
            status="disconnected",
            message=f"driver '{driver_id}' deregistered",
            error_code=None if teardown.success else teardown.error_code,
            payload={"teardown_status": teardown.status, "teardown_message": teardown.message},
        )

    def apply_management_op(
        self,
        driver_id: str,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        """Owner: channel driver subsystem.

        Purpose:
            Route one management op to the named registered driver.

        Inputs:
            `driver_id` - a registered driver id.
            `op_name` - the management op name to apply.
            `payload` - optional op payload.

        Returns:
            The driver's structured `ChannelManagementResult`.

        Raises:
            ChannelError when no driver is registered under `driver_id` or `op_name` is empty.
        """

        if not op_name:
            raise ChannelError("apply_management_op requires a non-empty op_name")
        driver = self._require_driver(driver_id)
        return driver.apply_management_op(op_name, payload)

    def drain_inbound(self, budget: int) -> SubsystemDrainResult:
        """Owner: channel driver subsystem.

        Purpose:
            Run one NAPI-style bounded fair drain across drivers reporting pending packets,
            mapping each drained packet to a `RawSignal` with the QoS marker preserved.

        Inputs:
            `budget` - the maximum total number of packets to drain this tick (>= 0).

        Returns:
            A `SubsystemDrainResult` with the mapped raw signals, the total pending remainder
            still queued across drivers, the drained count, and per-driver overflow counts.

        Raises:
            ChannelError on a negative budget or a malformed driver drain result.

        Notes:
            The ready set is iterated round-robin starting from a persisted cursor so no
            driver is starved across ticks. A driver returning fewer than its requested
            budget is considered exhausted for this drain; remainder stays pending and is
            picked up next tick.
        """

        if budget < 0:
            raise ChannelError("drain_inbound budget must be >= 0")
        raw_signals: list[RawSignal] = []
        overflow_counts: dict[str, int] = {}
        drained_count = 0
        remaining_budget = budget

        ordered_ids = self._rotated_order()
        if budget > 0:
            for driver_id in ordered_ids:
                if remaining_budget <= 0:
                    break
                driver = self._drivers[driver_id]
                if driver.status().pending_inbound <= 0:
                    continue
                result = driver.drain_inbound(remaining_budget)
                self._validate_drain_result(driver_id, result, remaining_budget)
                for packet in result.packets:
                    raw_signals.append(_raw_signal_from_packet(packet))
                drained_count += len(result.packets)
                remaining_budget -= len(result.packets)
                if result.overflow_count:
                    overflow_counts[driver_id] = result.overflow_count
                # advance the cursor past this driver so the next tick starts fairly
                self._drain_cursor = (self._order.index(driver_id) + 1) % max(len(self._order), 1)

        pending_remaining = sum(
            self._drivers[driver_id].status().pending_inbound for driver_id in self._order
        )
        return SubsystemDrainResult(
            raw_signals=tuple(raw_signals),
            pending_remaining=pending_remaining,
            drained_count=drained_count,
            overflow_counts=overflow_counts,
        )

    def dispatch_outbound(
        self,
        decisions: tuple[OutboundPacket, ...],
        budget: int,
    ) -> SubsystemDispatchResult:
        """Owner: channel driver subsystem.

        Purpose:
            Dispatch outbound packets to their target drivers under a budget, honoring the
            planner-provided execution priority, and publish explicit per-packet outcomes.

        Inputs:
            `decisions` - the planner-accepted outbound packets to dispatch.
            `budget` - the maximum number of packets to dispatch this tick (>= 0).

        Returns:
            A `SubsystemDispatchResult` with one outcome per attempted packet, the dispatched
            count, and the count deferred to the next tick.

        Raises:
            ChannelError on a negative budget.

        Notes:
            The framework never re-selects the channel; it sends to `target_driver_id`. An
            unknown or unavailable driver yields an explicit `driver_unavailable` outcome.
            Packets beyond the budget are deferred (not dropped) and reported in
            `deferred_count`.
        """

        if budget < 0:
            raise ChannelError("dispatch_outbound budget must be >= 0")
        ordered = sorted(
            enumerate(decisions),
            key=lambda item: (-item[1].execution_priority, item[0]),
        )
        outcomes: list[OutboundDispatchOutcome] = []
        dispatched_count = 0
        deferred_count = 0
        for position, (_, packet) in enumerate(ordered):
            if position >= budget:
                deferred_count += 1
                continue
            driver = self._drivers.get(packet.target_driver_id)
            if driver is None:
                outcomes.append(
                    OutboundDispatchOutcome(
                        packet_id=packet.packet_id,
                        target_driver_id=packet.target_driver_id,
                        status="driver_unavailable",
                        detail=f"no driver registered as '{packet.target_driver_id}'",
                    )
                )
                continue
            outcome = driver.send_outbound(packet)
            if not isinstance(outcome, OutboundDispatchOutcome):
                raise ChannelError("Driver send_outbound must return an OutboundDispatchOutcome")
            outcomes.append(outcome)
            dispatched_count += 1
        return SubsystemDispatchResult(
            outcomes=tuple(outcomes),
            dispatched_count=dispatched_count,
            deferred_count=deferred_count,
        )

    def channel_state_snapshot(self) -> ChannelStateSnapshot:
        """Owner: channel driver subsystem.

        Purpose:
            Return the real per-driver descriptor/status snapshot for the planner to consume
            instead of the hardcoded channel-state shim.

        Returns:
            A `ChannelStateSnapshot` carrying every registered driver's descriptor and status.

        Notes:
            This carries transport facts only; it never recommends a channel selection.
        """

        descriptors = tuple(self._drivers[driver_id].descriptor() for driver_id in self._order)
        statuses = tuple(self._drivers[driver_id].status() for driver_id in self._order)
        return ChannelStateSnapshot(descriptors=descriptors, statuses=statuses)

    def descriptors(self) -> tuple[ChannelDriverDescriptor, ...]:
        """Owner: channel driver subsystem.

        Purpose:
            Return every registered driver's descriptor in registration order.
        """

        return tuple(self._drivers[driver_id].descriptor() for driver_id in self._order)

    def statuses(self) -> tuple[ChannelDriverStatusReport, ...]:
        """Owner: channel driver subsystem.

        Purpose:
            Return every registered driver's status report in registration order.
        """

        return tuple(self._drivers[driver_id].status() for driver_id in self._order)

    def check_static_readiness(self, driver_ids: tuple[str, ...]) -> ChannelReadinessReport:
        """Owner: channel driver subsystem.

        Purpose:
            Report, for each requested driver, whether it is registered and reports a
            network-free static readiness.

        Inputs:
            `driver_ids` - the driver ids whose static readiness gates startup.

        Returns:
            A deterministic `ChannelReadinessReport`. An unknown driver is reported not-ready
            rather than raising.

        Notes:
            This performs no network call; it only consults each driver's declared
            credential/resource presence.
        """

        entries = []
        for driver_id in driver_ids:
            driver = self._drivers.get(driver_id)
            if driver is None:
                entries.append(
                    ChannelDriverReadiness(
                        driver_id=driver_id,
                        ready=False,
                        detail="driver is not registered",
                    )
                )
                continue
            readiness = driver.static_readiness()
            if not isinstance(readiness, ChannelDriverReadiness):
                raise ChannelError("Driver static_readiness must return a ChannelDriverReadiness")
            entries.append(readiness)
        return ChannelReadinessReport(
            report_id=f"channel-static-readiness:{'+'.join(driver_ids) or 'none'}",
            entries=tuple(entries),
        )

    def _require_driver(self, driver_id: str) -> ChannelDriver:
        driver = self._drivers.get(driver_id)
        if driver is None:
            raise ChannelError(f"No channel driver registered as '{driver_id}'")
        return driver

    def _rotated_order(self) -> list[str]:
        if not self._order:
            return []
        cursor = self._drain_cursor % len(self._order)
        return self._order[cursor:] + self._order[:cursor]

    @staticmethod
    def _validate_drain_result(
        driver_id: str,
        result: InboundDrainResult,
        requested_budget: int,
    ) -> None:
        if not isinstance(result, InboundDrainResult):
            raise ChannelError("Driver drain_inbound must return an InboundDrainResult")
        if result.driver_id != driver_id:
            raise ChannelError("Driver drain_inbound returned a result for a different driver")
        if len(result.packets) > requested_budget:
            raise ChannelError("Driver drain_inbound returned more packets than the budget allowed")


@dataclass
class InMemoryChannelDriver(ChannelDriver):
    """Owner: channel driver subsystem (deterministic test driver).

    Purpose:
        A deterministic, network-free driver for validating the framework. It models an
        async-received backlog with an explicit `enqueue_inbound`, a bounded backlog with a
        counted overflow policy, a status that follows simple lifecycle ops, an outbound
        sink that records sent packets, and a static readiness derived from a declared
        credential field.

    Failure semantics:
        Construction raises `ChannelError` via the descriptor on invalid fields. Backlog
        overflow is bounded and counted, never raised.

    Notes:
        This driver is for tests only; the first real driver is requirement `31`. It derives
        the QoS class from the packet type alone (a transport-visible fact), never by reading
        content for meaning.
    """

    _descriptor: ChannelDriverDescriptor
    backlog_capacity: int = 16
    credential_present: bool = True
    _status: ChannelDriverStatus = field(default="uninitialized", init=False)
    _backlog: deque[InboundPacket] = field(default_factory=deque, init=False)
    _overflow_count: int = field(default=0, init=False)
    _sent: list[OutboundPacket] = field(default_factory=list, init=False)
    _send_should_fail: bool = field(default=False, init=False)

    @property
    def driver_id(self) -> str:
        return self._descriptor.driver_id

    @property
    def sent_packets(self) -> tuple[OutboundPacket, ...]:
        """Owner: channel driver subsystem (test driver).

        Purpose:
            Expose the packets this driver has sent, for test assertions.
        """

        return tuple(self._sent)

    def enqueue_inbound(
        self,
        packet_id: str,
        packet_type: str,
        content: str,
        qos_class: ChannelQosClass = "interactive",
        metadata: Mapping[str, object] | None = None,
    ) -> bool:
        """Owner: channel driver subsystem (test driver).

        Purpose:
            Simulate one asynchronously-received packet entering the bounded backlog.

        Returns:
            True when the packet was accepted; False when the backlog was full and the
            overflow policy dropped it (the overflow counter is incremented).
        """

        if len(self._backlog) >= self.backlog_capacity:
            self._overflow_count += 1
            return False
        self._backlog.append(
            InboundPacket(
                packet_id=packet_id,
                driver_id=self.driver_id,
                packet_type=packet_type,
                content=content,
                qos_class=qos_class,
                metadata=dict(metadata or {}),
            )
        )
        return True

    def set_send_failure(self, should_fail: bool) -> None:
        """Owner: channel driver subsystem (test driver).

        Purpose:
            Toggle whether `send_outbound` reports a failed delivery, for test coverage.
        """

        self._send_should_fail = should_fail

    def descriptor(self) -> ChannelDriverDescriptor:
        return self._descriptor

    def apply_management_op(
        self,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        transitions = {
            "connect": "connected",
            "disconnect": "disconnected",
            "pause": "paused",
            "teardown": "disconnected",
        }
        if op_name not in transitions:
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=False,
                status=self._status,
                message=f"unsupported management op '{op_name}'",
                error_code="unsupported_op",
            )
        self._status = transitions[op_name]
        return ChannelManagementResult(
            driver_id=self.driver_id,
            op_name=op_name,
            success=True,
            status=self._status,
            message=f"applied '{op_name}'",
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
            config_values={"backlog_capacity": self.backlog_capacity},
            mutable_fields=("backlog_capacity",),
        )

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        if budget < 0:
            raise ChannelError("InMemoryChannelDriver drain budget must be >= 0")
        drained: list[InboundPacket] = []
        while self._backlog and len(drained) < budget:
            drained.append(self._backlog.popleft())
        overflow = self._overflow_count
        self._overflow_count = 0
        return InboundDrainResult(
            driver_id=self.driver_id,
            packets=tuple(drained),
            pending_remaining=len(self._backlog),
            overflow_count=overflow,
        )

    def send_outbound(self, packet: OutboundPacket) -> OutboundDispatchOutcome:
        if self._send_should_fail:
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail="test driver configured to fail delivery",
            )
        self._sent.append(packet)
        return OutboundDispatchOutcome(
            packet_id=packet.packet_id,
            target_driver_id=self.driver_id,
            status="delivered",
            detail=f"delivered op '{packet.op_name}'",
        )

    def static_readiness(self) -> ChannelDriverReadiness:
        if self.credential_present:
            return ChannelDriverReadiness(
                driver_id=self.driver_id,
                ready=True,
                detail="declared credential present",
            )
        return ChannelDriverReadiness(
            driver_id=self.driver_id,
            ready=False,
            detail="declared credential missing",
        )
