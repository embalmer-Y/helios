# Requirement 04 - Neuromodulator system task plan

## 1. Task Breakdown

1. Define the neuromodulator state API and ops contracts.
2. Encode the confirmed baseline input mapping, allowed initialization priors, learned-parameter categories, decay family, and hard/soft gate scope in the contract and design surface.
3. Keep the remaining unresolved neuromodulator semantics as explicit confirmation gates.
4. Implement the owner skeleton for appraisal-batch validation, update op construction, and state publication.
5. Export the public neuromodulator contract surface.
6. Add focused contract and owner-skeleton tests for immutability, provenance, validation, learned-parameter surfacing, and no-fallback behavior.

## 2. Dependencies

1. `03-rapid-salience-appraisal` for the upstream `RapidAppraisalBatch` contract.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/neuromodulation/contracts.py`
2. `helios_v2/src/helios_v2/neuromodulation/engine.py`
3. `helios_v2/src/helios_v2/neuromodulation/__init__.py`
4. `helios_v2/tests/test_neuromodulator_contracts.py`
5. `helios_v2/tests/test_neuromodulator_engine.py`

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
2. `pytest helios_v2/tests/test_neuromodulator_contracts.py helios_v2/tests/test_neuromodulator_engine.py -q`

## 6. Completion Criteria

1. A documented API from rapid appraisal into neuromodulator update exists.
2. Update and publication ops are defined and documented.
3. The contract surface models independent neuromodulator channels and excludes feeling, memory, and action semantics.
4. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
5. The package encodes the confirmed learned-parameter policy, allowed priors, decay family, and hard/soft gate scope without hardcoding permanent heuristics.
6. Only the remaining truly unresolved semantics remain as explicit confirmation gates.
7. Focused contract and owner-skeleton tests pass.