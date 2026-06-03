# Requirement 28 - Internal-only tick closure (wave_C opener)

## 1. Background and Problem

Requirement `27` made the model's structured thought output drive the `11` internal-thought owner's judgment. For the first time, the runtime can legitimately decide, on a fired tick, to continue thinking or to conclude without acting. This is a real cognitive outcome: not every cycle of internal thought should produce an outward action.

However, the downstream execution chain was built on the prior shim assumption that every fired tick yields a normalized action proposal. A tick that produces no proposal currently cannot complete:

1. `PlannerBridgeRuntimeStage` invokes the `13` planner-bridge owner unconditionally, and the owner hard-requires a normalized `ThoughtExternalizationResult`. A no-proposal tick raises `PlannerBridgeError`.
2. The `18` autonomy owner's `ProactiveDriveRequest` requires a non-empty `source_planner_bridge_result_id` and a non-empty `source_writeback_result_ids`. A continue/no-action tick that also proposes no self-revision produces zero writeback results, so the request cannot be constructed.

The result is that the default LLM-backed runtime crashes whenever the model decides to keep thinking or to refrain from acting. A continuous brain-inspired runtime must be able to run an internally consequential tick that produces no outward action, and must record that internal-only outcome through formal owner contracts rather than failing. This is the first concrete task of wave_C (execution closure): close the internal-only tick so that "the system chose not to act" is a representable, traceable runtime outcome.

## 2. Goal

Allow a fired tick that produces no externalizable action proposal to complete through the planner-bridge, experience-writeback, autonomy, and evaluation owners as an explicit internal-only outcome, recorded through formal owner contracts, without fabricating an action, without weakening the existing externalizing path, and without granting any owner new outward execution authority.

## 3. Functional Requirements

### 3.1 Planner-bridge internal-only outcome
1. The `13` planner-bridge owner must expose an explicit way to represent a tick with no normalized proposal to route, as a first-class result (for example a `no_actionable_proposal` bridge status), rather than requiring the runtime to skip it informally or raising an error.
2. The internal-only planner result must publish no action decision and no rejection, and must be distinguishable from an accepted, rejected, or failed outcome.
3. The runtime planner-bridge stage must produce this internal-only result when the upstream externalization result is not normalized, and must still produce the normal evaluated result when a proposal is present.

### 3.2 Experience-writeback internal-only continuity
1. The `15` experience-writeback owner must be able to record an internal-only tick (no world change, no self change) as an explicit continuity writeback, so that "a thinking cycle occurred and concluded without outward action" is preserved rather than dropped.
2. The internal-only writeback must carry explicit provenance to the thought-cycle result and the internal-only planner outcome, and must classify itself distinctly from world-changed and self-changed outcomes.

### 3.3 Autonomy tolerance of internal-only ticks
1. The `18` autonomy owner must accept an internal-only tick: it must be able to integrate proactive drive when the planner outcome is internal-only and when the only writeback is the internal-only continuity writeback.
2. The autonomy owner must preserve its existing deferred-continuity, decay/merge/expire, and long-horizon thread semantics. An internal-only tick is a normal input, not a degraded mode.
3. No autonomy provenance requirement may be satisfied by fabricating a planner or writeback id that does not correspond to a real owner outcome.

### 3.4 Evaluation visibility of internal-only ticks
1. The `17`/`23` evaluation owner must classify an internal-only tick as an explicit consequence-binding outcome (for example `internally_activated_only` or a dedicated internal-only label), distinct from blocked, rejected, executed, and continuity-written.
2. The evaluation diagnostic must not report an internal-only tick as a failure or as missing evidence; it is a valid outcome with its own provenance.

### 3.5 No fallback or fabrication
1. An internal-only outcome must never be produced by inventing an action, a channel, or a decision. It is the explicit absence of an action, recorded as such.
2. The externalizing path must remain unchanged: a tick with a normalized proposal must still flow through planner acceptance, execution, and writeback exactly as before.
3. Missing or malformed inputs must continue to fail fast through the existing owner errors; the internal-only path is for the valid no-proposal case only.

## 4. Non-Functional Requirements

1. Determinism: for identical inputs, the internal-only path must produce deterministic owner results, comparable across runs.
2. Reliability: the default LLM-backed runtime must complete a tick for both an externalizing envelope and a continue/no-action envelope, with a deterministic fake gateway, network-free.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. Internal-only outcomes travel through formal owner result contracts and the existing `21` timeline.
4. Compatibility and migration: additive. The externalizing path and existing tests must remain green. New statuses/outcome classes must be additive to the existing taxonomies.

## 5. Code Behavior Constraints

1. The internal-only outcome must be owned by the respective owners (`13` planner status, `15` writeback class, `18` autonomy tolerance, `17` evaluation label). The composition root must remain assembly-only and must not encode the internal-only decision as cognitive policy.
2. Deciding that there is no proposal to route is an orchestration fact derived from the upstream externalization status; mapping it into the planner owner's internal-only result is owned by `13`, not by the runtime adapter inventing a planner decision.
3. No owner may gain outward channel execution authority in this slice. wave_C outward closure (real channel routing of a proposal) remains a later requirement.
4. No `logging`/`print`; the guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/planner_bridge/contracts.py`
2. `helios_v2/src/helios_v2/planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/experience_writeback/contracts.py` (if a new outcome class is needed)
4. `helios_v2/src/helios_v2/experience_writeback/engine.py`
5. `helios_v2/src/helios_v2/autonomy/contracts.py` (provenance tolerance) and/or `helios_v2/src/helios_v2/runtime/stages.py`
6. `helios_v2/src/helios_v2/evaluation/engine.py`
7. `helios_v2/src/helios_v2/runtime/stages.py` (planner and writeback stage adapters)
8. `helios_v2/src/helios_v2/composition/bridges.py` (planner request, writeback request, autonomy request bridges)
9. `helios_v2/tests/test_planner_bridge_*.py`, `helios_v2/tests/test_experience_writeback_*.py`, `helios_v2/tests/test_autonomy_*.py`, `helios_v2/tests/test_evaluation_engine.py`, `helios_v2/tests/test_runtime_composition.py`
10. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. The `13` owner exposes an explicit internal-only (no-actionable-proposal) result distinct from accepted/rejected/failed, with no action decision.
2. The `15` owner records an internal-only continuity writeback with explicit thought-cycle and planner provenance, classified distinctly from world-changed and self-changed.
3. The `18` owner integrates an internal-only tick without fabricated provenance and preserves all existing continuity/thread semantics.
4. The `17`/`23` owner classifies an internal-only tick as an explicit, non-failure consequence outcome with provenance.
5. The default LLM-backed assembled runtime completes a tick for both an externalizing envelope and a continue/no-action envelope, network-free with a deterministic fake gateway.
6. The externalizing path and all existing tests remain green; the logging-guard test passes and `pytest helios_v2/tests -q` is green.

## 8. Future Extension Scope

This requirement closes the internal-only tick. It does not implement outward channel execution of a proposal (real transport), which remains the later wave_C outward-closure requirement, nor does it populate continuity threads with motive content (wave_B). Both build on this slice without moving owner boundaries.
