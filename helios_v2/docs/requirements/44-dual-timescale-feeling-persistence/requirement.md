# Requirement 44 - Dual-Timescale Interoceptive Feeling Persistence and Checkpoint

## 1. Background and Problem

The `05` interoceptive feeling owner is, since R38, derived from the real `04` neuromodulator
state under the semantic-memory assembly: each tick it constructs the seven-dimension feeling
vector as a bounded linear function of the neuromodulator levels. But that construction is
**stateless**: it reads no prior-tick feeling, so the felt body-state is a memoryless function of
the current tick's neuromodulator levels.

This is the exact same gap R43 just closed for `04`, one layer downstream. With a stateless `05`,
feeling has no momentum: a calm tick fully erases the prior tick's tension or arousal, there is no
lingering mood, no slow fatigue build-up, no comfort that fades gradually. The `05` contract
already reserves the interface for fixing this: `InteroceptiveFeelingConfig` declares the
learned-parameter category `feeling_persistence`, which is currently unused.

With R43, `04` now evolves across ticks and persists across a restart. But `05` (the subjective
"felt body" the conscious layer and continuity consume) still snaps to a memoryless function each
tick and resets on restart. To complete the affect pair — neuromodulator dynamics (`04`) plus felt
body-state dynamics (`05`) — `05` must gain the same dual-timescale persistence and be checkpointed
alongside `04`.

## 2. Goal

Make the `05` interoceptive feeling vector evolve across ticks through the same deterministic,
bounded dual-timescale (leaky-integrator) form R43 introduced for `04` — phasic terms move the
feeling quickly toward the neuromodulator-derived target, tonic terms pull it slowly back toward
the baseline — carrying the prior-tick feeling forward, and persist that cross-tick feeling through
the R42 checkpoint so a restarted runtime resumes its prior felt body-state instead of recomputing
from baseline; the `05` owner remains the sole owner of the feeling-persistence semantics, the
instantaneous neuromodulator-derived target stays owned by the R38 construction path, and the
default (non-semantic, non-checkpointing) assembly keeps the existing stateless behavior.

## 3. Functional Requirements

### 3.1 Dual-timescale feeling persistence

1. The `05` owner must own a feeling-persistence construction path that computes the next feeling
   vector from the prior-tick feeling plus the current tick's neuromodulator-derived target feeling.
2. The update must follow the same leaky-integrator form as R43, per dimension:
   `next = clamp(prior + alpha_phasic * (target - prior) + alpha_tonic * (baseline - prior),
   legal_min, legal_max)`, where `target` is the instantaneous neuromodulator-derived feeling (the
   R38 construction), `alpha_phasic` is the fast tracking rate and `alpha_tonic` the slow
   baseline-regression rate.
3. `alpha_phasic` must be greater than `alpha_tonic` and both bounded in `(0, 1]`; an invalid
   ordering must be rejected at construction.
4. On a cold start (no prior feeling: the first tick or a cold checkpoint), the prior must default
   to the baseline feeling, so the first tick is one integrator step from baseline (no fabricated
   history).
5. The dynamics must be deterministic and bounded (every dimension clamped); no NN, no hidden
   branch, no divergence.

### 3.2 Owner boundary and protocol extension

1. The instantaneous neuromodulator-derived target stays owned by the R38
   `NeuromodulatorDerivedFeelingConstructionPath` (unchanged). The dual-timescale carry is the new
   `05`-owned semantic, implemented as an owner-owned path that wraps the R38 construction path.
2. The `FeelingConstructionPath` protocol must be extended with an optional `prior_feeling`
   parameter (default `None`). When `None`, a construction path must reproduce its existing
   stateless behavior byte-for-byte.
3. The `InteroceptiveFeelingAPI.update_state` (and the engine) must accept an optional
   `prior_state` parameter (default `None`) and forward its feeling vector to the construction
   path. When `None`, behavior is unchanged.
4. The `InteroceptiveFeelingRuntimeStage` must hold the prior-tick `InteroceptiveFeelingState` as
   cross-tick stage state (like `04`/`09`/`18`), feed it into `update_state` each tick, update it
   after each tick, and expose a `seed_prior_state` restore seam.

### 3.3 Checkpoint integration

1. The R42 `RuntimeContinuitySnapshot` must carry the latest `05` `InteroceptiveFeelingVector`
   (the `snapshot_version` is bumped to 3). The save must capture the tick's published `05`
   feeling; the restore must seed the `05` stage's prior state from it.
2. Snapshot version 3 does not need to remain backward-compatible with versions 1 or 2 (no
   production data exists yet); a version mismatch must be rejected on load rather than migrated.

### 3.4 Rollout and boundary

1. The dual-timescale feeling persistence must activate under the same semantic-memory opt-in as
   R38/R43 (where the `04` state and therefore the feeling target are real). The default,
   recency-only, and offline assemblies keep the stateless constant feeling.
2. Checkpointing `05` feeling must only occur when checkpointing is enabled (R42 opt-in); when
   checkpointing is off, `05` still evolves within a session but resets on restart.

## 4. Non-Functional Requirements

1. Performance: one bounded arithmetic pass over seven dimensions per tick; no scan.
2. Reliability: the integrator is provably bounded (clamped, `alpha` in `(0,1]`); it cannot diverge.
3. Observability: no new logging mechanism; the `05` state travels through the
   `InteroceptiveFeelingStageResult` and the checkpoint snapshot.
4. Compatibility: the protocol extension is additive (optional `None`-defaulted params).

## 5. Code Behavior Constraints

1. The dual-timescale feeling path must live in `helios_v2.feeling` (the `05` owner), not in
   composition glue. Composition only injects it (wrapping the R38 path) under the semantic
   assembly.
2. The path must not fabricate prior feeling: a `None` prior means cold start = baseline feeling.
3. No degraded path; the dynamics are deterministic.
4. The `alpha_phasic`/`alpha_tonic` coefficients are explicit bounded first-version constants under
   the already-declared `feeling_persistence` learned-parameter category (P5-learnable later); this
   slice does not learn them.
5. The checkpoint carry must remain owner-neutral (composition reads the published `05` feeling and
   seeds the stage; it computes no dynamics).
6. Hygiene: remove the pre-existing dead duplicate `NeuromodulatorDerivedFeelingConstructionPath`
   definition in `feeling/engine.py` (the first of the two identically-named classes is shadowed
   dead code) so the file has exactly one canonical R38 construction path that R44 wraps.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/feeling/engine.py` (extend `FeelingConstructionPath`, `update_state`;
   add the owner-owned `PersistentFeelingConstructionPath` wrapping the R38 path; remove the dead
   duplicate)
2. `helios_v2/src/helios_v2/feeling/contracts.py` (extend `InteroceptiveFeelingAPI.update_state`)
3. `helios_v2/src/helios_v2/runtime/stages.py` (`InteroceptiveFeelingRuntimeStage` prior-state
   carry + `seed_prior_state`)
4. `helios_v2/src/helios_v2/continuity_checkpoint/contracts.py` + `engine.py` (snapshot v3 with
   `feeling`)
5. `helios_v2/src/helios_v2/composition/bridges.py` (`ContinuityCheckpointBridge` carries/restores
   `05` feeling; the R38 path becomes the inner path of the persistence wrapper)
6. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (assemble the persistent feeling path
   under the semantic opt-in; keep the `05` stage ref; seed/restore)
7. `helios_v2/tests/test_interoceptive_feeling_engine.py`, `tests/test_continuity_checkpoint_*`,
   `tests/test_runtime_composition.py` (new/updated)
8. Docs: `index.md`, both progress-flow maps, both owner guides, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, a high-arousal stimulus on tick N raises the relevant
   feeling dimensions, and on a subsequent low-target tick N+1 those dimensions are measurably
   higher than they would be from a stateless recompute (phasic carry), then decay toward baseline
   over further low-target ticks (tonic regression) — verified by the trajectory, not a string.
2. The first tick (cold prior) produces a feeling equal to a single leaky-integrator step from the
   baseline feeling toward the target (no fabricated history).
3. The integrator stays within `[legal_min, legal_max]` for every dimension across many ticks.
4. With checkpointing enabled, after running ticks that move `05` away from baseline, a fresh
   runtime assembled against the same checkpoint file resumes the prior `05` feeling (provenance
   assertion: restored feeling equals the last saved snapshot's feeling), and the next tick
   continues the trajectory.
5. The default, recency-only, and offline assemblies keep the existing stateless constant `05`
   behavior (existing tests stay green); the `prior_feeling=None` path reproduces prior behavior.
6. Snapshot version is 3 and carries `feeling`; a version-1/2 (or mismatched) payload is rejected
   on load rather than migrated.
7. The full test suite passes and remains network-free.
