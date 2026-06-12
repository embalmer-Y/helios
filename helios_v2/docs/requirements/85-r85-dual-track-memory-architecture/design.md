# R85: Dual-Track Memory Architecture — Design

## 1. Design Overview

R85 implements the dual-track memory architecture proposed in `docs/research/memory_redesign/05_design_proposal.md` (pre-research commit `382d2e8`):

- **Track A**: 4-layer time stratification + objective importance override + double confirmation + decay + reconsolidation + soft-delete
- **Track B**: New mandatory driver (owner 31) implementing 3 of 5 LLM-callable memory tools via the owner 30 channel subsystem

The design is **conservative**: it does not touch R10 / R15 / R82 / R83 / R84 first-version behavior. R85 *adds* new fields, new functions, and a new owner; legacy code paths continue to work.

## 2. Current State and Gap

See `docs/research/memory_redesign/04_helios_current_state.md` for the full gap analysis. Summary:

| Gap | Current state | R85 fix |
|---|---|---|
| Single store, no time stratification | 4-tier naming in `RetrievalRequest.target_tiers` but no actual layered storage | `MemoryRecord.layer` field + `read_memory_records_by_layer` |
| No time decay | store grows forever | `effective_priority` function with Ebbinghaus decay |
| LLM-dominated decision | `FirstVersionExperienceWritebackPath` reads `llm_output.remember_this` only | `should_persist` adds `objective_importance` override |
| No reconsolidation | recall does not modify the record | bump `recall_count` + `last_recall_at_wall` on every R10 hit |
| No active forgetting | no forget API | `MemoryRecord.soft_delete` + `ForgetDriver` (L18 gated) |
| No LLM active management tools | LLM cannot `recall()` / `forget()` / `consolidate()` | owner 31 `MemoryToolChannelDriver` |
| No reflection cycle | no DMN | deferred to R88 |
| No sleep consolidation | no background job | deferred to R88 |

## 3. Target Architecture

### 3.1 Owner 31 (NEW): memory_tool_channel

```
                  +----------------------------------+
                  | owner 30 channel subsystem      |
                  | (ChannelDriver Protocol)        |
                  +----------------------------------+
                                  ^
                                  | implements
                                  |
   +------------------------------------------------------+
   | owner 31 memory_tool_channel                         |
   |   MemoryToolChannelDriver                            |
   |   (mandatory, always registered)                     |
   +------------------------------------------------------+
       |               |              |
       v               v              v
   +-------+      +-----------+   +-----------+
   |Recall |      |Consolidate|   |  Forget   |
   |Driver |      |  Driver   |   |  Driver   |
   +-------+      +-----------+   +-----------+
       |               |              |
       v               v              v
   R10 directed    L4 promotion    L18 governance
   retrieval      + audit         + soft-delete
   + recall       trail append    + audit trail
     counter
     bump
```

### 3.2 Data flow

```
[LLM output] "我想起了上次他生气的时候"
       |
       v
v3 prompt post-processor (owner 31 intent_parser)
       |
       v
MemoryToolCall(tool_name="recall", args={"query": "上次他生气的时候"}, priority="low")
       |
       v
ChannelSubsystem.dispatch(MemoryToolCall) → outbound packet
       |
       v
MemoryToolChannelDriver.send_outbound(packet) → RecallDriver
       |
       v
R10 directed retrieval → MemoryRetrievalCandidate list
       |
       v
For each hit: bump recall_count + last_recall_at_wall on the record (reconsolidation)
       |
       v
Construct inbound packet with tool_result
       |
       v
Next tick: inject inbound packet into v3 prompt as retrieval context
```

### 3.3 Persistence layer

```
InMemoryExperienceStoreBackend / SqliteExperienceStoreBackend
       |
       v (backward compat)
PersistedExperienceRecord (legacy)   ←-- reads unchanged
       |
       v (new field auto-migrated on first read)
MemoryRecord (Track A)               ←-- new writes go here
       |
       v (query by layer)
read_memory_records_by_layer(layer: Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"])
```

### 3.4 Default rollout

- `assemble_runtime` **always** registers `MemoryToolChannelDriver` (no toggle)
- `assemble_runtime` **always** uses `MemoryRecord` for new writes (auto-migration on read)
- `objective_importance` is **always** computed (no toggle)
- Double-confirmation is **always** active
- Decay is **always** applied during R10 retrieval
- Soft-delete is **always** available (the L18 gate decides when it is permitted)

R85 is default-on. The only configurable knob is `MemoryToolChannelConfig`:
- `max_tool_calls_per_tick` (default 3)
- `max_recall_per_tick` (default 5)
- `decay_per_day` (default 0.05)
- `recall_rebound_factor` (default 0.1)

## 4. Data Structures

### 4.1 MemoryRecord (new, owner 06 memory/contracts.py)

```python
@dataclass(frozen=True)
class MemoryRecord:
    # Legacy (preserved)
    record_id: str
    tick_id: int
    continuity_kind: str
    outcome_class: str
    summary: str

    # Track A new
    layer: Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]
    objective_importance: float
    llm_remember_decision: bool
    double_confirmation_class: Literal["persist_full", "persist_low_priority", "skip"]
    hormone_snapshot: Mapping[str, float]
    feeling_snapshot: Mapping[str, float]

    created_at_tick: int
    created_at_wall: float
    last_recall_at_wall: float | None
    recall_count: int
    is_consolidated: bool
    soft_deleted_at: float | None
    memory_gc_after: float | None
    audit_trail: tuple[Mapping[str, str], ...]

    tags: tuple[str, ...]
    context_keywords: tuple[str, ...]
    cross_links: tuple[str, ...]
```

### 4.2 MemoryToolCall (new, owner 31)

```python
@dataclass(frozen=True)
class MemoryToolCall:
    tool_name: Literal["recall", "consolidate", "forget"]  # R87 adds link, reflect
    args: Mapping[str, str]
    priority: Literal["low", "medium", "high"]
    source_tick: int
    source_llm_output_id: str

@dataclass(frozen=True)
class MemoryToolResult:
    call_id: str
    tool_name: str
    success: bool
    result_payload: Mapping[str, object] | None
    rejection_reason: str | None
    latency_ms: float
```

### 4.3 MemoryToolChannelConfig (new, owner 31)

```python
@dataclass(frozen=True)
class MemoryToolChannelConfig:
    max_tool_calls_per_tick: int = 3
    max_recall_per_tick: int = 5
    decay_per_day: float = 0.05
    recall_rebound_factor: float = 0.1
    novelty_window_size: int = 20
    objective_threshold_full: float = 0.5
    objective_threshold_low: float = 0.2
```

### 4.4 Layer promotion rules

| From | To | Trigger |
|---|---|---|
| L3_short | L4_long | `recall_count >= 2` (synaptic tagging) |
| L3_short | (decay) | `effective_priority < 0.1` (auto-decay below threshold) |
| L4_long | L5_autobiographical | `recall_count >= 5` AND `objective_importance >= 0.7` |
| L4_long | (soft_delete) | `forget()` L18 approved |
| any | (soft_delete) | L18 `check_forget_permission` approved |

## 5. Module Changes

### 5.1 New: `src/helios_v2/memory_tool_channel/`

- `__init__.py` — public exports
- `contracts.py` — `MemoryToolCall`, `MemoryToolResult`, `MemoryToolChannelConfig`, `MemoryToolChannelAPI`, `MemoryToolError`, `MemoryToolGovernanceError`
- `engine.py` — `MemoryToolChannelDriver` (implements owner 30 `ChannelDriver` Protocol)
- `intent_parser.py` — `MemoryToolIntentParser` (LLM output → tool calls, regex-based)
- `drivers/__init__.py` — sub-driver factory
- `drivers/recall.py` — `RecallDriver.execute(call) -> MemoryToolResult`
- `drivers/consolidate.py` — `ConsolidateDriver.execute(call) -> MemoryToolResult`
- `drivers/forget.py` — `ForgetDriver.execute(call) -> MemoryToolResult` (L18-gated)

### 5.2 Modified: `src/helios_v2/memory/contracts.py`

Add `MemoryRecord` dataclass + `objective_importance` function signature.

### 5.3 Modified: `src/helios_v2/memory/engine.py`

Implement `objective_importance` with the 6-dim formula. Helper `_novelty_cosine(stimulus, recent_records) -> float`.

### 5.4 Modified: `src/helios_v2/persistence/engine.py`

- Add `append_memory_record(record: MemoryRecord) -> None`
- Add `read_memory_records_by_layer(layer: str) -> list[MemoryRecord]`
- Add `_migrate_persisted_to_memory_v2(legacy: PersistedExperienceRecord) -> MemoryRecord` (one-shot, idempotent)

### 5.5 Modified: `src/helios_v2/experience_writeback/contracts.py`

Add `double_confirmation_class` field to `ExperienceWritebackRequest`.

### 5.6 Modified: `src/helios_v2/experience_writeback/engine.py`

In `FirstVersionExperienceWritebackPath.write`:
1. Compute `objective_importance`
2. Compute `should_persist`
3. Branch on `double_confirmation_class`

### 5.7 Modified: `src/helios_v2/directed_retrieval/engine.py`

In `FirstVersionDirectedRetrievalPath.plan_and_select`, after a retrieval hit:
1. Bump `recall_count`
2. Set `last_recall_at_wall = time.time()`
3. If `recall_count >= 2 AND !is_consolidated`, set `is_consolidated = True`

### 5.8 Modified: `src/helios_v2/runtime_assembly.py`

- Import `MemoryToolChannelDriver` from owner 31
- In `assemble_runtime`, **always** call `register_source` for the memory tool channel driver
- Wire `MemoryRecord` writes to the existing `experience_store` (auto-migration on legacy reads)

### 5.9 Modified: `src/helios_v2/composition/bridges.py`

Add a new bridge that:
- Renders the 3 tool instructions into the v3 prompt (R79-D compat)
- Connects `MemoryToolChannelDriver.drain_inbound` results into the v3 prompt as retrieval context

### 5.10 Modified: `src/helios_v2/tests/r79d/framework.py`

Extend the v3 prompt template with a new section "记忆工具说明" (memory tool instructions).

### 5.11 Modified: `src/helios_v2/identity_governance/engine.py`

Implement `check_forget_permission(record, reason, justification) -> GovernanceVerdict`:
- Default fail-closed: `allowed = False`
- Allowed iff: `record.layer != "L5_autobiographical"` (autobiographical is permanent)
- Records marked `non_forgettable: True` are always denied

## 6. Migration Plan

### 6.1 Backward compatibility

- `PersistedExperienceRecord` (legacy) continues to be readable
- `_migrate_persisted_to_memory_v2` runs on read; migrated records have `layer = "L4_long"`, `objective_importance = 0.5` (default), `is_consolidated = False`, `audit_trail = ()`
- New writes always produce `MemoryRecord`

### 6.2 R85 vs R84 boundary

- R84's `MemoryProbe` (R83) reads `experience_store.read_recent()` — this still works (legacy interface)
- R84's `LongRunner` does not need changes (the R85 changes are additive)
- R84's A3 score is unchanged in semantics; the underlying records are now `MemoryRecord` but the `read_recent` interface returns the same fields

### 6.3 Default behavior

- R85 ships **default-on** for all new behavior
- The 3 drivers are always registered
- The 4-layer model is always active
- Decay is always computed during R10 retrieval
- Double-confirmation is always enforced
- Soft-delete is always available

## 7. Failure Modes and Constraints

| Failure | Behavior |
|---|---|
| Owner 31 fails to register | `assemble_runtime` raises (fail-fast; owner 31 is mandatory) |
| LLM intent parser cannot parse an output | The output is treated as normal LLM output; no tool call is dispatched (fail-soft at LLM layer) |
| Recall quota exceeded | Excess recalls are deferred to the next tick |
| Forget L18 check fails | `MemoryToolGovernanceError` returned; the record is NOT soft-deleted; the LLM sees a rejection reason |
| Audit trail write fails | `soft_delete` is rolled back (fail-closed) |
| Decay computation overflows (record > 1 year old) | Clamp `effective_priority` to 0.0 (fail-safe) |
| Embedding gateway unavailable during novelty computation | Fall back to recency proxy (last record's id differs) |
| Backward compat: legacy record missing `layer` field | Auto-migrate to `L4_long` on first read |

## 8. Observability and Logging

Each `MemoryRecord` write is logged via the observability owner (`observability.metrics`):
- `memory_record_count{layer=, double_confirmation_class=}` (counter)
- `memory_record_objective_importance{layer=}` (histogram)

Each tool call is logged:
- `memory_tool_call_total{tool_name=, result_class=}` (counter)
- `memory_tool_call_latency_ms{tool_name=}` (histogram)
- `memory_tool_call_quota_exceeded{tick=}` (counter)

Forgetting is audited (permanent log):
- `memory_forget_audit{record_id, reason, allowed, denial_reason}` (counter)

## 9. Validation Strategy

### 9.1 Unit tests (≥ 48)

- `tests/test_r85_memory_record.py` (≥ 8): schema, migration, decay, reconsolidation, soft-delete
- `tests/test_r85_objective_importance.py` (≥ 10): 6-dim score, edge cases (zero, all-1, NaN guard)
- `tests/test_r85_double_confirmation.py` (≥ 6): 3 branches of `should_persist`
- `tests/test_r85_memory_tool_channel.py` (≥ 15): 3 drivers + intent parser + quota + L18 gate
- `tests/test_r85_soft_delete.py` (≥ 5): audit trail, GC stub, fail-closed
- `tests/test_r85_runtime_integration.py` (≥ 4): assemble_runtime auto-registration, smoke

### 9.2 Integration tests

- 1-minute real LLM run with R85: at least 1 tool call dispatched
- 5-tick real LLM run: at least 1 L4 record with `double_confirmation_class` populated
- Real LLM forget with L18 denial: tool call returns `MemoryToolGovernanceError`

### 9.3 Performance

- `objective_importance` < 5ms per call
- `MemoryToolChannelDriver.drain_inbound` < 50ms for default quota
- `read_memory_records_by_layer` < 10ms for 1000 records (in-memory backend)

### 9.4 Backward compat

- All 987 R84 tests still pass
- R84 `MemoryProbe` still works (reads via `read_recent` interface)
- R84 A3 score still reproducible within ±0.05
