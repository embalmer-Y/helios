# Requirement 53 - Workload pressure from the interoceptive afferent (design)

## 1. Design Overview

R53 grounds the `09` gate's `workload_pressure` in the runtime's real compute/runtime load. The gate-signal bridge already runs after `02` sensory and `04`/`07` (it reads those stage results for R37/R48), so the R50 interoceptive stimuli are already present in `frame.stage_results["sensory_ingress"].batch`. R53 adds one owner-neutral helper that derives a bounded `workload_pressure` from the cpu/memory interoceptive load channels and forwards it in the `ThoughtGateSignalSnapshot`, replacing the constant `0.1`. When no load stimulus is present, it keeps `0.1` byte-for-byte.

The change is one helper plus a two-line edit in each gate-signal bridge:

1. `_interoceptive_workload_pressure(frame, default=0.1)` reads the `02` sensory batch, collects the cpu/memory interoceptive `pressure_value`s (from the reserved metadata keys), and returns a bounded aggregate (the max of cpu/memory load — the dominant resource pressure), or the `default` when none is present.
2. Both `NeuromodulatorAwareThoughtGateSignalBridge` (semantic) and `FirstVersionThoughtGateSignalBridge` (default) call it instead of hardcoding `0.1`.

Scope boundary: this changes only how `workload_pressure` is sourced. The gate weight (`* 0.45`), the resource-pressure block threshold, and every other gate-signal input are untouched. The `09` owner stays the sole owner of the gate decision.

## 2. Current State and Gap

Verified in code:

1. `thought_gating/engine.py` gate score includes `- signal_snapshot.workload_pressure * 0.45` and a block path: `workload_pressure >= policy.resource_pressure_block_threshold and continuation_signal < 0.25 -> blocked`. So `workload_pressure` is a real, load-suppressive gate term.
2. Both gate-signal bridges hardcode `workload_pressure=0.1`.
3. The R50 interoceptive stimuli normalize to `Stimulus(modality="interoceptive", metadata={"pressure_channel": <cpu|memory|latency|error>, "pressure_value": <float in [0,1]>})` and sit in the `02` batch, which runs before `09`.
4. The semantic gate-signal bridge already reads `frame.stage_results` for the `04` and `07` results, so reading the `02` result is the same pattern.

Gap: the load-suppressive gate term is constant; real machine load never reaches the gate.

## 3. Target Architecture

### 3.1 Owner-neutral helper (`helios_v2.composition.bridges`)

```
# Reuses the R51 reserved metadata keys (_PRESSURE_CHANNEL_METADATA_KEY / _PRESSURE_VALUE_METADATA_KEY
# are owned by the 05 feeling owner; the gate bridge reads the same reserved keys the 50 producer set).
_WORKLOAD_PRESSURE_CHANNELS = frozenset({"cpu", "memory"})

def _interoceptive_workload_pressure(frame, default: float = 0.1) -> float:
    """Owner-neutral: derive a bounded workload_pressure from the 02 interoceptive load stimuli.

    Returns the max cpu/memory pressure present in the current tick's sensory batch (the dominant
    resource pressure), or `default` when no recognized load stimulus is present. Reads only the
    reserved pressure metadata; skips unrecognized/out-of-range values; never raises."""
    from helios_v2.runtime.stages import SensoryIngressStageResult
    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult):
        return default
    pressures: list[float] = []
    for stimulus in sensory.batch.stimuli:
        if stimulus.modality != "interoceptive":
            continue
        metadata = stimulus.metadata or {}
        channel = metadata.get("pressure_channel")
        value = metadata.get("pressure_value")
        if channel not in _WORKLOAD_PRESSURE_CHANNELS:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if numeric < 0.0 or numeric > 1.0:
            continue
        pressures.append(numeric)
    if not pressures:
        return default
    return _clamp(round(max(pressures), 4), 0.0, 1.0)
```

Design choices:
- **max of cpu/memory**, not sum/mean: the dominant resource pressure governs allostatic load; max keeps it bounded in `[0,1]` without a normalization constant and is monotonic in each channel. (A weighted blend is a P5 refinement.)
- Reads the reserved keys the R50 producer set and R51 already consumes; it does not import the interoception owner (the afferent flows through `02`).
- `default=0.1` preserves the exact current value when no load stimulus exists.

### 3.2 Bridge edits

Both bridges replace `workload_pressure=0.1` with `workload_pressure=_interoceptive_workload_pressure(frame)`. `FirstVersionThoughtGateSignalBridge.build_signal_snapshot` already receives `frame`; the semantic bridge does too. No signature change.

### 3.3 Default rollout

When no interoceptive source is wired (default, recency-only, channel-bound-without-interoception, and semantic-without-sampler), the `02` batch carries no interoceptive stimulus, so the helper returns `0.1` — byte-for-byte the current behavior. The real value activates exactly when the interoceptive afferent is present.

## 4. Data Structures

No new contract. One module-level helper + a channel-set constant in `helios_v2.composition.bridges`. No change to `ThoughtGateSignalSnapshot`/`ThoughtGateResult`/`Stimulus`.

## 5. Module Changes

1. `helios_v2/src/helios_v2/composition/bridges.py`: add `_WORKLOAD_PRESSURE_CHANNELS` + `_interoceptive_workload_pressure`; call it in both gate-signal bridges.

## 6. Migration Plan

1. Additive helper; both bridges keep `0.1` whenever no load stimulus is present.
2. No contract or stage-order change; the afferent already flows through `02`.
3. The only behavior change is on assemblies that wire the interoceptive source, where `workload_pressure` now tracks real cpu/memory load.

## 7. Failure Modes and Constraints

1. No interoceptive load stimulus -> the defined constant `0.1` (current behavior), never a fabricated load.
2. Unrecognized channel / non-numeric / out-of-range `pressure_value` -> skipped, never raises (consistent with R51).
3. The derived value is bounded `[0,1]` and deterministic for a fixed batch; the `ThoughtGateSignalSnapshot.__post_init__` range check is a backstop.
4. The gate weight and block threshold are unchanged in the `09` owner; the bridge computes no gate score.
5. No `logging`/`print` under `src/`; the guard test stays green.
6. **Bounded end-to-end exercise (surfaced constraint).** Because `workload_pressure` is subtractive in the gate score (`* 0.45`) and high values trigger the gate's `resource_pressure_too_high` block, a high real load drives the gate to no-fire — and the assembled chain has no no-fire closure (directed retrieval raises on a non-fired gate). So R53's end-to-end tests stay within the firing window (cpu/memory up to ~0.3 given the other first-version constants), and the high-load -> high-`workload_pressure` -> block relationship is validated at the owner-neutral helper level. The full-range end-to-end exercise is unlocked by the separate gate-no-fire closure requirement (Future Extension Scope item 1). R53 does not weaken the gate or the block path; it only sources the input.

## 8. Observability and Logging

No new logging mechanism. The real value surfaces only in the existing `ThoughtGateResult.contributing_signals["workload_pressure"]` and (through the gate score) the fire/block decision.

## 9. Validation Strategy

Network-free, deterministic, using the existing `_ConfigurableInteroceptiveSampler` (R51) for high/at-rest pressure.

1. `test_runtime_composition.py` (extend):
   - Interoceptive assembly with a high cpu/memory sampler: `contributing_signals["workload_pressure"]` > 0.1 and equals the max cpu/memory channel; the gate score is lower than the same assembly at-rest; assert the value tracks the injected pressure.
   - At-rest interoceptive sampler (cpu=memory=0): `workload_pressure` is `0.0` (real zero load), distinct from the constant `0.1` — confirming the value is genuinely sourced.
   - No interoceptive source (default / semantic-without-sampler): `workload_pressure` stays `0.1` byte-for-byte.
   - A very high load with low continuation exercises the documented block path (gate blocked), demonstrating real load can restrain firing.
2. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_composition.py -q -k "workload or interocept"
```
