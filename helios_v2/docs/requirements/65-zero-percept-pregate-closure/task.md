# Requirement 65 - Zero-Percept Pre-Gate Closure

## 1. Task Breakdown

### T1 - Stage Result 增加 activated 判别器
In `runtime/stages.py`, add `activated: bool = True` and `inactive_id: str | None = None` fields
plus `@classmethod inactive(cls, tick_id)` factories to `MemoryAffectReplayStageResult`,
`WorkspaceCompetitionStageResult`, and `ConsciousContentStageResult`. Each inactive factory
returns a valid default-constructed result with `activated=False` and a stable `inactive_id`.
The inactive `ConsciousState` uses `commit_status="no_commit"`,
`no_commit_reason="context_not_reportable"`, and inert provenance IDs.

### T2 - Runtime Stage 增加零感知检测与 inactive 分支
In `runtime/stages.py`, add zero-percept short-circuit logic to three runtime stage adapters:

1. `MemoryAffectReplayRuntimeStage.run`: check `frame.stage_results["sensory_ingress"].batch.stimuli`;
   if empty, return `MemoryAffectReplayStageResult.inactive(frame.tick_id)` without calling the
   memory engine.
2. `WorkspaceCompetitionRuntimeStage.run`: check `memory_result.activated`; if `False`, return
   `WorkspaceCompetitionStageResult.inactive(frame.tick_id)` without calling the workspace engine.
3. `ConsciousContentRuntimeStage.run`: check `workspace_result.activated`; if `False`, return
   `ConsciousContentStageResult.inactive(frame.tick_id)` without calling the consciousness engine.

### T3 - Gate (09) 消费 pre-gate inactive 信号
In `ThoughtGatingRuntimeStage.run`, when `conscious_result.activated` is `False`: build a minimal
`ThoughtGateSignalSnapshot` with `global_activation_level=0.0` and empty `selected_stimuli`, then
pass it through the gate engine normally. The engine's `commit_status != "committed"` check
(L168) produces `no_fire` with reason `conscious_content_not_eligible` — the natural causal chain.

### T4 - R60 bridge 注释标注
In `composition/bridges.py`, annotate `FirstVersionMemoryBindingContextBridge`'s no-percept marker
path as a defensive fallback unreachable from the runtime path after R65 (docstring annotation only,
no code change).

### T5 - 测试
New file `tests/test_zero_percept_pregate_closure.py` with six tests:
1. Zero-percept tick → `06`/`07`/`08` all `activated=False`.
2. Zero-percept tick closes through gate → `no_fire`.
3. Default assembly unchanged (placeholder percept → all pre-gate stages activate).
4. Semantic assembly with real percept unchanged.
5. Source exhaustion → subsequent ticks go inactive.
6. Interoceptive-only tick still forms memory.

Verify existing `test_runtime_composition.py` tests remain green.

### T6 - 文档同步
Update `index.md` (row 65), both `OWNER_GUIDE` files (`06` memory zero-percept item delivered),
both `PROGRESS_FLOW` maps (sync line naming R65).

### T7 - Git 提交与推送
Branch `feat/R65-zero-percept-pregate-closure`; commit message
`R65: zero-percept pre-gate closure - 06/07/08 inactive on empty percept`.

## 2. Dependencies

1. T1 → T2 → T3 → T4 → T5 (sequential code path; each step builds on the previous).
2. T6 after T5 (document only after tests pass).
3. T7 after T6.
4. External requirement dependencies: R54 (post-gate inactive pattern), R60 (no-percept marker),
   R59 (empty external source), R02 (`StimulusBatch`).

## 3. Files and Modules

1. `src/helios_v2/runtime/stages.py` (T1, T2, T3)
2. `src/helios_v2/composition/bridges.py` (T4, annotation only)
3. `tests/test_zero_percept_pregate_closure.py` (T5, new file)
4. `tests/test_runtime_composition.py` (T5, verify green)
5. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md` (T6)

## 4. Implementation Order

T1 → T2 → T3 → T4 → T5 → T6 → T7. Stage results first (additive defaults, no callers), then
runtime adapters (activate the new path), then gate consumption, then tests, then docs, then git.
Run the full suite after T1 (field additions with defaults), after T3 (short-circuit paths),
and after T5 (focused tests).

## 5. Validation Plan

1. After T1: `pytest helios_v2/tests -q` green (default `activated=True` keeps all existing paths).
2. After T3: `pytest helios_v2/tests -q` green (short-circuit only on genuinely empty batches).
3. After T5 (focused tests): `pytest helios_v2/tests/test_zero_percept_pregate_closure.py -q`
   green (6 tests); `pytest helios_v2/tests -q` green; count ≥ prior baseline (746) + 6.
4. Guards: `pytest helios_v2/tests/test_composition_owner_boundary_guard.py
   helios_v2/tests/test_no_adhoc_logging_guard.py -q` green.

## 6. Completion Criteria

1. With an R59 empty `SequenceExternalSignalSource` and no interoceptive sampler, a tick completes:
   `06`/`07`/`08` return `activated=False`, `09` gate decides `no_fire`, and all 19 canonical
   stage results are produced without raising.
2. The default assembly (with `FirstVersionSensorySource` placeholder) behaves identically.
3. The semantic assembly with a real external stimulus behaves identically.
4. An interoceptive-only tick still forms memory, competes workspace, and commits consciousness.
5. Full network-free suite green; owner-boundary and ad-hoc-logging guards green.
6. `index.md` has row 65; both `OWNER_GUIDE` files record the zero-percept item as delivered;
   both `PROGRESS_FLOW` maps have sync lines naming R65.

## 7. Acceptance Test Commands

```
pytest helios_v2/tests/test_zero_percept_pregate_closure.py -v
pytest helios_v2/tests -q
pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q
```
