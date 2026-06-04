# Requirement 37 - Neuromodulatory gating coupling (design)

## 1. Design Overview

R37 wires the real `04` norepinephrine level into the `09` thought-gating decision, under the existing semantic-memory opt-in, without a stage reorder and without moving gating policy out of the `09` owner.

The design has three moving parts, mirroring the R35/R36 boundary discipline (composition forwards a raw fact; the owner owns the cognitive mapping):

1. The `09` owner gains one additive optional raw input field on `ThoughtGateSignalSnapshot` (`neuromodulatory_arousal: float | None`).
2. The `09` owner gains an arousal-aware gate path that owns how that raw fact maps into the gate score, bounded so it never single-handedly forces or suppresses a fire.
3. Composition gains an arousal-forwarding gate-signal bridge that reads the `04` `NeuromodulatorStageResult` already present in `frame.stage_results` and forwards `levels.norepinephrine` verbatim as the raw fact. Assembly selects the arousal-aware path + forwarding bridge only under the semantic-memory opt-in.

## 2. Current State and Gap

Stage order is `02 sensory -> 03 appraisal -> 04 neuromodulator -> 05 feeling -> 06 -> 07 -> 08 conscious -> 09 gating` (`CANONICAL_STAGE_ORDER`). So when `ThoughtGatingRuntimeStage.run` executes, `frame.stage_results["neuromodulator_system"]` is already a populated `NeuromodulatorStageResult` carrying `state.levels.norepinephrine`.

Today:

- `ThoughtGateSignalSnapshot` has `workload_pressure`, `global_activation_level`, `temporal_signal`, `drive_urgency_signal`, `dmn_available`, `selected_stimuli`. No neuromodulator input.
- `FirstVersionThoughtGatePath.evaluate` computes `gate_score = clamp(stimulus*0.30 + continuation*0.30 + global_activation_level*0.20 + drive_urgency*0.10 + temporal*0.10 + (0.10 if dmn else 0) - workload*0.45)`. The `global_activation_level*0.20` term is the natural arousal slot.
- `FirstVersionThoughtGateSignalBridge.build_signal_snapshot` hardcodes `global_activation_level=0.9` (and the other fields) every tick. The `04` result is never read.

Gap: the real `04` arousal has zero causal effect on gating. R37 closes that gap for the norepinephrine channel.

## 3. Target Architecture

### 3.1 Data flow (coupled assembly)

```
04 NeuromodulatorStageResult (in frame.stage_results)
        |
        |  composition reads levels.norepinephrine (raw fact, no mapping)
        v
NeuromodulatorAwareThoughtGateSignalBridge.build_signal_snapshot(frame, conscious_result)
        |  sets ThoughtGateSignalSnapshot.neuromodulatory_arousal = norepinephrine
        v
09 ThoughtGatingEngine.evaluate_gate(...)
        |  injected ArousalAwareThoughtGatePath
        v
gate_score incorporates an owner-owned bounded arousal contribution;
ThoughtGateResult.contributing_signals["neuromodulatory_arousal"] = arousal
```

In the default/recency/offline assemblies the field stays `None`, the first-version path runs unchanged, and the snapshot is byte-for-byte equivalent to today.

### 3.2 Ownership

- `neuromodulatory_arousal` raw fact field: owned by the `09` contract (it is a `09` input), validated `[0,1]`.
- arousal-to-gate-score mapping: owned by the `09` engine (the arousal-aware gate path). This is the cognitive semantic and must not live in composition.
- the act of forwarding the `04` level: owned by composition glue (a raw fact relay, exactly like R35's `MemoryGroundedSimilaritySource` forwarding raw cosine).

### 3.3 The bounded coupling rule (owner-private)

The arousal-aware path keeps the first-version gate-score structure and adds one distinct bounded term driven by the real arousal fact. It does not touch the existing `global_activation_level` term (that input stays its own, separately-owned, still-first-version constant; de-shimming it from `07` workspace is a later slice):

- Let `arousal = snapshot.neuromodulatory_arousal`. When `None`, the path is byte-for-byte the first-version computation (no arousal term).
- When present, add a single non-negative term `arousal_gain * arousal` to the existing gate-score sum, with `arousal_gain` an explicit bounded first-version constant under the `gate_policy` learned-parameter category. First-version `arousal_gain = 0.15`.
- `gate_score = clamp(<existing first-version sum> + arousal_gain * arousal)`. The existing terms (stimulus, continuation, `global_activation_level * 0.20`, drive_urgency, temporal, dmn, minus workload) are unchanged.
- `contributing_signals["neuromodulatory_arousal"] = arousal` (the raw fact, already `[0,1]`, consistent with the map's existing validation) is recorded when arousal is present.

Safety / "never a hard gate by itself":
- It cannot solely force a fire: the arousal term contributes at most `arousal_gain = 0.15`, which is below `fire_threshold = 0.55`, so a tick with no other supporting signal stays sub-threshold regardless of arousal.
- It cannot solely suppress a fire: the term is additive and non-negative, so it can only raise (never lower) the gate score; a fire that the other terms already justify is never flipped to no_fire by arousal.

Monotonicity: `gate_score` is non-decreasing in `arousal` because the added term has a positive coefficient and all other terms are independent of arousal. Determinism: pure arithmetic on snapshot fields; no clock, no prior-tick read.

The no-fire reason taxonomy, the continuation-pressure transition, and the trigger-reason logic are unchanged.

## 4. Data Structures

### 4.1 `ThoughtGateSignalSnapshot` (additive field)

```python
@dataclass(frozen=True)
class ThoughtGateSignalSnapshot:
    snapshot_id: str
    source_conscious_state_id: str
    workload_pressure: float
    global_activation_level: float
    temporal_signal: float
    drive_urgency_signal: float
    dmn_available: bool
    selected_stimuli: tuple[SelectedStimulusSummary, ...] = ()
    tick_id: int | None = None
    neuromodulatory_arousal: float | None = None  # R37: raw 04 norepinephrine fact, [0,1], None = uncoupled
```

`__post_init__` validates `neuromodulatory_arousal` to `[0,1]` only when not None (reusing `_validate_unit_interval`). The field is last and defaulted, so all existing positional/keyword constructions stay valid and uncoupled snapshots are unchanged.

### 4.2 `ArousalAwareThoughtGatePath` (new owner-private path)

A `ThoughtGatePath` implementation in `thought_gating/engine.py`. It reuses the first-version decision structure (shared via a small private helper or subclass) and only adds one non-negative arousal term to the gate-score sum when `neuromodulatory_arousal` is present; the existing terms (including `global_activation_level`) are untouched. Bounded constant: `arousal_gain` (explicit first-version value `0.15` under the `gate_policy` learned-parameter category, P5-learnable later).

### 4.3 `NeuromodulatorAwareThoughtGateSignalBridge` (new composition bridge)

Reads `frame.stage_results["neuromodulator_system"]` as `NeuromodulatorStageResult`, takes `state.levels.norepinephrine`, and builds the same snapshot as the first-version bridge plus `neuromodulatory_arousal=that level`. It forwards the raw value with no mapping. A missing/wrong-typed neuromodulator result is the existing fail-fast stage error (the helper `_require_stage_result` pattern), not a degraded uncoupled snapshot.

## 5. Module Changes

1. `thought_gating/contracts.py`: add the optional field + its validation. No other contract changes.
2. `thought_gating/engine.py`: add `ArousalAwareThoughtGatePath`. Refactor the score computation so the first-version and arousal-aware paths share the structure with only the optional added arousal term differing (keep `FirstVersionThoughtGatePath` behavior identical for `None`, and never modify the `global_activation_level` term). Export nothing new from the engine that breaks the existing API.
3. `thought_gating/__init__.py`: export `ArousalAwareThoughtGatePath` for composition.
4. `composition/bridges.py`: add `NeuromodulatorAwareThoughtGateSignalBridge`. Import the `04` `NeuromodulatorStageResult` type for an isinstance/typed read (mirroring how runtime stages use `_require_stage_result`). The first-version bridge stays.
5. `composition/runtime_assembly.py`: when `semantic_memory_enabled`, build the `ThoughtGatingEngine` with `gate_path=ArousalAwareThoughtGatePath()` and register the stage with `signal_provider=NeuromodulatorAwareThoughtGateSignalBridge()`; otherwise keep `FirstVersionThoughtGatePath()` + `FirstVersionThoughtGateSignalBridge()`.

## 6. Migration Plan

1. Land the additive optional contract field first; the whole suite stays green because the field defaults to `None` and the first-version path ignores it.
2. Add the arousal-aware path and assert (in unit tests) it is identical to the first-version path when `neuromodulatory_arousal is None`.
3. Add the forwarding bridge and the assembly selection behind `semantic_memory_enabled` (the existing R35/R36 opt-in flag; no new flag).
4. The default assembly continues to construct the first-version bridge and path, so its behavior and tests are unchanged.

No full rewrite: the gate-score formula, the decision taxonomy, and the continuation-pressure logic are preserved; only the activation input gains a real source under the opt-in.

## 7. Failure Modes and Constraints

1. Coupling enabled but `04` result missing/mis-typed in the frame: fail fast via the existing stage-result requirement (`RuntimeStageExecutionError`), never a silent uncoupled fallback.
2. `neuromodulatory_arousal` out of `[0,1]`: rejected by `ThoughtGateSignalSnapshot.__post_init__` (`ThoughtGatingError`).
3. Arousal must never be a hard gate: structurally guaranteed because the arousal term is a non-negative additive contribution with weight `arousal_gain = 0.15` below the `0.55` fire threshold (see 3.3); a focused test asserts arousal alone cannot flip an otherwise sub-threshold tick to fire, and cannot suppress a fire other signals justify.
4. Stateless: no prior-tick gate or neuromodulator state is read by the coupling. The existing continuation-pressure carry is unrelated and unchanged.
5. No NN, no hidden branch keyed on content: the mapping is a fixed bounded arithmetic blend.

## 8. Observability and Logging

No new logging mechanism. The arousal influence is visible through `ThoughtGateResult.contributing_signals["neuromodulatory_arousal"]`, which is already part of the published gate-result contract and already range-validated. No `logging`/`print` anywhere under `src`; the guard test stays green.

## 9. Validation Strategy

1. Contract test (`test_thought_gating_contracts.py`): `neuromodulatory_arousal` defaults to `None`; valid value in `[0,1]` accepted; out-of-range rejected with `ThoughtGatingError`.
2. Engine tests (`test_thought_gating_engine.py`):
   - arousal-aware path with `None` arousal produces an identical result to `FirstVersionThoughtGatePath` for the same inputs;
   - higher arousal yields a gate score `>=` lower arousal (monotonic), with a strict increase when other signals leave headroom;
   - arousal alone (all other gate signals at/below their no-fire floors) cannot produce `fire`;
   - a tick that other signals already push to `fire` is not flipped to `no_fire` by the lowest arousal;
   - `contributing_signals` contains `neuromodulatory_arousal` when present;
   - determinism for identical inputs.
3. Composition tests (`test_runtime_composition.py`):
   - the coupled (semantic-memory) assembly produces a different `contributing_signals["neuromodulatory_arousal"]` (and a different/`>=` gate score) across two ticks whose `03` novelty differs, read from the `09` stage result;
   - the default assembly's gate snapshot has `neuromodulatory_arousal is None` and its gate behavior is unchanged.
4. Guard + full gate: `test_no_adhoc_logging_guard.py` plus `pytest helios_v2/tests -q` stays green and network-free.
