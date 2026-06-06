# Requirement 49 - Thought-directed retrieval recall intent

## 1. Background and Problem

The `10` directed-retrieval owner's query-planning path is real (it builds query text and tiered selection from the explicit `RetrievalRequest`), and its candidate providers are real under persistence/semantic memory (R33/R34). But what composition *feeds into* the `RetrievalRequest` is still partly shim. In `FirstVersionDirectedRetrievalRequestBridge`:

1. `recall_intent = "remember runtime chain context"` — a fixed constant string every tick;
2. `selected_memory_refs = (f"memory:runtime:{tick_id}",)` — a fabricated reference that points at nothing real;

while `compact_stimuli` (from the `09` gate result), `source_gate_result_id`, and `source_continuation_active` are real.

This is the single most important `10` shim because of what `recall_intent` is supposed to be. In `brain.mmd` and the locked philosophy (`ARCHITECTURE_PHILOSOPHY.zh-CN.md` §5.3: "上一轮 thought owner 指定的 recall intent 会真实影响后续 directed retrieval"), directed retrieval is *memory-guided*: when the `11` internal-thought owner continues thinking, it publishes a `MemoryHandoffDirective` (`recall_intent` + `selected_memory_refs`, with `saved_for_next_tick=True`) that says "this is what I want to recall next tick to keep this line of thought going". Today that handoff is computed by `11` and then **discarded** — the next tick's `10` ignores it and uses the constant string instead. So the thought owner's expressed recall intent has no effect on what is actually retrieved, breaking the memory-guided-maintenance loop that distinguishes directed retrieval from a fixed context fetch.

The `11` owner already produces the real directive (verified: `ThoughtCycleResult.memory_handoff` carries `recall_intent` and `selected_memory_refs` when continuation is requested). The missing piece is a cross-tick carry from the prior tick's `11` handoff into the current tick's `10` request — exactly the carry mechanism R32 established for the consequence claim and R42 for continuity state.

## 2. Goal

When thought-directed retrieval is enabled, the `10` directed-retrieval request's `recall_intent` and `selected_memory_refs` come from the prior tick's `11` internal-thought `MemoryHandoffDirective` (when the thought owner saved one for the next tick), so a line of thought the system chose to continue actually steers what memory it retrieves next tick; when there is no saved handoff (the first tick, or a tick where thought did not continue), the request falls back to the real `09` `compact_stimuli` exactly as today; the carry is owner-neutral (composition transports the `11`-owned directive verbatim, computes no retrieval policy), no contract changes, and the default and shim assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Cross-tick recall-intent carry
1. Under the semantic-memory assembly, composition must carry the prior tick's `11` internal-thought `MemoryHandoffDirective` forward and feed its `recall_intent` and `selected_memory_refs` into the current tick's `10` `RetrievalRequest`, when that prior directive was saved for the next tick (`saved_for_next_tick=True`).
2. The carry must be owner-neutral: composition captures the `11`-published directive verbatim after the tick and transports it to the next tick's request bridge. It must not synthesize, rewrite, or reinterpret the recall intent or the memory refs; those are `11`-owned values.
3. The carried `recall_intent` and `selected_memory_refs` must reach the `10` owner through the existing `RetrievalRequest` contract unchanged, so the `10` query-planning path consumes them through the existing boundary.

### 3.2 Defined absence fallback to real stimuli
1. When there is no carried handoff (the first tick, a tick where `11` did not run because the gate did not fire, or a tick where `11` did not request continuation and saved no directive), the `10` request must use the real `09` `compact_stimuli` as the retrieval demand exactly as today, with `recall_intent` absent (or empty) and `selected_memory_refs` empty.
2. This absence fallback is a defined behavior, not a degraded path: a tick with no continued line of thought legitimately has no prior recall intent, and retrieval is then driven by the current stimuli. The request must remain valid (the `RetrievalRequest` contract requires at least one of `compact_stimuli`, `recall_intent`, or `selected_memory_refs`, and `compact_stimuli` is always real from `09`).

### 3.3 Real downstream effect
1. The change must be observable: on a tick following a `11` continuation that saved a handoff, the `10` request's `recall_intent` must equal the `11` directive's `recall_intent` (not the constant string), and the resulting query plan's `query_text`/`query_source` must reflect it; on a tick with no prior handoff, the request must carry no recall intent and be driven by `compact_stimuli`.
2. The carried `selected_memory_refs` must flow into the query plan exactly as the `10` path already handles explicit memory refs (it already incorporates them into `query_text` and `query_source`).

### 3.4 Opt-in rollout and fail-fast
1. Thought-directed recall intent must activate on the existing semantic-memory opt-in (durable store and embedding gateway both present), consistent with R45-R48 — it builds on the real cognition chain those slices established. The default assembly and any assembly without the semantic opt-in must keep the constant `recall_intent`/fabricated `selected_memory_refs` and behave exactly as today.
2. No new degraded path: a carried directive is used when present; its absence is the defined stimulus-driven fallback. Malformed prior state is impossible because the carried value is the `11` owner's already-validated `MemoryHandoffDirective` projection.

## 4. Non-Functional Requirements

1. Performance: the carry is one read of the prior tick's published thought result plus one request assembly per tick; it must not change the runtime stage execution structure.
2. Reliability and fault tolerance: for identical prior-tick handoffs and identical current stimuli, the `10` request must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. The recall intent travels only through the existing `RetrievalRequest` and `RetrievalQueryPlan` contracts.
4. Compatibility and migration: the carry holder, the capture seam, and the de-shimmed request bridge are additive and opt-in. The default assembly keeps its current `10` request behavior; existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The recall-intent carry must be owner-neutral composition glue, mirroring the R32 consequence-claim carry and the R42 continuity carry: a holder field, a post-tick capture in `RuntimeHandle.tick`, and a request bridge that reads the carried directive. It must not move retrieval-planning policy out of `10` or thought-handoff ownership out of `11`.
2. The `10` owner and its `RetrievalRequest`/`RetrievalQueryPlan`/`ThoughtWindowBundle` contracts are unchanged; only the values fed into the request change when enabled.
3. The `11` owner is unchanged; composition only reads its already-published `memory_handoff`.
4. No degraded or fallback path beyond the defined stimulus-driven absence behavior. The request stays valid because `compact_stimuli` is always real from `09`.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (a holder for the prior-tick `11` recall directive, and a de-shimmed directed-retrieval request bridge that consumes it with the stimulus-driven absence fallback)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (capture the `11` `memory_handoff` into the holder after each tick, mirroring the consequence-claim capture; select the de-shimmed request bridge under the semantic opt-in)
3. `helios_v2/tests/test_runtime_composition.py` (extend: a tick after a saved `11` handoff carries the real recall intent into the `10` request/plan; first tick / no-handoff falls back to stimuli; default keeps the constant)
4. `helios_v2/docs/requirements/index.md`
5. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
6. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
7. `helios_v2/docs/OWNER_GUIDE.md`
8. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
9. `helios_v2/docs/PROGRESS_FLOW.en.md`
10. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, on a tick following a `11` continuation that saved a `MemoryHandoffDirective`, the `10` `RetrievalRequest.recall_intent` equals the prior directive's `recall_intent` (not the constant `"remember runtime chain context"`), and `selected_memory_refs` equals the directive's refs; the resulting query plan's `query_text`/`query_source` reflect them.
2. On the first tick or a tick with no saved prior handoff, the `10` request carries no recall intent (absent/empty) and empty `selected_memory_refs`, and is driven by the real `09` `compact_stimuli`; the request is valid and the bundle assembles.
3. The carry is owner-neutral: composition transports the `11`-owned directive verbatim and computes no retrieval policy; `10` and `11` contracts are unchanged.
4. The default assembly and non-semantic assemblies keep the constant `recall_intent` and fabricated `selected_memory_refs`; their existing tests pass unmodified.
5. The recall intent is deterministic for identical prior handoff + stimuli; no contract changes; the value flows through the existing `RetrievalRequest`/`RetrievalQueryPlan`.
6. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R49 de-shims the `10` request's recall intent and memory refs only. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Deeper recall-intent shaping in the `10` owner (tier selection or limit derived from the recall intent's content), once richer intent semantics exist.
2. Connecting the recall intent to long-horizon continuity (`18`/`24` threads), so a continuity thread's focus steers retrieval across many ticks (wave_B).
3. Real `compact_stimuli` provenance from a de-shimmed `02`/`03` projection rather than the gate result's selected-stimulus summaries.
4. P5 learning of how strongly recall intent vs current stimuli weight the query plan.

None of these may be smuggled into this slice. R49 changes only the source of `recall_intent`/`selected_memory_refs` fed into the `10` request (the prior `11` handoff, with a stimulus-driven absence fallback), introduces no contract change, and adds no default-on behavior.
