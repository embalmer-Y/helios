# R-PROTO-LEARN.9 Tasks

## Implementation Tasks

- [x] T1: Add pure-python pseudo-inverse helper (`_matmul`, `_transpose`, `_gauss_jordan_inverse`, `_pinv_tall`, `_compute_hormone_adjustment`)
- [x] T2: Add 3 config params (`hormone_closure_enabled` default True, `hormone_closure_strength` default 0.7, `hormone_closure_clip` default 0.5) + validation
- [x] T3: Add `_project_feeling_unclamped` private method
- [x] T4: Modify `update()` to route LLM appraisal through the closure path when enabled
- [x] T5: Add 6 unit tests for the closure (`test_closure_hormone_adjustment_zero_residual_in_unclipped`, `test_closure_disabled_returns_zero_adjustment`, `test_closure_clip_bounds_adjustment`, `test_closure_update_reduces_residual_vs_open_loop`, `test_closure_config_validates_strength_range`, `test_closure_config_validates_clip_range`)
- [x] T6: Run unit tests — 53/53 pass
- [x] T7: Run real LLM extended smoke — 4 blocks × 48 dialogues, all complete; regime transitions observed; residual dramatically reduced
- [x] T8: Verify R-PROTO-LEARN series all 189/189 pass
- [x] T9: Write design.md, result.md, task.md
- [x] T10: Commit + push to research branch

## Out-of-Scope (left for follow-up)

- Lower `commit_threshold` or add `commit_window` to make commit count > 0
  (residual is now 0.10-0.38, just above 0.3 threshold; small tweak needed)
- Use numpy for the pseudo-inverse (current pure-python is sufficient and
  avoids the dependency)
- Wire `P5-feel` to actual owner 04 `AppraisalDerivedNeuromodulatorUpdatePath`
  (current implementation uses a pure-mathematical pseudo-inverse; full
  integration would require threading the appraisal batch through the
  owner 04 path before P5-feel sees the hormone, which is the natural
  follow-up of the next R-PROTO-LEARN.10+ if the closed-loop residual
  remains too noisy in production)
