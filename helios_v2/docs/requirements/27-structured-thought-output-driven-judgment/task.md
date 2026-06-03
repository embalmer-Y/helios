# Requirement 27 - Structured thought output driving owner judgment task plan

## 1. Title

Requirement 27 - Structured thought output driving owner judgment

## 2. Task Breakdown

1. Add the owner-private `StructuredThoughtEvidence` structure and a `_parse_structured_thought` validator (JSON-object parse, bounded/typed field validation, clamped sufficiency) in `internal_thought/engine.py`.
2. Extend `_derive_thought_judgment` with an optional `evidence` parameter and the deterministic evidence-informed rule (bounded sufficiency blend with `model_signal_weight`; model-driven continuation with runtime-carry and low-context floors; action proposal gated by no-continue AND model action intent; self-revision gated by model intent AND existing autobiographical constraint). Keep `evidence=None` behavior identical to today.
3. Update `LlmBackedInternalThoughtPath.run` to request `json_object` output, instruct the schema in the system message, parse+validate into evidence, build `ThoughtContent` from the evidence thought text, and call the evidence-informed judgment; map validation failure and empty content to explicit `insufficient_generation`.
4. Add the `model_signal_weight` owner constant.
5. Add a `deterministic_thought` assembly parameter to `assemble_runtime` that wires the deterministic path and omits the LLM critical dependency and gateway construction when set.
6. Add `--deterministic` to `scripts/run_runtime_driver.py` and document the LLM requirement in its module docstring/help.
7. Extend `tests/test_internal_thought_engine.py` with structured-evidence cases (sufficient+externalize, insufficient+continue, sufficiency-blend assertion, malformed/missing/out-of-range/wrong-typed failures, empty content, gateway failure, continuation-carry override) and keep deterministic-path cases unchanged.
8. Extend `tests/test_runtime_composition.py` with a structured-envelope fake gateway multi-tick case and a `deterministic_thought=True` offline assembly case.
9. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (narrow the behavioral-consequence gap: cognition now influences the thought-owner decision).

## 3. Dependencies

1. `25-llm-inference-gateway` provides the `json_object` response-format capability and the gateway API.
2. `26-llm-backed-internal-thought` provides the `LlmBackedInternalThoughtPath` and the shared judgment helper this slice upgrades.
3. `22-runtime-composition-root-and-runnable-runtime` provides the assembly seam for the deterministic path and the driver.
4. No real network or api key for any test; a deterministic fake gateway returning fixed structured JSON covers all cases.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/internal_thought/engine.py`
2. `helios_v2/src/helios_v2/internal_thought/contracts.py`
3. `helios_v2/src/helios_v2/internal_thought/__init__.py`
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
5. `helios_v2/scripts/run_runtime_driver.py`
6. `helios_v2/tests/test_internal_thought_engine.py`
7. `helios_v2/tests/test_runtime_composition.py`
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
10. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 5. Implementation Order

1. Add `StructuredThoughtEvidence` + `_parse_structured_thought`; unit-test parsing/validation in isolation.
2. Extend `_derive_thought_judgment` with the evidence branch; assert deterministic-path behavior unchanged and evidence-informed behavior under fixed evidence.
3. Update `LlmBackedInternalThoughtPath.run` to JSON request + parse; add the engine tests with a structured fake gateway.
4. Add the `deterministic_thought` assembly seam and the driver `--deterministic` flag.
5. Extend composition tests for the structured envelope and the deterministic offline assembly.
6. Update boundary, grounding, and index docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_internal_thought_engine.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_runtime_dependencies.py -q`
5. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
6. `pytest helios_v2/tests -q`
7. Optional real check (consumes tokens): `python helios_v2/scripts/run_llm_smoke.py --ticks 3` and `python helios_v2/scripts/run_runtime_driver.py --deterministic --ticks 3`

## 7. Completion Criteria

1. The LLM-backed path requests and parses a structured thought envelope into a bounded, typed owner-private evidence structure.
2. The owner's `sufficiency_level` and `continuation_requested` are demonstrably a deterministic function of the model's structured signals plus retrieval/continuation context; changing only the structured output changes the owner decision.
3. A "sufficient + externalize" envelope externalizes and an "insufficient + continue" envelope continues/defers under identical retrieval context, with no `11` contract change.
4. Malformed/missing/out-of-range/wrong-typed structured output yields explicit `insufficient_generation`; gateway failure stays an `LlmError` hard stop; empty content stays non-`completed`.
5. The deterministic path behavior and its tests are unchanged; `assemble_runtime(deterministic_thought=True)` runs offline without the LLM dependency; the driver documents the LLM requirement and offers `--deterministic`.
6. The logging-guard test passes and `pytest helios_v2/tests -q` is green and network-free.

## 8. Completion Snapshot

Status on 2026-06-03: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/internal_thought/engine.py` (`StructuredThoughtEvidence`, `StructuredThoughtParseError`, `_parse_structured_thought`, `_MODEL_SIGNAL_WEIGHT=0.6`, evidence-informed `_derive_thought_judgment`, `LlmBackedInternalThoughtPath` now requests `json_object` and parses the envelope)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (`assemble_runtime(deterministic_thought=...)` explicit offline seam, omits the LLM critical dependency when set)
3. `helios_v2/scripts/run_runtime_driver.py` (`--deterministic` flag, documents the default LLM requirement)
4. `helios_v2/tests/test_internal_thought_engine.py`, `helios_v2/tests/test_runtime_composition.py` (R27 structured-evidence cases; R26 fakes updated to emit JSON envelopes)
5. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

Validated outcomes:

1. `pytest helios_v2/tests/test_internal_thought_engine.py -q` -> 22 passed
2. `pytest helios_v2/tests -q` -> 321 passed, network-free

Implementation notes:

1. The model supplies a structured envelope (thought text + sufficiency + continue/action/self-revision intent). The `11` owner parses and bounds it into `StructuredThoughtEvidence`, then maps it into the final judgment: sufficiency is a bounded blend (`0.6*model + 0.4*retrieval`), continuation follows model intent under owner floors (runtime-carried continuation and a low-context floor the model cannot override), an action proposal needs no-continue AND model action intent, and self-revision needs model intent AND the existing autobiographical constraint.
2. Malformed/missing/out-of-range/wrong-typed envelopes and empty thought text yield an explicit `insufficient_generation` result; gateway failure stays an `LlmError` hard stop. No retrieval-only fallback, no fabricated judgment.
3. The deterministic path (`evidence=None`) reproduces the prior behavior verbatim, so its tests are unchanged.

## 9. Scope Boundary Deferred to wave_C (R28)

Implementation surfaced that a model "continue" or "no action" decision produces a tick with no normalized proposal, which the current `13`/`15`/`18` chain does not tolerate (planner owner requires a normalized proposal; autonomy requires non-empty planner and writeback provenance). Closing the internal-only tick through the chain requires cross-owner contract changes and is the defined opening task of wave_C, tracked as requirement `28`. `27` is therefore complete at the `11` owner level (cognition-driven judgment proven by engine tests) plus the externalizing path end to end in the assembled runtime; the full continue/no-action chain closure is owned by `28`.
