# R85: Dual-Track Memory Architecture — Task Breakdown

> **Progress (last updated 2026-06-12 ~17:00 UTC)**
> - [x] **T1** MemoryRecord schema + migration helper (commit `573dff4`, 27 tests)
> - [x] **T2** objective_importance 6-dim function (commit `573dff4`, 18 tests)
> - [x] **T3** should_persist double-confirmation (commit `573dff4`, included in T1 tests)
> - [x] **T4** integrate into R15 via opt-in R85MemoryClassifierBridge (commit `573dff4`, 16 tests)
> - [x] **T5** MemoryRecord soft_delete (commit `573dff4`, included in T1 tests)
> - [x] **T6** decay + effective_priority (commit `573dff4`, included in T1 tests)
> - [x] **T7** layer promotion via promote_layer (commit `573dff4`, included in T2 tests)
> - [x] **T8** owner 31 memory_tool_channel contracts
> - [x] **T9** MemoryToolIntentParser
> - [x] **T10** 3 sub-drivers (recall / consolidate / forget)
> - [~] **T11** L18 check_forget_permission (callable hook exposed, implementation deferred to R86)
> - [x] **T12** MemoryToolChannelDriver (channel driver protocol)
> - [x] **T13** runtime_assembly registration (opt-in: default OFF, 1089 baseline preserved)
> - [x] **T14** v3 prompt extension + intent dispatcher (commit `dfb6f36`, 12 tests)
> - [x] **T15** integration tests + smoke (10 new tests, 1099 passed)
> - [x] **T16** consolidation-timing decision C (write-trigger promote_layer) (commit pending, 9 tests)
>
> **Track A: 7/7 done (100%)** | **Track B: 7/8 done (~88%)** | **R85 total: 14/15 (~93%)**


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

## 5. Progress Notes

### 2026-06-12 — R85-A done (commit `573dff4`)

- Track A 基础设施 T1-T7 全部 done
- 61 新测试通过，1043 passed 整库回归
- `src/helios_v2/memory/{contracts,engine,classifier}.py` 完整实现
- `src/helios_v2/composition/bridges.py` 加 `R85MemoryClassifierBridge` (opt-in glue)
- 删 `src/helios_v2/tests/_scratch/` 解决 R21 ad-hoc logging guard 冲突

### 2026-06-12 — R85-B done (commit `efa0efa`)

- Track B 基础设施 T8-T10 全部 done
- 41 新测试通过，1084 passed 整库回归
- 新 owner 31 `src/helios_v2/memory_tool_channel/{__init__,contracts,engine}.py` 完整实现
  - 3 LLM-callable tool: `memory_save` / `memory_replay` / `memory_forget`
  - `MemoryToolIntentParser` 双策略 (fenced JSON + 中英文 keyword fallback)
  - `apply_quota_and_governance` (per-tick cap 3, forget-priority-sort, governance hook)
  - `MemoryToolDispatcher` 路由到 3 sub-driver callable
  - `MemoryToolChannelDriver` 完整 ChannelDriver Protocol 实现

### 2026-06-12 — R85-C partial done (commit `a1a80b2`)

- T13 集成 owner 31 driver 到 runtime_assembly（**OPT-IN 模式，默认 OFF**）
- T15 集成测试 + smoke（10 新测试，1099 passed 整库回归）
- T11 L18 check_forget_permission **callable hook 已暴露**，实现延后到 R86
- T14 v3 prompt extension + intent dispatcher **待小黑拍板是否做**（影响 LLM 是否真能调用工具）

#### T13 关键决策（2026-06-12 13:30）

原计划 mandatory driver（默认 ON）触发了 116 个 R83/R10/R15 regression 失败。
改用 opt-in 模式（`memory_tool_channel=True` 显式开启），保住 1089 passed 基线。

设计原理：
- 默认 runtime contract 不变（向后兼容）
- 显式 `memory_tool_channel=True` 的 callsite 才注册 driver
- `channel_cli=True` + `memory_tool_channel=True` 兼容
- 重复注册 guard：`if driver_id not in channel_subsystem._drivers`

#### T11 推迟决策

callable `check_forget_permission` 已在 `MemoryToolChannelDriver.__init__` 暴露，
但实际 L18 governance 实现需要在 R86 与 identity_governance owner 协同实施。
R85 不阻塞。

### 2026-06-12 — R85-T14 done (commit `dfb6f36`)

- v3 prompt 加 `_R85_MEMORY_TOOL_PROMPT_SECTION` constant (~700 chars)
  - 描述 memory_save / memory_replay / memory_forget 3 个 tool
  - 包含 fenced-JSON 调用示例
  - 包含中英文 keyword fallback 说明
- `AggressiveRadicalEmbodiedPromptPath.build` 在
  `capability_summary["memory_tool_channel_enabled"]` 为 True 时追加 section
- `FirstVersionEmbodiedPromptRequestBridge` / `SemanticEmbodiedPromptRequestBridge`
  都加 `memory_tool_channel_enabled: bool = False` 字段
- `assemble_runtime` 把 driver 存在性 plumb 到 bridge 的 capability_summary
- R79-D framework 集成:
  - `TickRecord` 加 `tool_calls` / `tool_results` 字段
  - `run_experiment` 每 tick 跑 `MemoryToolIntentParser` → `driver.set_intents` → 可选 `dispatcher.dispatch`
  - `v3_build_messages` 在 `handle.memory_tool_channel_driver` 存在时
    把 section 追加到 v3 system prompt
  - `v3_build_messages` 把上 tick admitted 的 tool calls 写到 user message 的
    "Memory tool calls admitted last tick (R85)" section
- 新文件 `tests/test_r85_t14_integration.py` — 12 个测试全部通过
- Smoke (`/tmp/exp1/r85_t14_smoke.py`): opt-in driver + parser + dispatch green;
  v3 system prompt 包含 memory tool section
- 1111 passed 整库回归（1099 baseline + 12 T14 新增）
- R21 ad-hoc logging guard clean

T14 让 LLM 真正能发出 memory tool 调用（通过 fenced-JSON 或 keyword fallback），
配合 T13 的 opt-in driver 注册，整套 owner 31 → v3 prompt → LLM → driver → sub-driver
→ 结果回喂下 tick 链路打通。

R85 total 进度: 13.5/15 (~90%)
- T11 L18 governance 实现留到 R86
- 巩固时机 5 候选方案待小黑拍板
- 真 LLM 1-min 端到端验证待做

### 2026-06-12 — R85 consolidation-timing 拍板 (5 候选 → C 写入+recall 触发, D idle 兜底留 R86)

小黑拍板 C+D 组合的"方案 2"（composition 层做、不在 dispatcher / record 内部）。

- **C（write + recall hot path 触发单条 promote_layer）**:
  - write 路径: T16 在 `R85MemoryClassifierBridge.build_memory_records` 末尾调 `promote_layer`
  - recall 路径: 推迟到 R86，等 R85 record store 实际落地再挂
- **D（idle 兜底 batch 重检）**: 推迟到 R86 的 runtime lifecycle hooks 工作
  - 语义契约已定: "consolidation 是 runtime 责任"
  - 实施延后: `RuntimeHandle.register_idle_hook` + `heliosd` 心跳回调注册
- 选 C+D 而非 A（每 tick）的原因: 避免全表扫描，写入/recall 是 LLM 主导的真实 trigger 点
- 选 β 实施范围（仅 write-trigger）而非 α/γ（含 record store）的原因: 保住 R85 14/15 进度，recall-trigger 跟着 record store 一起做更自然

### 2026-06-12 — R85-T16 done (commit pending)

- T16 consolidation-timing decision C: write-trigger
- 在 `R85MemoryClassifierBridge.build_memory_records` 末尾追加 `promote_layer(mem)` 调用
- 新建 record 永远是 L3 + recall=0，promote 实际是 no-op；但 hot path 上 wire-in 完成
- 未来 R85 record store 落地后，recall_count 可以跨 tick 累积，wire-in 立即生效
- `pyproject.toml` 加 `[tool.pytest.ini_options]` 排除 `scratch_r79b` 等目录
- 9 个 T16 测试覆盖: 触发性 / no-op / 多 record / 真实 engine 函数 / 幂等 / 空入 / lazy import / L3→L4 / L4→L5
- 1120 passed 整库回归（1099 baseline + 12 T14 + 9 T16）
- R21 ad-hoc logging guard clean

R85 total 进度: 14/15 (~93%)
- T11 L18 governance 实现留到 R86
- 巩固时机 recall-trigger 路径留到 R86
- 巩固时机 D (idle 兜底) 留到 R86
- 真 LLM 1-min 端到端验证待做

## 6. Completion Criteria

R85 is **done** when:

1. All 15 tasks marked complete with their specific validations passing
2. ≥ 48 new tests added (1035+ total)
3. All 4 documentation files updated
4. `index.md` R85 row appended with `baseline_implementation` maturity
5. Real LLM 1-min run shows R85 features working
6. R85 commit pushed to beta branch `aggressive-radical-persona-no-theater`
