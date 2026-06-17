# R-PROTO-LEARN Tier 4 — 余 4 owner P5 收官 (Design)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## 架构原则

复用 Tier 1+2+3 统一学习框架 (helios_v2/learning/):
- LearnerABC 通用基类 + numpy pinv closure
- 5 算法 + 3 态 Regime + numpy-only path
- 7-dim LLM signal → N-dim target linear mapping
- W 矩阵 9x7 rank-7 algebraic 限制 接受
- 7-dim state context（owner 特定字段）

## 4 owner 详细设计

### R21 owner 08 consciousness (input=7, output=9)
**3 policies**:
- commitment_policy: 3-dim output
  - commitment_threshold, confidence_required, retention_ticks
- quiet_state_policy: 3-dim output
  - quiet_threshold, recovery_rate, idle_decay
- semantic_shaping_policy: 3-dim output
  - semantic_alignment, conflict_resolution_strength, depth_score

**state context** (7-dim):
- candidate_count, signal_strength, dopamine, acetylcholine, novelty,
  conscious_state_size, semantic_drift

**学术对位**: Tononi 2004 (IIT) + Dehaene 2014 (GNW)
- commitment_policy ↔ IIT Φ (integrated information commitment)
- quiet_state_policy ↔ GNW "ignition threshold" (deactivation)
- semantic_shaping_policy ↔ GNW "long-range cortical reentry"

### R22 owner 13 planner_bridge (input=7, output=9)
**3 policies**:
- policy_evaluation_policy: 3-dim output
  - evaluation_threshold, exploration_bonus, consistency_score
- channel_selection_policy: 3-dim output
  - channel_weight, fall_back_score, signal_strength
- feedback_normalization_policy: 3-dim output
  - normalization_strength, scope_pressure, integration_depth

**state context** (7-dim):
- bridge_intensity, request_count, dopamine, acetylcholine, novelty,
  feedback_volume, decision_confidence

**学术对位**: Laird 2012 (Soar) + Parisi 2019 transfer
- policy_evaluation_policy ↔ Soar "impasse detection" + evaluation
- channel_selection_policy ↔ Soar "operator selection" (channel = operator)
- feedback_normalization_policy ↔ Parisi 2019 transfer (across-domain normalization)

### R23 owner 14 identity_governance (input=7, output=12)
**4 policies** (12-dim output):
- governance_evaluation_policy: 3-dim output
  - evaluation_threshold, alignment_strictness, weight
- pressure_interpretation_policy: 3-dim output
  - pressure_threshold, signal_strength, interpretation_bias
- supported_revision_policy: 3-dim output
  - revision_threshold, support_weight, alignment_strictness
- boundary_check_policy: 3-dim output
  - boundary_strictness, safety_margin, fall_back_score

**state context** (7-dim):
- pressure_intensity, signal_strength, dopamine, acetylcholine, novelty,
  proposal_count, boundary_risk

**学术对位**: Kotseruba 2018 self-regulation + R79-R80 governance
- governance_evaluation_policy ↔ self-regulation "performance monitor"
- pressure_interpretation_policy ↔ self-regulation "state evaluator"
- supported_revision_policy ↔ self-regulation "controller"
- boundary_check_policy ↔ R79-R80 governance "constraint enforcer"

### R24 owner 15 experience_writeback (input=7, output=9)
**3 policies**:
- continuity_classification_policy: 3-dim output
  - continuity_threshold, classification_threshold, weight
- consolidation_priority_policy: 3-dim output
  - priority_threshold, weight, decay_rate
- autobiographical_salience_policy: 3-dim output
  - salience_threshold, weight, integration_strength

**state context** (7-dim):
- continuity_intensity, evidence_strength, dopamine, acetylcholine, novelty,
  candidate_count, autobiographical_signal

**学术对位**: Bhatt 2019 reconsolidation + Parisi 2019 consolidation
- continuity_classification_policy ↔ Bhatt 2019 "memory trace classification"
- consolidation_priority_policy ↔ Parisi 2019 "consolidation scheduling"
- autobiographical_salience_policy ↔ Parisi 2019 "salience-based prioritization"

## W 矩阵设计

| Owner | W 矩阵 | Rank 限制 | residual 预期 |
|---|---|---|---|
| 08 consciousness | 9x7 | rank-7 | 0.4-0.6 (algebraic 真相) |
| 13 planner_bridge | 9x7 | rank-7 | 0.4-0.6 |
| 14 identity_governance | 12x7 | rank-7 | 0.6-0.8 (12 > 9 algebraic) |
| 15 experience_writeback | 9x7 | rank-7 | 0.4-0.6 |

identity_governance 是 4 policy = 12-dim output, 12x7 W rank 限制更严,
residual 0.6-0.8 范围（algebraic 真相，跟 Tier 2 R16 9x7 类似）。

## acceptance criteria

- residual 在 [0, 1] 区间（不超界）
- regime 转换工作
- W matrix shape valid
- weights 渐变学习
- 真 LLM smoke 跑通

## 实施步骤

1. R21 consciousness_learner.py + 17 tests
2. R22 planner_bridge_learner.py + 17 tests
3. R23 identity_governance_learner.py (12-dim) + 17 tests
4. R24 experience_writeback_learner.py + 17 tests
5. __init__.py 导出 4 owner
6. 真 LLM smoke 脚本 4 owner × 8 ticks = 32 calls
7. 整库回归
8. commit + push (1 commit ship)
9. 调研分支铁律保持
