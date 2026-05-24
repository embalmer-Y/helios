# Requirement 08 - Stimulus Weighting and Thought Gating

## 1. Design Overview

本设计建立一个统一的 stimulus contract，并把 thought gate 提升为主循环正式 owner。输入不再直接以 channel message 或 trigger dict 的形式零散流入，而是先归一化为 stimulus，再统一参与门控。

## 2. Current State and Gap

当前存在以下断裂：

1. `ChannelMessage.metadata` 可扩展但未形成正式刺激契约。
2. `habituation.py` 只对 trigger 强度做缩放，未直接参与 thought gate。
3. `cognitive_impact`、SEC appraisal、drive、temporal gate 和 phi 指标没有统一合流点。
4. 主循环目前缺乏独立的 thought gate owner。

## 3. Target Architecture

目标结构：

1. `channel_gateway` 输出统一 `StimulusEnvelope` 列表。
2. `helios_main.py` 汇总 internal stimuli 与 external stimuli。
3. `ThoughtGateEvaluator` 计算 gate result。
4. gate result 决定是否进入 R07 的 thought loop。

## 4. Data Structures

### 4.1 StimulusEnvelope

```text
stimulus_id
source_channel_id
source_kind
trigger_condition
stimulus_intensity
payload
text_summary
cognitive_impact
novelty_factor
sensitization_factor
created_at_tick
created_at_ts
metadata
```

### 4.2 ThoughtGateResult

```text
should_think
gate_score
dominant_reason
reason_trace
contributing_signals
blocked_reasons
selected_stimuli
```

## 5. Module Changes

1. `helios_io/channel.py`
   - 定义统一 stimulus/message contract 或扩展现有 message contract。
2. `helios_io/channel_gateway.py`
   - 负责将 channel 输入归一化为 stimulus envelope。
3. `habituation.py`
   - 保留实现，但其 novelty 输出要直接进入 gate signal。
4. `cognition/cognitive_impact.py`
   - 统一为 stimulus cognitive impact owner。
5. `helios_main.py`
   - 增加 gate evaluation stage。
6. `core/helios_state.py`
   - 存储 selected stimuli 与 gate result trace。

## 6. Migration Plan

1. 定义 stimulus envelope 与 gate result。
2. 把 channel 输入迁移到 envelope 输出。
3. 将 `habituation.py` 接入新 gate owner。
4. 将 gate owner 接入主循环并取代零散阈值判断。

## 7. Failure Modes and Constraints

1. 若 stimulus 无法完整解析，系统必须允许降级为最小 envelope，但必须保留 source 和 intensity 字段。
2. 若 habituation 或 cognitive impact 缺失，gate 可使用默认值，但必须显式记录。
3. gate result 必须设置上限/下限，避免所有信号被无界叠加。

## 8. Observability and Logging

必须记录：

1. normalized stimulus summary
2. selected stimuli count
3. gate score and dominant reason
4. blocked reasons
5. habituation / sensitization contribution

## 9. Validation Strategy

1. 单元测试验证 stimulus normalization。
2. 单元测试验证 low-intensity stimulus 被 gate 拒绝。
3. 单元测试验证 habituation / sensitization 会影响 gate score。
4. 集成测试验证无外部输入但 continuation pressure 存在时仍可进入思考。
