# Requirement 93 - Reliable Reply Loop From `i_want_to_say` — Task

## 1. Task Breakdown

R93 lands as six small ordered slices. Each slice is independently testable
and the full-suite gate runs after each one to catch regressions early.

### T1 — Contract: `intended_reply_text` field on `StructuredThoughtEvidence`

- Modified: `src/helios_v2/internal_thought/contracts.py`.
- Adds module-level constants `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` and
  `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"`.
- Adds additive optional field `intended_reply_text: str = ""` to
  `StructuredThoughtEvidence`.
- New test: `tests/test_internal_thought_evidence_intended_reply.py` (≈ 5 cases:
  default empty, accepted non-empty, frozen, length cap, deterministic suffix).

### T2 — Parser: read `i_want_to_say` from envelope

- Modified: `src/helios_v2/internal_thought/engine.py` `_parse_structured_thought`.
- Reads optional `i_want_to_say` per design §3.2: absent / null / empty /
  whitespace-only -> `""`; non-empty trimmed string -> stored (over-cap
  truncated); non-string -> `StructuredThoughtParseError`.
- New test: `tests/test_internal_thought_parse_i_want_to_say.py` (≈ 8 cases).
- Validation: `pytest tests/test_internal_thought_parse_i_want_to_say.py
  tests/test_internal_thought_engine.py -q` is green.

### T3 — Composition: `_current_operator_id(frame)` projection

- Modified: `src/helios_v2/composition/bridges.py`.
- Adds the owner-neutral `_current_operator_id(frame)` helper per design §3.5.
- Adds `current_operator_id` key into the `prompt_contract_summary` dict in
  both `SemanticInternalThoughtRequestBridge.build_request` and
  `FirstVersionInternalThoughtRequestBridge.build_request`.
- New test: `tests/test_composition_current_operator_id.py` (≈ 6 cases:
  earliest external wins, internal modalities skipped, empty when no `02`,
  empty when only internal stimuli, both bridges add the key).

### T4 — Engine: implicit-reply branch in `_emit_proposal`

- Modified: `src/helios_v2/internal_thought/engine.py` `_emit_proposal`.
- Adds the implicit-reply branch per design §3.3 with the explicit-tool
  precedence rule and the silent-when-operator-empty rule.
- New test: `tests/test_internal_thought_implicit_reply_intent.py` (≈ 8
  cases: implicit reply built when `i_want_to_say` set + operator present;
  silent when operator absent; explicit `tool_op` wins; legacy fallback path
  unchanged when `evidence is None`; both `intended_reply_text` and
  `model_intends_action` true => implicit reply path; continuation requested
  takes precedence over both).

### T5 — System prompt: tell the model `i_want_to_say` is transported

- Modified: `src/helios_v2/internal_thought/engine.py` `_build_messages`.
- Adds the explicit `i_want_to_say` schema line and the transport-clause
  paragraph per design §3.4. Legacy fallback (no envelope) path is unchanged.
- New test: `tests/test_internal_thought_build_messages_reply_clause.py`
  (≈ 3 cases: system prompt now contains the transport clause; the
  `i_want_to_say` schema entry exists; user message unchanged for both legacy
  and present-field cases — backward compatibility).

### T6 — End-to-end smoke + real-LLM probes + docs sync

- New: `tests/test_runtime_stage_chain_implicit_reply.py` end-to-end test
  using the channel-bound semantic assembly + a fake provider returning
  `i_want_to_say="hello"` to verify a real CLI sink dispatch occurs with the
  reply text + `executed` continuity record.
- New: `scripts/r93_probes/01_basic_reply.json` (positive control) and
  `scripts/r93_probes/02_silence_negative_control.json` (negative control).
- Documentation sync per cross-file rule §8 / §8.1:
  `docs/requirements/index.md`, `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`,
  `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md`,
  `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`,
  `ROADMAP.zh-CN.md`.

## 2. Dependencies

| Task | Depends on |
| --- | --- |
| T1 | (none) |
| T2 | T1 |
| T3 | (none — composition projection is independent of evidence shape) |
| T4 | T1, T2, T3 (needs the field, the parsed value, and the operator id) |
| T5 | (none — pure system-prompt update; semantically depends on T4 but parsing/emission still works without T5) |
| T6 | T1–T5 (end-to-end test) |

Independent slices T1, T3, T5 can land in parallel; T2 follows T1; T4 follows
T1+T2+T3; T6 follows everything.

## 3. Files and Modules

### 3.1 Modified code

- `src/helios_v2/internal_thought/contracts.py`
- `src/helios_v2/internal_thought/engine.py`
- `src/helios_v2/composition/bridges.py`

### 3.2 New tests

- `tests/test_internal_thought_evidence_intended_reply.py`
- `tests/test_internal_thought_parse_i_want_to_say.py`
- `tests/test_composition_current_operator_id.py`
- `tests/test_internal_thought_implicit_reply_intent.py`
- `tests/test_internal_thought_build_messages_reply_clause.py`
- `tests/test_runtime_stage_chain_implicit_reply.py`

### 3.3 New scripts

- `scripts/r93_probes/01_basic_reply.json`
- `scripts/r93_probes/02_silence_negative_control.json`

### 3.4 Documentation

- `docs/requirements/93-reply-loop-from-i-want-to-say/{requirement.md, design.md, task.md}`
- `docs/requirements/index.md`
- `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`
- `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md`
- `docs/ROADMAP.zh-CN.md`

## 4. Implementation Order

1. T1 — contract field (foundation; everything else imports from it)
2. T2 — parser reads the field
3. T3 — composition projection (independent; can run in parallel with T2)
4. T4 — implicit-reply branch in `_emit_proposal`
5. T5 — system prompt clause
6. T6 — end-to-end + probes + docs sync

## 5. Validation Plan

### 5.1 Per-task focused validation

| Task | Command |
| --- | --- |
| T1 | `pytest helios_v2/tests/test_internal_thought_evidence_intended_reply.py -q` |
| T2 | `pytest helios_v2/tests/test_internal_thought_parse_i_want_to_say.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T3 | `pytest helios_v2/tests/test_composition_current_operator_id.py -q` |
| T4 | `pytest helios_v2/tests/test_internal_thought_implicit_reply_intent.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T5 | `pytest helios_v2/tests/test_internal_thought_build_messages_reply_clause.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T6 | `pytest helios_v2/tests/test_runtime_stage_chain_implicit_reply.py helios_v2/tests/test_runtime_stage_chain.py -q` + the real-LLM probe runs |

### 5.2 Full-suite gate (closes the change set)

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests -q
```

Expected outcome: ≥ 1107 + new R93 tests passed, 4 skipped, 0 failed,
0 errors. The composition owner-boundary guard and the no-ad-hoc-logging
guard must both stay green.

## 6. Completion Criteria

R93 is complete when ALL of the following hold:

1. `_parse_structured_thought` reads `i_want_to_say` per design §3.2;
   `StructuredThoughtEvidence.intended_reply_text` carries the parsed value.
2. `_emit_proposal` builds an implicit `reply_message` tool intent with
   `op_params={"outbound_text", "target_user_id"}` when the conditions in
   design §3.3 hold; explicit `tool_op` (R85) takes precedence; missing
   operator id silently abstains.
3. Composition projects `current_operator_id` from the same-frame `02`
   external stimulus into the `prompt_contract_summary` of both internal-
   thought request bridges.
4. `_build_messages` includes the new schema line and transport clause; the
   model can know that `i_want_to_say` is transported as a reply.
5. End-to-end test: a fake provider returning `i_want_to_say="hello"`
   under the channel-bound semantic assembly produces a real CLI sink
   dispatch carrying the reply text and an `executed` continuity record.
6. The legacy `assemble_runtime()` deterministic offline path remains
   byte-for-byte unchanged. The pre-R93 network-free test suite (1107
   passed / 4 skipped) is green; the new R93 tests are green; the
   composition owner-boundary guard and the no-ad-hoc-logging guard are
   green.
7. The real-LLM probe `scripts/r93_probes/01_basic_reply.json` shows the
   model fills `i_want_to_say` with operator-addressed reply text after
   the new system-prompt clause; the negative-control probe shows the model
   leaves the field null/empty when no operator is present.
8. `docs/requirements/index.md`, both `OWNER_GUIDE` files, both
   `PROGRESS_FLOW` maps, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`, and `ROADMAP.zh-CN.md` are updated
   in the same change set.
