# Requirement 46 - Workspace competition de-shim (tasks)

## 1. Task Breakdown

### Task 1 - Owner-owned real competition + bounded retention (`07`)
Add `SalienceWeightedWorkspaceCompetitionPath` and `BoundedAttentionRetentionPath` to `helios_v2.workspace`, implementing the existing `WorkspaceCompetitionPath` / `WorkingStateRetentionPath` protocols. Competition scores each candidate as a bounded function of the real `priority_hint` + the real `05` feeling salience (replacing constant `0.95`) while preserving every owner invariant (all replay candidates in the set, forced flag and provenance verbatim). Retention selects a bounded top-K subset (the attention bottleneck) with a deterministic tie-break and a never-empty guarantee for a non-empty set. Weights/bound are explicit constants under the config's existing learned-parameter categories. Export both from `workspace/__init__.py`. No cross-owner import.

### Task 2 - Opt-in assembly wiring
In `assemble_runtime`, under the existing `semantic_memory_enabled` opt-in, assemble `07` with the owner-owned competition + retention paths; keep `FirstVersion*` for default/recency-only/non-semantic. Import the two paths from `helios_v2.workspace`.

### Task 3 - Validation
Extend the workspace and composition test modules per the design validation strategy. Keep the suite network-free and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R46 row; reassess `07` maturity), `ARCHITECTURE_BOUNDARIES.md` (`07` owner real competition note), `BRAIN_ARCHITECTURE_COMPARISON.md` (`07` now a real attention bottleneck; narrow the `03-07` shim language), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`07` state/next-step; update last-synced + baseline), and both `PROGRESS_FLOW` maps (recolor/relabel `07`; update last-synced line and baseline count).

## 2. Dependencies

1. Task 1 is independent (owner-internal), but depends conceptually on R45 having made `priority_hint` real.
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green (maturity reflects shipped+validated code).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/workspace/engine.py`, `workspace/__init__.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_workspace_engine.py`, `test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (owner competition + retention) - the cognitive truth, independently testable.
2. Task 2 (opt-in wiring) - activates the path end to end.
3. Task 3 (validation) - prove real scoring, bounded bottleneck, never-empty, invariants preserved, default unchanged.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_workspace_engine.py -q` (real score from priority+feeling; top-K bounded retention; never empty; deterministic; invariants preserved).
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q` (semantic assembly: bounded score-ordered working state, non-constant scores; default unchanged).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. `07` scores candidates through an owner-owned competition path (bounded function of real `priority_hint` + real `05` feeling salience), not a constant; in `[0,1]`; deterministic.
2. `07` retains only a bounded top-K subset into the working state (the attention bottleneck), bound under the existing learned-parameter categories, deterministic tie-break, never empty for a non-empty set.
3. Higher-salience candidates are retained and lower-salience excluded once over the bound; the difference is attributable to the real score; no downstream contract change.
4. All existing `07` owner invariants still hold and fail fast; the candidate set still carries every (incl. forced) candidate to `08` while the working state is the bounded held subset.
5. Real competition activates only on the semantic-memory opt-in; default and non-semantic assemblies keep the constant `07` behavior; existing tests pass unmodified.
6. Full suite green and network-free; logging guard green.
7. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps are updated in the same change set.
