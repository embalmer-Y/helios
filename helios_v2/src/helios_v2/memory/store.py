"""Owner: 06 memory (R85 Track A - store layer).

Owns:
- the runtime-accessible R85 `MemoryRecord` persistence surface
- in-process record lookup, soft-delete, and recall-count mutation
- layer-preserving query/filter for the memory_tool_channel sub-drivers

Does not own:
- durable on-disk persistence (no SQLite; R85 store is in-memory)
- cross-process record sharing
- legacy `PersistedExperienceRecord` storage (owner 33 persistence)
- L18 governance policy (owner 14 identity governance; consults but does not decide)

This module is OPT-IN: nothing in the runtime kernel reaches into it.
The store is wired in only when the caller asks for `memory_tool_channel=True`
in `assemble_runtime()` (R85 Phase 1 T17).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from .contracts import (
    MemoryAffectReplayError,
    MemoryLayer,
    MemoryRecord,
)


# =============================================================================
# Errors (hard-stop, no fallback per R79 fail-fast policy)
# =============================================================================


class MemoryRecordStoreError(MemoryAffectReplayError):
    """Raised on any R85 store invariant violation (duplicate id, unknown id, ...)."""


# =============================================================================
# Protocol
# =============================================================================


@runtime_checkable
@dataclass(frozen=True)
class R85MemoryStoreBackend(Protocol):
    """R85 `MemoryRecord` store backend boundary.

    Owner: 06 memory (R85 Track A).

    Purpose:
        Provide the runtime-accessible surface for reading, writing, and
        mutating `MemoryRecord` instances. Implementations must be safe under
        the runtime kernel's single-threaded tick execution model. Cross-process
        or persistent durability is explicitly out of scope.

    Failure semantics:
        All invariant violations raise `MemoryRecordStoreError`. The store
        never silently drops a record and never fabricates one.

    Notes:
        - `append` is idempotent on `record_id` (a duplicate id is a hard error).
        - `increment_recall` mutates and returns a new immutable record; the
          call site must store the returned value if it needs the promoted
          version.
        - Soft-deleted records are excluded from `list()` by default; the
          store keeps them for audit until the GC job runs (R86+).
    """

    def append(self, record: MemoryRecord) -> None:
        """Owner: 06 memory.

        Purpose:
            Persist a new `MemoryRecord`. The store assigns no implicit id;
            `record.record_id` must already be set by the caller.

        Inputs:
            record: a fully-constructed, validated `MemoryRecord`.

        Returns:
            None.

        Raises:
            MemoryRecordStoreError: if a record with the same `record_id`
                already exists.
        """
        ...

    def get(self, record_id: str) -> MemoryRecord | None:
        """Owner: 06 memory.

        Purpose:
            Look up a single record by id. Soft-deleted records are
            returned if and only if the caller asks for them implicitly
            (default returns them too, for audit access).

        Inputs:
            record_id: a non-empty string id.

        Returns:
            The current `MemoryRecord` (which may have been mutated by
            subsequent `increment_recall` calls) or `None` if no such id.

        Raises:
            MemoryRecordStoreError: if `record_id` is empty.
        """
        ...

    def list(
        self,
        *,
        layer: MemoryLayer | None = None,
        include_soft_deleted: bool = False,
    ) -> tuple[MemoryRecord, ...]:
        """Owner: 06 memory.

        Purpose:
            Enumerate records, optionally filtered by layer. The returned
            tuple is ordered by `created_at_tick` ascending (the temporal
            order the store saw them).

        Inputs:
            layer: optional filter; `None` returns all layers.
            include_soft_deleted: if `False` (default), soft-deleted records
                are filtered out.

        Returns:
            A tuple of `MemoryRecord` instances.

        Raises:
            None expected; this is a read-only operation.
        """
        ...

    def increment_recall(self, record_id: str, *, at_wall: float) -> MemoryRecord:
        """Owner: 06 memory.

        Purpose:
            Bump `recall_count` and `last_recall_at_wall` on a record, then
            run the consolidation `promote_layer` rule on the updated
            record. The returned record is the post-promotion version
            (which may be the same object if no promotion triggered).

        Inputs:
            record_id: a non-empty string id.
            at_wall: monotonic wall-clock seconds; must be >= the record's
                `last_recall_at_wall` (or `created_at_wall` for first recall).

        Returns:
            The post-promotion `MemoryRecord` (immutable new instance if
            promotion triggered, else the same record).

        Raises:
            MemoryRecordStoreError: if `record_id` is unknown or
                `at_wall` is older than the last recall.
        """
        ...

    def soft_delete(self, record_id: str, *, at_wall: float, reason: str) -> MemoryRecord:
        """Owner: 06 memory.

        Purpose:
            Mark a record as soft-deleted (sets `soft_deleted_at`, retains
            the record in storage for audit, and excludes it from
            `list()` unless `include_soft_deleted=True`).

        Inputs:
            record_id: a non-empty string id.
            at_wall: monotonic wall-clock seconds.
            reason: free-text justification; appended to the record's
                `audit_trail`.

        Returns:
            The new soft-deleted `MemoryRecord` (immutable).

        Raises:
            MemoryRecordStoreError: if `record_id` is unknown or the
                record is already soft-deleted.
        """
        ...

    def search_by_keyword(
        self,
        query: str,
        *,
        limit: int = 5,
        min_keyword_hits: int = 1,
    ) -> tuple[MemoryRecord, ...]:
        """Owner: 06 memory.

        Purpose:
            Naive keyword search across `summary`, `tags`, and
            `context_keywords`. Used by the owner 31 `memory_replay`
            sub-driver (T18) when the LLM asks for recall without a
            specific record id hint.

        Inputs:
            query: free-text query; whitespace is normalized.
            limit: maximum number of records to return; must be > 0.
            min_keyword_hits: minimum number of distinct keyword matches
                a record must have to qualify.

        Returns:
            Up to `limit` matching records, ordered by hit count desc
            then `created_at_tick` desc.

        Raises:
            MemoryRecordStoreError: if `limit` <= 0.
        """
        ...


# =============================================================================
# In-memory implementation
# =============================================================================


class InMemoryR85MemoryStore:
    """R85 `MemoryRecord` in-memory store.

    Owner: 06 memory (R85 Track A).

    Purpose:
        Default R85 store backend. Holds records in a dict protected by
        a single re-entrant lock (the runtime tick is single-threaded but
        tests may fire concurrent calls). All returned records are
        immutable `MemoryRecord` instances; mutations return new records.

    Inputs to `__init__`: none (the store starts empty).

    Failure semantics:
        All hard-stop conditions raise `MemoryRecordStoreError`. The store
        never silently drops, fabricates, or coerces a record.

    Notes:
        - Not durable: state vanishes on process exit. R86+ may add
          SQLite-backed backend following the owner 33 pattern.
        - Not thread-safe across processes: a single in-process dict
          is the only state.
        - Promotion is delegated to `memory.engine.promote_layer`; this
          store never inlines the layer rule.
    """

    def __init__(self) -> None:
        # record_id -> MemoryRecord (current version)
        self._records: dict[str, MemoryRecord] = {}
        self._lock = threading.RLock()

    # -- Protocol compliance: append ---------------------------------------

    def append(self, record: MemoryRecord) -> None:
        with self._lock:
            if not record.record_id:
                raise MemoryRecordStoreError("record_id must be non-empty")
            if record.record_id in self._records:
                raise MemoryRecordStoreError(
                    f"record_id {record.record_id!r} already exists in store"
                )
            self._records[record.record_id] = record

    # -- Protocol compliance: get ------------------------------------------

    def get(self, record_id: str) -> MemoryRecord | None:
        if not record_id:
            raise MemoryRecordStoreError("record_id must be non-empty")
        with self._lock:
            return self._records.get(record_id)

    # -- Protocol compliance: list -----------------------------------------

    def list(
        self,
        *,
        layer: MemoryLayer | None = None,
        include_soft_deleted: bool = False,
    ) -> tuple[MemoryRecord, ...]:
        with self._lock:
            snapshot = sorted(
                self._records.values(),
                key=lambda r: r.created_at_tick,
            )
        out: list[MemoryRecord] = []
        for r in snapshot:
            if layer is not None and r.layer != layer:
                continue
            if not include_soft_deleted and r.soft_deleted_at is not None:
                continue
            out.append(r)
        return tuple(out)

    # -- Protocol compliance: increment_recall -----------------------------

    def increment_recall(self, record_id: str, *, at_wall: float) -> MemoryRecord:
        if not record_id:
            raise MemoryRecordStoreError("record_id must be non-empty")
        # Import here to avoid a top-level import cycle and to keep the
        # store importable without pulling engine.py.
        from .engine import promote_layer

        with self._lock:
            current = self._records.get(record_id)
            if current is None:
                raise MemoryRecordStoreError(
                    f"record_id {record_id!r} is unknown to the store"
                )
            if current.soft_deleted_at is not None:
                raise MemoryRecordStoreError(
                    f"record_id {record_id!r} is soft-deleted; cannot recall"
                )
            last_wall = (
                current.last_recall_at_wall
                if current.last_recall_at_wall is not None
                else current.created_at_wall
            )
            if at_wall < last_wall:
                raise MemoryRecordStoreError(
                    f"at_wall={at_wall} is older than last_recall_at_wall={last_wall}"
                )
            bumped = MemoryRecord(
                record_id=current.record_id,
                tick_id=current.tick_id,
                continuity_kind=current.continuity_kind,
                outcome_class=current.outcome_class,
                summary=current.summary,
                layer=current.layer,
                objective_importance=current.objective_importance,
                llm_remember_decision=current.llm_remember_decision,
                double_confirmation_class=current.double_confirmation_class,
                hormone_snapshot=current.hormone_snapshot,
                feeling_snapshot=current.feeling_snapshot,
                created_at_tick=current.created_at_tick,
                created_at_wall=current.created_at_wall,
                last_recall_at_wall=at_wall,
                recall_count=current.recall_count + 1,
                is_consolidated=current.is_consolidated,
                soft_deleted_at=current.soft_deleted_at,
                memory_gc_after=current.memory_gc_after,
                audit_trail=current.audit_trail,
                tags=current.tags,
                context_keywords=current.context_keywords,
                cross_links=current.cross_links,
            )
            promoted = promote_layer(bumped)
            self._records[record_id] = promoted
            return promoted

    # -- Protocol compliance: soft_delete -----------------------------------

    def soft_delete(self, record_id: str, *, at_wall: float, reason: str) -> MemoryRecord:
        if not record_id:
            raise MemoryRecordStoreError("record_id must be non-empty")
        if not reason:
            raise MemoryRecordStoreError("soft_delete reason must be non-empty")
        with self._lock:
            current = self._records.get(record_id)
            if current is None:
                raise MemoryRecordStoreError(
                    f"record_id {record_id!r} is unknown to the store"
                )
            if current.soft_deleted_at is not None:
                raise MemoryRecordStoreError(
                    f"record_id {record_id!r} is already soft-deleted"
                )
            if at_wall < current.created_at_wall:
                raise MemoryRecordStoreError(
                    f"at_wall={at_wall} is older than created_at_wall={current.created_at_wall}"
                )
            # GC after 7 days (in seconds). 604800 = 7 * 24 * 3600.
            gc_after = at_wall + 604800.0
            audit_entry: tuple[Mapping[str, str], ...] = current.audit_trail + (
                {"event": "soft_delete", "at_wall": str(at_wall), "reason": reason},
            )
            new_record = MemoryRecord(
                record_id=current.record_id,
                tick_id=current.tick_id,
                continuity_kind=current.continuity_kind,
                outcome_class=current.outcome_class,
                summary=current.summary,
                layer=current.layer,
                objective_importance=current.objective_importance,
                llm_remember_decision=current.llm_remember_decision,
                double_confirmation_class=current.double_confirmation_class,
                hormone_snapshot=current.hormone_snapshot,
                feeling_snapshot=current.feeling_snapshot,
                created_at_tick=current.created_at_tick,
                created_at_wall=current.created_at_wall,
                last_recall_at_wall=current.last_recall_at_wall,
                recall_count=current.recall_count,
                is_consolidated=current.is_consolidated,
                soft_deleted_at=at_wall,
                memory_gc_after=gc_after,
                audit_trail=audit_entry,
                tags=current.tags,
                context_keywords=current.context_keywords,
                cross_links=current.cross_links,
            )
            self._records[record_id] = new_record
            return new_record

    # -- Protocol compliance: search_by_keyword ----------------------------

    def search_by_keyword(
        self,
        query: str,
        *,
        limit: int = 5,
        min_keyword_hits: int = 1,
    ) -> tuple[MemoryRecord, ...]:
        if limit <= 0:
            raise MemoryRecordStoreError("limit must be > 0")
        if min_keyword_hits < 1:
            raise MemoryRecordStoreError("min_keyword_hits must be >= 1")
        # Normalize the query: lowercased, whitespace-split, dedup, drop empties.
        raw_tokens = query.lower().split()
        tokens = tuple(t for t in dict.fromkeys(raw_tokens) if t)
        if not tokens:
            return ()
        with self._lock:
            snapshot = list(self._records.values())
        # Score = distinct token hits across (summary, tags, context_keywords).
        # Matching is substring-based (token in any corpus token) so that
        # "promise" matches "promised". This is deliberately simple — R86+
        # may replace it with proper stemming or embedding-based search.
        scored: list[tuple[int, int, MemoryRecord]] = []
        for r in snapshot:
            if r.soft_deleted_at is not None:
                continue  # soft-deleted is invisible to recall
            corpus_tokens = _tokenize_record_for_search(r)
            if not corpus_tokens:
                continue
            hits = sum(1 for t in tokens if any(t in ct for ct in corpus_tokens))
            if hits < min_keyword_hits:
                continue
            scored.append((hits, r.created_at_tick, r))
        # Sort: hits desc, then created_at_tick desc (newer first on tie)
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return tuple(r for _, _, r in scored[:limit])


def _tokenize_record_for_search(record: MemoryRecord) -> set[str]:
    """Lowercase set of tokens used for keyword recall (summary + tags + keywords)."""
    out: set[str] = set()
    if record.summary:
        out.update(record.summary.lower().split())
    for t in record.tags:
        out.update(t.lower().split())
    for k in record.context_keywords:
        out.update(k.lower().split())
    return out


__all__ = [
    "InMemoryR85MemoryStore",
    "MemoryRecordStoreError",
    "R85MemoryStoreBackend",
]
