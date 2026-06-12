# R85 双重记忆架构预研 - 摘要

> **时间**：2026-06-12 07:44 - 08:00（~16 分钟）
> **目的**：基于人类记忆科学 + Helios 现状盘点 + 双线方案设计
> **状态**：调研完成，待小黑拍板

## 三层调研结论

### L1 神经解剖 (`01_neuroscience.md`)
人类记忆是**多类型**系统：
- 感觉 / 短时 / 长时（陈述性 vs 程序性）
- 长时子类：情景 / 语义 / 程序 / 启动 / 条件反射
- 关键脑区：海马 / 内嗅皮层 / 前额叶 / 杏仁核 / 蓝斑核
- 关键机制：突触标记 / 蛋白合成依赖巩固 / 重塑窗口

### L2 认知心理学 (`03_cognitive_psychology.md`)
人类记忆有**8 个关键机制** Helios 缺失：
1. **时间衰减**（Schacter 罪 1）
2. **期望性困难**（Bjork）—— 间隔 + 交错
3. **提取诱发遗忘**（RIF, Anderson）
4. **主动遗忘**（Anderson 2003）
5. **元认知**（Flavell）—— LLM 主动管理
6. **干扰理论**—— 主题分组
7. **外部验证**—— 错误记忆防御
8. **重塑窗口**（Dudai 2004）

### L3 计算模型 (`02_computational_models.md`)
现代 AI 记忆模型有 **11 个**重要方案：
- Hopfield → attention（理论统一）
- RETRO（DeepMind 2021）：检索嵌入架构
- MemGPT（2023）：LLM 主动管理记忆
- MemoryBank（2024）：遗忘 + 反思
- A-MEM（2025）：自描述 + cross-link

## Helios 现状盘点 (`04_helios_current_state.md`)

### 已有
- ✅ 7 owner 模块（memory / persistence / directed_retrieval / experience_writeback / embedding / continuity_checkpoint / evaluation）
- ✅ 4-tier 命名（short_term / mid_term / long_term / autobiographical）
- ✅ 两种 retrieval provider（recency + semantic）
- ✅ 两种 persistence backend（InMemory + SQLite）
- ✅ ConsolidationCandidate 概念
- ✅ Cross-tick carry (R81)

### 缺失（按严重性）
1. ❌ **单一 store 没有时间分层**（4-tier 命名有但实现同质）
2. ❌ **无时间衰减**（Ebbinghaus / 遗忘曲线缺失）
3. ❌ **LLM 主导决定 + 无客观算式覆盖**（实验 2 漏记 100% 根因）
4. ❌ **无 reconsolidation**（recall 不改写记录）
5. ❌ **无主动遗忘**（L18 治理部分）
6. ❌ **无 LLM 主动管理工具**（无 recall/forget/consolidate API）
7. ❌ **无反思周期**（无 DMN 模拟）
8. ❌ **无 sleep 巩固**（无后台任务）

### 实验数据支撑
- 实验 1：2/8 state LLM 漂移
- 实验 2：漏记率 100% (3/3)
- 实验 3：Precision 43%, Recall 100%, F1 60%
- **结论**：当前 F1 60% 不足，需要 75%+

## 双线方案设计 (`05_design_proposal.md`)

### 线 A：**时间分层 + 客观算式**（基础设施）
- **4 层 L2-L5**：工作 / 短时 / 长时 / 自传
- **客观算式 `objective_importance`**：6 维度加权
- **双重确认写入**：LLM True OR 算式 ≥ 0.5
- **Ebbinghaus 衰减**：5%/天（被回忆回弹）
- **Reconsolidation**：recall 时改写
- **预期**：F1 60% → 75%

### 线 B：**LLM 主动管理 + 反思 + 主动遗忘**（上层应用）
- **5 个 LLM 工具**：recall / consolidate / forget / link / reflect
- **ReflectionScheduler**：后台周期（每 100 tick）
- **SleepConsolidationJob**：后台周期（每 10 min wall）
- **ForgetOp + L18 治理**：软删除 + 7 天 GC + 审计
- **L5 自传体 layer**：被回忆 5 次 + 高 affect 才提升
- **预期**：LLM 主动管理 + 40%

### 实施路线（4 phase）
- **R85**（A1，3 天）：基础设施
- **R86**（A2，5 天）：分层 + 重塑
- **R87**（B1，3 天）：LLM 工具
- **R88**（B2，5 天）：反思 + 主动遗忘
- **总**：~16 天 / 8 owner

## 需要小黑拍板（5 个决策点）

1. **4 层 vs 2 层分层**？
2. **LLM OR 算式 vs 单线算式**？
3. **软删除 + 审计 vs 物理删除**？
4. **Sleep 巩固后台 vs 实时同步**？
5. **Reflection 暴露工具 vs 周期自动**？

## 文件清单

```
docs/research/memory_redesign/
├── 00_summary.md                      1421 bytes
├── 01_neuroscience.md                 5872 bytes
├── 02_computational_models.md         4898 bytes
├── 03_cognitive_psychology.md         4869 bytes
├── 04_helios_current_state.md         5253 bytes
└── 05_design_proposal.md              8778 bytes
                                       31091 bytes total
```
