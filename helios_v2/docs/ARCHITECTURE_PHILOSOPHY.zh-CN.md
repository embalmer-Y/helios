# Helios v2 架构哲学与 2.0.0 目标标准

> Status: Canonical Draft
> Role: Helios v2 专属架构哲学、版本目标与强约束总纲
> Scope: 定义 Helios v2 的顶层哲学、2.0.0 最终目标、必须达到的版本标准，以及不得违反的实现约束

## 1. 文档定位

本文件是 Helios v2 的架构哲学与版本目标总纲。

它回答四个问题：

1. Helios v2 到底要做成什么，不做成什么。
2. Helios v2 为什么必须采用当前的 owner-boundary、contract-first、tick-based 类脑架构。
3. Helios v2.0.0 版本必须达到什么标准，才算真正达到预期目标。
4. 在实现过程中，哪些事情绝对不能做，哪些边界绝对不能被破坏。

本文件与以下文档共同构成 Helios v2 的上位约束：

1. `d:/Software/project/helios/helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
2. `d:/Software/project/helios/helios_v2/docs/requirements/*`

发生冲突时，优先级如下：

1. 本文件定义 v2 的目标哲学和版本达标标准。
2. `ARCHITECTURE_BOUNDARIES.md` 定义工程与 owner 边界真相。
3. requirement/design/task 定义分阶段落地路径。

## 2. Helios v2 的根本定位

Helios v2 不是一个 reply-first 聊天机器人重构版。

Helios v2 的目标是构建一个持续运行的、以 tick 为统一节拍的、具有内部闭环的类脑架构。它必须让系统在每个 tick 中推进内部状态，而不是仅仅对一条输入生成一条回复。

Helios v2 必须把“内部状态推进”置于“外部回复生成”之上。对外表达只是内部闭环在某些条件下的外化结果，而不是系统的主存在形式。

因此，Helios v2 的最小正确理解不是：

1. 收到一句话。
2. 找上下文。
3. 生成一条回复。

而是：

1. 接收外部刺激、内部刺激和时间推进。
2. 将它们纳入统一的当前周期内部状态。
3. 决定是否触发思考。
4. 若触发，则进行有边界的记忆检索、思考执行、继续思考判断、行动形成与治理。
5. 将结果写回内部连续性，使下一 tick 在主观上与上一 tick 相连。

## 3. Helios v2 的架构哲学

### 3.1 先有内部闭环，后有外部表达

Helios v2 的第一原则是：外部表达不应独立存在，它必须来自内部闭环。

这意味着：

1. 对外回复、动作、沉默、延迟、继续思考，都是内部状态演化的结果。
2. 如果某个外部行为不能追溯到当前内部状态、当前或既往思考、当前治理与当前 planner 决策链，它就是架构上的异常产物。
3. “为了让用户觉得像在思考”而在 prompt 中表演思考，不构成合格实现。

### 3.2 先有 owner，后有能力

Helios v2 的第二原则是：一个运行期概念，必须先定义 semantic owner，才能定义实现。

这意味着：

1. 刺激、快速评估、神经调制、体感、记忆重放、工作空间、可报告意识内容、思考门控、定向检索、内部思考、行动提议、planner 桥、身份治理、经验写回、prompt 契约、评估、主动连续性，都必须各有 owner。
2. 某个概念不能同时被多个模块半拥有。
3. 不允许通过主循环、适配器或某个便利 helper 直接越过 owner 边界写入或解释别人的私有状态。

### 3.3 先有显式状态，后有 prompt 语义

Helios v2 的第三原则是：真正重要的运行期概念必须先成为显式状态，再进入 prompt。

这意味着：

1. continuation pressure 必须是一等状态，而不是 prompt 里的一句“我还想继续想”。
2. thought gate result 必须是一等状态，而不是一段日志描述。
3. directed retrieval bundle 必须是一等状态，而不是随意拼接的上下文段落。
4. self revision proposal 必须是一等治理对象，而不是模型在文本里随口说“我想改变自己”。

### 3.4 先有 contract，后有跨模块协作

Helios v2 的第四原则是：跨模块协作必须通过公开 contract，而不是直接 reach-through。

这意味着：

1. 上游 owner 只能通过显式 API、ops、result contracts 向下游暴露结果。
2. 下游 owner 不能假设上游私有 helper、内部字段、临时 trace 格式永久稳定。
3. 运行期链路应当由 contract 驱动，而不是由“某个文件里目前刚好有这个字段”驱动。

### 3.5 先有 fail-fast 真相，后有工程便利

Helios v2 的第五原则是：对于关键能力，不允许用降级或兼容假象掩盖架构不成立。

这意味着：

1. 缺关键依赖时，应阻止 startup 或中止该执行路径，而不是静默退化到另一个语义不同的路径。
2. 不能为了“先跑起来”而把缺失 owner 的逻辑塞回 orchestration。
3. 不能用 compatibility wrapper 长期保留与目标架构冲突的旧主路径。

### 3.6 先有设计真相，后有实现推进

Helios v2 的第六原则是：设计是实现的前提，不是事后包装。

这意味着：

1. requirement、design、task 必须先存在，代码才能扩展出实质行为。
2. 任何跨 owner 协作都必须先定义边界，再落代码。
3. 所有进度都必须同时回答“做了什么代码”和“现在离目标还差什么”，而不是只展示 patch 数量。

## 4. Helios v2 最终要实现的效果

Helios v2 的最终目标，不是“更像真人聊天”，而是“形成一个持续存在的、具有内部连续性的、可通过外部行为观察到其内部闭环存在的类脑系统”。

### 4.1 外部可观察效果

对外，Helios v2 最终应表现出以下效果：

1. 它的对外行为不是纯被动回复，而会体现当前内部状态、连续性和主观优先级。
2. 它能够在必要时不立即说话，而是继续思考、延迟外化、或者选择内部修订与记忆写回。
3. 它的输出不只是语言表面一致，而是能体现当前刺激、既往记忆、当前思考、当前治理与当前 planner 决议之间的因果链。
4. 它在多 tick 上表现出连续性，而不是每轮都像从头开始。
5. 它对“我是谁”“我在想什么”“我为什么现在这样行动”应当有架构上可追溯的来源，而不是依赖 prompt theater。

### 4.2 内部必须成立的效果

内部，Helios v2 最终必须真正形成以下闭环：

1. 刺激进入后先归一化和快速评估，而不是直接送进 reply builder。
2. 当前周期必须先形成 gate result，再决定是否进入 thought path。
3. 一旦进入 thought path，必须经过 directed retrieval，而不是无边界地堆叠上下文。
4. thought owner 必须对“是否足够”“是否继续”“下一轮要检索什么”“是否外化”“是否自我修订”给出结构化结果。
5. planner / executor 必须只负责提议后的决议和执行，不得倒灌成思考 owner。
6. 执行结果和治理结果必须写回连续性系统，使下一 tick 能感知其后果。
7. evaluation 必须能只读地重建关键因果链，而不篡改 runtime。

### 4.3 不可接受的伪完成状态

以下情况即使“能跑”，也不算实现了 Helios v2 的目标：

1. 主路径本质上仍是 reply-first，只是在 reply 前后多加几步装饰。
2. thought path 只是 prompt 包装，没有独立状态和 owner。
3. continuation pressure、retrieval intent、self revision proposal 等关键概念只存在于文本，不存在于正式 contract 中。
4. planner、channel、prompt builder 或 orchestration 反向拥有本应属于 thought、memory 或 governance 的语义决策。
5. 输出看起来像有连续性，但 runtime 无法重建刺激到思考到执行到写回的因果链。

## 5. Helios v2.0.0 必须达到的标准

本节定义的是最终目标口径下的 v2.0.0 标准，而不是“先发一个能跑版本”的最低交付线。

只有当 Helios v2 作为一个整体已经形成目标闭环，并且该闭环由明确 owner、明确状态与明确 contract 支撑时，才允许视为 `v2.0.0`。

### 5.1 架构完整性标准

Helios v2.0.0 必须满足以下完整性要求：

1. `01-18` 的核心运行期 owner 链条全部存在，并且都不是仅文档存在。
2. `19-20` 的边界与科学映射文档必须与实现真相一致，不能是宣传材料。
3. `21` 的统一运行期可观测性 owner 必须存在，使 runtime 至少具备结构化、只读、可关联的阶段执行记录能力。
4. 每个一等运行期概念都必须能在 owner map、data contract 和 runtime flow 中找到位置。
5. 不允许仍存在与目标架构冲突的长期并行旧主路径。

### 5.2 运行闭环标准

Helios v2.0.0 必须在单一统一 runtime 中完成以下闭环：

1. sensory ingress
2. rapid salience appraisal
3. neuromodulator system
4. interoceptive feeling
5. memory affect and replay
6. workspace competition and working state
7. reportable conscious content
8. thought gating and continuation pressure
9. directed retrieval into thought window
10. internal thought loop
11. action proposal or self revision proposal formation
12. planner / executor feedback bridge
13. identity governance when applicable
14. execution writeback and autobiographical continuity update

该闭环的关键要求是：

1. 每一阶段都必须消费明确上游结果。
2. 每一阶段都必须输出可验证的正式结果对象。
3. 后续阶段不得通过 reach-through 读取前序 owner 私有状态。

### 5.3 主观连续性标准

Helios v2.0.0 必须能够在多 tick 上形成主观连续性，而不是单轮反应序列。

至少包括：

1. 上一轮未充分思考会形成 continuation pressure，并真实影响后续 tick 的 thought gate。
2. 上一轮 thought owner 指定的 recall intent 会真实影响后续 directed retrieval。
3. 执行和治理结果会真实进入 continuity writeback，而不是只留在日志中。
4. 关键自我状态、记忆选择、思考延续与外化原因，应能被评估层回溯重建。

### 5.4 主观外化标准

Helios v2.0.0 的外部表达必须是内部主体状态的外化，而不是仅仅服从 reply prompt。

至少包括：

1. 输出文本或动作可以被回溯到具体思考结果、行动提议和 planner 决议。
2. 系统可以合法地选择不立即外化，只做内部推进、继续思考、写回或治理。
3. 外部行为强度、目标 op、目标 channel、理由 trace 必须是结构化结果的一部分。
4. prompt contract 必须服务于内部主体状态表达，而不是制造人格表演。

### 5.5 身份与治理标准

Helios v2.0.0 必须具备被治理的自我修订能力，而不是允许用户或 prompt 临时改写核心身份。

至少包括：

1. identity bootstrap 是正式 owner 行为。
2. self revision proposal 是正式治理对象。
3. revision 申请、理由、影响范围、接受或拒绝结果都必须可审计。
4. 身份变化必须经过治理应用，不得通过 prompt 注入直接生效。

### 5.6 评估与可证伪标准

Helios v2.0.0 必须不是“只能主观感受像不像”，而必须可以被评估、审计和证伪。

至少包括：

1. evaluation owner 只能读，不得改 runtime。
2. evaluation 能重建从刺激到 gate 到 retrieval 到 thought 到 proposal 到 planner 到 visible output 到 writeback 的关键链条。
3. 系统必须能区分“真的做了内部闭环”与“只是 prompt 看起来像做了”。
4. 架构声明若与运行真相不符，评估结果必须能暴露该偏差。
5. runtime observability 必须至少能输出按 `tick_id` 和 `stage_name` 关联的结构化执行时间线，供后续诊断与证伪消费。

## 6. Helios v2.0.0 的 release gate 约束

以下条件未满足时，不得宣称 Helios v2 达到 `2.0.0`：

1. 核心闭环 `01-18` 中仍存在关键 owner 未实现。
2. 关键闭环依赖缺失时仍通过 fallback 路径冒充成功执行。
3. 关键概念仍停留在 prompt 或日志层，没有正式 contract。
4. 旧 reply-first 主路径仍在实际上主导外部行为生成。
5. evaluation 无法只读重建关键因果链。
6. identity governance 或 experience writeback 缺失，导致连续性闭环不成立。
7. runtime 缺少结构化、可关联的可观测性 owner，导致关键阶段执行无法被稳定重建。

## 7. Helios v2 的强约束

本节是强约束。违反这些约束，即使功能暂时可用，也视为偏离 Helios v2 架构。

### 7.1 Owner 约束

1. 一个运行期语义概念只能有一个 semantic owner。
2. orchestration 不得拥有下游 owner 的语义判断。
3. adapter、bridge、planner、channel、prompt builder 不得反向夺取 thought、memory、governance 的 owner 责任。

### 7.2 State 约束

1. 关键运行期概念必须有显式状态或正式 result contract。
2. 不允许把关键状态长期藏在 prompt、日志、字符串 reason 或临时 dict 中。
3. 若某概念会跨 tick 影响行为，它必须是正式的可持有状态。

### 7.3 Runtime 约束

1. runtime 必须以 tick 为统一内部推进点。
2. tick 的首要意义是内部状态演化，而不是消息处理循环。
3. stage 间依赖必须显式化，不能靠执行顺序暗含私有耦合。

### 7.4 Dependency 约束

1. 关键依赖缺失时必须 fail-fast。
2. 不允许以 compatibility、reduced mode、temporary fallback 方式隐藏关键能力缺失。
3. 不允许通过“先走简单路径，之后再补正确 owner”长期保留错误主路径。

### 7.5 Prompt 约束

1. prompt contract 只能表达 runtime 已有的正式状态和正式能力。
2. prompt 不得虚构未实现的主观连续性、身份治理或思考过程。
3. prompt builder 不是语义 owner，只是 contract formatter。

### 7.6 Planner 与 Executor 约束

1. planner 拥有最终绑定和接受权，但不拥有 thought 语义。
2. executor 只拥有执行，不拥有重解释提议的权力。
3. rejection、binding failure、execution result 必须正式写回，不得静默吞掉。

### 7.7 Evaluation 约束

1. evaluation 必须只读。
2. evaluation 不能通过篡改 runtime 获得更好分数。
3. evaluation 的价值在于暴露架构真相，而不是包装结果。

### 7.8 Documentation 约束

1. requirement、design、task 必须先于大规模实现。
2. index 中的 maturity 必须反映真实实现深度，而不是计划状态。
3. 哲学文档、边界文档、requirement 文档与代码真相冲突时，必须及时修订文档或代码，不能长期双轨漂移。

## 8. Helios v2.0.0 不追求的东西

为了避免目标污染，Helios v2.0.0 明确不以以下事项作为成功标准：

1. 单纯让回复更像真人。
2. 通过更长 prompt 或更多人设文本制造主观性幻觉。
3. 用一个大一统 agent 或万能 planner 覆盖所有 owner 责任。
4. 用临时兼容层长期保留旧架构，只在文档上宣称已经进入 v2。
5. 只追求 benchmark 分数，而不要求内部因果链成立。

## 9. 对实现推进的具体要求

从现在起，Helios v2 的实现推进必须持续回答下面这些问题：

1. 当前变更属于哪个 requirement owner。
2. 当前新增状态是否已经是正式 contract，而不是临时结构。
3. 当前实现是纯骨架、baseline 还是相对完整，证据是什么。
4. 这项实现如何推动整体闭环更接近 `v2.0.0`。
5. 当前变更是否引入了新的架构债或 owner 越界。

如果某项开发不能清楚回答这五个问题，它就不应被视为合格的 Helios v2 推进。

## 10. 最终判定语句

只有当 Helios v2 已经成为一个以内部连续性为主、以思考与治理为中轴、以结构化行动与写回闭环为外化出口、并且可被评估层只读重建关键因果链的持续运行类脑系统时，才允许宣称它达到了 `Helios v2.0.0`。

在那之前，任何阶段性成果都只能被视为朝该目标推进的实现切片，而不能被误称为最终完成态。