# Requirement 32 - Execution-truth-corroborated consequence binding (wave_A closeout)

## 1. Background and Problem

After `23`, the evaluation owner (`helios_v2.evaluation`) already consumes the observability-owned `ExecutionTimelineView` of the previous completed tick and publishes a consequence-binding path outcome (`no_activation`, `internally_activated_only`, `internal_only_decision`, `blocked`, `rejected`, `executed`, `continuity_written`) plus an `internal_to_visible_consequence` score.

However, the `wave_A_behavioral_truth` exit signal in `BRAIN_ARCHITECTURE_COMPARISON.md` is still not met. The decisive gap is this:

1. The published consequence path outcome is derived **only from owner self-reported statuses** (the planner-bridge status, the action-normalization status, and whether continuity writeback claims it was written). Evaluation never checks those self-reports against the **actual kernel execution truth** carried by the timeline.
2. The execution timeline is therefore consumed only as an **existence** signal (`observed` / `observed_incomplete` / `no_prior_timeline` / `absent_uninstrumented`). It is not yet consumed as a **corroboration** signal that can confirm or contradict the self-reported causal chain.

This matters directly for the locked final-goal standard. `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 12 `FG-6` requires global falsifiability: when an architecture claim disagrees with runtime truth, evaluation must be able to expose the deviation. The v2.0.0 release gate (section 6, item 5) requires that evaluation can read-only reconstruct the key causal chain. A self-reported causal chain that cannot be falsified by independent execution truth does not meet either standard. Today a buggy or dishonest upstream owner could publish `planner_status="executed"` on a tick where the planner-bridge stage never completed, and evaluation would score `executed` / `continuity_written` without protest.

The previous completed tick's timeline (already carried forward by the `23` `TimelineViewHolder`) records which stages actually started, completed, or failed for that tick. That is exactly the independent execution truth needed to corroborate the self-reported outcome of the **same** tick. The missing piece is that the self-reported outcome of the previous tick is not carried forward alongside its timeline, so the two cannot be aligned and cross-checked.

## 2. Goal

Make the evaluation owner falsifiable about consequence binding: each tick it must corroborate the previous completed tick's self-reported consequence path outcome against that same tick's kernel execution timeline, and publish an explicit corroboration verdict (`corroborated`, `discrepant`, or `unverifiable_no_timeline`) that escalates any contradiction into a first-class fidelity warning, while remaining read-only, deriving corroboration only from kernel execution-timing facts plus owner-published statuses, never re-deriving an owner's decision, and never inferring corroboration from missing evidence.

## 3. Functional Requirements

### 3.1 Carry the previous tick's self-reported consequence claim forward
1. Evaluation must publish, as part of its artifact, a compact **consequence claim** for the tick it evaluates: the `consequence_path_outcome` it derived and the owner-published statuses that outcome depended on (at minimum the planner-bridge status, the action-normalization status, and whether continuity was written).
2. The composition owner must carry the previous completed tick's consequence claim forward into the next tick's evaluation evidence assembly, aligned to the same tick the carried timeline describes, through an explicit owner-neutral bridge.
3. The consequence claim and the execution timeline carried into one evaluation cycle must describe the **same** prior tick id. If they disagree on tick id, evaluation must treat the pair as unverifiable rather than corroborate across mismatched ticks.

### 3.2 Corroborate self-report against execution truth
1. Evaluation must compute a **corroboration verdict** for the previous completed tick by checking the carried consequence claim against the carried timeline's per-stage completed/failed facts.
2. The corroboration must use an explicit, documented mapping from each `consequence_path_outcome` to the kernel stage-completion facts that outcome implies. At minimum:
   - `continuity_written` and `executed` imply the `planner_executor_feedback_bridge` stage completed for that tick;
   - `continuity_written` additionally implies the `execution_writeback_and_autobiographical_consolidation` stage completed for that tick;
   - `blocked` implies a stage in the externalization/planner segment is recorded as failed, or the planner-bridge stage did not complete;
   - `internal_only_decision` and `internally_activated_only` imply the `internal_thought_loop_owner` stage completed and no externally consequential stage is contradicted.
3. The corroboration mapping must consume only kernel execution-timing facts (stage name, stage completed/failed status) from the formal `ExecutionTimelineView` projection, plus the owner-published statuses inside the consequence claim. It must not parse raw `LogEvent` objects and must not re-derive any owner's semantic decision.
4. Evaluation must publish the corroboration verdict as a first-class field with at least these values: `corroborated`, `discrepant`, `unverifiable_no_timeline`. A `discrepant` verdict must carry a bounded, human-readable detail naming which implied stage fact was missing or contradicted.

### 3.3 Escalate discrepancy as a fidelity warning
1. When the corroboration verdict is `discrepant`, evaluation must emit a first-class `FidelityWarning` of a dedicated warning kind that references both the consequence-claim evidence and the timeline evidence.
2. The discrepancy warning must name the contradicted outcome and the missing or failed stage fact, so a reviewer can locate the exact mismatch.
3. A `corroborated` verdict must not emit a discrepancy warning. An `unverifiable_no_timeline` verdict must reuse the existing explicit timeline-incompleteness reporting and must not be reported as either corroboration or discrepancy.

### 3.4 No fallback and no scoring redesign
1. A missing or tick-mismatched timeline, or a missing consequence claim (for example on the first instrumented tick where there is no prior tick), must yield `unverifiable_no_timeline` and an explicit incompleteness note, never an optimistic `corroborated` default.
2. This requirement must not redesign the existing dimension-score values, the existing `consequence_path_outcome` taxonomy, or the existing `internal_to_visible_consequence` scoring. It only adds the corroboration verdict, the consequence-claim carry, and the discrepancy warning on top of the existing artifact.
3. Evaluation must not mutate runtime behavior, planner authority, channel execution, governance decisions, or storage, and must remain read-only.

## 4. Non-Functional Requirements

1. Performance: corroboration must be bounded by the number of stages in one tick's timeline and must not change runtime execution behavior.
2. Reliability: for identical evidence, the corroboration verdict and any discrepancy warning must be deterministic and comparable across runs.
3. Observability and logging: this requirement consumes the `21` event surface only through the formal `ExecutionTimelineView`; it must not introduce a second logging mechanism and must not use `logging` or `print`.
4. Compatibility and migration: the consequence claim, its carry bridge, and the corroboration verdict are additive. An uninstrumented runtime (no recorder) must still assemble and run; corroboration simply reports `unverifiable_no_timeline` in that case. The default 19-stage and opt-in 21-stage assemblies must both keep working.

## 5. Code Behavior Constraints

1. The corroboration mapping lives in the evaluation owner. Evaluation must not reconstruct timelines itself; it must keep consuming the observability-owned `ExecutionTimelineView` projection.
2. Evaluation must not depend on the log channel to receive any owner's semantic decision. Owner statuses must continue to arrive only through the existing owner result contracts (carried as the consequence claim), and only kernel execution-timing facts may come from the timeline.
3. The composition owner remains assembly-only. Carrying the previous tick's consequence claim forward must be owner-neutral glue aligned to the carried timeline's tick, not a new cognitive decision and not a re-derivation of any owner status.
4. No degraded or fallback corroboration is allowed. A verdict of `corroborated` may only be published when the timeline actually supports every implied stage fact for the claimed outcome.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/evaluation/contracts.py`
2. `helios_v2/src/helios_v2/evaluation/engine.py`
3. `helios_v2/src/helios_v2/evaluation/__init__.py`
4. `helios_v2/src/helios_v2/composition/bridges.py`
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
6. `helios_v2/tests/test_evaluation_contracts.py`
7. `helios_v2/tests/test_evaluation_engine.py`
8. `helios_v2/tests/test_runtime_composition.py`
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
11. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The evaluation artifact publishes a compact consequence claim (the derived `consequence_path_outcome` plus the planner-bridge status, action-normalization status, and continuity-written flag it depended on) for the tick it evaluates.
2. The composition owner carries the previous completed tick's consequence claim forward, aligned to the same prior tick id as the carried timeline, through an explicit owner-neutral bridge, across the default and channel-bound assemblies.
3. Evaluation publishes a first-class corroboration verdict (`corroborated`, `discrepant`, `unverifiable_no_timeline`) computed from the documented outcome-to-stage-fact mapping using only `ExecutionTimelineView` timing facts plus the carried consequence claim.
4. On a normal multi-stage tick where the planner-bridge and writeback stages completed and continuity was written, the next tick's evaluation reports `corroborated` for a `continuity_written` claim, with no discrepancy warning.
5. When the carried claim asserts an outcome the carried timeline contradicts (for example a `continuity_written`/`executed` claim while the planner-bridge stage is absent or recorded failed in the timeline), evaluation reports `discrepant` and emits a dedicated discrepancy `FidelityWarning` referencing both the consequence-claim and timeline evidence and naming the contradicted stage fact.
6. When no recorder is attached, or on the first instrumented tick with no prior consequence claim, or when the claim and timeline describe different tick ids, evaluation reports `unverifiable_no_timeline` and does not emit a discrepancy warning and does not report `corroborated`.
7. The existing `consequence_path_outcome` taxonomy, dimension scores, and `internal_to_visible_consequence` scoring are unchanged in value; the corroboration verdict is strictly additive.
8. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement closes `wave_A_behavioral_truth` by making consequence binding falsifiable against execution truth while the early-chain cognition (`03-10`) is still deterministic first-version shim. The following are explicitly anticipated future work, each via its own requirement package, and must preserve the owner boundaries established here:

1. Corroborating finer-grained owner-level emission once `21` opens owner-level observability (plan C), beyond kernel stage lifecycle.
2. Deeper consequence metrics and discrepancy taxonomies once non-deterministic real cognition produces variable paths through the chain.
3. Wave_B long-horizon continuity corroboration (preserved vs resolved vs degraded continuity threads) as `18`, `14`, and `15` deepen.
4. Durable persistence and cross-run comparison of corroboration verdicts (depends on the P2 persistence base).

None of these may be smuggled into this slice. This requirement does not introduce LLM cognition, does not change any cognitive owner's policy, does not redesign the existing scoring, and does not grant evaluation any runtime write authority.
