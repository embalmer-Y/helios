# Helios 与人脑功能架构对照

> Status: Working Draft
> Role: scientific grounding and gap analysis
> Scope: 以功能角色而非器官等价为原则，对 Helios 各主要域与人脑相关功能系统做谨慎映射，并给出当前差距和 requirement 回链

## 1. 使用原则

本文件不主张“Helios 等于大脑”，也不把软件模块机械映射为单一脑区。这里采用的是功能角色比较法：

1. 先看系统解决的功能问题是否相似。
2. 再看实现机制是近似、替代，还是当前缺失。
3. 最后把差距回链到具体 requirement，而不是停留在口号式类比。

## 2. 证据等级

| 等级 | 含义 |
| --- | --- |
| A | 该结论有较成熟综述或经典论文支持，且与当前架构 concern 高度相关 |
| B | 该结论主要用于功能启发，具备一定文献支持，但不能直接推出软件实现细节 |
| C | 该结论主要是工程类比或设计假设，需要谨慎使用 |

## 3. 域级对照总表

| Helios 域 | 人脑相关功能角色 | 当前对应类型 | 当前完成度判断 | 主要差距 | 关联 requirement |
| --- | --- | --- | --- | --- | --- |
| `allostasis.py` + `neurochem.py` + `temporal_gate.py` | 预测性调节、异稳态维持、能量与节律约束 | 功能近似 | 中 | 仍偏状态修饰，尚未充分驱动主动性和思考延续 | R18 |
| `daisy_emotion.py` + `mood_tracker.py` | 情绪价态、行动准备、显著性调制 | 功能近似 | 中 | 情绪还未稳定转化为外化策略与长期偏好塑形 | R18 |
| `cognition/thinking_integration.py` + `phi.py` | 全局整合、工作空间式竞争与广播 | 功能启发 | 中低 | thought continuation 仍弱，行为真实性与内部分数脱节 | R17, R18 |
| `memory/memory_system.py` + `retrieval.py` + `autobiographical.py` | 分层记忆、情景/语义/自传连续性 | 功能近似 | 中 | directed retrieval 与自我连续性整合仍在迁移态 | R11, R18 |
| `regulation/` + `behavior_registry/` | 驱动、意动、行动倾向与能力约束 | 功能启发 | 中 | 主动 drive 尚未成为正式一等信号 | R18 |
| `helios_io/planning.py` + `limb.py` + `channel_gateway.py` | 执行控制、行动选择、效应器约束 | 工程替代 | 中 | 仍受 reply-first 历史路径影响，主动外化不足 | R09, R16, R18 |
| `personality.py` + governance 面 | 自我模型、长期特质稳定与更新 | 工程替代 | 中低 | 审计化身份演化闭环还不完整 | R10, R18 |
| `helios_evaluation/` | 元认知式自检与外部行为评估 | 工程替代 | 中低 | 评分真实性不足，缺少可靠诊断 provenance | R17 |

## 4. 关键专题比较

### 4.1 调节、情绪与生存性约束

人脑并不是先“生成回复”，再把情绪附加上去；情绪、异稳态和内稳态约束会先塑造显著性、行动准备和注意分配。对 Helios 而言，`allostasis.py`、`neurochem.py`、`daisy_emotion.py`、`mood_tracker.py` 已构成不错的工程底盘，但它们目前更多影响状态摘要，尚未稳定转化为主动思考压力和外化倾向。

启发：如果调节系统只改变 prompt 风格或阈值，而不改变 thought continuation 和 action tendency，它在功能上更像“装饰性情绪层”，而不是类脑调节层。

对应差距：

1. 主动 drive 仍弱，无法在无输入窗口中形成连续主观活动。
2. 情绪张力与外发强度、计划优先级之间的绑定不够强。

对应 requirement：R18。

### 4.2 记忆分层与自传连续性

脑科学中的记忆并不是单一缓存；情景记忆、语义记忆、自传连续性和工作记忆在功能上分化明显。Helios 的 `memory_system.py`、`retrieval.py` 和 `autobiographical.py` 已经接近这种分层思想，但 directed retrieval、未完成意图保留和自传连续性的 owner 边界还不够稳定。

启发：如果记忆只在用户输入时被检索，它更接近对话上下文缓存，而不是服务主观连续性的记忆系统。

对应差距：

1. recall intent 没有稳定牵引下一 tick 的思考延续。
2. 主动行为与自我演化结果尚未稳定沉淀进长期轨迹。

对应 requirement：R11、R18。

### 4.3 执行控制与对外行动

人脑的执行控制并不是纯文本生成，它包含候选竞争、抑制、择优和外周执行约束。Helios 的 `planning.py`、`interaction_policy.py`、`limb.py` 和 `channel_gateway.py` 是这一功能角色的工程替代物。R16 已经把 channel 边界清理到正式 ops 层，但主动候选如何进入 planner/policy 并被安全外化，还未完全恢复。

启发：如果主动候选形成后仍只能被动等待外部输入触发输出，执行控制就只完成了一半。

对应差距：

1. proactive provenance 尚未成为正式 planner/policy 语义。
2. policy 拒绝后的内部 trace 还不稳定。

对应 requirement：R09、R16、R18。

### 4.4 主观连续性与全局整合

关于意识的工程比较，最安全的做法不是宣称某个文件等于某个脑区，而是看系统是否具备“跨域整合、维持主题、在时间上延续并可影响行为”的能力。Helios 的 `thinking_integration.py`、`thinking.py`、`phi.py` 已承担这类角色，但最近 5 分钟评估暴露出一个关键问题：内部维度分数偏高，而用户可见行为仍弱。这说明当前系统在“整合是否真实影响行为”这个点上仍不够强。

启发：没有行为后果的内部激活，不应被高估为接近类脑主观连续性。

对应差距：

1. evaluation 还没有把 internal activation 与 external consequence 牢固绑定。
2. thought continuation 与 proactive externalization 仍断裂。

对应 requirement：R17、R18。

### 4.5 自我模型与身份治理

人类自我并不是一段静态 persona 文本，而是跨时间维持的自我模型、社会约束和更新机制。Helios 的 `personality.py`、`personality_contract.py` 和持久化数据面还处在工程替代阶段：它们已经提供特质和表述边界，但“如何被允许更新、如何审计、如何保留连续性”仍需更严格 owner 化。

启发：如果身份状态可以被 prompt 或一次交互直接改写，那更像临时角色设定，而不是自我治理。

对应差距：

1. identity revision history 与 self-evolution trace 仍未完整收敛。
2. 主动行为对长期自我模型的影响缺少治理路径。

对应 requirement：R10、R18、R19。

## 5. 当前最关键的类脑差距

按当前工程优先级，而不是按宣传效果，最关键的差距如下：

1. 评估真实性不足：系统可能在行为弱时仍获得过高内部健康分，导致优化方向失真。
2. 主动性不足：内部驱动未稳定转化为连续思考和受控外化。
3. owner/boundary 不够显式：会反复诱发 shortcut 和职责漂移。
4. 自我演化闭环不完整：记忆、治理、主动行为还没有形成长期可审计轨迹。

对应 requirement：R17、R18、R19。

## 6. 明确不直接追求的模拟范围

以下内容不应被当前文档误读为 Helios 的直接目标：

1. 精确神经动力学模拟。
2. 脑区级生物真实性复刻。
3. 突触学习规则或真实神经递质方程重建。
4. 以“看起来像脑区命名”为目的的模块重命名。

Helios 当前追求的是功能角色上的更强对齐，而不是生物细节同构。

## 7. 参考文献与依据类型

以下文献主要用于功能角色 grounding，而不是为某个具体代码实现背书：

1. Miller EK, Cohen JD. An integrative theory of prefrontal cortex function. Annual Review of Neuroscience, 2001.
   - 依据类型：A
   - 用途：支持执行控制、目标维持、候选竞争与行为调节的比较。
2. Squire LR. Memory systems of the brain: a brief history and current perspective. Neurobiology of Learning and Memory, 2004.
   - 依据类型：A
   - 用途：支持记忆分层和不同记忆系统功能角色区分。
3. Dehaene S, Changeux JP. Experimental and theoretical approaches to conscious processing. Neuron, 2011.
   - 依据类型：A
   - 用途：支持“全局整合与可广播性”作为意识相关工程比较维度，而不是单点脑区等价。
4. Sterling P. Allostasis: a model of predictive regulation. Physiology & Behavior, 2012.
   - 依据类型：A
   - 用途：支持异稳态和预测性调节对整体行为组织的重要性。
5. Northoff G, Heinzel A, de Greck M, Bermpohl F, Dobrowolny H, Panksepp J. Self-referential processing in our brain: a meta-analysis of imaging studies on the self. NeuroImage, 2006.
   - 依据类型：B
   - 用途：支持自我模型比较时应关注跨时间自我相关处理，而非静态 persona 文本。
6. Pessoa L. A network model of the emotional brain. Trends in Cognitive Sciences, 2017.
   - 依据类型：A
   - 用途：支持情绪与执行、认知控制和行为调节的网络化耦合，而非孤立情绪模块观。

## 8. 对后续 requirement 的直接约束

1. R17 必须把“内部激活是否真实带来行为后果”作为评分真实性核心。
2. R18 必须恢复由调节、记忆和意动共同塑造的主动思考与主动外化。
3. R19 必须把 owner 与 shortcut 约束写清，否则任何类脑比较都会重新退化成口号。
4. R20 后续扩写时可以继续补文献，但不得改变这里已经明确的克制比较原则。
