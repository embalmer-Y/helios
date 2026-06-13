"""R90 memory-fidelity probe core.

`run_memory_fidelity_probe(handle_factory, config)` drives a real durable production-shaped runtime and
returns a `MemoryFidelityReport`. It is read-only on owner state and offline: it exercises only the
public `tick()` and the public `ExperienceStore` facade, imports no owner internals, and emits no
`print`/`logging` (R21 discipline). It asserts nothing; a consuming test renders/asserts.

Metrics (all bounded `[0,1]`, honest absence is `None`, never a fabricated number):
  - recall_hit_rate (R10 end-to-end): fired ticks whose `10` bundle held a store-sourced hit, over
    fired ticks where the store was non-empty.
  - writeback_persistence_rate (R15 -> R33): this-run appended records that survive a restart.
  - latency_score (R34/R33): bounded `search_similar` median latency.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field

_RETRIEVAL_STAGE = "directed_retrieval_into_thought_window"


@dataclass(frozen=True)
class MemoryFidelityConfig:
    """Configuration for one memory-fidelity probe run."""

    ticks: int = 60
    latency_threshold_ms: float = 100.0
    latency_trials: int = 5
    search_limit: int = 5
    recent_probe_limit: int = 10
    store_hit_source_prefix: str = "experience_store"


@dataclass
class MemoryFidelityReport:
    """The structured outcome of one memory-fidelity probe (no logging; a test renders/asserts)."""

    ticks_requested: int
    ticks_completed: int = 0
    crash: str | None = None
    reason: str | None = None
    store_count_start: int = 0
    store_count_end: int = 0
    appended: int = 0
    survived_after_restart: int = 0
    recall_possible_ticks: int = 0
    recall_hit_ticks: int = 0
    self_recall_probes: int = 0
    self_recall_hits: int = 0
    latency_median_ms: float | None = None
    recall_hit_rate: float | None = None
    writeback_persistence_rate: float = 0.0
    latency_score: float | None = None

    @property
    def fidelity_score(self) -> float | None:
        present = [
            metric
            for metric in (
                self.recall_hit_rate,
                self.writeback_persistence_rate,
                self.latency_score,
            )
            if metric is not None
        ]
        if not present:
            return None
        return sum(present) / len(present)

    @property
    def usable(self) -> bool:
        return (
            self.crash is None
            and self.reason is None
            and self.ticks_completed == self.ticks_requested
            and self.writeback_persistence_rate is not None
            and (self.recall_hit_rate is not None or self.latency_score is not None)
        )

    def violations(self) -> list[str]:
        out: list[str] = []
        if self.crash is not None:
            out.append(f"crash: {self.crash}")
        if self.reason is not None:
            out.append(f"reason: {self.reason}")
        if self.ticks_completed != self.ticks_requested:
            out.append(f"incomplete: {self.ticks_completed}/{self.ticks_requested} ticks")
        if self.appended <= 0:
            out.append("no records appended (writeback did not persist)")
        return out

    def summary(self) -> str:
        def _fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.4f}"

        fidelity = self.fidelity_score
        lines = [
            f"R90 memory fidelity: usable={self.usable} fidelity_score={_fmt(fidelity)} "
            f"({self.ticks_completed}/{self.ticks_requested} ticks)",
            f"  recall_hit_rate={_fmt(self.recall_hit_rate)} "
            f"(hits {self.recall_hit_ticks}/{self.recall_possible_ticks} recall-possible ticks)",
            f"  writeback_persistence_rate={_fmt(self.writeback_persistence_rate)} "
            f"(store {self.store_count_start}->{self.store_count_end}, appended {self.appended}, "
            f"survived {self.survived_after_restart})",
            f"  latency_score={_fmt(self.latency_score)} "
            f"(median {_fmt(self.latency_median_ms)} ms; self-recall "
            f"{self.self_recall_hits}/{self.self_recall_probes})",
        ]
        violations = self.violations()
        if violations:
            lines.append("  violations: " + "; ".join(violations))
        return "\n".join(lines)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _store_count(store) -> int:
    try:
        return int(store.count())
    except Exception:  # noqa: BLE001 - count is diagnostic; never fail the probe on it
        return -1


def _has_store_hit(bundle, prefix: str) -> bool:
    if bundle is None:
        return False
    tiers = (
        getattr(bundle, "short_term_context", ()),
        getattr(bundle, "mid_term_hits", ()),
        getattr(bundle, "long_term_hits", ()),
        getattr(bundle, "autobiographical_hits", ()),
    )
    for tier in tiers:
        for hit in tier:
            source = getattr(hit, "source", "") or ""
            if source.startswith(prefix):
                return True
    return False


def _measure_latency_and_self_recall(store, config: MemoryFidelityConfig) -> tuple[
    float | None, int, int
]:
    """Time `search_similar` over embedded recent records; return (median_ms, probes, self_hits)."""

    try:
        recents = store.read_recent(config.recent_probe_limit)
    except Exception:  # noqa: BLE001 - read is diagnostic; degrade to no latency sample
        return None, 0, 0

    embedded = [record for record in recents if getattr(record, "embedding", None)]
    timings_ms: list[float] = []
    self_hits = 0
    probes = 0
    for record in embedded[: config.latency_trials]:
        probes += 1
        started = time.perf_counter()
        try:
            result = store.search_similar(record.embedding, config.search_limit)
        except Exception:  # noqa: BLE001 - a search failure contributes no timing/hit
            continue
        timings_ms.append((time.perf_counter() - started) * 1000.0)
        hit_ids = {getattr(hit.record, "record_id", None) for hit in getattr(result, "hits", ())}
        if getattr(record, "record_id", None) in hit_ids:
            self_hits += 1

    median = statistics.median(timings_ms) if timings_ms else None
    return median, probes, self_hits


def run_memory_fidelity_probe(
    handle_factory, config: MemoryFidelityConfig = MemoryFidelityConfig()
) -> MemoryFidelityReport:
    """Drive a durable runtime and measure the R10+R15 memory loop end to end.

    `handle_factory` must build a (not-yet-started) runtime over a FIXED durable data directory each
    call, so the probe can call it a second time to measure cross-restart persistence against the same
    store. The first handle is driven `config.ticks` ticks; the second is only started (to read the
    persisted count).
    """

    report = MemoryFidelityReport(ticks_requested=config.ticks)

    try:
        handle = handle_factory()
        handle.startup()
    except Exception as error:  # noqa: BLE001 - a startup failure is a recorded reason, not a raise
        report.reason = f"startup_failed: {type(error).__name__}: {error}"
        return report

    store = getattr(handle, "experience_store", None)
    if store is None:
        report.reason = "no_experience_store"
        return report

    report.store_count_start = _store_count(store)

    for tick_index in range(config.ticks):
        store_before = _store_count(store)
        try:
            result = handle.tick()
        except Exception as error:  # noqa: BLE001 - a per-tick crash is the headline fact
            report.crash = f"tick {tick_index}: {type(error).__name__}: {error}"
            break
        report.ticks_completed += 1

        stage_results = getattr(result, "stage_results", {}) or {}
        retrieval = stage_results.get(_RETRIEVAL_STAGE)
        if retrieval is not None and getattr(retrieval, "activated", False) and store_before > 0:
            report.recall_possible_ticks += 1
            if _has_store_hit(getattr(retrieval, "bundle", None), config.store_hit_source_prefix):
                report.recall_hit_ticks += 1

    report.store_count_end = _store_count(store)
    report.appended = report.store_count_end - report.store_count_start

    median_ms, probes, self_hits = _measure_latency_and_self_recall(store, config)
    report.latency_median_ms = median_ms
    report.self_recall_probes = probes
    report.self_recall_hits = self_hits

    # Restart: a fresh runtime over the same durable directory; read the persisted count before any
    # tick to measure cross-restart survival of this run's writeback.
    try:
        restart = handle_factory()
        restart.startup()
        report.survived_after_restart = _store_count(restart.experience_store)
    except Exception as error:  # noqa: BLE001 - a restart failure is a recorded reason
        report.reason = f"restart_failed: {type(error).__name__}: {error}"
        return report

    # Metrics.
    if report.recall_possible_ticks > 0:
        report.recall_hit_rate = report.recall_hit_ticks / report.recall_possible_ticks
    if report.appended > 0:
        report.writeback_persistence_rate = _clamp(
            (report.survived_after_restart - report.store_count_start) / report.appended
        )
    else:
        report.writeback_persistence_rate = 0.0
    if median_ms is not None and median_ms > 0:
        report.latency_score = _clamp(config.latency_threshold_ms / median_ms)
    elif median_ms is not None:
        report.latency_score = 1.0  # an immeasurably fast (sub-microsecond) search is full score

    return report
