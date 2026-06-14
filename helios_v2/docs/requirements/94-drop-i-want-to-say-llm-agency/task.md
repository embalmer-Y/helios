# Task 94 — Drop `i_want_to_say`; LLM full agency over action + channel

> Implementation task breakdown for R94. Mirrors the project discipline:
> each task is a single coherent diff that compiles + tests green on its
> own. Tasks are ordered to minimize cascading churn (constant renames
> first, evidence field second, parser third, engine precedence fourth,
> prompt fifth, tests + probes last).

## T1. Constants rename in `contracts.py` (R94, prerequisite)

**File**: `src/helios_v2/internal_thought/contracts.py`

**Diff**:
- `INTENDED_REPLY_TEXT_MAX_CHARS` → `REPLY_TEXT_MAX_CHARS` (same value 2000).
- `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX` → `REPLY_TEXT_TRUNCATION_SUFFIX`
  (same value `"…(truncated)"`).
- Update the comment block above the constants: reframe from R93 / R93 P2
  narrative to R94 narrative (reply_text sub-detail of action_intent="reply").

**Acceptance**: `python -c "from helios_v2.internal_thought.contracts import
REPLY_TEXT_MAX_CHARS, REPLY_TEXT_TRUNCATION_SUFFIX; print(REPLY_TEXT_MAX_CHARS,
REPLY_TEXT_TRUNCATION_SUFFIX)"` prints `2000 …(truncated)`. The legacy
`INTENDED_REPLY_TEXT_*` names are gone.

**Why first**: every subsequent task imports the new constant name.

## T2. Evidence field swap in `engine.py` (R94, breaking)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `StructuredThoughtEvidence`:
- Remove `intended_reply_text: str = ""` field.
- Add `reply_text: str | None = None` field.
- Update the comment block: reframe the field as a sub-detail of
  `action_intent="reply"`, not an independent choice.

**Acceptance**: `python -c "from helios_v2.internal_thought.engine import
StructuredThoughtEvidence; ev = StructuredThoughtEvidence(thought_text='x',
model_sufficiency=0.5, wants_to_continue=False, continue_reason='',
intends_action=False, action_summary='', intends_self_revision=False,
self_revision_summary=''); print(ev.reply_text)"` prints `None`. The
legacy `intended_reply_text` attribute is gone.

**Why second**: T3 (parser) needs the new field name to populate.

## T3. Parser: replace `_optional_intended_reply_text` with `_optional_reply_text` (R94)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff**:
- Remove the `_optional_intended_reply_text` function.
- Add `_optional_reply_text` with the following semantics:
  - Field absent or `null` => return `None`.
  - Field is empty or whitespace-only string => return `None` (honest absence).
  - Field is a non-empty string => return trimmed value, deterministically
    truncated with `REPLY_TEXT_TRUNCATION_SUFFIX` when over
    `REPLY_TEXT_MAX_CHARS` cap.
  - Field is a non-string => raise `StructuredThoughtParseError`.
- Update the call site in `_parse_structured_thought`: replace
  `intended_reply_text = _optional_intended_reply_text(payload)` with
  `reply_text = _optional_reply_text(payload)`. Pass `reply_text=<value>`
  to the `StructuredThoughtEvidence(...)` constructor.
- The `i_want_to_say` literal in the payload is silently ignored (no raise,
  no `intended_reply_text` field — just a no-op read).

**Acceptance**: an envelope with `reply_text="hello"` parses to
`evidence.reply_text == "hello"`. An envelope with
`i_want_to_say="hello"` (legacy) parses to
`evidence.reply_text is None` (the field is ignored). A non-string
`reply_text` raises `StructuredThoughtParseError`.

## T4. Engine precedence rewrite in `_emit_proposal` (R94, core)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `_derive_thought_judgment` (the `_emit_proposal` block):

**Remove**:
- The `reply_compat_path` boolean (the `evidence is not None and not
  tool_intent and bool(evidence.intended_reply_text) and bool(target_user_id)`
  check).
- The `reply_explicit_path` boolean (the `evidence.action_intent ==
  ACTION_INTENT_REPLY and bool(target_user_id)` check — its logic is
  subsumed by the new combined check below).
- The `implicit_reply_intent = reply_compat_path or reply_explicit_path`
  boolean (no longer needed; the new check is inline).

**Add** (or rewrite) the reply branch to require all three signals:

```python
reply_text = evidence.reply_text
reply_explicit_path = (
    evidence.action_intent == ACTION_INTENT_REPLY
    and reply_text is not None
    and bool(target_user_id)
)
```

The reply proposal block (later in `_emit_proposal`) is rewritten to
use the new `reply_text` variable name in place of `evidence.intended_reply_text`.
The `op_params={"outbound_text": reply_text, "target_user_id":
target_user_id}` is unchanged structurally.

**Tool intent resolution** (R93 P2): consolidate the `tool_intent_resolved
= tool_intent or explicit_tool_path_via_intent` boolean into a single
`_resolved_tool_intent(evidence)` helper for clarity (optional refactor;
the behavior is unchanged).

**Acceptance**: 
- `action_intent="reply" + reply_text="hi" + target` ⇒ reply proposal with
  `op_params={"outbound_text": "hi", "target_user_id": <target>}`.
- `action_intent="reply" + reply_text=None` ⇒ `action_proposal is None`
  (the model picked "reply" but supplied no text; the owner doesn't fabricate).
- `action_intent="reply" + reply_text="hi" + no target` ⇒
  `action_proposal is None` (no fabricated target).
- `action_intent="no_action" + reply_text="hi" + target` ⇒
  `action_proposal is None` (`no_action` wins).
- `action_intent=None + i_want_to_say="hi" + target` (legacy compat payload)
  ⇒ `action_proposal is None` (compat path removed).
- `action_intent="tool"` (without `i_want_to_use_tool=true`) ⇒ tool proposal
  (R93 P2 path preserved).
- `intends_tool_use=true + tool_op="fs_write" + action_intent="reply" +
  reply_text="hi"` ⇒ tool proposal wins (R85 precedence preserved).
- `evidence is None` (deterministic offline path) ⇒ legacy reply with
  `outbound_text=thought.content` + `preferred_channels=("cli",)`
  (Phase-1 acceptance criterion preserved).

**Why fourth**: this is the architectural change. After T4 the engine
behaves per R94; T5 updates the prompt; T6-T8 update the tests.

## T5. System prompt rewrite in `_build_messages` (R94, prompt surface)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `LlmBackedInternalThoughtPath._build_messages`:
- Remove the schema line for `"i_want_to_say"`.
- Restructure the schema to lead with `action_intent`. The exact prompt
  content is in `design.md` §3.3.
- Rewrite the transport clause to be `action_intent` + `reply_text` led
  (verbatim from `design.md` §3.3).
- Strengthen the "Action class is a CHOICE" paragraph (the R93 P2
  paragraph is preserved and made more emphatic).

**Acceptance**:
- The system prompt does not contain the literal string `i_want_to_say`.
- The schema block lists `action_intent` as the first action-class field
  and `reply_text` as a sub-detail of `action_intent="reply"`.
- The transport clause references `action_intent + reply_text +
  target_user_id`, not `i_want_to_say + cli`.

## T6. Update shared test fixture `envelope()` (R94, prerequisite for tests)

**File**: `tests/_internal_thought_test_fixtures.py`

**Diff**:
- `i_want_to_say: Any = None` param → `reply_text: Any = None`.
- Inside the helper: `if i_want_to_say is not None: payload["i_want_to_say"]
  = i_want_to_say` → `if reply_text is not None: payload["reply_text"] =
  reply_text`.
- Update the docstring to reflect the R94 schema.

**Acceptance**: `inspect.signature(envelope)` lists `reply_text` (not
`i_want_to_say`). Calling `envelope(reply_text="hi")` produces a payload
with `reply_text="hi"`; calling `envelope()` produces a payload without
the `reply_text` key.

## T7. Update test files using `i_want_to_say` (R94, test rewrite)

**Files** (in dependency order — internal-thought-engine first since
other tests depend on its fixtures):

1. `tests/test_internal_thought_engine.py`
   - `FakeThoughtGateway.i_want_to_say` field → `reply_text` field.
   - `JsonThoughtGateway` payload helper: `i_want_to_say` key → `reply_text`
     key in the constructed envelope dict.
   - Any other `i_want_to_say` literals in test code → `reply_text`.
2. `tests/test_runtime_composition.py`
   - `FakeThoughtProvider.i_want_to_say: str = "operator-addressed reply
     content"` → `reply_text: str = "operator-addressed reply content"`.
   - The `_build_envelope()` helper in the provider: `i_want_to_say` key →
     `reply_text` key.
   - The `FakeProvider` always sets `action_intent="reply"` when
     `reply_text` is set (the R94 path requires both).
3. `tests/test_internal_thought_implicit_reply_intent.py`
   - Rename file to `tests/test_internal_thought_explicit_reply_intent.py`
     (mirroring the R94 architectural rename: "implicit" → "explicit").
   - All test payloads: `i_want_to_say="<text>"` →
     `reply_text="<text>", action_intent="reply"`.
   - The "compat path" test (`i_want_to_say` set without `action_intent`)
     is removed (R94 has no compat path; the test no longer applies).
4. `tests/test_internal_thought_evidence_intended_reply.py` → **RENAME to**
   `tests/test_internal_thought_evidence_reply_text.py`.
   - All assertions on `evidence.intended_reply_text` →
     `evidence.reply_text` (with `is None` for the absence case).
   - The `StructuredThoughtEvidence` constructor calls update to use the
     new kwarg name.
5. `tests/test_internal_thought_parse_i_want_to_say.py` → **RENAME to**
   `tests/test_internal_thought_parse_reply_text.py`.
   - All `_envelope(i_want_to_say=...)` calls → `_envelope(reply_text=...)`.
   - The "field absent" / "field null" / "field empty" tests now assert
     `ev.reply_text is None` (not `ev.intended_reply_text == ""`).
   - The "non-string raises" test uses `reply_text=42` instead of
     `i_want_to_say=42`.
   - A new test is added: `_envelope(i_want_to_say="legacy")` (the legacy
     field is silently ignored) → `ev.reply_text is None`.
   - Constant imports: `INTENDED_REPLY_TEXT_*` → `REPLY_TEXT_*`.
6. `tests/test_runtime_stage_chain_implicit_reply.py` → **RENAME to**
   `tests/test_runtime_stage_chain_explicit_reply.py`.
   - `_ReplyThoughtProvider.i_want_to_say: str | None = "hello operator"`
     → `reply_text: str | None = "hello operator"`.
   - The `envelope()` construction in the provider includes
     `action_intent="reply"` (the R94 path requires it).
   - The end-to-end test's assertions on `ActionDecision.op_params`
     remain structurally identical (`outbound_text` + `target_user_id`).
   - The "explicit tool wins" test is preserved (just the envelope
     construction is updated).
7. `tests/test_internal_thought_emit_proposal_phase2.py`
   - All test payloads: `i_want_to_say=...` → `reply_text=...` +
     `action_intent="reply"`.
   - The "compat path" test (i_want_to_say without action_intent) is
     removed (no compat path in R94).
   - New tests added (R94-specific):
     - `reply_text` set without `action_intent` ⇒ `action_proposal is None`.
     - `action_intent="reply"` + no `reply_text` ⇒ `action_proposal is None`.
     - `action_intent="no_action"` + `reply_text` set ⇒ `action_proposal is None`.

**Acceptance**: `pytest tests/test_internal_thought_engine.py
tests/test_runtime_composition.py tests/test_internal_thought_*.py
tests/test_runtime_stage_chain_explicit_reply.py` passes with all
existing + R94 assertions green.

## T8. Add the structural test (R94, regression guard)

**New file**: `tests/test_internal_thought_no_i_want_to_say_in_prompt.py`

**Tests**:
1. `test_system_prompt_does_not_mention_i_want_to_say`: drives
   `LlmBackedInternalThoughtPath._build_messages` on a sample request
   and asserts the system + user message contents do not contain the
   literal `i_want_to_say`. Uses `assertNotIn` for clarity.
2. `test_source_code_does_not_contain_i_want_to_say_literal`: reads
   `src/helios_v2/internal_thought/engine.py` and
   `src/helios_v2/internal_thought/contracts.py` as text, asserts
   `i_want_to_say` is not present. (This catches a future regression
   where someone reintroduces the field in a code path the prompt-level
   test doesn't cover.)
3. `test_envelope_fixture_does_not_accept_i_want_to_say_kwarg`: uses
   `inspect.signature` to assert `_internal_thought_test_fixtures.envelope`
   has no parameter named `i_want_to_say`.

**Acceptance**: `pytest tests/test_internal_thought_no_i_want_to_say_in_prompt.py`
passes. A deliberate test that re-introduces `i_want_to_say` (e.g. in a
throwaway string in the source) causes at least one of the three
assertions to fail.

## T9. Add the R94 emit_proposal precedence test file (R94, regression guard)

**New file**: `tests/test_internal_thought_emit_proposal_r94.py`

**Tests** (mirroring the R93 P2 `test_internal_thought_emit_proposal_phase2.py`
style):
1. `test_action_intent_reply_with_reply_text_and_target_builds_reply`:
   explicit-reply path, full success.
2. `test_action_intent_reply_without_reply_text_yields_none`: explicit
   `action_intent="reply"` but no `reply_text` ⇒ no proposal (R94 strict).
3. `test_action_intent_reply_with_reply_text_but_no_target_yields_none`:
   no operator, no fabrication.
4. `test_action_intent_no_action_with_reply_text_yields_none`: `no_action`
   overrides `reply_text`.
5. `test_reply_text_set_without_action_intent_yields_none`: the R93
   compat path is removed; setting `reply_text` alone is silent.
6. `test_legacy_i_want_to_say_payload_ignored`: an envelope with only
   `i_want_to_say` (no `action_intent`, no `reply_text`) yields
   `action_proposal is None` (R93 compat path removed).
7. `test_explicit_tool_wins_over_action_intent_reply`: R85 precedence
   preserved.
8. `test_deterministic_offline_path_unchanged`: `evidence is None` still
   produces the legacy `outbound_text=thought.content` reply.

**Acceptance**: the 8 tests above pass, and the R93 P2
`test_internal_thought_emit_proposal_phase2.py` is updated to no longer
assert the removed compat-path behavior.

## T10. Update real-LLM probes (R94, prompt surface)

**Files** (in `scripts/r93_probes/`):

1. `01_basic_reply.json`
   - The system_prompt captured in the JSON is updated to the R94
     variant (action_intent-led schema, no `i_want_to_say` line,
     rewritten transport clause).
   - `must_contain`: `["苏蕊", "i_want_to_say"]` → `["苏蕊", "reply_text"]`.
   - `user_prompt` and other fields are unchanged.
2. `02_silence_negative_control.json`
   - The system_prompt captured is updated to the R94 variant.
   - `must_contain` / `must_not_contain` are unchanged.
3. `03_action_choice.json`
   - The system_prompt captured is updated to the R94 variant.
   - `must_contain_any`: `["action_intent", "reply", "i_want_to_say"]` →
     `["action_intent", "reply", "reply_text"]`.
4. `04_no_action_when_unmoved.json`
   - The system_prompt captured is updated to the R94 variant.
   - `must_contain` / `must_not_contain` are unchanged.
   - The `_notes` field is updated to call out the R94 evaluation focus:
     compare the `no_action` choice rate to the R93 P2 baseline.

**Acceptance**: each JSON parses (valid JSON; updated prompts reflect
the R94 schema). Running `python scripts/run_llm_prompt_probe.py
--case-file scripts/r93_probes/01_basic_reply.json` produces a
completion that includes `reply_text` (not `i_want_to_say`).

## T11. Re-run all 4 real-LLM probes and record results (R94, evaluation)

**Command** (per probe):
```bash
PYTHONIOENCODING=utf-8 python scripts/run_llm_prompt_probe.py \
    --case-file scripts/r93_probes/01_basic_reply.json \
    --report logs/r94_probe_01.json
```

Repeat for 02, 03, 04. The R94 probe outputs are written to
`logs/r94_probe_NN.json`.

**Evaluation**:
- Probe 01: assert the model produces `reply_text` (not `i_want_to_say`)
  with operator-addressed content for `苏蕊`.
- Probe 02: assert the model leaves `action_intent` and `reply_text` both
  null/empty on an interoception-only tick.
- Probe 03: assert the model produces `action_intent` + `reply_text`
  when the operator asks for advice.
- Probe 04 (focus): compare the `no_action` choice rate to the R93 P2
  baseline (~80%). If the rate holds or improves, R94 is signed off. If
  the rate regresses, escalate to R96 for root-cause investigation.

**Acceptance**: 4/4 probes pass the structural assertions (correct
field names, correct `action_intent` choices, no fabricated operator
replies). The probe 04 evaluation note is written to
`docs/requirements/94-drop-i-want-to-say-llm-agency/probe_04_comparison.md`.

## T12. Update cross-file documentation (R94, sync)

**Files**:
1. `docs/requirements/index.md` — new R94 row, Maturity column "in
   progress" → "shipped" once tests + probes + commit land.
2. `docs/OWNER_GUIDE.md` / `docs/OWNER_GUIDE.zh-CN.md` — `11` next-step
   section updated to drop the `i_want_to_say` mention; status header
   sync.
3. `docs/PROGRESS_FLOW.en.md` / `docs/PROGRESS_FLOW.zh-CN.md` —
   last-synced sync.
4. `docs/ARCHITECTURE_BOUNDARIES.md` — last-synced + a brief
   migration-history note (R93 introduced `i_want_to_say`; R93 P2
   de-emphasized it with `action_intent`; R94 removes it).
5. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — `gap_execution_closure` row
   updated to note that the dialog-reply leg of the local outward-
   execution loop is now driven by explicit
   `action_intent + reply_text`, not the legacy `i_want_to_say`
   heuristic.
6. `docs/ROADMAP.zh-CN.md` — W2.5 R94 row updated to "已交付"; the
   subsequent R95/R96/R97 numbering is preserved.

**Acceptance**: every doc file's `Last synced` line is updated to
`2026-06`. The R94 row in `requirements/index.md` reads as
"shipped". The R94 W2.5 row in `ROADMAP.zh-CN.md` is moved from
"推进中" to "已交付".

## T13. Run full test suite (R94, network-free baseline)

**Command**:
```bash
cd helios_v2 && PYTHONIOENCODING=utf-8 python -m pytest \
    -x --no-header -q 2>&1 | tail -40
```

**Expected**:
- ≥ 1195 + new tests passed (R94 adds ~8 new tests via T8 + T9).
- 4 pre-existing `wall_clock_profile` skipped tests remain skipped
  (out of R94 scope; pre-existing).
- The composition owner-boundary guard and the no-adhoc-logging guard
  remain green (no new module imports `06` / `10` / `13`; no new
  `print()` / `logging.info` calls).

**Acceptance**: `tail -40` output ends with
`===== N passed, 4 skipped in M.Ms =====` where N ≥ 1203.

## T14. Commit and push (R94, release)

**Sequence**:
1. `git status --short` to verify the diff covers T1–T12.
2. `git add -A` to stage the change set.
3. `git commit -m "R94: drop i_want_to_say; LLM full agency over action + channel" \
        -m "..."` with a body that summarizes the R94 changes.
4. `git push origin main` to push to the remote.

**Acceptance**: `git log --oneline -1` shows the R94 commit; `git
status` is clean; the remote `main` branch is one commit ahead of the
local clone.

## Task dependency graph

```text
T1 (constants) ──► T2 (evidence) ──► T3 (parser) ──► T4 (engine)
                                                         │
                                                         ▼
                                              T5 (system prompt)
                                                         │
                                                         ▼
                                            T6 (envelope fixture)
                                                         │
                                                         ▼
                                            T7 (test files)
                                                         │
                                                         ▼
                                  ┌──────────────────────┼──────────────────────┐
                                  ▼                      ▼                      ▼
                              T8 (structural       T9 (emit_proposal      T10 (probes)
                                  test)               r94 test)
                                  │                      │                      │
                                  └──────────────────────┼──────────────────────┘
                                                         ▼
                                                T11 (re-run probes)
                                                         │
                                                         ▼
                                                T12 (docs sync)
                                                         │
                                                         ▼
                                                T13 (full suite)
                                                         │
                                                         ▼
                                                T14 (commit + push)
```

## Estimated scope

- **Source changes**: 2 files, ~80 lines net diff (mostly in
  `engine.py`).
- **Test changes**: 7 files modified, 2 new files (T8 + T9).
- **Probe changes**: 4 JSON files.
- **Doc changes**: 6+ files.
- **Test count delta**: +8–10 new tests (T8 + T9 + the
  end-to-end rename to `explicit_reply`).
- **Total diff size**: ~250–300 lines across 19 files (estimate).
