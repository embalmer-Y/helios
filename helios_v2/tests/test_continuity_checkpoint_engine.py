from __future__ import annotations

import pytest

from helios_v2.autonomy import ContinuityThread, DeferredContinuityRecord
from helios_v2.continuity_checkpoint import (
    CheckpointError,
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    RuntimeContinuitySnapshot,
    SqliteCheckpointBackend,
)
from helios_v2.neuromodulation import NeuromodulatorLevels
from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.feeling import InteroceptiveFeelingVector


def _feeling(value: float = 0.4) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=value,
        arousal=value,
        tension=value,
        comfort=value,
        fatigue=value,
        pain_like=value,
        social_safety=value,
    )


def _levels(value: float = 0.42) -> NeuromodulatorLevels:
    return NeuromodulatorLevels(
        dopamine=value,
        norepinephrine=value,
        serotonin=value,
        acetylcholine=value,
        cortisol=value,
        oxytocin=value,
        opioid_tone=value,
        excitation=value,
        inhibition=value,
    )


def _snapshot(tick_id: int, *, level: float = 0.5, carry_count: int = 1) -> RuntimeContinuitySnapshot:
    return RuntimeContinuitySnapshot(
        tick_id=tick_id,
        continuation_state=ContinuationPressureState(
            active=True,
            level=level,
            origin_thought_id="thought:1",
            reason="need_more_context",
            expires_at_tick=tick_id + 4,
            carry_count=carry_count,
        ),
        deferred_records=(
            DeferredContinuityRecord(
                record_id=f"deferred:{tick_id}",
                continuity_key="key-1",
                origin_ref="origin-1",
                carry_reason="carry forward",
                carry_count=carry_count,
                decayed_pressure=0.4,
                expires_after_ticks=5,
            ),
        ),
        continuity_threads=(
            ContinuityThread(
                thread_id=f"thread:{tick_id}",
                continuity_key="key-1",
                origin_ref="origin-1",
                age_ticks=tick_id,
                reinforcement_count=carry_count,
                thread_strength=0.6,
                thread_state="reinforced",
                last_carry_reason="recurring tendency",
            ),
        ),
        neuromodulator_levels=_levels(0.3 + 0.01 * tick_id),
        feeling=_feeling(0.4 + 0.01 * tick_id),
    )


# --- In-memory backend + facade ---


def test_in_memory_cold_load_returns_none() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    store.initialize()
    assert store.load_latest() is None


def test_in_memory_save_then_load_round_trips_exactly() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    snapshot = _snapshot(3)
    store.save_latest(snapshot)
    assert store.load_latest() == snapshot


def test_save_replaces_latest_does_not_append() -> None:
    backend = InMemoryCheckpointBackend()
    store = ContinuityCheckpointStore(backend=backend)
    store.save_latest(_snapshot(1, carry_count=1))
    store.save_latest(_snapshot(2, carry_count=2))
    loaded = store.load_latest()
    assert loaded is not None
    # Latest-state: only the second snapshot remains.
    assert loaded.tick_id == 2
    assert loaded.continuation_state.carry_count == 2


# --- SQLite durability ---


def test_sqlite_round_trips_snapshot(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    store = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    store.initialize()
    snapshot = _snapshot(5)
    store.save_latest(snapshot)
    assert store.load_latest() == snapshot


def test_sqlite_latest_survives_reopen(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    first = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    first.save_latest(_snapshot(2, carry_count=2))

    # A brand-new store object on the same file must see the latest snapshot.
    second = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    loaded = second.load_latest()
    assert loaded is not None
    assert loaded.tick_id == 2
    assert loaded.continuation_state.carry_count == 2


def test_sqlite_reopen_sees_replacement_not_history(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    a = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    a.save_latest(_snapshot(1, carry_count=1))
    a.save_latest(_snapshot(4, carry_count=3))

    b = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    loaded = b.load_latest()
    assert loaded is not None
    assert loaded.tick_id == 4
    assert loaded.continuation_state.carry_count == 3


def test_sqlite_initialize_is_idempotent(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    backend.initialize()
    store = ContinuityCheckpointStore(backend=backend)
    assert store.load_latest() is None


def test_sqlite_unwritable_path_fails_fast(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    db_path = str(blocker / "nested" / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    with pytest.raises(CheckpointError):
        backend.initialize()


def test_corrupt_stored_payload_raises_on_load(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    # Write a non-JSON payload directly through the backend; load must hard-stop.
    backend.save_latest("{not valid json")
    store = ContinuityCheckpointStore(backend=backend)
    with pytest.raises(CheckpointError):
        store.load_latest()


# --- Requirement 43: snapshot v2 carries 04 neuromodulator levels ---


def test_snapshot_round_trips_neuromodulator_levels(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    store = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    snapshot = _snapshot(5)
    store.save_latest(snapshot)
    loaded = store.load_latest()
    assert loaded is not None
    assert loaded.neuromodulator_levels == snapshot.neuromodulator_levels
    assert loaded.snapshot_version == 3


def test_snapshot_without_levels_round_trips_as_none() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    snapshot = RuntimeContinuitySnapshot(
        tick_id=1,
        continuation_state=ContinuationPressureState.inactive(),
    )
    store.save_latest(snapshot)
    loaded = store.load_latest()
    assert loaded is not None
    assert loaded.neuromodulator_levels is None


def test_version_one_payload_is_rejected_not_migrated(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    # A version-1 payload (the pre-R43 shape) must be rejected on load, not silently migrated.
    backend.save_latest(
        '{"snapshot_version": 1, "tick_id": 1, '
        '"continuation_state": {"active": false, "level": 0.0, "origin_thought_id": "", '
        '"reason": "", "expires_at_tick": 0, "carry_count": 0}, '
        '"deferred_records": [], "continuity_threads": []}'
    )
    store = ContinuityCheckpointStore(backend=backend)
    with pytest.raises(CheckpointError, match="version"):
        store.load_latest()


def test_corrupt_neuromodulator_levels_hard_stop_on_load(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    # An out-of-range level (1.5) violates the 04 owner invariant; load must hard-stop.
    backend.save_latest(
        '{"snapshot_version": 3, "tick_id": 1, '
        '"continuation_state": {"active": false, "level": 0.0, "origin_thought_id": "", '
        '"reason": "", "expires_at_tick": 0, "carry_count": 0}, '
        '"deferred_records": [], "continuity_threads": [], '
        '"neuromodulator_levels": {"dopamine": 1.5, "norepinephrine": 0.3, "serotonin": 0.3, '
        '"acetylcholine": 0.3, "cortisol": 0.3, "oxytocin": 0.3, "opioid_tone": 0.3, '
        '"excitation": 0.3, "inhibition": 0.3}}'
    )
    store = ContinuityCheckpointStore(backend=backend)
    with pytest.raises(CheckpointError):
        store.load_latest()


# --- Requirement 44: snapshot v3 carries 05 feeling ---


def test_snapshot_round_trips_feeling(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    store = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    snapshot = _snapshot(6)
    store.save_latest(snapshot)
    loaded = store.load_latest()
    assert loaded is not None
    assert loaded.feeling == snapshot.feeling
    assert loaded.snapshot_version == 3


def test_version_two_payload_is_rejected_not_migrated(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    # A version-2 payload (the pre-R44 shape, with 04 levels but no 05 feeling) must be rejected.
    backend.save_latest(
        '{"snapshot_version": 2, "tick_id": 1, '
        '"continuation_state": {"active": false, "level": 0.0, "origin_thought_id": "", '
        '"reason": "", "expires_at_tick": 0, "carry_count": 0}, '
        '"deferred_records": [], "continuity_threads": [], '
        '"neuromodulator_levels": {"dopamine": 0.3, "norepinephrine": 0.3, "serotonin": 0.3, '
        '"acetylcholine": 0.3, "cortisol": 0.3, "oxytocin": 0.3, "opioid_tone": 0.3, '
        '"excitation": 0.3, "inhibition": 0.3}}'
    )
    store = ContinuityCheckpointStore(backend=backend)
    with pytest.raises(CheckpointError, match="version"):
        store.load_latest()


def test_corrupt_feeling_hard_stop_on_load(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")
    backend = SqliteCheckpointBackend(db_path=db_path)
    backend.initialize()
    # An out-of-range feeling dimension (1.5) violates the 05 owner invariant; load must hard-stop.
    backend.save_latest(
        '{"snapshot_version": 3, "tick_id": 1, '
        '"continuation_state": {"active": false, "level": 0.0, "origin_thought_id": "", '
        '"reason": "", "expires_at_tick": 0, "carry_count": 0}, '
        '"deferred_records": [], "continuity_threads": [], "neuromodulator_levels": null, '
        '"feeling": {"valence": 1.5, "arousal": 0.4, "tension": 0.4, "comfort": 0.4, '
        '"fatigue": 0.4, "pain_like": 0.4, "social_safety": 0.4}}'
    )
    store = ContinuityCheckpointStore(backend=backend)
    with pytest.raises(CheckpointError):
        store.load_latest()
