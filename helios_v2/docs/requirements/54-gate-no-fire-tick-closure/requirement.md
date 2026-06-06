# Requirement 54 - Gate no-fire tick closure

## 1. Background and Problem

The `09` thought gate already produces a real `no_fire` decision with a taxonomy of reasons (`conscious_content_not_eligible`, `resource_pressure_too_high`, `continuation_absent_and_no_stimulus`, `gate_score_too_low`). But the assembled `01-18` chain cannot complete a tick whose gate does not fire: the post-gate stages — `10` directed-retrieval, the `16` prompt / outward-expression / outward-expression-externalization stages, `11` internal-thought, `12` action-externalization, and `14` identity-governance — all hard-require a fired `ThoughtGateResult` (a deliberate owner invariant: "Internal thought requires a fired ThoughtGateResult") and raise `DirectedRetrievalError` / `RuntimeStageExecutionError` on a non-fired gate.

This was acceptable while every gate input was a constant tuned to always fire. It became a real blocker with R53: grounding the gate's `workload_pressure` in real compute load means a high-load tick now correctly decides `no_fire` (`resource_pressure_too_high`) — and the tick then crashes instead of completing. The same will happen as R55/R56 ground the remaining gate inputs (temporal, DMN, drive-urgency) in real signals: any of them can legitimately produce a no-fire, and every such tick currently aborts. So the gate's own real decision cannot yet be exercised end to end, and the runtime cannot represent the most basic brain-like outcome: a moment where the system takes in its situation and decides *not* to start a new line of thought.

R28 already established the precedent for the mirror case: a *fired* tick that produces no externalizable proposal closes through the planner-bridge (`no_actionable_proposal`), writeback (`internal_only` continuity), autonomy, and evaluation as an explicit internal-only outcome. R54 is the *upstream* analog: a tick that does not fire at all must close through the same continuity/autonomy/evaluation tail as an explicit no-fire outcome, without fabricating retrieval, thought, or an action, and without weakening any fired-path owner invariant.

## 2. Goal

Make a `no_fire` gate decision close the tick cleanly as an explicit, owner-recorded no-fire outcome: the post-gate fired-path stages (`10`, the `16` family, `11`, `12`, `14`) observe the gate owner's published `no_fire` decision and emit an explicit not-activated stage result instead of invoking their fired-path owner APIs (so those owners' "requires a fired gate" invariants are never violated), and the existing internal-only continuity tail (`13` planner-bridge, `15` writeback, `18` autonomy, `17` evaluation) records the tick as a no-fire continuity outcome that preserves continuation pressure and long-horizon continuity across the tick, so a no-fire tick advances internal state and is reconstructable by evaluation rather than aborting the runtime.

## 3. Functional Requirements

### 3.1 No-fire is a first-class tick outcome
1. When the `09` gate publishes `decision == "no_fire"`, the tick must complete through every registered stage and produce a `RuntimeTickResult` (the kernel runs all stages; no stage may raise solely because the gate did not fire).
2. The fired-path owners (`10` directed-retrieval, `11` internal-thought, `12` action-externalization, `14` identity-governance, and the `16` prompt/outward-expression family) must not be invoked on their fired-path APIs on a no-fire tick. Their "requires a fired/completed upstream" invariants must remain unchanged and must continue to fail fast if ever called with a non-fired input.
3. Each post-gate stage must emit an explicit not-activated stage result on a no-fire tick, carrying a deterministic id and an explicit `activated == False` discriminator, so downstream stages and evaluation can distinguish a genuinely inactive stage from an active one. The fired-path (gate fired) behavior must be unchanged (`activated == True`).

### 3.2 No-fire continuity closure
1. On a no-fire tick, the continuity tail must record the tick as an explicit no-fire continuity outcome (reusing or extending the existing `internal_only` writeback path), so the tick is preserved as experience rather than dropped.
2. Continuation pressure and the `18`/`24` long-horizon continuity state must be carried across a no-fire tick exactly as the owners define (the `09` continuation-pressure carry and the `18` autonomy stage's cross-tick state must still update), so a no-fire tick does not reset subjective continuity.
3. The `18` autonomy owner must still run on a no-fire tick (autonomy integrates continuation/continuity regardless of whether thought fired) and must receive a well-formed request that reflects the no-fire outcome (no action proposal, no outward readiness), without the runtime fabricating thought content.
4. The `17` evaluation owner must still run on a no-fire tick (read-only) and its evidence bundle must represent the no-fire outcome explicitly (no thought/action/governance activation this tick), so the no-fire tick is diagnostically reconstructable.

### 3.3 Provenance integrity on no-fire
1. The not-activated stage results and the no-fire continuity/autonomy/evaluation requests must preserve a consistent provenance chain (the ids the downstream provenance checks validate must be present and consistent), so no provenance validation raises on a no-fire tick.
2. No not-activated result may carry a fabricated cognitive artifact (no invented thought content, retrieval bundle hits, action proposal, or governance revision). Absence must be represented as explicit absence (`activated == False`, `None` artifacts), never as a default-valued artifact that reads as real.

### 3.4 Rollout and fail-fast
1. The no-fire closure is part of the default assembled runtime (it is not opt-in): once present, any assembly that can produce a no-fire gate completes the tick. The fired-path behavior on a fired gate is byte-for-byte unchanged.
2. There is no degraded mode: a no-fire tick is an explicit, fully-recorded outcome, not a silent skip. A malformed no-fire closure (an inconsistent provenance chain, a missing required continuity record) must still fail fast through the existing stage/owner invariants.

## 4. Non-Functional Requirements

1. Performance: a no-fire tick does strictly less work than a fired tick (it skips the fired-path owner calls); no new per-tick cost on the fired path.
2. Reliability and fault tolerance: a no-fire tick is deterministic given its inputs and completes without raising; the fired path is unchanged.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. The no-fire outcome travels through the existing stage-result, writeback, autonomy, and evaluation contracts.
4. Compatibility and migration: the `activated` discriminator and any Optional artifact fields are additive (default to the current fired-path shape), so existing fired-path tests pass unmodified; the default and channel-bound assemblies complete a fired tick exactly as today.

## 5. Code Behavior Constraints

1. Whether a stage runs its owner's fired-path API is a runtime-orchestration fact owned by the runtime stage adapter (keyed on the gate owner's published decision), not a cognitive decision. The stage adapter must not re-derive the gate decision; it reads the published `ThoughtGateResult.decision`.
2. The fired-path owners must not gain a "run on no-fire" path. Their invariants stay as-is; the runtime simply does not call them on a no-fire tick.
3. No fabricated cognition: a not-activated stage result carries explicit absence, never a synthesized artifact.
4. The no-fire continuity outcome must reuse the existing continuity/writeback/autonomy/evaluation owner contracts (extending their taxonomies additively if needed), not a parallel ad-hoc path.
5. No `logging`/`print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/runtime/stages.py` (no-fire branch + explicit inactive stage results for `10`, `16` family, `11`, `12`, `14`; `activated` discriminator + Optional artifact fields on the affected stage results)
2. `helios_v2/src/helios_v2/composition/bridges.py` (no-fire-aware autonomy and evaluation request/evidence bridges; the writeback request bridge's no-fire continuity record)
3. Possibly `helios_v2/src/helios_v2/planner_bridge/`, `helios_v2/src/helios_v2/experience_writeback/`, `helios_v2/src/helios_v2/autonomy/`, `helios_v2/src/helios_v2/evaluation/` (additive no-fire taxonomy values only if the existing internal-only path does not already cover the no-fire outcome)
4. `helios_v2/tests/test_runtime_composition.py` (a no-fire tick completes; continuity/autonomy/evaluation record it; fired path unchanged; provenance intact)
5. `helios_v2/tests/test_runtime_stage_chain.py` (stage-level no-fire inactive results)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (the no-fire tick closes the `gap_behavioral_consequence_binding` "restraint is also an outcome" point)
9. `helios_v2/docs/OWNER_GUIDE.md`, `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
10. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. A tick whose `09` gate decides `no_fire` (for any reason in the taxonomy) completes and returns a `RuntimeTickResult`; no stage raises because of the no-fire decision.
2. On a no-fire tick, the `10`/`16`-family/`11`/`12`/`14` stage results are present with `activated == False` and no fabricated cognitive artifact; the fired-path owners' fired-path APIs were not invoked.
3. On a no-fire tick, the writeback stage records an explicit no-fire (internal-only-style) continuity outcome, the `18` autonomy stage runs and updates its cross-tick continuity state, and the `17` evaluation stage runs read-only and represents the no-fire outcome in its evidence.
4. Continuation pressure and `18`/`24` continuity carry across a no-fire tick (a no-fire tick does not reset them); a subsequent fired tick sees the carried state.
5. A high-compute-load tick (R53: cpu/memory pressure driving `resource_pressure_too_high`) now completes end to end as a no-fire tick (the R53 constraint is lifted), demonstrating real load can restrain firing without aborting the runtime.
6. The fired-gate path is byte-for-byte unchanged (all affected stage results default to `activated == True` with their existing artifacts); existing fired-path tests pass unmodified.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R54 closes the no-fire tick. The following remain future:

1. Richer no-fire diagnostics in `17` (distinguishing the no-fire reasons and their downstream continuity effects), once non-deterministic cognition makes them vary.
2. A no-fire-specific autonomy disposition (e.g. a no-fire tick that raises continuation pressure toward firing next tick) beyond the first-version carry.
3. Grounding the remaining gate inputs (`temporal_signal`, `dmn_available`, `drive_urgency_signal`) so more no-fire causes become real (R55/R56), now safely closeable.
