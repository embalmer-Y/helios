# Requirement 18 - Subjective autonomy and proactive evolution task plan

## 1. Task Breakdown

1. Define the autonomy API and ops contracts.
2. Define explicit request contracts for proactive-drive integration.
3. Implement public contracts for drive state, deferred continuity, result taxonomy, API, and ops contracts.
4. Implement the owner skeleton for proactive integration and deferred-continuity publication.
5. Implement runtime-stage wiring.
6. Export the public autonomy surface.
7. Add focused autonomy tests.
8. Extend evaluation so R17 consumes the new autonomy artifact.

## 2. Dependencies

1. `09-thought-gating-and-continuation-pressure`
2. `11-internal-thought-loop-owner`
3. `13-planner-executor-feedback-bridge`
4. `15-execution-writeback-and-autobiographical-consolidation`
5. `16-embodied-subjective-prompt-and-action-autonomy`
6. `17-evaluation-fidelity-and-diagnostic-provenance`

## 3. Files and Modules

1. `helios_v2/src/helios_v2/autonomy/contracts.py`
2. `helios_v2/src/helios_v2/autonomy/engine.py`
3. `helios_v2/src/helios_v2/autonomy/__init__.py`
4. `helios_v2/tests/test_autonomy_contracts.py`
5. `helios_v2/tests/test_autonomy_engine.py`

## 4. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_autonomy_contracts.py helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`
4. `pytest helios_v2/tests -q`

## 5. Completion Criteria

1. A documented API for proactive-drive integration exists.
2. Deferred continuity is formally represented.
3. Outward proactive behavior still routes through formal action owners.

## 6. Completion Snapshot

1. `helios_v2/src/helios_v2/autonomy/` landed with immutable contracts, deterministic baseline policy, and public exports.
2. `AutonomyRuntimeStage` now executes after experience writeback and before evaluation, with owner-private multi-tick deferred-continuity carry.
3. `DeferredContinuityRecord` and `FirstVersionAutonomyPath` now encode long-horizon decay, same-key merge, and explicit resolved-or-expired continuity accounting instead of only bounded carry-forward.
4. `evaluation/` now consumes `autonomy_evidence` alongside the two-layer outward-expression artifact chain.
5. Validation for the current closeout state is now `26 passed` on the requirement-adjacent focused slice and `204 passed` on the full `helios_v2/tests` suite.
