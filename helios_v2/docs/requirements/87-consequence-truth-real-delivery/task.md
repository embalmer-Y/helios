# Requirement 87 - Consequence-truth real-delivery verdict task plan

## 1. Title

Requirement 87 - Consequence-truth corroboration: real-delivery verdict (B4 closeout)

## 2. Task Breakdown (by increment; each green before the next)

### Increment 1 - contracts + engine corroboration
1. `evaluation/contracts.py`: add additive optional `ConsequenceClaim` fields `decision_id`,
   `selected_op`, `op_effect_class`, `op_user_visible` (default `None`); `to_evidence` carries them. Add
   the additive `EvaluationEvidenceBundle.delivered_tool_result_evidence` category (default empty,
   validated).
2. `evaluation/engine.py`: populate the claim's new fields from `planner_evidence`; add
   `_corroborate_delivery(prior_claim_evidence, delivered_tool_result_evidence)` returning a
   (verdict, detail) pair; publish `consequence_delivery` + `consequence_delivery_detail` in the gap
   summary; append a `consequence_delivery_discrepancy` warning on `delivered_failed`. Leave `32`
   `consequence_corroboration` + scoring untouched.
3. Tests: `test_evaluation_contracts.py` (claim round-trip + bundle category), `test_evaluation_engine.py`
   (the delivery corroboration matrix; assert `32` verdict/scores unchanged).

### Increment 2 - composition projection + end-to-end
4. `composition/bridges.py` (evaluation request bridge): project `decision_id`/`selected_op`/
   `op_effect_class`/`op_user_visible` into planner evidence (from the accepted `ActionDecision` +
   channel-state op spec); project the current frame's `channel_inbound_drain` `tool_result` reafferences
   (decision_id + ok) into `delivered_tool_result_evidence`.
5. Tests: `test_runtime_composition.py` — channel-bound effector executed → next-tick `really_delivered`;
   failure-injected reafference → `delivered_failed`; reply/no-action → `delivery_not_applicable`;
   default assembly artifact unchanged.

### Increment 3 - P0–P3 exit re-evaluation + docs
6. A focused P0–P3 exit-evaluation test (R64/R72/R73 pattern) asserting B4 closed.
7. Docs: `index.md` row 87; `OWNER_GUIDE.*` (`17` consequence delivery); `PROGRESS_FLOW.*`;
   `ARCHITECTURE_BOUNDARIES.md` §4.2 (evaluation owner — delivery corroboration); `BRAIN_ARCHITECTURE_COMPARISON.md`
   (`gap_behavioral_consequence_binding`); `ROADMAP.zh-CN.md` (R87 → done; P0–P3 100%).

## 3. Dependencies

1. `32` execution-truth corroboration + the prior-consequence-claim carry.
2. `84`/`85`/`86` effectors + `tool_result` reafference with correlation `decision_id` + `ok`.
3. `30`/`31` channel subsystem + the `channel_inbound_drain` stage; the composition evaluation request
   bridge.
4. Network-free, subprocess-free CI (`FakeCommandRunner`/`InlineFileOpExecutor`).

## 4. Files and Modules

1. `helios_v2/src/helios_v2/evaluation/contracts.py`, `evaluation/engine.py`
2. `helios_v2/src/helios_v2/composition/bridges.py`
3. `helios_v2/tests/test_evaluation_contracts.py`, `test_evaluation_engine.py`,
   `test_runtime_composition.py`, the P0–P3 exit-evaluation test
4. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.md`, `OWNER_GUIDE.zh-CN.md`,
   `PROGRESS_FLOW.en.md`, `PROGRESS_FLOW.zh-CN.md`, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 5. Implementation Order

Increment 1 (contracts + engine, unit-tested in isolation) → increment 2 (composition projection +
end-to-end) → increment 3 (exit re-evaluation + docs). Each green before the next.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py -q`
5. `pytest helios_v2/tests/test_p3_exit_evaluation.py -q` (+ the new B4 exit assertion)
6. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`
7. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `ConsequenceClaim` additively carries the four decision facts; the bundle additively carries
   `delivered_tool_result_evidence`; composition projects both from published facts.
2. `consequence_delivery` ∈ {`really_delivered`, `delivered_failed`, `delivery_unverified`,
   `delivery_not_applicable`} is published with a bounded detail; `delivered_failed` warns; the `32`
   corroboration verdict + scoring are byte-for-byte unchanged.
3. End-to-end: executed effector → next-tick `really_delivered`; failure → `delivered_failed`;
   non-effector → `delivery_not_applicable`; default assembly unchanged.
4. The P0–P3 exit re-evaluation asserts B4 closed; docs record P0–P3 at 100%.
5. Full suite green and network-free; owner-boundary + ad-hoc-logging guards pass.
