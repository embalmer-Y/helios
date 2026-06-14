# Requirement 94 — Drop `i_want_to_say`; LLM full agency over action + channel

## 1. Background and Problem

R93 Phase 2 (commit `e258926`, 2026-06) successfully closed the "confiding machine"
pattern: with the new `action_intent` envelope field (`reply` / `tool` / `no_action`)
and the planner's `target_user` → `preferred` → `iteration-order` priority, real-LLM
emotion probes (probe 04) showed the model can now legitimately choose `no_action`
on a low-salience "ok" stimulus, dropping the previous 97%-reflexive-reply pattern to
a deliberate-chooser pattern.

But the underlying design still has a structural flaw: the R93 Phase 1 `i_want_to_say`
envelope field is still part of the schema. The field name itself encodes a design
bias — **"want to say"** literally prompts the model to say something. Inspecting
the post-Phase 2 R93 captured envelopes and the probe outputs:

1. **Models reflexively fill `i_want_to_say`** even when they have not picked
   `action_intent="reply"`. In the 04 negative-control probe (low-salience "ok"
   stimulus) the model successfully picked `no_action`, but the envelope was still
   sometimes accompanied by an `i_want_to_say` text. The model engages the field
   as a side effect of the schema even when its primary action choice is silent.
2. **The R93 Phase 2 compat path is structurally vulnerable.** Phase 2 keeps
   `action_intent=None + i_want_to_say set` as a Phase-1 backward-compat reply
   trigger. This means: any model that fills `i_want_to_say` *implicitly* causes
   a reply, even when its `action_intent` is "no_action" or absent. The owner
   enforces the precedence (`explicit_no_action` wins), but the schema still
   invites the conflict.
3. **Field name is not symmetric with action taxonomy.** "I want to say" is
   reply-specific; there is no parallel field name for "I want to act on a tool"
   (the `i_want_to_use_tool` family exists, but it doesn't share the same
   "want to X" framing). The reply path is privileged by naming.
4. **Empirical observation (R93 Phase 2 evaluation):** the action_intent="no_action"
   probe 04 worked, but only because the model's "internal judgment" was strong
   enough to override the implicit `i_want_to_say` field. The bias is structural,
   not absolute; it should be removed at the design level, not left to the model's
   discipline to overcome.

The R93 Phase 2 backward-compat fallback (the `reply_compat_path` branch in
`_emit_proposal`) was a deliberate Phase-1 → Phase-2 migration aid. R94 retires
that aid: **the `i_want_to_say` field is removed from the schema entirely.** The
model's reply content moves to a generic `reply_text` field that is *only*
relevant when `action_intent="reply"`.

## 2. Goal

Eliminate the `i_want_to_say` field's structural bias in the `11` internal-thought
schema, so the LLM's reply / tool / no_action choice is driven by `action_intent`
alone, not by a reply-specific field name. Concretely:

1. Remove the top-level `i_want_to_say` field from the model's envelope schema
   (parser, evidence field, system-prompt schema line, transport clause).
2. Add a new optional `reply_text: str | None` field on `StructuredThoughtEvidence`
   that the model uses to declare what text to send *when it has already picked
   `action_intent="reply"`*. The field is silent-when-unused (only consumed in
   the explicit-reply branch).
3. Remove the R93 Phase 2 backward-compat `reply_compat_path` in
   `_emit_proposal`. The reply proposal is now constructed *only* when:
   - the model asserts `action_intent="reply"`, AND
   - the model supplies a non-empty `reply_text`, AND
   - a target user id is resolved (model-supplied `target_user_id` or
     composition-projected `current_operator_id`).
4. Keep `action_intent` as the sole primary action-class indicator. The model
   MUST pick an action class; the legacy `proposed_action.intends_action` flag
   remains a content hint but does not drive a proposal on its own.
5. Update the system prompt to lead with the action-class choice and remove all
   mention of `i_want_to_say`. The transport clause (now keyed on
   `action_intent="reply" + reply_text`) is rewritten.
6. Add a structural assertion test (`test_internal_thought_no_i_want_to_say_in_prompt.py`)
   that the system prompt and evidence-construction code never reference the
   `i_want_to_say` literal — a future regression that reintroduces the field is
   caught at test time.
7. Re-run all 4 R93 real-LLM probes (01 positive reply, 02 silence negative
   control, 03 action choice, 04 no-action when unmoved) with the updated
   schema. Compare the 04 negative-control output to the R93 Phase 2 baseline;
   if the `no_action` choice is *less* stable on R94, escalate to R96 (Chinese
   appraisal grounding) as a root-cause investigation.

## 3. Functional Requirements

### 3.1 Envelope parsing: drop `i_want_to_say`, add `reply_text`

1. `_parse_structured_thought` no longer reads the top-level `i_want_to_say`
   field. The literal `i_want_to_say` string is not in the parser's accept-set;
   a payload that contains `i_want_to_say` is parsed normally (the field is
   ignored, not rejected) — this is for forward-compat with any in-flight
   model checkpoint that still produces the field.
2. `_parse_structured_thought` reads the new optional top-level `reply_text`
   field as a string. Accepted shapes:
   1. Absent or `null` => `reply_text=None`.
   2. Empty or whitespace-only string => `reply_text=None` (honest absence;
      the model did not actually supply reply text).
   3. Non-empty string => `reply_text=<trimmed value>`, deterministically
      truncated with `REPLY_TEXT_TRUNCATION_SUFFIX` when over the
      `REPLY_TEXT_MAX_CHARS` cap.
   4. Non-string (e.g. number, list, object) => parser raises the existing
      `StructuredThoughtParseError` (no silent coercion).
3. `StructuredThoughtEvidence` field changes (a strict additive → breaking
   transition):
   1. **Removed**: `intended_reply_text: str = ""` field (R93/R93 P2).
   2. **Added**: `reply_text: str | None = None` field.
4. The owner-threaded constants rename:
   1. `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` → `REPLY_TEXT_MAX_CHARS = 2000`
      (same value; new name).
   2. `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"` → 
      `REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"` (same value; new name).
5. The R93 Phase 2 `target_user_id` field is preserved unchanged (256 chars
   cap, same parser semantics, same role in reply path).

### 3.2 `_emit_proposal` precedence rewrite

1. The new precedence for emitting a proposal is:
   1. **Explicit `tool_op` (R85)** wins when `evidence.intends_tool_use and
      bool(evidence.tool_op)`. The proposal is a tool action; no reply is
      constructed.
   2. **Explicit `action_intent="tool"`** wins when the model asserts it,
      even without `i_want_to_use_tool=true` set. The proposal is a tool
      action with `op_params=evidence.tool_params` plus `target_user_id` if
      resolved.
   3. **Explicit `action_intent="reply"`** fires when:
      - `evidence.action_intent == "reply"`, AND
      - `evidence.reply_text is not None` (non-empty), AND
      - the resolved `target_user_id` is non-empty.
      The proposal is a `reply_message` tool intent with
      `op_params={"outbound_text": evidence.reply_text, "target_user_id":
      <resolved>}`.
   4. **Explicit `action_intent="no_action"`** closes the cycle internal-only
      regardless of every other signal.
   5. **`action_intent is None`** (the model left the field unset) closes the
      cycle internal-only. There is no compat path that auto-constructs a
      reply from `i_want_to_say` (R93's compat path is removed).
   6. **`evidence is None`** (the deterministic offline path) is the only
      remaining path that produces a default reply proposal: the legacy
      `assemble_runtime()` deterministic path keeps its Phase-1 acceptance
      criterion (reply with `outbound_text=thought.content` +
      `preferred_channels=("cli",)`). The R93 Phase 2 docstring that
      documented "this branch is unreachable for the LLM-backed path" remains
      accurate.
2. The `reply_compat_path` branch is removed entirely. There is no path in
   `_emit_proposal` that references `evidence.intended_reply_text`; the field
   no longer exists.
3. The `_emit_proposal` emits at most one proposal per tick (unchanged from
   R85 / R93 / R93 P2).

### 3.3 `target_user_id` resolution for reply (unchanged from R93 P2)

1. The reply's `target_user_id` is resolved in this order (R93 P2 convention
   preserved):
   1. `evidence.target_user_id` if the model explicitly set it.
   2. `request.prompt_contract_summary.get("current_operator_id", "")` as the
      composition-projected default.
2. If the resolved `target_user_id` is empty, the explicit-reply branch is
   silent (no proposal), regardless of `action_intent` or `reply_text`.
3. The composition projection of `current_operator_id` from `02
   sensory_ingress` is owner-neutral and unchanged. The projection is now
   *only* used as a default for `target_user_id` resolution; it is not
   auto-promoted to the reply proposal.

### 3.4 System prompt rewrite

1. `_build_messages` removes the `i_want_to_say` schema line entirely.
2. The system prompt's schema description is rewritten to lead with
   `action_intent`:
   ```
   "action_intent": "reply" | "tool" | "no_action" (REQUIRED),
   "reply_text": "<only when action_intent is reply, the text to send>",
   "target_user_id": "<optional override of current operator id, for reply/tool>",
   "i_want_to_use_tool": <bool>, "tool_op": "<optional>", "tool_params": {<optional>},
   ```
3. The transport clause is rewritten:
   - **Before (R93 P2)**: "When you set `i_want_to_say` to a non-empty string,
     the runtime will transport that text as a `reply_message`..."
   - **After (R94)**: "When you set `action_intent` to `reply` AND supply
     `reply_text`, the runtime will transport that text as a `reply_message`
     to the resolved `target_user_id` through the connected channel."
4. The "Action class is a CHOICE" paragraph (added in R93 P2) is preserved and
   strengthened. The "reply / tool / no_action" taxonomy is now the primary
   classification; `reply_text` is a sub-detail of `action_intent="reply"`,
   not an independent choice.
5. The legacy schema (`thought` / `sufficiency` / `wants_to_continue` /
   `proposed_action` / `self_revision` / `hormone_response_i_predict`) is
   unchanged; the additive R93/R93 P2 fields are reformulated; `i_want_to_say`
   is gone.

### 3.5 Test helper / fixture: `envelope()` signature

1. The shared `_internal_thought_test_fixtures.envelope()` helper's `i_want_to_say`
   parameter is replaced with a `reply_text` parameter.
2. The parameter accepts `None` (omit), an empty string, or a non-empty string;
   the helper emits the `reply_text` field in the JSON payload when non-`None`
   (mirroring the R93 P2 `action_intent` parameter convention).
3. Existing call sites that pass `i_want_to_say="<text>"` are updated to pass
   `reply_text="<text>"` AND `action_intent="reply"` (since the R94 path
   requires both for a reply proposal to be constructed).

### 3.6 No new `preferred_channel` field

1. The model does NOT name channels directly. The reply's driver routing is
   handled by the planner's R93 P2 priority (`target_user` → `preferred` →
   `iteration-order`), where `target_user_id` is the model's pick and the
   `bound_user_ids` driver self-description (R93 P2) is the routing key.
2. No `preferred_channel` / `channel` / `via` envelope field is added in R94.
   Adding one would couple the model to driver implementation details and
   re-introduce the bias that R94 is removing from the reply field.

## 4. Non-Functional Requirements

1. **Performance.** No additional LLM call. The parser swaps one optional-string
   read for another; the precedence in `_emit_proposal` is a slightly smaller
   branch set (one branch removed: `reply_compat_path`).
2. **Reliability.** A model envelope with a non-string `reply_text` raises
   `StructuredThoughtParseError` (fail-fast, no silent coercion). An envelope
   that uses the legacy `i_want_to_say` field is parsed normally (the field is
   ignored), so any in-flight model checkpoint that still produces
   `i_want_to_say` is not broken by R94 — its `i_want_to_say` content is
   ignored, the model is expected to start producing `reply_text` once it has
   the new prompt.
3. **Observability.** No new logging mechanism. The `21` runtime observability
   already captures the `13 planner_bridge` decision; the new `reply_text`
   field surfaces in the existing trace without R94 adding a new log surface.
4. **Compatibility and migration.** R94 is **breaking** relative to R93 / R93 P2:
   - The `i_want_to_say` field is removed from the schema; any model that
     relies on it for a reply must be retrained / re-prompted to use
     `action_intent="reply" + reply_text`. (This is the R94 design intent.)
   - The `reply_compat_path` is removed; the R93/R93 P2 compat behavior
     (filling `i_want_to_say` without `action_intent` ⇒ implicit reply) no
     longer exists. The model MUST pick `action_intent` explicitly.
   - All R93 / R93 P2 tests that exercise the `i_want_to_say` path are
     updated to use `reply_text` + `action_intent="reply"`. The deterministic
     offline path's byte-for-byte Phase-1 acceptance criterion is preserved
     (no `reply_text` involvement on that path).
5. **Schema name stability.** The new field is `reply_text`, not
   `i_want_to_reply` or `reply_content` or `outbound_text`. The name
   `reply_text` is:
   - Generic (not "I want to X"): does not embed a verb that would re-bias
     the model.
   - Symmetric with `action_intent="reply"`: the field is a sub-detail of the
     reply action class.
   - Clear about scope: it is the *text* of the reply, not the *decision* to
     reply (that is `action_intent`).
6. **The structural test.** A new test
   `test_internal_thought_no_i_want_to_say_in_prompt.py` walks every system
   prompt / user prompt / evidence construction path in the engine and asserts
   the literal `i_want_to_say` string is nowhere present. A future R that
   reintroduces the field is caught at test time, not at evaluation time.

## 5. Code Behavior Constraints

1. **Forbidden — `i_want_to_say` field in schema.** The system prompt, the
   parser, the evidence field set, and the test helpers must never reference
   `i_want_to_say` after R94. The structural test enforces this.
2. **Forbidden — implicit reply from absent `action_intent`.** When the
   envelope omits `action_intent` (or sets it to `null`), the owner must not
   construct a reply proposal. The R93/R93 P2 compat path is removed.
3. **Forbidden — fabricated reply text.** When `action_intent="reply"` is set
   but `reply_text` is `None`/empty, the owner must not construct a reply
   proposal. (The model must supply both: the action class choice AND the
   text to send.) No fabrication from `thought.content`.
4. **Forbidden — fabricated operator.** Same as R93 / R93 P2: an empty
   resolved `target_user_id` is honest absence, not a default.
5. **Forbidden — `13` content authoring.** `13 planner_bridge` does not
   construct reply content; it only validates and routes (R93 P2 invariant).
6. **Boundary — driver self-description.** `bound_user_ids` is a transport
   fact declared by the driver. The model picks `target_user_id`; the
   planner routes to the driver whose `bound_user_ids` covers that user.
7. **Boundary — composition is the projector.** The `current_operator_id`
   projection from `02 sensory_ingress` is owner-neutral and unchanged. The
   projection is now a *fallback* for `target_user_id`, not a forced value.
8. **No-adhoc-logging guard.** No new logging mechanism; existing
   observability carries the new field through to traces.

## 6. Impacted Modules

### 6.1 Source — modified

1. `src/helios_v2/internal_thought/contracts.py`
   - Rename `INTENDED_REPLY_TEXT_MAX_CHARS` → `REPLY_TEXT_MAX_CHARS`.
   - Rename `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX` → `REPLY_TEXT_TRUNCATION_SUFFIX`.
   - Update the comment block above the constants (was R93 / R93 P2 narrative;
     is now R94 narrative referencing the new `reply_text` field).
2. `src/helios_v2/internal_thought/engine.py`
   - `StructuredThoughtEvidence`: remove `intended_reply_text: str = ""`,
     add `reply_text: str | None = None`. Update the comment block.
   - Remove `_optional_intended_reply_text` parser.
   - Add `_optional_reply_text` parser (string-or-None semantics; non-string
     raises; over-cap truncated).
   - `_parse_structured_thought`: stop calling `_optional_intended_reply_text`;
     call `_optional_reply_text` instead.
   - `_derive_thought_judgment._emit_proposal`:
     - Remove `reply_compat_path` branch.
     - Add `reply_explicit_path` requirement: `evidence.action_intent ==
       ACTION_INTENT_REPLY` AND `evidence.reply_text is not None` (non-empty)
       AND resolved target is non-empty.
     - Update the `implicit_reply_intent` calculation to use only the
       `reply_explicit_path` (no compat branch).
   - `_build_messages` system prompt: remove `i_want_to_say` schema line;
     rewrite the schema block to lead with `action_intent`; rewrite the
     transport clause to reference `action_intent="reply" + reply_text`; add
     a stronger "Action class is a CHOICE" paragraph.

### 6.2 Source — unchanged

3. `src/helios_v2/channel/contracts.py` — `bound_user_ids` is the R93 P2
   additive field; R94 doesn't touch it.
4. `src/helios_v2/channel/drivers/cli.py` — `bound_user_ids=frozenset()`
   wildcard is correct for CLI; unchanged.
5. `src/helios_v2/composition/bridges.py` — `_current_operator_id` projection
   unchanged; only its consumer in `_emit_proposal` is reframed as a fallback.
6. `src/helios_v2/planner_bridge/engine.py` — `_select_channel` priority
   rewrite (R93 P2) is correct and unchanged.

### 6.3 Tests — modified

7. `tests/_internal_thought_test_fixtures.py` — `envelope()` signature:
   replace `i_want_to_say` param with `reply_text` param. Update the
   docstring narrative.
8. `tests/test_runtime_composition.py` — `FakeThoughtProvider.i_want_to_say`
   field renamed to `reply_text`; tied to `action_intent="reply"` for the
   reply path.
9. `tests/test_internal_thought_engine.py` — `FakeThoughtGateway` /
   `JsonThoughtGateway` / `FakeProvider.i_want_to_say` references updated to
   `reply_text` + `action_intent="reply"`.
10. `tests/test_internal_thought_implicit_reply_intent.py` — all test
    payloads use `i_want_to_say=...` replaced with `reply_text=...` +
    `action_intent="reply"`. Tests for the removed `reply_compat_path`
    (i_want_to_say without action_intent) are deleted; replaced with
    explicit-reply tests.
11. `tests/test_internal_thought_evidence_intended_reply.py` — RENAMED to
    `tests/test_internal_thought_evidence_reply_text.py`. All assertions
    on `intended_reply_text` updated to `reply_text`.
12. `tests/test_internal_thought_parse_i_want_to_say.py` — RENAMED to
    `tests/test_internal_thought_parse_reply_text.py`. All assertions on
    `i_want_to_say` updated to `reply_text`.
13. `tests/test_runtime_stage_chain_implicit_reply.py` — RENAME to
    `tests/test_runtime_stage_chain_explicit_reply.py`. The e2e test now
    drives the explicit-reply path: `_ReplyThoughtProvider.i_want_to_say`
    replaced with `reply_text` + `action_intent="reply"`. The "explicit
    tool wins" assertion is preserved.
14. `tests/test_internal_thought_emit_proposal_phase2.py` — all
    `i_want_to_say=...` test payloads updated to `reply_text=...` +
    `action_intent="reply"`. The compat-path test (i_want_to_say without
    action_intent) is removed.

### 6.4 Tests — new

15. `tests/test_internal_thought_no_i_want_to_say_in_prompt.py` — structural
    test: walks every prompt construction / envelope-build path and asserts
    the literal `i_want_to_say` is absent. Concretely:
    1. `_build_messages` of `LlmBackedInternalThoughtPath` does not contain
       the literal `i_want_to_say` in either the system or user message.
    2. The source code of `engine.py` and `contracts.py` does not contain
       the string `i_want_to_say` (a source-level guard).
    3. The shared test fixture's `envelope()` does not accept a kwarg named
       `i_want_to_say`.
    4. The Phase-1 `i_want_to_say` schema line from the R93 system prompt
       is gone.
16. `tests/test_internal_thought_emit_proposal_r94.py` — the new
    `_emit_proposal` precedence: explicit-reply requires `action_intent +
    reply_text + target`; `action_intent="no_action"` with `reply_text`
    set yields `None`; `reply_text` set without `action_intent` yields
    `None` (no compat path); explicit-tool wins; deterministic offline
    path unchanged.

### 6.5 Real-LLM probes — modified + re-run

17. `scripts/r93_probes/01_basic_reply.json` — `must_contain` updated from
    `["苏蕊", "i_want_to_say"]` to `["苏蕊", "reply_text"]` (and the
    `i_want_to_say` literal removed from the system prompt captured in the
    JSON). Re-run: model must produce `reply_text` (not `i_want_to_say`)
    with operator-addressed content.
18. `scripts/r93_probes/02_silence_negative_control.json` — system prompt
    captured in JSON is updated (no `i_want_to_say` line); the
    `must_not_contain` list is unchanged in spirit (no fabricated operator
    reply). Re-run: model leaves both `action_intent` and `reply_text`
    null/empty on an interoception-only tick.
19. `scripts/r93_probes/03_action_choice.json` — system prompt captured
    is updated; `must_contain_any` updated to `["action_intent", "reply",
    "reply_text"]` (the model must declare an action class AND supply
    `reply_text` for the reply class). Re-run.
20. `scripts/r93_probes/04_no_action_when_unmoved.json` — system prompt
    updated; re-run with the new schema. **Evaluation focus**: compare the
    `no_action` choice rate to the R93 P2 baseline. If the R94 schema
    regresses the negative control (i.e. the model now reflexively fills
    `reply_text` and `action_intent="reply"` on a low-salience stimulus),
    escalate to R96 (Chinese appraisal grounding) for root-cause
    investigation.

### 6.6 Documentation — modified

21. `docs/requirements/index.md` — new R94 row (Maturity column "in
    progress" → "shipped" once tests + probes + commit land).
22. `docs/OWNER_GUIDE.md` / `docs/OWNER_GUIDE.zh-CN.md` — `11` next-step
    section updated to drop the `i_want_to_say` mention; status header
    sync.
23. `docs/PROGRESS_FLOW.en.md` / `docs/PROGRESS_FLOW.zh-CN.md` — last-synced
    sync.
24. `docs/ARCHITECTURE_BOUNDARIES.md` — last-synced + a brief
    migration-history note (R93 introduced `i_want_to_say`; R93 P2
    de-emphasized it with `action_intent`; R94 removes it).
25. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — `gap_execution_closure` row
    updated to note that the dialog-reply leg of the local outward-
    execution loop is now driven by explicit `action_intent + reply_text`,
    not the legacy `i_want_to_say` heuristic.
26. `docs/ROADMAP.zh-CN.md` — W2.5 R94 row updated to "已交付"; the
    subsequent R95/R96/R97 numbering is preserved.

## 7. Acceptance Criteria

1. `_parse_structured_thought` reads `reply_text` per §3.1; the parser
   returns an evidence whose `reply_text` matches the rules (default None;
   accepted non-empty strings preserved verbatim up to the cap; non-string
   raises). The legacy `i_want_to_say` field is no longer parsed (it is
   silently ignored if present, to support in-flight model checkpoints).
2. With a fake provider returning
   `{"thought":"...", "sufficiency":0.9, "wants_to_continue":false,
   "proposed_action":{"intends_action":false},
   "self_revision":{"intends_revision":false}, "action_intent":"reply",
   "reply_text":"hello", "target_user_id":"operator-x"}` and the
   semantic + channel-bound assembly running a CLI submission, the
   resulting tick produces:
   1. an `ActionDecision` whose `op_name="reply_message"` and
      `op_params={"outbound_text":"hello", "target_user_id":"operator-x"}`,
   2. a CLI sink dispatch carrying the reply text,
   3. an `executed` continuity record.
3. With the same envelope but `reply_text` absent (None / empty), the
   reply proposal is silently absent even though `action_intent="reply"`
   is set; the cycle closes as internal-only. No fabricated text.
4. With `action_intent="no_action"` AND `reply_text="<text>"`, the reply
   proposal is silently absent; `no_action` wins regardless of
   `reply_text` content. No reply is constructed.
5. With `action_intent` absent (None) AND `i_want_to_say` set in a legacy
   envelope (forward-compat with old model checkpoints), the reply proposal
   is silently absent. The R93 compat path is removed; the model must pick
   `action_intent` explicitly.
6. With an explicit `tool_op="fs_write"` AND `action_intent="reply"` AND
   `reply_text="<text>"`, the explicit `fs_write` wins (R85 precedence
   preserved). The reply is not constructed.
7. The deterministic offline path (`assemble_runtime()`) remains
   byte-for-byte unchanged: every pre-R94 test that exercises the
   deterministic path passes; the legacy `outbound_text=thought.content`
   + `preferred_channels=("cli",)` shape is preserved.
8. The system prompt of `LlmBackedInternalThoughtPath._build_messages` does
   not contain the literal `i_want_to_say` string. The structural test
   `test_internal_thought_no_i_want_to_say_in_prompt.py` asserts this.
9. The full network-free test suite is green: ≥ 1195 + new tests passed,
   the 4 pre-existing `wall_clock_profile` skipped tests remain skipped
   (out of R94 scope), the composition owner-boundary guard and the
   no-ad-hoc-logging guard remain green.
10. The real-LLM probe `scripts/r93_probes/01_basic_reply.json` shows
    the model fills `reply_text` (not `i_want_to_say`) with operator-
    addressed reply text after the new system prompt; the negative-
    control probes (02, 04) show the model leaves both `action_intent`
    and `reply_text` null/empty when no action is warranted.
11. The R94 R93-P2 baseline comparison for probe 04 (low-salience "ok"
    stimulus) is recorded in a short note under
    `docs/requirements/94-drop-i-want-to-say-llm-agency/probe_04_comparison.md`:
    if `no_action` choice rate regresses relative to R93 P2, escalate
    to R96 (Chinese appraisal grounding) as a root-cause investigation;
    if the rate holds or improves, R94 is signed off as a clean
    structural cleanup that strictly improves LLM action-class agency.
12. All cross-file documentation (§6.6) is synced in the same change set.
