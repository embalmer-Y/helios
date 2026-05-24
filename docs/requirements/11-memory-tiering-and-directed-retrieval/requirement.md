# Requirement 11 - Memory Tiering and Directed Retrieval

## 1. Background and Problem

当前记忆系统具备 working/episodic/semantic/autobiographical 等结构，但其公开语义与新哲学不一致，且“思考前定向回想”尚未成为主路径。结果是：

1. 记忆更像是回复上下文和事件记录的混合体。
2. 没有正式的短期/中期/长期/自传四层认知语义。
3. 当前刺激与上一次思考 recall intent 驱动的定向检索没有成为正式 owner。
4. retrieval SEC 仍未被明确纳入主架构。

## 2. Goal

将记忆系统重构为以短期/中期/长期/自传四层为公开认知模型，并建立思考前的 directed retrieval 机制，使当前刺激和上一轮思考的 recall intent 都能引导中长期记忆进入本次思考窗口。

## 3. Functional Requirements

### 3.1 Memory Tier Model

1. 系统必须对外明确定义四层记忆：
   - short-term
   - mid-term
   - long-term
   - autobiographical
2. 四层记忆必须具有不同的容量、衰减、用途和检索角色。
3. 旧 working/episodic/semantic/autobio 结构可作为实现层，但不得继续作为唯一公开认知模型。

### 3.2 Directed Retrieval

1. 在每次 thought loop 前，系统必须先运行 directed retrieval。
2. directed retrieval 必须至少接受两类线索：
   - current stimulus
   - prior-thought recall intent
3. directed retrieval 必须优先从 mid-term、long-term 和 autobiographical 层中选择候选，而不是平铺全部上下文。

### 3.3 Retrieval SEC

1. 系统应允许在 directed retrieval 中运行 retrieval SEC，用于评估候选记忆与当前思考的相关性、重要性和进入窗口价值。
2. retrieval SEC 可以是规则式、向量式或 LLM 辅助，但必须输出结构化评分结果。
3. retrieval SEC 的结果必须可观测。

### 3.4 Short-Term Memory Boundary

1. short-term memory 必须保持极小规模。
2. short-term memory 应主要容纳：
   - 最近外部输入
   - 最近计算出的临时号码/片段
   - 当前 thought loop 的短期上下文
3. short-term memory 不得退化为无限对话拼接上下文。

## 4. Non-Functional Requirements

1. directed retrieval 必须足够轻量，适合每次思考前运行。
2. 记忆分层和检索 trace 必须可解释。
3. 本 requirement 不要求兼容旧记忆 API 命名。
4. 现有 SQLite backend 应优先复用为持久化承载层。

## 5. Code Behavior Constraints

1. 不得继续把回复上下文抓取作为记忆主路径 owner。
2. 不得把全部长记忆平铺进 prompt。
3. 不得让 short-term memory 无限增长。
4. 不得保留无用旧命名兼容层作为长期接口。

## 6. Impacted Modules

1. `memory/memory_system.py`
2. `memory/retrieval.py`
3. `memory/autobiographical.py`
4. `memory/backend.py`
5. `memory/sqlite_backend.py`
6. `helios_main.py`
7. `cognition/thinking_integration.py`
8. `helios_io/response_pipeline.py` or replacement prompt path

## 7. Acceptance Criteria

1. 系统对外存在正式的 short-term / mid-term / long-term / autobiographical 语义定义。
2. 每次思考前都运行 directed retrieval，而不是直接平铺全上下文。
3. directed retrieval 同时支持 current stimulus 与 prior-thought recall intent。
4. retrieval SEC 可输出结构化评分或筛选结果。
5. short-term memory 保持小规模且边界明确。
