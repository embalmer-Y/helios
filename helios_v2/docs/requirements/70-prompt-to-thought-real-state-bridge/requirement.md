# Requirement 70 - Prompt-to-Thought Real-State Bridge

## 1. Background and Problem

The Helios v2 cognitive chain (`03`–`10`) has been fully de-shimmed under the semantic-memory
assembly (R35–R65, R69 default). Every owner from rapid salience appraisal through directed
retrieval now consumes real, non-constant signals by default. However, the **two bridges that
feed the LLM thought loop** (`11`) and the prompt-contract owner (`16`) still inject **hardcoded
constant strings** in every assembly, including the default semantic assembly:

1. `FirstVersionEmbodiedPromptRequestBridge` (bridges.py L1824–1893) constructs two
   `EmbodiedPromptRequest` instances whose `stimulus_summary`, `state_summary`, and
   `retrieval_summary` are all **constant English sentences** unrelated to the real `02`–`10`
   owner state present in the tick frame. The LLM receives:
   - `stimulus_summary["present_field"]` = "A cli text stimulus is present..." (constant)
   - `state_summary["affective_summary"]` = "arousal is elevated..." (constant)
   - `state_summary["continuation_summary"]` = "continuation pressure is active..." (constant)
   - `retrieval_summary["retrieval_context"]` = "short-term context..." (constant)
   - `retrieval_summary["continuity_context"]` = "preserve the current user anchor..." (constant)

2. `FirstVersionInternalThoughtRequestBridge` (bridges.py L1897–1933) constructs an
   `InternalThoughtRequest` whose `internal_state_summary` is the **constant string**
   `"runtime state summary"` — the LLM's sole window into the brain's real emotional, feeling,
   neuromodulator, and salience state is a fabricated label.

The downstream prompt-contract engine (`FirstVersionEmbodiedPromptPath`) renders these
summaries into six prompt layers (present_field, embodied_state, memory_and_continuity,
action_autonomy, anti_theatrical_constraints, consumer_orientation). The LLM-backed thought
engine (`LlmBackedInternalThoughtPath._build_messages`) consumes the
`internal_state_summary` directly in its user message. Both are insulated from the real
cognitive state computed in the `03`–`10` chain.

Evidence:

1. `assemble_runtime()` (with no arguments, R69 default = semantic) produces `semantic_memory_enabled == True`, so `03`–`10` produce real signals — but the `16` prompt stage and `11` thought stage still see only constant text.
2. The `NeuromodulatorLevels`, `InteroceptiveFeelingVector`, `RapidSalienceVector`, `ThoughtGateResult`, and `DirectedRetrievalResult` are all present in the frame and contain real computed values. The bridges currently read only the provenance IDs (`state_id`, `result_id`, `bundle_id`) and ignore the content.
3. This violates `ARCHITECTURE_PHILOSOPHY` §4.3 (unacceptable pseudo-completion state #1: "the main path is essentially reply-first, only adding decorative steps before and after the reply") and §5.3 (cognitive-state-guided prompt assembly).

## 2. Goal

Under the semantic-memory assembly, the prompt-to-thought bridges must derive their summary
text from the real `02`–`10` owner state present in the tick frame, so the LLM thought loop
receives an honest, bounded projection of the brain's actual affective state, stimulus field,
and retrieval context instead of constant English sentences. The `FirstVersion*Bridge`
implementations remain available under `default_signal_mode="legacy_constant"` and must
reproduce their current behavior byte-for-byte.

## 3. Functional Requirements

### 3.1 Semantic embodied-prompt request bridge

1. A `SemanticEmbodiedPromptRequestBridge` must be shipped in `composition/bridges.py`,
   conforming to the existing `EmbodiedPromptRequestProvider` protocol.
2. Under the semantic-memory assembly, `stimulus_summary["present_field"]` must derive from
   the real `02` sensory batch: the external-stimulus content when present, or an honest
   "no external stimulus" marker when absent. The bridge must not fabricate stimulus content.
3. Under the semantic-memory assembly, `state_summary["affective_summary"]` must derive from
   the real `05` `InteroceptiveFeelingVector`: a bounded English projection of the dominant
   feeling dimensions (arousal, valence, tension, etc.) with their real `[0,1]` values. The
   bridge must not fabricate emotional states.
4. Under the semantic-memory assembly, `state_summary["continuation_summary"]` must derive
   from the real `09` `ThoughtGateResult` and `ContinuationPressureState`: whether
   continuation pressure is active and what contributed to the gate decision.
5. Under the semantic-memory assembly, `retrieval_summary["retrieval_context"]` must derive
   from the real `10` directed-retrieval result: whether short-term context, mid-term hits,
   and autobiographical anchors are present.
6. Under the semantic-memory assembly, `retrieval_summary["continuity_context"]` must derive
   from the real `10` retrieval bundle's content summary when present, or an honest "no
   active continuity trace" marker when absent.
7. The bridge must preserve the provenance IDs (`source_conscious_state_id`,
   `source_gate_result_id`, `source_retrieval_bundle_id`) and the `capability_summary` /
   `identity_boundary_summary` unchanged from the `FirstVersionEmbodiedPromptRequestBridge`
   (these are composition-level constants not derived from owner state).
8. When any required stage result is missing from the frame (wrong assembly order or
   structural error), the bridge must raise `RuntimeStageExecutionError` rather than silently
   falling back to a constant.

### 3.2 Semantic internal-thought request bridge

1. A `SemanticInternalThoughtRequestBridge` must be shipped in `composition/bridges.py`,
   conforming to the existing `InternalThoughtRequestProvider` protocol.
2. Under the semantic-memory assembly, `internal_state_summary` must derive from the real
   `04` `NeuromodulatorLevels`, `05` `InteroceptiveFeelingVector`, and `03`
   `RapidSalienceVector`: a bounded English projection of the current neuromodulator
   levels, felt body-state, and salience landscape. The bridge must not fabricate state.
3. The bridge must preserve `source_gate_result_id`, `source_retrieval_bundle_id`,
   `source_continuation_active`, and `prompt_contract_summary` unchanged from
   `FirstVersionInternalThoughtRequestBridge`.

### 3.3 Assembly wiring

1. In `assemble_runtime`, the `EmbodiedPromptRuntimeStage.request_provider` must use
   `SemanticEmbodiedPromptRequestBridge()` when `semantic_memory_enabled == True` and
   `FirstVersionEmbodiedPromptRequestBridge()` when `False`.
2. In `assemble_runtime`, the `InternalThoughtRuntimeStage.request_provider` must use
   `SemanticInternalThoughtRequestBridge()` when `semantic_memory_enabled == True` and
   `FirstVersionInternalThoughtRequestBridge()` when `False`.
3. The wiring must follow the established pattern (ternary `if semantic_memory_enabled
   else ...`) used for all other de-shim bridges (`03`, `04`, `05`, `06`, `07`, `08`, `09`).

### 3.4 Owner-neutral bridge constraints

1. The bridges must only read bounded raw facts from published stage results and project them
   into English text. The bridges must not compute policy, scoring, or threshold values.
2. The bridges must not import any cognitive owner (`appraisal`, `neuromodulation`,
   `feeling`, `consciousness`, `thought_gating`, `directed_retrieval`). They must read only
   the published contract types already present in the frame.
3. The text projection must be deterministic for a given set of input values. No randomness,
   no model calls, no network access.

## 4. Non-Functional Requirements

1. **Performance**: the text projection must complete in under 1 ms per call. No model or
   network access.
2. **Reliability**: the bridges must never fabricate a state that was not computed by the
   upstream owners. Missing required stage results are a hard stop.
3. **Observability**: no new logging mechanism. The existing `21` observability owner and
   kernel instrumentation are unchanged.
4. **Compatibility**: `FirstVersion*Bridge` behavior under `default_signal_mode="legacy_constant"`
   must be byte-for-byte identical to the pre-R70 default. No contract shape change to
   `EmbodiedPromptRequest` or `InternalThoughtRequest`.

## 5. Code Behavior Constraints

1. `SemanticEmbodiedPromptRequestBridge` and `SemanticInternalThoughtRequestBridge` must
   live in `composition/bridges.py` and conform to the existing provider protocols. They
   must not be placed in any cognitive owner package.
2. The bridges must read stage results from the `frame.stage_results` mapping using the
   `_require_stage_result` helper already used by runtime stages (not by direct import of
   owner engines).
3. The text projection format must be bounded: each summary value must be a short English
   sentence (under 200 characters) that names the real dimension and its bounded value.
4. No new contract type, field, or validation rule may be introduced on `EmbodiedPromptRequest`
   or `InternalThoughtRequest`. The shape (5 summary dicts, `internal_state_summary` string)
   is unchanged; only the content values change under the semantic assembly.
5. The composition owner-boundary guard (`test_composition_owner_boundary_guard.py`) must
   still pass after the new bridges are added. The bridges are owner-neutral glue; they
   forward bounded facts and derive no cognitive policy.

## 6. Impacted Modules

1. `helios_v2/composition/bridges.py` — two new bridge classes.
2. `helios_v2/composition/runtime_assembly.py` — ternary wiring for prompt/thought bridges.
3. `tests/test_composition_bridges.py` or `tests/test_runtime_composition.py` — new bridge
   tests and migration of existing tests that assert on constant summary text.
4. `tests/test_runtime_stage_chain.py` — tests that construct prompt/thought stages may
   need migration.
5. `helios_v2/docs/requirements/index.md` — new R70 row.
6. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` / `PROGRESS_FLOW.en.md` — sync line update.
7. `helios_v2/docs/PHASE_METRICS.md` — P1 completion metrics update.

## 7. Acceptance Criteria

1. `assemble_runtime()` (default semantic) produces an `EmbodiedPromptRuntimeStage` wired
   with `SemanticEmbodiedPromptRequestBridge` and an `InternalThoughtRuntimeStage` wired
   with `SemanticInternalThoughtRequestBridge`.
2. A tick under the default assembly produces an `EmbodiedPromptRequest` whose
   `stimulus_summary["present_field"]` contains text derived from the real `02` sensory
   batch content (not "A cli text stimulus is present...").
3. A tick under the default assembly produces an `EmbodiedPromptRequest` whose
   `state_summary["affective_summary"]` contains text derived from the real `05`
   `InteroceptiveFeelingVector` dimensions and values (not "arousal is elevated...").
4. A tick under the default assembly produces an `InternalThoughtRequest` whose
   `internal_state_summary` contains text derived from the real `04`/`05`/`03` state (not
   "runtime state summary").
5. `assemble_runtime(default_signal_mode="legacy_constant")` produces prompt/thought
   bridges byte-for-byte identical to the pre-R70 default.
6. Varying external stimuli across ticks produces measurably different `stimulus_summary`
   and `state_summary` text — the LLM's prompt context reflects the brain's real state
   variation.
7. The composition owner-boundary guard still passes.
8. Full test suite passes (`pytest helios_v2/tests/ -x`).