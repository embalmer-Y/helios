# R-PROTO-LEARN Tier 4 — 余 4 owner P5 收官 (Task)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## T1: 三件套
- [x] requirement.md (1,751 字节)
- [x] design.md (4,577 字节)
- [x] task.md (本文件)

## T2: R21 owner 08 consciousness_learner.py
- [ ] `ConsciousnessLearnerConfig` (input=7, output=9)
- [ ] `ConsciousnessLearner` 子类
- [ ] 3 policies: commitment_policy / quiet_state_policy / semantic_shaping_policy
- [ ] 7-dim LLM signal → 9-dim target linear mapping
- [ ] 7-dim state context: candidate_count / signal_strength / dopamine / ach / novelty / conscious_state_size / semantic_drift
- [ ] module-level numpy import
- [ ] Smoke import OK

## T3: R22 owner 13 planner_bridge_learner.py
- [ ] `PlannerBridgeLearnerConfig` (input=7, output=9)
- [ ] `PlannerBridgeLearner` 子类
- [ ] 3 policies: policy_evaluation / channel_selection / feedback_normalization
- [ ] 7-dim LLM signal → 9-dim target linear mapping
- [ ] 7-dim state context: bridge_intensity / request_count / dopamine / ach / novelty / feedback_volume / decision_confidence
- [ ] Smoke import OK

## T4: R23 owner 14 identity_governance_learner.py
- [ ] `IdentityGovernanceLearnerConfig` (input=7, output=12)
- [ ] `IdentityGovernanceLearner` 子类
- [ ] 4 policies: governance_evaluation / pressure_interpretation / supported_revision / boundary_check
- [ ] 7-dim LLM signal → 12-dim target linear mapping (12x7 W rank-7 限制)
- [ ] 7-dim state context: pressure_intensity / signal_strength / dopamine / ach / novelty / proposal_count / boundary_risk
- [ ] Smoke import OK

## T5: R24 owner 15 experience_writeback_learner.py
- [ ] `ExperienceWritebackLearnerConfig` (input=7, output=9)
- [ ] `ExperienceWritebackLearner` 子类
- [ ] 3 policies: continuity_classification / consolidation_priority / autobiographical_salience
- [ ] 7-dim LLM signal → 9-dim target linear mapping
- [ ] 7-dim state context: continuity_intensity / evidence_strength / dopamine / ach / novelty / candidate_count / autobiographical_signal
- [ ] Smoke import OK

## T6: Unit tests (4 × 17 = 68 tests)
- [ ] test_r_proto_learn_21_consciousness_learner.py (17)
- [ ] test_r_proto_learn_22_planner_bridge_learner.py (17)
- [ ] test_r_proto_learn_23_identity_governance_learner.py (17)
- [ ] test_r_proto_learn_24_experience_writeback_learner.py (17)
- [ ] 68/68 全 pass

## T7: 真 LLM smoke
- [ ] scripts/r_proto_learn_tier4_real_llm_smoke.py
- [ ] 4 owner × 8 ticks = 32 calls
- [ ] 跑通 + 报告

## T8: 整库回归
- [ ] 1550+ passed + 3 skipped
- [ ] 5 failed = main 已有

## T9: commit + push
- [ ] commit "feat(R-PROTO-LEARN.Tier4): owner 08/13/14/15 P5 收官"
- [ ] push 到调研分支
- [ ] **铁律：永不 merge main**

## 验收
- 4 owner learner module 全部实现
- 68 单元测试全 pass
- 真 LLM smoke 跑通
- 整库 1550+ passed
- 调研分支 HEAD 1 commit ahead
- **P5 全部 17 owner 完成** (62% → 100%)
