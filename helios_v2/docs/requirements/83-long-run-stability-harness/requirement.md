# Requirement 83 - Long-Run Stability and Owner-Boundedness Harness

## 1. Background and Problem

R82 made durable persistence (SQLite store + R42 checkpoint) the standard production default, closing
the G2 gate. The two remaining P0-P3 "foundation-stability" gates in `ARCHITECTURE_PHILOSOPHY.zh-CN.md`
§13.3.1 are still unverified: **G0** (long-time stable operation: a single runtime runs for a long
horizon with no crash, no uncaught exception, no memory/handle leak, no fail-fast misfire, every tick
closing through the chain or an explicit no-fire/internal-only path) and **G1** (every non-fixed owner
produces real, bounded, reproducible, non-divergent, non-NaN output that varies deterministically with
its input).

Today there is no repeatable harness that drives an assembled runtime for many ticks and produces a
falsifiable stability/boundedness verdict. R76/R77 ship short prerequisite checks (20 ticks); the
performance benchmark (R71) measures throughput, not long-horizon boundedness. Without a harness, G0/G1
can only be asserted by inspection, not reconstructed from evidence.

## 2. Goal

Add a repeatable, network-free long-run harness that drives the R82 production-shaped assembly for a
locked number of ticks, collects per-owner boundedness (no NaN, no non-finite, no out-of-range, no
divergence) over the whole run plus crash / uncaught-exception facts and in-process memory growth, and
emits a structured long-run report with a falsifiable G0/G1 verdict - run as a fast CI-tier smoke by
default and a manual production-scale (>= 100k tick) tier opt-in, with a separate opt-in real-LLM tier.

## 3. Functional Requirements

### 3.1 Reusable harness

1. A tests-only harness module (`tests/r83_long_runner/`) must expose `run_long_run(handle, config)`
   that drives an already-started `RuntimeHandle` for `config.ticks` ticks and returns a structured
   `LongRunReport`. It must assert nothing itself; the verdict lives on the report.
2. The harness must be read-only (exercise only the public `tick()`; never mutate owner state) and must
   emit no `print`/`logging` (R21 discipline); a consuming test may render the report.
3. Per tick the harness must capture each tracked owner field and update running boundedness statistics
   (observations, min, max, NaN count, non-finite count, out-of-range count). Tracked fields must cover
   `04` neuromodulator levels (9 channels, legal `[0,1]`), `05` interoceptive feeling (7 dimensions,
   legal `[0,1]`), the `09` gate score and continuation level (legal `[0,1]`), and the `18`
   `outward_drive` (checked against a divergence ceiling, not a unit interval, since it crosses an
   action threshold > 1).
4. A per-tick exception must be captured as an explicit crash (recording the tick index and exception),
   stopping the run; the report must record how far it got. A run that completes all ticks with no crash
   satisfies the G0 completion criterion.
5. The report must expose: `crash`, `ticks_completed`/`ticks_requested`, per-field stats, in-process
   memory start/peak/end (via `tracemalloc`), durable-store count start/end, a sampled cross-tick
   evolution curve, an explicit `verdict_ok`, and a human-readable `summary()` plus a `violations()` list.

### 3.2 Tiers

1. **CI tier**: a repeatable, deterministic, network-free run on the R82 production-shaped assembly
   (SQLite store + R42 checkpoint + semantic chain) driven by a deterministic fake LLM gateway, at a
   locked tick count (`_CI_TICKS`, default 150, override via `HELIOS_R83_CI_TICKS`). It must assert no
   crash, full completion, owner boundedness, bounded memory, and genuine durable accumulation.
2. **Opt-in production-scale tier**: the hard G0 gate at `_LONG_TICKS` (default 100000); skipped unless
   `HELIOS_R83_LONG_RUN` is set; never in CI.
3. **Opt-in real-LLM tier**: a short run against a real LLM gateway from environment credentials;
   skipped unless `HELIOS_R83_REAL_LLM` is set; never in CI.

### 3.3 Determinism and findings

1. Two fresh CI-tier runs (separate data directories) must produce identical owner-field min/max
   (reproducibility).
2. The harness must surface, as a documented finding, that per-tick cost grows roughly linearly with
   stored-memory size (the `03`/`06`/`10` cosine searches are O(n) over the store; R34 deferred an ANN
   index), so an unbounded run is ~O(n^2); this motivates a future bounded-window / ANN requirement and
   is why the CI tier is bounded while the 100k gate is manual.

## 4. Non-Functional Requirements

1. Performance: the CI tier must stay bounded (default 150 ticks) so the default suite stays reasonable;
   the production-scale tier is opt-in.
2. Reliability: the harness must never itself crash the suite on a diagnostic (e.g. a store-count read)
   and must capture a runtime crash as data, not propagate it as a test error inside the harness.
3. Observability and logging: no `print`/`logging` in the harness (only tests render); `21` stays the
   single runtime logging mechanism. The harness consumes only public `RuntimeTickResult` fields.
4. Compatibility and migration: no runtime/owner code changes; this is a tests-only addition. The full
   network-free suite stays green.

## 5. Code Behavior Constraints

1. Forbidden: the harness mutating owner state, importing owner internals, or using `print`/`logging`.
2. Forbidden: the CI tier touching the network (it injects a deterministic fake LLM gateway and uses the
   offline hash embedding).
3. Forbidden: hiding a runtime crash or an out-of-range owner value; both must appear in the report and
   fail the consuming test's verdict.
4. The harness reads owner facts defensively through public stage-result fields and tolerates an
   inactive (no-fire) stage without inventing values.

## 6. Impacted Modules

1. `helios_v2/tests/r83_long_runner/__init__.py`, `long_runner.py` (the harness),
   `test_r83_long_run.py` (the three tiers).
2. Docs: `requirements/index.md` (row 83); `OWNER_GUIDE.*` only as a note if needed (no owner maturity
   change); `PROGRESS_FLOW.*` unchanged (no color/chain/boundary change).

## 7. Acceptance Criteria

1. `run_long_run` drives a started handle for N ticks and returns a `LongRunReport` whose `verdict_ok`
   is `True` only when there was no crash, all ticks completed, every tracked field stayed bounded /
   finite / non-NaN, and memory stayed under the ceiling.
2. The CI-tier test runs the R82 production-shaped assembly for the locked tick count network-free,
   asserting no crash, full completion, boundedness of every tracked `04`/`05`/`09`/`18` field, bounded
   memory, and durable store growth; the report summary is rendered to the CI log.
3. A reproducibility test shows two fresh runs produce identical owner-field min/max.
4. The production-scale (>= 100k) and real-LLM tiers exist and are skipped unless their env flags are
   set (never in CI).
5. No runtime/owner code changed; the full network-free suite is green; `index.md` has a row 83 noting
   the harness, the locked CI/long tick counts, and the O(n) novelty-cost finding.
