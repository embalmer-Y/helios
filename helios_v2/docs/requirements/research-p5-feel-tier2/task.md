# R-PROTO-LEARN Tier 2 — 行为对位 (Task)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## T1: 三件套
- [x] requirement.md (2,460 字节)
- [x] design.md (5,111 字节)
- [x] task.md (本文件)

## T2: R16 owner 12 action_externalization_learner.py
- [ ] `ActionExternalizationLearnerConfig` (input=7, output=9)
- [ ] `ActionExternalizationLearner` 子类
- [ ] 3 policies: normalization / bridge_evidence / bridge_rejection
- [ ] 7-dim LLM signal → 9-dim target mapping
- [ ] `import numpy as np` module-level (fail-fast)
- [ ] Smoke import OK

## T3: R17 owner 17 evaluation_learner.py
- [ ] `EvaluationLearnerConfig` (input=7, output=8)
- [ ] `EvaluationLearner` 子类
- [ ] 3 policies: fidelity_scoring / gap_analysis / long_range_diagnostic
- [ ] 7-dim LLM signal → 8-dim target mapping
- [ ] module-level numpy import
- [ ] Smoke import OK

## T4: Unit tests
- [ ] `test_r_proto_learn_16_action_externalization_learner.py` (16 tests)
- [ ] `test_r_proto_learn_17_evaluation_learner.py` (16 tests)
- [ ] 32/32 全 pass

## T5: Smoke script
- [ ] `scripts/r_proto_learn_tier2_smoke.py` (2 owner × 8 ticks)
- [ ] 跑通 + 报告

## T6: 整库回归
- [ ] 1445+ passed + 3 skipped
- [ ] 5 failed = main 已有（验证无关）

## T7: commit + push
- [ ] commit "feat(R-PROTO-LEARN.Tier2): owner 12/17 行为对位"
- [ ] push 到调研分支
- [ ] **铁律：永不 merge main**

## 验收
- 2 owner learner module 全部实现
- 32 单元测试全 pass
- 2-owner smoke 跑通
- 整库 1445+ passed
- 调研分支 HEAD 1 commit ahead
