"""R92: tests for the additive `created_at_wall` field on `PersistedExperienceRecord` and the
SQLite migration that adds the column.

Asserts:
  - `PersistedExperienceRecord(created_at_wall=...)` validates finite + non-negative; default is
    `None` (legacy unchanged).
  - `with_sequence` and `with_embedding` preserve the field across rebuild.
  - In-memory backend trivially round-trips the field.
  - SQLite backend round-trips the field on a fresh database.
  - SQLite migration: an existing pre-R92 database without the column gains it on initialize;
    old rows read back with `created_at_wall=None`; new writes carry the value.
  - The bridges (`ExperienceRecordBridge`, `MemoryRecordBridge`) forward the kernel-seeded
    `tick_wall_seconds` into `created_at_wall` verbatim.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Mapping

import pytest

from helios_v2.persistence.contracts import PersistedExperienceRecord, PersistenceError
from helios_v2.persistence.engine import (
    InMemoryExperienceStoreBackend,
    SqliteExperienceStoreBackend,
)


# ---------------------------------------------------------------------------
# Contract: validation + default
# ---------------------------------------------------------------------------


def _record(**overrides) -> PersistedExperienceRecord:
    """Build a minimal valid record for tests."""

    defaults = dict(
        record_id="experience:r92:1",
        tick_id=1,
        continuity_kind="executed_outcome",
        outcome_class="self_changed",
        source_outcome_kind="planner_decision",
        source_outcome_id="decision:1",
        writeback_status="written",
        summary="a summary",
        requested_effect_summary="a request",
        applied_effect_summary="an effect",
        reason_trace=("a", "b"),
        linkage={"thought_cycle_result_id": "thought:1"},
    )
    defaults.update(overrides)
    return PersistedExperienceRecord(**defaults)


def test_record_default_created_at_wall_is_none() -> None:
    rec = _record()
    assert rec.created_at_wall is None


def test_record_accepts_finite_non_negative_value() -> None:
    rec = _record(created_at_wall=12.5)
    assert rec.created_at_wall == 12.5


def test_record_normalizes_int_to_float() -> None:
    rec = _record(created_at_wall=10)
    assert rec.created_at_wall == 10.0
    assert isinstance(rec.created_at_wall, float)


def test_record_rejects_nan() -> None:
    with pytest.raises(PersistenceError):
        _record(created_at_wall=math.nan)


def test_record_rejects_infinity() -> None:
    with pytest.raises(PersistenceError):
        _record(created_at_wall=math.inf)


def test_record_rejects_negative_value() -> None:
    with pytest.raises(PersistenceError):
        _record(created_at_wall=-1.0)


def test_record_rejects_non_numeric_value() -> None:
    with pytest.raises(PersistenceError):
        _record(created_at_wall="now")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Round-trip helpers preserve the field
# ---------------------------------------------------------------------------


def test_with_sequence_preserves_created_at_wall() -> None:
    rec = _record(created_at_wall=42.0)
    stamped = rec.with_sequence(7)
    assert stamped.sequence == 7
    assert stamped.created_at_wall == 42.0


def test_with_embedding_preserves_created_at_wall() -> None:
    rec = _record(created_at_wall=42.0)
    embedded = rec.with_embedding((0.1, 0.2, 0.3))
    assert embedded.embedding == (0.1, 0.2, 0.3)
    assert embedded.created_at_wall == 42.0


# ---------------------------------------------------------------------------
# In-memory backend round-trip
# ---------------------------------------------------------------------------


def test_in_memory_backend_round_trips_created_at_wall() -> None:
    backend = InMemoryExperienceStoreBackend()
    backend.initialize()
    backend.append((_record(record_id="a", created_at_wall=10.0),))
    backend.append((_record(record_id="b", created_at_wall=20.0),))
    backend.append((_record(record_id="c"),))  # no clock wired => None

    rows = backend.read_recent(10)
    assert len(rows) == 3
    by_id = {row.record_id: row for row in rows}
    assert by_id["a"].created_at_wall == 10.0
    assert by_id["b"].created_at_wall == 20.0
    assert by_id["c"].created_at_wall is None


# ---------------------------------------------------------------------------
# SQLite backend round-trip on fresh database
# ---------------------------------------------------------------------------


def test_sqlite_backend_round_trips_created_at_wall(tmp_path) -> None:
    db_path = tmp_path / "store.sqlite3"
    backend = SqliteExperienceStoreBackend(db_path=str(db_path))
    backend.initialize()
    backend.append((_record(record_id="a", created_at_wall=10.5),))
    backend.append((_record(record_id="b", created_at_wall=20.25),))
    backend.append((_record(record_id="c"),))  # None

    rows = backend.read_recent(10)
    by_id = {row.record_id: row for row in rows}
    assert by_id["a"].created_at_wall == 10.5
    assert by_id["b"].created_at_wall == 20.25
    assert by_id["c"].created_at_wall is None


# ---------------------------------------------------------------------------
# SQLite migration: pre-R92 file gains the column in place
# ---------------------------------------------------------------------------


def _create_legacy_pre_r92_table(db_path: Path) -> None:
    """Simulate a pre-R92 database by creating the table without the `created_at_wall` column,
    then inserting one row through plain SQLite (no Helios layer)."""

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE experience_records (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                tick_id INTEGER,
                continuity_kind TEXT NOT NULL,
                outcome_class TEXT NOT NULL,
                source_outcome_kind TEXT NOT NULL,
                source_outcome_id TEXT NOT NULL,
                writeback_status TEXT NOT NULL,
                summary TEXT NOT NULL,
                requested_effect_summary TEXT NOT NULL,
                applied_effect_summary TEXT NOT NULL,
                reason_trace TEXT NOT NULL,
                linkage TEXT NOT NULL,
                embedding TEXT,
                record_kind TEXT,
                metadata TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO experience_records (
                record_id, tick_id, continuity_kind, outcome_class,
                source_outcome_kind, source_outcome_id, writeback_status,
                summary, requested_effect_summary, applied_effect_summary,
                reason_trace, linkage, embedding, record_kind, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy:1",
                1,
                "executed_outcome",
                "self_changed",
                "planner_decision",
                "decision:legacy",
                "written",
                "legacy summary",
                "legacy request",
                "legacy effect",
                '["a", "b"]',
                '{"thought_cycle_result_id": "thought:legacy"}',
                None,
                None,
                None,
            ),
        )
        conn.commit()


def test_sqlite_migration_adds_created_at_wall_column_in_place(tmp_path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_pre_r92_table(db_path)

    # Confirm the legacy table lacks the column.
    with sqlite3.connect(str(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(experience_records)")}
    assert "created_at_wall" not in cols

    # Initialize the R92 backend; the migration should add the column.
    backend = SqliteExperienceStoreBackend(db_path=str(db_path))
    backend.initialize()

    # Column now exists.
    with sqlite3.connect(str(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(experience_records)")}
    assert "created_at_wall" in cols

    # The legacy row reads back with `created_at_wall=None` (NULL preserved as honest absence).
    rows = backend.read_recent(10)
    assert len(rows) == 1
    assert rows[0].record_id == "legacy:1"
    assert rows[0].created_at_wall is None


def test_sqlite_migration_preserves_legacy_rows_and_accepts_new_writes(tmp_path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_pre_r92_table(db_path)

    backend = SqliteExperienceStoreBackend(db_path=str(db_path))
    backend.initialize()
    # New writes carry the value.
    backend.append((_record(record_id="post-r92", created_at_wall=100.0),))

    rows = backend.read_recent(10)
    by_id = {row.record_id: row for row in rows}
    assert by_id["legacy:1"].created_at_wall is None
    assert by_id["post-r92"].created_at_wall == 100.0


# ---------------------------------------------------------------------------
# Bridges forward tick_wall_seconds into created_at_wall verbatim
# ---------------------------------------------------------------------------


def test_experience_record_bridge_forwards_tick_wall_seconds_into_created_at_wall() -> None:
    """`ExperienceRecordBridge.build_records(..., tick_wall_seconds=X)` must put `X` into every
    record's `created_at_wall`.

    Uses minimally-valid `ContinuityEvidencePacket` / `ExperienceWritebackResult` /
    `ExperienceWritebackStageResult` instances per their real contract shapes.
    """

    from helios_v2.composition.bridges import ExperienceRecordBridge
    from helios_v2.experience_writeback.contracts import (
        ConsolidationCandidate,
        ContinuityEvidencePacket,
        ExperienceWritebackResult,
    )
    from helios_v2.runtime.stages import ExperienceWritebackStageResult

    packet = ContinuityEvidencePacket(
        packet_id="packet:1",
        continuity_kind="external_action",
        source_outcome_kind="planner_bridge",
        source_outcome_id="decision:1",
        outcome_class="world_changed",
        summary="a summary",
        requested_effect_summary="a request",
        applied_effect_summary="an effect",
        reason_trace=("reason-a",),
        source_provenance={"thought_cycle_result_id": "thought:1"},
    )
    candidate = ConsolidationCandidate(
        candidate_id="candidate:1",
        target_memory_family="autobiographical",
        priority_hint=0.5,
        salience_reason="r92-test",
        continuity_packet=packet,
    )
    writeback = ExperienceWritebackResult(
        result_id="r:1",
        source_request_id="req:1",
        status="written",
        continuity_packet=packet,
        consolidation_candidates=(candidate,),
        tick_id=1,
    )
    stage = ExperienceWritebackStageResult(
        requests=(),
        results=(writeback,),
        publish_writeback_ops=(),
        publish_candidate_ops=(),
    )

    bridge = ExperienceRecordBridge()
    records_with_clock = bridge.build_records(stage, tick_id=1, tick_wall_seconds=42.0)
    assert len(records_with_clock) == 1
    assert records_with_clock[0].created_at_wall == 42.0

    # When no clock is wired, default is None.
    records_without_clock = bridge.build_records(stage, tick_id=1)
    assert records_without_clock[0].created_at_wall is None
