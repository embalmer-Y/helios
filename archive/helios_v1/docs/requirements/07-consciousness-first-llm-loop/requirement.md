# Requirement 07 - Consciousness-First LLM Loop

## 1. Background

Helios 的主循环已经从 reply-first 迁移到 thought-first，但要把这项 requirement 认定为真正关闭，必须进一步明确两个边界：

1. 主 owner 不是裸 `Thought`，而是 `ThoughtCycleResult`。
2. 多 tick 未完成思考不是松散标量，而是正式的 `ContinuationPressureState`。
3. 任意面向用户的 LLM 外发文本都不是 reply path 直接生成的自然语言，而必须是 thought loop 产出的结构化 channel op proposal 参数。

本 requirement 的目标不是让 LLM 每个 tick 都说话，而是让 LLM 先参与内在思考，并输出结构化 thought decision，再由该 decision 决定是否继续思考、是否回想记忆、是否产生外化动作或自我修订。

## 2. Goal

建立一个统一的 thought-centered orchestration，使每个 tick 的主路径稳定遵循：stimulus ingress -> state update -> thought gate -> directed retrieval -> structured thought generation -> continuation state update -> thought-origin action / memory handoff / self-revision derivation -> feedback / memory。

## 3. Functional Requirements

### 3.1 主循环 owner

1. `cognition/thinking_integration.py` 必须是 thought loop 的正式 owner。
2. `helios_main.py` 只能消费 `ThoughtCycleResult` 决定后续边界，不得在 thought-active tick 中重新把 owner 交回 reply-first helper。
3. 面向外部的文本生成只能来自 thought externalization，不得再保留 no-thought external fallback 作为并列 owner。
4. channel 输入到达后，LLM 不得在独立 reply prompt 中直接产出用户消息；输入只作为当前/下一 tick 的 stimulus，由 thought decision 明确决定是否调用哪个输出 channel、哪个 op、以及 op 参数。

### 3.2 ThoughtCycleResult 契约

1. 每次 thought loop 必须输出统一的 `ThoughtCycleResult`。
2. 结果至少要包含：
   - `triggered`
   - `trigger_reason`
   - `thought_id`
   - `thought_type`
   - `sufficiency_level`
   - `continuation_requested`
   - `continuation_reason`
   - `continuation_pressure_delta`
   - `continuation_pressure`
   - `continuation`
   - `recall_intent`
   - `memory_handoff`
   - `action_proposal`
   - `self_revision_proposal`
   - `quiet_tick`
   - `owner_path`
3. `last_thought_cycle_result` 必须保存该契约的序列化结果，供 `get_state()`、日志和下一 tick 使用。

### 3.3 Structured thought decision

1. thought loop 的 LLM 输出不得只是一句自由文本内在独白；必须至少同时给出：
   - `thought_text`
   - `sufficiency_level` 或等价 continuation judgement
   - `continuation_requested`
   - `recall_intent`
   - `action_proposal`（可为空）
   - `memory_handoff`（可为空）
2. prose thought text 可以继续存在，但只能作为 `ThoughtCycleResult` 的一部分，不得替代结构化 decision。
3. 若 LLM 输出无法解析为结构化 decision，系统必须显式走 fallback 路径并保留 rejection reason。
4. 当 thought 选择对外表达时，`action_proposal.params` 必须允许直接承载该次 channel op 需要的参数，例如 `outbound_text`、`target_user_id`、结构化 metadata；不得再把“回复文案生成”交给并行 reply owner 二次补写。

### 3.4 ContinuationPressureState 契约

1. 当 thought 不充分时，系统必须建立正式的 `ContinuationPressureState`。
2. 该状态至少要包含：
   - `active`
   - `level`
   - `origin_thought_id`
   - `reason`
   - `expires_at_tick`
   - `carry_count`
3. continuation state 必须跨 tick 持有并参与 gate scoring。
4. continuation state 可以派生出兼容性的标量 `continuation_pressure`，但标量不再是 owner。

### 3.5 Quiet tick 与 fallback

1. 未触发 thought 时，系统必须返回结构化 `quiet_tick` 结果，而不是只写 debug 文本。
2. LLM 不可用时，thought loop 必须返回结构化 fallback thought result。
3. no-thought tick 不得直接外化用户可见行动；若没有有效 thought-origin outbound proposal，运行时只允许记录、持有、延后思考或内部状态更新。
4. no-thought tick 不得再调用独立 reply LLM，也不得消费 passive external fallback proposal 去直接生成或发送用户消息。

### 3.6 Memory handoff

1. thought result 必须允许携带面向下一 tick 的 `memory_handoff`。
2. `memory_handoff` 至少要能表达：
   - 本轮认为下一轮需要继续回想的主题
   - 本轮从 directed retrieval 中选中的记忆线索或层级引用
   - 这些线索已被保存，可供下一轮 thought loop 读取
3. `memory_handoff` 不得只存在于日志文本，必须进入 runtime state。

### 3.7 LLM observability

1. `internal_thought`、`passive_reply`、`active_speech`、`sec_evaluation` 必须遵守统一 LLM 调用日志约定。
2. 日志至少要包含 owner path、model、temperature、timeout、prompt 长度与 prompt dump 摘要。
3. 运行日志必须能区分“thought-origin externalization”与“no-thought suppressed outbound”。
4. 当系统存在可用 channel/op 与 memory handoff contract 时，internal thought prompt dump 不得长期出现 `channel_context=unavailable` 或 `no_channel_ops_available`。

## 4. Non-Functional Requirements

1. quiet tick 必须稳定，不得因为无消息输入而退化为无意义空转。
2. continuation state 必须具备明确 observability，不能只存在于 prompt 或局部变量。
3. 默认运行配置必须允许 internal-thought LLM 成为真实主路径，而不是名义主路径。
4. 本 requirement 不要求兼容旧 reply-first public API。
5. internal thought prompt 不得被重新收窄为“仅允许内在独白且禁止任何结构化动作/记忆决策”。
6. 不得保留 `response_pipeline.generate_reply()` 这一类并行 LLM reply owner 作为运行时补丁路径。

## 5. Code Boundary

1. `helios_main.py` 负责 orchestration 和跨 tick 状态持有。
2. `cognition/thinking_integration.py` 负责 thought gate、thought result、continuation derivation。
3. `core/helios_state.py` 负责 runtime owner state carrier，包括 `ContinuationPressureState`。
4. `helios_io/response_pipeline.py` 不得再作为主循环 external proposal source 被消费。
5. `helios_io/response_pipeline.py` 若继续存在，只能负责 interaction policy、history 和 trace，不得再承担 LLM 直出用户消息或 no-thought externalization 的 owner 职责。

## 6. Acceptance Criteria

1. thought-active tick 中，主循环只消费 `ThoughtCycleResult` 决定后续行为。
2. `get_state()` 中可直接看到结构化 `thought_cycle` 和结构化 `continuation`。
3. reflective thought 产生 continuation 时，下一 tick 能看到 `origin_thought_id`、`reason`、`expires_at_tick`、`carry_count`。
4. quiet tick 能看到结构化 `quiet_tick` 结果和 continuation 衰减结果。
5. no-thought inbound tick 不会直接产出 external reply；若无 thought-origin proposal，则 reply 为 `None`。
6. thought-active tick 的 LLM 输出能直接产出结构化 `recall_intent`、`action_proposal` 与 `memory_handoff`，而不是完全依赖后处理启发式猜测。
7. 运行时不存在“thought 先决定要回复，再由 reply prompt 单独写文案”的并行 owner；若有用户可见文本发送，其 `outbound_text` 必须可追溯到 structured thought decision。
