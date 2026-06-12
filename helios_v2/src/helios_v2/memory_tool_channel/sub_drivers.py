"""Owner: 31 memory_tool_channel (R85 Track B sub-drivers).

Owns:
- the concrete sub-driver callables that `MemoryToolDispatcher` invokes
  for `memory_save`, `memory_replay`, and `memory_forget`
- the integration of those sub-drivers with the R85 `MemoryRecord` store
  and the L18 governance gate

Does not own:
- intent parsing (owner 31 parser)
- quota and governance application (owner 31 channel driver)
- the R85 record store itself (owner 06 memory)

This module is OPT-IN: the sub-drivers are wired in only when the caller
asks for `memory_tool_channel=True` in `assemble_runtime()`. Without
opt-in, the legacy contract is preserved.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, Protocol, runtime_checkable

from helios_v2.identity_governance.forget_permission import (  # type: ignore[attr-defined]
    check_forget_permission,
)
from helios_v2.memory.classifier import (
    classify_for_persistence,
    make_memory_record,
)
from helios_v2.memory.contracts import (
    MemoryRecord,
    should_persist,
)
from helios_v2.memory.engine import (
    objective_importance,
)
from helios_v2.memory.store import (
    InMemoryR85MemoryStore,
    MemoryRecordStoreError,
    R85MemoryStoreBackend,
)

from .contracts import MemoryToolCall, MemoryToolResult


# =============================================================================
# Helpers
# =============================================================================


def _now() -> float:
    return time.time()


def _make_record_id() -> str:
    return f"mem-{uuid.uuid4().hex[:12]}"


# =============================================================================
# Sub-driver factories
# =============================================================================


@runtime_checkable
class SubDriverDeps(Protocol):
    """Minimal dependencies a sub-driver needs to do its work.

    Owner: 31 memory_tool_channel.

    Purpose:
        Let tests inject a stub store and clock without going through
        the runtime assembly. The runtime assembly is responsible for
        providing a fully-real `SubDriverDeps` in production paths.

    Notes:
        `check_forget` is a callable for testability of the L18 gate.
    """

    store: R85MemoryStoreBackend
    tick_id: int
    hormone_snapshot: dict[str, float]
    feeling_snapshot: dict[str, float]
    now: Callable[[], float]
    check_forget: Callable[[MemoryRecord, str], "GovernanceVerdict"]  # type: ignore[name-defined]  # noqa: F821


def build_sub_drivers(
    *,
    deps: SubDriverDeps,
) -> tuple[
    Callable[[MemoryToolCall], MemoryToolResult],
    Callable[[MemoryToolCall], MemoryToolResult],
    Callable[[MemoryToolCall], MemoryToolResult],
]:
    """Return (save, replay, forget) sub-driver callables for `MemoryToolDispatcher`.

    The returned callables are the production implementations for R85.
    """
    return (
        _make_save_driver(deps),
        _make_replay_driver(deps),
        _make_forget_driver(deps),
    )


# =============================================================================
# save
# =============================================================================


def _make_save_driver(
    deps: SubDriverDeps,
) -> Callable[[MemoryToolCall], MemoryToolResult]:
    def save_driver(call: MemoryToolCall) -> MemoryToolResult:
        if call.tool != "memory_save":
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason="save_driver called with non-save tool",
            )
        # Double-confirmation: subjective (LLM "remember") + objective (score).
        # In the opt-in path the LLM has already declared intent (the tool
        # call itself is the LLM's remember vote), so llm_remember=True.
        importance = objective_importance(
            stimulus_text=call.content,
            hormone_snapshot=deps.hormone_snapshot,
            feeling_snapshot=deps.feeling_snapshot,
            outcome_class="self_changed",
        )
        decision = should_persist(llm_remember=True, objective_score=importance)
        if decision == "skip":
            return MemoryToolResult(
                call_id=call.record_id_hint or call.call_id,
                tool=call.tool,
                status="skipped",
                result_summary=f"double-confirmation skip (importance={importance:.2f})",
            )
        record_id = call.record_id_hint or _make_record_id()
        try:
            classification = classify_for_persistence(
                llm_remember=True,
                stimulus_text=call.content,
                hormone_snapshot=deps.hormone_snapshot,
                feeling_snapshot=deps.feeling_snapshot,
                outcome_class="self_changed",
            )
            record = make_memory_record(
                record_id=record_id,
                tick_id=deps.tick_id,
                outcome_class="self_changed",
                continuity_kind="world_changed",
                summary=call.content,
                classification=classification,
                llm_remember=True,
                hormone_snapshot=deps.hormone_snapshot,
                feeling_snapshot=deps.feeling_snapshot,
                created_at_wall=deps.now(),
            )
        except Exception as e:  # construction invariant violation
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason=f"MemoryRecord construction failed: {type(e).__name__}: {e}",
            )
        try:
            deps.store.append(record)
        except MemoryRecordStoreError as e:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason=str(e),
            )
        return MemoryToolResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            record_id=record.record_id,
            result_summary=f"saved as {record.layer} (importance={importance:.2f})",
        )

    return save_driver


# =============================================================================
# replay (T18: this is the C-recall trigger)
# =============================================================================


def _make_replay_driver(
    deps: SubDriverDeps,
) -> Callable[[MemoryToolCall], MemoryToolResult]:
    def replay_driver(call: MemoryToolCall) -> MemoryToolResult:
        if call.tool != "memory_replay":
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason="replay_driver called with non-replay tool",
            )
        # Two resolution paths:
        # 1. LLM gave a specific record_id_hint -> get + increment_recall
        # 2. LLM asked a free-text query -> search_by_keyword + increment_recall
        #    on the top hit (if any)
        record: MemoryRecord | None = None
        if call.record_id_hint:
            record = deps.store.get(call.record_id_hint)
        else:
            hits = deps.store.search_by_keyword(call.content, limit=1)
            if hits:
                record = hits[0]
        if record is None:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="skipped",
                record_id=None,
                result_summary="no matching memory found",
            )
        try:
            promoted = deps.store.increment_recall(record.record_id, at_wall=deps.now())
        except MemoryRecordStoreError as e:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason=str(e),
            )
        promoted_note = ""
        if promoted.layer != record.layer:
            promoted_note = f" (promoted {record.layer} -> {promoted.layer})"
        return MemoryToolResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            record_id=promoted.record_id,
            result_summary=(
                f"recalled {promoted.summary!r} "
                f"(recall_count={promoted.recall_count}){promoted_note}"
            ),
        )

    return replay_driver


# =============================================================================
# forget (T19: L18 governance gate is consulted here)
# =============================================================================


def _make_forget_driver(
    deps: SubDriverDeps,
) -> Callable[[MemoryToolCall], MemoryToolResult]:
    def forget_driver(call: MemoryToolCall) -> MemoryToolResult:
        if call.tool != "memory_forget":
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason="forget_driver called with non-forget tool",
            )
        if not call.record_id_hint:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason="forget requires a record_id_hint",
            )
        record = deps.store.get(call.record_id_hint)
        if record is None:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="ok",
                record_id=None,
                result_summary="forget target not found",
            )
        # L18 gate (T19). The function is fail-closed and may deny.
        verdict = deps.check_forget(record, call.content)
        if not verdict.allow:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason=f"L18 denied: {verdict.reason}",
            )
        try:
            deleted = deps.store.soft_delete(
                record.record_id, at_wall=deps.now(), reason=call.content or "LLM forget"
            )
        except MemoryRecordStoreError as e:
            return MemoryToolResult(
                call_id=call.call_id,
                tool=call.tool,
                status="error",
                error_reason=str(e),
            )
        return MemoryToolResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            record_id=deleted.record_id,
            result_summary=f"soft-deleted {deleted.layer} memory",
        )

    return forget_driver


# =============================================================================
# Convenience wiring for runtime_assembly
# =============================================================================


def default_sub_driver_deps(
    *,
    store: R85MemoryStoreBackend,
    tick_id: int,
    hormone_snapshot: dict[str, float] | None = None,
    feeling_snapshot: dict[str, float] | None = None,
) -> SubDriverDeps:
    """Build a production `SubDriverDeps` with real L18 gate."""
    from helios_v2.identity_governance.forget_permission import (  # type: ignore[attr-defined]
        check_forget_permission,
    )

    class _Deps:
        pass

    deps = _Deps()
    deps.store = store
    deps.tick_id = tick_id
    deps.hormone_snapshot = dict(hormone_snapshot or {})
    deps.feeling_snapshot = dict(feeling_snapshot or {})
    deps.now = _now
    deps.check_forget = check_forget_permission
    return deps  # type: ignore[return-value]


__all__ = [
    "SubDriverDeps",
    "build_sub_drivers",
    "default_sub_driver_deps",
]
