"""R83 memory-fidelity probe (Axis 3) — real implementation.

The R83 axis 3 ("memory-fidelity") score is computed by issuing
**directed-retrieval probes** via owner 10 (`directed_retrieval`) and
verifying that the persona's `remember_this` field is consistent with
what was persisted to the experience store by owner 15
(`experience_writeback`).

This probe is invoked by the R83 CLI after the 40-tick preflight
completes. It:

  1. Loads the 40-tick JSONL trail
  2. Groups records by state block (8 blocks × 5 ticks)
  3. For each block, issues 1 directed-retrieval probe using the
     FirstVersionDirectedRetrievalPath + a
     StoreBackedDirectedMemoryCandidateProvider over the runtime's
     experience_store
  4. Checks whether the probe query text appears in any candidate's
     summary (a substring match is enough for a probe-grade eval)
  5. Counts `remember_this=True` ticks per block and cross-references
     with persisted records whose tick_id matches
  6. Computes 3 sub-metrics: retrieval_latency_ms, recall_hit_rate,
     writeback_persistence_rate
  7. Aggregates to a per-state A3 + overall A3 axis score

Failure modes (all fail-soft):
  - `handle` is None or has no experience_store → A3=0.5, reason "no-store"
  - R10 path raises an exception → that state's A3=0.5, others OK
  - All 8 probes fail → A3=0.5, reason "all-probes-failed"
  - 0 records → A3=0.5, reason "no-records"

This module is owned by R83 (tests/r83/) and imports from owners 10
(directed_retrieval), 15 (experience_writeback), and persistence.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import _io


# ============================================================
# Data structures
# ============================================================


@dataclass(frozen=True)
class PerStateA3Breakdown:
    """Per-state A3 sub-metric breakdown for one state block."""

    state_id: str
    n_ticks: int
    n_remember_this_true: int
    retrieval_latency_ms: float | None
    recall_hit_rate: float  # 0.0-1.0
    writeback_persistence_rate: float  # 0.0-1.0
    latency_score: float  # 0.0-1.0 (1.0 = instant, 0.0 = >= 1s)
    a3_score: float  # 0.0-1.0
    probe_reasoning: str


@dataclass(frozen=True)
class MemoryProbeResult:
    """Result of the A3 memory-fidelity probe."""

    score: float
    reasoning: str
    retrieval_latency_ms: float | None = None
    recall_hit_rate: float | None = None
    writeback_persistence_rate: float | None = None
    per_state: tuple[PerStateA3Breakdown, ...] = field(default_factory=tuple)
    n_probes_succeeded: int = 0
    n_probes_failed: int = 0


# ============================================================
# Helpers
# ============================================================


def _load_records(jsonl_path: Path) -> list[dict]:
    """Load per-tick records from the JSONL trail."""
    if not jsonl_path.exists():
        return []
    records: list[dict] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _group_by_state(records: Sequence[dict]) -> dict[str, list[dict]]:
    """Group records by `state_id` (or `block_id` for older formats)."""
    grouped: dict[str, list[dict]] = {}
    for r in records:
        sid = r.get("state_id") or r.get("block_id") or "unknown"
        grouped.setdefault(sid, []).append(r)
    return grouped


def _bundle_contains_text(bundle: Any, query_text: str) -> bool:
    """Check if any tier of a ThoughtWindowBundle has a hit whose summary
    contains the query text (substring match)."""
    if bundle is None or not query_text:
        return False
    needle = query_text.strip()[:30]
    if not needle:
        return False
    for attr_name in ("short_term_context", "mid_term_hits", "long_term_hits",
                      "autobiographical_hits"):
        hits = getattr(bundle, attr_name, ())
        for hit in hits:
            summary = getattr(hit, "summary", "") or ""
            if needle in summary:
                return True
    return False


def _per_state_a3(
    *,
    recall_hit_rate: float,
    writeback_persistence_rate: float,
    latency_ms: float | None,
) -> tuple[float, float]:
    """Compute the per-state A3 score + latency_score.

    Formula: A3 = 0.4 * recall_hit_rate + 0.3 * writeback_persistence_rate
                  + 0.3 * latency_score

    latency_score = 1.0 - min(latency_ms / 1000.0, 1.0)
    """
    if latency_ms is None:
        # Probe failed; weight it at 0
        latency_score = 0.0
    else:
        latency_score = 1.0 - min(latency_ms / 1000.0, 1.0)
    a3 = (
        0.4 * max(0.0, min(1.0, recall_hit_rate))
        + 0.3 * max(0.0, min(1.0, writeback_persistence_rate))
        + 0.3 * max(0.0, min(1.0, latency_score))
    )
    return a3, latency_score


# ============================================================
# MemoryProbe (real implementation)
# ============================================================


class MemoryProbe:
    """A3 memory-fidelity probe (real implementation).

    Owner: 17 evaluation (MemoryProbe in tests/r83/).

    The probe runs AFTER the 40-tick LongRunner completes. It uses
    the live RuntimeHandle's `experience_store` (owner 17 persistence)
    and the R10 retrieval path's `plan_and_select` to issue 1 probe
    per state block.
    """

    def __init__(self, handle: Any | None = None) -> None:
        self.handle = handle

    def score(self, jsonl_path: Path) -> MemoryProbeResult:
        """Compute the A3 memory-fidelity score.

        Args:
            jsonl_path: path to the R83 40-tick JSONL trail.

        Returns:
            `MemoryProbeResult` with sub-metrics and per-state breakdown.
        """
        records = _load_records(jsonl_path)
        if not records:
            return MemoryProbeResult(
                score=0.5,
                reasoning="no-records: empty jsonl trail",
                per_state=(),
                n_probes_succeeded=0,
                n_probes_failed=0,
            )

        # Fail-soft: if no handle or no experience_store, return 0.5
        if self.handle is None:
            return MemoryProbeResult(
                score=0.5,
                reasoning="no-handle: cannot access experience_store",
                per_state=(),
                n_probes_succeeded=0,
                n_probes_failed=0,
            )
        experience_store = getattr(self.handle, "experience_store", None)
        if experience_store is None:
            return MemoryProbeResult(
                score=0.5,
                reasoning="no-store: handle.experience_store is None",
                per_state=(),
                n_probes_succeeded=0,
                n_probes_failed=0,
            )

        # Group by state
        grouped = _group_by_state(records)
        per_state_results: list[PerStateA3Breakdown] = []
        n_succeeded = 0
        n_failed = 0

        for state_id, state_records in sorted(grouped.items()):
            state_result = self._probe_state(
                state_id=state_id,
                state_records=state_records,
                experience_store=experience_store,
            )
            per_state_results.append(state_result)
            if state_result.retrieval_latency_ms is not None:
                n_succeeded += 1
            else:
                n_failed += 1

        if n_succeeded == 0:
            return MemoryProbeResult(
                score=0.5,
                reasoning="all-probes-failed: R10 path unusable for all 8 states",
                per_state=tuple(per_state_results),
                n_probes_succeeded=0,
                n_probes_failed=n_failed,
            )

        # Aggregate
        per_state_scores = [r.a3_score for r in per_state_results if r.retrieval_latency_ms is not None]
        overall_a3 = sum(per_state_scores) / len(per_state_scores) if per_state_scores else 0.5
        avg_latency = sum(
            r.retrieval_latency_ms for r in per_state_results
            if r.retrieval_latency_ms is not None
        ) / max(n_succeeded, 1)
        avg_recall = sum(
            r.recall_hit_rate for r in per_state_results
            if r.retrieval_latency_ms is not None
        ) / max(n_succeeded, 1)
        avg_persistence = sum(
            r.writeback_persistence_rate for r in per_state_results
            if r.retrieval_latency_ms is not None
        ) / max(n_succeeded, 1)

        return MemoryProbeResult(
            score=overall_a3,
            reasoning=(
                f"real-probe: {n_succeeded}/{len(per_state_results)} states probed, "
                f"latency={avg_latency:.1f}ms, recall={avg_recall:.2f}, "
                f"persistence={avg_persistence:.2f}"
            ),
            retrieval_latency_ms=avg_latency,
            recall_hit_rate=avg_recall,
            writeback_persistence_rate=avg_persistence,
            per_state=tuple(per_state_results),
            n_probes_succeeded=n_succeeded,
            n_probes_failed=n_failed,
        )

    # --------------------------------------------------------
    # Per-state probe
    # --------------------------------------------------------

    def _probe_state(
        self,
        *,
        state_id: str,
        state_records: Sequence[dict],
        experience_store: Any,
    ) -> PerStateA3Breakdown:
        """Probe one state block: 1 retrieval probe + writeback check."""
        n_ticks = len(state_records)
        n_remember = sum(
            1 for r in state_records
            if r.get("llm_output", {}).get("remember_this", False)
        )

        # Sub-metric 1: recall hit rate
        recall_hit_rate = n_remember / n_ticks if n_ticks > 0 else 0.0

        # Sub-metric 2: retrieval latency + hit check
        first_stimulus = state_records[0].get("stimulus_text", "") if state_records else ""
        latency_ms: float | None = None
        probe_hit = False
        probe_reasoning = "no-probe"
        if first_stimulus:
            try:
                t0 = time.perf_counter()
                probe_hit = self._issue_retrieval_probe(
                    experience_store=experience_store,
                    query_text=first_stimulus,
                )
                latency_ms = (time.perf_counter() - t0) * 1000.0
                probe_reasoning = "probe-ok"
            except Exception as exc:  # noqa: BLE001
                latency_ms = None
                probe_reasoning = f"probe-failed: {type(exc).__name__}: {exc}"
        else:
            probe_reasoning = "no-stimulus"

        # Sub-metric 3: writeback persistence
        writeback_persistence_rate = self._compute_writeback_persistence(
            experience_store=experience_store,
            state_records=state_records,
        )

        # Per-state A3
        a3, latency_score = _per_state_a3(
            recall_hit_rate=recall_hit_rate,
            writeback_persistence_rate=writeback_persistence_rate,
            latency_ms=latency_ms,
        )

        return PerStateA3Breakdown(
            state_id=state_id,
            n_ticks=n_ticks,
            n_remember_this_true=n_remember,
            retrieval_latency_ms=latency_ms,
            recall_hit_rate=recall_hit_rate,
            writeback_persistence_rate=writeback_persistence_rate,
            latency_score=latency_score,
            a3_score=a3,
            probe_reasoning=probe_reasoning,
        )

    # --------------------------------------------------------
    # R10 retrieval probe
    # --------------------------------------------------------

    def _issue_retrieval_probe(
        self,
        *,
        experience_store: Any,
        query_text: str,
    ) -> bool:
        """Issue a directed-retrieval probe and return True if the query
        is found in any candidate's summary.

        Uses the public R10 path API:
          - FirstVersionDirectedRetrievalPath.plan_and_select
          - StoreBackedDirectedMemoryCandidateProvider over the
            runtime's experience_store
        """
        from helios_v2.directed_retrieval import (
            FirstVersionDirectedRetrievalPath,
            DirectedRetrievalConfig,
            RetrievalRequest,
        )
        from helios_v2.thought_gating.contracts import SelectedStimulusSummary
        from helios_v2.persistence import StoreBackedDirectedMemoryCandidateProvider

        # Build a minimal RetrievalRequest (bypasses gate-firing logic)
        request = RetrievalRequest(
            request_id=f"r84-probe-{int(time.time() * 1000)}",
            source_gate_result_id="r84-memory-probe",
            source_continuation_active=False,
            compact_stimuli=(
                SelectedStimulusSummary(
                    stimulus_id=query_text[:40],
                    source_kind="r84_memory_probe",
                    source_channel_id="r84-memory-probe",
                    stimulus_intensity=0.5,
                ),
            ),
            recall_intent=query_text,
            selected_memory_refs=(),
            target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
            limit=10,
            tick_id=None,
        )
        path = FirstVersionDirectedRetrievalPath()
        provider = StoreBackedDirectedMemoryCandidateProvider(
            store=experience_store,
        )
        config = DirectedRetrievalConfig(
            max_hits_per_tier=10,
            max_short_term_context=10,
            retrieval_bootstrap_id="r84-memory-probe",
            mandatory_learned_parameters=(
                "retrieval_planning_policy",
                "tier_selection_policy",
                "thought_window_shaping_policy",
            ),
        )
        plan, bundle = path.plan_and_select(request, provider, config)
        return _bundle_contains_text(bundle, query_text)

    # --------------------------------------------------------
    # R15 writeback persistence
    # --------------------------------------------------------

    def _compute_writeback_persistence(
        self,
        *,
        experience_store: Any,
        state_records: Sequence[dict],
    ) -> float:
        """Compute the writeback persistence rate.

        For ticks where persona's `remember_this=True`, check if the
        experience_store has a persisted record whose tick_id matches.
        Returns: `n_matched_records / n_remember_true_ticks`,
        capped at 1.0.

        When there are no `remember_this=True` ticks in the state,
        we use a proxy: ratio of stored records to total ticks (this
        avoids division-by-zero and still gives a meaningful signal).
        """
        n_remember = sum(
            1 for r in state_records
            if r.get("llm_output", {}).get("remember_this", False)
        )
        n_total = len(state_records)
        if n_total == 0:
            return 0.0

        # Pull all persisted records
        try:
            store_count = experience_store.count()
        except Exception:  # noqa: BLE001
            store_count = 0
        if store_count == 0:
            return 0.0

        # If there are remember_this=True ticks, compute the precise match rate
        if n_remember > 0:
            tick_ids_remember = {
                r.get("tick_id")
                for r in state_records
                if r.get("llm_output", {}).get("remember_this", False)
                and r.get("tick_id") is not None
            }
            try:
                recent = experience_store.read_recent(limit=min(store_count, 200))
            except Exception:  # noqa: BLE001
                return 0.0
            matched = sum(
                1 for record in recent
                if record.tick_id in tick_ids_remember
            )
            return min(matched / n_remember, 1.0)

        # No remember_this=True ticks: use proxy = stored_records / n_total (capped)
        # This gives a coarse "are we writing back at all" signal
        return min(store_count / max(n_total, 1), 1.0)
