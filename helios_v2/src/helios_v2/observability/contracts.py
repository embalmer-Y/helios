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


ExecutionTimelineStageStatus = Literal["completed", "failed"]

_TIMELINE_STAGE_STATUSES = frozenset({"completed", "failed"})


@dataclass(frozen=True)
class ExecutionTimelineStageEntry:
    """Immutable per-stage execution fact for one reconstructed tick.

    Owner: observability.

    This entry carries only kernel execution-timing facts (stage order, lifecycle
    status, duration). It never carries an owner's semantic decision. It is derived by
    the timeline reconstructor from already-captured kernel lifecycle events.

    Failure semantics:
        Construction raises `ObservabilityError` on empty stage name, negative stage
        index, negative duration, an unknown status, or a failed entry without an
        `error_type`.
    """

    stage_name: str
    stage_index: int
    status: ExecutionTimelineStageStatus
    duration_ms: float
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not self.stage_name:
            raise ObservabilityError("ExecutionTimelineStageEntry must declare a non-empty stage_name")
        if not isinstance(self.stage_index, int) or self.stage_index < 0:
            raise ObservabilityError("ExecutionTimelineStageEntry stage_index must be a non-negative integer")
        if self.status not in _TIMELINE_STAGE_STATUSES:
            raise ObservabilityError(f"Unknown timeline stage status: {self.status!r}")
        if self.duration_ms < 0:
            raise ObservabilityError("ExecutionTimelineStageEntry duration_ms must be non-negative")
        if self.status == "failed" and not self.error_type:
            raise ObservabilityError("A failed ExecutionTimelineStageEntry must declare an error_type")
        if self.status == "completed" and self.error_type is not None:
            raise ObservabilityError("A completed ExecutionTimelineStageEntry must not declare an error_type")


@dataclass(frozen=True)
class ExecutionTimelineView:
    """Immutable read-only reconstruction of one tick's kernel execution timeline.

    Owner: observability.

    This view is the only sanctioned form in which downstream owners may consume kernel
    execution-timing facts. Downstream owners must not parse raw `LogEvent` objects to
    obtain timing facts, and this view never transports any owner's semantic decision.

    Failure semantics:
        Construction raises `ObservabilityError` on a non-positive tick id, a
        `stage_count` that disagrees with the number of stage entries, or stage indices
        that are not strictly increasing from zero.
    """

    tick_id: int
    stages: tuple[ExecutionTimelineStageEntry, ...]
    completed: bool
    stage_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.tick_id, int) or self.tick_id <= 0:
            raise ObservabilityError("ExecutionTimelineView tick_id must be a positive integer")
        if self.stage_count != len(self.stages):
            raise ObservabilityError("ExecutionTimelineView stage_count must equal the number of stage entries")
        for expected_index, stage in enumerate(self.stages):
            if stage.stage_index != expected_index:
                raise ObservabilityError(
                    "ExecutionTimelineView stage indices must be strictly increasing from zero"
                )

    def to_evidence(self, evidence_id: str) -> dict[str, object]:
        """Owner: observability.

        Purpose:
            Return a compact, JSON-friendly projection of this timeline view for
            downstream read-only evidence consumption (for example by the evaluation owner).

        Inputs:
            `evidence_id` - a non-empty stable id the consumer assigns to this evidence.

        Returns:
            A plain dict carrying `evidence_id`, `tick_id`, `completed`, `stage_count`,
            and a compact per-stage status list. The dict is a copy and does not alias
            view state.

        Raises:
            ObservabilityError if `evidence_id` is empty.

        Notes:
            The projection includes only execution-timing facts, never owner decisions.
        """

        if not evidence_id:
            raise ObservabilityError("ExecutionTimelineView.to_evidence requires a non-empty evidence_id")
        return {
            "evidence_id": evidence_id,
            "tick_id": self.tick_id,
            "completed": self.completed,
            "stage_count": self.stage_count,
            "stages": [
                {
                    "stage_name": stage.stage_name,
                    "stage_index": stage.stage_index,
                    "status": stage.status,
                    "duration_ms": stage.duration_ms,
                    "error_type": stage.error_type,
                }
                for stage in self.stages
            ],
        }
