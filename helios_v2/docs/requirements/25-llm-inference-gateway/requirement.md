# Requirement 25 - LLM inference gateway

## 1. Background and Problem

The entire `01-18` cognition chain currently runs on deterministic first-version shim behavior. The internal-thought owner (`11`) synthesizes thought content by string assembly with `llm_used=False`; appraisal, neuromodulation, feeling, gating, retrieval, and governance are all driven by injected deterministic bridges. No part of the runtime can call a real language model.

A standalone probe script (`helios_v2/scripts/run_llm_prompt_probe.py`) proves the OpenAI-compatible call shape works, but it does not participate in the runtime, owns no contracts, and has no fail-fast integration. There is no shipped, owner-bounded way for a runtime owner to obtain a real completion.

Multiple owners will eventually need real inference, not just `11`. Appraisal-grade evaluation (`17`/`23` adjacency), identity governance (`14`), and prompt-adjacent work (`16`) are all plausible future consumers, and they will reasonably want different models, endpoints, or parameters. If each owner constructs its own client, the project gets scattered configuration, no single fail-fast point, no per-consumer model selection, and a violation of the one-concept-one-owner rule.

This matters for the final-goal standard. The philosophy explicitly warns that an LLM bolted onto a reply-first path becomes prompt theater. Helios v2 avoids that trap only because its cognitive owners, states, and contracts already exist independently. To exploit that, real inference must enter the runtime as a narrow capability provider that owns no cognition, so that cognitive owners keep owning the interpretation of model output.

## 2. Goal

Introduce a single backend-neutral LLM inference gateway owner that turns a neutral inference request into a formal completion result through a named profile, supports a profile registry so different consumers can bind different models and endpoints, fails fast when a bound profile is not statically ready, and exposes an explicit opt-in live readiness probe, while owning no prompt assembly, no cognitive interpretation of output, and no cross-owner state transport.

## 3. Functional Requirements

### 3.1 Owner boundary
1. The LLM inference gateway must be a dedicated capability owner in a new package `helios_v2.llm`.
2. The gateway must own only: the neutral inference request/completion contracts, the named profile registry, provider dispatch, and readiness reporting.
3. The gateway must not own prompt assembly, must not interpret completion text as any cognitive decision, must not know which cognitive stage it serves, and must not transport one owner's decision to another owner.
4. The gateway must be backend-neutral: the concrete provider is injected behind a provider protocol, so the gateway is not bound to any single vendor SDK.

### 3.2 Inference request and completion contracts
1. The gateway must accept an immutable `LlmRequest` carrying a request id, a target profile name, an ordered tuple of role-tagged messages, an explicit response format (`text` or `json_object`), and an optional provenance metadata mapping.
2. The gateway must return an immutable `LlmCompletion` carrying the source request id, the resolved profile name and model, the output text, the finish reason, optional token usage, and measured latency.
3. The request and completion must be formal owner contracts. Completion facts (usage, latency, model) must travel through this contract, never through the log channel.
4. Message roles must use a fixed taxonomy (`system`, `user`, `assistant`). An empty message tuple or an empty profile name must fail fast.

### 3.3 Profile registry and consumer binding
1. The gateway must own a registry mapping a stable profile name to an immutable `LlmProfile` declaring at least: model, api-key environment variable name, base URL, temperature, max tokens, timeout, and default response format.
2. The gateway must resolve the target profile by the request's profile name and must fail fast when the profile name is unknown.
3. Binding a consuming owner to a profile name is a composition (assembly) concern, not a gateway concern. The gateway must remain ignorant of consumer identity and must key only on profile name.
4. The registry must support more than one profile so different consumers can bind different models or endpoints.

### 3.4 Static readiness and startup fail-fast
1. The gateway must expose a static readiness check that, for a given set of profile names, reports whether each profile exists in the registry and whether its declared api-key environment variable resolves to a non-empty value. This check must perform no network call and must be deterministic.
2. The runtime startup dependency gate must treat the bound LLM profiles' static readiness as a critical dependency. When any bound profile is not statically ready, startup must fail fast through the existing dependency gate with the missing capability explicit.
3. There must be no degraded or shimmed inference path when a profile is not ready. The system must not silently fall back to deterministic synthesis when the gateway is unavailable.

### 3.5 Live readiness probe
1. The gateway must expose an explicit live readiness probe that issues a minimal real completion per requested profile and reports per-profile live success or failure.
2. The live probe must be opt-in and must not be part of the mandatory startup gate, so that ordinary startup and the full test suite remain deterministic and network-free.
3. The live probe result must be an explicit structured report distinguishing static readiness from live readiness, including the case where live readiness was not checked.

### 3.6 Invocation behavior
1. The gateway must invoke inference synchronously and return one completion per request in the first version. Asynchronous or concurrent invocation is out of scope.
2. Provider or transport failure during invocation must raise an explicit `LlmError` hard-stop. The first version must not retry silently and must not substitute a fabricated completion.
3. When a request declares `json_object` response format, the gateway must request structured output from the provider; validating that the returned text parses or conforms to a schema is the consuming owner's responsibility, not the gateway's.

## 4. Non-Functional Requirements

1. Performance: a single synchronous invocation must add only the provider round-trip plus bounded local request shaping; the gateway must not add background work or hidden batching in the first version.
2. Reliability: gateway behavior must be deterministic given a fixed provider. The only non-deterministic boundary is the injected provider, which tests must replace with a deterministic double.
3. Observability and logging: the gateway must not introduce a second logging mechanism and must not use `logging` or `print`. Completion facts travel through the `LlmCompletion` contract; the kernel's existing `21` stage-timing emission continues to observe the consuming stage.
4. Compatibility and migration: the gateway is additive. It introduces a new package and a new critical-dependency capability only for runtimes that bind an LLM consumer. A runtime that binds no LLM consumer must remain assemblable and runnable unchanged.

## 5. Code Behavior Constraints

1. The neutral inference contracts, the profile registry, provider dispatch, and readiness reporting must live in `helios_v2.llm`. No other module may construct a vendor client directly.
2. The gateway must accept its provider through an injected provider protocol. It must not import a concrete vendor SDK at module import time in a way that makes the package unusable without that SDK installed; the concrete provider may import the SDK lazily inside its own call path.
3. The gateway must not assemble prompts, must not parse completion text into cognitive state, and must not hold any cognitive policy.
4. Missing profile, unready profile, empty messages, or provider failure must raise explicit errors. No degraded or fallback inference mode is allowed.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/llm/__init__.py`
2. `helios_v2/src/helios_v2/llm/contracts.py`
3. `helios_v2/src/helios_v2/llm/engine.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/tests/test_llm_contracts.py`
6. `helios_v2/tests/test_llm_engine.py`
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 7. Acceptance Criteria

1. The `helios_v2.llm` package exposes documented immutable `LlmMessage`, `LlmRequest`, `LlmCompletion`, `LlmUsage`, `LlmProfile`, and `LlmReadinessReport` contracts, an `LlmProvider` protocol, an `LlmError`, and an `LlmGateway` owner with a public API.
2. A gateway built with a registered profile and a deterministic fake provider returns an `LlmCompletion` preserving the request id and resolved profile/model, with the fake provider's output text and usage.
3. Invoking with an unknown profile name, empty messages, or a failing provider raises an explicit `LlmError`, with no fabricated completion.
4. The static readiness check reports ready for a profile whose api-key environment variable is set and not-ready otherwise, performs no network call, and is deterministic; the composition dependency gate fails startup fast when a bound profile is not statically ready.
5. The live readiness probe is opt-in, issues a real completion only when explicitly invoked, and produces a structured report distinguishing static from live readiness; it is never invoked by the mandatory startup gate or by the default test suite.
6. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement ships the narrow capability owner only. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Bounded, explicit retry and timeout policy for transient provider failures.
2. Streaming, tool/function calling, and embeddings as separate provider capabilities.
3. Asynchronous or concurrent invocation once the runtime gains a non-blocking tick model.
4. Additional consumers (`14`, `16`, evaluation-adjacent) binding their own profiles.
5. Optional gateway-level cost/usage accounting surfaced as a formal contract rather than a log.

None of these may be smuggled into this slice. This requirement does not introduce any cognitive interpretation of model output and grants the gateway no cognitive authority.
