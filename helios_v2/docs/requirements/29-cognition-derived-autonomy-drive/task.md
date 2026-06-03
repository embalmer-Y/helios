# Requirement 29 - Cognition-derived autonomy drive inputs task plan

## 1. Title

Requirement 29 - Cognition-derived autonomy drive inputs

## 2. Task Breakdown

1. Add documented module-level derivation constants to `composition/bridges.py` for the autonomy drive-input mapping.
2. Rewrite `FirstVersionAutonomyRequestBridge.build_request` to derive `continuation_pressure`, `temporal_pressure`, `identity_unresolved_pressure`, and the outward-readiness pair from `internal_thought_result`, `planner_bridge_result`, `thought_gating_result`, and `identity_governance_result`, keeping `retrieval_pull` as today and clamping all numerics to `[0,1]`. Preserve all existing provenance ids.
3. Confirm no `runtime/stages.py` change is needed (all required results are already passed to the bridge); adjust only if a required result is not currently available.
4. Update `tests/test_runtime_composition.py`: assert `externalize` for an executed-action envelope, a non-externalize disposition for a continue/no-action envelope, `defer` + deferred record for a planner-blocked action, and `24` thread formation across repeated continue ticks.
5. Add or adjust focused autonomy coverage only if useful; the owner rule is unchanged.
6. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` to record that autonomy drive is now cognition-derived and that the `24` thread layer now runs on real cognition.

## 3. Dependencies

1. `26`/`27`/`28` provide the real thought-owner decision and the internal-only closure the derivation reads.
2. `18` provides the autonomy owner rule and `24` thread layer the derived inputs feed; this requirement does not change them.
3. `22` provides the bridge surface and assembled runtime for the end-to-end tests.
4. No real network or api key for any test; a deterministic fake gateway covers all cases.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/composition/bridges.py`
2. `helios_v2/src/helios_v2/runtime/stages.py` (only if required)
3. `helios_v2/tests/test_runtime_composition.py`
4. `helios_v2/tests/test_autonomy_engine.py` (optional focused coverage)
5. `helios_v2/docs/requirements/index.md`
6. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
7. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 5. Implementation Order

1. Implement the derivation in the bridge with documented constants.
2. Update composition tests for the four disposition cases plus thread formation; iterate constants until the documented dispositions are deterministically reached.
3. Run the focused autonomy + composition slices, then the full suite.
4. Update boundary, grounding, and index docs.
5. Optional: real LLM smoke to confirm a no-action tick now shows a non-externalize disposition.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_autonomy_engine.py -q`
4. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
5. `pytest helios_v2/tests -q`
6. Optional real check (consumes tokens): `python helios_v2/scripts/run_llm_smoke.py --ticks 3 --stimulus "just reflect quietly, you don't need to reply"`

## 7. Completion Criteria

1. No autonomy drive input is a hardcoded behavioral constant; all are derived from explicit upstream owner results (temporal baseline excepted and documented as a non-switching baseline).
2. Executed-action ticks drive `externalize`; continue/no-action ticks drive a non-externalize disposition; planner-blocked action ticks drive `defer` with a deferred record.
3. Repeated continue ticks form and reinforce `24` continuity threads, proving the thread layer runs on real cognition.
4. The autonomy owner rule and contracts are unchanged; the change is confined to the bridge derivation.
5. The logging-guard test passes and `pytest helios_v2/tests -q` is green and network-free.

## 8. Completion Snapshot

Status on 2026-06-03: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/composition/bridges.py` (`FirstVersionAutonomyRequestBridge` now derives `continuation_pressure`, `temporal_pressure`, `identity_unresolved_pressure`, and the outward-readiness pair from the thought-cycle result, planner status, and continuation state, with documented derivation constants and `[0,1]` clamping; `retrieval_pull` unchanged)
2. `helios_v2/tests/test_runtime_composition.py` (executed-action -> externalize; continue/no-action -> non-externalize; concluded/no-action -> defer + thread; repeated deferring ticks persist a thread)
3. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

Validated outcomes:

1. `pytest helios_v2/tests -q` -> 332 passed, network-free
2. Real LLM smoke (`run_llm_smoke.py --ticks 3 --stimulus "...you don't need to reply"`): a no-action decision now yields `disposition=defer/deferred_continuity` and `long_horizon=forming_dominant_thread -> reinforced_dominant_thread`, where before R29 it was `externalize/outward_proactive` with `no_active_thread`.

Implementation notes:

1. The autonomy owner engine and contracts are unchanged. The change is confined to the bridge's value derivation: it translates the thought owner's real decision (action present / continue / concluded) plus planner status into the bounded drive inputs the owner consumes. The owner still applies its own disposition rule.
2. Empirical correction from the design's initial prediction: continue ticks resolve to `reflect` (no deferral), while concluded/no-action ticks resolve to `defer` and form the `24` thread. Threads form on real cognition where they were previously always inert (autonomy always externalized and cleared deferrals).
3. `temporal_pressure` remains an explicit non-switching baseline (the thought owner does not produce a clock/time-since signal); deriving real temporal pressure is a separate future signal. Cross-tick reinforcement strength is bounded by the existing `18` continuity-key scheme and is out of scope here.
