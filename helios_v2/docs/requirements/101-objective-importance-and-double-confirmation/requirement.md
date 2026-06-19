# Requirement 101 — 6-Dimensional Objective Importance + Double-Confirmation + P5-Ready Foundation

> **Status**: DRAFT v2 (P5-optimal 重构; 待主人拍板 §6 最终决策)
> **Owner**: `06 memory` (objective_importance + double_confirmation + cross-tick utility + loss/extractor interfaces) + `33 persistence` (hybrid storage) + `22 composition` (6-seam profile + wiring + training data extraction)
> **Goal**: 在 R100 `MemoryRecord` schema + 4-layer time stratification 之上，建立 **6 维客观重要性向量 + 客观-主观双重确认 gate + 跨 tick utility tracking + P5 学习循环数据底座**。让"什么值得持久化为 L4_long / L5_autobiographical"成为**客观 6 维 + 主观 R81 prediction + 跨 tick recall utility** 三信号共同决策的产物，所有可学习参数通过协议声明**让 P5 学习循环 plug-in 替换而不需重写 schema**。
> **前置**: R100 MemoryRecord schema + 4-layer time stratification (2026-06-18, df4bd39) + R96 真实语义 embedding + R98 post-LLM hormone adjustment + R81 hormone corroboration。
> **后续**: R102 Ebbinghaus 衰减 + 自动晋升（消费 R101 的 `recall_count` / `last_updated_at_wall` / `promotion_history`）+ R103 bounded-window/ANN 检索 + R104 memory_tool_channel + R105 forget 治理 fail-closed + **P5 学习循环**（消费 R101 的 `MemoryImportanceLoss` 接口 + `MemoryTrainingDatasetExtractor` seam，单独 R110+ requirement）。
> **β 分支参考**: `origin/aggressive-radical-persona-no-theater` 的 R85-A (`573dff4` 等) 预研了 6 维 `objective_importance` + LLM `llm_remember` + `OUTCOME_CLASS_WEIGHTS` + `should_persist` 三类决策 + `promote_layer` 跨 tick 晋升。本 R101 在 main 重新编号落地，**不复用** β 分支 commit hash；借鉴核心思路但**按 P5 最优解重构**（protocol 化 / 不 drop skip 类 / 增跨 tick utility / 声明 loss 接口）。

---

## 1. Background and Problem

### 1.1 R100 的局限

R100 已交付 `MemoryRecord` schema + 4-layer time stratification，由 `AffectOutcomeMemoryLayerClassifier` 在写入时刻按 `affect_intensity` + `outcome_class` 决定初始层。但**单维 salience 不足以表达"重要性"**——人脑决策一条记忆是否值得长期保留至少有 6 维独立输入（β 分支 R85-A 已预研）：
1. **刺激强度**（stimulus intensity）——文本/刺激的长度 + 复杂度
2. **应激响应**（cortisol_response）——HPA 轴激活程度
3. **唤醒度**（arousal_response）——皮层唤醒水平
4. **结局归类**（outcome_class_weight）——执行成功/失败/自变化/世界变化
5. **新颖度**（novelty_score）——与已有记忆的语义距离
6. **关系风险**（relationship_risk = 1 - social_safety）——人际关系脆弱性

R100 仅用 `affect_intensity` + `outcome_class` 两维，缺 1/3/5/6 维信息；且没有跨 tick utility 信号、没有为 P5 学习循环铺底。

### 1.2 P5 学习循环的需求

ROADMAP §5 / OWNER_GUIDE §2.6 / BRAIN_ARCHITECTURE_COMPARISON §5 已明确：**P5 学习循环**（权重 / 原型 / 衰减等可学习参数）是当前最大缺口。R88（漂移评估）/ R89（图灵 harness）/ R90（记忆保真探针）已交付**评估框架**，但**实际学习逻辑零实现**。

P5 学习循环需要的最小数据底座：
1. **可学习参数协议化**——`ObjectiveAggregator` 协议（不是硬编码凸组合；P5 可换 NN / 决策树 / 学得权重）
2. **训练数据全保留**——`skip` 类记录**不 drop**（是负样本训练数据，P5 必备）
3. **跨 tick utility tracking**——`recall_count` + `last_recall_at_tick` + `recall_utility_score` 字段（cross-tick reward = "回忆多少次 + 回忆时是否有用")
4. **时间衰减基础**——`last_updated_at_wall` 字段（给 R102 Ebbinghaus 用，给 P5 衰减学习用）
5. **晋升事件日志**——`promotion_history` 字段（R102 跨 tick 晋升时记录）
6. **Loss 接口声明**——`MemoryImportanceLoss` 协议（P5 plug-in；R101 只声明契约不实现）
7. **训练数据抽取 seam**——`MemoryTrainingDatasetExtractor` 协议（P5 训练时按需抽取）
8. **混合存储**——1 JSON 列存完整状态 + 4 indexed 列支持 P5 SQL query（`objective_score > 0.7 AND recall_count > 3 AND recall_utility > 0.5`）

### 1.3 β 分支 R85-A 的局限

β 分支 `aggressive-radical-persona-no-theater` 预研了 R85-A：
- 6 维 `objective_importance` 公式
- `OUTCOME_CLASS_WEIGHTS` 映射
- `should_persist(llm_remember, objective_score)` 三类决策
- `promote_layer(recall_count, objective_importance)` 跨 tick 晋升

β 分支局限：
1. **`should_persist` 用 LLM `llm_remember` 作 veto**——违背 R56/R57 owner boundary（LLM 不拥有持久化决策）
2. **`aggregate()` 硬编码凸组合**——P5 不可替换
3. **`skip` 类被丢弃**——P5 缺负样本
4. **无 loss 接口 / 无训练数据抽取**——P5 无法 plug-in
5. **存储未声明 hybrid**——P5 query 困难

R101 在 main 重新编号落地，按 **P5-optimal 重构**：所有可学习参数通过协议声明，所有训练数据保留，跨 tick utility 字段齐全，loss/extractor 接口声明。

## 2. Goal

在 R100 `MemoryRecord` 之上，建立 **6 维客观重要性向量 + 客观-主观双重确认 + 跨 tick utility tracking + P5 数据底座**：

**核心原则**：
- **6 维客观向量** → `ObjectiveImportanceVector` 6 维 ∈ `[0, 1]`，单调有界，确定性可算
- **协议化聚合** → `ObjectiveAggregator` 协议（首版：凸组合；P5 可换）
- **客观-主观 AND-gate** → R101's `DoubleConfirmationGate` 决策 4 类（`both_pass` / `objective_only` / `subjective_only` / `skip`）
- **Skip 类不 drop** → 全部 `MemoryRecord` 保留（标记 `skip` 是负样本）
- **跨 tick utility** → `recall_count` + `last_recall_at_tick` + `recall_utility_score` + `last_updated_at_wall` 字段齐全
- **晋升事件日志** → `promotion_history: tuple[PromotionEvent, ...]` 给 R102 用
- **Loss 接口声明** → `MemoryImportanceLoss` 协议（P5 plug-in；R101 不实现）
- **训练数据抽取 seam** → `MemoryTrainingDatasetExtractor` 协议（P5 训练时按需抽取）
- **混合存储** → 1 JSON 列 + 4 indexed 列（P5 SQL query 友好）

**最终目标**：`06` memory 写入路径成为 **P5 学习循环的训练数据源**——所有可学习参数通过协议声明，所有记录都带 cross-tick 信号，所有数据可被 SQL 抽取用于离线训练。

R101 **不**做：
- **实际 weight learning**（P5 scope；R101 仅声明协议）
- **Ebbinghaus 衰减逻辑**（R102；R101 仅声明字段）
- **bounded-window / ANN 检索**（R103）
- **memory_tool_channel**（R104）
- **forget 治理**（R105）
- **让 LLM 直接说"记不记"**（β 分支做法；R101 用 R81 `hormone_response_i_predict` 间接表达）

## 3. Functional Requirements

### 3.1 ObjectiveImportanceVector 契约（owner `06`）

1. 新增冻型 `ObjectiveImportanceVector`（`helios_v2/memory/contracts.py`）含 6 个 `[0, 1]` 字段：
   - `stimulus_intensity: float` —— 文本/刺激长度与复杂度代理（0..1）
   - `cortisol_response: float` —— 应激 HPA 通道响应（[0, 1]）
   - `arousal_response: float` —— 体感唤醒度（[0, 1]）
   - `outcome_class_weight: float` —— 结局归类权重（[0.20..0.95]）
   - `novelty_score: float` —— 与已有记忆的语义距离（1 - max_cosine，R34/R96 embedding）
   - `relationship_risk: float` —— `1 - social_safety`（[0, 1]）
2. 构造时 fail-fast：6 个值全部必须在 `[0, 1]`，否则 `MemoryAffectReplayError`。
3. 6 维 → JSON 序列化方法（`to_json() -> str` / `from_json(str) -> ObjectiveImportanceVector`），供 SQLite 持久化。
4. 不在 `ObjectiveImportanceVector` 上定义 `aggregate()`——**聚合通过 `ObjectiveAggregator` 协议**（见 §3.2），让 P5 plug-in。

### 3.2 ObjectiveAggregator 协议（owner `06`; **P5 关键 hooks #1**）

1. 新增协议 `ObjectiveAggregator`（`helios_v2/memory/objective_importance.py`）：
   ```python
   class ObjectiveAggregator(Protocol):
       def aggregate(self, vector: ObjectiveImportanceVector) -> float: ...
       def declared_weights(self) -> tuple[float, ...]: ...   # P5 introspection
   ```
2. `aggregate()` 返回 `[0, 1]`；`declared_weights()` 返回当前 6 维权重（用于 P5 introspection / explainability）。
3. 首版实现 `ConvexWeightedObjectiveAggregator`（同文件）：
   - 默认权重 `(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)`（β 分支已预研）
   - 权重声明在 `objective_importance_weights`（`MemoryLearnedParameterCategory` 新增 `"objective_importance_weights"`）
   - **关键**：构造时权重和必须为 1.0（否则 fail-fast）
4. **P5 替换路径**：`LearnedObjectiveAggregator` 由 P5 scope 实现（独立 R110+ requirement），用 R101 schema 的 `declared_weights()` introspection 接口读取当前权重，用训练数据更新；`06` 引擎不变。

### 3.3 OUTCOME_CLASS_WEIGHTS 映射（owner `06`）

1. 新增 `OUTCOME_CLASS_WEIGHTS: Mapping[str, float]`（`helios_v2/memory/contracts.py`），覆盖 `15` outcome taxonomy 全部取值：
   - `self_changed` → 0.95（最重：身份变化）
   - `world_changed` → 0.80（重：外部世界变化）
   - `continuity_written` → 0.70（中重：连续性被记录）
   - `executed` → 0.55（中：执行成功）
   - `rejected` → 0.40（轻：被拒）
   - `blocked` → 0.35（轻：被阻塞）
   - `internal_only_decision` → 0.25（轻：内部决策）
   - `no_outcome` → 0.20（最轻）
2. 未知 outcome_class → 0.50（中位默认值，绝不抛错；honest absence）。
3. **P5 替换路径**：`OUTCOME_CLASS_WEIGHTS` 通过 `objective_importance_weights` 类别学习；P5 用真实数据更新映射。

### 3.4 ObjectiveImportanceEstimator 协议（owner `06`）

1. 新增协议 `ObjectiveImportanceEstimator`（`helios_v2/memory/engine.py`）：
   ```python
   class ObjectiveImportanceEstimator(Protocol):
       def estimate(
           self,
           *,
           stimulus_text: str,
           hormone_snapshot: Mapping[str, float],
           feeling_snapshot: Mapping[str, float],
           outcome_class: str,
           recent_summaries: Sequence[str] = (),
           embed_callable: Callable[[str], Sequence[float]] | None = None,
       ) -> ObjectiveImportanceVector: ...
   ```
2. 首版实现 `FirstVersionObjectiveImportanceEstimator`（`helios_v2/memory/objective_importance.py`）：
   - `stimulus_intensity = min(1.0, len(stimulus_text) / 200.0)`（长度代理）
   - `cortisol_response = safe_get(hormone_snapshot, "cortisol", 0.5)`
   - `arousal_response = safe_get(feeling_snapshot, "arousal", 0.5)`
   - `outcome_class_weight = OUTCOME_CLASS_WEIGHTS.get(outcome_class, 0.5)`
   - `novelty_score = _novelty_cosine(stimulus_text, recent_summaries, embed_callable)`（1 - max_cosine；无 embed 时 0.5 中性）
   - `relationship_risk = 1.0 - safe_get(feeling_snapshot, "social_safety", 0.5)`
3. `embed_callable` 由 composition 注入（owner-neutral），`06` 不 import embedding owner。

### 3.5 DoubleConfirmationGate（owner `06`）

1. 新增 `DoubleConfirmationGate` 协议（`helios_v2/memory/objective_importance.py`）：
   ```python
   DoubleConfirmationClass = Literal["both_pass", "objective_only", "subjective_only", "skip"]

   @dataclass(frozen=True)
   class DoubleConfirmationResult:
       classification: DoubleConfirmationClass
       objective_score: float       # ObjectiveAggregator.aggregate(vector)
       subjective_score: float      # R81 hormone_prediction max
       confidence: float            # 0..1; 0 when subjective absent

   class DoubleConfirmationGate(Protocol):
       def evaluate(
           self,
           *,
           objective_score: float,
           subjective_score: float,
           subjective_confidence: float,
           outcome_class: str,
       ) -> DoubleConfirmationResult: ...
   ```
2. 首版实现 `FirstVersionDoubleConfirmationGate`（同文件）：
   - `OBJECTIVE_PASS_THRESHOLD = 0.50`（首版常量；`objective_importance_weights` 类别下）
   - `SUBJECTIVE_PASS_THRESHOLD = 0.60`（任一激素预测 > 0.6 即认为模型判断"对生理有显著影响"）
   - 决策：
     - `objective_score >= 0.50` ∧ `subjective_score >= 0.60` → `both_pass`
     - `objective_score >= 0.50` ∧ `subjective_score < 0.60` → `objective_only`
     - `objective_score < 0.50` ∧ `subjective_score >= 0.60` → `subjective_only`
     - 双低于阈值 → `skip`
3. `subjective_score` 的计算：读跨 tick carry 的 `hormone_response_i_predict`（R81 通道），取所有 9 通道预测的最大值；空 / None → `subjective_score = 0.0`, `confidence = 0.0`。
4. **关键不变量**：`skip` 类不 drop——`MemoryRecord` 仍产（layer=`L2_working`，`double_confirmation.classification="skip"`），**进入 33 持久化层作为负样本训练数据**（详见 §3.9）。

### 3.6 ObjectiveImportanceLayerResolver（owner `06`）

1. R100 已有 `AffectOutcomeMemoryLayerClassifier(affect_intensity, outcome_class) → MemoryLayer` 作为"初始层"。R101 不改此契约。
2. R101 新增 `ObjectiveImportanceLayerResolver`（`helios_v2/memory/objective_importance.py`）：**修正** R100 的初始层基于双确认结果：
   - `both_pass` → 在 R100 初始层基础上**保级或升级**：
     - R100 初始层 = `L5_autobiographical` → 保持
     - R100 初始层 = `L4_long` → 保持
     - R100 初始层 = `L3_short` ∧ `objective_score >= 0.70` → 升级到 `L4_long`
     - R100 初始层 = `L2_working` ∧ `objective_score >= 0.85` ∧ 命中 identity outcome → 升级到 `L5_autobiographical`（极端重要：客观分极高 + 自我变化 + 主观确认）
   - `objective_only` → 在 R100 初始层基础上**降级**：
     - R100 初始层 = `L4_long` ∧ `objective_score < 0.70` → 降到 `L3_short`
     - R100 初始层 = `L5_autobiographical` ∧ `objective_score < 0.85` → 降到 `L4_long`
     - 其他 → 保持
   - `subjective_only` → 保持 R100 初始层（不升不降；保守）
   - `skip` → layer 设为 `L2_working`（保守；负样本仍保留训练数据）
3. 升级 / 降级阈值（`0.70` / `0.85`）是首版常量，挂在 `objective_importance_weights` 类别下，P5 可学。
4. 此 resolver 注入到 `MemoryAffectReplayEngine` 替换 R100 默认的"直接用 R100 初始层"逻辑。当 resolver 缺席（legacy path / 默认装配）→ R100 行为 byte-for-byte 不变。

### 3.7 RecallUtilityTracker（owner `06`; **P5 关键 hooks #2**）

1. 新增协议 `RecallUtilityTracker`（`helios_v2/memory/objective_importance.py`）：
   ```python
   class RecallUtilityTracker(Protocol):
       def record_recall(self, record: MemoryRecord, current_tick: int) -> MemoryRecord: ...
       def record_utility(self, record: MemoryRecord, utility: float, current_tick: int) -> MemoryRecord: ...
   ```
2. 首版实现 `FirstVersionRecallUtilityTracker`（同文件）：
   - `record_recall`: `recall_count += 1`, `last_recall_at_tick = current_tick`, 返回新 `MemoryRecord`（immutable）
   - `record_utility`: 用 EMA（指数移动平均）更新 `recall_utility_score`：`new = α * utility + (1-α) * old`，α = 0.3 首版常量
3. `MemoryRecord` 增 4 个 additive 字段：
   - `recall_count: int = 0`
   - `last_recall_at_tick: int | None = None`
   - `recall_utility_score: float | None = None`（`recall_count == 0` 时 None；首次 utility 后初始化）
   - `last_updated_at_wall: float | None = None`（**R102 Ebbinghaus 衰减用** + P5 衰减学习用）
4. **R101 仅实现 tracker 协议 + EMA 更新**；**utility 的语义判定**（"这次回忆是否有用"）留给 R102 / P5（需要 cross-tick action outcome 信号）。
5. `record_recall` / `record_utility` 在 tick N+1 评估 tick N 的 memory 时调用——carry seam 仿 R49 / R62 / R67 模式。

### 3.8 PromotionEvent + promotion_history（owner `06`; 给 R102 用）

1. 新增冻型 `PromotionEvent`（`helios_v2/memory/contracts.py`）：
   ```python
   @dataclass(frozen=True)
   class PromotionEvent:
       event_id: str
       from_layer: MemoryLayer
       to_layer: MemoryLayer
       tick_id: int
       wall_seconds: float | None
       reason: str   # "recall_count_threshold" | "objective_score_threshold" | "decay_rebalance" | ...
   ```
2. `MemoryRecord` 增 additive `promotion_history: tuple[PromotionEvent, ...] = ()`（默认空 tuple；bounded by R102 上限）。
3. R101 **不实现自动晋升逻辑**（留给 R102），但声明字段 + 数据结构，让 R102 / P5 直接 append 而不重写 schema。

### 3.9 MemoryImportanceLoss 接口（owner `06`; **P5 关键 hooks #3**）

1. 新增协议 `MemoryImportanceLoss`（`helios_v2/memory/objective_importance.py`）：
   ```python
   class MemoryImportanceLoss(Protocol):
       def loss(
           self,
           *,
           predicted_objective_score: float,
           observed_recall_utility: float | None,
           recall_count: int,
           record: MemoryRecord,
       ) -> float: ...
   ```
2. **R101 不实现 `MemoryImportanceLoss`**——仅声明契约。P5 scope（独立 R110+ requirement）会提供：
   - `MseImportanceLoss`（MSE 损失）
   - `HuberImportanceLoss`（Huber 损失，鲁棒）
   - `ContrastiveImportanceLoss`（对比损失，基于 recall utility 排序）
3. `MemoryAffectReplayEngine` 不持有 `MemoryImportanceLoss` 引用——P5 scope 在独立 training harness 中使用。

### 3.10 MemoryTrainingDatasetExtractor 接口（owner `06`; **P5 关键 hooks #4**）

1. 新增协议 `MemoryTrainingDatasetExtractor`（`helios_v2/memory/objective_importance.py`）：
   ```python
   @dataclass(frozen=True)
   class MiningRecord:
       memory_id: str
       objective_vector: ObjectiveImportanceVector
       objective_score: float
       subjective_score: float | None
       double_confirmation_class: DoubleConfirmationClass
       recall_count: int
       recall_utility_score: float | None
       last_updated_at_wall: float | None
       layer: MemoryLayer
       outcome_class: str
       tick_id: int | None

   class MemoryTrainingDatasetExtractor(Protocol):
       def extract_mining_dataset(
           self,
           *,
           min_recall_count: int = 0,
           min_objective_score: float = 0.0,
           layer_filter: tuple[MemoryLayer, ...] | None = None,
           double_confirmation_filter: tuple[DoubleConfirmationClass, ...] | None = None,
           since_wall_seconds: float | None = None,
           limit: int | None = None,
       ) -> tuple[MiningRecord, ...]: ...
   ```
2. 首版实现 `SqlBackedTrainingDatasetExtractor`（`helios_v2/memory/objective_importance.py`，同文件）：
   - 通过 `ExperienceStore` facade 调 `search_similar` / `read_recent`
   - 应用所有 filter 字段
   - 投影 `PersistedExperienceRecord` → `MiningRecord`
3. **关键**：filter 字段让 P5 可以按需抽取训练数据子集：
   - "所有 `skip` 类 + `recall_count > 0`" → 训练 recall failure detector
   - "所有 `L4_long` + `recall_utility_score > 0.7`" → 训练 success-reinforced weights
   - "所有 `last_updated_at_wall < T`" → 训练 decay 模型
4. P5 scope 用此 seam 抽数据训练。

### 3.11 PersistedExperienceRecord 扩展（owner `33`）

1. `PersistedExperienceRecord` 增 additive：
   - `objective_importance_json: str | None = None`（完整 6 维 JSON；P5 抽取完整 state 用）
   - `objective_score: float | None = None`（聚合分；indexed）
   - `subjective_score: float | None = None`（主观 R81 max；indexed）
   - `double_confirmation_class: DoubleConfirmationClass | None = None`（indexed）
   - `recall_count: int | None = None`（默认 0；indexed；P5 训练特征）
   - `recall_utility_score: float | None = None`（P5 ground truth signal）
   - `last_updated_at_wall: float | None = None`（R102 衰减 + P5 decay learning）
   - `promotion_history_json: str | None = None`（R102 写入；R101 仅声明列）
2. 持久化方案：**混合存储**（方案 C）—— 1 JSON 列 + 4 indexed 列：
   - `objective_importance_json TEXT`（nullable）—— 完整向量
   - `objective_score REAL`（nullable, indexed via query；非真实 SQL index，避免 schema 复杂化）
   - `subjective_score REAL`（nullable）
   - `double_confirmation_class TEXT`（nullable）
   - `recall_count INTEGER`（nullable）
3. SQLite `ALTER TABLE` PRAGMA-guarded 增 5 列（4 indexed + 1 JSON）；pre-existing 行读 `None`。
4. `__post_init__` 校验：当 `objective_score is not None`，clamp `[0, 1]`；当 `recall_count is not None`，`>= 0`；`double_confirmation_class` 必须在合法枚举内；`objective_importance_json` 必须可被 `ObjectiveImportanceVector.from_json` 解析。
5. **P5 query 支持**：SQL `WHERE objective_score > 0.7 AND recall_count > 3 AND recall_utility_score > 0.5 AND double_confirmation_class IN ('both_pass', 'objective_only')` 直接可执行（4 个 indexed 列）。

### 3.12 Composition wiring

1. `RuntimeProfile` 增 6 个 seam（fail-fast 同进同出）：
   - `objective_importance_estimator: ObjectiveImportanceEstimator | None`
   - `objective_aggregator: ObjectiveAggregator | None`
   - `double_confirmation_gate: DoubleConfirmationGate | None`
   - `objective_layer_resolver: ObjectiveImportanceLayerResolver | None`
   - `recall_utility_tracker: RecallUtilityTracker | None`
   - `training_dataset_extractor: MemoryTrainingDatasetExtractor | None`
2. `__post_init__` 校验：6 个 seam 必须同进同出（要么全 None 走 legacy，要么全 wire）。这是 fail-fast。
3. Semantic 装配 wire 全部：`FirstVersionObjectiveImportanceEstimator()` + `ConvexWeightedObjectiveAggregator()` + `FirstVersionDoubleConfirmationGate()` + `ObjectiveImportanceLayerResolver(threshold_promote=0.70, threshold_demote=0.85)` + `FirstVersionRecallUtilityTracker()` + `SqlBackedTrainingDatasetExtractor()`。
4. Default 装配 / legacy 装配 → 6 个 None → R100 byte-for-byte 不变。
5. `assemble_production_runtime()` 继承 semantic 装配。
6. composition 投影 6 维 + double_confirmation + scores + recall fields + JSON 到 `PersistedExperienceRecord`（通过 `ExperienceRecordBridge` / `MemoryRecordBridge`）。
7. `embed_callable` 由 composition 注入 `FirstVersionObjectiveImportanceEstimator`（owner-neutral glue）；estimator 不 import embedding owner。
8. `SqlBackedTrainingDatasetExtractor` 由 composition 通过 `ExperienceStore` 注入（owner-neutral）；extractor 不直接 import persistence owner。

## 4. Non-Functional Requirements

1. **Additive-first**：所有契约扩展均为 additive（默认 None / 0 / 空 tuple 走 legacy path）。R100 baseline 1329+ 测试零回归。
2. **Migration-safe**：SQLite `ALTER TABLE` 加 5 列（PRAGMA-guarded 幂等）；pre-existing 行读全部 `None` / `0`。
3. **Owner boundary**（R56/R57 精神）：
   - `06` 拥有 6 维向量 + aggregator 协议 + OUTCOME_CLASS_WEIGHTS + gate 协议 + layer 升级 / 降级 + recall utility tracker 协议 + loss 接口声明 + extractor 接口声明
   - `33` 拥有持久化（不解释向量 / 不计算聚合分）
   - `22` 拥有 wiring + 注入（仅 projector / 不持有协议实现）
   - **LLM 不直接决定"记不记"**——只通过 R81 `hormone_response_i_predict` 间接表达
   - **P5 不在 R101 范围内**——R101 仅声明契约，P5 scope（独立 R110+）实现
4. **C_engineering_hypothesis**：6 维权重、AND-gate 阈值、升级 / 降级阈值、EMA α 都是首版常量（`objective_importance_weights` 类别），P5 可学。
5. **Honest absence**：
   - 缺 `embed_callable` → `novelty_score = 0.5`（中性，不是 0）
   - 缺 `hormone_prediction` → `subjective_score = 0.0`, `confidence = 0.0`
   - 缺 `hormone_snapshot` / `feeling_snapshot` 任一字段 → 维度默认 0.5（中性）
   - 未知 `outcome_class` → 0.5（中性，绝不抛错）
   - 缺 utility signal → `recall_utility_score = None`（不伪造，P5 训练时可过滤）
6. **Performance**：
   - `ObjectiveImportanceEstimator.estimate` 是无状态纯函数（除 `embed_callable`），O(1) per record
   - `ObjectiveAggregator.aggregate` 是 O(1)
   - `DoubleConfirmationGate.evaluate` 是 O(1)
   - `RecallUtilityTracker.record_recall` / `record_utility` 是 O(1) immutable update
   - `MemoryTrainingDatasetExtractor.extract_mining_dataset` 是 O(N) over filtered set；P5 调用频次可控
   - 不引入 ANN / bounded-window（R103 范围）
7. **Compatibility**：所有 1329 个 R100 baseline 测试零回归；R99 emotion probe baseline 不破；R88 drift evaluator baseline 不破。
8. **P5 forward-compatibility**：所有可学习参数（aggregator 权重、gate 阈值、layer resolver 阈值、tracker EMA α、OUTCOME_CLASS_WEIGHTS）通过协议声明或 `MemoryLearnedParameterCategory` 声明；P5 可 plug-in 替换实现而不改 schema / 不改 contract 形状。

## 5. Code Behavior Constraints

1. **Forbidden**：`06` import `helios_v2.persistence` 或 `helios_v2.embedding` 或 `helios_v2.llm` —— 持久化 / embedding / LLM 由 composition 注入
2. **Forbidden**：用 LLM 字段（除 R81 `hormone_response_i_predict`）做持久化决策 —— 避免 prompt theater
3. **Forbidden**：`MemoryAffectReplayEngine` 不持有 `MemoryImportanceLoss` 引用 —— P5 在独立 training harness 中用
4. **Forbidden**：`ObjectiveAggregator.aggregate` 在 `ObjectiveImportanceVector` 内 hardcode —— 必须通过协议
5. **Forbidden**：hardcode `OUTCOME_CLASS_WEIGHTS` 数值在 composition 或 `13 planner_bridge` —— 归 `06` owner
6. **Forbidden**：直接修改 R100 `AffectOutcomeMemoryLayerClassifier` 的初始层决策表 —— R101 用 resolver 在其之上**覆盖**（不替换 R100 契约）
7. **Forbidden**：在没有 `embed_callable` 时让 `novelty_score` 退化为 0 或 1 —— 退化为 0.5（中性）
8. **Forbidden**：drop `skip` 类 `MemoryRecord` —— 必须保留为训练数据
9. **Forbidden**：`MemoryTrainingDatasetExtractor` 直接 import `helios_v2.persistence` —— 通过 `ExperienceStore` facade
10. **Forbidden**：在不升级 owner 的情况下用 `aggregator.declared_weights()` 之外的 introspection —— P5 训练只读 declared_weights()，不读内部状态
11. **Boundary**：
    - `06` 拥有所有协议 + 6 维 + recall utility tracker + loss/extractor 接口声明
    - `33` 拥有持久化（不解释向量）
    - `22` 拥有 wiring + 注入（仅 projector）
    - 其他 owner 不参与

## 6. Open Design Decisions (最终 4 个; 已按 P5-optimal 标注默认)

### 6.1 持久化方案（已选 方案 C = 混合存储）

**方案 C（已选）**：1 JSON 列 (`objective_importance_json TEXT`) + 4 indexed 列 (`objective_score REAL` / `subjective_score REAL` / `double_confirmation_class TEXT` / `recall_count INTEGER`)
- **优点**：P5 SQL query 直接可执行（"objective_score > 0.7 AND recall_count > 3"）；JSON 保留完整状态供 P5 抽取；与 R100 / R45 / R92 列式风格一致
- **缺点**：列数适中（5 列 + R100 17 列 = 22 列）
- **依据**：P5 训练需要 SQL 批量抽取；JSON 单列无法支持 query

### 6.2 Skip 类处理（已选 方案 Y = 保留为负样本）

**方案 Y（已选）**：`MemoryRecord(layer="L2_working", double_confirmation_class="skip")` 仍写入 `33` store；标 `skip` 是负样本训练数据
- **优点**：P5 训练可同时用正样本（`both_pass` / `objective_only` 升级到 L4+）和负样本（`skip`）做监督学习；保留完整 `recall_count` / `recall_utility_score` 跨 tick 信号
- **缺点**：store 体积略大（多 ~30% 记录——取决于 skip 比例）
- **依据**：P5 supervised learning 必备负样本；R88 drift evaluator 期望完整 store

### 6.3 6 维权重与 gate 阈值（已选 β 分支原版 P1）

**方案 P1（已选）**：权重 `(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)`；gate 阈值 `OBJECTIVE_PASS = 0.50`, `SUBJECTIVE_PASS = 0.60`；layer upgrade 阈值 `0.70` / demote `0.85`
- **依据**：β 分支 R85-A 已预研；P5 可学（权重 / 阈值都在 `objective_importance_weights` 类别下）

### 6.4 跨 tick hormone prediction（已选 S1 = 同 tick）

**方案 S1（已选）**：用**同 tick** R81 `hormone_response_i_predict`（11 → 06 直接传递，不跨 tick）
- **依据**：最简单；同 tick 已反映"模型此刻认为重要"。**跨 tick recall utility 信号另由 `RecallUtilityTracker.record_utility` 捕获**（不需要 cross-tick R81 carry）
- **P5 训练**：P5 用 `recall_utility_score` 作 ground truth signal，而非依赖跨 tick R81 carry

### 6.5 6 个 seam 的同进同出校验（建议 方案 X）

- **方案 X（建议）**：6 个 seam 必须同进同出（要么全 None 走 legacy，要么全 wire）
- **方案 Y**：每 seam 独立（部分 None 部分 wire 走部分 legacy + 部分 R101）

**建议方案 X** —— R101 是统一切片，semantic 装配应当全 wire；legacy / default 装配应当全 None

### 6.6 P5 学习循环的时机（建议 方案 1）

- **方案 1（建议）**：R110+ 单独 requirement（P5 不在 R101 scope）
- **方案 2**：R101 内含 P5 first-version 实现（小步快跑）

**建议方案 1** —— R101 范围已大（6 个新协议 + 9 个字段 + 5 列 + 6 个 owner 引用），混入 P5 会让切片过大；P5 应当单独切片以便 focus

## 7. Impacted Modules

1. `helios_v2/memory/contracts.py` — NEW `ObjectiveImportanceVector` (含 `to_json`/`from_json`), `OUTCOME_CLASS_WEIGHTS`, `DoubleConfirmationClass`, `DoubleConfirmationResult`, `PromotionEvent`; `MemoryRecord` 增 `objective_importance` / `objective_score` / `subjective_score` / `double_confirmation` / `recall_count` / `last_recall_at_tick` / `recall_utility_score` / `last_updated_at_wall` / `promotion_history`; `MemoryLearnedParameterCategory` 加 `"objective_importance_weights"`
2. `helios_v2/memory/objective_importance.py` (NEW) — `ObjectiveAggregator` protocol + `ConvexWeightedObjectiveAggregator`, `ObjectiveImportanceEstimator` protocol + `FirstVersionObjectiveImportanceEstimator`, `DoubleConfirmationGate` protocol + `FirstVersionDoubleConfirmationGate`, `ObjectiveImportanceLayerResolver` + helpers, `RecallUtilityTracker` protocol + `FirstVersionRecallUtilityTracker`, `MemoryImportanceLoss` protocol, `MemoryTrainingDatasetExtractor` protocol + `SqlBackedTrainingDatasetExtractor`, `MiningRecord`, `_novelty_cosine`, `_safe_get`
3. `helios_v2/memory/engine.py` — `MemoryAffectReplayEngine` 增 5 注入点 (estimator / aggregator / gate / layer_resolver / recall_tracker); record_state 路径消费 5 个；`MemoryAffectReplayStageResult.memory_records` 已存在，引擎内部用 R101 决策填
4. `helios_v2/memory/__init__.py` — 导出所有新协议 / 冻型 / 实现
5. `helios_v2/persistence/contracts.py` — `PersistedExperienceRecord` 增 8 个 additive 字段 (5 列)
6. `helios_v2/persistence/engine.py` — SQLite `ALTER TABLE` PRAGMA-guarded 增 5 列；`_row_to_record` 读新列
7. `helios_v2/composition/bridges.py` — `ExperienceRecordBridge` / `MemoryRecordBridge` 投影 8 个字段（含 JSON 序列化）
8. `helios_v2/composition/runtime_composition.py` — `RuntimeProfile` 增 6 seam + `__post_init__` 同进同出校验；semantic 装配 wire 6 个
9. `helios_v2/tests/test_objective_importance_*.py` (NEW ×3) — `ObjectiveAggregator` + `DoubleConfirmationGate` + `ObjectiveImportanceLayerResolver`
10. `helios_v2/tests/test_recall_utility_tracker.py` (NEW) — tracker protocol + EMA update
11. `helios_v2/tests/test_training_dataset_extractor.py` (NEW) — extractor seam + filter combinations
12. `helios_v2/tests/test_memory_engine_dual_confirmation.py` (NEW) — engine 集成 5 注入点
13. `helios_v2/tests/test_persistence_objective_importance_*.py` (NEW ×2) — 持久化 + migration + JSON round-trip
14. `helios_v2/tests/test_runtime_six_seam_wiring.py` (NEW) — composition 6 seam 同进同出校验
15. `docs/requirements/101-.../{requirement,design,task}.md` (NEW) — 本三件套
16. `docs/requirements/index.md` — 加 R101 行
17. `docs/ROADMAP.zh-CN.md` — 同步 R101 状态（"P5-ready foundation"）
18. `docs/PROGRESS_FLOW.zh-CN.md` / `en.md` — 同步 06 / 33 / 22 状态
19. `docs/ARCHITECTURE_BOUNDARIES.md` — 6 维 + 双重确认 + P5 接口 boundary 真相
20. `docs/OWNER_GUIDE.zh-CN.md` — 02 节 06 owner 升级（P5-ready 标注）
21. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — `gap_persistence_and_learning` row 标注 R101 是 P5 入口

## 8. Acceptance Criteria

1. `ObjectiveImportanceVector` 6 维 ∈ [0, 1]；构造时 6 维全在 [0, 1] 否则 `MemoryAffectReplayError`；`to_json` / `from_json` 双向 round-trip 成功。
2. `ObjectiveAggregator` 协议 + `ConvexWeightedObjectiveAggregator` 首版实现；构造时权重和必须为 1.0；`declared_weights()` 返回 6 维 tuple。
3. `FirstVersionObjectiveImportanceEstimator.estimate` 在已知 stimulus + hormone + feeling + outcome + recent_summaries + embed_callable 输入下，6 维 deterministic 计算；缺字段时回退到 §4.5 honest absence。
4. `FirstVersionDoubleConfirmationGate.evaluate` 按 §3.5 决策表输出 `DoubleConfirmationResult.classification ∈ {both_pass, objective_only, subjective_only, skip}`。
5. `ObjectiveImportanceLayerResolver.resolve(R100_initial_layer, objective_score, double_confirmation_class, outcome_class) → MemoryLayer` 按 §3.6 表正确升级 / 降级 / skip→L2_working。
6. `MemoryRecord` 增 9 个 additive 字段（`objective_importance` / `objective_score` / `subjective_score` / `double_confirmation` / `recall_count` / `last_recall_at_tick` / `recall_utility_score` / `last_updated_at_wall` / `promotion_history`）；legacy path（缺所有 R101 seam）不变。
7. **skip 类不 drop**：`double_confirmation.classification == "skip"` 的 `MemoryRecord` 仍写入 `33` store，layer=`L2_working`。
8. `FirstVersionRecallUtilityTracker.record_recall` 增加 `recall_count`，更新 `last_recall_at_tick`；`record_utility` 用 EMA 更新 `recall_utility_score`。
9. `PersistedExperienceRecord` 增 8 个 additive 字段；SQLite PRAGMA-guarded `ALTER TABLE` 增 5 列幂等；`objective_importance_json` round-trip 成功。
10. P5 SQL query 可执行：测试断言 `WHERE objective_score > 0.7 AND recall_count > 3 AND double_confirmation_class IN ('both_pass', 'objective_only')` 能返回正确 records。
11. `MemoryTrainingDatasetExtractor.extract_mining_dataset` 按 6 个 filter 字段正确抽取；返回 `tuple[MiningRecord, ...]`；filter 组合全测试覆盖。
12. `RuntimeProfile` 6 seam 同进同出校验：缺一即 `CompositionError`；semantic 装配 wire 6 个；default 装配全 None → R100 byte-for-byte 不变。
13. R100 baseline 1329 测试零回归；R99 emotion probe baseline 不破；R88 drift evaluator baseline 不破。
14. **P5 forward-compatibility**：所有可学习参数（aggregator 权重 / gate 阈值 / layer resolver 阈值 / tracker EMA α / OUTCOME_CLASS_WEIGHTS）通过协议 + `MemoryLearnedParameterCategory` 声明；测试断言 P5 可注入自定义 aggregator / gate / loss / extractor 而不改 schema。
15. R101 三件套文档完整（requirement.md, design.md, task.md）；`index.md` / `ROADMAP` / `PROGRESS_FLOW` / `ARCHITECTURE_BOUNDARIES` / `OWNER_GUIDE` / `BRAIN_ARCHITECTURE_COMPARISON` 同步。
16. R56/R57 owner-boundary guard 仍然绿（`tests/test_composition_owner_boundary_guard.py`）。
17. R21 observability guard 仍然绿（`tests/test_no_adhoc_logging_guard.py`）。
18. R95 followup C1-C6 no-hardcoded-op-name guard 仍然绿（`tests/test_no_hardcoded_op_names_in_engines.py`）。