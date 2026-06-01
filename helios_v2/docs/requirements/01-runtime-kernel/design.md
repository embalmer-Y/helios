# Requirement 01 - Runtime kernel design

## 1. Design Overview

The runtime kernel is a narrow orchestration owner. It owns startup validation, stage registration, and lifecycle dispatch. It does not own domain strategy, policy, prompt logic, or transport-specific behavior.

## 2. Current State and Gap

Helios v1 centralizes too much orchestration in a monolithic runtime loop. It contains transition logic and compatibility-era branching that is incompatible with Helios v2 goals.

The missing foundation in v2 is a clean kernel contract that can reject incomplete startup and drive registered stage owners without fallback semantics.

## 3. Target Architecture

The initial architecture contains five runtime concepts:

1. `RuntimeDependencySpec`: a declared critical capability requirement.
2. `RuntimeFrame`: an immutable runtime-owned input contract for one stage execution.
3. `RuntimeStage`: an owner-facing protocol with `stage_name` and `run(frame)`.
4. `RuntimeKernel`: the startup gate and stage dispatcher.
5. Stage adapter records: runtime-owned wrappers that translate between domain owner APIs and ordered stage execution.

Lifecycle:

1. Construct kernel with dependency specs.
2. Validate declared dependencies using a dependency provider.
3. Refuse startup if any required capability is unavailable.
4. Dispatch registered stages in order for a tick while passing each stage an immutable frame of prior stage outputs.
5. Return a structured snapshot of per-stage outputs.

First executable chain in this slice:

1. `SensoryIngressRuntimeStage` calls the sensory ingress owner API and returns a structured stage result.
2. `RapidSalienceAppraisalRuntimeStage` reads that prior stage result from the immutable frame, builds the request op, calls the appraisal owner API, and returns a structured stage result.
3. `NeuromodulatorRuntimeStage` reads the prior appraisal stage result from the immutable frame, builds the update op, calls the neuromodulator owner API, and returns a structured stage result.
4. `InteroceptiveFeelingRuntimeStage` reads the prior neuromodulator stage result from the immutable frame, optionally reuses body/interoceptive sensory signals, calls the feeling owner API, and returns a structured stage result.
5. Missing or malformed upstream stage results abort execution explicitly.

## 4. Data Structures

### 4.1 RuntimeDependencySpec
- `name: str`
- `required: bool`
- `description: str`

### 4.2 RuntimeDependencyStatus
- `name: str`
- `available: bool`
- `detail: str | None`

### 4.3 RuntimeTickResult
- `tick_id: int`
- `stage_results: Mapping[str, object]`

### 4.4 RuntimeFrame
- `tick_id: int`
- `stage_results: Mapping[str, object]`

### 4.5 SensoryIngressStageResult
- `batch: StimulusBatch`
- `publish_op: PublishStimulusBatchOp`

### 4.6 RapidSalienceAppraisalStageResult
- `assess_op: AssessStimulusBatchOp`
- `batch: RapidAppraisalBatch`
- `publish_op: PublishRapidAppraisalBatchOp`

### 4.7 NeuromodulatorStageResult
- `update_op: UpdateNeuromodulatorsOp`
- `state: NeuromodulatorState`
- `publish_op: PublishNeuromodulatorStateOp`

### 4.8 InteroceptiveFeelingStageResult
- `update_op: UpdateInteroceptiveFeelingOp`
- `state: InteroceptiveFeelingState`
- `publish_op: PublishInteroceptiveFeelingStateOp`

## 5. Module Changes

1. `dependencies.py` defines startup dependency contracts and structured startup errors.
2. `contracts.py` defines the runtime frame, runtime stage protocol, and dependency provider protocol.
3. `kernel.py` wires dependency validation and ordered stage dispatch with immutable prior-stage visibility.
4. `stages.py` defines explicit runtime-owned adapters for sensory ingress, rapid appraisal, neuromodulator execution, and interoceptive feeling execution.
5. Tests validate startup success, startup failure, stage result aggregation, frame immutability, and the first executable stage chain.

## 6. Migration Plan

This slice does not migrate Helios v1 code directly.

Instead, it creates a clean foundation that later domains can plug into. Existing Helios runtime code remains reference-only.

## 7. Failure Modes and Constraints

1. Missing critical dependency must raise `RuntimeStartupError` before any stage executes.
2. Duplicate stage names must raise a configuration error.
3. The kernel must not continue after a critical stage abort.
4. No fallback mode is allowed.
5. Downstream stages must fail explicitly if their declared upstream stage result is missing or malformed.

## 8. Observability and Logging

Initial implementation keeps observability minimal and testable:

1. startup errors expose missing dependency names,
2. tick results expose tick identity and stage output by stage name,
3. stage adapter results preserve domain batch, state, feeling, and ops provenance for test assertions.

Logging expansion is deferred until the evaluation and diagnostics slice.

## 9. Validation Strategy

1. Unit test startup success with all dependencies available.
2. Unit test startup failure with missing dependencies.
3. Unit test ordered stage aggregation.
4. Unit test immutable prior-stage frame passing.
5. Unit test duplicate stage rejection.
6. Unit test the `sensory ingress -> rapid salience appraisal -> neuromodulator system -> interoceptive feeling layer` runtime chain.
7. Unit test explicit failure when appraisal stage lacks the required upstream sensory stage result.
8. Unit test explicit failure when neuromodulator stage lacks the required upstream appraisal stage result.
9. Unit test explicit failure when interoceptive feeling stage lacks the required upstream neuromodulator stage result.