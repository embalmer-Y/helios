# Requirement 07 - Consciousness-First LLM Loop

## 1. Design Overview

R07 的设计中心是把 Helios 的 thought loop 固化成正式运行时 contract，而不是停留在“能生成 internal thought 文本”的功能层。当前实现采用四层 owner：

1. `ThoughtGateResult` 负责是否进入 thought。
2. `ThoughtCycleResult` 负责 thought tick 的正式结果契约。
3. `ContinuationPressureState` 负责多 tick 的未完成思考压力状态。
4. `memory_handoff` 负责把本轮 thought 选中的回想线索传给下一轮 retrieval。

## 2. Runtime Flow

当前目标流如下：

1. `helios_main.py` 收集 stimulus 并完成 affect / drive / temporal / neurochem 更新。
2. 在 thought loop 前运行 directed retrieval。
3. `ThinkingEngineIntegration.evaluate_trigger()` 生成 `ThoughtGateResult`。
4. 若 gate 命中，执行 structured thought generation，并返回包含 prose thought 与结构化 decision 的 `ThoughtCycleResult`。
5. 若未命中或 type cooldown 命中，返回 `ThoughtCycleResult(triggered=False, quiet_tick=...)`。
6. `ThinkingEngineIntegration` 根据 sufficiency 建立或衰减 `ContinuationPressureState`。
7. `helios_main.py` 持有结构化 continuation state，并在下一 tick 重新注入 `HeliosState`。
8. passive reply 只在 no-thought tick 中作为 helper 路径存在。
9. 即便存在 channel 输入刺激，LLM 的对外表达文本也必须在 thought decision 内以结构化 op 参数出现，不能再由 reply path 二次生成自然语言。

## 3. Data Contracts

### 3.1 ThoughtCycleResult

正式字段：

```text
triggered
trigger_reason
thought
thought_id
thought_type
sufficiency_level
continuation_requested
continuation_reason
continuation_pressure_delta
continuation_pressure
continuation
recall_intent
memory_handoff
llm_used
fallback_used
owner_path
action_proposal
self_revision_proposal
quiet_tick
```

边界说明：

1. `thought` 只是内部内容，不是 orchestration owner；正式 owner 是其旁边的结构化 thought decision 字段。
2. `continuation` 是正式 continuation state 快照；`continuation_pressure` 只是派生标量。
3. `last_thought_cycle_result` 保存该结构的序列化快照。

### 3.2 Structured thought decision contract

正式字段：

```text
thought_text
sufficiency_level
continuation_requested
continuation_reason
recall_intent
memory_handoff
action_proposal
self_revision_proposal
```

设计规则：

1. LLM 输出必须优先按结构化 decision 解析；自由文本只作为 `thought_text`。
2. continuation、recall、action、memory handoff 优先来自结构化 decision，而不是完全由后处理启发式推导。
3. 若 LLM 输出不合格，系统回退到 fallback / heuristic derivation，但必须记录该降级。

### 3.2 ContinuationPressureState

正式字段：

```text
active
level
origin_thought_id
reason
expires_at_tick
carry_count
```

设计规则：

1. 新 reflective open loop 建立 continuation 时写入 `origin_thought_id`。
2. continuation 在 quiet tick 中衰减。
3. continuation 到期或衰减为零时清空。
4. `carry_count` 表示该 continuation 被跨 tick 携带的次数。

### 3.4 QuietTickOutcome

正式字段：

```text
tick
gate_reason
continuation_pressure
stimulus_summary
memory_summary
```

## 4. Module Ownership

1. `core/helios_state.py`
   - 持有 `ContinuationPressureState`。
   - 提供标量镜像与结构化 payload。
2. `cognition/thinking_integration.py`
   - 生成 `ThoughtGateResult` 和 `ThoughtCycleResult`。
   - 建立、衰减、清空 continuation state。
3. `helios_main.py`
   - 跨 tick 持有 continuation state。
   - 通过 `get_state()` 暴露 `continuation`、`thought_cycle`、`internal_thought`、`directed_retrieval` 与 `memory_handoff`。
4. `helios_io/response_pipeline.py`
   - 只保留为 no-thought passive helper。
   - 负责 interaction policy、history 与 observability。
   - 不再拥有独立 reply LLM prompt 或用户消息直写权。

## 5. Implementation Notes

1. continuation state 通过 `HeliosState.continuation` 正式持有。
2. `HeliosState.continuation_pressure` 和 `continuation_reason` 保留为派生镜像，服务已有度量面和 prompt metrics。
3. `helios_main.py` 通过 `last_continuation_state` 跨 tick 传递完整 continuation owner。
4. `ThoughtCycleResult.to_state_payload()` 必须带出结构化 `continuation`。
5. `last_internal_thought_trace` 必须带出结构化 continuation 快照，方便调试 quiet tick 和 reflective carry。
6. internal thought prompt 不得只注入 `internal_monologue` 伪行为，而必须接入真实 channel/op 与 memory handoff contract。

## 6. Failure Modes

1. LLM 不可用时返回结构化 fallback thought result。
2. continuation 到期时必须显式清空，而不是静默残留旧 reason / origin。
3. thought-active tick 不得回退到 passive direct reply owner。
4. accepted `reply_message` decision 若缺失 `outbound_text`，必须视为上游 owner 缺失，而不是触发独立 reply LLM 补写。
4. internal thought prompt 若长期出现 `channel_context=unavailable` 或 `no_channel_ops_available`，视为 thought contract 未正确接线。

## 7. Validation Strategy

1. 单元测试验证 reflective thought 会建立结构化 continuation state。
2. 单元测试验证 structured thought output 可直接产出 `recall_intent`、`memory_handoff` 和 optional `action_proposal`。
3. 集成测试验证 `get_state()` 暴露 `continuation`、`thought_cycle.continuation` 和 `memory_handoff`。
4. 集成测试验证 thought-active tick 不触发 passive fallback reply。
5. debug 日志验证 internal thought prompt dump 包含真实 channel/op contract。
