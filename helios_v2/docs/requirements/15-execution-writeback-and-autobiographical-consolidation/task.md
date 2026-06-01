# Requirement 15 - Execution writeback and autobiographical consolidation task plan

## 1. Task Breakdown

1. Completed: defined the experience-writeback API and publication-op contracts.
2. Completed: defined the explicit writeback-request contract that carries normalized planner-bridge and identity-governance outcomes into `15` without owner reach-through.
3. Completed: encoded the confirmed boundary that `15` owns continuity publication and consolidation-candidate assembly, not raw backend writes, retrieval planning, or planner/governance authority.
4. Completed: implemented public contracts for writeback request, continuity packet, consolidation candidate, result taxonomy, API, and publication ops.
5. Completed: implemented the owner skeleton for input validation, deterministic continuity classification, and bounded candidate assembly.
6. Completed: implemented the runtime-owned stage adapter and provider contract.
7. Completed: exported the public writeback surface through package and runtime export layers.
8. Completed: added focused contract, engine, and runtime-stage tests.

## 2. Dependencies

1. `13-planner-executor-feedback-bridge`
2. `14-identity-governance-self-revision-integration`
3. `01-runtime-kernel`

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/experience_writeback/contracts.py`
2. `helios_v2/src/helios_v2/experience_writeback/engine.py`
3. `helios_v2/src/helios_v2/experience_writeback/__init__.py`
4. `helios_v2/tests/test_experience_writeback_contracts.py`
5. `helios_v2/tests/test_experience_writeback_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/__init__.py`
3. `helios_v2/src/helios_v2/__init__.py`
4. `helios_v2/tests/test_runtime_stage_chain.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/15-execution-writeback-and-autobiographical-consolidation/requirement.md`
2. `helios_v2/docs/requirements/15-execution-writeback-and-autobiographical-consolidation/design.md`
3. `helios_v2/docs/requirements/15-execution-writeback-and-autobiographical-consolidation/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Public contracts.
3. Owner skeleton.
4. Runtime stage adapter and export surface.
5. Focused tests.
6. Adjacent runtime-chain validation.
7. Full `helios_v2/tests` regression validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract, owner, and stage validation: `pytest helios_v2/tests/test_experience_writeback_contracts.py helios_v2/tests/test_experience_writeback_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`
4. Full regression validation: `pytest helios_v2/tests -q`

## 6. Completion Criteria

1. A documented API from runtime outcomes into formal experience-writeback results exists.
2. Consolidation-candidate contracts are defined and published.
3. Blocked, failed, successful, and identity-mutating outcomes all remain continuity-visible.
4. Focused contract, owner-skeleton, and runtime-stage tests pass.
5. Full `helios_v2/tests` regression passes.

## 7. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_experience_writeback_contracts.py helios_v2/tests/test_experience_writeback_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `16 passed`
2. `pytest helios_v2/tests -q` -> `168 passed`

Delivered files:

1. `helios_v2/src/helios_v2/experience_writeback/contracts.py`
2. `helios_v2/src/helios_v2/experience_writeback/engine.py`
3. `helios_v2/src/helios_v2/experience_writeback/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_experience_writeback_contracts.py`
8. `helios_v2/tests/test_experience_writeback_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`
