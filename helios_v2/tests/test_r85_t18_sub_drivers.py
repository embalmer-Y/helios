"""R85-T18 + T19 sub-drivers wired to the store + L18 governance.

T18: owner 31 sub-drivers (save / replay / forget) use the real
     R85MemoryStore. The replay sub-driver is the C-recall trigger.

T19: T11 L18 check_forget_permission is real; the forget sub-driver
     consults it and returns error on deny.

10 tests:
1. save: returns ok with new record_id, record is in store
2. save: skip path when importance < 0.2 (returns status=skipped)
3. replay with record_id_hint: hits store, increments recall_count
4. replay without hint: search_by_keyword resolves the record
5. replay twice: L3 -> L4 promotion via store.increment_recall (T18 C-recall)
6. replay with no match: status=skipped, record_id=None
7. forget: L3 -> ok, record is soft-deleted
8. forget: L5 -> L18 denied, status=error, error_reason mentions L18
9. forget: missing reason returns L18 denied (fail-closed)
10. forget: L3 with no record_id_hint -> error
"""
from __future__ import annotations

import pytest

from helios_v2.identity_governance.forget_permission import check_forget_permission
from helios_v2.memory.classifier import (
    classify_for_persistence,
    make_memory_record,
)
from helios_v2.memory.contracts import MemoryRecord
from helios_v2.memory.store import InMemoryR85MemoryStore
from helios_v2.memory_tool_channel import (
    MemoryToolCall,
    MemoryToolDispatcher,
    build_sub_drivers,
    default_sub_driver_deps,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_record(
    record_id: str,
    *,
    tick_id: int = 1,
    layer: str = "L3_short",
    summary: str = "Xiaohei promised to come back by 8pm",
    created_at_wall: float = 1000.0,
    objective_importance: float = 0.5,
    recall_count: int = 0,
    last_recall_at_wall: float | None = None,
) -> MemoryRecord:
    classification = classify_for_persistence(
        llm_remember=True,
        stimulus_text=summary,
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6},
        outcome_class="self_changed",
    )
    rec = make_memory_record(
        record_id=record_id,
        tick_id=tick_id,
        outcome_class="self_changed",
        continuity_kind="world_changed",
        summary=summary,
        classification=classification,
        llm_remember=True,
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6},
        created_at_wall=created_at_wall,
    )
    if layer != rec.layer:
        # Force a different layer for L5 / L4 tests (classifier picks L3).
        rec = MemoryRecord(
            record_id=rec.record_id,
            tick_id=rec.tick_id,
            continuity_kind=rec.continuity_kind,
            outcome_class=rec.outcome_class,
            summary=rec.summary,
            layer=layer,  # type: ignore[arg-type]
            objective_importance=objective_importance,
            llm_remember_decision=rec.llm_remember_decision,
            double_confirmation_class=rec.double_confirmation_class,
            hormone_snapshot=rec.hormone_snapshot,
            feeling_snapshot=rec.feeling_snapshot,
            created_at_tick=rec.created_at_tick,
            created_at_wall=rec.created_at_wall,
            last_recall_at_wall=last_recall_at_wall,
            recall_count=recall_count,
            is_consolidated=layer == "L5_autobiographical",
            soft_deleted_at=rec.soft_deleted_at,
            memory_gc_after=rec.memory_gc_after,
            audit_trail=rec.audit_trail,
            tags=rec.tags,
            context_keywords=rec.context_keywords,
            cross_links=rec.cross_links,
        )
    return rec


def _build_dispatcher():
    store = InMemoryR85MemoryStore()
    deps = default_sub_driver_deps(
        store=store,
        tick_id=1,
        hormone_snapshot={"cortisol": 0.3, "arousal": 0.5},
        feeling_snapshot={"warmth": 0.6},
    )
    save, replay, forget = build_sub_drivers(deps=deps)
    return (
        MemoryToolDispatcher(
            save_driver=save, replay_driver=replay, forget_driver=forget
        ),
        store,
    )


def _call(tool, call_id, content, record_id_hint=None, priority=100):
    return MemoryToolCall(
        call_id=call_id,
        tick_id=1,
        tool=tool,
        record_id_hint=record_id_hint,
        content=content,
        priority=priority,
    )


# =============================================================================
# T18: save sub-driver
# =============================================================================


def test_t18_save_returns_ok_and_appends_to_store():
    dispatcher, store = _build_dispatcher()
    results = dispatcher.dispatch((
        _call("memory_save", "c1", "Xiaohei promised to come back"),
    ))
    assert results[0].status == "ok"
    assert results[0].record_id is not None
    # record is in store
    got = store.get(results[0].record_id)
    assert got is not None
    assert "promised" in got.summary


def test_t18_save_skip_when_double_confirmation_fails(monkeypatch):
    """Force should_persist to return 'skip' (the LLM-AND-objective fail path)."""
    dispatcher, store = _build_dispatcher()

    def _fake_should_persist(*args, **kwargs):
        return "skip"

    from helios_v2.memory_tool_channel import sub_drivers
    monkeypatch.setattr(sub_drivers, "should_persist", _fake_should_persist)
    results = dispatcher.dispatch((
        _call("memory_save", "c1", "trivial detail"),
    ))
    assert results[0].status == "skipped"
    assert "skip" in results[0].result_summary.lower()
    # store is still empty
    assert store.list() == ()


# =============================================================================
# T18: replay sub-driver (the C-recall trigger)
# =============================================================================


def test_t18_replay_with_hint_increments_recall_count():
    dispatcher, store = _build_dispatcher()
    store.append(_make_record("r1"))
    results = dispatcher.dispatch((
        _call("memory_replay", "c1", "anything", record_id_hint="r1"),
    ))
    assert results[0].status == "ok"
    assert results[0].record_id == "r1"
    assert "recall_count=1" in results[0].result_summary


def test_t18_replay_without_hint_uses_keyword_search():
    dispatcher, store = _build_dispatcher()
    store.append(_make_record("r1", summary="Xiaohei promised to come back"))
    store.append(_make_record("r2", summary="we argued about lunch"))
    results = dispatcher.dispatch((
        _call("memory_replay", "c1", "promise"),
    ))
    assert results[0].status == "ok"
    assert results[0].record_id == "r1"


def test_t18_replay_twice_promotes_l3_to_l4():
    """T18 wires the recall half of C-recall: 2 recalls promotes L3->L4."""
    dispatcher, store = _build_dispatcher()
    store.append(_make_record("r1", layer="L3_short"))
    r1 = dispatcher.dispatch((_call("memory_replay", "c1", "x", record_id_hint="r1"),))
    assert r1[0].status == "ok"
    r2 = dispatcher.dispatch((_call("memory_replay", "c2", "x", record_id_hint="r1"),))
    assert r2[0].status == "ok"
    assert "promoted L3_short -> L4_long" in r2[0].result_summary
    # Store now has the promoted record
    got = store.get("r1")
    assert got is not None
    assert got.layer == "L4_long"
    assert got.is_consolidated is True


def test_t18_replay_with_no_match_returns_skipped():
    dispatcher, store = _build_dispatcher()
    results = dispatcher.dispatch((
        _call("memory_replay", "c1", "never seen this content"),
    ))
    assert results[0].status == "skipped"
    assert results[0].record_id is None


# =============================================================================
# T19: forget sub-driver + L18 governance
# =============================================================================


def test_t19_forget_l3_succeeds():
    dispatcher, store = _build_dispatcher()
    store.append(_make_record("r1", layer="L3_short"))
    results = dispatcher.dispatch((
        _call("memory_forget", "c1", "pattern broke", record_id_hint="r1", priority=0),
    ))
    assert results[0].status == "ok"
    assert "soft-deleted" in results[0].result_summary
    got = store.get("r1")
    assert got is not None
    assert got.soft_deleted_at is not None


def test_t19_forget_l5_is_denied_by_l18():
    dispatcher, store = _build_dispatcher()
    store.append(_make_record("r1", layer="L5_autobiographical"))
    results = dispatcher.dispatch((
        _call("memory_forget", "c1", "want to forget this", record_id_hint="r1", priority=0),
    ))
    assert results[0].status == "error"
    assert "L18" in results[0].error_reason
    assert "L5_autobiographical" in results[0].error_reason
    # store still has the record, not soft-deleted
    got = store.get("r1")
    assert got is not None
    assert got.soft_deleted_at is None


def test_t19_forget_missing_reason_is_denied_fail_closed():
    """L18 gate is fail-closed: no reason -> deny."""
    record = _make_record("r1", layer="L3_short")
    verdict = check_forget_permission(record, reason="")
    assert verdict.allow is False
    assert "reason" in verdict.reason.lower()


def test_t19_forget_requires_record_id_hint():
    dispatcher, store = _build_dispatcher()
    results = dispatcher.dispatch((
        _call("memory_forget", "c1", "no hint", record_id_hint=None, priority=0),
    ))
    assert results[0].status == "error"
    assert "record_id_hint" in results[0].error_reason
