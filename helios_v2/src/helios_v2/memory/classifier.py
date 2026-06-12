"""Owner: 06 memory — R85 Track A classification layer.

Provides a thin classifier that combines `should_persist` (LLM ↔ objective
double confirmation) and `objective_importance` into a single decision
that the experience-writeback path can consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Callable

from helios_v2.memory.contracts import (
    DoubleConfirmationClass,
    MemoryRecord,
    should_persist,
)
from helios_v2.memory.engine import objective_importance


@dataclass(frozen=True)
class MemoryClassification:
    """Result of classifying a candidate writeback for memory layer assignment.

    Attributes:
        classification: persist_full / persist_low_priority / skip
        objective_importance: computed 6-dim score in [0, 1]
        target_layer: L3_short / L4_long / skip (None for skip)
        reason: human-readable reasoning
    """
    classification: DoubleConfirmationClass
    objective_importance: float
    target_layer: str | None
    reason: str


def classify_for_persistence(
    *,
    llm_remember: bool,
    stimulus_text: str,
    hormone_snapshot: Mapping[str, float],
    feeling_snapshot: Mapping[str, float],
    outcome_class: str,
    recent_summaries: Sequence[str] = (),
    embed_callable: Callable[[str], Sequence[float]] | None = None,
) -> MemoryClassification:
    """Classify a candidate outcome for memory persistence.

    Combines:
        1. `should_persist(llm_remember, objective_score)` — 3-class decision
        2. `objective_importance(...)` — 6-dim score
        3. Layer target mapping

    Layer mapping (R85 design §4.2):
        persist_full + obj >= 0.7  -> L4_long
        persist_full + obj <  0.7  -> L3_short
        persist_low_priority       -> L3_short
        skip                       -> None (do not store)
    """
    obj_score = objective_importance(
        stimulus_text=stimulus_text,
        hormone_snapshot=hormone_snapshot,
        feeling_snapshot=feeling_snapshot,
        outcome_class=outcome_class,
        recent_summaries=recent_summaries,
        embed_callable=embed_callable,
    )
    cls = should_persist(llm_remember, obj_score)

    target_layer: str | None
    if cls == "skip":
        target_layer = None
        reason = f"skipped (obj={obj_score:.3f}, llm_remember={llm_remember})"
    elif cls == "persist_full" and obj_score >= 0.7:
        target_layer = "L4_long"
        reason = f"persist_full + high importance ({obj_score:.3f}) -> L4_long"
    elif cls == "persist_full":
        target_layer = "L3_short"
        reason = f"persist_full + moderate importance ({obj_score:.3f}) -> L3_short"
    else:  # persist_low_priority
        target_layer = "L3_short"
        reason = f"persist_low_priority (obj={obj_score:.3f}) -> L3_short"

    return MemoryClassification(
        classification=cls,
        objective_importance=obj_score,
        target_layer=target_layer,
        reason=reason,
    )


def make_memory_record(
    *,
    record_id: str,
    tick_id: int,
    outcome_class: str,
    continuity_kind: str,
    summary: str,
    classification: MemoryClassification,
    llm_remember: bool,
    hormone_snapshot: Mapping[str, float],
    feeling_snapshot: Mapping[str, float],
    created_at_wall: float,
    extra_tags: Sequence[str] = (),
) -> MemoryRecord:
    """Construct a MemoryRecord from a MemoryClassification.

    Caller must pass `created_at_wall` (e.g. time.time()) — we do not read clocks
    inside this layer (R85 fail-fast: no implicit I/O).
    """
    if classification.target_layer is None:
        raise ValueError(
            f"make_memory_record called with classification that has no target_layer: "
            f"{classification.classification} (skip cannot be materialized as MemoryRecord)"
        )
    return MemoryRecord(
        record_id=record_id,
        tick_id=tick_id,
        continuity_kind=continuity_kind,
        outcome_class=outcome_class,
        summary=summary,
        layer=classification.target_layer,
        objective_importance=classification.objective_importance,
        llm_remember_decision=llm_remember,
        double_confirmation_class=classification.classification,
        hormone_snapshot=hormone_snapshot,
        feeling_snapshot=feeling_snapshot,
        created_at_tick=tick_id,
        created_at_wall=created_at_wall,
        last_recall_at_wall=created_at_wall,
        recall_count=0,
        is_consolidated=(classification.target_layer in ("L4_long", "L5_autobiographical")),
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=({"classification_reason": classification.reason},),
        tags=tuple(extra_tags),
        context_keywords=(),
        cross_links=(),
    )
