# Requirement 90 - Memory Fidelity Probe (Real R10+R15 End-to-End)

## 1. Design Overview

Add a tests-only package `tests/r90_memory_fidelity_probe/` with a reusable probe
(`memory_fidelity_probe.py`) and a verification module (`test_r90_memory_fidelity_probe.py`). The probe
drives a real durable production-shaped runtime, measures three bounded memory-fidelity metrics from
real runtime/store provenance, composes a `MemoryFidelityReport`, and returns it without asserting or
logging. R89's `evaluate_turing` gains one additive optional `memory_fidelity_probe` parameter that
turns the `memory_fidelity` axis from the stub into a real reconstructed axis when a usable report is
supplied. No runtime/owner code changes.

## 2. Current State and Gap

1. `assemble_production_runtime(data_dir, gateway)` yields a durable SQLite-backed, semantic,
   checkpointed runtime that runs offline with a deterministic fake gateway + offline hash embedding;
   `handle.experience_store` exposes the `33` `ExperienceStore` facade.
2. `RuntimeTickResult.stage_results["directed_retrieval_into_thought_window"]` is a
   `DirectedRetrievalStageResult` with `activated: bool` and `bundle: ThoughtWindowBundle | None`; the
   bundle's `short_term_context`/`mid_term_hits`/`long_term_hits`/`autobiographical_hits` are
   `ThoughtWindowHit`s carrying `source`. Store-recalled hits use `source="experience_store_semantic"`.
3. `ExperienceStore` exposes `count()`, `read_recent(limit)`, and
   `search_similar(query_vector, limit, max_scan) -> SimilaritySearchResult` (`hits[*].record`);
   `PersistedExperienceRecord.embedding: tuple[float, ...] | None`.
4. R89's `memory_fidelity` axis is a `STUBBED` placeholder; nothing measures the real loop.

## 3. Target Architecture

### 3.1 `memory_fidelity_probe.py`

- `MemoryFidelityConfig(ticks=60, latency_threshold_ms=100.0, latency_trials=5, search_limit=5,
  recent_probe_limit=10, store_hit_source_prefix="experience_store")`.
- `MemoryFidelityReport` - `ticks_requested`/`ticks_completed`, `crash`, `store_count_start`/`_end`,
  `appended`, `survived_after_restart`, `recall_possible_ticks`/`recall_hit_ticks`,
  `self_recall_probes`/`self_recall_hits`, `latency_median_ms`, the three metrics
  (`recall_hit_rate: float | None`, `writeback_persistence_rate: float`, `latency_score: float | None`),
  `reason: str | None`, derived `fidelity_score`/`usable`, `violations()`, `summary()`.
- `_has_store_hit(bundle, prefix)` - True iff any hit across the four tiers has a `source` starting with
  `prefix`.
- `run_memory_fidelity_probe(handle_factory, config=MemoryFidelityConfig()) -> MemoryFidelityReport`:
  1. `handle = handle_factory(); handle.startup()`; `store = handle.experience_store`;
     `store_count_start = store.count()`.
  2. Per tick (`try/except` → `crash`, stop): read `store.count()` before the tick; `result =
     handle.tick()`; inspect `result.stage_results["directed_retrieval_into_thought_window"]`; if
     `activated` and the pre-tick store count `> 0`, `recall_possible_ticks += 1` and, if
     `_has_store_hit(bundle)`, `recall_hit_ticks += 1`.
  3. `store_count_end = store.count()`; `appended = store_count_end - store_count_start`.
  4. Latency + self-recall: `recents = store.read_recent(recent_probe_limit)`; for up to
     `latency_trials` records carrying an embedding, time `store.search_similar(record.embedding,
     search_limit)`, record the elapsed ms, and count a self-recall hit when the record's id appears in
     the result hits. `latency_median_ms` = median of the timings (or `None`).
  5. Restart: `restart = handle_factory(); restart.startup()`; `survived_after_restart =
     restart.experience_store.count()` (read before any tick).
  6. Compute metrics (below) and return the report.

### 3.2 Metric computation

1. `recall_hit_rate = recall_hit_ticks / recall_possible_ticks` when `recall_possible_ticks > 0`, else
   `None`.
2. `writeback_persistence_rate = clamp((survived_after_restart - store_count_start) / appended, 0, 1)`
   when `appended > 0`, else `0.0`.
3. `latency_score = clamp(latency_threshold_ms / latency_median_ms, 0, 1)` when `latency_median_ms` is
   a positive number, else `None` (a zero/near-zero median clamps to `1.0`).
4. `fidelity_score` = mean of the present values among `{recall_hit_rate, writeback_persistence_rate,
   latency_score}`; `None` when none present.
5. `usable = crash is None and ticks_completed == ticks_requested and writeback_persistence_rate is not
   None and (recall_hit_rate is not None or latency_score is not None)`.

### 3.3 R89 harness integration (additive)

- `evaluate_turing(..., memory_fidelity_probe: MemoryFidelityReport | None = None)`.
- In the axis loop, when scoring `MEMORY_FIDELITY`: if `memory_fidelity_probe is not None` and
  `memory_fidelity_probe.usable` and its `fidelity_score is not None`, emit an `AVAILABLE` axis with
  `judge_track = RECONSTRUCTED`, `score = fidelity_score`, and provenance naming the probe metrics;
  otherwise keep the existing `_stubbed_axis(...)` path (byte-for-byte R89 behavior).
- The harness imports the report type structurally (duck-typed: it reads `.usable`/`.fidelity_score`),
  so `r89_turing_harness` gains no hard import of the `r90` package (the dependency direction is the
  test supplying the report).

### 3.4 `test_r90_memory_fidelity_probe.py`

- A `handle_factory(tmp_path)` closure building `assemble_production_runtime(data_dir, gateway=
  deterministic)` (the R83 deterministic-gateway pattern).
- Probe metrics: `run_memory_fidelity_probe` yields a usable report; assert
  `writeback_persistence_rate` high, the three metrics in `[0,1]` (or `None` where honestly absent),
  `fidelity_score` in `[0,1]`, and `appended > 0` (the durable loop ran). Render `summary()`.
- R89 integration: feed the report to `evaluate_turing`; assert `memory_fidelity` is `AVAILABLE` /
  `reconstructed` / `score == fidelity_score` / non-empty provenance; assert without it the axis stays
  `STUBBED`.
- Robustness: an unusable report (crash/empty) leaves the R89 axis stubbed; a crashing factory yields
  `usable == False` with a reason.

## 4. Data Structures

`MemoryFidelityConfig`, `MemoryFidelityReport` (tests-only). One additive optional parameter on the
existing R89 `evaluate_turing`. No runtime contract changes.

## 5. Module Changes

1. New `tests/r90_memory_fidelity_probe/__init__.py`, `memory_fidelity_probe.py`,
   `test_r90_memory_fidelity_probe.py`.
2. Additive edit to `tests/r89_turing_harness/turing_harness.py` (`memory_fidelity_probe` parameter +
   the available-axis branch).
3. Docs: `requirements/index.md` row 90; `ROADMAP.zh-CN.md` R90 delivered.

## 6. Migration Plan

1. Tests-only plus one additive optional harness parameter; no runtime/owner code is touched.
2. R89's existing tests call `evaluate_turing` without the new parameter, so they keep the stub path
   and stay green; the new R90 tests exercise the available path.
3. The probe reuses the deterministic offline production assembly, so it is network-free and
   reproducible.

## 7. Failure Modes and Constraints

1. A per-tick crash is captured as `crash` (not propagated); `usable == False`.
2. A metric with no opportunity (no recall-possible tick / no embedded record) is `None`, excluded from
   `fidelity_score`, and (for the two required ones) makes the report unusable.
3. The R89 axis stays stubbed for an absent or unusable report — the stub path is preserved exactly.
4. No `print`/`logging`; no owner-internal imports; read-only on owner state.

## 8. Observability and Logging

No new logging mechanism and no `print`/`logging` in the probe. The probe test renders `summary()` via
`print` (allowed in tests, not in `src/`) so the memory-fidelity readout appears in the CI log.

## 9. Validation Strategy

1. CI: `pytest helios_v2/tests/r90_memory_fidelity_probe -q` - the probe yields a usable report with a
   high writeback-persistence rate and bounded metrics, and the R89 integration turns `memory_fidelity`
   into a real available axis.
2. Regression: `pytest helios_v2/tests/r89_turing_harness -q` stays green (stub path preserved); the
   full network-free suite stays green.
3. Falsifiable: an unusable report keeps the axis stubbed; the persistence rate falls below 1.0 if
   records do not survive the restart.
