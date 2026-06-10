# Requirement 77 - Long-Term Stability Prerequisites

## 1. Background and Problem

The Helios v2 runtime has passed P3 exit (R64) and is progressing through P1/P2 evaluation.
However, long-term operational stability requires properties that individual feature tests
do not validate:

1. **Resource boundedness**: after 20+ ticks, memory and storage growth must be bounded,
   not linear-unbounded.
2. **State isolation**: independent runtime handles must not share mutable state (cross-handle
   leakage would cause subtle bugs in multi-instance deployments).
3. **Checkpoint corruption recovery**: corrupted checkpoint files must trigger fail-fast,
   never silent degradation.
4. **Embedding failure isolation**: embedding exceptions must be hard-stop, never falling
   back to recency-only retrieval.
5. **Zero-percept and high-load closure**: empty input and high-load ticks must complete
   the full chain without error (R65/R54).
6. **Owner boundary non-regression**: composition guard tests must remain green.

## 2. Goal

Provide a read-only prerequisite assessment that validates the six long-term stability
properties, producing a structured `StabilityVerdict` that gates whether the system is
ready for extended operational deployment.

## 3. Functional Requirements

### 3.1 LT-1: Resource boundedness

1. A test must run 20 ticks and verify that memory growth (tracemalloc) is bounded
   (peak < 500 MB) and store growth is proportional to tick count (not quadratic).

### 3.2 LT-2: State isolation

1. A test must create two independent handles, run ticks on both, and verify that
   handle A's store does not contain handle B's records.

### 3.3 LT-3: Checkpoint corruption recovery

1. A test must write a corrupted checkpoint file and verify that loading it raises
   an exception (fail-fast), not silent degradation.

### 3.4 LT-4: Embedding failure isolation

1. A test must inject a raising embedding provider and verify that `assemble_runtime()`
   raises at startup or first embedding call (hard-stop, no fallback).

### 3.5 LT-5: Zero-percept and high-load closure

1. A test must verify that a zero-percept tick (empty sensory batch) completes without
   error (R65 path).
2. A test must verify that a high-load tick (elevated pressure) completes the `18`/`17`
   tail without error (R54 path).

### 3.6 LT-6: Owner boundary non-regression

1. A test must verify that `test_composition_owner_boundary_guard` patterns still pass
   (composition does not import cognitive policy from owners).

### 3.7 Composite verdict

1. Aggregate all checks into a `StabilityVerdict`.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: no owner code modification.
3. **Bounded time**: each test completes in under 30 seconds.

## 5. Code Behavior Constraints

1. State isolation tests must create handles with separate `ExperienceStore` instances.
2. Checkpoint corruption test must write raw bytes, not use the checkpoint API.
3. Embedding failure test must inject a `_RaisingEmbeddingProvider` that raises on `.embed()`.

## 6. Impacted Modules

1. `helios_v2/tests/test_long_term_stability_prerequisites.py` — new prerequisite module.
2. `helios_v2/docs/requirements/index.md` — new R77 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_long_term_stability_prerequisites.py -v` passes all tests.
2. Composite verdict covers LT-1 through LT-6.
3. Full suite still passes.
