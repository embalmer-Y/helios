# Requirement 70 - Prompt-to-Thought Real-State Bridge — Task

## 1. Task Breakdown

### Task A: Implement `SemanticEmbodiedPromptRequestBridge` and projection helpers

**Scope**: Add the semantic prompt bridge class and all private projection helpers to `bridges.py`.
**Dependency**: None (additive, no existing code affected until Task C wires it).
**Touched modules**:
- `helios_v2/src/helios_v2/composition/bridges.py` — new class + helpers.

**Completion definition**:
- `SemanticEmbodiedPromptRequestBridge` is defined in `bridges.py`, conforms to
  `EmbodiedPromptRequestProvider` protocol.
- `_present_field_text`, `_affective_summary_text`, `_continuation_summary_text`,
  `_retrieval_context_text`, `_continuity_context_text` helpers defined and tested.
- All helpers use `_require_stage_result` to read from frame.
- Deterministic text output for known input values.
- Focused unit tests pass: `pytest helios_v2/tests/ -x -k "semantic_embodied_prompt"`.

**Validation step**:
```
pytest helios_v2/tests/ -x -k "semantic_prompt_bridge"
```

### Task B: Implement `SemanticInternalThoughtRequestBridge` and `_internal_state_text`

**Scope**: Add the semantic thought bridge class and its projection helper to `bridges.py`.
**Dependency**: None (additive, parallel with Task A).
**Touched modules**:
- `helios_v2/src/helios_v2/composition/bridges.py` — new class + helper.

**Completion definition**:
- `SemanticInternalThoughtRequestBridge` defined in `bridges.py`, conforms to
  `InternalThoughtRequestProvider` protocol.
- `_internal_state_text(frame)` reads `03`/`04`/`05` and projects combined state.
- Focused unit tests pass.

**Validation step**:
```
pytest helios_v2/tests/ -x -k "semantic_thought_bridge"
```

### Task C: Wire bridges in `assemble_runtime`

**Scope**: Update `runtime_assembly.py` to use ternary wiring for prompt and thought bridges.
**Dependency**: Task A (embodied bridge exists), Task B (thought bridge exists).
**Touched modules**:
- `helios_v2/src/helios_v2/composition/runtime_assembly.py` — ternary wiring + import.

**Completion definition**:
- `EmbodiedPromptRuntimeStage.request_provider` uses `SemanticEmbodiedPromptRequestBridge()`
  when `semantic_memory_enabled == True`, else `FirstVersionEmbodiedPromptRequestBridge()`.
- `InternalThoughtRuntimeStage.request_provider` uses `SemanticInternalThoughtRequestBridge()`
  when `semantic_memory_enabled == True`, else `FirstVersionInternalThoughtRequestBridge()`.
- Default assembly (`assemble_runtime()`) produces semantic bridges.
- Legacy assembly produces `FirstVersion*Bridge` (byte-for-byte unchanged).
- Integration test: `pytest helios_v2/tests/ -x -k "semantic_bridge_wiring"`.

**Validation step**:
```
pytest helios_v2/tests/ -x -k "runtime_composition"
```

### Task D: Migrate existing tests

**Scope**: Update tests that assert on constant summary text under the default (now semantic)
assembly.
**Dependency**: Task C (wiring active).
**Touched modules**:
- `helios_v2/tests/test_runtime_composition.py` — tests asserting on constant summary text.
- `helios_v2/tests/test_runtime_stage_chain.py` — tests constructing prompt/thought stages.
- Any other test file that calls `assemble_runtime()` and asserts on constant prompt/thought
  summary text.

**Completion definition**:
- Tests that need legacy behavior explicitly declare `default_signal_mode="legacy_constant"`.
- Tests that should validate real-state behavior update assertions to check for
  dimension/value-based text (not exact constant strings).
- Full suite passes: `pytest helios_v2/tests/ -x`.

**Validation step**:
```
pytest helios_v2/tests/ -x
```

### Task E: Add integration tests

**Scope**: Integration tests validating that varying stimuli produce varying prompt/thought
summary text under the semantic assembly.
**Dependency**: Task C (wiring active).
**Touched modules**:
- `helios_v2/tests/test_runtime_composition.py` — new test class.

**Completion definition**:
- Test creates `assemble_runtime()` with no arguments.
- Runs two ticks with different stimuli.
- Asserts `stimulus_summary["present_field"]` contains text derived from real `02` content.
- Asserts `state_summary["affective_summary"]` contains real `05` feeling dimension names.
- Asserts `InternalThoughtRequest.internal_state_summary` contains real neuromodulator/feeling
  dimension names.
- Asserts varying stimuli produce measurably different summary text.

**Validation step**:
```
pytest helios_v2/tests/ -x -k "prompt_real_state"
```

### Task F: Update documentation

**Scope**: Sync all living documents with R70.
**Dependency**: Task D (full suite green), Task E (integration tests green).
**Touched modules**:
- `helios_v2/docs/requirements/index.md` — add R70 row.
- `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` — update sync line + bridge status.
- `helios_v2/docs/PROGRESS_FLOW.en.md` — update sync line + bridge status.
- `helios_v2/docs/PHASE_METRICS.md` — update P1 metrics (prompt-to-LLM gap closed).

**Completion definition**:
- `index.md` contains R70 row with `baseline_implementation` maturity.
- Both progress flow maps reference R70 in their sync line.
- `PHASE_METRICS.md` notes the prompt-to-LLM shim gap is closed under R70.

**Validation step**: visual inspection; no automated check.

## 2. Dependencies

```
Task A (embodied bridge) ──┐
                            ├─> Task C (wiring) ─> Task D (test migration)
Task B (thought bridge) ──┘                              │
                                                          ├─> Task F (docs)
                              Task E (integration) ─────┘
```

Tasks A and B are independent and may be done in parallel.
Task C depends on both A and B.
Tasks D and E depend on C and may be done in parallel.
Task F depends on D (full suite green) and E.

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/src/helios_v2/composition/bridges.py` | Add classes + helpers | `SemanticEmbodiedPromptRequestBridge`, `SemanticInternalThoughtRequestBridge`, projection helpers |
| `helios_v2/src/helios_v2/composition/runtime_assembly.py` | Modify | Ternary wiring for prompt/thought bridges |
| `helios_v2/tests/test_composition_bridges.py` | Add tests | Bridge unit tests (or in `test_runtime_composition.py`) |
| `helios_v2/tests/test_runtime_composition.py` | Modify + add | Migrate legacy tests + add semantic bridge tests |
| `helios_v2/tests/test_runtime_stage_chain.py` | Modify | Migrate tests asserting on constant summaries |
| `helios_v2/docs/requirements/index.md` | Add row | R70 entry |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` | Update sync line | R70 reference |
| `helios_v2/docs/PROGRESS_FLOW.en.md` | Update sync line | R70 reference |
| `helios_v2/docs/PHASE_METRICS.md` | Update metrics | P1 prompt-to-LLM gap |

## 4. Implementation Order

1. Task A: `SemanticEmbodiedPromptRequestBridge` + helpers (no dependencies).
2. Task B: `SemanticInternalThoughtRequestBridge` + `_internal_state_text` (no dependencies).
3. Task C: Assembly wiring (depends on A + B; breaking change).
4. Task D: Test migration (depends on C; restores full suite green).
5. Task E: Integration tests (depends on C; validates new behavior).
6. Task F: Documentation (depends on D + E).

## 5. Validation Plan

After each task:

| Task | Validation command |
|------|-------------------|
| A | `pytest helios_v2/tests/ -x -k "semantic_prompt_bridge"` |
| B | `pytest helios_v2/tests/ -x -k "semantic_thought_bridge"` |
| C | `pytest helios_v2/tests/ -x -k "runtime_composition"` |
| D | `pytest helios_v2/tests/ -x` |
| E | `pytest helios_v2/tests/ -x -k "prompt_real_state"` |
| F | Visual inspection of updated documents |

Final validation: `pytest helios_v2/tests/ -x` (full suite green).

## 6. Completion Criteria

1. `SemanticEmbodiedPromptRequestBridge` and `SemanticInternalThoughtRequestBridge` are
   shipped in `composition/bridges.py` with projection helpers.
2. `assemble_runtime()` (default semantic) uses semantic bridges; `legacy_constant` uses
   `FirstVersion*Bridge` byte-for-byte identical to pre-R70.
3. Default assembly's `EmbodiedPromptRequest` summaries contain text derived from real
   `02`/`05`/`09`/`10` owner state (not constant strings).
4. Default assembly's `InternalThoughtRequest.internal_state_summary` contains text derived
   from real `03`/`04`/`05` owner state (not "runtime state summary").
5. All existing tests pass after migration.
6. Integration tests validate varying stimuli produce varying summary text.
7. Composition owner-boundary guard still passes.
8. All living documents are updated to reference R70.
9. `requirements/index.md` contains the R70 row with correct maturity.