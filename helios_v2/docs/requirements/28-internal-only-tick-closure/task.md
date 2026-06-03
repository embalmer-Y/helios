# Requirement 28 - Internal-only tick closure task plan

## 1. Title

Requirement 28 - Internal-only tick closure (wave_C opener)

## 2. Task Breakdown

1. Add a `no_actionable_proposal` status to the `13` planner-bridge `BridgeStatus` taxonomy and allow an all-None payload result; produce it from the owner when no normalized proposal is present.
2. Update the runtime planner-bridge stage adapter to drive the owner into the internal-only result for a non-normalized externalization result, preserving the externalizing path.
3. Add an internal-only continuity outcome to the `15` experience-writeback owner and emit one internal-only writeback request when the planner outcome is `no_actionable_proposal`, with thought-cycle and planner provenance.
4. Confirm the `18` autonomy owner integrates an internal-only tick using the real internal-only planner result id and the internal-only writeback id (no contract relaxation, no fabricated ids); adjust the autonomy request bridge only to forward provenance.
5. Add an explicit internal-only consequence-binding outcome to the `17`/`23` evaluation owner, distinct from blocked/rejected/executed/continuity-written and from a missing-action failure.
6. Add owner-level tests for `13`, `15`, `18`, `17`, then a composition test asserting the default LLM-backed runtime completes a tick for both an externalizing envelope and a continue/no-action envelope (network-free fake gateway).
7. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` to record the internal-only tick closure and narrow the behavioral-consequence gap.

## 3. Dependencies

1. `27-structured-thought-output-driven-judgment` makes the continue/no-action decision reachable and defines the boundary this requirement closes.
2. `13`, `15`, `18`, `17` provide the owners whose contracts gain the internal-only outcome.
3. `22` provides the assembled runtime and bridges for the end-to-end composition test.
4. No real network or api key for any test; a deterministic fake gateway covers the LLM-backed path.

## 4. Files and Modules

Per requirement section 6.

## 5. Implementation Order

1. `13` internal-only status + owner production + planner stage adapter; owner tests.
2. `15` internal-only continuity writeback + bridge; owner tests.
3. Confirm `18` tolerance + autonomy bridge provenance forwarding; owner tests.
4. `17` internal-only consequence label; evaluation tests.
5. Composition end-to-end test for both envelopes.
6. Docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_planner_bridge_contracts.py helios_v2/tests/test_planner_bridge_engine.py -q`
4. `pytest helios_v2/tests/test_experience_writeback_contracts.py helios_v2/tests/test_experience_writeback_engine.py -q`
5. `pytest helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_evaluation_engine.py -q`
6. `pytest helios_v2/tests/test_runtime_composition.py -q`
7. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. A no-proposal tick completes through planner, writeback, autonomy, and evaluation as an explicit internal-only outcome with real provenance.
2. The default LLM-backed runtime completes both an externalizing and a continue/no-action tick, network-free.
3. The externalizing path and all existing tests remain green; the logging-guard test passes and `pytest helios_v2/tests -q` is green.

## 8. Status

Status on 2026-06-03: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/planner_bridge/contracts.py` (`no_actionable_proposal` status + all-None payload validation + `build_evaluate_op_internal_only`/`evaluate_internal_only` API)
2. `helios_v2/src/helios_v2/planner_bridge/engine.py` (`evaluate_internal_only`, `build_evaluate_op_internal_only`, internal-only validation)
3. `helios_v2/src/helios_v2/experience_writeback/contracts.py` (`internal_thought_cycle` source kind, `internal_only` outcome class, `written_internal_only` status, `internal_thought_cycle` continuity kind)
4. `helios_v2/src/helios_v2/experience_writeback/engine.py` (internal-only mapping in all five maps + request validation)
5. `helios_v2/src/helios_v2/evaluation/engine.py` (`internal_only_decision` consequence-binding label/score + classifier branch)
6. `helios_v2/src/helios_v2/runtime/stages.py` (planner-bridge stage branches to internal-only on non-normalized externalization; writeback stage maps `internal_thought_cycle` provenance)
7. `helios_v2/src/helios_v2/composition/bridges.py` (writeback request bridge emits the internal-only continuity request)
8. `helios_v2/tests/test_planner_bridge_engine.py`, `helios_v2/tests/test_experience_writeback_engine.py`, `helios_v2/tests/test_runtime_composition.py` (internal-only owner + end-to-end tests)
9. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

Validated outcomes:

1. `pytest helios_v2/tests -q` -> 328 passed, network-free
2. Real LLM smoke (`run_llm_smoke.py --ticks 3 --stimulus "...you don't need to reply"`): all ticks completed with `consequence_outcome=internal_only_decision` (the path that crashed before R28).

Implementation notes:

1. The internal-only outcome is owned by each owner: `13` produces a `no_actionable_proposal` result with no decision; `15` records an `internal_only` continuity writeback with real provenance to the planner result; `17` classifies the tick as `internal_only_decision`. Autonomy needed no contract change because the internal-only planner result and internal-only writeback supply real, non-empty provenance.
2. The externalizing path is unchanged; deciding there is no proposal to route is an orchestration fact derived from the upstream externalization status, mapped into the planner owner's internal-only result.
3. Known adjacent shim gap (not in `28` scope): the autonomy owner's drive summaries are still hardcoded by the autonomy request bridge, so `dominant_disposition` does not yet reflect the thought owner's no-action decision. That is a separate later requirement; `28` closes the tick through the chain.

## 9. Out-of-Scope Confirmation

`28` does not implement outward channel execution (real transport of a normalized proposal), which remains the later wave_C outward-closure requirement, and does not feed autonomy drive inputs from real cognition.
