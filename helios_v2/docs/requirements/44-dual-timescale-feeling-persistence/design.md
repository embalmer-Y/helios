# Requirement 44 - Dual-Timescale Interoceptive Feeling Persistence and Checkpoint

## 1. Title

Dual-timescale (leaky-integrator) interoceptive feeling persistence with prior-tick carry and R42
checkpoint persistence — the `05` mirror of R43.

## 2. Design Overview

R38 gave the `05` owner a real instantaneous *target* feeling (a bounded linear function of the
`04` neuromodulator levels) but applied it statelessly. R44 adds the temporal layer the contract
already reserves (`feeling_persistence`): a leaky-integrator that carries the prior-tick feeling
forward, moving it quickly toward the target (phasic) and slowly back toward the baseline (tonic).
This is the exact structural mirror of R43 (`04`), one layer downstream, reusing the same equation
shape so the two affect owners share one dynamics form (and one future P5 learning surface).

The instantaneous target stays owned by the injected R38 construction path. The new persistence
carry is a `05`-owned path that *wraps* the R38 path: it asks the inner path for the target
feeling, then applies the leaky-integrator step against the prior feeling. Prior state lives on the
`InteroceptiveFeelingRuntimeStage` (like `04`/`09`/`18`), persisted/restored through the R42
checkpoint (snapshot bumped to v3 with a `feeling` field).

## 3. Current State and Gap

- `InteroceptiveFeelingEngine.update_state(neuromodulator_state, internal_signals, tick_id)` calls
  `construction_path.construct_feeling(neuromodulator_state, internal_signals, config, tick_id)` —
  no prior feeling anywhere.
- `NeuromodulatorDerivedFeelingConstructionPath.construct_feeling` (R38) computes
  `clamp(baseline + Σ coupling·level)` and is explicitly stateless.
- `InteroceptiveFeelingRuntimeStage.run` calls `update_state(...)` with no carry; it holds no
  cross-tick field.
- R42/R43 `RuntimeContinuitySnapshot` carries continuation pressure + deferred + threads +
  `neuromodulator_levels`; `snapshot_version = 2`.
- Hygiene: `feeling/engine.py` currently defines `NeuromodulatorDerivedFeelingConstructionPath`
  twice; the first definition is shadowed dead code.

## 4. Target Architecture

### 4.1 Protocol extension (additive)

`FeelingConstructionPath.construct_feeling` gains an optional trailing parameter:

```python
def construct_feeling(self, neuromodulator_state, internal_signals, config, tick_id,
                      prior_feeling: InteroceptiveFeelingVector | None = None) -> InteroceptiveFeelingVector: ...
```

- The R38 `NeuromodulatorDerivedFeelingConstructionPath` and the constant
  `FirstVersionFeelingConstructionPath` ignore `prior_feeling` (they remain the target/constant
  producers).

`InteroceptiveFeelingAPI.update_state` (and the engine) gains `prior_state: InteroceptiveFeelingState | None = None`;
the engine forwards `prior_state.feeling` (or `None`) to `construct_feeling`.

### 4.2 The persistent feeling path (05-owned)

```python
@dataclass
class PersistentFeelingConstructionPath(FeelingConstructionPath):
    target_path: FeelingConstructionPath   # the inner R38 neuromodulator-derived construction
    alpha_phasic: float = 0.6
    alpha_tonic: float = 0.1

    def construct_feeling(self, neuromodulator_state, internal_signals, config, tick_id, prior_feeling=None):
        target = self.target_path.construct_feeling(neuromodulator_state, internal_signals, config, tick_id)
        prior = prior_feeling if prior_feeling is not None else config.baseline_feeling   # cold start = baseline
        # per dimension: next = clamp(prior + a_phasic*(target - prior) + a_tonic*(baseline - prior))
        ...
```

- Invariant `0 < alpha_tonic < alpha_phasic <= 1`, rejected at construction otherwise
  (`InteroceptiveFeelingError`).
- Cold start: `prior_feeling is None` → `prior = baseline_feeling`.
- Same constants as R43's default (0.6 / 0.1) so the two affect owners decay on a consistent
  timescale.

### 4.3 Stage prior-state carry + seed seam

`InteroceptiveFeelingRuntimeStage` gains:
- `_prior_state: InteroceptiveFeelingState | None = None` (init=False), passed into `update_state`
  each tick and updated from the produced state after the call.
- `seed_prior_state(state: InteroceptiveFeelingState) -> None` — the owner-neutral restore seam.

### 4.4 Checkpoint v3

- `RuntimeContinuitySnapshot` gains `feeling: InteroceptiveFeelingVector | None = None`;
  `SNAPSHOT_VERSION` → 3.
- Facade encode/decode adds the feeling (a 7-float dict). Decode of a payload whose version != 3
  raises `CheckpointError` (no v1/v2 migration).
- `ContinuityCheckpointBridge.build_snapshot` reads the `05` stage result's `state.feeling`;
  `restore_feeling_state(snapshot)` reconstructs an `InteroceptiveFeelingState` to seed the `05`
  stage.

### 4.5 Composition wiring

- Under the semantic assembly the `05` construction path becomes
  `PersistentFeelingConstructionPath(target_path=NeuromodulatorDerivedFeelingConstructionPath())`.
  Off the semantic assembly: unchanged `FirstVersionFeelingConstructionPath`.
- The checkpoint restore step seeds the `05` stage when the snapshot carries a feeling; save reads
  the `05` stage result. The handle keeps a `05` stage ref (like the `04` one added in R43).

## 5. Data Structures

```python
# contracts.py (continuity_checkpoint)
@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    tick_id: int | None
    continuation_state: ContinuationPressureState
    deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    continuity_threads: tuple[ContinuityThread, ...] = ()
    neuromodulator_levels: NeuromodulatorLevels | None = None
    feeling: InteroceptiveFeelingVector | None = None          # NEW (v3)
    snapshot_version: int = 3                                  # was 2
```

The reused `InteroceptiveFeelingVector` is encoded as a 7-key float dict; decode reconstructs it
(running the owner's range validation → corrupt feeling hard-stops on load).

## 6. Module Changes

1. `feeling/engine.py`: extend the protocol + engine signature; add
   `PersistentFeelingConstructionPath`; remove the dead duplicate R38 class.
2. `feeling/contracts.py`: extend `InteroceptiveFeelingAPI.update_state` signature.
3. `runtime/stages.py`: `InteroceptiveFeelingRuntimeStage` carry + `seed_prior_state`.
4. `continuity_checkpoint/contracts.py` + `engine.py`: snapshot v3 + feeling encode/decode +
   version-mismatch hard stop.
5. `composition/bridges.py`: `ContinuityCheckpointBridge` reads/restores `05` feeling.
6. `composition/runtime_assembly.py`: assemble persistent feeling path; keep `05` stage ref; seed
   on restore; save `05` feeling.

## 7. Migration Plan

1. Extend protocol/engine signatures with defaulted `None` params (no behavior change yet).
2. Add the persistent feeling path + focused engine tests; remove the dead duplicate.
3. Add the stage carry + seed seam.
4. Bump the snapshot to v3 + feeling; update the bridge.
5. Wire composition under the semantic opt-in; update resumption tests.
6. Sync docs.

## 8. Failure Modes and Constraints

1. Cold prior → baseline feeling (defined), never fabricated.
2. `alpha` out of `(0,1]` or `alpha_tonic >= alpha_phasic` → reject at construction.
3. Snapshot version != 3 on load → `CheckpointError`.
4. Corrupt feeling in a stored snapshot → the `InteroceptiveFeelingVector` constructor raises,
   wrapped to `CheckpointError`.
5. Owner boundary: target stays in the injected R38 path; carry stays in the `05`-owned wrapper;
   composition computes no dynamics.

## 9. Observability and Logging

No new logging mechanism. `05` state travels through `InteroceptiveFeelingStageResult` and the
checkpoint snapshot. The guard test must stay green.

## 10. Validation Strategy

1. Engine: phasic carry, tonic regression, cold-start = one step from baseline, boundedness over
   many ticks, `prior_feeling=None` reproduces the inner path exactly, unstable-alpha rejection.
2. Checkpoint: snapshot v3 round-trips feeling; version-1/2/mismatch rejected; corrupt feeling
   hard-stop.
3. Composition: semantic assembly evolves `05` across ticks; restart resumes `05` feeling by
   provenance and continues the trajectory; default/recency/offline keep stateless `05`.
4. Full suite network-free.
