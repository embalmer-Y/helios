# Requirement 12 - Prompt Metric and Channel Context Contract

## 1. Design Overview

本设计把 prompt 构建提升为统一 contract owner，而不是各个 LLM path 自行拼接。该 owner 负责把内部指标说明、channel 上下文、action op schema 和身份边界以一致形式喂给各类 LLM path。

## 2. Current State and Gap

当前 gap：

1. `reply_prompt_builder.py` 仍服务于旧 reply path。
2. `thinking_integration.py` 与其他 LLM path 之间缺少统一 contract。
3. channel 与 op schema 没有稳定进入 prompt，尤其 internal thought path 仍可能看到 unavailable。
4. memory handoff / recall contract 还没有进入统一 prompt owner。
5. 身份边界缺少统一治理。
7. `response_pipeline.py` 仍残留 direct-user-message reply prompt，这与“由 thought 产出结构化 channel op payload”的设计冲突。

## 3. Target Architecture

目标结构：

1. 新增统一 `PromptContractBuilder` owner。
2. 其输入包括：
   - identity contract
   - metric explanations
   - current state summary
   - stimulus/channel context
   - directed memory bundle
   - available ops and channel controls
   - memory handoff contract
3. 输出可供不同 path 使用的结构化 prompt plan。
4. 若某条 LLM path 负责提出外发动作，它输出的应该是结构化 op payload，而不是独立的用户消息自然语言 owner。

## 4. Data Structures

### 4.1 MetricDescriptor

```text
name
range
meaning
interpretation_notes
```

### 4.2 ChannelContextDescriptor

```text
channel_id
source_kind
trigger_condition
stimulus_intensity
supported_ops
op_schema_summary
```

### 4.3 PromptContractPlan

```text
identity_layer
metric_layer
state_layer
stimulus_layer
memory_layer
channel_layer
action_layer
constraints_layer
```

### 4.4 MemoryHandoffDescriptor

```text
recall_intent_field
selected_memory_refs_field
saved_for_next_tick_field
```

## 5. Module Changes

1. `personality_contract.py`
   - 为统一 prompt contract 提供身份层输入。
2. `helios_io/reply_prompt_builder.py`
   - 删除或迁移为统一 prompt contract owner 的一部分。
   - 不再承载 direct-user-message owner 指令。
3. `cognition/thinking_integration.py`
   - 改为消费统一 contract。
   - internal thought path 必须接入真实 channel/op 和 memory handoff contract。
4. `helios_io/llm_sec_evaluator.py`
   - 若仍使用 LLM，也应消费统一指标语义。
5. `helios_io/channel.py` / `action_models.py`
   - 暴露 channel/op schema 摘要给 contract builder。

## 6. Migration Plan

1. 先定义 metric/channel/op descriptor 结构。
2. 再实现统一 contract builder。
3. 再让 thought loop / retrieval SEC / other LLM path 接入。
4. 最后删除旧 reply-only prompt owner。

## 7. Failure Modes and Constraints

1. 若某项指标不可用，contract builder 必须显式说明缺失，而不是 silently drop。
2. 若 channel/op 信息不可用，必须退回最小 capability summary。
3. contract builder 必须控制 prompt 长度，优先使用摘要与结构字段。
4. 仅当系统本身真的没有可用 output channel 或 memory handoff contract 时，才允许输出 unavailable；否则视为 wiring defect。
5. 任何保留下来的 reply compatibility prompt 都必须显式声明自己不是运行时主 owner，且不得要求模型直接输出给用户的消息正文。

## 8. Observability and Logging

必须记录：

1. prompt contract layer summary
2. metric descriptors count
3. channel descriptors count
4. omitted / unavailable sections
5. compatibility/deprecated prompt path 的调用次数（若仍保留）

## 9. Validation Strategy

1. 单元测试验证 contract builder 输出层结构。
2. 单元测试验证指标范围说明存在。
3. 单元测试验证 channel/op 摘要进入 prompt plan。
4. 集成测试验证旧 reply-only prompt owner 已降级或删除。
5. 集成测试验证 internal thought prompt dump 能看到真实 channel/op 与 memory handoff contract。
6. 集成测试验证 reply compatibility path 不再出现 `direct_user_message` 或等价 owner 指令。
