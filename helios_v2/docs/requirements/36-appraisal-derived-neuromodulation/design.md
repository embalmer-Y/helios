# Requirement 36 - Appraisal-derived neuromodulation (design)

## 1. Design Overview

R36 replaces the constant neuromodulator update path with a deterministic appraisal-derived one, so the real `03` salience (especially the R35 novelty signal) shapes the `04` neuromodulator state. It is the second P3 cognitive-owner de-shim and reuses the exact injection pattern R35 used: the owner defines/keeps its `NeuromodulatorUpdatePath` protocol, and composition provides a first-version implementation in `bridges.py` (mirroring where `FirstVersionNeuromodulatorUpdatePath` lives today).

One additive, opt-in piece:

1. `AppraisalDerivedNeuromodulatorUpdatePath` (in `composition/bridges.py`): a pure function of the `RapidAppraisalBatch` + `NeuromodulatorConfig` that aggregates the batch's coarse salience (per-dimension max), maps it to channel deltas via explicit bounded sensitivity coefficients, adds the configured tonic baseline, and clamps each channel into its legal range.
2. Opt-in selection in `assemble_runtime`: when `03` produces real signals (the semantic-memory assembly, where R35 novelty is real), `04` is assembled with the appraisal-derived path; otherwise the constant path is kept unchanged.

The `04` owner engine, its contracts, and every other owner are untouched. The derivation is stateless (no prior-tick levels), deterministic, bounded, and never diverges outside the legal range.

## 2. Current State and Gap

Current state:

1. `04` `NeuromodulatorEngine.update_state` validates the batch, calls an injected `NeuromodulatorUpdatePath.update_levels(batch, config, tick_id)`, and wraps the result in a `NeuromodulatorState`. The engine is real and owner-correct.
2. Composition injects `FirstVersionNeuromodulatorUpdatePath` (in `bridges.py`), whose `update_levels` does `del batch, config, tick_id` and returns a fixed constant `NeuromodulatorLevels`.
3. R35 made `03` novelty real; that real `RapidAppraisalBatch` is exactly what flows into `04.update_state`, but the constant path ignores it.

Gap: the real appraisal signal dies at `04`. No appraisal difference changes the neuromodulator state.

## 3. Target Architecture

### 3.1 Appraisal-derived update path (composition-provided, owner-protocol-conforming)

The new path implements the owner's existing `NeuromodulatorUpdatePath` protocol and lives in `composition/bridges.py` next to `FirstVersionNeuromodulatorUpdatePath`:

```
@dataclass
class AppraisalDerivedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    # First-version bounded sensitivity coefficients (P5-learnable later).
    novelty_to_norepinephrine: float = 0.5
    uncertainty_to_norepinephrine: float = 0.3
    reward_to_dopamine: float = 0.5
    novelty_to_dopamine: float = 0.15        # weak exploration drive
    threat_to_cortisol: float = 0.5

    def update_levels(self, batch, config, tick_id) -> NeuromodulatorLevels:
        del tick_id
        salience = _aggregate_salience(batch)            # per-dimension max across appraisals
        base = config.tonic_baseline
        return NeuromodulatorLevels(
            dopamine=_clamp(base.dopamine
                            + self.reward_to_dopamine * salience.reward
                            + self.novelty_to_dopamine * salience.novelty,
                            config.legal_min.dopamine, config.legal_max.dopamine),
            norepinephrine=_clamp(base.norepinephrine
                                  + self.novelty_to_norepinephrine * salience.novelty
                                  + self.uncertainty_to_norepinephrine * salience.uncertainty,
                                  config.legal_min.norepinephrine, config.legal_max.norepinephrine),
            cortisol=_clamp(base.cortisol
                            + self.threat_to_cortisol * salience.threat,
                            config.legal_min.cortisol, config.legal_max.cortisol),
            # Remaining channels regress to tonic baseline (clamped for safety) in this slice.
            serotonin=_clamp(base.serotonin, config.legal_min.serotonin, config.legal_max.serotonin),
            acetylcholine=_clamp(base.acetylcholine, config.legal_min.acetylcholine, config.legal_max.acetylcholine),
            oxytocin=_clamp(base.oxytocin, config.legal_min.oxytocin, config.legal_max.oxytocin),
            opioid_tone=_clamp(base.opioid_tone, config.legal_min.opioid_tone, config.legal_max.opioid_tone),
            excitation=_clamp(base.excitation, config.legal_min.excitation, config.legal_max.excitation),
            inhibition=_clamp(base.inhibition, config.legal_min.inhibition, config.legal_max.inhibition),
        )
```

`_clamp(value, lo, hi)` is a tiny bounded helper. The mapping is a fixed linear combination plus clamp — no NN, no runtime strategy branch, no divergence.

### 3.2 Batch salience aggregation

```
@dataclass(frozen=True)
class _AggregatedSalience:
    threat: float; reward: float; novelty: float; social: float; uncertainty: float

def _aggregate_salience(batch) -> _AggregatedSalience:
    if not batch.appraisals:
        return _AggregatedSalience(0.0, 0.0, 0.0, 0.0, 0.0)   # empty batch -> baseline only
    vecs = [a.salience for a in batch.appraisals]
    return _AggregatedSalience(
        threat=max(v.threat for v in vecs),
        reward=max(v.reward for v in vecs),
        novelty=max(v.novelty for v in vecs),
        social=max(v.social for v in vecs),
        uncertainty=max(v.uncertainty for v in vecs),
    )
```

Per-dimension max: the most salient stimulus drives modulation (winner-takes-attention). An empty batch produces all-zero salience, so the result is exactly the tonic baseline (clamped) — no divergence, no error.

### 3.3 Channel mapping (cautious brain-function reading)

| Channel | Driven by | Rationale (brain.mmd) |
| --- | --- | --- |
| dopamine | reward (+ weak novelty) | DA tracks reward prediction; novelty adds bounded exploration drive |
| norepinephrine | novelty + uncertainty | NE tracks alertness / novelty / uncertainty |
| cortisol | threat | stress/threat axis |
| serotonin, acetylcholine, oxytocin, opioid_tone, excitation, inhibition | none this slice | regress to tonic baseline; their real drivers are later slices |

The coefficients are first-version bounded constants under the config's declared learned-parameter categories (`channel_gain_sensitivity` etc.), the surface P5 tunes later.

### 3.4 Opt-in selection in assembly

`assemble_runtime` selects the update path the same way R35 selected the dimension estimator:

1. `experience_store` and `embedding_gateway` both present (the semantic-memory assembly, where `03` novelty is real) -> `AppraisalDerivedNeuromodulatorUpdatePath()`.
2. otherwise -> the existing `FirstVersionNeuromodulatorUpdatePath()` (unchanged).

No new public assembly flag; the trigger is the existing semantic-memory opt-in, consistent with R35. Deriving neuromodulation from appraisal only matters once appraisal itself is real, so the two de-shims share one trigger.

### 3.5 Default rollout

Default-off. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep `FirstVersionNeuromodulatorUpdatePath` and the constant levels. Only the semantic-memory assembly gains appraisal-derived neuromodulation.

## 4. Data Structures

No new cross-owner data contract. `NeuromodulatorLevels`, `NeuromodulatorState`, `NeuromodulatorConfig`, `RapidAppraisalBatch` are unchanged. New types (in `composition/bridges.py`):

1. `AppraisalDerivedNeuromodulatorUpdatePath` — implements `NeuromodulatorUpdatePath`; deterministic linear-combination-plus-clamp derivation with bounded coefficients.
2. `_AggregatedSalience` + `_aggregate_salience` + `_clamp` — owner-neutral helpers, module-private.

## 5. Module Changes

1. `helios_v2/src/helios_v2/composition/bridges.py`: add `AppraisalDerivedNeuromodulatorUpdatePath` and the private helpers. It imports the appraisal `RapidSalienceVector`/batch types it already has access to and the `NeuromodulatorLevels`/`NeuromodulatorUpdatePath` it already imports; it reads no other owner's state.
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: select `AppraisalDerivedNeuromodulatorUpdatePath` for the `NeuromodulatorEngine` when the semantic-memory assembly is active; keep `FirstVersionNeuromodulatorUpdatePath` otherwise.
3. No change to `helios_v2/src/helios_v2/neuromodulation/*`: the owner engine and its `NeuromodulatorUpdatePath` protocol already support the injection.

## 6. Migration Plan

1. All new code is additive in composition. The default `FirstVersionNeuromodulatorUpdatePath` path is unchanged and remains the default.
2. No contract changes; `05` feeling and later consumers receive the same `NeuromodulatorState` shape — only the levels change when the derived path is enabled.
3. No stage-order change; `04` is the same stage with a different injected update path.
4. The semantic-memory assembly automatically gains derived neuromodulation (same trigger as R35), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. Empty appraisal batch: all-zero aggregated salience -> tonic-baseline levels (clamped). No error, no divergence.
2. Out-of-range arithmetic: every channel is clamped into `[legal_min, legal_max]`, so the `NeuromodulatorLevels` contract is always satisfied; coefficients are bounded so a single tick cannot diverge.
3. Malformed batch: rejected by the existing `04` engine validation before the update path runs (unchanged).
4. Statelessness: the path reads no prior-tick levels; identical batch + config always yields identical levels. Dual-timescale decay is explicitly deferred.
5. The update path reads only the batch + config; it imports/reaches no other owner's state and produces no feeling/action semantics.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. Levels travel only through `NeuromodulatorState`/`NeuromodulatorLevels`. The path emits nothing itself.

## 9. Validation Strategy

Network-free, deterministic.

1. `test_neuromodulator_engine.py` (extend): drive the engine with `AppraisalDerivedNeuromodulatorUpdatePath` and a config with a known tonic baseline + legal range:
   - a high-novelty appraisal batch yields higher norepinephrine than a low-novelty batch; a high-reward batch yields higher dopamine; a high-threat batch yields higher cortisol.
   - an empty batch yields the tonic-baseline levels (clamped).
   - all produced levels lie within the legal range; identical batch -> identical levels (determinism).
   - non-driven channels (serotonin, etc.) equal the clamped tonic baseline regardless of salience.
2. `test_runtime_composition.py` (extend): in the semantic-memory assembly, two ticks whose appraisal differs in novelty (for example a cold store -> max novelty tick vs a tick whose stimulus matches stored experience -> lower novelty) produce measurably different norepinephrine levels at the `04` stage result; the default assembly keeps the constant levels.
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_neuromodulator_engine.py -q
```
