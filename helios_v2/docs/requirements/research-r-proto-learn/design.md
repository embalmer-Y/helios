# Design: R-PROTO-LEARN — 6-Layer Multi-Mechanism Appraisal 总体设计

> **配套**：`requirement.md` + `task.md` + `research_notes.md`。
> **状态**：调研阶段（仅设计，不写代码）。
> **作者**：小白，2026-06-16 06:30-（调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` from main `15b4650`）

---

## 1. 6 层 emotion system 总体架构

### 1.1 数据流图（ASCII 详细版）

```
┌────────────────────────────────────────────────────────────────────┐
│ visitor input (raw stimulus text + structured fields)              │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│ Layer 2: 预测层 (Predictive Coding)                                │
│  - Input: visitor input + recent context (last 5 ticks)            │
│  - Process: LLM.predict("visitor 会说什么")                        │
│  - Output: surprise_score ∈ [0, 1]                                 │
│  - Owner: owner 11 LLM                                             │
│  - Theory: Predictive Coding Theory (Rao & Ballard 1999)           │
│  - Schema: A (NEMORI-style)                                        │
│  - 实现: R81 hormone-predict corroboration 已有 50%，升级            │
└────────────────────────────────────────────────────────────────────┘
                              ↓ surprise_score
┌────────────────────────────────────────────────────────────────────┐
│ Layer 1: 内感受层 (Active Inference / Interoception)               │
│  - Input: surprise_score + 17-dim hormone current state            │
│  - Process: hormone_update(surprise) → interoceptive_state         │
│  - Output: interoceptive_state ∈ [0,1]^17                         │
│  - Owner: owner 04 神经调质                                        │
│  - Theory: Active Inference (Friston 2010)                         │
│  - Schema: E (17-dim hormone)                                      │
│  - 实现: hormone 100% 已有，hormone → appraisal 映射 0%             │
└────────────────────────────────────────────────────────────────────┘
                              ↓ interoceptive_state
┌────────────────────────────────────────────────────────────────────┐
│ Layer 3: 记忆层 (Pattern Completion / 海马体)                       │
│  - Input: visitor input + interoceptive_state                     │
│  - Process: R85.recall_similar(n=5, outcome_class=threat)         │
│           + R85.recall_similar(n=5, outcome_class=reward)         │
│  - Output: 5 similar past threat episodes + 5 similar past reward  │
│  - Owner: owner 06 memory                                          │
│  - Theory: Pattern Completion (海马体 - 皮层反馈)                  │
│  - Schema: D (memory-driven anchors)                                │
│  - 实现: R99-R104 既有切片 90%，R-PROTO-LEARN.3 对接               │
└────────────────────────────────────────────────────────────────────┘
                              ↓ similar episodes
┌────────────────────────────────────────────────────────────────────┐
│ Layer 4: 构造层 (Constructed Emotion)                              │
│  - Input: surprise_score + interoceptive_state + similar episodes │
│  - Process: LLM.construct_emotion_concept(                         │
│              "综合 surprise + 身体状态 + 历史经验 = 当前情绪概念")  │
│  - Output: emotion_concept: str (LLM 实时构造)                     │
│  - Owner: owner 11 LLM                                             │
│  - Theory: Constructed Emotion Theory (Lisa Feldman Barrett)       │
│  - Schema: 新增（emotion concept 不是 phrase）                     │
│  - 实现: 0%（要 LLM 实时构造 emotion concept）                     │
└────────────────────────────────────────────────────────────────────┘
                              ↓ emotion_concept
┌────────────────────────────────────────────────────────────────────┐
│ Layer 5: 学习层 (Bayesian Update / Active Inference)               │
│  - Input: emotion_concept + similar episodes outcome               │
│  - Process: bayesian_update(P(emotion_concept | input))            │
│           + write_back_to_R100_importance                          │
│  - Output: learned_emotion_prior (per stimulus pattern)            │
│  - Owner: owner 06 memory + 03 appraisal                           │
│  - Theory: Bayesian update + Active Inference                      │
│  - Schema: C (Bayesian posterior update)                           │
│  - 实现: R100 importance 30% 已有，扩到 emotion concept 概率更新    │
└────────────────────────────────────────────────────────────────────┘
                              ↓ learned_emotion_prior
┌────────────────────────────────────────────────────────────────────┐
│ Layer 6: Fallback 层 (EmoGist-style description retrieval)         │
│  - Input: visitor input (only if Layer 1-5 返回低置信度)           │
│  - Process: cosine(input_embedding, fallback_anchor_descriptions)  │
│  - Output: fallback_threat_score + fallback_reward_score           │
│  - Owner: owner 03 appraisal                                       │
│  - Theory: Context-dependent emotion categorization                │
│  - Schema: B (EmoGist-style description)                            │
│  - 实现: R97/R98 11 ZH + 10 EN anchors 70%，升级为 description 30%  │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│ appraisal 03 output:                                               │
│   - threat: float ∈ [0, 1]                                        │
│   - reward: float ∈ [0, 1]                                        │
│   - novelty: float ∈ [0, 1]                                       │
│   - confidence: float ∈ [0, 1]  (Layer 1-5 置信度，< 0.5 触发 Layer 6)│
└────────────────────────────────────────────────────────────────────┘
                              ↓
R36 appraisal-derived dynamics → owner 04 神经调质 → 17 hormone 更新
                              ↓
R98 post-LLM hormone adjustment (modulation ±0.10)
                              ↓
R81 next-tick corroboration (Layer 5 反馈)
```

### 1.2 layer 间依赖关系（无环）

```
Layer 2 依赖: visitor input
Layer 1 依赖: Layer 2 surprise_score + 17-dim hormone
Layer 3 依赖: visitor input + Layer 1 interoceptive_state
Layer 4 依赖: Layer 1 + Layer 2 + Layer 3
Layer 5 依赖: Layer 4 emotion_concept + Layer 3 similar episodes
Layer 6 依赖: visitor input (仅 Layer 1-5 置信度低时触发)

数据流无环 ✓
```

### 1.3 layer 间数据契约（API 边界）

#### 1.3.1 Layer 2 预测层 API

```python
@dataclass(frozen=True)
class PredictiveCodingSurprise:
    """Layer 2 → Layer 1 接口"""
    surprise_score: float  # ∈ [0, 1]，0 = 完全预期，1 = 极度意外
    predicted_themes: tuple[str, ...]  # LLM 预测的 visitor 会说的主题
    actual_themes: tuple[str, ...]  # visitor 实际说的主题
    confidence: float  # ∈ [0, 1]，LLM 对自己预测的置信度
```

#### 1.3.2 Layer 1 内感受层 API

```python
@dataclass(frozen=True)
class InteroceptiveState:
    """Layer 1 → Layer 3 接口"""
    hormone_state: tuple[float, ...]  # 17-dim hormone 当前值
    hormone_delta: tuple[float, ...]  # 本 tick 变化量（来自 surprise）
    valence: float  # ∈ [-1, 1]，从 hormone 聚合
    arousal: float  # ∈ [0, 1]，从 hormone 聚合
    dominance: float  # ∈ [0, 1]，从 hormone 聚合
    confidence: float  # ∈ [0, 1]
```

#### 1.3.3 Layer 3 记忆层 API

```python
@dataclass(frozen=True)
class SimilarEpisode:
    """Layer 3 → Layer 4 接口"""
    episode_id: str  # R85 memory record id
    outcome_class: str  # "threat" | "reward" | "neutral"
    outcome_detail: str  # 详细 outcome 描述
    similarity: float  # ∈ [0, 1]，cosine to current input
    recency: float  # ∈ [0, 1]，时间衰减后的最近性
    confidence: float  # ∈ [0, 1]
```

#### 1.3.4 Layer 4 构造层 API

```python
@dataclass(frozen=True)
class EmotionConcept:
    """Layer 4 → Layer 5 接口"""
    concept: str  # LLM 构造的情绪概念，如 "深沉的共情+轻微担忧+准备好倾听"
    components: tuple[str, ...]  # 拆解的子成分
    confidence: float  # ∈ [0, 1]
    construction_reasoning: str  # LLM 的构造理由
```

#### 1.3.5 Layer 5 学习层 API

```python
@dataclass(frozen=True)
class LearnedEmotionPrior:
    """Layer 5 → appraisal 03 接口"""
    concept_probability: dict[str, float]  # emotion concept → 概率
    prior_strength: float  # ∈ [0, 1]，prior 的强度
    update_count: int  # 已被 update 多少次
    last_updated_at: float  # wall time
```

#### 1.3.6 Layer 6 Fallback API

```python
@dataclass(frozen=True)
class FallbackAnchorScore:
    """Layer 6 → appraisal 03 接口"""
    threat_score: float  # ∈ [0, 1]
    reward_score: float  # ∈ [0, 1]
    matched_anchor: str  # 命中的 fallback anchor description
    confidence: float  # ∈ [0, 1]
```

### 1.4 appraisal 03 融合公式

```python
def fuse_layers_to_appraisal(
    layer2_surprise: PredictiveCodingSurprise,
    layer1_intero: InteroceptiveState,
    layer3_episodes: tuple[SimilarEpisode, ...],
    layer4_concept: EmotionConcept,
    layer5_prior: LearnedEmotionPrior,
    layer6_fallback: FallbackAnchorScore | None,  # 仅 fallback 时
) -> AppraisalDimensions:
    """融合 6 层输出为 appraisal 03 的 5 维 (threat, reward, novelty, etc.)"""

    # 1. threat score 来自 4 个来源
    threat_from_surprise = layer2_surprise.surprise_score * 0.3  # 预测偏差
    threat_from_episodes = _aggregate_episode_threat(layer3_episodes) * 0.3  # 历史模式
    threat_from_concept = _concept_to_threat(layer4_concept) * 0.2  # 构造概念
    threat_from_fallback = layer6_fallback.threat_score * 0.2 if layer6_fallback else 0  # fallback

    threat = threat_from_surprise + threat_from_episodes + threat_from_concept + threat_from_fallback

    # 2. reward score 类似
    reward = (...)

    # 3. 总体置信度
    confidence = min(layer2_surprise.confidence, layer4_concept.confidence, ...)

    # 4. 如果 confidence < 0.5，触发 Layer 6 fallback
    if confidence < 0.5 and layer6_fallback is None:
        layer6_fallback = invoke_layer6_fallback(current_input)
        # 重算 threat / reward
        ...

    return AppraisalDimensions(threat=threat, reward=reward, novelty=novelty, confidence=confidence)
```

---

## 2. 每层详细设计

### 2.1 Layer 1 内感受层（Active Inference / Interoception）

**Owner**: owner 04 神经调质

**现状**：
- 17-dim hormone 已有（R36 + R81）
- hormone → appraisal 映射 0%（R36 是 appraisal → hormone，反向没有）

**R-PROTO-LEARN.1 实施内容**：
1. 在 appraisal 03 入口加 `current_hormone_state` 参数
2. 用 LLM 实时评估 hormone → 5 appraisal dimension 映射
3. R36 + R81 保留（appraisal → hormone 方向不变）
4. 双向：appraisal 既受 hormone 影响（Layer 1），又影响 hormone（R36）

**API**:
```python
def map_hormone_to_appraisal(
    hormone_state: tuple[float, ...],  # 17-dim
    current_stimulus: Stimulus,
) -> InteroceptiveState:
    """LLM 评估: 当前 hormone 状态如何影响对当前 stimulus 的 appraisal"""
```

**理论依据**: Active Inference (Friston 2010) — 大脑用 interoceptive state 预测/解释外部刺激

**风险**: 中
- LLM 评估 hormone → appraisal 映射的训练数据需要构造
- 跟 R36 appraisal → hormone 方向可能冲突（需要 R36 公式里预留"hormone 当前值"项）

**MVP 简化**: 不接 LLM，用简单数学（hormone mean → baseline appraisal adjustment）

### 2.2 Layer 2 预测层（Predictive Coding）

**Owner**: owner 11 LLM

**现状**：
- R81 hormone-predict corroboration 已有（50%）
- 是"next-tick"模式，不是"current-tick"模式

**R-PROTO-LEARN.2 实施内容**：
1. 在 appraisal 03 入口加 LLM 预测环节
2. 预测输入："based on recent context, what will visitor say?"
3. 实际输入：visitor 实际说的话
4. surprise = distance(predicted, actual)
5. R81 corroboration 升级为 "next-tick" 反馈 → Layer 5 learning

**API**:
```python
def predict_and_compare(
    recent_context: tuple[Stimulus, ...],  # 最近 5 ticks
    actual_input: Stimulus,
    llm_gateway: LlmGateway,
) -> PredictiveCodingSurprise:
    """LLM 预测 + 比对实际 → surprise score"""
```

**理论依据**: Predictive Coding Theory (Rao & Ballard 1999) — 大脑每层都在做预测

**风险**: 中
- 每次 tick 多 1 次 LLM 调用（成本增加）
- 预测质量依赖 recent context 质量

**MVP 简化**: 不用 LLM 预测，用 embedding 距离（cosine(recent_input_embedding, current_input_embedding)）

### 2.3 Layer 3 记忆层（Pattern Completion）

**Owner**: owner 06 memory

**现状**：
- R85 memory store 已成熟
- R96 real semantic embedding 已默认
- R10 directed_retrieval 已 production-ready
- R99-R104 既有切片已规划 Layer 3 主体

**R-PROTO-LEARN.3 实施内容**（**最小切片，主要是"对接文档"**）：
1. R85 memory store 加 `recall_similar(n, outcome_class)` 检索方法
2. R-PROTO-LEARN.3 标注哪些 R99-R104 切片在 6 层架构里属于 Layer 3
3. 不新增实施切片，只做架构对接

**API**:
```python
def recall_similar(
    input_stimulus: Stimulus,
    n: int = 5,
    outcome_class: str | None = None,  # "threat" | "reward" | "neutral"
    min_similarity: float = 0.3,
) -> tuple[SimilarEpisode, ...]:
    """从 R85 memory store 检索最相似的 n 条 memory"""
```

**理论依据**: 海马体 Pattern Completion (Teyler & DiScenna 1986) — 一小段提示触发完整记忆

**风险**: 低
- R85 + R10 + R96 已经成熟
- 只是加 1 个检索维度（outcome_class）

### 2.4 Layer 4 构造层（Constructed Emotion）

**Owner**: owner 11 LLM

**现状**：
- 0%（helios 当前没有"emotion concept"概念）
- 只有 5 appraisal dimensions（threat, reward, novelty, etc.）

**R-PROTO-LEARN.4 实施内容**：
1. owner 11 LLM 加 `construct_emotion_concept` 输出
2. 输入：surprise + interoceptive + similar episodes
3. 输出：emotion concept（自然语言描述 + 拆解成分）
4. concept → appraisal 5 维的映射（用 LLM）

**API**:
```python
def construct_emotion_concept(
    surprise: PredictiveCodingSurprise,
    intero: InteroceptiveState,
    similar_episodes: tuple[SimilarEpisode, ...],
    llm_gateway: LlmGateway,
) -> EmotionConcept:
    """LLM 构造 emotion concept"""
```

**理论依据**: Constructed Emotion Theory (Lisa Feldman Barrett) — 情绪是 process，不是 entity

**风险**: 高
- 每次 tick 多 1 次 LLM 调用
- concept 质量依赖 LLM 质量
- 跟 R98 post-LLM hormone adjustment 可能有重叠（两者都让 LLM 做 appraisal 类工作）

**MVP 简化**: 不接 LLM 实时构造，用固定 emotion concept 字典（~10 个常见 concept）

### 2.5 Layer 5 学习层（Bayesian Update）

**Owner**: owner 06 memory + 03 appraisal

**现状**：
- R100 importance + 双重确认 30%
- R81 next-tick corroboration 已有（部分 Bayesian 性质）

**R-PROTO-LEARN.5 实施内容**：
1. R100 importance 升级到 emotion concept 概率更新
2. 每次 emotion concept 构造后，update Bayesian posterior
3. posterior 用于下次 Layer 1-4 的 prior
4. 跟 R81 corroboration 整合（next-tick 反馈 → posterior update）

**API**:
```python
def bayesian_update_emotion_prior(
    current_prior: dict[str, float],
    new_observation: tuple[SimilarEpisode, ...],  # 真实 outcome
    learning_rate: float = 0.1,
) -> dict[str, float]:
    """Bayesian update emotion concept probability"""
```

**理论依据**: Bayesian update + Active Inference (Friston 2010)

**风险**: 中
- 跟 R100 现有 importance 双写机制对接
- learning rate 需要调参

### 2.6 Layer 6 Fallback 层（EmoGist-style Description）

**Owner**: owner 03 appraisal

**现状**：
- R97 11 ZH anchors（5 threat + 5 reward + 5 medical symptom threat）
- R97 10 EN anchors（5 threat + 5 reward）
- 都还是 phrase-level

**R-PROTO-LEARN.6 实施内容**：
1. R97/R98 21 条 phrase 升级为 description（多段 LLM-friendly 描述）
2. EmoGist-style context-dependent retrieval
3. cosine(input_embedding, description_embedding) → fallback score
4. **R97/R98 现有 anchor 保留为 description 字段**，不删

**API**:
```python
@dataclass(frozen=True)
class FallbackAnchorDescription:
    anchor_phrase: str  # 原 phrase
    dimension: str  # "threat" | "reward"
    language: str  # "zh" | "en"
    description: str  # LLM-friendly 描述
    embedding: tuple[float, ...]  # description 的 embedding

def fallback_retrieve(
    input_stimulus: Stimulus,
    catalog: tuple[FallbackAnchorDescription, ...],
    top_k: int = 3,
) -> FallbackAnchorScore:
    """cosine retrieval + max aggregate → fallback threat/reward score"""
```

**理论依据**: EmoGist (Seoh & Goldwasser 2025) — context-dependent definition of emotion labels

**风险**: 极低
- R97/R98 现有 anchor 字段保留
- 只是升级为 description

---

## 3. 跟 R97/R98/R96/R85 既有切片的对接

### 3.1 跟 R97 (ZH anchors) 对接

| R97 现状 | R-PROTO-LEARN 对接 |
|---|---|
| `ZH_THREAT_ANCHORS` 5 短语 | R-PROTO-LEARN.6 升级为 description |
| `ZH_REWARD_ANCHORS` 5 短语 | R-PROTO-LEARN.6 升级为 description |
| `AnchorCatalog` 已有 5+5 ZH + R40 EN aliased | 兼容：保留原 anchor_phrase 字段，加 description 字段 |
| `estimate_dimensions` 取 max(R40, catalog) | 兼容：保留 R40 路径，新加 description 路径 |

### 3.2 跟 R98 (post-LLM hormone adjustment) 对接

| R98 现状 | R-PROTO-LEARN 对接 |
|---|---|
| `PostLLMHormoneAdjuster` 翻译 LLM prediction → hormone Δ | R-PROTO-LEARN.2 surprise score 走 R98 通路 |
| `catalog 极小扩 (5→11 ZH threat)` | R-PROTO-LEARN.6 description 升级 11 ZH threat |
| `LLM_HORMONE_DELTA ±0.10` 限制 | 保留（Layer 4 emotion concept 也有 ±0.10 modulation） |
| Owner-owned translation rules | R-PROTO-LEARN.4 复用 R98 owner 边界（owner 11 + 03 + 04 共同所有） |

### 3.3 跟 R96 (real semantic embedding) 对接

| R96 现状 | R-PROTO-LEARN 对接 |
|---|---|
| `EmbeddingProfileRegistry` 默认 OpenAI-compatible | R-PROTO-LEARN.6 description embedding 复用 |
| `DeterministicHashEmbeddingProvider` fallback | 保留（用于网络关闭场景） |
| `runtime_assembly` 注入 `_embed_text` 闭包 | R-PROTO-LEARN.2/3/6 都用同一 _embed_text |

### 3.4 跟 R85 (memory store) 对接

| R85 现状 | R-PROTO-LEARN 对接 |
|---|---|
| `R85MemoryStoreBackend` Protocol | R-PROTO-LEARN.3 加 `recall_similar(n, outcome_class)` 方法 |
| `MemoryRecord` 含 outcome_class 字段 | R-PROTO-LEARN.3 直接用 |
| `search_by_keyword` 中文不工作 | **R85 T17 已知问题**，R-PROTO-LEARN.3 改用 cosine（走 R96） |
| `promote_layer` 巩固机制 | R-PROTO-LEARN.5 Bayesian update 复用 promote_layer 的 consolidation |

### 3.5 跟 R99-R104 双轨记忆切片的对接

| R99-R104 切片 | 在 6 层架构里 | 对接方式 |
|---|---|---|
| R99 (MemoryRecord schema) | Layer 3 基础 | 既有 |
| R100 (6-dim importance + 双写) | Layer 5 基础 | 升级（用 emotion concept 概率替换原 importance） |
| R101 (Ebbinghaus 衰减 + 重固化) | Layer 3 强化 | 既有 |
| R102 (bounded-window / ANN) | Layer 3 工程化 | 既有 |
| R103 (memory_tool_channel) | Layer 3 用户接口 | 既有 |
| R104 (forget 治理) | Layer 3 治理 | 既有 |
| **R-PROTO-LEARN.1-6** | Layer 1+2+4+5+6 | **新增**（R-PROTO-LEARN.3 主要做"对接文档"） |

---

## 4. 风险评估

### 4.1 技术风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| LLM 调用成本增加（Layer 2 + Layer 4 多次调用） | 高 | MVP 用简化方案（embedding 距离代替 LLM） |
| emotion concept 质量难评估 | 高 | 用 CAREBench 论文的 appraisal reasoning 评估 |
| Layer 4 跟 R98 post-LLM hormone 边界冲突 | 中 | 明确划分：R98 是 hormone 调制，R-PROTO-LEARN.4 是 concept 构造 |
| 6 层融合后 latency 增量 | 中 | 加 timeout，async 并行化 |
| 跟 R100 双写机制对接 | 中 | 复用双写 schema |

### 4.2 owner 边界风险

| owner | 当前在 appraisal 的角色 | R-PROTO-LEARN 新增角色 |
|---|---|---|
| owner 03 appraisal | 现有 5 维输出 | 加 Layer 6 fallback + Layer 4 集成 |
| owner 04 神经调质 | 现有 17 hormone | Layer 1 interoception（hormone → appraisal 方向） |
| owner 06 memory | R85 既有 | Layer 3 recall_similar + Layer 5 Bayesian update |
| owner 11 LLM | R98 既有 | Layer 2 prediction + Layer 4 concept construction |
| owner 14 governance | 既有 | 无新增（不参与） |

### 4.3 兼容性风险

| 兼容性 | 状态 |
|---|---|
| R40 英文 anchors | 保留为 description |
| R97 ZH anchors | 保留为 description |
| R98 medical symptom anchors | 保留为 description |
| R36 appraisal → hormone | 保留（Layer 1 反向） |
| R81 next-tick corroboration | 升级为 Layer 5 Bayesian |
| R98 post-LLM hormone | 复用（Layer 2 surprise 走 R98 通路） |
| R85 memory store | 加 `recall_similar(n, outcome_class)` 方法 |
| R96 real embedding | 复用 |
| 1174 baseline 测试 | 必须全 pass |

---

## 5. MVP 3 周切片详细设计

### 5.1 R-PROTO-LEARN.6 Fallback (第 1 周)

**改动范围**:
- `appraisal/anchor_catalog.py`：`AnchorSet` 加 `description` 字段
- 11 ZH + 10 EN anchors 加 description（手工 + LLM 生成）
- `estimate_dimensions` 加 description cosine 路径
- 测试：description cosine 命中率 ≥ keyword cosine 命中率

**不改动**:
- `appraisal/engine.py` 现有 5+5 R40 短语保留
- `appraisal/post_llm_hormone_adjuster.py` 不动
- R97/R98 现有 anchor 字段保留

**验收**:
- 11 ZH description + 10 EN description 全部就绪
- 中文输入"胸口闷得慌" 命中 description（即使没命中 phrase）
- 1174 baseline 测试全 pass

### 5.2 R-PROTO-LEARN.5 Bayesian (第 2 周)

**改动范围**:
- `appraisal/engine.py` 加 `EmotionPriorState` 字段（frozen）
- `bayesian_update_emotion_prior` 函数
- 跟 R100 importance 双写机制对接
- 跟 R81 next-tick corroboration 整合

**不改动**:
- appraisal 5 维输出接口不变
- R36 appraisal → hormone 路径不变

**验收**:
- 10 次观察后，emotion concept 概率分布稳定
- B3 metric 正负分离 ≥ +0.05（fake LLM）
- 1174 baseline + 新测试全 pass

### 5.3 R-PROTO-LEARN.1 Interoception (第 3 周)

**改动范围**:
- `appraisal/engine.py` `GroundedDimensionEstimator` 入口加 `current_hormone_state` 参数
- `map_hormone_to_appraisal` 函数（LLM 实时评估）
- R36 公式里预留"hormone 当前值"项

**不改动**:
- 17-dim hormone 状态本身
- R36 appraisal → hormone 方向

**验收**:
- hormone state 影响 appraisal 5 维
- B3 metric 正负分离 ≥ +0.10（fake LLM）
- 1174 baseline + 新测试全 pass

### 5.4 MVP 3 周总验收

- 1174 + 60 新测试 = 1234 测试全 pass
- 真实云端 85 句 cortisol 正负分离 **≥ +0.10**（B3 headline 闭合）
- 真实云端 85 句 cortisol 正负分离 **≥ +0.05**（B2 headline 闭合）
- 6 层架构跑通（Layer 6 + 5 + 1 三个低风险层先跑通，Layer 2 + 4 留后续）
- appraisal latency 增量 < 200ms/tick

---

## 6. 完整 6-8 周路径概要

| 周 | 切片 | 实施内容 |
|---|---|---|
| 1 | .6 | Fallback description |
| 2 | .5 | Bayesian update |
| 3 | .1 | Interoception |
| 4-5 | .2 | Predictive coding（LLM predict + compare） |
| 6-7 | .4 | Constructed emotion（LLM concept） |
| 8 | 集成 | 6 层融合 + 整体验收 |

---

_Generated by 小白 on 2026-06-16 06:30-。仅调研，不实施代码。_
