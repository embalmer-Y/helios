# Requirement 57 - Owner Boundary Recovery of the Cognition-Derived Autonomy Drive Inputs

## 1. Design Overview

This is a behavior-preserving relocation plus a guard extension. The cognition-outcome to
autonomy-drive-input mapping currently lives in `FirstVersionAutonomyRequestBridge`
(`composition/bridges.py`): tuned pressure constants, the planner executed/blocked
classification, the retrieval-pull normalization, and an implicit dependence on the `18`
owner's `outward_drive >= 1.6` action threshold. The design introduces an `18`-owned input
contract `ProactiveCognitionFacts` (the raw facts composition is entitled to read) and an
`18`-owned projection `derive_drive_inputs(facts)` that produces the five existing drive-input
summaries. The composition bridge is reduced to: read raw facts from upstream stage results,
forward provenance ids, call the owner projection, assemble `ProactiveDriveRequest`.

No summary value, threshold, classification, or branch changes. `ProactiveDriveRequest` keeps
its shape. The autonomy disposition is byte-for-byte unchanged for every tick and assembly.

## 2. Current State and Gap

`FirstVersionAutonomyRequestBridge.build_request` today:

1. Branches on `internal_thought_result.activated` (fired vs no-fire R54 path).
2. Derives booleans: `has_action`, `planner_executed`/`planner_blocked` (via
   `_PLANNER_EXECUTED_STATUSES` / `_PLANNER_BLOCKED_STATUSES`), `wants_continue`,
   `has_self_revision`.
3. Maps them to pressure constants (`_ACTION_*`, `_CONTINUE_*`, `_CONCLUDED_*`,
   `_BASELINE_TEMPORAL_PRESSURE`, `_UNRESOLVED_/_RESOLVED_IDENTITY_PRESSURE`) chosen so the
   `18` owner's `outward_drive = continuation + temporal + identity >= 1.6` threshold is
   reachable for an action tick.
4. Normalizes retrieval pull as `(mid_term_hits + autobiographical_hits) / 4.0`.
5. Builds the five summaries + provenance ids into `ProactiveDriveRequest`.

Steps 2-4 are `18` owner cognitive policy mislocated in composition (the docstring itself
reverse-engineers the owner's 1.6 threshold). Step 1 (which upstream result to read, which
provenance id to forward) and the raw-fact extraction are legitimate assembly concerns.

Gap: the autonomy owner consumes already-semanticized pressures, while the cognition→pressure
policy that defines those pressures (and silently encodes the owner threshold) lives in glue.

## 3. Target Architecture

```
helios_v2.autonomy (18 owner)
  contracts.py
    ProactiveCognitionFacts            (new, owner-owned raw-fact input contract)
    ProactiveDriveRequest              (unchanged shape)
  engine.py
    OUTWARD_ACTION_THRESHOLD = 1.6     (owner-owned; the owner's own threshold constant)
    AutonomyDriveInputProjection       (new, owner-owned)
      derive_drive_inputs(facts) -> dict of the five summaries
    FirstVersionAutonomyPath           (unchanged; still reads the five summaries)
  __init__.py
    re-export ProactiveCognitionFacts, AutonomyDriveInputProjection

helios_v2.composition (assembly-only)
  bridges.py
    FirstVersionAutonomyRequestBridge
      build_request:
        - branch fired vs no-fire (assembly: which result/provenance to read)
        - extract ProactiveCognitionFacts from upstream stage results
        - summaries = owner_projection.derive_drive_inputs(facts)
        - assemble ProactiveDriveRequest(summaries + provenance ids)
      (no pressure constants, no planner classification, no normalization, no threshold)
```

The autonomy owner now owns: which planner statuses count as executed/blocked, how a hit
count becomes retrieval pull, what pressures each cognition outcome yields, and (already) the
1.6 action threshold. The bridge owns: reading the frame, forwarding provenance, and calling
the owner.

## 4. Data Structures

New owner-owned input contract (additive; does not replace `ProactiveDriveRequest`):

```python
@dataclass(frozen=True)
class ProactiveCognitionFacts:
    activated: bool                 # thought path fired this tick (R54 no-fire => False)
    has_action_proposal: bool       # fired tick produced an action proposal
    continuation_requested: bool    # thought owner asked to continue
    continuation_active: bool       # 09 continuation state active (carried)
    has_self_revision: bool         # thought owner proposed self-revision
    planner_status: str             # 13 planner status string (verbatim)
    retrieval_hit_count: int        # mid_term + autobiographical hits (>= 0)
```

Validation: `planner_status` non-empty; `retrieval_hit_count >= 0`. On a no-fire tick the
bridge constructs `ProactiveCognitionFacts(activated=False, ...)` with the remaining flags
False, `planner_status` from the real planner result, and `retrieval_hit_count = 0` (matching
the current no-fire branch which sets `retrieval_pull = 0.0`).

The five output summaries are unchanged in shape and content:
`continuation_summary={"continuation_pressure": x}`,
`retrieval_pull_summary={"retrieval_pull": x}`,
`temporal_pressure_summary={"temporal_pressure": x}`,
`identity_unresolved_summary={"identity_unresolved_pressure": x}`,
`outward_readiness_summary={"outward_ready": b, "externalization_blocked": b}`.

## 5. Module Changes

1. `autonomy/contracts.py`
   - Add `ProactiveCognitionFacts` with its validation.
2. `autonomy/engine.py`
   - Add the owner-owned action threshold constant `OUTWARD_ACTION_THRESHOLD = 1.6` (the value
     `FirstVersionAutonomyPath` already uses inline becomes a named owner constant reused by
     the projection's documentation; the path keeps using the same value).
   - Add `AutonomyDriveInputProjection` with `derive_drive_inputs(facts) -> dict[str, Mapping]`
     carrying the relocated pressure constants, planner classification, retrieval
     normalization, and the fired/no-fire mapping verbatim.
3. `autonomy/__init__.py`
   - Re-export `ProactiveCognitionFacts` and `AutonomyDriveInputProjection`.
4. `composition/bridges.py`
   - `FirstVersionAutonomyRequestBridge` holds a `AutonomyDriveInputProjection` instance,
     extracts `ProactiveCognitionFacts` from the upstream results (fired and no-fire branches),
     calls the projection, and assembles `ProactiveDriveRequest` with the returned summaries +
     provenance ids. All pressure constants, `_PLANNER_*` tuples, `/4.0`, and the 1.6 reference
     are deleted.
5. `tests/test_autonomy_engine.py`
   - Add focused projection tests (fact set -> summaries) covering each branch.
6. `tests/test_composition_owner_boundary_guard.py`
   - Extend the guard to also fail on an autonomy pressure-constant / threshold pattern under
     composition, with a positive control.

## 6. Migration Plan

1. Add `ProactiveCognitionFacts` to the owner contracts.
2. Add `OUTWARD_ACTION_THRESHOLD` + `AutonomyDriveInputProjection` to the owner engine,
   transcribing the bridge's mapping verbatim (same constants, classification, normalization,
   branching) so the projection is provably behavior-equivalent.
3. Re-export from the owner `__init__`.
4. Rewrite the composition bridge to extract facts, forward provenance, and call the
   projection; delete the relocated policy.
5. Add focused projection tests and the equivalence test for the bridge output.
6. Extend the owner-boundary guard.
7. Run the full suite; assert identical pass behavior (count grows only by added tests).
8. Update documentation truth in the same change set.

No rewrite of the autonomy decision path, no parallel path, no behavior toggle. The mapping
moves and the bridge repoints in the same change set.

## 7. Migration Plan Detail - Behavioral Equivalence Argument

Because the projection transcribes the bridge's exact constants, planner-status tuples,
`/4.0` normalization, fired/no-fire branching, and `[0,1]` rounding, `derive_drive_inputs`
returns the same summaries the bridge produced inline. The bridge then builds the same
`ProactiveDriveRequest`. `FirstVersionAutonomyPath` is untouched, so the same summaries yield
the same `outward_drive`, `proactive_action_requested`, disposition, deferred records, and
threads. Hence every assembly's autonomy output is byte-for-byte identical.

## 8. Failure Modes and Constraints

1. A missing/wrong-typed upstream stage result raises in the bridge's extraction step exactly
   as today (the existing stage-result access/typing). No new failure branch.
2. `ProactiveCognitionFacts` validation (non-empty planner status, non-negative hit count) is
   a fail-fast guard on the owner contract; the bridge always supplies valid facts, so this is
   defense-in-depth, not a runtime branch.
3. The projection is total and deterministic; every summary value is bounded into `[0,1]` and
   rounded exactly as before. No degraded mode, no fallback.
4. Default-on and unconditional: relocating a mapping does not change what the runtime
   computes, so there is no opt-in flag and every assembly is behavior-invariant.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. Neither the
new owner projection/contract nor the guard extension uses `logging`/`print`, so the
ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. Owner-projection unit tests (`test_autonomy_engine.py`): for each fact set
   (fired+action, fired+action+planner-blocked, fired+continue, fired+concluded,
   fired+self-revision, no-fire) assert the returned summaries equal the documented
   first-version values, and that `continuation + temporal + identity` crosses / stays under
   1.6 exactly as before.
2. Bridge-equivalence test: assert the bridge's `ProactiveDriveRequest` for representative
   upstream stage-result fixtures matches the pre-relocation field values (summaries +
   provenance ids), including the no-fire branch.
3. Existing autonomy-engine, autonomy-contract, and runtime-stage-chain tests stay green
   unchanged (the request shape and the decision path are untouched).
4. Owner-boundary guard: fails on a planted autonomy pressure-constant / `1.6` threshold under
   composition, passes on the real tree; positive control keeps it non-vacuous.
5. Full network-free suite (`pytest helios_v2/tests -q`) green; count = prior + added tests.
