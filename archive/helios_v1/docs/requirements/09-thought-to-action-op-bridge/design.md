# Requirement 09 - Thought-to-Action Op Bridge

## 1. Design Overview

本设计把 thought result 与 action system 正式接通。认知层不直接执行动作，但可以输出结构化行动提议；planner 与 executor 仍保留治理和执行权。这样既满足“思考后行动”，又保留能力与安全边界。

## 2. Current State and Gap

当前 gap 主要有五点：

1. `ThoughtCycleResult` 虽有 `action_proposal` 字段，但 thought prompt 仍可能不给出真实 `requested_op` / `candidate_channels` / `outbound_intensity`。
2. thought-origin externalization 仍可能退回启发式推导，导致 bridge owner 名义成立、决策 owner 未成立。
3. `ActionProposal` / `ActionDecision` 已具备部分 op/intensity 字段，但缺少一条“LLM 明确提议 -> planner 治理”的稳定生产路径。
4. channel 层已有 op descriptor，但 internal thought prompt 可能没有接入真实 channel context。
5. runtime 仍需显式防止“accepted reply decision -> hydration/补齐执行 payload”的兼容缝；即使不再调用 reply LLM，只要主循环允许在 accepted 后补齐 `outbound_text`，bridge owner 仍会被后处理重新夺回。
6. 真实 5 分钟 debug runtime 已出现 `content` 中保留 structured JSON / 外向回应意图，但 `thought_cycle.action_proposal={}` 的情况，说明 structured output parse、normalization、bridge mapping 与 trace export 之间仍存在丢失点。
7. 2026-05-30 修正 evaluator 可见输出口径后的 fresh 20 分钟 live artifact 已显示 `action_proposal_samples > 0`、`final_action_summaries=["speak_share:send"]` 且 `visible_reply_events > 0`，因此当前主问题已不再是 visible output gap，而是 live path 中 `action_explicit_samples=0`、`action_drop_reason_samples=0`，说明显式桥接证据没有稳定落到 runtime trace/export。

当前运行时已经具备 direct bridge 基础，但本轮需要把“提议者”真正收口到 thought LLM 本身，而不是让后处理启发式继续代替 channel/op 决策。

## 3. Target Architecture

最终终态进一步明确为：对用户可见外发而言，系统中只保留一条正式 owner path，即主路径 `stimulus ingress -> internal thought / ThoughtCycleResult.action_proposal -> thought_action_bridge -> planner -> executor -> channel`。外部输入仍可存在，但它们只负责形成 stimulus/context，不再拥有并行的 passive reply owner。任何当前保留的 passive/helper 组件，都必须被归类为“保留辅助语义”“降级兼容层”或“最终删除对象”，不得继续处于语义模糊状态。

目标流：

1. `ThinkingEngineIntegration.generate()` 返回 `ThoughtCycleResult`。
2. `ThoughtCycleResult` 中若存在 `action_proposal`，该 proposal 必须优先来自 structured thought decision，而不是外部启发式补造。
3. `helios_main.py` 在 regulation proposal 和任何 passive helper 之前显式消费 `ThoughtCycleResult.action_proposal`；主循环不再消费 passive external fallback proposal。
4. 该 proposal 先被映射为标准 `ActionProposal`，再交由 `ExecutionPlanner` 做 schema、capability、channel/op binding 和 governance 检查；planner 负责治理，不负责替 LLM 长期生成主要 channel/op 选择。
5. `BehaviorExecutor` 消费 `ActionDecision` 并调用 channel ops。
6. `FeedbackRecorder` 记录 origin thought、proposal、decision、channel receipt 与 result。
7. 若行为是 `reply_message` 或其它用户可见文本输出，`outbound_text` 必须在 step 1 的 thought-origin proposal 中就已经出现；主循环与 response helper 只能透传、校验和执行，不再补写文案。
8. 若 accepted `reply_message` decision 缺失 `outbound_text`，主循环必须记录 `execution_consistency_failure` 并拒绝外发，而不是回退到 hydration/helper path。

换句话说，R09 收口后的正式 owner 路径是：

```text
ThoughtCycleResult.action_proposal
-> ThoughtActionBridge adapter
-> ActionProposal
-> ExecutionPlanner
-> ActionDecision
-> BehaviorExecutor / ChannelGateway
-> FeedbackRecorder
```

`preconscious` 在该目标架构中不再承担唯一 bridge owner；若保留，其作用仅是对 thought-origin externalization 做补充筛选或社会性放大。

本轮进一步收口约束：

1. runtime 中正式 external thought-origin candidate 只允许从 `ThoughtCycleResult.action_proposal` 进入 `thought_action_bridge`。
2. `preconscious` 保留为 internal fallback / helper producer，不再独立产出 external `thought_action` ActionProposal。
3. 任何对外 thought-origin action 的 acceptance / rejection / feedback trace 都必须以 `thought_action_bridge` 为 source path，而不是 `preconscious`。
4. `response_pipeline` 若继续存在，只能作为 interaction/history helper，不再拥有文本补写或 no-thought externalization owner 权限。
5. structured thought decision 的解析结果必须成为一等 runtime trace，而不是只把原始 JSON 文本塞进 `thought.content`；否则无法区分“LLM 未提议 action”和“runtime 丢失 action proposal”。
6. 若 live artifact 已出现 `action_proposal` 与用户可见输出，但 `action_explicit` 仍长期为 0，则视为 bridge observability defect，而不是 closeout success；显式 bridge 证据必须能在 `internal_thought` / `thought_cycle` / evaluation export 中形成一致口径。
7. R09 的终态不是“主路径优先、passive 兜底”，而是“用户可见外发统一经由主路径”；passive path 若继续存在，只能保留非外发辅助语义。

### 3.1 Passive/Helper Boundary Classification

为避免迁移期再次出现 owner 漂移，现存 passive/helper 相关能力在 design 中统一分三类：

可保留：

1. stimulus ingress：接收外部输入、形成 `current_stimuli`、补充 channel/session/user 上下文。
2. interaction/history helper：记录会话历史、turn pair、channel receipt、非 owner 型 metadata。
3. SEC / memory / evaluation 辅助：情绪评估、记忆写入、report/export、diagnostic observability。
4. 非 owner 型 render/helper：在不改变文案 owner 的前提下补充 `rendered_text`、`expression_profile`、receipt metadata。

必须彻底降级为 compatibility/helper：

1. `preconscious` 的 externalization 语义：仅允许作为 internal fallback、社会性筛选、或 thought-origin 候选的二次评估器，不再作为独立 external producer。
2. `response_pipeline` 的历史 interaction 语义：仅保留 history / exchange record / receipt 汇总，不再承担 reply text producer。
3. passive helper 对 accepted decision 的 hydration：只允许补执行元数据，不允许补写用户可见 payload。

最终必须删除或禁止调用：

1. 任何独立的 passive reply producer，只要它能在主路径外直接生成用户可见外部文案。
2. `response_pipeline.generate_reply()`、`populate_reply_decision()`、`build_passive_fallback_proposals()` 这类会与主路径竞争文案 owner 的并行外发路径。
3. 在 thought-origin proposal 被拒绝或缺参后，自动退回 passive direct reply 的外发 shortcut。
4. 任何 accepted `reply_message` / `speak_*` decision 在执行阶段再回头调用独立 LLM 生成文案的路径。

## 4. Data Structures

### 4.1 ThoughtActionProposal

```text
origin_thought_id
behavior_name
preferred_op
params
channel_constraints
outbound_intensity
reason_trace
governance_hints
scope                # internal | external
target_user_id       # optional but explicit when required
```

### 4.2 ActionProposal 扩展字段

```text
origin_type=thought
origin_id
op_name
op_params
outbound_intensity
constraints.execution_scope
provenance.owner_path=thought_action_bridge
```

### 4.3 ActionDecision 扩展字段

```text
selected_op
validated_params
normalized_intensity
rejection_reason
routing_trace
policy_trace.violations
```

### 4.4 ThoughtCycleResult Consumption Contract

```text
triggered
thought_id
thought_type
action_proposal      # formal thought-origin action owner candidate
self_revision_proposal
owner_path=internal_thought_loop
```

### 4.5 Structured Decision Trace Contract

```text
structured_output_valid
action_explicit
equivalent_bridge_evidence
bridge_evidence_kind        # heuristic_externalization | other future equivalent trace kinds
action_parse_status         # parsed | explicit_none | invalid_schema | dropped_during_normalization
raw_action_summary
final_action_summary
drop_reason                 # optional but required when action_explicit=true and final action missing
```

设计约束：

1. `action_explicit=true` 且 `final_action_summary` 为空时，必须记录 `drop_reason`。
2. 若 `thought.content` 保存的是 JSON 文本或其截断形式，状态中必须同时暴露 parse 结果，避免把 parse 失败伪装成普通 thought prose。
3. runtime report/export 必须能区分：LLM 未提议 action、LLM 提议了但 schema 无效、runtime 正常接受并桥接。
4. 当 `action_proposal` 已成功进入 planner/executor 并形成最终外发时，显式 bridge 证据仍必须可追溯：要么 `action_explicit=true`，要么存在与之等价的 thought-origin structured-decision flag；不得只剩 `final_action_summary` 而失去“谁显式提议了这个动作”的证据层。
5. 对于 `speak_share` 这类设计上允许 heuristic externalization 的路径，不得伪造 `action_explicit=true`；应导出正式 `equivalent_bridge_evidence=true` 与明确 `bridge_evidence_kind`，使 evaluator 能把“implicit 但有 owner evidence”与“证据缺失”区分开。

设计约束：

1. `thought` 文本内容本身不是 action bridge owner；`action_proposal` 才是后续 planner 消费的正式桥接对象。
2. 主循环不得要求 `preconscious` 先把 thought 重新解释一遍，thought-origin action proposal 才能进入 planner。
3. 若 `action_proposal` 缺失，主循环才可继续考虑其它 action source。
4. 对用户可见输出而言，`params` / `op_params` 必须已包含执行所需 payload；`reply_message` 不是一张空白票据，不能留给后续 reply LLM 再生成文本。
5. 外部输入触发并不等于 passive reply owner；即使是用户输入驱动的外发，只要最终形成了用户可见输出，也必须能回溯到主路径中的正式 action owner。

## 5. Module Changes

1. `cognition/thinking_integration.py`
   - 正式定义 `ThoughtActionProposal` 结构或等价字典契约。
   - 在 thought 生成阶段直接产出 optional `action_proposal`。
2. `helios_main.py`
   - 新增或维持 thought-action bridge 消费点。
   - 在 regulation / passive helper 之前优先评估 `ThoughtCycleResult.action_proposal`。
   - 当 LLM 未提供有效 proposal 时，主循环不得再降级消费 passive external fallback proposal；最多只保留记录和后续 tick continuation。
   - 不再允许 accepted `reply_message` decision 回头调用 `response_pipeline.generate_reply()` 之类的并行文案生成路径。
   - 迁移终态中，主循环只保留 stimulus ingress、history、SEC/memory 等非 owner helper；所有能独立产生用户可见外发的 passive shortcut 都必须删除或永久禁用。
3. `helios_io/action_models.py`
   - 明确 thought-origin proposal 最小字段和 provenance 约束。
4. `helios_io/planning.py`
   - 新增 thought-origin governance rules、requested op 校验、intensity normalization trace。
5. `helios_io/limb.py`
   - 支持 op payload + intensity 执行。
6. `cognition/preconscious.py`
   - 删除永久 `internal_only` 假设。
   - 收口为 internal fallback / helper policy；不再独立产出 external `thought_action` proposal。
   - 若后续仍保留模块文件，也不得再保留“无主路径 thought proposal 时直接顶上 external output owner”的兼容职责。
7. `helios_io/channel.py` / `channel_gateway.py`
   - 确保 channel op descriptor 足以支撑 selected op 执行与参数校验。
8. `tests/manual/run_30min_live_eval.py` / runtime report export
   - 暴露 structured decision trace，确保 live eval 可验证 R09 是否在真实 runtime 中闭合。
9. `core/helios_state.py` / `helios_main.py` / live sampling path
   - 确保 `action_explicit`、`equivalent_bridge_evidence`、`bridge_evidence_kind`、`action_parse_status`、`drop_reason` 不会在 tick state 汇总、跨模块透传或 live sample 导出时被静默丢失。

## 6. Migration Plan

1. 先锁定 `ThoughtCycleResult.action_proposal` 的正式 schema。
2. 再实现 thought-action bridge adapter，把 `action_proposal` 直接映射到 `ActionProposal`。
3. 再让 `helios_main.py` 优先消费该 bridge 输出。
4. 再扩展 planner / executor / channel op 验证和 trace。
5. 最后处理 `preconscious` 的 owner 降级和旧假设清理。
6. reopen 收口阶段增加“structured decision -> final action proposal”闭环修复，再跑真实 debug runtime 验证。
7. 当前收口阶段优先补齐 live path 的 `action_explicit` 或等价 bridge evidence，不继续把 `visible_reply_events` 误判当作 R09 主 blocker。
8. 最终收口阶段必须完成 passive/helper 分类清理：保留 stimulus/history/SEC/memory helper，降级兼容层，删除并行 passive external owner。

## 7. Failure Modes and Constraints

1. 若 thought 产生无效 op 名称，planner 必须拒绝并记录原因。
2. 若 channel 不支持对应 op，planner 必须拒绝或降级。
3. 若 intensity 超界，planner 必须归一化或拒绝。
4. 若 action proposal 缺少最小必要字段，不得隐式补齐为旧 send-text path。
5. 若 thought-origin proposal 被拒绝，系统不得自动把该拒绝伪装成 passive fallback success；必须先留下 rejection trace，再由显式策略决定是否降级。
6. 若 `preconscious` 与 `ThoughtCycleResult.action_proposal` 同时提供外化候选，thought result owner 优先，`preconscious` 只能作为补充候选或二次筛选。
7. 若 accepted decision 缺失 `outbound_text` 这类执行必要参数，必须记为 owner/path defect，而不是再启用 reply prompt 二次生成。
8. 若 LLM 返回的 structured JSON 可解析，但 `action_proposal` 因 normalization、schema 过滤或 bridge mapping 被丢弃，系统必须显式记录 drop reason，并可在 live trace/report 中查看。
9. passive helper 即使仍保留非 LLM interaction/history 语义，也不得在 accepted decision 阶段补写 `reply_message` payload；缺参只能拒绝并留痕。
10. 最终架构中不得再存在“用户输入来了，所以先走一条被动 reply producer，再与主路径竞争”的双轨外发模型；用户输入只能进入 stimulus ingress，再由主路径决定是否外发。

## 8. Observability and Logging

必须记录：

1. originating thought id
2. thought-origin action proposal summary
3. planner acceptance / rejection
4. normalized outbound intensity
5. channel execution result
6. proposal owner path (`thought_action_bridge` vs `preconscious` vs regulation)
7. rejection 时的 requested op、candidate channels、violations
8. structured decision parse status、action_explicit、equivalent bridge evidence、drop_reason、final action proposal summary

## 9. Validation Strategy

1. 单元测试验证 `ThoughtCycleResult.action_proposal` schema 与最小字段。
2. 单元测试验证 thought-action bridge adapter 正确映射为 `ActionProposal`。
3. 单元测试验证 planner 对无效 op、缺失 target、越界 intensity 的拒绝。
4. 集成测试验证 thought result 可直接驱动 proposal -> decision -> executor 全链路。
5. 集成测试验证旧 `internal_only` 硬约束已被移除，且 `preconscious` 不再是唯一 owner。
6. 集成测试验证 `preconscious` 不再独立产出 external `thought_action` proposal，direct bridge 成为唯一 external owner。
7. debug prompt dump 验证 internal thought path 已接入真实 channel/op contract，而不是 `channel_context=unavailable`。
8. 集成测试验证 accepted `reply_message` decision 只透传 thought-origin `outbound_text`，不会触发独立 reply LLM 补写。
9. 真实 debug runtime 验证：当 thought LLM 输出包含外向行动意图时，report 中必须出现非空 `action_proposal` 或显式 `drop_reason`，不得再出现 silent `{}`。
10. fresh live artifact 验证：若 report 中已存在 `final_action_summaries` 与 `visible_reply_events > 0`，则必须同时验证 `action_explicit_samples > 0` 或存在等价 structured-decision evidence；否则判为 `missing_action_explicit`，不得宣布 R09 closeout。
11. 最终架构验证：代码中不再保留可独立产生用户可见文案的 passive reply owner；保留下来的 helper 只能落在 stimulus ingress、history、SEC/memory、render/receipt 辅助这几类。

上一轮 closeout 结论已被真实 runtime 否证，当前 reopen 证据如下：

1. focused tests 已证明 direct bridge、planner governance 与 reply owner 边界在 mock/integration slice 内成立。
2. 真实 `live_eval_5min_2026-05-25_debug.json` 显示 `thought_cycle.content` 保存了 structured JSON 形态 thought，但同一状态中的 `action_proposal` 仍为 `{}`。
3. 因此当前 reopen 目标不是新增 requirement，而是把 R09 从“测试内成立”推进到“真实 runtime trace 也闭合”。
4. 真实 `cli_brain_like_eval_r09_closeout_20min_20260530_single_live_v2.json` 已进一步证明 visible outbound 本身并不是当前唯一阻塞项：artifact 中已出现 `action_proposal_samples=17`、`visible_reply_events=21` 与 `final_action_summaries=["speak_share:send"]`，但 `action_explicit_samples=0`。因此下一设计切片必须把问题收窄到 live bridge evidence 缺失，而不是泛化为整个 thought-to-action 路径失效。
5. 2026-05-30 新的短场景 live artifact `cli_brain_like_eval_r09_focus_6min_20260530_t099_equiv.json` 已证明 `speak_share` heuristic externalization 可以通过正式 `equivalent_bridge_evidence` 收口：artifact 中 `action_explicit_samples=0`、`equivalent_bridge_evidence_samples=5`、`r09_closeout.closeout_status="equivalent_bridge_evidence_observed"`。因此当前 reopen 已不再把这类 implicit path 视为 `missing_action_explicit`，后续只需继续确认真正 explicit structured-decision path 的 live closeout 稳定性。
