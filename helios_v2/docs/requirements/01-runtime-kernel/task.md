# Requirement 01 - Runtime kernel task plan

## 1. Task Breakdown

1. Define runtime dependency contracts and startup error model.
2. Define runtime stage protocol and immutable runtime frame contract.
3. Implement kernel startup gate and ordered stage dispatch.
4. Add focused unit tests for startup gating, stage aggregation, and immutable frame passing.
5. Add runtime-owned stage adapters for the first executable `01 -> 02 -> 03` chain.
6. Add focused end-to-end chain tests for explicit stage-to-stage data flow.

## 2. Dependencies

1. No upstream Helios v2 requirement dependency.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/runtime/contracts.py`
2. `helios_v2/src/helios_v2/runtime/dependencies.py`
3. `helios_v2/src/helios_v2/runtime/kernel.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_runtime_dependencies.py`
6. `helios_v2/tests/test_runtime_stage_chain.py`

## 4. Implementation Order

1. Contracts
2. Dependency gate
3. Kernel
4. Stage adapters
5. Tests

## 5. Validation Plan

1. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
2. `pytest helios_v2/tests/test_runtime_dependencies.py helios_v2/tests/test_runtime_stage_chain.py -q`

## 6. Completion Criteria

1. Startup succeeds when declared critical dependencies are available.
2. Startup fails explicitly when declared critical dependencies are missing.
3. Kernel aggregates stage output deterministically.
4. Later stages receive immutable prior-stage outputs through an explicit runtime contract.
5. The first runtime stage chain executes sensory ingress before rapid appraisal, neuromodulator update, and interoceptive feeling update through explicit runtime-owned adapters.
6. Missing upstream stage results abort the active execution path explicitly.
7. No fallback or degraded mode exists in the implementation.