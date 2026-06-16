# 需求 P5-feel：owner 05 feeling 的真 P5 自我学习

> 状态：**调研分支直接全套实现**（小黑 2026-06-16 ~19:50 拍板）——
> 学术 ground truth 一次性 ship，验证方案真实有效性
> 调研分支：`research/R-PROTO-LEARN-appraisal-multi-mechanism`
> 范围：与 6 层 emotion system 同分支，跳过需求流程（按小黑 2026-06-16 11:54 拍板）
> 验收：真 LLM 跑通（8-15 条 ZH 情绪对话）+ 漂移收敛

## 0. 目标（学术权威版 + helios 落地）

把神经科学**3 篇核心论文**（Fermin 2021 IMAC + Reddan 2018 embodied emotion + Hinrichs 2025 hyperscanning）
直接落地为 helios owner 05 feeling 的 P5 真学习切片：

- **真实学习**（不是 hardcoded 默认值、不是 LLM 直觉、不是 1 步拟合）
- **完整三阶段**（habitual / model-based / exploratory）
- **DA precision + ACh flexibility 双驱**（不是单纯 RL reward）
- **lifelong 多阶段固化**（先探索后固化，不是 1 次性拟合）
- **真实 LLM 验证**（8-15 条 ZH 情绪对话跑通）

## 1. 范围

### 1.1 学术 ground truth（**已 download PDF**）

| # | 论文 | 关键贡献 | PDF |
|---|---|---|---|
| 1 | Fermin, Yamawaki, Friston (2021) "Insula Interoception, Active Inference and Feeling Representation" | IMAC 模型：3 层岛叶 + 3 PFC-striatum 回路 + mesaception/metaception 概念 + DA/ACh 双驱 | `/tmp/insula_active_inference.pdf` (1.4MB) |
| 2 | Reddan, Chang, Kragel, Wager (2018) "Somatosensory and motor contributions to emotion representation" | fMRI 证实 4 区域（somatosensory/motor/insula/mPFC）支撑 embodied emotion | `/tmp/somatomotor_emotion.pdf` (1.5MB) |
| 3 | Hinrichs, Albarracin, Bolis et al. (2025) "Geometric Hyperscanning of Affect under Active Inference" | valence = self-model prediction error weighted by self-relevance | `/tmp/geometric_affect.pdf` (3.2MB) |
| 4 | Seth (2013) "Interoceptive inference, emotion, and the embodied self" | 经典 interoceptive inference 框架 | R-PROTO-LEARN research_notes.md |
| 5 | Barrett (2017) "The theory of constructed emotion" | 构造情绪理论（constructed emotion） | R-PROTO-LEARN research_notes.md |
| 6 | Friston (2010) "The free-energy principle" | 主动推理 / 自由能 | R-PROTO-LEARN research_notes.md |

### 1.2 helios 落地的 5 项必备实现

| # | 切片 | 算法 | 神经对应 | 实现位置 |
|---|---|---|---|---|
| 1 | **探索阶段** | R-PROTO-LEARN.2 LLM appraisal 作 ground truth | aINS exploratory | `feeling/learning_path.py` + 复用 R-PROTO-LEARN.2 |
| 2 | **固化阶段** | 连续 N tick mapping 不变 → 写入 owner 05 config | gINS habitual | `feeling/learning_path.py` |
| 3 | **精度信号（DA）** | mapping 残差 ↔ dopamine 调 confidence | R81 precision signal | `feeling/learning_path.py`（复用 R81）|
| 4 | **灵活性信号（ACh）** | novelty ↔ acetylcholine 决定是否学新 mapping | Fermin 2021 ACh 角色 | `feeling/learning_path.py`（**新**）|
| 5 | **三态切换** | aINS / dINS / gINS = R88 漂移收敛触发 | Fermin 2021 IMAC 三回路 | `feeling/learning_path.py`（**新**）|

**5 项 = 一个切片 = 一个 commit**（不切分、不阶段化）。

## 2. 验收

### 2.1 单元 / 集成测试
- 跑通整库 `pytest tests/ -q --ignore=scratch_r79b`（**0 失败**）
- 新增 30+ 测试覆盖：
  - 5 项算法各自独立测试
  - 5 项算法集成测试
  - DA precision 信号测试
  - ACh flexibility 信号测试
  - 三态切换测试
  - 真实 7 维 feeling output 测试

### 2.2 真 LLM 验证
- 跑 8-15 条 ZH 情绪对话（沿用 R-PROTO-LEARN smoke 数据集 + 增 5-7 条 cover 慢路径场景）
- 每个对话观察：
  - 7 维 feeling 输出在 LLM appraisal 触发下方向正确
  - dopamine precision 真实收敛
  - acetylcholine flexibility 真实触发探索
  - 阶段切换可观察
  - 经过 N tick 后 mapping 写入 config

### 2.3 行为验收
- **P5-feel 跑后**：
  - owner 05 feeling 输出在长跑（100+ tick）下**不再 hardcoded 常数**（变化 > 0.05 量程）
  - 同一激素状态下，连续 tick 行为**更可预测**（无 jitter）
  - 新激素状态下**有探索行为**（ACh > threshold → 探索新 mapping）

### 2.4 失败兜底
- 如果 DA + ACh + 3 阶段跑通后，**真实 LLM 验证暴露设计 bug** → 修 bug → 不切分补到同一个 commit
- 如果**整套方案暴露根本性不可行** → 报告小黑 → 决定是返工还是放弃

## 3. 不属本切片（明确排除）

- **owner 03 appraisal 关键词写死的根本性清理**（R40/R97 26 条）—— P5-feel 假设 9 通道 hormone 已是 ground truth
- **3rd order PFC introspection**（owner 11 internal_thought 反思 feeling）—— 后续切片
- **社会 affective**（Hinrichs 2025 hyperscanning / Forman-Ricci）—— R-PROTO-LEARN.6 远期
- **owner 04 neuromodulation R81 corroboration 内部机制**——已 ship，仅复用
- **R88/R89/R90 评估器内部机制**——已 ship，仅作 ground truth / 验证工具

## 4. 决策点（已拍板，小黑 2026-06-16 ~19:50）

- **分支**：调研分支（不阻塞 main）
- **不切分**：5 项一次到位 ship 一个 commit
- **验证**：真 LLM smoke + 整库测试 + 行为验收
- **失败处理**：暴露 bug 同 commit 修；根本性不可行 → 报告小黑

## 5. 依赖

### 已 ship（直接复用）
- R-PROTO-LEARN.1 interoception（`a0533d8`）—— 9 通道 hormone → appraisal bias
- R-PROTO-LEARN.2 LLM appraisal（`9fa98a8`）—— ground truth 来源
- R-PROTO-LEARN.5 Bayesian concept（`a0533d8`）—— 5 维 emotion concept
- R81 corroboration（main）—— precision signal
- R88 漂移评估（main）—— 三态切换触发
- R96 真实 embedding（main）—— feeling 记忆检索
- R80 9 channel hormone（main）—— input

### 待 ship（本切片）
- 全部 5 项 P5-feel 算法

## 6. 风险

| 风险 | 缓解 |
|---|---|
| 真实 LLM 暴露 DA+ACh 双驱设计 bug | 1 个 commit 内修 |
| 三态切换判定不收敛（R88 漂移信号不稳）| 用 fallback：连续 N tick 同 mapping 直接 habitual |
| 9→7 维权重矩阵学习过慢 / 发散 | 学习率保守（0.01）+ 残差 clip |
| 探索 + 固化冲突（ACh high 时不该写 config）| ACh > threshold 时禁用写入 |
| 5 项一起 ship 出问题难 debug | 写 5 个 sub-test helper，分别 enable/disable |
