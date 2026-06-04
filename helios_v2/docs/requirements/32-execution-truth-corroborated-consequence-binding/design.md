# Requirement 32 - Execution-truth-corroborated consequence binding (design)

## 1. Design Overview

This design adds a falsifiability layer on top of the existing `23` consequence-binding evaluation without redesigning its scoring. The evaluation owner already derives a `consequence_path_outcome` from owner-published statuses and already consumes the previous tick's `ExecutionTimelineView` as an existence signal. This requirement makes the evaluation owner cross-check that self-reported outcome against the same tick's kernel execution truth and publish an explicit corroboration verdict, escalating contradictions into a dedicated fidelity warning.

The change is built from three additive pieces:

1. A formal **consequence claim** published in the evaluation artifact, capturing the derived outcome plus the owner statuses it depended on for the evaluated tick.
2. A composition-owned **owner-neutral carry** that forwards the previous completed tick's consequence claim into the next tick's evaluation evidence, tick-aligned with the already-carried timeline view.
3. An evaluation-owned **corroboration step** that maps the claimed outcome to the kernel stage-completion facts it implies, compares them against the carried timeline, and publishes `corroborated` / `discrepant` / `unverifiable_no_timeline` plus a discrepancy warning when contradicted.

Everything stays read-only. No cognitive owner changes policy. No new scoring values are introduced.

## 2. Current State and Gap

Current state (post-`23`):

1. `FirstVersionEvaluationPath.assemble_artifact` derives `consequence_path_outcome` via `_classify_consequence_outcome` from `action_status`, `planner_status`, and `any_written`. It publishes `gap_summary["consequence_path_outcome"]` and the `internal_to_visible_consequence` dimension score.
2. It consumes `bundle.execution_timeline_evidence` only to set `long_range_diagnostics["execution_timeline_status"]` (`observed` / `observed_incomplete` / `no_prior_timeline` / `absent_uninstrumented`) and `execution_timeline_tick_id`.
3. `composition.bridges.TimelineViewHolder` already carries the previous completed tick's `ExecutionTimelineView` plus an `instrumented` flag, and `FirstVersionExecutionTimelineEvidenceBridge` projects it into `execution_timeline_evidence`.

Gap:

1. The self-reported outcome of tick N is never compared with the execution truth of tick N. The timeline is consumed for existence, not corroboration.
2. The previous tick's consequence claim is not carried forward, so even though the previous tick's timeline is available, there is nothing tick-aligned to corroborate it against.

## 3. Target Architecture

### 3.1 Data flow per tick

For the evaluation stage running inside tick `N` (the prior completed tick is `N-1`):

1. Composition assembles the evaluation evidence bundle as today, including `execution_timeline_evidence` projected from the carried `ExecutionTimelineView` of tick `N-1`.
2. Composition additionally injects the **carried consequence claim** of tick `N-1` (captured from tick `N-1`'s evaluation artifact) into the bundle as a new evidence category `prior_consequence_claim_evidence`.
3. The evaluation owner derives tick `N`'s own outcome and publishes tick `N`'s consequence claim into the artifact (for the next tick to corroborate).
4. The evaluation owner runs the corroboration step against the carried tick `N-1` claim + tick `N-1` timeline and publishes the corroboration verdict for tick `N-1` into tick `N`'s artifact.

This keeps the same cross-tick model `23` already established (evaluation reasons about the previous completed tick) and reuses the existing holder mechanism. The corroboration always targets the prior tick, because the current tick's timeline is not complete while the evaluation stage runs.

### 3.2 Owner responsibilities

1. Evaluation owner (`helios_v2.evaluation`) owns: the consequence-claim contract, the outcome-to-stage-fact corroboration mapping, the corroboration verdict, and the discrepancy warning.
2. Observability owner (`helios_v2.observability`) is unchanged. It still owns the `ExecutionTimelineView`; evaluation consumes only its `to_evidence` projection.
3. Composition owner (`helios_v2.composition`) owns only the owner-neutral carry of the prior claim, tick-aligned with the prior timeline. It computes no status and no verdict.

### 3.3 Corroboration mapping (evaluation-owned)

The mapping consumes the carried claim's `consequence_path_outcome` and the carried timeline's per-stage `{stage_name: status}` facts (`completed` / `failed`), where stage facts come only from the `ExecutionTimelineView` projection.

| Claimed outcome | Implied kernel stage facts | Discrepant when |
| --- | --- | --- |
| `continuity_written` | `planner_executor_feedback_bridge` completed AND `execution_writeback_and_autobiographical_consolidation` completed | either stage absent or failed in the timeline |
| `executed` | `planner_executor_feedback_bridge` completed | planner-bridge stage absent or failed |
| `blocked` | a planner/externalization-segment stage failed OR `planner_executor_feedback_bridge` not completed | timeline shows planner-bridge completed and no failed stage in the segment |
| `rejected` | `planner_executor_feedback_bridge` completed (the rejection is a planner decision, so the stage ran) | planner-bridge stage absent or failed |
| `internal_only_decision` | `internal_thought_loop_owner` completed AND no externally consequential stage contradicted | thought stage absent or failed |
| `internally_activated_only` | `internal_thought_loop_owner` completed | thought stage absent or failed |
| `no_activation` | no implied stage facts (vacuously corroborated when timeline present) | never discrepant on stage facts alone |

Rules:

1. The mapping reads stage facts only by canonical stage name. It never reads owner decision payloads (the `ExecutionTimelineView` carries none).
2. If the carried timeline is absent, incomplete in a way that omits an implied stage, or describes a different tick id than the claim, the verdict is `unverifiable_no_timeline` (not `discrepant`), because absence is not contradiction.
3. A `discrepant` verdict names the contradicted outcome and the specific implied stage fact that was missing or failed.

### 3.4 Default rollout

This behavior is default-on whenever the runtime is instrumented (a recorder is attached and a prior tick exists), exactly like `23`'s timeline consumption. On an uninstrumented runtime or first tick it is `unverifiable_no_timeline`. No new toggle is introduced.

## 4. Data Structures

### 4.1 New: `ConsequenceClaim` (evaluation contract)

Immutable, owner-published, carried forward by composition. Plain-mapping-friendly so it can ride the existing evidence-bundle pattern.

```
@dataclass(frozen=True)
class ConsequenceClaim:
    claim_id: str                 # stable id, e.g. f"consequence-claim:{bundle_id}"
    tick_id: int | None           # the tick this claim describes; None only if unknown
    consequence_path_outcome: str # one of the existing _CONSEQUENCE_BINDING_LABELS keys
    planner_status: str | None
    action_status: str | None
    continuity_written: bool
```

Construction validates: non-empty `claim_id`; `consequence_path_outcome` is one of the known outcome keys.

### 4.2 New evidence category on `EvaluationEvidenceBundle`

Add one additive field:

```
prior_consequence_claim_evidence: tuple[Mapping[str, object], ...] = ()
```

It follows the existing `_freeze_evidence_items` rule (each item must carry a non-empty `evidence_id`). It carries at most one item: the projection of the prior tick's `ConsequenceClaim`. Empty tuple means "no prior claim carried" (first tick or uninstrumented).

### 4.3 New artifact fields (additive)

The evaluation artifact gains, without changing existing fields:

1. `gap_summary["consequence_corroboration"]`: one of `corroborated` / `discrepant` / `unverifiable_no_timeline`.
2. `gap_summary["consequence_corroboration_detail"]`: bounded string; for `discrepant` it names the contradicted outcome + missing/failed stage; otherwise a short reason (e.g. `no_prior_claim`, `tick_mismatch`, `timeline_absent`, or `all_implied_stages_present`).
3. A published **current-tick consequence claim** so the next tick can corroborate it. Carried in `long_range_diagnostics["consequence_claim"]` as a plain dict (the same shape as `ConsequenceClaim` projected), keeping the artifact a single published object.
4. When `discrepant`, one additional `FidelityWarning` with `warning_kind="consequence_discrepancy"` whose `evidence_refs` include both the prior-claim evidence id and the timeline evidence id.

### 4.4 Composition carry holder extension

Extend the existing `TimelineViewHolder` (or add a sibling) so the same holder transports the prior tick's published consequence claim alongside the prior timeline view, keeping them tick-aligned:

```
@dataclass
class TimelineViewHolder:
    view: ExecutionTimelineView | None = None
    instrumented: bool = False
    prior_consequence_claim: dict | None = None   # NEW: the prior tick's published claim
```

A new owner-neutral bridge `FirstVersionPriorConsequenceClaimEvidenceBridge` projects `holder.prior_consequence_claim` into `prior_consequence_claim_evidence`, emitting `()` when absent.

## 5. Module Changes

### 5.1 `evaluation/contracts.py`
1. Add `ConsequenceClaim` dataclass with validation.
2. Add `prior_consequence_claim_evidence` field to `EvaluationEvidenceBundle` (additive, defaulted) and include it in the `__post_init__` freeze loop.
3. Export `ConsequenceClaim` from `evaluation/__init__.py`.

### 5.2 `evaluation/engine.py`
1. Add module-level constants: the canonical stage names used by corroboration (`_PLANNER_BRIDGE_STAGE`, `_WRITEBACK_STAGE`, `_THOUGHT_STAGE`) and the corroboration verdict labels.
2. Add `_corroborate_consequence(prior_claim_evidence, timeline_evidence) -> tuple[str, str]` returning `(verdict, detail)`, implementing the mapping in 3.3. Pure function over the two evidence projections.
3. In `assemble_artifact`:
   - build the current-tick `ConsequenceClaim` from the already-derived `consequence_path_outcome`, `planner_status`, `action_status`, `any_written`, and the request/bundle tick id; project it into `long_range_diagnostics["consequence_claim"]`;
   - call `_corroborate_consequence`, set `gap_summary["consequence_corroboration"]` and `..._detail`;
   - when `discrepant`, append the `consequence_discrepancy` `FidelityWarning`.
4. No change to `_classify_consequence_outcome`, dimension scores, or `internal_to_visible_consequence`.

### 5.3 `composition/bridges.py`
1. Extend `TimelineViewHolder` with `prior_consequence_claim`.
2. Add `FirstVersionPriorConsequenceClaimEvidenceBridge.build_claim_evidence(holder)`.
3. Where the evaluation evidence bundle is assembled, pass the projected `prior_consequence_claim_evidence`.

### 5.4 `composition/runtime_assembly.py`
1. After the evaluation stage produces its artifact for tick `N`, capture the published `consequence_claim` dict into the holder so it is available as the prior claim for tick `N+1`, alongside the existing timeline-view capture.
2. Apply the same capture in both the default and channel-bound assemblies (the evaluation stage exists in both).

## 6. Migration Plan

1. All new fields are additive with safe defaults (`()`, `None`). Existing tests that build `EvaluationEvidenceBundle` without the new field keep compiling.
2. The artifact gains fields but loses none, so existing assertions on dimension scores, gaps, and warnings remain valid; new assertions are added for the corroboration fields.
3. The holder extension defaults `prior_consequence_claim=None`, so a runtime that has not yet captured a claim (first tick) yields `unverifiable_no_timeline`.
4. No stage-order change. `CANONICAL_STAGE_ORDER` and `CHANNEL_BOUND_STAGE_ORDER` are untouched.

## 7. Failure Modes and Constraints

1. Missing timeline evidence: verdict `unverifiable_no_timeline`, detail `timeline_absent`; no discrepancy warning; existing timeline-incompleteness warning still fires as today.
2. Missing prior claim (first instrumented tick): verdict `unverifiable_no_timeline`, detail `no_prior_claim`.
3. Tick mismatch between carried claim and carried timeline: verdict `unverifiable_no_timeline`, detail `tick_mismatch`; never corroborate or contradict across mismatched ticks.
4. Incomplete timeline that omits an implied stage: `unverifiable_no_timeline` (absence is not contradiction), unless the timeline is complete and the implied stage is present-but-failed, which is `discrepant`.
5. Read-only invariant: the owner mutates no runtime state; corroboration is a pure function of the two carried evidence projections.
6. No `logging`/`print`; the guard test must stay green.

## 8. Observability and Logging

This requirement consumes the `21` surface only through the formal `ExecutionTimelineView.to_evidence` projection already carried by composition. It adds no new logging mechanism and emits no log events itself. The corroboration verdict travels only through the evaluation artifact contract, never through the log channel.

## 9. Validation Strategy

Focused tests (network-free, deterministic):

1. `test_evaluation_contracts.py`:
   - `ConsequenceClaim` validation (rejects empty id, rejects unknown outcome key).
   - `EvaluationEvidenceBundle` accepts and freezes `prior_consequence_claim_evidence`; rejects items without `evidence_id`.
2. `test_evaluation_engine.py`:
   - corroborated: prior claim `continuity_written` + timeline with planner-bridge and writeback stages completed -> `corroborated`, no discrepancy warning, current-tick claim published.
   - discrepant (missing stage): prior claim `continuity_written` + timeline missing the writeback stage (complete timeline) -> `discrepant`, `consequence_discrepancy` warning referencing both evidence ids, detail names the writeback stage.
   - discrepant (failed stage): prior claim `executed` + timeline with planner-bridge stage `failed` -> `discrepant`.
   - unverifiable: no timeline evidence -> `unverifiable_no_timeline`, detail `timeline_absent`.
   - unverifiable: timeline present but no prior claim -> `unverifiable_no_timeline`, detail `no_prior_claim`.
   - unverifiable: claim tick id != timeline tick id -> `unverifiable_no_timeline`, detail `tick_mismatch`.
   - regression: existing dimension scores and `consequence_path_outcome` values are unchanged for a known bundle.
3. `test_runtime_composition.py`:
   - across two ticks of the default assembly, tick 2's artifact corroborates tick 1's claim against tick 1's timeline and reports `corroborated`.
   - first tick reports `unverifiable_no_timeline` with `no_prior_claim` or `timeline_absent`.
   - channel-bound assembly performs the same carry across two ticks.
4. `test_no_adhoc_logging_guard.py` stays green; full `helios_v2/tests` suite stays green.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_evaluation_contracts.py -q
```
