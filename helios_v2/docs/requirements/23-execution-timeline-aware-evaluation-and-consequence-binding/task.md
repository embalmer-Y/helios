# Requirement 23 - Execution-timeline-aware evaluation and consequence binding task plan

## 1. Title

Requirement 23 - Execution-timeline-aware evaluation and consequence binding

## 2. Task Breakdown

1. Add the immutable `ExecutionTimelineStageEntry` and `ExecutionTimelineView` contracts (with `to_evidence`) to `observability/contracts.py`.
2. Add the read-only `ExecutionTimelineReconstructor` to `observability/engine.py`, deriving the view only from kernel lifecycle/timing facts, with explicit incompleteness and fail-fast on malformed pairing.
3. Export the timeline contracts and reconstructor from `observability/__init__.py`.
4. Add focused observability timeline tests in `tests/test_observability_timeline.py`.
5. Extend `EvaluationEvidenceBundle` in `evaluation/contracts.py` with the `execution_timeline_evidence` category (defaulting to empty, validated like other categories).
6. Upgrade `FirstVersionEvaluationPath` in `evaluation/engine.py` with consequence-binding scoring, the `internal_to_visible_consequence` dimension, timeline-status diagnostics, the shim-derived annotation, and the missing-timeline warning.
7. Extend evaluation tests in `tests/test_evaluation_engine.py` for consequence-binding outcomes, timeline status, and the missing-timeline warning.
8. Add `FirstVersionExecutionTimelineEvidenceBridge` to `composition/bridges.py` and extend `FirstVersionEvaluationRequestBridge.build_evidence_bundle` to include carried timeline evidence.
9. Extend `RuntimeHandle` in `composition/runtime_assembly.py` to reconstruct and carry `last_timeline_view` across ticks when a recorder is present, and feed it to the evaluation bridge.
10. Extend composition tests in `tests/test_runtime_composition.py` for cross-tick timeline carry, first-tick `no_prior_timeline`, and uninstrumented `absent_uninstrumented`.
11. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` to record the timeline view ownership and the narrowed wave A gap.

## 3. Dependencies

1. `21-unified-runtime-observability-and-logging` provides the events and owns the new timeline reconstruction.
2. `17-evaluation-fidelity-and-diagnostic-provenance` provides the evaluation owner being deepened.
3. `22-runtime-composition-root-and-runnable-runtime` provides the runnable runtime and the bridge surface for cross-tick carry.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/observability/contracts.py`
2. `helios_v2/src/helios_v2/observability/engine.py`
3. `helios_v2/src/helios_v2/observability/__init__.py`
4. `helios_v2/src/helios_v2/evaluation/contracts.py`
5. `helios_v2/src/helios_v2/evaluation/engine.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`
7. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
8. `helios_v2/tests/test_observability_timeline.py`
9. `helios_v2/tests/test_evaluation_engine.py`
10. `helios_v2/tests/test_runtime_composition.py`
11. `helios_v2/docs/requirements/index.md`
12. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
13. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 5. Implementation Order

1. Land the timeline contracts in `observability/contracts.py` first; they have no internal dependency.
2. Land the reconstructor in `observability/engine.py` and export it.
3. Add timeline tests and validate the observability slice in isolation.
4. Extend the evaluation evidence bundle and the scoring path; add evaluation tests.
5. Add the composition timeline-evidence bridge and the `RuntimeHandle` cross-tick carry; extend composition tests.
6. Update boundary, index, and grounding docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_observability_timeline.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_composition.py -q`
4. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
5. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. The observability owner exposes the timeline view contract and a read-only reconstructor with explicit incompleteness and fail-fast on malformed pairing.
2. A reconstructed multi-stage tick lists stages in canonical order with per-stage status and duration, derived only from kernel timing facts.
3. The evaluation bundle carries an execution-timeline evidence category and consumes it as a formal contract.
4. Evaluation reasons about the previous tick's timeline, records `no_prior_timeline` on the first tick, and consumes the carried view across later ticks.
5. Evaluation publishes consequence-binding scores distinguishing internally-activated, blocked, rejected, executed, and continuity-written outcomes using owner status taxonomies, plus a shim-derived annotation.
6. An uninstrumented runtime produces an explicit timeline incompleteness warning with no inferred fidelity.
7. The logging-guard test passes and `pytest helios_v2/tests -q` is green.

## 8. Completion Snapshot

Status: pending implementation. This section will be updated with validated results and the final delivered file list once the implementation lands.
