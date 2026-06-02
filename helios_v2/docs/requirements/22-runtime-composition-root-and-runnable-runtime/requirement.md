# Requirement 22 - Runtime composition root and runnable runtime

## 1. Background and Problem

Helios v2 now has a real owner chain from `01` through `18`, a fail-fast runtime kernel (`runtime/kernel.py`), explicit stage adapters (`runtime/stages.py`), and an optional observability seam (`21`). The full `01 -> 18` chain is proven to run in a single `RuntimeKernel.tick()` call.

However, that proof exists only inside one test, `helios_v2/tests/test_runtime_stage_chain.py`. There is no runnable runtime in `helios_v2/src`. The concrete symptoms are:

1. There is no composition root in `src`. Nothing in the shipped package assembles the dependency gate, the eighteen stage adapters, the cross-owner bridges, and an optional observability recorder into one constructible runtime handle.
2. The cross-owner bridge providers required by `runtime/stages.py` (for example `MemoryBindingContextProvider`, `ThoughtGateSignalProvider`, `DirectedRetrievalRequestProvider`, `InternalThoughtRequestProvider`, `PlannerBridgeRequestProvider`, `ExperienceWritebackRequestProvider`, `AutonomyRequestProvider`, `EvaluationRequestProvider`, and the prompt/outward-expression request providers) only have ad-hoc `Fixed*` test doubles inside the test file. The only bridge that exists in `src` today is `WorkspaceConsciousContentMaterialBridge`. So the chain cannot be assembled outside the test.
3. There is no driver entry point. A developer cannot run the runtime for several ticks, feed it stimuli, and observe the resulting per-tick stage timeline without re-deriving the entire assembly by hand.
4. Because there is no shipped assembly, the later evaluation and behavioral-truth work (`17`, wave A) has no runnable substrate to consume. It would otherwise be forced to consume the test's private assembly.

This is a foundational gap. The runtime is architecturally complete at the owner level but is not yet a runnable system. A shipped composition root is the prerequisite for end-to-end validation, for consuming the `21` event stream as real runtime evidence, and for every later owner-deepening wave to be verified end-to-end rather than only in isolated unit tests.

## 2. Goal

Introduce one shipped runtime composition root in `helios_v2/src` that assembles the critical-dependency gate, the full ordered `01 -> 18` stage chain with first-version owner-owned cross-owner bridges, and an optional observability recorder into a single constructible, startable, and tickable runtime handle, plus a minimal driver entry point that runs the runtime for a bounded number of ticks and emits a reconstructable per-tick stage timeline, without moving any owner boundary or introducing any degraded or fallback execution path.

## 3. Functional Requirements

### 3.1 Composition root owner
1. `22` must define exactly one composition owner package, `helios_v2.composition`, responsible for assembling a runnable runtime from existing owners.
2. The composition owner must not contain cognitive policy. It must only construct owner engines, owner-owned bridges, the dependency gate, and the kernel, then wire them in the brain-aligned order already defined by `runtime/stages.py`.
3. The composition owner must not reinterpret, mutate, or bypass any owner result. It must only pass explicit public contracts between owners through the existing stage and provider protocols.
4. The composition owner must register stages in the canonical order: sensory ingress, rapid salience appraisal, neuromodulator system, interoceptive feeling, memory affect and replay, workspace competition, reportable conscious content, thought gating, directed retrieval, embodied prompt, outward expression, outward expression externalization, internal thought, action externalization, planner bridge, identity governance, experience writeback, autonomy, evaluation.

### 3.2 First-version owner-owned bridges
1. The composition owner must provide a concrete first-version implementation for every cross-owner bridge protocol declared in `runtime/stages.py` that currently exists only as a test double, so the chain can be assembled from shipped code.
2. Each bridge implementation must preserve upstream provenance ids explicitly and must fail fast when a required upstream artifact is missing or inconsistent, exactly as the stage contracts already require.
3. Bridge implementations must not embed hardcoded runtime strategy. Where a value is needed that an owner has not yet produced, it must be derived from explicit upstream contract fields or from an explicitly injected bootstrap input, not from a fixed in-code decision branch that simulates owner judgment.
4. Bridge implementations must be owner-neutral glue: they may shape and forward explicit upstream results into the next owner's request contract, but they must not compute a downstream owner's semantic decision on its behalf.

### 3.3 Runnable runtime handle
1. The composition owner must expose a single public assembly function or builder that returns a runtime handle wrapping a fully wired `RuntimeKernel`.
2. The assembly must accept an explicit set of critical dependency specs and a dependency provider, and must run the existing fail-fast startup gate before any tick executes.
3. The assembly must accept an optional observability recorder. When supplied, the runtime must emit the `21` lifecycle and per-stage timeline. When omitted, the runtime must run uninstrumented and behave exactly as the bare kernel does today.
4. The runtime handle must support running a single tick and running a bounded sequence of `n` ticks, returning the structured per-tick results in order.
5. The assembly must validate at construction time that all nineteen stages are registered exactly once and in the canonical order, and must raise an explicit error otherwise.

### 3.4 Sensory input boundary
1. The composition owner must accept stimuli for a tick only through the existing sensory ingress owner API. It must not inject stimuli directly into downstream stages.
2. The driver must be able to supply a bounded batch of raw signals per tick through the sensory ingress owner, so the runtime advances on explicit external input plus internal continuity rather than on hidden defaults.

### 3.5 Driver entry point
1. `22` must provide a minimal driver under `helios_v2/scripts` that constructs the runtime through the composition owner, attaches a JSON-line observability sink, runs a bounded number of ticks, and writes the resulting event stream to an explicit output stream or file.
2. The driver must be a thin entry point only. It must not contain owner policy, bridge logic, or assembly logic that belongs in the composition owner.
3. The driver must run a bounded, explicitly specified number of ticks and then stop. It must not start an unbounded background loop.

### 3.6 No fallback behavior
1. Missing critical dependencies must block startup through the existing dependency gate. The composition owner must not substitute a reduced-capability assembly.
2. A missing or inconsistent upstream artifact inside any bridge must raise the existing stage execution error rather than synthesize a placeholder.
3. The composition owner must not provide a degraded assembly mode that omits stages to "just run".

## 4. Non-Functional Requirements

1. Performance: assembly must be a bounded one-time construction cost. Per-tick overhead introduced by the composition layer beyond the owners themselves must be constant and small.
2. Reliability: a constructed runtime must either be fully wired in canonical order or fail construction explicitly. There must be no partially wired runnable state.
3. Observability and logging: the runtime must support the `21` recorder as the single logging mechanism. The composition owner and driver must not introduce `logging` or `print`-based output.
4. Compatibility and migration: the composition owner is additive. Existing kernel construction, existing stage adapters, and the existing stage-chain test must remain valid and unmodified in behavior.

## 5. Code Behavior Constraints

1. The composition owner must not own any cognitive decision. It is assembly-only.
2. The composition owner must not reach into owner private state; it may only construct owners and pass their public contracts.
3. First-version bridges must not become hidden owners. They may forward and shape explicit upstream contract fields but must not compute a downstream owner's semantic judgment.
4. No degraded, reduced, or fallback assembly is allowed. Missing critical dependencies or missing upstream artifacts must fail fast.
5. No `logging` or `print` usage may be introduced. The only legal logging mechanism is the `21` observability owner. This requirement also adds an explicit, enforceable guard described in section 3 of the design.
6. The driver must not embed assembly or owner logic and must not run an unbounded loop.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/__init__.py`
2. `helios_v2/src/helios_v2/composition/bridges.py`
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/src/helios_v2/__init__.py`
6. `helios_v2/scripts/run_runtime_driver.py`
7. `helios_v2/tests/test_runtime_composition.py`
8. `helios_v2/tests/test_no_adhoc_logging_guard.py`
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 7. Acceptance Criteria

1. A documented composition owner package exists exposing a single public assembly entry point that returns a runnable runtime handle wrapping a fully wired `RuntimeKernel` with all nineteen stages registered exactly once in canonical order.
2. Every cross-owner bridge protocol declared in `runtime/stages.py` has a first-version implementation in `helios_v2/src/helios_v2/composition`, so the full chain assembles from shipped code with no test-only doubles.
3. Constructing the runtime runs the fail-fast dependency gate; a missing critical dependency blocks startup with the existing `RuntimeStartupError` and no reduced-mode assembly is produced.
4. Running one tick through the assembled runtime produces the same structured per-stage results that the existing stage-chain assembly produces for an equivalent input, validated by provenance ids rather than only by string contents.
5. Running `n` ticks returns `n` ordered tick results, and when an observability recorder is attached, the captured event stream reconstructs the per-tick stage timeline in canonical stage order with strictly monotonic sequence numbers.
6. With no recorder attached, the assembled runtime emits nothing and behaves identically to the bare kernel.
7. The driver script constructs the runtime through the composition owner, runs a bounded number of ticks, and writes a parseable JSON-line event stream.
8. A repository guard test fails if any module under `helios_v2/src` introduces `import logging`, a logger, or a `print(` call, enforcing that the `21` observability owner is the single logging mechanism.
9. The full `helios_v2/tests` suite remains green.
