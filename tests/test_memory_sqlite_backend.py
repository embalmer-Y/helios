"""Focused tests for the SQLite long-term memory backend."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalStore, MemorySystem, SQLiteMemoryBackend, ensure_sqlite_memory_backend


def test_sqlite_memory_backend_initializes_expected_tables(tmp_path):
    db_path = tmp_path / "memory_backend.sqlite3"
    backend = ensure_sqlite_memory_backend(db_path)

    assert backend.db_path.exists()
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "memory_semantic" in tables
    assert "memory_episodic" in tables
    assert "memory_autobio" in tables
    assert "memory_autobio_chapters" in tables
    assert "memory_autobio_archive" in tables


def test_sqlite_memory_backend_round_trips_memory_system_payloads(tmp_path):
    backend = SQLiteMemoryBackend(tmp_path / "memory_backend.sqlite3")
    memory_system = MemorySystem(backend=backend)
    memory_system.learn("favorite.color", "blue", tags=["preference"])
    memory_system.remember("A vivid event", valence=0.8, arousal=0.6, phi=0.5)

    memory_system.save_to_backend(backend)

    restored = MemorySystem(backend=backend)
    restored.load_from_backend(backend)

    assert restored.know("favorite.color") == "blue"
    assert len(restored.episodic.items) == 1
    assert restored.episodic.items[0].summary == "A vivid event"


def test_sqlite_memory_backend_round_trips_autobiographical_store(tmp_path):
    backend = SQLiteMemoryBackend(tmp_path / "memory_backend.sqlite3")
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False, backend=backend)

    store.record(
        panksepp={"SEEKING": 0.8},
        valence=0.4,
        arousal=0.5,
        dominant="SEEKING",
        phi=0.3,
        narrative="Found something interesting",
        cycle=7,
    )
    store.flush()

    reloaded = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False, backend=backend)

    assert backend.count_moments() == 1
    assert len(reloaded.moments) == 1
    assert reloaded.moments[0].narrative == "Found something interesting"
    assert reloaded.moments[0].cycle == 7


def test_sqlite_memory_backend_archives_and_rewrites_autobio_active_view(tmp_path):
    backend = SQLiteMemoryBackend(tmp_path / "memory_backend.sqlite3")
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False, backend=backend)

    first = store.record(
        panksepp={"CARE": 0.7},
        valence=0.5,
        arousal=0.4,
        dominant="CARE",
        phi=0.2,
        narrative="First moment",
        cycle=1,
    )
    second = store.record(
        panksepp={"PLAY": 0.7},
        valence=0.6,
        arousal=0.5,
        dominant="PLAY",
        phi=0.4,
        narrative="Second moment",
        cycle=2,
    )
    store.flush()

    backend.archive_active_log("batch-1")
    assert backend.count_moments() == 0

    backend.overwrite_active_moments([second.to_dict()])

    reloaded = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False, backend=backend)
    assert len(reloaded.moments) == 1
    assert reloaded.moments[0].moment_id == second.moment_id

    with sqlite3.connect(backend.db_path) as connection:
        archived_rows = connection.execute(
            "SELECT COUNT(*) FROM memory_autobio_archive WHERE archive_batch = ?",
            ("batch-1",),
        ).fetchone()[0]
    assert archived_rows == 2