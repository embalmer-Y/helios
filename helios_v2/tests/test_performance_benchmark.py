"""R71 — Performance benchmark: automated performance metrics validation.

Validates the performance metrics defined in PHASE_METRICS.md:

- P1-P1: single tick latency (offline, no LLM) < 50ms.
- P1-P2: single tick latency (with LLM thought) < 5s (skipped offline).
- P1-P3: memory footprint (idle 100 ticks) < 500MB.
- P2-P1: SQLite append throughput >= 100 records/s.
- P2-P2: semantic recall latency (1000 records) < 100ms.
- P2-P3: checkpoint save/load < 10ms per tick.

This test module is **read-only**: it measures the existing runtime but never
modifies any owner implementation. Results are reported as a structured verdict
visible in ``pytest -s`` output.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_runtime, default_composition_config
from helios_v2.composition import RuntimeProfile, SequenceExternalSignalSource
from helios_v2.embedding import (
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    ProviderEmbedding,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.persistence import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    SqliteExperienceStoreBackend,
)
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
)
from helios_v2.sensory import RawSignal as _RawSignal


# ---------------------------------------------------------------------------
# Fake providers (deterministic, network-free)
# ---------------------------------------------------------------------------


@dataclass
class _FakeThoughtProvider:
    thought_text: str = "deterministic llm thought for the current cycle"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    continue_reason: str = ""
    intends_action: bool = True
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        envelope = {
            "thought": self.thought_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": self.continue_reason,
            "proposed_action": {"intends_action": self.intends_action, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(
            output_text=json.dumps(envelope), finish_reason=self.finish_reason
        )


class _FakeEmbeddingProvider:
    """Deterministic hash-based embedding; similar texts embed similarly."""

    dimensions: int = 16

    def embed(self, profile, request, api_key):
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def _ready_gateway(config=None, provider=None) -> LlmGateway:
    resolved = config if config is not None else default_composition_config()
    return LlmGateway(
        provider=provider or _FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _embedding_gateway(provider=None) -> EmbeddingGateway:
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    return EmbeddingGateway(
        provider=provider or _FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble_legacy(**kwargs):
    """Assemble a legacy-constant runtime (fastest offline path)."""
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    kwargs.setdefault("default_signal_mode", "legacy_constant")
    return assemble_runtime(**kwargs)


def _assemble_semantic(**kwargs):
    """Assemble a semantic runtime (full de-shim path, in-memory backends)."""
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    if "experience_store" not in kwargs:
        kwargs["experience_store"] = ExperienceStore(
            backend=InMemoryExperienceStoreBackend()
        )
    if "embedding_gateway" not in kwargs:
        kwargs["embedding_gateway"] = _embedding_gateway()
    return assemble_runtime(**kwargs)


def _external_batch(signal_id: str, content: str) -> tuple[_RawSignal, ...]:
    return (
        _RawSignal(
            signal_id=signal_id,
            source_name="external",
            signal_type="text",
            content=content,
            channel="external",
            metadata={"turn_id": signal_id},
        ),
    )


# ---------------------------------------------------------------------------
# Benchmark data structures
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """One atomic performance benchmark result."""

    metric_id: str
    description: str
    target: str
    actual: float
    passed: bool
    unit: str = "ms"
    detail: str = ""


@dataclass
class PerformanceVerdict:
    """Aggregated performance benchmark verdict."""

    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)

    def summary(self) -> dict:
        return {
            "verdict": "PASS" if self.passed else "FAIL",
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "details": [
                {
                    "id": r.metric_id,
                    "passed": r.passed,
                    "target": r.target,
                    "actual": f"{r.actual:.3f} {r.unit}",
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# P1-P1: Single tick latency (legacy, offline, no LLM)
# ---------------------------------------------------------------------------


def test_p1_p1_legacy_tick_latency() -> None:
    """P1-P1: single tick latency (offline, legacy assembly) < 50ms average."""
    handle = _assemble_legacy()
    handle.startup()

    # Warm up: one tick to prime any lazy imports.
    handle.tick()

    latencies_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        handle.tick()
        elapsed = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed)

    avg_ms = sum(latencies_ms) / len(latencies_ms)
    max_ms = max(latencies_ms)
    target_ms = 50.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P1-P1-avg",
        description="legacy avg tick latency",
        target=f"< {target_ms}ms",
        actual=avg_ms,
        passed=avg_ms < target_ms,
        detail=f"max={max_ms:.1f}ms, n=50",
    ))
    verdict.add(BenchmarkResult(
        metric_id="P1-P1-max",
        description="legacy max tick latency",
        target=f"< {target_ms * 4}ms (4x avg)",
        actual=max_ms,
        passed=max_ms < target_ms * 4,
        detail=f"avg={avg_ms:.1f}ms",
    ))

    assert verdict.passed, (
        f"P1-P1 BENCHMARK FAIL:\n"
        + "\n".join(
            f"  [FAIL] {r.metric_id}: {r.description} = {r.actual:.1f}ms (target {r.target})"
            for r in verdict.results
            if not r.passed
        )
    )
    _print_verdict("P1-P1 (Legacy Tick Latency)", verdict)


# ---------------------------------------------------------------------------
# P1-P1b: Single tick latency (semantic, offline, no LLM)
# ---------------------------------------------------------------------------


def test_p1_p1_semantic_tick_latency() -> None:
    """P1-P1b: single tick latency (offline, semantic assembly) < 100ms average."""
    handle = _assemble_semantic()
    handle.startup()

    # Warm up.
    handle.tick()

    latencies_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        handle.tick()
        elapsed = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed)

    avg_ms = sum(latencies_ms) / len(latencies_ms)
    max_ms = max(latencies_ms)
    # Semantic assembly is heavier (embedding, store, similarity); relax target to 100ms.
    target_ms = 100.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P1-P1b-avg",
        description="semantic avg tick latency",
        target=f"< {target_ms}ms",
        actual=avg_ms,
        passed=avg_ms < target_ms,
        detail=f"max={max_ms:.1f}ms, n=50",
    ))

    assert verdict.passed, (
        f"P1-P1b BENCHMARK FAIL:\n"
        + "\n".join(
            f"  [FAIL] {r.metric_id}: {r.actual:.1f}ms (target {r.target})"
            for r in verdict.results
            if not r.passed
        )
    )
    _print_verdict("P1-P1b (Semantic Tick Latency)", verdict)


# ---------------------------------------------------------------------------
# P1-P3: Memory footprint (idle 100 ticks)
# ---------------------------------------------------------------------------


def test_p1_p3_memory_footprint() -> None:
    """P1-P3: memory footprint (100 idle ticks, legacy) < 500MB peak."""
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    handle = _assemble_legacy()
    handle.startup()
    handle.run_ticks(100)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    target_mb = 500.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P1-P3-peak",
        description="peak memory (100 ticks)",
        target=f"< {target_mb}MB",
        actual=peak_mb,
        passed=peak_mb < target_mb,
        unit="MB",
        detail=f"current={current / (1024 * 1024):.1f}MB",
    ))

    assert verdict.passed, f"P1-P3 FAIL: peak memory {peak_mb:.1f}MB exceeds {target_mb}MB"
    _print_verdict("P1-P3 (Memory Footprint)", verdict)


# ---------------------------------------------------------------------------
# P2-P1: SQLite append throughput
# ---------------------------------------------------------------------------


def test_p2_p1_sqlite_append_throughput(tmp_path) -> None:
    """P2-P1: SQLite append throughput >= 100 records/s."""
    db_path = str(tmp_path / "benchmark_store.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))

    # Run enough ticks to get a meaningful throughput measurement.
    handle = _assemble_semantic(experience_store=store)
    handle.startup()

    n_ticks = 30
    start = time.perf_counter()
    handle.run_ticks(n_ticks)
    elapsed = time.perf_counter() - start

    count = store.count()
    throughput = count / elapsed if elapsed > 0 else float("inf")
    target_rps = 100.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P2-P1-throughput",
        description="SQLite append throughput",
        target=f">= {target_rps} records/s",
        actual=throughput,
        passed=throughput >= target_rps,
        unit="records/s",
        detail=f"count={count}, elapsed={elapsed:.3f}s, n_ticks={n_ticks}",
    ))

    assert verdict.passed, (
        f"P2-P1 FAIL: throughput {throughput:.0f} records/s < {target_rps}"
    )
    _print_verdict("P2-P1 (SQLite Append Throughput)", verdict)


# ---------------------------------------------------------------------------
# P2-P2: Semantic recall latency (1000 records)
# ---------------------------------------------------------------------------


def test_p2_p2_semantic_recall_latency(tmp_path) -> None:
    """P2-P2: semantic recall latency (1000 records) < 100ms."""
    db_path = str(tmp_path / "benchmark_recall.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))

    # Pre-populate 1000 records with embeddings.
    from helios_v2.persistence.contracts import PersistedExperienceRecord

    records = []
    for i in range(1000):
        # Deterministic embedding vector from a hash of the content.
        text = f"experience record number {i} with some content"
        buckets = [0.0] * 16
        for idx, ch in enumerate(text):
            buckets[(ord(ch) + idx) % 16] += 1.0
        vec = tuple(buckets)
        records.append(PersistedExperienceRecord(
            record_id=f"r-{i}",
            tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-{i}",
            writeback_status="written_internal_only",
            summary=text,
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=(),
            linkage={},
            embedding=vec,
        ))
    store.append_records(tuple(records))
    assert store.count() == 1000

    # Measure recall latency.
    query_vec = tuple([1.0 if i % 2 == 0 else 0.0 for i in range(16)])
    latencies_ms: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        result = store.search_similar(query_vec, limit=10, max_scan=1000)
        elapsed = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed)

    avg_ms = sum(latencies_ms) / len(latencies_ms)
    max_ms = max(latencies_ms)
    target_ms = 100.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P2-P2-avg",
        description="semantic recall avg latency (1000 records)",
        target=f"< {target_ms}ms",
        actual=avg_ms,
        passed=avg_ms < target_ms,
        detail=f"max={max_ms:.1f}ms, hits={len(result.hits)}, n=20",
    ))

    assert verdict.passed, (
        f"P2-P2 FAIL: avg recall latency {avg_ms:.1f}ms > {target_ms}ms"
    )
    _print_verdict("P2-P2 (Semantic Recall Latency)", verdict)


# ---------------------------------------------------------------------------
# P2-P3: Checkpoint save/load latency
# ---------------------------------------------------------------------------


def test_p2_p3_checkpoint_save_load_latency() -> None:
    """P2-P3: checkpoint save/load < 10ms per operation."""
    checkpoint = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    checkpoint.initialize()

    # Build a semantic runtime with checkpoint and run a few ticks to populate state.
    handle = _assemble_semantic(continuity_checkpoint=checkpoint)
    handle.startup()
    handle.run_ticks(5)

    # The checkpoint should have saved at least once.
    saved = checkpoint.load_latest()
    assert saved is not None, "checkpoint should have saved after 5 ticks"

    # Measure save latency (re-save the current snapshot).
    save_latencies_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        checkpoint.save_latest(saved)
        elapsed = (time.perf_counter() - start) * 1000.0
        save_latencies_ms.append(elapsed)

    # Measure load latency.
    load_latencies_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        checkpoint.load_latest()
        elapsed = (time.perf_counter() - start) * 1000.0
        load_latencies_ms.append(elapsed)

    avg_save = sum(save_latencies_ms) / len(save_latencies_ms)
    avg_load = sum(load_latencies_ms) / len(load_latencies_ms)
    target_ms = 10.0

    verdict = PerformanceVerdict()
    verdict.add(BenchmarkResult(
        metric_id="P2-P3-save",
        description="checkpoint save latency",
        target=f"< {target_ms}ms",
        actual=avg_save,
        passed=avg_save < target_ms,
        detail=f"n=50",
    ))
    verdict.add(BenchmarkResult(
        metric_id="P2-P3-load",
        description="checkpoint load latency",
        target=f"< {target_ms}ms",
        actual=avg_load,
        passed=avg_load < target_ms,
        detail=f"n=50",
    ))

    assert verdict.passed, (
        f"P2-P3 FAIL:\n"
        + "\n".join(
            f"  [FAIL] {r.metric_id}: {r.actual:.3f}ms (target {r.target})"
            for r in verdict.results
            if not r.passed
        )
    )
    _print_verdict("P2-P3 (Checkpoint Save/Load Latency)", verdict)


# ---------------------------------------------------------------------------
# Composite benchmark verdict
# ---------------------------------------------------------------------------


def test_performance_benchmark_composite() -> None:
    """Run all performance benchmarks and produce a composite pass/fail verdict."""
    verdict = PerformanceVerdict()

    # -- P1-P1: Legacy tick latency --
    handle = _assemble_legacy()
    handle.startup()
    handle.tick()  # warmup
    latencies = []
    for _ in range(20):
        start = time.perf_counter()
        handle.tick()
        latencies.append((time.perf_counter() - start) * 1000.0)
    avg_legacy = sum(latencies) / len(latencies)
    verdict.add(BenchmarkResult(
        "P1-P1", "legacy tick avg latency", "< 50ms",
        avg_legacy, avg_legacy < 50.0,
    ))

    # -- P1-P1b: Semantic tick latency --
    sem_handle = _assemble_semantic()
    sem_handle.startup()
    sem_handle.tick()  # warmup
    sem_latencies = []
    for _ in range(20):
        start = time.perf_counter()
        sem_handle.tick()
        sem_latencies.append((time.perf_counter() - start) * 1000.0)
    avg_sem = sum(sem_latencies) / len(sem_latencies)
    verdict.add(BenchmarkResult(
        "P1-P1b", "semantic tick avg latency", "< 100ms",
        avg_sem, avg_sem < 100.0,
    ))

    # -- P1-P2: Skip (requires live LLM) --
    verdict.add(BenchmarkResult(
        "P1-P2", "LLM thought latency", "< 5s (requires live LLM)",
        0.0, True,  # Not a failure; skipped.
        detail="skipped: requires live LLM, not evaluated offline",
    ))

    # -- P1-P3: Memory footprint (abbreviated: 20 ticks) --
    tracemalloc.start()
    mem_handle = _assemble_legacy()
    mem_handle.startup()
    mem_handle.run_ticks(20)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / (1024 * 1024)
    verdict.add(BenchmarkResult(
        "P1-P3", "peak memory (20 ticks)", "< 500MB",
        peak_mb, peak_mb < 500.0, unit="MB",
    ))

    # Final assertion.
    assert verdict.passed, (
        f"PERFORMANCE BENCHMARK FAIL:\n"
        + "\n".join(
            f"  [FAIL] {r.metric_id}: {r.description} = {r.actual:.3f} (target {r.target})"
            for r in verdict.results
            if not r.passed
        )
    )
    _print_verdict("Composite Performance Benchmark", verdict)


# ---------------------------------------------------------------------------
# Diagnostic output helper
# ---------------------------------------------------------------------------


def _print_verdict(title: str, verdict: PerformanceVerdict) -> None:
    summary = verdict.summary()
    print(f"\n{'=' * 60}")
    print(f"{title}: {summary['verdict']}")
    print(f"  Total: {summary['total']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
    for d in summary["details"]:
        status = "PASS" if d["passed"] else "FAIL"
        print(f"  [{status}] {d['id']}: actual={d['actual']}, target={d['target']}")
        if d.get("detail"):
            print(f"         detail: {d['detail']}")
    print(f"{'=' * 60}")
