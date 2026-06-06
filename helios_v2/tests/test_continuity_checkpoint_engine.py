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
from helios_v2.thought_gating import ContinuationPressureState


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
