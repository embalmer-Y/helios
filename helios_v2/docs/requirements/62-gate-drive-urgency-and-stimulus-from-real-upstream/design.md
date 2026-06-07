# Requirement 62 - Thought-Gate Drive-Urgency from the Prior-Tick Autonomy Drive

## 1. Design Overview

De-shim the `09` gate-signal `drive_urgency_signal` by carrying the prior tick's real `18`
proactive drive forward through an owner-neutral `PriorDriveUrgencyHolder`: the holder is updated
after each tick from the `18` stage result (`ProactiveDriveState.pressure_components["outward_drive"]`,
clamped to `[0,1]`) and read by the gate-signal bridge next tick. `18` runs after `09`, so this
cross-tick carry is the only honest way the proactive urgency can reach the gate — the established
pattern from R49 (recall directive) and R55 (temporal). The first tick uses a documented neutral
cold-start equal to the prior constant (`0.7`), so the first tick is unchanged and tick-2-onward
reflects the real prior drive. The `09` owner keeps the `* 0.10` weight and decision policy. No
`09` contract change.

`selected_stimuli` is deferred to R63 (see the scope note in `requirement.md`): projecting the
real `03` appraisal flips the default assembly to no-fire, which is honest but exposes a deeper
"default-assembly ignition source" problem that needs its own requirement.

## 2. Current State and Gap

Both gate-signal bridges build the snapshot with `drive_urgency_signal=0.7`. The `09` engine
computes `... + signal_snapshot.drive_urgency_signal * 0.10 + ...` in the gate score. So the
proactive-urgency term is a constant. The `18` owner publishes a real `ProactiveDriveState` each
tick (available post-tick from `result.stage_results["subjective_autonomy_and_proactive_evolution"].result.drive_state`),
but it runs after `09`, so it can only reach the gate next tick. Gap: the bridge emits a constant
instead of carrying the prior tick's real drive.

## 3. Target Architecture

```
_DRIVE_URGENCY_COLD_START = 0.7   # documented first-tick neutral baseline (== prior constant)

@dataclass
class PriorDriveUrgencyHolder:
    urgency: float = _DRIVE_URGENCY_COLD_START
    def set_from_drive_state(self, drive_state) -> None:
        # raw bounded projection of the published 18 outward_drive (clamped to [0,1]),
        # exactly as R48 clamps the published 07 activation; non-numeric/bool -> no update
        v = (getattr(drive_state, "pressure_components", None) or {}).get("outward_drive", 0.0)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            self.urgency = clamp(float(v))
    def current(self) -> float:
        return self.urgency

def _drive_urgency_signal(holder) -> float:
    return holder.current() if holder is not None else _DRIVE_URGENCY_COLD_START

# both gate-signal bridges:
drive_urgency_signal=_drive_urgency_signal(self.drive_urgency_holder)

# RuntimeHandle post-tick (next to _carry_temporal):
def _carry_drive_urgency(self, result):
    if self.drive_urgency_holder is None: return
    autonomy = result.stage_results.get("subjective_autonomy_and_proactive_evolution")
    drive_state = getattr(getattr(autonomy, "result", None), "drive_state", None)
    if drive_state is not None:
        self.drive_urgency_holder.set_from_drive_state(drive_state)
```

`outward_drive` is a sum that can exceed 1.0 (it is `continuation + temporal + identity`, reaching
`1.7` on an action tick); clamping projects it into the gate's `[0,1]` input range — a raw bounded
projection of a published `18` value, not a re-derivation of the `18` disposition. The cold-start
`0.7` equals the retired constant, so the first tick is byte-for-byte unchanged.

## 4. Data Structures

No contract changes. New composition-glue only: `_DRIVE_URGENCY_COLD_START` (float) and
`PriorDriveUrgencyHolder` (carries one bounded float). The `RuntimeHandle` gains an optional
`drive_urgency_holder` field.

## 5. Module Changes

1. `composition/bridges.py`
   - Add `_DRIVE_URGENCY_COLD_START`, `_drive_urgency_signal(holder)`, and `PriorDriveUrgencyHolder`.
   - Both gate-signal bridges gain an optional `drive_urgency_holder` field and read
     `_drive_urgency_signal(self.drive_urgency_holder)` for `drive_urgency_signal` (the `0.7`
     literal removed from snapshot construction). `selected_stimuli` keeps its first-version
     constant (deferred to R63).
2. `composition/runtime_assembly.py`
   - Construct one `PriorDriveUrgencyHolder`, pass it to the wired gate-signal bridge, store it on
     `RuntimeHandle`, and add `_carry_drive_urgency(result)` to the post-tick carry sequence.
3. Tests (see Validation Strategy).

No `09` engine/contract change; no stage reorder.

## 6. Migration Plan

1. Add the cold-start constant, the holder, and the `_drive_urgency_signal` helper.
2. Rewire both gate-signal bridges to read the holder (remove the `0.7` literal).
3. Construct + wire the holder in assembly; add the post-tick carry.
4. Add focused tests (first-tick cold start, prior-tick carry, bounded projection).
5. Run the full suite; confirm behavior-invariance for the first tick and that no existing test
   regresses (the cold-start equals the old constant, so tick-1 is unchanged).
6. Update documentation truth.

## 7. Failure Modes and Constraints

1. First tick → `_DRIVE_URGENCY_COLD_START` (neutral `0.7`); the real prior-tick `18` drive applies
   from tick 2. No crash, no fabricated high urgency.
2. Absent `18` stage result / non-numeric `outward_drive` → the holder is left unchanged (keeps the
   last carried value or the cold start). No new failure branch.
3. The projection is total/deterministic and clamped to `[0,1]`.
4. No fabricated value: a high drive urgency arises only from a real high prior-tick `18` drive.

## 8. Rollout (Default-On vs Default-Off)

Default-on (the gate-signal bridge and the holder are in every assembly). The first tick is
byte-for-byte unchanged (cold-start `0.7` = old constant); the behavior change is that from tick 2
the gate's drive-urgency term reflects the real prior-tick `18` drive instead of a constant. The
`09` owner weights/policy are unchanged.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The holder, the
helper, and the carry use neither `logging` nor `print`; the ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. First-tick cold start: tick 1's gate `drive_urgency_signal` (in `contributing_signals`) equals
   `0.7`.
2. Prior-tick carry: an externalizing prior tick (high `18` `outward_drive` ≥ 1.6) makes tick 2's
   gate `drive_urgency_signal` equal the clamped prior drive (`1.0`), above the tick-1 cold start.
3. Bounded projection: across several ticks the gate `drive_urgency_signal` stays within `[0,1]`,
   never an unclamped sum.
4. No regression: existing gate/composition/stage-chain tests stay green (the first tick is
   unchanged). Full network-free suite green; owner-boundary and ad-hoc-logging guards green.
