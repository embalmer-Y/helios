# R85: Dual-Track Memory Architecture (Time-Stratified Layers + Objective Importance Override + Memory Tool Channel)

**Status:** draft
**Owner:** 06 memory (MemoryRecord), 33 persistence (objective_importance + double confirmation), 15 experience_writeback (decay + consolidation), 31 memory_tool_channel (NEW owner, mandatory driver)
**Depends on:** R84 (P5 Memory-Fidelity Probe), R10 (directed retrieval), R15 (experience writeback), R79-D framework, R82 (drift evaluator), owner 30 (channel subsystem)
**Target maturity:** baseline_implementation

---

## 1. Background

R84 closed the measurement gap (A3 from stub 0.5 to real 0.746) but **uncovered 3 fundamental memory architecture problems** that 3 experiments (2026-06-12) confirmed:

1. **LLM subjective memory decision is unstable** (experiment 1): 6/8 states stable across 5 runs, 2/8 (`challenge`/`surprise`) drift with variance 0.20-0.30
2. **LLM "do not remember" judgment is 100% unreliable** (experiment 2): 3/3 cases (`praise`/`neglect`/`surprise`) where LLM said "do not remember" in the moment all reversed to "should remember" in hindsight
3. **LLM "remember" judgment is too lenient** (experiment 3): Precision 42.86%, Recall 100%, F1 60% — LLM exhibits "remember-everything-just-in-case" bias

The current memory architecture has **8 fundamental gaps** identified in the pre-research (`docs/research/memory_redesign/04_helios_current_state.md`):

| Gap | Severity | Evidence |
|---|---|---|
| Single store, no time stratification | High | 4-tier naming exists, implementation is recency-uniform |
| No time decay (Ebbinghaus) | High | store grows forever; no forgetting |
| LLM-dominated decision, no objective override | Critical | experiment 2: 100% miss rate |
| No reconsolidation on recall | Medium | recall does not rewrite the record |
| No active forgetting | Medium | no L18 forget mechanism |
| No LLM active management tools | High | LLM cannot `recall()` / `forget()` / `consolidate()` |
| No reflection cycle | High | no DMN simulation |
| No sleep consolidation | High | no background job |

The current owner 30 channel subsystem provides a **mature driver abstraction** (8 lifecycle ops, QoS taxonomy, readiness probes). Black 决定: **memory tool calls = a mandatory driver**, not a plugin. The driver is a system dependency.

---

## 2. Goal

Implement the **dual-track memory architecture** in two parallel tracks:

**Track A (Infrastructure, this requirement's primary deliverable):**
1. **A.1** Stratify the persistence layer into 4 explicit time layers (L2 working / L3 short / L4 long / L5 autobiographical)
2. **A.2** Add an **objective_importance function** that computes a 6-dimensional score independent of LLM judgment
3. **A.3** Add **double-confirmation write rule**: a record enters L4 iff `llm_remember OR objective_score >= 0.5`, with an AND-fallback to "persist_low_priority" for `0.2 <= objective_score < 0.5 AND llm_remember`
4. **A.4** Add **Ebbinghaus-style decay** (5% per day, recall-rebound)
5. **A.5** Add **reconsolidation on recall** (rewrite notes, bump priority)
6. **A.6** Add **soft-delete + 7-day GC + permanent audit trail** for the forget path

**Track B (LLM active management, secondary deliverable):**
1. **B.1** New owner **31 `memory_tool_channel`** = a **mandatory driver** under owner 30 channel subsystem
2. **B.2** Expose 5 LLM-callable tools: `recall()` / `consolidate()` / `forget()` / `link()` / `reflect()` via natural-language intent parsing
3. **B.3** Driver implements owner 30 `ChannelDriver` Protocol (8 ops)
4. **B.4** Per-tick tool-call quota (default 3) + per-tick recall quota (default 5)
5. **B.5** L18 governance check on `forget()` before soft-delete is committed

This requirement (R85) ships **Track A in full + Track B skeleton with `recall()` + `consolidate()` + `forget()` tools working end-to-end**. `link()` + `reflect()` are deferred to R87.

---

## 3. Functional Requirements

### 3.1 Track A: MemoryRecord schema upgrade

The `PersistedExperienceRecord` in `src/helios_v2/persistence/contracts.py` must be **superseded** (not deleted — for backward compat) by a new `MemoryRecord`:

```python
@dataclass(frozen=True)
class MemoryRecord:
    # Legacy fields (preserved)
    record_id: str
    tick_id: int
    continuity_kind: str
    outcome_class: str
    summary: str

    # New Track A fields
    layer: Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]
    objective_importance: float         # 6-dim score, [0.0, 1.0]
    llm_remember_decision: bool        # LLM's subjective call (frozen at write time)
    double_confirmation_class: Literal["persist_full", "persist_low_priority", "skip"]
    hormone_snapshot: Mapping[str, float]   # 9 fields at write time
    feeling_snapshot: Mapping[str, float]   # 7 fields at write time

    # Time dimension
    created_at_tick: int
    created_at_wall: float
    last_recall_at_wall: float | None
    recall_count: int
    is_consolidated: bool
    soft_deleted_at: float | None
    memory_gc_after: float | None      # soft_delete_at + 7 days
    audit_trail: tuple[Mapping[str, str], ...]   # permanent, never GCed

    # Self-description (A-MEM style)
    tags: tuple[str, ...]
    context_keywords: tuple[str, ...]
    cross_links: tuple[str, ...]       # links to other record_ids
```

The legacy `PersistedExperienceRecord` is migrated via `_migrate_persisted_to_memory_v2()` one-shot helper (analogous to R81 v3→v4).

### 3.2 Track A: objective_importance function

A new `objective_importance(stimulus, llm_output, hormone_state, feeling_state, outcome_class) -> float` function in `src/helios_v2/memory/contracts.py` must compute:

```
objective_importance = min(1.0, max(0.0,
    0.25 * stimulus_intensity(stimulus)
  + 0.20 * hormone_state.cortisol
  + 0.15 * feeling_state.arousal
  + 0.15 * outcome_class_weight(outcome_class)
  + 0.15 * novelty(stimulus, recent_records)
  + 0.10 * (1.0 - feeling_state.social_safety)
))
```

`outcome_class_weight` table (per R83 `ContinuityOutcomeClass` taxonomy):
| outcome | weight |
|---|---|
| `self_changed` | 0.95 |
| `world_blocked` | 0.80 |
| `world_changed` | 0.60 |
| `world_failed` | 0.50 |
| `self_blocked` | 0.40 |
| `internal_only` | 0.20 |

`novelty(stimulus, recent_records)` must use embedding cosine distance to the last 20 records (or recency proxy if embedding gateway unavailable).

### 3.3 Track A: double-confirmation write rule

In `FirstVersionExperienceWritebackPath.write`, add:

```python
def should_persist(llm_remember: bool, objective_score: float) -> str:
    if llm_remember or objective_score >= 0.5:
        return "persist_full"
    if llm_remember and 0.2 <= objective_score < 0.5:
        return "persist_low_priority"
    return "skip"
```

The `double_confirmation_class` field on the record reflects this decision. `persist_full` records enter L4; `persist_low_priority` enter L3 (subject to decay); `skip` records are NOT written.

### 3.4 Track A: time decay + reconsolidation

In `MemoryRecord` queries (R10 retrieval), apply:

```python
def effective_priority(record, current_wall: float) -> float:
    if record.is_consolidated:
        return record.objective_importance  # no decay for consolidated
    days_since_creation = (current_wall - record.created_at_wall) / 86400.0
    days_since_recall = (
        (current_wall - record.last_recall_at_wall) / 86400.0
        if record.last_recall_at_wall else days_since_creation
    )
    decay = 0.95 ** days_since_creation
    rebound = 1.0 + 0.1 / max(days_since_recall, 1.0)
    return min(1.0, record.objective_importance * decay * rebound)
```

In `R10 DirectedRetrievalPath.plan_and_select`, on every probe hit:
1. Bump `recall_count` by 1
2. Set `last_recall_at_wall = now()`
3. If `recall_count >= 2 AND !is_consolidated`, mark `is_consolidated = True` (synaptic tagging heuristic)

### 3.5 Track A: soft-delete + audit trail

`MemoryRecord` supports `soft_delete(reason: str, llm_justification: str, audit_record: Mapping) -> None`:
- Sets `soft_deleted_at = now()`
- Sets `memory_gc_after = now() + 7 * 86400`
- Appends `(at, reason, justification, audit)` to `audit_trail`
- **Never** physically removes the record
- A `MemoryGCJob` (deferred to R88) sweeps records with `memory_gc_after <= now()`

`audit_trail` is **permanent** (never GCed, even after soft-delete + GC). It is stored in a separate `audit_log` table (R88 implements the table; R85 stores in record itself for prototype).

### 3.6 Track B: owner 31 memory_tool_channel

New owner module `src/helios_v2/memory_tool_channel/` (sibling of `channel/`):
- `contracts.py` — `MemoryToolCall`, `MemoryToolResult`, `MemoryToolChannelConfig`, `MemoryToolChannelAPI`
- `engine.py` — `MemoryToolChannelDriver` implementing owner 30 `ChannelDriver` Protocol
- `__init__.py` — public exports
- `drivers/` — subdirectory with concrete drivers (R85 ships `RecallDriver`, `ConsolidateDriver`, `ForgetDriver`; R87 adds `LinkDriver`, `ReflectDriver`)

Mandatory driver design:
- `MemoryToolChannelDriver` is **always registered** in `assemble_runtime` (cannot be `None` or off)
- Implements all 8 owner 30 `ChannelDriver` ops: `driver_id`, `descriptor`, `apply_management_op`, `status`, `config_snapshot`, `drain_inbound`, `send_outbound`, `static_readiness`
- `driver_id` is stable: `"memory_tool_channel"`
- `descriptor` reports: 3 sub-drivers (`recall`/`consolidate`/`forget`), QoS class `high` for `forget`, `medium` for `consolidate`, `low` for `recall`

### 3.7 Track B: 5 LLM-callable tools (R85 ships 3)

R85 implements 3 of the 5 tools end-to-end:

| Tool | Driver | Priority | L18 gate |
|---|---|---|---|
| `recall(query)` | `RecallDriver` | low | no |
| `consolidate(record_id, reflection)` | `ConsolidateDriver` | medium | no |
| `forget(record_id, reason, justification)` | `ForgetDriver` | high | **yes** (mandatory) |

R87 adds `link(from_id, to_id, relation)` and `reflect(theme)`.

### 3.8 Track B: natural-language intent parsing

The v3 prompt (R79-D framework) is extended with a new section:

```
你拥有以下"记忆工具"（用自然语言表达即可，runtime 会解析）：

1. recall(query) — 想主动回忆时
   例："我想起了上次他生气的时候"
2. consolidate(reflection) — 想巩固理解时
   例："我意识到我总是这样被忽视"
3. forget(reason) — 想主动遗忘时
   例："我想忘掉那次尴尬"
   注意：forget 会被审计，治理会检查滥用
```

The runtime post-processor (new `MemoryToolIntentParser` in owner 31) detects tool-call intents in LLM output and constructs `MemoryToolCall` records, which are dispatched via the channel subsystem.

### 3.9 Track B: per-tick quotas

- `max_tool_calls_per_tick = 3` (default; configurable in `MemoryToolChannelConfig`)
- `max_recall_per_tick = 5`
- If a tick exceeds quota, remaining calls are queued for the next tick
- `drain_inbound` enforces quota; excess tool results are deferred

### 3.10 Track B: L18 governance on forget

`ForgetDriver.send_outbound` MUST call `IdentityGovernance.check_forget_permission(record, reason, justification)` before any state change. If the check fails, the tool call is rejected with `MemoryToolGovernanceError` and a structured rejection reason returned to the LLM.

---

## 4. Non-Functional Requirements

1. **Performance**:
   - `objective_importance` must compute in < 5ms (no embedding in hot path; embedding for novelty is cached)
   - `MemoryToolChannelDriver.drain_inbound` must complete in < 50ms for default quota
   - Decay computation is O(1) per record (no DB scan)
2. **Reliability**:
   - Soft-delete must never lose the record (fail-safe: if audit write fails, soft-delete is rolled back)
   - Tool calls fail-soft: if LLM intent parsing fails, the LLM output is processed normally (no tool call dispatched)
3. **Observability**:
   - Each `MemoryRecord` write is logged via the observability owner (no print/import logging)
   - Each tool call is logged with `tool_name`, `latency_ms`, `result_class` (success/reject/error)
4. **Compatibility**:
   - Legacy `PersistedExperienceRecord` continues to work (R84 probe reads legacy fields)
   - `_migrate_persisted_to_memory_v2` runs on read for any record lacking `layer`
   - Default `assemble_runtime` upgrades to `MemoryRecord` automatically

---

## 5. Code Behavior Constraints

1. **R85 must not modify R10 / R15 / R82 / R83 / R84 code paths** — R85 *adds* to them, never edits their first-version behavior
2. **Owner 31 is mandatory** — `assemble_runtime` always registers the `MemoryToolChannelDriver`. It cannot be `None` (fail-fast if registration fails)
3. **No print() / import logging** — R21 compliance
4. **L18 governance is mandatory on forget** — `ForgetDriver` cannot be bypassed
5. **Decay is server-time-based** — uses `time.time()` not `tick_id`; tick-based decay is a future extension
6. **Soft-delete is forever** — even after GC, the record's `audit_trail` MUST be preserved (in a separate audit table, R88)
7. **Tool calls do not change the LLM context directly** — they go through the channel subsystem and are injected in the next tick as inbound packets
8. **Quota enforcement is at the driver layer, not at the LLM layer** — even if LLM outputs 10 tool calls, only 3 are dispatched per tick

---

## 6. Impacted Modules

### 6.1 New modules

| Module | Purpose |
|---|---|
| `src/helios_v2/memory_tool_channel/__init__.py` | Owner 31 public exports |
| `src/helios_v2/memory_tool_channel/contracts.py` | `MemoryToolCall`, `MemoryToolResult`, `MemoryToolChannelConfig`, `MemoryToolChannelAPI` |
| `src/helios_v2/memory_tool_channel/engine.py` | `MemoryToolChannelDriver` (implements owner 30 `ChannelDriver` Protocol) |
| `src/helios_v2/memory_tool_channel/intent_parser.py` | `MemoryToolIntentParser` (LLM output → tool calls) |
| `src/helios_v2/memory_tool_channel/drivers/__init__.py` | Sub-drivers |
| `src/helios_v2/memory_tool_channel/drivers/recall.py` | `RecallDriver` |
| `src/helios_v2/memory_tool_channel/drivers/consolidate.py` | `ConsolidateDriver` |
| `src/helios_v2/memory_tool_channel/drivers/forget.py` | `ForgetDriver` |

### 6.2 Modified modules

| Module | Change |
|---|---|
| `src/helios_v2/memory/contracts.py` | Add `MemoryRecord` + `objective_importance` |
| `src/helios_v2/memory/engine.py` | Add `objective_importance` implementation |
| `src/helios_v2/persistence/contracts.py` | Re-export `MemoryRecord` (alias of `PersistedExperienceRecord` for v1 compat) |
| `src/helios_v2/persistence/engine.py` | Add `append_memory_record`, `read_memory_records_by_layer`, `_migrate_persisted_to_memory_v2` |
| `src/helios_v2/experience_writeback/contracts.py` | Add `double_confirmation_class` to `ExperienceWritebackRequest` |
| `src/helios_v2/experience_writeback/engine.py` | Add double-confirmation logic in `FirstVersionExperienceWritebackPath.write` |
| `src/helios_v2/directed_retrieval/engine.py` | Add reconsolidation hook in `plan_and_select` |
| `src/helios_v2/runtime_assembly.py` | Register `MemoryToolChannelDriver` (mandatory); wire `MemoryRecord` to `experience_store` |
| `src/helios_v2/composition/bridges.py` | Bridge `MemoryToolChannelDriver` to v3 prompt renderer |
| `src/helios_v2/tests/r79d/framework.py` | Extend v3 prompt with tool-call instructions (R79-D compat) |
| `src/helios_v2/identity_governance/contracts.py` | Add `check_forget_permission` |
| `src/helios_v2/identity_governance/engine.py` | Implement `check_forget_permission` (fail-closed default) |

### 6.3 New test modules

| Module | Tests |
|---|---|
| `tests/test_r85_memory_record.py` | ≥8 tests (schema, migration, decay) |
| `tests/test_r85_objective_importance.py` | ≥10 tests (6-dim score, edge cases) |
| `tests/test_r85_double_confirmation.py` | ≥6 tests (3 branches of `should_persist`) |
| `tests/test_r85_memory_tool_channel.py` | ≥15 tests (3 drivers + intent parser + quota + L18 gate) |
| `tests/test_r85_soft_delete.py` | ≥5 tests (audit trail, GC stub) |
| `tests/test_r85_runtime_integration.py` | ≥4 tests (assemble_runtime auto-registration, smoke) |

### 6.4 Documentation

| Doc | Change |
|---|---|
| `docs/OWNER_GUIDE.md` | §3.8.6 R85 new section + status header R84 → R85 |
| `docs/ARCHITECTURE_BOUNDARIES.md` | §10.g R85 new section + status header |
| `docs/PROGRESS_FLOW.en.md` | R85 索引块 + status R85 |
| `docs/PROGRESS_FLOW.zh-CN.md` | R85 索引块 + status R85 |
| `docs/requirements/index.md` | Append R85 row |
| `docs/research/memory_redesign/` | 6 files already exist from pre-research (R85-pre-research commit `382d2e8`) |

---

## 7. Acceptance Criteria

1. **Code**: All 13 new modules in owner 31 exist; `MemoryRecord` schema is complete; `objective_importance` is implemented
2. **Tests**: `pytest tests/` returns **≥ 1035 passed** (987 R84 baseline + ≥ 48 R85 new). 0 regressions.
3. **Track A smoke**: a 1-tick real LLM run shows `double_confirmation_class` populated and `objective_importance ∈ [0.0, 1.0]`
4. **Track A double-confirmation**: 100% of `should_persist` unit tests pass (3 branches: `persist_full` / `persist_low_priority` / `skip`)
5. **Track A decay**: a 1-day-old record has `effective_priority < objective_importance`; a just-recalled record has `effective_priority ≈ objective_importance`
6. **Track A soft-delete**: a soft-deleted record has `soft_deleted_at != None`; `audit_trail` is non-empty; record is not physically removed
7. **Track B mandatory driver**: `assemble_runtime` always registers `MemoryToolChannelDriver`; runtime without owner 31 fails-fast
8. **Track B driver protocol**: `MemoryToolChannelDriver` passes the owner 30 driver readiness check
9. **Track B tool dispatch**: LLM output `"我想起了上次他生气的时候"` triggers a `MemoryToolCall(tool_name="recall", query="上次他生气的时候")` which is dispatched to `RecallDriver`
10. **Track B L18 gate**: LLM calling `forget` for a protected record (e.g. `record_id` flagged by L18 as `non-forgettable`) returns `MemoryToolGovernanceError` and **does not** soft-delete
11. **Track B quota**: a tick with 5 tool calls dispatches only 3; remaining 2 are deferred to next tick
12. **Real LLM end-to-end**: a 1-minute real LLM run with R85-enabled runtime shows ≥1 tool call dispatched (recall or consolidate) and ≥1 L4 record with `double_confirmation_class` populated
13. **P5 launch gate unchanged**: R82 drift evaluator still passes
14. **R21 ad-hoc logging guard**: 1/1 green
15. **Composition owner-boundary guard**: 158/158 green
