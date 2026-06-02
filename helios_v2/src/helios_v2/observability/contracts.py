"""Owner: unified runtime observability and logging.

Owns:
- structured runtime log-event contract
- severity and event-kind taxonomies
- the log-sink protocol boundary

Does not own:
- any cognitive runtime decision or state
- planner authority, channel execution, or governance judgment
- authoritative inter-owner state transport
- storage or persistence policy beyond the sink dispatch boundary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable


class ObservabilityError(RuntimeError):
    """Hard-stop error raised when observability owner invariants fail."""


LogSeverity = Literal["debug", "info", "notice", "warning", "error", "critical"]
LogEventKind = Literal[
    "runtime_startup",
    "runtime_startup_failed",
    "stage_started",
    "stage_completed",
    "stage_failed",
    "runtime_tick_completed",
    "owner_emission",
]

# Monotonic severity ranks used for threshold comparison. Lower rank is less severe.
_SEVERITY_RANKS: Mapping[str, int] = MappingProxyType(
    {
        "debug": 10,
        "info": 20,
        "notice": 25,
        "warning": 30,
        "error": 40,
        "critical": 50,
    }
)

_EVENT_KINDS = frozenset(
    {
        "runtime_startup",
        "runtime_startup_failed",
        "stage_started",
        "stage_completed",
        "stage_failed",
        "runtime_tick_completed",
        "owner_emission",
    }
)


def severity_rank(severity: str) -> int:
    """Owner: observability.

    Purpose:
        Return the monotonic integer rank for one severity label.

    Inputs:
        `severity` - a severity label expected to be in the fixed taxonomy.

    Returns:
        The integer rank used for minimum-severity threshold comparison.

    Raises:
        ObservabilityError if the severity label is not in the fixed taxonomy.

    Notes:
        Higher rank means more severe.
    """

    rank = _SEVERITY_RANKS.get(severity)
    if rank is None:
        raise ObservabilityError(f"Unknown log severity: {severity!r}")
    return rank


def _freeze_payload(payload: Mapping[str, object] | None) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(payload or {}))
    for key in frozen:
        if not isinstance(key, str) or not key:
            raise ObservabilityError("LogEvent payload keys must be non-empty strings")
    return frozen


@dataclass(frozen=True)
class LogEvent:
    """Immutable structured runtime log event stamped by the observability recorder.

    Owner: observability.

    Failure semantics:
        Construction raises `ObservabilityError` on empty owner, empty message,
        unknown severity, unknown event kind, negative sequence, or invalid payload keys.
    """

    event_id: str
    sequence: int
    severity: LogSeverity
    event_kind: LogEventKind
    owner: str
    message: str
    tick_id: int | None = None
    stage_name: str | None = None
    provenance_refs: tuple[str, ...] = ()
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ObservabilityError("LogEvent must declare a non-empty event_id")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ObservabilityError("LogEvent sequence must be a non-negative integer")
        # severity_rank validates the severity taxonomy.
        severity_rank(self.severity)
        if self.event_kind not in _EVENT_KINDS:
            raise ObservabilityError(f"Unknown log event kind: {self.event_kind!r}")
        if not self.owner:
            raise ObservabilityError("LogEvent must declare a non-empty owner")
        if not self.message:
            raise ObservabilityError("LogEvent must declare a non-empty message")
        if any(not ref for ref in self.provenance_refs):
            raise ObservabilityError("LogEvent provenance_refs must not contain empty values")
        object.__setattr__(self, "payload", _freeze_payload(self.payload))

    def to_record(self) -> dict[str, object]:
        """Owner: observability.

        Purpose:
            Return a JSON-serializable dict snapshot of this event for stream sinks.

        Inputs:
            None.

        Returns:
            A plain dict with stable keys mirroring the event fields.

        Raises:
            None.

        Notes:
            The returned dict is a copy; mutating it does not affect the event.
        """

        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "severity": self.severity,
            "event_kind": self.event_kind,
            "owner": self.owner,
            "message": self.message,
            "tick_id": self.tick_id,
            "stage_name": self.stage_name,
            "provenance_refs": list(self.provenance_refs),
            "payload": dict(self.payload),
        }


@runtime_checkable
class LogSink(Protocol):
    """Public sink boundary consumed by the observability recorder.

    Owner: observability.
    """

    def emit(self, event: LogEvent) -> None:
        """Owner: observability.

        Purpose:
            Accept one finished, recorder-stamped log event for delivery.

        Inputs:
            `event` - one immutable `LogEvent` already assigned a sequence and id.

        Returns:
            None.

        Raises:
            Any sink-specific error. The recorder lets such errors propagate.

        Notes:
            Sinks must not mutate the event.
        """

        ...
