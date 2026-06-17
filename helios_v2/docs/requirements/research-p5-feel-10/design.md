# R-PROTO-LEARN.10 Design

## Architecture

```
LLM appraisal (7-dim feeling)
       |
       +-- (numpy_pinv)       (R-PROTO-LEARN.9)
       |     pinv(W) * (target - W*hormone)
       |     -> 9-dim delta
       |
       +-- (appraisal_derived) (R-PROTO-LEARN.10, NEW)
             |
             v
        _default_feeling_to_salience(7-dim) -> 5-dim salience
        (Panksepp 7 systems + Fermin 2021 grounded)
             |
             v
        RapidAppraisalBatch (1 appraisal)
             |
             v
        AppraisalDerivedNeuromodulatorUpdatePath.update_levels(
            batch, config, tick_id, prior_levels)  <- owner 04 R36
             |
             v
        NeuromodulatorLevels (9-dim) -> per-channel delta
        delta = strength * (new - current), clipped to +/-1
             |
             v
        effective_hormone = current + delta
        effective_feeling = W * effective_hormone
        residual = LLM - effective_feeling
```

## Why two paths

| Dimension | numpy_pinv (R9) | appraisal_derived (R10) |
|---|---|---|
| Mathematically exact | Yes | No (by design) |
| Biologically plausible | No | Yes |
| Requires NeuromodulatorConfig | No | Yes |
| Requires AppraisalDerivedNeuromodulatorUpdatePath | No | Yes |
| Real LLM closed-loop residual | Smaller | Larger |
| Final regime in 20-tick smoke | habitual | model_based |
| Commits in 20-tick smoke | 3 | 0 |
| Purpose | Math demonstration | Production realism |

## Why the default feeling->salience mapper is heuristic

The owner 03 `RapidSalienceVector` is the actual wire format that owner
04 `AppraisalDerivedNeuromodulatorUpdatePath.update_levels()` consumes.
It has 5 fields: threat / reward / novelty / social / uncertainty.
P5-feel's LLM appraisal is a 7-dim feeling vector. There is no
canonical 7->5 mapping in the helios runtime (this is a research
question, not a contract).

The default mapper uses Panksepp 7 systems + Fermin 2021 IMAC role
assignments as the ground truth:
- `threat = (1 - valence) * tension + pain * 0.7` (Panksepp RAGE/FEAR)
- `reward = valence * (1 - fatigue) * (1 - pain)` (Panksepp SEEKING)
- `novelty = arousal * (1 - comfort)` (Fermin 2021 aINS exploratory)
- `social = social_safety * (1 - threat)` (Panksepp CARE/PANIC)
- `uncertainty = (1 - valence) * (1 - comfort) * arousal`
  (Fermin 2021 dINS model-based)

These mappings are heuristics and can be replaced by a learned mapper
in a later P5 slice without changing the P5-feel public contract --
callers may inject their own `FeelingToSalienceMapper` Protocol
implementation via `config.appraisal_salience_mapper`.

## Why the real owner 04 path uses `prior_levels`

`AppraisalDerivedNeuromodulatorUpdatePath.update_levels()` is
stateless and reads no prior-tick levels (R43 dual-timescale decay is
the wrapper). For P5-feel, we pass the current hormone state as
`prior_levels` so the resulting `NeuromodulatorLevels` reflects the
small perturbation implied by the LLM appraisal, not the absolute
target. This means the per-channel `delta = new - current` is small
(typically 0.1-0.4 per channel) and the strength-scaled, clipped
delta is well within [-1, +1].

## Failure semantics

- `P5FeelLearningConfig(hormone_path='appraisal_derived')` requires
  3 injected dependencies. Missing any one raises `ValueError` with
  a clear message listing all missing fields.
- `_default_feeling_to_salience` clamps each salience dim to [0, 1].
- `_compute_appraisal_derived_hormone` clips the per-channel delta
  to [-1, +1].
- All other errors (NaN inputs, illegal level values) propagate as
  exceptions and are NOT silently swallowed (per owner decision
  2026-06-17 5:50, no silent degradation).

## Out-of-scope (left for later slices)

- Replace the heuristic feeling->salience mapper with a learned one
  (would need training data, a new owner 03 path, etc.).
- Wire P5-feel to consume the real owner 04 state (currently the
  real hormone state is read-only; P5-feel only sees what caller
  passes in `hormone_state`).
- Add a per-dim `closed_loop_residual_threshold` config so R10 path
  can also trigger commit (current 0.3 threshold is fine for R9 but
  R10 leaves larger residuals by design).
