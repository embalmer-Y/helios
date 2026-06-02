# Requirement 21 - Unified runtime observability and logging task plan

## 1. Title

Requirement 21 - Unified runtime observability and logging

## 2. Task Breakdown

1. Define the observability owner contracts: `LogSeverity`, `LogEventKind`, `LogEvent`, `LogSink` protocol, and `ObservabilityError` in `observability/contracts.py`.
2. Implement the recorder and sinks: `RuntimeObservabilityRecorder`, `InMemoryLogSink`, and `JsonLineStreamLogSink` in `observability/engine.py`.
3. Export the public observability surface in `observability/__init__.py`.
4. Integrate the optional recorder emission seam into `runtime/kernel.py` for startup, per-stage start/completion/failure, and tick completion.
5. Surface the observability recorder and `LogEvent` from the top-level package `__init__.py`.
6. Add focused contract tests in `tests/test_observability_contracts.py`.
7. Add focused engine tests in `tests/test_observability_engine.py`.
8. Add kernel integration tests in `tests/test_runtime_kernel_observability.py`.
9. Update `docs/requirements/index.md` and `docs/ARCHITECTURE_BOUNDARIES.md` to record the new owner and its boundary.

## 3. Dependencies

1. `01-runtime-kernel` provides the kernel lifecycle and stage dispatch that the emission seam wraps.

This requirement does not depend on any cognitive owner internals. It observes only public kernel-held stage results and lifecycle events.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/observability/contracts.py`
2. `helios_v2/src/helios_v2/observability/engine.py`
3. `helios_v2/src/helios_v2/observability/__init__.py`
4. `helios_v2/src/helios_v2/runtime/kernel.py`
5. `helios_v2/src/helios_v2/__init__.py`
6. `helios_v2/tests/test_observability_contracts.py`
7. `helios_v2/tests/test_observability_engine.py`
8. `helios_v2/tests/test_runtime_kernel_observability.py`
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 5. Implementation Order

1. Land `observability/contracts.py` first; it has no internal dependency.
2. Land `observability/engine.py` against the contracts.
3. Land `observability/__init__.py` exports.
4. Add contract and engine tests, validate the owner package in isolation.
5. Integrate the optional recorder into `runtime/kernel.py`.
6. Add kernel integration tests.
7. Update top-level exports.
8. Update `index.md` and `ARCHITECTURE_BOUNDARIES.md`.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_observability_contracts.py helios_v2/tests/test_observability_engine.py helios_v2/tests/test_runtime_kernel_observability.py -q`
4. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. The observability owner package exists with documented public interfaces.
2. A zero-sink recorder raises, severity threshold filtering works, and sink failures propagate.
3. The in-memory sink preserves order and the JSON-line stream sink output parses back to the event record.
4. `RuntimeKernel` emits startup, per-stage start/completion/failure with `tick_id` and `stage_name`, and tick-completion events when a recorder is injected.
5. A no-recorder kernel run emits nothing and preserves prior behavior, with the full suite green.

## 8. Completion Snapshot

Status on 2026-06-02: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_observability_contracts.py helios_v2/tests/test_observability_engine.py helios_v2/tests/test_runtime_kernel_observability.py -q` -> `24 passed`
2. `pytest helios_v2/tests -q` -> `228 passed`

Delivered files:

1. `helios_v2/src/helios_v2/observability/contracts.py`
2. `helios_v2/src/helios_v2/observability/engine.py`
3. `helios_v2/src/helios_v2/observability/__init__.py`
4. `helios_v2/src/helios_v2/runtime/kernel.py`
5. `helios_v2/src/helios_v2/__init__.py`
6. `helios_v2/tests/test_observability_contracts.py`
7. `helios_v2/tests/test_observability_engine.py`
8. `helios_v2/tests/test_runtime_kernel_observability.py`
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
