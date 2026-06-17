# R-PROTO-LEARN Tier 1 — 神经机制对位 (R11-R15)

## 1. 目标

完成 5 owner 真实学习 slice，对位 Parisi 2019 6 大神经机制 + Kotseruba 2018
3 大 metacognition 机制中**5 个核心 owner**：

| Slice | owner | LPC | 学术对位 |
|---|---|---|---|
| **R-PROTO-LEARN.11** | 06 memory | 3 | De Lange 2021 (replay) + Bhatt 2019 (reconsolidation) |
| **R-PROTO-LEARN.12** | 09 thought_gating | 3 | Einhauser 2018 (pupil=effort) + Parisi 2019 (curriculum) |
| **R-PROTO-LEARN.13** | 10 directed_retrieval | 3 | Parisi 2019 (transfer learning) + R85 4 层 store |
| **R-PROTO-LEARN.14** | 11 internal_thought | 3 | Kotseruba 2018 (self-observation) + R-PROTO-LEARN.7 P5-feel |
| **R-PROTO-LEARN.15** | 18 autonomy | 3 | Parisi 2019 (intrinsic motivation) + Kotseruba 2018 (self-regulation) |

## 2. 架构原则

### 2.1 统一学习框架
5 owner 共享一个 **`helios_v2/learning/`** 框架：
- `Learner` Protocol: `update(state, llm_signal, novelty, tick_id) -> (state, residual, regime, commit)`
- `LearnerConfig` frozen dataclass: 11 个超参数（与 P5-feel 相同）
- 3 态 `Regime` enum: EXPLORATORY / MODEL_BASED / HABITUAL
- W 矩阵 dense 化 + 5 算法 + numpy-only closure（与 P5-feel 完全一致）

### 2.2 numpy-only 路径（**无 fallback**）
- `module-level import numpy as np` 顶部导入（fail-fast）
- 缺 numpy 直接 ImportError（**小黑 2026-06-17 06:59 拍板**）
- R-PROTO-LEARN.9 已经验证，R11-R15 复用同套 pinv helper

### 2.3 旁路观察者
- 5 owner 各自加 **opt-in `p5_learner: LearnerABC | None = None` 字段**
- P5 learning **不修改 canonical state**，只观察 + 跟 canonical state 对位
- 跟 R-PROTO-LEARN.7 P5-feel 完全同模式

### 2.4 4 件套调研文档
- `docs/requirements/research-p5-feel-tier1/requirement.md` (本文件)
- `docs/requirements/research-p5-feel-tier1/design.md`
- `docs/requirements/research-p5-feel-tier1/task.md`
- `docs/requirements/research-p5-feel-tier1/result.md`

## 3. 5 owner 神经机制对位详细

### R11: owner 06 memory (3 cat)
**学术对位**: De Lange 2021 (replay) + Bhatt 2019 (reconsolidation = learning window)

- **`replay_priority_policy`**: 5 dim 输入 (affect_intensity, prediction_mismatch,
  autobiographical_salience, time_since_last_replay, novelty) → replay priority ∈ [0,1]
  - 学术依据: Parisi 2019 memory replay (海马回放) + De Lange 2021
  - R85 4 层 L2-L5 store 已有 replay trigger，本 slice 学习 priority 权重

- **`consolidation_policy`**: 4 dim 输入 (sleep_phase, affect_intensity,
  replay_count, time_since_formation) → consolidation rate ∈ [0,1]
  - 学术依据: Bhatt 2019 LTP→DNA methylation dual-timescale
  - R85 consolidation 时机 C+D (C 立即 = hot path / D idle batch = R86) 已有基础
  - 本 slice 学习 consolidation rate（DNA methylation 模拟）

- **`memory_family_write_policy`**: 3 dim 输入 (episodic_signal,
  semantic_signal, autobiographical_signal) → 3 dim output (episodic weight,
  semantic weight, autobiographical weight) softmax-normalized
  - 学术依据: Bhatt 2019 (episodic / semantic / autobiographical 分类)

### R12: owner 09 thought_gating (3 cat)
**学术对位**: Einhauser 2018 (pupil = effort) + Parisi 2019 (curriculum)

- **`signal_normalization_policy`**: 6 dim 输入 (norepinephrine, dopamine,
  acetylcholine, novelty, task_demand, signal_magnitude) → 6 dim output
  (normalized signal weights) ∈ [0,1]
  - 学术依据: Einhauser 2018 pupil dilation = effort 指标
  - LC-NE 系统 norepinephrine → 跟 effort 同步 → gate sensitivity

- **`continuation_policy`**: 4 dim 输入 (curriculum_stage, novelty,
  dopamine, signal_normalized) → 1 dim output (continuation_rate)
  - 学术依据: Parisi 2019 curriculum learning (Elman 1993)
  - task 难度渐进 → 跟 dopamine 信心协同

- **`gate_policy`**: 5 dim 输入 (dopamine, acetylcholine, novelty,
  continuation_rate, signal_normalized) → 1 dim output (gate_open_probability)
  - 学术依据: dopaminergic 信心门 + ACh 灵活性门（已部分实现）

### R13: owner 10 directed_retrieval (3 cat)
**学术对位**: Parisi 2019 (transfer learning) + R85 4 层 store

- **`tier_selection_policy`**: 6 dim 输入 (L2 episodic / L3 semantic /
  L4 autobiographical / L5 immutable / dopaminergic_signal / time_decay) →
  4 dim output (tier weights) softmax-normalized
  - 学术依据: R85 4 层 L2-L5 store 路线
  - replay 任务从哪一层取 → 学习 tier 权重

- **`retrieval_planning_policy`**: 5 dim 输入 (curiosity_signal,
  transfer_signal, retrieval_count, novelty, dopamine) → 3 dim output
  (episodic / semantic / autobiographical planning) softmax
  - 学术依据: Parisi 2019 transfer learning

- **`thought_window_shaping_policy`**: 4 dim 输入 (dopamine, retrieved_count,
  acetylcholine, continuation_rate) → 4 dim output (window_shape) ∈ [0,1]
  - 学术依据: Panksepp SEEKING 启发的主动检索

### R14: owner 11 internal_thought (3 cat)
**学术对位**: Kotseruba 2018 (self-observation) + R-PROTO-LEARN.7 P5-feel

- **`thought_generation_policy`**: 6 dim 输入 (feeling_state, novelty,
  dopamine, salience, continuation_rate, gate_open) → 1 dim output
  (thought_generation_rate)
  - 学术依据: R-PROTO-LEARN.7 P5-feel feeling → thought 协同
  - 跟 owner 05 feeling 的 7-dim feeling state 联动

- **`sufficiency_policy`**: 4 dim 输入 (thought_count, novelty, dopamine,
  continuation_rate) → 1 dim output (sufficiency_threshold)
  - 学术依据: R85 reconsolidation C+D 组合
  - 跨 tick 思考"是否足够" → 跟 dopamine 信心协同

- **`proposal_emission_policy`**: 5 dim 输入 (dopamine, feeling_state,
  acetylcholine, novelty, sufficiency) → 1 dim output (emission_rate)
  - 学术依据: dopaminergic emission gating

### R15: owner 18 autonomy (3 cat)
**学术对位**: Parisi 2019 (intrinsic motivation) + Kotseruba 2018 (self-regulation)

- **`drive_integration_policy`**: 7 dim 输入 (6 pressure + 1 threshold) →
  7 dim output (drive weights) ∈ [0,1]
  - 学术依据: Parisi 2019 intrinsic motivation (curiosity-driven)
  - 跟 R-PROTO-LEARN.7 P5-feel hormone→feeling 闭环协同
  - 自治压力 → 学习整合权重

- **`continuity_carry_policy`**: 4 dim 输入 (cross_tick_signal,
  autobiographical_salience, time_decay, identity_strength) → 1 dim output
  (carry_strength)
  - 学术依据: R85 phase 1 cross-tick carry state
  - 自我连续性 → 学习 carry 强度

- **`proactive_externalization_policy`**: 5 dim 输入 (autonomy_drive,
  gate_open, novelty, dopamine, continuity_carry) → 1 dim output
  (proactive_probability)
  - 学术依据: Kotseruba 2018 self-regulation (**P6 入口**)
  - 主动外化 → self-regulation 学习

## 4. 验收标准

1. **5 个新文件** in `helios_v2/learning/`
2. **5 owner 各自集成 opt-in p5_learner 字段**（不破坏现状）
3. **80+ 个新 unit test**（每 owner 16 个左右）
4. **真 LLM extended smoke** — 4 block × 48 对话（5 owner 都跑）
5. **整库 1440+ passed**（1368 baseline + 80+ R11-R15 = 1448+）
6. **R21 guard clean**
7. **调研分支不 merge main** (小黑确认)
8. **3 态 Regime 切换** — 4 blocks 至少 2 切到 HABITUAL
9. **commit + push** — 1 commit ship 5 slice

## 5. 范围限制

- **调研分支** `research/R-PROTO-LEARN-appraisal-multi-mechanism` 推 commit
- **绝对不 merge main**
- **不立即合并不在本 slice 范围内的 owner**（07/08/12/13/14/15/16a/16b/17/prompt_contract 留 R16-R20）
- **不破坏现有 owner contract**（旁路 opt-in）
- **不引入新依赖**（除 numpy 已装的）

## 6. 风险评估

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| 5 owner 集成时 contract 冲突 | 中 | 严格 opt-in 旁路 + 测试 helper default 跟生产一致 |
| numpy 装环境失败 | 低 | 上一轮 R-PROTO-LEARN.9 已验过 |
| 5 owner 同时测 + 整库跑超 timeout | 中 | 分两批跑（先 5 owner + R-PROTO-LEARN 5+1+1，最后整库） |
| W 矩阵 dim 跟各 owner state 字段对不上 | 中 | 每个 owner 仔细 audit state fields 维度 |
| 真 LLM smoke 5 owner 全开性能差 | 低 | 旁路 opt-in，默认 None 关闭 |

## 7. 进度节点

- T1: 学习框架 `helios_v2/learning/`（contracts + framework）
- T2: 5 owner 各自 learner + 集成
- T3: 80+ unit test
- T4: 整库 + 真 LLM smoke
- T5: 4 件套文档 + commit + push
