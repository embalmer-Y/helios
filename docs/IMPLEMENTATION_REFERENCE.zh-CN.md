# Helios 实现映射参考

> Status: Active
> Audience: 架构维护者、研究型开发者、后续模块扩展者
> Source of truth: 代码实现为准；本文件负责把当前实现与理论来源、研究文档和验证线索关联起来

## 1. 文档角色

本文件补上 Active 架构说明与 Foundational 研究笔记之间缺失的一层：

- `ARCHITECTURE.*` 说明系统如何分层
- `DESIGN_PHILOSOPHY.*` 说明系统如何运行
- 本文件说明哪些模块实现或参考了哪些理论、论文与研究结果

当理论说明与代码行为不一致时，以代码和 Active 文档为准。

## 2. 阅读方式

推荐按以下顺序使用本文件：

1. 先定位模块所在层。
2. 再看该模块引用的理论依据。
3. 再看实现证据与关键类/函数。
4. 最后看相关测试，判断该理论是否已经落到可验证行为。

## 3. 模块级映射总表

| 模块 | 运行角色 | 理论/论文基础 | 研究文档锚点 | 实现状态 | 相关验证 |
| --- | --- | --- | --- | --- | --- |
| `allostasis.py` | 异稳态调节与负荷累积 | Sterling & Eyer (1988), McEwen (1998), Schulkin (2003) | `fep_formalization.md`, `friston_panksepp_synthesis.md` | 已实现 | `tests/test_drive_regulation_scoring.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `daisy_emotion.py` | 7 系统情感动力学引擎 | Panksepp (1998), Russell (1980), Kuppens (2010), Solomon & Corbit (1974), Davidson (2000), Barrett (2017) | `panksepp_helio_mapping.md` | 已实现 | `tests/test_habituation_integration.py`, `tests/test_drive_integration.py` |
| `mood_tracker.py` | 心境层与情绪惯性 | Gebhard (2005) ALMA, Kuppens (2010), Russell (1980) | `panksepp_helio_mapping.md` | 已实现 | `tests/test_helios_state_pipeline_pbt.py` |
| `personality.py` | Big Five 到原始情感系统映射 | McCrae & Costa (1997), Davis & Panksepp (2011), Roberts et al. (2006) | `panksepp_helio_mapping.md` | 已实现 | `tests/test_habituation_pbt.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `neurochem.py` | 神经调质背景与动力学 | 多巴胺/阿片/催产素/皮质醇调制框架 | `neurochem_model.md` | 已实现 | `tests/test_drive_integration.py`, `tests/test_icri_temperature_pbt.py` |
| `cognition/phi.py` | ICRI / 统一 Phi 聚合 | Tononi (2004), Dehaene (2006), Seth (2011) | `dmn_thinking_model.md`, `fep_formalization.md` | 已实现 | `tests/test_lifecycle_integration.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `cognition/drives.py` | 五维驱动缺口估计 | Friston FEP / Active Inference | `fep_formalization.md`, `friston_panksepp_synthesis.md` | 已实现 | `tests/test_drive_integration.py`, `tests/test_drive_regulation_scoring.py` |
| `cognition/appraisal.py` | SEC 特征到情感系统映射 | Stimulus Evaluation Checks, appraisal tradition | `anthropic_emotion_concepts.txt` | 已实现 | `tests/test_llm_sec_evaluator.py` |
| `cognition/thinking_integration.py` | 内生思维与 DMN 条件 | DMN / replay / endogenous thinking | `dmn_thinking_model.md` | 已实现 | `tests/test_lifecycle_integration.py` |
| `memory/memory_system.py` | 工作、情景、语义、自传四类记忆 | 多存储记忆模型, Baddeley working memory | `DESIGN_PHILOSOPHY.*` | 已实现 | `tests/test_memory_compression.py`, `tests/test_conversation_history.py` |
| `memory/memory_compressor.py` | 老旧自传记忆摘要压缩 | 自传记忆摘要化与 consolidation after low-phi rest | `DESIGN_PHILOSOPHY.*` | 已实现 | `tests/test_memory_compression.py`, `tests/test_consolidation_scheduling.py` |
| `helios_io/response_pipeline.py` | 被动回复与对话语境生成 | SEC 驱动回应决策, ICRI 温度调制 | `anthropic_emotion_paper.txt`, `DESIGN_PHILOSOPHY.*` | 已实现 | `tests/test_conversation_history.py`, `tests/test_llm_sec_evaluator.py`, `tests/test_channel_gateway.py` |
| `regulation/regulation.py` | 记忆驱动的行为调节 | affect regulation as behavior selection, reinforcement by outcome | `friston_panksepp_synthesis.md`, `DESIGN_PHILOSOPHY.*` | 已实现 | `tests/test_drive_regulation_scoring.py`, `tests/test_behavior_executor_pbt.py` |
| `helios_main.py` | 运行编排、tick 生命周期、跨层闭环 | FEP 驱动、Panksepp affect、memory-cognition-regulation loop | `ARCHITECTURE.*`, `DESIGN_PHILOSOPHY.*` | 已实现 | `tests/test_lifecycle_integration.py`, `tests/test_helios_state_pipeline_pbt.py` |

## 4. 关键模块细化

### 4.1 `allostasis.py`

- 模块职责：根据预测需求和累积负荷动态调整 setpoint，而不是维持固定静态基线。
- 理论依据：Allostasis 与 Allostatic Load。
- 代码证据：模块头部 docstring 明确引用 Sterling & Eyer, McEwen, Schulkin；`AllostaticState.update_demand()`、`accumulate_load()` 与 `update_setpoint()` 实现了“预测需求 + 负荷惩罚 + 恢复”逻辑。
- 关键类/函数：
  - `AllostasisConfig`: 把需求平滑、负荷阈值和恢复系数参数化。
  - `AllostaticState.update_demand()`: 近期峰值驱动 predicted demand。
  - `AllostaticState.accumulate_load()`: 偏离基线会累积 allostatic load。
  - `AllostaticState.update_setpoint()`: setpoint 随预测需求与疲劳负荷动态漂移。
- 设计含义：该模块为后续 affect、drive 与 regulation 提供“为什么当前需要上调/下调”的中间变量。

### 4.2 `daisy_emotion.py`

- 模块职责：实现 7 维 Panksepp 情感系统的共激活、时序动力学与对向过程。
- 理论依据：
  - Panksepp 7 原始情感系统
  - Russell valence-arousal circumplex
  - Kuppens emotional inertia
  - Solomon & Corbit opponent-process
  - Davidson 情感时序风格
  - Barrett 共激活而非单标签胜者通吃
- 代码证据：模块头部 docstring 与 `CHRONOMETRY`, `OPPONENT_PAIRS`, `VALENCE_BIAS`, `AROUSAL_BIAS`, `BASELINE` 常量；`AffectiveChronometer` 和 `OpponentRegulator` 明确体现两个关键理论构件。
- 关键类/函数：
  - `AffectState`: 把 7 系统激活压缩为当前 affect snapshot。
  - `AffectiveChronometer.tick()`: 用 rise/peak/decay 参数模拟系统时间过程。
  - `OpponentRegulator`: 用 a-process / b-process 实现回弹与习惯化基础。
- 设计含义：Helios 的情感底盘不是标签分类器，而是连续动力系统。

### 4.3 `mood_tracker.py`

- 模块职责：把短时情绪累积成慢变量心境，并反向调制新事件的感知偏置。
- 理论依据：ALMA 三层模型、Emotional Inertia、Russell 二维环状模型。
- 代码证据：模块头部 docstring；`MoodConfig.beta_valence` 与 `beta_arousal` 明确体现“心境比情绪慢一个数量级”；`MoodState._update_label()` 用效价-唤醒标签命名。
- 关键类/函数：
  - `MoodTracker.update()`: EMA 累积情绪进入心境。
  - `MoodTracker.modulate_event()`: 当前心境反向影响事件感知。
  - `MoodTracker.modulate_triggers()`: 心境改变 Panksepp 触发放大/抑制。

### 4.4 `personality.py`

- 模块职责：以 Big Five 作为长期 trait 层，对 Panksepp 系统增益和时序参数进行慢变量调制，并允许人格缓慢演化。
- 理论依据：McCrae & Costa Big Five、Davis & Panksepp 人格与原始情感系统相关、Roberts 等人格长期变化研究。
- 代码证据：模块头部 docstring；`BIG5_TO_PANKSEPP` 和 `BIG5_TO_CHRONO` 明确把 trait 投影到情感系统增益与时序。
- 关键类/函数：
  - `PersonalityProfile._recompute()`: 从 Big Five 重新计算 neuro gains 和 chrono mods。
  - `PersonalityProfile.get_baseline()`: 为各系统提供 trait-modulated baseline。
  - `PersonalityProfile.adapt()`: 让长期情感经历缓慢塑造人格。

### 4.5 `cognition/phi.py`

- 模块职责：把感知整合、情感共振、DMN 深度、自我反思和全局点火聚合为 ICRI / Phi。
- 理论依据：IIT、Global Neuronal Workspace、Predictive Processing。
- 代码证据：模块头部理论基础说明；`UnifiedPhi` 的五个子成分字段和 `feed_*` 接口直接对应五类来源。
- 关键类/函数：
  - `UnifiedPhi.feed_emotional()`: 将多系统共振映射为 emotional coherence。
  - `UnifiedPhi.feed_dmn()`: 以 thought count、新颖性和模式多样性估计 temporal depth。
  - `UnifiedPhi.feed_ignition_from_panksepp()`: 用多系统活跃数近似全局广播。
- 设计含义：Helios 的“清醒度”是跨层整合结果，不是单一认知分数。

### 4.6 `cognition/drives.py`

- 模块职责：计算 curiosity、social、homeostatic、achievement、aesthetic 五维驱动缺口。
- 理论依据：自由能原理、主动推断、偏差最小化。
- 代码证据：模块头部说明 `D(t) = Σ w_i × deficit_i(t)`；`DriveVector.total` 权重化汇总；`DriveOracle._compute_curiosity()` 等函数分别对各缺口建模。
- 关键类/函数：
  - `DriveVector`: 驱动强度、dominant 与行动阈值。
  - `HeliosSnapshot`: 为驱动计算提供跨层轻量快照。
  - `DriveOracle.cycle()`: 汇总五维缺口并接收 neurochem 调制。

### 4.7 `cognition/appraisal.py`

- 模块职责：把 SEC 特征映射到 Panksepp 系统激活与效价/唤醒偏置。
- 理论依据：appraisal tradition / Stimulus Evaluation Checks。
- 代码证据：`SECFeatures` 数据结构直接暴露 novelty、pleasantness、goal relevance、coping potential、urgency 等维度；`AppraisalEngine.evaluate()` 按规则产出 SEEKING/FEAR/RAGE/PANIC/CARE/PLAY/LUST。
- 关键类/函数：
  - `SECFeatures`: 标准 appraisal 输入结构。
  - `AppraisalEngine.evaluate()`: 从 SEC 到 affective bias 的规则投影。
  - `EVENT_SEC_PROFILES`: 常见事件的 appraisal 原型库。

### 4.8 `cognition/thinking_integration.py`

- 模块职责：在满足 DMN 条件时触发内生思维，并把 thought activity 回写到 autobiographical memory 与 ICRI 管线。
- 理论依据：DMN、replay、emotion-biased endogenous thought。
- 代码证据：`EMOTION_THOUGHT_BIAS` 将 dominant affect 映射到 thought type；`should_generate()` 与 `_determine_dmn_activity()` 约束何时进入内生思维。
- 关键类/函数：
  - `ThinkingEngineIntegration.should_generate()`: ICRI 阈值 + DMN 激活 + 节流。
  - `ThinkingEngineIntegration.get_biased_types()`: 情感系统决定思维偏向。
  - `ThinkingEngineIntegration._record_thought()`: 将思维写回自传记忆。

### 4.9 `memory/memory_system.py`

- 模块职责：统一工作记忆、情景记忆、语义记忆、自传记忆以及 consolidation/retrieval 入口。
- 理论依据：多存储记忆模型、Baddeley 工作记忆、episodic-to-semantic consolidation。
- 代码证据：模块头部对四类记忆与 consolidator/retriever 的划分；`WorkingMemory` docstring 明确提到 Baddeley 与 Miller。
- 关键类/函数：
  - `MemoryItem`: 各类记忆的共用原子结构。
  - `WorkingMemory.recall()`: TTL 过期前可提升到 episodic memory。
  - `MemoryItem.recalc_importance()`: 用 valence/arousal/phi/access_count 计算重要性。

### 4.10 `memory/memory_compressor.py`

- 模块职责：把较老的自传记忆压缩为按日期归纳的 summary narrative。
- 理论依据：长期叙事压缩、 consolidation 后摘要化。
- 代码证据：`find_compressible_days()`、`compress_day()`、`execute_compression()` 体现“按天聚合、提取情绪弧线、保留关键事件”。
- 关键类/函数：
  - `CompressedSummary`: 压缩后保留 date、emotional arc、key events、source ids。
  - `MemoryCompressor._build_emotional_arc()`: 将一系列 moment 收束为情绪轨迹。

### 4.11 `helios_io/response_pipeline.py`

- 模块职责：基于消息、SEC 评估、记忆上下文和 ICRI 温度调制生成被动回复。
- 理论依据：SEC appraisal 结果进入回复决策；内部 consciousness intensity 调制语言风格。
- 代码证据：`should_reply()` 用 goal relevance + novelty 作为最小回复阈值；`generate_reply()` 把对话历史、记忆、自传、情感、人格和温度映射合并到提示词中。
- 关键类/函数：
  - `ResponsePipeline.should_reply()`: 基于 appraisal urgency 做最小回应门控。
  - `ResponsePipeline.generate_reply()`: 组装多源上下文并调用 LLM。
  - `ResponsePipeline.record_exchange()`: 将互动沉淀回 conversation history。

### 4.12 `regulation/regulation.py`

- 模块职责：不是固定表驱动，而是基于情感偏离与过往成功经验来选择调节行为。
- 理论依据：调节是情感稳态恢复的手段，行为通过结果反馈强化或削弱。
- 代码证据：模块头部 docstring 明确说明“检索过去什么行为缓解过该偏离”；`RegulationMemory` 保存动作效果；`BOOTSTRAP_REGULATION` 只是可被后续经验覆盖的初值。
- 关键类/函数：
  - `RegulationMemory.update()`: 用新结果更新动作效果估计。
  - `ActionCandidate.score`: 将 benefit 与 confidence 合成候选分数。
  - `RegulationEngine.tick()`: 基于当前 affect、时间与驱动状态选择动作。

### 4.13 `helios_main.py`

- 模块职责：作为运行编排器，固定 tick 生命周期，负责把 affect、memory、cognition、regulation 与 helios_io 接成闭环。
- 理论依据：不是单一论文模块，而是对 FEP、Panksepp affect、DMN thinking、memory consolidation、behavior feedback 的系统集成。
- 代码证据：主循环阶段顺序在 `DESIGN_PHILOSOPHY.*` 已与代码同步描述；系统初始化阶段装配 DAISY、Allostasis、Mood、Personality、MemorySystem、Phi、DriveOracle、ThinkingEngineIntegration、ResponsePipeline、RegulationEngine 与 limb bridge。

## 5. 分层到理论映射

| 层 | 主要模块 | 理论核心 |
| --- | --- | --- |
| 情感底盘 | `daisy_emotion.py`, `allostasis.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py` | Panksepp affect systems, allostasis, mood inertia, personality-trait modulation, neurochemical background |
| 认知层 | `cognition/phi.py`, `cognition/drives.py`, `cognition/appraisal.py`, `cognition/thinking_integration.py` | IIT, GNW, predictive processing, FEP, appraisal, DMN |
| 记忆层 | `memory/memory_system.py`, `memory/autobiographical.py`, `memory/memory_compressor.py` | multi-store memory, autobiographical continuity, consolidation/compression |
| 调节层 | `regulation/regulation.py`, `helios_io/limb.py`, `helios_io/limb_decision_bridge.py` | affect regulation, action selection, feedback learning |
| I/O 边界 | `helios_io/response_pipeline.py`, `helios_io/llm_sec_evaluator.py`, `helios_io/channel_gateway.py` | SEC-guided response, context-conditioned expression, channel mediation |
| 主循环编排 | `helios_main.py` | system integration across affect, memory, cognition, regulation, and execution |

## 6. 标注规范

后续新增或重写模块时，建议使用以下最小标注格式：

1. 模块头部 docstring 说明理论来源与实现边界。
2. 若类或关键函数直接对应理论构件，在 docstring 中明确点名。
3. 若引用研究文档，优先引用 `docs/foundations/` 内的整理文档，而不是在代码里长段粘贴论文内容。
4. 如果实现只是“受启发”而不是“直接实现”，应写清楚，避免过度归因。

## 7. 与其他文档的关系

- `ARCHITECTURE.*`: 看分层与所有权。
- `DESIGN_PHILOSOPHY.*`: 看 tick 流程与对象协作。
- `SOURCE_CATALOG.*`: 看原始资料、引用条目与待收集清单。
- Foundational 文档: 看理论原始背景与推导。