# Requirement 78 - R70 Real-State Bridge Stage-Key Alignment — Design

## 1. Design Overview

Three string-key edits in `composition/bridges.py` correct the stage-result lookups in the
R70 semantic bridges to match the actual stage names published by `runtime/stages.py`. The
fix is owner-neutral, additive-free, and contract-preserving: the bridges continue to
project bounded raw facts from the frame into short English sentences; they just stop
silently falling back to constant text on every tick. The change unlocks the LLM-facing
visibility of the real `04` `NeuromodulatorLevels` and `05` `InteroceptiveFeelingVector` that
R70 was designed to provide, and re-anchors the 09 continuation-pressure projection on the
correct upstream state.

## 2. Current State and Gap

End-to-end capture on 2026-06-10 (3 ticks, default semantic assembly, mock LLM gateway)
shows the LLM user message always contains:

- `Neuromodulators: neuromodulators at tonic baseline.` — the literal fallback at
  `bridges.py:2092`.
- `Feeling: feeling at baseline.` — the literal fallback at `bridges.py:2102`.

The 03 appraisal projection in the same function reads the correct key
(`"rapid_salience_appraisal"`, matching `stages.py:1012`) and correctly shows
`Salience: aggregate 0.89, top dimension: novelty` — proving the 03 path is wired correctly
and the bug is isolated to the 04/05 key lookups.

Stage name inventory (from `runtime/stages.py`):

| stage | runtime writes | bridges.py reads (R70) | match |
|-------|---------------|----------------------|-------|
| sensory_ingress | L990: `sensory_ingress` | L1273/1526/1706/1957: `sensory_ingress` | ✅ |
| rapid_salience_appraisal | L1012: `rapid_salience_appraisal` | L1340/1646/2105: `rapid_salience_appraisal` | ✅ |
| neuromodulator_system | L1044: `neuromodulator_system` | L2085: `neuromodulation` | ❌ |
| interoceptive_feeling_layer | L1105: `interoceptive_feeling_layer` | L1980/2097: `interoceptive_feeling` | ❌ |

The key mismatch on the 04/05 sites (3 lookups total: 1 neuromodulator + 2 feeling) is the
entire gap.

## 3. Target Architecture

```
SemanticEmbodiedPromptRequestBridge._affective_summary_text(frame):
    stage_results = frame.stage_results or {}
    # R78: align with stages.py:1105
    feeling_result = stage_results.get("interoceptive_feeling_layer")
    if isinstance(feeling_result, InteroceptiveFeelingStageResult):
        ... real projection of dominant feeling dims ...
    else:
        return "Affect baseline; no computed feeling state."  # unchanged fallback

SemanticInternalThoughtRequestBridge._present_internal_state_text(frame):
    stage_results = frame.stage_results or {}
    # R78: align with stages.py:1044
    nm_result = stage_results.get("neuromodulator_system")
    if isinstance(nm_result, NeuromodulatorStageResult):
        ... real DA/NE/5-HT/ACh/Cort projection ...
    else:
        nm_text = "neuromodulators at tonic baseline"  # unchanged fallback

    # R78: align with stages.py:1105
    feeling_result = stage_results.get("interoceptive_feeling_layer")
    if isinstance(feeling_result, InteroceptiveFeelingStageResult):
        ... real arousal/valence/tension projection ...
    else:
        feel_text = "feeling at baseline"  # unchanged fallback

    appraisal_result = stage_results.get("rapid_salience_appraisal")  # already correct
    ... unchanged ...
```

The continuation-pressure projection in
`SemanticEmbodiedPromptRequestBridge._continuation_summary_text` (L2011) does not read
`stage_results` — it consumes the `thought_gating_result` argument directly — so it is
unaffected by the key fix.

The R70 ternary wiring in `composition/runtime_assembly.py:1579,1592` is unchanged: the
same `SemanticEmbodiedPromptRequestBridge` and `SemanticInternalThoughtRequestBridge`
classes are wired when `semantic_memory_enabled == True`; only their internal key
lookups are corrected.

## 4. Data Structures

No data structure changes. The frame, stage results, and prompt contract shapes are
unchanged. The R70 text projection format strings are unchanged. The only change is the
string key passed to `dict.get`.

## 5. Module Changes

### 5.1 `helios_v2/src/helios_v2/composition/bridges.py`

Three single-line edits:

1. **L1980** (`_affective_summary_text` — produces `state_summary["affective_summary"]`,
   used by `SemanticEmbodiedPromptRequestBridge`):
   - Old: `feeling_result = stage_results.get("interoceptive_feeling")`
   - New: `feeling_result = stage_results.get("interoceptive_feeling_layer")`

2. **L2085** (`_internal_state_text` — produces `internal_state_summary` neuromodulator
   part, used by `SemanticInternalThoughtRequestBridge`):
   - Old: `nm_result = stage_results.get("neuromodulation")`
   - New: `nm_result = stage_results.get("neuromodulator_system")`

3. **L2097** (`_internal_state_text` — produces `internal_state_summary` feeling part,
   used by `SemanticInternalThoughtRequestBridge`):
   - Old: `feeling_result = stage_results.get("interoceptive_feeling")`
   - New: `feeling_result = stage_results.get("interoceptive_feeling_layer")`

### 5.2 `helios_v2/tests/test_r70_real_state_bridge_key_alignment.py`

New test file. One verification test that:

1. Builds `assemble_runtime(deterministic_thought=False, gateway=mock)`.
2. Registers a fake sensory source.
3. Runs one tick.
4. Captures the LLM request via the mock gateway.
5. Asserts the user message contains `"DA "` (real neuromodulator projection).
6. Asserts the user message contains `"arousal "` (real feeling projection).
7. Asserts the user message does **not** contain the literal fallback
   `"neuromodulators at tonic baseline"`.
8. Asserts the user message does **not** contain the literal fallback `"feeling at baseline"`.

### 5.3 Documentation sync

- `index.md`: add R78 row, maturity `baseline_implementation` (one-line test added; no new
  capability, but the bug fix is operationally significant for P5 and the R70 contract
  intent).
- `PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md`: sync line naming R78.
- `PHASE_METRICS.md`: confirm P1 metrics unchanged.

## 6. Migration Plan

1. Branch `fix/R78-r70-real-state-bridge-key-alignment` from `main` at the current commit
   (R77, `0f34c2d`).
2. Apply the three string-key edits in `composition/bridges.py`.
3. Add the verification test.
4. Run `pytest helios_v2/tests/ -x` to confirm the baseline moves from 834 passed to 835+
   passed with no regression.
5. Commit: `fix(R78): align R70 semantic bridges with stages.py stage names — 04/05 projections
   now reach the LLM` and push.
6. Open a PR describing the R78 requirement package.

## 7. Failure Modes and Constraints

- The defensive `isinstance` guard is preserved: when the upstream stage result is genuinely
  absent (e.g. assembly mode, warm-up tick, structural error), the bridge continues to emit
  the existing fallback string. The fallback is a structured "no computed state yet"
  marker, not a fabricated emotional claim.
- The fix does not introduce new owner imports. The bridges still read only published
  contract types (`NeuromodulatorStageResult`, `InteroceptiveFeelingStageResult`) from the
  frame, never the cognitive owner engines.
- The fix does not change the projection format strings: the real projection still reads
  `f"DA {levels.dopamine:.2f} NE {levels.norepinephrine:.2f} 5-HT ..."` and
  `f"arousal {feeling.arousal:.2f}, valence {feeling.valence:.2f}, tension ..."`.

## 8. Observability and Logging

No new observability mechanism. The R70 change is invisible to the `21` observability owner:
the projection text changes from a constant string to a real bounded string of identical
shape, and the existing prompt-contract observability already records the rendered prompt
content.

## 9. Validation Strategy

1. **Unit test (new)**: `test_r70_real_state_bridge_key_alignment.py` — see §5.2.
2. **Regression**: full `pytest helios_v2/tests/ -x` — baseline 834 passed must move to
   835+ passed with no failures.
3. **End-to-end capture**: re-run the 2026-06-10 capture script
   (`scratch_llm_prompt_reconstruction.py`) and confirm the LLM user message contains real
   `DA <value>` and `arousal <value>` projections across at least three consecutive ticks.
4. **Composition owner-boundary guard**: `test_composition_owner_boundary_guard.py` must
   remain green (no new cognitive-owner imports in the bridges).
