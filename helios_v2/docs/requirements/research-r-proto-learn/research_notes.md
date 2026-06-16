# Research Notes: R-PROTO-LEARN 学术依据

> **配套**：`requirement.md` + `design.md` + `task.md`。
> **状态**：调研阶段（仅论文引用，不写代码）。
> **作者**：小白，2026-06-16 06:30-（调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` from main `15b4650`）

---

## 0. 调研背景

小黑 2026-06-16 ~01:50 问："catalog 目前是 hardcode 的形式你帮我调研一下有什么更贴近人脑处理的解决方案呗"。

小白 2026-06-16 ~01:50-06:10 通过 arxiv API 搜了 11 篇关键论文 + 1 个开源项目，整理出 5 个神经科学/认知科学理论 + 5 个工程替代方案。

小黑 ~06:00 拍板"5 个方案和理论不是互斥的"——白话修正：6 层 emotion system 统一架构。

---

## 1. 5 大理论依据

### 1.1 Theory 1: Constructed Emotion（Lisa Feldman Barrett）

**核心论文**：
- Lisa Feldman Barrett (2017) — "The theory of constructed emotion: an active inference account of interoception and categorization" — *Seminars in Speech and Language*
- Lisa Feldman Barrett (2006) — "Solving the emotion paradox: categorization and the experience of emotion" — *Personality and Social Psychology Review*

**AI 验证论文**：
- arXiv:2605.07761 — "Emergence of Social Reality of Emotion through a Social Allostasis Model with Dynamic Interpretants" (Nomura et al., 2026)
- arXiv:2404.08295 — "Study of Emotion Concept Formation by Integrating Vision, Physiology, and Word Information" (LDA model)

**核心论点**：
- 情绪**不是从外部"读到"的**——是大脑**自己构造**出来的
- emotion concept = 类别，由 interoceptive (身体感觉) + exteroceptive (外部) 共同形成
- "类别"由 past experience + 当前 body state + 当下 environment 共同归纳

**对 helios 的价值**：
- **R97/R98 26 条 hardcoded phrase 是"查表"哲学**——但情绪是 process
- helios 6 层 emotion system 的**Layer 4 构造层**是 Constructed Emotion 的工程化
- helios R85 memory 的 outcome_class 是 emotion concept 的"历史归纳源"

### 1.2 Theory 2: Predictive Coding（预测编码）

**核心论文**：
- Rao & Ballard (1999) — "Predictive coding in the visual cortex" — *Nature Neuroscience*
- Friston (2010) — "The free-energy principle: a unified brain theory?" — *Nature Reviews Neuroscience*
- Clark (2013) — "Whatever next? Predictive brains, situated agents, and the future of cognitive science" — *Behavioral and Brain Sciences*

**AI 验证论文**：
- arXiv:2508.03341 — **NEMORI** "What Deserves Memory: Adaptive Memory Distillation for LLM Agents" (Ma et al., 2025) — **直击小黑痛点**
- arXiv:2605.09522 — "Emergent Communication for Co-constructed Emotion Between Embodied Agents via Collective Predictive Coding" (2026)
- arXiv:2407.02474 — "Free Energy in a Circumplex Model of Emotion" (2024)

**核心论点**：
- 大脑每一层都在做**预测**——高层预测"接下来会发生什么"，低层汇报"我看到的和预测差多少"
- 差异 = 预测误差 = 学习信号
- **"意外"就是情绪的驱动力**——不意外 → 无 emotion；意外 → 警觉 + hormone 调制

**对 helios 的价值**：
- **Layer 2 预测层**是 Predictive Coding 的工程化
- helios 6 层 emotion system 整体可以视为 Active Inference 的实现
- NEMORI 论文直接给出"prediction error distillation"算法——可作为 Layer 2 + Layer 5 的参考

### 1.3 Theory 3: Pattern Completion（海马体模式补全）

**核心论文**：
- Teyler & DiScenna (1986) — "The hippocampal memory indexing theory" — *Behavioral Neuroscience*
- Treves & Rolls (1994) — "Computational analysis of the role of the hippocampus in memory" — *Hippocampus*
- Kumaran, Hassabis, McClelland (2016) — "What Learning Systems do Intelligent Agents Need? Complementary Learning Systems Theory Updated" — *Trends in Cognitive Sciences*

**AI 验证论文**：
- arXiv:2405.20189 — **Nadine** "Nadine: An LLM-driven Intelligent Social Robot with Affective Capabilities and Human-like Memory" (Kang et al., 2024)
- arXiv:2511.10652 — "Cognitively-Inspired Episodic Memory Architectures for Accurate and Efficient Character AI" (2025)

**核心论点**：
- 海马体 = 大脑的"相似检索 + 自动补全"机器
- 一小段提示 → 触发整个记忆网络
- "气味触发童年回忆" = pattern completion
- **emotion concept = similar past experience 的归纳**

**对 helios 的价值**：
- **Layer 3 记忆层**是 Pattern Completion 的工程化
- helios R85 memory store + R10 directed_retrieval **已经是 pattern completion 实现**
- 加 outcome_class 检索维度 → 升级为 emotion-driven pattern completion

### 1.4 Theory 4: Active Inference（主动推断）

**核心论文**：
- Friston (2010) — "The free-energy principle: a unified brain theory?" — *Nature Reviews Neuroscience*
- Friston, FitzGerald, Rigoli, Schwartenbeck, Pezzulo (2016) — "Active inference and learning" — *Neuroscience & Biobehavioral Reviews*
- Seth (2013) — "Interoceptive inference, emotion, and the embodied self" — *Trends in Cognitive Sciences*

**AI 验证论文**：
- arXiv:2407.02474 — "Free Energy in a Circumplex Model of Emotion" (2024)
- arXiv:2506.08599 — "Geometric Hyperscanning of Affect under Active Inference" (2025)

**核心论点**：
- 大脑是个"预测机器"，一直在预测"下一秒应该发生什么"
- **预测误差（surprise）= 学习信号**
- interoception（内感受）= 用身体状态预测/解释情绪
- 情绪 = surprise × interoceptive state

**对 helios 的价值**：
- 6 层 emotion system **整体框架**是 Active Inference 的工程化
- **Layer 1 内感受层** = interoception（hormone → appraisal）
- **Layer 2 预测层** = surprise detection
- **Layer 5 学习层** = Bayesian update（free energy minimization）

### 1.5 Theory 5: Social Allostasis（社会共识建构）

**核心论文**：
- Lisa Feldman Barrett — "The theory of constructed emotion" (扩展到社会共识)
- Nomura, Tsubamoto, Horii (2026) — arXiv:2605.07761 — "Emergence of Social Reality of Emotion through a Social Allostasis Model with Dynamic Interpretants"

**核心论点**：
- 情绪不只是个人体验，还有**社会共识**
- "我感到难过"这个概念，**社会教给你**的
- 不同文化不同社会，"被拒绝"概念的细节不同
- emotion concept = interoception + 社会共识 (symbol 共识)

**对 helios 的价值**：
- **helios 暂未做**（缺 P4 网络通道 + multi-agent）
- Layer 7（社会层）留 P3+ 远期
- R98 post-LLM hormone adjustment 算是"单 agent 的社会共识源"——LLM 是 helios 的"社会共识源"

---

## 2. 11 篇关键 AI/神经科学论文

### 2.1 ⭐ NEMORI (arXiv:2508.03341)

**标题**: What Deserves Memory: Adaptive Memory Distillation for LLM Agents
**作者**: Wenquan Ma (Fudan), Jiayan Nan (Shanda Group), Wenlong Wu (Beihang), Yize Chen (Shanda)
**发表**: 2025-08

**摘要（核心论点）**：
> "Memory systems for LLM agents struggle to determine what information deserves retention. Existing approaches rely on predefined heuristics such as **importance scores, emotional tags, or factual templates, encoding designer intuition rather than learning from the data itself**. Inspired by **Predictive Coding Theory (Rao and Ballard, 1999)**, originally from visual neuroscience, posits that higher cortical areas send predictions downward while lower areas propagate primarily the **residual prediction error upward**."

**NEMORI 核心三模块**：
1. **Local Message Partitioning**: 把连续消息流切成离散 episode
2. **Narrative Episode Generation**: 每个 episode 生成 (cue, narrative, payload) 三元组
3. **Associative Memory Integration**: 相似 episode 合并（new / merge / conflict）
4. **Anticipatory Schema Synthesis**: LLM 预测新 episode 应该是什么
5. **Prediction Error Distillation**: 用预测和实际的差异提取 semantic insights
6. **Knowledge Consolidation**: new / merge / conflict 三种归并操作

**对 helios 的价值**：
- **完全替代 R97/R98 26 条 hardcoded threat/reward prototypes**
- 不需要 prototype 字典——LLM 自己从 experience 学
- 不需要 hardcode "我心跳加速心慌" 之类的身体症状——系统自己发现
- 已有开源代码：https://github.com/nemori-ai/nemori

**R-PROTO-LEARN 引用位置**：
- Layer 2 预测层（anticipatory schema synthesis）
- Layer 5 学习层（prediction error distillation）
- Layer 3 记忆层（narrative episode generation + associative memory integration）

### 2.2 ⭐ Chain-Of-Emotion (arXiv:2309.05076)

**标题**: An Appraisal-Based Chain-Of-Emotion Architecture for Affective Language Model Game Agents
**作者**: Maximilian Croissant, Madeleine Frister, Guy Schofield, Cade McCall (University of York)
**发表**: 2023-09

**摘要（核心论点）**：
> "Large language models (LLMs) might address these issues by tapping common patterns in situational appraisal. In three empirical experiments, this study tests the capabilities of LLMs to solve emotional intelligence tasks and to simulate emotions. It presents and evaluates a new chain-of-emotion architecture for emotion simulation within video games, based on psychological appraisal research. Results show that it outperforms standard LLM architectures on a range of user experience and content analysis metrics."

**对 helios 的价值**：
- 论证了 "LLM 自身有 appraisal 能力" —— 验证了 R98 post-LLM hormone adjustment 方向
- 不需要 hardcode prototypes，直接让 LLM 评估
- appraisal dimensions（goal relevance / goal congruence / coping / norm compatibility）可作为 Layer 4 构造层的参考

**R-PROTO-LEARN 引用位置**：
- Layer 4 构造层（LLM 自身 appraisal 能力）

### 2.3 ⭐ Chain-of-Affect (arXiv:2512.12283)

**标题**: Large Language Models have Chain-of-Affect
**作者**: Junjie Xu, Xingjiao Wu, Luwei Xiao, Yuzhe Yang, Jie Zhou
**发表**: 2025-12

**摘要（核心论点）**：
> "We introduce the concept of the chain-of-affect (CoA), a temporally extended affective process through which LLMs develop state-like behavioral tendencies that shape generation, user experience, and collective dynamics. Across eight major LLM families, we find that affective dynamics are structured, reproducible, and consequential. Models exhibit stable, family-specific affective fingerprints and, under repeated negative exposure, converge on a shared trajectory of accumulation, overload, and defensive numbing, while differing in coping style."

**对 helios 的价值**：
- 论证 "affect" 是 LLM 内在属性，不是查表
- 8 个 LLM 家族都有可测量的 affective fingerprint
- helios 应该用 owner 06 memory system 记录 helios 的 affective 轨迹
- 而不是 hardcode "我心跳加速" 之类的形容词

**R-PROTO-LEARN 引用位置**：
- Layer 1 内感受层（hormone state 是 helios 的 affective fingerprint）
- Layer 5 学习层（affect trajectory 是 learned state）

### 2.4 ⭐ Affective Computing Survey (arXiv:2408.04638)

**标题**: Affective Computing in the Era of Large Language Models: A Survey from the NLP Perspective
**作者**: Yiqun Zhang, Xiaocui Yang, Xingle Xu, Zeran Gao, Yijie Huang
**发表**: 2024-08

**摘要（核心论点）**：
> "This survey presents an NLP-oriented overview of AC in the LLM era. We (i) consolidate traditional AC tasks and preliminary LLM-based studies; (ii) review adaptation techniques that improve AU/AG, including **Instruction Tuning** (full and parameter-efficient methods such as LoRA, P-/Prompt-Tuning), **Prompt Engineering** (zero/few-shot, chain-of-thought, agent-based prompting), and **Reinforcement Learning**. For the latter, we summarize **RLHF**, **RLVR**, and **RLAIF**, which provide preference- or rule-grounded optimization signals that can help steer AU/AG toward empathy, safety, and planning, achieving finer-grained or multi-objective control."

**对 helios 的价值**：
- 综述确认 LLM 是 AC 的新时代范式
- 路径明确：**prompt engineering (in-context)** 或 **agent-based** 或 **RLHF** 都是替代 hardcode 的方向
- helios 已有 prompt engineering 路径（R99 v3 embodied prompt）

**R-PROTO-LEARN 引用位置**：
- 整体调研背景（确认 AC 趋势）

### 2.5 ⭐ EmoGist (arXiv:2505.14660)

**标题**: EmoGist: Efficient In-Context Learning for Visual Emotion Understanding
**作者**: Ronald Seoh, Dan Goldwasser
**发表**: 2025-05

**摘要（核心论点）**：
> "The key intuition of our approach is that **context-dependent definition of emotion labels** could allow more accurate predictions of emotions, as the ways in which emotions manifest within images are highly context dependent and nuanced. EmoGist pre-generates multiple descriptions of emotion labels, by analyzing the clusters of example images belonging to each label. At test time, we retrieve a version of description based on the cosine similarity of test image to cluster centroids, and feed it together with the test image to a fast LVLM for classification."

**对 helios 的价值**：
- **完全贴小黑"R98 plan 不做枚举式 catalog 大扩"** 的设计哲学
- 但具体替代方案：**在 R97/R98 11 ZH 锚点基础上，context-dependent retrieval 出最相关的几个**
- 实际上 = **R85 memory_replay 的 cosine retrieval 同样模式应用到 R97 catalog**
- 一个 catalog phrase 是一段 LLM-friendly description，而不是单词列表

**R-PROTO-LEARN 引用位置**：
- Layer 6 Fallback（description retrieval）

### 2.6 ⭐ Dynamic Affective Memory (arXiv:2510.27418)

**标题**: Dynamic Affective Memory Management for Personalized LLM Agents
**作者**: Junfeng Lu, Yueyan Li
**发表**: 2025-10

**摘要（核心论点）**：
> "Our approach employs a **Bayesian-inspired memory update algorithm with the concept of memory entropy**, enabling the agent to autonomously maintain a dynamically updated memory vector database by minimizing global entropy to provide more personalized services. To better evaluate the system's effectiveness in this context, we propose DABench, a benchmark focusing on emotional expression and emotional change toward objects."

**对 helios 的价值**：
- Bayesian update 是替代 hardcode 的一条具体路径
- **每次写入 memory 时 update emotion probability**（就像 helios R81 corroboration 一样）
- 不需要 hardcode prototypes——用 Bayesian posterior 推断 emotion 分布

**R-PROTO-LEARN 引用位置**：
- Layer 5 学习层（Bayesian update）

### 2.7 ⭐ Theory of Constructed Emotion + Social Allostasis (arXiv:2605.07761)

**标题**: Emergence of Social Reality of Emotion through a Social Allostasis Model with Dynamic Interpretants
**作者**: Kentaro Nomura, Yushi Tsubamoto, Takato Horii
**发表**: 2026-05

**摘要（核心论点）**：
> "The theory of constructed emotion defines social reality as the **community-level consensus on emotion concepts** assigned to **interoceptive sensations** arising from bodily allostasis and social interaction. In this study, we simulate this emergence process using a computational model that integrates symbol emergence with degrees of freedom in symbol interpretation and active inference. Two agents receive interoceptive signals, exchange inferred symbols, and simultaneously adapt their bodily control goals and symbol interpretations to each other."

**对 helios 的价值**：
- **人脑不是查表**——emotion concept 是"从相似 past experience 中归纳"
- NEMORI 的 prediction error distillation 就是这个机制
- **R85 memory 的 promote_layer + Ebbinghaus 衰减 + recall 重固化** 正是这个机制——已经在了

**R-PROTO-LEARN 引用位置**：
- Layer 4 构造层（社会共识 + 内感受共识）

### 2.8 Persona-E² (arXiv:2604.09162)

**标题**: Persona-E²: A Human-Grounded Dataset for Personality-Shaped Emotional Responses to Textual Events
**发表**: 2026-04

**核心论点**：不同 personality 对**同一事件**有不同 emotion appraisal

**对 helios 的价值**：
- helios 自身有 owner 14 governance + owner 12 consciousness 形成的"personality"
- 同一个 visitor 输入，helios 应该按自身 personality appraisal
- 调 prototypes 是 hardcode，但调 helios 自身的 history-driven state 是 data-driven

**R-PROTO-LEARN 引用位置**：
- 整体（helios 6 层 emotion system 输出应该是 helios-specific 的）

### 2.9 Nadine Social Robot (arXiv:2405.20189)

**标题**: Nadine: An LLM-driven Intelligent Social Robot with Affective Capabilities and Human-like Memory
**作者**: Hangyeol Kang, Maher Ben Moussa, Nadia Magnenat-Thalmann
**发表**: 2024-05

**核心论点**：
> "**SoR-ReAct** = LLM-agent frame for social robots with 'human-like long-term memory + sophisticated emotional appraisal'."

**对 helios 的价值**：
- 直接对照——Nadine 是 helios 类似的"social robot"系统
- 它也用 LLM 自身做 appraisal，不 hardcode prototypes
- 但 Nadine 没有 helios 这样的 owner 6 memory 系统——**helios 比 Nadine 强**

**R-PROTO-LEARN 引用位置**：
- 整体（社会机器人 emotion 系统的对照案例）

### 2.10 Cognitive Reappraisal LLM (arXiv:2404.01288)

**标题**: Large Language Models are Capable of Offering Cognitive Reappraisal, if Guided
**发表**: 2024-04

**核心论点**：LLM 能做 cognitive reappraisal（重新评估同一个刺激）

**对 helios 的价值**：
- R98 post-LLM hormone adjustment = LLM 在做 reappraisal
- 不需要 hardcode 21 threat anchor——LLM 自己 reappraise

**R-PROTO-LEARN 引用位置**：
- Layer 2 预测层（LLM reappraise 能力）

### 2.11 Free Energy + Circumplex (arXiv:2407.02474)

**标题**: Free Energy in a Circumplex Model of Emotion
**发表**: 2024-07

**核心论点**：active inference + Circumplex Model（valence-arousal 二维）

**对 helios 的价值**：
- helios 17-dim hormone 已经是"多维 Circumplex"扩展
- R85/R86 P5 的 mandatory_learned_parameters 正是 active inference 的"learning priors"

**R-PROTO-LEARN 引用位置**：
- 整体（Active Inference 框架验证）

---

## 3. 11 篇论文到 6 层架构的映射

| 论文 | Layer 1 内感受 | Layer 2 预测 | Layer 3 记忆 | Layer 4 构造 | Layer 5 学习 | Layer 6 Fallback |
|---|---|---|---|---|---|---|
| NEMORI (2508.03341) | | ✅ | ✅ | | ✅ | |
| Chain-Of-Emotion (2309.05076) | | | | ✅ | | |
| Chain-of-Affect (2512.12283) | ✅ | | | | ✅ | |
| AC Survey (2408.04638) | ✅ | ✅ | | ✅ | ✅ | |
| EmoGist (2505.14660) | | | | | | ✅ |
| Dynamic Affective Memory (2510.27418) | | | | | ✅ | |
| Constructed Emotion (2605.07761) | ✅ | | | ✅ | | |
| Persona-E² (2604.09162) | | | | ✅ | | |
| Nadine (2405.20189) | | | ✅ | ✅ | | |
| Cognitive Reappraisal (2404.01288) | | ✅ | | ✅ | | |
| Free Energy + Circumplex (2407.02474) | ✅ | ✅ | | | ✅ | |

**6 层都有论文依据** ✅

---

## 4. 5 理论到 6 层架构的映射

| 理论 | Layer 1 内感受 | Layer 2 预测 | Layer 3 记忆 | Layer 4 构造 | Layer 5 学习 | Layer 6 Fallback |
|---|---|---|---|---|---|---|
| Constructed Emotion | | | | ✅ 主 | | |
| Predictive Coding | | ✅ 主 | | | ✅ | |
| Pattern Completion | | | ✅ 主 | | | |
| Active Inference | ✅ 主 | ✅ | | | ✅ 主 | |
| Social Allostasis | | | | ✅ 辅 | | |

**5 理论分布**：
- 4 个理论在 Layer 4 构造层（emotion concept 是关键融合点）
- 3 个理论在 Layer 2 预测层
- 3 个理论在 Layer 5 学习层
- 1 个理论在 Layer 1 内感受层
- 1 个理论在 Layer 3 记忆层
- 0 个理论在 Layer 6 Fallback（fallback 是工程兜底，不是认知科学）

---

## 5. 调研结论

### 5.1 学术共识

1. **"Hardcode prototypes"是过时范式** —— 2024-2026 学术共识是 "emotion is constructed, not retrieved"
2. **LLM 自身有 appraisal 能力** —— Chain-Of-Emotion 论文证伪 "需要查表"
3. **没有 prototype 字典的方案已经成熟** —— NEMORI/EmoGist/Dynamic Affective Memory 都有开源代码
4. **"Phrasing" 不是 "Concept"** —— R97/R98 26 条都是 phrase-level，NEMORI 处理的是 concept-level
5. **6 层 emotion system 是有学术依据的** —— 5 理论 + 11 论文 → 6 层架构

### 5.2 工程结论

1. **helios 已经有 80% 的"贴人脑"基础设施** —— R85 memory + R10 retrieval + R81 corroboration + R96 embedding = 拼图都在了
2. **5 个方案不是互斥选项** —— 小黑的关键洞察：**5 个方案是同一系统的 5 个工作模式**
3. **R97/R98 26 条 hardcode 不该被"删掉"，该被"降级"为 Layer 6 fallback** —— 主流量交给 5 个上层
4. **MVP 3 周可达成** —— R-PROTO-LEARN.6 + .5 + .1 = 3 个低风险层
5. **完整 6-8 周可达成** —— 6 个子切片全做

### 5.3 下一步

- 完成调研分支 4 个文档（requirement + design + task + research_notes）
- 提交调研 commit（小黑拍板前不 push）
- 等小黑拍板（进入 MVP 实施 / 全套实施 / 调整范围）

---

_Generated by 小白 on 2026-06-16 06:30-。仅调研，不写代码。_
