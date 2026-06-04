# Requirement 32 - Execution-truth-corroborated consequence binding (tasks)

## 1. Task Breakdown

### Task 1 - Evaluation contracts: consequence claim + evidence category
1. Add the `ConsequenceClaim` frozen dataclass to `evaluation/contracts.py` with validation (non-empty `claim_id`; `consequence_path_outcome` must be a known outcome key).
2. Add the additive `prior_consequence_claim_evidence: tuple[Mapping[str, object], ...] = ()` field to `EvaluationEvidenceBundle` and include it in the `__post_init__` freeze loop.
3. Export `ConsequenceClaim` from `evaluation/__init__.py`.
4. Completion: contracts import cleanly; new contract validates and freezes; no change to existing fields' semantics.
5. Validation: `pytest helios_v2/tests/test_evaluation_contracts.py -q`.

### Task 2 - Evaluation engine: corroboration mapping + verdict + claim publication
1. Add module constants for the canonical stage names used by corroboration (`planner_executor_feedback_bridge`, `execution_writeback_and_autobiographical_consolidation`, `internal_thought_loop_owner`) and the verdict labels.
2. Implement `_corroborate_consequence(prior_claim_evidence, timeline_evidence) -> (verdict, detail)` per design section 3.3 as a pure function.
3. In `assemble_artifact`: build and publish the current-tick consequence claim into `long_range_diagnostics["consequence_claim"]`; compute and publish `gap_summary["consequence_corroboration"]` and `consequence_corroboration_detail`; append the `consequence_discrepancy` `FidelityWarning` only when `discrepant`.
4. Leave `_classify_consequence_outcome`, dimension scores, and `internal_to_visible_consequence` untouched.
5. Completion: corroboration verdict is published for all six evidence scenarios; existing scores unchanged.
6. Validation: `pytest helios_v2/tests/test_evaluation_engine.py -q`.

### Task 3 - Composition: carry prior consequence claim, tick-aligned
1. Extend `TimelineViewHolder` in `composition/bridges.py` with `prior_consequence_claim: dict | None = None`.
2. Add `FirstVersionPriorConsequenceClaimEvidenceBridge.build_claim_evidence(holder)` projecting the prior claim into `prior_consequence_claim_evidence` (emit `()` when absent).
3. Wire the projected evidence into the evaluation evidence-bundle assembly.
4. In `composition/runtime_assembly.py`, after the evaluation stage runs, capture the artifact's published `consequence_claim` into the holder for the next tick, in both default and channel-bound assemblies (mirroring the existing timeline-view capture).
5. Completion: across two ticks, tick 2 receives tick 1's claim aligned with tick 1's timeline.
6. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Tests for corroboration behavior
1. Add contract tests (Task 1 surface): claim validation, bundle freeze of the new category.
2. Add engine tests: corroborated, discrepant-missing-stage, discrepant-failed-stage, unverifiable-no-timeline, unverifiable-no-prior-claim, unverifiable-tick-mismatch, and a regression that existing scores/outcome are unchanged.
3. Add composition tests: two-tick corroboration in default and channel-bound assemblies; first-tick unverifiable.
4. Completion: all new tests pass and assert provenance (evidence_refs) for the discrepancy warning, not just verdict strings.
5. Validation: `pytest helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_runtime_composition.py -q`.

### Task 5 - Documentation sync
1. Update `index.md`: add the R32 row (status draft, maturity per evidence after implementation), depends on `17, 21, 22, 23`.
2. Update `ARCHITECTURE_BOUNDARIES.md`: extend the `17`/evaluation owner snapshot and migration-state notes to record the corroboration verdict and prior-claim carry; record that `composition` carries the prior consequence claim as owner-neutral glue.
3. Update `BRAIN_ARCHITECTURE_COMPARISON.md`: narrow `gap_behavioral_consequence_binding` to reflect that consequence binding is now corroborated against execution truth, and mark `wave_A_behavioral_truth` exit signal progress.
4. Update both `PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md` (same change set): note R32 as last-synced; reflect that evaluation now corroborates execution truth. Adjust the `17` color only if maturity actually changes.
5. Completion: no doc/code drift; index, boundaries, comparison, and both flow maps all reflect R32.
6. Validation: manual review + `getDiagnostics` on the spec docs.

## 2. Dependencies

1. Depends on `23` (timeline-aware evaluation + `TimelineViewHolder` + consequence path outcome) — already shipped.
2. Depends on `21` (`ExecutionTimelineView` + `to_evidence`) — already shipped.
3. Depends on `22` (composition assembly seam) — already shipped.
4. No dependency on `25/26/27` LLM cognition; works on the deterministic chain.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/evaluation/contracts.py` (Task 1)
2. `helios_v2/src/helios_v2/evaluation/__init__.py` (Task 1)
3. `helios_v2/src/helios_v2/evaluation/engine.py` (Task 2)
4. `helios_v2/src/helios_v2/composition/bridges.py` (Task 3)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 3)
6. `helios_v2/tests/test_evaluation_contracts.py` (Task 4)
7. `helios_v2/tests/test_evaluation_engine.py` (Task 4)
8. `helios_v2/tests/test_runtime_composition.py` (Task 4)
9. `helios_v2/docs/requirements/index.md` (Task 5)
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 5)
11. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 5)
12. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 5)
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 5)

## 4. Implementation Order

1. Task 1 (contracts) — foundation; no behavior yet.
2. Task 2 (engine corroboration) — owner behavior on top of the new contract.
3. Task 3 (composition carry) — wires the prior claim cross-tick.
4. Task 4 (tests) — incrementally alongside Tasks 1-3, finalized here.
5. Task 5 (docs) — last, once behavior and maturity are evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_evaluation_contracts.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_evaluation_engine.py -q`.
3. After Task 3: `pytest helios_v2/tests/test_runtime_composition.py -q`.
4. After Task 4: the three suites above together, plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
5. Full gate: `pytest helios_v2/tests -q` (must stay fully green and network-free).

## 6. Completion Criteria

1. Evaluation publishes a per-tick consequence claim and a first-class corroboration verdict (`corroborated` / `discrepant` / `unverifiable_no_timeline`) for the prior completed tick.
2. A contradicted claim produces a `consequence_discrepancy` fidelity warning that references both the prior-claim and timeline evidence and names the contradicted stage fact.
3. Missing timeline, missing prior claim, and tick mismatch all yield `unverifiable_no_timeline` with no discrepancy warning and no false `corroborated`.
4. Existing scoring, outcome taxonomy, and dimension values are unchanged; corroboration is strictly additive.
5. Default and channel-bound assemblies both carry the claim across ticks.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green.
