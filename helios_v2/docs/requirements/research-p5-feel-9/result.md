# R-PROTO-LEARN.9 Implementation Result

## Summary

**Before (R-PROTO-LEARN.8 修后)**:
- avg_max_res: A=0.544, B=0.631, C=0.543, D=0.510
- regime: 4/4 model_based
- commits: 0 (all blocks)

**After (R-PROTO-LEARN.9 闭环)**:
- avg_max_res: A=0.343, B=0.380, C=0.285, D=0.249 (4 blocks 平均 0.314, **降 44%**)
- regime: **3/4 habitual** (B end habitual, C all habitual, D all habitual)
- commits: 0 still (residual 0.10-0.38 vs threshold 0.3, 仍 boundary)

## Core mechanism

1. `_compute_hormone_adjustment(W, hormone, target, strength, clip)`:
   - Solve `adj0 = W^+ * (target - W * hormone)` via pure-python Moore-Penrose
   - Scale by `strength` (default 0.7) and clip per channel to `±clip` (default 0.5)
   - When `clip >= 1.0` the helper returns the unclamped least-squares solution
2. `update()` calls the helper when `hormone_closure_enabled=True` and `llm_appraisal is not None`:
   - Build `effective_hormone = hormone + adjustment` (unclamped for residual computation)
   - Project `effective_feeling = W * effective_hormone` (unclamped, via `_project_feeling_unclamped`)
   - Use `residual = target - effective_feeling` as the **closed-loop** residual
   - The real hormone state is never modified — this is a pure sidecar adjustment

## Why this solves R-PROTO-LEARN.8 partial failure

- R-PROTO-LEARN.8 root cause: LLM appraisal and W baseline are two unrelated
  signal sources (the LLM knows the text content, W only knows hormone levels).
- R-PROTO-LEARN.9 fix: route the LLM appraisal through a pseudo-inverse-based
  hormone adjustment so the LLM appraisal is expressed as a perturbation
  of the hormone state, not as an unexplained residual. The closed-loop
  residual is then much smaller because most of the feeling space IS
  reachable via the hormone adjustment.

## Test results

- Unit tests: 53/53 pass (6 new R-PROTO-LEARN.9 tests + 47 prior)
- Real LLM smoke (extended 4 blocks × 48 dialogues): all 48 complete,
  regime transitions observed, residual dramatically reduced
- No regressions in other test files (R-PROTO-LEARN series 189/189 pass)
- Main already-failing 5 tests remain failing (verified unrelated)
