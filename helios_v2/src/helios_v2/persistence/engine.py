"""Owner: durable experience store.

Provides the `ExperienceStore` facade, the first-version SQLite file backend, a deterministic
in-memory backend double, and the store-backed directed-retrieval candidate provider.

The store is infrastructure: it durably appends already-public owner outputs and returns them
in deterministic recency order. It holds no cognitive policy, ranks nothing by meaning, and
makes no runtime decision. Semantic retrieval (embeddings, vectors) is requirement `34`.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from helios_v2.directed_retrieval import (
    DirectedMemoryCandidateProvider,
    MemoryRetrievalCandidate,
    RetrievalQueryPlan,
    ThoughtWindowTier,
)

from .contracts import (
    ExperienceStoreBackend,
    PersistedExperienceRecord,
    PersistenceError,
    PriorExistenceSnapshot,
    SimilarityHit,
    SimilaritySearchResult,
)

# Continuity kinds whose persisted experience maps to the autobiographical tier. Everything
# else maps to the episodic tier. This is a transport mapping by stored kind, not a semantic
# ranking: the store never reads content for meaning.
_AUTOBIOGRAPHICAL_CONTINUITY_KINDS = frozenset(
    {
        "identity_change",
        "blocked_identity_change",
        "internal_thought_cycle",
    }
)

# Default number of most-recent records the store-backed candidate provider surfaces per plan.
_DEFAULT_PROVIDER_LIMIT = 8

# Default bound on the most-recent embedded records a semantic search scans per query. Keeps
# brute-force cosine cost bounded and deterministic without an external vector index.
_DEFAULT_MAX_SCAN = 256


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Owner: durable experience store.

    Purpose:
        Compute the cosine similarity between two equal-length vectors.

    Inputs:
        `a`, `b` - non-empty numeric vectors of equal length.

    Returns:
        The cosine similarity in the range [-1.0, 1.0].

    Raises:
        PersistenceError on an empty vector, a length mismatch, or a zero-norm vector.

    Notes:
        Standard-library math only; no numpy. This is the single ranking primitive over
        vectors the store is given; the store never embeds text itself.
    """

    if not a or not b:
        raise PersistenceError("cosine_similarity requires non-empty vectors")
    if len(a) != len(b):
        raise PersistenceError(
            f"cosine_similarity requires equal-length vectors: {len(a)} != {len(b)}"
        )
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for component_a, component_b in zip(a, b):
        dot += component_a * component_b
        norm_a += component_a * component_a
        norm_b += component_b * component_b
    if norm_a <= 0.0 or norm_b <= 0.0:
        raise PersistenceError("cosine_similarity is undefined for a zero-norm vector")
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _rank_similar(
    records: Sequence[PersistedExperienceRecord],
    query_vector: tuple[float, ...],
    limit: int,
) -> SimilaritySearchResult:
    """Owner: durable experience store.

    Rank the embedded records in `records` by cosine similarity to `query_vector`, returning
    the top `limit`. Records without an embedding are excluded and counted. Tie-break is
    descending similarity then descending sequence (more-recent wins ties). `records` is the
    already-bounded scan window the backend selected.
    """

    if not query_vector:
        raise PersistenceError("search_similar requires a non-empty query_vector")
    if not isinstance(limit, int) or limit <= 0:
        raise PersistenceError("search_similar limit must be a positive integer")
    skipped = 0
    scored: list[SimilarityHit] = []
    for record in records:
        if record.embedding is None:
            skipped += 1
            continue
        similarity = cosine_similarity(query_vector, record.embedding)
        scored.append(SimilarityHit(record=record, similarity=similarity))
    scored.sort(key=lambda hit: (hit.similarity, hit.record.sequence), reverse=True)
    return SimilaritySearchResult(
        hits=tuple(scored[:limit]),
        scanned_count=len(records),
        skipped_non_embedded_count=skipped,
    )


@dataclass
class InMemoryExperienceStoreBackend(ExperienceStoreBackend):
    """Owner: durable experience store.

    Purpose:
        A deterministic, list-backed backend double for tests and offline runs. Same sequence
        and ordering semantics as the durable SQLite backend, but with no file.

    Failure semantics:
        Raises `PersistenceError` on a non-positive `read_recent` limit. Append is total.

    Notes:
        Not durable across processes; for restart-continuity behavior use the SQLite backend.
    """

    _records: list[PersistedExperienceRecord] = field(default_factory=list)
    _sequence: int = 0

    def initialize(self) -> None:
        """Owner: durable experience store. Idempotent no-op for the in-memory backend."""

        return None

    def append(
        self,
        records: tuple[PersistedExperienceRecord, ...],
    ) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store. Append a batch, stamping increasing sequences."""

        stamped: list[PersistedExperienceRecord] = []
        for record in records:
            self._sequence += 1
            stamped_record = record.with_sequence(self._sequence)
            self._records.append(stamped_record)
            stamped.append(stamped_record)
        return tuple(stamped)

    def read_recent(self, limit: int) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store. Return the most-recent `limit` records, ascending."""

        if not isinstance(limit, int) or limit <= 0:
            raise PersistenceError("read_recent limit must be a positive integer")
        if not self._records:
            return ()
        window = self._records[-limit:]
        return tuple(window)

    def count(self) -> int:
        """Owner: durable experience store. Return the total persisted record count."""

        return len(self._records)

    def search_similar(
        self,
        query_vector: tuple[float, ...],
        limit: int,
        max_scan: int,
    ) -> SimilaritySearchResult:
        """Owner: durable experience store. Rank the most-recent embedded records by cosine."""

        if not isinstance(max_scan, int) or max_scan <= 0:
            raise PersistenceError("search_similar max_scan must be a positive integer")
        window = self._records[-max_scan:] if self._records else []
        return _rank_similar(window, query_vector, limit)


@dataclass
class SqliteExperienceStoreBackend(ExperienceStoreBackend):
    """Owner: durable experience store.

    Purpose:
        The first-version durable backend: a local SQLite file (standard library, no new
        dependency). Records survive process exit and re-open of the same file.

    Failure semantics:
        Wraps any `sqlite3.Error` (including an unwritable path) in `PersistenceError`. Never
        fabricates or drops records.

    Notes:
        `reason_trace` and `linkage` are JSON-encoded columns. The integer primary key
        (`AUTOINCREMENT`) provides the strictly-increasing store sequence. Each call opens and
        closes its own connection so the backend holds no long-lived handle.
    """

    db_path: str
    _initialized: bool = False

    _TABLE = "experience_records"

    def _connect(self) -> sqlite3.Connection:
        try:
            path = Path(self.db_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(self.db_path)
        except (sqlite3.Error, OSError, ValueError) as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend could not open '{self.db_path}': {error}"
            ) from error

    def initialize(self) -> None:
        """Owner: durable experience store. Create the records table if absent (idempotent)."""

        try:
            with self._connect() as connection:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._TABLE} (
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
                        embedding TEXT
                    )
                    """
                )
                connection.commit()
            self._initialized = True
        except sqlite3.Error as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend could not initialize '{self.db_path}': {error}"
            ) from error

    def append(
        self,
        records: tuple[PersistedExperienceRecord, ...],
    ) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store. Durably insert a batch, returning stamped records."""

        if not records:
            return ()
        if not self._initialized:
            self.initialize()
        stamped: list[PersistedExperienceRecord] = []
        try:
            with self._connect() as connection:
                for record in records:
                    cursor = connection.execute(
                        f"""
                        INSERT INTO {self._TABLE} (
                            record_id, tick_id, continuity_kind, outcome_class,
                            source_outcome_kind, source_outcome_id, writeback_status,
                            summary, requested_effect_summary, applied_effect_summary,
                            reason_trace, linkage, embedding
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.record_id,
                            record.tick_id,
                            record.continuity_kind,
                            record.outcome_class,
                            record.source_outcome_kind,
                            record.source_outcome_id,
                            record.writeback_status,
                            record.summary,
                            record.requested_effect_summary,
                            record.applied_effect_summary,
                            json.dumps(list(record.reason_trace)),
                            json.dumps(dict(record.linkage)),
                            json.dumps(list(record.embedding)) if record.embedding is not None else None,
                        ),
                    )
                    assigned = cursor.lastrowid
                    if not isinstance(assigned, int) or assigned <= 0:
                        raise PersistenceError(
                            "SqliteExperienceStoreBackend did not receive a valid row sequence"
                        )
                    stamped.append(record.with_sequence(assigned))
                connection.commit()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend append failed for '{self.db_path}': {error}"
            ) from error
        return tuple(stamped)

    def read_recent(self, limit: int) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store. Read the most-recent `limit` records, ascending."""

        if not isinstance(limit, int) or limit <= 0:
            raise PersistenceError("read_recent limit must be a positive integer")
        if not self._initialized:
            self.initialize()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT sequence, record_id, tick_id, continuity_kind, outcome_class,
                           source_outcome_kind, source_outcome_id, writeback_status, summary,
                           requested_effect_summary, applied_effect_summary, reason_trace, linkage,
                           embedding
                    FROM {self._TABLE}
                    ORDER BY sequence DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend read failed for '{self.db_path}': {error}"
            ) from error
        # Rows arrive most-recent-first; reverse to ascending-by-sequence for the caller.
        return tuple(self._row_to_record(row) for row in reversed(rows))

    def count(self) -> int:
        """Owner: durable experience store. Return the total persisted record count."""

        if not self._initialized:
            self.initialize()
        try:
            with self._connect() as connection:
                row = connection.execute(f"SELECT COUNT(*) FROM {self._TABLE}").fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend count failed for '{self.db_path}': {error}"
            ) from error
        return int(row[0]) if row else 0

    def search_similar(
        self,
        query_vector: tuple[float, ...],
        limit: int,
        max_scan: int,
    ) -> SimilaritySearchResult:
        """Owner: durable experience store. Rank the most-recent embedded rows by cosine."""

        if not isinstance(max_scan, int) or max_scan <= 0:
            raise PersistenceError("search_similar max_scan must be a positive integer")
        # Bounded scan: read the most-recent max_scan records (ascending), then rank in Python.
        window = self.read_recent(max_scan)
        return _rank_similar(window, query_vector, limit)

    def _row_to_record(self, row: Sequence[object]) -> PersistedExperienceRecord:
        try:
            reason_trace = tuple(json.loads(row[11]))
            linkage = dict(json.loads(row[12]))
            embedding = tuple(json.loads(row[13])) if row[13] is not None else None
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise PersistenceError(
                f"SqliteExperienceStoreBackend found a corrupt row in '{self.db_path}': {error}"
            ) from error
        return PersistedExperienceRecord(
            record_id=str(row[1]),
            tick_id=row[2] if row[2] is None else int(row[2]),
            continuity_kind=str(row[3]),
            outcome_class=str(row[4]),
            source_outcome_kind=str(row[5]),
            source_outcome_id=str(row[6]),
            writeback_status=str(row[7]),
            summary=str(row[8]),
            requested_effect_summary=str(row[9]),
            applied_effect_summary=str(row[10]),
            reason_trace=reason_trace,
            linkage=linkage,
            sequence=int(row[0]),
            embedding=embedding,
        )


@dataclass
class ExperienceStore:
    """Owner: durable experience store.

    Purpose:
        The public facade over an injected durable backend. It appends experience records,
        reads the most-recent window in deterministic order, counts records, and builds a
        bounded prior-existence snapshot.

    Failure semantics:
        Delegates durability to the backend, which raises `PersistenceError` on failure.
        `read_recent`/`prior_existence_snapshot` raise `PersistenceError` on a non-positive
        limit.

    Notes:
        The facade performs no ranking and no cognitive judgment. Ordering is by the backend's
        store-assigned sequence.
    """

    backend: ExperienceStoreBackend

    def initialize(self) -> None:
        """Owner: durable experience store.

        Purpose:
            Idempotently prepare the durable backend before any append or read.

        Raises:
            PersistenceError if the backend cannot be initialized.
        """

        self.backend.initialize()

    def append_records(
        self,
        records: tuple[PersistedExperienceRecord, ...],
    ) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store.

        Purpose:
            Durably append a bounded batch of experience records.

        Inputs:
            `records` - the records to persist; an empty batch is a no-op.

        Returns:
            The stamped records (with store-assigned sequences).

        Raises:
            PersistenceError on a durability failure.
        """

        if not records:
            return ()
        return self.backend.append(records)

    def read_recent(self, limit: int) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store.

        Purpose:
            Return up to `limit` most-recent records, ascending by store sequence.

        Inputs:
            `limit` - a positive maximum record count.

        Returns:
            Up to `limit` records; empty when the store is cold.

        Raises:
            PersistenceError on a non-positive limit or a read failure.
        """

        if not isinstance(limit, int) or limit <= 0:
            raise PersistenceError("ExperienceStore.read_recent limit must be a positive integer")
        return self.backend.read_recent(limit)

    def search_similar(
        self,
        query_vector: tuple[float, ...],
        limit: int,
        max_scan: int = _DEFAULT_MAX_SCAN,
    ) -> SimilaritySearchResult:
        """Owner: durable experience store.

        Purpose:
            Return up to `limit` embedded records most similar to `query_vector`, scanning at
            most the `max_scan` most-recent records.

        Inputs:
            `query_vector` - a non-empty query embedding.
            `limit` - a positive maximum number of hits.
            `max_scan` - a positive bound on the most-recent records examined.

        Returns:
            A `SimilaritySearchResult` ranked by descending similarity (tie-break descending
            sequence), with scanned and skipped-non-embedded counts.

        Raises:
            PersistenceError on an empty query vector, a non-positive limit/max_scan, a
            dimension mismatch, or a read failure.
        """

        if not query_vector:
            raise PersistenceError("ExperienceStore.search_similar requires a non-empty query_vector")
        if not isinstance(limit, int) or limit <= 0:
            raise PersistenceError("ExperienceStore.search_similar limit must be a positive integer")
        if not isinstance(max_scan, int) or max_scan <= 0:
            raise PersistenceError("ExperienceStore.search_similar max_scan must be a positive integer")
        return self.backend.search_similar(query_vector, limit, max_scan)

    def count(self) -> int:
        """Owner: durable experience store.

        Purpose:
            Return the total number of persisted records.

        Returns:
            The total count (>= 0).

        Raises:
            PersistenceError on a read failure.
        """

        return self.backend.count()

    def prior_existence_snapshot(self, recent_limit: int = 5) -> PriorExistenceSnapshot:
        """Owner: durable experience store.

        Purpose:
            Build a bounded read-only summary of the prior existence held in the store.

        Inputs:
            `recent_limit` - a positive bound on the number of recent summaries included.

        Returns:
            A `PriorExistenceSnapshot` carrying the total count, the most-recent sequence and
            tick id, and a bounded tail of recent summaries.

        Raises:
            PersistenceError on a non-positive limit or a read failure.

        Notes:
            Diagnostics only. The snapshot carries no authority and is not cognitive state.
        """

        if not isinstance(recent_limit, int) or recent_limit <= 0:
            raise PersistenceError(
                "ExperienceStore.prior_existence_snapshot recent_limit must be a positive integer"
            )
        total = self.backend.count()
        if total == 0:
            return PriorExistenceSnapshot(
                total_record_count=0,
                most_recent_sequence=None,
                most_recent_tick_id=None,
                recent_summaries=(),
            )
        recent = self.backend.read_recent(recent_limit)
        most_recent = recent[-1]
        return PriorExistenceSnapshot(
            total_record_count=total,
            most_recent_sequence=most_recent.sequence,
            most_recent_tick_id=most_recent.tick_id,
            recent_summaries=tuple(record.summary for record in recent),
        )


@dataclass
class StoreBackedDirectedMemoryCandidateProvider(DirectedMemoryCandidateProvider):
    """Owner: durable experience store.

    Purpose:
        Surface persisted experience records as directed-retrieval memory candidates, so the
        `10` owner can retrieve real prior experience (including a prior session's experience
        after a restart) instead of fabricated shim candidates.

    Failure semantics:
        Propagates `PersistenceError` from the store on a read failure. A cold store yields no
        candidates explicitly; it never fabricates.

    Notes:
        Selection is deterministic recency only: the most-recent records are mapped to memory
        candidates with a recency-rank score. There is no semantic ranking, embedding, or
        vector similarity here; that is requirement `34`. The store-assigned continuity kind
        chooses the tier (autobiographical vs episodic); content is never read for meaning.
    """

    store: ExperienceStore
    limit: int = _DEFAULT_PROVIDER_LIMIT

    def collect_candidates(self, plan: RetrievalQueryPlan) -> tuple[MemoryRetrievalCandidate, ...]:
        """Owner: durable experience store.

        Purpose:
            Return bounded memory candidates derived from the most-recent persisted experience.

        Inputs:
            `plan` - the directed-retrieval query plan (used for stable candidate-id provenance).

        Returns:
            Up to `limit` `MemoryRetrievalCandidate` values, or an empty tuple for a cold store.

        Raises:
            PersistenceError on a store read failure.

        Notes:
            The `10` owner still owns retrieval planning and thought-window shaping; this only
            supplies the candidate set, replacing the fabricating shim when persistence is on.
        """

        records = self.store.read_recent(self.limit)
        if not records:
            return ()
        candidates: list[MemoryRetrievalCandidate] = []
        total = len(records)
        for rank, record in enumerate(records):
            # Deterministic recency score in (0, 1]: the most-recent record (last in ascending
            # order) scores highest. This is a transport recency rank, not a semantic score.
            recency_score = round((rank + 1) / total, 4)
            tier, memory_type = _record_tier(record)
            candidates.append(
                MemoryRetrievalCandidate(
                    candidate_id=f"experience-candidate:{plan.plan_id}:{record.sequence}",
                    tier=tier,
                    memory_id=f"experience:{record.sequence}",
                    memory_type=memory_type,
                    summary=record.summary,
                    score=recency_score,
                    source="experience_store",
                    tags=(record.continuity_kind, record.outcome_class),
                )
            )
        return tuple(candidates)


def _record_tier(record: PersistedExperienceRecord) -> tuple[ThoughtWindowTier, str]:
    """Owner: durable experience store. Map a record's stored continuity kind to a tier.

    This is a transport mapping by stored kind, not a semantic judgment; content is never
    read for meaning. Returns the thought-window tier and the candidate memory_type.
    """

    if record.continuity_kind in _AUTOBIOGRAPHICAL_CONTINUITY_KINDS:
        return "autobiographical", "autobiographical"
    return "mid_term", "episodic"


@dataclass
class SemanticStoreBackedDirectedMemoryCandidateProvider(DirectedMemoryCandidateProvider):
    """Owner: durable experience store.

    Purpose:
        Surface persisted experience records as directed-retrieval candidates ranked by
        semantic similarity to the current retrieval query, so the `10` owner recalls
        experience that is relevant to the current cycle (including a prior session's
        experience after a restart), not merely the most recent.

    Failure semantics:
        Propagates `PersistenceError` from the store and any embedding error from the injected
        `embed_query` callable as a hard stop. A cold or all-non-embedded store yields no
        candidates explicitly; it never fabricates and never falls back to recency.

    Notes:
        The query-embedding capability is injected as `embed_query` (a `Callable[[str], tuple
        [float, ...]]`), so the persistence owner stays free of any embedding-owner import.
        Composition binds `embed_query` to the embedding gateway. Ranking is cosine similarity
        over stored vectors; the store-assigned continuity kind chooses the tier.
    """

    store: ExperienceStore
    embed_query: Callable[[str], tuple[float, ...]]
    limit: int = _DEFAULT_PROVIDER_LIMIT
    max_scan: int = _DEFAULT_MAX_SCAN

    def collect_candidates(self, plan: RetrievalQueryPlan) -> tuple[MemoryRetrievalCandidate, ...]:
        """Owner: durable experience store.

        Purpose:
            Return candidates derived from the experience most semantically similar to the
            plan's query text.

        Inputs:
            `plan` - the directed-retrieval query plan; its `query_text` is embedded.

        Returns:
            Up to `limit` `MemoryRetrievalCandidate` values ranked by similarity, or an empty
            tuple when the store holds no embedded records.

        Raises:
            PersistenceError on a store read failure; any embedding error propagates as a hard
            stop (no recency fallback).

        Notes:
            The `10` owner still owns retrieval planning and thought-window shaping; this only
            supplies the semantically-ranked candidate set when semantic memory is enabled.
        """

        query_vector = self.embed_query(plan.query_text)
        result = self.store.search_similar(query_vector, self.limit, self.max_scan)
        if not result.hits:
            return ()
        candidates: list[MemoryRetrievalCandidate] = []
        for hit in result.hits:
            record = hit.record
            tier, memory_type = _record_tier(record)
            # Clamp the cosine similarity into the [0, 1] candidate score range; negative
            # similarities are floored to 0 (a non-relevant memory, not a forbidden value).
            score = round(min(1.0, max(0.0, hit.similarity)), 4)
            candidates.append(
                MemoryRetrievalCandidate(
                    candidate_id=f"experience-candidate:{plan.plan_id}:{record.sequence}",
                    tier=tier,
                    memory_id=f"experience:{record.sequence}",
                    memory_type=memory_type,
                    summary=record.summary,
                    score=score,
                    source="experience_store_semantic",
                    tags=(record.continuity_kind, record.outcome_class),
                )
            )
        return tuple(candidates)

