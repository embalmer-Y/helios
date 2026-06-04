from __future__ import annotations

import pytest

from helios_v2.directed_retrieval import RetrievalQueryPlan
from helios_v2.persistence import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    PersistedExperienceRecord,
    PersistenceError,
    SemanticStoreBackedDirectedMemoryCandidateProvider,
    SqliteExperienceStoreBackend,
    StoreBackedDirectedMemoryCandidateProvider,
    cosine_similarity,
)


def _record(seq_hint: int, *, continuity_kind: str = "external_action") -> PersistedExperienceRecord:
    return PersistedExperienceRecord(
        record_id=f"experience:writeback-result:{seq_hint}",
        tick_id=seq_hint,
        continuity_kind=continuity_kind,
        outcome_class="world_changed",
        source_outcome_kind="planner_bridge",
        source_outcome_id=f"planner-bridge-result:{seq_hint}",
        writeback_status="written",
        summary=f"experience {seq_hint}",
        requested_effect_summary="send reply",
        applied_effect_summary="reply sent",
        reason_trace=("planner accepted",),
        linkage={"source_request_id": f"planner-bridge-result:{seq_hint}"},
    )


def _plan() -> RetrievalQueryPlan:
    return RetrievalQueryPlan(
        plan_id="retrieval-plan:1",
        source_request_id="retrieval-request:1",
        query_text="recall prior experience",
        query_source="recall_intent",
        target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
        limit=2,
        retrieval_strategy="deterministic_first_version",
        tick_id=1,
    )


# --- In-memory backend + store facade ---


def test_in_memory_append_assigns_strictly_increasing_sequence() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    stamped = store.append_records((_record(1), _record(2)))
    assert [r.sequence for r in stamped] == [1, 2]
    more = store.append_records((_record(3),))
    assert more[0].sequence == 3
    assert store.count() == 3


def test_read_recent_returns_most_recent_ascending() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(tuple(_record(i) for i in range(1, 6)))
    recent = store.read_recent(3)
    # Most-recent 3 records, ascending by sequence.
    assert [r.sequence for r in recent] == [3, 4, 5]


def test_read_recent_rejects_non_positive_limit() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    with pytest.raises(PersistenceError, match="positive integer"):
        store.read_recent(0)


def test_empty_append_is_a_no_op() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    assert store.append_records(()) == ()
    assert store.count() == 0


def test_prior_existence_snapshot_on_cold_and_warm_store() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    cold = store.prior_existence_snapshot()
    assert cold.total_record_count == 0
    assert cold.most_recent_sequence is None
    assert cold.recent_summaries == ()

    store.append_records((_record(1), _record(2)))
    warm = store.prior_existence_snapshot(recent_limit=5)
    assert warm.total_record_count == 2
    assert warm.most_recent_sequence == 2
    assert warm.most_recent_tick_id == 2
    assert warm.recent_summaries == ("experience 1", "experience 2")


# --- SQLite backend durability ---


def test_sqlite_backend_round_trips_records(tmp_path) -> None:
    db_path = str(tmp_path / "experience_store.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    store.initialize()
    store.append_records((_record(1), _record(2, continuity_kind="internal_thought_cycle")))

    recent = store.read_recent(10)
    assert [r.sequence for r in recent] == [1, 2]
    assert recent[1].continuity_kind == "internal_thought_cycle"
    assert recent[0].linkage == {"source_request_id": "planner-bridge-result:1"}


def test_sqlite_durability_survives_reopen(tmp_path) -> None:
    db_path = str(tmp_path / "experience_store.sqlite3")
    first = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    first.append_records((_record(1), _record(2)))
    assert first.count() == 2

    # A brand-new store object on the same file must see the prior records.
    second = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    assert second.count() == 2
    recent = second.read_recent(10)
    assert [r.summary for r in recent] == ["experience 1", "experience 2"]
    # New appends continue the sequence rather than resetting.
    stamped = second.append_records((_record(3),))
    assert stamped[0].sequence == 3


def test_sqlite_initialize_is_idempotent(tmp_path) -> None:
    db_path = str(tmp_path / "experience_store.sqlite3")
    backend = SqliteExperienceStoreBackend(db_path=db_path)
    backend.initialize()
    backend.initialize()
    store = ExperienceStore(backend=backend)
    assert store.count() == 0


def test_sqlite_unwritable_path_fails_fast(tmp_path) -> None:
    # Make the parent path a regular file, so the store cannot create its directory/file
    # under it; initialize must fail fast with PersistenceError (no degraded path).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    db_path = str(blocker / "nested" / "experience_store.sqlite3")
    backend = SqliteExperienceStoreBackend(db_path=db_path)
    with pytest.raises(PersistenceError):
        backend.initialize()


# --- Store-backed directed-retrieval candidate provider ---


def test_store_backed_provider_maps_records_to_tiered_candidates() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(
        (
            _record(1, continuity_kind="external_action"),
            _record(2, continuity_kind="internal_thought_cycle"),
        )
    )
    provider = StoreBackedDirectedMemoryCandidateProvider(store=store)
    candidates = provider.collect_candidates(_plan())

    assert len(candidates) == 2
    assert all(c.source == "experience_store" for c in candidates)
    # external_action -> mid_term/episodic; internal_thought_cycle -> autobiographical.
    by_memory = {c.memory_id: c for c in candidates}
    assert by_memory["experience:1"].tier == "mid_term"
    assert by_memory["experience:1"].memory_type == "episodic"
    assert by_memory["experience:2"].tier == "autobiographical"
    assert by_memory["experience:2"].memory_type == "autobiographical"
    # Deterministic recency score: most-recent (seq 2) scores highest.
    assert by_memory["experience:2"].score == 1.0
    assert 0.0 < by_memory["experience:1"].score <= 1.0


def test_store_backed_provider_cold_store_returns_no_candidates() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    provider = StoreBackedDirectedMemoryCandidateProvider(store=store)
    assert provider.collect_candidates(_plan()) == ()


# --- Requirement 34: vector storage + semantic similarity search ---


def _embedded_record(seq_hint: int, vector: tuple[float, ...], *, continuity_kind: str = "external_action"):
    return _record(seq_hint, continuity_kind=continuity_kind).with_embedding(vector)


def test_cosine_similarity_basic_and_errors() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    with pytest.raises(PersistenceError, match="equal-length"):
        cosine_similarity((1.0, 0.0), (1.0,))
    with pytest.raises(PersistenceError, match="non-empty"):
        cosine_similarity((), (1.0,))
    with pytest.raises(PersistenceError, match="zero-norm"):
        cosine_similarity((0.0, 0.0), (1.0, 1.0))


def test_record_with_embedding_round_trips_in_sqlite(tmp_path) -> None:
    db_path = str(tmp_path / "experience_store.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    store.append_records((_embedded_record(1, (0.1, 0.2, 0.3)),))

    # Reopen the same file: the embedding vector must survive exactly.
    reopened = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    recent = reopened.read_recent(10)
    assert recent[0].embedding == pytest.approx((0.1, 0.2, 0.3))


def test_search_similar_ranks_near_above_far_in_memory() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(
        (
            _embedded_record(1, (1.0, 0.0, 0.0)),   # seq 1: aligned with query
            _embedded_record(2, (0.0, 1.0, 0.0)),   # seq 2: orthogonal to query
        )
    )
    result = store.search_similar((1.0, 0.0, 0.0), limit=2, max_scan=10)
    assert len(result.hits) == 2
    # The aligned record ranks first despite being older.
    assert result.hits[0].record.sequence == 1
    assert result.hits[0].similarity > result.hits[1].similarity
    assert result.skipped_non_embedded_count == 0


def test_search_similar_excludes_and_counts_non_embedded() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(
        (
            _embedded_record(1, (1.0, 0.0)),
            _record(2),  # no embedding
        )
    )
    result = store.search_similar((1.0, 0.0), limit=5, max_scan=10)
    assert len(result.hits) == 1
    assert result.hits[0].record.sequence == 1
    assert result.skipped_non_embedded_count == 1


def test_search_similar_honors_max_scan_bound() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(tuple(_embedded_record(i, (float(i), 1.0)) for i in range(1, 6)))
    # Only the most-recent 2 records are scanned.
    result = store.search_similar((1.0, 1.0), limit=5, max_scan=2)
    assert result.scanned_count == 2
    assert {hit.record.sequence for hit in result.hits} <= {4, 5}


def test_search_similar_dimension_mismatch_raises() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records((_embedded_record(1, (1.0, 0.0, 0.0)),))
    with pytest.raises(PersistenceError, match="equal-length"):
        store.search_similar((1.0, 0.0), limit=1, max_scan=10)


def test_semantic_provider_maps_hits_with_similarity_scores() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.append_records(
        (
            _embedded_record(1, (1.0, 0.0, 0.0)),
            _embedded_record(2, (0.0, 1.0, 0.0), continuity_kind="internal_thought_cycle"),
        )
    )

    def embed_query(text: str) -> tuple[float, ...]:
        del text
        return (1.0, 0.0, 0.0)

    provider = SemanticStoreBackedDirectedMemoryCandidateProvider(store=store, embed_query=embed_query)
    candidates = provider.collect_candidates(_plan())

    assert all(c.source == "experience_store_semantic" for c in candidates)
    # The aligned record (seq 1) ranks first with the highest score.
    assert candidates[0].memory_id == "experience:1"
    assert candidates[0].score >= candidates[-1].score


def test_semantic_provider_cold_store_returns_empty() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    provider = SemanticStoreBackedDirectedMemoryCandidateProvider(
        store=store, embed_query=lambda text: (1.0, 0.0)
    )
    assert provider.collect_candidates(_plan()) == ()
