# Research: R-PROTO-LEARN — 6-Layer Multi-Mechanism Appraisal 调研

> **配套**：`design.md` + `task.md` + `research_notes.md`。
> **ROADMAP §5 R99+ 切片的预备调研**；§1.0 R97/R98 后 next-step。
> **依赖**：R96（real semantic embedding）+ R97（ZH anchors）+ R98（post-LLM hormone adjustment）+ R85（memory store）。
> **状态**：调研阶段（**仅调研，不实施代码**）。小黑 2026-06-16 拍板走方案 (a) 6-8 周全套 / 3 周 MVP。
> **作者**：小白，2026-06-16 06:30-（调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism`）

---

## 1. 问题陈述（实证 + 反思）

### 1.1 现状：hardcoded catalog 是"过时范式"

远端 main 在 R97/R98 之后，appraisal `03` 拥有 **26 条 hand-authored 短语**作为 threat/reward anchors：

| 来源 | 数量 | grounding |
|---|---|---|
| R40 英文 `THREAT_PROTOTYPES` | 5 英文 | C_engineering_hypothesis |
| R40 英文 `REWARD_PROTOTYPES` | 5 英文 | C_engineering_hypothesis |
| R97 ZH `THREAT_ANCHORS` | 5 中文 | PANAS-X 中文翻译 + 心理学词表 |
| R97 ZH `REWARD_ANCHORS` | 5 中文 | PANAS-X 中文翻译 + 心理学词表 |
| R98 ZH `THREAT_SET_A` | 6 中文 | DSM-5/ICD-11 焦虑/抑郁/急性 distress 身体症状 |
| **合计** | **26 条 hardcode** | — |

`appraisal/engine.py` 第 378-382 行 **代码注释自己承认**：
> "They are an explicit, hand-authored, English-centric PLACEHOLDER anchor with `C_engineering_hypothesis` grounding -- NOT a calibrated affective model. They are the surface a later slice replaces (P5 learning of the prototypes/gains, a `06` memory-affect grounding scoring threat/reward from the outcomes of similar past experience, or a slow `11`-LLM second-stage re-appraisal). They must not be over-claimed as real threat/reward understanding."

### 1.2 根因分析：单一机制 → 多机制涌现

**小白上一轮的盲点**：把 5 个方案当成"互斥选项"列出来。

**小黑原话**（2026-06-16 ~06:00）：
> "我感觉这些方案并不是互斥的你给我总结的几个科学理论看起来也并不是互斥的，而且每一种都解释了某一种现象"

**白话修正**：
- **5 个理论不是互斥**——是同一系统的 5 个机制层（构造 / 预测 / 记忆 / 内感受 / 社会）
- **5 个方案不是互斥**——是同一系统的 5 个工作模式（快路径 / 冷启动 / 慢路径 / self-model / 后台学习）
- 5 个理论 + 5 个方案对应到 **6 层 emotion system**：
  - Layer 1 内感受 / 方案 E
  - Layer 2 预测 / 方案 A
  - Layer 3 记忆 / 方案 D
  - Layer 4 构造 / Constructed Emotion
  - Layer 5 学习 / 方案 C
  - Layer 6 Fallback / 方案 B

**根因**：当前 helios 只有 **Layer 3（部分）+ Layer 6（部分）**——其他 4 层缺失。

### 1.3 R-PROTO-LEARN 调研要回答的问题

1. **6 层 emotion system 怎么定义？** layer 间数据流、API 边界、依赖关系
2. **6 个子切片怎么切？** 哪个先做、哪个后做、哪个是 MVP、哪个是 stretch
3. **怎么跟 R99-R104 既有切片对接？** R99-R104 已经处理 Layer 3 的一部分
4. **风险评估**：每层切片的落地难度、依赖、测试需求、跟 R97/R98/R96 的边界
5. **MVP 3 周落地路径**：R-PROTO-LEARN.6 fallback + .5 Bayesian + .1 interoception
6. **完整 6-8 周路径**：6 个子切片全做

---

## 2. 范围

### 2.1 In scope（调研要产出）

1. **6 层 emotion system 总体 design**（`design.md`）：
   - 6 层架构图 + layer 间数据流
   - 每层 API 边界（输入、输出、依赖、被依赖）
   - 每层对应 1 个理论 + 1 个方案 + 1 个 helios owner
   - 跟 R97/R98 现有 26 条 hardcode 的兼容路径（**降级为 Layer 6 fallback，不删**）

2. **6 个子切片 outline**（`task.md`）：
   - R-PROTO-LEARN.1 (Layer 1 内感受)
   - R-PROTO-LEARN.2 (Layer 2 预测)
   - R-PROTO-LEARN.3 (Layer 3 记忆 = R99-R104 既有切片，**无需新增**)
   - R-PROTO-LEARN.4 (Layer 4 构造)
   - R-PROTO-LEARN.5 (Layer 5 学习)
   - R-PROTO-LEARN.6 (Layer 6 Fallback)

3. **MVP 切片清单**（3 周）：R-PROTO-LEARN.6 + .5 + .1

4. **风险评估**：每层切片的落地难度 + 依赖 + 测试需求

5. **跟 R99-R104 既有切片的对接方案**：避免重复实现

6. **学术依据汇总**（`research_notes.md`）：11 篇论文的引用 + 5 个理论的对应

### 2.2 Out of scope（不在本调研内）

1. **不写代码**：本调研只写设计 + 调研笔记，不动 helios_v2 任何 owner
2. **不实施子切片**：R-PROTO-LEARN.1-6 是下一阶段实施切片，本调研不实施
3. **不修改 R97/R98 现有 26 条 hardcode**：本调研只规划"如何降级为 Layer 6 fallback"
4. **不重新设计 owner 03 appraisal**：本调研只规划"如何加 Layer 1+2+4 增量"
5. **不评估 social allostasis（Layer 7）**：缺 P4 网络通道，留 P3+ 远期

---

## 3. 退出信号（可证伪）

### 3.1 调研结束的标志

- [ ] `design.md` 6 层 emotion system 总体设计完成
- [ ] `task.md` 6 个子切片 outline 完成（含 MVP 切片清单）
- [ ] `research_notes.md` 学术依据汇总完成（11 篇论文 + 5 个理论）
- [ ] 风险评估 + 跟 R99-R104 对接方案完成
- [ ] **小黑拍板**：是否进入实施阶段 + 走 MVP（3 周）还是全套（6-8 周）

### 3.2 调研质量的可证伪标准

- 6 层架构是否 **数据流无环**（每层只依赖下层 + 横向输入）
- 6 层架构是否 **owner 边界清晰**（每层只跟 1-2 个 helios owner 对接）
- 6 层架构是否 **跟 R97/R98/R96 现有路径兼容**（不破坏现有 1174 测试）
- MVP 3 周切片是否 **每片可独立交付**（不阻塞其他切片）
- MVP 3 周切片是否 **每片可证伪验收**（有 B3+ / B4+ 量化指标）

### 3.3 R-PROTO-LEARN 总体目标（实施后）

- 真实云端 85 句 cortisol 正负分离 **≥ +0.10**（B3 headline 闭合）
- 真实云端 85 句 cortisol 正负分离 **≥ +0.05**（B2 headline 闭合）
- appraisal `03` threat/reward 不依赖任何 hardcoded phrase 字典
- 冷启动 fallback（Layer 6）保留 11 ZH + 10 EN anchors，**降级为 description** 而非 keyword
- 6 层融合后 appraisal latency 增量 **< 200ms/tick**

---

## 4. 6 层 emotion system 概览

### 4.1 数据流图

```
visitor input
   ↓
[Layer 2: 预测层（Predictive Coding）] ← LLM context (R98)
   ↓ surprise score
[Layer 1: 内感受层（Active Inference）] ← 17-dim hormone (R81)
   ↓ interoceptive state
[Layer 3: 记忆层（Pattern Completion）] ← R85 memory store + R10 retrieval
   ↓ similar past episodes
[Layer 4: 构造层（Constructed Emotion）] ← LLM 实时构造 emotion concept
   ↓ emotion concept
[Layer 5: 学习层（Bayesian update）] ← R100 importance + 双写机制
   ↓ learned emotion prior
   ↓
appraisal 03 output: threat / reward / novelty / etc.
   ↓
R36 appraisal-derived dynamics → 04 神经调质 → cortisol / dopamine / etc.
```

### 4.2 6 层 + 5 理论 + 5 方案 + helios owner 对应表

| Layer | 5 理论 | 5 方案 | helios owner | 现状 | 风险 |
|---|---|---|---|---|---|
| 1 内感受 | Active Inference (interoception) | E (17-dim hormone) | owner 04 神经调质 | 100% 已有 | 低（要写 LLM mapping） |
| 2 预测 | Predictive Coding (surprise) | A (LLM predict + compare) | owner 11 LLM | 50% 已有（R81） | 中（要改 owner 03） |
| 3 记忆 | Pattern Completion (海马体) | D (R85 outcome_class) | owner 06 memory | 90% 已有（R99-R104） | 低（基本复用） |
| 4 构造 | Constructed Emotion | — | owner 11 LLM | 0%（需 emotion concept 输出） | 高（要 LLM 实时构造） |
| 5 学习 | Bayesian update | C (R100 importance) | owner 06 memory + 03 appraisal | 30% 已有 | 中（要写 Bayesian update） |
| 6 Fallback | — | B (EmoGist description) | owner 03 appraisal | 70% 已有（R97/R98 anchors） | 极低（只改 anchor 字段） |

### 4.3 MVP 3 周切片清单

| 切片 | 周 | 工作量 | 输出 |
|---|---|---|---|
| R-PROTO-LEARN.6 (fallback) | 第 1 周 | 3-5 天 | R97/R98 11 ZH + 10 EN 锚点升级为 description |
| R-PROTO-LEARN.5 (Bayesian) | 第 2 周 | 1 周 | R100 importance 升级到 emotion concept 概率更新 |
| R-PROTO-LEARN.1 (interoception) | 第 3 周 | 1 周 | hormone → appraisal 集成（hormone state 写入 appraisal 03 输入） |

### 4.4 完整 6-8 周切片清单

| 切片 | 周 | 依赖 | 风险 |
|---|---|---|---|
| R-PROTO-LEARN.6 | 1 | — | 极低 |
| R-PROTO-LEARN.5 | 2 | .6 | 中 |
| R-PROTO-LEARN.1 | 3 | .6 | 中 |
| R-PROTO-LEARN.2 | 4-5 | .1, .6 | 中 |
| R-PROTO-LEARN.4 | 6-7 | .1, .2, .3, .5 | 高 |
| R-PROTO-LEARN.3 (R99-R104) | 已有 | — | — |

---

## 5. 关键决策

### 5.1 决策 1：R97/R98 26 条 hardcode **不删，降级为 Layer 6 fallback**

**理由**：
- R97/R98 已经交付并被远端 main 接受，不能粗暴删除
- Layer 6 fallback 仍有价值：冷启动、零经验时的安全网
- 升级为 description 而非 keyword 即可：Emoticist 风格 context-dependent

### 5.2 决策 2：调研分支不写代码

**理由**：
- 6 层 emotion system 涉及 owner 03 / 04 / 06 / 11，跨 owner 改动需要黑拍板
- 调研期先做 design + 风险评估，实施时再写代码
- 避免调研分支代码污染 main

### 5.3 决策 3：MVP 3 周先做 R-PROTO-LEARN.6 + .5 + .1

**理由**：
- 6 层全套 6-8 周太长，先 MVP 验证架构
- MVP 选 3 个低风险层（.6 极低 / .5 中 / .1 中）
- MVP 跑通后，黑再决定是否做 .2 + .4

### 5.4 决策 4：R-PROTO-LEARN.3 复用 R99-R104 既有切片

**理由**：
- R99-R104 已经规划了 Layer 3 的大部分
- 不重复实现，避免切片爆炸
- R-PROTO-LEARN.3 主要是"对接文档"，标注哪些 R99-R104 切片在 6 层架构里属于 Layer 3

---

## 6. 调研产出物清单

| 文档 | 内容 | 状态 |
|---|---|---|
| `requirement.md` | 本文档（问题陈述 + 范围 + 验收） | ✅ 完成 |
| `design.md` | 6 层 emotion system 总体设计 + 数据流 + API 边界 | 📝 调研中 |
| `task.md` | 6 个子切片 outline + MVP 清单 + 风险评估 | 📝 调研中 |
| `research_notes.md` | 11 篇论文引用 + 5 个理论对应 + 学术依据 | 📝 调研中 |

---

## 7. 时间线

| 阶段 | 时间 | 状态 |
|---|---|---|
| 创建调研分支 | 2026-06-16 06:30 | ✅ 完成 |
| `requirement.md` 起草 | 2026-06-16 06:30-07:00 | ✅ 完成 |
| `design.md` 起草 | 调研中 | ⏳ 进行中 |
| `task.md` 起草 | 待续 | ⏳ 待续 |
| `research_notes.md` 起草 | 待续 | ⏳ 待续 |
| 小黑拍板 | 待续 | ⏳ 待续 |
| 进入实施（MVP 3 周） | 待续 | ⏳ 待续 |

---

_Generated by 小白 on 2026-06-16 06:30-（调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` from main `15b4650`）。仅调研，不实施代码。_
