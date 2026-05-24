# Requirement 11 - Memory Tiering and Directed Retrieval

## 1. Design Overview

本设计把记忆系统从“多种存储结构的实现集合”提升为“服务 thought loop 的分层认知系统”。关键变化是引入 directed retrieval，将记忆选择前置到 thought loop 之前。

## 2. Current State and Gap

当前 gap：

1. `memory_system.py` 的 working/episodic/semantic/autobio 结构偏实现导向。
2. `response_pipeline.py` 仍拥有一部分 reply-oriented memory bundle owner 语义。
3. prior-thought recall intent 尚未正式落地。
4. retrieval SEC 尚未成为 first-class 概念。

## 3. Target Architecture

目标流：

1. thought gate 命中。
2. 系统构造 `RetrievalQueryPlan`。
3. `RetrievalQueryPlan` 同时包含 current stimulus 与 prior recall intent。
4. memory system 从 mid-term、long-term、autobiographical 层拉取候选。
5. retrieval SEC 对候选排序或筛选。
6. 结果形成 `DirectedMemoryBundle`，供 thought loop 消费。

## 4. Data Structures

### 4.1 RetrievalQueryPlan

```text
current_stimulus
recall_intent
target_scopes
limit
retrieval_strategy
```

### 4.2 DirectedMemoryBundle

```text
short_term_context
mid_term_hits
long_term_hits
autobiographical_hits
selection_trace
retrieval_sec_trace
```

### 4.3 RetrievalSECResult

```text
candidate_id
candidate_type
score
reason
selected
```

## 5. Module Changes

1. `memory/memory_system.py`
   - 暴露新的四层公开语义和 directed retrieval facade。
2. `memory/retrieval.py`
   - 增加 query plan、selection trace、retrieval SEC 结构。
3. `memory/backend.py` / `sqlite_backend.py`
   - 继续作为存储承载。
4. `helios_main.py`
   - 在 thought loop 前调用 directed retrieval。
5. `cognition/thinking_integration.py`
   - 消费 `DirectedMemoryBundle`。
6. `helios_io/response_pipeline.py`
   - 若仍保留，应失去 reply-oriented memory ownership。

## 6. Migration Plan

1. 定义新的四层公开语义。
2. 新增 directed retrieval facade。
3. 将 thought path 切到新 retrieval owner。
4. 清理旧 reply-oriented memory bundle owner。

## 7. Failure Modes and Constraints

1. 若 retrieval SEC 不可用，系统必须回落到规则式筛选。
2. 若 recall intent 缺失，仍可仅用 current stimulus 构建 query plan。
3. 若某层记忆为空，必须显式记录而不是静默吞掉。

## 8. Observability and Logging

必须记录：

1. retrieval query plan summary
2. 各层命中数量
3. retrieval SEC selection trace
4. final directed bundle size

## 9. Validation Strategy

1. 单元测试验证四层语义 facade。
2. 单元测试验证 query plan 组合 current stimulus 和 recall intent。
3. 单元测试验证 retrieval SEC fallback。
4. 集成测试验证 thought loop 在新 directed retrieval 下工作。
