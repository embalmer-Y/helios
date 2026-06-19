"""R101 T8 + T9: PersistedExperienceRecord 8 additive fields + SQLite ALTER TABLE migration tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from helios_v2.memory import ObjectiveImportanceVector
from helios_v2.persistence import (
    PersistenceError,
    PersistedExperienceRecord,
    SqliteExperienceStoreBackend,
)


# =============================================================================
# T8: Contract tests for 8 additive fields
# =============================================================================


def _make_record(**overrides) -> PersistedExperienceRecord:
    defaults = dict(
        record_id="r-1",
        tick_id=1,
        continuity_kind="externalized_outward",
        outcome_class="executed",
        source_outcome_kind="planner_executed",
        source_outcome_id="d-1",
        writeback_status="executed",
        summary="test",
        requested_effect_summary="",
        applied_effect_summary="",
        reason_trace=("reason",),
        linkage={"source": "d-1"},
    )
    defaults.update(overrides)
    return PersistedExperienceRecord(**defaults)


def test_record_with_all_r101_fields_constructs() -> None:
    rec = _make_record(
        objective_importance_json=ObjectiveImportanceVector(0.5, 0.5, 0.5, 0.5, 0.5, 0.5).to_json(),
        objective_score=0.65,
        subjective_score=0.7,
        double_confirmation_class="both_pass",
        recall_count=3,
        recall_utility_score=0.6,
        last_updated_at_wall=1234567890.0,
        promotion_history_json="[]",
    )
    assert rec.objective_score == 0.65
    assert rec.subjective_score == 0.7
    assert rec.double_confirmation_class == "both_pass"
    assert rec.recall_count == 3
    assert rec.recall_utility_score == 0.6
    assert rec.last_updated_at_wall == 1234567890.0


def test_record_with_no_r101_fields_defaults_none() -> None:
    rec = _make_record()
    assert rec.objective_importance_json is None
    assert rec.objective_score is None
    assert rec.subjective_score is None
    assert rec.double_confirmation_class is None
    assert rec.recall_count is None
    assert rec.recall_utility_score is None
    assert rec.last_updated_at_wall is None
    assert rec.promotion_history_json is None


def test_record_with_skip_class_constructs() -> None:
    """P5 key invariant: skip records are retained (not dropped)."""
    rec = _make_record(
        double_confirmation_class="skip",
        objective_score=0.2,
    )
    assert rec.double_confirmation_class == "skip"
    assert rec.objective_score == 0.2


def test_objective_score_out_of_range_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(objective_score=1.5)
    with pytest.raises(PersistenceError):
        _make_record(objective_score=-0.1)


def test_subjective_score_out_of_range_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(subjective_score=2.0)


def test_recall_count_negative_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(recall_count=-1)


def test_recall_count_non_int_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(recall_count="not_an_int")  # type: ignore[arg-type]


def test_recall_utility_score_out_of_range_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(recall_utility_score=1.5)


def test_last_updated_at_wall_finite_non_negative() -> None:
    with pytest.raises(PersistenceError):
        _make_record(last_updated_at_wall=float("inf"))
    with pytest.raises(PersistenceError):
        _make_record(last_updated_at_wall=-1.0)
    with pytest.raises(PersistenceError):
        _make_record(last_updated_at_wall=float("nan"))


def test_double_confirmation_class_invalid_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(double_confirmation_class="invalid_class")  # type: ignore[arg-type]


def test_double_confirmation_class_all_four_accepted() -> None:
    for cls in ("both_pass", "objective_only", "subjective_only", "skip"):
        rec = _make_record(double_confirmation_class=cls)
        assert rec.double_confirmation_class == cls


def test_objective_importance_json_malformed_raises() -> None:
    with pytest.raises(PersistenceError):
        _make_record(objective_importance_json="not valid json")


def test_objective_importance_json_roundtrip() -> None:
    v = ObjectiveImportanceVector(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    rec = _make_record(objective_importance_json=v.to_json())
    v2 = ObjectiveImportanceVector.from_json(rec.objective_importance_json)
    assert v == v2


# =============================================================================
# T9: SQLite ALTER TABLE migration tests
# =============================================================================


def _make_temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        path = Path(f.name)
    return path


def test_sqlite_initialization_creates_8_new_columns() -> None:
    path = _make_temp_db()
    backend = SqliteExperienceStoreBackend(path)
    try:
        backend.initialize()
        # Inspect schema (use correct table name)
        with sqlite3.connect(str(path)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(experience_records)")}
        expected_new = {
            "objective_importance_json", "objective_score", "subjective_score",
            "double_confirmation_class", "recall_count", "recall_utility_score",
            "last_updated_at_wall", "promotion_history_json",
        }
        missing = expected_new - cols
        assert not missing, f"Missing R101 columns: {missing}"
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_sqlite_roundtrip_r101_fields() -> None:
    path = _make_temp_db()
    backend = SqliteExperienceStoreBackend(path)
    try:
        backend.initialize()
        v = ObjectiveImportanceVector(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
        rec = _make_record(
            objective_importance_json=v.to_json(),
            objective_score=0.65,
            subjective_score=0.7,
            double_confirmation_class="both_pass",
            recall_count=3,
            recall_utility_score=0.6,
            last_updated_at_wall=1234567890.0,
            promotion_history_json='[{"from": "L3_short"}]',
        )
        stamped = backend.append((rec,))
        # Read back
        recent = backend.read_recent(10)
        assert len(recent) == 1
        read_back = recent[0]
        assert read_back.objective_score == pytest.approx(0.65)
        assert read_back.subjective_score == pytest.approx(0.7)
        assert read_back.double_confirmation_class == "both_pass"
        assert read_back.recall_count == 3
        assert read_back.recall_utility_score == pytest.approx(0.6)
        assert read_back.last_updated_at_wall == pytest.approx(1234567890.0)
        # Vector round-trip via JSON
        v2 = ObjectiveImportanceVector.from_json(read_back.objective_importance_json)
        assert v == v2
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_sqlite_migration_idempotent_on_existing_r100_db() -> None:
    """Pre-R101 database (with R100 layer/memory_metadata but no R101 columns) upgrades in place."""
    path = _make_temp_db()
    try:
        # Create a pre-R101 schema with R100 columns only
        with sqlite3.connect(str(path)) as conn:
            conn.execute("""
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
                    requested_effect_summary TEXT,
                    applied_effect_summary TEXT,
                    reason_trace TEXT,
                    linkage TEXT,
                    embedding TEXT,
                    record_kind TEXT,
                    metadata TEXT,
                    created_at_wall REAL,
                    layer TEXT,
                    memory_metadata TEXT
                )
            """)
            conn.commit()
        # Now initialize backend -> should ALTER TABLE to add 8 R101 columns
        backend = SqliteExperienceStoreBackend(path)
        backend.initialize()
        with sqlite3.connect(str(path)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(experience_records)")}
        assert "objective_score" in cols
        assert "subjective_score" in cols
        assert "double_confirmation_class" in cols
        assert "recall_count" in cols
        # Old layer column preserved
        assert "layer" in cols
        assert "memory_metadata" in cols
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_sqlite_pre_existing_rows_read_r101_fields_as_none() -> None:
    """Rows written before R101 read back with all R101 fields None."""
    path = _make_temp_db()
    try:
        # Write a pre-R101 row (no R101 columns populated)
        with sqlite3.connect(str(path)) as conn:
            conn.execute("""
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
                    requested_effect_summary TEXT,
                    applied_effect_summary TEXT,
                    reason_trace TEXT,
                    linkage TEXT,
                    embedding TEXT,
                    record_kind TEXT,
                    metadata TEXT,
                    created_at_wall REAL,
                    layer TEXT,
                    memory_metadata TEXT
                )
            """)
            conn.execute(
                "INSERT INTO experience_records (record_id, continuity_kind, outcome_class, source_outcome_kind, source_outcome_id, writeback_status, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("legacy-r-1", "externalized_outward", "executed", "planner_executed", "d-1", "executed", "legacy"),
            )
            conn.commit()
        backend = SqliteExperienceStoreBackend(path)
        backend.initialize()  # migration runs
        recent = backend.read_recent(10)
        assert len(recent) == 1
        rec = recent[0]
        assert rec.record_id == "legacy-r-1"
        assert rec.objective_importance_json is None
        assert rec.objective_score is None
        assert rec.subjective_score is None
        assert rec.double_confirmation_class is None
        assert rec.recall_count is None
        assert rec.recall_utility_score is None
        assert rec.last_updated_at_wall is None
        assert rec.promotion_history_json is None
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_sqlite_p5_sql_query_on_indexed_columns() -> None:
    """P5 use case: SQL query on indexed R101 columns works after migration."""
    path = _make_temp_db()
    backend = SqliteExperienceStoreBackend(path)
    try:
        backend.initialize()
        # Insert several records with varied R101 fields
        records = [
            _make_record(record_id=f"r-{i}", objective_score=0.3 + i * 0.1, recall_count=i)
            for i in range(5)
        ]
        backend.append(tuple(records))
        # Query directly via SQL
        with sqlite3.connect(str(path)) as conn:
            high_score = conn.execute(
                "SELECT record_id FROM experience_records WHERE objective_score > 0.5"
            ).fetchall()
            multi_recall = conn.execute(
                "SELECT record_id FROM experience_records WHERE recall_count >= 2"
            ).fetchall()
        assert len(high_score) >= 1
        assert len(multi_recall) >= 1
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_inmemory_backend_handles_8_new_fields() -> None:
    """InMemory backend stores full PersistedExperienceRecord, so 8 new fields are auto-preserved."""
    from helios_v2.persistence import InMemoryExperienceStoreBackend
    backend = InMemoryExperienceStoreBackend()
    rec = _make_record(
        objective_score=0.5,
        double_confirmation_class="skip",
        recall_count=5,
    )
    backend.append((rec,))
    recent = backend.read_recent(10)
    assert len(recent) == 1
    assert recent[0].objective_score == 0.5
    assert recent[0].double_confirmation_class == "skip"
    assert recent[0].recall_count == 5


def test_record_with_full_r101_state_passes_validation() -> None:
    """A realistic R101 record with all 8 fields + R100 fields should construct without error."""
    v = ObjectiveImportanceVector(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)
    rec = _make_record(
        layer="L4_long",
        memory_metadata={"reason": "high importance"},
        objective_importance_json=v.to_json(),
        objective_score=0.55,
        subjective_score=0.65,
        double_confirmation_class="both_pass",
        recall_count=2,
        recall_utility_score=0.7,
        last_updated_at_wall=1234567890.0,
        promotion_history_json="[]",
    )
    assert rec.layer == "L4_long"
    assert rec.objective_score == 0.55
    assert rec.double_confirmation_class == "both_pass"
    assert rec.recall_count == 2