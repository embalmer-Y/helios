# Requirement 47 - Conscious ignition commitment (tasks)

## 1. Task Breakdown

### Task 1 - Owner-owned ignition focal-selection policy (`08`)
Add `IgnitionFocalSelectionPolicy` to `helios_v2.consciousness.engine`, implementing the existing private `_FocalSelectionPolicy` protocol. When one or more candidates are retained, ignite the single highest-`workspace_score_hint` candidate as focal (deterministic tie-break by `source_workspace_candidate_id`) and pass the ranked losers as supporting materials; preserve the `insufficient_commitment_signal` (zero retained) and `context_not_reportable` (empty focal summary) no-commit outcomes; never emit `semantic_conflict_unresolved` for mere multiplicity. Pre-trim supporting materials to `max_supporting_context_items` by descending score if the renderer does not already cap them. Export the policy from `consciousness/__init__.py`.

### Task 2 - Opt-in assembly wiring
In `assemble_runtime`, under the existing `semantic_memory_enabled` opt-in, construct `FirstVersionConsciousCommitmentPath(focal_selection_policy=IgnitionFocalSelectionPolicy())`; keep the default `FirstVersionConsciousCommitmentPath()` for default/recency-only/non-semantic. Import the policy from `helios_v2.consciousness`.

### Task 3 - Validation
Extend the consciousness and composition test modules per the design validation strategy. Keep the suite network-free and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R47 row; reassess `08` maturity/color note), `ARCHITECTURE_BOUNDARIES.md` (note the `08` commitment de-shim if boundary truth changes), `BRAIN_ARCHITECTURE_COMPARISON.md` (`08` now ignites a winner; narrow the relevant shim language), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`08` state/next-step; update last-synced + baseline), and both `PROGRESS_FLOW` maps (relabel `08`; update last-synced line and baseline count).

## 2. Dependencies

1. Task 1 is independent (owner-internal), but depends conceptually on R46 having made `workspace_score_hint` real.
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/consciousness/engine.py`, `consciousness/__init__.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_consciousness_engine.py`, `test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (ignition policy) - the cognitive truth, independently testable.
2. Task 2 (opt-in wiring) - activates the path end to end.
3. Task 3 (validation) - prove winner ignition, multiplicity commits, no-commit cases preserved, default unchanged.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_consciousness_engine.py -q` (ignition picks top score; multiplicity commits; supporting bounded/ordered; zero-retained + empty-summary still no-commit; deterministic; passes engine validation).
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q` (semantic assembly commits focal on >1-retained working state; default keeps count-based no-commit).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. `08` ignites the highest-`workspace_score_hint` retained candidate as focal (deterministic tie-break), commits on a >1-retained working state, and no longer emits `semantic_conflict_unresolved` for mere multiplicity.
2. Losing retained candidates become supporting context, ordered by descending score and bounded by `max_supporting_context_items`; focal never duplicated.
3. Zero-retained → `insufficient_commitment_signal`; empty focal summary → `context_not_reportable`; both preserved.
4. All existing `08` owner invariants hold and fail fast; no contract change; the decision flows through `ConsciousState`/`ReportableConsciousContent` unchanged.
5. Ignition activates only on the semantic-memory opt-in; default and non-semantic assemblies keep the count-based policy; existing tests pass unmodified.
6. Full suite green and network-free; logging guard green.
7. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps are updated in the same change set.
