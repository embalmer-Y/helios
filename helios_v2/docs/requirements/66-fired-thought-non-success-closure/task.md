# Task 66 - Fired thought non-success closure

## 1. Title

Implement fired thought non-success closure

## 2. Task Breakdown

1. Author the requirement/design/task package for the fired-thought non-success closure and register it in the requirements index.
2. Update `ActionExternalizationRuntimeStage` so an activated non-completed `11` result closes as a `no_externalization` marker instead of invoking the `12` owner.
3. Update `IdentityGovernanceRuntimeStage` so the same path emits an explicit inactive marker instead of invoking the `14` owner.
4. Update the autonomy request bridge and runtime provenance checks to accept an explicit governance inactive marker on an activated thought path.
5. Update evaluation evidence construction so governance absence on that path is explicit and non-crashing.
6. Add a focused network-free regression covering malformed structured output -> `insufficient_generation` -> full-chain internal-only closure.
7. Run targeted validation, then rerun the real LLM smoke in the required `helios` virtual environment and analyze the resulting log/output.

## 3. Dependencies

1. Requirement `27` for the non-`completed` thought-result taxonomy.
2. Requirement `28` for the downstream internal-only closure path.
3. Requirement `54` for the explicit inactive marker pattern in runtime stages.

## 4. Files and Modules

1. `helios_v2/docs/requirements/66-fired-thought-non-success-closure/requirement.md`
2. `helios_v2/docs/requirements/66-fired-thought-non-success-closure/design.md`
3. `helios_v2/docs/requirements/66-fired-thought-non-success-closure/task.md`
4. `helios_v2/docs/requirements/index.md`
5. `helios_v2/src/helios_v2/runtime/stages.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`
7. `helios_v2/tests/test_runtime_composition.py`

## 5. Implementation Order

1. Finalize the requirement package and index entry.
2. Patch the runtime stage adapters.
3. Patch the downstream owner-neutral bridges/provenance checks.
4. Add the focused regression test.
5. Run targeted validation.
6. Run the real LLM smoke and inspect the resulting log/output.

## 6. Validation Plan

1. `pytest helios_v2/tests/test_runtime_composition.py -q -k malformed`
2. `pytest helios_v2/tests/test_runtime_composition.py -q -k internal_only`
3. `D:\Compiler\anaconda3\envs\helios\python.exe scripts/run_llm_smoke.py --ticks 2 --probe-live --save-json ...`

## 7. Completion Criteria

1. Requirement package and index entry exist and follow the authoring standard.
2. A non-completed fired thought result no longer crashes `12` or `14`.
3. The full chain closes through planner/writeback/autonomy/evaluation.
4. Focused regression tests pass.
5. Real LLM smoke completes past the previously failing path, with the resulting log/output analyzed.