# R-PROTO-LEARN.9 Design

## Architecture

```
LLM appraisal (7-dim)
       ↓
_compute_hormone_adjustment(W, hormone, target, strength, clip)
       ↓
   pinv(W) * (target - W*hormone) -- scaled by strength, clipped to ±clip
       ↓
effective_hormone = hormone + adjustment
       ↓
effective_feeling = W * effective_hormone   (unclamped)
       ↓
residual = LLM - effective_feeling          (closed-loop)
       ↓
_apply_update + regime + commit
```

## Why pseudo-inverse (not gradient descent)

- 7x9 is small and (with the dense R-PROTO-LEARN.8 W) full-rank
- Pseudo-inverse gives the exact least-squares solution in one step
- No hyperparameter learning rate to tune for the closure step
- Pure-python implementation (no numpy dependency) — uses
  Gauss-Jordan elimination on the 7x7 (W W^T) matrix

## Why unclamped projection

- The pseudo-inverse solution assumes the linear algebra is exact
- Clamping the *feeling* output to [0, 1] would distort the residual
  and break the closed-loop property
- The clamp is therefore applied only at the user-facing output
  (not at the residual computation)

## Integration boundary

- `P5FeelLearningPath.update()` gains the closure branch
- `_project_feeling_unclamped` is a new private method on the path
- `_compute_hormone_adjustment` is a module-level helper
- No changes to owner 04 neuromodulation or owner 03 appraisal contracts
- No changes to canonical feeling output (R36/R43 path unchanged)

## Risk & rollback

- If `_compute_hormone_adjustment` returns all-zero (e.g. W W^T singular),
  the path silently falls back to the open-loop behavior — safe degradation
- The `hormone_closure_enabled` config flag defaults to True; setting it to
  False restores the pre-R-PROTO-LEARN.9 behavior exactly
- The pure-python pseudo-inverse is O(n^3) on a 7x7 matrix, well below
  microsecond latency
