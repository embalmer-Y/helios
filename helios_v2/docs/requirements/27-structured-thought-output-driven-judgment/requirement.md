# Requirement 27 - Structured thought output driving owner judgment

## 1. Background and Problem

Requirement `26` landed the first real cognition consumer: `LlmBackedInternalThoughtPath` sources thought content from the `25` gateway. A real 3-to-4 tick smoke run confirmed the model produces genuine, varied thought content end to end.

However, the smoke run exposed a concrete and important gap. The model's content has almost no causal influence on the owner's decisions. The owner judgment helper `_derive_thought_judgment` computes sufficiency, continuation, recall intent, memory handoff, action proposal, and self-revision proposal purely from retrieval hit counts and the continuation flag. It never reads what the model actually said. In the smoke run the model repeatedly stated "no action required" and "maintain idle", yet the owner still set `sufficiency=0.8`, `continuation_requested=False`, emitted an external action proposal, and the downstream chain reported `consequence=continuity_written` and `disposition=externalize` every tick.

This is the next pseudo-completion risk after prompt theater: the system now has real cognition, but that cognition does not change behavior. Internal-state richness still outruns behavioral consequence, which is exactly the final-goal weakness the philosophy and the grounding gaps warn about. Closing it requires the model's reasoning to become structured evidence that the owner consumes when forming its judgment, while keeping the owner as the sole authority over the final decision.

A second, smaller debt also surfaced: the existing thin driver `scripts/run_runtime_driver.py` now assembles the default LLM-backed runtime, so a real run requires a live api key and otherwise fails fast at startup, but the driver does not document this and offers no deterministic assembly path for offline use.

## 2. Goal

Make the internal-thought owner consume a structured thought output from the model as formal evidence when forming its fired-cycle judgment, so that the model's reasoning measurably influences sufficiency, continuation, and proposal decisions, while the `11` owner remains the sole authority that validates, bounds, and maps that evidence into the final decision, fails fast on malformed structured output rather than fabricating judgment, and changes no `11` result contract; and resolve the driver debt by documenting the LLM requirement and providing an explicit deterministic assembly path for offline runs.

## 3. Functional Requirements

### 3.1 Structured thought output as model-supplied evidence
1. The LLM-backed path must request a structured thought output from the model using the `25` gateway's `json_object` response format, carrying at least: a free-text thought content field, a self-assessed sufficiency signal, a continuation intent, an optional action-proposal intent, and an optional self-revision intent.
2. The structured output must be parsed and validated by the `11` owner into a first-class owner-private structure before it informs any decision. It is model-supplied evidence, never the final decision.
3. The structured output fields must be bounded and typed by the owner: out-of-range, missing-required, or wrong-typed fields are a validation failure, not silently coerced.

### 3.2 Owner-retained judgment, now evidence-informed
1. The owner judgment must combine the model's structured evidence with the existing retrieval/continuation context. The owner remains the sole authority that produces the final `sufficiency_level`, `continuation_requested`, `continuation_reason`, `recall_intent`, `memory_handoff`, `action_proposal`, and `self_revision_proposal`.
2. The model's sufficiency signal must measurably influence the final `sufficiency_level` under an explicit, bounded, deterministic owner rule (for example a bounded blend of model signal and retrieval-derived signal), rather than being ignored.
3. The model's continuation intent must be able to change the final `continuation_requested` outcome relative to the retrieval-only baseline, under an explicit owner rule, so a model that judges the cycle unfinished can keep the thought open and a model that judges it complete can let it close.
4. An action proposal must only be emitted when both the owner's continuation decision permits it and the model expressed an action intent; the owner still owns the proposal's scope, behavior, channels, intensity bounds, and governance hints. The model's expressed intent does not grant execution authority.
5. A self-revision proposal must only be emitted when the model expressed a self-revision intent and the owner's existing constraints permit it; the model's expressed intent does not bypass governance ownership.
6. The owner judgment must remain deterministic given a fixed structured output and fixed retrieval/continuation context, so tests with a deterministic fake gateway are fully reproducible.

### 3.3 Falsifiable behavioral influence
1. With identical retrieval/continuation context, two different model structured outputs (one judging the cycle sufficient and externalizable, one judging it insufficient and wanting to continue) must produce different owner decisions (for example externalize vs continue/defer), demonstrating that cognition now influences behavior.
2. The influence must be observable through existing result and trace fields and through the existing `17`/`23` consequence-binding and `24` long-horizon diagnostics, without adding a new logging mechanism.

### 3.4 Failure semantics
1. If the model returns output that is not valid JSON, is missing a required field, or carries an out-of-range or wrong-typed field, the path must publish an explicit non-`completed` execution status (consistent with the existing taxonomy, for example `insufficient_generation`) with no fabricated `ThoughtContent` and no proposals. It must not silently fall back to retrieval-only judgment.
2. A gateway/provider failure remains an explicit hard stop (`LlmError`), as in `26`. There is no deterministic-synthesis fallback.
3. An empty thought content field remains an explicit non-`completed` result, as in `26`.

### 3.5 Driver debt resolution
1. The thin driver `scripts/run_runtime_driver.py` must document that the default assembled runtime is LLM-backed and that a real run requires a statically-ready bound LLM profile, so startup fails fast without one.
2. The driver must offer an explicit deterministic assembly path (for example a `--deterministic` flag) that assembles the runtime with the deterministic thought path and without the LLM critical dependency, for offline runs and quick checks. The deterministic path must be explicit and opt-in; it must never be a hidden fallback when the LLM is unavailable.

## 4. Non-Functional Requirements

1. Performance: the path still issues at most one synchronous inference call per fired thought cycle; structured output adds parsing only, no extra calls.
2. Reliability: with a deterministic fake gateway returning fixed structured output, the whole thought cycle and the resulting owner decision are reproducible; the only non-deterministic boundary remains the real provider.
3. Observability and logging: no second logging mechanism; no `logging` or `print` under `helios_v2/src`. Structured-output facts travel through the owner's result and trace fields, not through the log channel.
4. Compatibility and migration: no `11` result contract field changes. The deterministic path remains valid. Existing tests must remain green, and the test suite must remain network-free.

## 5. Code Behavior Constraints

1. Structured-output parsing, validation, and the evidence-to-judgment mapping must live in the `11` internal-thought owner. The `25` gateway must not parse or interpret the structured output.
2. The model must never become the owner of the final decision. The owner must validate and bound every model-supplied field before use, and must own the mapping rule.
3. Malformed or out-of-range structured output must produce an explicit non-success status. No silent coercion, no retrieval-only fallback, no fabricated judgment.
4. The deterministic driver path must be explicit and opt-in, never a hidden fallback substituted when the LLM is unavailable.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

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

## 7. Acceptance Criteria

1. The LLM-backed path requests `json_object` output and parses it into a documented owner-private structured-thought-evidence structure with bounded, typed validation.
2. The owner's final `sufficiency_level` and `continuation_requested` are demonstrably a function of the model's structured signals plus retrieval/continuation context, under explicit deterministic rules, verified by tests where changing only the structured output changes the owner decision.
3. With identical retrieval/continuation context, a "sufficient + externalize" structured output yields an externalizing decision while an "insufficient + continue" structured output yields a continuing/deferring decision, with no `11` contract change.
4. Malformed, missing-required, or out-of-range structured output yields an explicit non-`completed` status with no fabricated content or proposals; a gateway failure remains an `LlmError` hard stop; an empty content field remains a non-`completed` result.
5. The deterministic path still produces its existing reproducible judgment, and its tests remain green.
6. The driver documents the LLM requirement and provides an explicit deterministic assembly path that runs offline without the LLM critical dependency.
7. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement makes real cognition behaviorally consequential at the thought owner. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Richer structured schemas (for example explicit recall-intent targets or memory-ref selection) once downstream owners can consume them.
2. wave_C execution closure (`13`, `16`): now that the model can decide to externalize, defer, or continue, the planner/outward path can close proactive provenance into bounded outward consequence.
3. wave_B long-horizon adjacency (`14`, `15`, `24`): now that the model can decide to defer, deferred-continuity records and continuity threads can carry real motive content rather than only deterministic recurrence.
4. LLM-backed judgment for other owners, each via its own requirement and profile binding.

None of these may be smuggled into this slice. This requirement does not change any `11` result contract, does not move final judgment ownership to the model, does not introduce external transport or channel execution, and does not grant the gateway any interpretation authority.

## 9. Scope Boundary Discovered During Implementation (Internal-Only Tick Closure)

Implementing this requirement surfaced a latent defect that is explicitly recorded here and deferred to wave_C rather than absorbed into `27`.

Before `27`, the deterministic retrieval shim always produced `continuation_requested=False`, so the thought owner always emitted an action proposal, and every tick flowed action -> planner -> writeback. `27` makes the model's "continue" and "no action" decisions reachable for the first time. Such a tick produces no normalized proposal to route, which the current downstream chain does not tolerate:

1. `PlannerBridgeRuntimeStage` invokes the planner owner unconditionally and the planner owner hard-requires a normalized proposal, so a no-proposal tick raises `PlannerBridgeError`.
2. The autonomy owner requires a non-empty `source_planner_bridge_result_id` and a non-empty `source_writeback_result_ids`, but a continue/no-action tick that also proposes no self-revision produces zero writeback results.

Closing this requires changes to the `13` planner-bridge, `15` writeback, and `18` autonomy owner contracts (for example an explicit planner no-op/internal-only outcome, an internal-continuity writeback, and autonomy tolerance for an internal-only tick). That is cross-owner execution-closure work and is the defined opening task of wave_C, tracked as requirement `28`.

Consequently, `27` proves the cognition-driven judgment at the `11` owner level (engine tests cover externalize, continue, blend, and all failure modes) and, in the assembled runtime, validates the externalizing envelope end to end. The full continue/no-action path through the planner and writeback chain is intentionally out of scope for `27` and owned by `28`.
