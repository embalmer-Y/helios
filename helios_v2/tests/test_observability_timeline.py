from __future__ import annotations

import pytest

from helios_v2.observability import (
    ExecutionTimelineReconstructor,
    ExecutionTimelineStageEntry,
    ExecutionTimelineView,
    LogEvent,
    ObservabilityError,
)


def _event(
    sequence: int,
    event_kind: str,
    *,
    tick_id: int | None = None,
    stage_name: str | None = None,
    payload: dict | None = None,
    severity: str = "info",
) -> LogEvent:
    return LogEvent(
        event_id=f"log-event:{sequence}",
        sequence=sequence,
        severity=severity,
        event_kind=event_kind,
        owner="runtime_kernel",
        message=f"{event_kind} {stage_name or ''}".strip(),
        tick_id=tick_id,
        stage_name=stage_name,
        payload=payload or {},
    )


def _stage_lifecycle(
    start_seq: int,
    tick_id: int,
    stage_name: str,
    stage_index: int,
    *,
    failed: bool = False,
) -> list[LogEvent]:
    started = _event(
        start_seq,
        "stage_started",
        tick_id=tick_id,
        stage_name=stage_name,
        severity="debug",
        payload={"stage_index": stage_index},
    )
    if failed:
        terminal = _event(
            start_seq + 1,
            "stage_failed",
            tick_id=tick_id,
            stage_name=stage_name,
            severity="error",
            payload={"stage_index": stage_index, "duration_ms": 1.5, "error_type": "ValueError"},
        )
    else:
        terminal = _event(
            start_seq + 1,
            "stage_completed",
            tick_id=tick_id,
            stage_name=stage_name,
            payload={"stage_index": stage_index, "duration_ms": 1.5},
        )
    return [started, terminal]


def test_timeline_stage_entry_rejects_failed_without_error_type() -> None:
    with pytest.raises(ObservabilityError):
        ExecutionTimelineStageEntry(
            stage_name="s",
            stage_index=0,
            status="failed",
            duration_ms=1.0,
            error_type=None,
        )


def test_timeline_stage_entry_rejects_completed_with_error_type() -> None:
    with pytest.raises(ObservabilityError):
        ExecutionTimelineStageEntry(
            stage_name="s",
            stage_index=0,
            status="completed",
            duration_ms=1.0,
            error_type="ValueError",
        )


def test_timeline_view_rejects_non_increasing_stage_indices() -> None:
    entry_a = ExecutionTimelineStageEntry(stage_name="a", stage_index=0, status="completed", duration_ms=1.0)
    entry_c = ExecutionTimelineStageEntry(stage_name="c", stage_index=2, status="completed", duration_ms=1.0)
    with pytest.raises(ObservabilityError):
        ExecutionTimelineView(tick_id=1, stages=(entry_a, entry_c), completed=True, stage_count=2)


def test_timeline_view_to_evidence_projection() -> None:
    entry = ExecutionTimelineStageEntry(stage_name="a", stage_index=0, status="completed", duration_ms=2.0)
    view = ExecutionTimelineView(tick_id=3, stages=(entry,), completed=True, stage_count=1)

    evidence = view.to_evidence("timeline-evidence:3")

    assert evidence["evidence_id"] == "timeline-evidence:3"
    assert evidence["tick_id"] == 3
    assert evidence["completed"] is True
    assert evidence["stage_count"] == 1
    assert evidence["stages"][0]["stage_name"] == "a"
    assert evidence["stages"][0]["status"] == "completed"


def test_reconstruct_multi_stage_tick_in_canonical_order() -> None:
    events = (
        _event(1, "runtime_startup"),
        *_stage_lifecycle(2, 1, "sensory_ingress", 0),
        *_stage_lifecycle(4, 1, "rapid_salience_appraisal", 1),
        *_stage_lifecycle(6, 1, "neuromodulator_system", 2),
        _event(8, "runtime_tick_completed", tick_id=1, payload={"stage_count": 3}),
    )

    view = ExecutionTimelineReconstructor().reconstruct(events, 1)

    assert view.tick_id == 1
    assert view.completed is True
    assert view.stage_count == 3
    assert tuple(stage.stage_name for stage in view.stages) == (
        "sensory_ingress",
        "rapid_salience_appraisal",
        "neuromodulator_system",
    )
    assert all(stage.status == "completed" for stage in view.stages)


def test_reconstruct_failed_stage_yields_failed_entry() -> None:
    events = (
        *_stage_lifecycle(1, 1, "sensory_ingress", 0),
        *_stage_lifecycle(3, 1, "rapid_salience_appraisal", 1, failed=True),
    )

    view = ExecutionTimelineReconstructor().reconstruct(events, 1)

    assert view.completed is False
    failed = view.stages[-1]
    assert failed.stage_name == "rapid_salience_appraisal"
    assert failed.status == "failed"
    assert failed.error_type == "ValueError"


def test_reconstruct_missing_lifecycle_yields_incomplete_view() -> None:
    events = (_event(1, "runtime_startup"),)

    view = ExecutionTimelineReconstructor().reconstruct(events, 5)

    assert view.tick_id == 5
    assert view.stages == ()
    assert view.completed is False
    assert view.stage_count == 0


def test_reconstruct_terminal_without_started_raises() -> None:
    events = (
        _event(1, "stage_completed", tick_id=1, stage_name="ghost", payload={"stage_index": 0, "duration_ms": 1.0}),
    )

    with pytest.raises(ObservabilityError, match="unstarted stage"):
        ExecutionTimelineReconstructor().reconstruct(events, 1)


def test_reconstruct_duplicate_terminal_raises() -> None:
    events = (
        *_stage_lifecycle(1, 1, "sensory_ingress", 0),
        _event(3, "stage_completed", tick_id=1, stage_name="sensory_ingress", payload={"stage_index": 0, "duration_ms": 1.0}),
    )

    with pytest.raises(ObservabilityError, match="duplicate terminal"):
        ExecutionTimelineReconstructor().reconstruct(events, 1)


def test_reconstruct_rejects_non_positive_tick_id() -> None:
    with pytest.raises(ObservabilityError, match="positive tick_id"):
        ExecutionTimelineReconstructor().reconstruct((), 0)
