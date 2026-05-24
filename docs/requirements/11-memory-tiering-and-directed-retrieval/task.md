# Requirement 11 - Memory Tiering and Directed Retrieval

## 1. Task Breakdown

### T11-1 定义四层公开语义
1. 明确 short-term / mid-term / long-term / autobiographical 边界。
2. 绑定到现有实现层或新实现层。
3. 补充基本文档与测试。

### T11-2 定义 directed retrieval contract
1. 新增 `RetrievalQueryPlan`。
2. 新增 `DirectedMemoryBundle`。
3. 明确 recall intent 输入。

### T11-3 实现 retrieval SEC
1. 增加候选评分/筛选结构。
2. 实现规则式 fallback。
3. 补充 observability。

### T11-4 接入 thought loop
1. 在 thought loop 前运行 directed retrieval。
2. 让 `thinking_integration` 消费新 bundle。
3. 移除旧 reply-oriented memory owner。

### T11-5 清理旧命名与回归
1. 清理无用旧接口。
2. 更新测试到新公开语义。
3. 运行 memory + thinking 窄回归。

## 2. Dependencies

1. 依赖 R07 的 thought owner。
2. 依赖 R08 的 stimulus contract。
3. 与 R12 prompt contract 强耦合。

## 3. Files and Modules

1. `memory/memory_system.py`
2. `memory/retrieval.py`
3. `memory/autobiographical.py`
4. `memory/backend.py`
5. `memory/sqlite_backend.py`
6. `helios_main.py`
7. `cognition/thinking_integration.py`
8. `tests/`

## 4. Implementation Order

1. T11-1
2. T11-2
3. T11-3
4. T11-4
5. T11-5

## 5. Validation Plan

1. 首轮验证四层语义 facade。
2. 第二轮验证 directed retrieval contract。
3. 第三轮验证 retrieval SEC 与 fallback。
4. 第四轮验证 memory + thinking 集成。

## 6. Completion Criteria

1. 新四层记忆模型已成为公开语义。
2. directed retrieval 已成为 thought loop 前置步骤。
3. recall intent 已接入 retrieval。
4. 无用旧 memory owner 路径已清理。
