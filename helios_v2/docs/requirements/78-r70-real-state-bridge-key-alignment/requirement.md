# Requirement 78 - R70 Real-State Bridge Stage-Key Alignment

## 1. Background and Problem

R70 (`70-prompt-to-thought-real-state-bridge`) shipped two semantic bridges
(`SemanticEmbodiedPromptRequestBridge` and `SemanticInternalThoughtRequestBridge`) intended to
project the real `04` `NeuromodulatorLevels` and `05` `InteroceptiveFeelingVector` from the
tick frame into the LLM user-message context, so the LLM thought loop (R11) sees the brain's
actual affective state instead of constant English strings.

End-to-end capture (2026-06-10) of the real LLM request confirms the bridges are wired
correctly but **silently falling back to constant strings** in every observed tick:

- `Neuromodulators: neuromodulators at tonic baseline.` (constant fallback)
- `Feeling: feeling at baseline.` (constant fallback)

Root cause: stage-result key mismatch between the bridges and the runtime stage producers.

- `composition/bridges.py:1980` (`_affective_summary_text` — produces
  `state_summary["affective_summary"]`) reads `stage_results.get("interoceptive_feeling")`
- `composition/bridges.py:2085` (`_internal_state_text` — produces
  `internal_state_summary` neuromodulator part) reads `stage_results.get("neuromodulation")`
- `composition/bridges.py:2097` (`_internal_state_text` — produces
  `internal_state_summary` feeling part) reads `stage_results.get("interoceptive_feeling")`
- but `runtime/stages.py:1044` writes `"neuromodulator_system"` and
  `runtime/stages.py:1105` writes `"interoceptive_feeling_layer"`.

All three key lookups are wrong; the `isinstance` guard always falls through, and the bridge
returns the literal fallback string instead of computing a real projection. The 03 appraisal
projection in the same function reads the correct key (`"rapid_salience_appraisal"`,
matching `stages.py:1012`), which is why the user message correctly shows
`Salience: aggregate ...` even though the neuromodulator/feeling projections are fabricated.

This directly violates R70 § 3.1.8 ("When any required stage result is missing from the frame
... the bridge must raise `RuntimeStageExecutionError` rather than silently falling back to a
constant") and R70 § 4.2 ("The bridges must never fabricate a state that was not computed by
the upstream owners. Missing required stage results are a hard stop.").

The R70 §7 acceptance criteria that depend on these projections:

- §7.3 — `state_summary["affective_summary"]` derives from the real `05` feeling vector
  (currently broken via L1980).
- §7.4 — `internal_state_summary` derives from real `04`/`05`/`03` (currently broken via
  L2085/L2097 for the 04/05 parts; the 03 part is correct).

Note: R70 §3.1.8 also says missing upstream results must raise `RuntimeStageExecutionError`,
not silently fall back. This requirement chooses to keep the current defensive
`isinstance`-based fallback (a structured "no computed state yet" marker, not a fabricated
emotional claim) rather than introduce a hard raise, because the current architecture wires
the bridges before the `04`/`05` stages run and a hard raise would break the default assembly.
The fallback text itself is preserved; only the key lookup is corrected so the fallback is
reached only when the upstream stage result is truly absent, not always.

## 2. Goal

Repair the stage-result key lookup in the R70 semantic bridges so they read the real
`NeuromodulatorLevels`, `InteroceptiveFeelingVector`, and 09 continuation signal from the
frame, fulfilling the R70 acceptance criteria §7.2-§7.4 (LLM user message reflects real
04/05/09 state, not constant fallback strings). Preserve the existing `isinstance`-based
defensive pattern: when the real stage result is genuinely absent (e.g. legacy constant
assembly or upstream order error), keep the existing fallback string and treat the absence
as a structured signal — do not raise, because the fallback is a deliberate "no computed
state yet" projection, not a fabricated emotional claim.

## 3. Functional Requirements

### 3.1 Stage-key alignment

1. In `composition/bridges.py:2085`, change the neuromodulator stage-result lookup key from
   `"neuromodulation"` to `"neuromodulator_system"`, matching `runtime/stages.py:1044`.
2. In `composition/bridges.py:2097` and `composition/bridges.py:1980`, change the
   interoceptive-feeling stage-result lookup key from `"interoceptive_feeling"` to
   `"interoceptive_feeling_layer"`, matching `runtime/stages.py:1105`.
3. The fix is owner-neutral: do not modify any cognitive owner package
   (`neuromodulation`, `feeling`, `thought_gating`, etc.) and do not modify `runtime/stages.py`.

### 3.2 Defensive projection semantics

1. The `isinstance` guard must remain in place: when a stage result is genuinely absent
   (assembly mode, upstream order error, or warm-up), the bridge must continue to emit the
   existing fallback string. The fallback is a structured "no computed state yet" marker, not
   a fabricated emotional claim.
2. The fallback text strings for 04 and 05 must remain unchanged:
   - `"neuromodulators at tonic baseline"`
   - `"feeling at baseline"`
3. The fix must not introduce new imports, new contract types, or new public APIs. The two
   R70 semantic bridge classes and their `__init__` / `build` / text-projection method
   signatures remain identical.

### 3.3 Observability and verification

1. The existing `21` observability owner and `R70` smoke tests must continue to pass without
   modification, because the change only corrects the key — it does not change the projection
   format or the contract.
2. A new R78 verification test must run a default-assembly tick and assert the captured
   `LlmRequest.user_message` content does **not** contain the literal fallback substrings
   `"neuromodulators at tonic baseline"` or `"feeling at baseline"`. The assertion is on the
   real projection format, e.g. it must contain the prefix `"DA "` and `"arousal "` (or
   whichever bounded projection format R70 produced for real `NeuromodulatorLevels` /
   `InteroceptiveFeelingVector`).

## 4. Non-Functional Requirements

1. **Performance**: zero per-tick cost change. Same `dict.get` + `isinstance` shape.
2. **Reliability**: the defensive `isinstance` guard is preserved; absence of upstream
   results remains a structured projection, never a fabrication of an emotional state.
3. **Compatibility**: `FirstVersion*Bridge` behavior under
   `default_signal_mode="legacy_constant"` is unchanged (those bridges are in the same file
   but do not read these keys).
4. **No new owner imports**: the bridges must not import any cognitive owner engine; they
   continue to read only published contract types (`NeuromodulatorStageResult`,
   `InteroceptiveFeelingStageResult`) and bounded facts.

## 5. Code Behavior Constraints

1. The change is a pure key-rename: 2 occurrences on the 04 neuromodulator side, 2
   occurrences on the 05 feeling side (one in `_present_feeling_text`, one in
   `_present_continuation_summary_text`).
2. The fix is allowed to be delivered as a single commit on a feature branch.
3. The fix must not bypass R70's owner-neutrality guarantee: the bridges still read only
   published contract types from the frame, never cognitive policy.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` — three string-key edits at L1980, L2085,
   L2097.
2. `helios_v2/tests/test_r70_real_state_bridge_key_alignment.py` — new verification test that
   runs one default-assembly tick, captures the LlmRequest via a mock gateway, and asserts
   the real projection format is present.
3. `helios_v2/docs/requirements/index.md` — add R78 row, maturity `baseline_implementation`
   (the bug is a one-line, fully-tested fix that does not introduce new behavior).
4. `helios_v2/docs/PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md` — sync line naming R78.
5. `helios_v2/docs/PHASE_METRICS.md` — confirm P1 metrics unchanged (no new capability added,
   an existing one is now correctly wired).

## 7. Acceptance Criteria

1. Running `assemble_runtime()` (default semantic) and a single tick produces an LLM user
   message containing the real `DA <value> NE <value> ...` projection (not the literal
   substring `"neuromodulators at tonic baseline"`).
2. The same LLM user message contains the real `arousal <value>, valence <value>, tension
   <value>` projection (not the literal substring `"feeling at baseline"`).
3. The composition owner-boundary guard test
   (`test_composition_owner_boundary_guard.py`) still passes — the fix introduces no new
   cognitive-owner imports.
4. The R70 verification test (`test_r70_real_state_bridge_key_alignment.py`) is green.
5. The full test suite (`pytest helios_v2/tests/`) is green modulo pre-existing R71
   performance-flake failures (`test_p2_p1_sqlite_append_throughput`,
   `test_p2_p2_semantic_recall_latency` — both timing-sensitive, confirmed pre-existing by
   stash-and-rerun on the pre-R78 commit `0f34c2d`). Baseline moves from 834 passed to
   838 total / 836 passed / 2 pre-existing R71 perf-flake failures.
6. End-to-end capture (mirroring the 2026-06-10 capture) shows 04 and 05 projected with real
   bounded values across at least three consecutive ticks with varying salience.
