# R-PROTO-LEARN Tier 2 — 行为对位 (Result)

**Date**: 2026-06-17
**Status**: ✅ SHIPPED (commit pending)
**Owner scope**: owner 12 action_externalization / 17 evaluation

## Goal

Continue P5 real-learning slicing for 2 behavior owners:
- R16 owner 12 action_externalization (3 policies)
- R17 owner 17 evaluation (3 policies)

## Architecture (consistent with Tier 1)

```
helios_v2/learning/                              (shared framework)
├── contracts.py                                 (LearnerConfig, Regime, Learner)
├── framework.py                                 (LearnerABC + numpy pinv closure)
├── memory_learner.py                            (R11)
├── thought_gating_learner.py                    (R12)
├── retrieval_learner.py                         (R13)
├── internal_thought_learner.py                  (R14)
├── autonomy_learner.py                          (R15)
├── action_externalization_learner.py            (R16) ← NEW
└── evaluation_learner.py                        (R17) ← NEW
```

## Per-Owner Policies (3 each = 6 total)

| R | Owner | Policies | Academic grounding |
|---|---|---|---|
| R16 | 12 action_externalization | normalization / bridge_evidence / bridge_rejection | Kotseruba 2018 self-regulation + Parisi 2019 intrinsic motivation |
| R17 | 17 evaluation | fidelity_scoring / gap_analysis / long_range_diagnostic | Kotseruba 2018 self-observation + self-analysis + Parisi 2019 continual learning |

## Real LLM Smoke Result (3 blocks)

```
Block A — owner 12 action_externalization (8 base behaviors)
  avg_max_residual: 0.4983
  final_regime:     exploratory
  commit_count:     0
  max_abs_weight:   0.0985
  Note: 9-dim target, 7-dim W column space → closure is best-effort
        least-squares (residual ~0.5 is algebraic, not a bug).

Block B — owner 17 evaluation (8 real-life scenarios)
  avg_max_residual: 0.0199  ← LLM appraisal 跟 7x7 W 几乎完美闭合
  final_regime:     exploratory
  commit_count:     1  ← 🎉 触发 commit
  max_abs_weight:   0.0979

Block C — owner 17 evaluation (8-tick replay)
  avg_max_residual: 0.0779
  final_regime:     model_based  ← 8-tick 收敛
  commit_count:     1  ← 🎉 replay 触发 commit
  max_abs_weight:   0.0992
```

## Residual Analysis (key insight)

- **R16 ActionExternalization**: 9-dim target, 7-dim W → rank-7 best-effort
  closure. Residual 0.50 reflects **algebraic truth** that 9-dim output
  space cannot be exactly spanned by 7-dim W. **This is honest math** —
  not a bug. To reduce residual would need either (a) more input
  features or (b) a non-linear mapping.

- **R17 Evaluation**: 8-dim target, 7-dim W → rank-7 best-effort.
  Residual 0.02-0.08 with real LLM appraisal.  **The LLM's evaluation
  appraisal is more aligned with the W's 7-dim input space** than
  action_externalization's broad 9-dim output, hence the cleaner
  closure.

## Test Suite

- 2 unit test files (16 tests each = **32 tests**), all passing.
- `test_r_proto_learn_16_action_externalization_learner.py` (16 tests) ✅
- `test_r_proto_learn_17_evaluation_learner.py` (16 tests) ✅

## Library Tests (整库)

- 1479 passed + 3 skipped + 5 failed
- 5 failed = main `15b4650` 已有（r88 drift / long_term_stability /
  performance_benchmark），与本切片无关
- Tier 1 1445 → Tier 2 1479 = +34 新测试

## Code Stats

| Dimension | Count |
|---|---|
| New files | 4 (2 owner learner + 2 unit test) |
| Updated files | 2 (`__init__.py` exports + framework deps) |
| Smoke scripts | 2 (offline + real LLM) |
| Total unit tests | 32 (2 × 16) |
| Lines added | ~ 1,200 |

## Files Touched

```
src/helios_v2/learning/
├── __init__.py                                (updated, add 2 owner exports)
├── action_externalization_learner.py          (NEW, R16)
└── evaluation_learner.py                      (NEW, R17)

tests/
├── test_r_proto_learn_16_action_externalization_learner.py  (NEW)
└── test_r_proto_learn_17_evaluation_learner.py              (NEW)

scripts/
├── r_proto_learn_tier2_smoke.py               (NEW, offline)
└── r_proto_learn_tier2_real_llm_smoke.py      (NEW, real LLM)
```

## Real LLM Smoke Test Output

The smoke script `scripts/r_proto_learn_tier2_real_llm_smoke.py` runs:
- 3 blocks: 8 base action_ext + 8 real-life eval + 8-tick replay
- Uses real LLM gateway (deepseek/deepseek-v4-flash via shengsuanyun
  router) with 7-dim appraisal extraction per tick
- Reports per-tick: novelty, max_residual, regime, commit
- Trigger 2 commits: 1 in Block B, 1 in Block C

Run:
```bash
set -a && . /root/project/helios/.env && set +a
PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_tier2_real_llm_smoke.py
```

## Branch

- `research/R-PROTO-LEARN-appraisal-multi-mechanism` only
- **铁律**: never merge to main (2026-06-17 08:09 小黑拍板)
