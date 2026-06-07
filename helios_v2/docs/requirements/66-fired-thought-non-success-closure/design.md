# Design 66 - Fired thought non-success closure

## 1. Title

Fired thought non-success closure

## 2. Design Overview

This slice closes an activated thought tick whose `11` owner result is non-`completed` by handling the closure entirely in runtime orchestration and owner-neutral bridges.

The design has three parts:

1. `12` action externalization short-circuits before invoking the owner when `execution_status != "completed"`, but still publishes a provenance-preserving `no_externalization` marker result.
2. `14` identity governance short-circuits before invoking the owner on the same condition and emits an explicit inactive marker rather than a fabricated governance result.
3. The autonomy/evaluation bridges are widened just enough to consume that explicit governance absence on an otherwise activated thought path.

No owner contract changes. The non-success thought result remains owned by `11`; the closure mechanics remain owned by runtime orchestration.

## 3. Current State and Gap

Current assembled behavior:

1. `11` can validly publish `insufficient_generation` with `thought=None`, `action_proposal=None`, and `self_revision_proposal=None`.
2. `12` runtime stage always calls `build_request_op` and `externalize_action_proposal`, which raises because `12` requires a completed thought result.
3. If `12` were bypassed, `14` runtime stage would still raise because identity governance also requires a completed thought result.
4. The downstream `13 -> 15 -> 18 -> 17` internal-only tail already exists, but the runtime never reaches it on this path.

The gap is therefore orchestration-only: the runtime has no explicit representation for an activated but non-completed thought cycle.

## 4. Target Architecture

Target flow for an activated non-completed thought cycle:

1. `11` publishes its non-success result unchanged.
2. `12` runtime stage builds the owner-neutral externalization request but does not call the `12` owner. It synthesizes a `ThoughtExternalizationResult(status="no_externalization")` anchored to the request id.
3. `13` planner runtime stage sees a non-normalized externalization result and reuses the existing `evaluate_internal_only` path, producing `no_actionable_proposal`.
4. `14` runtime stage emits an explicit inactive marker result for this tick instead of invoking governance.
5. `15` writeback still records the planner's internal-only continuity outcome; no governance writeback is produced.
6. `18` autonomy request construction uses the real `11`, `13`, and `15` artifacts plus the governance inactive marker id.
7. `17` evaluation evidence bundle records thought evidence, action no-externalization evidence, planner/writeback evidence, and governance inactive evidence, allowing the existing consequence classifier to conclude `internal_only_decision`.

## 5. Data Structures

No public contract additions are required.

Existing contracts reused:

1. `ThoughtExternalizationRequest`
2. `ThoughtExternalizationResult(status="no_externalization")`
3. `IdentityGovernanceStageResult` with `activated=False` and a runtime-owned inactive marker id
4. Existing evaluation evidence maps with additive `activated=False` governance evidence on this path

## 6. Module Changes

1. `runtime/stages.py`
Adds one non-completed branch to `ActionExternalizationRuntimeStage.run` that synthesizes a no-externalization marker result and skips `12` owner invocation.

2. `runtime/stages.py`
Adds one non-completed branch to `IdentityGovernanceRuntimeStage.run` that returns an explicit inactive marker result and skips `14` owner invocation.

3. `composition/bridges.py`
Updates `FirstVersionAutonomyRequestBridge.build_request` so an activated thought path with inactive governance uses the stage's inactive marker id instead of reading a missing owner result.

4. `runtime/stages.py`
Updates autonomy-stage provenance checks so they accept either a real governance result id or the explicit governance inactive marker, depending on stage activation.

5. `composition/bridges.py`
Updates evaluation evidence construction so governance evidence on this path is an explicit inactive marker instead of reading a missing owner result.

6. `tests/test_runtime_composition.py`
Adds a focused regression proving malformed structured output closes the full runtime rather than crashing.

## 7. Migration Plan

1. Land the runtime-stage short-circuit for `12`.
2. Land the runtime-stage short-circuit for `14`.
3. Update the autonomy/evaluation bridges to tolerate governance absence on an activated thought path.
4. Add the focused regression test.
5. Run targeted tests, then rerun the real LLM smoke in the required environment.

No data migration, persistence migration, or contract-version bump is required.

## 8. Failure Modes and Constraints

1. If the `11` stage is activated but its result object is absent, runtime must still fail fast; this requirement covers only valid non-completed thought results.
2. If a completed thought result is present, `12` and `14` must continue to call their owners exactly as before.
3. The runtime must not synthesize a governance result, proposal, rejection, or equivalent evidence for the non-completed path.
4. The autonomy bridge may use only explicit absence markers, never fabricated owner result ids that pretend governance actually ran.

## 9. Observability and Logging

Observability remains the existing stage-result surface plus recorder events. The new path is inspectable through:

1. `internal_thought_loop_owner.result.execution_status`
2. `action_proposal_externalization_contract.result.status == "no_externalization"`
3. `identity_governance_self_revision_integration.activated == False`
4. Planner/writeback/evaluation outcomes already published today

No new log channel and no new runtime prints.

## 10. Validation Strategy

1. Add a network-free regression test using a fake LLM provider that returns malformed structured output (`<think>...</think>{...}`) so `11` yields `insufficient_generation`.
2. Assert the full runtime tick completes.
3. Assert `12` publishes `no_externalization`, `14` stays inactive, planner publishes `no_actionable_proposal`, writeback publishes `written_internal_only`, and evaluation publishes `internal_only_decision`.
4. Re-run the real LLM smoke script in `D:\Compiler\anaconda3\envs\helios` and inspect the saved log/json output for the next exposed issue, if any.