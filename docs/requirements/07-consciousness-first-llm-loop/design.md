# Requirement 07 - Consciousness-First LLM Loop

## 1. Design Overview

本设计把 Helios 的 LLM owner 从“被动回复生成器 + 内部 thought 支路”重构为“主意识循环中的思考参与者”。目标不是把所有行为都交给 LLM，而是让 LLM 的调用点严格收敛到内部思考阶段，再由思考结果影响后续行动、回想、自我修订或 quiet tick 延续。

## 2. Current State and Gap

当前运行时存在三个问题：

1. `helios_main.py` 中 passive inbound 处理仍直接进入 SEC + reply generation。
2. `cognition/thinking_integration.py` 只在满足阈值时生成 internal thought，属于旁路 owner。
3. thought 结果是否需要继续思考没有正式状态 owner，导致多 tick 思考不成立。

因此，当前架构是“外部响应优先，内部 thought 补充”，而不是“内部意识流优先，外部行动为结果”。

## 3. Target Architecture

目标架构采用以下运行流：

1. 收集并标准化 stimulus。
2. 更新 affect、drive、temporal、neurochem、memory-ready state。
3. 基于统一门控判断是否进入 thought loop。
4. 若进入思考，则拉取定向记忆上下文并执行 thought generation。
5. thought generation 返回 `ThoughtCycleResult`。
6. 系统根据 `ThoughtCycleResult` 更新 continuation pressure、recall intent、action candidate、self-revision candidate。
7. planner / executor 只消费 thought 输出，而不直接消费 reply-first prompt path。

## 4. Data Structures

### 4.1 ThoughtCycleResult

建议新增统一结构：

```text
thought_id
triggered_at_tick
triggered_by
content
sufficiency_level
continuation_requested
continuation_reason
continuation_pressure_delta
recall_intent
action_proposal
self_revision_proposal
observability
fallback_used
llm_used
```

### 4.2 ContinuationPressure

建议在运行状态中引入：

```text
active
level
origin_thought_id
reason
expires_at_tick
carry_count
```

### 4.3 QuietTickOutcome

用于在未触发思考时保留可观测行为：

```text
tick
gate_reason
continuation_pressure
stimulus_summary
memory_summary
```

## 5. Module Changes

1. `helios_main.py`
   - 移除 LLM reply-first 的主路径 owner 地位。
   - 重排 tick 顺序，使 thought loop 成为唯一 LLM 入口。
2. `cognition/thinking_integration.py`
   - 升级为主 thought loop owner。
   - 输出 `ThoughtCycleResult` 而非自由 thought 对象。
3. `cognition/thinking.py`
   - 保留 mode/type 机制，但扩展为 sufficiency / continuation owner 的一部分。
4. `cognition/phi.py`
   - 与思考门控和 continuation pressure 紧耦合。
5. `core/helios_state.py`
   - 新增 continuation pressure、recall intent、quiet tick outcome 等字段。
6. `helios_io/response_pipeline.py`
   - 降级或拆除 direct reply generation owner 地位。
7. `helios_io/llm/speech.py`
   - 若保留，则只服务 thought externalization。

## 6. Migration Plan

1. 先定义新的 `ThoughtCycleResult` 与 `ContinuationPressure` 数据结构。
2. 再把 `thinking_integration` 的输出收敛到新结构。
3. 再重排 `helios_main.py` tick orchestration。
4. 最后拆除或降级 `response_pipeline.py` 中的旧 reply-first LLM owner。

本轮不要求保留旧接口兼容层，迁移中允许直接删除无用 wrapper。

## 7. Failure Modes and Constraints

1. 若 LLM 请求失败，thought loop 必须返回结构化 fallback 结果。
2. 若当前 tick 无足够刺激且无 continuation pressure，系统可以进入 quiet tick，但不得跳过状态演化。
3. 若 continuation pressure 持续累积，系统必须有上限和衰减机制，避免永久高压锁死。
4. 若旧 reply-first path 尚未完全删除，必须显式标记为 transitional path，不得继续扩展。

## 8. Observability and Logging

必须新增以下可观测面：

1. thought gate decision
2. thought started / skipped
3. thought sufficiency result
4. continuation pressure established / decayed / cleared
5. quiet tick outcome
6. fallback_used / llm_used

## 9. Validation Strategy

1. 单元测试验证 thought gate 命中与未命中时的结构化输出。
2. 单元测试验证 continuation pressure 从 thought result 写入 state。
3. 集成测试验证 `helios_main.py` 在存在 inbound stimulus 时不再直接走 reply-first owner。
4. 集成测试验证 quiet tick 仍记录结构化 observability。
5. 回归测试验证 LLM 故障时返回结构化 fallback thought result。
