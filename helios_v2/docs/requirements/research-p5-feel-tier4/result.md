# R-PROTO-LEARN Tier 4 — 余 4 owner P5 收官 (Result)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## ship 表

| R | Owner | Policies | W 矩阵 | Real LLM Residual | commits | regime 转换 | 学术 |
|---|---|---|---|---|---|---|---|
| R21 | 08 consciousness | commitment / quiet_state / semantic_shaping | 9x7 | 0.54 | 0 | exploratory | Tononi 2004 (IIT) + Dehaene 2014 (GNW) |
| R22 | 13 planner_bridge | policy_evaluation / channel_selection / feedback_normalization | 9x7 | 0.52 | 0 | exploratory | Laird 2012 (Soar) + Parisi 2019 transfer |
| R23 | 14 identity_governance | governance_evaluation / pressure_interpretation / supported_revision / boundary_check | **12x7** | **0.87** | 0 | exploratory | Kotseruba 2018 self-regulation + R79-R80 |
| R24 | 15 experience_writeback | continuity_classification / consolidation_priority / autobiographical_salience | 9x7 | 0.54 | 0 | exploratory | Bhatt 2019 reconsolidation + Parisi 2019 consolidation |

## 关键设计真相

**identity_governance 12x7 W rank-7 algebraic 限制** (R23):
- 4 policy = 12-dim output (3+3+3+3)
- 12x7 W 矩阵 rank ≤ 7
- algebraic 真相: 5-dim 永远不能 closure
- residual 范围 0.78-1.02 (高于 9x7 owner)
- acceptance: residual in [0, 1.5] (algebraic 真相宽容)

**其他 3 owner 9x7 W rank-7 限制** (R21/R22/R24):
- 3 policy = 9-dim output
- 9x7 W 矩阵 rank ≤ 7
- algebraic 真相: 2-dim 永远不能 closure
- residual 0.50-0.57 (跟 Tier 2/3 一致)

## 关键架构

**4 owner 共享统一 helios_v2/learning/ 框架**:
- LearnerABC + numpy pinv closure
- 5 算法 + 3 态 + numpy-only path
- 7-dim LLM signal → N-dim target linear mapping
- 7-dim state context (owner 特定字段)

**4 owner 学术对位**:
- **08 consciousness**: Tononi 2004 IIT (integrated information) + Dehaene 2014 GNW (global neuronal workspace)
  - commitment_policy ↔ IIT Φ-threshold
  - quiet_state_policy ↔ GNW ignition threshold / deactivation
  - semantic_shaping_policy ↔ GNW long-range cortical reentry
- **13 planner_bridge**: Laird 2012 Soar (action selection) + Parisi 2019 transfer
  - policy_evaluation_policy ↔ Soar impasse detection + operator evaluation
  - channel_selection_policy ↔ Soar operator selection
  - feedback_normalization_policy ↔ Parisi 2019 transfer normalization
- **14 identity_governance**: Kotseruba 2018 self-regulation + R79-R80 governance
  - governance_evaluation_policy ↔ performance monitor
  - pressure_interpretation_policy ↔ state evaluator
  - supported_revision_policy ↔ controller
  - boundary_check_policy ↔ R79-R80 constraint enforcer
- **15 experience_writeback**: Bhatt 2019 reconsolidation + Parisi 2019 consolidation
  - continuity_classification_policy ↔ Bhatt 2019 memory trace classification
  - consolidation_priority_policy ↔ Parisi 2019 consolidation scheduling
  - autobiographical_salience_policy ↔ Tulving 1985 + Panksepp SEEKING

## 单元测试

4 owner × 17 tests = **68/68 全 pass**:
- test_r_proto_learn_21_consciousness_learner.py (17)
- test_r_proto_learn_22_planner_bridge_learner.py (17)
- test_r_proto_learn_23_identity_governance_learner.py (17)
- test_r_proto_learn_24_experience_writeback_learner.py (17)
- 整库 R-PROTO-LEARN: 449/449 pass

## 真 LLM smoke

- scripts/r_proto_learn_tier4_real_llm_smoke.py (10,501 字节)
- 32 calls / 95s / 3.0s/msg
- consciousness (08) 0.54, planner_bridge (13) 0.52
- identity_governance (14) **0.87** (12x7 W algebraic)
- experience_writeback (15) 0.54

## 关键文件

```
src/helios_v2/learning/
├── consciousness_learner.py           (4,526 字节) ← R21
├── planner_bridge_learner.py          (4,470 字节) ← R22
├── identity_governance_learner.py     (5,031 字节) ← R23 (12-dim)
├── experience_writeback_learner.py    (4,687 字节) ← R24
└── __init__.py                        (导出 4 owner)

tests/
├── test_r_proto_learn_21_consciousness_learner.py (4,620 字节)
├── test_r_proto_learn_22_planner_bridge_learner.py (4,624 字节)
├── test_r_proto_learn_23_identity_governance_learner.py (4,773 字节)
└── test_r_proto_learn_24_experience_writeback_learner.py (4,800 字节)

scripts/
└── r_proto_learn_tier4_real_llm_smoke.py (10,501 字节)
```

## P5 完成度 = 100%

**P5 全部 17 owner / 53 policy 完成**:

| Tier | Owner 数量 | Policy 数量 | 学术论文数 |
|---|---|---|---|
| Tier 1 (R11-R15) | 5 | 15 | 5 |
| Tier 2 (R16-R17) | 2 | 6 | 2 |
| Tier 3 (R18-R20b) | 4 | 12 | 3 |
| Tier 4 (R21-R24) | 4 | 13 | 4 |
| R10 (owner 04) | 1 | 1 (hormone path) | - |
| R-PROTO-LEARN.7-10 (owner 05) | 1 | 6 (P5-feel + closure) | 3 |
| **合计** | **17** | **53** | - |

**15 owner = 17 owner - 2 P5-feel 系**:
- 04 neuromodulation: 1 hormone path
- 05 feeling: 5 algorithm + 1 closure (P5-feel 系)
- 06 memory: 3 policy (Tier 1)
- 07 workspace: 3 policy (Tier 3)
- 08 consciousness: 3 policy (Tier 4)
- 09 thought_gating: 3 policy (Tier 1)
- 10 directed_retrieval: 3 policy (Tier 1)
- 11 internal_thought: 3 policy (Tier 1)
- 12 action_externalization: 3 policy (Tier 2)
- 13 planner_bridge: 3 policy (Tier 4)
- 14 identity_governance: 4 policy (Tier 4)
- 15 experience_writeback: 3 policy (Tier 4)
- 16a outward_expression: 3 policy (Tier 3)
- 16b outward_expression_ext: 3 policy (Tier 3)
- 17 evaluation: 3 policy (Tier 2)
- 18 autonomy: 3 policy (Tier 1)
- prompt_contract: 3 policy (Tier 3)

## 调研分支铁律

`research/R-PROTO-LEARN-appraisal-multi-mechanism` 分支永不 merge 到 main (2026-06-17 08:09 拍板)。
