# Requirement 66 - Fired thought non-success closure

## 1. Background and Problem

The real LLM smoke run exposed a fired-path closure gap that the deterministic test envelope did not surface. On a live tick, the `11` internal-thought owner can legitimately publish a non-`completed` `ThoughtCycleResult` such as `insufficient_generation` when the provider returns malformed structured output. This is an intentional first-class result under `27`: no fabricated `ThoughtContent`, no fabricated proposals, and no retrieval-only fallback.

However, the downstream runtime adapters still assume that an activated thought stage always carries a `completed` result:

1. The `12` action-externalization runtime stage unconditionally calls the owner API, but the owner contract explicitly requires a `completed` `ThoughtCycleResult`.
2. The `14` identity-governance runtime stage also unconditionally calls its owner API, and that owner likewise requires a `completed` `ThoughtCycleResult`.

The result is that a real fired tick with a valid non-success thought outcome aborts at runtime before the existing internal-only closure tail can run. This is not an LLM connectivity failure; it is a runtime closure bug. A continuous runtime must be able to represent "the thought path activated, but the thought owner did not complete this cycle" without crashing, without fabricating action or self-revision results, and without weakening any owner's completed-result contract.

## 2. Goal

Allow an activated `11` thought cycle that publishes a non-`completed` result to close through the assembled runtime as an explicit non-externalizing, non-self-revising outcome, preserving owner contracts and downstream provenance, instead of aborting in the `12` or `14` runtime stages.

## 3. Functional Requirements

### 3.1 Action externalization closure for non-success thought results
1. When the `11` stage is activated but its `ThoughtCycleResult.execution_status` is not `completed`, the runtime must not call the `12` owner APIs that require a completed thought result.
2. The `12` runtime stage must instead publish a provenance-preserving owner-neutral marker result using the existing externalization taxonomy, so the downstream planner can treat the tick as a no-proposal internal-only path.
3. This marker must preserve the source thought-cycle result id through the externalization request contract and must not fabricate a normalized proposal, rejection, or equivalent-evidence payload.

### 3.2 Identity-governance closure for non-success thought results
1. When the `11` stage is activated but its result is non-`completed`, the runtime must not call the `14` owner APIs that require a completed thought result.
2. The `14` runtime stage must publish an explicit inactive/absent marker for that tick rather than fabricating a governance result.
3. Downstream bridges must be able to consume this explicit governance absence without inventing a real `14` owner result id.

### 3.3 Downstream closure continuity
1. The existing `13` planner internal-only path (`no_actionable_proposal`) must remain the closure route for a non-`completed` fired thought tick.
2. The existing `15` internal-only continuity writeback path must still run when the planner publishes `no_actionable_proposal`.
3. The `18` autonomy request bridge and runtime stage must tolerate an explicit governance-absent marker on an otherwise activated thought path.
4. The `17` evaluation evidence bundle must publish the activated thought evidence, the no-externalization action evidence, and an explicit governance-inactive evidence marker so the tick is classified as an internal-only consequence outcome rather than a crash.

### 3.4 No fallback or contract weakening
1. The `11` owner contract remains unchanged: malformed structured LLM output continues to yield an explicit non-`completed` result.
2. The `12` and `14` owner contracts remain unchanged: they still require completed thought results when invoked.
3. The fix must live in runtime orchestration and owner-neutral request/evidence bridges, not by broadening owner input validation to accept incomplete thought results.

## 4. Non-Functional Requirements

1. Determinism: for a fixed non-`completed` thought result, the runtime closure path must produce deterministic stage results and evidence.
2. Reliability: the assembled runtime must complete a tick when the LLM returns malformed structured output that leads to `insufficient_generation`.
3. Observability and logging: no new logging mechanism, no `logging` or `print` under `helios_v2/src`; closure must be visible through formal stage results and existing observability.
4. Compatibility: additive and behavior-preserving for completed thought cycles and existing no-fire/internal-only flows.

## 5. Code Behavior Constraints

1. The runtime must not fabricate a completed `12` or `14` owner outcome for a non-`completed` thought cycle.
2. The action-externalization marker must use the existing `ThoughtExternalizationResult` taxonomy, specifically a no-externalization outcome with empty payload fields.
3. Governance absence must be represented as explicit runtime-stage non-activation on that slice, and downstream bridges must carry an explicit absence marker id rather than a fake owner result.
4. The externalizing path for `execution_status == "completed"` must remain byte-for-byte equivalent in behavior.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/composition/bridges.py`
3. `helios_v2/tests/test_runtime_composition.py`
4. `helios_v2/docs/requirements/index.md`

## 7. Acceptance Criteria

1. An activated `11` stage result with `execution_status="insufficient_generation"` no longer causes `12` or `14` runtime-stage failure.
2. The `12` stage publishes a no-externalization marker result with preserved thought-cycle provenance and no fabricated payloads.
3. The `14` stage publishes an explicit inactive marker for the same tick rather than a fabricated governance result.
4. The assembled runtime completes the full tick, the planner publishes `no_actionable_proposal`, writeback publishes `written_internal_only`, and evaluation classifies the tick as `internal_only_decision`.
5. A focused regression test reproduces the malformed-structured-output path network-free and passes after the change.

## 8. Future Extension Scope

This requirement closes the runtime around non-`completed` fired thought cycles. It does not make provider output more schema-compliant, relax `11`/`12`/`14` owner contracts, or redesign structured-output prompting/parsing. Those remain separate concerns.