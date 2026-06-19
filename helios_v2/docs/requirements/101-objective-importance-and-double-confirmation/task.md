# Requirement 101 — Task Breakdown: 6-Dimensional Objective Importance + Double-Confirmation + P5-Ready Foundation

## 1. Title

Requirement 101 — Task Breakdown: 6-Dimensional Objective Importance + Double-Confirmation + P5-Ready Foundation

## 2. Task Breakdown

### T1: MemoryRecord 9 additive fields + supporting types in `helios_v2/memory/contracts.py`

- **Dependency**: none (root task)
- **Touched modules**: `helios_v2/memory/contracts.py`, `helios_v2/memory/__init__.py`
- **Completion definition**:
  - `MemoryLearnedParameterCategory` Literal extended to include `"objective_importance_weights"`
  - `OUTCOME_CLASS_WEIGHTS: MappingProxyType[str, float]` defined (8 entries)
  - `ObjectiveImportanceVector` frozen dataclass with `__post_init__` validation + `to_json()` + `from_json()`
  - `DoubleConfirmationClass` Literal type
  - `DoubleConfirmationResult` frozen dataclass
  - `PromotionEvent` frozen dataclass
  - `MemoryRecord` gains 9 additive fields:
    - `objective_importance: ObjectiveImportanceVector | None = None`
    - `objective_score: float | None = None`
    - `subjective_score: float | None = None`
    - `double_confirmation: DoubleConfirmationResult | None = None`
    - `recall_count: int = 0`
    - `last_recall_at_tick: int | None = None`
    - `recall_utility_score: float | None = None`
    - `last_updated_at_wall: float | None = None`
    - `promotion_history: tuple[PromotionEvent, ...] = ()`
  - `__post_init__` validates new fields (None-allowed + range checks when present)
  - All exports from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_objective_importance_vector.py helios_v2/tests/test_memory_record_contract.py -x --tb=short -q` — all new contract tests pass; existing R100 contract tests unchanged

### T2: NEW `helios_v2/memory/objective_importance.py` — `ObjectiveAggregator` + `ConvexWeightedObjectiveAggregator`

- **Dependency**: T1 (ObjectiveImportanceVector)
- **Touched modules**: `helios_v2/memory/objective_importance.py` (NEW), `helios_v2/memory/__init__.py`
- **Completion definition**:
  - Module-level constants: `OUTCOME_PASS_THRESHOLD = 0.50`, `SUBJECTIVE_PASS_THRESHOLD = 0.60`, `PROMOTE_THRESHOLD = 0.70`, `DEMOTE_THRESHOLD = 0.85`, `RECALL_EMA_ALPHA = 0.3`
  - `_safe_get(mapping, key, default=0.5) -> float` helper
  - `ObjectiveAggregator` Protocol with `aggregate(vector) -> float` and `declared_weights() -> tuple[float, ...]`
  - `ConvexWeightedObjectiveAggregator(weights: tuple[float, ...])` dataclass implementation; default weights `(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)`; `__post_init__` validates weights sum = 1.0 (with float epsilon 1e-6) and length = 6
  - All exported from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_objective_aggregator.py -x --tb=short -q` — new tests pass (weights sum invariant; default weights; aggregate monotonicity; declared_weights returns tuple)

### T3: `ObjectiveImportanceEstimator` protocol + `FirstVersionObjectiveImportanceEstimator`

- **Dependency**: T1 (ObjectiveImportanceVector), T2 (constants), R100 contracts
- **Touched modules**: `helios_v2/memory/objective_importance.py`, `helios_v2/memory/__init__.py`
- **Completion definition**:
  - `ObjectiveImportanceEstimator` Protocol with `estimate(stimulus_text, hormone_snapshot, feeling_snapshot, outcome_class, recent_summaries, embed_callable) -> ObjectiveImportanceVector`
  - `FirstVersionObjectiveImportanceEstimator` implementation:
    - `stimulus_intensity = min(1.0, len(stimulus_text) / 200.0)` (empty text → 0.0)
    - `cortisol_response = _safe_get(hormone_snapshot, "cortisol", 0.5)`
    - `arousal_response = _safe_get(feeling_snapshot, "arousal", 0.5)`
    - `outcome_class_weight = OUTCOME_CLASS_WEIGHTS.get(outcome_class, 0.5)`
    - `novelty_score = _novelty_cosine(...)` (1 - max_cosine; 0.5 if embed_callable is None or recent_summaries is empty)
    - `relationship_risk = 1.0 - _safe_get(feeling_snapshot, "social_safety", 0.5)`
  - `_novelty_cosine(stimulus_text, recent_summaries, embed_callable) -> float` helper; if `embed_callable is None` returns 0.5; else computes max cosine
  - All exported from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_objective_importance_estimator.py -x --tb=short -q` — tests cover all 6 dimensions; missing-field defaults; embed_callable absent returns 0.5

### T4: `DoubleConfirmationGate` protocol + `FirstVersionDoubleConfirmationGate` + `DoubleConfirmationResult` (already in T1) + `DoubleConfirmationClass` Literal (already in T1)

- **Dependency**: T1 (DoubleConfirmationResult, DoubleConfirmationClass), T2 (thresholds)
- **Touched modules**: `helios_v2/memory/objective_importance.py`, `helios_v2/memory/__init__.py`
- **Completion definition**:
  - `DoubleConfirmationGate` Protocol with `evaluate(objective_score, subjective_score, subjective_confidence, outcome_class) -> DoubleConfirmationResult`
  - `FirstVersionDoubleConfirmationGate(threshold_objective=0.50, threshold_subjective=0.60)` implementation:
    - `objective_score >= threshold_objective` ∧ `subjective_score >= threshold_subjective` → `both_pass`
    - `objective_score >= threshold_objective` ∧ `subjective_score < threshold_subjective` → `objective_only`
    - `objective_score < threshold_objective` ∧ `subjective_score >= threshold_subjective` → `subjective_only`
    - Both below → `skip`
  - All exported from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_double_confirmation_gate.py -x --tb=short -q` — tests cover all 4-class decision combinations; subjective absent; boundary values 0.50/0.60

### T5: `ObjectiveImportanceLayerResolver` + `RecallUtilityTracker` + `FirstVersionRecallUtilityTracker`

- **Dependency**: T1 (MemoryRecord, PromotionEvent), T2 (constants)
- **Touched modules**: `helios_v2/memory/objective_importance.py`, `helios_v2/memory/__init__.py`
- **Completion definition**:
  - `ObjectiveImportanceLayerResolver(promote_threshold=0.70, demote_threshold=0.85)` dataclass with `resolve(initial_layer: MemoryLayer, objective_score: float | None, double_confirmation_class: DoubleConfirmationClass | None, outcome_class: str) -> MemoryLayer` method:
    - `both_pass`: keep L5/L4; L3 + obj≥0.70 → L4; L2 + obj≥0.85 + identity outcome → L5
    - `objective_only`: L4 + obj<0.70 → L3; L5 + obj<0.85 → L4; else keep
    - `subjective_only`: keep
    - `skip`: return L2_working
  - `RecallUtilityTracker` Protocol:
    - `record_recall(record: MemoryRecord, current_tick: int) -> MemoryRecord`
    - `record_utility(record: MemoryRecord, utility: float, current_tick: int) -> MemoryRecord`
  - `FirstVersionRecallUtilityTracker(ema_alpha=0.3)` implementation:
    - `record_recall`: returns new `MemoryRecord` with `recall_count += 1`, `last_recall_at_tick = current_tick`
    - `record_utility`: returns new `MemoryRecord` with `recall_utility_score = α * utility + (1-α) * old` (or `utility` if old is None)
  - All exported from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_objective_layer_resolver.py helios_v2/tests/test_recall_utility_tracker.py -x --tb=short -q` — promote/demote rules; skip→L2_working; EMA update; record_recall bump

### T6: `MemoryImportanceLoss` protocol + `MemoryTrainingDatasetExtractor` protocol + `MiningRecord` + `SqlBackedTrainingDatasetExtractor`

- **Dependency**: T1 (MemoryRecord, ObjectiveImportanceVector, etc.), T5 (constants)
- **Touched modules**: `helios_v2/memory/objective_importance.py`, `helios_v2/memory/__init__.py`, `helios_v2/memory/engine.py` (no logic change; just import)
- **Completion definition**:
  - `MiningRecord` frozen dataclass (see design §5.7)
  - `MemoryImportanceLoss` Protocol:
    ```python
    class MemoryImportanceLoss(Protocol):
        def loss(self, *, predicted_objective_score: float, observed_recall_utility: float | None, recall_count: int, record: MemoryRecord) -> float: ...
    ```
  - **R101 does NOT provide first-version MemoryImportanceLoss** — P5 scope (R110+) implements
  - `MemoryTrainingDatasetExtractor` Protocol:
    ```python
    class MemoryTrainingDatasetExtractor(Protocol):
        def extract_mining_dataset(self, *, min_recall_count=0, min_objective_score=0.0, layer_filter=None, double_confirmation_filter=None, since_wall_seconds=None, limit=None) -> tuple[MiningRecord, ...]: ...
    ```
  - `SqlBackedTrainingDatasetExtractor(experience_store)` implementation:
    - Uses `experience_store.read_recent(limit=limit or 1000, layer_filter=...)` to fetch records
    - Filters by `recall_count`, `objective_score`, `double_confirmation_class`, `since_wall_seconds`
    - Returns `tuple[MiningRecord, ...]` with `objective_vector` deserialized from JSON
  - All exported from `__init__.py`
- **Validation step**: `pytest helios_v2/tests/test_memory_importance_loss.py helios_v2/tests/test_training_dataset_extractor.py -x --tb=short -q` — protocol declaration compiles; extractor filters work; MiningRecord projection

### T7: `MemoryAffectReplayEngine` 5 injection points + record_state integration

- **Dependency**: T1-T6 (all types defined)
- **Touched modules**: `helios_v2/memory/engine.py`
- **Completion definition**:
  - `MemoryAffectReplayEngine` gains 5 new fields:
    - `objective_importance_estimator: ObjectiveImportanceEstimator | None = None`
    - `objective_aggregator: ObjectiveAggregator | None = None`
    - `double_confirmation_gate: DoubleConfirmationGate | None = None`
    - `objective_layer_resolver: ObjectiveImportanceLayerResolver | None = None`
    - `recall_utility_tracker: RecallUtilityTracker | None = None`
  - `record_state` signature unchanged (still accepts `feeling_state, binding_context, mismatch_evidence, outcome_class, tick_id`)
  - **Fast path** (when any of the 5 R101 fields is None → legacy R100 path):
    - No new fields populated on MemoryRecord (all None/0/empty)
    - No new gate / resolver logic
    - Existing R100 layer classifier decides layer
    - Byte-for-byte identical to R100 behavior
  - **R101 path** (when all 5 are present):
    - For each `AffectTaggedMemoryItem` produced by formation path:
      - Compute `objective_vector = objective_importance_estimator.estimate(stimulus_text=item.content.salient_tokens or "", hormone_snapshot=feeling_state.neuromodulator_state, feeling_snapshot=feeling_state.feeling, outcome_class=outcome_class, recent_summaries=..., embed_callable=self.embed_callable)`
      - Compute `objective_score = objective_aggregator.aggregate(objective_vector)`
      - Compute `subjective_score` = max of `hormone_prediction` Mapping (or 0.0 if absent)
      - `double_confirmation = double_confirmation_gate.evaluate(objective_score=objective_score, subjective_score=subjective_score, subjective_confidence=..., outcome_class=outcome_class)`
      - `r100_initial_layer = self.layer_classifier.classify_layer(gate_value, outcome_class)` (R100 logic)
      - `final_layer = self.objective_layer_resolver.resolve(r100_initial_layer, objective_score, double_confirmation.classification, outcome_class)`
      - Build `MemoryRecord` with all 9 R101 fields populated
  - Skip class records still built (layer = L2_working), retained for P5 negative samples
- **Validation step**: `pytest helios_v2/tests/test_memory_engine_dual_confirmation.py helios_v2/tests/test_memory_engine_layer.py -x --tb=short -q` — engine-with-all-5-injection produces MemoryRecord with R101 fields; engine-without-injection produces MemoryRecord with R101 fields=None (R100 byte-for-byte)

### T8: `PersistedExperienceRecord` 8 additive fields + `__post_init__` validation + `PersistenceError`

- **Dependency**: T1 (ObjectiveImportanceVector, DoubleConfirmationClass)
- **Touched modules**: `helios_v2/persistence/contracts.py`
- **Completion definition**:
  - `PersistedExperienceRecord` gains 8 additive fields (per design §5.6):
    - `objective_importance_json: str | None = None`
    - `objective_score: float | None = None`
    - `subjective_score: float | None = None`
    - `double_confirmation_class: DoubleConfirmationClass | None = None`
    - `recall_count: int | None = None`
    - `recall_utility_score: float | None = None`
    - `last_updated_at_wall: float | None = None`
    - `promotion_history_json: str | None = None`
  - `__post_init__` validates:
    - `objective_score ∈ [0, 1]` when not None
    - `subjective_score ∈ [0, 1]` when not None
    - `recall_count >= 0` when not None
    - `double_confirmation_class ∈ {both_pass, objective_only, subjective_only, skip}` when not None
    - `objective_importance_json` parses via `ObjectiveImportanceVector.from_json` when not None
- **Validation step**: `pytest helios_v2/tests/test_persistence_contracts.py -x --tb=short -q` — existing R100 tests unchanged; new tests for each new field validation

### T9: SQLite ALTER TABLE migration + `_row_to_record`/`_record_to_row` 5 columns + InMemory backend parity

- **Dependency**: T8 (PersistedExperienceRecord 8 fields)
- **Touched modules**: `helios_v2/persistence/engine.py`
- **Completion definition**:
  - `SqliteExperienceStoreBackend.initialize` runs 5 PRAGMA-guarded `ALTER TABLE ADD COLUMN` statements (idempotent):
    - `objective_importance_json TEXT`
    - `objective_score REAL`
    - `subjective_score REAL`
    - `double_confirmation_class TEXT`
    - `recall_count INTEGER`
    - Plus: optionally `recall_utility_score REAL`, `last_updated_at_wall REAL`, `promotion_history_json TEXT` (R101 design includes these in 8-field set; 3 of them can be packed into JSON column)
  - Actually: 5 indexed columns per design §5.6/§7.1 (objective_importance_json + 4 indexed: objective_score, subjective_score, double_confirmation_class, recall_count). The other 3 (recall_utility_score, last_updated_at_wall, promotion_history_json) can be packed into objective_importance_json OR have separate columns. **Decision: separate columns for P5 queryability** (8 columns total: 1 JSON + 4 indexed + 3 utility columns).
  - Wait, design §6.5 says "5 列 SQLite ALTER TABLE" — let me reconcile: SQLite receives 5 indexed/queryable columns + 3 packed-into-JSON OR 8 separate columns. **R101 will use 8 separate columns** for full P5 queryability. UPDATE design.md if needed.
  - `_row_to_record` reads 8 new columns with `len(row) > N` forward-compat guard
  - `_record_to_row` writes 8 new columns
  - `InMemoryExperienceStoreBackend` honors same 8 columns
  - `append`, `read_recent`, `search_similar` carry new fields through
- **Validation step**: `pytest helios_v2/tests/test_persistence_layer_migration.py helios_v2/tests/test_persistence_layer_extension.py helios_v2/tests/test_persistence_engine.py -x --tb=short -q` — migration idempotent; pre-existing rows read None; JSON round-trip; new fields persisted correctly

### T10: Composition 6 seam `RuntimeProfile` + bridge projection + semantic assembly wiring

- **Dependency**: T1-T9 (all types and persistence implemented)
- **Touched modules**: `helios_v2/composition/bridges.py`, `helios_v2/composition/runtime_composition.py`
- **Completion definition**:
  - `RuntimeProfile` gains 6 new seam fields with `None` defaults:
    - `objective_importance_estimator: ObjectiveImportanceEstimator | None`
    - `objective_aggregator: ObjectiveAggregator | None`
    - `double_confirmation_gate: DoubleConfirmationGate | None`
    - `objective_layer_resolver: ObjectiveImportanceLayerResolver | None`
    - `recall_utility_tracker: RecallUtilityTracker | None`
    - `training_dataset_extractor: MemoryTrainingDatasetExtractor | None`
  - `RuntimeProfile.__post_init__`: validate all 6 same-state (all None OR all wired; otherwise `CompositionError`)
  - Semantic assembly (`assemble_runtime(default_signal_mode="semantic")`) wires all 6 with first-version implementations
  - Default assembly (`assemble_runtime()` with default mode) leaves all 6 None
  - `assemble_production_runtime()` inherits semantic wiring
  - `ExperienceRecordBridge` / `MemoryRecordBridge` in `composition/bridges.py`:
    - Project 8 fields from `MemoryRecord` → `PersistedExperienceRecord` (using `to_json()` for vector + `json.dumps()` for promotion_history)
    - When R101 seams absent (legacy), bridges preserve None values
- **Validation step**: `pytest helios_v2/tests/test_runtime_six_seam_wiring.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_composition_layer_bridge.py -x --tb=short -q` — semantic assembly wires all 6; default assembly None; bridges project fields; 同进同出 raises CompositionError on mismatch

### T11: Documentation sync (index.md / ROADMAP / PROGRESS_FLOW / ARCHITECTURE_BOUNDARIES / OWNER_GUIDE)

- **Dependency**: T10 (all implementation done; tests green)
- **Touched modules**: `docs/requirements/index.md`, `docs/ROADMAP.zh-CN.md`, `docs/PROGRESS_FLOW.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/OWNER_GUIDE.zh-CN.md`, `docs/OWNER_GUIDE.md`, `docs/BRAIN_ARCHITECTURE_COMPARISON.md`
- **Completion definition**:
  - `docs/requirements/index.md`: add R101 row with `Maturity: baseline_implementation`, `Depends On: 06, 33, 10, 22`, note "P5-ready foundation: 6-dim objective importance + double confirmation gate + cross-tick utility + P5 hooks"
  - `docs/ROADMAP.zh-CN.md`: update §1 state line (mention R101 delivered); add R101 to §2 completed table; update §3 queue (R100 done; R101 next done; R102+ still pending); update §5 R101 description; update §1.0 next-iteration table to mark R101 done and remove from active list
  - `docs/PROGRESS_FLOW.zh-CN.md` / `en.md`: update top "Last synced" line; update 06 / 33 / 22 owner nodes; add R101 row to progress summary
  - `docs/ARCHITECTURE_BOUNDARIES.md`: add R101 boundary snapshot section; describe 6 protocol seams + 9 new fields + 8 column hybrid storage + R56/R57 owner-boundary preservation
  - `docs/OWNER_GUIDE.zh-CN.md` / `en.md`: update top "最近同步" line to mention R101; update §2.6 (06 owner) section to describe R101 additions (6-dim objective importance + double confirmation + recall utility tracker + P5 protocol hooks)
  - `docs/BRAIN_ARCHITECTURE_COMPARISON.md`: update `gap_persistence_and_learning` row to mark R101 as P5-ready foundation entry point
- **Validation step**: manual review of docs consistency; ensure "Last synced" lines all reflect R101; cross-check OWNER_GUIDE §2.6 vs requirement.md vs actual implementation

### T12: Full regression + commit + push

- **Dependency**: T11
- **Touched modules**: none (validation + commit only)
- **Completion definition**:
  - Full `helios_v2/tests` regression: `D:/Compiler/anaconda3/envs/helios/python.exe -m pytest helios_v2/tests -q` → all pass (target: 1329+ R100 baseline + ~50-80 new R101 tests = ~1380+)
  - R99 emotion probe baseline unchanged
  - R88 drift evaluator baseline unchanged
  - R56/R57 owner-boundary guard green
  - R21 observability guard green
  - R95 followup C1-C6 no-hardcoded-op-name guard green
  - Commit: `feat(R101): 6-dim objective importance + double-confirmation + P5-ready foundation` (or similar)
  - Push to `origin/main`
- **Validation step**: `git push origin main` succeeds; `pytest helios_v2/tests -q` returns all green

## 3. Dependencies

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T10 → T11 → T12
T1 → T8 → T9 → T10
T2 → T4
T2 → T5
```

T1 is the root. T2/T3/T4/T5/T6 form a chain on top of T1 (each depends on previous contracts and protocols). T7 (engine integration) depends on T1-T6 (all types and protocols). T8 (PersistedExperienceRecord fields) depends only on T1 (ObjectiveImportanceVector). T9 (SQLite migration) depends on T8. T10 (composition wiring) depends on T7 + T8 + T9. T11 depends on T10. T12 depends on T11.

## 4. Files and Modules

| Task | New files | Modified files |
|------|-----------|----------------|
| T1 | `tests/test_objective_importance_vector.py` | `memory/contracts.py`, `memory/__init__.py` |
| T2 | `tests/test_objective_aggregator.py` | `memory/objective_importance.py` (NEW), `memory/__init__.py` |
| T3 | `tests/test_objective_importance_estimator.py` | `memory/objective_importance.py`, `memory/__init__.py` |
| T4 | `tests/test_double_confirmation_gate.py` | `memory/objective_importance.py`, `memory/__init__.py` |
| T5 | `tests/test_objective_layer_resolver.py`, `tests/test_recall_utility_tracker.py` | `memory/objective_importance.py`, `memory/__init__.py` |
| T6 | `tests/test_memory_importance_loss.py`, `tests/test_training_dataset_extractor.py` | `memory/objective_importance.py`, `memory/__init__.py` |
| T7 | `tests/test_memory_engine_dual_confirmation.py` | `memory/engine.py` |
| T8 | (tests in T9) | `persistence/contracts.py` |
| T9 | `tests/test_persistence_objective_importance.py` | `persistence/engine.py` |
| T10 | `tests/test_runtime_six_seam_wiring.py` | `composition/bridges.py`, `composition/runtime_composition.py` |
| T11 | none | `docs/requirements/index.md`, `docs/ROADMAP.zh-CN.md`, `docs/PROGRESS_FLOW.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/OWNER_GUIDE.zh-CN.md`, `docs/OWNER_GUIDE.md`, `docs/BRAIN_ARCHITECTURE_COMPARISON.md` |
| T12 | none | none (validation + commit only) |

## 5. Implementation Order

1. **T1** — `contracts.py` (foundation; all types defined)
2. **T8** — `persistence/contracts.py` (additive fields; independent of engine)
3. **T2** — `ObjectiveAggregator` (depends on T1)
4. **T3** — `ObjectiveImportanceEstimator` (depends on T1, T2)
5. **T4** — `DoubleConfirmationGate` (depends on T1, T2)
6. **T5** — `ObjectiveImportanceLayerResolver` + `RecallUtilityTracker` (depends on T1, T2)
7. **T6** — `MemoryImportanceLoss` + `MemoryTrainingDatasetExtractor` (depends on T1-T5)
8. **T9** — SQLite ALTER TABLE migration (depends on T8)
9. **T7** — `MemoryAffectReplayEngine` 5-injection integration (depends on T1-T6)
10. **T10** — Composition 6 seam + bridge projection + semantic wiring (depends on T7, T8, T9)
11. **T11** — Documentation sync
12. **T12** — Full regression + commit + push

Estimated total: ~6-8 hours of implementation + testing + docs.

## 6. Validation Plan

### Phase gate after T1-T3-T4-T5 (contracts and protocols)

- All new contract tests pass
- All 4 protocol implementations exist and pass unit tests
- R100 contract tests unchanged

### Phase gate after T6-T8-T9 (extractor + persistence)

- Extractor filters work
- PersistedExperienceRecord 8 fields valid
- SQLite ALTER TABLE migration idempotent

### Phase gate after T7-T10 (engine + composition wiring)

- Engine produces MemoryRecord with 9 R101 fields when all 5 R101 seams injected
- Engine byte-for-byte unchanged when any of 5 seams absent
- Composition semantic assembly wires 6 seams
- Default assembly leaves 6 seams None

### Phase gate after T11 (docs)

- index.md has R101 row
- ROADMAP / PROGRESS_FLOW / ARCHITECTURE_BOUNDARIES / OWNER_GUIDE / BRAIN_ARCHITECTURE_COMPARISON all synced

### Phase gate after T12 (regression)

- All 1329+ R100 tests pass
- R99 emotion probe baseline unchanged
- R88 drift evaluator baseline unchanged
- R56/R57/R21/R95-followup guards all green

## 7. Completion Criteria

1. `ObjectiveImportanceVector` / `OUTCOME_CLASS_WEIGHTS` / `DoubleConfirmationResult` / `PromotionEvent` / `MemoryRecord` 9 additive fields all defined with fail-fast validation.
2. `ObjectiveAggregator` / `ObjectiveImportanceEstimator` / `DoubleConfirmationGate` / `ObjectiveImportanceLayerResolver` / `RecallUtilityTracker` / `MemoryImportanceLoss` / `MemoryTrainingDatasetExtractor` 7 protocols declared.
3. `ConvexWeightedObjectiveAggregator` / `FirstVersionObjectiveImportanceEstimator` / `FirstVersionDoubleConfirmationGate` / `FirstVersionRecallUtilityTracker` / `SqlBackedTrainingDatasetExtractor` 5 first-version implementations.
4. `MemoryAffectReplayEngine` integrates 5 injection points; legacy path byte-for-byte unchanged.
5. `PersistedExperienceRecord` 8 additive fields; SQLite `ALTER TABLE` migration idempotent (PRAGMA-guarded).
6. `RuntimeProfile` 6-seam 同进同出 validation; semantic assembly wires 6; default assembly 6 None.
7. `ExperienceRecordBridge` projects `MemoryRecord` 9 R101 fields → `PersistedExperienceRecord` 8 fields.
8. **Skip class** records retained in `33` store as negative training samples.
9. **Cross-tick utility** fields (`recall_count` / `last_recall_at_tick` / `recall_utility_score` / `last_updated_at_wall` / `promotion_history`) all functional.
10. **Hybrid storage** (1 JSON + 7 indexed columns) supports P5 SQL query.
11. **P5 forward-compatibility**: all 5 first-version implementations are replaceable via Protocol injection without schema changes.
12. R100 baseline 1329 tests zero regression; R99 emotion probe baseline unchanged; R88 drift evaluator baseline unchanged.
13. R56/R57 owner-boundary guard green.
14. R21 observability guard green.
15. R95 followup C1-C6 no-hardcoded-op-name guard green.
16. R101 三件套文档完整; `index.md` / `ROADMAP` / `PROGRESS_FLOW` / `ARCHITECTURE_BOUNDARIES` / `OWNER_GUIDE` / `BRAIN_ARCHITECTURE_COMPARISON` all synced.
17. Commit + push to `origin/main`.