# Requirement 49 - Thought-directed retrieval recall intent (design)

## 1. Design Overview

R49 feeds the prior tick's `11` internal-thought `MemoryHandoffDirective` into the current tick's `10` directed-retrieval request under the semantic-memory assembly, so the thought owner's saved recall intent actually steers retrieval. It changes no contract and no owner engine; it mirrors the cross-tick carry mechanism R32 (consequence claim) and R42 (continuity state) already established.

Three additive, opt-in pieces, all owner-neutral composition glue:

1. A holder field carrying the prior tick's `11` recall directive (`recall_intent` + `selected_memory_refs`), captured after each tick.
2. A capture seam in `RuntimeHandle.tick` that reads the `11` stage result's `memory_handoff` (when saved for next tick) into the holder, mirroring `_carry_consequence_claim`.
3. A de-shimmed directed-retrieval request bridge that, when the holder carries a directive, builds the `10` `RetrievalRequest` with the carried `recall_intent`/`selected_memory_refs`; otherwise falls back to the real `09` `compact_stimuli` exactly as today.

The `10` query-planning path already consumes `recall_intent`/`selected_memory_refs`/`compact_stimuli` from the request (verified in `_build_query_text`), so no `10` change is needed — only what composition feeds in.

## 2. Current State and Gap

Current state (verified in code):

1. `FirstVersionDirectedRetrievalRequestBridge.build_request` sets `recall_intent="remember runtime chain context"` (constant) and `selected_memory_refs=(f"memory:runtime:{tick_id}",)` (fabricated), while `compact_stimuli` comes from the real `09` gate result.
2. The `11` owner publishes `ThoughtCycleResult.memory_handoff: MemoryHandoffDirective | None` with `recall_intent` + `selected_memory_refs` + `saved_for_next_tick` when continuation is requested (verified in `internal_thought/engine.py` `_derive_thought_judgment`).
3. `10` runs before `11` in `CANONICAL_STAGE_ORDER`, so the current tick's `11` handoff cannot feed the current tick's `10`; it must feed the *next* tick — a cross-tick carry.
4. `RuntimeHandle.tick` already captures cross-tick state after the tick (`_carry_consequence_claim`, `_persist_experience`, `_checkpoint_continuity`); `TimelineViewHolder` already carries `prior_consequence_claim`. The exact carry pattern exists.
5. `RetrievalRequest.__post_init__` requires at least one of `compact_stimuli`/`recall_intent`/`selected_memory_refs`; `compact_stimuli` is always real from `09`, so the absence fallback is always valid.

Gap: the `11` recall directive is discarded; `10` retrieves against a constant string instead of the thought owner's expressed intent.

## 3. Target Architecture

### 3.1 Prior-thought recall-directive holder (composition glue)

A small holder carries the prior tick's directive (owner-neutral, like `TimelineViewHolder`):

```
@dataclass
class PriorThoughtRecallHolder:
    """Carries the prior tick's 11 MemoryHandoffDirective projection for the next tick's 10 request.
    Owner-neutral: transports 11-owned values verbatim; computes no retrieval policy."""
    recall_intent: str | None = None
    selected_memory_refs: tuple[str, ...] = ()
```

(Alternatively the existing `TimelineViewHolder` could gain these fields; the design uses a dedicated holder to keep the recall-carry concern separate from the timeline/claim carry. Either is acceptable; tasks pick a dedicated holder.)

### 3.2 Post-tick capture seam (RuntimeHandle)

`RuntimeHandle.tick` gains `_carry_recall_directive(result)`, mirroring `_carry_consequence_claim`:

```
def _carry_recall_directive(self, result):
    if self.prior_thought_recall_holder is None:
        return
    stage_result = result.stage_results.get("internal_thought_loop_owner")
    handoff = getattr(getattr(stage_result, "result", None), "memory_handoff", None)
    if handoff is not None and handoff.saved_for_next_tick:
        self.prior_thought_recall_holder.recall_intent = handoff.recall_intent
        self.prior_thought_recall_holder.selected_memory_refs = handoff.selected_memory_refs
    else:
        self.prior_thought_recall_holder.recall_intent = None
        self.prior_thought_recall_holder.selected_memory_refs = ()
```

It reads only the `11` owner's already-published `memory_handoff` and copies its values; it computes nothing. When `11` did not run (gate did not fire, no stage result) or saved no directive, the holder is cleared, yielding the absence fallback next tick.

### 3.3 De-shimmed directed-retrieval request bridge (composition glue)

A `ThoughtDirectedRetrievalRequestBridge` consumes the holder:

```
@dataclass
class ThoughtDirectedRetrievalRequestBridge:
    holder: PriorThoughtRecallHolder
    def build_request(self, frame, thought_gating_result) -> RetrievalRequest:
        tick_id = frame.tick_id
        carried_intent = self.holder.recall_intent
        carried_refs = self.holder.selected_memory_refs
        return RetrievalRequest(
            request_id=f"retrieval-request:runtime:{tick_id}",
            source_gate_result_id=thought_gating_result.result.result_id,
            source_continuation_active=thought_gating_result.continuation_state.active,
            compact_stimuli=thought_gating_result.result.selected_stimuli,   # always real from 09
            recall_intent=carried_intent,                                    # 11-owned, or None
            selected_memory_refs=carried_refs,                               # 11-owned, or ()
            target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
            limit=2,
            tick_id=tick_id,
        )
```

When the holder carries a directive, `recall_intent` is the `11`-owned string and the `10` path uses it (its `_build_query_text` already prioritizes `recall_intent`). When the holder is empty, `recall_intent=None` and `selected_memory_refs=()`, so the request is driven by `compact_stimuli` (always non-empty from `09` on a fired tick) — the defined absence fallback, exactly today's stimulus-driven behavior minus the fabricated constant.

Note on request validity: a fired tick always has a `09` gate result whose `selected_stimuli` is the real `compact_stimuli`; the existing shim already relies on this. If `compact_stimuli` is empty AND there is no carried intent, the `RetrievalRequest` contract would reject the request — but `10` only runs on a fired gate, and the fired-gate path carries selected stimuli, so this is the same precondition the current shim depends on. No new failure surface.

### 3.4 Opt-in selection in assembly

`assemble_runtime` selects the directed-retrieval request bridge on the existing `semantic_memory_enabled` flag:

1. semantic-memory assembly → `ThoughtDirectedRetrievalRequestBridge(holder=prior_thought_recall_holder)`, and the holder is captured each tick.
2. default / recency-only / non-semantic → `FirstVersionDirectedRetrievalRequestBridge` (unchanged constant behavior), no holder capture.

No new public assembly flag; the recall-intent carry only matters once the real LLM cognition chain is active, which is the semantic opt-in.

### 3.5 Default rollout

Default-off. The default assembly and any assembly without the semantic opt-in keep the constant `recall_intent` and fabricated `selected_memory_refs`. Only the semantic-memory assembly carries the real `11` recall intent.

## 4. Data Structures

No new contract. `RetrievalRequest`, `RetrievalQueryPlan`, `ThoughtWindowBundle`, `MemoryHandoffDirective` are unchanged. New composition-internal types:

1. `PriorThoughtRecallHolder` (in `helios_v2.composition.bridges`) — owner-neutral carry holder for the prior `11` directive's `recall_intent`/`selected_memory_refs`.
2. `ThoughtDirectedRetrievalRequestBridge` (in `helios_v2.composition.bridges`) — de-shimmed request bridge consuming the holder, with the stimulus-driven absence fallback.

## 5. Module Changes

1. `helios_v2/src/helios_v2/composition/bridges.py`: add `PriorThoughtRecallHolder` and `ThoughtDirectedRetrievalRequestBridge`.
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: under `semantic_memory_enabled`, construct the holder, wire `ThoughtDirectedRetrievalRequestBridge(holder=...)` into the `DirectedRetrievalRuntimeStage`, add a `prior_thought_recall_holder` field to `RuntimeHandle`, and call `_carry_recall_directive(result)` in `tick` after the existing carries. Default keeps `FirstVersionDirectedRetrievalRequestBridge`.

## 6. Migration Plan

1. All new code is additive composition glue. The default request bridge is unchanged and remains the default.
2. No contract change, so `10` query planning consumes the request exactly as before — only `recall_intent`/`selected_memory_refs` values change when the opt-in is on.
3. No stage-order change; the carry is a post-tick capture into a holder, like the consequence-claim carry.
4. The semantic-memory assembly automatically gains the recall carry (same `semantic_memory_enabled` trigger), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. First tick (holder empty): absence fallback — `recall_intent=None`, `selected_memory_refs=()`, driven by `compact_stimuli`. Defined, not a failure.
2. Tick where the gate did not fire (no `11` stage result): the capture clears the holder, so the next fired tick uses the absence fallback. Defined.
3. Tick where `11` ran but did not request continuation (no saved handoff): the capture clears the holder. Defined.
4. The carried value is the `11` owner's already-validated `MemoryHandoffDirective` projection, so no malformed-state surface is introduced.
5. Owner-neutral glue only: composition transports `11`-owned values and computes no retrieval policy; `10` and `11` engines are unchanged.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The recall intent travels through the existing `RetrievalRequest.recall_intent`/`selected_memory_refs` and surfaces in the `RetrievalQueryPlan.query_text`/`query_source` and the `ThoughtWindowBundle.selection_trace`. No emission is added.

## 9. Validation Strategy

Network-free, deterministic.

1. `test_runtime_composition.py` (extend):
   - semantic-memory assembly, two consecutive ticks where the first tick's `11` continues and saves a handoff: assert the second tick's `10` request/plan carries the prior directive's `recall_intent` (read the directed-retrieval stage result's plan `query_text`/`query_source`, and/or expose the request), not the constant string.
   - first tick (no prior handoff): the `10` request is driven by `compact_stimuli`; `recall_intent` is absent/empty; the bundle still assembles.
   - a tick where `11` did not continue (no saved handoff) clears the carry, so the following tick falls back to stimuli.
   - default assembly: the `10` request keeps the constant `recall_intent="remember runtime chain context"` and fabricated `selected_memory_refs` (constant bridge); existing tests unmodified.
   - determinism: identical prior handoff + stimuli → identical `10` request.
2. A focused unit test for `ThoughtDirectedRetrievalRequestBridge` with a seeded holder (carries the intent) and an empty holder (stimulus fallback) may live in the composition test module.
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_composition.py -q
```
