# Requirement 09 - Thought-to-Action Op Bridge

## 1. Task Breakdown

### T09-1 扩展 action model schema
1. 在 `action_models.py` 中加入 thought-origin 字段、op payload 和 intensity。
2. 明确边界值与最小字段。
3. 为 schema 补充单元测试。

### T09-2 改造 thought bridge
1. 重构 `preconscious.py` 或引入新的 thought bridge owner。
2. 删除永久 `internal_only` 假设。
3. 让 thought result 能映射到标准 action proposal。

### T09-3 扩展 planner
1. 增加 thought-origin governance 校验。
2. 增加 op schema 校验和 intensity 归一化。
3. 补充 rejection trace。

### T09-4 扩展 executor 与 channel ops
1. executor 接收结构化 op 决议。
2. channel 层暴露正式 op schema。
3. 统一记录执行结果与回执。

### T09-5 清理旧路径与验证
1. 清理旧 internal-only 兼容假设。
2. 清理无用 send-text only wrapper。
3. 运行 thought-to-action 全链路测试。

## 2. Dependencies

1. 依赖 R07 提供 thought owner。
2. 依赖 R08 提供统一 stimulus / gate 上下文。
3. 与 behavior registry 和 planner 强相关。

## 3. Files and Modules

1. `cognition/preconscious.py`
2. `cognition/thinking_integration.py`
3. `helios_io/action_models.py`
4. `helios_io/planning.py`
5. `helios_io/limb.py`
6. `helios_io/channel.py`
7. `helios_io/channel_gateway.py`
8. `helios_main.py`
9. `behavior_registry/`
10. `tests/`

## 4. Implementation Order

1. T09-1
2. T09-2
3. T09-3
4. T09-4
5. T09-5

## 5. Validation Plan

1. 首轮验证 action model schema。
2. 第二轮验证 planner governance。
3. 第三轮验证 executor/channel op 扩展。
4. 第四轮验证 thought-to-action 全链路集成测试。

## 6. Completion Criteria

1. thought-origin action proposal 已成为正式路径。
2. `internal_only` 旧硬约束已移除。
3. planner / executor / channel ops 已支持结构化 op + intensity。
4. 所有外化行动均具备 thought origin trace。
