# Design 79c - R79-C Hormone Predict Corroborator and 5-HT / Oxy / Opioid Drivers

## 1. Architecture Overview

R79-C sits inside the existing 3-owner R79 pipeline:

```
[02 sensory] → [03 appraisal] → [04 neuromodulation] → [05 feeling] → ...
                                          ↑
                          R79-C: 3 new driver lines + corroborator
                                          
[16 prompt_contract] → LLM JSON envelope → [R79-B post-processor dispatch]
                ↑
      R79-C: 12th field `hormone_response_i_predict`
                ↓
   [R79-D baseline framework reads LLM JSON + corroborator output]
```

R79-C touches two existing owner packages and adds one new module. It does
not introduce new owners or new owner boundaries.

```
helios_v2/
├── neuromodulation/                          [04 owner — modified + 1 new file]
│   ├── contracts.py                          [+1 literal: hormone_predict_coupling]
│   ├── engine.py                             [+3 fields, ~10 lines]
│   ├── corroborator.py                       [NEW: corroborator owner class]
│   └── __init__.py                           [+4 exports]
└── prompt_contract/                          [16 owner — modified]
    └── engine.py                             [+1 schema field, +1 hard rule]
```

## 2. Design Decisions

### 2.1 Why a separate corroborator file (not engine.py)?

The corroborator is conceptually a **separate cognitive policy** from the
formula-derived drive:

- The `AppraisalDerivedNeuromodulatorUpdatePath` is owned by the `04`
  neuromodulator's instantaneous drive; its equation shape is
  `clamp(baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)`.
- The `HormonePredictCorroborator` is owned by the `04` neuromodulator's
  **LLM-predict coupling** policy; its equation shape is
  `classify(formula_drive, LLM predict) → verdict × magnitude → bias`.

Mixing them in `engine.py` would conflate the two policies and violate the
"one owner = one well-defined cognitive policy" rule. The corroborator also
needs its own unit tests (silent / corroborate / conflict / magnitude
matching) that are independent of the appraisal-batch path's tests.

The corroborator imports only `helios_v2.neuromodulation.contracts` (same
package, no cross-owner import).

### 2.2 Why does the corroborator not consume the bias internally?

The corroborator is a **producer** of a bias vector, not a consumer of
it. The consumer is the **next tick's** `RapidAppraisalBatch` (via a
future composition bridge, R80 scope). The corroborator must not feedback
on its own tick because:

1. The LLM's `hormone_response_i_predict` is a prediction *of* the
   current stimulus's effect on the body; the corroborator measures
   whether the formula agrees; if we feedback the bias on the same
   tick, the formula and the LLM's predict would co-vary on the same
   input, which is circular.
2. R79-D baseline framework tests show the bias series is non-trivial
   (A_praise has coherent LLM predict, B_neglect has near-zero LLM
   predict); if we feedback on the same tick, the next-tick `5-HT / Oxy
   / Opioid` would also be biased, polluting the next scenario's
   baseline.

The bias travels through the dual-timescale integrator (R43) as a
non-zero initial offset, so the per-tick `5-HT / Oxy / Opioid` series
under R79-C reflects the formula AND the corroborated LLM predict —
which is the entire point of R79-C.

### 2.3 Why `5-HT / Oxy / Opioid` from rapid-appraisal salience (not from feeling)?

The requirement §3.1 says these three channels should be driven by
appraisal salience. The `RapidSalienceVector` has 5 dimensions
(threat / reward / novelty / social / uncertainty) — these are coarse
early signals that the LLM's appraisal of a stimulus produces before
the slow feeling layer commits to a 7-dim body feeling.

The `InteroceptiveFeelingVector` (7 dims) is downstream of the
neuromodulator update — it would be **circular** to drive
neuromodulators from feelings. The 5-dim rapid salience is the right
upstream signal.

R79-C's `5-HT = safety_social * (1 - threat) * social` formula is the
mapping a person would describe: "I feel safe (low threat) and I'm
with people (high social), so my mood lifts (high 5-HT)". The formula
is intentionally simple — a future P5 slice can learn more complex
mappings.

### 2.4 Why is the corroborator's bonus / penalty *not* a same-tick drive mutation?

Same as §2.2: the bias is a `NeuromodulatorLevels` value, returned to
the caller. The caller is the R79-D baseline framework (in R79-C scope,
for testing) and the future R80 composition bridge (out of R79-C
scope). The bias is the next-tick offset added before the dual-timescale
integrator runs.

R79-C's acceptance test (§7.3) verifies the bias is bounded — this is
the R79-D framework's job, not the corroborator's. The corroborator
clips the bias output to the legal range, but the framework verifies
the bound is upheld across all 9 channels × 4 scenarios × N ticks.

### 2.5 Why does the v3 prompt schema add 1 new field, not restructure?

R79-A's 11-field schema is the v3 contract. Adding `hormone_response_i_predict`
as a 12th field (optional, `null` default) is a backward-compatible
extension: the v1 prompt contract is untouched, and a v3 prompt output
without the 12th field is treated as silent (no bias). R79-C's
acceptance test (§7.2) verifies the field count bumps from 11 to 12
without changing the existing 11 fields' descriptions.

## 3. Module Design

### 3.1 `helios_v2/neuromodulation/corroborator.py`

```
@dataclass(frozen=True)
class HormonePredictCouplingConfig:
    corroborate_bonus: float = 0.05
    conflict_penalty: float = -0.05
    sign_match_tolerance: float = 0.1
    magnitude_match_tolerance: float = 0.2
    
    def __post_init__(self) -> None:
        # 1. bounds check: 0.0 <= corroborate_bonus <= 0.2
        # 2. bounds check: -0.2 <= conflict_penalty <= 0.0
        # 3. bounds check: 0.0 < sign_match_tolerance <= 0.5
        # 4. bounds check: 0.0 < magnitude_match_tolerance <= 0.5

class HormonePredictCouplingChannel(Enum):
    DOPAMINE = "dopamine"
    NOREPINEPHRINE = "norepinephrine"
    SEROTONIN = "serotonin"
    ACETYLCHOLINE = "acetylcholine"
    CORTISOL = "cortisol"
    OXYTOCIN = "oxytocin"
    OPIOID_TONE = "opioid_tone"
    EXCITATION = "excitation"
    INHIBITION = "inhibition"

Verdict = Literal["corroborate", "conflict", "silent"]

@dataclass(frozen=True)
class HormonePredictCouplingClassification:
    channel: HormonePredictCouplingChannel
    verdict: Verdict
    magnitude: float  # the LLM predict value, in [-1.0, +1.0]

@dataclass(frozen=True)
class HormonePredictCorroborator:
    config: HormonePredictCouplingConfig
    
    def classify_predict(
        self,
        formula_drive: NeuromodulatorLevels,
        predict: Mapping[str, float] | None,
        tonic_baseline: NeuromodulatorLevels,
    ) -> tuple[HormonePredictCouplingClassification, ...]:
        # Returns an empty tuple if predict is None or empty.
        # For each of the 9 channels:
        #   1. predict_value = predict.get(channel.name, 0.0)
        #   2. drive_value = formula_drive.<channel> - tonic_baseline.<channel>
        #   3. apply the rule from §3.2 of requirement.md
        ...
    
    def aggregate_coupling_bias(
        self,
        classifications: tuple[HormonePredictCouplingClassification, ...],
        tonic_baseline: NeuromodulatorLevels,
        legal_min: NeuromodulatorLevels,
        legal_max: NeuromodulatorLevels,
    ) -> dict[str, float]:
        # Returns a 9-key dict (one per channel) with each channel:
        #   corroborate: bonus * magnitude
        #   conflict: penalty * magnitude
        #   silent: 0.0
        # clamped to [legal_min - tonic_baseline, legal_max - tonic_baseline]
        # NOTE: dict[str, float] is used instead of NeuromodulatorLevels
        # because the bias can be negative (a conflict verdict produces a
        # negative penalty), and NeuromodulatorLevels enforces [0.0, 1.0]
        # per channel. The caller (R80 composition bridge or R79-D baseline
        # framework) consumes the dict and adds it as a per-channel offset
        # to the next-tick RapidAppraisalBatch.
        ...
```

The corroborator is a **pure function**: it does not import the engine
or any cross-owner module. It is a `frozen` dataclass with two
methods, both pure.

### 3.2 `helios_v2/neuromodulation/engine.py` (modify)

Add 3 fields to `AppraisalDerivedNeuromodulatorUpdatePath`:

```python
safety_social_to_serotonin: float = 0.4
social_uncertainty_to_oxytocin: float = 0.4
safety_uncertainty_to_opioid: float = 0.4
```

Replace the 3 shim lines (5-HT / Oxy / Opioid) with the 3 formulas from
requirement §3.1. The other 3 shimmed channels (ACh / excitation /
inhibition) remain at the tonic baseline (R79-C does not de-shim them).

### 3.3 `helios_v2/neuromodulation/contracts.py` (modify)

Add `"hormone_predict_coupling"` to the `LearnedParameterCategory` Literal
and to the `expected_learned_parameters` set in
`NeuromodulatorConfig.__post_init__`. The Literal gains a 5th value.
The set gains a 5th element.

### 3.4 `helios_v2/neuromodulation/__init__.py` (modify)

Add 4 new exports:

```python
from .corroborator import (
    HormonePredictCorroborator,
    HormonePredictCouplingChannel,
    HormonePredictCouplingClassification,
    HormonePredictCouplingConfig,
)
```

Update `__all__` to include the 4 new names.

### 3.5 `helios_v2/prompt_contract/engine.py` (modify)

In `_AGGRESSIVE_RADICAL_V3_SYSTEM_PROMPT`:

1. Add 12th field to the JSON schema:
   ```
   "hormone_response_i_predict": "<...>"
   ```
2. Add 1 hard rule:
   ```
   - "hormone_response_i_predict" is a 9-key dict (or null). Each key is a
     channel name, each value is a number in [-1.0, +1.0]. No other keys
     allowed.
   ```
3. In `_schema_instructions()` (or wherever the field-count check lives),
   bump the assertion from 11 to 12.

The existing `_build_*` method is unchanged in its 6-layer structure
(present_field / embodied_state / attention_breakdown / channel_catalog /
response_schema / v3_system_prompt). The v3_system_prompt layer is
re-rendered with the new template; no layer count change.

### 3.6 `tests/test_aggressive_radical_prompt_path.py` (modify)

The single assertion that counts the JSON schema's field count: bump
from 11 to 12. This is the only edit. All other R79-A tests are
unchanged.

## 4. Test Design

### 4.1 `tests/test_hormone_predict_corroborator.py` (new, ~14 tests)

Test groups:

1. **Config bounds** (4 tests): corroborate_bonus > 0.2 rejected,
   conflict_penalty < -0.2 rejected, sign_match_tolerance out-of-range
   rejected, magnitude_match_tolerance out-of-range rejected.

2. **classify_predict: silent paths** (3 tests):
   - empty predict → empty tuple
   - all-zero predict values → empty tuple
   - None predict → empty tuple

3. **classify_predict: corroborate path** (3 tests):
   - sign match + magnitude match (drive=0.5, predict=0.5) → corroborate
   - sign match + magnitude within tolerance (drive=0.5, predict=0.4) → corroborate
   - sign match + magnitude beyond tolerance (drive=0.5, predict=0.1) → silent

4. **classify_predict: conflict path** (3 tests):
   - sign mismatch + magnitude match (drive=+0.5, predict=-0.5) → conflict
   - sign mismatch + magnitude within tolerance (drive=+0.5, predict=-0.4) → conflict
   - sign mismatch + magnitude beyond tolerance (drive=+0.5, predict=-0.1) → silent

5. **aggregate_coupling_bias** (3 tests):
   - empty classifications → all-zero `NeuromodulatorLevels` clamped to legal range
   - corroborate verdict → bias = bonus * magnitude on the right channel
   - conflict verdict → bias = penalty * magnitude on the right channel

6. **Multi-channel aggregation** (2 tests):
   - Mixed corroborate / conflict / silent across 9 channels → bias sum respects bounds
   - Per-channel bias is independently clamped to `[legal_min - tonic_baseline, legal_max - tonic_baseline]`

Total: **18 unit tests** in this file.

### 4.2 `tests/test_r79c_hormone_coverage.py` (new, ~6 tests)

Test groups:

1. **3 sensitivity fields under non-empty batch** (3 tests):
   - 5-HT varies when threat / social varies
   - Oxy varies when social / uncertainty varies
   - Opioid varies when threat / uncertainty varies

2. **Empty batch behavior** (1 test):
   - All 3 channels equal tonic_baseline when batch is empty

3. **Coverage interaction with dual-timescale** (1 test):
   - 10-tick run with constant A_praise stimulus shows monotonically
     increasing 5-HT and Oxy, monotonically decreasing cortisol

4. **12th-field schema count** (1 test):
   - `AggressiveRadicalEmbodiedPromptPath._build_*` emits 12 fields
     in the v3 JSON schema instruction

Total: **6 coverage tests** in this file.

### 4.3 Existing tests to update

- `tests/test_aggressive_radical_prompt_path.py` — 1 line: the
  11-field count → 12-field count.

## 5. R79-D Baseline Output

R79-C produces a v2 baseline output under
`helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/`:

```
helios_v2/logs/prompt_probe_scenarios/r79d/
├── baseline/                  (R79-D v1 output, R79-A era)
│   ├── A_praise/              (10 ticks, no corroborator)
│   ├── B_neglect/             (10 ticks, no corroborator)
│   ├── C_bipolar/             (12 ticks, no corroborator)
│   └── D_repeat/              (20 ticks, no corroborator)
└── corroborator/              (R79-D v2 output, R79-C era)
    ├── A_praise/              (10 ticks, with corroborator + LLM predict)
    ├── B_neglect/             (10 ticks, with corroborator + LLM predict)
    ├── C_bipolar/             (12 ticks, with corroborator + LLM predict)
    └── D_repeat/              (20 ticks, with corroborator + LLM predict)
```

Each scenario in `corroborator/` produces a CSV with 9-channel series
(5-HT / Oxy / Opioid non-constant; corroborate_bias bounded) and a
JSON report summarizing A vs B delta on Oxy (acceptance §7.3.14).

The R79-D framework's `assertions.assert_all_salience_series_non_constant`
is extended to also assert
`assert_corroborate_bias_bounded`. The R79-C tests in
`test_r79c_hormone_coverage.py` verify the assertions library exposes
the new function.

## 6. Migration / Backward Compatibility

R79-C is **backward-compatible** for v1 assembly:

- `NeuromodulatorConfig.mandatory_learned_parameters` gains a 5th
  element. Any caller constructing a `NeuromodulatorConfig` literal
  without `"hormone_predict_coupling"` will see `__post_init__` raise
  `NeuromodulatorError`. R79-C patches `tests/conftest.py` and any
  other fixture that constructs a `NeuromodulatorConfig` literal.
- `AppraisalDerivedNeuromodulatorUpdatePath` gains 3 new fields with
  default `0.4`. The v1 assembly uses
  `FirstVersionConstantNeuromodulatorUpdatePath`, not
  `AppraisalDerivedNeuromodulatorUpdatePath`, so the default has no
  effect on the v1 path.
- The v3 prompt schema gains 1 optional field. v1 callers that consume
  v3 LLM JSON output without the 12th field are unaffected (the field
  defaults to silent in the corroborator).

R79-C is **forward-compatible** for R80:

- R80 may add a composition bridge that calls
  `HormonePredictCorroborator.classify_predict` with the LLM JSON's
  `hormone_response_i_predict` and the formula-derived drive from
  `AppraisalDerivedNeuromodulatorUpdatePath`. The corroborator's public
  API is stable.

R79-C is **forward-compatible** for P5:

- The 3 new sensitivity coefficients are under the existing
  `channel_gain_sensitivity` category. P5 may tune them without
  changing the equation shape.
- The corroborator's bonus / penalty / tolerance constants are under
  the new `hormone_predict_coupling` category. P5 may tune them without
  changing the corroborator's equation shape.
- The corroborator is a pure function: P5 may replace it with a learned
  classifier without breaking the contract.
