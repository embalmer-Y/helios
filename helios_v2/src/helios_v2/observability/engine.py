"""Owner: unified runtime observability and logging.

Provides the runtime observability recorder plus first-version sinks.
The recorder is the only component that assigns sequence numbers and event ids.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol, TextIO, runtime_checkable

from .contracts import (
    ExecutionTimelineStageEntry,
    ExecutionTimelineView,
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


@dataclass
class ExecutionTimelineReconstructor:
    """Owner: observability.

    Purpose:
        Reconstruct one tick's execution timeline view from already-captured kernel
        lifecycle events. This keeps the log-to-structured-fact transformation inside the
        observability owner, so downstream owners consume the formal `ExecutionTimelineView`
        rather than parsing raw `LogEvent` objects.

    Failure semantics:
        Derives the view only from kernel execution-timing facts (stage order, lifecycle,
        duration). A tick with no observed lifecycle events yields an explicitly incomplete
        view rather than a fabricated one. A malformed pairing (a completed or failed stage
        with no matching started stage, or a duplicated completed/failed stage) raises
        `ObservabilityError`.
    """

    def reconstruct(self, events: tuple[LogEvent, ...], tick_id: int) -> ExecutionTimelineView:
        """Owner: observability.

        Purpose:
            Build the immutable `ExecutionTimelineView` for one tick.

        Inputs:
            `events` - the captured event stream (for example `InMemoryLogSink.events`).
            `tick_id` - the positive tick id whose timeline is being reconstructed.

        Returns:
            An `ExecutionTimelineView`. When no lifecycle events exist for the tick, the
            view is explicitly incomplete (`stages=()`, `completed=False`).

        Raises:
            ObservabilityError on a non-positive tick id or a malformed lifecycle pairing.

        Notes:
            Only `stage_started`, `stage_completed`, `stage_failed`, and
            `runtime_tick_completed` events for the given tick are consulted, and only their
            timing facts are read. Owner decision payloads are never interpreted.
        """

        if not isinstance(tick_id, int) or tick_id <= 0:
            raise ObservabilityError("ExecutionTimelineReconstructor requires a positive tick_id")

        started_stage_names: set[str] = set()
        tick_completed = False
        ordered_entries: list[ExecutionTimelineStageEntry] = []
        seen_terminal_stage_names: set[str] = set()

        for event in events:
            if event.tick_id != tick_id:
                continue
            if event.event_kind == "runtime_tick_completed":
                tick_completed = True
                continue
            if event.event_kind == "stage_started":
                if event.stage_name:
                    started_stage_names.add(event.stage_name)
                continue
            if event.event_kind in ("stage_completed", "stage_failed"):
                stage_name = event.stage_name
                if not stage_name:
                    raise ObservabilityError(
                        "Timeline reconstruction found a stage lifecycle event without a stage_name"
                    )
                if stage_name not in started_stage_names:
                    raise ObservabilityError(
                        f"Timeline reconstruction found a terminal event for unstarted stage '{stage_name}'"
                    )
                if stage_name in seen_terminal_stage_names:
                    raise ObservabilityError(
                        f"Timeline reconstruction found a duplicate terminal event for stage '{stage_name}'"
                    )
                seen_terminal_stage_names.add(stage_name)
                payload = event.payload
                stage_index = payload.get("stage_index")
                if not isinstance(stage_index, int):
                    raise ObservabilityError(
                        "Timeline reconstruction requires an integer stage_index in the stage payload"
                    )
                duration_value = payload.get("duration_ms")
                duration_ms = float(duration_value) if isinstance(duration_value, (int, float)) else 0.0
                if event.event_kind == "stage_completed":
                    ordered_entries.append(
                        ExecutionTimelineStageEntry(
                            stage_name=stage_name,
                            stage_index=stage_index,
                            status="completed",
                            duration_ms=duration_ms,
                        )
                    )
                else:
                    error_type = payload.get("error_type")
                    ordered_entries.append(
                        ExecutionTimelineStageEntry(
                            stage_name=stage_name,
                            stage_index=stage_index,
                            status="failed",
                            duration_ms=duration_ms,
                            error_type=str(error_type) if error_type else "UnknownError",
                        )
                    )

        ordered_entries.sort(key=lambda entry: entry.stage_index)
        normalized_entries = tuple(
            ExecutionTimelineStageEntry(
                stage_name=entry.stage_name,
                stage_index=position,
                status=entry.status,
                duration_ms=entry.duration_ms,
                error_type=entry.error_type,
            )
            for position, entry in enumerate(ordered_entries)
        )
        return ExecutionTimelineView(
            tick_id=tick_id,
            stages=normalized_entries,
            completed=tick_completed,
            stage_count=len(normalized_entries),
        )
