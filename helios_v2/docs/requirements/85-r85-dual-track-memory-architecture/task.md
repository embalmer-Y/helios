# R85: Dual-Track Memory Architecture — Task Breakdown

## 1. Task Breakdown

### Track A: Infrastructure (10 tasks)

#### T1: MemoryRecord schema + migration helper
- **Module**: `src/helios_v2/memory/contracts.py`, `src/helios_v2/persistence/engine.py`
- **Work**:
  - Add `MemoryRecord` dataclass (full schema per design §4.1)
  - Add `_migrate_persisted_to_memory_v2(legacy) -> MemoryRecord` one-shot helper
  - Add `append_memory_record`, `read_memory_records_by_layer` to persistence backend
  - Add unit tests for schema + migration
- **Validation**: `pytest tests/test_r85_memory_record.py` ≥ 8 tests pass
- **Completion**: MemoryRecord can be written + read; legacy records auto-migrate

#### T2: objective_importance function
- **Module**: `src/helios_v2/memory/engine.py`
- **Work**:
  - Implement `objective_importance(stimulus, llm_output, hormone, feeling, outcome_class) -> float`
  - 6-dim weighted sum with clamping
  - `outcome_class_weight` table (6 classes)
  - `_novelty_cosine` helper with embedding fallback
  - Unit tests for all 6 dims + edge cases
- **Validation**: `pytest tests/test_r85_objective_importance.py` ≥ 10 tests pass
- **Completion**: `objective_importance` returns a value in [0.0, 1.0] for all valid inputs

#### T3: should_persist double-confirmation
- **Module**: `src/helios_v2/memory/contracts.py`
- **Work**:
  - Add `should_persist(llm_remember: bool, objective_score: float) -> Literal["persist_full", "persist_low_priority", "skip"]`
  - Unit tests for all 3 branches + boundary values
- **Validation**: `pytest tests/test_r85_double_confirmation.py` ≥ 6 tests pass
- **Completion**: 100% branch coverage

#### T4: integrate should_persist into FirstVersionExperienceWritebackPath
- **Module**: `src/helios_v2/experience_writeback/contracts.py`, `src/helios_v2/experience_writeback/engine.py`
- **Work**:
  - Add `double_confirmation_class` field to `ExperienceWritebackRequest`
  - In `FirstVersionExperienceWritebackPath.write`:
    1. Compute `objective_importance`
    2. Call `should_persist`
    3. Branch on result
  - Update existing tests if needed (legacy path preserved)
- **Validation**: all R15 existing tests pass; new tests for double-confirmation integration
- **Completion**: A real LLM run produces `double_confirmation_class != None` for every record

#### T5: MemoryRecord soft_delete
- **Module**: `src/helios_v2/memory/contracts.py`
- **Work**:
  - Add `soft_delete(reason, justification, audit_record)` method (or function)
  - Audit trail append (frozen tuple, never mutates existing)
  - Unit tests
- **Validation**: `pytest tests/test_r85_soft_delete.py` ≥ 5 tests pass
- **Completion**: soft-deleted record has `soft_deleted_at != None`; `audit_trail` is non-empty; record is not physically removed

#### T6: decay + reconsolidation in R10
- **Module**: `src/helios_v2/directed_retrieval/engine.py`
- **Work**:
  - Add `effective_priority(record, current_wall) -> float` helper
  - In `FirstVersionDirectedRetrievalPath.plan_and_select`:
    1. Apply decay to all candidates before ranking
    2. On hit, bump `recall_count` and `last_recall_at_wall`
    3. If `recall_count >= 2`, mark `is_consolidated = True`
  - Unit tests
- **Validation**: tests show decay < original after 1 day; recall bumps `last_recall_at_wall`
- **Completion**: reconsolidation is automatic on every retrieval

#### T7: layer promotion rules
- **Module**: `src/helios_v2/memory/engine.py`
- **Work**:
  - Add `promote_layer(record) -> MemoryRecord` helper
  - Rules per design §4.4
  - Called when `append_memory_record` is invoked (initial layer = L3_short by default)
  - SleepConsolidationJob is deferred to R88 (initial layer is L3; promotion happens on recall or future sleep job)
- **Validation**: tests show L3 → L4 on `recall_count >= 2`
- **Completion**: layer promotion is correct

### Track B: Memory Tool Channel (8 tasks)

#### T8: owner 31 contracts + config
- **Module**: `src/helios_v2/memory_tool_channel/contracts.py`, `__init__.py`
- **Work**:
  - `MemoryToolCall`, `MemoryToolResult`, `MemoryToolChannelConfig`, `MemoryToolChannelAPI`
  - `MemoryToolError`, `MemoryToolGovernanceError`
  - Public exports
- **Validation**: imports work; tests for dataclass invariants
- **Completion**: contracts are well-defined

#### T9: MemoryToolIntentParser
- **Module**: `src/helios_v2/memory_tool_channel/intent_parser.py`
- **Work**:
  - Regex-based parser for LLM output
  - Detects: "我想起了..." / "我意识到..." / "我想忘掉..." etc.
  - Returns list of `MemoryToolCall`
  - Fail-soft: returns empty list if no intent detected
- **Validation**: tests for ≥ 5 pattern types + non-matching text
- **Completion**: parser correctly identifies tool calls

#### T10: 3 sub-drivers (recall / consolidate / forget)
- **Module**: `src/helios_v2/memory_tool_channel/drivers/{recall,consolidate,forget}.py`
- **Work**:
  - `RecallDriver.execute(call) -> MemoryToolResult`: calls R10 retrieval, returns top-k records
  - `ConsolidateDriver.execute(call) -> MemoryToolResult`: appends reflection to record's `audit_trail`, promotes layer
  - `ForgetDriver.execute(call) -> MemoryToolResult`: L18 check, then `soft_delete`
- **Validation**: tests for each driver
- **Completion**: 3 drivers all working end-to-end

#### T11: L18 check_forget_permission
- **Module**: `src/helios_v2/identity_governance/engine.py`
- **Work**:
  - `check_forget_permission(record, reason, justification) -> GovernanceVerdict`
  - Fail-closed default
  - Allow iff `record.layer != "L5_autobiographical"`
- **Validation**: tests for allow / deny / audit
- **Completion**: L18 gate is functional

#### T12: MemoryToolChannelDriver (mandatory driver)
- **Module**: `src/helios_v2/memory_tool_channel/engine.py`
- **Work**:
  - Implements owner 30 `ChannelDriver` Protocol (8 ops)
  - `drain_inbound` returns tool results (from previous tick)
  - `send_outbound` dispatches a `MemoryToolCall` to the correct sub-driver
  - Quota enforcement in `drain_inbound`
  - Status / readiness / config_snapshot
- **Validation**: protocol conformance tests; quota tests
- **Completion**: driver is fully functional

#### T13: runtime_assembly registration
- **Module**: `src/helios_v2/runtime_assembly.py`
- **Work**:
  - Always register `MemoryToolChannelDriver` in `assemble_runtime`
  - Wire `MemoryRecord` writes to `experience_store`
  - Auto-migration on read
  - Fail-fast if registration fails
- **Validation**: integration tests
- **Completion**: runtime without owner 31 fails-fast

#### T14: v3 prompt extension + intent dispatcher
- **Module**: `src/helios_v2/tests/r79d/framework.py`, `src/helios_v2/composition/bridges.py`
- **Work**:
  - Add "记忆工具说明" section to v3 prompt
  - Add intent dispatcher: LLM output → `MemoryToolIntentParser` → tool calls
  - Inject tool results into next tick's prompt as retrieval context
- **Validation**: real LLM run produces tool calls
- **Completion**: LLM can call recall / consolidate / forget

#### T15: integration tests + smoke
- **Module**: `tests/test_r85_runtime_integration.py`, smoke scripts
- **Work**:
  - 1-tick smoke: register driver + compute objective_importance + double-confirm
  - 5-tick real LLM run: at least 1 tool call dispatched
  - Real LLM forget with L18 denial
- **Validation**: ≥ 4 integration tests pass
- **Completion**: end-to-end flow works

## 2. Dependencies

```
T1 (MemoryRecord) ──┬──> T5 (soft_delete) ──> T11 (L18 check) ──> T10 (forget driver) ──> T12 (driver)
                    │
                    ├──> T2 (objective_importance) ──> T3 (should_persist) ──> T4 (integrate into R15)
                    │                                                              │
                    │                                                              v
                    └──> T6 (decay + reconsolidation) ──> T7 (layer promotion) <────┘
                                                                                    │
                                                                                    v
                                                            T8 (contracts) ──> T9 (intent parser) ──> T10 (drivers) ──> T12 (driver) ──> T13 (runtime) ──> T14 (v3 prompt) ──> T15 (smoke)
```

Track A (T1-T7) and Track B (T8-T15) can be developed in parallel after T1 lands.

## 3. Files and Modules

### 3.1 New files (16 files)

| File | LOC est. |
|---|---|
| `src/helios_v2/memory_tool_channel/__init__.py` | 30 |
| `src/helios_v2/memory_tool_channel/contracts.py` | 200 |
| `src/helios_v2/memory_tool_channel/engine.py` | 300 |
| `src/helios_v2/memory_tool_channel/intent_parser.py` | 150 |
| `src/helios_v2/memory_tool_channel/drivers/__init__.py` | 20 |
| `src/helios_v2/memory_tool_channel/drivers/recall.py` | 100 |
| `src/helios_v2/memory_tool_channel/drivers/consolidate.py` | 80 |
| `src/helios_v2/memory_tool_channel/drivers/forget.py` | 120 |
| `tests/test_r85_memory_record.py` | 250 |
| `tests/test_r85_objective_importance.py` | 300 |
| `tests/test_r85_double_confirmation.py` | 200 |
| `tests/test_r85_memory_tool_channel.py` | 500 |
| `tests/test_r85_soft_delete.py` | 150 |
| `tests/test_r85_runtime_integration.py` | 200 |
| `docs/requirements/85-r85-dual-track-memory-architecture/requirement.md` | (already written) |
| `docs/requirements/85-r85-dual-track-memory-architecture/design.md` | (already written) |

### 3.2 Modified files (10 files)

| File | Change |
|---|---|
| `src/helios_v2/memory/contracts.py` | +MemoryRecord + objective_importance signature |
| `src/helios_v2/memory/engine.py` | +objective_importance impl + promote_layer + effective_priority |
| `src/helios_v2/persistence/engine.py` | +append_memory_record + read_memory_records_by_layer + migration |
| `src/helios_v2/experience_writeback/contracts.py` | +double_confirmation_class field |
| `src/helios_v2/experience_writeback/engine.py` | +should_persist integration |
| `src/helios_v2/directed_retrieval/engine.py` | +reconsolidation hook + decay |
| `src/helios_v2/runtime_assembly.py` | +owner 31 registration + auto-migration |
| `src/helios_v2/composition/bridges.py` | +tool instructions in v3 prompt + tool result injection |
| `src/helios_v2/tests/r79d/framework.py` | +记忆工具说明 in v3 prompt |
| `src/helios_v2/identity_governance/engine.py` | +check_forget_permission |

### 3.3 Documentation sync (4 files)

| File | Change |
|---|---|
| `docs/OWNER_GUIDE.md` | §3.8.6 R85 new section + status R84 → R85 |
| `docs/ARCHITECTURE_BOUNDARIES.md` | §10.g R85 new section + status |
| `docs/PROGRESS_FLOW.en.md` | R85 索引块 + status |
| `docs/PROGRESS_FLOW.zh-CN.md` | R85 索引块 + status |
| `docs/requirements/index.md` | R85 row append |

## 4. Implementation Order

### Phase A (T1-T4): MemoryRecord + objective_importance + double-confirm
1. T1: schema + migration (1 day)
2. T2: objective_importance (0.5 day)
3. T3: should_persist (0.5 day)
4. T4: integrate into R15 (1 day)

### Phase B (T5-T7): soft-delete + decay + reconsolidation + layer promotion
5. T5: soft_delete (0.5 day)
6. T6: decay + reconsolidation in R10 (1 day)
7. T7: layer promotion (0.5 day)

### Phase C (T8-T12): owner 31 contracts + parser + drivers + L18 + main driver
8. T8: contracts + config (0.5 day)
9. T9: intent parser (0.5 day)
10. T10: 3 sub-drivers (1 day)
11. T11: L18 check (0.5 day)
12. T12: main driver (1 day)

### Phase D (T13-T15): runtime + v3 prompt + smoke
13. T13: runtime_assembly (0.5 day)
14. T14: v3 prompt + dispatcher (1 day)
15. T15: integration tests + smoke (0.5 day)

**Total**: ~10 working days for 1 person (or ~5 days for 2 people in parallel on Phase A/B and Phase C)

## 5. Validation Plan

### 5.1 Per-task validation
Each task has a specific validation step (see task entries above).

### 5.2 Cumulative validation at phase boundaries

After Phase A (T1-T4):
- `pytest tests/test_r85_memory_record.py tests/test_r85_objective_importance.py tests/test_r85_double_confirmation.py` ≥ 24 tests pass
- 1-tick real LLM run shows `double_confirmation_class` populated

After Phase B (T5-T7):
- `pytest tests/test_r85_soft_delete.py` ≥ 5 tests pass
- Decay + reconsolidation unit tests pass

After Phase C (T8-T12):
- `pytest tests/test_r85_memory_tool_channel.py` ≥ 15 tests pass
- `MemoryToolChannelDriver` passes owner 30 driver readiness check

After Phase D (T13-T15):
- `pytest tests/test_r85_runtime_integration.py` ≥ 4 tests pass
- 1-minute real LLM run shows ≥ 1 tool call dispatched
- 5-tick real LLM run shows ≥ 1 L4 record with `double_confirmation_class`

### 5.3 Final acceptance

- **1035+ passed** in `pytest tests/` (987 R84 baseline + ≥ 48 R85 new)
- 0 regressions
- R21 ad-hoc logging guard: 1/1 green
- Composition owner-boundary guard: 158/158 green
- R82 P5 launch gate: still passes
- Real LLM 1-min run: ≥ 1 tool call + ≥ 1 L4 record with double_confirm

## 6. Completion Criteria

R85 is **done** when:

1. All 15 tasks marked complete with their specific validations passing
2. ≥ 48 new tests added (1035+ total)
3. All 4 documentation files updated
4. `index.md` R85 row appended with `baseline_implementation` maturity
5. Real LLM 1-min run shows R85 features working
6. R85 commit pushed to beta branch `aggressive-radical-persona-no-theater`
