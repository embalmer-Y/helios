# Requirement 62 - Thought-Gate Drive-Urgency from the Prior-Tick Autonomy Drive

> Scope note (decided during implementation): this requirement originally bundled two `09`
> gate-signal de-shims — `drive_urgency_signal` and `selected_stimuli`. Implementing the
> `selected_stimuli` projection surfaced a real architectural fork: projecting the real `03`
> appraisal drops the default (non-semantic) assembly's stimulus signal from the constant `0.9`
> to the real first-version aggregate `0.4`, which pushes the default gate below the `0.55` fire
> threshold and flips the default runtime to a no-fire world (17 fired-path tests depend on the
> default assembly firing). That flip is architecturally honest (a weak constant-`0.4` appraisal
> should not fire every tick), but it exposes a deeper problem — the default assembly has no real
> high-salience ignition source — that deserves its own requirement rather than being forced
> through here by projecting a weak constant or by patching the `09` owner's threshold to
> accommodate a shim removal (which would violate the owner-boundary discipline). So
> `selected_stimuli` is **deferred to R63** ("real selected-stimuli + default-assembly ignition
> source"), and R62 is converged to the `drive_urgency_signal` de-shim only, which is
> behavior-clean and zero blast radius.

## 1. Background and Problem

The `09` thought-gate score is a weighted sum of normalized signals. After R37/R48/R53/R55, four
of its inputs are real (arousal, workspace activation, workload pressure, temporal/DMN). The
`drive_urgency_signal` input (weight `* 0.10`) is still the hardcoded constant `0.7` every tick in
`FirstVersionThoughtGateSignalBridge` / `NeuromodulatorAwareThoughtGateSignalBridge`.

`drive_urgency_signal` is meant to be the proactive drive's urgency. That drive is owned by `18`
autonomy, which runs *after* `09` in the tick, so the gate can only ever see the prior tick's
drive. Today it sees a constant `0.7` instead, so under `FG-1` the proactive system's real urgency
never actually influences whether the system thinks next tick — the one gate term that should
carry "how much do I want to act / keep going" is a constant.

The real source exists: each tick the `18` owner publishes a `ProactiveDriveState` whose
`pressure_components["outward_drive"]` is the proactive drive's strength. Carrying it forward (the
established R49 recall-directive and R55 temporal carry pattern) lets the prior tick's real drive
ground the next tick's gate urgency.

## 2. Goal

Ground the `09` gate's `drive_urgency_signal` in the prior tick's real `18` proactive drive,
carried forward through an owner-neutral cross-tick holder, so the proactive system's real urgency
influences whether the system thinks next tick — replacing the `0.7` constant, with a documented
neutral cold-start on the first tick (before any `18` drive exists) and no fabricated urgency.

## 3. Functional Requirements

### 3.1 Drive urgency from the prior tick's real autonomy drive

1. `drive_urgency_signal` each tick must be derived from the prior tick's real `18`
   `ProactiveDriveState`, carried forward through an owner-neutral cross-tick holder updated after
   each tick (mirroring the R49/R55 carry seams), since `18` runs after `09`.
2. The carried urgency must be a bounded `[0,1]` raw fact projected from an already-published `18`
   value (`outward_drive`, clamped); composition forwards it and the `09` owner keeps the `* 0.10`
   weight. It must not compute the `18` disposition or invent an urgency.
3. On the first tick (no prior `18` result yet), `drive_urgency_signal` must use a defined neutral
   cold-start value (documented), not crash and not fabricate a high urgency.

### 3.2 Behavioral scope

1. The change must affect only the `drive_urgency_signal` input. The `09` gate decision policy,
   weights, thresholds, and the other inputs (including the still-constant `selected_stimuli`,
   deferred to R63) are unchanged.
2. Because the cold-start neutral value equals the prior constant (`0.7`), the first tick of every
   assembly is byte-for-byte unchanged; the carried real drive supersedes it only from tick 2.

## 4. Non-Functional Requirements

1. Performance: no measurable per-tick overhead beyond reading one carried value and the `18`
   result post-tick.
2. Reliability: an absent `18` result leaves the carry unchanged; no new failure branch, no
   fabricated urgency.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the `09` `ThoughtGateSignalSnapshot` contract is unchanged in
   shape. This replaces one input source through an additive carry seam. The first tick is
   unchanged (cold-start `0.7`); only tick-2-onward reflects the real prior drive.

## 5. Code Behavior Constraints

1. Forbidden: the hardcoded `drive_urgency_signal=0.7` constant in composition once the carry
   lands, except as the documented first-tick cold-start baseline.
2. Forbidden: fabricating a drive urgency not derived from the real prior-tick `18` drive
   (`ARCHITECTURE_PHILOSOPHY` §4.3/§8); the neutral cold-start is the only non-real value and is
   the documented first-tick baseline.
3. Boundary rule: composition projects the prior-tick `18` `outward_drive` (clamped) into the gate
   signal; the `09` owner keeps the gate weight and decision policy.
4. Failure mode: first tick → neutral cold-start; absent `18` result → carry unchanged.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` — add `_DRIVE_URGENCY_COLD_START`, a
   `PriorDriveUrgencyHolder`, and `_drive_urgency_signal`; both gate-signal bridges read the holder
   for `drive_urgency_signal` (replacing the `0.7` literal).
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — construct the holder, wire it into
   the gate-signal bridge, store it on `RuntimeHandle`, and add a `_carry_drive_urgency` post-tick
   seam reading the `18` stage result.
3. `helios_v2/tests/test_runtime_composition.py` — tests for first-tick cold start, prior-tick
   drive carry, and bounded projection.
4. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md`.

## 7. Acceptance Criteria

1. `drive_urgency_signal` on tick N (N≥2) equals the bounded clamped `18` `outward_drive` from
   tick N-1 (verified: a high-drive prior tick raises the next-tick gate `drive_urgency_signal`
   above a low-drive prior tick); the constant `0.7` appears only as the documented first-tick
   cold-start.
2. The first tick uses the neutral cold-start `0.7` and the runtime does not crash.
3. The carried urgency is always a bounded `[0,1]` projection, never an unclamped sum.
4. The `09` gate decision policy/weights/thresholds and the other inputs are unchanged (their
   tests stay green); the full network-free suite is green with added tests; owner-boundary and
   ad-hoc-logging guards stay green.
5. `index.md` has a row 62 (and a row/entry noting R63 defers `selected_stimuli`); the `09`
   `OWNER_GUIDE` entries and the `BRAIN_ARCHITECTURE_COMPARISON` note record that
   `drive_urgency_signal` is now real (prior-tick `18` carry) and that `selected_stimuli` remains
   the gate's last constant input pending R63, with sync lines naming R62.
