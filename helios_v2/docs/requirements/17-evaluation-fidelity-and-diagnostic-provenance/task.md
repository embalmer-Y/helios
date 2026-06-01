# Requirement 17 - Evaluation fidelity and diagnostic provenance task plan

## 1. Task Breakdown

1. Completed: defined the evaluation API and ops contracts.
2. Completed: defined explicit read-only evidence bundle contracts.
3. Completed: implemented public contracts for evidence bundle, artifact, fidelity warning, API, and ops contracts.
4. Completed: implemented the owner skeleton for artifact assembly, gap reporting, outward-expression artifact-chain consumption, and long-range diagnostics.
5. Completed: implemented runtime provider/stage wiring so evaluation consumes explicit stage results instead of logs.
6. Completed: exported the public evaluation surface.
7. Completed: added focused evaluation tests.

## 2. Dependencies

1. `13-planner-executor-feedback-bridge`
2. `15-execution-writeback-and-autobiographical-consolidation`
3. `16-embodied-subjective-prompt-and-action-autonomy`

## 3. Files and Modules

1. `helios_v2/src/helios_v2/evaluation/contracts.py`
2. `helios_v2/src/helios_v2/evaluation/engine.py`
3. `helios_v2/src/helios_v2/evaluation/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_evaluation_contracts.py`
8. `helios_v2/tests/test_evaluation_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`

## 4. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`

## 5. Completion Criteria

1. A documented read-only evaluation API exists.
2. Diagnostic artifacts expose evidence-driven gap reporting.
3. Long-range fidelity diagnostics are explicitly represented.
4. The two-layer outward-expression artifact chain is consumed through formal evidence categories.

## 6. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `14 passed`
2. `pytest helios_v2/tests -q` -> `192 passed`

Delivered files:

1. `helios_v2/src/helios_v2/evaluation/contracts.py`
2. `helios_v2/src/helios_v2/evaluation/engine.py`
3. `helios_v2/src/helios_v2/evaluation/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_evaluation_contracts.py`
8. `helios_v2/tests/test_evaluation_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`
