# R-PROTO-LEARN.P5-A: 真实运行后果驱动的学习信号（Real-RPE）

**Owner**: R-PROTO-LEARN 调研分支（`research/R-PROTO-LEARN-appraisal-multi-mechanism`）
**Created**: 2026-06-17
**Status**: ACTIVE — 实验设计 + 实施

## 1. 背景与动机

### 1.1 ROADMAP 13.3 P5-A 第 2 条（**锁定约束**）
> "学习信号以 `brain.mmd` 的多巴胺奖励预测误差为主锚点，由**真实运行后果**（执行成败、连续性是否推进、目标冲突是否缓解）定义，非人工硬编码分数。"

### 1.2 当前 ship 的 gap
R-PROTO-LEARN Tier 1+2+3+4 (commits `968f278`/`6589d62`/`79e3ea5`/`16f31ec`) ship 的 17 owner learner 用 **LLM appraisal 作 ground truth** 当 target——这是**信号源 gap**：
- LLM appraisal 是"内心独白层主观判断"
- ROADMAP 要求的是"真实运行后果"
- **两者不是同一种信号**

### 1.3 三类"真实运行后果"信号源

helios 已有 / 可在 P5-A ship 的真实后果反馈环：

1. **执行成败（owner 12/16b 真实外化）**
   - 草稿发送出去，对话对方有没有回应 / 回应内容是接受还是拒绝 / 是否要求重写
   - 工具调用是否成功（成功 vs 失败 vs 部分成功）
   - **当前 ship 状态**：owner 12/16b 真外化链可用，但**真实后果反馈** 缺 owner 反馈入口

2. **连续性是否推进（owner 14/15 governance + identity）**
   - 行动是否保持跨 tick 一致性
   - 长期目标 vs 短期行动是否对齐
   - **当前 ship 状态**：R-PROTO-LEARN.7 P5-feel 在 owner 05 旁路观察，无连续性反馈环

3. **目标冲突是否缓解（owner 07 workspace + owner 11 internal_thought）**
   - 多个 candidate 间冲突解决是否高效
   - 内部 thought proposal 是否被 workspace 接受
   - **当前 ship 状态**：owner 07/11 ship 了 learner，但**冲突评估信号**没明确

## 2. 目标

### 2.1 ship 1 个**真实运行后果驱动**的学习信号构造器 `RealRPESignal`

```
RealRPESignal
├── dopamine (RPE)
│   └── = predicted_outcome − actual_outcome
├── norepinephrine (effort / arousal)
│   └── = execution_attempt_difficulty
├── serotonin (long-term stability)
│   └── = continuity_progress_metric
└── cortisol (threat / conflict)
    └── = unresolved_goal_conflict_intensity
```

### 2.2 三组对照实验验证（**严密实验设计**）

**实验目的**：证明 17 owner learner 在"真实 RPE"信号下 vs "LLM appraisal"信号下，行为差异显著 + 真实后果驱动更接近"人脑"模式

| 实验组 | 信号源 | 假设 |
|---|---|---|
| **H0（对照）** | LLM appraisal | 当前 ship 的 17 owner learner 跑 100 tick — baseline 行为模式 |
| **H1（实验）** | RealRPE only | 17 owner learner 跑 100 tick — 真实后果驱动 — 应触发更显著 regime 切换 + 更少的假阳 commit |
| **H2（混合）** | RealRPE (70%) + LLM appraisal (30%) | 17 owner learner 跑 100 tick — 混合驱动 — 应比 H0 更稳，比 H1 收敛更快 |

### 2.3 关键假设（**严密**）

1. **H_alt_1**：RealRPE 驱动的 dopamine 残差（predicted − actual）有显著方差（**不应全是 noise**）
2. **H_alt_2**：RealRPE 驱动的 cortisol 在"目标冲突未缓解"时显著上升（**有状态-后果相关性**）
3. **H_alt_3**：H1 在 100 tick 内 regime 切换次数比 H0 **显著更多**（**真实后果触发的 regime 切换应该是更频繁的**）
4. **H_alt_4**：H1 的 commit_count 比 H0 **显著更少**（**真实后果驱动的 commit 应该更难触发**——比 LLM appraisal 更严苛）
5. **H_alt_5**：H1 跟 H2 的 residual correlation 在 dopamine 维度 > 0.5（**H2 是混合驱动不是完全无关**）

### 2.4 验收门

- **A1**：RealRPESignal 真实构造器 ship + 单测 100% pass
- **A2**：H1 vs H0 在 regime_switch_count 上有 ≥2x 差异（**统计显著**）
- **A3**：H1 vs H0 在 commit_count 上有 ≥3x 差异（**H1 commit 更少**）
- **A4**：H2 跟 H1 在 dopamine 维度 Pearson r > 0.5（**混合驱动不是完全无关**）
- **A5**：3 组实验在同一 owner (R11 memory) 上跑出**显著差异**（不是 noise）

## 3. 非目标

- **不**做 P5-B 类脑记忆规范化（独立任务）
- **不**做 P5-C 快慢思维决策（独立任务）
- **不**做 P5-D 类图灵验收（独立任务）
- **不**改 17 owner learner 的内部算法（**只换信号源**）
- **不**merge 到 main（**铁律**）

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| RealRPE 构造器不可行（真实运行后果无法获取） | 仿真环境 mock — 用 deterministic reward 函数模拟 |
| 实验组间差异是 noise 而非真实信号 | 3 组 × 5 owner × 100 tick × 5 seeds = 7500 跑，统计检验 |
| 真实后果反馈环 owner 边界模糊 | 限制 RealRPE 只读 4 个 neuromodulator channel + 3 个 owner 输入 |
| LLM appraisal 跟 RealRPE 完全无关（混淆了"主观"和"客观"两个不同维度） | 这是 feature 不是 bug — 实验目的就是验证两者**不是同一种信号** |

## 5. 路线图（**3 周**）

| 周 | 任务 | 验收 |
|---|---|---|
| W1 | RealRPESignal 构造器 + 单测 + 真 LLM smoke | A1 ✅ |
| W2 | 三组对照实验 (H0/H1/H2 × 5 owner × 5 seeds) | A2/A3/A5 ✅ |
| W3 | 实验报告 + R-PROTO-LEARN.P5-A commit + push | A4 ✅ + 调研文档 |