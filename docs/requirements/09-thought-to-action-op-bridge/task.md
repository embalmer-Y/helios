# Requirement 09 - Thought-to-Action Op Bridge

## 0. Execution Status

- Status: in-progress
- Review result: 原 T09-1 到 T09-6 已完成测试内收口，但真实 runtime trace 否证了“bridge 已稳定闭合”的结论。
- Final target update: R09 的最终目标已进一步明确为“移除独立 passive 承接/补写路径作为用户可见输出 owner”，统一由主路径处理所有用户可见外发；被动输入仍可作为 stimulus ingress 存在，但不再允许并行 passive reply producer 与主路径竞争 owner。
- Reopen evidence:
	- `live_eval_5min_2026-05-25_debug.json` 中 `thought_cycle.content` 已出现 structured JSON / 外向回应意图
	- 同一 thought cycle 的 `action_proposal` 仍为 `{}`
	- 因此需要补完 structured decision -> action proposal -> runtime trace 的最后收口

## 1. Task Breakdown

### T09-1 扩展 action model schema
1. 在 `action_models.py` 中加入 thought-origin 字段、op payload 和 intensity。
2. 明确边界值与最小字段。
3. 为 schema 补充单元测试。

补充边界：

1. 标准 `ActionProposal` 要能无损承载来自 `ThoughtCycleResult.action_proposal` 的字段。
2. provenance 中必须能区分 `thought_action_bridge`、`preconscious`、`regulation`。

### T09-2 改造 thought bridge
1. 在 `thinking_integration.py` 内正式产出 `ThoughtCycleResult.action_proposal`。
2. 在 `helios_main.py` 或独立 bridge helper 中实现 `ThoughtCycleResult.action_proposal -> ActionProposal` 的直接映射。
3. 删除“thought 必须先经 `preconscious` 转译，才能成为正式行动 proposal”的隐式前提。
4. 删除永久 `internal_only` 假设。
5. 让 internal thought prompt 接入真实 channel/op/parameter contract，使 LLM 能显式提议 `requested_op`、`candidate_channels` 与 `outbound_intensity`。

### T09-3 扩展 planner
1. 增加 thought-origin governance 校验。
2. 增加 op schema 校验和 intensity 归一化。
3. 补充 rejection trace。
4. 明确 requested op 缺失、required capability 不满足、target 约束缺失等拒绝分支。

### T09-4 扩展 executor 与 channel ops
1. executor 接收结构化 op 决议。
2. channel 层暴露正式 op schema。
3. 统一记录执行结果与回执。
4. 外部执行结果必须回写 origin thought id / proposal id / decision id。

### T09-5 清理旧路径与验证
1. 清理旧 internal-only 兼容假设。
2. 清理 thought-origin 必须走 `preconscious` 旁路的旧 owner 假设。
3. 保留必要 wrapper 时，必须把其语义降级为 compatibility/helper，而非正式 bridge owner。
4. 运行 thought-to-action 全链路测试。

### T09-6 收口 reply_message payload owner
1. 明确 `reply_message` 的 `outbound_text` 必须来自 thought-origin proposal，而不是 runtime 补写。
2. 去掉 `helios_main.py` 中 accepted/rejected reply decision 回头调用独立 reply LLM 的路径。
3. 若 decision 缺失 `outbound_text`，记录并拒绝执行，而不是默默补齐。
4. 去掉 `helios_main.py` 对 `response_pipeline.populate_reply_decision()` 这类 hydration helper 的依赖；target user / outbound metadata 只能在不改变 owner 的前提下补充执行元数据。

### T09-7 修复 structured decision 到 action proposal 的 runtime 收口
1. 在 `thinking_integration.py` 中明确区分：未显式提议 action、显式提议但 schema 无效、显式提议且成功桥接。
2. 修复 structured JSON parse / normalize / bridge mapping 丢失 action proposal 的路径。
3. 当 `action_explicit=true` 且最终 proposal 缺失时，必须记录 `drop_reason`，不得静默返回 `{}`。
4. 若 LLM 输出本身是 JSON 文本，state/report 不得只保留 `thought.content`，必须同时保留 structured parse status。

### T09-8 扩展真实 runtime trace 与 live validation
1. 扩展 live eval/report export，暴露 `structured_output_valid`、`action_explicit`、`drop_reason` 与 final action summary。
2. 增加 focused tests，覆盖“LLM 输出 structured JSON 且包含外向意图时，runtime 得到非空 action proposal 或显式 drop_reason”。
3. 重新运行 debug runtime，并用真实报告验证 thought-origin external payload 是否能在 trace 中闭合。

### T09-9 修复 live path 的 explicit bridge evidence
1. 追踪 `cognition/thinking_integration.py` 中 `action_explicit` / `action_parse_status` 的写入点，确认该标记是否只停留在局部对象、没有稳定落到 `internal_thought` / `thought_cycle` / state export。
2. 检查 `helios_main.py` 与 live sample 采集路径，确认 `action_proposal` 已进入 planner/executor 后，显式 bridge 证据不会在 owner 透传中被覆盖或清空。
3. 为 `speak_share` 等非 `reply_message` 外发路径补 focused regression，要求同时看到：`final_action_summary`、用户可见输出，以及 `action_explicit=true` 或等价 structured decision trace。
4. 若某些路径在设计上确实属于 implicit proposal，必须把它与 `action_explicit` 正式区分并导出；不得继续用 `0` 混淆“没有显式提议”与“证据丢失”。
5. 重新运行单次 fresh live artifact，验证 `missing_action_explicit` 是否消除；若未消除，继续沿 owner path 定位到具体丢失边界。

T09-9 最新结果：

1. `cognition/thinking_integration.py` 已为 heuristic `speak_share` 路径补上正式 `equivalent_bridge_evidence=true` 与 `bridge_evidence_kind="heuristic_externalization"`，不再把该路径误报成纯 `missing_action_explicit`。
2. `helios_evaluation/cli_brain_like_evaluation.py` 已同步消费该字段；R09 closeout 现在可区分 `implicit_proposal_only` 与 `equivalent_bridge_evidence_observed`。
3. focused regression 已覆盖 thought trace export 与 evaluator closeout 语义。
4. fresh short live artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_t099_equiv.json` 已显示 `equivalent_bridge_evidence_samples=5`、`blocking_reasons=[]`，说明旧 `missing_action_explicit` blocker 已不再适用于这类 implicit-but-traced path。
5. 随后继续直追 explicit structured-decision live owner path 后，`helios_main.py` 已新增 owner boundary：thought-origin `speak_*` 若缺失 `outbound_text`，runtime 现在记录 `execution_consistency_failure(reason=missing_outbound_text)` 并拒绝外发，而不是再调用下游 `LLMSpeechGenerator` 补文案。
6. 新鲜 live artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_explicit_probe_v4.json` 已出现 `execution_consistency_failure_events=6`、`top_rejection_reasons=["missing_outbound_text:6"]`、`visible_reply_events=0`，证明当前真正 blocker 已从“implicit evidence 是否缺失”进一步收窄为“explicit thought-origin visible text payload 没有稳定落地”。
7. evaluator 已同步把该 rejection 收口为 `r09_closeout.closeout_status="blocked_missing_outbound_text"`，避免再把这类 artifact 误判成 `equivalent_bridge_evidence_observed` closeout 成功。
8. 继续按 design/task 收紧 structured decision 归一化后，`cognition/thinking_integration.py` 现在会把 `op_name/requested_op -> preferred_op`、`visible_text/message_text/reply_text/utterance/text/message -> params.outbound_text`、以及顶层 `target_user_id/candidate_channels` 等近邻字段 canonicalize 到既有 contract。
9. 新鲜 live artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_explicit_probe_v5.json` 已把 `structured_output_valid_samples` 与 `action_explicit_samples` 从 0 推到 1，说明 live provider 的一部分 explicit JSON 已能穿过 bridge；但 `execution_consistency_failure_events=6`、`r09_closeout.closeout_status="blocked_missing_outbound_text"` 仍然存在，证明剩余 blocker 不只是字段别名，而是 explicit thought-origin visible text payload 仍未稳定出现。

### T09-10 框架调整清单（按终态边界）

`helios_main.py`

1. 保留：`ThoughtCycleResult.action_proposal` 的主循环消费、`_drain_behavior_executor()`、`_handle_action()`、`_route_outbound_text()`、execution consistency failure 留痕。
2. 降级：被动输入相关逻辑仅保留 stimulus ingress、SEC、history record、memory write、observability 汇总。
3. 删除：任何 passive external fallback proposal 的消费、任何 accepted decision 之后回头补写用户可见文案的调用点、任何在主路径失败后自动退回 passive direct reply 的 shortcut。

`cognition/thinking_integration.py`

1. 保留：structured decision parse/normalize、`ThoughtCycleResult.action_proposal` 生成、`action_explicit` / `drop_reason` / equivalent bridge evidence trace、raw structured payload observability。
2. 降级：heuristic `speak_share` externalization 仅作为显式 structured decision 缺席时的临时兼容路径，并持续以 `equivalent_bridge_evidence` 标识，不得伪装 explicit。
3. 删除：任何只保留 thought prose 但丢弃 structured action owner 的旧兼容假设。

`helios_io/planning.py`

1. 保留：thought-origin proposal 的 schema/capability/channel/op governance、selected channel/op 绑定、rejection trace。
2. 降级：planner 可裁剪/拒绝 proposal，但不能再承担“替上游补主要外发 payload”的隐式兜底语义。
3. 删除：把不完整 thought-origin proposal 自动补齐为旧 reply/send-text path 的任何逻辑。

`helios_io/limb.py` / `helios_io/limb_decision_bridge.py`

1. 保留：`ActionDecision -> BehaviorCommand -> executor` 的正式执行桥、command/result feedback。
2. 降级：无。
3. 删除：无独立文案 owner；不得在此层新增文本补写能力。

`helios_io/channel_gateway.py` / `helios_io/channel.py`

1. 保留：outbound route、op 支持校验、channel receipt、render/receipt metadata。
2. 降级：render/helper 只能处理表达调制与 receipt，不得改变 thought-origin 文案 owner。
3. 删除：任何在 channel route 阶段回头生成或改写主文案的隐式兜底路径。

`helios_io/response_pipeline.py`

1. 保留：`should_reply()` 的兼容判断、`record_exchange()`、history/query/context helper。
2. 降级：模块整体降级为 interaction/history helper，不再承担 reply text producer 或 external proposal owner。
3. 删除：`generate_reply()` 等任何独立产生用户可见外部文案的 owner 语义；旧 hydration / passive fallback proposal 相关调用点不得再被主循环消费。

`cognition/preconscious.py`

1. 保留：internal bias、observability、对主路径 proposal/rejection 的辅助分析。
2. 降级：externalization 语义彻底降级为 secondary helper /筛选器，不再独立产出 external `thought_action` proposal。
3. 删除：与 `ThoughtCycleResult.action_proposal` 并列竞争 external owner 的生产者角色。

`helios_evaluation/*` / live harness

1. 保留：R09 closeout、explicit/equivalent evidence 区分、owner-path diagnostics、raw structured payload observability export。
2. 降级：无。
3. 删除：任何会把 passive fallback success 混同于主路径 closeout success 的旧评估口径。

## 2. Dependencies

1. 依赖 R07 提供 thought owner。
2. 依赖 R08 提供统一 stimulus / gate 上下文。
3. 与 behavior registry 和 planner 强相关。

## 3. Files and Modules

1. `cognition/preconscious.py`
2. `cognition/thinking_integration.py`
3. `helios_io/action_models.py`
4. `helios_io/planning.py`
5. `helios_io/limb.py`
6. `helios_io/channel.py`
7. `helios_io/channel_gateway.py`
8. `helios_main.py`
9. `behavior_registry/`
10. `tests/`

## 4. Implementation Order

1. T09-1
2. T09-2
3. T09-3
4. T09-4
5. T09-5
6. T09-7
7. T09-8
8. T09-9

本轮收口顺序进一步约束为：

1. 先锁 `ThoughtCycleResult.action_proposal` 契约。
2. 再接主循环 direct consumption。
3. 然后修 planner / executor trace。
4. 最后处理 `preconscious` owner 降级与兼容边界。
5. reopen 阶段先补 structured decision 收口与 trace，再做真实 runtime closeout。
6. 当前 narrowed reopen 阶段优先补齐 `action_explicit` 或等价 bridge evidence，不再把 visible output gap 视为默认 blocker。

当前子任务边界：

1. 移除 `cognition/preconscious.py` 中独立 external `thought_action` producer。
2. 保留 `preconscious` 的 internal fallback / helper proposal 能力。
3. 把 passive/active/integration tests 改写为 direct bridge 是唯一 external owner。

T09-6 最新执行状态：

1. `helios_main.py` 已不再通过 `response_pipeline.populate_reply_decision()` 补齐 accepted `reply_message` decision。
2. accepted `reply_message` 缺失 `outbound_text` 时，runtime 现在记录 `execution_consistency_failure(reason=missing_outbound_text)` 并跳过外发。
3. focused regression 已覆盖该边界，确保 passive path 不再通过 hydration 抢回 owner。
4. `helios_main.py` 已不再消费 `response_pipeline.build_passive_fallback_proposals()` 产生的 external proposal；no-thought inbound 现在只保留 SEC、memory write、history record 与后续 tick state。
5. `helios_main.py` 现在会把 `normalized_intensity` / `outbound_intensity` 正式写入 outbound metadata；文字/语音通道共享 `helios_io/expression_modulation.py` 表达调制层，在显式强度存在时真实影响终止标点、冗余标点压缩与语气强弱。TTS channel 在注入的合成函数支持时还会显式消费该强度参数，不再只停留在 planner/feedback trace。
6. `channel_receipt` 现在采用混合边界：顶层正式记录 `original_text` / `rendered_text` / `expression_profile`，同时保留 `metadata` 作为兼容上下文容器；thought-origin 原文 owner 不变，最终外发文本只在通道 render 与 receipt 审计中闭合。

新增 reopen 子边界：

1. 把 `response_pipeline.py` 从“reply text producer”降级为 interaction/history helper。
2. 把 `reply_message` 从“需要后续文案生成”的行为改成“上游已经给出 payload 的执行行为”。

该子任务边界现已完成，收口结果如下：

1. `ThoughtCycleResult.action_proposal -> thought_action_bridge` 已成为运行时唯一正式 external thought-origin owner path。
2. `preconscious` 已降级为 internal/helper-only，不再与 direct bridge 竞争 external owner 语义。
3. planner rejection、execution result、channel receipt、execution consistency failure 已能直接暴露 `owner_path`、`requested_op`、`candidate_channels`、`selected_channel_id`、`selected_op` 等关键 trace 字段。

## 5. Validation Plan

1. 首轮验证 `ThoughtCycleResult.action_proposal` schema 与 adapter。
2. 第二轮验证 planner governance。
3. 第三轮验证 `helios_main.py` direct bridge consumption。
4. 第四轮验证 executor/channel op 扩展。
5. 第五轮验证 thought-to-action 全链路集成测试。
6. 第六轮验证真实 5 分钟 debug runtime trace。
7. 第七轮验证 fresh live artifact 中：若已存在 `final_action_summaries` 与用户可见输出，则必须同时存在 `action_explicit` 或等价 structured decision evidence；否则判为 `missing_action_explicit`。

## 6. Completion Criteria

1. thought-origin action proposal 已成为正式路径。
2. `internal_only` 旧硬约束已移除。
3. planner / executor / channel ops 已支持结构化 op + intensity。
4. 所有外化行动均具备 thought origin trace。
5. `ThoughtCycleResult.action_proposal` 已从“占位字段”变为主循环正式消费的 owner 契约。
6. `preconscious` 即使保留，也不再是唯一 thought-to-action bridge owner。
7. internal thought prompt dump 中能看到真实输入 channel、可用输出 channel、supported ops 和参数格式。
8. 当 internal thought LLM 显式给出外向行动意图时，`action_proposal` 在真实 runtime report 中不得静默为 `{}`；若未桥接成功，必须有显式 `drop_reason`。
9. 当真实 live artifact 已出现 `action_proposal` 与用户可见外发时，report 中不得继续长期保持“既无 `action_explicit`、也无等价 bridge evidence”；若确属 implicit path，必须以正式字段区分，而不是沉默缺失。

当前验收状态：reopened，且 blocker 已进一步具体化。对 heuristic `speak_share` live path，旧 `missing_action_explicit` 已被 `equivalent_bridge_evidence_observed` 收口替代；当 runtime 严格执行 owner boundary 后，真实 blocker 已明确表现为 `missing_outbound_text` rejection，而不是下游 speech owner 抢回文本。最新 v5 live 说明 explicit structured-decision path 已开始零星穿透，但还不能稳定产出 `outbound_text`。当前剩余关注点仍是不依赖 heuristic externalization 的真正 explicit structured-decision path，是否能在 live artifact 中稳定产出 `outbound_text`，并保留 `action_explicit` / `drop_reason` 证据。

最终目标补充说明：R09 收口的终态不是“主路径优先、被动路径兜底”，而是“用户可见外发统一由主路径处理”。被动输入仍可保留为 stimulus ingress / history / SEC / memory 辅助语义，但不得再保留独立 passive reply producer 或其它并行文案 owner。

## 7. Closeout Review

1. T09-1 到 T09-6：保留完成结论，这些切片在测试和局部集成上已成立。
2. 新增 T09-7：负责修复真实 runtime 中 structured JSON thought 被保留为 `content`，但 `action_proposal` 静默丢失的问题。
3. 新增 T09-8：负责把 live eval/report 变成 R09 的正式 closeout 验证，而不是仅依赖 mock/integration slice。
4. 新增 T09-9：负责把当前 reopen 问题从“外发是否发生”进一步收窄到“显式 bridge evidence 是否稳定落到 live trace”。
5. T09-9 当前阶段性结论：implicit `speak_share` path 已不再属于 evidence-missing；后续 closeout 重点转向 explicit structured-decision live payload 的稳定性，以及 comparison/report/doc 三处口径一致。
