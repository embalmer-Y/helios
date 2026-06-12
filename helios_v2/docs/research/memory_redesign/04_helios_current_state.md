# Helios 记忆架构现状盘点（2026-06-12）

> **范围**：owner 06 (memory) / 10 (directed_retrieval) / 14 (embedding) / 15 (experience_writeback) / 17 (evaluation) / 33 (persistence) / 42 (continuity_checkpoint)
> **方法**：grep contracts + engine + R79-D framework + R83 MemoryProbe 真实使用

## 1. 现有 owner 模块（按记忆数据流）

### 1.1 owner 06: memory (Memory Affect and Replay)
- **文件**：`src/helios_v2/memory/{contracts.py, engine.py}` 1080 行
- **关键类**：
  - `MemoryContentPacket` — 记忆内容（含 source 引用 + content fields）
  - `MemoryBindingContext` — 绑定上下文（time/place/affect）
  - `AffectTaggedMemoryItem` — 情感标签的记忆
  - `MemoryReplayCandidate` — 重放候选
  - `RecalledMemoryFact` — 回忆出的事实
  - `MemoryFormationState` — 记忆形成状态
  - `MemoryAffectReplayConfig` — 配置
- **能力**：✅ 有 memory 抽象；✅ 有 affect-tagging；✅ 有 replay
- **缺失**：
  - ❌ 无时间衰减算式
  - ❌ 无 working / episodic / semantic 三层分离
  - ❌ 无程序性记忆 (procedural)
  - ❌ 无 LLM 主动管理工具

### 1.2 owner 10: directed_retrieval
- **文件**：`src/helios_v2/directed_retrieval/{contracts.py, engine.py}` 552 行
- **关键类**：
  - `RetrievalRequest` — 检索请求（compact_stimuli + recall_intent + selected_memory_refs + target_tiers + limit）
  - `RetrievalQueryPlan` — 检索查询计划
  - `MemoryRetrievalCandidate` — 检索候选
  - `ThoughtWindowBundle` — 思维窗口束（带 tier 分层）
  - `ThoughtWindowTier` — `Literal["short_term", "mid_term", "long_term", "autobiographical"]`
- **能力**：✅ 4-tier 分层（**已实现**！）
- **缺失**：
  - ❌ Tier 实际没有差异化检索策略（都走 recency）
  - ❌ 无语义检索整合（需要 embedding）
  - ❌ 无检索诱发遗忘 (RIF)
  - ❌ Retrieval 不是"attention-level" 融合，只是 bundle 对象

### 1.3 owner 14: embedding
- **文件**：`src/helios_v2/embedding/{contracts.py, engine.py}` 786 行
- **能力**：✅ OpenAI-compatible embedding 客户端
- **缺失**：
  - ❌ 还未与 R10 深度整合
  - ❌ 默认 OFF（`assemble_runtime(embedding_gateway=None)`）
  - ❌ 无 RAG 工具暴露给 LLM

### 1.4 owner 15: experience_writeback
- **文件**：`src/helios_v2/experience_writeback/{contracts.py, engine.py}` 597 行
- **关键类**：
  - `ExperienceWritebackRequest` — 写回请求
  - `ContinuityEvidencePacket` — 连续性证据
  - `ConsolidationCandidate` — **巩固候选**（**已实现**！✅）
  - `ExperienceWritebackResult` — 写回结果
  - `ExperienceWritebackAPI` — 协议
- **能力**：✅ 有 ConsolidationCandidate 概念
- **缺失**：
  - ❌ Consolidation 触发条件是 `outcome_class`，不是 LLM 主观
  - ❌ **没有真正的"巩固"算式**（Ebbinghaus / synaptic tagging）
  - ❌ 没有 sleep / replay 机制

### 1.5 owner 17: evaluation
- **能力**：✅ R82 drift evaluator（17-dim BehaviorDriftDimension）
- **缺失**：
  - ❌ 没法评估"记忆准确度"（recall / precision / F1）
  - ❌ MemoryProbe 只测了通路持久化，没测语义准确度

### 1.6 owner 33: persistence
- **文件**：`src/helios_v2/persistence/{contracts.py, engine.py}` 1141 行
- **关键类**：
  - `PersistedExperienceRecord` — 持久化记录（record_id, tick_id, continuity_kind, outcome_class, source_outcome_kind, source_outcome_id, writeback_status, summary, requested_effect_summary, applied_effect_summary, reason_trace, linkage, sequence, embedding, record_kind, metadata）
  - `ExperienceStoreBackend` — Protocol（append / read_recent / count / search_similar）
  - `InMemoryExperienceStoreBackend` — 内存后端
  - `SqliteExperienceStoreBackend` — SQLite 后端
  - `StoreBackedDirectedMemoryCandidateProvider` — **基于 store 的 R10 候选**
  - `SemanticStoreBackedDirectedMemoryCandidateProvider` — **基于语义相似度的 R10 候选**
- **能力**：✅ 完整持久化；✅ 两种 backend；✅ 两种 retrieval provider
- **缺失**：
  - ❌ 无时间衰减字段
  - ❌ 无"已巩固/未巩固"标记
  - ❌ 无"主动删除"工具
  - ❌ 无"重要度"动态调整

### 1.7 owner 42: continuity_checkpoint
- **文件**：`src/helios_v2/continuity_checkpoint/{contracts.py, engine.py}` 804 行
- **关键类**：
  - `InternalMonologueCarryState` — 内部独白跨 tick carry
  - `RuntimeContinuitySnapshot` — 连续性快照（含 v3 → v4 schema bump）
  - `RuntimeContinuityCheckpoint` — checkpoint
  - `ContinuityCheckpointStore` — store
- **能力**：✅ 跨 tick 状态持久化（R81 完成）
- **缺失**：
  - ❌ 仍是 v4 单一快照，不是"多时间尺度"
  - ❌ 无 epoch / session / tick 多层级

## 2. 端到端记忆数据流（当前）

```
LLM 输出 (remember_this: true/false)
        ↓
[当前] R15 写回决定（只看 LLM）
        ↓
[当前] outcome_class 决定 ConsolidationCandidate
        ↓
ExperienceWritebackEngine.write()
        ↓
runtime._persist_experience()
        ↓
PersistedExperienceRecord 入 InMemoryExperienceStoreBackend
        ↓
[可选] 带 embedding 入库

[检索] Runtime 触发 thought gate "fire"
        ↓
R10 DirectedRetrievalPath.plan_and_select()
        ↓
StoreBackedDirectedMemoryCandidateProvider (recency) 或 SemanticStoreBackedDirectedMemoryCandidateProvider (cosine)
        ↓
ThoughtWindowBundle 4-tier 命中
        ↓
[当前] bundle 注入 v3 prompt 当 context
```

## 3. 当前架构的根本问题

### 3.1 单层 store
- 所有 tick 进同一个 store
- 没有"工作 / 短时 / 长时 / 自传体"分层
- 4-tier 命名有，但实现是 recency 同质

### 3.2 LLM 主导决定
- `remember_this` 决定一切
- 实验证明 LLM 漏记 12.5%、多存 50%
- 没有客观算式覆盖

### 3.3 静态写入
- 一旦入 store 不变
- 没有 Ebbinghaus 衰减
- 没有 reconsolidation
- 没有 RIF

### 3.4 黑盒检索
- 检索结果直接塞 prompt
- LLM 不知道"这条是从记忆里来的"还是"这是实时 stimulus"
- 无法做 retrieval-aware 决策

### 3.5 LLM 被动
- LLM 不能主动调 `recall()` / `forget()` / `consolidate()`
- 没有"AI 元认知"

## 4. 关键数字（与 3 个实验的对应）

| 实验 | 发现 | 含义 |
|---|---|---|
| 1 | 6/8 state 跨轮稳定，2/8 漂移 | LLM 主观判断不绝对稳定 |
| 2 | 漏记率 100% (3/3) | LLM "不要记"判断系统性错 |
| 3 | precision 43%, recall 100% | LLM "宁滥勿缺" |
| 总 | F1 = 60% | 当前记忆架构有 40% 的浪费/错误 |

## 5. 现状总结

**Helios 当前 = "LLM 输出 → 单一 store → RAG 检索 → 塞回 prompt"**
- 优点：简单、可工作
- 缺点：**完全没有时间维度、没有衰减、没有重塑、没有主动遗忘、没有 LLM 主动管理**
- 缺的是真实人脑 14 个核心机制中的 **8-10 个**

## 6. 下一部分：双线方案设计

详见 `05_design_proposal.md`
