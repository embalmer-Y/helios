# Requirement 11 - Memory Tiering and Directed Retrieval

## 1. Background

R11 的主体功能已经存在，但要彻底关闭，需要把“实现层已做”与“系统边界可观测”对齐。当前最关键的边界是：retrieval SEC 不能只在 `DirectedMemoryBundle` 内部存在，还必须通过 runtime state 对外暴露为结构化 trace。

## 2. Goal

建立一个面向 thought loop 的分层记忆检索系统，使公开语义、检索 contract、SEC 评分、thought-driven recall intent 与运行时 observability 全部一致。

## 3. Functional Requirements

### 3.1 Public memory tiers

1. 系统对外公开四层认知语义：
   - `short-term`
   - `mid-term`
   - `long-term`
   - `autobiographical`
2. 这四层必须在 `get_state()` 中可见。
3. working / episodic / semantic / autobio 仍可作为实现层，但不是唯一公开视图。

### 3.2 Directed retrieval contract

1. 每次 thought loop 前都必须建立 `RetrievalQueryPlan`。
2. query plan 至少包含：
   - `current_stimulus`
   - `recall_intent`
   - `query_text`
   - `target_tiers`
   - `limit`
   - `retrieval_strategy`
3. 运行时必须暴露 query plan 摘要。
4. query plan 的来源必须同时支持：
   - 当前外部刺激
   - 上一轮 thought 明确给出的 recall intent / memory handoff

### 3.3 Retrieval SEC contract

1. retrieval SEC 必须输出结构化 `RetrievalSECResult`。
2. 每条 SEC 结果至少包含：
   - `candidate_id`
   - `candidate_type`
   - `score`
   - `reason`
   - `selected`
3. runtime state 必须暴露结构化 `retrieval_sec_trace`，不能只给 count。

### 3.4 Directed bundle observability

1. runtime state 必须暴露各层命中数。
2. runtime state 必须暴露结构化 `selection_trace`。
3. runtime state 必须暴露结构化 `retrieval_sec_trace`。

### 3.5 Memory handoff contract

1. thought loop 必须允许输出用于下一轮 retrieval 的 `memory_handoff`。
2. `memory_handoff` 至少包含：
   - `recall_intent`
   - `selected_memory_refs` 或等价层级/候选引用
   - `saved_for_next_tick`
3. `memory_handoff` 必须进入 runtime state，并可被下一轮 retrieval 读取。
4. 不得只依赖“从 thought 文本截前 80 个字符”这类启发式作为唯一 recall intent owner。

## 4. Non-Functional Requirements

1. directed retrieval 必须轻量，适合每 tick 运行。
2. SEC trace 必须可解释，便于分析为什么某条记忆进入窗口。
3. short-term 边界必须持续保持小规模。
4. memory handoff 必须轻量，不得把整个 retrieval bundle 生硬复制进下一轮上下文。

## 5. Code Boundary

1. `memory/retrieval.py` 定义 query / bundle / SEC contract。
2. `memory/memory_system.py` 负责检索实现与 SEC fallback。
3. `helios_main.py` 负责在 thought loop 前执行 directed retrieval 并导出 observability。
4. `cognition/thinking_integration.py` 只消费 directed bundle，不拥有 retrieval SEC owner。

## 6. Acceptance Criteria

1. `get_state()["memory"]` 能看到 public tiers 与 tier snapshots。
2. `get_state()["directed_retrieval"]` 能看到 `query_text`、`target_tiers`、`selection_trace`、`retrieval_sec_trace`。
3. retrieval SEC 的结构化结果不是只存在于内部 bundle，而是可从系统边界直接读取。
4. `get_state()` 或等价 runtime state 能看到上一轮 thought 导出的 `memory_handoff`，并验证下一轮 retrieval 已消费该 handoff。
