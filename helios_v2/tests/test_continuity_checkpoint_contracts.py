from __future__ import annotations

import pytest

from helios_v2.autonomy import ContinuityThread, DeferredContinuityRecord
from helios_v2.continuity_checkpoint import (
    CheckpointError,
    RuntimeContinuitySnapshot,
    decode_snapshot,
    encode_snapshot,
)
from helios_v2.thought_gating import ContinuationPressureState


def _active_continuation() -> ContinuationPressureState:
    return ContinuationPressureState(
        active=True,
        level=0.5,
        origin_thought_id="thought:1",
        reason="need_more_context",
        expires_at_tick=7,
        carry_count=2,
    )


def _deferred() -> DeferredContinuityRecord:
    return DeferredContinuityRecord(
        record_id="deferred:1",
        continuity_key="key-1",
        origin_ref="origin-1",
        carry_reason="carry forward unresolved thought",
        carry_count=3,
        decayed_pressure=0.4,
        expires_after_ticks=5,
    )


def _thread() -> ContinuityThread:
    return ContinuityThread(
        thread_id="thread:1",
        continuity_key="key-1",
        origin_ref="origin-1",
        age_ticks=4,
        reinforcement_count=2,
        thread_strength=0.6,
        thread_state="reinforced",
        last_carry_reason="recurring tendency",
    )


def test_snapshot_reuses_owner_contracts_verbatim() -> None:
    snapshot = RuntimeContinuitySnapshot(
        tick_id=9,
        continuation_state=_active_continuation(),
        deferred_records=(_deferred(),),
        continuity_threads=(_thread(),),
    )
    assert snapshot.tick_id == 9
    assert snapshot.continuation_state.active is True
    assert snapshot.deferred_records[0].record_id == "deferred:1"
    assert snapshot.continuity_threads[0].thread_id == "thread:1"
    assert snapshot.snapshot_version == 2


def test_snapshot_rejects_non_positive_version() -> None:
    with pytest.raises(CheckpointError, match="snapshot_version"):
        RuntimeContinuitySnapshot(
            tick_id=1,
            continuation_state=ContinuationPressureState.inactive(),
            snapshot_version=0,
        )


def test_snapshot_rejects_wrong_typed_collections() -> None:
    with pytest.raises(CheckpointError, match="deferred_records"):
        RuntimeContinuitySnapshot(
            tick_id=1,
            continuation_state=ContinuationPressureState.inactive(),
            deferred_records=("not-a-record",),  # type: ignore[arg-type]
        )
    with pytest.raises(CheckpointError, match="continuity_threads"):
        RuntimeContinuitySnapshot(
            tick_id=1,
            continuation_state=ContinuationPressureState.inactive(),
            continuity_threads=("not-a-thread",),  # type: ignore[arg-type]
        )


def test_encode_decode_round_trips_active_snapshot() -> None:
    snapshot = RuntimeContinuitySnapshot(
        tick_id=12,
        continuation_state=_active_continuation(),
        deferred_records=(_deferred(),),
        continuity_threads=(_thread(),),
    )
    restored = decode_snapshot(encode_snapshot(snapshot))
    assert restored == snapshot


def test_encode_decode_round_trips_inert_snapshot() -> None:
    snapshot = RuntimeContinuitySnapshot(
        tick_id=None,
        continuation_state=ContinuationPressureState.inactive(),
    )
    restored = decode_snapshot(encode_snapshot(snapshot))
    assert restored == snapshot
    assert restored.deferred_records == ()
    assert restored.continuity_threads == ()


def test_decode_rejects_non_json() -> None:
    with pytest.raises(CheckpointError, match="not valid JSON"):
        decode_snapshot("{not json")


def test_decode_rejects_non_object_payload() -> None:
    with pytest.raises(CheckpointError, match="must be a JSON object"):
        decode_snapshot("[1, 2, 3]")


def test_decode_invariant_violating_owner_state_is_hard_stop() -> None:
    # An active continuation state with a zero level violates the `09` owner invariant; the
    # decoder must surface it as a hard stop, never seed an invalid state.
    corrupt = (
        '{"snapshot_version": 2, "tick_id": 1, '
        '"continuation_state": {"active": true, "level": 0.0, "origin_thought_id": "t", '
        '"reason": "r", "expires_at_tick": 3, "carry_count": 1}, '
        '"deferred_records": [], "continuity_threads": []}'
    )
    with pytest.raises(CheckpointError):
        decode_snapshot(corrupt)
