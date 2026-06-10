# Requirement 70 - Prompt-to-Thought Real-State Bridge — Design

## 1. Design Overview

This design replaces the two constant-shim bridges that feed the LLM thought loop (`11`) and
prompt-contract owner (`16`) with semantic variants that read the real `02`–`10` owner state
from the tick frame and project it into bounded English text. It introduces:

1. **`SemanticEmbodiedPromptRequestBridge`** — reads `02` sensory batch, `05` feeling vector,
   `09` gate/continuation state, and `10` retrieval bundle from the frame, and derives the
   five summary dicts required by `EmbodiedPromptRequest`.
2. **`SemanticInternalThoughtRequestBridge`** — reads `04` neuromodulator levels, `05`
   feeling vector, and `03` salience vector from the frame, and derives the
   `internal_state_summary` string required by `InternalThoughtRequest`.
3. **Assembly wiring** — ternary `if semantic_memory_enabled else FirstVersion*` pattern in
   `assemble_runtime`, identical to all prior de-shim wiring.

The design preserves every existing invariant: no contract shape change, no new validation
rule, no cognitive policy in the bridges, `FirstVersion*Bridge` byte-for-byte unchanged
under `legacy_constant` mode, and the composition owner-boundary guard still passes.

## 2. Current State and Gap

### 2.1 Current state

`FirstVersionEmbodiedPromptRequestBridge.build_requests()`:

- Reads only `conscious_result.state.state_id`, `thought_gating_result.result.result_id`,
  `directed_retrieval_result.bundle.bundle_id` (provenance IDs).
- All five summary dicts contain constant English strings.
- No reference to `frame.stage_results` beyond the explicitly passed arguments.

`FirstVersionInternalThoughtRequestBridge.build_request()`:

- Reads `thought_gating_result.result.result_id`,
  `directed_retrieval_result.bundle.bundle_id`,
  `thought_gating_result.continuation_state.active`, and the `prompt_result.contracts`.
- `internal_state_summary = "runtime state summary"` (constant).
- No reference to any `03`–`05` state.

### 2.2 Gap

The bridges receive `frame` (a `RuntimeFrame` containing all `02`–`18` stage results) as
their first parameter but currently only use provenance IDs from the explicitly passed
results. The real `03`–`10` state is present in `frame.stage_results` and can be read
through `_require_stage_result` (the same helper used by runtime stages). The bridges need
to access this data and project it into text.

## 3. Target Architecture

### 3.1 Semantic embodied-prompt request bridge data flow

```
SemanticEmbodiedPromptRequestBridge.build_requests(frame, conscious, gate, retrieval)
  ├─ stimulus_summary["present_field"]
  │     = _present_field_text(frame) — reads 02 SensoryIngressStageResult
  │       → external stimulus content if present, else "no external stimulus this cycle"
  ├─ state_summary["affective_summary"]
  │     = _affective_summary_text(frame) — reads 05 InteroceptiveFeelingStageResult
  │       → dominant feeling dimensions with real [0,1] values
  ├─ state_summary["continuation_summary"]
  │     = _continuation_summary_text(frame, gate) — reads 09 ThoughtGatingStageResult
  │       → gate decision + continuation pressure state
  ├─ retrieval_summary["retrieval_context"]
  │     = _retrieval_context_text(frame, retrieval) — reads 10 DirectedRetrievalStageResult
  │       → which tier contents are present
  ├─ retrieval_summary["continuity_context"]
  │     = _continuity_context_text(retrieval) — reads 10 bundle content
  │       → first available content summary, or "no active continuity trace"
  ├─ capability_summary  (constant, from FirstVersion)
  ├─ identity_boundary_summary  (constant, from FirstVersion)
  └─ provenance IDs (unchanged)
```

### 3.2 Semantic internal-thought request bridge data flow

```
SemanticInternalThoughtRequestBridge.build_request(frame, gate, retrieval, prompt)
  ├─ internal_state_summary
  │     = _internal_state_text(frame) — reads 03/04/05 stage results
  │       → neuromodulator levels + feeling vector + salience landscape
  ├─ source_gate_result_id  (unchanged)
  ├─ source_retrieval_bundle_id  (unchanged)
  ├─ source_continuation_active  (unchanged)
  ├─ prompt_contract_summary  (unchanged)
```

### 3.3 Assembly wiring

```
EmbodiedPromptRuntimeStage(
    prompt_layer=embodied_prompt,
    request_provider=(
        SemanticEmbodiedPromptRequestBridge()
        if semantic_memory_enabled
        else FirstVersionEmbodiedPromptRequestBridge()
    ),
)
InternalThoughtRuntimeStage(
    internal_thought_layer=internal_thought,
    request_provider=(
        SemanticInternalThoughtRequestBridge()
        if semantic_memory_enabled
        else FirstVersionInternalThoughtRequestBridge()
    ),
)
```

## 4. Data Structures

No new contract types or fields are introduced. The bridges read existing types:

### 4.1 Types read by `SemanticEmbodiedPromptRequestBridge`

| Frame key | Type | Fields used |
|-----------|------|------------|
| `sensory_ingress` | `SensoryIngressStageResult` | `batch.stimuli` (content, modality) |
| `interoceptive_feeling` | `InteroceptiveFeelingStageResult` | `state.feeling` (arousal, valence, tension, etc.) |
| `thought_gating_and_continuation_pressure` | `ThoughtGatingStageResult` | `result.decision`, `continuation_state.active` |
| `directed_retrieval_into_thought_window` | `DirectedRetrievalStageResult` | `bundle.short_term_context`, `bundle.mid_term_hits`, `bundle.autobiographical_hits` |

### 4.2 Types read by `SemanticInternalThoughtRequestBridge`

| Frame key | Type | Fields used |
|-----------|------|------------|
| `rapid_salience_appraisal` | `RapidSalienceAppraisalStageResult` | `batch.salience_vectors` (aggregate, threat, reward, etc.) |
| `neuromodulation` | `NeuromodulatorStageResult` | `state.levels` (dopamine, norepinephrine, etc.) |
| `interoceptive_feeling` | `InteroceptiveFeelingStageResult` | `state.feeling` (arousal, valence, etc.) |

### 4.3 Text projection format

Each projection produces a bounded English sentence (under 200 characters) that names the
real dimension and its `[0,1]` value. Example outputs:

- `stimulus_summary["present_field"]`: "External stimulus present: 'hello runtime' (modality: cli_text)."
  Or: "No external stimulus this cycle; only internal body signals present."
- `state_summary["affective_summary"]`: "Arousal 0.72, tension 0.35, valence 0.48; dominant: arousal."
- `state_summary["continuation_summary"]`: "Continuation pressure active; gate fired on salience-driven arousal."
  Or: "No continuation pressure; gate fired on initial stimulus ignition."
- `retrieval_summary["retrieval_context"]`: "Short-term context present; 1 mid-term hit; 0 autobiographical anchors."
- `retrieval_summary["continuity_context"]`: "Current obligation: 'remember runtime chain context'."
  Or: "No active continuity trace this cycle."
- `internal_state_summary`: "Neuromodulators: DA 0.55 NE 0.72 5-HT 0.40 ACh 0.30 Cort 0.15. Feeling: arousal 0.72, valence 0.48, tension 0.35. Salience: aggregate 0.62, novelty 0.45, threat 0.10."

## 5. Module Changes

### 5.1 `helios_v2/composition/bridges.py`

1. Add `SemanticEmbodiedPromptRequestBridge` dataclass after `FirstVersionEmbodiedPromptRequestBridge`.
2. Add `SemanticInternalThoughtRequestBridge` dataclass after `FirstVersionInternalThoughtRequestBridge`.
3. Add private projection helpers:
   - `_present_field_text(frame)` — reads `02` sensory result, projects stimulus content.
   - `_affective_summary_text(frame)` — reads `05` feeling result, projects dominant dimensions.
   - `_continuation_summary_text(frame, thought_gating_result)` — reads `09` gate state.
   - `_retrieval_context_text(frame, directed_retrieval_result)` — reads `10` retrieval bundle tiers.
   - `_continuity_context_text(directed_retrieval_result)` — reads `10` bundle content.
   - `_internal_state_text(frame)` — reads `03`/`04`/`05` results, projects combined state.
4. All helpers use `_require_stage_result` from `runtime.stages` (already imported in bridges.py).

### 5.2 `helios_v2/composition/runtime_assembly.py`

1. Change `EmbodiedPromptRuntimeStage.request_provider` from unconditional
   `FirstVersionEmbodiedPromptRequestBridge()` to ternary:
   `SemanticEmbodiedPromptRequestBridge() if semantic_memory_enabled else FirstVersionEmbodiedPromptRequestBridge()`.
2. Change `InternalThoughtRuntimeStage.request_provider` from unconditional
   `FirstVersionInternalThoughtRequestBridge()` to ternary:
   `SemanticInternalThoughtRequestBridge() if semantic_memory_enabled else FirstVersionInternalThoughtRequestBridge()`.
3. Import the two new bridges in the module's import block.

### 5.3 No changes to cognitive owner packages

`03`–`10` owners, `11` internal thought, `16` prompt contract — no engine or contract changes.
The bridges are composition-only glue.

## 6. Migration Plan

### 6.1 Phase 1: Ship the two new bridge classes (no behavior change)

Add `SemanticEmbodiedPromptRequestBridge` and `SemanticInternalThoughtRequestBridge` to
`bridges.py`. Add private projection helpers. Add focused unit tests. No assembly change.
No existing test breaks.

### 6.2 Phase 2: Wire bridges in `assemble_runtime`

Update `runtime_assembly.py` to use ternary wiring for prompt and thought bridges. This
is the breaking change: existing tests that assert on constant summary text under the
default semantic assembly will fail.

### 6.3 Phase 3: Migrate existing tests

Tests that depend on constant summary text must either:
- Add `default_signal_mode="legacy_constant"` to preserve the old assertion, or
- Update assertions to check for real-state-derived text (e.g. `assert "arousal" in
  state_summary["affective_summary"]` instead of `assert state_summary["affective_summary"]
  == "arousal is elevated..."`).

### 6.4 Phase 4: Add integration tests and update documentation

Integration test validating that varying stimuli produce varying prompt/thought text.
Update `index.md`, `PROGRESS_FLOW.*`, `PHASE_METRICS.md`.

## 7. Failure Modes and Constraints

1. **Missing stage result in frame**: the `_require_stage_result` helper raises
   `RuntimeStageExecutionError` with a clear diagnostic. This is the same failure mode
   used by every runtime stage and is a hard stop, never a silent fallback.
2. **No external stimulus in `02` batch**: `_present_field_text` returns an honest "no
   external stimulus" marker, not a fabricated content string. This is defined behavior.
3. **Empty retrieval bundle**: `_retrieval_context_text` returns "no retrieval context
   available"; `_continuity_context_text` returns "no active continuity trace". Defined
   behavior.
4. **Legacy constant mode**: `FirstVersion*Bridge` is byte-for-byte unchanged. No
   degradation path from semantic to constant — the ternary selects one or the other based
   on the profile, never blending.

## 8. Observability and Logging

No new logging mechanism. The existing `21` observability owner and kernel instrumentation
are unchanged. The bridge selection (semantic vs. first-version) is reflected in the
`semantic_memory_enabled` property of `RuntimeProfile`, which is already observable.

## 9. Validation Strategy

1. **Unit tests** for each projection helper: deterministic text output for known input
   values; bounded length; honest absence markers.
2. **Unit tests** for each bridge class: conform to provider protocol; produce valid
   `EmbodiedPromptRequest` / `InternalThoughtRequest` with real-state-derived summaries.
3. **Integration test**: default semantic assembly produces prompt/thought requests with
   non-constant summaries; varying stimuli produce varying summary text.
4. **Regression test**: legacy constant assembly produces byte-for-byte identical
   prompt/thought requests compared to pre-R70.
5. **Owner-boundary guard**: still passes after bridge additions.
6. **Full suite**: all 775+ existing tests pass after migration.