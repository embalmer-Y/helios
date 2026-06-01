# Requirement 12 - Prompt Metric and Channel Context Contract

## 0. Execution Status

- Status: validated
- Review result: T12-1 到 T12-5 已全部完成。
- Runtime closure:
	- `helios_io/prompt_contract.py` 已成为统一 prompt contract owner
	- thought / reply / SEC / speech 已接入同一基础 contract
	- direct-user-message reply owner 指令已移除，reply path 仅保留 compatibility/helper 语义

## 1. Task Breakdown

### T12-1 定义 prompt contract 数据结构
1. 定义 metric descriptor。
2. 定义 channel context descriptor。
3. 定义 unified prompt contract plan。

### T12-2 实现统一 contract builder
1. 新增统一 owner。
2. 接入 identity、state、stimulus、memory 和 action schema。
3. 补充序列化与测试。
4. 扩展 memory handoff / recall contract，使 thought loop 能显式看到下一轮记忆保存与读取边界。

### T12-3 迁移 thought loop 与相关 LLM path
1. 让 `thinking_integration.py` 使用新 contract。
2. 让 retrieval SEC path 使用新 contract（若适用）。
3. 让 `helios_io/llm/speech.py` 使用同一基础 contract。
4. 清理旧局部 prompt 拼接。
5. 禁止 internal thought path 再以“纯内在独白”作为唯一输出契约。

### T12-4 清理 reply-only prompt owner
1. 删除或降级 `reply_prompt_builder.py` 旧 owner 地位。
2. 清理无用兼容接口。
3. 更新相关测试。
4. 移除 `response_pipeline.py` 中 direct-user-message prompt 指令，避免它与 thought/action owner 并行存在。

### T12-5 验证指标和 channel 语义完整性
1. 校验所有关键指标均有说明与范围。
2. 校验 channel 输入输出语义与 op schema 已进入 contract。
3. 校验身份边界文案合规。
4. 校验 thought prompt 中 memory handoff contract 已进入统一 builder。

## 2. Dependencies

1. 依赖 R07、R08、R09、R10、R11 的正式 owner 和数据契约。
2. 与 `personality_contract.py`、`thinking_integration.py` 和 channel/action schema 强相关。

## 3. Files and Modules

1. `personality_contract.py`
2. `cognition/thinking_integration.py`
3. `helios_io/reply_prompt_builder.py`
4. `helios_io/llm_sec_evaluator.py`
5. `helios_io/llm/speech.py`
6. `helios_io/channel.py`
7. `helios_io/action_models.py`
8. `tests/`

## 4. Implementation Order

1. T12-1
2. T12-2
3. T12-3
4. T12-4
5. T12-5

## 5. Validation Plan

1. 首轮验证 prompt contract 数据结构。
2. 第二轮验证统一 builder 输出。
3. 第三轮验证 thought loop 接入。
4. 第四轮验证 channel/op/identity 语义完整性。
5. 第五轮验证 speech/reply/SEC/thought 四条 LLM path 的统一 contract 收口。
6. 第六轮验证 reply compatibility path 已不再承担用户可见文本 owner。

## 6. Completion Criteria

1. 统一 prompt contract owner 已建立。
2. thought loop、reply、retrieval SEC 和 active speech path 已消费统一 contract。
3. 指标说明、范围、channel 语义、op schema 已进入 prompt。
4. 旧 reply-only prompt owner 已被移除或降级。
5. internal thought prompt 不再长期出现 `channel_context=unavailable` / `no_channel_ops_available`。
6. 代码库中不再保留 `reply_requirement=直接输出一条要发给用户的消息` 这类 direct-user-message owner 指令。

## 7. Closeout Review

1. T12-1 已完成：metric/channel/prompt plan 数据结构已建立。
2. T12-2 已完成：统一 `PromptContractBuilder` 已接入 identity、state、stimulus、memory、action schema。
3. T12-3 已完成：thought / SEC / speech 等路径已消费同一基础 contract。
4. T12-4 已完成：reply-only prompt owner 已降级，`response_pipeline.py` 中 direct-user-message 指令已移除。
5. T12-5 已完成：关键指标范围、channel/op 语义、memory handoff contract、身份边界均已有验证覆盖。
