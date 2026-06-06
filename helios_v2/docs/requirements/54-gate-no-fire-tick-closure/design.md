# Requirement 54 - Gate no-fire tick closure (design)

## 1. Design Overview

A no-fire gate is closed entirely in the **runtime stage adapters** (`runtime/stages.py`) plus the **composition bridges** (`bridges.py`). No fired-path owner gains a "run on no-fire" path; the runtime simply does not call those owners on a no-fire tick, and instead emits explicit inactive stage results and routes the closure tail through no-fire-aware owner calls.

The gate decision (`ThoughtGatingStageResult.result.decision`) is published in the frame and read by every post-gate stage. Each post-gate stage's `run` gains a guard:

```
gate = _require_stage_result(frame, gate_stage, ThoughtGatingStageResult)
if gate.result.decision != "fire":
    return <inactive / no-fire result>   # owner fired-path API NOT called
# ... existing fired-path behavior unchanged ...
```

Two categories of post-gate stage:

1. **Pure fired-path stages** (`10` directed-retrieval, `16` embodied-prompt, `16` outward-expression, `16` outward-expression-externalization, `11` internal-thought, `12` action-externalization, `14` identity-governance): on no-fire they return an **inactive stage result** — a new `activated: bool = True` discriminator set to `False`, with the artifact fields made `Optional` and set to `None`/empty, and no owner fired-path call. The fired-path owners' invariants are untouched.

2. **Closure-tail stages** (`13` planner-bridge, `15` writeback, `18` autonomy, `17` evaluation): on no-fire they still run their owners, but through a no-fire request built from stable provenance anchors (the gate result id plus deterministic no-fire marker ids), reusing the existing R28 internal-only owner outcomes (`no_actionable_proposal` planner result, `internal_only` writeback continuity). This preserves continuation pressure and `18`/`24` continuity carry across the tick.

The channel-bound assembly's `channel_outbound_dispatch` already dispatches nothing when there is no accepted decision (R31), so a no-fire tick transports nothing with no change.

Scope: the no-fire closure is default (not opt-in) — it is a correctness fix for the assembled chain. The fired path is byte-for-byte unchanged (all new fields default to the fired shape).

## 2. Current State and Gap

Verified in code:

1. `09` publishes `ThoughtGateResult.decision in {"fire","no_fire"}`. The post-gate stages run unconditionally (the kernel runs all stages) and `10`/`11`/`12`/`14` raise on a non-fired/non-completed upstream (deliberate owner invariants); `16`-family raises on the absent retrieval bundle / prompt view.
2. R28 already built the internal-only tail for the *fired-but-no-proposal* case: `PlannerBridge.evaluate_internal_only` -> `no_actionable_proposal`; the writeback bridge emits an `internal_only` continuity record; autonomy/evaluation already consume a no-action outcome.
3. The autonomy stage validates request provenance against `directed_retrieval_result.bundle.bundle_id`, `internal_thought_result.result.result_id`, `outward_expression_result.draft.draft_id`, etc. The evaluation bridge reads `internal_thought_result.result`, `action_externalization_result.result`, etc.
4. The `RuntimeHandle.tick` carry seams (`_carry_recall_directive`, `_persist_experience`, `_persist_memory`, `_checkpoint_continuity`) all use tolerant `.get(...)` and `getattr(...)`, so they already survive a no-fire tick (the recall seam explicitly handles "no `11` result").

Gap: a no-fire gate aborts the tick at the first post-gate stage.

## 3. Target Architecture

### 3.1 Inactive stage-result discriminator

Each affected stage result dataclass gains `activated: bool = True` and makes its artifact fields `Optional` with a `None`/empty default, plus a deterministic `inactive_id: str | None = None` (the stable provenance anchor for the no-fire tick). A factory classmethod builds the inactive form:

```
@dataclass(frozen=True)
class DirectedRetrievalStageResult:
    ...
    plan: RetrievalQueryPlan | None = None
    bundle: ThoughtWindowBundle | None = None
    ...
    activated: bool = True
    inactive_id: str | None = None

    @classmethod
    def inactive(cls, tick_id) -> "DirectedRetrievalStageResult":
        return cls(plan_op=None, request=None, plan=None, bundle=None,
                   publish_bundle_op=None, activated=False,
                   inactive_id=f"directed-retrieval-no-fire:{tick_id}")
```

The same shape applies to the `16` prompt/outward/externalization, `11` internal-thought, `12` action-externalization, and `14` identity-governance stage results. Fired-path construction is unchanged (every new field defaults to the fired shape), so existing fired-path code and tests are untouched.

### 3.2 Pure fired-path stage no-fire guard

Each pure fired-path stage's `run` adds the guard at the top (after requiring the gate result):

```
def run(self, frame):
    gate = _require_stage_result(frame, self.gate_stage_name, ThoughtGatingStageResult)
    if gate.result.decision != "fire":
        return DirectedRetrievalStageResult.inactive(frame.tick_id)
    # existing fired-path body unchanged
```

For stages that currently key on a different upstream stage result (e.g. `12` action-externalization requires the `11` internal-thought result), the guard checks the upstream result's `activated` flag instead of re-reading the gate (so the no-fire signal propagates down the chain):

```
def run(self, frame):
    internal = _require_stage_result(frame, self.upstream_stage_name, InternalThoughtStageResult)
    if not internal.activated:
        return ActionExternalizationStageResult.inactive(frame.tick_id)
    # existing fired-path body unchanged
```

This keeps each stage reading only its declared upstream, with `activated` as the propagated no-fire signal. `10` and `16`-prompt read the gate directly (they are first after the gate); the rest propagate via `activated`.

### 3.3 Closure-tail no-fire branches

`13` planner-bridge: its existing R28 branch already produces `no_actionable_proposal` when the externalization result is not normalized. On a no-fire tick the `12` action-externalization result is inactive (`activated=False`, `result=None`). The planner stage's guard:

```
action = _require_stage_result(frame, upstream, ActionExternalizationStageResult)
if not action.activated:
    # No-fire tick: no proposal exists. Produce the internal-only result directly from a
    # no-fire marker request (reusing the no_actionable_proposal outcome).
    return self._run_no_fire(frame)
```

`_run_no_fire` builds a minimal `PlannerBridgeRequest` (normalized_proposal_present=False, anchored on `f"no-fire-externalization:{tick_id}"`) and calls `evaluate_internal_only`, yielding `no_actionable_proposal` — exactly the R28 outcome, now reachable on a no-fire tick.

`15` writeback: the writeback request bridge already emits an `internal_only` continuity record when the planner result is `no_actionable_proposal` (R28). Since the no-fire planner result is `no_actionable_proposal`, **the existing bridge already produces the right continuity record** — but it also reads `identity_governance_result.result.revision_decision`. On no-fire, governance is inactive (`result=None`), so the bridge gains a guard: skip the identity-writeback branch when governance is not activated. The internal-only continuity record is unchanged.

`18` autonomy: the autonomy stage gains a no-fire branch that builds the `ProactiveDriveRequest` from the gate result id plus deterministic no-fire marker ids for the thought/retrieval/outward provenance slots (the autonomy owner validates only non-emptiness of these ids and reads the bounded pressure summaries, not cross-stage consistency). The no-fire drive inputs: no action (`outward_ready=False`, `externalization_blocked=False`), continuation pressure from the carried `09` continuation state, so a no-fire tick still forms/reinforces deferred continuity exactly as a continue tick does. The stage's artifact-provenance validation is gated on `activated` (skipped on no-fire). The cross-tick continuity carry (`_prior_deferred_records`/`_prior_continuity_threads`) is unchanged.

`17` evaluation: the evaluation stage gains a no-fire branch; the bridge builds the request/evidence from the no-fire outcome (the inactive thought/action results contribute explicit `activated=False`/`None` evidence, the planner `no_actionable_proposal`, autonomy result present). Read-only; it never mutates. The carried prior-tick timeline and consequence claim are unchanged.

### 3.4 No-fire request markers (provenance anchors)

On a no-fire tick the stable provenance anchor is the gate result id (always present). The closure-tail request bridges use deterministic markers for the absent-artifact slots:

```
source_thought_cycle_result_id = f"no-fire-internal-thought:{tick_id}"
source_retrieval_bundle_id      = f"no-fire-directed-retrieval:{tick_id}"
source_outward_expression_draft_id = f"no-fire-outward-expression:{tick_id}"
source_outward_expression_externalization_draft_id = f"no-fire-outward-externalization:{tick_id}"
```

These are explicit no-fire markers, not fabricated artifacts: they carry no cognitive content, only a stable id so the owner's non-empty-id validation passes. The autonomy/evaluation stage adapters validate artifact provenance only when `activated`, so they accept the marker-anchored request on no-fire.

### 3.5 Default rollout

Default and channel-bound assemblies both get the closure (it is a correctness fix). A fired tick is byte-for-byte unchanged: every new stage-result field defaults to the fired shape, and the no-fire branches are reached only when `decision != "fire"`.

## 4. Data Structures

Additive only:
1. `activated: bool = True` + `inactive_id: str | None = None` on `DirectedRetrievalStageResult`, `EmbodiedPromptStageResult`, `OutwardExpressionStageResult`, `OutwardExpressionExternalizationStageResult`, `InternalThoughtStageResult`, `ActionExternalizationStageResult`, `IdentityGovernanceStageResult`.
2. The artifact fields on those results become `Optional` with current defaults; a `inactive(tick_id)` classmethod on each.
No owner contract change. The planner `no_actionable_proposal`, writeback `internal_only`, autonomy, and evaluation owner contracts are reused as-is.

## 5. Module Changes

1. `helios_v2/src/helios_v2/runtime/stages.py`: the `activated`/`inactive_id` fields + `inactive(...)` factories; the no-fire guard in each post-gate stage `run`; the `13`/`18`/`17` no-fire branches.
2. `helios_v2/src/helios_v2/composition/bridges.py`: the writeback bridge's governance-inactive guard; the autonomy and evaluation request/evidence bridges' no-fire request construction (marker anchors; no-action drive inputs; explicit no-fire evidence).

## 6. Migration Plan

1. All new fields default to the fired shape; fired-path construction and tests are unchanged.
2. The no-fire branches are reached only on `decision != "fire"`; no fired tick changes behavior.
3. The closure reuses the R28 internal-only owner outcomes; no new owner taxonomy unless an existing value does not fit (none expected).
4. The `RuntimeHandle.tick` carry seams already tolerate a no-fire tick (verified: `.get`/`getattr`).

## 7. Failure Modes and Constraints

1. No fabricated cognition: inactive results carry `activated=False` and `None` artifacts; the closure-tail markers are ids only.
2. The fired-path owners are never called on a no-fire tick; their invariants stay fail-fast for any direct misuse.
3. A no-fire tick still fails fast on a genuinely malformed closure (e.g. an inconsistent marker chain), through the existing owner/stage validation.
4. Continuation pressure and `18`/`24` continuity carry across a no-fire tick unchanged (the `09` continuation state and the autonomy stage's cross-tick fields are not reset).
5. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The no-fire outcome is visible in the stage results (`activated=False`), the planner `no_actionable_proposal`, the writeback `internal_only` record, the autonomy result, and the evaluation evidence — all existing contracts. The kernel's existing per-stage lifecycle events still fire for every stage (each stage runs and returns a result).

## 9. Validation Strategy

Network-free, deterministic.

1. `test_runtime_stage_chain.py` (extend): drive a stage chain to a `no_fire` gate (e.g. conscious content not committed, or a high `workload_pressure` snapshot) and assert each post-gate stage returns an inactive result (`activated=False`, `None` artifacts) and the closure tail produces `no_actionable_proposal` + an `internal_only` writeback + an autonomy result + an evaluation artifact, with no raise.
2. `test_runtime_composition.py` (extend):
   - A no-fire tick (constructed via a high cpu/memory interoceptive sampler, R53) completes and returns a `RuntimeTickResult`; the post-gate stage results are inactive; the writeback records `internal_only`; autonomy and evaluation ran.
   - Continuation pressure / continuity carry: a no-fire tick followed by a fire-able tick shows the carried state (the no-fire tick did not reset it).
   - The fired path is unchanged: an ordinary fired tick has `activated=True` everywhere and the existing artifacts.
   - The R53 high-load end-to-end test can now assert a completed no-fire tick (lifting the R53 firing-window constraint for the load case).
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_stage_chain.py -q
```
