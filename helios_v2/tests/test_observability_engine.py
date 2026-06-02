from __future__ import annotations

import io
import json

import pytest

from helios_v2.observability import (
    InMemoryLogSink,
    JsonLineStreamLogSink,
    LogEvent,
    ObservabilityError,
    RuntimeObservabilityRecorder,
)


def _recorder(minimum_severity: str = "info") -> tuple[RuntimeObservabilityRecorder, InMemoryLogSink]:
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity=minimum_severity)
    return recorder, sink


def test_recorder_requires_at_least_one_sink():
    with pytest.raises(ObservabilityError):
        RuntimeObservabilityRecorder(sinks=())


def test_recorder_rejects_unknown_minimum_severity():
    with pytest.raises(ObservabilityError):
        RuntimeObservabilityRecorder(sinks=(InMemoryLogSink(),), minimum_severity="trace")


def test_recorder_assigns_monotonic_sequence_and_stable_ids():
    recorder, sink = _recorder()
    first = recorder.record(
        severity="info",
        event_kind="owner_emission",
        owner="runtime_kernel",
        message="first",
    )
    second = recorder.record(
        severity="info",
        event_kind="owner_emission",
        owner="runtime_kernel",
        message="second",
    )
    assert (first.sequence, second.sequence) == (1, 2)
    assert (first.event_id, second.event_id) == ("log-event:1", "log-event:2")
    assert [event.sequence for event in sink.events] == [1, 2]


def test_recorder_filters_below_threshold_but_still_advances_sequence():
    recorder, sink = _recorder(minimum_severity="warning")
    below = recorder.record(
        severity="info",
        event_kind="owner_emission",
        owner="runtime_kernel",
        message="below threshold",
    )
    above = recorder.record(
        severity="error",
        event_kind="stage_failed",
        owner="runtime_kernel",
        message="above threshold",
    )
    # The below-threshold event is built and returned, but not dispatched.
    assert below.sequence == 1
    assert above.sequence == 2
    assert [event.sequence for event in sink.events] == [2]


def test_in_memory_sink_preserves_dispatch_order():
    recorder, sink = _recorder()
    for index in range(3):
        recorder.record(
            severity="info",
            event_kind="owner_emission",
            owner="runtime_kernel",
            message=f"event {index}",
        )
    assert [event.message for event in sink.events] == ["event 0", "event 1", "event 2"]


def test_json_line_stream_sink_emits_parseable_lines():
    stream = io.StringIO()
    recorder = RuntimeObservabilityRecorder(sinks=(JsonLineStreamLogSink(stream=stream),))
    recorder.record(
        severity="info",
        event_kind="runtime_startup",
        owner="runtime_kernel",
        message="startup",
        payload={"stage_count": 2},
    )
    recorder.record(
        severity="info",
        event_kind="runtime_tick_completed",
        owner="runtime_kernel",
        message="tick done",
        tick_id=1,
    )
    lines = [line for line in stream.getvalue().splitlines() if line]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event_kind"] == "runtime_startup"
    assert first["payload"] == {"stage_count": 2}
    assert second["event_kind"] == "runtime_tick_completed"
    assert second["tick_id"] == 1


class _FailingSink:
    def emit(self, event: LogEvent) -> None:
        raise RuntimeError("sink transport failed")


def test_sink_failure_propagates():
    recorder = RuntimeObservabilityRecorder(sinks=(_FailingSink(),))
    with pytest.raises(RuntimeError, match="sink transport failed"):
        recorder.record(
            severity="info",
            event_kind="owner_emission",
            owner="runtime_kernel",
            message="will fail",
        )
