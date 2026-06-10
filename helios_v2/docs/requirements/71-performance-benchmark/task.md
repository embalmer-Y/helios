# Requirement 71 - Performance Benchmark — Task

## 1. Task Breakdown

### Task A: Create benchmark module skeleton and tick latency tests

**Scope**: New `test_performance_benchmark.py` with helpers, `BenchmarkResult`, and P1-P1 tests.
**Dependency**: None.
**Touched modules**:
- `helios_v2/tests/test_performance_benchmark.py`

**Completion definition**:
- `BenchmarkResult` dataclass defined.
- `test_p1_p1_legacy_tick_latency` and `test_p1_p1_semantic_tick_latency` pass.
- Fake providers (`_ready_gateway`, `_embedding_gateway`) support offline assembly.

**Validation step**:
```
pytest helios_v2/tests/test_performance_benchmark.py -v -k "p1_p1"
```

### Task B: Memory footprint and persistence throughput tests

**Scope**: P1-P3, P2-P1, P2-P2, P2-P3 tests.
**Dependency**: Task A (module skeleton + helpers).
**Touched modules**:
- `helios_v2/tests/test_performance_benchmark.py`

**Completion definition**:
- `test_p1_p3_memory_footprint` passes (100 ticks < 500 MB).
- `test_p2_p1_sqlite_append_throughput` passes (≥ 100 records/s).
- `test_p2_p2_semantic_recall_latency` passes (< 100 ms for 1000 records).
- `test_p2_p3_checkpoint_save_load_latency` passes (< 10 ms per tick).

**Validation step**:
```
pytest helios_v2/tests/test_performance_benchmark.py -v -k "p1_p3 or p2_p"
```

### Task C: Composite verdict and documentation sync

**Scope**: Aggregate verdict test + index.md update.
**Dependency**: Task B (all benchmarks exist).
**Touched modules**:
- `helios_v2/tests/test_performance_benchmark.py`
- `helios_v2/docs/requirements/index.md`

**Completion definition**:
- `test_performance_benchmark_composite` passes.
- `index.md` contains R71 row.
- Full suite green.

**Validation step**:
```
pytest helios_v2/tests/test_performance_benchmark.py -v
```

## 2. Dependencies

```
Task A (skeleton + latency) → Task B (memory + persistence) → Task C (composite + docs)
```

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/tests/test_performance_benchmark.py` | Add | 7 benchmark tests + helpers |
| `helios_v2/docs/requirements/index.md` | Add row | R71 entry |

## 4. Implementation Order

1. Task A: Skeleton + P1-P1 latency tests.
2. Task B: P1-P3 memory + P2-P1/P2/P3 persistence tests.
3. Task C: Composite verdict + docs.

## 5. Validation Plan

| Task | Validation command |
|------|-------------------|
| A | `pytest helios_v2/tests/test_performance_benchmark.py -v -k "p1_p1"` |
| B | `pytest helios_v2/tests/test_performance_benchmark.py -v -k "p1_p3 or p2_p"` |
| C | `pytest helios_v2/tests/test_performance_benchmark.py -v` |

Final: `pytest helios_v2/tests/ -x` (full suite green).

## 6. Completion Criteria

1. All 7 benchmark tests pass offline.
2. Each benchmark validates its `PHASE_METRICS.md` target.
3. Composite verdict aggregates all results.
4. `index.md` updated with R71 row.
