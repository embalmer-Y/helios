from __future__ import annotations

import json

import pytest

from helios_v2.observability import (
    LogEvent,
    ObservabilityError,
    severity_rank,
)


def _valid_event(**overrides) -> LogEvent:
    base = dict(
        event_id="log-event:1",
        sequence=1,
        severity="info",
        event_kind="owner_emission",
        owner="runtime_kernel",
        message="stage completed",
    )
    base.update(overrides)
    return LogEvent(**base)


def test_log_event_is_immutable():
    event = _valid_event()
    with pytest.raises(Exception):
        event.message = "mutated"  # type: ignore[misc]


def test_log_event_freezes_payload():
    event = _valid_event(payload={"stage_index": 0})
    with pytest.raises(TypeError):
        event.payload["stage_index"] = 1  # type: ignore[index]


def test_log_event_rejects_empty_owner():
    with pytest.raises(ObservabilityError):
        _valid_event(owner="")


def test_log_event_rejects_empty_message():
    with pytest.raises(ObservabilityError):
        _valid_event(message="")


def test_log_event_rejects_unknown_severity():
    with pytest.raises(ObservabilityError):
        _valid_event(severity="verbose")


def test_log_event_rejects_unknown_event_kind():
    with pytest.raises(ObservabilityError):
        _valid_event(event_kind="stage_skipped")


def test_log_event_rejects_negative_sequence():
    with pytest.raises(ObservabilityError):
        _valid_event(sequence=-1)


def test_log_event_rejects_empty_provenance_ref():
    with pytest.raises(ObservabilityError):
        _valid_event(provenance_refs=("ok", ""))


def test_log_event_rejects_empty_payload_key():
    with pytest.raises(ObservabilityError):
        _valid_event(payload={"": "value"})


def test_to_record_is_json_serializable_and_stable():
    event = _valid_event(
        tick_id=3,
        stage_name="sensory_ingress",
        provenance_refs=("stimulus-batch:abc",),
        payload={"stage_index": 0, "duration_ms": 1.5},
    )
    record = event.to_record()
    encoded = json.dumps(record)
    decoded = json.loads(encoded)
    assert decoded["event_id"] == "log-event:1"
    assert decoded["sequence"] == 1
    assert decoded["severity"] == "info"
    assert decoded["event_kind"] == "owner_emission"
    assert decoded["tick_id"] == 3
    assert decoded["stage_name"] == "sensory_ingress"
    assert decoded["provenance_refs"] == ["stimulus-batch:abc"]
    assert decoded["payload"] == {"stage_index": 0, "duration_ms": 1.5}


def test_severity_rank_is_monotonic():
    assert severity_rank("debug") < severity_rank("info") < severity_rank("notice")
    assert severity_rank("notice") < severity_rank("warning") < severity_rank("error")
    assert severity_rank("error") < severity_rank("critical")


def test_severity_rank_rejects_unknown_label():
    with pytest.raises(ObservabilityError):
        severity_rank("trace")
