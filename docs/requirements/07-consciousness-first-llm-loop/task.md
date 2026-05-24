# Requirement 07 - Consciousness-First LLM Loop

## 1. Task Breakdown

### T07-1 定义 thought loop 数据结构
1. 新增 `ThoughtCycleResult`、`ContinuationPressure`、`QuietTickOutcome`。
2. 明确字段语义、上下限和 owner。
3. 完成定义后补充结构序列化与测试样例。

### T07-2 重构 thinking integration 输出
1. 让 `cognition/thinking_integration.py` 返回统一结构。
2. 保留 fallback，但 fallback 也必须返回同结构。
3. 明确 thought sufficiency 与 continuation request 的默认规则。

### T07-3 重排主循环
1. 调整 `helios_main.py` 的 tick 顺序。
2. 让 thought gate、thought execution、continuation pressure 成为正式阶段。
3. 增加 quiet tick 结构化记录。

### T07-4 降级或移除旧 reply-first owner
1. 审核 `helios_io/response_pipeline.py`、`helios_io/llm/speech.py` 的主路径地位。
2. 删除不再需要的 direct reply-first owner 或将其改为 thought externalization helper。
3. 清理无用兼容接口。

### T07-5 增加 observability 与测试
1. 增加 thought gate、continuation pressure、quiet tick 相关日志和 trace。
2. 补齐单元测试和集成测试。
3. 运行窄回归验证主循环行为。

## 2. Dependencies

1. 无前置 requirement 依赖，但 R08、R11、R09 都依赖本 requirement 的 owner 定义。
2. 与 `helios_main.py` orchestration 变更强相关。

## 3. Files and Modules

1. `helios_main.py`
2. `cognition/thinking_integration.py`
3. `cognition/thinking.py`
4. `cognition/phi.py`
5. `core/helios_state.py`
6. `helios_io/response_pipeline.py`
7. `helios_io/llm/speech.py`
8. `tests/`

## 4. Implementation Order

1. T07-1
2. T07-2
3. T07-3
4. T07-4
5. T07-5

## 5. Validation Plan

1. 首轮验证：thought data structure 测试。
2. 第二轮验证：`thinking_integration` 的结构化输出测试。
3. 第三轮验证：`helios_main.py` 窄集成测试，确保 reply-first 主路径已失效。
4. 第四轮验证：continuation pressure / quiet tick observability 测试。

## 6. Completion Criteria

1. LLM 主调用点已收敛到 thought loop。
2. `helios_main.py` 不再把外部消息直接交给 reply-first owner。
3. continuation pressure 成为正式状态。
4. quiet tick 有结构化 observability。
5. 无用旧接口与 wrapper 已清理。
