# Requirement 16 - Embodied subjective prompt and action autonomy task plan

## 1. Task Breakdown

1. Completed: defined the embodied-prompt API and ops contracts.
2. Completed: defined explicit request contracts for `thought` and `outward_expression` prompt assembly.
3. Completed: encoded the confirmed boundary that `16` owns prompt-contract assembly, not action execution, planner authority, channel authority, or governance truth.
4. Completed: implemented public contracts for prompt request, prompt layers, action boundary, contract publication, API, and ops contracts.
5. Completed: implemented the owner skeleton for bounded layer assembly, anti-theatrical constraints, fail-fast validation, and a minimal outward-expression consumer view.
6. Completed: implemented an independent outward-expression owner package with config, request, bounded draft, engine, and publication ops.
7. Completed: implemented runtime wiring between `16` and the outward-expression owner, consuming the prompt-owned request into a bounded draft stage.
8. Completed: implemented a downstream outward-expression externalization owner package with config, request, bounded externalization draft, engine, and publication ops.
9. Completed: implemented runtime wiring between the outward-expression owner and the outward-expression externalization owner, consuming the first draft into an execution-adjacent second draft stage.
10. Completed: preserved `11` as the only thought consumer of the thought-side contract while keeping both outward-expression draft owners independent from final execution authority.
11. Completed: exported the public prompt-contract, outward-expression, and outward-expression externalization owner surfaces.
12. Completed: added focused outward-expression externalization contract, engine, and runtime-chain tests.

## 2. Dependencies

1. `11-internal-thought-loop-owner`
2. `12-action-proposal-externalization-contract`
3. `13-planner-executor-feedback-bridge`
4. `15-execution-writeback-and-autobiographical-consolidation`

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/prompt_contract/contracts.py`
2. `helios_v2/src/helios_v2/prompt_contract/engine.py`
3. `helios_v2/src/helios_v2/prompt_contract/__init__.py`
4. `helios_v2/src/helios_v2/outward_expression/contracts.py`
5. `helios_v2/src/helios_v2/outward_expression/engine.py`
6. `helios_v2/src/helios_v2/outward_expression/__init__.py`
7. `helios_v2/src/helios_v2/outward_expression_externalization/contracts.py`
8. `helios_v2/src/helios_v2/outward_expression_externalization/engine.py`
9. `helios_v2/src/helios_v2/outward_expression_externalization/__init__.py`
10. `helios_v2/tests/test_prompt_contract_v2.py`
11. `helios_v2/tests/test_outward_expression_contracts.py`
12. `helios_v2/tests/test_outward_expression_engine.py`
13. `helios_v2/tests/test_outward_expression_externalization_contracts.py`
14. `helios_v2/tests/test_outward_expression_externalization_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/__init__.py`
3. `helios_v2/src/helios_v2/__init__.py`
4. `helios_v2/tests/test_runtime_stage_chain.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/16-embodied-subjective-prompt-and-action-autonomy/requirement.md`
2. `helios_v2/docs/requirements/16-embodied-subjective-prompt-and-action-autonomy/design.md`
3. `helios_v2/docs/requirements/16-embodied-subjective-prompt-and-action-autonomy/task.md`

## 4. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused outward-expression externalization owner and runtime validation: `pytest helios_v2/tests/test_outward_expression_externalization_contracts.py helios_v2/tests/test_outward_expression_externalization_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`
4. Full regression validation: `pytest helios_v2/tests -q`

## 5. Completion Criteria

1. A documented API for embodied prompt-contract assembly exists.
2. Prompt contracts remain grounded in v2 owner outputs and capability truth.
3. Cross-path contract-family consistency is defined and testable.
4. Outward-expression request handoff is defined and testable.
5. Independent outward-expression draft ownership is defined and testable.
6. Independent outward-expression externalization draft ownership is defined and testable.
7. Focused runtime-chain tests pass.
8. Full `helios_v2/tests` regression passes.

## 6. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_outward_expression_externalization_contracts.py helios_v2/tests/test_outward_expression_externalization_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `12 passed`
2. `pytest helios_v2/tests -q` -> `185 passed`

Delivered files:

1. `helios_v2/src/helios_v2/prompt_contract/contracts.py`
2. `helios_v2/src/helios_v2/prompt_contract/engine.py`
3. `helios_v2/src/helios_v2/prompt_contract/__init__.py`
4. `helios_v2/src/helios_v2/outward_expression/contracts.py`
5. `helios_v2/src/helios_v2/outward_expression/engine.py`
6. `helios_v2/src/helios_v2/outward_expression/__init__.py`
7. `helios_v2/src/helios_v2/outward_expression_externalization/contracts.py`
8. `helios_v2/src/helios_v2/outward_expression_externalization/engine.py`
9. `helios_v2/src/helios_v2/outward_expression_externalization/__init__.py`
10. `helios_v2/src/helios_v2/runtime/stages.py`
11. `helios_v2/src/helios_v2/runtime/__init__.py`
12. `helios_v2/src/helios_v2/__init__.py`
13. `helios_v2/tests/test_prompt_contract_v2.py`
14. `helios_v2/tests/test_outward_expression_contracts.py`
15. `helios_v2/tests/test_outward_expression_engine.py`
16. `helios_v2/tests/test_outward_expression_externalization_contracts.py`
17. `helios_v2/tests/test_outward_expression_externalization_engine.py`
18. `helios_v2/tests/test_runtime_stage_chain.py`
