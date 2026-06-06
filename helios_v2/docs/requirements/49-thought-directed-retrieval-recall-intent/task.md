# Requirement 49 - Thought-directed retrieval recall intent (tasks)

## 1. Task Breakdown

### Task 1 - Recall-directive holder + de-shimmed request bridge (composition glue)
Add `PriorThoughtRecallHolder` (owner-neutral carry holder for the prior `11` directive's `recall_intent`/`selected_memory_refs`) and `ThoughtDirectedRetrievalRequestBridge` (consumes the holder; when it carries a directive, builds the `10` `RetrievalRequest` with the carried `recall_intent`/`selected_memory_refs`; otherwise falls back to the real `09` `compact_stimuli` with `recall_intent=None`/empty refs) to `composition/bridges.py`. Both are owner-neutral; neither computes retrieval policy.

### Task 2 - Capture seam + opt-in wiring (RuntimeHandle / assembly)
Add a `prior_thought_recall_holder` field to `RuntimeHandle` and a `_carry_recall_directive(result)` method that reads the `11` stage result's `memory_handoff` (when `saved_for_next_tick`) into the holder, clearing it otherwise; call it in `tick` after the existing carries. In `assemble_runtime`, under `semantic_memory_enabled`, construct the holder, wire `ThoughtDirectedRetrievalRequestBridge(holder=...)` into the `DirectedRetrievalRuntimeStage`, and pass the holder into the `RuntimeHandle`. Default/non-semantic keep `FirstVersionDirectedRetrievalRequestBridge` and no holder.

### Task 3 - Validation
Extend the composition test module per the design validation strategy. Keep the suite network-free and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R49 row; `10` note), `ARCHITECTURE_BOUNDARIES.md` (record the `10` recall-intent de-shim as migration-state item), `BRAIN_ARCHITECTURE_COMPARISON.md` (`10` now memory-guided by the real `11` recall intent), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`10` state/next-step; update last-synced + baseline), and both `PROGRESS_FLOW` maps (relabel `10`; update last-synced line and baseline count).

## 2. Dependencies

1. Task 1 depends conceptually on the `11` owner already publishing `memory_handoff` (it does) and R32/R42 establishing the carry pattern.
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (holder + request bridge) - the carry mechanism + de-shimmed request.
2. Task 2 (capture seam + wiring) - activates the carry end to end.
3. Task 3 (validation) - prove real recall intent steers retrieval; absence fallback to stimuli; default unchanged.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q` (recall intent carried from prior `11`; first-tick/no-handoff stimulus fallback; default keeps the constant).
2. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. Under the semantic assembly, a tick after a saved `11` handoff carries the directive's `recall_intent`/`selected_memory_refs` into the `10` request/plan (not the constant string).
2. The first tick / a no-handoff tick falls back to the real `09` `compact_stimuli` with no recall intent; the request is valid and the bundle assembles.
3. The carry is owner-neutral; `10` and `11` contracts/engines are unchanged; no contract change.
4. The default and non-semantic assemblies keep the constant `recall_intent`/fabricated refs; existing tests pass unmodified.
5. Deterministic for identical prior handoff + stimuli; full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set.
