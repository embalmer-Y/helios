# Requirement 02 - Sensory ingress task plan

## 1. Task Breakdown

1. Define sensory ingress API and ops contracts.
2. Implement source registration and normalization owner.
3. Export the public sensory ingress surface.
4. Add focused tests for duplicate source rejection, normalization, and invalid required signal failure.

## 2. Dependencies

1. `01-runtime-kernel` for owner-safe lifecycle integration and fail-fast runtime expectations.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/sensory/contracts.py`
2. `helios_v2/src/helios_v2/sensory/ingress.py`
3. `helios_v2/src/helios_v2/sensory/__init__.py`
4. `helios_v2/tests/test_sensory_ingress.py`

## 4. Implementation Order

1. Requirement and design definition
2. Contracts
3. Owner implementation
4. Focused tests

## 5. Validation Plan

1. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_sensory_ingress.py -q`

## 6. Completion Criteria

1. Sensory ingress registers unique source owners only.
2. Valid raw signals normalize into immutable stimuli with preserved provenance.
3. Invalid required signals fail explicitly.
4. Public API and ops contracts are documented according to the guide.