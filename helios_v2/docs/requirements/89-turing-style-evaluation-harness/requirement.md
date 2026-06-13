# Requirement 89 - Long-Run Turing-Style Evaluation Harness

## 1. Background and Problem

R83 produced a repeatable long-run trace substrate and R88 added a read-only behavioral-drift
readout over it (the P5 startup gate). `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13.4 locks the eventual P5
acceptance as a long-run Turing-style experiment scored on six axes (`linguistic_naturalness`,
`bio_responsiveness`, `memory_fidelity`, `agency_locking`, `cross_tick_continuity`,
`stimulus_response_coherence`) under a dual similarity criterion (behavior similarity AND internal
causal-chain similarity), a locked rubric, evidence-anchored scoring (no runtime provenance → score
0), a human + LLM-judge dual track, conservative risk-averse aggregation, and an ≥ 80% pass line.

Today there is no harness that assembles those six axes into a single falsifiable verdict, no place
where the deterministically-reconstructable internal axes are scored from real runtime provenance,
and no enforcement of the anti-theatrical aggregation rules (behavior-only must not pass; an
unverifiable or stubbed axis must not contribute an optimistic passing score). Without the harness,
the §13.4 acceptance cannot be approached incrementally, and the internal axes that ARE
reconstructable today (from the R83 report + the R88 drift report) are not yet computed or anchored.

This requirement builds the harness scaffold and the reconstructable internal axes. It deliberately
does NOT ship the full §13.4 acceptance run (≥ 300 real stimuli, real human/LLM judges, real
anthropomorphism scoring), because the behavior-dimension axes require P4 real afferents + real model
output + calibrated judges, and `memory_fidelity` requires the R90 real probe. Per the project's
honesty discipline, those axes must be explicitly UNAVAILABLE/STUBBED in this slice rather than
faked, and the harness must therefore refuse to emit a passing Turing verdict on the offline baseline.

## 2. Goal

Add a read-only, deterministic, network-free Turing-style evaluation harness that consumes an R83
`LongRunReport` plus an R88 `DriftReport`, scores the six §13.4 rubric axes (reconstructing the
internal axes from real runtime provenance, accepting injected human/LLM-judge scores for the
behavior axes, and stubbing `memory_fidelity` pending R90), applies the locked anti-theatrical
conservative aggregation (evidence-anchored, both-dimension-required, any-axis-collapse fails,
≥ 80% pass line), and emits a falsifiable `TuringVerdict` that is honestly `incomplete` and
not-passing whenever any axis is unavailable or stubbed.

## 3. Functional Requirements

### 3.1 Reusable harness

1. A tests-only harness module (`tests/r89_turing_harness/`) must expose `evaluate_turing(long_run_report,
   drift_report, config, injected_scores=None)` that returns a structured `TuringVerdict`. It must
   assert nothing itself; the verdict lives on the report.
2. The harness must be read-only and offline: it must touch no runtime, mutate no state, perform no
   network or model call, and emit no `print`/`logging` (R21 discipline). A consuming test may render
   the verdict.
3. The harness must consume only the public R83 `LongRunReport` (field stats, completion, crash) and
   the R88 `DriftReport` (per-dimension availability/drift/divergence); it must not re-run the runtime
   or import owner internals.

### 3.2 Locked rubric axes and dimensions

1. The six axes must be exactly: `linguistic_naturalness`, `bio_responsiveness`, `memory_fidelity`,
   `agency_locking`, `cross_tick_continuity`, `stimulus_response_coherence`.
2. Each axis must be assigned to one similarity dimension: the BEHAVIOR dimension
   (`linguistic_naturalness`, `stimulus_response_coherence`) or the INTERNAL causal-chain dimension
   (`bio_responsiveness`, `memory_fidelity`, `agency_locking`, `cross_tick_continuity`).
3. Each axis must carry an explicit availability: `available` (scored from real provenance or an
   injected judge score), `stubbed_pending_real_probe` (a placeholder that cannot contribute a passing
   score), or `unavailable_needs_real_afferent` (cannot be scored offline).
4. Every axis score must carry an explicit `provenance` string naming the runtime fact it is anchored
   to. An `available` axis with empty provenance must score `0.0` (evidence anchoring: a score that
   cannot point to provenance is not a real score).

### 3.3 Reconstructed internal axes

1. `bio_responsiveness` must be reconstructed from the affect owners (`04.*`, `05.*`): a health
   component (the affect dimensions present in the drift report, non-`dim_unavailable`, and
   non-divergent) blended with a movement component (the affect dimensions whose R83 field-stat
   observed range exceeds a small epsilon, i.e. the affect actually evolved over the run). Anchored to
   the R88 drift report + the R83 field stats.
2. `cross_tick_continuity` must be reconstructed from run completion (no crash, all ticks) plus the
   presence and boundedness of the `09.continuation_level` dimension plus cross-tick affect evolution.
   Anchored to the R83 report + the drift report.
3. `agency_locking` must be reconstructed as a bounded proxy: the fraction of expected owner
   dimensions present, classifiable, and non-divergent (real bounded owner state produced every tick,
   versus prompt-only theater). It must be documented as a partial proxy; full agency-locking
   (owner-decision provenance via `21`/`17`) is deferred.
4. `memory_fidelity` must be a stub (`stubbed_pending_real_probe`, first-version value configurable)
   that the R90 probe replaces; it must not contribute a passing score and must force the verdict to
   `incomplete`.

### 3.4 Injected judge tracks and conservative aggregation

1. `injected_scores` must let a caller supply a per-axis score, provenance, and judge track
   (`human` / `llm_judge`) for any axis, modeling the §13.4 dual judge track; an injected score
   overrides the reconstructed/unavailable default for that axis. This is how the behavior axes
   (`linguistic_naturalness`, `stimulus_response_coherence`) become available.
2. Per dimension, the dimension score must be a conservative lower-quantile (risk-averse, nearest-rank
   at `lower_quantile`, default `0.25`) over only the `available` axes of that dimension; a dimension
   with no available axis has no score.
3. The overall aggregate must be `min(behavior_dimension_score, internal_dimension_score)` and must
   exist only when both dimensions have a score (behavior-only or internal-only must not produce an
   aggregate).
4. The verdict `passes` must be `True` only when: completeness is `complete` (every axis `available`,
   none stubbed/unavailable), both dimensions have a score, the aggregate `>= pass_threshold`
   (default `0.80`), and no `available` axis scored below `axis_collapse_threshold` (default `0.50`).
5. On the offline baseline (no injected behavior-axis scores), the behavior dimension has no available
   axis, so the verdict must be `incomplete` and `passes == False` — the harness must never emit an
   optimistic pass from the internal axes alone.

## 4. Non-Functional Requirements

1. Performance: the harness is a single pass over the two reports; it must run inside the default test
   suite alongside a short R83 long run.
2. Reliability: a missing/empty report input must produce an explicit non-passing verdict with a
   recorded reason, never an exception escaping the harness on routine input.
3. Observability and logging: no `print`/`logging` in the harness (only tests render); `21` stays the
   single runtime logging mechanism.
4. Compatibility and migration: tests-only addition; no runtime/owner code changes; the full
   network-free suite stays green.

## 5. Code Behavior Constraints

1. Forbidden: the harness importing owner internals, touching the runtime, or using `print`/`logging`.
2. Forbidden: a stubbed or unavailable axis contributing a passing score, or the verdict passing on a
   single dimension (behavior-only or internal-only). Both the dual-dimension rule and evidence
   anchoring are mandatory anti-theatrical guards.
3. Forbidden: an `available` axis without provenance keeping a non-zero score.
4. The harness must be deterministic: the same reports, config, and injected scores always yield the
   same verdict.

## 6. Impacted Modules

1. `helios_v2/tests/r89_turing_harness/__init__.py`, `turing_harness.py` (the harness),
   `test_r89_turing_harness.py` (synthetic fixtures + a real short R83 run integration).
2. Reuses `r83_long_runner` (`LongRunReport`, `run_long_run`, `TRACKED_FIELD_BOUNDS`) and
   `r88_drift_evaluator` (`DriftReport`, `evaluate_drift`).
3. Docs: `requirements/index.md` (row 89); `ROADMAP.zh-CN.md` (R89 delivered). `PROGRESS_FLOW.*` and
   `OWNER_GUIDE.*` unchanged (tests-only diagnostic harness, mirroring R83/R88).

## 7. Acceptance Criteria

1. `evaluate_turing` reconstructs the internal axes (`bio_responsiveness`, `cross_tick_continuity`,
   `agency_locking`) from a real short R83 run's `LongRunReport` + R88 `DriftReport`, each `available`
   with non-empty provenance; `memory_fidelity` is `stubbed_pending_real_probe`; the behavior axes are
   `unavailable_needs_real_afferent`; the verdict is `incomplete` and `passes == False` (anti-theatrical
   baseline: internal axes alone cannot pass).
2. With all six axes injected at `>= 0.9` with provenance, the verdict is `complete`, both dimensions
   have a score, the aggregate `>= 0.80`, and `passes == True`.
3. Falsifiability: an injected axis below the collapse threshold fails `passes`; an injected behavior
   axis with empty provenance scores `0.0` and fails; supplying only internal-dimension scores leaves
   the behavior dimension unscored and the verdict not-passing.
4. A missing/empty report yields a non-passing verdict with a recorded reason and no escaping
   exception.
5. No runtime/owner code changed; the full network-free suite is green; `index.md` has a row 89 and the
   ROADMAP shows R89 delivered with the explicit non-goal that the full §13.4 ≥ 300-stimulus acceptance
   run (real afferents, real judges, R90 memory probe) is deferred.
