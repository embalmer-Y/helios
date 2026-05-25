# Requirement 08 - Stimulus Weighting and Thought Gating

## 1. Task Breakdown

### T08-1 定义 stimulus envelope
1. 定义统一输入结构和字段语义。
2. 明确 intensity 范围和默认值。
3. 为主要 channel 提供归一化入口。

### T08-2 定义 thought gate result
1. 定义 gate result 结构。
2. 增加 reason trace 与 blocked reasons。
3. 为 observability 补充序列化。

### T08-3 接入 habituation / sensitization
1. 让 `habituation.py` 输出进入 gate 信号。
2. 增加 sensitization contribution trace。
3. 补充相关测试。

### T08-4 主循环接入 gate stage
1. 在 `helios_main.py` 增加 gate evaluation stage。
2. 替换零散阈值判断。
3. 让 R07 的 thought loop 消费 gate result。

### T08-5 清理旧输入边界
1. 删除或降级旧 message-only 边界。
2. 清理无用兼容 wrapper。
3. 更新测试到新 stimulus contract。

## 2. Dependencies

1. 与 R07 强耦合，需供给 thought loop。
2. 与 `habituation.py`、channel gateway 和 `core/helios_state.py` 强相关。

## 3. Files and Modules

1. `helios_io/channel.py`
2. `helios_io/channel_gateway.py`
3. `helios_main.py`
4. `core/helios_state.py`
5. `habituation.py`
6. `cognition/cognitive_impact.py`
7. `tests/`

## 4. Implementation Order

1. T08-1
2. T08-2
3. T08-3
4. T08-4
5. T08-5

当前收口子任务边界：

1. 把 thought gate 从 `InternalThoughtTrigger` 的隐含一部分收口为正式 `ThoughtGateResult` 契约。
2. 显式把 `sensitization_factor` 与 temporal dynamics 纳入 gate score 和 trace。
3. 保持现有主循环与 passive pipeline 的外部行为稳定，只修正 R08 owner 和 observability 缺口。
4. 用窄测试先验证 gate owner，再用相邻集成测试验证主循环消费路径。

当前子任务状态：已完成。

1. `ThoughtGateResult` 风格 payload 已进入 `HeliosState.last_thought_gate_result`。
2. 新增测试已覆盖 selected stimuli 摘要、sensitization trace、temporal dynamics trace，以及这些信号对 gate score 的影响。
3. `channel_gateway` 的 message-dict ingress 边界已被清理，stimulus contract 现已作为更直接的主循环输入 owner 暴露。

## 5. Validation Plan

1. 首轮验证 stimulus envelope normalization。
2. 第二轮验证 thought gate 结构化输出。
3. 第三轮验证 habituation 参与 gate。
4. 第四轮验证主循环 gate 接入后的窄集成测试。

## 6. Completion Criteria

1. 所有输入已进入统一 stimulus contract。
2. thought gate 成为正式 owner。
3. `habituation.py` 已从单纯 trigger 缩放器升级为 gate signal 参与者。
4. 无用旧输入边界已清理。

当前 requirement 状态：已完成。

1. `ThoughtGateResult` 与 `current_stimuli` 已成为 R08 的正式读取面。
2. `channel_gateway` 不再要求 message payload 夹带 normalized stimulus，旧输入边界已被清理。
3. 最终收口验证已覆盖 event source registry、channel gateway、thinking integration、tick wiring 与 prompt contract 相邻面，共 71 项通过。
