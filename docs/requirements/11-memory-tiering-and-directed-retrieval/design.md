# Requirement 11 - Memory Tiering and Directed Retrieval

## 1. Design Overview

R11 的设计目标不再只是 observability。除了 `RetrievalSECResult` 对外可见，本轮还要求把“上一轮 thought 想回想什么、想保留哪些记忆线索给下一轮”正式化为 `memory_handoff` 边界。

## 2. Runtime Flow

1. `helios_main.py` 在 thought loop 前构造 `RetrievalQueryPlan`。
2. `memory/memory_system.py` 执行 directed retrieval。
3. `DirectedMemoryBundle` 返回四层 hits、selection trace、retrieval SEC trace。
4. `cognition/thinking_integration.py` 消费 bundle summary，并在本轮 thought 后输出 recall intent / memory handoff。
5. `helios_main.py` 把 retrieval observability 与上一轮 `memory_handoff` 直接导出到 runtime state。

## 3. Data Contracts

### 3.1 RetrievalQueryPlan

```text
current_stimulus
recall_intent
query_text
target_tiers
limit
retrieval_strategy
metadata
```

### 3.2 RetrievalSelectionTrace

```text
tier_name
candidate_count
selected_count
query_source
```

### 3.3 RetrievalSECResult

```text
candidate_id
candidate_type
score
reason
selected
```

### 3.4 Directed retrieval observability payload

运行时导出至少包含：

```text
query_text
recall_intent
target_tiers
retrieval_strategy
metadata
short_term_count
mid_term_count
long_term_count
autobiographical_count
selection_trace
retrieval_sec_trace
retrieval_sec_trace_count
```

### 3.5 MemoryHandoff

```text
recall_intent
selected_memory_refs
saved_for_next_tick
source_thought_id
```

## 4. Module Ownership

1. `memory/retrieval.py`
   - 定义结构化 contract 和序列化 helper。
2. `memory/memory_system.py`
   - 生成 structured bundle。
3. `helios_main.py`
   - 负责 runtime observability 导出。
   - 负责把上一轮 `memory_handoff` 注入 retrieval plan 的 metadata / query source。

## 5. Implementation Notes

1. `DirectedMemoryBundle.to_observability_payload()` 作为主循环导出 helper。
2. `RetrievalSelectionTrace` 和 `RetrievalSECResult` 都应有 `to_dict()`。
3. `get_state()["directed_retrieval"]` 直接暴露结构化 trace，而不是要求调用方回到内部 bundle。
4. `memory_handoff` 不要求保存全部记忆正文，只保存下一轮 retrieval 所需的轻量引用与意图。

## 6. Validation Strategy

1. 单元测试验证 `retrieval_sec_trace` 结构化结果存在。
2. 集成测试验证 `get_state()["directed_retrieval"]` 暴露 `retrieval_sec_trace`。
3. 单元测试验证上一轮 thought 的 `memory_handoff` 能进入下一轮 retrieval plan。
4. 相邻回归验证 thought loop 仍可消费 directed bundle。
