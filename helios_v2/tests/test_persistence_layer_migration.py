"""T5 tests: SQLite ALTER TABLE migration + search_similar/read_recent layer support.

Owner: durable experience store (33).
Validates:
- SQLite migration adds layer and memory_metadata columns (idempotent)
- _row_to_record reads new columns (forward-compatible)
- read_recent with layer_filter returns only matching records
- search_similar with preferred_layers boosts preferred records
- InMemory backend same behavior
- Legacy layer=None records are excluded by filter and receive no boost
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from helios_v2.memory.contracts import MemoryLayer, VALID_MEMORY_LAYERS
from helios_v2.persistence.contracts import (
    PersistedExperienceRecord,
    PersistenceError,
    SimilarityHit,
)
from helios_v2.persistence.engine import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    SqliteExperienceStoreBackend,
    cosine_similarity,
)

# SQLite on Windows may hold file handles; ignore cleanup errors for temp dirs.
# Available since Python 3.10.
_TMP_CLEANUP = dict(ignore_cleanup_errors=True) if hasattr(tempfile.TemporaryDirectory, '__init__') else {}


# ── Helpers ────────────────────────────────────────────────────────────


def _make_record(
    record_id: str = "test-record",
    layer: MemoryLayer | None = None,
    memory_metadata: dict[str, str] | None = None,
    embedding: tuple[float, ...] | None = None,
    sequence: int = 1,
) -> PersistedExperienceRecord:
    return PersistedExperienceRecord(
        record_id=record_id,
        tick_id=1,
        continuity_kind="experience_writeback",
        outcome_class="no_outcome",
        source_outcome_kind="cognitive_impact",
        source_outcome_id="outcome-1",
        writeback_status="written",
        summary="Test summary",
        requested_effect_summary="req",
        applied_effect_summary="app",
        reason_trace=("high_affect_intensity",),
        linkage={"source_feeling_state_id": "fs-1"},
        sequence=sequence,
        embedding=embedding,
        record_kind="experience_writeback",
        metadata={},
        created_at_wall=None,
        layer=layer,
        memory_metadata=memory_metadata or {},
    )


_QUERY_VECTOR = (1.0, 0.0, 0.0, 0.0)
# Vector that gives cosine similarity ~0.5 with _QUERY_VECTOR:
# dot = 0.5, |half| = 1.0, |query| = 1.0 → cosine = 0.5
_VEC_HALF = (0.5, 0.8660254037844386, 0.0, 0.0)
# Vector parallel to query (cosine = 1.0) for simple boost tests
_VEC_SAME = (1.0, 0.0, 0.0, 0.0)


# ── SQLite migration tests ────────────────────────────────────────────


class TestSqliteMigration:
    """ALTER TABLE migration adds layer and memory_metadata columns."""

    def test_migration_adds_columns(self) -> None:
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            # Verify columns exist via PRAGMA
            with backend._connect() as conn:
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({backend._TABLE})")}
            assert "layer" in columns
            assert "memory_metadata" in columns

    def test_migration_idempotent(self) -> None:
        """Running initialize twice must not raise an error."""
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            backend.initialize()  # second call must be idempotent

    def test_legacy_row_reads_layer_none(self) -> None:
        """A row written before R100 (no layer/metadata columns in data) reads back as layer=None."""
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            # Insert a row WITHOUT layer/metadata (simulating pre-R100 data)
            with backend._connect() as conn:
                conn.execute(
                    f"""
                    INSERT INTO {backend._TABLE} (
                        record_id, tick_id, continuity_kind, outcome_class,
                        source_outcome_kind, source_outcome_id, writeback_status,
                        summary, requested_effect_summary, applied_effect_summary,
                        reason_trace, linkage, embedding, record_kind, metadata,
                        created_at_wall
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-row-1", 1, "experience_writeback", "no_outcome",
                        "cognitive_impact", "outcome-1", "written",
                        "Legacy summary", "req", "app",
                        json.dumps(["high_affect_intensity"]),
                        json.dumps({"source_feeling_state_id": "fs-1"}),
                        None, None, None, None,
                    ),
                )
                conn.commit()
            # Read back — the row should have layer=None
            records = backend.read_recent(1)
            assert len(records) == 1
            assert records[0].layer is None
            assert dict(records[0].memory_metadata) == {}

    def test_new_row_with_layer_reads_correctly(self) -> None:
        """A row with layer=L4_long reads back with that layer."""
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            record = _make_record(layer="L4_long", memory_metadata={"classifier_version": "1.0"})
            backend.append((record,))
            records = backend.read_recent(1)
            assert len(records) == 1
            assert records[0].layer == "L4_long"
            assert dict(records[0].memory_metadata) == {"classifier_version": "1.0"}

    def test_invalid_layer_in_row_raises(self) -> None:
        """An invalid layer value stored in SQLite raises PersistenceError on read."""
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            # Manually insert a row with an invalid layer value
            with backend._connect() as conn:
                conn.execute(
                    f"""
                    INSERT INTO {backend._TABLE} (
                        record_id, tick_id, continuity_kind, outcome_class,
                        source_outcome_kind, source_outcome_id, writeback_status,
                        summary, requested_effect_summary, applied_effect_summary,
                        reason_trace, linkage, embedding, record_kind, metadata,
                        created_at_wall, layer, memory_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "bad-row", 1, "experience_writeback", "no_outcome",
                        "cognitive_impact", "outcome-1", "written",
                        "Bad summary", "req", "app",
                        json.dumps(["high_affect_intensity"]),
                        json.dumps({"source_feeling_state_id": "fs-1"}),
                        None, None, None, None,
                        "L1_sensory",  # Invalid layer value
                        None,
                    ),
                )
                conn.commit()
            with pytest.raises(PersistenceError, match="invalid layer"):
                backend.read_recent(1)


# ── read_recent with layer_filter ──────────────────────────────────────


class TestReadRecentLayerFilter:
    """read_recent with layer_filter returns only matching records."""

    def test_inmemory_no_filter_returns_all(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer=None, sequence=1),
            _make_record("r2", layer="L3_short", sequence=2),
            _make_record("r3", layer="L4_long", sequence=3),
        )
        # InMemory backend assigns sequences on append
        backend.append(records)
        result = backend.read_recent(10)
        assert len(result) == 3

    def test_inmemory_layer_filter_returns_only_matching(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer=None),
            _make_record("r2", layer="L3_short"),
            _make_record("r3", layer="L4_long"),
            _make_record("r4", layer="L4_long"),
        )
        backend.append(records)
        result = backend.read_recent(10, layer_filter="L4_long")
        assert len(result) == 2
        assert all(r.layer == "L4_long" for r in result)

    def test_inmemory_layer_filter_excludes_none(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer=None),
            _make_record("r2", layer="L3_short"),
        )
        backend.append(records)
        result = backend.read_recent(10, layer_filter="L3_short")
        assert len(result) == 1
        assert result[0].layer == "L3_short"

    def test_inmemory_filter_no_match_returns_empty(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer="L3_short"),
            _make_record("r2", layer="L4_long"),
        )
        backend.append(records)
        result = backend.read_recent(10, layer_filter="L5_autobiographical")
        assert len(result) == 0

    def test_sqlite_layer_filter_returns_only_matching(self) -> None:
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            records = (
                _make_record("r1", layer=None),
                _make_record("r2", layer="L3_short"),
                _make_record("r3", layer="L4_long"),
                _make_record("r4", layer="L4_long"),
            )
            backend.append(records)
            result = backend.read_recent(10, layer_filter="L4_long")
            assert len(result) == 2
            assert all(r.layer == "L4_long" for r in result)

    def test_sqlite_no_filter_returns_all(self) -> None:
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            records = (
                _make_record("r1", layer=None),
                _make_record("r2", layer="L4_long"),
            )
            backend.append(records)
            result = backend.read_recent(10)
            assert len(result) == 2

    def test_experience_store_facade_forwards_layer_filter(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        store = ExperienceStore(backend=backend)
        records = (
            _make_record("r1", layer="L4_long"),
            _make_record("r2", layer="L3_short"),
        )
        store.initialize()
        store.append_records(records)
        result = store.read_recent(10, layer_filter="L4_long")
        assert len(result) == 1
        assert result[0].layer == "L4_long"


# ── search_similar with preferred_layers ──────────────────────────────


class TestSearchSimilarPreferredLayers:
    """search_similar with preferred_layers boosts preferred records."""

    def test_no_preferred_layers_same_as_pre_r100(self) -> None:
        """Without preferred_layers, ranking is pure cosine similarity."""
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer="L2_working", embedding=_VEC_SAME, sequence=1),
            _make_record("r2", layer="L4_long", embedding=_VEC_SAME, sequence=2),
        )
        backend.append(records)
        result = backend.search_similar(_QUERY_VECTOR, 2, 10)
        # Same embedding, same similarity — tie-break by sequence, most-recent first
        assert len(result.hits) == 2
        assert result.hits[0].record.sequence > result.hits[1].record.sequence

    def test_preferred_layers_boosts_l4_over_l2(self) -> None:
        """L4_long with same similarity beats L2_working when L4 is preferred."""
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer="L2_working", embedding=_VEC_SAME, sequence=1),
            _make_record("r2", layer="L4_long", embedding=_VEC_SAME, sequence=2),
        )
        backend.append(records)
        result = backend.search_similar(
            _QUERY_VECTOR, 2, 10,
            preferred_layers=("L4_long", "L5_autobiographical"),
        )
        # L4_long is boosted (effective similarity = 1.0 * 1.5 = 1.5)
        # L2_working is not boosted (effective similarity = 1.0)
        # L4 should rank first despite higher sequence
        assert result.hits[0].record.layer == "L4_long"

    def test_layer_none_records_receive_no_boost(self) -> None:
        """layer=None records are not boosted even when preferred_layers is set."""
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer=None, embedding=_VEC_SAME, sequence=1),
            _make_record("r2", layer="L4_long", embedding=_VEC_SAME, sequence=2),
        )
        backend.append(records)
        result = backend.search_similar(
            _QUERY_VECTOR, 2, 10,
            preferred_layers=("L4_long",),
        )
        assert result.hits[0].record.layer == "L4_long"

    def test_similarity_hit_stores_raw_cosine_not_boosted(self) -> None:
        """SimilarityHit.similarity must carry raw cosine, not the boosted value."""
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        records = (
            _make_record("r1", layer="L4_long", embedding=_VEC_SAME, sequence=1),
        )
        backend.append(records)
        result = backend.search_similar(
            _QUERY_VECTOR, 1, 10,
            preferred_layers=("L4_long",),
        )
        # The raw cosine similarity should be 1.0, NOT 1.5 (the boosted value)
        assert result.hits[0].similarity == 1.0

    def test_experience_store_facade_forwards_preferred_layers(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        store = ExperienceStore(backend=backend)
        records = (
            _make_record("r1", layer="L2_working", embedding=_VEC_SAME, sequence=1),
            _make_record("r2", layer="L4_long", embedding=_VEC_SAME, sequence=2),
        )
        store.initialize()
        store.append_records(records)
        result = store.search_similar(
            _QUERY_VECTOR, 2,
            preferred_layers=("L4_long", "L5_autobiographical"),
        )
        assert result.hits[0].record.layer == "L4_long"

    def test_sqlite_preferred_layers_boost(self) -> None:
        """SQLite backend also boosts preferred layers."""
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            records = (
                _make_record("r1", layer="L2_working", embedding=_VEC_SAME),
                _make_record("r2", layer="L4_long", embedding=_VEC_SAME),
            )
            backend.append(records)
            result = backend.search_similar(
                _QUERY_VECTOR, 2, 10,
                preferred_layers=("L4_long", "L5_autobiographical"),
            )
            assert result.hits[0].record.layer == "L4_long"


# ── Append preserves layer and memory_metadata ────────────────────────


class TestAppendPreservesLayerFields:
    """Appending records with layer/metadata preserves them through read-back."""

    def test_inmemory_append_preserves_layer(self) -> None:
        backend = InMemoryExperienceStoreBackend()
        backend.initialize()
        record = _make_record(layer="L4_long", memory_metadata={"k": "v"})
        stamped = backend.append((record,))
        assert stamped[0].layer == "L4_long"
        assert dict(stamped[0].memory_metadata) == {"k": "v"}

    def test_sqlite_append_preserves_layer(self) -> None:
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            record = _make_record(layer="L5_autobiographical", memory_metadata={"classifier": "v1"})
            stamped = backend.append((record,))
            assert stamped[0].layer == "L5_autobiographical"
            assert dict(stamped[0].memory_metadata) == {"classifier": "v1"}
            # Also verify read-back
            read_back = backend.read_recent(1)
            assert read_back[0].layer == "L5_autobiographical"
            assert dict(read_back[0].memory_metadata) == {"classifier": "v1"}

    def test_sqlite_append_layer_none_preserved(self) -> None:
        with tempfile.TemporaryDirectory(**_TMP_CLEANUP) as tmp:
            db = Path(tmp) / "test.db"
            backend = SqliteExperienceStoreBackend(db_path=str(db))
            backend.initialize()
            record = _make_record(layer=None)
            stamped = backend.append((record,))
            assert stamped[0].layer is None
