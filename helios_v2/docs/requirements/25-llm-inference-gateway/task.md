# Requirement 25 - LLM inference gateway task plan

## 1. Title

Requirement 25 - LLM inference gateway

## 2. Task Breakdown

1. Add the immutable neutral contracts to `llm/contracts.py`: `LlmMessage`, `LlmRequest`, `LlmUsage`, `LlmCompletion`, `LlmProfile`, `LlmProfileReadiness`, `LlmReadinessReport`, the `LlmProvider` protocol, the `LlmGatewayAPI` protocol, and `LlmError`.
2. Implement `LlmProfileRegistry` (non-empty unique profiles, `resolve`, `names`) in `llm/engine.py`.
3. Implement `LlmGateway` in `llm/engine.py`: `complete`, `check_static_readiness`, `probe_live_readiness`, with an injectable `env` mapping defaulting to `os.environ`.
4. Implement `OpenAICompatibleProvider` in `llm/engine.py` with a lazy `openai` SDK import inside `complete`, translating transport/SDK errors into `LlmError`.
5. Export the public surface from `llm/__init__.py`.
6. Add contract tests in `tests/test_llm_contracts.py`.
7. Add engine tests in `tests/test_llm_engine.py` using a deterministic fake provider and an injected env mapping (network-free).
8. Extend `composition/dependencies.py` with the `llm_profiles_ready` capability, a `LlmReadinessDependencyProvider` delegating to `gateway.check_static_readiness`, and a helper to extend the default critical-dependency specs when LLM consumers are bound.
9. Add composition-level dependency-gate tests covering ready and not-ready bound profiles (startup fail-fast).
10. Update `docs/requirements/index.md` (new R25 row, maturity) and `docs/ARCHITECTURE_BOUNDARIES.md` (new capability-owner snapshot entry for `helios_v2.llm`).

## 3. Dependencies

1. `01-runtime-kernel` provides the startup dependency gate (`validate_critical_dependencies`, `RuntimeStartupError`).
2. `22-runtime-composition-root-and-runnable-runtime` provides the composition dependency-spec/provider surface the readiness check plugs into.
3. No dependency on a real network or a real api key for any test; the deterministic fake provider and injected env mapping cover all tests.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/llm/__init__.py`
2. `helios_v2/src/helios_v2/llm/contracts.py`
3. `helios_v2/src/helios_v2/llm/engine.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/tests/test_llm_contracts.py`
6. `helios_v2/tests/test_llm_engine.py`
7. `helios_v2/tests/test_runtime_composition.py` (extend, or a focused dependency test)
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 5. Implementation Order

1. Land the neutral contracts and protocols in `llm/contracts.py`.
2. Implement the registry and gateway in `llm/engine.py`; add the first-version provider with lazy SDK import.
3. Export from `llm/__init__.py`; add contract and engine tests; validate the owner in isolation.
4. Add the composition dependency plumbing and the readiness-gate tests.
5. Update boundary and index docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_llm_contracts.py helios_v2/tests/test_llm_engine.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_runtime_dependencies.py -q`
5. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
6. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `helios_v2.llm` exposes documented neutral contracts, an `LlmProvider` protocol, a profile registry, the `LlmGateway` owner, the first-version `OpenAICompatibleProvider`, and `LlmError`.
2. The gateway returns a completion preserving request id and resolved profile/model with a deterministic fake provider; unknown profile, empty messages, missing api key, and provider failure all raise `LlmError`.
3. Static readiness is deterministic and network-free; the composition dependency gate fails startup fast when a bound profile is not statically ready and passes when it is.
4. The live readiness probe is opt-in, runs a real completion only when explicitly invoked, and reports static vs live readiness distinctly.
5. The logging-guard test passes and `pytest helios_v2/tests -q` is green and network-free.

## 8. Completion Snapshot

Status on 2026-06-03: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/llm/contracts.py` (`LlmMessage`, `LlmRequest`, `LlmUsage`, `LlmCompletion`, `LlmProfile`, `LlmProfileReadiness`, `LlmReadinessReport`, `ProviderCompletion`, `LlmProvider`, `LlmGatewayAPI`, `LlmError`)
2. `helios_v2/src/helios_v2/llm/engine.py` (`LlmProfileRegistry`, `LlmGateway`, `OpenAICompatibleProvider` with lazy SDK import)
3. `helios_v2/src/helios_v2/llm/__init__.py` (public exports)
4. `helios_v2/src/helios_v2/composition/dependencies.py` (`LLM_PROFILES_READY`, `llm_critical_dependency_spec`, `LlmReadinessDependencyProvider`)
5. `helios_v2/src/helios_v2/composition/__init__.py` (new exports)
6. `helios_v2/tests/test_llm_contracts.py`, `helios_v2/tests/test_llm_engine.py`, `helios_v2/tests/test_llm_dependency_gate.py`
7. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

Validated outcomes:

1. `pytest helios_v2/tests/test_llm_contracts.py helios_v2/tests/test_llm_engine.py -q` -> 27 passed
2. `pytest helios_v2/tests -q` -> 296 passed (after R25), 306 passed (after R26), network-free

Implementation notes:

1. The gateway keys only on `target_profile`; profile-to-consumer binding is a composition concern. The gateway never interprets completion text.
2. Static readiness is deterministic and network-free (profile registered + api-key env var non-empty) and is wired into the startup gate through `LlmReadinessDependencyProvider` + the `llm_profiles_ready` critical dependency. The live probe is opt-in and the only method that issues a real call.
3. `OpenAICompatibleProvider` imports the `openai` SDK lazily inside `complete`, so importing `helios_v2.llm` never requires the SDK; tests inject a deterministic fake provider and an injected env mapping.
