# Requirement 43 - Dual-Timescale Neuromodulator Dynamics and Checkpoint

## 1. Background and Problem

The `04` neuromodulator owner is, since R36, driven by real `03` appraisal salience under the
semantic-memory assembly: each tick it derives levels as
`clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)`. But that
derivation is **stateless**: it reads no prior-tick levels, so the neuromodulator state is a
memoryless function of the current tick's stimulus. Every tick it is recomputed from the tonic
baseline; nothing carries forward.

This directly weakens the locked final-goal axis FG-2 ("affect must truly evolve across multiple
ticks; the system can produce different internal behavior on a pure internal tick because of its
affective/interoceptive state"). A memoryless `04` cannot model the brain's real neuromodulatory
dynamics: phasic bursts that rise quickly to a stimulus and then decay, and tonic levels that
drift slowly back toward a setpoint. With a stateless `04`, a stimulus on tick N leaves no trace
on tick N+1, so there is no affective momentum, no lingering arousal, no slow stress build-up.

The `04` owner's contract already reserves the interface for this: `NeuromodulatorConfig` declares
`decay_family = "dual_timescale_tonic_phasic"` and the learned-parameter category
`decay_speed_persistence`. This requirement fills that reserved interface with a real first-version
dual-timescale dynamics model, and persists the resulting cross-tick `04` state through the R42
continuity checkpoint so it survives a restart.

## 2. Goal

Make the `04` neuromodulator state evolve across ticks through a deterministic, bounded
dual-timescale (leaky-integrator) dynamics model that carries the prior-tick levels forward —
phasic terms move levels quickly toward the appraisal-derived drive, tonic terms pull them slowly
back toward the baseline — and persist that cross-tick state through the R42 checkpoint so a
restarted runtime resumes its prior neuromodulator levels instead of recomputing from baseline;
the `04` owner remains the sole owner of the decay/carry semantics, the instantaneous drive stays
owned by the injected appraisal-derived path, and the default (non-semantic, non-checkpointing)
assembly keeps the existing stateless behavior.

## 3. Functional Requirements

### 3.1 Dual-timescale dynamics

1. The `04` owner must own a dual-timescale update path that computes the next levels from the
   prior-tick levels plus the current tick's appraisal-derived instantaneous drive.
2. The update must follow a leaky-integrator form per channel:
   `next = clamp(prior + alpha_phasic * (drive - prior) + alpha_tonic * (baseline - prior),
   legal_min, legal_max)`, where `drive` is the instantaneous appraisal-derived target
   (`tonic_baseline + sum(sensitivity_k * salience_k)`), `alpha_phasic` is the fast
   stimulus-tracking rate, and `alpha_tonic` is the slow baseline-regression rate.
3. `alpha_phasic` must be greater than `alpha_tonic` (phasic fast, tonic slow), and both must be
   bounded in `(0, 1]` so the integrator is stable and never diverges.
4. On a cold start (no prior state: the first tick, or a cold checkpoint), the prior levels must
   default to the tonic baseline, so the first tick reduces to a bounded function of the current
   drive (no fabricated history).
5. The dynamics must be deterministic and bounded (every channel clamped to the legal range); no
   NN, no hidden branch, no divergence.

### 3.2 Owner boundary and protocol extension

1. The instantaneous drive computation must remain owned by the injected appraisal-derived path
   (the R36 logic), unchanged. The dual-timescale carry/decay is the new `04`-owned semantic.
2. The `NeuromodulatorUpdatePath` protocol must be extended with an optional `prior_levels`
   parameter (default `None`). When `None`, an update path must reproduce its existing stateless
   behavior byte-for-byte (so the constant first-version path and the default assembly are
   unchanged).
3. The `NeuromodulatorSystemAPI.update_state` must accept an optional `prior_state` parameter
   (default `None`) and forward its levels to the update path. When `None`, behavior is unchanged.
4. The `NeuromodulatorRuntimeStage` must hold the prior-tick `NeuromodulatorState` as owner-stage
   cross-tick state (like `09`/`18`), feed it into `update_state` each tick, and update it from the
   produced state after each tick.

### 3.3 Checkpoint integration

1. The `NeuromodulatorRuntimeStage` must expose an explicit owner-neutral seed seam
   (`seed_prior_state`) so composition can restore the prior `04` state at startup.
2. The R42 `RuntimeContinuitySnapshot` must carry the latest `04` `NeuromodulatorLevels` (the
   `snapshot_version` is bumped to 2). The checkpoint save must capture the tick's published `04`
   levels; the restore must seed the `04` stage's prior state from them.
3. Snapshot version 2 does not need to remain backward-compatible with version 1 files (no
   production data exists yet); a version mismatch may be rejected rather than migrated.

### 3.4 Rollout and boundary

1. The dual-timescale dynamics must activate under the same semantic-memory opt-in as R36 (the
   path that produces real drive). The default, recency-only, and offline assemblies keep the
   stateless constant path and their current `04` behavior.
2. Checkpointing `04` state must only occur when checkpointing is enabled (R42 opt-in); when
   checkpointing is off, `04` still evolves within a session but resets on restart, exactly as the
   continuation-pressure / continuity-thread state does without a checkpoint.

## 4. Non-Functional Requirements

1. Performance: the update is one bounded arithmetic pass over nine channels per tick; no scan.
2. Reliability: the integrator is provably bounded (convex update toward in-range targets plus a
   defensive clamp); it cannot diverge or oscillate unboundedly for `alpha` in `(0, 1]`.
3. Observability: no new logging mechanism; the `04` state already travels through the
   `NeuromodulatorStageResult` and (via R42) the checkpoint snapshot.
4. Compatibility: the protocol extension is additive (optional parameters defaulting to `None`),
   so every existing caller and the constant path are unaffected.

## 5. Code Behavior Constraints

1. The dual-timescale path must live in `helios_v2.neuromodulation` (the `04` owner), not in
   composition glue. Composition only injects it (and the R36 drive path it wraps) under the
   semantic-memory assembly.
2. The path must not fabricate prior state: a `None` prior means cold start = tonic baseline, never
   an invented history.
3. No degraded path: the dynamics are deterministic; there is no fallback branch.
4. The `alpha_phasic`/`alpha_tonic` coefficients are explicit bounded first-version constants under
   the already-declared `decay_speed_persistence` learned-parameter category (P5-learnable later);
   this slice does not learn them.
5. The checkpoint carry must remain owner-neutral (composition reads the published `04` levels and
   seeds the stage; it computes no dynamics).

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/engine.py` (extend `NeuromodulatorUpdatePath`,
   `update_state`; add the owner-owned `DualTimescaleNeuromodulatorUpdatePath` wrapping a drive path)
2. `helios_v2/src/helios_v2/neuromodulation/contracts.py` (extend `NeuromodulatorSystemAPI.update_state`)
3. `helios_v2/src/helios_v2/runtime/stages.py` (`NeuromodulatorRuntimeStage` prior-state carry + `seed_prior_state`)
4. `helios_v2/src/helios_v2/continuity_checkpoint/contracts.py` + `engine.py` (snapshot v2 with `neuromodulator_levels`)
5. `helios_v2/src/helios_v2/composition/bridges.py` (`ContinuityCheckpointBridge` carries `04` levels; the R36 drive path becomes the inner path of the dual-timescale wrapper)
6. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (assemble the dual-timescale path under the semantic opt-in; seed/restore the `04` stage)
7. `helios_v2/tests/test_neuromodulator_engine.py`, `tests/test_continuity_checkpoint_*`, `tests/test_runtime_composition.py` (new/updated)
8. Docs: `index.md`, both progress-flow maps, both owner guides, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, a strong stimulus on tick N raises the relevant channels,
   and on a subsequent lower-drive tick N+1 those channels are measurably higher than they would be
   from a stateless recompute (phasic carry), then decay toward baseline over further low-drive
   ticks (tonic regression) — verified by asserting the level trajectory, not a string.
2. The first tick (cold prior) produces levels equal to a single leaky-integrator step from the
   tonic baseline toward the drive (no fabricated history).
3. The integrator stays within `[legal_min, legal_max]` for every channel across many ticks (no
   divergence).
4. With checkpointing enabled, after running ticks that move `04` away from baseline, a fresh
   runtime assembled against the same checkpoint file resumes the prior `04` levels (provenance
   assertion: restored levels equal the last saved snapshot's levels), and the next tick continues
   the trajectory rather than restarting from baseline.
5. The default, recency-only, and offline assemblies keep the existing stateless constant `04`
   behavior (existing tests stay green); the `prior_levels=None` path reproduces prior behavior.
6. Snapshot version is 2 and carries `neuromodulator_levels`; a version-1 (or version-mismatched)
   payload is rejected on load rather than silently migrated.
7. The full test suite passes and remains network-free.
