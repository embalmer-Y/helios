# Requirement 71 - Performance Benchmark — Design

## 1. Design Overview

A read-only test module that validates every `PHASE_METRICS.md` performance target
using the existing runtime. Tests assemble a runtime via `assemble_runtime()`, execute
ticks or persistence operations, measure wall-clock time / memory / throughput, and
assert against documented thresholds. A composite verdict test aggregates all results.

## 2. Current State and Gap

`PHASE_METRICS.md` defines P1-P1 through P2-P3 performance targets, but no automated
test validates them. Manual measurement is required during phase exit reviews, which
is error-prone and non-reproducible.

## 3. Target Architecture

```
test_performance_benchmark.py
├── BenchmarkResult dataclass — structured metric reporting
├── test_p1_p1_legacy_tick_latency     — P1-P1 legacy assembly
├── test_p1_p1_semantic_tick_latency   — P1-P1 semantic assembly
├── test_p1_p3_memory_footprint        — P1-P3 tracemalloc
├── test_p2_p1_sqlite_append_throughput — P2-P1 write burst
├── test_p2_p2_semantic_recall_latency — P2-P2 1000-record search
├── test_p2_p3_checkpoint_save_load_latency — P2-P3 round-trip
└── test_performance_benchmark_composite    — aggregate verdict
```

## 4. Data Structures

### 4.1 BenchmarkResult

```python
@dataclass
class BenchmarkResult:
    metric_id: str       # e.g. "P1-P1"
    name: str            # e.g. "legacy tick latency"
    passed: bool
    value: float         # measured value
    threshold: float     # target threshold
    unit: str            # "ms", "MB", "records/s"
    detail: str = ""
```

## 5. Module Changes

### 5.1 `tests/test_performance_benchmark.py`

New module. No production code changes.

Helpers:
- `_legacy_assembly()` — `assemble_runtime(default_signal_mode="legacy_constant")`
- `_semantic_assembly()` — `assemble_runtime()` (default semantic)
- `_embedding_gateway()` / `_ready_gateway()` — fake providers for offline use
- `_record(i)` — factory for `PersistedExperienceRecord` with known embedding

## 6. Migration Plan

No migration needed — this is a pure additive test module.

## 7. Failure Modes and Constraints

1. **CI variability**: latency thresholds use 2× margin to absorb CI jitter.
2. **Platform differences**: memory footprint threshold (500 MB) is generous; real
   usage is typically < 100 MB.
3. **Offline constraint**: P1-P2 (with LLM) is skipped when no live gateway is
   available; the test is structurally defined but marked `skip`.

## 8. Observability and Logging

No new logging. Benchmark results are printed via `print()` in `pytest -s` mode
and captured in the composite verdict.

## 9. Validation Strategy

1. Each benchmark test independently validates one PHASE_METRICS target.
2. Composite test aggregates all results into one pass/fail.
3. All tests run offline without modifying owner code.
