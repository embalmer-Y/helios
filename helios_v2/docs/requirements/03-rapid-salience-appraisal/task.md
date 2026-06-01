# Requirement 03 - Rapid salience appraisal task plan

## 1. Task Breakdown

1. Define the rapid appraisal API and ops contracts.
2. Implement the owner skeleton for batch assessment and op construction.
3. Export the public appraisal contract surface.
4. Add focused contract and owner-skeleton tests for immutability, provenance, and validation.
5. Keep `aggregate` as an owner-produced field while deferring permanent scoring implementation until appraisal semantics are further confirmed.

## 2. Dependencies

1. `02-sensory-ingress` for the upstream `StimulusBatch` contract.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/appraisal/contracts.py`
2. `helios_v2/src/helios_v2/appraisal/engine.py`
3. `helios_v2/src/helios_v2/appraisal/__init__.py`
4. `helios_v2/tests/test_rapid_salience_contracts.py`
5. `helios_v2/tests/test_rapid_salience_engine.py`

## 4. Implementation Order

1. Requirement and design definition
2. Contracts
3. Owner skeleton
4. Export surface
5. Focused tests

## 5. Validation Plan

1. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_rapid_salience_contracts.py helios_v2/tests/test_rapid_salience_engine.py -q`

## 6. Completion Criteria

1. A documented API from sensory ingress into rapid appraisal exists.
2. Assessment and publication ops are defined and documented.
3. The owner skeleton enforces the confirmed boundary and does not depend on downstream domains.
4. The contract surface includes uncertainty, excludes fine semantic and action semantics, and permits valid low-salience outputs.
5. Focused contract and owner-skeleton tests pass.