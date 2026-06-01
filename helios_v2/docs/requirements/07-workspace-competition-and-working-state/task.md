# Requirement 07 - Workspace competition and working state task plan

## 1. Task Breakdown

1. Define the workspace competition and working-state API and ops contracts.
2. Encode the confirmed first-version boundaries: memory-only candidate sources, `MemoryReplayCandidate + InteroceptiveFeelingState` input boundary, candidate-set output, owned short-lived working state, and forced-consolidation inclusion semantics.
3. Keep the remaining unresolved workspace semantics as explicit confirmation gates.
4. Keep the allowed first-version deferrals as explicit unimplemented items.
5. Mark the required downstream coordination created by the lack of final conscious-item ownership and multi-source competition as explicit follow-up work.
6. Implement the owner skeleton for input validation, competition request op construction, candidate-set publication, working-state publication, and fail-fast capability checks.
7. Export the public workspace contract surface.
8. Add focused contract and owner-skeleton tests for immutability, provenance, forced-consolidation inclusion, working-state ownership, and no-fallback behavior.

## 2. Dependencies

1. `06-memory-affect-and-replay` for the upstream `MemoryReplayCandidate` contract.
2. `05-interoceptive-feeling-layer` for the upstream `InteroceptiveFeelingState` contract.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/workspace/contracts.py`
2. `helios_v2/src/helios_v2/workspace/engine.py`
3. `helios_v2/src/helios_v2/workspace/__init__.py`
4. `helios_v2/tests/test_workspace_contracts.py`
5. `helios_v2/tests/test_workspace_engine.py`

## 4. Implementation Order

1. Requirement and design definition
2. Confirmed gate encoding
3. Deferred-item encoding
4. Cross-slice coordination marker encoding for later consciousness and multi-source workspace follow-up
5. Residual confirmation gate review for still-unresolved semantics
6. Contracts
7. Owner skeleton
8. Export surface
9. Focused tests

## 5. Validation Plan

1. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_workspace_contracts.py helios_v2/tests/test_workspace_engine.py -q`

## 6. Completion Criteria

1. A documented API from memory replay candidates plus feeling state into workspace competition and working-state update exists.
2. Competition-request, working-state publication, and candidate-set publication ops are defined and documented.
3. The contract surface publishes a workspace candidate set and a short-lived working-state snapshot without claiming final conscious-item ownership.
4. The package encodes the confirmed first-version boundaries: memory-only candidate sources, no direct neuromodulator input, and forced consolidation guarantees inclusion in the candidate set but not top-1 finality.
5. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
6. Required downstream coordination work for later consciousness/report and multi-source workspace integration remains explicitly documented rather than disappearing from the plan.
7. Deferred first-version items remain explicitly documented as unimplemented scope rather than disappearing from the plan.
8. Only the remaining truly unresolved semantics remain as explicit confirmation gates.
9. Focused contract and owner-skeleton tests pass.