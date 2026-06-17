"""Owner: durable experience store.

Owns:
- the durable persisted-experience record contract
- the prior-existence snapshot contract
- the durable backend protocol boundary

Does not own:
- continuity classification (owned by `15` experience writeback)
- retrieval planning or ranking (owned by `10` directed retrieval)
- any cognitive runtime decision or salience judgment
- semantic similarity, embeddings, or vector ranking (requirement `34`)
- authoritative inter-owner state transport

This owner is infrastructure, like observability. It durably stores already-public owner
outputs and returns them in deterministic order. It never interprets the meaning of what it
stores and never makes a cognitive decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.memory.contracts import MemoryLayer, VALID_MEMORY_LAYERS


class PersistenceError(RuntimeError):
    """Hard-stop error raised when durable experience-store invariants or backends fail."""


# Sentinel sequence for a record that has not yet been assigned a store sequence. The store
# backend stamps a strictly-increasing positive sequence on append; a value of -1 means the
# record has been built but not yet persisted.
UNASSIGNED_SEQUENCE = -1


@dataclass(frozen=True)
class PersistedExperienceRecord:
    """Owner: durable experience store.

    Purpose:
        One immutable durable record of an experience-writeback continuity outcome. It is a
        flattened, storage-friendly projection of a `15` `ExperienceWritebackResult` plus its
        `ContinuityEvidencePacket`, preserving the upstream provenance linkage ids verbatim.

    Failure semantics:
        Construction raises `PersistenceError` on an empty `record_id`, `source_outcome_id`,
        `summary`, `continuity_kind`, `outcome_class`, `source_outcome_kind`, or
        `writeback_status`. The `linkage` mapping is frozen to an immutable view.

    Notes:
        Taxonomy-valued fields (`continuity_kind`, `outcome_class`, `source_outcome_kind`,
        `writeback_status`) are stored as opaque strings. This owner does not re-validate the
        `15` taxonomies; `15` remains their sole owner. This record carries no authority and
        is never an inter-owner decision transport.
    """

    record_id: str
    tick_id: int | None
    continuity_kind: str
    outcome_class: str
    source_outcome_kind: str
    source_outcome_id: str
    writeback_status: str
    summary: str
    requested_effect_summary: str
    applied_effect_summary: str
    reason_trace: tuple[str, ...]
    linkage: Mapping[str, str]
    sequence: int = UNASSIGNED_SEQUENCE
    embedding: tuple[float, ...] | None = None
    record_kind: str = "experience_writeback"
    metadata: Mapping[str, str] = field(default_factory=dict)
    created_at_wall: float | None = None
    layer: MemoryLayer | None = None             # R100: honest absence for legacy records
    memory_metadata: Mapping[str, str] = field(default_factory=dict)  # R100: opaque, 06-owned keys

    def __post_init__(self) -> None:
        for attr_name in (
            "record_id",
            "source_outcome_id",
            "summary",
            "continuity_kind",
            "outcome_class",
            "source_outcome_kind",
            "writeback_status",
            "record_kind",
        ):
            if not getattr(self, attr_name):
                raise PersistenceError(
                    f"PersistedExperienceRecord must declare a non-empty {attr_name}"
                )
        if any(not item for item in self.reason_trace):
            raise PersistenceError(
                "PersistedExperienceRecord reason_trace must not contain empty values"
            )
        linkage = MappingProxyType(dict(self.linkage))
        for key, value in linkage.items():
            if not key or not isinstance(value, str):
                raise PersistenceError(
                    "PersistedExperienceRecord linkage must map non-empty keys to string ids"
                )
        object.__setattr__(self, "linkage", linkage)
        metadata = MappingProxyType(dict(self.metadata))
        for key, value in metadata.items():
            if not key or not isinstance(value, str):
                raise PersistenceError(
                    "PersistedExperienceRecord metadata must map non-empty keys to string values"
                )
        object.__setattr__(self, "metadata", metadata)
        if self.embedding is not None:
            vector = tuple(float(component) for component in self.embedding)
            if not vector:
                raise PersistenceError(
                    "PersistedExperienceRecord embedding must be non-empty when present"
                )
            object.__setattr__(self, "embedding", vector)
        # R100: validate the optional `layer` field. None is honest absence (no classifier
        # was wired when the record was written, or the runtime read it back from an old
        # SQLite file written before R100). When present, it must be one of the 4-layer
        # taxonomy values.
        if self.layer is not None and self.layer not in VALID_MEMORY_LAYERS:
            raise PersistenceError(
                f"PersistedExperienceRecord.layer must be None or one of {sorted(VALID_MEMORY_LAYERS)}, got: {self.layer}"
            )
        # R100: validate and freeze `memory_metadata`. Same rule as `metadata` — non-empty
        # keys to string values. `33` does not interpret the keys; `06` owns their semantics.
        mem_meta = MappingProxyType(dict(self.memory_metadata))
        for key, value in mem_meta.items():
            if not key or not isinstance(value, str):
                raise PersistenceError(
                    "PersistedExperienceRecord memory_metadata must map non-empty keys to string values"
                )
        object.__setattr__(self, "memory_metadata", mem_meta)
        # R92: validate the optional `created_at_wall` field. None is honest absence (no
        # `WallClock` was wired when the record was written, or the runtime read it back from
        # an old SQLite file written before R92). When present, it must be a finite,
        # non-negative real number — the same invariant `WallClockReading` enforces upstream.
        if self.created_at_wall is not None:
            import math as _math

            value = self.created_at_wall
            if not isinstance(value, (int, float)):
                raise PersistenceError(
                    "PersistedExperienceRecord.created_at_wall must be a real number when present"
                )
            value = float(value)
            if _math.isnan(value) or _math.isinf(value) or value < 0.0:
                raise PersistenceError(
                    "PersistedExperienceRecord.created_at_wall must be finite and non-negative"
                )
            object.__setattr__(self, "created_at_wall", value)

    def with_sequence(self, sequence: int) -> "PersistedExperienceRecord":
        """Owner: durable experience store.

        Purpose:
            Return a copy of this record stamped with a store-assigned sequence.

        Inputs:
            `sequence` - a positive, strictly-increasing store-assigned sequence.

        Returns:
            A new `PersistedExperienceRecord` identical except for `sequence`.

        Raises:
            PersistenceError if `sequence` is not a positive integer.

        Notes:
            Backends call this when persisting a record so callers receive the stamped form.
        """

        if not isinstance(sequence, int) or sequence <= 0:
            raise PersistenceError("PersistedExperienceRecord sequence must be a positive integer")
        return PersistedExperienceRecord(
            record_id=self.record_id,
            tick_id=self.tick_id,
            continuity_kind=self.continuity_kind,
            outcome_class=self.outcome_class,
            source_outcome_kind=self.source_outcome_kind,
            source_outcome_id=self.source_outcome_id,
            writeback_status=self.writeback_status,
            summary=self.summary,
            requested_effect_summary=self.requested_effect_summary,
            applied_effect_summary=self.applied_effect_summary,
            reason_trace=self.reason_trace,
            linkage=dict(self.linkage),
            sequence=sequence,
            embedding=self.embedding,
            record_kind=self.record_kind,
            metadata=dict(self.metadata),
            created_at_wall=self.created_at_wall,
            layer=self.layer,
            memory_metadata=dict(self.memory_metadata),
        )

    def with_embedding(self, vector: tuple[float, ...]) -> "PersistedExperienceRecord":
        """Owner: durable experience store.

        Purpose:
            Return a copy of this record carrying a semantic embedding vector.

        Inputs:
            `vector` - a non-empty sequence of numeric components.

        Returns:
            A new `PersistedExperienceRecord` identical except for `embedding`.

        Raises:
            PersistenceError if `vector` is empty.

        Notes:
            The persistence owner stores the vector it is given; it never embeds text itself
            and never interprets the vector's meaning. The embedding is supplied by the
            embedding owner through composition.
        """

        if not vector:
            raise PersistenceError("PersistedExperienceRecord embedding vector must be non-empty")
        return PersistedExperienceRecord(
            record_id=self.record_id,
            tick_id=self.tick_id,
            continuity_kind=self.continuity_kind,
            outcome_class=self.outcome_class,
            source_outcome_kind=self.source_outcome_kind,
            source_outcome_id=self.source_outcome_id,
            writeback_status=self.writeback_status,
            summary=self.summary,
            requested_effect_summary=self.requested_effect_summary,
            applied_effect_summary=self.applied_effect_summary,
            reason_trace=self.reason_trace,
            linkage=dict(self.linkage),
            sequence=self.sequence,
            embedding=tuple(float(component) for component in vector),
            record_kind=self.record_kind,
            metadata=dict(self.metadata),
            created_at_wall=self.created_at_wall,
            layer=self.layer,
            memory_metadata=dict(self.memory_metadata),
        )


@dataclass(frozen=True)
class PriorExistenceSnapshot:
    """Owner: durable experience store.

    Purpose:
        A bounded, read-only summary of what the store already holds at startup, for
        diagnostics only.

    Failure semantics:
        Construction raises `PersistenceError` on a negative `total_record_count`.

    Notes:
        This snapshot carries no authority and is never consumed as cognitive state. It exists
        so a startup path can report "the system has a prior existence of N records" without
        loading the whole stream.
    """

    total_record_count: int
    most_recent_sequence: int | None
    most_recent_tick_id: int | None
    recent_summaries: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.total_record_count < 0:
            raise PersistenceError("PriorExistenceSnapshot total_record_count must be >= 0")


@dataclass(frozen=True)
class SimilarityHit:
    """Owner: durable experience store.

    Purpose:
        One ranked similarity-search hit: a persisted record and its cosine similarity to the
        query vector.

    Failure semantics:
        Construction raises `PersistenceError` when the record carries no embedding.
    """

    record: PersistedExperienceRecord
    similarity: float

    def __post_init__(self) -> None:
        if self.record.embedding is None:
            raise PersistenceError("SimilarityHit record must carry an embedding")


@dataclass(frozen=True)
class SimilaritySearchResult:
    """Owner: durable experience store.

    Purpose:
        The result of one bounded similarity search: the ranked hits plus diagnostic counts.

    Failure semantics:
        None beyond field assignment.

    Notes:
        `scanned_count` is the number of records examined within the bounded scan;
        `skipped_non_embedded_count` is how many of those carried no embedding and were
        excluded. Absence of an embedding is reported, never silently treated as similar or
        dissimilar.
    """

    hits: tuple[SimilarityHit, ...]
    scanned_count: int
    skipped_non_embedded_count: int


@runtime_checkable
class ExperienceStoreBackend(Protocol):
    """Owner: durable experience store.

    Purpose:
        The durable backend boundary behind which a concrete store (SQLite file, in-memory
        double) is injected. The `ExperienceStore` facade depends only on this protocol.

    Notes:
        Implementations must assign a strictly-increasing positive sequence on append and
        must return records ordered ascending by that sequence. They must raise
        `PersistenceError` on an unrecoverable durability failure and must never fabricate or
        silently drop records.
    """

    def initialize(self) -> None:
        """Owner: durable experience store.

        Purpose:
            Idempotently prepare the backend (create the table/file if absent).

        Inputs:
            None.

        Returns:
            None.

        Raises:
            PersistenceError if the backend cannot be initialized (for example an unwritable
            path).

        Notes:
            Must be safe to call more than once.
        """

    def append(
        self,
        records: tuple[PersistedExperienceRecord, ...],
    ) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store.

        Purpose:
            Durably persist a batch of records, assigning each a strictly-increasing sequence.

        Inputs:
            `records` - the records to persist, in intended order. May be empty.

        Returns:
            The stamped records (with assigned sequences), in the same order.

        Raises:
            PersistenceError on a durability failure.

        Notes:
            Append-only. Backends must not mutate or delete prior records.
        """

    def read_recent(
        self,
        limit: int,
        layer_filter: MemoryLayer | None = None,
    ) -> tuple[PersistedExperienceRecord, ...]:
        """Owner: durable experience store.

        Purpose:
            Return up to `limit` most-recent records, ordered ascending by sequence.
            When `layer_filter` is provided, only records whose `layer` matches the filter
            are returned. `layer=None` records (legacy / pre-R100) are excluded by a filter.

        Inputs:
            `limit` - a positive maximum record count.
            `layer_filter` - optional MemoryLayer filter (R100). None means no filter.

        Returns:
            Up to `limit` records, oldest-first among the most-recent window. Empty when the
            store is cold or no records match the filter.

        Raises:
            PersistenceError on `limit <= 0` or a read failure.

        Notes:
            Ordering is by store-assigned sequence and is independent of wall-clock time.
        """

    def count(self) -> int:
        """Owner: durable experience store.

        Purpose:
            Return the total number of persisted records.

        Inputs:
            None.

        Returns:
            The total count (>= 0).

        Raises:
            PersistenceError on a read failure.
        """

    def search_similar(
        self,
        query_vector: tuple[float, ...],
        limit: int,
        max_scan: int,
        preferred_layers: tuple[MemoryLayer, ...] | None = None,
    ) -> SimilaritySearchResult:
        """Owner: durable experience store.

        Purpose:
            Return up to `limit` embedded records most similar to `query_vector` by cosine
            similarity, scanning at most the `max_scan` most-recent records. When
            `preferred_layers` is provided, records whose `layer` is in the preferred set
            receive a boost via `layer_preference_weight` (R100, C_engineering_hypothesis).

        Inputs:
            `query_vector` - a non-empty query embedding.
            `limit` - a positive maximum number of hits to return.
            `max_scan` - a positive bound on the most-recent records examined.
            `preferred_layers` - optional tuple of MemoryLayer values to boost (R100).
                None means no boost (same as pre-R100 behavior).

        Returns:
            A `SimilaritySearchResult` with hits ranked by descending effective similarity
            (boosted for preferred layers, tie-break descending sequence), plus the scanned
            and skipped-non-embedded counts.

        Raises:
            PersistenceError on an empty query vector, a non-positive `limit`/`max_scan`, a
            dimension mismatch against a stored embedding, or a read failure.

        Notes:
            Only records carrying an embedding are ranked; non-embedded records within the
            scan are excluded and counted. Cost is bounded by `max_scan`; no external vector
            index is used. `layer=None` records receive no boost (legacy / pre-R100).
        """
