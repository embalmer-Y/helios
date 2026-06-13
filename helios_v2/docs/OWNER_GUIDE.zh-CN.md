# Helios v2 Owner 指南（中文）

> 状态：活文档（owner 参考）。最近同步：R87。测试基线：968 passed / 4 skipped（离线）。
> 角色：逐 owner 说明每个 Helios v2 owner 的职责、在循环中的作用、完成度、以及下一步开发/优化方向。
> 配套文档：
> - `ARCHITECTURE_PHILOSOPHY.zh-CN.md` — 终局目标、锁定的验收标准、P0→P7 阶段路线图。
> - `ARCHITECTURE_BOUNDARIES.md` — owner 边界、允许的依赖方向、迁移状态真相。
> - `BRAIN_ARCHITECTURE_COMPARISON.md` — 脑功能类比、gap 分析、owner-wave 路线图。
> - `PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md` — 着色的模块进度图。
> - `requirements/index.md` — 权威的逐需求 `Maturity` 列。
> - `OWNER_GUIDE.md` — 本文件的英文配套版，必须与本文件一起更新。

## 1. 目的与阅读方式

本文件是 Helios v2 唯一的逐 owner 参考。对每个 owner 它说明：

1. Owner —— 需求编号与所属 Python 包。
2. 职责 —— owner 拥有什么（以及它明确不拥有的相邻关切）。
3. 在循环中的作用 —— 它在 tick 中的位置、消费什么、产出什么。
4. 完成度 —— 真实实现成熟度，外加诚实的 caveat（例如"输入仍是 composition 注入的 shim"）。
5. 下一步 —— 具体的开发或优化方向，对齐阶段路线图。

它是面向实现的：完成度标签必须与 `requirements/index.md` 和进度图的着色一致。当某 owner 的成熟度、
边界或阶段归属发生变化时，本文件必须在同一次变更内更新，与进度图同等纪律。

### 1.1 完成度词表

| 标签 | 含义 |
| --- | --- |
| `deep_real` | LLM 驱动认知，或主运行期产出真实（非占位）的 `relatively_complete` owner。 |
| `baseline_real` | owner 执行真实首版行为、含 fail-fast 契约与测试，但其输入或下游后果有实质部分仍浅或仍是 composition 注入的 shim。 |
| `infra_done` | 支撑性基础设施/能力 owner 已交付并验证；非认知 owner。 |
| `docs_owner` | 文档 owner：交付物是一套维护中的文档，而非运行期代码。 |

### 1.2 当前最大的单一 caveat

P3 已退出（R64 正式评估 PASS；FG-1/FG-2.1/FG-2.2 全部成立），且 R69 使语义装配成为默认
装配（`assemble_runtime()` 无参数调用时 `semantic_memory_enabled == True`），故 `03-10` 在
默认装配下已去 shim。认知主链端到端由真实信号驱动。

**剩余主要距离已转移**：
1. `12-16` 外化链仍为 `baseline_real`，wave_C 执行收口（真实外部 channel 执行）尚未开始。
2. `14` 身份治理虽有 R68 跨 tick carry，但长程自我演化与跨重启持久化仍待 wave_B/P6 深化。
3. 真实外部（网络）信号源（QQ/语音/视觉）仍属 wave_C。
4. `P4` 工具/效应器生态与 `P5` 学习循环尚未开篇。

当今真正由真实信号驱动的 owner 是 `02`、`03-10`（默认去 shim）、`11`（LLM）、`18`，以及
全部基础设施 owner。自 R51 起存在第一条端到端 FG-2 因果链（真实 compute/runtime 压力 → `05`
体感 → `07` 工作空间竞争），自 R59 起存在第二条（外部 afferent → appraisal → affect）。

---

## 2. 认知链 owner（每 tick 循环）

它们每 tick 按 `CANONICAL_STAGE_ORDER` 执行（19 阶段；channel-bound 变体插入两个传输阶段共 21）。

### 2.1 `01` 运行时内核 — `helios_v2.runtime.kernel`
- 完成度：`deep_real`（基础设施级）。
- 职责：生命周期编排、fail-fast 启动门、有序阶段调度，以及（注入 recorder 时）逐阶段生命周期发射。不拥有任何认知决策。
- 在循环中的作用：驱动整个 tick；构造逐阶段 `RuntimeFrame`，把阶段结果聚合为 `RuntimeTickResult`。
- 下一步：随后续 owner 深化保持编排 owner-safe；无扩张计划。它的终局可信度只取决于它调度的那些 owner。

### 2.2 `02` 感觉接入 — `helios_v2.sensory`
- 完成度：`deep_real`。
- 职责：把外部与内部原始信号归一化为去重的 `Stimulus`/`StimulusBatch`；保留传输固有的 QoS 元数据。不拥有显著性、检索或路由。
- 在循环中的作用：第一个认知阶段；把 `RawSignal`（来自 source 或 channel 子系统）变成后续 owner 依赖的归一化批次。
- 完成度细节（R59 外部 afferent 诚实化）：`02` 本身的归一化是真实的,但喂给它的**外部刺激源**此前是常量 shim——默认/语义装配注册 `FirstVersionSensorySource`,每 tick 固定吐 `content="hello runtime"`,这是 composition 注入的常量冒充外部输入（违反 FG-1）,且因内容不变,真实 `03` novelty 在首次写库后塌成定值。R59 把外部 afferent 变成一等可注入能力:`RuntimeProfile.external_signal_source`（符合既有 `02 SensorySource` 协议）注入时取代常量 placeholder;它与 `channel_cli` 互斥（都占外部 afferent 位,同传 `CompositionError`）。首版 `SequenceExternalSignalSource` 只回放调用方提供的真实信号、耗尽后吐空批次,**绝不编造内容**（不发明/随机/循环编造文本,守 §4.3/§8 反 prompt theater）;空 afferent 是诚实缺席,经既有 no-fire/internal-only 收口。语义装配下,变化的外部刺激可测量地改变 `03` novelty 与 `04`/`05` 状态——这是继 R51 内感受链之后的**第二条 FG-2 因果链（外部 afferent）**。**默认 placeholder 现明确标注为非真实**:R59 不让默认变真实（需真实部署源,网络属 wave_C）,而是让真实源可注入、并停止把常量当真实 afferent 计入。opt-in、default-off。
- 下一步：保护边界真相；真实外部（网络）信号源随未来 channel driver（wave_C）经 R59 的 `external_signal_source` seam 接入。

### 2.3 `03` 快速显著性评估 — `helios_v2.appraisal`
- 完成度：`baseline_real`（语义记忆装配下已完全去 shim：五维全部真实——novelty 自 R35、uncertainty + social 自 R39、threat + reward 自 R40——外加聚合判断自 R41；`03` 的每个输出都真实,无常量）。
- 职责：每刺激的快速粗显著性（威胁/奖励/新颖/社会/不确定 + 聚合），经注入式 estimator。不拥有精细语义解释、记忆或路由。
- 在循环中的作用：紧接 sensory 塑造下游显著性；评估批次喂给调质与门控信号。
- 下一步（本 owner 的分阶段 P3 去 shim）：
  1. **R35 — 基于记忆的 novelty（已交付）。** `novelty` 维已是真实信号：`novelty = clamp(1 - max_similarity, 0, 1)`，其中 `max_similarity` 是 embed 后的刺激与任一已存经验 embedding 的最大余弦相似度（经 `34` embedding 网关 + `33` store 相似度检索）。`03` 定义窄协议 `MemorySimilaritySource` 并在 `MemoryGroundedDimensionEstimator` 中拥有 novelty 显著性映射；composition 注入 owner-neutral 的 `MemoryGroundedSimilaritySource`（返回原始余弦事实或 `None`），故 `03` 既不 import embedding 也不 import persistence owner。触发于语义记忆 opt-in（store + embedding 同时存在）；冷库/空刺激内容产出定义的最大 novelty `1.0`（空内容不调网关）；运行期 embedding/store 失败是 hard stop（无常量回退）。默认/recency-only 装配保持常量 novelty `0.6`。
     - **首版已知 caveat（跨语域比较）：** store 当前只存 `15` 的结果/连续性摘要，不存原始刺激文本，所以 R35 的 novelty 是把进来的*刺激输入*与过去的*结果摘要*（共享同一 embedding profile）比较。方向正确（共享内容会被余弦捕捉），但这是"输入 vs 摘要"的近似，不是严格的"输入 vs 输入"，不得过度宣称为精确的刺激新颖度。
  2. **方案 B — 同类可比的 novelty（后续切片）。** 持久化原始刺激文本流（`15`/`33` 扩展或专用刺激日志），使 novelty 在同一语域里"刺激 vs 历史刺激"比较，退休上面的跨语域 caveat。因为它触及回写/持久化 owner 而非 `03`，所以是独立需求。
  3. **R39 — uncertainty + social（已交付）。** `uncertainty` 由检索歧义度 grounded：`03` 读 top-2 余弦相似度（经 owner 定义的 `RetrievalAmbiguitySource`,由 composition 在同一 `34`/`33` 底座上注入），映射 `uncertainty = clamp(1 - (n1 - n2), 0, 1)`（归一化 top-2；无可比记忆 → `1.0`；单一强匹配 → 低；多个近似匹配 → 高）。这与 novelty 是不同的读法（熟悉但歧义 → 低 novelty、高 uncertainty）。`social` 由传输出处 grounded：`03` 读有界 `social_presence` 事实（经 owner 定义的 `SocialContextSource`；composition 拥有 channel→presence 分类,外部交互主体 channel → 高,内部 body/background → 0），映射 `social = clamp(social_floor + social_gain * presence, 0, 1)`。两个映射都在 owner 持有的 `GroundedDimensionEstimator` 里。**诚实标注：** uncertainty 是 `B_functional_inspiration`（检索歧义代理,非校准置信度）；social 是纯传输事实,不需 embedding 底座,本刀挂在语义 opt-in 下仅为单一开关（后续可让它在 channel-bound 装配独立生效）。快路保持确定性、网络无关、无 LLM。
  4. **R40 — threat/reward 原型 embedding（已交付）。** `threat`/`reward` 由刺激对 owner 持有的原型短语集（`THREAT_PROTOTYPES`/`REWARD_PROTOTYPES`）的最大余弦相似度打分，经 `34` 底座 embed：`03` 定义 `PrototypeSimilaritySource` 协议,映射 `dimension = clamp(gain * max(0, max_cosine), 0, 1)`（正相关——靠近语义锚点,与 novelty 的距离读法相反;`None`/空内容 → `0.0`）；composition 的 `EmbeddingPrototypeSimilaritySource` 把 owner 给的短语 embed 一次（缓存）并回原始余弦,故 `03` 既不 import embedding 也不 import persistence。原型集与映射归 `03`。无冷启动（原型装配期 embed 一次）。**诚实标注 `C_engineering_hypothesis`：** 原型短语集是人工、英语中心的占位锚点,**非**校准情感模型,不得过度宣称为真实威胁/奖励理解。它是后续替换的接口——P5 学习原型/系数、`06` 记忆-情感 grounding（按相似过往经验的好/坏结局打分）、或慢速 `11`-LLM 二级再评估（独立于快 `03` 路）。五维全部真实后,常量 aggregate estimator（第 5 项）是下一刀。
  5. **R41 — 聚合显著性（已交付）。** 聚合判断（`RapidSalienceVector.aggregate`）现在是五维真实维度的真实凸组合,经 owner 持有的 `WeightedAggregateEstimator`：`aggregate = clamp(sum(weight_k * dimension_k), 0, 1)`,首版权重和为 1.0（`threat 0.25, reward 0.25, novelty 0.20, uncertainty 0.15, social 0.15`）。单调、确定性、有界、无状态;无需注入事实源（纯维度函数）。这收口了 `03` owner 的 P3 去 shim——`03` 每个输出都真实。**诚实标注：** 权重是首版占位分配（工程选择,非校准重要性先验;P5 可学）;且聚合继承输入的 grounding 强度——threat/reward 还是 R40 的 `C_engineering_hypothesis` 锚点时,聚合的 threat/reward 贡献只有那么强（输入升级后自动变强）。默认/recency/离线保持常量聚合 `0.4`。后续：P5 学习权重、模型辅助/非线性或慢速 `11`-LLM 二级整体评估、情感/时近加权。
  6. **下游耦合（novelty→`04`→`05`/`09` 已交付）。** 真实 `03` 显著性已塑造 `04` 神经调质状态（R36），并经其塑造 `05` 体感（R38）与 `09` 门控（R37）；R40 起 reward→多巴胺、threat→皮质醇 两条通道也由真实信号驱动。仍待：真实 threat/reward 喂给 cortisol/inhibition 硬门控,以及它们落地后更丰富的 `05`/`06` 耦合；之后做情感加权或时近加权。**grounding-权力排序约束：** 当 threat/reward 还是 R40 的 `C_engineering_hypothesis` 占位锚点时,在它们被升级到更强 grounding（P5 / `06` 记忆-情感）之前,避免给它们高权力下游耦合（例如能否决 fire 的 cortisol/inhibition 硬门控）；弱锚点不应获得否决认知的权力。

### 2.4 `04` 神经调质系统 — `helios_v2.neuromodulation`
- 完成度：`baseline_real`（语义记忆装配下水平已由 appraisal 推导,并自 R43 起经双时间尺度动力学跨 tick 演化、跨重启续存）。
- 职责：独立建模的神经调质水平状态（DA/NE/5-HT/ACh/皮质醇/催产素/阿片 + 兴奋/抑制），含显式可学习参数类别。不拥有体感主观化或行动。
- 在循环中的作用：应当偏置门控阈值、检索、外化强度的调制层。
- 完成度细节：`36`（P3 第二刀去 shim）在语义记忆装配下把常量更新路径替换为 `04` owner 拥有的 `AppraisalDerivedNeuromodulatorUpdatePath`（遵循 owner 既有的 `NeuromodulatorUpdatePath` 协议；引擎与契约不变）。**R56 起该路径由 composition 回迁到 `04` owner 包 `helios_v2.neuromodulation`**：哪个显著性驱动哪个神经调质通道、强度多少，是 `04` 的本职认知策略，此前误置于 assembly-only 的 composition 胶水里（违反 §4.5 / §3.2），现已收回 owner，composition 只构造/注入/包裹它（行为字节级不变，纯回迁）。它先对 rapid-appraisal 批次按维度取最大聚合，再按 `clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)` 推导每个通道的**瞬时 drive**：多巴胺由 reward（外加弱 novelty）驱动、去甲肾上腺素由 novelty 与 uncertainty 驱动、皮质醇由 threat 驱动，其余通道回归各自 tonic 基线。`43`（P2/P3 铰链）在此之上加了**双时间尺度动力学**：语义装配下 update path 换成 owner 持有的 `DualTimescaleNeuromodulatorUpdatePath`（包裹上面的 drive path）,每通道 `next = clamp(prior + alpha_phasic*(drive-prior) + alpha_tonic*(baseline-prior))`（相位快、张力慢,`0 < alpha_tonic < alpha_phasic <= 1`,挂 `decay_speed_persistence` 类别,P5 可学）。瞬时 drive 与跨 tick carry/衰减现已同处 `04` owner 包。`NeuromodulatorUpdatePath`/`update_state` 加可选 `prior_levels`/`prior_state`（默认 None 字节级复刻无状态）;`NeuromodulatorRuntimeStage` 像 09/18 持有上一 tick 状态并提供 `seed_prior_state`。冷启动 prior=tonic baseline（一步,无伪造历史）;积分器有界;不稳定 alpha 构造期被拒。`04` 状态经 R42 检查点（快照升 v2 加 `neuromodulator_levels`）跨重启续存。默认、纯时近、离线装配保留无状态常量路径。**R80（四通道补全）**：5-HT/Oxy/Opioid/ACh 此前恒定 tonic baseline，现由 `03` salience 派生真实 drive（5-HT←social×(1−threat)、Oxy←social、Opioid←reward+social、ACh←novelty；`C_engineering_hypothesis` grounding，brain.mmd 功能类比非校准，系数挂 `channel_gain_sensitivity` P5 可学；excitation/inhibition 仍留 baseline；映射归 `04` owner 只读 salience）。语义装配下情感系统从 3 通道扩到 7 通道 appraisal-responsive，拓宽 `05` 体感广度（FG-2）；R43 双时标 wrapper 自动 carry 这 4 通道。**R81（激素预测对账）**：项目内首条"模型断言 + owner 对账"路径（`C_engineering_hypothesis` 预测误差类比，P5 学习雏形）。`11` 可在结构化思考输出里主观断言 9 通道 `hormone_response_i_predict` 预测（可 null），经 owner-neutral 的 `PriorHormonePredictionHolder` carry 到下一 tick 的 `04`（因 `04` 在 `11` 之前跑）。`04` 新增 `helios_v2.neuromodulation.corroborator` 的 `HormonePredictCorroborator`：逐通道把 carry 来的预测与同 tick R80 公式 drive 做三态对账（corroborate/conflict/silent），**仅在方向一致（corroborate）时**施加有界 clamp 偏置 `drive + gain*(预测−drive)`——模型只能在公式已认同的方向上微调幅度，绝不能否决或反向覆盖 owner 计算（§14 内容/判断分离）。`CorroborationBiasedNeuromodulatorUpdatePath` 嵌在 R43 双时标 wrapper 内，偏置与 drive 同层被双时标平滑。新增 `hormone_predict_coupling` 学习参数类别（coupling gain + agreement deadzone，P5 可学）。挂同一语义 opt-in；预测缺席时（fake provider 不发）corroborator 字节级复刻 R80 drive，故默认/离线与既有语义装配 level 断言不变。
- 下一步：（1）✅ 双时间尺度 tonic/phasic 衰减携带上一 tick 水平 + 跨重启续存——**R43 已交付**；（2）`P5` 用奖励预测误差（DA）与结果反馈学习有界 sensitivity/alpha 系数，保持方程形状；（3）跨通道耦合（已声明的 `cross_channel_coupling_strength` 类别），超越首版独立映射；（4）下游耦合——`04` 的两个消费者现已都真实：去甲肾上腺素耦合进 `09` 门控（`37`），完整 `04` 状态驱动 `05` 体感（`38`）；仍待：cortisol/inhibition 硬门控进 `09`、以及其余通道（多巴胺→检索/探索）进各自消费者（FG-1/FG-2）；（5）给 `03` 其余四维去 shim，使所有神经调质驱动皆为真实。

### 2.5 `05` 内感受体感层 — `helios_v2.feeling`
- 完成度：`baseline_real`（语义记忆装配下体感已由神经调质推导,并自 R44 起经双时间尺度持久化跨 tick 演化、跨重启续存）。
- 职责：从神经调质状态 + 内部信号产出主观身体感受向量（valence/arousal/tension/comfort/fatigue/pain/social-safety）；仅软调制输出。不拥有调质状态或记忆。
- 在循环中的作用："我的身体状态感觉如何"层，喂给可报告意识与连续性。
- 完成度细节：`38`（P3 第四刀去 shim）在语义记忆装配下把常量构造 shim 换成 owner 私有的 `NeuromodulatorDerivedFeelingConstructionPath`（channel→维度映射归 `05` 自己；每维 `clamp(baseline + sum(coupling_k * level_k))` 的**瞬时 target**）。`44`（P2/P3 铰链,`04` 的镜像）在此之上加**双时间尺度持久化**：语义装配下构造路径换成 owner 持有的 `PersistentFeelingConstructionPath`（包裹 R38 target path）,每维与 R43 同形 `next = clamp(prior + alpha_phasic*(target-prior) + alpha_tonic*(baseline-prior))`（挂 `feeling_persistence` 类别,P5 可学,系数与 R43 一致）。`51`（FG-2 收口）在 target 与 persistence 之间再嵌入 owner 私有的 `InteroceptiveSignalModulatedFeelingConstructionPath`：当装配同时启用语义路径与 `50` 内感受 sampler 时,`05` 真正消费 R50 送达的 `internal_signals`——从刺激 metadata 读有界 `pressure_channel`/`pressure_value`（不解析 content;每通道取 max;不认识/越界/非数值的事实零贡献、不抛错）,给 target 叠加**有界、非负、朝压力方向**的逐维贡献（cpu→arousal/tension、memory→fatigue/tension、latency→fatigue/tension、error→pain_like/tension）,再 clamp。贡献是叠加在神经调质 target 之上（绝不替换它）,空/不认识的 afferent 字节级复刻 inner target,故无内感受 sampler 的装配不变。装配嵌套为 `persistence(interoceptive(neuromodulator))`,故身体贡献与神经调质分量走同一 R44 双时标 carry（无第二套持久化）。瞬时 target 仍归注入的 R38 路径;跨 tick carry 是 `05` owner 语义。`FeelingConstructionPath`/`update_state` 加可选 `prior_feeling`/`prior_state`（默认 None 字节级复刻无状态）;`InteroceptiveFeelingRuntimeStage` 像 04/09/18 持有上一 tick 状态并提供 `seed_prior_state`。冷启动 prior=baseline feeling。`05` feeling 经检查点（快照升 v3 加 `feeling`）跨重启续存。默认/recency/离线装配保持常量体感。valence/comfort/social_safety 本刀不受内感受影响（首版窄、单调）;coupling 系数为首版常量（挂 `feeling_coupling_strength`,P5 可学）。
- 下一步：（1）✅ 双时间尺度体感持久化 + 跨重启续存——**R44 已交付**；（2）✅ 整合真实身体/内感受信号——**R50 交付生产者 + R51 让 `05` 真正消费 `internal_signals` 塑造体感**：`helios_v2.interoception` 把真实 compute/runtime 压力作为 `interoceptive` 刺激喂进 `02`,`05` 现在据此叠加压力贡献,并经 R46 传导到 `07` 工作空间竞争——**真实"机器内部状况 → 体感 → 工作空间竞争"的第一条 FG-2 因果链已闭合,可被评估层只读重建**；**剩余**：真实 latency/error 通道数据源、跨 tick 疲劳累积、更丰富内感受通道、把 valence/comfort 也接入压力；（3）`P5` 学习有界 coupling/alpha 系数；（4）把演化的真实体感喂给 `06` 记忆情感标注与更多行为消费点,扩展 FG-2 因果面；（5）给 `03` 其余维去 shim,使所有上游驱动皆为真实。

### 2.6 `06` 记忆情感与重放 — `helios_v2.memory`
- 完成度：`baseline_real`（语义记忆装配下形成已去 shim 且记忆已耐久；输入在 `05` 以上仍依赖 opt-in）。
- 职责：情感标记的记忆形成与重放候选surfacing，含强制巩固约束。不拥有检索规划、工作空间晋升或身份回写。
- 在循环中的作用：形成情景/情感记忆并向工作空间供给重放候选。
- 完成度细节：`45`（P2 收尾 / P3 中段去 shim）一次收口 `06` 的两处 shim。**形成**：owner 自有的 `AffectGroundedMemoryFormationPath` 在语义记忆装配下取代常量 shim，从真实 `05` `InteroceptiveFeelingState` 形成 affect-tagged 记忆（item 的 `affect_tag` 是真实的当下体感向量，非常量），并由 owner 持有 episodic/autobiographical 家族映射（带 mismatch 证据 → autobiographical）。**显著性门控**：owner 自有的 `SalienceGatedReplayCandidateSelector` 从真实体感（arousal/tension/pain）与 mismatch 算出有界 affect-intensity，据此设每条 replay candidate 的 `forced_consolidation` + `priority_hint`（阈值/系数挂 `consolidation_policy`/`replay_priority_policy` 学习参数类别，P5 可学）——故平淡低情感 tick 不巩固任何记忆，高情感或高 mismatch tick 才巩固。**耐久**：经 owner-neutral 的 `MemoryRecordBridge` + `RuntimeHandle._persist_memory` carry（仿 `_persist_experience`），把恰好被标记 `forced_consolidation` 的 item 以 `record_kind="affect_memory"` 写时 embed 持久化进共享 `33` store，与 `15` 流共存。**召回**：复用 `34` 的语义召回面，affect-memory 经 `10` 可召回并跨重启续存。**记忆内容（R60 去 shim）**：记忆的**内容**此前来自 composition 的常量 binding-context bridge（固定 `("hello","novelty")`/`situational-summary`,所有装配皆然）,故耐久/召回的记忆是"关于一个常量"。R60 把 binding-context 内容改为从帧中真实 `02` percept 派生——优先外部刺激（内感受-only tick 回退整批）,投影主刺激为 `content_kind="perceived-stimulus-summary"`、`summary_ref`=真实刺激 id、`context_ref`=真实批次 id、`salient_tokens`=对真实感知内容的 owner-neutral 机械分词（每个 token 都是真实内容子串,绝不发明,上限 8）。**诚实缺席**：因 gate 前 `02-08` 链每 tick 都需形成记忆（`07` 工作空间对零候选抛错;R54 no-fire 收口只覆盖 gate 后），完全无 percept 的 tick（无外部且无内感受——R59 空源/channel 无输入）不返回 `None`、也不编造外部内容,而是绑定一个锚定真实 `05` 体感的 honest no-percept 标记（`content_kind="no-perceived-stimulus"`,空 token,`summary_ref`=真实体感 state id）;真正的零-percept gate 前收口是后续独立需求。`06` 既不 import persistence 也不 import embedding owner；carry seam 不重算决策（只按 `06` 已设的 flag 过滤）。**惊讶/mismatch（R61 去 shim）**：`06` 显著性门控的第二输入 prediction-mismatch 此前是 composition 常量（固定 `0.8`,使每 tick 都被判 autobiographical 且抬高巩固下限）。R61 把它 grounded 于真实 `03` novelty（`1 - 与既存经验最大余弦`,记忆系统里"惊讶"的功能核心）:取批次最大真实 novelty/uncertainty,投影 `mismatch_score=clamp(novelty)`、`confidence=clamp(1-uncertainty)`;低于阈值 `0.5`（familiar percept）返回 `None`→`06` 形成 episodic 记忆。诚实标注 `B_functional_inspiration`:novelty-as-surprise,非真正预测编码前向模型误差（属 P5）。默认/recency 装配 novelty 为常量 `0.6`（≥阈值）故仍发 `0.6`-派生 mismatch（autobiographical）,非旧 `0.8` 常量。Caveat：去重/合并仍未做。
- 下一步（P2/P3 后续）：（1）✅ 形成去 shim + 接耐久 store——**R45 已交付**；（2）✅ 召回过往情感记忆作为额外重放候选喂 `07`——**R52 已交付**；（3）✅ 记忆内容由真实 percept 派生——**R60 已交付**；（4）✅ prediction-mismatch（惊讶）由真实 `03` novelty grounded——**R61 已交付**；（5）✅ 零-percept gate 前收口——**R65 已交付**（当 `02` batch 为空时,`06`/`07`/`08` pre-gate 链返回 `activated=False` inactive result,不调动 owner engine;tick 经 `09` gate no-fire 收口;R54 post-gate 收口的 gate 前镜像）；（6）去重与同记忆合并/巩固（挂 `consolidation_policy`，有界、owner 拥有）；（7）真实 `05` 体感更深地驱动形成（不止 affect tag）。

### 2.7 `07` 工作空间竞争与工作态 — `helios_v2.workspace`
- 完成度：`baseline_real`（语义记忆装配下竞争与注意力瓶颈已去 shim；首版权重/瓶颈常量、单一候选来源）。
- 职责：候选集竞争与短时工作态保持；记忆衍生内容的晋升边界。不拥有意识承诺或检索。
- 在循环中的作用：注意力瓶颈（FPN 式竞争），决定什么进入可报告意识。
- 完成度细节：`46`（P3 中段去 shim,基于 R45 的真实 `priority_hint`）一次收口 `07` 的两处 shim。**竞争**：owner 自有的 `SalienceWeightedWorkspaceCompetitionPath` 把每个候选的竞争分算成真实有界函数 `score = clamp(0.6*priority_hint + 0.4*feeling_salience)`（feeling_salience 读真实 `05` 体感 arousal/tension/pain），取代常量 `0.95`;每条 replay 候选仍进 candidate set（保留 forced 标记与 feeling provenance,故 owner 既有不变量全部成立）。**注意力瓶颈**：owner 自有的 `BoundedAttentionRetentionPath` 只保留 top-K（首版 `max_retained=3`,挂 `working_state_update_policy`）进 working state,确定性 candidate-id tie-break,非空集永不产出空 working state,取代"保留全部"shim。**类脑语义（owner 确认）**："被巩固"（`06` 标 forced、长期持久化）与"此刻在注意焦点"（bounded working state）是两回事——一个 forced 候选可以在注意力竞争中落选、本 tick 不被 held,它仍在 candidate set（仍作为素材到 `08`）、仍被持久化,只是不在本 tick 焦点。权重/瓶颈是首版常量（挂学习参数类别,P5 可学）。opt-in 于与 R45 同一语义记忆开关（真实 `priority_hint` 只在 `06` 去 shim 后存在）;默认/非语义装配保持常量分 + 保留全部。无契约变更（`WorkspaceCandidateSet`/`WorkingStateSnapshot` 不变）;`07` 不 import 任何其他 owner;既有不变量仍 fail-fast。
- 下一步（P3 / P5）：（1）✅ 真实竞争 + 注意力瓶颈——**R46 已交付**；（2）✅ 多来源竞争（`06` 之外的候选源变真）——**R52 已交付**：`06` 现召回过往情感记忆作为额外候选,故 `07` 现在对真实多候选竞争（R46/47/48 端到端被激活）;（3）P5 学习竞争权重与瓶颈 K；（4）当前 tick 内并发多内容竞争（多刺激/多 binding context,待 `02`/`03` 投影去 shim,R54 territory）。

### 2.8 `08` 可报告意识内容 — `helios_v2.consciousness`
- 完成度：`baseline_real`（语义记忆装配下承诺路径已去 shim：真实点火承诺；上游 06/07 现也已去 shim）。
- 职责：从工作空间输出承诺全局可报告意识内容（或显式不承诺），含非 reach-through 的上游内容素材边界。不拥有思考生成或门控。
- 在循环中的作用："我本周期意识到什么"的承诺，供门控与 prompt 装配消费。
- 完成度细节：`47`（P3 中段去 shim,基于 R46 的真实 `workspace_score_hint`）去 shim 了 `08` 的承诺焦点选择。**问题**：首版 count-based 的 `_RetainedWorkingStateSelectionPolicy` 只要 working state 保留 >1 候选就判 `no_commit/semantic_conflict_unresolved`——而 R46 的有界 top-K 工作态按设计就保留 >1,故 `08` 几乎永不意识到任何东西。**修复**：owner 自有的 `IgnitionFocalSelectionPolicy`（经既有 `focal_selection_policy` 注入口,归 `helios_v2.consciousness`）把单个最高 `workspace_score_hint` 的保留候选点火为焦点可报告内容（全局工作空间 winner-take-all,确定性 tie-break by `source_workspace_candidate_id`）,其余降为支持上下文（按分降序,受 `max_supporting_context_items` 上限约束）。保留：`insufficient_commitment_signal`（零保留）与 `context_not_reportable`（焦点摘要为空）;`semantic_conflict_unresolved` 仍在词表中留给后续真实冲突切片,但不再因单纯多数触发。无契约/引擎/渲染器变更（点火产出正是既有校验与确定性渲染器已接受的 focal+supporting 形状）。opt-in 于与 R45/R46 同一开关;默认/非语义装配保持 count-based 策略。**端到端现状**：当前链每 tick 只形成一个候选,故"多数→点火赢家而非 no-commit"这一行为头条今天是 owner 级验证,待多候选来源落地后端到端可见。
- 下一步：（1）✅ 真实点火承诺——**R47 已交付**；（2）✅ 端到端多候选点火（"多数→点火赢家"行为头条端到端可见）——**R52 已交付**（`06` 召回过往情感记忆后 `07` 有真实多候选,`08` 在多候选中点火单一焦点赢家,其余降为支持上下文）；（3）真实语义冲突检测（内容矛盾才判 `semantic_conflict_unresolved`,待并发可矛盾内容）;（4）经已搭好的 owner 受控能力口接 LLM 语义渲染器;（5）P5 学习点火阈值/tie-break。

### 2.9 `09` 思考门控与延续压力 — `helios_v2.thought_gating`
- 完成度：`baseline_real`（语义记忆装配下所有门控输入已真实：arousal（R37）、global_activation（R48）、workload_pressure（R53）、temporal/DMN（R55）、drive_urgency（R62）、selected_stimuli（R63）；门控信号中不再有常量 shim）。
- 职责：思考窗口触发决策与多 tick 延续压力 carry 的唯一 owner；紧凑门控可观测。不坍缩进检索或思考生成。
- 在循环中的作用：决定一个 tick 是否触发思考路径，并把延续压力向前 carry。
- 完成度细节：`37`（P3 第三刀去 shim）使 `09` 门控决策成为 `04` 神经调质水平的首个真实消费者。owner 新增 `ArousalAwareThoughtGatePath` 与 `ThoughtGateSignalSnapshot` 上一个附加可选原始事实字段 `neuromodulatory_arousal`；语义记忆装配下 composition 把真实 `04` 去甲肾上腺素水平转发进来（仅原始事实——arousal→门控的映射归属本 owner,不在 composition）。该 path 向门控分数加一个非负有界项 `arousal_gain * arousal`（首版 `0.15`,属 `gate_policy` 类别）；单调、确定性、无状态,且结构上绝非硬门控（权重 `0.15 < fire 阈值 0.55`,且加项非负）。`48`（接 R46）把门控分中第二大的非刺激项 `global_activation_level`（权重 `* 0.20`）从常量 `0.9` 去 shim：语义装配下 composition 的门控信号 bridge 现从同 tick 的 `07` `WorkspaceCompetitionStageResult` 取真实工作空间激活——保留候选中的最大 `workspace_score_hint`（注意力中持有的主导点火强度）,无保留则 `0.0`。owner-neutral glue（bridge 只转发有界原始事实,clamp 到 `[0,1]`）;`09` 仍独占门控决策与该项权重（门控 path 不变）。R37 的 arousal 耦合保留（两个真实事实同乘一个快照）。`07` 在 `09` 前运行,故缺失/类型错的 `07` 结果是 hard fail（既有 `RuntimeStageExecutionError`）,无静默回退。其余门控信号输入（`workload_pressure`、`temporal_signal`、`dmn_available`）现已真实；R62 起 `drive_urgency_signal` 亦已真实（上一 tick 的 `18` `outward_drive` 经 owner-neutral 的 `PriorDriveUrgencyHolder` 向前 carry,tick 1 中性冷启动 `0.7`）；R63 起 `selected_stimuli` 亦已真实（同 tick `03` appraisal 批最大值 aggregate/novelty/uncertainty 经 owner-neutral 的 `_selected_stimuli_from_appraisal` helper 投影，默认装配 `FirstVersionAggregateEstimator` 从 `0.4` 提升到 `0.7` 提供诚实点火源）。**R63 之后，门控信号中不再有常量 shim**——每个 `09` 门控输入都是真实上游事实或文档化冷启动基线。当 `neuromodulatory_arousal` 为 `None` 时门控 path 仍字节级复刻首版（默认/recency/离线不变）。
- 下一步：（3）在 `03` threat 变真后耦合 cortisol/inhibition 硬门控通道；（4）`P5` 在 `gate_policy` 类别下学习权重与门控阈值。**R63 后门控信号中不再有常量 shim——每个 `09` 门控输入都是真实上游事实或文档化冷启动基线。**

### 2.10 `10` 定向检索进思考窗口 — `helios_v2.directed_retrieval`
- 完成度：`baseline_real`（候选来源真实；recall-intent 自 R49 起由真实 `11` handoff 驱动）。
- 职责：检索查询规划、分层选择、有界思考窗口 bundle 装配的唯一 owner。不拥有记忆持久化或思考生成。
- 在循环中的作用：装配思考 owner 推理所依据的有界记忆窗口。
- 完成度细节：`49` 去 shim 了 `10` 请求的 `recall_intent`/`selected_memory_refs`（查询规划路径本身早已真实,只是其输入是 shim）。常量 `recall_intent="remember runtime chain context"` 与伪造的 `selected_memory_refs=("memory:runtime:{tick}",)` 在语义装配下被替换为**上一 tick 的 `11` 内部思考 `MemoryHandoffDirective`**（当 `11` 为下一 tick 保存了 recall_intent + selected_memory_refs 时）,故系统选择继续的那条思路真实地引导下一 tick 检索什么记忆——收口记忆引导维持闭环（`ARCHITECTURE_PHILOSOPHY` §5.3）。carry 复用 R32 后果声明 / R42 连续性 的同一机制：owner-neutral 的 `PriorThoughtRecallHolder` + `RuntimeHandle._carry_recall_directive` tick 后捕获 + `ThoughtDirectedRetrievalRequestBridge` 读取。无保存 handoff 时（首 tick、未 fire tick、或 `11` 未继续）请求回落到真实 `09` `compact_stimuli`、无 recall intent——这是定义行为非降级,且因 `compact_stimuli` 恒真而始终有效。owner-neutral：composition 逐字转发 `11` 拥有的 directive、不算检索策略;`10`/`11` 契约与引擎不变。opt-in 于与 R45-R48 同一开关;默认/非语义装配保持常量 recall intent。
- 下一步：随 `33`/`34` 候选 provider 已真实（recency，再语义）。剩余：（1）✅ recall-intent 接真实 `11` handoff——**R49 已交付**；（2）`10` 内更深的 recall-intent 塑形（按意图内容选 tier/limit）；（3）把检索意图接到 `18`/`24` 长程连续性线程,让连续性线程跨多 tick 引导检索（wave_B）；（4）真实 `compact_stimuli` 出处（去 shim 的 `02`/`03` 投影）。

### 2.11 `16` 具身 prompt 契约 — `helios_v2.prompt_contract`
- 完成度：`baseline_real`。
- 职责：为 `thought` 与 `outward_expression` 消费者装配具身主观 prompt 契约；反表演约束；能力/权限边界渲染。不拥有思考执行、planner 权限或治理。
- 在循环中的作用：把承诺状态 + 检索 + 能力边界格式化成思考 owner 与外化 owner 消费的契约。
- 下一步：保持其为契约 formatter（绝不变成 reply-first 行为 owner）；随真实上游信号到来丰富层。仅深化。
- R79（v3 owner-grounded，默认）：新增 `OwnerGroundedEmbodiedPromptPath`（默认 `embodied_prompt_mode="v3"`，`"v1"` 为 legacy escape hatch）。身份框架从 `14` 上一 tick `identity_state_snapshot` 渲染（**不硬编码**"你是人/不是AI"），自然语言 11 字段 + focused/peripheral/filtered 注意力场 + ready_channels + 升级反表演（只表达状态支撑、不自指 AI）。身份归 `14`，prompt 仍是 formatter。
- R81（第 12 字段）：v3 response_schema 增加可选第 12 字段 `hormone_response_i_predict`（9 通道→`[0,1]` 的可空对象，模型可省略/null）。纯 schema 文本增补，无契约字段变更；实际解析与对账见 `11`（2.14）与 `04`（2.4）。

### 2.12 `16` 外化表达草稿 — `helios_v2.outward_expression`
- 完成度：`baseline_real`（设计上仅草稿）。
- 职责：从 prompt 拥有的请求产出一份有界、非权威的外化表达草稿。不拥有最终执行、planner 决策或 channel 路由。
- 在循环中的作用：准备候选外化草稿；永不权威。
- 下一步（wave_C）：执行收口深化后做更丰富的主动草稿塑形；最终权威留在该 owner 家族之外。

### 2.13 `16` 外化执行草稿 — `helios_v2.outward_expression_externalization`
- 完成度：`baseline_real`（设计上仅草稿）。
- 职责：从外化表达草稿产出执行相邻的外化草稿。不拥有最终 planner/channel/传输权限。
- 在循环中的作用：prompt→草稿链中最后的执行前塑形步骤。
- 下一步（wave_C）：经 planner + channel 路径把草稿接到真实外部传输；在此之前保持非权威。

### 2.14 `11` 内部思考循环 — `helios_v2.internal_thought`
- 完成度：`deep_real`（真实 LLM 驱动的认知核心）。
- 职责：触发路径思考执行与结构化判断（充分性、延续、recall intent、记忆 handoff、行动提议、自我修订提议）的唯一 owner。模型供给内容 + 结构化自评；owner 保留全部最终判断。不拥有持久化、规划或治理接受。
- 在循环中的作用：认知核心——经 `25` LLM 网关用中性结构化请求取思考内容，并解析成 owner 拥有的判断。
- 下一步：更强的充分性/延续/后果收口；随 P3 去 shim 落地更紧地耦合真实上游信号。这是最成熟的认知 owner。
- R79（解析鲁棒化）：`_parse_structured_thought` 解析前 strip `<think>` 块 + markdown 围栏（reasoning 模型输出可解析），thought profile `max_tokens`→2048 避免 reasoning 截断；提取后无 JSON → 显式 `insufficient_generation`（不虚构）。干净 JSON 恒等，无回归。
- R81（激素预测字段）：`_parse_structured_thought` 放过可选 `hormone_response_i_predict`（9 通道→`[0,1]` 的可空 dict；缺省/null→无预测，越界/类型错→parse error，未知键忽略），存入 `StructuredThoughtEvidence.hormone_prediction` 并经判断助手透传到 `ThoughtCycleResult.hormone_response_i_predict`。这是模型供给的**内容**，绝不改充分性/延续/提议判断；由 owner-neutral carry 送往下一 tick 的 `04`（见 2.4）。`11` 不 import `04` 的 `NeuromodulatorLevels`（9 通道名是文档化约定）。

### 2.15 `12` 行动提议与外化契约 — `helios_v2.action_externalization`
- 完成度：`baseline_real`。
- 职责：思考来源提议归一化、外化契约发布、桥级拒绝语义的唯一 owner。不拥有 planner 接受或 executor dispatch。
- 在循环中的作用：把一个思考的行动提议归一化成 planner 桥消费的契约。
- 下一步（wave_C）：在真实外部行动收口于下游深化时保持契约真相稳定。

### 2.16 `13` planner-executor 反馈桥 — `helios_v2.planner_bridge`
- 完成度：`baseline_real`（planner 判断真实；默认装配里 channel-state 快照仍 shim，channel-bound 装配里则真实）。
- 职责：提议到决策的桥接、正式拒绝/执行结果发布、归一化桥反馈的唯一 owner。拥有最终绑定/接受，不拥有思考语义；不拥有传输或反馈持久化。
- 在循环中的作用：把归一化提议变成 accept/reject/execute 决策；对内部 tick 发布 `no_actionable_proposal`（R28 fired-but-no-proposal,R54 起 gate-no-fire tick 也复用此 internal-only 路径收口）。
- R86（强制 risk-class 门）：把 R85 透传进 `policy_trace` 的 `op_risk_class` 从只读升级为**强制 fail-closed 门**。op 级 `unrestricted`（reply/`fs_*`）字节级不变；op 级 `governed`/`restricted`（命令 op）按 driver 投影的 `command_policy` 算 effective 逐调用风险——`unrestricted` 放行、`restricted`/未知 → `risk_class_restricted` 硬拒（绝不绑定）、`governed` 查 carried `14` 授权（按稳定 `action_authorization_key`）→ 放行 / `governance_denied` / `governance_required`（并发布 pending action 供 `14` 授权）。allowlist 内容归 driver、授权归 `14`、门归 `13`；planner 不硬编码任何命令名。
- 下一步（wave_C）：超越本地 CLI 的真实外部 channel 执行；更丰富的主动 provenance 进入行动选择。

### 2.17 `14` 身份治理与自我修订 — `helios_v2.identity_governance`
- 完成度：`baseline_real`（R68 起有跨 tick governance carry state）。
- 职责：自我修订治理、身份状态变更、主动治理压力、正式修订结果发布的唯一 owner。不拥有思考生成、人格投射或审计持久化。
- 在循环中的作用：治理一个自我修订提议是否接受，并应用受治理的身份变更。
- 完成度细节（R68 跨 tick carry）：`14` 新增 `GovernanceCarryState` 冻结数据类（identity_state_snapshot + recent_governance_trace_history + accepted/rejected_revision_count），`IdentityGovernanceRuntimeStage` 持有 `_prior_carry_state` 并从治理结果推进（accepted 修订携带新快照，否则保留旧快照；每 tick 追加有界 trace 条目；累积接受/拒绝计数）。bridge 经注入式 `carry_state_provider` 把 carry state 的快照与 trace 历史注入请求。无 provider 或返回 `None` 时回落 bootstrap 常量（字节级不变冷启动）。
- 完成度细节（R86 governed 动作授权，additive）：`14` 现额外是 `governed`-tier 工具动作的**授权权威**。新增 `GovernedActionAuthorization` 契约 + owner 私有 `GovernedActionGovernancePath` + `authorize_governed_action`/`evaluate_self_revision_and_authorize`（自我修订路径、契约、校验器**字节级不变**；无 pending action 时 `authorize_governed_action` 返回 `None`、inert）。首版策略：argv 匹配 composition 配置的授权前缀（由绑定 driver 的 governed 规则派生）才授权，默认空集 = fail-closed。两-tick 握手：`13` 在 tick N 对 governed 动作发 `governance_required` + pending action；`14`（在 `13` 之后跑）发布授权 verdict；经 owner-neutral 的 `PriorGovernedAuthorizationHolder` carry 到 tick N+1；复议时 `13` 凭 carried 授权放行。`14` 只授权，不选/绑/执行 channel，不拥有 allowlist（driver）或门（`13`）。
- 下一步（wave_B / P6）：更深的长程受治理自我演化（发展性，而非仅审计补丁）；跨重启持久化/恢复身份状态（纳入 `42` 检查点）；最终落地 P6 的受治理自我修订路径。R86 的 governed-action 授权可加 posture 耦合（`stabilize` 时拒）与审计 token 精化。

### 2.18 `15` 经验回写与自传巩固 — `helios_v2.experience_writeback`
- 完成度：`baseline_real`（其连续性流现已经 `33` 持久化）。
- 职责：执行结果回写、连续性证据 packet、巩固候选 handoff 的唯一 owner。不拥有 planner/治理决策或原始存储后端。
- 在循环中的作用：把每 tick 结果归类成连续性 packet 并喂 `15 → 06` 闭环；其流即 `33` 所持久化的。
- 下一步（wave_B）：更强的长程 carry 与再入；`06` 共享耐久底座后做更丰富的巩固。

### 2.19 `18` 主动性自治与主动演化 — `helios_v2.autonomy`
- 完成度：`deep_real`（`relatively_complete`；自 R29 起接真实认知；含 `24` 长程连续性线程层）。
- 职责：主动驱动整合、有界 disposition 选择、延迟连续性发布、长程连续性线程（复现强化、冲突仲裁、owner 拥有的 `LongHorizonContinuityState`）。可语义地请求主动外化，但绝不执行 channel 路径。
- 在循环中的作用：把真实认知整合成主动 disposition（行动 → externalize，无行动 → reflect/defer），并跨 tick 形成/强化连续性线程。
- 完成度细节（R57 边界回收）：**"认知结果 → 驱动输入"的映射已从 composition 回迁到 `18` owner**。此前 `FirstVersionAutonomyRequestBridge` 在装配胶水里标定压力常量（`_ACTION_*=0.9/0.4/0.4` 等）、做 planner executed/blocked 分类、做 retrieval `/4.0` 归一化,且其注释逆向引用了 owner 的 `outward_drive >= 1.6` 阈值——这是 `18` 的本职认知策略,违反 §4.5/§7.1/§3.3。R57 新增 owner 拥有的 `ProactiveCognitionFacts`（composition 可读的原始认知事实契约）与 `AutonomyDriveInputProjection.derive_drive_inputs(facts)`（产出既有五个驱动输入 summary）,并把阈值固化为 owner 常量 `OUTWARD_ACTION_THRESHOLD = 1.6`（`FirstVersionAutonomyPath` 复用）。composition bridge 退化为：抽取原始事实 + 转发 provenance + 调 owner 投影。`ProactiveDriveRequest` 契约形状不变;逐 tick、逐装配字节级不变。
- 下一步（wave_B）：超越有界 carry 的更丰富长程动机演化；更锐利的连续性 key 方案——**R67 已交付**：连续性 key 改为仅由 `carry_reason` 的 `_base_reason` 派生（去掉 tick-specific 的 `source_thought_cycle_result_id`/`source_planner_bridge_result_id`），使同一动机在 record 过期后重新出现时仍匹配同一线程（thread 不再因 key 差异重置到 age 1 / reinforcement_count 0）。跨重启持久化/恢复长程状态——**R42 已落地**：`18`/`24` 延迟记录与连续性线程现经 `42` 检查点跨重启续存（opt-in）。`drive_integration_policy` 下的压力常量与阈值现归 `18`,P5 可学。

### 2.20 `17` 评估保真与诊断 provenance — `helios_v2.evaluation`
- 完成度：`baseline_real`（只读；自 R32 起对账执行真相；消费 `23` 时间线）。
- 职责：证据驱动评估、后果绑定路径结论、执行真相对账（`corroborated`/`discrepant`/`unverifiable_no_timeline`）、诊断 provenance 发布的唯一只读 owner。不变更任何运行期状态。
- 在循环中的作用：最后一个阶段；重建内部到可见的因果链，现在还把自报结论对账内核执行时间线以证伪。
- 完成度细节（R87 真实送达对账）：在 R32「流程完成」对账之上，对 effector 动作新增**真实送达** verdict。`ConsequenceClaim` 加 `decision_id`/`selected_op`/`op_effect_class`/`op_user_visible`；bundle 加 `delivered_tool_result_evidence`（composition 从同帧 `channel_inbound_drain` 投影本 tick 回流的 correlation decision_id+ok）。`_corroborate_delivery` 对一个 `executed`/`continuity_written` 且为已知非 user-visible 的 host/world effector 动作，按 decision_id 匹配回流：`ok=True`→`really_delivered`、`ok=False`→`delivered_failed`(+`consequence_delivery_discrepancy` 告警)、无回流→`delivery_unverified`（诚实缺席，绝不乐观）；非 executed/未知/relay/internal→`delivery_not_applicable`（R32 对账照旧）。严格 additive：不改 R32 verdict/taxonomy/打分；只读、不重算 owner 决策（按 id 匹配 + 读 ok 事实）。`effect_class` 在此成为真实消费者。收口 B4（本机 effector 路径）。
- 下一步：非确定性认知产出可变路径后做更丰富的 discrepancy 分类与打分深度；`23` 侧跨 tick 送达延迟/重试长程诊断；preserved-vs-resolved-vs-degraded 连续性对账（wave_B）；artifact 的跨运行耐久比较（依赖 P2）。

---

## 3. 基础设施与能力 owner

非认知 owner。它们为认知链提供所依赖的底座。

### 3.1 `21` 统一运行时可观测性 — `helios_v2.observability`
- 完成度：`infra_done`。
- 职责：结构化 `LogEvent` 契约、severity/event-kind 词表、`LogSink` 协议 + 首版 sink、序号戳记 recorder、只读 `ExecutionTimelineView` + `ExecutionTimelineReconstructor`（`23` 底座）。绝非权威的 owner 间传输。
- 作用：默认关闭的内核插桩；时间线视图是下游消费时序事实的唯一合法形式。
- 下一步：超越内核生命周期的 owner 级细粒度发射（plan C），在后续切片需要时经同一 owner 开放。

### 3.2 `22` 运行时组合根 — `helios_v2.composition`
- 完成度：`infra_done`。
- 职责：仅装配地把依赖门、规范阶段链、owner-neutral 首版 bridge、可选 recorder、以及 opt-in 的 channel/persistence/embedding seam 接成可运行 `RuntimeHandle`。不持认知策略；无降级装配路径。
- 作用：唯一持有完整装配真相的地方；拥有 `CANONICAL_STAGE_ORDER` / `CHANNEL_BOUND_STAGE_ORDER`、owner-neutral bridge,以及 R58 的 `RuntimeProfile` 能力束。
- 完成度细节（R58 能力束）：`assemble_runtime` 曾把九个能力 seam 作为松散 kwargs 传入,跨能力规则（embedding 需 store）内联校验,派生标志 `semantic_memory_enabled` 作为局部变量穿过约 10 个三元分支——每加一个能力就要再穿一个松散 flag。R58 引入冻结的、composition 拥有的 `RuntimeProfile` 能力束:聚合这些 seam,在 `__post_init__` 一处做跨能力 fail-fast 校验,以 `semantic_memory_enabled` 属性暴露派生标志（只算一次）。`assemble_runtime` 新增可加的 `profile=` 参数（仍接受全部既有 kwargs,经 `_UNSET` sentinel 构建 profile;profile 与重叠 kwargs 同传则 `CompositionError`）。纯结构重构,逐装配、逐调用方字节级不变。
- 完成度细节（R69 语义装配默认化）：`RuntimeProfile` 新增 `default_signal_mode` 字段（`"semantic"` 新默认 vs `"legacy_constant"` 逃逸口）。当 `"semantic"` 且调用方未注入 `experience_store`/`embedding_gateway` 时，自动配置 `InMemoryExperienceStoreBackend` + `DeterministicHashEmbeddingProvider`，并重建冻结 profile 使 `semantic_memory_enabled` 反映装配状态。`assemble_runtime()` 无参数调用时 `semantic_memory_enabled == True`，`03`–`10` 去 shim 链激活。显式注入始终优先。
- 完成度细节（R82 标准生产装配 / G2 收口）：新增 `assemble_production_runtime()` 标准生产入口（与 in-memory 默认的 `assemble_runtime()` 测试/嵌入入口并列，后者字节级不变）。它默认把耐久基础设施**打开**：SQLite 经验存储（`SqliteExperienceStoreBackend`，R33）+ SQLite R42 连续性检查点（`SqliteCheckpointBackend`）+ `experience-embedding` 网关，全部落在 git-ignored 的 `data/`。不持认知策略——只构造耐久后端并委托 `assemble_runtime(default_signal_mode="semantic")`（后者已接好 checkpoint bridge、`experience_store_ready`/`embedding_profile_ready`/`continuity_checkpoint_ready` 关键依赖与启动恢复）。经此装配的运行时跨进程重启保留 `15` 经验流并恢复跨 tick 的 `09`/`18`/`04`/`05` 状态（FG-5.1），收口 §13.3.1 G2.2/G2.4 持久化门。embedding 网关 real-capable（设 `HELIOS_EMBEDDING_API_KEY` 用 OpenAI 兼容 provider；模型/base-url 经 `HELIOS_EMBEDDING_MODEL`/`HELIOS_EMBEDDING_BASE_URL`），否则回退网络无关 `DeterministicHashEmbeddingProvider`（真实 embedding 质量留 P5，哈希为显式占位）。任一后端不就绪 startup fail-fast；无降级非持久路径。
- 下一步：随 owner 去 shim，用 owner 真实的跨 owner 契约替换首版 bridge；保持装配不含认知策略。R56 已把误置于此的 `04` 神经调质 drive 映射（`AppraisalDerivedNeuromodulatorUpdatePath`）回迁到 `04` owner；R57 已把误置于此的 `18` autonomy 驱动输入映射（认知结果→压力常量、planner 分类、retrieval 归一化、阈值知识）回迁到 `18` owner（新增 `ProactiveCognitionFacts` + `AutonomyDriveInputProjection`）。guard（`tests/test_composition_owner_boundary_guard.py`）现同时防止 `<salience>_to_<channel>` 敏感度策略与 autonomy 驱动压力/阈值策略再次落入 composition。**当前仍留在 composition 的是被接受的 owner-neutral 胶水**：常量首版 shim 路径（`FirstVersion*`）与纯投影 bridge（只转发已发布 owner 字段、不施加打分权重,映射归消费方 owner,如 `09` 门控的 `workload_pressure`/`global_activation_level` 投影）。后续若发现其他认知策略残留,应按同一模式回迁。新能力应作为 `RuntimeProfile` 的一个字段加入,而非新的松散 kwarg。

### 3.3 `25` LLM 推理网关 — `helios_v2.llm`
- 完成度：`infra_done`。
- 职责：后端中性请求/完成契约、命名 profile registry、注入式 provider 协议 + 首版 OpenAI-compatible provider（懒加载 SDK）、网络无关静态 readiness、opt-in live probe。不拥有认知；绝不解释完成文本。
- 作用：`11` 思考 owner 消费的能力；经 composition 绑定逐消费者 profile。
- 下一步：随这些 owner 产生真实生成需求，新增绑定消费者（例如 `13` 工具调用规划、`14` 自我修订起草）。

### 3.4 `30` channel driver 子系统 — `helios_v2.channel`（+ `31` CLI driver；`84` OS 文件 effector — `helios_v2.channel.drivers.os_fs`）
- 完成度：`infra_done`（框架 + CLI relay + OS 文件 effector 真实；opt-in；非默认运行时）。
- 职责：Linux-driver 风格的传输 owner——统一 `ChannelDriver` 协议、registry、NAPI 式有界入站 drain（发出带 QoS 的 `RawSignal`）、有界出站 dispatch、真实逐 driver channel 状态、fail-fast readiness。仅传输/effector：非归一化（`02`）、显著性（`03`）、选择（`13`）或内容塑形（`16`），不解释结果含义。
- 作用：opt-in channel-bound 装配下本地 CLI 往返端到端运行；R84 起装配泛化为可注册一组 driver（`RuntimeProfile.channel_drivers`），OS 文件 **effector** 可与 CLI 共存于一个 subsystem。
- R84（首个 effector + reafference 闭环）：`OsFileSystemChannelDriver` 在 sandbox root 内执行 `fs_read/fs_write/fs_list/fs_modify`（`resolve()`+relative 严格路径逃逸防护，绝对外/`..`/软链拒绝；写受 `allow_write` 门控），经注入式 executor（测试 `InlineFileOpExecutor` 确定性 / 生产 `ThreadPoolFileOpExecutor` 真异步）。`send_outbound` 同步受理（`delivered`=已受理，非完成）；op 结果（成功或失败）作为带 correlation provenance 的 `tool_result` 包入队、于后续 tick 回流 `02`——项目首条 efference→reafference 工具使用闭环（FG-4）。失败写回（绝不冒充成功）；readiness=sandbox 存在。
- R85（自主工具选择 + per-op 自描述）：每个 driver 现声明 per-op `ChannelOpSpec`（`required_params`+`user_visible` 启用；`effect_class`+`risk_class` 声明，留 R86/R87 消费）。`13` planner 按声明的 spec 通用校验 op 输入（reply 与 `fs_*` 统一），能力门由真实 channel-state 派生（某连接 driver 声明该 op 即视为 registered）。真实认知（`11`）选工具 op+params（模型内容）、`12` 结构性贯通、`13` 按 op 绑定到提供该 op 的 driver——收口自主"思考→工具→结果→再思考"闭环（R84 只交付机制）。
- 下一步：R85 已交付；接下来 `86` OS 命令执行（受治理 fail-closed，复用已声明的 `risk_class`）与真实外部（网络）driver（QQ/飞书/语音）复用泛化的多 driver 装配与 per-op 自描述。

### 3.5 `33` 耐久经验存储 — `helios_v2.persistence`
- 完成度：`infra_done`（opt-in）。
- 职责：`PersistedExperienceRecord`/`PriorExistenceSnapshot` 契约、注入式后端协议（SQLite 文件 + 内存 double）、`ExperienceStore` facade（append / recent-N / count / snapshot / 相似度检索）、recency + 语义候选 provider。耐久追加 `15` 连续性流；确定性 recency 或余弦相似度再入 `10`。自身绝不 embed 文本；绝非权威 owner 间传输。
- 作用：给系统跨重启存活的记忆（FG-5.1）；持久化经验重新进入思考窗口。
- 下一步（P2）：`18`/`09`/`14` 的最新态检查点/恢复（`09`/`18`/`04`/`05` 已落地，`14` 待其获得跨 tick 状态）；✅ 把 `06` 记忆条目接入 store——**R45 已交付**（affect-memory 经 `record_kind` 判别字段与 `15` 流共存于同一 store）；之后做巩固/遗忘策略与 P5 学习的耐久底座。

### 3.6 `34` embedding 推理网关 — `helios_v2.embedding`
- 完成度：`infra_done`（opt-in）。
- 职责：后端中性 embedding 请求/结果契约、命名 profile registry、注入式 provider 协议 + 懒加载 OpenAI-compatible provider、fail-fast 网关、网络无关静态 readiness、opt-in live probe。不拥有认知；绝不解释向量。
- 作用：把文本变成向量，使 store 能按语义相似度排序经验；query/记录 embedding 由 composition 注入进 store（store 不依赖此 owner）。
- 下一步（P3 铰链）：喂 `03` novelty-from-memory（距最近存储记忆的距离）；pre-semantic 记录的重 embed/回填；规模上来后 ANN 索引。

### 3.7 `42` 耐久运行时连续性检查点 — `helios_v2.continuity_checkpoint`
- 完成度：`infra_done`（opt-in）。
- 职责：`RuntimeContinuitySnapshot` 契约（真正跨 tick 连续性状态的 owner-neutral 可序列化投影——`09` 延续压力 + `18`/`24` 长程连续性,直接复用这些 owner 的契约）、`CheckpointStoreBackend` 协议（单行 SQLite 文件后端 + 内存 double）、`ContinuityCheckpointStore` facade（`save_latest` 替换 / `load_latest` 或显式缺席）。保存最新态单快照（非追加日志）；自身绝不计算或重解释任何连续性决策。
- 作用：给系统跨重启续存"我刚才想到哪了/我反复回到的倾向"（FG-5.1）。opt-in `assemble_runtime(continuity_checkpoint=...)` 下每 tick 后保存,启动时（fail-fast 门通过后）恢复并经 stage 种入口种入 `09`/`18` 的上次跨 tick 状态。独立于 `33`/`34`。
- 下一步（P2）：随 `04`/`05` 双时间尺度动力学与 `14` 身份状态获得持久化 carry,把它们增量纳入快照（已版本化）；`06` 记忆条目接耐久底座后纳入巩固。

### 3.8 内感受信号源 — `helios_v2.interoception`
- 完成度：`infra_done`（opt-in；生产者已交付,`05` 消费待下一刀）。
- 职责：外周传入式生产者（类比内感受感受器报告身体内部状态）。把运行时真实内部状况（compute/runtime 压力：CPU/内存/延迟/错误率）报告为有界 `interoceptive` `RawSignal` 喂进 `02`。`RuntimePressureSample` 契约（四个 `[0,1]` 通道）、注入式 `RuntimePressureSampler` 协议、首版 `StdlibRuntimePressureSampler`（懒 `psutil` 取真实 CPU/内存,缺失降级到 stdlib load-average 或定义的中性默认,绝不为"仅不可用"的事实抛错）、`RuntimeInteroceptiveSource`（实现既有 `SensorySource`,每通道一条有界确定性信号）。不拥有任何 feeling/salience/认知策略,不 import feeling/appraisal/neuromodulation owner。
- 作用：收口 `gap_interoceptive_signal_source` 的**生产者半边**——`02→05` 的身体信号传入路径（代码早已存在但恒空）现真实承载信号；opt-in `assemble_runtime(interoceptive_sampler=...)` 下 `05` stage 收到非空且校验通过的 `internal_signals`。**消费者半边自 R51 起也已闭合**：`05` 的 `InteroceptiveSignalModulatedFeelingConstructionPath` 现据这些信号叠加压力贡献塑造体感。
- 下一步：（1）✅ 让 `05` 构造路径真正消费 `internal_signals` 塑造体感（FG-2）——**R51 已交付**；（2）✅ 把同一压力读数喂给 `09` 门控的 `workload_pressure`（第二消费者）——**R53 已交付**（cpu/memory 负载经门控信号 bridge 取代常量 `0.1`）；（3）更丰富的内感受通道（模拟身体状态模型：心跳/呼吸类比、跨 tick 疲劳累积）；（4）从 `21` 可观测喂真实 tick 延迟/错误率到 latency/error 通道（当前为首版可注入默认）。

### 3.9 时间节律与 DMN 源 — `helios_v2.temporal`
- 完成度：`infra_done`（opt-in）。
- 职责：报告 `09` 门控消费的两个真实情境事实——默认模式网络（DMN）是否在线（rest vs 外部任务）与从 elapsed rest 累积的自发思考节律。`TemporalPacingSample` 契约（`temporal_signal` `[0,1]` + `dmn_available` bool）、注入式 `TemporalSource` 协议（`sample(external_stimulus_present)` + `observe_tick(fired)`）、首版 `RestStateTemporalSource`（`dmn_available = not external_stimulus_present`;`temporal_signal = clamp(per_tick_increment * ticks_since_last_fire, 0, max_signal)`,跨无 fire tick 累积、fire 时重置）。不拥有门控决策或权重（归 `09`）,不 import gate/appraisal/feeling/neuromodulation owner。
- 作用：把 `09` 门控的 `temporal_signal`/`dmn_available` 从常量去 shim,使系统能表达 rest-state 自发思考节律（越久未思考越倾向于自发思考）与外部任务时 DMN 退离。跨 tick elapsed 状态经 owner-neutral 的 `RuntimeHandle._carry_temporal` seam 从已发布门控决策推进（fire 重置、no-fire 累加）。R54 使其安全：真实 temporal 输入现可正常导致 no-fire 而不中止 tick。
- 下一步：（1）✅ `drive_urgency_signal` 接真实 `18`——**R62 已交付**（上一 tick `18` `outward_drive` 向前 carry;门控最后一个常量输入曾是 `selected_stimuli`——**R63 已交付**——投影真实 `03` appraisal 并提升默认装配 aggregate）；（2）更丰富的时间动力学（昼夜/超日节律、真实 wall-clock 或 tick 速率节律）与 P5 学习累积率/门控权重；（3）更细的 DMN 模型（分级在线而非二元 rest/task 切换；DMN 在线耦合内省检索）；（4）跨重启 carry elapsed 状态（经 seed seam,已预留）。

---

## 4. 文档 owner

### 4.1 `19` 架构边界与 owner 文档
- 完成度：`docs_owner`。
- 职责：让 `ARCHITECTURE_BOUNDARIES.md`（及本 owner 图）与运行真相对齐——owner 边界、允许依赖、迁移注记、禁止捷径。
- 下一步：在每次 owner-wave 收口的同一变更内更新边界真相（当前已跟踪到 R69）。

### 4.2 `20` 脑架构对比与科学接地
- 完成度：`docs_owner`。
- 职责：让 `BRAIN_ARCHITECTURE_COMPARISON.md` 对齐——克制的脑功能类比、证据类别、显式非目标、gap 分析、owner-wave 路线图。
- 下一步：随 owner wave 收口收窄/退休 gap；让 wave 路线图与哲学文档的阶段路线图对齐。

---

## 5. 全系统视角（替代已退休的 distance 快照）

本节吸收了原先存放于已退休的 `TOTAL_DISTANCE_TO_FINAL_GOAL.md` 与
`REQUIREMENT_DISTANCE_TO_FINAL_GOAL.md` 的"距终局目标距离"聚合视角，现以活文档形式保留于此。

1. 系统在架构上真实、首版级别 owner 完整。P3 已退出（R64 PASS），语义装配已成为默认装配（R69）。它尚未达到终局完成态。
2. 当前最重的剩余运行期距离已转移：`12-16` 外化链去 shim 与 wave_C 执行收口、`14` 身份治理深化（wave_B）、真实外部网络信号源（wave_C）、`P4` 工具/效应器生态。
3. `wave_A_behavioral_truth`（评估证伪）随 R32 基线收口。`P2`（耐久记忆）随 R33 开篇，随 R34 获得语义召回，随 R42 获得跨重启的连续性状态续存（`09` 延续压力 + `18`/`24` 长程连续性），随 R45 获得情感记忆耐久。`P3`（去 shim）随 R35 开篇，随 R64 正式评估退出并判定 PASS。
4. 下一批最高杠杆动作是：wave_B 长程主观连续性（`18`/`14`/`15` 深化）、wave_C 执行收口（`13`/`16` 真实外部行动）、P4 工具生态。
5. 当今真正由真实信号驱动的 owner：`02`（感觉接入）、`03-10`（默认去 shim，R69）、`11`（LLM 驱动思考）、`18`（已接真实认知）、`17`（对账执行真相），加全部基础设施 owner。认知主链 `02→17` 端到端贯通，门控信号中不再有常量 shim（R63）。

## 6. 更新规则

本文件是活 owner 参考。它必须在任何实质改变 owner 职责、完成度、边界或下一步的需求的同一次变更内更新
——与治理 `requirements/index.md` 和进度图相同的纪律。顶部"最近同步"行必须写明本文件所反映的最新需求。
英文配套版 `OWNER_GUIDE.md` 必须与本文件一起更新。
