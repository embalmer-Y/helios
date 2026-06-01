# Requirement 07 - Consciousness-First LLM Loop

## 0. Execution Status

- Status: validated
- Review result: 本文件列出的 T07-1 到 T07-6 已全部完成。
- Runtime closure:
	- structured `ThoughtCycleResult` 已成为主循环正式 owner
	- `ContinuationPressureState` 已跨 tick 持有并暴露到 runtime state
	- `memory_handoff` 已进入下一轮 retrieval 边界
	- passive path 中的并行 reply LLM owner 已移除

## 1. Closeout Tasks

### T07-1 Formalize structured thought decision owner

1. 让 internal thought LLM 输出从“自由文本独白”升级为结构化 decision contract。
2. `ThoughtCycleResult` 增加或正式承载 `memory_handoff` 等下一轮思考导向字段。
3. 保留 prose thought 文本，但不再让 prose 文本充当 continuation / recall / action 的唯一来源。

### T07-2 Formalize continuation owner

1. 在 `core/helios_state.py` 引入正式 `ContinuationPressureState`。
2. 保留 `continuation_pressure` / `continuation_reason` 作为派生镜像，而不是 owner。
3. 提供结构化 payload，供 `helios_main.py` 和 `get_state()` 消费。

### T07-3 Tighten thought-cycle payload

1. `ThoughtCycleResult` 必须带出结构化 `continuation`。
2. quiet tick 和 cooldown skip 都必须返回正式 `ThoughtCycleResult`。
3. `last_internal_thought_trace` 必须保留结构化 continuation 快照。

### T07-4 Cross-tick orchestration

1. `helios_main.py` 必须跨 tick 持有 continuation owner，而不是只持有一个 float。
2. 下一 tick 创建 `HeliosState` 时，要重新注入完整 continuation state。
3. `get_state()` 必须直接暴露 `continuation`。

### T07-5 Validation

1. focused tests 验证 structured thought output 建立 continuation owner。
2. focused tests 验证 `get_state()` 暴露 continuation owner 与 memory handoff。
3. focused tests 验证 internal thought prompt 已接入真实 channel/op contract。
4. 相邻回归覆盖 thought-active / no-thought fallback 边界。

### T07-6 Remove parallel reply owner

1. 停止 `helios_main.py` 在 passive path 中调用独立 reply LLM 生成用户文本。
2. accepted `reply_message` decision 只能消费上游已经给出的 `outbound_text`。
3. 若缺失 `outbound_text`，记录 owner 缺口并跳过外发，不再由 `response_pipeline` 补写。

## 2. Implementation Boundary

1. 本轮不重新打开与 thought owner 无关的旧 reply 文案优化。
2. 本轮重点是把 R07 从“功能成立”提升为“structured thought owner 契约成立”。
3. 本轮明确包含“移除并行 reply LLM owner”这一边界，不再把它留给后续 requirement。

## 3. Completion Criteria

1. `ContinuationPressureState` 成为正式 owner。
2. `ThoughtCycleResult` 和 `get_state()` 都能看到结构化 continuation。
3. quiet tick 的 continuation 衰减和 reflective carry 可被观测。
4. internal thought 不再被 prompt 强制收窄为“仅内在独白”。
5. thought-active tick 的下一轮 recall / memory handoff 来源可从 state 与日志中直接读到。
6. 运行时不再存在独立 reply LLM 补写用户消息的路径。

## 4. Closeout Review

1. T07-1 已完成：internal thought 已输出结构化 decision，continuation / recall / action / handoff 不再只依赖 prose text。
2. T07-2 已完成：`ContinuationPressureState` 已在 `core/helios_state.py` 中成为正式 owner。
3. T07-3 已完成：`ThoughtCycleResult`、quiet tick、`last_internal_thought_trace` 已携带结构化 continuation 信息。
4. T07-4 已完成：`helios_main.py` 已跨 tick 持有 continuation、recall intent 与 memory handoff。
5. T07-5 已完成：相关 focused tests 与最终全量回归均已通过。
6. T07-6 已完成：runtime 已不再通过 `response_pipeline.generate_reply()` 补写用户消息正文。
7. 后续收口已补完 `helios_main.py -> response_pipeline.populate_reply_decision()` 的 hydration 缝；accepted `reply_message` 如缺 payload 现在直接记为 consistency failure，而不是被 helper 补齐。
