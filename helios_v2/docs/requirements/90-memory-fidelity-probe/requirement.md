# Requirement 90 - Memory Fidelity Probe (Real R10+R15 End-to-End)

## 1. Background and Problem

R89 shipped the Turing-style evaluation harness with six locked rubric axes. Five of those axes are
either reconstructed from real provenance (`bio_responsiveness`, `cross_tick_continuity`,
`agency_locking`) or honestly marked unavailable (the behavior axes). The sixth, `memory_fidelity`, is
a `stubbed_pending_real_probe` placeholder fixed at `0.5` — explicitly a stub that "cannot contribute a
passing score" and forces the verdict to `incomplete`.

A stub is the right honest first step, but the memory loop it stands for is real and measurable today:
the `15` experience-writeback stream is durably persisted into the `33` store and re-enters the `10`
directed-retrieval thought window by semantic similarity (`34`), surviving a process restart (R33/R42).
Nothing yet measures whether that loop actually closes — whether persisted experience is really
recalled by `10`, whether writeback really persists across a restart, and whether recall latency is
bounded. Until it does, the Turing harness cannot score memory fidelity from real runtime truth.

ROADMAP §4 R90 defines exactly this: replace the harness `memory_fidelity` stub with a real R10+R15
end-to-end probe scored on `recall_hit_rate` / `writeback_persistence_rate` / `latency_score`.

## 2. Goal

Add a read-only, deterministic, network-free memory-fidelity probe that drives a real durable
production-shaped runtime, measures `recall_hit_rate` (fired ticks whose published `10` thought-window
bundle contains a store-sourced hit, over fired ticks where the store was non-empty),
`writeback_persistence_rate` (this-run `15` records that survive a process restart against the same
durable store), and `latency_score` (bounded `34`/`33` `search_similar` recall latency), composes them
into a `MemoryFidelityReport` with a bounded `fidelity_score`, and additively feeds that score into the
R89 harness so the `memory_fidelity` axis becomes a real `available` reconstructed axis instead of the
stub — while every other R89 behavior is unchanged.

## 3. Functional Requirements

### 3.1 Reusable probe

1. A tests-only probe module (`tests/r90_memory_fidelity_probe/`) must expose
   `run_memory_fidelity_probe(handle_factory, config)` that builds a started runtime from
   `handle_factory()`, drives it for `config.ticks` ticks, and returns a structured
   `MemoryFidelityReport`. It must assert nothing itself; the metrics live on the report.
2. The probe must be read-only on owner state and offline: it exercises only the public `tick()` and
   the public `ExperienceStore` facade (`count`/`read_recent`/`search_similar`), imports no owner
   internals, and emits no `print`/`logging` (R21 discipline).
3. `handle_factory` must build a runtime over a fixed durable data directory each call, so the probe
   can call it a second time to measure cross-restart persistence against the same SQLite store.
4. A per-tick exception must be captured as an explicit `crash` (recording the tick), stopping the
   run; the report records how far it got.

### 3.2 Metrics (all bounded `[0,1]`)

1. `recall_hit_rate` (R10 end-to-end): over the ticks where the `directed_retrieval_into_thought_window`
   stage was activated (fired) AND the store was non-empty at tick start (recall was possible), the
   fraction whose published `ThoughtWindowBundle` contained at least one hit whose `source` is a
   store-sourced recall (prefix `experience_store`). When no tick had recall possible, the metric is
   `None` (honest absence), never a fabricated value.
2. `writeback_persistence_rate` (R15→R33 durability): the fraction of this-run appended records that
   survive a process restart — `clamp((store_count_after_restart - store_count_before_run) /
   records_appended_during_run, 0, 1)`. When nothing was appended, the metric is `0.0` (no writeback is
   a fidelity failure, not a free pass).
3. `latency_score` (R34/R33 recall latency): sample stored records carrying an embedding, time
   `search_similar(record.embedding, limit)` over a few trials, and score
   `clamp(latency_threshold_ms / median_latency_ms, 0, 1)` (`1.0` when the median is at or under the
   threshold). When no embedded record exists to probe, the metric is `None`.
4. `fidelity_score` must be the mean of the available metrics (each present metric in `[0,1]`); it must
   be `None` when no metric is available.

### 3.3 Report and harness integration

1. The `MemoryFidelityReport` must expose: `ticks_completed`, `crash`, the raw counts
   (`store_count_start`/`store_count_end`/`appended`/`survived_after_restart`,
   `recall_possible_ticks`/`recall_hit_ticks`, `self_recall_probes`/`self_recall_hits`,
   `latency_median_ms`), the three metrics, the derived `fidelity_score`, an explicit `usable`, a
   `violations()` list, and a human-readable `summary()`.
2. `usable` must be `True` only when there was no crash, all ticks completed, and at least the
   `writeback_persistence_rate` plus one of `recall_hit_rate`/`latency_score` are available, so an
   unusable probe never silently produces a misleading `fidelity_score`.
3. The R89 `evaluate_turing` must gain an additive optional `memory_fidelity_probe` parameter. When a
   usable report is supplied, the `memory_fidelity` axis becomes `available` (judge track
   `reconstructed`) with `score = fidelity_score` and provenance naming the probe metrics. When the
   parameter is absent or the report is unusable, the axis stays the `stubbed_pending_real_probe`
   placeholder, so all existing R89 behavior is byte-for-byte unchanged.

## 4. Non-Functional Requirements

1. Performance: the probe drives a bounded short run (default 60 ticks) plus one restart and a few
   `search_similar` calls; it must fit the default test suite.
2. Reliability: a runtime crash is captured as data (never propagated from inside the probe); a missing
   embedding / empty store degrades a metric to `None`, never an exception.
3. Observability and logging: no `print`/`logging` in the probe (only tests render); `21` stays the
   single runtime logging mechanism. The probe reads only public `RuntimeTickResult` and store facets.
4. Compatibility and migration: tests-only addition plus one additive optional parameter on the R89
   harness; no runtime/owner code changes; the full network-free suite (including all R89 tests) stays
   green.

## 5. Code Behavior Constraints

1. Forbidden: the probe importing owner internals, mutating owner state, or using `print`/`logging`.
2. Forbidden: a metric with no measurement opportunity being reported as a fabricated number; it must
   be `None` (honest absence).
3. Forbidden: the R89 harness changing any existing behavior when `memory_fidelity_probe` is absent or
   the report is unusable (the stub path must be preserved exactly).
4. The probe must be deterministic given the deterministic offline assembly (fixed fake gateway +
   offline hash embedding).

## 6. Impacted Modules

1. `helios_v2/tests/r90_memory_fidelity_probe/__init__.py`, `memory_fidelity_probe.py` (the probe),
   `test_r90_memory_fidelity_probe.py` (the metrics + the R89 integration).
2. `helios_v2/tests/r89_turing_harness/turing_harness.py` (additive optional `memory_fidelity_probe`
   parameter on `evaluate_turing`; `memory_fidelity` axis becomes available when a usable report is
   supplied).
3. Reuses `r83_long_runner` (deterministic gateway / production assembly pattern), the `33`
   `ExperienceStore`, and the `10` `directed_retrieval_into_thought_window` stage result.
4. Docs: `requirements/index.md` (row 90); `ROADMAP.zh-CN.md` (R90 delivered). `PROGRESS_FLOW.*` and
   `OWNER_GUIDE.*` unchanged (tests-only diagnostic + an additive harness parameter, no owner change).

## 7. Acceptance Criteria

1. `run_memory_fidelity_probe` drives a real durable production-shaped run, then a restart, and returns
   a `MemoryFidelityReport` with `writeback_persistence_rate` measured from real store growth + restart
   survival, `recall_hit_rate` measured from real `10` bundle store-sourced hits (or `None` if no
   recall was possible), `latency_score` from real `search_similar` latency (or `None`), and a
   `fidelity_score` that is the mean of the available metrics.
2. `writeback_persistence_rate` is high (records appended during the run survive the restart); the
   probe demonstrates the durable R15→R33 loop across a process boundary.
3. With a usable probe report passed to `evaluate_turing`, the `memory_fidelity` axis is `available`
   with `judge_track == reconstructed`, `score == fidelity_score`, and non-empty provenance; without
   it (or with an unusable report), the axis stays `stubbed_pending_real_probe` and every existing R89
   test still passes.
4. A crashing/empty probe yields `usable == False` with a recorded reason and no escaping exception.
5. No runtime/owner code changed; the full network-free suite is green; `index.md` has a row 90 and the
   ROADMAP shows R90 delivered.
