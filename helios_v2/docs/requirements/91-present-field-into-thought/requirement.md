# Requirement 91 - Present-Field Into the Internal Thought Prompt

## 1. Background and Problem

The 2026-06 real-LLM emotion test (89 Chinese-dialogue messages through the CLI driver, see ROADMAP
§9) produced one decisive empirical finding by capturing the raw `11` thought prompt:

```
Internal state: Neuromodulators: DA 0.55 NE 0.56 5-HT 0.37 ACh 0.36 Cort 0.53. Feeling: arousal 0.52,
valence 0.41, tension 0.55. Salience: aggregate 0.72, top dimension: social.
Autobiographical anchor: A thinking cycle concluded without outward action: ...
Continuation pressure is inactive for this cycle.
```

The operator's actual message text never appears. Inspection of `helios_v2/internal_thought/engine.py
_build_messages` confirms the `11` thought request renders only `internal_state_summary` (the salience
collapsed into numbers) plus the retrieval bundle's first hit summary plus the continuation flag. The
current stimulus content reaches `02→03→04→05/09/10` (where it is appraised into a salience number)
but is never rendered into the thinking LLM's user message as text. Helios appraises the message but
never reads it. The effect, repeated across 89 ticks: thoughts say "social salience high but nothing
in the present stream is a person, no incoming demand", almost no replies emit, every visitor's
content is lost. There is also no time/elapsed fact in the thought prompt at all (R55 `temporal_signal`
feeds only the `09` gate, not `11`).

A real-LLM probe under R91-shaped prompts (`scripts/r91_probes/01..07`, MiniMax-M3, max_tokens=2048,
strip_reasoning=on) shows that adding a `Present field` line carrying the operator's actual content +
elapsed pacing makes the model engage the content (it names 苏蕊/小林/阿哲/老周, tracks pre-defense
anxiety / grief / joy / anger, prepares meaningful Chinese replies, refuses to fabricate a speaker
when the present field is empty, and recalls visitors by name when the autobiographical anchor lists
them). The pre-R91 negative-control probe reproduces the failure pattern verbatim, confirming that the
missing present-field is the cause and adding it is the fix. The captured probe inputs/outputs and
judge notes live under git-ignored `helios_v2/logs/prerun/r91_probes/` and the case files under
`helios_v2/scripts/r91_probes/`.

## 2. Goal

Add an additive `present_field_summary` field to the `InternalThoughtRequest` contract that the
semantic-assembly composition bridge populates from the same-tick `08` `ReportableConsciousContent`
focal item (its real `focal_summary` + bounded `salient_tokens`) plus the real `temporal` owner's
elapsed-rest pacing fact, and that the `11` engine renders into the LLM user message as a
`Present field:` line, so the thinking LLM reads the actual current stimulus content and elapsed time.
The change is strictly additive: the legacy-constant assembly, the existing `11` byte-for-byte
behavior when the new field is absent, and every owner boundary remain unchanged. The full network-free
test suite stays green.

## 3. Functional Requirements

### 3.1 Contract (additive)

1. `InternalThoughtRequest` must gain one additive optional field
   `present_field_summary: str | None = None`. The default `None` must preserve the prior behavior
   byte-for-byte (no other field changes; no validation change for existing fields).
2. When a value is supplied, it must be non-empty (whitespace-only is rejected) and bounded in length
   (a hard upper bound, e.g. 600 characters, beyond which it is truncated with an explicit suffix);
   the upper bound and truncation suffix must be a single owner-defined constant.

### 3.2 Composition projection (owner-neutral, semantic-assembly only)

1. The `SemanticInternalThoughtRequestBridge` must populate `present_field_summary` from already
   published owner facts only:
   - the same-frame `reportable_conscious_content` `ReportableConsciousContent` (its
     `focal_summary` and `salient_tokens`) when a focal item exists, or the `no_commit_reason`
     when no focal item was committed,
   - the same-frame temporal pacing (`temporal_signal` from the `helios_v2.temporal`
     `TemporalSource` if wired, else a defined absent sentinel — never a fabricated number).
2. The projection must be owner-neutral: composition must read only published owner result fields,
   it must not interpret memory or salience semantics, must not call any LLM or embedding service,
   and must not invent a speaker when no focal content exists.
3. `FirstVersionInternalThoughtRequestBridge` (legacy-constant mode) must keep
   `present_field_summary=None`, so the legacy assembly is byte-for-byte unchanged.

### 3.3 `11` engine rendering

1. `InternalThoughtEngine._build_messages` must, when `request.present_field_summary` is non-None
   and non-empty, prepend a `Present field:` line to the LLM user message before the existing
   `Internal state:` / retrieval / continuation lines.
2. When `request.present_field_summary` is None, the user message must be byte-for-byte identical to
   the pre-R91 output (a falsifier the negative-control probe reproduces).
3. The system prompt must not change (that is `16`'s job and a separate, future requirement).

### 3.4 Owner boundaries

1. `11` keeps all judgment authority. The new field is text the model reads; `11` parses and decides
   exactly as before.
2. Composition holds no cognitive policy. It forwards published owner facts (08 focal content + 05
   feeling-tagged tokens + temporal pacing) into a bounded English line.
3. Memory content (10) and prompt-contract layers (16) are out of scope this slice. The
   present-field comes from `08`, which already integrates `02→06→07→08`; this requirement adds no
   new ownership and no `02`/`06`/`10` reach-through.

## 4. Non-Functional Requirements

1. Performance: the projection is one dict lookup + a small string assembly per fired tick; it must
   not change the per-tick cost characteristic measured in R83.
2. Reliability: missing `08` focal content (no_commit / inactive gate / pre-gate inactive) must
   produce an honest absent-content marker and must not raise; missing temporal source must produce
   a defined absent sentinel. There is no fabricated-content fallback.
3. Observability and logging: no new logging mechanism. No `print`/`logging` in `src/`; `21` stays
   the single logging owner.
4. Compatibility and migration: the contract change is additive and default-None; legacy-constant
   mode and existing semantic-assembly behavior outside the `11` user message are unchanged.

## 5. Code Behavior Constraints

1. Forbidden: composition fabricating a speaker, message, or time when none is present.
2. Forbidden: composition computing salience, memory ranking, or embedding inside the projection.
3. Forbidden: changing the system prompt or the v3 embodied prompt-contract layers in this slice.
4. Forbidden: any `02`/`06`/`10` reach-through inside the bridge (only published `08` and `temporal`
   facts).
5. The `present_field_summary` must respect the owner-defined length cap; if upstream content
   exceeds it, the truncation must be deterministic and carry an explicit suffix.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/internal_thought/contracts.py` — additive optional
   `present_field_summary` field + bounded validation.
2. `helios_v2/src/helios_v2/internal_thought/engine.py` — `_build_messages` prepends a
   `Present field:` line when the field is present.
3. `helios_v2/src/helios_v2/composition/bridges.py` —
   - `SemanticInternalThoughtRequestBridge.build_request` populates `present_field_summary` from
     `08` `ReportableConsciousContent` and the optional `temporal_source`.
   - `FirstVersionInternalThoughtRequestBridge.build_request` leaves it `None`.
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — wire the existing temporal source
   into the semantic thought-request bridge.
5. New focused tests under `helios_v2/tests/`:
   - `test_internal_thought_engine.py` — assert `_build_messages` prepends the `Present field:` line
     when set, and is byte-for-byte unchanged when None.
   - `test_internal_thought_contracts.py` — assert the additive validation (None ok, non-empty,
     length cap, truncation suffix).
   - `test_semantic_thought_request_bridge.py` (new or extension) — assert the bridge projects from
     real `08` content + temporal pacing, honestly reports absence, never fabricates.
6. Docs: `requirements/index.md` row 91; ROADMAP §10/§11.1 marked delivered;
   `OWNER_GUIDE`/`PROGRESS_FLOW` only if owner color or chain changes (this is additive and does
   not change either).

## 7. Acceptance Criteria

1. The `InternalThoughtRequest` accepts an optional bounded `present_field_summary`; default-None
   preserves all existing tests and behavior; over-cap input is deterministically truncated.
2. Under the semantic-memory assembly, every fired tick whose `08` committed a focal item produces a
   request whose `present_field_summary` carries that focal `focal_summary` (and bounded
   `salient_tokens`) verbatim, plus an elapsed pacing fact when the temporal source is wired.
3. When `08` did not commit a focal item, the projection emits an honest absent marker (no fabricated
   speaker), and the rest of the cycle still completes.
4. `_build_messages` includes a `Present field:` line in the LLM user message exactly when
   `present_field_summary` is non-None; with None, the user message is byte-for-byte the pre-R91
   form (falsifier reproduces the empirical failure).
5. Owner boundaries: the bridge does not import or call any `02`/`06`/`10`/embedding/LLM owner;
   `11` keeps all judgment; legacy-constant mode is unchanged.
6. The full network-free test suite stays green; new focused tests cover the additive paths.
7. The R91 design decision is validated by the real-LLM probe set under
   `helios_v2/scripts/r91_probes/` (cases shipped this requirement) and the captured outputs under
   the git-ignored `helios_v2/logs/prerun/r91_probes/`. Any subsequent prompt-shape change must be
   re-validated by the probe before merging (per `requirement-authoring-standard.md` §8.2).
