# Helios v2 Owner 指南（中文）

> 状态：活文档（owner 参考）。最近同步：R36。测试基线：486 passed（离线）。
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

认知主链端到端运行，但大多数前中段认知 owner（`03-07`、`09-10`、`12`）是 `baseline_real`，其
**输入仍是 composition 注入的确定性 shim**：契约、校验、测试都是真实的，但流入它们的值是固定的首版
常量，而非真实信号。给这些 owner 去 shim 是阶段 `P3` 的核心工作。当今真正由真实信号驱动的 owner 是
`02`、`08`、`11`（LLM）、`18`，以及基础设施 owner。

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
- 下一步：保护边界真相；无需去 shim。真实外部（网络）信号源随未来 channel driver 到来，不在此处。

### 2.3 `03` 快速显著性评估 — `helios_v2.appraisal`
- 完成度：`baseline_real`（自 R35 起,语义记忆装配下 novelty 维已真实；其余四维仍 shim）。
- 职责：每刺激的快速粗显著性（威胁/奖励/新颖/社会/不确定 + 聚合），经注入式 estimator。不拥有精细语义解释、记忆或路由。
- 在循环中的作用：紧接 sensory 塑造下游显著性；评估批次喂给调质与门控信号。
- 下一步（本 owner 的分阶段 P3 去 shim）：
  1. **R35 — 基于记忆的 novelty（已交付）。** `novelty` 维已是真实信号：`novelty = clamp(1 - max_similarity, 0, 1)`，其中 `max_similarity` 是 embed 后的刺激与任一已存经验 embedding 的最大余弦相似度（经 `34` embedding 网关 + `33` store 相似度检索）。`03` 定义窄协议 `MemorySimilaritySource` 并在 `MemoryGroundedDimensionEstimator` 中拥有 novelty 显著性映射；composition 注入 owner-neutral 的 `MemoryGroundedSimilaritySource`（返回原始余弦事实或 `None`），故 `03` 既不 import embedding 也不 import persistence owner。触发于语义记忆 opt-in（store + embedding 同时存在）；冷库/空刺激内容产出定义的最大 novelty `1.0`（空内容不调网关）；运行期 embedding/store 失败是 hard stop（无常量回退）。默认/recency-only 装配保持常量 novelty `0.6`。
     - **首版已知 caveat（跨语域比较）：** store 当前只存 `15` 的结果/连续性摘要，不存原始刺激文本，所以 R35 的 novelty 是把进来的*刺激输入*与过去的*结果摘要*（共享同一 embedding profile）比较。方向正确（共享内容会被余弦捕捉），但这是"输入 vs 摘要"的近似，不是严格的"输入 vs 输入"，不得过度宣称为精确的刺激新颖度。
  2. **方案 B — 同类可比的 novelty（后续切片）。** 持久化原始刺激文本流（`15`/`33` 扩展或专用刺激日志），使 novelty 在同一语域里"刺激 vs 历史刺激"比较，退休上面的跨语域 caveat。因为它触及回写/持久化 owner 而非 `03`，所以是独立需求。
  3. **其余四维（各自后续切片）。** 用各自合适的真实信号（轻量分类器或 LLM 打分）给 threat/reward/social/uncertainty 去 shim，一维一刀，使每个 estimator 可独立测试、owner 边界清晰。
  4. **聚合显著性。** 维度变真后，把常量 aggregate estimator 换成可学习或模型辅助的整体判断。
  5. **下游耦合。** novelty（及后续其余维）变真后，喂给去 shim 的 `04` 神经调质动力学模型与 `09` 门控，使真实显著性可度量地塑造门控阈值（FG-1/FG-2）；之后在 `04`/`05` 产出真实信号后做情感加权或时近加权的 novelty。

### 2.4 `04` 神经调质系统 — `helios_v2.neuromodulation`
- 完成度：`baseline_real`（语义记忆装配下水平已由 appraisal 推导；无状态）。
- 职责：独立建模的神经调质水平状态（DA/NE/5-HT/ACh/皮质醇/催产素/阿片 + 兴奋/抑制），含显式可学习参数类别。不拥有体感主观化或行动。
- 在循环中的作用：应当偏置门控阈值、检索、外化强度的调制层。
- 完成度细节：`36`（P3 第二刀去 shim）在语义记忆装配下把常量更新路径替换为 composition 提供的 `AppraisalDerivedNeuromodulatorUpdatePath`（遵循 owner 既有的 `NeuromodulatorUpdatePath` 协议；引擎与契约不变）。它先对 rapid-appraisal 批次按维度取最大聚合，再按 `clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)` 推导每个通道：多巴胺由 reward（外加弱 novelty）驱动、去甲肾上腺素由 novelty 与 uncertainty 驱动、皮质醇由 threat 驱动，其余通道回归各自 tonic 基线。推导是确定性、有界（无 NN、不发散）且**无状态**（不携带上一 tick 水平）。默认、纯时近、离线装配保留常量路径。Caveat：当前只有 novelty 是真实 `03` 驱动（R35），喂给 `04` 的其余四维显著性仍是首版常量，且 `04` 的水平尚未耦合进去 shim 的 `05`/`09`。
- 下一步：（1）双时间尺度 tonic/phasic 衰减，携带上一 tick 水平（依赖神经调质状态携带/检查点，属 `18`/`09`/`14` 状态检查点族）；（2）`P5` 用奖励预测误差（DA）与结果反馈学习有界 sensitivity 系数，保持方程形状；（3）跨通道耦合（已声明的 `cross_channel_coupling_strength` 类别），超越首版独立映射；（4）下游耦合，使真实 `04` 状态可度量地塑造去 shim 的 `05` 体感与 `09` 门控（FG-1/FG-2）；（5）给 `03` 其余四维去 shim，使所有神经调质驱动皆为真实。

### 2.5 `05` 内感受体感层 — `helios_v2.feeling`
- 完成度：`baseline_real`（输入仍 shim）。
- 职责：从神经调质状态 + 内部信号产出主观身体感受向量（valence/arousal/tension/comfort/fatigue/pain/social-safety）；仅软调制输出。不拥有调质状态或记忆。
- 在循环中的作用："我的身体状态感觉如何"层，喂给可报告意识与连续性。
- 下一步（P3）：从真实 `04` 状态构造真实感受；让体感真实地在下游产生因果（FG-2），而非固定向量。之后：持久化/恢复感受状态（P2 检查点切片）。

### 2.6 `06` 记忆情感与重放 — `helios_v2.memory`
- 完成度：`baseline_real`（输入仍 shim；`33` 已有耐久 store，但 `06` 形成仍在进程内造记忆）。
- 职责：情感标记的记忆形成与重放候选surfacing，含强制巩固约束。不拥有检索规划、工作空间晋升或身份回写。
- 在循环中的作用：形成情景/情感记忆并向工作空间供给重放候选。
- 下一步（P2/P3）：把 `06` 记忆条目接入 `33` 耐久 store（形成 → 持久化 → 与 `10` 共享同一耐久底座），使记忆形成不再每 tick 凭空造。再从真实感受/失配证据去 shim 形成。

### 2.7 `07` 工作空间竞争与工作态 — `helios_v2.workspace`
- 完成度：`baseline_real`（输入仍 shim）。
- 职责：候选集竞争与短时工作态保持；记忆衍生内容的晋升边界。不拥有意识承诺或检索。
- 在循环中的作用：注意力瓶颈（FPN 式竞争），决定什么进入可报告意识。
- 下一步（P3）：上游候选变真后做真实竞争打分（可学习/注意力式 scorer）；保持 owner 纯净同时增大下游影响。

### 2.8 `08` 可报告意识内容 — `helios_v2.consciousness`
- 完成度：`deep_real`。
- 职责：从工作空间输出承诺全局可报告意识内容（或显式不承诺），含非 reach-through 的上游内容素材边界。不拥有思考生成或门控。
- 在循环中的作用："我本周期意识到什么"的承诺，供门控与 prompt 装配消费。
- 下一步：把承诺内容更强地绑到下游行为/诊断后果；深化而非去 shim。

### 2.9 `09` 思考门控与延续压力 — `helios_v2.thought_gating`
- 完成度：`baseline_real`（输入仍 shim）。
- 职责：思考窗口触发决策与多 tick 延续压力 carry 的唯一 owner；紧凑门控可观测。不坍缩进检索或思考生成。
- 在循环中的作用：决定一个 tick 是否触发思考路径，并把延续压力向前 carry。
- 下一步（P3 + wave_B）：用真实显著性/情感/延续信号驱动门控；深化多 tick carry。之后：跨重启持久化/恢复延续压力（P2 检查点切片）。

### 2.10 `10` 定向检索进思考窗口 — `helios_v2.directed_retrieval`
- 完成度：`baseline_real`（规划仍 shim；启用持久化/语义记忆时候选来源已真实）。
- 职责：检索查询规划、分层选择、有界思考窗口 bundle 装配的唯一 owner。不拥有记忆持久化或思考生成。
- 在循环中的作用：装配思考 owner 推理所依据的有界记忆窗口。
- 下一步：随 `33`/`34` 候选 provider 已真实（recency，再语义）。剩余：从真实上游门控深化查询规划与 recall-intent 收口；把检索意图接到后续连续性（wave_B）。

### 2.11 `16` 具身 prompt 契约 — `helios_v2.prompt_contract`
- 完成度：`baseline_real`。
- 职责：为 `thought` 与 `outward_expression` 消费者装配具身主观 prompt 契约；反表演约束；能力/权限边界渲染。不拥有思考执行、planner 权限或治理。
- 在循环中的作用：把承诺状态 + 检索 + 能力边界格式化成思考 owner 与外化 owner 消费的契约。
- 下一步：保持其为契约 formatter（绝不变成 reply-first 行为 owner）；随真实上游信号到来丰富层。仅深化。

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

### 2.15 `12` 行动提议与外化契约 — `helios_v2.action_externalization`
- 完成度：`baseline_real`。
- 职责：思考来源提议归一化、外化契约发布、桥级拒绝语义的唯一 owner。不拥有 planner 接受或 executor dispatch。
- 在循环中的作用：把一个思考的行动提议归一化成 planner 桥消费的契约。
- 下一步（wave_C）：在真实外部行动收口于下游深化时保持契约真相稳定。

### 2.16 `13` planner-executor 反馈桥 — `helios_v2.planner_bridge`
- 完成度：`baseline_real`（planner 判断真实；默认装配里 channel-state 快照仍 shim，channel-bound 装配里则真实）。
- 职责：提议到决策的桥接、正式拒绝/执行结果发布、归一化桥反馈的唯一 owner。拥有最终绑定/接受，不拥有思考语义；不拥有传输或反馈持久化。
- 在循环中的作用：把归一化提议变成 accept/reject/execute 决策；对内部 tick 发布 `no_actionable_proposal`。
- 下一步（wave_C）：超越本地 CLI 的真实外部 channel 执行；更丰富的主动 provenance 进入行动选择。

### 2.17 `14` 身份治理与自我修订 — `helios_v2.identity_governance`
- 完成度：`baseline_real`。
- 职责：自我修订治理、身份状态变更、主动治理压力、正式修订结果发布的唯一 owner。不拥有思考生成、人格投射或审计持久化。
- 在循环中的作用：治理一个自我修订提议是否接受，并应用受治理的身份变更。
- 下一步（wave_B / P6）：更深的长程受治理自我演化（发展性，而非仅审计补丁）；跨重启持久化/恢复身份状态（P2 检查点切片）；最终落地 P6 的受治理自我修订路径。

### 2.18 `15` 经验回写与自传巩固 — `helios_v2.experience_writeback`
- 完成度：`baseline_real`（其连续性流现已经 `33` 持久化）。
- 职责：执行结果回写、连续性证据 packet、巩固候选 handoff 的唯一 owner。不拥有 planner/治理决策或原始存储后端。
- 在循环中的作用：把每 tick 结果归类成连续性 packet 并喂 `15 → 06` 闭环；其流即 `33` 所持久化的。
- 下一步（wave_B）：更强的长程 carry 与再入；`06` 共享耐久底座后做更丰富的巩固。

### 2.19 `18` 主动性自治与主动演化 — `helios_v2.autonomy`
- 完成度：`deep_real`（`relatively_complete`；自 R29 起接真实认知；含 `24` 长程连续性线程层）。
- 职责：主动驱动整合、有界 disposition 选择、延迟连续性发布、长程连续性线程（复现强化、冲突仲裁、owner 拥有的 `LongHorizonContinuityState`）。可语义地请求主动外化，但绝不执行 channel 路径。
- 在循环中的作用：把真实认知整合成主动 disposition（行动 → externalize，无行动 → reflect/defer），并跨 tick 形成/强化连续性线程。
- 下一步（wave_B）：超越有界 carry 的更丰富长程动机演化；更锐利的连续性 key 方案；跨重启持久化/恢复长程状态（P2 检查点切片）。

### 2.20 `17` 评估保真与诊断 provenance — `helios_v2.evaluation`
- 完成度：`baseline_real`（只读；自 R32 起对账执行真相；消费 `23` 时间线）。
- 职责：证据驱动评估、后果绑定路径结论、执行真相对账（`corroborated`/`discrepant`/`unverifiable_no_timeline`）、诊断 provenance 发布的唯一只读 owner。不变更任何运行期状态。
- 在循环中的作用：最后一个阶段；重建内部到可见的因果链，现在还把自报结论对账内核执行时间线以证伪。
- 下一步：非确定性认知产出可变路径后做更丰富的 discrepancy 分类与打分深度；preserved-vs-resolved-vs-degraded 连续性对账（wave_B）；artifact 的跨运行耐久比较（依赖 P2）。

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
- 作用：唯一持有完整装配真相的地方；拥有 `CANONICAL_STAGE_ORDER` / `CHANNEL_BOUND_STAGE_ORDER` 与 owner-neutral bridge。
- 下一步：随 owner 去 shim，用 owner 真实的跨 owner 契约替换首版 bridge；保持装配不含认知策略。

### 3.3 `25` LLM 推理网关 — `helios_v2.llm`
- 完成度：`infra_done`。
- 职责：后端中性请求/完成契约、命名 profile registry、注入式 provider 协议 + 首版 OpenAI-compatible provider（懒加载 SDK）、网络无关静态 readiness、opt-in live probe。不拥有认知；绝不解释完成文本。
- 作用：`11` 思考 owner 消费的能力；经 composition 绑定逐消费者 profile。
- 下一步：随这些 owner 产生真实生成需求，新增绑定消费者（例如 `13` 工具调用规划、`14` 自我修订起草）。

### 3.4 `30` channel driver 子系统 — `helios_v2.channel`（+ `31` CLI driver — `helios_v2.channel.drivers.cli`）
- 完成度：`infra_done`（框架 + CLI driver 真实；opt-in；非默认运行时）。
- 职责：Linux-driver 风格的传输 owner——统一 `ChannelDriver` 协议、registry、NAPI 式有界入站 drain（发出带 QoS 的 `RawSignal`）、有界出站 dispatch、真实逐 driver channel 状态、fail-fast readiness。仅传输：非归一化（`02`）、显著性（`03`）、选择（`13`）或内容塑形（`16`）。
- 作用：opt-in channel-bound 装配下，本地 CLI 往返端到端运行（operator 输入 → 刺激 → 认知 → 外化决策 → sink）。
- 下一步（wave_C）：真实外部（网络）driver（QQ/语音/视觉）以及把 channel-bound 装配设为默认运行时；两者皆后续需求。

### 3.5 `33` 耐久经验存储 — `helios_v2.persistence`
- 完成度：`infra_done`（opt-in）。
- 职责：`PersistedExperienceRecord`/`PriorExistenceSnapshot` 契约、注入式后端协议（SQLite 文件 + 内存 double）、`ExperienceStore` facade（append / recent-N / count / snapshot / 相似度检索）、recency + 语义候选 provider。耐久追加 `15` 连续性流；确定性 recency 或余弦相似度再入 `10`。自身绝不 embed 文本；绝非权威 owner 间传输。
- 作用：给系统跨重启存活的记忆（FG-5.1）；持久化经验重新进入思考窗口。
- 下一步（P2）：`18`/`09`/`14` 的最新态检查点/恢复；把 `06` 记忆条目接入 store；之后做巩固/遗忘策略与 P5 学习的耐久底座。

### 3.6 `34` embedding 推理网关 — `helios_v2.embedding`
- 完成度：`infra_done`（opt-in）。
- 职责：后端中性 embedding 请求/结果契约、命名 profile registry、注入式 provider 协议 + 懒加载 OpenAI-compatible provider、fail-fast 网关、网络无关静态 readiness、opt-in live probe。不拥有认知；绝不解释向量。
- 作用：把文本变成向量，使 store 能按语义相似度排序经验；query/记录 embedding 由 composition 注入进 store（store 不依赖此 owner）。
- 下一步（P3 铰链）：喂 `03` novelty-from-memory（距最近存储记忆的距离）；pre-semantic 记录的重 embed/回填；规模上来后 ANN 索引。

---

## 4. 文档 owner

### 4.1 `19` 架构边界与 owner 文档
- 完成度：`docs_owner`。
- 职责：让 `ARCHITECTURE_BOUNDARIES.md`（及本 owner 图）与运行真相对齐——owner 边界、允许依赖、迁移注记、禁止捷径。
- 下一步：在每次 owner-wave 收口的同一变更内更新边界真相（当前已跟踪到 R34）。

### 4.2 `20` 脑架构对比与科学接地
- 完成度：`docs_owner`。
- 职责：让 `BRAIN_ARCHITECTURE_COMPARISON.md` 对齐——克制的脑功能类比、证据类别、显式非目标、gap 分析、owner-wave 路线图。
- 下一步：随 owner wave 收口收窄/退休 gap；让 wave 路线图与哲学文档的阶段路线图对齐。

---

## 5. 全系统视角（替代已退休的 distance 快照）

本节吸收了原先存放于已退休的 `TOTAL_DISTANCE_TO_FINAL_GOAL.md` 与
`REQUIREMENT_DISTANCE_TO_FINAL_GOAL.md` 的"距终局目标距离"聚合视角，现以活文档形式保留于此。

1. 系统在架构上真实、首版级别 owner 完整。它尚未达到终局完成态。
2. 当前最重的剩余运行期距离是 `03-07`/`09-10`/`12` 的去 shim（阶段 `P3`）与外部执行收口（`13`/`16`，wave_C）。
3. `wave_A_behavioral_truth`（评估证伪）随 R32 基线收口。`P2`（耐久记忆）随 R33 开篇，并随 R34 获得语义召回。
4. 下一批最高杠杆动作是：真实 `03` novelty-from-memory（P3 第一刀，基于 R34 构建），以及 P2 其余部分（状态检查点/恢复；`06` 接入耐久底座）。
5. 当今真正由真实信号驱动的 owner 是 `02`、`08`、`11`、`18`，加全部基础设施 owner；其余皆为诚实的 baseline，等待各自的去 shim wave。

## 6. 更新规则

本文件是活 owner 参考。它必须在任何实质改变 owner 职责、完成度、边界或下一步的需求的同一次变更内更新
——与治理 `requirements/index.md` 和进度图相同的纪律。顶部"最近同步"行必须写明本文件所反映的最新需求。
英文配套版 `OWNER_GUIDE.md` 必须与本文件一起更新。
