# Requirement 91 - Present-Field Into the Internal Thought Prompt — Design

## 1. Design Overview

R91 is a strictly additive change in three small surfaces that lets the `11` thinking LLM read the
current stimulus content + elapsed pacing it already had cause to know about:

1. `InternalThoughtRequest` gets an optional `present_field_summary: str | None = None` (default None
   preserves byte-for-byte behavior).
2. `SemanticInternalThoughtRequestBridge` (composition, owner-neutral glue) projects the **same-frame
   `02 sensory_ingress` external stimulus content** (the operator's actual words) plus the same-frame
   `08 ReportableConsciousContent` focal commitment status plus the optional `TemporalSource`'s
   `temporal_signal` into a bounded English line and assigns it.
3. `InternalThoughtEngine._build_messages` prepends the line into the LLM user message when present.

**Empirical correction (post-implementation smoke).** The initial design assumed `08.focal_summary`
was the place where the operator's text lived. A real-LLM smoke after T1–T4 captured the actual
prompt and showed `08.focal_summary` is a generic candidate-level descriptor
("Current focal content from perceived-stimulus-summary: ...current-cycle memory context") that does
NOT carry the raw operator text — and the model continued to idle. The operator's words are at the
source: `02 sensory_ingress.batch.stimuli[*].content`. The bridge therefore projects directly from
`02` (filtered by the existing `_INTERNAL_MODALITIES` set so internal/body/background signals do not
become a fabricated speaker), and `08` commitment is appended as a secondary clause. This finding is
also recorded in ROADMAP §11.2.

No new owner. No new logging. No system-prompt change. `FirstVersionInternalThoughtRequestBridge`
keeps the field None, so legacy-constant mode is unchanged. Real-LLM prompt validation (§9) is
already complete via `scripts/r91_probes/01..07` (judge notes under
`helios_v2/logs/prerun/r91_probes/_JUDGE_NOTES.md`).

## 2. Current State and Gap

- `InternalThoughtRequest` (in `helios_v2/internal_thought/contracts.py`) currently has
  `request_id` / `source_gate_result_id` / `source_retrieval_bundle_id` /
  `source_continuation_active` / `internal_state_summary` / `prompt_contract_summary` / `tick_id`,
  with `internal_state_summary` validated non-empty.
- `_build_messages` in `helios_v2/internal_thought/engine.py` produces:
  `"Internal state: ..." → "Current context: ..." (short_term[0]) → "Mid-term memory: ..." → "Autobiographical anchor: ..." → "Continuation pressure is ... for this cycle."`.
  No present-field line; the operator's words are nowhere.
- Real-LLM probe (negative control 07) reproduces the empirical failure: "Social salience lingers...
  no impulse to reach outward." Probes 01–06 prove that adding a `Present field:` line resolves it.
- `08` `ReportableConsciousContent` already carries the bounded text we need: `focal_summary` (1
  sentence) + `salient_tokens` (≤ N short tokens). Composition can read it from the same-frame
  `frame.stage_results["reportable_conscious_content"].state.focal_content` and the conscious-state
  `no_commit_reason`.
- `helios_v2.temporal.TemporalSource.sample(...)` already returns a bounded `temporal_signal` per
  tick. The semantic gate-signal bridge already calls it; this requirement also calls it from the
  thought-request bridge through the same injected source.

## 3. Target Architecture

### 3.1 Contract change (`internal_thought/contracts.py`)

Add the additive field with bounded validation:

```python
PRESENT_FIELD_SUMMARY_MAX_CHARS: Final = 600
PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX: Final = "…(truncated)"

@dataclass(frozen=True)
class InternalThoughtRequest:
    ...existing fields...
    tick_id: int | None
    present_field_summary: str | None = None  # additive

    def __post_init__(self) -> None:
        ...existing validation...
        if self.present_field_summary is not None:
            value = self.present_field_summary
            if not value or not value.strip():
                raise InternalThoughtError(
                    "InternalThoughtRequest.present_field_summary must not be blank when set"
                )
            if len(value) > PRESENT_FIELD_SUMMARY_MAX_CHARS:
                # deterministic truncation with explicit suffix; never silent
                cap = PRESENT_FIELD_SUMMARY_MAX_CHARS - len(PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX)
                object.__setattr__(
                    self,
                    "present_field_summary",
                    value[:cap] + PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX,
                )
```

### 3.2 Bridge projection (`composition/bridges.py`)

Two owner-neutral helpers:

1. `_present_field_stimuli_clause(frame)` reads `frame.stage_results["sensory_ingress"]` and
   selects up to `_PRESENT_FIELD_MAX_STIMULI = 3` stimuli whose modality is NOT in
   `_INTERNAL_MODALITIES = {"body", "interoceptive", "background"}` — so internal interoceptive
   signals never become a fabricated speaker. Each kept stimulus is rendered as
   `<source_name|channel> said: "<content[:_PRESENT_FIELD_PER_STIMULUS_CHARS=200]>"`. Returns None
   when no external stimulus is present (honest absence).

2. `_present_field_summary_text(frame, temporal_source)` composes the final line by joining (in
   order, when present): the stimuli clause, an `08` focal-content clause
   (`focal: <focal_summary>; tokens: <up to 8>` when committed, else
   `no focal content this cycle: <reason>`), and a `pacing: <signal>` clause from the optional
   temporal source. Returns None on a tick with no external stimulus, no `08`, and no temporal
   source.

`SemanticInternalThoughtRequestBridge` gains an optional injected `temporal_source` (mirroring the
gate-signal bridge already declares one) and assigns the projected text to `present_field_summary`.

`FirstVersionInternalThoughtRequestBridge` is unchanged (leaves the field default None).

### 3.3 LLM message rendering (`internal_thought/engine.py`)

In `LlmInternalThoughtPath._build_messages`, prepend the present-field line before the existing
`Internal state:` line when present:

```python
user_lines: list[str] = []
if request.present_field_summary:
    user_lines.append(f"Present field: {request.present_field_summary}")
user_lines.append(f"Internal state: {request.internal_state_summary}")
...existing retrieval / continuation lines...
```

When `present_field_summary` is None, the produced user message is byte-for-byte identical to today.

### 3.4 Composition wiring (`composition/runtime_assembly.py`)

The existing `temporal_source` (already constructed for the gate-signal bridge in semantic mode) is
also passed to the new `SemanticInternalThoughtRequestBridge` field. One-line wiring change.

## 4. Data Structures

- Two module-level constants in `internal_thought/contracts.py`:
  `PRESENT_FIELD_SUMMARY_MAX_CHARS = 600`, `PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX = "…(truncated)"`.
- One additive field on `InternalThoughtRequest`. No other contract changes.

## 5. Module Changes

1. `internal_thought/contracts.py` — additive field + bounded validation + two constants.
2. `internal_thought/engine.py` — one prepended user-line in `_build_messages`.
3. `composition/bridges.py` — helper + bridge field + assignment in
   `SemanticInternalThoughtRequestBridge` (FirstVersion bridge unchanged).
4. `composition/runtime_assembly.py` — pass `temporal_source` to the semantic thought-request bridge.
5. New tests:
   - `tests/test_internal_thought_contracts.py` (or extend the existing thought-related contract
     tests if present) — None default; non-empty rule; length cap + deterministic truncation.
   - `tests/test_internal_thought_engine.py` — `_build_messages` includes the line iff set; None
     keeps the message byte-for-byte; the LLM-driven path threads it through.
   - `tests/test_semantic_thought_request_bridge.py` (or extend existing bridge tests) — focal
     committed → projects `focal:` + tokens; no-commit → honest absent marker; with temporal source →
     pacing appended; legacy bridge stays None.
6. Docs: `requirements/index.md` row 91; ROADMAP §10 mark R91 delivered;
   `OWNER_GUIDE`/`PROGRESS_FLOW` unchanged (no maturity color / chain change — this is additive).

## 6. Migration Plan

1. Default-None for the new field means every existing test that constructs `InternalThoughtRequest`
   directly continues to pass without change.
2. The bridge and assembly changes are scoped to semantic mode (`default_signal_mode="semantic"`,
   the post-R69 default). Legacy-constant assemblies keep their constant bridge with field None.
3. Probe-driven validation (real-LLM, MiniMax-M3) was completed before implementation per
   `requirement-authoring-standard.md` §8.2. The implementation must keep the same prompt shape the
   probe validated; any subsequent shape change requires a re-probe.

## 7. Failure Modes and Constraints

1. Empty/whitespace value → contract raises (an explicit honest failure, never silently empty).
2. Over-cap value → deterministic truncation with the documented suffix.
3. Missing `08` focal content (no_commit / inactive) → honest absent marker; thought cycle still
   completes; no fabricated speaker.
4. Missing/no temporal source → no pacing clause appended (defined absence; never a fabricated 0).
5. The bridge imports no LLM, embedding, memory, or sensory owner. It reads only published `08`
   stage-result fields and the injected temporal source.

## 8. Observability and Logging

No new logging mechanism. The projected line is part of the published `InternalThoughtRequest`
contract that flows through the existing kernel observability (R21) when a recorder is wired; no
new emitter, no `print`/`logging` in `src/`.

## 9. Validation Strategy

### 9.1 Real-LLM prompt validation (already complete)

Per `requirement-authoring-standard.md` §8.2, the expected R91 prompt was probed against the real
configured model **before** implementation. Cases live under `helios_v2/scripts/r91_probes/`; raw
inputs/outputs and judge notes under git-ignored `helios_v2/logs/prerun/r91_probes/`:

| Case | Intent | Verdict |
| --- | --- | --- |
| 01_anxiety | core: present-field unlocks content-level engagement | PASS |
| 02_grief | negative valence + high cortisol + low 5-HT | PASS |
| 03_joy | reverse valence + cross-visitor memory awareness | PASS |
| 04_anger | challenging content + no theatrical agreement | PASS |
| 05_silence | boundary: no speaker → must NOT hallucinate one | PASS |
| 06_continuity | meta-question + must name prior visitors | PASS (must_contain "小林") |
| 07_pre_r91_negative_control | falsifier: pre-R91 prompt reproduces failure | PASS (failure mode reproduced) |

### 9.2 Network-free unit/integration tests (added in this slice)

1. `InternalThoughtRequest` — None default, bounded validation, deterministic truncation.
2. `_build_messages` — line prepended iff set; None preserves byte-for-byte; LLM path threads it.
3. Bridge — focal-committed projection, no-commit honest absence, optional temporal pacing,
   FirstVersion bridge unchanged.

### 9.3 Regression

The full `pytest helios_v2/tests -q` (network-free) must stay green. No owner color / chain /
boundary change, so `OWNER_GUIDE`/`PROGRESS_FLOW` stay synced; `index.md` adds row 91; ROADMAP §10
marks R91 delivered.
