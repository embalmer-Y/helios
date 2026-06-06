# Requirement 43 - Dual-Timescale Neuromodulator Dynamics and Checkpoint

## 1. Title

Dual-timescale (leaky-integrator) neuromodulator dynamics with prior-tick carry and R42
checkpoint persistence.

## 2. Design Overview

R36 gave the `04` owner a real instantaneous *drive* (`tonic_baseline + sum(sensitivity·salience)`)
but applied it statelessly. R43 adds the **temporal** layer the contract already reserved
(`decay_family = "dual_timescale_tonic_phasic"`, `decay_speed_persistence`): a leaky-integrator
that carries the prior-tick levels forward, moving them quickly toward the drive (phasic) and
slowly back toward the baseline (tonic).

The instantaneous drive stays owned by the injected appraisal-derived path (R36, unchanged). The
new dual-timescale carry is an `04`-owned path that *wraps* an inner drive path: it asks the inner
path for the drive, then applies the leaky-integrator step against the prior levels. Prior state
lives on the `NeuromodulatorRuntimeStage` (like `09`/`18`), and is persisted/restored through the
R42 checkpoint (snapshot bumped to v2 with a `neuromodulator_levels` field).

## 3. Current State and Gap

- `NeuromodulatorEngine.update_state(batch, tick_id)` calls `update_path.update_levels(batch,
  config, tick_id)` — no prior state anywhere.
- `AppraisalDerivedNeuromodulatorUpdatePath.update_levels` computes `clamp(baseline + Σ sens·sal)`
  and is explicitly stateless.
- `NeuromodulatorRuntimeStage.run` calls `update_state(batch, tick_id=frame.tick_id)` with no
  carry; it holds no cross-tick field.
- R42 `RuntimeContinuitySnapshot` carries continuation pressure + deferred records + threads only;
  `snapshot_version = 1`.

Gap: there is no place to hold prior `04` levels, no carry, and the snapshot does not include `04`.

## 4. Target Architecture

### 4.1 Protocol extension (additive, backward-compatible)

`NeuromodulatorUpdatePath.update_levels` gains an optional trailing parameter:

```python
def update_levels(self, batch, config, tick_id, prior_levels: NeuromodulatorLevels | None = None) -> NeuromodulatorLevels: ...
```

- The constant `FirstVersionNeuromodulatorUpdatePath` and the R36
  `AppraisalDerivedNeuromodulatorUpdatePath` ignore `prior_levels` (they remain the drive/constant
  producers). Adding the parameter with a default keeps every existing caller working.

`NeuromodulatorSystemAPI.update_state` gains an optional `prior_state`:

```python
def update_state(self, batch, tick_id=None, prior_state: NeuromodulatorState | None = None) -> NeuromodulatorState: ...
```

- The engine forwards `prior_state.levels` (or `None`) to `update_path.update_levels`.

### 4.2 The dual-timescale path (04-owned)

```python
@dataclass
class DualTimescaleNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    drive_path: NeuromodulatorUpdatePath   # the inner R36 appraisal-derived drive path
    alpha_phasic: float = 0.6              # fast stimulus-tracking rate (decay_speed_persistence)
    alpha_tonic: float = 0.1               # slow baseline-regression rate (decay_speed_persistence)

    def update_levels(self, batch, config, tick_id, prior_levels=None):
        drive = self.drive_path.update_levels(batch, config, tick_id)   # R36 instantaneous target
        prior = prior_levels if prior_levels is not None else config.tonic_baseline  # cold start = baseline
        # per channel: next = clamp(prior + a_phasic*(drive - prior) + a_tonic*(baseline - prior))
        ...
```

- Invariant: `0 < alpha_tonic < alpha_phasic <= 1`. With both in `(0,1]` and `drive`/`baseline`
  in range, `next` is a convex-ish combination plus clamp — provably bounded.
- Cold start: `prior_levels is None` → `prior = tonic_baseline`, so the first tick is
  `baseline + a_phasic*(drive - baseline)` (a single integrator step from baseline), never
  fabricated history.
- Stateless inner path is reused verbatim, so the drive semantics (R36) are unchanged and only the
  temporal layer is new.

### 4.3 Stage prior-state carry + seed seam

`NeuromodulatorRuntimeStage` gains:
- `_prior_state: NeuromodulatorState | None = None` (init=False), passed into `update_state` each
  tick and updated from the produced state after the call.
- `seed_prior_state(state: NeuromodulatorState) -> None` — the owner-neutral composition-time
  restore seam (mirrors `09`/`18`).

### 4.4 Checkpoint v2

- `RuntimeContinuitySnapshot` gains `neuromodulator_levels: NeuromodulatorLevels | None = None`;
  `SNAPSHOT_VERSION` → 2.
- The facade encode/decode adds the levels (a 9-float dict). Decode of a payload whose version != 2
  raises `CheckpointError` (no v1 migration; acceptance criterion 6).
- `ContinuityCheckpointBridge.build_snapshot` additionally reads the `04` stage result's
  `state.levels`; restore seeds the `04` stage via `seed_prior_state` (reconstructing a
  `NeuromodulatorState` from the levels with a restore provenance id).

### 4.5 Composition wiring

- Under the semantic-memory assembly, the `04` update path becomes
  `DualTimescaleNeuromodulatorUpdatePath(drive_path=AppraisalDerivedNeuromodulatorUpdatePath())`.
  Off the semantic assembly: unchanged `FirstVersionNeuromodulatorUpdatePath`.
- The checkpoint restore step (in `RuntimeHandle._restore_continuity`) also seeds the `04` stage
  when the snapshot carries levels; save (`_checkpoint_continuity`) reads the `04` stage result.
- The handle needs a reference to the `04` stage (like it already keeps `09`/`18`).

## 5. Data Structures

```python
# contracts.py (continuity_checkpoint)
@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    tick_id: int | None
    continuation_state: ContinuationPressureState
    deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    continuity_threads: tuple[ContinuityThread, ...] = ()
    neuromodulator_levels: NeuromodulatorLevels | None = None   # NEW (v2)
    snapshot_version: int = 2                                   # was 1
```

The reused `NeuromodulatorLevels` contract is encoded as a 9-key float dict in the snapshot JSON;
decode reconstructs it (running the owner's `_validate_level` invariants → corrupt levels hard-stop
on load).

## 6. Module Changes

1. `neuromodulation/engine.py`: extend the protocol + engine signature; add
   `DualTimescaleNeuromodulatorUpdatePath`.
2. `neuromodulation/contracts.py`: extend `NeuromodulatorSystemAPI.update_state` signature.
3. `runtime/stages.py`: `NeuromodulatorRuntimeStage` carry + `seed_prior_state`.
4. `continuity_checkpoint/contracts.py` + `engine.py`: snapshot v2 + levels encode/decode +
   version-mismatch hard stop.
5. `composition/bridges.py`: `ContinuityCheckpointBridge` reads/restores `04` levels.
6. `composition/runtime_assembly.py`: assemble dual-timescale path; keep `04` stage ref; seed on
   restore; save `04` levels.

## 7. Migration Plan

1. Extend the protocol/engine signatures with defaulted `None` params (no behavior change yet).
2. Add the dual-timescale path + focused engine tests.
3. Add the stage carry + seed seam.
4. Bump the snapshot to v2 + levels; update the bridge.
5. Wire composition under the semantic opt-in; update resumption tests.
6. Sync docs.

## 8. Failure Modes and Constraints

1. Cold prior → baseline (defined), never fabricated.
2. `alpha` out of `(0,1]` or `alpha_tonic >= alpha_phasic` → reject at path construction
   (`NeuromodulatorError`), so an unstable integrator cannot be assembled.
3. Snapshot version != 2 on load → `CheckpointError` (no silent migration).
4. Corrupt levels in a stored snapshot → the `NeuromodulatorLevels` constructor raises, wrapped to
   `CheckpointError` on load.
5. Owner boundary: drive stays in the injected path; carry stays in the `04`-owned wrapper;
   composition computes no dynamics.

## 9. Observability and Logging

No new logging mechanism. `04` state travels through `NeuromodulatorStageResult` and the checkpoint
snapshot. The guard test (`tests/test_no_adhoc_logging_guard.py`) must stay green.

## 10. Validation Strategy

1. Engine: phasic carry (high drive tick then low drive tick → level above stateless recompute),
   tonic regression (repeated low-drive ticks → decay toward baseline), cold-start = one step from
   baseline, boundedness over many ticks, `prior_levels=None` reproduces the inner path exactly,
   unstable-alpha construction rejected.
2. Checkpoint: snapshot v2 round-trips levels; version-1/mismatch payload rejected; corrupt levels
   hard-stop.
3. Composition: semantic assembly evolves `04` across ticks; restart resumes `04` levels by
   provenance and continues the trajectory; default/recency/offline keep stateless `04`.
4. Full suite network-free.
