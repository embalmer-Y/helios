# R-PROTO-LEARN.8 修复 P5-feel first-version W 缺陷

## 0. 摘要

**目标**：修复 P5-feel (R-PROTO-LEARN.7) 暴露的 4 大核心问题，让真实 LLM appraisal 跟 canonical feeling 的差距 (residual 0.5-0.9) 显著缩小到 (residual 0.1-0.3)，并触发 regime 切换到 HABITUAL 跟 commit。

**约束**：
- **绝对不合并到 main**（main 永远 `15b4650`）
- 调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` HEAD `434006d` 继续推 commit
- 调研分支从 main `15b4650` 拉，可直接动 `src/`

**Owner**：05 interoceptive feeling layer

**分支计划**：保持调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` 不变（不创建新子分支），按 P5-feel 1 commit ship 风格做 R-PROTO-LEARN.8 1 commit ship

**周期**：1 个 P5-feel 切片

## 1. 现状（2026-06-17 01:18 extended smoke 暴露）

### 1.1 Extended smoke 数据
| Block | |W| 变化 | avg_max_res | min_max_res | max_max_res | commits | regime |
|---|---|---|---|---|---|---|---|
| A 8 情绪 | +0.0023 | 0.569 | 0.456 | 0.764 | 0 | exp→model |
| B 16 生活 | +0.0049 | 0.640 | 0.475 | **0.900** | 0 | model→exp |
| C 20 长程 | +0.0027 | 0.574 | **0.351** | 0.716 | 0 | exp→model |
| D 4 极端 | +0.0005 | 0.537 | 0.475 | 0.602 | 0 | model→model |

### 1.2 4 大核心问题

#### 问题 1：first-version R36 W 矩阵太稀疏
- 7 dim × 9 channel = 63 个权重
- `_FIRST_VERSION_WEIGHTS` 只定义了 **22 个非零** (≈35%)
- 例如 fatigue 维度只有 `excitation: 0.20, inhibition: 0.20`（2 个非零，缺 90%）
- 实际真实 LLM appraisal 反映：
  - "发烧 39 度" LLM 给 `fatigue=0.9, pain=0.9` 但 R36 给 `fatigue=0.2, pain=0.0`（**缺 90%**）

#### 问题 2：学习率 0.01 太慢
- 实际跑 48 次对话，|W| 变化最大 +0.0049
- 学 0.5 改进需要 25 次对话 × 7 秒 = 175 秒
- 而 smoking 1 block 才 16 dialogue
- **要学得"能 commit" (residual < 0.2) 至少需要 50+ dialogue**（时间不够）

#### 问题 3：commit 永远不触发
- commit 条件：`max(residual) < commit_threshold=0.2` 连续 20 tick
- 实际 residual 0.5-0.9 远大于 0.2
- 全部 4 个 block commits=0

#### 问题 4：regime 永远不切到 HABITUAL
- regime EXPLORATORY → MODEL_BASED 来回摆动
- HABITUAL 需要 residual < 0.3 连续 5 tick
- 实际始终 > 0.3 → 永远到不了 HABITUAL

## 2. 修复方向（3 选 1 → 实际是 3 个组合修复）

### 修复 A：发全套 7×9 W 矩阵（49 个权重）
- **从硬编码 22 个 → 完整 63 个权重**
- 用 Panksepp 神经回路 + 临床常识填上 missing ones
- 关键修复：
  - **fatigue** 行：加 `cortisol: 0.30, dopamine: -0.30, serotonin: -0.20`
  - **pain_like** 行：加 `norepinephrine: 0.20, serotonin: -0.20`
  - **tension** 行：加 `acetylcholine: 0.10`
  - **arousal** 行：加 `dopamine: 0.10, acetylcholine: 0.10, serotonin: -0.10`
  - **valence** 行：加 `norepinephrine: 0.10`
  - **comfort** 行：加 `norepinephrine: -0.10, acetylcholine: -0.10`
  - **social_safety** 行：加 `opioid_tone: 0.10, dopamine: 0.10`

### 修复 B：调整学习率 + commit_threshold
- `learning_rate`: 0.01 → **0.05**（5 倍）
- `commit_threshold`: 0.2 → **0.3**（允许更大 residual commit）
- `min_stable_ticks`: 20 → **8**（更快固化）
- `frozen_ticks_post_commit`: 10 → **5**

### 修复 C：调节 regime 切换阈值
- `flexibility_threshold`: 0.4 → **0.3**（ACh 0.3+ 触发 EXPLORATORY）
- `regime_hysteresis_ticks`: 2 → **3**（更稳定）
- 引入新的 `habitual_residual_threshold`: 0.5（即使 residual 大但稳定也可 HABITUAL）
- `habitual_recent_window`: 5 → **3**（更快判 HABITUAL）

### 修复 D（可选）：扩大 LLM appraisal 影响
- 当前 `_explore_residual` = LLM - current_feeling（差值驱动）
- 改为：`_explore_target` = `(LLM + 2 * current) / 3` 混合 target（让 current 也有话语权）
- 或：`_explore_residual` = LLM - last_committed_feeling（更稳定 target）

## 3. 推荐方案：修复 A + 修复 B + 修复 C（不实施修复 D）

理由：
- **修复 A**：用 Panksepp 神经回路 + 临床常识填全 7×9 = 63 权重，让 baseline 跟 LLM 接近
- **修复 B**：让学习在合理时间内 commit
- **修复 C**：让 regime 切换正常工作
- **不修修复 D**：保留 LLM appraisal 主导（对应 aINS 探索阶段），避免 learned W 跟 LLM 互锁

## 4. 具体实施步骤

### Step 1：扩 7×9 W 矩阵（修复 A）
**文件**：`src/helios_v2/feeling/learning_path.py`
**改动**：`_FIRST_VERSION_WEIGHTS` 6 个 missing 维度补全

### Step 2：调 learning config（修复 B + C）
**文件**：`src/helios_v2/feeling/learning_path.py`
**改动**：`P5FeelLearningConfig` default 调整

### Step 3：调 extended smoke 默认参数
**文件**：`scripts/r_proto_learn_7_p5_feel_extended_smoke.py`
**改动**：ext smoke 用新 defaults（不写死参数，让 learner 用新 default）

### Step 4：跑测试
- **单元测试**：`tests/test_r_proto_learn_7_p5_feel.py` 47 个全 pass
- **extended smoke** 真 LLM 跑：4 block × 48 dialogue
- 期望：commits ≥ 3, regime 至少一次切到 HABITUAL, avg_max_res < 0.4

### Step 5：更新 3 件套
- `docs/requirements/research-p5-feel-fix-1/` 新增（requirement.md / design.md / task.md）
- **小黑 2026-06-16 11:54 拍板**：调研分支可改 src/，**不强制走需求流程**——但 fix-1 是 fix 工作，按规约**走 3 件套**
- 更新 `research_notes_v2_journals.md` 章节"R-PROTO-LEARN.8 修复记录"

### Step 6：1 commit ship（保持 P5-feel 1 commit ship 风格）
```
fix(R-PROTO-LEARN.8): P5-feel first-version W matrix full + config retune
```

## 5. 验收标准

| 指标 | 当前（fix 前） | 目标（fix 后） |
|---|---|---|
| 4 block commits 总数 | 0 | ≥ 3 |
| 至少 1 个 block regime 切到 HABITUAL | ❌ | ✅ |
| avg_max_res 整体 | 0.6-0.7 | < 0.4 |
| max_max_res 整体 | 0.9 | < 0.7 |
| min_max_res 整体 | 0.4-0.5 | < 0.3 |
| 单元测试 47 个 | pass | pass (无破坏) |
| 整库测试 1300 passed | pass | 1300+ passed (无破坏) |

## 6. 不做的事

- ❌ 不创建新子分支（保持 `research/R-PROTO-LEARN-appraisal-multi-mechanism`）
- ❌ 不合并到 main
- ❌ 不修改 9-dim hormone channels
- ❌ 不修改 7-dim feeling dimensions
- ❌ 不破坏 P5-feel 现有 47 个单元测试
- ❌ 不破坏整库 1300 passed
- ❌ 不引入新依赖

## 7. 风险与回退

### 风险 1：W 矩阵发全套可能 over-claim
- 7×9 = 63 个权重 = 0.05 增量 × 63 = 3.15 累计变化
- 修后 residual 应在 0.3 区间

### 风险 2：commits 触发了但 commit 内容是错的
- 缓解：`frozen_ticks_post_commit=5` 让 commit 后冻结 5 tick 不再学
- 验证：ext smoke 跑完检查 commit_count

### 风险 3：extended smoke 新 default 跑出回归
- 缓解：unit test 47 个先跑，1300+ 全过再做 smoke
- 回退：git reset 434006d --hard

## 8. 周期

| Step | 预计时间 |
|---|---|
| Step 1 改 W 矩阵 | 30 min |
| Step 2 改 config | 15 min |
| Step 3 改 smoke | 10 min |
| Step 4 跑测试 + smoke | 30 min (含 LLM 调用) |
| Step 5 写 3 件套 | 30 min |
| Step 6 commit + push | 10 min |
| **总计** | **~2h** |

## 9. 后续（fix 完成后）

- **R-PROTO-LEARN.9**：三态切换深度优化 + 真实 LLM 长期累积（20+ tick 验证 HABITUAL）
- **R-PROTO-LEARN.10**：LLM appraisal ground truth 完善（多 turn dialogue + context 累积）
- **R-PROTO-LEARN.11**：PR 整合到 main（待小黑拍板）
