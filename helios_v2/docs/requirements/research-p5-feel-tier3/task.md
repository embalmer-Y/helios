# R-PROTO-LEARN Tier 3 — 协议对位 (Task)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## T1: 三件套
- [x] requirement.md (3,252 字节)
- [x] design.md (6,727 字节)
- [x] task.md (本文件)

## T2: R18 owner 07 workspace_learner.py
- [ ] `WorkspaceLearnerConfig` (input=7, output=9)
- [ ] `WorkspaceLearner` 子类
- [ ] 3 policies: competition / candidate_retention / working_state_update
- [ ] 7-dim LLM signal → 9-dim target mapping
- [ ] module-level numpy import
- [ ] Smoke import OK

## T3: R19 owner 16a outward_expression_learner.py
- [ ] `OutwardExpressionLearnerConfig` (input=7, output=9)
- [ ] `OutwardExpressionLearner` 子类
- [ ] 3 policies: delivery_guidance / boundary_rendering / draft_publication
- [ ] 7-dim LLM signal → 9-dim target mapping
- [ ] Smoke import OK

## T4: R20 owner 16b outward_expression_externalization_learner.py
- [ ] `OutwardExpressionExternalizationLearnerConfig` (input=7, output=9)
- [ ] `OutwardExpressionExternalizationLearner` 子类
- [ ] 3 policies: envelope_rendering / delivery_selection / execution_boundary
- [ ] Smoke import OK

## T5: R20b owner prompt_contract_learner.py
- [ ] `PromptContractLearnerConfig` (input=7, output=9)
- [ ] `PromptContractLearner` 子类
- [ ] 3 policies: layering / anti_theatrical / action_boundary
- [ ] Smoke import OK

## T6: Unit tests (4 × 16 = 64 tests)
- [ ] test_r_proto_learn_18_workspace_learner.py (16)
- [ ] test_r_proto_learn_19_outward_expression_learner.py (16)
- [ ] test_r_proto_learn_20_outward_expression_externalization_learner.py (16)
- [ ] test_r_proto_learn_20b_prompt_contract_learner.py (16)
- [ ] 64/64 全 pass

## T7: 真 LLM smoke
- [ ] scripts/r_proto_learn_tier3_real_llm_smoke.py
- [ ] 4 owner × 8 ticks = 32 calls
- [ ] 跑通 + 报告

## T8: 整库回归
- [ ] 1479+ passed + 3 skipped
- [ ] 5 failed = main 已有

## T9: commit + push
- [ ] commit "feat(R-PROTO-LEARN.Tier3): owner 07/16a/16b/prompt_contract 协议对位"
- [ ] push 到调研分支
- [ ] **铁律：永不 merge main**

## 验收
- 4 owner learner module 全部实现
- 64 单元测试全 pass
- 真 LLM smoke 跑通
- 整库 1479+ passed
- 调研分支 HEAD 1 commit ahead
