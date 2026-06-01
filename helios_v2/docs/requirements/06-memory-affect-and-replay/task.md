# Requirement 06 - Memory affect and replay task plan

## 1. Task Breakdown

1. Define the memory affect and replay API and ops contracts.
2. Encode the confirmed affect-tag reuse rule, first-version replay triggers, forced-consolidation rule, candidate-output granularity, and no-workspace-ownership rule in the contract and design surface.
3. Keep the remaining unresolved memory/replay semantics as explicit confirmation gates.
4. Keep the allowed first-version deferrals as explicit unimplemented items.
5. Mark the required downstream coordination created by `5A` and `6A` as explicit follow-up work for later workspace and identity slices.
6. Implement the owner skeleton for feeling-state validation, memory-record op construction, replay-candidate publication, memory-state publication, and fail-fast capability checks.
6. Export the public memory contract surface.
7. Add focused contract and owner-skeleton tests for immutability, provenance, affect-tag reuse, replay-trigger surfacing, forced-consolidation handling, and no-fallback behavior.

## 2. Dependencies

1. `05-interoceptive-feeling-layer` for the upstream `InteroceptiveFeelingState` and `InteroceptiveFeelingVector` contracts.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/memory/contracts.py`
2. `helios_v2/src/helios_v2/memory/engine.py`
3. `helios_v2/src/helios_v2/memory/__init__.py`
4. `helios_v2/tests/test_memory_contracts.py`
5. `helios_v2/tests/test_memory_engine.py`

## 4. Implementation Order

1. Requirement and design definition
2. Confirmed gate encoding
3. Deferred-item encoding
4. Cross-slice coordination marker encoding for workspace and identity follow-up
5. Residual confirmation gate review for still-unresolved semantics
6. Contracts
7. Owner skeleton
8. Export surface
9. Focused tests

## 5. Validation Plan

1. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_memory_contracts.py helios_v2/tests/test_memory_engine.py -q`

## 6. Completion Criteria

1. A documented API from feeling state into affect-linked memory recording exists.
2. Record, replay-candidate publication, and memory-state publication ops are defined and documented.
3. The contract surface reuses `InteroceptiveFeelingVector` and preserves provenance without introducing a second affect-language schema.
4. The package encodes the three confirmed first-version replay triggers and the forced-consolidation rule for `high anomaly + high affect`.
5. The package publishes candidate memory items for later workspace owners without claiming final conscious-content selection.
6. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
7. Required downstream coordination work for later workspace and identity integration remains explicitly documented rather than disappearing behind `5A` and `6A`.
8. Deferred first-version items remain explicitly documented as unimplemented scope rather than disappearing from the plan.
9. Only the remaining truly unresolved semantics remain as explicit confirmation gates.
10. Focused contract and owner-skeleton tests pass.