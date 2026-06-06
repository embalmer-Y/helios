# Requirement 54 - Gate no-fire tick closure (tasks)

## 1. Task Breakdown

### Task 1 - Inactive stage-result discriminators
In `helios_v2/src/helios_v2/runtime/stages.py`, add `activated: bool = True` + `inactive_id: str | None = None` to `DirectedRetrievalStageResult`, `EmbodiedPromptStageResult`, `OutwardExpressionStageResult`, `OutwardExpressionExternalizationStageResult`, `InternalThoughtStageResult`, `ActionExternalizationStageResult`, and `IdentityGovernanceStageResult`; make their artifact fields Optional with current defaults; add an `inactive(tick_id)` classmethod to each. Fired-path construction stays unchanged.

### Task 2 - No-fire guards in the pure fired-path stages
Add the no-fire guard to each pure fired-path stage `run`: `10` directed-retrieval and `16` embodied-prompt read the gate decision directly; `16` outward-expression, `16` outward-expression-externalization, `11` internal-thought, `12` action-externalization, and `14` identity-governance propagate via the upstream result's `activated` flag. On no-fire, return the inactive result without calling the owner's fired-path API. Fired-path body unchanged.

### Task 3 - Closure-tail no-fire branches
`13` planner-bridge: when the upstream action-externalization result is inactive, run the existing `evaluate_internal_only` path from a no-fire marker request -> `no_actionable_proposal`. `15` writeback bridge: guard the identity-writeback branch on governance `activated` (the `internal_only` continuity record is already produced for `no_actionable_proposal`). `18` autonomy and `17` evaluation stages/bridges: build no-fire requests from the gate result id + deterministic no-fire marker ids and no-action drive inputs; gate artifact-provenance validation on `activated`. Reuse the R28 internal-only owner outcomes; no owner contract change.

### Task 4 - Validation
Extend `test_runtime_stage_chain.py` (stage-level: no-fire -> inactive results + closure tail, no raise) and `test_runtime_composition.py` (end-to-end no-fire tick completes; `internal_only` writeback; autonomy/evaluation ran; continuity carries; fired path unchanged; R53 high-load tick now completes). Network-free; logging guard green.

### Task 5 - Documentation truth sync
Update `index.md` (R54 row), `ARCHITECTURE_BOUNDARIES.md` (migration-state item: no-fire tick closure), `BRAIN_ARCHITECTURE_COMPARISON.md` (`gap_behavioral_consequence_binding`: restraint/no-fire is now a first-class recorded outcome), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`09` + the closure-tail owners), both `PROGRESS_FLOW` maps (note no-fire closure; update last-synced + baseline count). Also update the R53 package's surfaced-constraint note to "closed by R54".

## 2. Dependencies

1. Task 1 is independent.
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Tasks 1-3.
5. Task 5 depends on Task 4 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/runtime/stages.py` (Tasks 1-3)
2. `helios_v2/src/helios_v2/composition/bridges.py` (Task 3)
3. `helios_v2/tests/test_runtime_stage_chain.py`, `helios_v2/tests/test_runtime_composition.py` (Task 4)
4. `helios_v2/docs/requirements/index.md` + four truth docs + two progress maps + R53 note (Task 5)

## 4. Implementation Order

1. Task 1 (inactive result shapes).
2. Task 2 (pure fired-path guards).
3. Task 3 (closure-tail branches).
4. Task 4 (validation): stage-level then end-to-end.
5. Task 5 (doc sync).

## 5. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_runtime_stage_chain.py -q` (inactive results propagate; no raise to the planner).
2. After Task 3: `pytest helios_v2/tests/test_runtime_composition.py -q` (no-fire tick completes end to end; closure tail records it; fired path unchanged).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; logging guard green.

## 6. Completion Criteria

1. A `no_fire` gate completes the tick; post-gate stages return inactive results (`activated=False`, no fabricated artifact); fired-path owners' fired-path APIs not invoked.
2. The closure tail records the no-fire tick (`no_actionable_proposal` planner result, `internal_only` writeback), autonomy and evaluation run, and continuation/continuity carry across the tick.
3. The R53 high-compute-load tick now completes end to end as a no-fire tick.
4. The fired path is byte-for-byte unchanged; existing tests pass unmodified.
5. Full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, both progress maps, and the R53 surfaced-constraint note updated in the same change set.
