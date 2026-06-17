# Requirement 100 — MemoryRecord Schema + 4-Layer Time Stratification

## 1. Background and Problem

The current memory architecture stores all experience records in a single flat store (`PersistedExperienceRecord` in `33`). Every record — whether a trivial internal-only tick closure or a world-changing event with high affect intensity — is persisted with the same recency-based retrieval priority. This creates three fundamental problems:

1. **No time stratification**: The brain's memory system organizes experience into distinct temporal layers — working memory (seconds), short-term (minutes-to-hours), long-term (days-to-weeks), and autobiographical/identity-level (months-to-years). The current flat store has no layer concept; all records compete equally for retrieval, so a 3-day-old trivial internal-only closure competes with yesterday's emotionally significant conversation for workspace entry.

2. **No importance-aware persistence**: The `06` salience gate (`SalienceGatedReplayCandidateSelector`) already computes affect_intensity and decides whether a memory item is consolidation-worthy (`forced_consolidation`). But this cognitive judgment is lost at the persistence boundary — once a record enters the `33` store, its formation salience is recorded only as `reason_trace` strings, not as a stratification signal. The store cannot filter or prioritize by importance.

3. **Flat retrieval**: The `10` directed retrieval reads `search_similar` results from a single store without any layer bias. Under a growing store, high-affect L4-level records are diluted by low-affect L2-level records, reducing retrieval relevance.

The beta branch (`aggressive-radical-persona-no-theater` R85) pre-validated a more complete dual-track memory architecture including `objective_importance`, `double_confirmation`, `Ebbinghaus decay`, and `memory_tool_channel`. R100 takes the **incremental slice approach** per ROADMAP §5: first only the schema + 4-layer stratification, leaving objective_importance (R101), Ebbinghaus decay (R102), retrieval scaling (R103), tool channel (R104), and forget governance (R105) for subsequent slices.

## 2. Goal

Add 4-layer time stratification (L2_working / L3_short / L4_long / L5_autobiographical) to the memory system, so that every `06`-formed memory record carries an explicit `layer` field determined at write time by affect_intensity and outcome_class, and the `33` store can filter and prioritize records by layer.

This slice does NOT include: objective_importance scoring (R101), Ebbinghaus decay/auto-promotion (R102), bounded-window retrieval (R103), memory_tool_channel (R104), forget governance (R105).

## 3. Functional Requirements

### 3.1 MemoryRecord schema (owner `06`)

1. A new frozen dataclass `MemoryRecord` in `helios_v2.memory.contracts` must represent the cognitive memory contract owned by `06`. It must carry: `memory_id`, `layer` (4-layer taxonomy), `affect_intensity_at_write` (the `06` salience gate's computed value at formation time, frozen as a fact), `outcome_class_at_write` (the `15` outcome taxonomy at write time), `source_feeling_state_id`, `family` (MemoryFamily), `content` (MemoryContentPacket), `binding_context_id`, `tick_id`, `created_at_wall`, plus an opaque `memory_metadata: Mapping[str, str]` for R101+ additive extensions.
2. `MemoryLayer` must be a `Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]` type — not a free-form string.
3. `MemoryRecord` must be immutable (`frozen=True`). Construction must fail-fast on empty required fields.
4. `memory_metadata` must default to an empty frozen mapping; `06` owns what keys it carries; `33` stores it verbatim without interpreting the keys.

### 3.2 Initial layer assignment (owner `06`)

1. A new `MemoryLayerClassifier` protocol in `helios_v2.memory.engine` must determine the initial `MemoryLayer` from the formation-time affect_intensity and outcome_class.
2. The first-version classifier `AffectOutcomeMemoryLayerClassifier` must implement the following `C_engineering_hypothesis` rules (bounded, explicit, documented as first-version constants under `MemoryLearnedParameterCategory "layer_assignment_policy"`):

| Condition | Layer |
|-----------|-------|
| `affect_intensity < 0.15` AND outcome_class is `internal_to_visible_consequence` or `no_outcome` | `L2_working` |
| `affect_intensity < 0.15` AND outcome_class is any other | `L3_short` |
| `affect_intensity >= 0.15` AND `affect_intensity < 0.50` | `L3_short` |
| `affect_intensity >= 0.50` AND outcome_class is `self_changed` | `L5_autobiographical` |
| `affect_intensity >= 0.50` AND outcome_class is not `self_changed` | `L4_long` |
| `affect_intensity >= 0.15` AND outcome_class is `self_changed` AND `affect_intensity < 0.50` | `L4_long` |

3. The classifier must be injected into the `MemoryAffectReplayEngine` at composition; the engine does not import it statically.
4. When the classifier is absent (legacy assembly, default `assemble_runtime`), `MemoryRecord` is NOT produced and the legacy `AffectTaggedMemoryItem` + `PersistedExperienceRecord` path runs byte-for-byte unchanged.

### 3.3 PersistedExperienceRecord additive extension (owner `33`)

1. `PersistedExperienceRecord` gains two additive optional fields: `layer: MemoryLayer | None = None` and `memory_metadata: Mapping[str, str] = field(default_factory=dict)`.
2. When `layer` is `None` (legacy records predating R100, or records from the default assembly that does not wire the classifier), the record is a flat store record — existing retrieval and persistence behavior is byte-for-byte unchanged.
3. When `layer` is set, the `33` SQLite backend must persist it via a PRAGMA-guarded `ALTER TABLE` migration (mirroring the R45/R92 pattern), adding a `layer` column (TEXT, nullable) and a `memory_metadata` column (TEXT, nullable, JSON-encoded). A pre-existing row with no `layer` reads back as `layer=None` (honest absence).
4. `PersistedExperienceRecord.__post_init__` must validate that `layer` is either `None` or one of the 4 valid `MemoryLayer` literals when present. `memory_metadata` keys must be non-empty strings; `33` does not interpret the values.

### 3.4 Layer-aware retrieval (owner `10` / `33`)

1. `ExperienceStore.search_similar` gains an additive optional `preferred_layers: tuple[MemoryLayer, ...] | None = None` parameter. When set, hits matching a preferred layer are boosted in ranking (their similarity score is multiplied by a `layer_preference_weight`, default 1.5, first-version constant). Hits not in any preferred layer are ranked at their raw cosine similarity. The result ordering becomes: preferred-layer hits first (by boosted similarity), then non-preferred hits (by raw similarity), then tie-break by recency.
2. `ExperienceStore.read_recent` gains an additive optional `layer_filter: MemoryLayer | None = None` parameter. When set, only records with matching `layer` are returned (descending recency within that layer). When `None`, existing behavior is byte-for-byte unchanged.
3. Both parameters must be additive; the default `assemble_runtime()` path calls `search_similar` and `read_recent` without them, so all existing tests pass unchanged.

### 3.5 Composition wiring

1. When `RuntimeProfile` includes a `memory_layer_classifier` (set by the semantic assembly), composition wires it into the `MemoryAffectReplayEngine`.
2. The `ExperienceRecordBridge` (composition) must project the `06`-formed `MemoryRecord.layer` into the corresponding `PersistedExperienceRecord.layer` field, and the `MemoryRecord.memory_metadata` into the corresponding `memory_metadata` field. When no `MemoryRecord` is available (legacy path), both fields remain `None` / empty dict.
3. The `10` directed retrieval bridge (composition) must project the `MemoryLayerClassifier`'s output and the `RuntimeProfile.memory_layer_preference` into the `search_similar` and `read_recent` calls, so retrieval biases toward higher layers when the classifier is wired.

## 4. Non-Functional Requirements

1. **Additive-first**: `PersistedExperienceRecord`, `ExperienceStore`, `MemoryAffectReplayEngine`, and all composition bridges gain only additive optional fields/parameters. No existing contract field is removed, renamed, or changed in type. Legacy assembly (`assemble_runtime()` without classifier) is byte-for-byte unchanged.
2. **Migration-safe**: SQLite `ALTER TABLE` adds columns; no existing column is modified or deleted. Pre-existing rows read back with `layer=None` and `memory_metadata=None` (honest absence). The migration is idempotent (PRAGMA-guarded, same pattern as R45/R92).
3. **Owner boundary**: `06` owns MemoryRecord and the layer assignment strategy. `33` owns persistence and the layer column. `10` owns retrieval ranking but the layer preference is composition-injected. Composition owns wiring only. No cognitive owner imports another cognitive owner's internals.
4. **C_engineering_hypothesis**: The initial layer assignment thresholds (0.15, 0.50) and weights are documented first-version constants under `MemoryLearnedParameterCategory "layer_assignment_policy"`, not calibrated neuroscientific parameters. The `layer_preference_weight` (1.5) is similarly a first-version constant under `MemoryLearnedParameterCategory "replay_priority_policy"`.
5. **Honest absence**: A record without `layer` is `None`, never a fabricated default. A classifier that cannot decide (missing affect_intensity or outcome_class) must assign `L2_working` (the safest, shortest-lived layer) and log the fallback via `21` observability.
6. **Performance**: The `ALTER TABLE` migration runs once at SQLite initialization. Layer filtering in `read_recent` is a linear scan over the bounded recent window (not a full store scan). `search_similar` layer preference is a post-rank adjustment over the already-bounded scan window. No ANN or index is required (R103).
7. **Compatibility**: All 1172+ existing network-free tests must pass unchanged. R99 emotion validation probe baseline must not regress.

## 5. Code Behavior Constraints

1. **Forbidden**: destructive migration of `PersistedExperienceRecord` (no field removal, type change, or rename). The additive pattern is mandatory.
2. **Forbidden**: cross-tick auto-promotion (L3→L4, L4→L5) in this slice. Layer assignment happens only at write time. Promotion is deferred to R102.
3. **Forbidden**: importing `MemoryRecord` from `helios_v2.persistence` — `06` owns the cognitive contract, `33` stores a projection.
4. **Forbidden**: hardcoding `MemoryLayer` values outside `06` contracts and `33` persistence. The 4-layer taxonomy lives in `helios_v2.memory.contracts` as a `Literal` type; other modules reference it by importing from `06`.
5. **Forbidden**: `objective_importance`, `double_confirmation`, `Ebbinghaus decay`, `memory_tool_channel`, or `forget` in this slice — these belong to R101–R105.
6. **Boundary**: `06` owns layer assignment strategy; composition injects the classifier; `33` persists the layer as an opaque column; `10` uses it for ranking. No module owns another's strategy.

## 6. Impacted Modules

1. `helios_v2/memory/contracts.py` — NEW `MemoryRecord`, `MemoryLayer` type, `MemoryLayerClassifier` protocol
2. `helios_v2/memory/engine.py` — `MemoryAffectReplayEngine` gains classifier injection; formation path produces `MemoryRecord`
3. `helios_v2/memory/__init__.py` — export `MemoryRecord`, `MemoryLayer`, `MemoryLayerClassifier`, `AffectOutcomeMemoryLayerClassifier`
4. `helios_v2/persistence/contracts.py` — `PersistedExperienceRecord` additive `layer`, `memory_metadata`
5. `helios_v2/persistence/engine.py` — SQLite `ALTER TABLE` migration; `search_similar` + `read_recent` additive parameters; read-back handles nullable columns
6. `helios_v2/persistence/__init__.py` — export `MemoryLayer` reference for `33` consumers
7. `helios_v2/directed_retrieval/` — `10` retrieval bridge uses layer preference
8. `helios_v2/composition/bridges.py` — `ExperienceRecordBridge` projects `MemoryRecord` → `PersistedExperienceRecord` layer/metadata
9. `helios_v2/composition/runtime_composition.py` — `RuntimeProfile` gains `memory_layer_classifier` seam; semantic assembly wires classifier
10. `helios_v2/tests/` — NEW R100 contract/engine/bridge/retrieval tests + updated fixtures
11. `docs/requirements/100-memory-record-schema-4-layer/` — R100 docs
12. `docs/requirements/index.md` — R100 row

## 7. Acceptance Criteria

1. `MemoryRecord` carries `layer` field with 4-layer taxonomy; construction fails on empty required fields.
2. `AffectOutcomeMemoryLayerClassifier` assigns initial layer per the `C_engineering_hypothesis` table; `affect_intensity >= 0.50` + `self_changed` → `L5_autobiographical`; `affect_intensity < 0.15` + `internal_to_visible_consequence` → `L2_working`.
3. `PersistedExperienceRecord` additive fields `layer` and `memory_metadata` persist through SQLite; pre-existing rows read back as `layer=None`.
4. `ExperienceStore.search_similar(preferred_layers=("L4_long", "L5_autobiographical"))` ranks L4/L5 hits above L2/L3 hits at equivalent raw cosine similarity.
5. `ExperienceStore.read_recent(limit=10, layer_filter="L4_long")` returns only L4 records.
6. Legacy assembly (`assemble_runtime()` without classifier) is byte-for-byte unchanged; all 1172+ existing tests pass.
7. Semantic assembly (`assemble_runtime(default_signal_mode="semantic")`) wires the classifier; formed records carry `layer`.
8. R99 emotion validation probe baseline does not regress.
9. R100 docs three-piece set complete (requirement.md, design.md, task.md).
10. `index.md` / `PROGRESS_FLOW` maps synced.
