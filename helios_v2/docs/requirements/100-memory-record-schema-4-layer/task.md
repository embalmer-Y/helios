# Requirement 100 — Task Breakdown: MemoryRecord Schema + 4-Layer Time Stratification

## 1. Title

Requirement 100 — Task Breakdown: MemoryRecord Schema + 4-Layer Time Stratification

## 2. Task Breakdown

### T1: MemoryLayer type + MemoryRecord contract + MemoryLearnedParameterCategory extension

- **Dependency**: none (first task)
- **Touched modules**: `helios_v2/memory/contracts.py`, `helios_v2/memory/__init__.py`
- **Completion definition**: `MemoryLayer` type alias defined; `MemoryRecord` frozen dataclass with `__post_init__` validation; `MemoryLearnedParameterCategory` includes `"layer_assignment_policy"`; all exported from `__init__.py`
- **Validation step**: `pytest tests/test_memory_contracts.py -x --tb=short -q` (new contract tests: valid construction, empty-field rejection, invalid-layer rejection, out-of-range affect_intensity)

### T2: MemoryLayerClassifier protocol + AffectOutcomeMemoryLayerClassifier implementation

- **Dependency**: T1 (MemoryLayer type)
- **Touched modules**: `helios_v2/memory/engine.py`, `helios_v2/memory/__init__.py`
- **Completion definition**: `MemoryLayerClassifier` protocol with `classify_layer(affect_intensity, outcome_class) -> MemoryLayer`; `AffectOutcomeMemoryLayerClassifier` with `low_affect_threshold=0.15`, `high_affect_threshold=0.50`, `identity_outcome_classes=("self_changed",)`; all 6 table rows correctly implemented; exported from `__init__.py`
- **Validation step**: `pytest tests/test_memory_layer_classifier.py -x --tb=short -q` (new classifier tests: all 6 table rows, boundary values 0.15/0.50, extreme values 0.0/1.0, fallback to L2_working on unknown outcome_class)

### T3: MemoryAffectReplayEngine classifier injection + MemoryRecord production

- **Dependency**: T1 (MemoryRecord), T2 (classifier)
- **Touched modules**: `helios_v2/memory/engine.py`
- **Completion definition**: `MemoryAffectReplayEngine` gains `layer_classifier: MemoryLayerClassifier | None = None` field; when classifier is present AND item has `forced_consolidation=True`, engine produces `MemoryRecord` alongside `AffectTaggedMemoryItem`; when classifier is absent, engine produces only `AffectTaggedMemoryItem` (byte-for-byte unchanged); `MemoryAffectReplayStageResult` gains additive `memory_records: tuple[MemoryRecord, ...] = ()` field
- **Validation step**: `pytest tests/test_memory_engine.py -x --tb=short -q` (engine-with-classifier produces MemoryRecord; engine-without-classifier produces only AffectTaggedMemoryItem; layer field matches classifier output)

### T4: PersistedExperienceRecord additive extension (layer + memory_metadata)

- **Dependency**: T1 (MemoryLayer type)
- **Touched modules**: `helios_v2/persistence/contracts.py`, `helios_v2/persistence/__init__.py`
- **Completion definition**: `PersistedExperienceRecord` gains `layer: MemoryLayer | None = None` and `memory_metadata: Mapping[str, str] = field(default_factory=dict)`; `__post_init__` validates layer (None or valid literal) and memory_metadata keys; `MemoryLayer` imported from `06`; exported from `__init__.py`
- **Validation step**: `pytest tests/test_persistence_contracts.py -x --tb=short -q` (existing tests unchanged; new tests: layer=None succeeds, layer="L3_short" succeeds, layer="invalid" raises PersistenceError; memory_metadata construction; combined layer+metadata)

### T5: SQLite ALTER TABLE migration + read-back + search_similar preferred_layers + read_recent layer_filter

- **Dependency**: T4 (PersistedExperienceRecord additive fields)
- **Touched modules**: `helios_v2/persistence/engine.py`
- **Completion definition**: `SqliteExperienceStoreBackend.initialize` runs PRAGMA-guarded ALTER TABLE adding `layer TEXT` and `memory_metadata TEXT` columns; `_row_to_record` reads both columns (forward-compatible: `len(row) > 18` guard); `search_similar` accepts `preferred_layers: tuple[MemoryLayer, ...] | None = None` (boost via `layer_preference_weight=1.5`); `read_recent` accepts `layer_filter: MemoryLayer | None = None` (filter by layer); same parameters on `InMemoryExperienceStoreBackend`; `ExperienceStore` facade forwards both parameters; `layer_preference_weight` is a first-version constant declared under `"replay_priority_policy"`
- **Validation step**: `pytest tests/test_persistence_engine.py tests/test_memory_stability_assessment.py -x --tb=short -q` (SQLite migration: adds columns, idempotent, pre-existing rows read layer=None; search_similar with preferred_layers boosts L4/L5; read_recent with layer_filter returns only matching layer; InMemory backend same behavior)

### T6: Composition bridge projection (MemoryRecord → PersistedExperienceRecord)

- **Dependency**: T3 (MemoryRecord production), T4 (PersistedExperienceRecord additive fields), T5 (SQLite migration)
- **Touched modules**: `helios_v2/composition/bridges.py`
- **Completion definition**: `ExperienceRecordBridge.build_records` accepts additive `memory_records: tuple[MemoryRecord, ...] = ()` parameter; projects `MemoryRecord.layer` → `PersistedExperienceRecord.layer` and `MemoryRecord.memory_metadata` → `PersistedExperienceRecord.memory_metadata`; when no `MemoryRecord` matches a candidate, `layer=None` and `memory_metadata=empty`; `MemoryRecordBridge` (affect-memory path) also projects these fields
- **Validation step**: `pytest tests/test_composition_bridges.py -x --tb=short -q` (bridge with MemoryRecord projects layer/metadata; bridge without MemoryRecord produces layer=None; affect-memory bridge also projects)

### T7: RuntimeProfile seam + semantic assembly wiring + retrieval bridge layer preference

- **Dependency**: T2 (classifier), T6 (bridge projection)
- **Touched modules**: `helios_v2/composition/runtime_composition.py`, `helios_v2/composition/bridges.py`, `helios_v2/directed_retrieval/`
- **Completion definition**: `RuntimeProfile` gains `memory_layer_classifier: MemoryLayerClassifier | None = None` and `memory_layer_preference: tuple[MemoryLayer, ...] | None = None`; semantic assembly wires `AffectOutcomeMemoryLayerClassifier` + `memory_layer_preference=("L4_long", "L5_autobiographical")`; production assembly inherits; default assembly leaves both None; `10` retrieval bridge projects `memory_layer_preference` into `search_similar`/`read_recent` calls
- **Validation step**: `pytest tests/test_runtime_composition.py -x --tb=short -q` (semantic assembly wires classifier; default assembly does not; layer_preference projected into retrieval)

### T8: Full regression + R99 baseline + end-to-end smoke

- **Dependency**: T1–T7
- **Touched modules**: all (validation only, no code changes)
- **Completion definition**: all 1172+ existing tests pass; R99 emotion probe baseline unchanged; semantic assembly end-to-end smoke produces records with layer; mixed L2/L3/L4/L5 distribution matches classifier rules
- **Validation step**: `pytest tests/ -x --tb=line -q` (full suite green); then run R99 probe: `pytest tests/r99_emotion_validation_probe/ -x --tb=short -q` (baseline unchanged)

### T9: Documentation sync (index.md + PROGRESS_FLOW + ROADMAP)

- **Dependency**: T8 (all tests pass, R100 scope verified)
- **Touched modules**: `docs/requirements/index.md`, `docs/PROGRESS_FLOW.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/ROADMAP.zh-CN.md`
- **Completion definition**: `index.md` has R100 row; PROGRESS_FLOW maps updated (06 maturity reflects layer assignment; 33 reflects layer column); ROADMAP §2 has R100 entry; all "Last synced" headers reflect R100
- **Validation step**: manual review of docs consistency

## 3. Dependencies

```
T1 → T2 → T3 → T6 → T7 → T8 → T9
T1 → T4 → T5 → T6
```

T1 is the root. T4 and T5 can proceed after T1 (they only need MemoryLayer type). T2 depends on T1. T3 depends on T1+T2. T6 depends on T3+T4+T5. T7 depends on T2+T6. T8 depends on all. T9 depends on T8.

## 4. Files and Modules

| Task | New files | Modified files |
|------|-----------|----------------|
| T1 | `tests/test_memory_record_contract.py` | `memory/contracts.py`, `memory/__init__.py` |
| T2 | `tests/test_memory_layer_classifier.py` | `memory/engine.py`, `memory/__init__.py` |
| T3 | `tests/test_memory_engine_layer.py` | `memory/engine.py`, `memory/contracts.py` |
| T4 | `tests/test_persistence_layer_extension.py` | `persistence/contracts.py`, `persistence/__init__.py` |
| T5 | `tests/test_persistence_layer_migration.py`, `tests/test_persistence_layer_retrieval.py` | `persistence/engine.py` |
| T6 | `tests/test_composition_layer_bridge.py` | `composition/bridges.py` |
| T7 | `tests/test_runtime_layer_composition.py` | `composition/runtime_composition.py`, `composition/bridges.py` |
| T8 | none | none (validation only) |
| T9 | none | `docs/requirements/index.md`, `docs/PROGRESS_FLOW.*`, `docs/ROADMAP.zh-CN.md` |

## 5. Implementation Order

1. T1 (MemoryLayer + MemoryRecord contract) — foundation
2. T4 (PersistedExperienceRecord additive fields) — can parallel with T2
3. T2 (Classifier protocol + implementation) — depends on T1
4. T5 (SQLite migration + retrieval) — depends on T4
5. T3 (Engine injection) — depends on T1+T2
6. T6 (Bridge projection) — depends on T3+T4+T5
7. T7 (Runtime wiring) — depends on T2+T6
8. T8 (Full regression) — depends on all
9. T9 (Documentation sync) — depends on T8

Estimated total: ~8–10 hours of implementation + testing.

## 6. Validation Plan

### Phase gate after T1+T2+T4+T5 (contracts and persistence foundation)

- All new contract tests pass
- SQLite migration runs correctly
- Existing persistence tests unchanged

### Phase gate after T3+T6+T7 (engine + bridge + wiring)

- Engine produces MemoryRecord with layer
- Bridge projects layer/metadata
- Semantic assembly wires classifier
- Default assembly unchanged

### Phase gate after T8 (full regression)

- All 1172+ tests pass
- R99 emotion probe baseline unchanged

### Phase gate after T9 (documentation)

- index.md has R100 row
- PROGRESS_FLOW synced
- ROADMAP synced

## 7. Completion Criteria

1. `MemoryRecord` and `MemoryLayer` defined in `06` contracts with fail-fast validation
2. `AffectOutcomeMemoryLayerClassifier` implements the C_engineering_hypothesis table
3. `PersistedExperienceRecord` carries `layer` and `memory_metadata` additive fields; SQLite migration idempotent
4. `search_similar(preferred_layers)` and `read_recent(layer_filter)` work on both InMemory and SQLite backends
5. Composition bridge projects `MemoryRecord` → `PersistedExperienceRecord` layer/metadata
6. Semantic assembly wires classifier; default assembly byte-for-byte unchanged
7. All 1172+ existing tests pass; R99 baseline unchanged
8. R100 docs three-piece set complete; index.md / PROGRESS_FLOW / ROADMAP synced
