# R-PROTO-LEARN.P5-A.2: RealRPE hard-couple 到 17 owner learner

**Owner**: R-PROTO-LEARN 调研分支（`research/R-PROTO-LEARN-appraisal-multi-mechanism`）
**Created**: 2026-06-17
**Status**: ACTIVE — 修复 P5-A 负面发现
**小黑拍板**: 选项 B（修改 17 owner learner 让它对 RealRPE 敏感）

## 1. 背景

### 1.1 P5-A.1 负面发现（**真实**）
P5-A.1 (commit `5f0db68`) ship 的 3-group ablation study 揭示：
- 当前 17 owner learner 算法**对输入信号源不敏感**
- H0 (LLM appraisal) 跟 H1 (RealRPE) 跑出几乎一样的行为
- A2/A3/A5 验收门全失败

### 1.2 根因
- `_llm_signal_to_target_vec` 把 7-dim LLM appraisal 当 input
- W 矩阵 closure 学习（numpy pinv）吸收任何 bounded 7-dim signal
- 算法只关心 closure quality，不关心信号真实语义

### 1.3 ROADMAP 13.3 P5-A 第 2 条要求（**锁定约束**）
> "学习信号以脑脑的多巴胺奖励预测误差为主锚点，由**真实运行后果**定义"

## 2. 目标

### 2.1 让 17 owner learner **真正实现** P5-A 第 2 条

```
RealRPE 4-channel 显式驱动:
  ├─ dopamine RPE ──→ 5 个 owner 的 "confidence" 输出 dim
  ├─ norepinephrine ──→ 5 个 owner 的 "effort" 输出 dim
  ├─ serotonin ──→ 5 个 owner 的 "stability" 输出 dim
  └─ cortisol ──→ 5 个 owner 的 "threat" 输出 dim
```

### 2.2 关键架构改动

1. **`_llm_signal_to_target_vec` 接受双信号源**:
   - `llm_signal` (7-dim) 保留 — 提供"主观"信号
   - `rpe_signal` (4-dim) **新增** — 提供"真实后果"信号
   - 两者**显式 concat**成 11-dim 联合信号

2. **RPE 通道映射到 output 通道**:
   - dopamine (RPE) → "confidence" 类输出 (e.g. R11 replay_priority, R13 retrieval_planning)
   - norepinephrine (effort) → "effort" 类输出 (e.g. R12 gate_open_probability, R15 drive_integration)
   - serotonin (stability) → "stability" 类输出 (e.g. R14 thought_generation_rate, R17 fidelity_scoring)
   - cortisol (threat) → "threat" 类输出 (e.g. R13 tier_selection_priority, R21 commitment_threshold)

3. **W 矩阵维度升级**:
   - input_dim: 7 → 11 (7 LLM + 4 RPE)
   - output_dim: 不变 (每个 owner 特定)
   - 11xN W 矩阵 rank ≤ 7 (W 的 row dim) — **algebraic 限制仍在但 closure 性能变化**

4. **regime 切换由 RPE 触发**:
   - dopamine 极负向 → 强制 EXPLORATORY
   - serotonin 极低 + cortisol 极高 → 强制 MODEL_BASED
   - serotonin 稳定 + 残差 < threshold → 允许 HABITUAL

### 2.3 验收门

- **B1**: 17 owner learner 全部支持双信号源 (llm + rpe)，单测 100% pass
- **B2**: H1 (RealRPE) 跟 H0 (LLM) 在 regime_switch_count 上有 ≥2x 差异, p<0.01
- **B3**: H1 跟 H0 在 commit_count 上有 ≥3x 差异, p<0.01
- **B4**: 5 owner per-owner residual diff > 0.1
- **B5**: H2 (mixed) 跟 H1 dopamine 相关 r > 0.5
- **B6**: 17 owner 整库回归 ≥ 95% pass (允许少量 algebraic-limited owner 部分测试 fail)

## 3. 非目标

- **不**改 17 owner 的核心算法（closure / pinv / W update）— 只升级 input dim
- **不**重新设计 3 态 regime — 只新增 RPE 触发条件
- **不**改 mock 环境 — 30-tick 3-phase cycle 复用 P5-A.1
- **不**merge 到 main（铁律）

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 17 owner 全部改动回归测试大面积失败 | 逐 owner 增量 ship + 实时回归 |
| W 矩阵 11xN 维度升级导致 R12/R13 algebraic 限制更严 | 不强制 closure 完美，接受 algebraic 限制 |
| RPE 触发 regime 切换跟现有 hysteresis 冲突 | 加优先级：RPE 强制 > hysteresis 累积 |
| RPE 4-channel 跟 LLM 7-dim scale 不匹配（RPE 有 signed） | RPE 通道先 clip 到 [0, 1] 再 concat |
| 修改范围太大，破坏 17 owner 的可读性 | 抽 helper `_rpe_to_target_dim(feeling_dim_idx, rpe_channel, llm_signal)` |

## 5. 路线图

| 任务 | 验收 |
|---|---|
| W1 D1: 写 `LearnerConfig` 加 `rpe_signal` 字段（optional, default None） | -- |
| W1 D2: 写 `LearnerABC.update` 加 `rpe_signal` 参数（optional） | -- |
| W1 D3: 改 `_llm_signal_to_target_vec` 为 `_signals_to_target_vec(llm, rpe, novelty)` 内部接口 | -- |
| W1 D4: 写 helper `_rpe_to_output_dim_mapping` (per owner) | -- |
| W1 D5: 17 owner 全部升级 (5+2+4+4 = 15 owner) + 单测 | B1 |
| W2 D1: 改 ablation 脚本支持双信号源 | -- |
| W2 D2: 跑 75 runs ablation 验证 H0/H1/H2 行为差异 | B2/B3/B4/B5 |
| W2 D3: 整库回归 | B6 |
| W3: 写 result.md + commit + push | -- |