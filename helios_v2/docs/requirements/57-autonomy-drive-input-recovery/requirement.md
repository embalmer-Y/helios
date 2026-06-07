# Requirement 57 - Owner Boundary Recovery of the Cognition-Derived Autonomy Drive Inputs

## 1. Background and Problem

The runtime composition root (`helios_v2.composition`) is assembly-only by boundary truth
(`ARCHITECTURE_BOUNDARIES.md` §4.5): it constructs owners and owner-neutral bridges and
holds no cognitive policy. `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §7.1 forbids orchestration
from owning a downstream owner's semantic judgment; §3.3 requires that a runtime-significant
concept be a first-class owner state rather than a value tuned inside glue.

The R56 recovery closed one such leak (`04` neuromodulator drive mapping). A second,
deeper one remains in `FirstVersionAutonomyRequestBridge` (`composition/bridges.py`). That
bridge claims to be an "owner-neutral translation table", but it actually authors the `18`
autonomy owner's cognitive policy:

1. It maps the thought owner's real fired-cycle outcome into a set of **tuned pressure
   constants** — `_ACTION_CONTINUATION_PRESSURE = 0.9`, `_ACTION_TEMPORAL_PRESSURE = 0.4`,
   `_ACTION_IDENTITY_PRESSURE = 0.4`, `_CONTINUE_CONTINUATION_PRESSURE = 0.8`,
   `_UNRESOLVED_IDENTITY_PRESSURE = 0.6`, etc.
2. The bridge's own docstring states these constants are chosen so that
   `outward_drive = 0.9 + 0.4 + 0.4 = 1.7 >= 1.6` — i.e. composition reverse-engineers the
   `18` owner's internal action threshold (`outward_drive >= 1.6`) to decide what pressures
   to emit. Composition therefore depends on and encodes `18`'s decision threshold.
3. It owns the `planner_status -> executed/blocked` classification
   (`_PLANNER_EXECUTED_STATUSES` / `_PLANNER_BLOCKED_STATUSES`) — an interpretation of `13`'s
   output for the autonomy decision — and the retrieval-pull normalization (`hit_count / 4.0`).

This is a clear owner-boundary violation: "how strong a proactive drive a given cognition
outcome should produce, relative to my own action threshold" is the defining judgment of the
`18` autonomy owner, not assembly glue. It is the autonomy analog of the R56 neuromodulator
leak, and is worse because it couples to the consumer owner's internal threshold.

This requirement does not change runtime behavior. It relocates the cognition-outcome to
drive-input mapping to the `18` owner and reduces the composition bridge to forwarding raw
cognition facts, then guards against recurrence.

## 2. Goal

Move the cognition-outcome to autonomy-drive-input mapping (the tuned pressure constants,
the planner-status classification, the retrieval-pull normalization, and the implicit
knowledge of the `18` action threshold) out of the composition bridge into an `18`-owned
drive-input projector, so the autonomy owner owns how genuine cognition becomes its drive
inputs, composition only forwards raw cognition facts, and the produced autonomy
disposition is byte-for-byte unchanged for every tick and every assembly.

## 3. Functional Requirements

### 3.1 Owner-owned drive-input projection

1. The `18` owner package `helios_v2.autonomy` must define an owner-owned projection that
   maps a bounded set of raw cognition facts (whether the thought path activated, whether it
   produced an action proposal, whether it requested continuation, whether it proposed
   self-revision, the planner status, whether continuation is active, and the retrieval hit
   count) into the five existing drive-input summaries the autonomy owner already consumes
   (`continuation_summary`, `retrieval_pull_summary`, `temporal_pressure_summary`,
   `identity_unresolved_summary`, `outward_readiness_summary`).
2. The tuned pressure constants, the planner-status executed/blocked classification, the
   retrieval-pull normalization, and any dependence on the autonomy action threshold must
   reside with that owner-owned projection, not in composition.
3. The raw cognition facts must be expressed as an owner-owned input contract so the boundary
   between "facts composition forwards" and "drive inputs the owner derives" is explicit.

### 3.2 Composition reduced to fact forwarding

1. The composition autonomy request bridge must only extract the raw cognition facts from the
   already-published upstream owner stage results, forward provenance ids verbatim, and call
   the owner-owned projection to obtain the drive-input summaries.
2. The composition bridge must not define any autonomy pressure constant, the planner
   executed/blocked classification, the retrieval-pull normalization, or any reference to the
   autonomy action threshold.

### 3.3 Behavioral invariance

1. For any combination of upstream cognition facts (fired with/without action, continue, no
   continue, self-revision present/absent, each planner status, and the no-fire tick), the
   `ProactiveDriveRequest` produced by composition must be field-for-field identical to the
   pre-relocation request (same summaries, same provenance ids, same ordering).
2. The resulting autonomy disposition and `AutonomyResult` must be byte-for-byte identical to
   before for every assembly (default, recency-only, semantic, channel-bound, interoceptive,
   temporal, continuity-checkpoint), including the no-fire tick path.

### 3.4 Recurrence guard

1. The repository owner-boundary guard must fail if the composition tree defines autonomy
   drive-pressure tuning (a pressure-constant naming pattern or a literal reference to the
   autonomy action threshold) so this class of violation cannot silently reappear.
2. The guard must pass on the post-relocation tree.

### 3.5 Boundary-truth recording

1. `ARCHITECTURE_BOUNDARIES.md`, both `OWNER_GUIDE` files (`18` and `22` entries), and both
   `PROGRESS_FLOW` maps must record that the cognition-derived autonomy drive-input mapping is
   now owner-owned, and what remains in composition is raw-fact forwarding.

## 4. Non-Functional Requirements

1. Performance: no runtime performance change; code-location and indirection change only.
2. Reliability: the owner-owned projection is a total deterministic function of the cognition
   facts; it never branches into a degraded mode and bounds every summary value into `[0,1]`
   exactly as today. Malformed upstream results still fail fast in the bridge's extraction
   step (the existing stage-result typing), with no new silent fallback.
3. Observability and logging: no new logging mechanism; the `21` owner remains the single
   logging mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the `ProactiveDriveRequest` contract is unchanged in shape, so
   existing autonomy-owner and contract tests are unaffected. A new owner-owned cognition-facts
   input contract is additive. Default rollout is immediate and unconditional; behavior is
   unchanged for every assembly.

## 5. Code Behavior Constraints

1. Forbidden: defining an autonomy drive-pressure constant or referencing the autonomy action
   threshold anywhere under `helios_v2/composition`.
2. Forbidden: changing any pressure constant value, the planner-status classification, the
   retrieval-pull normalization, the threshold, or the fire/no-fire branching during
   relocation. The diff must be behavior-preserving.
3. Boundary rule: the `18` owner owns how cognition facts become drive inputs; composition may
   extract and forward raw facts and provenance but must not author the mapping.
4. Boundary rule (scope guard): this requirement recovers only the cognition-to-drive-input
   mapping currently in `FirstVersionAutonomyRequestBridge`. The remaining first-version
   constant shims and pure projection bridges stay accepted owner-neutral glue under §4.5.
5. Failure mode: a malformed or missing upstream stage result still raises in the bridge's
   extraction step exactly as today; the relocation adds no new failure branch.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/autonomy/contracts.py` — new owner-owned `ProactiveCognitionFacts`
   input contract.
2. `helios_v2/src/helios_v2/autonomy/engine.py` — new owner-owned drive-input projection from
   `ProactiveCognitionFacts` to the five drive-input summaries (the recovered mapping).
3. `helios_v2/src/helios_v2/autonomy/__init__.py` — re-export the new contract/projection.
4. `helios_v2/src/helios_v2/composition/bridges.py` — `FirstVersionAutonomyRequestBridge`
   reduced to fact extraction + provenance forwarding + projection call; all pressure
   constants, the planner classification, the normalization, and the threshold knowledge
   removed.
5. `helios_v2/tests/test_autonomy_engine.py` — focused tests for the owner-owned projection.
6. `helios_v2/tests/test_composition_owner_boundary_guard.py` — extend the guard.
7. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md`.

## 7. Acceptance Criteria

1. The owner-owned `ProactiveCognitionFacts` contract and the drive-input projection are
   importable from `helios_v2.autonomy` and defined in the `18` owner package; the pressure
   constants, planner classification, retrieval normalization, and threshold knowledge are no
   longer present in `helios_v2/composition`.
2. A focused test asserts the owner-owned projection reproduces the documented first-version
   summaries for representative fact sets: fired+action (outward_drive 1.7, outward_ready),
   fired+action+planner-blocked (externalization_blocked), fired+continue (continuation 0.8,
   no outward), fired+concluded, fired+self-revision (identity 0.6), and the no-fire tick.
3. A behavioral-equivalence test asserts the composition bridge produces a field-for-field
   identical `ProactiveDriveRequest` to the pre-relocation logic for the same upstream facts,
   and the runtime stage-chain tests stay green unchanged.
4. The owner-boundary guard fails on a planted autonomy pressure-constant / threshold reference
   under composition and passes on the actual tree; the ad-hoc-logging guard stays green.
5. The full network-free suite is green (`pytest helios_v2/tests -q`), with the count growing
   only by the added focused/guard tests.
6. `index.md` has a row 57; both `OWNER_GUIDE` files (`18` + `22`) and both `PROGRESS_FLOW`
   maps record the recovered ownership and the raw-fact-forwarding scope, with the sync lines
   naming R57.
