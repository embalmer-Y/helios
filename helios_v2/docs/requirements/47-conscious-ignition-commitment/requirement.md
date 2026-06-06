# Requirement 47 - Conscious ignition commitment (global-workspace winner-take-all)

## 1. Background and Problem

With R46 the `07` workspace owner is a real attention bottleneck: it scores candidates from the real `06` `priority_hint` + real `05` feeling salience and retains a bounded top-K subset (first-version K=3) in the working state. The next mid-chain shim is the `08` reportable conscious-content owner's commitment decision.

`08` is shimmed at its focal-selection policy. The injected default `_RetainedWorkingStateSelectionPolicy` decides what becomes reportable conscious content purely from the *count* of retained working-state candidates:

1. zero retained → `no_commit` (`insufficient_commitment_signal`);
2. exactly one retained → commit that one as focal;
3. **more than one retained → `no_commit` (`semantic_conflict_unresolved`)**.

Rule 3 is the problem. Now that R46 holds a bounded top-K (K=3) working state by design, `08` will see more than one retained candidate on most ticks and therefore declare "semantic conflict, no commit" almost every tick — the system would rarely become consciously aware of anything once attention legitimately holds several items. This inverts the intended behavior: the workspace bottleneck narrowing to a few items should make ignition *more* focused, not suppress it.

In `brain.mmd` and global-workspace theory, reportable consciousness is an *ignition*: when multiple candidates compete in the workspace, the single dominant winner is ignited into globally reportable content while the others remain as (non-focal) context — it is winner-take-all, not "freeze whenever there is more than one candidate". The real signal to choose the winner now exists: the R46 `workspace_score_hint` is a real competition score. So `08` should ignite the highest-scoring retained candidate as focal and demote the rest to supporting context, rather than reading multiplicity as conflict.

The `08` owner, its `ConsciousState`/`ReportableConsciousContent` contracts, its provenance validation, its semantic renderer, and the injectable `focal_selection_policy` seam are all real today; only the default count-based selection policy is the shim.

## 2. Goal

When conscious ignition is enabled, the `08` owner selects reportable focal content by igniting the single highest-scoring retained working-state candidate (global-workspace winner-take-all) and demoting the remaining retained candidates to bounded supporting context, instead of declaring `semantic_conflict_unresolved` whenever more than one candidate is retained; the `08` owner keeps sole ownership of the commitment policy through its existing injectable focal-selection seam, preserves every provenance and no-commit invariant it already enforces, changes no contract, and the default and shim assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Owner-owned ignition focal selection
1. The `08` owner must select focal content through an owner-owned focal-selection policy injected into the existing `focal_selection_policy` seam, not a composition concern. The policy must live in `helios_v2.consciousness`.
2. When one or more candidates are retained in the working state, the policy must ignite the single candidate with the highest real `workspace_score_hint` as the focal conscious content (winner-take-all). Ties must be broken deterministically (for example by `workspace_score_hint` descending then `source_workspace_candidate_id`).
3. The remaining retained candidates (those that lost ignition) must become supporting context, bounded by the owner config's `max_supporting_context_items`, ordered deterministically by descending score. Candidates beyond that bound are simply not published as supporting context (they remain in the candidate set as material; they are neither focal nor supporting this tick).
4. When zero candidates are retained, the policy must still produce `no_commit` with `insufficient_commitment_signal`, exactly as today (an empty attention focus is genuinely nothing to report).
5. When the ignited focal candidate has an empty normalized summary, the policy must produce `no_commit` with `context_not_reportable`, exactly as today (a focal item with nothing reportable is not committed).

### 3.2 Preserved invariants and contracts
1. The selection must continue to satisfy every existing `08` owner invariant: focal content references a material published this cycle; supporting items reference published materials; supporting items never duplicate the focal item or its workspace candidate; supporting context never exceeds `max_supporting_context_items`.
2. No contract may change. Ignition flows through the existing `ConsciousState` / `ReportableConsciousContent` / `SupportingContextItem` contracts and the existing semantic renderer; only which candidate becomes focal (and that multiplicity is no longer treated as conflict) changes.
3. The `semantic_conflict_unresolved` no-commit reason must remain a valid part of the taxonomy for future genuine-conflict semantics, but the ignition policy must not emit it merely because more than one candidate was retained.

### 3.3 Real downstream effect
1. The change must be observable: given a bounded top-K (>1) working state with differing real `workspace_score_hint` values, the committed focal content must be the highest-scoring candidate, and the conscious state must be `committed` (not `no_commit/semantic_conflict_unresolved`); the focal choice must be attributable to the real score.
2. The committed focal content must flow unchanged to the downstream consumers (thought gating, prompt assembly) through the existing `ConsciousState` boundary.

### 3.4 Opt-in rollout and fail-fast
1. Conscious ignition must activate on the existing semantic-memory opt-in (durable store and embedding gateway both present), consistent with R45/R46 — because the real `workspace_score_hint` it ignites on only exists once `07` is de-shimmed under that same opt-in. The default assembly and any assembly without the semantic opt-in must keep the count-based first-version selection policy and behave exactly as today.
2. The owner must continue to fail fast on its existing invariants. No new degraded or fallback path is introduced; the no-commit outcomes in 3.1.4 and 3.1.5 are defined results, not fallbacks.

## 4. Non-Functional Requirements

1. Performance: ignition is one bounded pass plus one bounded sort over the retained candidates per tick; it must not change the runtime stage execution structure.
2. Reliability and fault tolerance: for identical workspace outputs and identical materials, the ignited focal choice and supporting context must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Commitment facts travel only through the existing consciousness contracts and the existing owner-private trace.
4. Compatibility and migration: the ignition policy and its wiring are additive and opt-in. The default assembly and the non-semantic assemblies keep their current `08` behavior; existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The `08` owner must stay the sole owner of the commitment policy. The ignition focal-selection policy lives in `helios_v2.consciousness` and is injected through the existing `focal_selection_policy` seam; composition selects it but holds no commitment policy.
2. The ignition policy must not change the semantic renderer, the engine, or any contract. It only changes which retained candidate is focal and stops treating multiplicity as conflict.
3. The ignition policy must preserve all existing provenance and bound invariants and must keep the existing no-commit outcomes for the genuinely empty / non-reportable cases.
4. No degraded or fallback path: the owner keeps failing fast on its existing invariants.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/consciousness/engine.py` (an owner-owned ignition focal-selection policy implementing the existing `_FocalSelectionPolicy` protocol)
2. `helios_v2/src/helios_v2/consciousness/__init__.py` (export the ignition policy and a public constructor for the commitment path bound to it, if needed for composition)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in selection of the ignition-backed commitment path under the semantic-memory opt-in; the constant count-based path otherwise)
4. `helios_v2/tests/test_consciousness_engine.py` (extend: ignition picks the top-scoring candidate; multiplicity no longer means no-commit; supporting context bounded/ordered; zero-retained and empty-summary still no-commit; deterministic)
5. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly commits focal content on a multi-retained working state; default keeps count-based behavior)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
9. `helios_v2/docs/OWNER_GUIDE.md`
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. With conscious ignition enabled and a bounded top-K (>1) working state, the `08` owner commits focal content equal to the highest `workspace_score_hint` retained candidate (deterministic tie-break), and the conscious state is `committed`, not `no_commit/semantic_conflict_unresolved`.
2. The losing retained candidates become supporting context, bounded by `max_supporting_context_items` and ordered by descending score; the focal item is never duplicated in supporting context.
3. Zero retained candidates still yields `no_commit/insufficient_commitment_signal`; an ignited focal with an empty normalized summary still yields `no_commit/context_not_reportable`.
4. Every existing `08` owner invariant still holds and still fails fast; no contract changes; the ignition decision flows through `ConsciousState`/`ReportableConsciousContent` unchanged.
5. Conscious ignition activates only on the semantic-memory opt-in; the default assembly and non-semantic assemblies keep the count-based first-version policy, and their existing tests pass unmodified.
6. The `semantic_conflict_unresolved` taxonomy value remains available for future genuine-conflict semantics but is not emitted merely for retained multiplicity under ignition.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R47 de-shims the focal-selection decision only. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Genuine semantic-conflict detection (a real `semantic_conflict_unresolved`) when the top candidates are contradictory rather than merely multiple, using richer content semantics.
2. An LLM-backed semantic commitment renderer through the already-scaffolded owner-controlled capability seam, replacing the deterministic summary renderer.
3. `P5` learning of the ignition threshold / tie-break weighting from real downstream consequence.
4. Affect- or continuity-weighted ignition once richer upstream signals land.

None of these may be smuggled into this slice. R47 changes only the focal-selection policy (ignite the top-scoring retained candidate; stop treating multiplicity as conflict), introduces no contract change, and adds no default-on behavior.
