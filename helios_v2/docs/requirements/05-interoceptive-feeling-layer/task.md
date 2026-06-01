# Requirement 05 - Interoceptive feeling layer task plan

## 1. Task Breakdown

1. Define the interoceptive feeling API and ops contracts.
2. Encode the confirmed input boundary, including reused `sensory.Stimulus` for optional body/interoceptive signals, feeling-schema minimum, publication boundary, learning policy, and no-hard-gate rule in the contract and design surface.
3. Keep the remaining unresolved feeling semantics as explicit confirmation gates.
4. Implement the owner skeleton for neuromodulator-state validation, optional internal-signal intake, update op construction, and feeling-state publication.
5. Export the public feeling contract surface.
6. Add focused contract and owner-skeleton tests for immutability, provenance, validation, learned-parameter surfacing, and no-fallback behavior.

## 2. Dependencies

1. `04-neuromodulator-system` for the upstream `NeuromodulatorState` contract.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/feeling/contracts.py`
2. `helios_v2/src/helios_v2/feeling/engine.py`
3. `helios_v2/src/helios_v2/feeling/__init__.py`
4. `helios_v2/tests/test_interoceptive_feeling_contracts.py`
5. `helios_v2/tests/test_interoceptive_feeling_engine.py`

## 4. Implementation Order

1. Requirement and design definition
2. Confirmed gate encoding
3. Residual confirmation gate review for still-unresolved semantics
4. Contracts
5. Owner skeleton
6. Export surface
7. Focused tests

## 5. Validation Plan

1. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_interoceptive_feeling_contracts.py helios_v2/tests/test_interoceptive_feeling_engine.py -q`

## 6. Completion Criteria

1. A documented API from neuromodulator state into feeling-state update exists.
2. Update and publication ops are defined and documented.
3. The contract surface models the confirmed dimensional feeling vector and excludes memory, workspace, and action semantics.
4. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
5. The package encodes the confirmed learning policy, reused body/interoceptive signal contract, publication boundary, and no-hard-gate rule without hardcoding permanent heuristics.
6. Only the remaining truly unresolved semantics remain as explicit confirmation gates.
7. Focused contract and owner-skeleton tests pass.