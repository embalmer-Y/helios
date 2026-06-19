# Requirement 101 — Design: 6-Dimensional Objective Importance + Double-Confirmation + P5-Ready Foundation

## 1. Title

Requirement 101 — Design: 6-Dimensional Objective Importance + Double-Confirmation + P5-Ready Foundation

## 2. Design Overview

R101 在 R100 `MemoryRecord` schema + 4-layer time stratification 之上，建立 **6 维客观重要性向量 + 客观-主观双重确认 gate + 跨 tick utility tracking + P5 学习循环数据底座**。设计遵循六原则：

1. **Cognitive contract separation**：`06` memory 拥有 6 维向量 + aggregator / gate / layer resolver / recall tracker / loss / extractor 协议声明；`33` 持久化只存储投影不解释；`22` 装配只 wire 不持有策略。
2. **Protocol-first**：所有可学习参数通过 `Protocol` + 首版实现声明（P5 plug-in 不重写 schema）。4 个关键协议：`ObjectiveAggregator` / `DoubleConfirmationGate` / `RecallUtilityTracker` / `MemoryImportanceLoss` / `MemoryTrainingDatasetExtractor`。
3. **Skip 不 drop**：`double_confirmation.classification == "skip"` 的 `MemoryRecord` 仍写入 `33` store（layer=`L2_working`）—— 这些是 P5 supervised learning 的负样本。
4. **Cross-tick utility**：新增 `recall_count` / `last_recall_at_tick` / `recall_utility_score` / `last_updated_at_wall` / `promotion_history` 字段，让 P5 用 cross-tick reward 作 ground truth signal。
5. **Hybrid storage**：1 JSON 列 (`objective_importance_json`) + 4 indexed 列 (`objective_score` / `subjective_score` / `double_confirmation_class` / `recall_count`) —— P5 SQL query 友好。
6. **P5 forward-compatibility**：所有可学习参数（aggregator 权重、gate 阈值、layer resolver 阈值、tracker EMA α、OUTCOME_CLASS_WEIGHTS）通过 `MemoryLearnedParameterCategory` 声明（"objective_importance_weights"），P5 plug-in 替换实现。

## 3. Current State and Gap

### 3.1 R100 当前路径

`MemoryAffectReplayEngine.record_state` 流程：
1. 收 `InteroceptiveFeelingState` + optional `MemoryBindingContext` + `outcome_class` (R100)
2. `AffectGroundedMemoryFormationPath` 形成 `AffectTaggedMemoryItem`（real affect-tag）
3. `SalienceGatedReplayCandidateSelector` 算 `affect_intensity` + 设 `forced_consolidation`
4. **`AffectOutcomeMemoryLayerClassifier(affect_intensity, outcome_class) → MemoryLayer`** —— R100 单维 salience 决策
5. 产 `MemoryRecord`（当 classifier 注入时）+ `MemoryReplayCandidate`
6. composition `ExperienceRecordBridge` 投影到 `PersistedExperienceRecord(layer=..., memory_metadata={...})`

### 3.2 R100 的 Gap

| Gap | 说明 | R101 修复 |
|---|---|---|
| 单维 salience | `affect_intensity` + `outcome_class` 2 维，缺 stimulus_intensity / cortisol / arousal / novelty / relationship_risk | 6 维 `ObjectiveImportanceVector` |
| LLM 主观信号缺失 | 无 R81 hormone prediction 对照 | `DoubleConfirmationGate` 用 R81 max hormone pred |
| 跨 tick utility 缺失 | 无 `recall_count` / `recall_utility_score` 字段 | 4 个新字段 + `RecallUtilityTracker` |
| 不可学习 | aggregator / gate / thresholds 全 hardcode | 5 个 Protocol + `objective_importance_weights` 类别 |
| 无 P5 数据底座 | 无 loss interface / training dataset extractor / hybrid storage | 5 维接口 + 5 列 SQLite |
| 训练数据不全 | skip 类如 drop 则缺负样本 | skip 类保留为负样本 |

### 3.3 β 分支 R85-A 当前实现（参考）

β 分支已落地（仅在 `origin/aggressive-radical-persona-no-theater`）：
- 6 维 `objective_importance` 函数（concave weighted sum）
- `OUTCOME_CLASS_WEIGHTS` 映射（8 个 outcome class）
- `should_persist(llm_remember, objective_score)` 三类决策（skip / persist_low / persist_full）
- `promote_layer(recall_count, objective_importance)` 跨 tick 晋升

β 分支局限（已在 requirement.md §1.3 详述）：用 LLM `llm_remember` 作 veto、aggregate 硬编码、skip drop、无 loss/extractor、存储未 hybrid。

## 4. Target Architecture

### 4.1 数据流（semantic 装配）

```
11 Internal Thought
   → ThoughtCycleResult.hormone_response_i_predict (R81)
      ↓ (composition 投影到 prompt_contract_summary)
06 MemoryAffectReplayEngine.record_state
   ├─→ ObjectiveImportanceEstimator.estimate(...)
   │   └─→ ObjectiveImportanceVector (6 维)
   │
   ├─→ ObjectiveAggregator.aggregate(vector)
   │   └─→ objective_score [0,1]
   │
   ├─→ DoubleConfirmationGate.evaluate(objective, subjective_R81)
   │   └─→ DoubleConfirmationResult(classification ∈ {both_pass, objective_only, subjective_only, skip})
   │
   ├─→ AffectOutcomeMemoryLayerClassifier(affect_intensity, outcome_class)
   │   └─→ initial_layer (R100)
   │
   ├─→ ObjectiveImportanceLayerResolver.resolve(initial_layer, objective_score, classification, outcome_class)
   │   └─→ final_layer ∈ {L2_working, L3_short, L4_long, L5_autobiographical}
   │
   └─→ For each forced_consolidation candidate:
       └─→ MemoryRecord(
             objective_importance=vector,
             objective_score=agg,
             subjective_score=R81_max,
             double_confirmation=result,
             layer=final_layer,
             recall_count=0,
             last_recall_at_tick=None,
             recall_utility_score=None,
             last_updated_at_wall=tick_wall_seconds,
             promotion_history=(),
           )
      ↓ (composition ExperienceRecordBridge / MemoryRecordBridge)
33 ExperienceStore
   ├─→ SQLite (objective_importance_json + 4 indexed columns)
   ├─→ search_similar / read_recent (P5 queryable)
   └─→ SqlBackedTrainingDatasetExtractor.extract_mining_dataset(...)
      └─→ tuple[MiningRecord, ...] for P5 training

(后续 tick) 10 Directed Retrieval recall → RecallUtilityTracker.record_recall(record, current_tick)
  → record.recall_count += 1
  → record.last_recall_at_tick = current_tick
  (R102 接入 utility 判定时) RecallUtilityTracker.record_utility(record, utility, current_tick)
  → record.recall_utility_score = EMA(utility, α=0.3)
  → record.last_updated_at_wall = tick_wall_seconds
```

### 4.2 数据流（default 装配 / legacy path）

```
06 MemoryAffectReplayEngine.record_state
   → 6 seam 全 None → R100 路径 byte-for-byte 不变
   → 不产 R101-only 字段
   → 不写 PersistedExperienceRecord 新列（None）
```

### 4.3 Skip 类处理（关键 P5 设计决策）

```
double_confirmation.classification == "skip":
   ├─ MemoryRecord 仍产（layer = L2_working）
   ├─ 写入 33 store（保留为负样本训练数据）
   ├─ recall_count / recall_utility_score 默认 0 / None
   └─ P5 用 `WHERE double_confirmation_class = 'skip' AND recall_count > N` 抽取 recall failure detector 训练集
```

### 4.4 Cross-tick Utility Carry

```
tick N:   record_utility triggers when downstream decision references this memory (R102 scope)
   ├─ MemoryRecord.recall_utility_score = EMA(new_utility, α=0.3)
   └─ MemoryRecord.last_updated_at_wall = tick_wall_seconds(N+1)

(R101 只实现 record_recall / record_utility 协议 + EMA 更新；
 utility 语义判定 "这次回忆是否有用" 留给 R102 + P5)
```

## 5. Data Structures

### 5.1 `ObjectiveImportanceVector` (NEW in `helios_v2/memory/contracts.py`)

```python
@dataclass(frozen=True)
class ObjectiveImportanceVector:
    """6-dimensional objective importance vector (R101).
    Owner: 06 memory.
    """
    stimulus_intensity: float         # [0, 1]
    cortisol_response: float          # [0, 1]
    arousal_response: float           # [0, 1]
    outcome_class_weight: float       # [0.20, 0.95]
    novelty_score: float              # [0, 1]
    relationship_risk: float          # [0, 1]

    def __post_init__(self) -> None:
        for name in ("stimulus_intensity", "cortisol_response", "arousal_response",
                     "outcome_class_weight", "novelty_score", "relationship_risk"):
            v = getattr(self, name)
            if v < 0.0 or v > 1.0:
                raise MemoryAffectReplayError(f"ObjectiveImportanceVector.{name} must be in [0, 1]")

    def to_json(self) -> str:
        return json.dumps({
            "stimulus_intensity": self.stimulus_intensity,
            "cortisol_response": self.cortisol_response,
            "arousal_response": self.arousal_response,
            "outcome_class_weight": self.outcome_class_weight,
            "novelty_score": self.novelty_score,
            "relationship_risk": self.relationship_risk,
        }, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def from_json(s: str) -> ObjectiveImportanceVector:
        d = json.loads(s)
        return ObjectiveImportanceVector(**d)
```

### 5.2 `OUTCOME_CLASS_WEIGHTS` (NEW in `helios_v2/memory/contracts.py`)

```python
OUTCOME_CLASS_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "self_changed": 0.95,
    "world_changed": 0.80,
    "continuity_written": 0.70,
    "executed": 0.55,
    "rejected": 0.40,
    "blocked": 0.35,
    "internal_only_decision": 0.25,
    "no_outcome": 0.20,
})
# Unknown outcome_class → 0.5 default (honest absence)
```

### 5.3 `DoubleConfirmationClass` + `DoubleConfirmationResult` (NEW)

```python
DoubleConfirmationClass = Literal["both_pass", "objective_only", "subjective_only", "skip"]

@dataclass(frozen=True)
class DoubleConfirmationResult:
    classification: DoubleConfirmationClass
    objective_score: float       # [0, 1]
    subjective_score: float      # [0, 1]; 0.0 when absent
    confidence: float            # [0, 1]; 0.0 when subjective absent
```

### 5.4 `PromotionEvent` (NEW)

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

### 5.5 `MemoryRecord` Additive Extensions (9 fields)

```python
@dataclass(frozen=True)
class MemoryRecord:
    # ... existing fields ...
    # R101 additive (P5-ready):
    objective_importance: ObjectiveImportanceVector | None = None
    objective_score: float | None = None
    subjective_score: float | None = None
    double_confirmation: DoubleConfirmationResult | None = None
    recall_count: int = 0
    last_recall_at_tick: int | None = None
    recall_utility_score: float | None = None
    last_updated_at_wall: float | None = None
    promotion_history: tuple[PromotionEvent, ...] = ()
```

### 5.6 `PersistedExperienceRecord` Additive Extensions (8 fields)

```python
@dataclass(frozen=True)
class PersistedExperienceRecord:
    # ... existing fields ...
    # R101 additive (P5 hybrid storage):
    objective_importance_json: str | None = None        # full 6-dim JSON
    objective_score: float | None = None               # indexed
    subjective_score: float | None = None              # indexed
    double_confirmation_class: DoubleConfirmationClass | None = None  # indexed
    recall_count: int | None = None                    # indexed (default 0)
    recall_utility_score: float | None = None
    last_updated_at_wall: float | None = None
    promotion_history_json: str | None = None
```

### 5.7 `MiningRecord` (NEW in `helios_v2/memory/objective_importance.py`)

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
```

## 6. Module Changes

### 6.1 NEW `helios_v2/memory/objective_importance.py` (300-400 LOC)

Contents:
- `_safe_get(mapping, key, default=0.5) -> float` — bounded default helper
- `_novelty_cosine(stimulus_text, recent_summaries, embed_callable) -> float` — 1 - max_cosine
- `OUTCOME_PASS_THRESHOLD = 0.50`, `SUBJECTIVE_PASS_THRESHOLD = 0.60` (constants)
- `PROMOTE_THRESHOLD = 0.70`, `DEMOTE_THRESHOLD = 0.85` (constants)
- `RECALL_EMA_ALPHA = 0.3` (constant)
- Protocols:
  - `ObjectiveAggregator(Protocol)` — `aggregate(vector) -> float`, `declared_weights() -> tuple[float, ...]`
  - `ObjectiveImportanceEstimator(Protocol)`
  - `DoubleConfirmationGate(Protocol)`
  - `RecallUtilityTracker(Protocol)` — `record_recall(record, tick) -> MemoryRecord`, `record_utility(record, utility, tick) -> MemoryRecord`
  - `MemoryImportanceLoss(Protocol)` — declared only, no first-version
  - `MemoryTrainingDatasetExtractor(Protocol)`
- First-version implementations:
  - `ConvexWeightedObjectiveAggregator(weights: tuple[float, ...])` — default `(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)`
  - `FirstVersionObjectiveImportanceEstimator`
  - `FirstVersionDoubleConfirmationGate`
  - `FirstVersionRecallUtilityTracker` — EMA α=0.3
  - `SqlBackedTrainingDatasetExtractor(experience_store)` — uses ExperienceStore facade
- Helper:
  - `ObjectiveImportanceLayerResolver(promote_threshold, demote_threshold)` — upgrade/downgrade logic
  - `MiningRecord` (frozen dataclass)

### 6.2 `helios_v2/memory/contracts.py` MODIFIED

- `MemoryLearnedParameterCategory` Literal extended: add `"objective_importance_weights"`
- `OUTCOME_CLASS_WEIGHTS` MappingProxyType
- `ObjectiveImportanceVector` frozen dataclass (with to_json/from_json)
- `DoubleConfirmationClass` Literal
- `DoubleConfirmationResult` frozen dataclass
- `PromotionEvent` frozen dataclass
- `MemoryRecord` 9 additive fields + `__post_init__` validation for new fields
- `MemoryAffectReplayError` for ObjectiveImportanceVector validation

### 6.3 `helios_v2/memory/engine.py` MODIFIED

- `MemoryAffectReplayEngine` gains 5 new fields:
  - `objective_importance_estimator: ObjectiveImportanceEstimator | None = None`
  - `objective_aggregator: ObjectiveAggregator | None = None`
  - `double_confirmation_gate: DoubleConfirmationGate | None = None`
  - `objective_layer_resolver: ObjectiveImportanceLayerResolver | None = None`
  - `recall_utility_tracker: RecallUtilityTracker | None = None`
- `record_state` signature unchanged; when all 5 are present:
  - Compute `objective_importance` via estimator
  - Compute `objective_score` via aggregator
  - Compute `double_confirmation` via gate (consumes R81 hormone_prediction)
  - Compute `final_layer` via resolver (R100 initial_layer → R101 resolved)
  - Build `MemoryRecord` with 9 new fields populated
  - When estimators absent: legacy R100 path byte-for-byte unchanged

### 6.4 `helios_v2/memory/__init__.py` MODIFIED

Export all new types:
- `ObjectiveImportanceVector`, `OUTCOME_CLASS_WEIGHTS`, `DoubleConfirmationClass`, `DoubleConfirmationResult`, `PromotionEvent`
- `ObjectiveAggregator`, `ConvexWeightedObjectiveAggregator`
- `ObjectiveImportanceEstimator`, `FirstVersionObjectiveImportanceEstimator`
- `DoubleConfirmationGate`, `FirstVersionDoubleConfirmationGate`
- `ObjectiveImportanceLayerResolver`
- `RecallUtilityTracker`, `FirstVersionRecallUtilityTracker`
- `MemoryImportanceLoss` (protocol only)
- `MemoryTrainingDatasetExtractor`, `SqlBackedTrainingDatasetExtractor`, `MiningRecord`

### 6.5 `helios_v2/persistence/contracts.py` MODIFIED

- `PersistedExperienceRecord` gains 8 additive fields
- `__post_init__` validation:
  - `objective_score` ∈ [0, 1] when not None
  - `subjective_score` ∈ [0, 1] when not None
  - `recall_count` ≥ 0 when not None
  - `double_confirmation_class` ∈ valid Literal
  - `objective_importance_json` parses via `ObjectiveImportanceVector.from_json` when not None
- `PersistenceError` for new validations

### 6.6 `helios_v2/persistence/engine.py` MODIFIED

- `SqliteExperienceStoreBackend.initialize`: PRAGMA-guarded ALTER TABLE adding 5 columns
  - `objective_importance_json TEXT`
  - `objective_score REAL`
  - `subjective_score REAL`
  - `double_confirmation_class TEXT`
  - `recall_count INTEGER`
- `_row_to_record`: read 5 new columns (forward-compatible with `len(row) > N` guard)
- `_record_to_row`: write 5 new columns
- `InMemoryExperienceStoreBackend` updates to honor same 5 columns

### 6.7 `helios_v2/composition/bridges.py` MODIFIED

- `ExperienceRecordBridge.build_records` accepts additive `memory_records: tuple[MemoryRecord, ...] = ()`
- Project `MemoryRecord.objective_importance` → `PersistedExperienceRecord.objective_importance_json` (via `to_json()`)
- Project `MemoryRecord.objective_score` → `PersistedExperienceRecord.objective_score`
- Project `MemoryRecord.subjective_score` → `PersistedExperienceRecord.subjective_score`
- Project `MemoryRecord.double_confirmation.classification` → `PersistedExperienceRecord.double_confirmation_class`
- Project `MemoryRecord.recall_count` → `PersistedExperienceRecord.recall_count`
- Project `MemoryRecord.recall_utility_score` → `PersistedExperienceRecord.recall_utility_score`
- Project `MemoryRecord.last_updated_at_wall` → `PersistedExperienceRecord.last_updated_at_wall`
- Project `MemoryRecord.promotion_history` → `PersistedExperienceRecord.promotion_history_json` (via json.dumps)

### 6.8 `helios_v2/composition/runtime_composition.py` MODIFIED

- `RuntimeProfile` gains 6 new seams (fail-fast 同进同出):
  - `objective_importance_estimator`
  - `objective_aggregator`
  - `double_confirmation_gate`
  - `objective_layer_resolver`
  - `recall_utility_tracker`
  - `training_dataset_extractor`
- `__post_init__`: validate all 6 same-state (all None OR all wired)
- Semantic assembly wires: `FirstVersionObjectiveImportanceEstimator()` + `ConvexWeightedObjectiveAggregator()` + `FirstVersionDoubleConfirmationGate()` + `ObjectiveImportanceLayerResolver()` + `FirstVersionRecallUtilityTracker()` + `SqlBackedTrainingDatasetExtractor()`
- Default assembly: all 6 None (legacy path)
- `assemble_production_runtime()` inherits semantic wiring
- `embed_callable` injected into estimator; `ExperienceStore` injected into extractor

## 7. Migration Plan

### 7.1 SQLite Migration (idempotent)

```sql
-- Run once per database initialization, in order
ALTER TABLE experience ADD COLUMN objective_importance_json TEXT;
ALTER TABLE experience ADD COLUMN objective_score REAL;
ALTER TABLE experience ADD COLUMN subjective_score REAL;
ALTER TABLE experience ADD COLUMN double_confirmation_class TEXT;
ALTER TABLE experience ADD COLUMN recall_count INTEGER;
-- Plus: recall_utility_score, last_updated_at_wall, promotion_history_json
-- (Optional: separate columns for full P5 queryability OR pack into JSON column)
```

PRAGMA-guarded: each ALTER wrapped with `try/except OperationalError` to handle "duplicate column" gracefully.

### 7.2 Pre-existing Rows

- All new columns are nullable (no NOT NULL constraint)
- Pre-existing rows read `None` / `0` (honest absence)
- R100 `memory_records` (R100's MemoryRecord) remain readable; their new fields are `None`

### 7.3 Default Assembly (legacy)

- 6 new RuntimeProfile seams = None
- `MemoryAffectReplayEngine.record_state` sees `None` for all 5 injected fields → R100 path byte-for-byte unchanged
- No new columns populated
- All 1329+ R100 tests pass unchanged

## 8. Failure Modes and Constraints

### 8.1 Hard Stops (fail-fast)

- `ObjectiveImportanceVector` field out of [0, 1] → `MemoryAffectReplayError`
- `ConvexWeightedObjectiveAggregator` weights sum ≠ 1.0 → `MemoryAffectReplayError`
- `PersistedExperienceRecord` `objective_score` / `subjective_score` out of [0, 1] → `PersistenceError`
- `PersistedExperienceRecord` `objective_importance_json` malformed → `PersistenceError`
- `RuntimeProfile` 6 seams not all-None / all-wired → `CompositionError`
- `SqliteExperienceStoreBackend.initialize` ALTER TABLE pre-existing duplicate column → swallowed (idempotent)

### 8.2 Honest Absence (never-fabricate)

- Missing `embed_callable` → `novelty_score = 0.5` (neutral, not 0 or 1)
- Missing `hormone_snapshot` field → 0.5 default
- Missing `feeling_snapshot` field → 0.5 default
- Missing `hormone_response_i_predict` → `subjective_score = 0.0`, `confidence = 0.0`
- Unknown `outcome_class` → 0.5 default
- Missing utility signal → `recall_utility_score = None` (P5 filters None records)

### 8.3 Skip Class Invariant

`double_confirmation.classification == "skip"` records:
- **Always** retained in `33` store (never dropped)
- `layer = L2_working` (conservative)
- `objective_score` / `subjective_score` may be low (negative example for P5)
- `recall_count` starts at 0 (P5 tracks recall failure pattern)

## 9. Observability and Logging

### 9.1 No new logging mechanism

R21 observability owner is the single logging mechanism. R101 adds NO new logging or `print` calls. The existing `RuntimeObservabilityRecorder` consumes stage results and emits structured events.

### 9.2 R101 observable via stage results

- `MemoryAffectReplayStageResult.memory_records` exposes tuple of `MemoryRecord` with all R101 fields
- Downstream owners (`17 evaluation`, `15 writeback`) consume the new fields
- R88 drift evaluator (`tests/r88_drift_evaluator/`) can classify `06.objective_score` and `06.recall_count` drift over time

### 9.3 R101 drift dimensions for R88

- `06.objective_score` — mean across run should be in [0.2, 0.6] (most records moderate importance)
- `06.recall_count` — bounded by store age × retrieval frequency
- `06.recall_utility_score` — once R102 lands, should trend positive (memories that get recalled are useful)

## 10. Validation Strategy

### 10.1 Unit Tests

| File | Coverage |
|---|---|
| `tests/test_objective_importance_vector.py` (NEW) | 6-dim validation; to_json/from_json round-trip |
| `tests/test_objective_aggregator.py` (NEW) | ConvexWeightedObjectiveAggregator: weights sum=1.0 invariant; declared_weights(); aggregate monotonicity |
| `tests/test_objective_importance_estimator.py` (NEW) | FirstVersionObjectiveImportanceEstimator: 6-dim computation; missing-field defaults |
| `tests/test_double_confirmation_gate.py` (NEW) | FirstVersionDoubleConfirmationGate: 4-class decision table; subjective absent handling |
| `tests/test_objective_layer_resolver.py` (NEW) | promote/demote rules; skip→L2_working |
| `tests/test_recall_utility_tracker.py` (NEW) | EMA update; record_recall bumps count |
| `tests/test_memory_importance_loss.py` (NEW) | MemoryImportanceLoss protocol declared (no implementation) |
| `tests/test_training_dataset_extractor.py` (NEW) | 6-filter combinations; MiningRecord projection |
| `tests/test_memory_engine_dual_confirmation.py` (NEW) | MemoryAffectReplayEngine 5-injection integration |
| `tests/test_persistence_objective_importance.py` (NEW) | PersistedExperienceRecord 8 new fields; SQLite ALTER TABLE migration; JSON round-trip |
| `tests/test_runtime_six_seam_wiring.py` (NEW) | RuntimeProfile 6 seam 同进同出; semantic assembly wires 6; default assembly 6 None |

### 10.2 Integration Tests

- Full `helios_v2/tests` regression — all 1329 R100 tests must pass
- R99 emotion probe baseline — cortisol positive-vs-negative separation must not regress
- R88 drift evaluator — must classify `06.objective_score` and `06.recall_count` as drift_neutral on semantic_600.jsonl

### 10.3 P5 Forward-Compatibility Smoke

Test that P5 can inject custom `ObjectiveAggregator` / `DoubleConfirmationGate` / `MemoryImportanceLoss` / `MemoryTrainingDatasetExtractor` without schema changes:
- `tests/test_p5_forward_compatibility.py` (NEW): construct mock implementations, wire into RuntimeProfile, run semantic assembly, verify fields populate