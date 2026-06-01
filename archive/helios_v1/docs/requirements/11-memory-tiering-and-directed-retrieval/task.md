# Requirement 11 - Memory Tiering and Directed Retrieval

## 0. Execution Status

- Status: validated
- Review result: T11-1 到 T11-4 已全部完成。
- Runtime closure:
	- `directed_retrieval` 已导出 query plan、selection trace、SEC trace 和 tier snapshots
	- `memory_handoff` 已进入 runtime state，并参与下一轮 retrieval plan
	- retrieval observability 与 four-tier public semantics 已闭合

## 1. Closeout Tasks

### T11-1 Tighten SEC observability export

1. 为 `RetrievalSelectionTrace` 和 `RetrievalSECResult` 增加结构化序列化 helper。
2. 为 `DirectedMemoryBundle` 增加 observability payload helper。
3. `helios_main.py` 导出完整 `retrieval_sec_trace`，不再只导出 count。

### T11-2 Formalize memory handoff boundary

1. 为 thought result 增加 `memory_handoff` 结构化字段。
2. 让下一轮 retrieval plan 显式消费 `memory_handoff`，而不是只吃启发式 recall text。
3. 在 runtime state 中暴露 handoff 摘要，便于调试和验收。

### T11-3 Tighten state boundary

1. `get_state()["directed_retrieval"]` 必须直接暴露 query plan 摘要、selection trace、SEC trace。
2. 保留 count 字段作为汇总视图，但不再替代结构化 trace。

### T11-4 Validation

1. focused tests 验证 structured SEC trace 仍在 memory contract 中成立。
2. focused tests 验证系统级 `get_state()` 暴露 structured retrieval trace。
3. focused tests 验证上一轮 thought 导出的 `memory_handoff` 已进入下一轮 retrieval plan。

## 2. Implementation Boundary

1. 本轮不重写 retrieval ranking 策略。
2. 本轮不改变四层公开语义。
3. 本轮补齐 runtime observability 与 memory handoff 边界。

## 3. Completion Criteria

1. retrieval SEC 的结构化结果可从 runtime state 直接读取。
2. public tiers、selection trace、SEC trace 在同一状态面上闭合。
3. `memory_handoff` 不再只是 thought 文本截断副产物，而是正式的下一轮 retrieval 输入边界。

## 4. Closeout Review

1. T11-1 已完成：`RetrievalSelectionTrace` / `RetrievalSECResult` / `DirectedMemoryBundle` 已具备结构化导出。
2. T11-2 已完成：thought result 已产出 `memory_handoff`，下一轮 retrieval plan 已显式消费 handoff。
3. T11-3 已完成：`get_state()["directed_retrieval"]` 已暴露 query/selection/SEC 结构化 trace。
4. T11-4 已完成：focused tests 与最终全量回归均覆盖并通过。
