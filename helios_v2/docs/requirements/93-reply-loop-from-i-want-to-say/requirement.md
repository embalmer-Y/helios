# Requirement 93 - Reliable Reply Loop From `i_want_to_say`

## 1. Background and Problem

The 2026-06 real-LLM emotion long-run (ROADMAP §9) sent 89 Chinese visitor messages
through the R31 CLI driver into a real-LLM, semantic, channel-bound runtime. The
captured raw `11` thought prompts and parsed envelopes show two facts:

1. The model **filled `i_want_to_say`** with substantial Chinese reply content in nearly
   every visitor turn (cf. R91 probe `_RESULTS_OVERVIEW.md`: `苏蕊，谢谢你愿意来找我聊聊...`,
   `小林，听到这些...`, `阿哲，三年啊...`, `周师傅，我听着呢。十二年的事...`).
2. Yet only 1 of 89 visitor messages reached the operator as a real CLI reply.

Inspecting the runtime shows three structural reasons in series:

1. `internal_thought.engine._parse_structured_thought` reads only the legacy schema
   fields (`thought` / `sufficiency` / `wants_to_continue` / `proposed_action.intends_action`
   / `self_revision`) plus optional `hormone_response_i_predict` (R81) and optional
   tool fields (`i_want_to_use_tool` / `tool_op` / `tool_params`, R85). It **never reads
   the top-level `i_want_to_say`** even though the engine's own system prompt explicitly
   asks the model to fill it (`internal_thought/engine.py._build_messages` line listing
   `"i_want_to_say": "<optional words to say outward>"`). The reply text never enters
   `StructuredThoughtEvidence`.
2. The `11` `_emit_proposal` legacy fallback path (the one taken when
   `proposed_action.intends_action=true` and there is no explicit `tool_op`) builds a
   `ThoughtActionProposalCarrier` with `behavior_name="reply_message"`,
   `outbound_text=thought.content` (the **narration** field, not the reply text),
   `preferred_channels=("cli",)` hardcoded, and **no `op_params`**.
3. R85 made `13 planner_bridge` validate `op_params` against the driver's
   self-described `required_params`. The CLI driver's `reply_message` op declares
   `required_params=("outbound_text", "target_user_id")`. The legacy path supplies
   neither (the legacy `outbound_text=thought.content` is on the proposal carrier, not
   in `op_params`, and `target_user_id` is missing). The planner rejects with
   `missing_op_inputs` and writes a `world_blocked` continuity record. The CLI sees
   nothing.

So the chain `LLM intends to reply -> 11 normalizes -> 13 binds reply_message -> CLI
dispatch` is broken at step 1 (lossy parse) and step 3 (validation rejection). With
R91 the model now reads the operator's words; with R92 it knows how long ago they
arrived; with R93 it must also be able to actually answer.

## 2. Goal

Make a model-supplied `i_want_to_say` reach the operator as a real CLI reply in the
default channel-bound runtime, end to end through the existing R85 effector spine,
without inventing a fabricated reply when the model did not request one. Concretely:

1. The `11` envelope parser must read the top-level `i_want_to_say` field (already in
   the system prompt) into a new `intended_reply_text` slot on
   `StructuredThoughtEvidence`.
2. When `intended_reply_text` is non-empty and there is no explicit `tool_op`, the
   `11` `_emit_proposal` path must auto-construct an **implicit** `reply_message` tool
   intent with `op_params={"outbound_text": <intended_reply_text>, "target_user_id":
   <current operator id>}`, so the existing R85 planner-validation +
   `reply_message`-binding spine carries it through to CLI dispatch.
3. The "current operator id" must come from a real composition projection of the
   same-frame `02 sensory_ingress` external stimulus's source provenance — not
   hardcoded in `11` and not invented when there is no operator (an absent operator
   id makes the implicit reply intent **silently absent**, not a fabricated reply).
4. The system prompt must explicitly tell the model that `i_want_to_say`, when set,
   will be transported as a `reply_message` to the current operator through the
   `cli` channel, so the model produces operator-addressed reply text rather than a
   1st-person inner monologue.
5. The legacy `emit_action` fallback path (taken when `evidence is None`, i.e. the
   deterministic offline path) must remain byte-for-byte unchanged on its inputs (the
   default `assemble_runtime()` test path stays green).

When R93 is in place, a real-LLM channel-bound dialogue produces an actual operator-
visible reply for every tick whose envelope sets `i_want_to_say`, and produces
**no fabricated reply** for ticks whose envelope leaves it null/empty (the model's
honest "no reply this cycle" remains honest).

## 3. Functional Requirements

### 3.1 Envelope parsing

1. `_parse_structured_thought` must additionally read the top-level `i_want_to_say`
   field as an optional string. Accepted shapes:
   1. The field is absent or `null` => `intended_reply_text=""` (no implicit reply).
   2. The field is an empty or whitespace-only string => `intended_reply_text=""`
      (no implicit reply).
   3. The field is a non-empty trimmed string => `intended_reply_text=<value>`
      (a length cap mirroring the existing prompt cap; over-cap is deterministically
      truncated with an explicit suffix).
   4. The field is a non-string (e.g. number, list, object) => parser raises the
      existing `StructuredThoughtParseError` (no silent coercion).
2. `StructuredThoughtEvidence` gains one additive field
   `intended_reply_text: str = ""`. Default value preserves byte-for-byte the
   pre-R93 evidence shape and downstream consumers.

### 3.2 Implicit reply intent in `11` `_emit_proposal`

1. When the cycle closes (not continuing) and either:
   - the model envelope is present (`evidence is not None`), AND
   - no explicit tool intent is set (`evidence.intends_tool_use == False` or
     `evidence.tool_op == ""`), AND
   - `evidence.intended_reply_text` is non-empty, AND
   - the prompt-contract summary's `current_operator_id` is non-empty,
   then `11` must build an **implicit reply tool intent**: a
   `ThoughtActionProposalCarrier` with `behavior_name="reply_message"`,
   `requested_op="reply_message"`, `outbound_text=None` (data lives in `op_params`),
   `op_params={"outbound_text": evidence.intended_reply_text, "target_user_id":
   current_operator_id}`, `preferred_channels=` the same `ready_channels` projection
   already used by the explicit-tool path, and a reason trace identifying the
   implicit-reply origin.
2. Explicit `tool_op` (R85) takes precedence: when both an explicit tool intent and
   `intended_reply_text` are set, the explicit tool intent wins (deterministic
   precedence; the implicit reply is not constructed).
3. When `intended_reply_text` is non-empty but `current_operator_id` is empty (no
   external operator this tick), the implicit reply intent is **silently absent**:
   the cycle closes through the existing internal-only path. No fabricated reply.
4. When `evidence is None` (the deterministic offline path), behavior is unchanged
   (the legacy `emit_action` branch with `outbound_text=thought.content` and
   `preferred_channels=("cli",)` continues to apply).

### 3.3 Composition: current_operator_id projection

1. The composition request bridges that build the `prompt_contract_summary` for the
   `11` thought request (`SemanticInternalThoughtRequestBridge` and
   `FirstVersionInternalThoughtRequestBridge`) must add one additive key
   `current_operator_id: str` to the summary, projected from the **earliest external
   stimulus** in the same-frame `02 sensory_ingress` batch (mirrors the
   `_present_field_stimuli_clause` ordering rule from R91 / R92).
2. The projection identifier source is the stimulus's `source_name` field
   (e.g. `cli` or `cli via cli`). The projection helper applies the same
   `_INTERNAL_MODALITIES` filter the present-field stimuli clause already uses
   (interoceptive / body / background signals never become a "speaker" target).
3. When no external stimulus is present this tick (or every external stimulus has an
   empty `source_name`), `current_operator_id` is the empty string `""` (honest
   absence; downstream `11` treats this as "no operator, no implicit reply").
4. The composition projection is owner-neutral: it reads only already-published
   `02` stage-result fields, computes no salience or selection policy, and imports
   no `06`/`10`/`13` owner.

### 3.4 System prompt update

1. `_build_messages` must update the system-prompt schema description so the model
   knows that `i_want_to_say`, when set, will be transported as a real
   `reply_message` to the current operator through a connected user-visible channel
   (`cli`). Concretely the system prompt must add one bounded line stating: when the
   model fills `i_want_to_say`, the runtime will send that text through the user-
   visible channel as a reply to the current operator (no need to use
   `i_want_to_use_tool` / `tool_op` for replies — only for non-reply effectors).
2. The legacy schema (`thought` / `sufficiency` / `wants_to_continue` /
   `proposed_action` / `self_revision` / optional `hormone_response_i_predict` /
   optional `i_want_to_use_tool` / `tool_op` / `tool_params`) is otherwise unchanged
   in this slice; R93 adds one promoted field (`i_want_to_say`) to the existing
   list, not a v3 schema rewrite.

## 4. Non-Functional Requirements

1. **Performance.** No additional LLM call. The parse step adds one optional-string
   read; the implicit-reply branch is a trivial dataclass build. The composition
   `current_operator_id` projection is one pass over already-built `02` stimuli (the
   same pass `_present_field_stimuli_clause` already does — the helper may share it).
2. **Reliability.** A model envelope that sets `i_want_to_say` to a non-string raises
   the existing `StructuredThoughtParseError` (fail-fast, no silent coercion). An
   envelope that omits `i_want_to_say` or sets it to null/empty preserves the
   pre-R93 path byte-for-byte. An empty `current_operator_id` is honest absence,
   never a fabricated target.
3. **Observability.** No new logging mechanism. The existing `21` runtime
   observability captures the `13 planner_bridge` decision (which now sees the
   filled `op_params`), so the implicit-reply path is reconstructable from the
   existing timeline without R93 adding any new log surface.
4. **Compatibility and migration.** Strictly additive: every change defaults to the
   legacy behavior. The default `assemble_runtime()` deterministic offline path is
   unchanged; R85's explicit-`tool_op` path is unchanged; pre-R93 `legacy_constant`
   prompt mode is unchanged.

## 5. Code Behavior Constraints

1. **Forbidden — fabricated reply.** When the envelope leaves `i_want_to_say` null /
   empty, the runtime must not synthesize a reply from `thought` or any other field.
   The cycle closes as internal-only.
2. **Forbidden — fabricated operator.** When no external stimulus is present, the
   composition projection must return `""`, not invent a "default" target_user_id.
   `11` must respect this (no implicit reply when target is empty).
3. **Forbidden — `13` content authoring.** `13 planner_bridge` must not author
   `outbound_text` or `target_user_id`. The implicit-reply construction lives in
   `11` (cognitive judgment "I want to reply with this text"), with composition
   only supplying the operator-id fact. R85's existing `required_params` validation
   in `13` still applies and will reject any malformed implicit reply (defense in
   depth).
4. **Boundary — explicit precedence.** An explicit `tool_op` (R85) always wins over
   the implicit-reply path. The implicit reply is a fallback when the model chose
   the natural-language reply field instead of the explicit tool field.
5. **Boundary — composition is the projector.** The composition bridge is the only
   place that turns "the operator's source_name in `02`" into the
   `current_operator_id` value for the prompt-contract summary. `11` consumes it as
   a flat string and never imports `02`/`channel`.
6. **Length cap.** `intended_reply_text` carries a deterministic upper-bound cap
   (mirroring the R91 `present_field_summary` 600-char convention; a sensible cap is
   `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` to allow longer reply paragraphs while
   preventing pathological lengths). Over-cap input is deterministically truncated
   with an explicit suffix.

## 6. Impacted Modules

Modified:
1. `src/helios_v2/internal_thought/contracts.py` — additive
   `intended_reply_text: str = ""` on `StructuredThoughtEvidence`; constants
   `INTENDED_REPLY_TEXT_MAX_CHARS`, `INTENDED_REPLY_TRUNCATION_SUFFIX`.
2. `src/helios_v2/internal_thought/engine.py` —
   `_parse_structured_thought` reads `i_want_to_say`;
   `_emit_proposal` adds the implicit-reply branch with the explicit-precedence
   rule; `_build_messages` updates the system-prompt schema description.
3. `src/helios_v2/composition/bridges.py` —
   one new owner-neutral helper `_current_operator_id(frame) -> str`;
   both `SemanticInternalThoughtRequestBridge` and
   `FirstVersionInternalThoughtRequestBridge` add `current_operator_id` into the
   `prompt_contract_summary` dict.

New tests:
4. `tests/test_internal_thought_parse_i_want_to_say.py` — parsing semantics
   (default empty, accepted strings, whitespace-empty, non-string raises, length cap
   truncation).
5. `tests/test_internal_thought_implicit_reply_intent.py` — `_emit_proposal`
   precedence rules (explicit tool wins, implicit reply when only `intended_reply_text`
   is set, no implicit reply when `current_operator_id` is empty, no implicit reply
   when continuation requested, deterministic offline path unchanged).
6. `tests/test_composition_current_operator_id.py` — projection rules (earliest
   external stimulus's `source_name` wins, internal-modality stimuli ignored, empty
   when no external stimulus).
7. `tests/test_runtime_stage_chain_implicit_reply.py` — end-to-end through the
   channel-bound runtime: a CLI submission whose `_LoggingProvider` returns a fake
   completion with `i_want_to_say="hello"` produces an actual CLI sink dispatch with
   the reply text.

Documentation (cross-file rule §8):
8. `docs/requirements/index.md` — new R93 row.
9. `docs/OWNER_GUIDE.md` / `docs/OWNER_GUIDE.zh-CN.md` — `11` and `12`/`13` next-step
   sections updated; status header sync.
10. `docs/PROGRESS_FLOW.en.md` / `docs/PROGRESS_FLOW.zh-CN.md` — last-synced sync.
11. `docs/ARCHITECTURE_BOUNDARIES.md` — last-synced + a brief migration-history note.
12. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — `gap_execution_closure` row updated to
    note that the dialog-reply leg of the local outward-execution loop is now
    closed; the network-driver leg remains future P4 work.
13. `docs/ROADMAP.zh-CN.md` — close W2 R93; advance the one-sentence ordering line.

Probe (per §8.2):
14. `scripts/r93_probes/01_basic_reply.json` — real-LLM probe verifying that a
    visitor message + the new system-prompt clause produces a fillled `i_want_to_say`
    (positive control).
15. `scripts/r93_probes/02_silence_negative_control.json` — verifies that on an
    interoception-only / no-operator tick the model leaves `i_want_to_say` null /
    empty rather than fabricating a reply.

## 7. Acceptance Criteria

1. `_parse_structured_thought` reads `i_want_to_say` per §3.1; the parser returns an
   evidence whose `intended_reply_text` matches the rules above (default empty;
   accepted non-empty strings preserved verbatim up to the cap; non-string raises).
2. With a fake provider returning `{"thought":"...", "sufficiency":0.9,
   "wants_to_continue":false, "proposed_action":{"intends_action":false},
   "self_revision":{"intends_revision":false}, "i_want_to_say":"hello"}` and the
   semantic + channel-bound assembly running a CLI submission ("hi from operator"),
   the resulting tick produces:
   1. an `ActionDecision` whose `op_name="reply_message"` and `op_params=
      {"outbound_text":"hello", "target_user_id":<the cli source>}`,
   2. a CLI sink dispatch carrying the reply text,
   3. an `executed` continuity record,
   4. (with R92's wall-clock wired) the persisted record's `created_at_wall` is set.
3. With the same envelope but no operator stimulus this tick (interoception-only
   tick), the implicit reply intent is silently absent; the cycle closes as
   internal-only; no CLI dispatch occurs.
4. With an explicit `tool_op="fs_write"` AND a non-empty `i_want_to_say`, the
   explicit `fs_write` wins (R85 precedence preserved); the implicit reply is not
   constructed.
5. The default `assemble_runtime()` deterministic offline path remains byte-for-byte
   unchanged: every existing pre-R93 test passes; every R85/R86/R87/R91/R92 test
   passes.
6. The composition projection of `current_operator_id` returns the earliest external
   stimulus's `source_name` (filtering internal modalities) and returns `""` when no
   external stimulus is present.
7. The full network-free test suite is green: ≥ 1107 + new tests passed, the
   composition owner-boundary guard and the no-ad-hoc-logging guard remain green.
8. The real-LLM probe `scripts/r93_probes/01_basic_reply.json` shows the model fills
   `i_want_to_say` with operator-addressed reply text after the new system-prompt
   clause; the negative-control probe shows the model leaves the field null/empty
   when no operator is present.
9. All cross-file documentation is synced in the same change set.
