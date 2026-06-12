"""R85-T17 in-memory R85MemoryStore + recall-trigger promote_layer tests.

T17 implements the RECALL half of consolidation-timing decision C:
- store keeps MemoryRecord by id
- increment_recall bumps recall_count + last_recall_at_wall
- then runs promote_layer (L3 + recall=2 -> L4)

Plus the store's other responsibilities:
- append (idempotency on record_id)
- get / list / list filter
- soft_delete with audit trail
- search_by_keyword

10 tests:
1. append + get round-trip
2. duplicate append raises
3. list() filters soft-deleted
4. list(layer=L4) filters by layer
5. increment_recall bumps count and last_recall_at_wall
6. increment_recall triggers promote L3->L4 at recall_count=2
7. increment_recall on unknown id raises
8. soft_delete marks record + adds audit entry + sets memory_gc_after
9. search_by_keyword returns matching records
10. search_by_keyword skips soft-deleted records
"""
from __future__ import annotations

import time

import pytest

from helios_v2.memory.contracts import (
    DoubleConfirmationClass,
    MemoryRecord,
)
from helios_v2.memory.store import (
    InMemoryR85MemoryStore,
    MemoryRecordStoreError,
)


def _make_record(
    record_id: str = "r1",
    *,
    tick_id: int = 1,
    layer: str = "L3_short",
    summary: str = "I promised Xiaohei to come back by 8pm",
    created_at_wall: float = 1000.0,
    tags: tuple[str, ...] = (),
    context_keywords: tuple[str, ...] = (),
) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id,
        tick_id=tick_id,
        continuity_kind="world_changed",
        outcome_class="self_changed",
        summary=summary,
        layer=layer,  # type: ignore[arg-type]
        objective_importance=0.5,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.4},
        feeling_snapshot={"warmth": 0.6, "anxiety": 0.2},
        created_at_tick=tick_id,
        created_at_wall=created_at_wall,
        last_recall_at_wall=None,
        recall_count=0,
        is_consolidated=False,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=tags,
        context_keywords=context_keywords,
        cross_links=(),
    )


# =============================================================================
# Test 1-4: basic CRUD + list filters
# =============================================================================


def test_t17_append_and_get_round_trip():
    store = InMemoryR85MemoryStore()
    rec = _make_record(record_id="r1")
    store.append(rec)
    got = store.get("r1")
    assert got is not None
    assert got.record_id == "r1"
    assert got.summary == rec.summary


def test_t17_duplicate_append_raises():
    store = InMemoryR85MemoryStore()
    rec = _make_record(record_id="r1")
    store.append(rec)
    with pytest.raises(MemoryRecordStoreError, match="already exists"):
        store.append(rec)


def test_t17_list_excludes_soft_deleted_by_default():
    store = InMemoryR85MemoryStore()
    r1 = _make_record(record_id="r1")
    r2 = _make_record(record_id="r2", summary="another")
    store.append(r1)
    store.append(r2)
    store.soft_delete("r1", at_wall=2000.0, reason="test")
    all_records = store.list()
    assert len(all_records) == 1
    assert all_records[0].record_id == "r2"
    with_deleted = store.list(include_soft_deleted=True)
    assert len(with_deleted) == 2


def test_t17_list_filter_by_layer():
    store = InMemoryR85MemoryStore()
    store.append(_make_record(record_id="l3a", layer="L3_short"))
    store.append(_make_record(record_id="l4a", layer="L4_long"))
    store.append(_make_record(record_id="l3b", layer="L3_short"))
    l3_only = store.list(layer="L3_short")
    assert {r.record_id for r in l3_only} == {"l3a", "l3b"}


# =============================================================================
# Test 5-7: increment_recall (T17's primary contribution)
# =============================================================================


def test_t17_increment_recall_bumps_count_and_timestamp():
    store = InMemoryR85MemoryStore()
    store.append(_make_record(record_id="r1", created_at_wall=1000.0))
    updated = store.increment_recall("r1", at_wall=1100.0)
    assert updated.recall_count == 1
    assert updated.last_recall_at_wall == 1100.0
    # store now holds the bumped record
    got = store.get("r1")
    assert got is not None
    assert got.recall_count == 1


def test_t17_increment_recall_triggers_promote_l3_to_l4_at_count_2():
    """T17 wires the recall half of C-recall: 2 recalls promotes L3->L4."""
    store = InMemoryR85MemoryStore()
    store.append(_make_record(record_id="r1", layer="L3_short", created_at_wall=1000.0))
    # First recall: still L3, count=1
    after_first = store.increment_recall("r1", at_wall=1100.0)
    assert after_first.layer == "L3_short"
    assert after_first.recall_count == 1
    # Second recall: promoted to L4 (per promote_layer rule)
    after_second = store.increment_recall("r1", at_wall=1200.0)
    assert after_second.layer == "L4_long"
    assert after_second.recall_count == 2
    assert after_second.is_consolidated is True
    # Store should reflect the promoted version
    got = store.get("r1")
    assert got is not None
    assert got.layer == "L4_long"


def test_t17_increment_recall_unknown_id_raises():
    store = InMemoryR85MemoryStore()
    with pytest.raises(MemoryRecordStoreError, match="unknown"):
        store.increment_recall("nope", at_wall=1100.0)


# =============================================================================
# Test 8: soft_delete semantics
# =============================================================================


def test_t17_soft_delete_marks_record_and_writes_audit():
    store = InMemoryR85MemoryStore()
    store.append(_make_record(record_id="r1", created_at_wall=1000.0))
    deleted = store.soft_delete("r1", at_wall=2000.0, reason="pattern broke")
    assert deleted.soft_deleted_at == 2000.0
    assert deleted.memory_gc_after is not None
    assert deleted.memory_gc_after > 2000.0  # 7-day TTL
    # audit trail contains the soft_delete event
    assert len(deleted.audit_trail) == 1
    event = dict(deleted.audit_trail[0])
    assert event["event"] == "soft_delete"
    assert event["reason"] == "pattern broke"


# =============================================================================
# Test 9-10: search_by_keyword
# =============================================================================


def test_t17_search_by_keyword_returns_matching_records():
    store = InMemoryR85MemoryStore()
    store.append(_make_record(
        record_id="a",
        summary="Xiaohei promised to come back",
        tags=("relationship",),
        context_keywords=("promise", "evening"),
    ))
    store.append(_make_record(
        record_id="b",
        summary="we argued about the meeting",
        tags=("conflict",),
        context_keywords=(),
    ))
    store.append(_make_record(
        record_id="c",
        summary="nothing relevant here",
        tags=(),
        context_keywords=(),
    ))
    hits = store.search_by_keyword("promised evening", limit=5)
    ids = [r.record_id for r in hits]
    assert "a" in ids
    assert "b" not in ids


def test_t17_search_skips_soft_deleted():
    store = InMemoryR85MemoryStore()
    store.append(_make_record(record_id="a", summary="important promise"))
    store.soft_delete("a", at_wall=2000.0, reason="forgotten")
    hits = store.search_by_keyword("promise", limit=5)
    assert all(r.record_id != "a" for r in hits)
