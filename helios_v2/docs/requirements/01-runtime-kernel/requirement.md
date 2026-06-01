# Requirement 01 - Runtime kernel

## 1. Background and Problem

The original Helios runtime accumulated orchestration responsibilities, transition-era behavior branches, and reply-first compatibility paths inside the main loop. That shape makes it difficult to enforce clean owner boundaries, hard startup gates, and a single runtime truth.

Helios v2 needs a new kernel that owns only lifecycle orchestration and dependency gating. It must not contain degraded modes, fallback behavior, or strategy shortcuts.

## 2. Goal

Create a runtime kernel that validates critical dependencies before startup, orchestrates registered stages in a fixed lifecycle, and aborts execution explicitly when critical runtime invariants are violated.

## 3. Functional Requirements

### 3.1 Startup dependency gate
1. The kernel must require explicit declaration of critical runtime dependencies before startup.
2. The kernel must fail startup when any declared critical dependency is unavailable.
3. The kernel must report all missing critical dependencies in a structured error.

### 3.2 Stage orchestration
1. The kernel must orchestrate runtime work through registered stages.
2. Each stage must expose a single owner-facing lifecycle contract.
3. The kernel must stop the active execution path if a critical stage invariant fails.

### 3.3 No fallback execution
1. The kernel must not substitute an alternative path when a critical dependency or stage is unavailable.
2. The kernel must not embed fixed strategy routing or degraded behavior branches.

## 4. Non-Functional Requirements

1. Startup validation must be deterministic and complete for the declared dependency set.
2. Failure reporting must be explicit enough for diagnostics and test assertions.
3. The kernel API must remain small and owner-oriented to reduce orchestration sprawl.

## 5. Code Behavior Constraints

1. Kernel code must not infer missing dependencies from implicit defaults.
2. Kernel code must not import domain strategy owners just to emulate unavailable behavior.
3. Startup and runtime abort semantics must be explicit in code and tests.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/runtime/dependencies.py`
2. `helios_v2/src/helios_v2/runtime/kernel.py`
3. `helios_v2/src/helios_v2/runtime/contracts.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_runtime_dependencies.py`
6. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. Startup with all declared critical dependencies available succeeds.
2. Startup with any missing critical dependency raises a structured error naming the missing dependencies.
3. Kernel stage execution returns a structured runtime snapshot when all stages succeed.
4. The first runtime chain can execute `sensory ingress -> rapid salience appraisal -> neuromodulator system -> interoceptive feeling layer` through explicit stage adapters rather than hidden shared state.
5. No test or implementation path demonstrates degraded or fallback execution for missing critical capabilities.