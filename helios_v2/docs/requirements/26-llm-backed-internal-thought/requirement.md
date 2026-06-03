# Requirement 26 - LLM-backed internal thought

## 1. Background and Problem

The internal-thought owner (`11`) is the runtime's cognition core: it consumes a fired gate result, the directed-retrieval thought window, and continuation pressure, then publishes a formal `ThoughtCycleResult` with `ThoughtContent`, a sufficiency judgment, a continuation decision, an optional memory handoff, and an optional action or self-revision proposal. Today its only shipped path, `FirstVersionInternalThoughtPath`, synthesizes content by deterministic string assembly with `llm_used=False`. Every downstream owner therefore reasons about deterministic shim content, and the `17`/`23` evaluation framework scores a chain that never produces genuinely non-deterministic cognition.

The whole point of the `21 -> 22 -> 23 -> 24` waves was to build the measurement and continuity scaffolding so that real cognition could land and be evaluated. Requirement `25` now provides a backend-neutral LLM inference gateway as a narrow capability owner. The missing piece is the first real consumer: a thought path that produces its thought content from a real model while keeping every cognitive decision (sufficiency, continuation, proposal emission) owned by `11`, not by the model and not by the gateway.

The risk to avoid is prompt theater. If the model were allowed to "be" the thought owner, or if the gateway were allowed to interpret model output into runtime state, the architecture would regress to the reply-first trap the philosophy forbids. Because `11` already owns its result contracts and states, the model can fill content without owning judgment, which is exactly the v2 advantage to exploit here.

## 2. Goal

Add an LLM-backed internal-thought path that obtains thought content from the `25` inference gateway through a neutral request, keeps the sufficiency, continuation, memory-handoff, and proposal-emission decisions owned by the `11` owner, binds the thought consumer to a named LLM profile at composition time as a fail-fast critical dependency, and fails fast on inference failure rather than silently falling back to deterministic synthesis, while preserving the existing deterministic path for tests and changing no `11` result contract.

## 3. Functional Requirements

### 3.1 Owner boundary
1. The LLM-backed path must be a new `InternalThoughtPath` implementation owned by the `11` internal-thought package, alongside the existing `FirstVersionInternalThoughtPath`.
2. The model must supply thought content only. The `11` owner must remain the sole owner of sufficiency level, continuation decision, recall intent, memory handoff, action proposal emission, and self-revision proposal emission.
3. The LLM-backed path must obtain completions only through the `25` `LlmGateway` API using a neutral `LlmRequest`. It must not construct a vendor client and must not embed gateway internals.
4. Adapting the `11` request and the prompt-contract summary into `LlmMessage` values is owned by this path (the consumer), so the gateway stays ignorant of cognitive structure.

### 3.2 Inference-driven thought content
1. When invoked on a fired path, the LLM-backed path must build a neutral inference request from the fired gate result, the retrieval thought window, the continuation state, and the prompt-contract summary, then call the gateway and use the returned completion text as the basis for `ThoughtContent.content`.
2. The produced `ThoughtContent` must set `llm_used=True` and `fallback_used=False`, and must record a `source_path` value that identifies the LLM-backed path distinctly from the deterministic path.
3. The path must preserve all existing `11` request-validation invariants (gate fired, request preserves gate-result id and retrieval-bundle id, continuation-active alignment) before any inference call, so an invalid cycle fails before spending an inference call.

### 3.3 Owner-retained judgment
1. Sufficiency level, continuation-requested, continuation reason, recall intent, continuation pressure delta, memory handoff, action proposal, and self-revision proposal must be decided by owner-held first-version policy in `11`, using the model output as input evidence rather than as the authoritative decision.
2. The owner judgment must remain deterministic given a fixed completion text, so that with a deterministic fake gateway the whole thought cycle is reproducible.
3. The path must continue to honor the existing result-contract constraints: a non-`completed` status must not publish `ThoughtContent` or downstream proposals, and a published memory handoff must preserve the thought id.

### 3.4 Composition binding and fail-fast
1. Composition must bind the internal-thought consumer to a named LLM profile and inject a gateway plus that profile name into the LLM-backed path, replacing the deterministic path in the default assembled runtime.
2. Composition must register the bound thought profile as an LLM critical dependency through the `25` readiness plumbing, so startup fails fast when the bound profile is not statically ready.
3. There must be no automatic fallback to `FirstVersionInternalThoughtPath` when the gateway is unavailable or inference fails. The deterministic path remains available only for explicit test assembly, never as a hidden runtime degradation.

### 3.5 Inference failure semantics
1. If the gateway raises during a thought cycle, the LLM-backed path must surface an explicit hard-stop error and must not fabricate thought content or substitute deterministic synthesis.
2. If the completion is empty or unusable for content, the path must publish an explicit non-`completed` execution status (no fabricated `ThoughtContent`), consistent with the existing thought execution-status taxonomy, rather than inventing content.
3. The path must never set `fallback_used=True` to mask an inference failure; the first version has no fallback.

## 4. Non-Functional Requirements

1. Performance: the path issues at most one synchronous inference call per fired thought cycle in the first version; no internal retry loop and no extra calls.
2. Reliability: with a deterministic fake gateway, the thought cycle is fully reproducible; the only non-deterministic boundary is the real provider, which tests do not invoke.
3. Observability and logging: the path must not introduce a second logging mechanism and must not use `logging` or `print`. The kernel `21` seam still observes the internal-thought stage; LLM facts arrive through the `25` `LlmCompletion` contract.
4. Compatibility and migration: the change is additive at the contract level. No `11` result contract field changes. The deterministic path remains for tests, and a non-LLM test assembly remains possible.

## 5. Code Behavior Constraints

1. The LLM-backed path lives in `helios_v2.internal_thought` and depends on `helios_v2.llm` only through the gateway API and neutral contracts.
2. The path must not interpret completion text inside the gateway, must not move sufficiency/continuation/proposal ownership into the gateway or composition, and must not encode a fixed reply path.
3. Inference failure, empty completion, and invalid request must produce explicit errors or explicit non-success statuses. No degraded or fallback inference path is allowed.
4. The deterministic path must not be silently swapped in at runtime when inference fails.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/internal_thought/engine.py`
2. `helios_v2/src/helios_v2/internal_thought/__init__.py`
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/tests/test_internal_thought_engine.py`
6. `helios_v2/tests/test_runtime_composition.py`
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. `helios_v2.internal_thought` exposes a documented `LlmBackedInternalThoughtPath` implementing the existing `InternalThoughtPath` protocol, constructed with a `25` gateway and a bound profile name.
2. With a deterministic fake gateway returning fixed completion text, the path publishes a `completed` `ThoughtCycleResult` whose `ThoughtContent` carries `llm_used=True`, `fallback_used=False`, an LLM-distinct `source_path`, and content derived from the completion, while sufficiency, continuation, and proposal decisions are produced by owner policy and are reproducible.
3. When the fake gateway raises, the path raises an explicit hard-stop error and publishes no fabricated content; when the completion is empty, the path publishes an explicit non-`completed` status with no `ThoughtContent`.
4. The default assembled runtime binds the thought consumer to a named LLM profile, injects the gateway-backed path, and registers the bound profile as a critical dependency so startup fails fast when the profile is not statically ready; the deterministic path is used only in explicit test assembly.
5. Existing internal-thought validation invariants (gate fired, preserved provenance ids, continuation alignment, result-contract constraints) still hold on the LLM-backed path.
6. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement lands the first real cognition consumer with owner-retained judgment. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Owner-policy deepening that uses richer structured model output (for example a JSON thought envelope) to inform sufficiency and proposal judgment, still owned by `11`.
2. LLM-backed paths for other owners (appraisal-adjacent evaluation, identity governance, prompt-adjacent shaping), each binding their own profile.
3. Replacing remaining deterministic shim bridges (`03-10`) with real signals once the thought path proves the consumption pattern.
4. Evaluation upgrades that score genuinely non-deterministic thought content against consequence-binding and long-horizon continuity.

None of these may be smuggled into this slice. This requirement does not change any `11` result contract, does not move judgment ownership to the model, and does not introduce any external transport or channel execution.
