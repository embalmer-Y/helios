# Requirement 09 - Thought-to-Action Op Bridge

## 1. Background and Problem

当前 thought 与 action 之间的桥接仍受旧设计限制：

1. `cognition/preconscious.py` 产生的 proposal 被限制为 `internal_only`。
2. thought 结果不能正式提议对外 op 和参数。
3. planner 目前主要消费 policy 产生的 proposal，而不是 thought owner 的结构化行动结果。
4. 输出强度还没有成为 action proposal/decision 的正式字段。
5. 真实 runtime trace 仍出现“thought LLM 已输出 JSON 形态内容与明确外向意图，但 `thought_cycle.action_proposal` 仍为空”的情况；这说明 structured thought decision 到正式 bridge owner 的收口尚未稳定闭合。

这使得“思考后决定采取行动”这一类脑路径无法成立。

## 2. Goal

建立一个受控的 thought-to-action op bridge，使思考结果可以提议结构化 op、参数和输出强度，但仍由 planner、policy、executor 和 channel capability 共同决定是否允许外化以及如何执行。

R09 的最终目标进一步明确为：运行时对用户可见外部输出不再保留独立的 passive 承接/补写 owner path；所有用户可见外化都必须统一经由主路径处理，即 `stimulus ingress -> internal thought / thought action proposal -> planner / executor / channel`。外部刺激仍可作为思考触发来源存在，但不再允许并行的 passive reply producer 与主路径竞争 owner。

## 3. Functional Requirements

### 3.1 Thought Action Proposal

1. thought result 必须允许包含结构化 action proposal。
2. action proposal 至少包含：
   - behavior or intent
   - preferred op
   - params
   - target constraints
   - outbound intensity in `[0, 1]`
   - reason trace
3. LLM 可以提议 op + params + candidate channels + outbound intensity，但不得直接执行。
4. `ThoughtCycleResult` 必须成为 thought-origin action proposal 的正式 owner；不得只把 proposal 留在 `preconscious` 或其它旁路模块。
5. 若当前 tick 形成 thought-origin action proposal，主循环后续阶段必须优先消费该 proposal，再决定是否进入其它外化候选路径。
6. thought-origin action proposal 必须显式区分：
   - internal action proposal
   - external action proposal
7. 即使最终未执行，该 proposal 也必须以结构化形式写入 trace/state，供 planner rejection、审计和测试读取。
8. planner 可以治理、归一化和拒绝 thought-origin proposal，但不得长期以纯启发式后处理代替 LLM 对 `requested_op`、`candidate_channels` 与 `outbound_intensity` 的明确选择。
9. 若 proposal 目标是用户可见 channel 输出，则最终外发文本或等价 payload 必须已经存在于 thought-origin `params` / `op_params` 中；不得再由 reply pipeline 二次生成自然语言文案。
10. 若 internal thought LLM 已返回可解析的 structured JSON，运行时必须把 `thought_text`、`action_proposal`、`action_explicit` 三者一致落入状态与 trace；不得出现 thought 文本保留了 JSON 语义而 `action_proposal` 静默丢失的情况。
11. 对用户可见输出而言，外部输入只负责形成 stimulus / context，不再拥有独立的 passive reply owner 路径；是否外发、外发什么内容、以及通过哪个 op/channel 外发，最终都必须由主路径中的 thought-origin proposal 或其他正式上游 owner 决定。

### 3.2 Planner Governance

1. planner 必须对 thought-origin proposal 执行 schema、capability、channel availability 和 governance 校验。
2. planner 必须能够拒绝无效或越权 proposal，并记录 rejection reason。
3. planner 必须支持对 outbound intensity 的限制、裁剪或归一化。
4. planner 不得把不完整的 thought-origin proposal 隐式补齐为旧 reply-only send-text path。
5. planner rejection trace 至少必须包含：origin thought id、requested op、candidate channels、rejection reason、normalized intensity 或拒绝前 intensity。

### 3.3 Executor and Channel Ops

1. executor 必须能消费包含 op、params 和 outbound intensity 的决议。
2. channel 层必须支持基于 op schema 的执行，而不仅是简单 send text。
3. 行动执行结果必须回写为统一反馈事件。
4. 外部执行成功时，反馈事件必须可追溯到 originating thought id、proposal id、decision id 和 selected op。
5. 若执行器因为 channel binding 或 op 输入不合法而拒绝执行，该失败必须保留结构化 rejection trace，而不是静默回退。
6. 若系统存在可用输出 channel，thought prompt 必须把 channel 输入/输出语义、supported ops 和参数格式提供给 LLM；不得长期以 `no_channel_ops_available` 运行。

### 3.4 Internal vs External Actions

1. thought result 可以提议内部行动，也可以提议对外行动。
2. 不再把 thought-origin proposal 永久限制为 `internal_only`。
3. 若某个 proposal 被治理规则判定只能内部执行，系统必须明确记录约束原因。
4. 本 requirement 不要求删除 `preconscious`，但若其继续存在，角色只能是 thought-origin proposal 的放大、筛选或社会性外化辅助，不得继续充当唯一 thought-to-action bridge owner。
5. R09 收口后，运行时正式 external thought-origin action candidate 的唯一 owner path 必须是 `ThoughtCycleResult.action_proposal -> thought_action_bridge`；`preconscious` 不得再独立生产 external `thought_action` proposal。
5. passive reply fallback 不得冒充 thought-origin action bridge；两者必须在 owner path 和 trace 中可区分。
6. `reply_message` 只是行为名之一，不再意味着“由 reply prompt 负责生成文本”；它的 `outbound_text` 也必须由 thought-origin action proposal 或其他正式上游 owner 给出。
7. R09 最终收口时，旧 passive 承接路径只允许保留 stimulus ingress、history write、SEC / memory 等非外发辅助语义；不得再保留任何能够直接产生用户可见外部文案的并行 owner。

## 4. Non-Functional Requirements

1. action proposal 和 decision 必须可追溯到 originating thought。
2. planner rejection 必须可解释，便于调试和审计。
3. 旧 `internal_only` 兼容层不是必须目标，允许直接替换。
4. channel op 扩展必须保持 schema 明确，不得退回隐式字符串参数。
5. R09 的最终实现必须使 runtime 能直接回答“这是 thought 直接提出的行动，还是 policy / passive fallback 产生的行动”。
6. R09 的最终实现必须使 runtime 能直接回答“这条用户可见输出是否完全经由主路径产生”，并且答案不能再依赖被动承接并行路径或 reply helper 补写。

## 5. Code Behavior Constraints

1. 不得保留 `internal_only` 作为 thought-origin proposal 的永久硬约束。
2. 不得让 LLM 绕过 planner / executor 直接操作 channel。
3. 不得让 outbound intensity 只存在于 prompt 或日志中。
4. 不得继续扩展 reply-only send-text 路径作为唯一外化手段。
5. 不得让 `ThoughtCycleResult.action_proposal` 长期保持“字段存在但主循环不消费”的空壳状态。
6. 不得让 `preconscious` 成为 thought-origin action proposal 的唯一生产 owner。
7. 不得让 `preconscious` 在最终 runtime 中继续以独立 producer 身份生成 external `thought_action` proposal，与 `ThoughtCycleResult.action_proposal` 并列竞争 owner 语义。
7. 不得在 thought-origin proposal 被拒绝后，未经显式策略判断就直接退回 passive direct reply。
8. 不得在 accepted `reply_message` decision 缺失 `outbound_text` 时，再调用独立 reply LLM 补写消息。
9. 不得在最终架构中继续保留可独立产生用户可见外部输出的 passive reply producer；若保留 passive 相关模块，也只能承担 stimulus ingress、history、evaluation 或 helper 语义。

## 6. Impacted Modules

1. `cognition/preconscious.py`
2. `cognition/thinking_integration.py`
3. `helios_io/action_models.py`
4. `helios_io/planning.py`
5. `helios_io/limb.py`
6. `helios_io/channel.py`
7. `helios_io/channel_gateway.py`
8. `helios_main.py`
9. `behavior_registry/`

## 7. Acceptance Criteria

1. thought result 可正式产出包含 op、params 和 outbound intensity 的 action proposal。
2. planner 可对 thought-origin proposal 做接受/拒绝，并返回结构化 reason。
3. executor 可执行结构化 op 决议，而不限于简单文本发送。
4. thought-origin proposal 不再默认 `internal_only`。
5. 所有外化行动均可追溯到 originating thought 与 planner decision。
6. `helios_main.py` 可直接消费 `ThoughtCycleResult.action_proposal` 进入 planner，而不是必须经过 `preconscious` 旁路转译后才能成为正式路径。
7. 若 thought-origin action proposal 被拒绝，状态或日志中可读到 requested op、rejection reason、candidate channels 与 originating thought id。
8. debug prompt dump 中可读到输入 channel、输出 channel 控制方式、可用 ops 和参数格式。
9. 运行时若成功发送用户可见消息，trace 中必须能把 `outbound_text` 或等价输出 payload 追溯到 originating thought proposal，而不是追溯到 `response_pipeline.generate_reply()`。
10. 在真实 debug runtime 中，当 internal thought LLM 输出包含外向行动意图的 structured JSON 时，`thought_cycle.action_proposal` 不得长期为 `{}`；若 LLM 显式拒绝行动，也必须在 trace 中保留 `action_explicit=true` 与明确的无 action 结果。
11. R09 最终收口后，系统中不再存在与主路径并列竞争用户可见输出 owner 的 passive 承接路径；所有用户可见外发都必须能在 trace 中回溯到主路径中的正式 owner。
