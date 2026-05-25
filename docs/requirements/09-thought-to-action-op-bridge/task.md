# Requirement 09 - Thought-to-Action Op Bridge

## 0. Execution Status

- Status: in-progress
- Review result: 原 T09-1 到 T09-6 已完成测试内收口，但真实 runtime trace 否证了“bridge 已稳定闭合”的结论。
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

本轮收口顺序进一步约束为：

1. 先锁 `ThoughtCycleResult.action_proposal` 契约。
2. 再接主循环 direct consumption。
3. 然后修 planner / executor trace。
4. 最后处理 `preconscious` owner 降级与兼容边界。
5. reopen 阶段先补 structured decision 收口与 trace，再做真实 runtime closeout。

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

## 6. Completion Criteria

1. thought-origin action proposal 已成为正式路径。
2. `internal_only` 旧硬约束已移除。
3. planner / executor / channel ops 已支持结构化 op + intensity。
4. 所有外化行动均具备 thought origin trace。
5. `ThoughtCycleResult.action_proposal` 已从“占位字段”变为主循环正式消费的 owner 契约。
6. `preconscious` 即使保留，也不再是唯一 thought-to-action bridge owner。
7. internal thought prompt dump 中能看到真实输入 channel、可用输出 channel、supported ops 和参数格式。
8. 当 internal thought LLM 显式给出外向行动意图时，`action_proposal` 在真实 runtime report 中不得静默为 `{}`；若未桥接成功，必须有显式 `drop_reason`。

当前验收状态：reopened。真实 runtime 已证明 structured thought decision 到正式 action proposal 的最后收口尚未完成。

## 7. Closeout Review

1. T09-1 到 T09-6：保留完成结论，这些切片在测试和局部集成上已成立。
2. 新增 T09-7：负责修复真实 runtime 中 structured JSON thought 被保留为 `content`，但 `action_proposal` 静默丢失的问题。
3. 新增 T09-8：负责把 live eval/report 变成 R09 的正式 closeout 验证，而不是仅依赖 mock/integration slice。
