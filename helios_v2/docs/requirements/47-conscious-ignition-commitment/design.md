# Requirement 47 - Conscious ignition commitment (design)

## 1. Design Overview

R47 makes the `08` reportable conscious-content owner ignite a single winner into reportable content under the semantic-memory assembly, without changing any contract, the engine, or the semantic renderer. It is the next P3 mid-chain de-shim after `07` (R46), and it reuses an injection seam that already exists.

One additive, opt-in piece, owned by `helios_v2.consciousness`:

1. An owner-owned `IgnitionFocalSelectionPolicy` implementing the existing private `_FocalSelectionPolicy` protocol. Instead of the count-based default (`>1 retained → no_commit/semantic_conflict_unresolved`), it ignites the single highest-`workspace_score_hint` retained candidate as focal and demotes the rest to bounded supporting context. The genuinely empty (`insufficient_commitment_signal`) and non-reportable (`context_not_reportable`) no-commit cases are preserved.

Composition selects the commitment path bound to this policy under the existing `semantic_memory_enabled` flag (the same opt-in that makes `07`'s score real), reusing the already-present `FirstVersionConsciousCommitmentPath(focal_selection_policy=...)` constructor field. Default and non-semantic assemblies keep the count-based policy.

Everything stays within the existing `ConsciousState` / `ReportableConsciousContent` / `SupportingContextItem` contracts and the existing `_MaterialSummarySemanticCommitmentRenderer`. Only which retained candidate becomes focal — and the fact that multiplicity is no longer conflict — changes.

## 2. Current State and Gap

Current state (verified in code):

1. `ConsciousnessEngine` delegates commitment to an injected `ConsciousCommitmentPath`; in composition that is `FirstVersionConsciousCommitmentPath`, whose `focal_selection_policy` field defaults to `_RetainedWorkingStateSelectionPolicy`.
2. `_RetainedWorkingStateSelectionPolicy.decide` (engine.py): zero retained → `no_commit/insufficient_commitment_signal`; exactly one retained → commit it focal (others become supporting context); **more than one retained → `no_commit/semantic_conflict_unresolved`**.
3. R46 made the working state a bounded top-K (K=3) with real `workspace_score_hint`. So most ticks now retain >1 candidate, and rule 3 makes `08` declare conflict / no-commit almost every tick — the opposite of ignition.
4. The semantic renderer (`_MaterialSummarySemanticCommitmentRenderer`) and every `ConsciousState` invariant already accept exactly the focal+supporting shape ignition produces; the constructor already accepts an injected `focal_selection_policy`.

Gap: the focal-selection policy reads multiplicity as conflict instead of igniting the dominant winner. The real winner signal (`workspace_score_hint`) and the injection seam both already exist and are unused for ignition.

## 3. Target Architecture

### 3.1 Owner-owned ignition focal selection (in `helios_v2.consciousness`)

`08` stays the commitment owner. A new owner-owned policy implements the existing `_FocalSelectionPolicy` protocol:

```
@dataclass
class IgnitionFocalSelectionPolicy(_FocalSelectionPolicy):
    """Global-workspace winner-take-all: ignite the highest-scoring retained candidate."""
    def decide(self, candidate_set, working_state, material_map):
        retained = tuple(material_map[cid] for cid in working_state.retained_candidate_ids)
        if not retained:
            return _FocalSelectionOutcome("no_commit", None, (), "insufficient_commitment_signal")
        # Winner-take-all by the real R46 competition score; deterministic tie-break by candidate id.
        ranked = sorted(
            retained,
            key=lambda m: (-(m.workspace_score_hint if m.workspace_score_hint is not None else 0.0),
                           m.source_workspace_candidate_id),
        )
        focal_material = ranked[0]
        if not _normalize_summary(focal_material.material_summary):
            return _FocalSelectionOutcome("no_commit", None, (), "context_not_reportable")
        supporting = ranked[1:]                              # losers become supporting context
        return _FocalSelectionOutcome("committed", focal_material, tuple(supporting), None)
```

Key differences from the count-based default:
1. `>1 retained` no longer returns `no_commit`; it ignites `ranked[0]` and passes the rest as supporting materials.
2. Supporting materials are the ranked losers (the engine/renderer already bound them to `max_supporting_context_items` and drop the focal's own candidate).
3. The empty-retained and empty-summary no-commit outcomes are preserved verbatim.

The renderer and engine are unchanged: the engine's `_validate_supporting_context` already trims/validates against `max_supporting_context_items`, never duplicates the focal candidate, and preserves provenance. Ignition produces exactly the shape they already accept.

Note on the supporting bound: the selection policy may pass more supporting materials than `max_supporting_context_items`; the downstream renderer/validation path already enforces the cap. The policy orders them by descending score so the cap keeps the most salient losers. (Confirmed against the existing `_validate_supporting_context` and renderer behavior; if the renderer does not itself trim, the policy will pre-trim to the configured cap to stay within the invariant — see Validation.)

### 3.2 Opt-in selection in assembly

`assemble_runtime` selects the commitment path on the existing `semantic_memory_enabled` flag, the same trigger as R45/R46:

1. semantic-memory assembly → `FirstVersionConsciousCommitmentPath(focal_selection_policy=IgnitionFocalSelectionPolicy())`.
2. default / recency-only / non-semantic → `FirstVersionConsciousCommitmentPath()` (the count-based `_RetainedWorkingStateSelectionPolicy`, unchanged).

No new public assembly flag; the ignition winner signal only matters once `07` is real, which is the same opt-in.

### 3.3 Default rollout

Default-off. The default assembly and any assembly without the semantic opt-in keep the count-based policy and its `semantic_conflict_unresolved`-on-multiplicity behavior. Only the semantic-memory assembly gains ignition.

## 4. Data Structures

No new contract. `ConsciousState`, `ReportableConsciousContent`, `SupportingContextItem`, `_FocalSelectionOutcome` are unchanged. New type:

1. `IgnitionFocalSelectionPolicy` (in `helios_v2.consciousness.engine`, exported from the package) — implements the existing `_FocalSelectionPolicy` protocol; owns the winner-take-all ignition selection.

## 5. Module Changes

1. `helios_v2/src/helios_v2/consciousness/engine.py`: add `IgnitionFocalSelectionPolicy` implementing `_FocalSelectionPolicy` (the ignition selection lives here, alongside `_RetainedWorkingStateSelectionPolicy`). If the renderer does not trim supporting materials to the cap, the policy pre-trims by descending score.
2. `helios_v2/src/helios_v2/consciousness/__init__.py`: export `IgnitionFocalSelectionPolicy`.
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: under `semantic_memory_enabled`, construct `FirstVersionConsciousCommitmentPath(focal_selection_policy=IgnitionFocalSelectionPolicy())`; otherwise keep the default. Import the policy from `helios_v2.consciousness`.

## 6. Migration Plan

1. All new code is additive and owner-owned. The default count-based policy is unchanged and remains the default.
2. No contract changes to `ConsciousState`/`ReportableConsciousContent`/`SupportingContextItem`, so thought gating and prompt assembly consume the conscious state exactly as before — only which content is focal (and that multiplicity now commits) changes when the opt-in is on.
3. No stage-order change; `08` is the same stage with a different injected focal-selection policy.
4. The semantic-memory assembly automatically gains ignition (same `semantic_memory_enabled` trigger as R45/R46), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. Zero retained candidates: `no_commit/insufficient_commitment_signal` (defined; an empty attention focus is nothing to report).
2. Ignited focal with empty normalized summary: `no_commit/context_not_reportable` (defined).
3. The ignited focal and supporting context always satisfy the engine's existing validation (focal references a current-cycle material; supporting items reference current-cycle materials, never duplicate the focal candidate, never exceed `max_supporting_context_items`).
4. `workspace_score_hint == None` on a material: treated as score `0.0` in ranking (a defined floor), so a scored candidate always outranks an unscored one.
5. The ignition policy emits no `semantic_conflict_unresolved`; that taxonomy value remains valid for a future genuine-conflict slice.
6. `08` imports no other owner for this change; composition injects the policy. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The commitment decision travels through the existing `ConsciousState` and the existing owner-private `_ConsciousCommitmentPathTrace` (`last_trace`). No emission is added in `08` or composition.

## 9. Validation Strategy

Network-free, deterministic.

1. `test_consciousness_engine.py` (extend):
   - `IgnitionFocalSelectionPolicy` with a multi-retained working state (differing `workspace_score_hint`): commits focal = highest-scoring retained candidate; conscious state is `committed`, not `no_commit`; losers become supporting context ordered by descending score and bounded by `max_supporting_context_items`; focal never duplicated in supporting.
   - deterministic tie-break: equal scores → smaller `source_workspace_candidate_id` ignites.
   - zero retained → `no_commit/insufficient_commitment_signal`.
   - ignited focal with empty summary → `no_commit/context_not_reportable`.
   - the policy passes the engine's full `commit_content` validation (run through `ConsciousnessEngine`).
   - determinism: identical inputs → identical focal + supporting.
2. `test_runtime_composition.py` (extend):
   - semantic-memory assembly: over several ticks where the working state retains >1 candidate, the conscious state is `committed` with focal content equal to the top-scored candidate (assert `commit_status == "committed"` and focal provenance), proving multiplicity no longer suppresses ignition.
   - default assembly: a constructed >1-retained working state still yields the count-based `no_commit/semantic_conflict_unresolved` (the constant path is unchanged).
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_consciousness_engine.py -q
```
