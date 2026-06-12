# 双线方案设计：Helios 记忆架构深度重构

> **设计原则**：基于人类记忆神经科学 + 认知心理学 + LLM 时代计算模型
> **目标**：把 8-10 个缺失机制落地，分两线（双轨）实施
> **范围**：owner 06 / 10 / 14 / 15 / 17 / 33 / 42

## 1. 双线定义

### 线 A：**"工作 / 短时 / 长时 / 自传"4 层分层 + 客观算式覆盖 LLM 主观**

解决：
- 漏记（实验 2）
- 多存（实验 3）
- 无衰减
- 检索-存储脱节

### 线 B：**"LLM 主动管理 + 反思周期 + 主动遗忘 + 重塑窗口"**

解决：
- LLM 被动（实验 1+2+3 根因）
- 无元认知
- 无法主动整理
- 无"睡眠巩固"

### 两条线的依赖关系
- 线 A 是 **基础设施**（必须先做）
- 线 B 是 **上层应用**（依赖线 A 的分层）

## 2. 线 A 详细设计

### 2.1 4 层时间尺度（按 Ebbinghaus + Baddeley 2000）

| 层 | 容量 | 时长 | 检索 | 写入条件 | 例子 |
|---|---|---|---|---|---|
| **L1 感觉缓冲** | 大 | 500ms | 自动 | 全部 | 原始 sensor signal |
| **L2 工作记忆** | 4±1 块 | 15-30s | attention | 当前 tick 上下文 | 正在处理的 stimulus + LLM 思考 |
| **L3 短时记忆** | 50 项 | 几分钟 | recency | outcome_class ∈ {world_changed, internal_only} | 最近 5 分钟的对话 |
| **L4 长时记忆** | 无限 | 持久 | semantic + recency | **双重确认**：LLM True OR 客观算式 ≥ 阈值 | 长期重要事件 |
| **L5 自传体** | 100s | 一生 | 触发式 | L4 + recency 5%+ + affect 强度高 | "我第一次被用户骂" |

**Helios 当前层数**：1 层（persistence store）
**Helios 目标层数**：4 层（L2-L5，跳过 L1 因 LLM 已经是 attention-level）

### 2.2 客观算式（覆盖 LLM 主观）

`objective_importance` 函数：

```python
def objective_importance(stimulus, llm_output, hormone_state, feeling_state, outcome_class):
    score = 0.0
    score += 0.25 * stimulus_intensity(stimulus)         # 刺激强度
    score += 0.20 * hormone_state.cortisol               # 应激水平
    score += 0.15 * feeling_state.arousal                # 唤醒度
    score += 0.15 * outcome_class_weight(outcome_class)  # 结果权重
    score += 0.15 * novelty(stimulus)                    # 新奇度
    score += 0.10 * social_safety_inverse(feeling_state) # 关系风险
    return min(max(score, 0.0), 1.0)
```

**outcome_class_weight**（基于 L18 治理 / R83 ContinuityOutcomeClass 6 种）：
| outcome | weight | 含义 |
|---|---|---|
| `self_changed` | 0.95 | 自我有变，最该记 |
| `world_blocked` | 0.80 | 被拒绝，重要 |
| `world_changed` | 0.60 | 有结果，中等 |
| `world_failed` | 0.50 | 失败，中等 |
| `self_blocked` | 0.40 | 自我变化被阻 |
| `internal_only` | 0.20 | 纯内心戏 |

### 2.3 双重确认写入规则

```python
def should_persist_to_L4(llm_remember, objective_score):
    # OR 逻辑：LLM 主观 OR 客观算式
    return llm_remember or objective_score >= L4_THRESHOLD
```

**L4_THRESHOLD = 0.50**

**含义**：
- LLM 觉得该记 → 记
- LLM 觉得不该记，但客观算式 ≥ 0.5 → 仍记
- LLM 觉得不该记，客观算式 < 0.5 → 不记

**预期效果**（基于实验 3 数据）：
- LLM 漏记的 praise（客观算式可能 ≥ 0.7）→ 仍记 ✅
- LLM 多存的 comfort（客观算式可能 ~ 0.3）→ 仍记但 priority 低 ⚠️
- LLM 不存的 neglect（客观算式可能 ~ 0.4）→ 不存 ✅
- **Precision: 43% → 75%+**
- **Recall: 100% → 100%**（不减反增）

### 2.4 时间衰减

```python
def decay_priority(priority, days_since_creation, last_recall_days_ago, is_consolidated):
    if is_consolidated:
        return priority  # 已巩固的不衰减
    return priority * (0.95 ** days_since_creation) * (1.0 + 0.1 / max(last_recall_days_ago, 1))
```

**Ebbinghaus 风格**：5% 每日衰减，但被回忆过会回弹。

### 2.5 reconsolidation（重塑）

每次 recall 时：
```python
def on_recall(record, current_context):
    record.last_recall_at = now()
    record.recall_count += 1
    # 重塑：可以加 notes，可以 adjust tags
    record.notes = maybe_regenerate_notes(record, current_context)
    # priority 提升
    record.priority = min(1.0, record.priority + 0.1)
```

### 2.6 数据结构升级

```python
@dataclass(frozen=True)
class MemoryRecord:
    # 原有
    record_id: str
    tick_id: int
    continuity_kind: str
    outcome_class: str
    summary: str
    # 新增
    layer: Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]
    objective_importance: float
    llm_remember_decision: bool
    hormone_snapshot: dict
    feeling_snapshot: dict
    # 时间维度
    created_at_tick: int
    created_at_wall: float
    last_recall_at_wall: float | None
    recall_count: int
    is_consolidated: bool
    # 自描述（A-MEM 风格）
    tags: tuple[str, ...]
    context_keywords: tuple[str, ...]
    cross_links: tuple[str, ...]  # 链接到其他 record_id
```

## 3. 线 B 详细设计

### 3.1 LLM 工具暴露（MemGPT 风格）

在 v3 prompt 中暴露以下工具（**不调用，作为"思维框架"自然语言**）：

```
你拥有以下"记忆工具"（自然语言表达，runtime 自动解析）：

1. recall(query): 想主动回忆某事时
   例："我想起了上次他生气的时候，那次我也搞砸了"
   → 触发 R10 retrieval 注入 prompt

2. consolidate(reflection): 想巩固某个理解时
   例："我现在意识到，我总是这样被忽视"
   → 触发 consolidation 算式，把这条记录提升到 L5

3. forget(reason): 想主动遗忘某事时
   例："我想忘掉那次尴尬的失败"
   → 触发主动遗忘（带治理审计 trail）

4. link(from_id, to_id, relation): 想建立记忆关联时
   例："这次的批评让我想起之前那次类似的"
   → 触发 cross_link

5. reflect(theme): 想做周期性反思时
   例："我最近是不是太敏感了？"
   → 触发 L5 自传体模式检索
```

### 3.2 反思周期（DMN 模拟）

**不是每 tick 触发**，而是后台周期性任务：

```python
class ReflectionScheduler:
    """每 N tick 或每 T wall-time 触发一次反思"""
    
    triggers = {
        "first_run": 50,           # 首次反思在 tick 50
        "periodic": 100,           # 之后每 100 tick
        "high_impact": "auto",     # 强烈情绪事件后立刻
        "low_activity": 30,        # 低活动期也强制反思
    }
    
    def reflect(self, handle):
        # 1. 检索最近 N tick 的所有 L4 records
        recent = store.read_recent(layer="L4", limit=50)
        
        # 2. 让 LLM 总结模式
        prompt = REFLECTION_PROMPT.format(records=recent)
        result = handle.llm_call(prompt)
        
        # 3. 把 summary 入 L5 自传体
        store.append(L5_autobiographical_record(
            content=result.summary,
            source_records=[r.record_id for r in recent],
        ))
```

### 3.3 主动遗忘（治理审计）

```python
class ForgetOp:
    """LLM 主动遗忘（带审计 trail）"""
    
    def forget(self, record_id, reason, llm_justification):
        record = store.get(record_id)
        
        # 1. 治理审计 (L18)
        audit = IdentityGovernance.check_forget_permission(
            record, reason, llm_justification
        )
        if not audit.allowed:
            raise IdentityGovernanceError(audit.reason)
        
        # 2. 软删除（保留 audit trail 一定时间）
        record.soft_delete(at=now(), reason=reason, audit=audit)
        
        # 3. 7 天后 GC
        store.mark_for_gc(record_id, after=now() + 7days)
```

**关键**：
- **不是物理删除**（防 AI 抹证据）
- **7 天软删除**（用户/治理可恢复）
- **审计 trail 永久保留**（治理合规）

### 3.4 sleep 巩固（后台任务）

```python
class SleepConsolidationJob:
    """每 T wall-time 跑一次（不是每 tick）"""
    
    def run(self, store):
        # 1. 找 L3 中重要度 ≥ 阈值 且 持续 ≥ 30s 的
        candidates = store.find(
            layer="L3_short",
            min_age_s=30,
            min_priority=0.5,
        )
        
        for c in candidates:
            # 2. synaptic tagging 检查
            if any_nearby_high_priority(c, store):
                # 邻近有高 priority → 借力巩固
                c.layer = "L4_long"
                c.is_consolidated = True
                c.priority = max(c.priority, 0.7)
            
            elif c.recall_count >= 2:
                # 被回忆 2 次以上 → 巩固
                c.layer = "L4_long"
                c.is_consolidated = True
            else:
                # 不重要的 → 衰减
                c.priority *= 0.5
        
        # 3. L4 → L5 提升（被回忆 ≥ 5 次 + affect 高）
        for c in store.find(layer="L4_long", recall_count_gte=5):
            if c.feeling_snapshot.arousal > 0.7:
                c.layer = "L5_autobiographical"
```

## 4. 实施路线（最小可行）

### Phase A1（R85, ~3 天）：基础设施
1. **升级 PersistedExperienceRecord → MemoryRecord**
2. **加 objective_importance 算式**
3. **加双重确认写入**
4. **加时间衰减**
5. **不动线 B**
6. **预期**：MemoryProbe F1 从 60% → 75%

### Phase A2（R86, ~5 天）：分层 + 重塑
1. **加 4 层 L2-L5**（从 store 分区）
2. **加 reconsolidation 在 recall 时**
3. **加 RIF（retrieval-induced forgetting）**
4. **加 cross-link 字段**
5. **预期**：precision 75% → 85%

### Phase B1（R87, ~3 天）：LLM 工具
1. **v3 prompt 加 5 个工具说明**
2. **加自然语言意图解析**（轻量 LLM 调用）
3. **recall / consolidate / link 三个先做**
4. **预期**：LLM 主动管理能力 +0%

### Phase B2（R88, ~5 天）：反思 + 主动遗忘
1. **加 ReflectionScheduler**
2. **加 SleepConsolidationJob**
3. **加 ForgetOp（带 L18 治理）**
4. **加 L5 自传体 layer**
5. **预期**：记忆系统"看起来像人脑"

## 5. 风险评估

| 风险 | 影响 | 缓解 |
|---|---|---|
| 数据迁移（旧 record → 新 schema）| R85 阻塞 | 写 v1→v2 migration helper |
| 性能（reflection 任务开销）| R88 可能慢 | reflection 限频（10 min 一次）|
| 治理（forget 滥用）| AI 抹证据 | L18 审计 + 软删除 + 7 天 GC |
| 评估（怎么测"看起来像人脑"）| 缺 metric | 跑 4 个实验 (1 漏记 / 2 衰减 / 3 检索 / 4 反思) |
| LLM 拒绝用工具 | recall 工具闲置 | 让工具 = 自然语言表述（v3 prompt 已学会）|

## 6. 替代方案对比

| 方案 | 改动量 | 效果 | 推荐 |
|---|---|---|---|
| A. 双线（推荐）| 8 owner × 5 天 = 40 人天 | 接近人脑 80% | ✅ |
| B. 仅 LLM 工具 | 1 owner × 2 天 = 2 人天 | 漏记缓解，多存不变 | ❌ 不够 |
| C. 仅客观算式 | 1 owner × 2 天 = 2 人天 | 漏记 +30%，precision +20% | ⚠️ 中间方案 |
| D. 保留 LLM 主导 | 0 | 不变 | ❌ F1 60% 不够 |

## 7. 与 P5 学习循环的关系

P5 的目标是 AI **自己学**。
- 当前 P5 = mandatory_learned_parameters 字段已声明，**没有 update 机制**
- 双线方案**间接**打通 P5：
  - recall 时记录"成功/失败"
  - consolidate 时让 importance 算式**真的被学习**（不是硬编码）
  - 反思时让 LLM 自己**调整** objective_importance 的权重

**即**：双线方案 = P5 的必要前置（不实施双线，P5 学个空）

## 8. 落地决策点

需要你确认：
1. **是否同意 4 层分层**？还是简化 2 层（短时 + 长时）？
2. **是否同意双重确认**（LLM OR 客观算式）？还是单线（只信算式）？
3. **是否同意治理审计 + 软删除**（forget 安全）？还是直接物理删除？
4. **是否同意 sleep 巩固**（后台周期任务）？还是实时同步？
5. **是否同意 reflection**（LLM 主动回顾）？还是只暴露工具让它自己调？

你的回答会决定 R85-R88 的具体设计。
