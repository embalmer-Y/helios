# R-PROTO-LEARN.10 — Real owner 04 neuromodulation path for the LLM->hormone closure

## 1. Background

R-PROTO-LEARN.9 (`81f21fa` -> `8cc5c6c`) made P5-feel's hormone-feeling
closure work via a pure-mathematical numpy pseudo-inverse solve. The
solution is exact in the linear-algebra sense (any 7-dim feeling can
be exactly explained by a 9-dim hormone adjustment), but it does NOT
reflect the helios cognitive policy: the real owner 04
`AppraisalDerivedNeuromodulatorUpdatePath` translates a 5-dim salience
vector (threat / reward / novelty / social / uncertainty) into a 9-dim
hormone vector using a fixed linear combination with specific
sensitivity coefficients. Routing the LLM appraisal through that real
path is the "production" closure: the LLM appraisal 7-dim -> salience
5-dim -> hormone 9-dim pipeline uses the same equations that owner 04
uses for the real rapid-appraisal input.

## 2. Goal

Make the hormone-feeling closure selectable between two implementations:

1. **numpy_pinv (R-PROTO-LEARN.9)**: numpy.linalg.pinv least-squares
   fit. No neuromodulator config required. Mathematically exact.
2. **appraisal_derived (R-PROTO-LEARN.10)**: routes the LLM appraisal
   through the real owner 04 `AppraisalDerivedNeuromodulatorUpdatePath`.
   Uses the real helios cognitive policy. Not necessarily exact in the
   linear-algebra sense (by design -- the policy leaves room for
   uncertainty, which is the right biological behavior).

The two paths can be swapped at construction time without changing the
P5-feel public contract (`update()` signature is unchanged).

## 3. Why this matters

R-PROTO-LEARN.9 is mathematically clean but biologically implausible:
a least-squares fit can produce any hormone vector the math likes,
including ones that violate the helios cognitive policy (e.g. raising
cortisol without a corresponding threat signal). R-PROTO-LEARN.10 makes
the closure policy-conformant: hormone adjustments can only be made
through the equations the rest of the helios runtime uses, so the
learning signal cannot accidentally violate the cognitive policy.

This is the same logic the rest of helios uses: composition-level
ownership means a new P5-feel cannot bypass owner 04 to set hormone
levels directly; it has to go through the owner 04 update path.

## 4. Constraints

- numpy is a hard dependency of P5-feel (no fallback path; per owner
  decision 2026-06-17 5:50, we do not silently degrade).
- The R10 path is opt-in via `P5FeelLearningConfig.hormone_path`; the
  default is still `numpy_pinv` (R9) so existing callers and tests
  are not broken.
- The 7-dim feeling -> 5-dim salience mapping is grounded in Panksepp
  2011 (7 systems) + Fermin 2021 (IMAC roles). Heuristics only --
  the `appraisal_neuromodulator_config` channel-gain sensitivities
  can later tune these mappings without changing the equation shape.
- The R10 path is a sidecar adjustment: the real hormone state is
  never modified, only the residual computation uses the new
  (hypothetical) hormone state.
- The P5-feel public contract (`update()` signature, return value)
  is unchanged.
- Real LLM extended smoke must run for both paths (R9 and R10) to
  verify neither regresses.

## 5. Acceptance criteria

1. `P5FeelLearningConfig(hormone_path='appraisal_derived')` raises
   `ValueError` if any of the 3 required fields (config, update_path,
   mapper) is missing.
2. `_default_feeling_to_salience` produces 5-dim salience in [0, 1]^5
   for any 7-dim feeling in [0, 1]^7, with high threat for low
   valence + high pain.
3. `_compute_appraisal_derived_hormone` returns a 9-dim tuple in
   [-1, 1]^9 (the per-channel delta).
4. R10 closed-loop residual is smaller than open-loop residual on a
   representative LLM appraisal (e.g. (0.1, 0.8, 0.9, 0.1, 0.5, 0.9, 0.2)).
5. Real LLM extended smoke runs to completion for both `--path numpy_pinv`
   and `--path appraisal_derived`; neither breaks the smoke.
6. 199/199 R-PROTO-LEARN unit tests pass; 63/63 P5-feel tests pass.
7. R21 guard clean.
