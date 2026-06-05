# Requirement 38 - Neuromodulator-derived feeling (design)

## 1. Design Overview

R38 replaces the constant `05` feeling construction shim with a deterministic neuromodulator-derived construction path owned by the `05` feeling owner, under the existing semantic-memory opt-in. This is the cleanest de-shim so far: the `05` owner already receives the complete `04` `NeuromodulatorState` every tick, so there is no contract change, no new bridge, and no stage reorder. Only the injected construction path changes.

The design mirrors R35/R37 boundary discipline (the cognitive mapping lives in the owner) and R36's bounded-equation shape (`clamp(baseline + sum(coeff * delta))`):

1. The `05` owner gains an owner-private `NeuromodulatorDerivedFeelingConstructionPath` in `feeling/engine.py` that owns the channel->dimension mapping.
2. Composition selects that owner-provided path (instead of `FirstVersionFeelingConstructionPath`) only under the semantic-memory opt-in.

## 2. Current State and Gap

Stage order is `... 03 appraisal -> 04 neuromodulator -> 05 feeling -> 06 ...`. The `InteroceptiveFeelingRuntimeStage` reads the `neuromodulator_system` stage result and calls `feeling_layer.update_state(neuromodulator_result.state, internal_signals, tick_id=...)`. So `05` already holds the real `04` state.

Today `FirstVersionFeelingConstructionPath.construct_feeling` does `del neuromodulator_state, internal_signals, config, tick_id` and returns a fixed vector `(valence=0.4, arousal=0.7, tension=0.5, comfort=0.2, fatigue=0.3, pain_like=0.1, social_safety=0.4)`. The real `04` state has zero effect on feeling. R38 closes that gap.

## 3. Target Architecture

### 3.1 Data flow (semantic-memory assembly)

```
04 NeuromodulatorStageResult.state.levels
        |  (already passed into 05 by InteroceptiveFeelingRuntimeStage)
        v
05 InteroceptiveFeelingEngine.update_state(neuromodulator_state, internal_signals, tick_id)
        |  injected NeuromodulatorDerivedFeelingConstructionPath.construct_feeling(...)
        v
InteroceptiveFeelingVector: per dimension
   clamp(baseline_dim + sum(coupling_k * (level_k - reference_k)), legal_min_dim, legal_max_dim)
        v
InteroceptiveFeelingState (unchanged contract) -> 06 memory-affect
```

In the default/recency/offline assemblies the constant `FirstVersionFeelingConstructionPath` runs unchanged.

### 3.2 Ownership

- channel->dimension mapping (the feeling subjectivation semantic): owned by the `05` engine module (`NeuromodulatorDerivedFeelingConstructionPath`). This is `05`'s entire reason to exist, so it belongs in the owner, not in composition.
- selecting the path under the opt-in: owned by composition assembly (a wiring choice, like selecting `AppraisalDerivedNeuromodulatorUpdatePath` for `04`).

### 3.3 The bounded mapping (owner-private)

Reference point: each channel contributes via its deviation from a neutral reference level. First-version reference is `0.0` for every channel (so the contribution is `coupling_k * level_k`), keeping the first version a simple bounded linear combination around the configured `baseline_feeling`. The mapping is then clamped into `[legal_min, legal_max]` per dimension.

First-version coupling table (explicit bounded constants; `+` raises, `-` lowers the dimension):

| dimension | + channels (coeff) | - channels (coeff) |
| --- | --- | --- |
| valence | dopamine (0.30), opioid_tone (0.15), serotonin (0.15) | cortisol (0.30) |
| arousal | norepinephrine (0.40), excitation (0.20) | - |
| tension | cortisol (0.40), norepinephrine (0.20) | - |
| comfort | opioid_tone (0.30), oxytocin (0.20), serotonin (0.15) | cortisol (0.30) |
| pain_like | cortisol (0.40) | opioid_tone (0.35) |
| social_safety | oxytocin (0.40), serotonin (0.15) | cortisol (0.25) |
| fatigue | inhibition (0.20) | excitation (0.20) |

Each dimension value is `clamp(baseline.dim + sum(+coeff * level) - sum(-coeff * level), legal_min.dim, legal_max.dim)`. Determinism: pure arithmetic on the levels + config; no clock, no prior-tick read. Boundedness: every dimension is clamped into its configured legal range, so no divergence regardless of coefficients.

The coefficients are organized so they map onto the config's declared `feeling_mapping_strength` / `feeling_coupling_strength` learned-parameter categories conceptually (the direct level->dimension gains are mapping strength; the cross-channel up/down combinations are coupling strength). `feeling_persistence` is intentionally unused this slice (stateless).

## 4. Data Structures

No new or changed contract. The new behavior lives entirely inside a new `FeelingConstructionPath` implementation that returns the existing `InteroceptiveFeelingVector`. The `InteroceptiveFeelingConfig` (with `baseline_feeling`, `legal_min`, `legal_max`) is consumed as-is.

### 4.1 `NeuromodulatorDerivedFeelingConstructionPath` (new owner-private path)

```python
@dataclass
class NeuromodulatorDerivedFeelingConstructionPath(FeelingConstructionPath):
    # explicit bounded first-version coupling coefficients (per the table above)
    def construct_feeling(self, neuromodulator_state, internal_signals, config, tick_id) -> InteroceptiveFeelingVector:
        del internal_signals, tick_id  # this slice derives from neuromodulator levels only
        levels = neuromodulator_state.levels
        base = config.baseline_feeling
        low = config.legal_min
        high = config.legal_max
        return InteroceptiveFeelingVector(
            valence=_clamp(base.valence + 0.30*levels.dopamine + 0.15*levels.opioid_tone + 0.15*levels.serotonin - 0.30*levels.cortisol, low.valence, high.valence),
            ...
        )
```

A small module-private `_clamp(value, low, high)` mirrors the pattern already used in `04`'s appraisal-derived path.

## 5. Module Changes

1. `feeling/engine.py`: add `NeuromodulatorDerivedFeelingConstructionPath` (implements the existing `FeelingConstructionPath` protocol) plus a module-private `_clamp`. The engine, the protocol, and `FirstVersionFeelingConstructionPath` (which lives in composition) are unchanged.
2. `feeling/__init__.py`: export `NeuromodulatorDerivedFeelingConstructionPath` so composition can select it.
3. `composition/runtime_assembly.py`: when `semantic_memory_enabled`, build the `InteroceptiveFeelingEngine` with `construction_path=NeuromodulatorDerivedFeelingConstructionPath()`; otherwise keep `FirstVersionFeelingConstructionPath()`.
4. `composition/bridges.py`: unchanged except imports if needed; the constant `FirstVersionFeelingConstructionPath` stays for the default assembly.

## 6. Migration Plan

1. Add the owner-private path; it is inert until selected.
2. Switch the assembly selection behind `semantic_memory_enabled` (the existing R35/R36/R37 opt-in flag; no new flag).
3. The default assembly continues to construct `FirstVersionFeelingConstructionPath`, so its behavior and tests are unchanged.

No full rewrite: the feeling contracts, the engine, the dominant-dimension reporter, and the constant path are preserved; only the construction input gains a real source under the opt-in.

## 7. Failure Modes and Constraints

1. Malformed neuromodulator state: rejected by the existing `05` `_validate_neuromodulator_state` before the construction path runs (`InteroceptiveFeelingError`).
2. Out-of-range feeling value: structurally impossible because every dimension is clamped into the configured legal range; a focused test asserts every dimension stays within `[legal_min, legal_max]` for extreme neuromodulator states.
3. Stateless: no prior-tick feeling is read by the construction path. The dual-timescale `feeling_persistence` category is intentionally unused this slice.
4. No NN, no hidden branch keyed on content: the mapping is a fixed bounded linear combination plus clamp.
5. No fallback: when enabled the path always derives from the real state; when disabled the constant path runs.

## 8. Observability and Logging

No new logging mechanism. Feeling travels only through the existing `InteroceptiveFeelingState`/`InteroceptiveFeelingVector` contracts and the existing `PublishInteroceptiveFeelingStateOp` (dominant dimensions). No `logging`/`print` anywhere under `src`; the guard test stays green.

## 9. Validation Strategy

1. Engine tests (`test_interoceptive_feeling_engine.py`):
   - high-cortisol vs low-cortisol state -> higher tension and pain_like, lower valence and comfort;
   - high-dopamine -> higher valence; high-norepinephrine -> higher arousal; high-oxytocin -> higher social_safety;
   - all dimensions within `[legal_min, legal_max]` for extreme states (clamping holds);
   - determinism for identical inputs;
   - the derived path differs from the constant path for a non-baseline state (the de-shim is real).
2. Composition tests (`test_runtime_composition.py`):
   - the semantic-memory assembly produces different feeling (tension/pain_like) across two ticks whose `04` cortisol differs (read from the `05` stage result), driven by the real novelty->`04` chain;
   - the default assembly keeps the constant feeling vector (valence=0.4, arousal=0.7, ...).
3. Guard + full gate: `test_no_adhoc_logging_guard.py` plus `pytest helios_v2/tests -q` stays green and network-free.
