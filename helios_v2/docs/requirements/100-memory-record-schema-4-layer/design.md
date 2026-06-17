# Requirement 100 — Design: MemoryRecord Schema + 4-Layer Time Stratification

## 1. Title

Requirement 100 — MemoryRecord Schema + 4-Layer Time Stratification

## 2. Design Overview

R100 adds 4-layer time stratification to the memory pipeline. The design follows three principles:

1. **Cognitive contract separation**: `06` memory owns a new `MemoryRecord` that carries the `layer` field as a cognitive judgment. `33` persistence stores it as a projection on the existing `PersistedExperienceRecord` via additive fields.
2. **Write-time assignment**: The `MemoryLayerClassifier` determines the initial layer at write time from affect_intensity and outcome_class. No cross-tick auto-promotion in this slice (deferred to R102).
3. **Additive-only migration**: `PersistedExperienceRecord` gains `layer` and `memory_metadata` as optional additive fields. SQLite adds columns via PRAGMA-guarded `ALTER TABLE`. Legacy records and the default assembly path are byte-for-byte unchanged.

## 3. Current State and Gap

### 3.1 Current `06` memory formation path

The `MemoryAffectReplayEngine` produces `AffectTaggedMemoryItem` + `MemoryReplayCandidate`. The `SalienceGatedReplayCandidateSelector` computes `affect_intensity` and `forced_consolidation` per item. Composition's `ExperienceRecordBridge` builds `PersistedExperienceRecord` from the candidate and memory item, but **the affect_intensity value is lost at the bridge boundary** — it is not persisted anywhere on the record.

### 3.2 Current `33` persistence

`PersistedExperienceRecord` has 17 columns (record_id, tick_id, continuity_kind, outcome_class, source_outcome_kind, source_outcome_id, writeback_status, summary, requested_effect_summary, applied_effect_summary, reason_trace, linkage, sequence, embedding, record_kind, metadata, created_at_wall). No `layer` column exists. SQLite schema has no stratification column.

### 3.3 Current `10` retrieval

`ExperienceStore.search_similar` ranks by cosine similarity with tie-break by sequence (recency). `read_recent` returns the most-recent N records regardless of importance or layer. No stratification bias exists.

### 3.4 Gap

The `06` cognitive judgment (`affect_intensity`, `forced_consolidation`) and the `15` outcome taxonomy (`outcome_class`) are computed at write time but not projected into the persistence layer as a stratification signal. The `10` retrieval has no layer awareness.

## 4. Target Architecture

### 4.1 Data flow (semantic assembly)

```
06 MemoryAffectReplayEngine
   → AffectTaggedMemoryItem (unchanged)
   → MemoryReplayCandidate (unchanged)
   → MemoryRecord (NEW: layer + affect_intensity_at_write + outcome_class_at_write + memory_metadata)
      ↓
Composition ExperienceRecordBridge
   → PersistedExperienceRecord (layer + memory_metadata projected from MemoryRecord)
      ↓
33 ExperienceStore
   → SQLite (layer + memory_metadata columns)
   → search_similar(preferred_layers=...) (layer-aware ranking)
   → read_recent(layer_filter=...) (layer-filtered read)
      ↓
10 DirectedRetrieval
   → ThoughtWindowBundle (layer preference injected by composition)
```

### 4.2 Data flow (default assembly, legacy path)

```
06 MemoryAffectReplayEngine (no classifier injected)
   → AffectTaggedMemoryItem (unchanged)
   → MemoryReplayCandidate (unchanged)
   → NO MemoryRecord produced
      ↓
Composition ExperienceRecordBridge
   → PersistedExperienceRecord (layer=None, memory_metadata=empty)
      ↓
33 ExperienceStore (unchanged retrieval behavior)
```

### 4.3 MemoryRecord production trigger

The `MemoryAffectReplayEngine.run_tick` produces `MemoryRecord` only when:
1. A `MemoryLayerClassifier` is injected into the engine
2. The item passed the salience gate (`forced_consolidation=True`)
3. The `outcome_class` is available from the same tick's `15` result

When any of these conditions is absent, the legacy path produces no `MemoryRecord` and the bridge uses the existing `PersistedExperienceRecord` construction logic unchanged.

## 5. Data Structures

### 5.1 MemoryLayer (NEW, in `helios_v2.memory.contracts`)

```python
MemoryLayer = Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]
```

Type alias, not a free-form string. All modules import from `06`.

### 5.2 MemoryRecord (NEW, in `helios_v2.memory.contracts`)

```python
@dataclass(frozen=True)
class MemoryRecord:
    """Owner: memory affect and replay layer.

    Purpose:
        One immutable cognitive memory record carrying the layer assignment
        determined at write time by the injected classifier. This is the `06`
        cognitive contract; `33` stores its projection on PersistedExperienceRecord.

    Failure semantics:
        Construction raises MemoryAffectReplayError on empty required fields,
        out-of-range affect_intensity, or invalid MemoryLayer.
    """

    memory_id: str
    layer: MemoryLayer
    affect_intensity_at_write: float          # frozen fact, [0, 1]
    outcome_class_at_write: str               # the 15 outcome taxonomy
    source_feeling_state_id: str
    family: MemoryFamily
    content: MemoryContentPacket
    binding_context_id: str | None
    tick_id: int | None
    created_at_wall: float | None             # R92 wall-time at write
    memory_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise MemoryAffectReplayError("MemoryRecord must declare a non-empty memory_id")
        if not self.source_feeling_state_id:
            raise MemoryAffectReplayError("MemoryRecord must declare a non-empty source_feeling_state_id")
        if self.layer not in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
            raise MemoryAffectReplayError(f"MemoryRecord layer must use the 4-layer taxonomy, got: {self.layer}")
        _validate_unit_interval("MemoryRecord.affect_intensity_at_write", self.affect_intensity_at_write)
        if not self.outcome_class_at_write:
            raise MemoryAffectReplayError("MemoryRecord must declare a non-empty outcome_class_at_write")
```

### 5.3 PersistedExperienceRecord additive fields

```python
# Additive fields on PersistedExperienceRecord:
layer: MemoryLayer | None = None             # honest absence for legacy records
memory_metadata: Mapping[str, str] = field(default_factory=dict)  # opaque, 06-owned keys
```

`__post_init__` extends validation: when `layer` is not `None`, it must be one of the 4 `MemoryLayer` literals. `memory_metadata` keys must be non-empty strings (same rule as `metadata`).

### 5.4 MemoryLayerClassifier protocol (NEW, in `helios_v2.memory.engine`)

```python
@runtime_checkable
class MemoryLayerClassifier(Protocol):
    """Owner: memory affect and replay layer.

    Purpose:
        Determine the initial MemoryLayer for a memory item based on
        formation-time affect_intensity and outcome_class.
    """

    def classify_layer(
        self,
        affect_intensity: float,
        outcome_class: str,
    ) -> MemoryLayer:
        """Return the initial layer assignment for this memory item."""
        ...
```

### 5.5 AffectOutcomeMemoryLayerClassifier (NEW, in `helios_v2.memory.engine`)

```python
@dataclass
class AffectOutcomeMemoryLayerClassifier:
    """Owner: memory affect and replay layer.

    Purpose:
        First-version layer classifier using affect_intensity thresholds and
        outcome_class taxonomy. All thresholds are C_engineering_hypothesis
        first-version constants under 'layer_assignment_policy'.

    Brain analogy:
        L2 ≈ sensory register (sub-second); L3 ≈ hippocampal short-term
        (minutes-hours); L4 ≈ cortical long-term (days-weeks);
        L5 ≈ autobiographical/identity (months-years). The thresholds are
        cautious engineering approximations, not calibrated neuroscience.
    """

    low_affect_threshold: float = 0.15       # C_engineering_hypothesis
    high_affect_threshold: float = 0.50      # C_engineering_hypothesis
    identity_outcome_classes: tuple[str, ...] = ("self_changed",)

    def classify_layer(self, affect_intensity: float, outcome_class: str) -> MemoryLayer:
        if affect_intensity < self.low_affect_threshold:
            if outcome_class in ("internal_to_visible_consequence", "no_outcome"):
                return "L2_working"
            return "L3_short"
        if affect_intensity >= self.high_affect_threshold:
            if outcome_class in self.identity_outcome_classes:
                return "L5_autobiographical"
            return "L4_long"
        # affect_intensity in [0.15, 0.50)
        if outcome_class in self.identity_outcome_classes:
            return "L4_long"
        return "L3_short"
```

### 5.6 MemoryLearnedParameterCategory extension

The existing `MemoryLearnedParameterCategory` Literal gains a new value:

```python
MemoryLearnedParameterCategory = Literal[
    "memory_family_write_policy",
    "replay_priority_policy",
    "consolidation_policy",
    "layer_assignment_policy",   # NEW
]
```

`MemoryAffectReplayConfig.mandatory_learned_parameters` must include `"layer_assignment_policy"` when the classifier is wired.

## 6. Module Changes

### 6.1 `helios_v2/memory/contracts.py`

- ADD `MemoryLayer` type alias
- ADD `MemoryRecord` frozen dataclass
- MODIFY `MemoryLearnedParameterCategory` to include `"layer_assignment_policy"`

### 6.2 `helios_v2/memory/engine.py`

- ADD `MemoryLayerClassifier` protocol
- ADD `AffectOutcomeMemoryLayerClassifier` implementation
- MODIFY `MemoryAffectReplayEngine` to accept optional `layer_classifier: MemoryLayerClassifier | None` field
- MODIFY `MemoryAffectReplayEngine.run_tick` to produce `MemoryRecord` when classifier is present and item has `forced_consolidation`

### 6.3 `helios_v2/memory/__init__.py`

- ADD exports: `MemoryRecord`, `MemoryLayer`, `MemoryLayerClassifier`, `AffectOutcomeMemoryLayerClassifier`

### 6.4 `helios_v2/persistence/contracts.py`

- ADD `layer: MemoryLayer | None = None` on `PersistedExperienceRecord`
- ADD `memory_metadata: Mapping[str, str] = field(default_factory=dict)` on `PersistedExperienceRecord`
- MODIFY `__post_init__` to validate `layer` (None or valid literal) and `memory_metadata` keys
- Import `MemoryLayer` from `helios_v2.memory.contracts`

### 6.5 `helios_v2/persistence/engine.py`

- ADD SQLite `ALTER TABLE` migration: `layer TEXT` + `memory_metadata TEXT` columns (PRAGMA-guarded, idempotent, same pattern as R45/R92)
- MODIFY `_row_to_record` to read `layer` and `memory_metadata` from extended columns (forward-compatible: `len(row) > 18` guard)
- MODIFY `InMemoryExperienceStoreBackend.search_similar` to accept `preferred_layers` parameter; apply `layer_preference_weight` boost
- MODIFY `InMemoryExperienceStoreBackend.read_recent` to accept `layer_filter` parameter
- MODIFY `SqliteExperienceStoreBackend.search_similar` to accept `preferred_layers` parameter
- MODIFY `SqliteExperienceStoreBackend.read_recent` to accept `layer_filter` parameter
- MODIFY `ExperienceStore` facade to forward both parameters to backends

### 6.6 `helios_v2/persistence/__init__.py`

- ADD `MemoryLayer` import from `helios_v2.memory.contracts` for `33` consumers

### 6.7 `helios_v2/composition/bridges.py`

- MODIFY `ExperienceRecordBridge.build_records` to project `MemoryRecord.layer` → `PersistedExperienceRecord.layer` and `MemoryRecord.memory_metadata` → `PersistedExperienceRecord.memory_metadata`
- ADD `MemoryRecordBridge` (or extend `ExperienceRecordBridge`) to also project `MemoryRecord` fields for affect-memory records

### 6.8 `helios_v2/composition/runtime_composition.py`

- ADD `RuntimeProfile.memory_layer_classifier: MemoryLayerClassifier | None = None` field
- ADD `RuntimeProfile.memory_layer_preference: tuple[MemoryLayer, ...] | None = None` field (default `("L4_long", "L5_autobiographical")` on semantic)
- MODIFY semantic assembly to wire `AffectOutcomeMemoryLayerClassifier` into engine and `memory_layer_preference` into retrieval

## 7. Migration Plan

### 7.1 SQLite migration

1. At `SqliteExperienceStoreBackend.initialize()`, after creating the base table, run PRAGMA-guarded `ALTER TABLE` to add `layer TEXT` and `memory_metadata TEXT` columns.
2. Existing rows automatically have `NULL` for both columns — read back as `layer=None` and `memory_metadata=None`.
3. The migration is idempotent: `PRAGMA table_info(experience_store)` checks column existence before `ALTER TABLE`.
4. Same pattern as R45 (metadata column) and R92 (created_at_wall column).

### 7.2 Legacy compatibility

1. `PersistedExperienceRecord` with `layer=None` is the legacy record. All existing retrieval code treats it as a flat record (no layer bias).
2. The default `assemble_runtime()` does NOT wire the classifier. The engine's `layer_classifier` field is `None`. `MemoryRecord` is never produced. The bridge uses the existing construction logic unchanged.
3. The semantic `assemble_runtime(default_signal_mode="semantic")` (and `assemble_production_runtime()`) wires the classifier. New records carry `layer`.
4. Mixed store: old records have `layer=None`; new records have `layer="L3_short"` etc. Retrieval with `preferred_layers` treats `layer=None` records as non-preferred (no boost). Retrieval without `preferred_layers` is unchanged.

### 7.3 Default rollout behavior

- Default: classifier OFF, layer OFF (same as pre-R100)
- Semantic assembly: classifier ON, layer preference `("L4_long", "L5_autobiographical")`
- Production assembly (`assemble_production_runtime`): classifier ON (inherits from semantic)

## 8. Failure Modes and Constraints

### 8.1 Classifier absent

When the classifier is not injected, `MemoryRecord` is not produced. The legacy path runs unchanged. This is not an error; it is the default-off behavior.

### 8.2 Missing affect_intensity or outcome_class

When `affect_intensity` or `outcome_class` is unavailable at write time (e.g., a tick with no salience gate firing, or a `15` writeback that has not yet produced an outcome), the classifier must assign `L2_working` (the safest, shortest-lived layer) and the engine must log the fallback via the `21` observability mechanism. This is honest absence — the record acknowledges it could not be properly classified.

### 8.3 SQLite migration failure

If the `ALTER TABLE` migration fails (e.g., read-only database, corrupted file), the backend must raise `PersistenceError` fail-fast. No degraded path without columns.

### 8.4 Mixed legacy/new records

When `search_similar` is called with `preferred_layers`, `layer=None` records are ranked as non-preferred (no boost). This means legacy records are still retrievable but not preferred. This is intentional: the classifier's judgment should gradually stratify the store.

### 8.5 memory_metadata size constraint

`memory_metadata` is stored as JSON TEXT in SQLite. No size limit is enforced at the contract level (the `PersistedExperienceRecord` `metadata` field has no limit either). Practical constraint: the JSON string must not exceed the SQLite row size limit (1GB theoretical, practical ~1MB). R101 objective_importance fields will be small (~6 floats), so no current concern.

## 9. Observability and Logging

1. `MemoryRecord` production: when the classifier produces a `MemoryRecord`, the engine's `run_tick` result includes a `memory_records: tuple[MemoryRecord, ...]` field (additive on `MemoryAffectReplayStageResult`). Composition reads it for bridge projection.
2. Layer assignment fallback: when the classifier assigns `L2_working` due to missing data, the engine emits a `21`-logged diagnostic (not a `print`/`logging` call; owner-neutral composition-glue projects it into the observability path).
3. No new ad-hoc logging mechanism: the no-adhoc-logging guard stays green.

## 10. Validation Strategy

### 10.1 Contract tests (network-free)

1. `MemoryRecord` construction: valid fields → success; empty `memory_id` → `MemoryAffectReplayError`; invalid `layer` → error; out-of-range `affect_intensity_at_write` → error.
2. `AffectOutcomeMemoryLayerClassifier.classify_layer`: all 6 table rows covered with explicit test cases; boundary values (0.15, 0.50) tested; extreme values (0.0, 1.0) tested.
3. `PersistedExperienceRecord` with `layer=None` → construction succeeds; with `layer="L3_short"` → succeeds; with `layer="invalid"` → `PersistenceError`.

### 10.2 Engine integration tests (network-free)

1. `MemoryAffectReplayEngine` with classifier: run_tick produces `MemoryRecord` with correct `layer`.
2. `MemoryAffectReplayEngine` without classifier: run_tick produces no `MemoryRecord`; `AffectTaggedMemoryItem` path unchanged.

### 10.3 Persistence tests (network-free)

1. SQLite migration: `ALTER TABLE` adds columns; pre-existing row reads `layer=None`; new row with `layer="L4_long"` reads correctly; idempotent migration (run twice → no error).
2. `search_similar(preferred_layers=("L4_long",))`: L4 record at similarity 0.5 beats L2 record at similarity 0.5 (boosted to 0.75).
3. `read_recent(layer_filter="L4_long")`: returns only L4 records; mixed store returns L4 subset.

### 10.4 Composition wiring tests (network-free)

1. `ExperienceRecordBridge` projects `MemoryRecord.layer` → `PersistedExperienceRecord.layer`.
2. Legacy path (no `MemoryRecord`) produces `PersistedExperienceRecord` with `layer=None`.

### 10.5 Regression tests

1. All 1172+ existing tests pass unchanged (default assembly byte-for-byte unchanged).
2. R99 emotion validation probe runs unchanged (no layer dependency in probe code).

### 10.6 End-to-end smoke (network-free)

1. Semantic assembly runs N ticks; formed records carry `layer`; store contains L2/L3/L4/L5 records proportionally matching the affect_intensity/outcome_class distribution.
