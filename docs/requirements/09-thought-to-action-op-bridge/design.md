# Requirement 09 - Thought-to-Action Op Bridge

## 1. Design Overview

本设计把 thought result 与 action system 正式接通。认知层不直接执行动作，但可以输出结构化行动提议；planner 与 executor 仍保留治理和执行权。这样既满足“思考后行动”，又保留能力与安全边界。

## 2. Current State and Gap

当前 gap 主要有三点：

1. `preconscious.py` 中 thought-origin proposal 被硬编码为 `internal_only`。
2. `ActionProposal` / `ActionDecision` 结构尚未正式承载 outbound intensity 与 op payload。
3. channel 层的 op 抽象仍偏薄，难以承载统一外化语义。

## 3. Target Architecture

目标流：

1. `ThoughtCycleResult` 产出 optional `ThoughtActionProposal`。
2. 该 proposal 被映射为标准 `ActionProposal`。
3. `ExecutionPlanner` 消费该 proposal 并进行 channel/op binding。
4. `BehaviorExecutor` 消费 `ActionDecision` 并调用 channel ops。
5. `FeedbackRecorder` 记录 origin thought、decision、channel receipt 与 result。

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
```

### 4.2 ActionProposal 扩展字段

```text
origin_type=thought
origin_id
op_name
op_params
outbound_intensity
```

### 4.3 ActionDecision 扩展字段

```text
selected_op
validated_params
normalized_intensity
rejection_reason
routing_trace
```

## 5. Module Changes

1. `cognition/preconscious.py`
   - 删除永久 `internal_only` 假设。
   - 迁移为 thought-origin action bridge owner 或被更直接的 thought bridge 取代。
2. `helios_io/action_models.py`
   - 扩展 proposal/decision schema。
3. `helios_io/planning.py`
   - 新增 thought-origin governance rules。
4. `helios_io/limb.py`
   - 支持 op payload + intensity 执行。
5. `helios_io/channel.py`
   - 增强 op schema 和 channel capability 描述。
6. `helios_main.py`
   - 在 thought result 后接入 action bridge。

## 6. Migration Plan

1. 先扩展数据结构。
2. 再把 thought result 接入 `ActionProposal` 生成。
3. 再扩展 planner 和 executor。
4. 最后删除旧 `internal_only` assumption 和无用 wrapper。

## 7. Failure Modes and Constraints

1. 若 thought 产生无效 op 名称，planner 必须拒绝并记录原因。
2. 若 channel 不支持对应 op，planner 必须拒绝或降级。
3. 若 intensity 超界，planner 必须归一化或拒绝。
4. 若 action proposal 缺少最小必要字段，不得隐式补齐为旧 send-text path。

## 8. Observability and Logging

必须记录：

1. originating thought id
2. thought-origin action proposal summary
3. planner acceptance / rejection
4. normalized outbound intensity
5. channel execution result

## 9. Validation Strategy

1. 单元测试验证 thought-origin proposal schema。
2. 单元测试验证 planner 对无效 op 和越界 intensity 的拒绝。
3. 集成测试验证 thought -> proposal -> decision -> executor 全链路。
4. 集成测试验证旧 `internal_only` 硬约束已被移除。
