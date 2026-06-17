# R-PROTO-LEARN Tier 4 — 余 4 owner P5 收官 (Requirement)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
**Tier 4 = R21-R24**

## 目标

完成 P5 全部剩余 4 owner 真学习能力 ship:
- **R21 owner 08 consciousness** (3 policy: commitment / quiet_state / semantic_shaping)
- **R22 owner 13 planner_bridge** (3 policy: policy_evaluation / channel_selection / feedback_normalization)
- **R23 owner 14 identity_governance** (4 policy: governance_evaluation / pressure_interpretation / supported_revision / boundary_check)
- **R24 owner 15 experience_writeback** (3 policy: continuity_classification / consolidation_priority / autobiographical_salience)

**13 policy 真实学习能力 ship**。

## 范围

- 4 owner × 3 policy = 12 policy（identity_governance 4 policy → 13）
- 4 owner 各自 unique LLM signal 维度（基于 owner 真实 LLM appraisal 接口）
- 4 owner 各自 state context 字段
- 复用 Tier 1+2+3 统一学习框架
- 必走真 LLM smoke 验证（**小黑硬性要求**延续）

## 学术对位

| Owner | 论文 | 核心机制 |
|---|---|---|
| 08 consciousness | Tononi 2004 (IIT) + Dehaene 2014 (GNW) | integrated information + global neuronal workspace |
| 13 planner_bridge | Laird 2012 (Soar) + Parisi 2019 transfer | action selection + transfer learning |
| 14 identity_governance | Kotseruba 2018 self-regulation + R79-R80 governance | self-regulation loop |
| 15 experience_writeback | Bhatt 2019 reconsolidation + Parisi 2019 consolidation | memory reconsolidation |

## 验收

- 4 owner learner module 全部实现（input_dim / output_dim / 3 policy 维度）
- 4 owner 单元测试通过（每 owner 17+ 测试 = 68+ 总测试）
- 真 LLM smoke 跑通（4 owner × 8 ticks = 32 calls）
- 整库回归 1550+ passed + 3 skipped
- 调研分支 HEAD 1 commit ahead
- **铁律：永不 merge main**

## 调研分支铁律

`research/R-PROTO-LEARN-appraisal-multi-mechanism` 分支永不 merge 到 main (2026-06-17 08:09 拍板)。
