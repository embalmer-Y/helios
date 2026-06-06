# Requirement 48 - Workspace-grounded thought-gate activation (tasks)

## 1. Task Breakdown

### Task 1 - Workspace-grounded activation in the semantic gate-signal bridge
Extend the semantic-assembly gate-signal bridge (`NeuromodulatorAwareThoughtGateSignalBridge` in `composition/bridges.py`) to additionally source `global_activation_level` from the same tick's `07` `WorkspaceCompetitionStageResult`: add a `_workspace_activation` helper (max retained `workspace_score_hint`, `0.0` when none, clamped/rounded), read the `07` result from the frame with the same hard-fail semantics R37 uses for the `04` result, and set `global_activation_level` to the real activation while preserving the R37 `neuromodulatory_arousal` sourcing. Add a `workspace_stage_name` field defaulting to the canonical stage name. Update the docstring. The `09` gate path and its weight are unchanged.

### Task 2 - Assembly wiring check
Confirm the semantic-assembly selection still wires this bridge and that the default assembly keeps `FirstVersionThoughtGateSignalBridge`. No stage-order change; pass `workspace_stage_name` explicitly only if the default does not match the canonical name.

### Task 3 - Validation
Extend the composition test module per the design validation strategy (real activation from `07`; differing strength → differing activation; default keeps `0.9`; R37 arousal preserved; `_workspace_activation` unit behavior). Adjust the stage-chain test only if it asserts gate-signal constants under a semantic wiring. Keep the suite network-free and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R48 row; `09` note), `ARCHITECTURE_BOUNDARIES.md` (record the `09` `global_activation_level` de-shim and the remaining constant inputs), `BRAIN_ARCHITECTURE_COMPARISON.md` (`09` now consumes a second real signal: workspace activation), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`09` state/next-step; update last-synced + baseline), and both `PROGRESS_FLOW` maps (relabel `09`; update last-synced line and baseline count).

## 2. Dependencies

1. Task 1 depends conceptually on R46 (real `workspace_score_hint`) and R37 (the gate-signal bridge seam).
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2, likely no change)
3. `helios_v2/tests/test_runtime_composition.py`, `test_runtime_stage_chain.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (activation projection in the bridge) - the de-shim, independently testable.
2. Task 2 (assembly check) - confirm wiring.
3. Task 3 (validation) - prove real activation, differing strength, default unchanged, arousal preserved.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_runtime_composition.py -q` (real `global_activation_level` from `07`; differing strength; default `0.9`; R37 arousal preserved).
2. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. Under the semantic assembly, `09`'s `global_activation_level` equals the max retained `07` `workspace_score_hint` (or `0.0` if none), within `[0,1]`, not the constant `0.9`, and appears in the gate result's `contributing_signals`.
2. Differing `07` workspace strength yields differing `global_activation_level` at `09`; the R37 arousal coupling is preserved.
3. A missing/wrong-typed `07` result is a hard fail; an empty retained set yields `0.0`.
4. No contract change; the `09` gate path and weight are unchanged; the projection is owner-neutral glue.
5. Workspace-grounded activation activates only on the semantic-memory opt-in; default and non-semantic assemblies keep `0.9`; existing tests pass unmodified.
6. The four other constant gate signals and the stimulus projection remain first-version constants.
7. Full suite green and network-free; logging guard green; `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set.
