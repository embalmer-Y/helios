"""Owner: unified runtime observability and logging.

Provides the runtime observability recorder plus first-version sinks.
The recorder is the only component that assigns sequence numbers and event ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol, TextIO, runtime_checkable

from .contracts import (
    LogEvent,
    LogEventKind,
    LogSeverity,
    LogSink,
    ObservabilityError,
    severity_rank,
)


@dataclass
class InMemoryLogSink(LogSink):
    """In-memory sink that captures dispatched events in order for inspection.

    Owner: observability.

    Failure semantics:
        Never drops events. Capture is append-only and order-preserving.
    """

    _events: list[LogEvent] = field(default_factory=list)

    def emit(self, event: LogEvent) -> None:
        """Owner: observability.

        Purpose:
            Append one event to the in-memory capture buffer.

        Inputs:
            `event` - one recorder-stamped `LogEvent`.

        Returns:
            None.

        Raises:
            None.
        """

        self._events.append(event)

    @property
    def events(self) -> tuple[LogEvent, ...]:
        """Owner: observability.

        Purpose:
            Return a read-only snapshot of captured events in dispatch order.

        Inputs:
            None.

        Returns:
            An immutable tuple of captured `LogEvent` objects.

        Raises:
            None.
        """

        return tuple(self._events)


@dataclass
class JsonLineStreamLogSink(LogSink):
    """Stream sink that serializes each event as one JSON line.

    Owner: observability.

    Failure semantics:
        Stream write failures propagate to the recorder caller.
    """

    stream: TextIO

    def emit(self, event: LogEvent) -> None:
        """Owner: observability.

        Purpose:
            Write one event as a single JSON line followed by a newline.

        Inputs:
            `event` - one recorder-stamped `LogEvent`.

        Returns:
            None.

        Raises:
            Any error raised by the underlying stream write or flush.

        Notes:
            One event maps to exactly one newline-terminated JSON document.
        """

        self.stream.write(json.dumps(event.to_record(), ensure_ascii=False))
        self.stream.write("\n")
        self.stream.flush()


@runtime_checkable
class RuntimeObservabilityAPI(Protocol):
    """Public API for the runtime observability recorder.

    Owner: observability.
    """

    def record(
        self,
        *,
        severity: LogSeverity,
        event_kind: LogEventKind,
        owner: str,
        message: str,
        tick_id: int | None = None,
        stage_name: str | None = None,
        provenance_refs: tuple[str, ...] = (),
        payload: Mapping[str, object] | None = None,
    ) -> LogEvent:
        """Stamp, build, optionally dispatch, and return one structured log event."""

        ...


@dataclass
class RuntimeObservabilityRecorder(RuntimeObservabilityAPI):
    """Owner: observability.

    Purpose:
        Stamp each event with a strictly monotonic sequence and stable id, then
        dispatch events at or above the minimum severity to all configured sinks.

    Failure semantics:
        Construction raises `ObservabilityError` when no sink is configured.
        Sink dispatch failures propagate; the recorder never swallows them.
    """

    sinks: tuple[LogSink, ...]
    minimum_severity: LogSeverity = "info"
    _sequence: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.sinks:
            raise ObservabilityError(
                "RuntimeObservabilityRecorder requires at least one configured sink"
            )
        # Validate the threshold against the fixed taxonomy at construction time.
        self._minimum_rank = severity_rank(self.minimum_severity)

    def record(
        self,
        *,
        severity: LogSeverity,
        event_kind: LogEventKind,
        owner: str,
        message: str,
        tick_id: int | None = None,
        stage_name: str | None = None,
        provenance_refs: tuple[str, ...] = (),
        payload: Mapping[str, object] | None = None,
    ) -> LogEvent:
        """Owner: observability.

        Purpose:
            Build one immutable event, dispatch it when it meets the severity
            threshold, and return it regardless of threshold for caller inspection.

        Inputs:
            Keyword-only event fields. `severity` and `event_kind` must be in the
            fixed taxonomies. `owner` and `message` must be non-empty.

        Returns:
            The stamped immutable `LogEvent`.

        Raises:
            ObservabilityError on invalid event fields.
            Any sink error during dispatch propagates unchanged.

        Notes:
            The sequence counter advances for every recorded event, including
            events below the dispatch threshold, so ordering identity is stable.
        """

        self._sequence += 1
        event = LogEvent(
            event_id=f"log-event:{self._sequence}",
            sequence=self._sequence,
            severity=severity,
            event_kind=event_kind,
            owner=owner,
            message=message,
            tick_id=tick_id,
            stage_name=stage_name,
            provenance_refs=provenance_refs,
            payload=payload or {},
        )
        if severity_rank(severity) >= self._minimum_rank:
            for sink in self.sinks:
                sink.emit(event)
        return event
