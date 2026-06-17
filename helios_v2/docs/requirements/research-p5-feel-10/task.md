# R-PROTO-LEARN.10 Tasks

## Implementation Tasks

- [x] T1: Add `FeelingToSalienceMapper` Protocol + `_default_feeling_to_salience`
        heuristic (Panksepp 7 systems + Fermin 2021 grounded)
- [x] T2: Add `_compute_appraisal_derived_hormone()` helper that
        routes the LLM appraisal through the real owner 04
        `AppraisalDerivedNeuromodulatorUpdatePath`
- [x] T3: Add 4 config fields to `P5FeelLearningConfig`:
        - `hormone_path: Literal["numpy_pinv", "appraisal_derived"] = "numpy_pinv"`
        - `appraisal_neuromodulator_config: object = None`
        - `appraisal_update_path: object = None`
        - `appraisal_salience_mapper: object = None`
- [x] T4: Add config validation: `appraisal_derived` requires the 3
        injected dependencies (clear ValueError listing missing fields)
- [x] T5: Modify `update()` to dispatch between numpy_pinv and
        appraisal_derived closure paths based on `config.hormone_path`
- [x] T6: Add 7 unit tests for R10 path:
        - test_r10_default_mapper_is_panksepp_grounded
        - test_r10_default_mapper_handles_neutral
        - test_r10_config_validates_missing_dependencies
        - test_r10_config_rejects_unknown_hormone_path
        - test_r10_appraisal_derived_hormone_via_owner_04_path
        - test_r10_path_produces_smaller_residual_than_open_loop
        - test_r10_vs_r9_residuals_are_both_smaller_than_open_loop
- [x] T7: Run unit tests -- 63/63 P5-feel pass (47 prior + 6 R9 +
        3 numpy integration/hard-coupling + 7 R10)
- [x] T8: Run R-PROTO-LEARN series regression -- 199/199 pass
- [x] T9: Modify `scripts/r_proto_learn_7_p5_feel_extended_smoke.py`
        to add `--path {numpy_pinv,appraisal_derived}` option
- [x] T10: Run real LLM extended smoke for both paths:
        - `--path numpy_pinv`: avg_max_res 0.240-0.387, commits=3 ✅
        - `--path appraisal_derived`: avg_max_res 0.295-0.465, commits=0
- [x] T11: Write requirement.md, design.md, task.md
- [x] T12: Commit + push to research branch

## Out-of-Scope (left for follow-up)

- Replace the heuristic feeling->salience mapper with a learned one
- Wire P5-feel to consume the real owner 04 state (currently read-only)
- Add a per-dim `closed_loop_residual_threshold` for R10 (so commits
  can also trigger on the appraisal_derived path)
- Decay wrapper for R10 (currently R10 is stateless; a later slice
  could wrap it in a dual-timescale decay path like R43 does for
  the real owner 04 path)
