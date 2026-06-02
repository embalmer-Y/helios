# Requirement 21 - Unified runtime observability and logging

## 1. Background and Problem

Helios v2 now has a real owner chain from `01` through `18`, wired into a single tick-based runtime through `runtime/kernel.py` and `runtime/stages.py`. Every owner emits structured result and ops objects, and the chain enforces provenance at each hop.

However, there is currently no logging or runtime observability layer at all. A repository-wide search for `import logging`, `getLogger`, or any logger usage in `helios_v2/src` returns zero matches. Each owner design from `01` through `18` explicitly states that observability is kept "structural" and that "logging expansion is deferred until the evaluation and diagnostics slice".

This creates concrete problems:

1. There is no uniform way to observe what the runtime did during a tick. The only observable artifacts are the in-memory stage result objects returned by `RuntimeKernel.tick`, which are not timestamped, not sequenced, not severity-tagged, and not emittable to any sink.
2. There is no correlation surface. When a stage fails, there is no structured record tying the failure to a `tick_id`, a `stage_name`, an ordering position, or a duration.
3. Debugging the `01 -> 18` chain currently depends on reading raw exceptions or attaching a debugger, because no stage-by-stage execution trace is produced.
4. Each owner deferred logging individually, so there is no single owner for the cross-cutting concern, which risks logging being reinvented inconsistently inside each owner and leaking into owner code as ad-hoc `print` or hidden state.

This is a foundational gap. A unified, structured observability layer is a prerequisite for debugging, for the evaluation owner (`17`) to later reconstruct causal chains from durable records, and for any future runtime-assembly and long-running operation.

## 2. Goal

Introduce one runtime-owned observability layer that produces structured, severity-tagged, sequence-correlated log events for the whole `01 -> 18` runtime path through a single kernel-level emission seam, dispatches those events to explicitly configured sinks with fail-fast semantics, and never becomes a home for authoritative runtime state or a cross-owner reach-through channel.

## 3. Functional Requirements

### 3.1 Owner boundary
1. `21` must define exactly one semantic owner package, `helios_v2.observability`, for structured runtime log events, severity taxonomy, sink dispatch, and the runtime observability recorder.
2. The observability owner must be read-only with respect to cognitive runtime state. It must not mutate any owner state, planner authority, channel execution, or governance decisions.
3. The observability owner must not become a transport for authoritative state between owners. Log events may mirror already-formal state and ops, but no owner may depend on the log channel to receive another owner's decision.
4. Cognitive owners (`02 - 18`) must not import the observability owner to emit their own logs in this slice. The uniform emission point for the chain is the runtime kernel, which observes public stage results only.

### 3.2 Structured log event contract
1. The owner must define an immutable structured log-event contract carrying at minimum: a stable event id, a monotonically increasing sequence number, an optional tick id, an optional stage name, the emitting owner name, a severity, an event kind, a message, provenance references, and a bounded structured payload.
2. Severity must use a fixed taxonomy of `debug`, `info`, `notice`, `warning`, `error`, and `critical`.
3. Event kind must use a fixed taxonomy that at minimum distinguishes runtime startup, runtime startup failure, stage start, stage completion, stage failure, tick completion, and generic owner emission.
4. The event contract must reject empty owner names, empty messages, unknown severities, unknown event kinds, and negative sequence numbers.

### 3.3 Recorder and sink behavior
1. The owner must provide a runtime observability recorder that stamps each event with a monotonically increasing sequence number and a stable event id, then dispatches the event to all configured sinks.
2. The recorder must require at least one configured sink. Constructing a recorder with zero sinks must raise an explicit error.
3. The recorder must support a minimum-severity threshold. Events below the threshold must be built and returned but must not be dispatched to sinks.
4. The owner must provide at least an in-memory sink for inspection and a stream sink that serializes each event as one JSON line.
5. Sink dispatch failures must propagate as explicit errors. The recorder must not silently swallow a sink failure.

### 3.4 Runtime integration
1. The runtime kernel must accept an optional injected observability recorder.
2. When a recorder is present, the kernel must emit a startup event on successful dependency validation and a startup-failure event before re-raising on missing dependencies.
3. When a recorder is present, the kernel must emit a stage-start event before each stage runs, a stage-completion event with the stage execution duration after each stage runs, and a stage-failure event before re-raising when a stage raises.
4. When a recorder is present, the kernel must emit a tick-completion event after all stages in a tick complete.
5. Every kernel-emitted stage event must carry the current `tick_id` and the `stage_name`, so the per-tick stage timeline of the `01 -> 18` chain is reconstructable from the event stream alone.
6. When no recorder is injected, the kernel must run exactly as before and emit nothing. The absence of a recorder is a non-instrumented runtime, not a degraded cognitive mode.

### 3.5 No fallback behavior
1. Missing sinks must fail explicitly at recorder construction rather than degrade to a no-op recorder.
2. Sink failures must surface rather than be hidden behind optimistic defaults.
3. The observability layer must not invent or infer runtime events that did not occur.

## 4. Non-Functional Requirements

1. Performance: per-stage instrumentation must add only bounded constant overhead per stage and must not change stage execution order or stage results.
2. Reliability: event sequence numbers must be strictly monotonic per recorder instance, so event ordering is deterministic and reconstructable.
3. Observability: events must be serializable to a stable JSON-line shape for durable capture and later diagnostic consumption.
4. Compatibility and migration: observability must be default-off at the kernel level through an optional injected recorder, so existing runtime construction and existing tests remain valid without modification.

## 5. Code Behavior Constraints

1. The observability owner must not import cognitive owner engines or reach into their private state.
2. The runtime kernel must observe only the public stage result objects it already aggregates. It must not introspect owner internals to build events.
3. Log events must not be used as the authoritative source of any first-class runtime concept. Authoritative state remains in formal result and ops contracts.
4. The recorder must not provide a degraded zero-sink mode.
5. Sink emission errors must not be swallowed.
6. No owner may add `print`-based or unstructured logging once this owner exists.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/observability/__init__.py`
2. `helios_v2/src/helios_v2/observability/contracts.py`
3. `helios_v2/src/helios_v2/observability/engine.py`
4. `helios_v2/src/helios_v2/runtime/kernel.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_observability_contracts.py`
8. `helios_v2/tests/test_observability_engine.py`
9. `helios_v2/tests/test_runtime_kernel_observability.py`
10. `helios_v2/docs/requirements/index.md`
11. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 7. Acceptance Criteria

1. A documented observability owner package exists exposing an immutable structured log-event contract, a fixed severity taxonomy, a fixed event-kind taxonomy, a sink protocol, and a runtime observability recorder API.
2. Constructing a recorder with zero sinks raises an explicit error, and a recorder with a minimum-severity threshold dispatches only events at or above that threshold.
3. The in-memory sink captures dispatched events in order, and the stream sink serializes each event as one parseable JSON line.
4. A sink that raises during emission causes the recorder dispatch to raise rather than silently continue.
5. `RuntimeKernel` accepts an optional recorder, and when present emits startup, per-stage start, per-stage completion with duration, per-stage failure, and tick-completion events carrying `tick_id` and `stage_name`.
6. With no recorder injected, `RuntimeKernel.startup` and `RuntimeKernel.tick` behave identically to the pre-change behavior and the existing runtime tests still pass.
7. The per-tick stage timeline for a multi-stage run is reconstructable from the captured event stream in stage order with strictly monotonic sequence numbers.

## 8. Implementation Status

Status on 2026-06-02: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/observability/contracts.py` defines the immutable `LogEvent`, the fixed `LogSeverity` and `LogEventKind` taxonomies, `severity_rank`, the `LogSink` protocol, and `ObservabilityError`, with JSON-serializable `to_record`.
2. `helios_v2/src/helios_v2/observability/engine.py` defines `InMemoryLogSink`, `JsonLineStreamLogSink`, and the sequence-stamping `RuntimeObservabilityRecorder` with zero-sink fail-fast, minimum-severity threshold filtering, and non-swallowed sink failures.
3. `helios_v2/src/helios_v2/runtime/kernel.py` integrates an optional `recorder` field and emits `runtime_startup`, `runtime_startup_failed`, `stage_started`, `stage_completed` (with measured duration), `stage_failed`, and `runtime_tick_completed` events carrying `tick_id` and `stage_name`.
4. `helios_v2/src/helios_v2/__init__.py` surfaces `RuntimeObservabilityRecorder`, `LogEvent`, `LogSink`, and `ObservabilityError`.
5. `helios_v2/tests/test_observability_contracts.py`, `helios_v2/tests/test_observability_engine.py`, and `helios_v2/tests/test_runtime_kernel_observability.py` cover contract validation, recorder/sink behavior, and the kernel emission seam including the no-recorder regression path.

Validated outcomes:

1. `pytest helios_v2/tests/test_observability_contracts.py helios_v2/tests/test_observability_engine.py helios_v2/tests/test_runtime_kernel_observability.py -q` -> `24 passed`
2. `pytest helios_v2/tests -q` -> `228 passed`

Implementation note:

1. The emission seam is default-off. A kernel constructed without a recorder behaves identically to the pre-change kernel and emits nothing. Owner-level fine-grained emission is intentionally deferred to a later slice and would be added through the same observability owner without changing the `LogEvent` contract.
