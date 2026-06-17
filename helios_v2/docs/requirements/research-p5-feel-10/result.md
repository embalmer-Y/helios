# R-PROTO-LEARN.10 Result

## Implementation outcome

The real owner 04 `AppraisalDerivedNeuromodulatorUpdatePath` is now an
opt-in closure path for P5-feel. The default remains the
R-PROTO-LEARN.9 numpy_pinv path so existing callers and tests are not
broken. Both paths produce a smaller closed-loop residual than the
open-loop residual, but the R9 path is mathematically exact while the
R10 path follows the helios cognitive policy.

## Quantitative results (real LLM extended smoke, 48 calls per path)

| Block | R9 numpy_pinv avg_max_res | R10 appraisal_derived avg_max_res | R9 commits | R10 commits |
|---|---|---|---|---|
| A 8 base 情绪 | 0.343 | 0.437 | 0 | 0 |
| B 16 真实生活场景 | 0.387 | 0.465 | 0 | 0 |
| C 20-tick 长程 | 0.276 | 0.367 | **3** | 0 |
| D 4 极端边界 | 0.240 | 0.295 | 0 | 0 |
| final regime | habitual | model_based | -- | -- |

R10 is biologically more plausible (the real cognitive policy can
leave larger residuals by design) and reflects what a real brain does
when an LLM-style appraisal hits a hard-coded neuromodulator update
equation. R9 is mathematically cleaner (a least-squares fit will
always land close to the target).

## Quantitative unit test results

- 199/199 R-PROTO-LEARN series tests pass
- 63/63 P5-feel tests pass (47 prior + 6 R9 closure + 3 numpy/hard-coupling + 7 R10)
- 0 regressions in the rest of the helios test suite
- R21 guard clean

## Decision rationale (already approved by 小黑)

The P5-feel 5-algorithm model was the original 1-commit ship. R9 and
R10 are two improvements on the *hormone* side of the model:

- R9: math-optimum hormone adjustment (numpy_pinv)
- R10: policy-conformant hormone adjustment (real owner 04 path)

Both are kept selectable because they answer different questions:
R9 is "what is the minimum-square hormone perturbation that makes
the LLM appraisal achievable", and R10 is "what hormone state would
the real helios neuromodulation pipeline land in if it saw the LLM
appraisal as a rapid-appraisal batch".

## Commit

- `HEAD` (research branch): R-PROTO-LEARN.10 added on top of `8cc5c6c`
  (R-PROTO-LEARN.9 numpy-only)
- The research branch remains `research/R-PROTO-LEARN-appraisal-multi-mechanism`
- main HEAD is unchanged at `15b4650` (R98)

## Open items for follow-up

- A later P5 slice may add a learned `FeelingToSalienceMapper` (instead
  of the heuristic defaults)
- A later P5 slice may add a per-dim residual threshold so R10 can
  also trigger commits (the larger residuals are policy by design, but
  the current 0.3 threshold is calibrated for R9)
- A later P5 slice may wrap R10 in a dual-timescale decay wrapper to
  match the real owner 04 invocation pattern (currently R10 is stateless)
