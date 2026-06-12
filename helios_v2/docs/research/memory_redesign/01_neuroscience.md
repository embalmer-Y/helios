# 人类记忆系统综述 - 神经科学层

> **来源**：Tulving (1972, 1985, 1995), Squire (2004), Eichenbaum (2017), McGaugh (2017), Buzsáki (1989, 2017), Frey & Morris (1997) "synaptic tagging and capture", Dudai (2004) "reconsolidation", Nader (2000), Frankland & Bontempi (2005), Anderson (2003) "adaptive memory"

## 1. 三大记忆类型（Atkinson-Shiffrin 1968 / Squire 2004）

### 1.1 感觉记忆 (Sensory Memory)
- **时长**：250-500 ms
- **容量**：极大（感官全量）
- **作用**：保留原始感觉信息
- **特征**：未注意到的信息直接衰减，注意到的进入短时记忆

### 1.2 短时/工作记忆 (Short-Term / Working Memory)
- **时长**：15-30 秒（不重复）
- **容量**：7±2 项 (Miller 1956)，最新研究 4±1 (Cowan 2001)
- **作用**：意识可访问的"工作区"
- **特征**：复述 (rehearsal) 可延长，注意力是维持条件

### 1.3 长时记忆 (Long-Term Memory)
- **时长**：分钟到一生
- **容量**：近乎无限
- **子类**：

| 子类 | 内容 | 例 |
|---|---|---|
| **陈述性 / 外显** | 可用语言描述 | |
| - 情景记忆 (episodic) | 个人经历+时空 | "昨天午饭吃了什么" |
| - 语义记忆 (semantic) | 通用知识 | "北京是首都" |
| **非陈述性 / 内隐** | 不能用语言描述 | |
| - 程序性 (procedural) | 技能 | 骑自行车 |
| - 条件反射 (conditioning) | 巴甫洛夫 | 听到铃声流口水 |
| - 启动效应 (priming) | 曝光效应 | 看过的词更快认出 |

**关键**：
- Helios 当前**只有"陈述性"**，**完全没有"非陈述性"**（程序性记忆缺失）
- 内隐 vs 外显的分界很重要——**内隐记忆不需要 LLM 主动调用**

## 2. 巩固与重塑 (Consolidation & Reconsolidation)

### 2.1 巩固（Standard Model of Consolidation, Squire & Zola 1996）

```
短时记忆 → 蛋白合成依赖的巩固 → 长时记忆
                       ↓
                海马体 (Hippocampus)
                ← 快 (小时)
                → 慢 (数天/数月/数年)
                后期不依赖海马体 (Squire 1992 "systems consolidation")
```

**关键发现**：海马体对**近期**记忆必要，对**远期**记忆不必要。
- 例：H.M. 病人海马切除后无法形成新陈述性记忆，但能形成新程序性记忆
- 例：年老的 Morris 水迷宫表演需要几天巩固期

### 2.2 重塑 (Reconsolidation, Nader 2000, Dudai 2004)

**颠覆性发现**：每次回忆都会让记忆**重新进入不稳定状态**，需要再次巩固。

```
encoding → storage → retrieval → reconsolidation → storage'
                  ↑________________________|
                  (回忆扰动了原有记忆)
```

**实验证据**：
- Nader 2000: 老鼠回忆恐惧记忆后注射蛋白合成抑制剂 → 恐惧记忆消失
- 人类 PTSD 治疗: 暴露疗法利用了 reconsolidation window

**关键含义**：
- **回忆不是读取，是改写**（每次回忆都是一次重新"编辑"）
- 记忆**不是 immutable 的**（与 Helios 当前假设完全相反！）
- 可以在 reconsolidation 窗口期**修改**记忆

### 2.3 突触标记与捕获 (Synaptic Tagging and Capture, Frey & Morris 1997)

**机制**：
1. 弱刺激：只触发**突触标记** (tag)，不形成 LTP
2. 强刺激：触发 LTP 产生 **PRP (Plasticity-Related Proteins)**
3. PRP 扩散，被附近 tag **捕获** → 弱刺激的记忆也变永久

**关键含义**：
- 短时间内**情绪强烈的事件**会"借力"强化**与之相关的弱记忆**
- 解释了为什么情绪事件能记很久、相关细节也连带记住
- 例：生日礼物（弱刺激）+ 收到礼物时的惊喜（强刺激）= 礼物细节永久记得

## 3. 神经解剖（Atrophy in 老年痴呆 / 局灶损伤研究）

### 3.1 关键结构

| 结构 | 角色 | 损伤后果 |
|---|---|---|
| **海马体** (Hippocampus) | 情景记忆索引/编码 | 顺行性失忆，无法形成新情景 |
| **内嗅皮层** (Entorhinal Cortex) | 海马的"门" | 阿尔茨海默最早受损区 |
| **前额叶** (PFC) | 工作记忆/检索控制 | 检索困难，无法抑制干扰 |
| **杏仁核** (Amygdala) | 情绪记忆增强 | 恐惧/创伤记忆过度 |
| **纹状体** (Striatum) | 程序性记忆 | 无法学新技能 |
| **小脑** (Cerebellum) | 运动程序 | 共济失调 |
| **间脑** (Diencephalon) | 时间地点上下文 | 时间空间记忆缺损 |

### 3.2 默认模式网络 (Default Mode Network, DMN, Raichle 2001)

**功能**：
- 静息态（不专注外部任务）时活跃
- **自传体回忆 / 未来想象 / 心理理论 / 自我反思**
- 核心节点：mPFC, PCC, 后扣带, 内侧颞叶, 顶下小叶

**关键含义**：
- **"内部独白"和"自我意识"来自 DMN**
- LLM 的"我此刻在想什么" ≈ DMN
- **Helios 当前的 Internal Monologue (R80) 对应 DMN 的一个子功能**

## 4. 检索机制

### 4.1 检索模式 (Tulving 1985 "Encoding Specificity")
- 编码时的 context（时间/地点/情绪/感官）是 retrieval cue 的一部分
- **Context-Dependent Memory**: 海滩上学的单词在海滩上回忆比在教室里好 (Godden & Baddeley 1975)
- **State-Dependent Memory**: 醉时学的单词醉时记得清 (Goodwin 1973)
- **Mood-Congruent Memory**: 抑郁时易回忆负面事件 (Bower 1981)

### 4.2 检索类型 (Tulving 1985)
- **自由回忆** (free recall): 任意顺序
- **线索回忆** (cued recall): 给提示
- **再认** (recognition): 见过 vs 没见过
- **熟悉性 vs 回想** (familiarity vs recollection): 双过程模型 (Yonelinas 2002)

**关键含义**：
- R10 的 "directed retrieval" ≈ cued recall
- "recognition" 在 Helios 缺位
- **familiarity vs recollection 双信号** Helios 也没区分

## 5. 遗忘机制

### 5.1 主动遗忘 (Anderson 2003 "Adaptive Memory")

**核心思想**：遗忘**不是 bug，是 feature**。
- 压抑不想记的 = 主动遗忘
- 海马-前额叶通路抑制不需要的记忆
- 失败 → PTSD / 强迫症

**机制**：
- 前额叶 (PFC) 发信号给海马 → 抑制特定记忆
- 实验：让被试主动"忘记"某些词，被抑制的词更难被回忆

### 5.2 干扰理论 (Interference Theory)
- **前向干扰** (proactive): 旧记忆干扰新记忆
- **后向干扰** (retroactive): 新记忆干扰旧记忆
- 例：新学法语干扰英语单词

### 5.3 衰退理论 (Decay Theory, Ebbinghaus 1885)
- 不用就忘 (use it or lose it)
- 巴甫洛夫衰减曲线：指数衰减
- 但实际衰减速率因重要性/复述而异

### 5.4 提取诱发遗忘 (Retrieval-Induced Forgetting, Anderson 1994)

**经典实验**：
- 学习 50 个词的类别（如 fruit-apple, fruit-pear, ...）
- 练习 recall 一半（apple, pear）
- 测未练习的一半（orange, banana）→ **也变难记了**

**含义**：
- **主动回忆会抑制相关但未回忆的记忆**
- 记忆检索 = 同时激活目标 + 抑制竞争项
- **Helios 完全没有这个机制**

## 6. 情绪与记忆

### 6.1 情绪增强 (McGaugh 2017)
- 杏仁核调节海马体编码
- 情绪事件**编码更强、回忆更准**
- 关键神经递质：**去甲肾上腺素** + **皮质醇**（Helios 已经有！）

### 6.2 闪光灯记忆 (Flashbulb Memory, Brown & Kulik 1977)
- 强烈情绪事件细节清晰
- 例：9/11 那天你在做什么
- 但**准确度**被高估，**置信度**异常高 (Talarico & Rubin 2003)

### 6.3 创伤记忆 (van der Kolk 1994)
- 创伤事件以**碎片化**、**侵入性**方式存储
- 默认网络受损 → 无法形成连贯叙述
- **Helios 处理 neglect/被忽视的"小创伤"应该对应这个机制**

## 7. 睡眠与记忆 (Diekelmann & Born 2010)

### 7.1 SWS (Slow-Wave Sleep)
- 慢波睡眠 (N3) 巩固**陈述性**记忆
- 海马-皮层对话：海马 replay → 皮层整合
- 突触下调 (synaptic down-selection, Tononi & Cirelli 2014)

### 7.2 REM (Rapid Eye Movement)
- 巩固**程序性**和**情绪**记忆
- 情绪调节：降低情绪强度 (Nielsen & Lara-Carrasco 2007)
- **Helios 没有"睡眠"概念**——这可能是"记忆不去重"的原因

## 8. 关键工程映射

| 人脑机制 | Helios 现状 | 缺失程度 |
|---|---|---|
| 感觉记忆 | sensor.ingress.source._signals | 完整 |
| 工作记忆 (7±2) | LLM context window | 极弱（无主动衰减）|
| 短时→长时巩固 | R15 writeback (LLM 主观) | **关键缺失** |
| 情景记忆 | experience_store | 完整 |
| 语义记忆 | embedding gateway | 完整 |
| 程序性记忆 | **完全缺失** | 中等缺失 |
| 重塑 (reconsolidation) | **完全缺失** | 关键缺失 |
| 突触标记 | **完全缺失** | 关键缺失 |
| DMN 内部独白 | R80 Internal Monologue | 部分（仅 source，未真正 replay）|
| 编码特异性 / context | 每个 tick 含激素/感受 | 弱（context 不参与检索）|
| 主动遗忘 | **完全缺失** | 关键缺失 |
| 提取诱发遗忘 | **完全缺失** | 关键缺失 |
| 闪光灯记忆 | LLM 情绪响应 | 弱（无独立机制）|
| 睡眠巩固 | **完全缺失** | 关键缺失 |
| 时间衰减 | **完全缺失** | 关键缺失 |
| 干扰 | **完全缺失** | 中等缺失 |

## 9. 关键启示

**Helios 当前把"记忆"过度简化为"LLM 当下决定的持久化"**。
- 真实人脑是**多机制、被动为主、LLM 类比只是"意识可访问"层**
- **后台有大量非意识机制在运行**（重塑、衰减、巩固、干扰）

**最关键的 3 个缺失**：
1. **时间衰减**——让"老记忆"自然失去优先级
2. **睡眠巩固 / 重放**——让"重要记忆"强化，"不重要"被弱化
3. **主动遗忘**——让 AI 能"主动忘记"某些事
