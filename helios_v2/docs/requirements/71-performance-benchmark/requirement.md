# Requirement 71 - Performance Benchmark

## 1. Background and Problem

`PHASE_METRICS.md` defines quantitative performance targets for P1 and P2 exit:

- P1-P1: single tick latency (offline, no LLM) < 50 ms
- P1-P2: single tick latency (with LLM thought) < 5 s
- P1-P3: memory footprint (idle 100 ticks) < 500 MB
- P2-P1: SQLite append throughput ≥ 100 records/s
- P2-P2: semantic recall latency (1000 records) < 100 ms
- P2-P3: checkpoint save/load < 10 ms per tick

These targets are documented but have no automated validation. Performance regressions
could go unnoticed until a phase exit review surfaces them manually.

## 2. Goal

Provide a read-only, automated performance benchmark suite that validates every
`PHASE_METRICS.md` performance target against the current runtime, producing a structured
verdict that makes regressions visible in CI or local `pytest` runs.

## 3. Functional Requirements

### 3.1 Tick latency benchmarks

1. A test must measure single-tick wall-clock latency under the legacy constant assembly
   (no LLM) and assert it is under 50 ms (P1-P1).
2. A test must measure single-tick wall-clock latency under the semantic assembly
   (no LLM) and assert it is under 50 ms (P1-P1 semantic variant).
3. P1-P2 (with LLM thought) must be structurally defined but may be skipped when no
   live LLM is available (network-offline constraint G-2).

### 3.2 Memory footprint benchmark

1. A test must run 100 idle ticks under the semantic assembly and measure peak memory
   via `tracemalloc`, asserting it stays under 500 MB (P1-P3).

### 3.3 Persistence throughput benchmarks

1. A test must measure SQLite append throughput over a burst of `PersistedExperienceRecord`
   writes and assert ≥ 100 records/s (P2-P1).
2. A test must measure `search_similar` latency against a 1000-record in-memory store
   and assert < 100 ms (P2-P2).
3. A test must measure checkpoint save/load round-trip latency and assert < 10 ms per
   tick (P2-P3).

### 3.4 Composite verdict

1. A composite test must aggregate all individual benchmark results into a single
   pass/fail verdict with human-readable metrics.

## 4. Non-Functional Requirements

1. **Offline**: all benchmarks must run without network access (G-2).
2. **Read-only**: benchmarks must not modify any owner implementation; they measure
   the existing runtime as-is.
3. **Deterministic**: results must be reproducible on the same hardware within a
   reasonable tolerance (2× margin for CI variability).

## 5. Code Behavior Constraints

1. Benchmark tests must not call any cognitive owner directly; they must use
   `assemble_runtime()` and `handle.tick()` / `handle.run_ticks()`.
2. Benchmarks must not depend on a specific LLM gateway configuration.
3. Memory measurement must use `tracemalloc` (stdlib), not third-party profilers.

## 6. Impacted Modules

1. `helios_v2/tests/test_performance_benchmark.py` — new test module.
2. `helios_v2/docs/requirements/index.md` — new R71 row.
3. `helios_v2/docs/PHASE_METRICS.md` — reference only (no change).

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_performance_benchmark.py -v` passes all tests offline.
2. Each benchmark produces a measurable metric value visible in test output.
3. The composite verdict test passes when all individual benchmarks pass.
4. Full suite still passes (`pytest helios_v2/tests/ -x`).
