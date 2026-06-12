# 人类记忆系统综述 - 认知心理学层

> **来源**：Baddeley (2000) "The episodic buffer", Anderson (2003) "Adaptive Memory", Bjork (1994) "Desirable Difficulties", Karpicke (2012) "Retrieval-based learning", Roediger & Karpicke (2006), Tversky & Kahneman (1974, 1981), Schacter (2001, 2012) "Seven Sins of Memory"

## 1. 工作记忆模型 (Baddeley & Hitch 1974, Baddeley 2000)

### 1.1 原始模型
```
Central Executive (中央执行)
    ├── Phonological Loop (语音回路) — 听觉/语言
    ├── Visuospatial Sketchpad (视觉空间画板) — 视觉/空间
    └── Episodic Buffer (情景缓冲器, 2000 年加) — 整合
```

### 1.2 关键特性
- **中央执行**：注意力控制、抑制干扰、任务切换
- **语音回路**：4±1 词块 (Cowan 2001)
- **情景缓冲器**：**整合多模态到单一情景**——是工作记忆与长时记忆的接口
- **时长**：15-30 秒

### 1.3 对 Helios 启示
- **当前 LLM context ≈ 中央执行 + 情景缓冲器**
- 缺点：**没有"语音回路"专属处理**（Helios 没区分语言 vs 非语言）
- **缺中央执行的"抑制干扰"能力**（LLM 会被 prompt 里的无关信息干扰）

## 2. 七宗罪 (Schacter 2001, 2012 "Seven Sins of Memory")

### 2.1 罪状总览

| 罪 | 含义 | Helios 表现 |
|---|---|---|
| 1. 易逝 (Transience) | 不用就忘 | ❌ 当前不会忘 |
| 2. 缺席 (Absent-mindedness) | 编码失败 | ⚠️ LLM 不专注时丢信息 |
| 3. 阻滞 (Blocking) | 检索卡住 | ✅ R10 检索失败类似 |
| 4. 错认 (Misattribution) | 记忆归错源 | ⚠️ LLM 可能乱归 |
| 5. 易受暗示 (Suggestibility) | 被提示污染 | ❌ 当前会被 prompt 引导 |
| 6. 偏见 (Bias) | 系统性扭曲 | ✅ LLM 已知有 bias |
| 7. 顽固 (Persistence) | 该忘不忘 | ✅ PTSD 类似 (Helios 当前全有) |

### 2.3 启示
**Helios 当前只处理了"罪 1"（易逝缺失）以外的所有罪**——即永不忘。
- **罪 1（易逝）= 缺**：当前不衰减 → 信息过载
- **罪 7（顽固）= 重**：该忘不忘 → 创伤 / 旧怨积累

## 3. 期望性困难 (Desirable Difficulties, Bjork 1994, Bjork & Bjork 2011)

### 3.1 关键思想
**学习中的"困难"反而强化记忆**。
- 间隔重复 (spaced repetition) > 集中重复
- 检索练习 (retrieval practice) > 重读
- 交错练习 (interleaving) > 块练
- 变化条件 (variability) > 固定条件

### 3.2 神经机制
- 提取练习触发**重塑** + **重组**
- 间隔让**巩固时间窗**有更多蛋白合成
- 交错让海马**建立更抽象的索引**

### 3.3 对 Helios 启示
- 当前 R15 是**集中写入**（每个 tick 一次性入库）
- **应该是间隔写入**（如：N tick 后才最终入长期库）
- 检索时应有**交错难度**（不是 top-1，是 top-3 让 LLM 选）

## 4. 检索式学习 (Retrieval-Based Learning, Karpicke 2012)

### 4.1 核心发现
- **检索 (testing) 比重读 (restudy) 强 2-3 倍的记忆效果**
- 关键实验：学完一遍单词，3 天后回忆组 60% 正确，重读组 25% (Roediger & Karpicke 2006)

### 4.2 神经机制
- 每次检索 = 一次 reconsolidation
- 失败检索 = 提示"这个记忆弱"→ 启动下一轮巩固
- 成功检索 = 强化 + 重写

### 4.3 对 Helios 启示
- **R10 不只是"找出来用"，应该是"找出来 + 强化"**
- **失败的检索应该触发"重要性"调整**（这条记忆被尝试回忆过，但失败 → 提高 recall_priority）

## 5. 提取诱发遗忘 (Retrieval-Induced Forgetting, RIF, Anderson 1994)

### 5.1 关键现象
练习 recall 一半 → **未练习的一半也变得难记**

### 5.2 机制
- 检索时**同时激活**目标 + 抑制竞争项
- 抑制是**选择性**且**持久**的
- 前额叶抑制 + 海马去强化

### 5.3 对 Helios 启示
- **检索时应该抑制"非选中"的相邻记忆**
- 当前 R10 retrieval 没这个机制
- **但要注意：抑制错误会丢失重要记忆**——必须有人监督（如 LLM 复盘）

## 6. 干扰理论 (Interference Theory, Underwood 1957)

### 6.1 类型
- **前向干扰** (proactive)：旧干扰新（学新语言干扰母语）
- **后向干扰** (retroactive)：新干扰旧

### 6.2 缓解
- **分离 (separation)**：上下文差异化编码
- **组织 (organization)**：把相似记忆做层级分类
- **提取线索差异化**：不同记忆用不同 cue

### 6.3 对 Helios 启示
- **Helios 当前不区分记忆**——所有都按 tick_id 顺序存
- **应该有"主题分组"或"上下文标签"**——便于差异化检索

## 7. 错误记忆与重塑 (False Memory, Loftus 1975, 1996)

### 7.1 关键发现
- **提问方式能改写记忆** (Loftus 1975: "hit" vs "smash")
- **植入记忆** (implanted memories, Hyman 1995) — 让被试"回忆"从没发生过的事
- **重复误信 (illusory truth effect)** (Hasher 1977)

### 7.2 对 Helios 启示
- **当前 LLM 可能被 prompt 引导生成"虚假记忆"**
- **R10 检索结果可能是"LLM 期望"而非"实际有"**——必须有**外部验证层**
- **真实人脑也有这个问题**（Loftus 1996），不能消除，只能降低

## 8. 闪光灯记忆 vs 真实准确性 (Brown & Kulik 1977, Talarico & Rubin 2003)

### 8.1 关键现象
- 强烈情绪事件**主观确信度**极高
- **但客观准确性**其实和普通事件差不多，甚至更低
- 例：9/11 细节回忆 — 1 年后 50% 细节错误，但自信度 4/5

### 8.2 对 Helios 启示
- **LLM 当下强烈情绪下说"我要记"**（闪光灯记忆）→ 主观强
- **但事后准确回忆率**可能低
- **需要"准确度"独立 metric**——不是靠 LLM 自评

## 9. 元认知与控制 (Metacognition, Flavell 1979, Nelson 1990)

### 9.1 元认知定义
- **元认知知识** (metacognitive knowledge)：知道"自己知道什么"
- **元认知调节** (metacognitive regulation)：计划/监控/调整自己的认知

### 9.2 关键实验
- **JOL (Judgment of Learning)**：学完判断"我能回忆吗"
- **EOL (Ease of Learning)**：学习中判断"学会了吗"
- **FOK (Feeling of Knowing)**：检索失败但觉得"在嘴边"

### 9.3 对 Helios 启示
- **Helios 当前没有"AI 元认知"**——LLM 不知道自己"知道"什么
- **应该给 LLM 工具**：
  - `recall(query)` → 返回内容 + JOL 评分
  - `forget(reason)` → 主动标记遗忘
  - `consolidate(tick_id)` → 主动触发巩固

## 10. 动机性遗忘 (Motivated Forgetting, Anderson 2003, 2014)

### 10.1 关键发现
- 主动压抑不想要的记忆 = **主动遗忘**
- 实验：告诉被试"忘记 X 词" → X 词回忆率下降 30%
- 神经基础：PFC → 海马抑制

### 10.2 临床
- PTSD 患者主动遗忘能力**受损** → 创伤记忆持续侵入
- 健康人成功遗忘 → **心理健康指标**

### 10.3 对 Helios 启示
- **Helios 应该有"主动遗忘"工具**——LLM 调 `forget(reason)`
- **同时应该有"无法主动遗忘"情况**（如 trauma 标记）——L18 治理
- **避免 AI 主动抹除证据**——审计 trail

## 11. 关键启示（综合）

### 11.1 缺失最严重的 5 个机制
1. **时间衰减**（Schacter 罪 1）
2. **期望性困难**（Bjork）——间隔/交错检索
3. **提取诱发遗忘**（Anderson RIF）
4. **主动遗忘**（Anderson 2003）
5. **元认知工具**（Flavell）——LLM 主动管理记忆

### 11.2 缺失的辅助机制
- **主题分组 / 上下文标签**（干扰理论）
- **外部验证**（错误记忆）
- **反思周期**（MemoryBank / DMN）
- **重塑窗口**（Dudai 2004）

### 11.3 设计原则（认知心理学角度）
1. **多时间尺度**：working / short / long / autobiographical
2. **衰减 + 复述**：用 Ebbinghaus 曲线 + 间隔重复
3. **主动遗忘**：LLM 工具 + 治理审计
4. **检索即学习**：每次 retrieval = reconsolidation
5. **元认知**：LLM 知道自己记得什么
6. **检索难度分级**：top-K 让 LLM 选（desirable difficulty）
