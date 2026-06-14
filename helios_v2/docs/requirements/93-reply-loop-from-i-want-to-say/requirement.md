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


---

# Phase 2 (2026-06) — Action Agency and Cross-Channel Routing

## 7. Phase 2 Background and Problem

The 2026-06-14 real-LLM visitor-eval (38 messages, 8 visitors, 8 emotion categories)
demonstrated that **R93 Phase 1 was necessary but insufficient**: the dialog-reply
loop is now closed (37/38 messages reach the operator as real CLI replies, up from
1/89 in the R91 era), but the underlying mental model was still wrong. Inspecting
the runtime reveals the new gap:

1. R93's `_emit_proposal` constructs an **implicit `reply_message` proposal by
   default** when the model fills `i_want_to_say` and no explicit `tool_op` is set.
   The proposal's `target_user_id` is **forced** to the composition-projected
   `current_operator_id` (i.e. the `source_name` of the most recent external
   stimulus). This makes reply the *default* action class and makes
   `target_user_id` a *forced* consequence of the input channel.
2. The model's `preferred_channels` on the proposal is documented as a
   "non-authoritative hint"; the planner's `_select_channel` ignores it entirely
   and picks the first connected driver that supports the op (currently always CLI).
3. The planner never reads `op_params["target_user_id"]` for routing. The CLI
   driver declares no notion of which user IDs it serves.

The end result: **Helios has become a "confiding machine"** — it always reflexively
replies to whoever triggered the current tick, and it always replies on the same
channel. The brain does not behave this way. In real cognition, the response is
not a reply-by-default but an **action choice among many effectors**:

- Hearing a friend's distress → choose to comfort (reply on the operator's channel)
- Hearing about an unfamiliar concept → choose to look it up (web_search channel;
  this is not a reply and has no `target_user_id`)
- Hearing a calendar reminder → choose to prepare (calendar channel; no input
  triggered it, autonomy drove it)
- Hearing a chat message and feeling reflective → choose to journal
  (file_write channel; the response is to oneself, not to the message source)
- Hearing and being unmoved → choose no_fire (no proposal at all)

In a multi-channel future (CLI + QQ + Feishu + voice + web_search + calendar + ...),
the cognitive question is not "do I reply to this person" but **"given my full
internal state and the available effectors, what action — if any — should I take,
on which effector, for which audience?"** The model is the decision-maker; the
planner is the gatekeeper; composition is the projector of runtime facts.

Phase 2 fixes three architectural defects:

- **D1 (action-class default)**: reply is no longer the implicit default. The model
  must explicitly choose an action class (or choose no_action).
- **D2 (target_user_id authority)**: `target_user_id` is the model's pick, not a
  forced projection from the input source. The planner respects it.
- **D3 (planner routing)**: planner honors `target_user_id` → `preferred_channels` →
  iteration-order priority, with each driver self-describing the user IDs it serves
  so the planner can map target→driver deterministically.

## 8. Phase 2 Goal

Make the LLM a **deliberate action-choosing agent** rather than a reflexive
responder, while keeping the W2 reply-closure behavior intact. Concretely:

1. The envelope gains an explicit `action_intent` field (`"reply" | "tool" |
   "no_action"`). The model uses it to declare which action class it has chosen.
2. The implicit-reply branch becomes **opt-in** rather than default. The branch
   fires only when (a) the model sets `action_intent="reply"` OR (b) the model
   fills `i_want_to_say` without `action_intent` (R93 compat fallback). When the
   model fills neither, no proposal is constructed — the cycle closes as
   internal-only even if `proposed_action.intends_action=true` was set (the legacy
   `intends_action` field becomes a content hint, not a proposal trigger).
3. `target_user_id` for the reply path becomes the model's pick
   (`evidence.target_user_id` if set, else `current_operator_id` as compat
   default). The composition projection of `current_operator_id` stays as a
   **context fact** for the model to see, not a forced value to copy.
4. Each driver self-describes the user IDs it serves via a new
   `ChannelOpSpec.bound_user_ids` field (CLI declares `frozenset()` as a wildcard;
   a future QQ driver would declare its bound openids).
5. The planner's `_select_channel` gains a priority strategy: target_user → driver
   serving that user → preferred_channels hint → iteration-order fallback. The
   legacy behavior (first available driver supporting the op) is preserved when
   no target_user and no preferred hint are given.
6. The system prompt is rewritten so the model understands action class is a
   choice, reply is one of many actions, and `i_want_to_say` is a synonym for
   `action_intent="reply" + reply_text=...` (not a hidden trap).

When R93 Phase 2 is in place:

- A real-LLM channel-bound dialogue produces an actual reply for every tick
  whose envelope sets `action_intent="reply"` (R93 compat path) — backward
  compatible with Phase 1 tests.
- The same model may also produce `action_intent="no_action"` when it judges
  that no action is appropriate, and no proposal is constructed (the cycle
  closes internal-only).
- In a multi-driver assembly, the model's `target_user_id` and `preferred_channels`
  are honored by the planner when those drivers serve the target user; otherwise
  the planner falls back to a connected driver offering the op.

## 9. Phase 2 Functional Requirements

### 9.1 Envelope: explicit `action_intent` field

1. `_parse_structured_thought` reads an optional top-level
   `action_intent: "reply" | "tool" | "no_action"` field. Accepted shapes:
   1. The field is absent or `null` => `action_intent=None` (compat: deferred to
      the precedence rule in §9.2).
   2. The field is one of the three string literals => `action_intent=<value>`.
   3. The field is any other string (or non-string) => parser raises the existing
      `StructuredThoughtParseError` (no silent coercion).
2. `StructuredThoughtEvidence` gains one additive optional field
   `action_intent: str | None = None`. Default value preserves byte-for-byte the
   R93 (Phase 1) evidence shape.
3. The legacy `proposed_action.intends_action` field is **no longer a proposal
   trigger**. It remains parsed (backward compat) and is now treated as a content
   hint surfaced in the trace. A model that sets `intends_action=true` but does
   not set `action_intent` and does not fill `i_want_to_say` produces no proposal
   (this is a behavior change from R93 Phase 1, where the legacy `emit_action`
   branch fired; that branch is **removed** in Phase 2).
4. The legacy `emit_action` fallback path in `_emit_proposal` is removed. There
   is no longer a default reply constructed from `thought.content` when
   `evidence is None`; the deterministic offline path emits no proposal at all
   (the R93 backward-compat fallback for the deterministic path is a no-op).
   This is documented as an intentional Phase 2 behavior change; the
   deterministic offline assembly is intended for tests, not for production.

### 9.2 `_emit_proposal` action-class precedence

1. The new precedence for emitting a proposal is:
   1. **Explicit `tool_op` (R85)** wins when `evidence.intends_tool_use and
      bool(evidence.tool_op)`. The proposal is a tool action; no reply is
      constructed.
   2. **Implicit reply (compat path)** fires when:
      - `evidence is not None` AND
      - no explicit `tool_op` AND
      - `(evidence.action_intent == "reply")` OR
        `(evidence.action_intent is None and evidence.intended_reply_text)`,
      AND
      - the resolved `target_user_id` (see §9.3) is non-empty.
      The proposal is a `reply_message` tool intent with `op_params={"outbound_text",
      "target_user_id"}`.
   3. **Implicit tool (compat path)** fires when `evidence is not None` AND
      `evidence.action_intent == "tool"`. The proposal is a tool action with
      `op_params=evidence.tool_params` (R85 path).
   4. **No action** when:
      - `evidence is None` (deterministic offline path) — no proposal, no
        outbound dispatch; cycle closes as internal-only.
      - `evidence.action_intent == "no_action"` — explicit abstention; no
        proposal.
      - `evidence.action_intent is None` AND no `i_want_to_say` AND no
        `i_want_to_use_tool` — cycle closes as internal-only.
2. The `_emit_proposal` emits at most one proposal per tick (unchanged from
   R85/R93 Phase 1).

### 9.3 `target_user_id` resolution for reply

1. `_emit_proposal` resolves the reply's `target_user_id` in this order:
   1. `evidence.target_user_id` if the model explicitly set it (new envelope
      field; see §9.4).
   2. `request.prompt_contract_summary.get("current_operator_id", "")` as the
      compat default (R93 Phase 1 projection; this is the input source's
      `source_name`).
2. If the resolved `target_user_id` is empty, the implicit-reply branch is
   silent (no proposal), regardless of the envelope's `i_want_to_say` or
   `action_intent`.
3. The composition projection of `current_operator_id` from `02 sensory_ingress`
   remains owner-neutral and is now labeled in the prompt as a **context fact**,
   not a forced default.

### 9.4 New envelope field: `target_user_id` and `reply_text`

1. `_parse_structured_thought` reads an optional top-level `target_user_id` field
   (string). Accepted shapes:
   1. Absent or `null` => `evidence.target_user_id=None`.
   2. A non-empty string => `evidence.target_user_id=<stripped value>`.
   3. A non-string => `StructuredThoughtParseError`.
2. The envelope also accepts an optional `reply_text` field as an explicit alias
   for `i_want_to_say` (both names map to `evidence.intended_reply_text`).
   This is documented but not promoted in the prompt (the prompt continues to
   reference `i_want_to_say` for backward-compat with any fine-tune that already
   learned the field name).

### 9.5 Driver self-description: `bound_user_ids`

1. `ChannelOpSpec` gains one additive optional field
   `bound_user_ids: frozenset[str] = frozenset()`. The owning driver declares
   the user IDs this op serves. `frozenset()` is a wildcard (any target user
   can be routed to this driver).
2. The CLI driver declares `bound_user_ids=frozenset()` (CLI is the local
   interactive terminal; any target can be routed to it via a CLI reply).
3. `ChannelSubsystemStateProvider.channel_descriptor_snapshot` automatically
   threads `bound_user_ids` into the planner's descriptor snapshot (no extra
   composition code).
4. A future QQ / Feishu / voice driver would declare its bound user IDs
   (openids / user_ids / phone_numbers) in this field. This slice does not
   ship those drivers; the field is added now so a future P4 channel addition
   can wire it without re-touching the planner or `11`.

### 9.6 Planner routing priority: `target_user` → `preferred` → `iteration`

1. `FirstVersionPlannerBridgePath._select_channel` (and the future
   `LlmBackedPlannerBridgePath` when one lands) is rewritten to honor this
   priority:
   1. Collect candidates: drivers whose `supported_ops` include
      `proposal.preferred_op` and whose `status.available` is True.
   2. If the proposal's `params` carries a non-empty `target_user_id`: filter
      candidates to those whose `bound_user_ids` either contain that user OR
      are `frozenset()` (wildcard).
   3. From the filtered set: if any candidate's `driver_id` is in
      `proposal.preferred_channels`, return the first such.
   4. Otherwise return the first candidate in the filtered set (deterministic
      iteration order, preserved from R85).
   5. If the target_user filter yields an empty set, **fall through to step 3**
      with the unfiltered candidate set (the model's `target_user_id` may name
      a user not served by any connected driver; planner degrades gracefully
      rather than rejecting the proposal).
2. The legacy R85 behavior (first available driver supporting the op) is
   preserved as the final fallback when both `target_user_id` and
   `preferred_channels` are absent.

### 9.7 System prompt update

1. `_build_messages` rewrites the system-prompt schema description so the model
   understands:
   1. Action class is a **choice**, not a default. The model must decide whether
      to act and what class of action (`reply` / `tool` / `no_action`).
   2. The optional envelope fields are listed: `i_want_to_say` (synonym for
      `action_intent="reply" + reply_text=...`), `i_want_to_use_tool` +
      `tool_op` + `tool_params` (R85), `action_intent` (explicit), `target_user_id`
      (overrides the input-source default for replies).
   3. The transport clause explains: when `action_intent="reply"` (or
      `i_want_to_say` is set without `action_intent`), the runtime transports
      the text as a `reply_message` to the resolved `target_user_id` through
      the connected driver serving that user. The model's `target_user_id` is
      authoritative; the planner will route accordingly.
2. The schema still lists the v1 fields (`thought` / `sufficiency` /
   `wants_to_continue` / `proposed_action` / `self_revision` /
   `hormone_response_i_predict` / `i_want_to_use_tool` / `tool_op` / `tool_params`)
   for backward compat; the new fields are additive and not mandatory.

## 10. Phase 2 Non-Functional Requirements

1. **Performance.** No additional LLM call. The parser adds at most two optional
   reads (`action_intent`, `target_user_id`). The planner routing change is
   a constant-time scan over a small candidate set (typically 1-2 drivers).
2. **Reliability.** A model envelope with a non-string `action_intent` or
   `target_user_id` raises `StructuredThoughtParseError`. An envelope with
   `action_intent` set to a value outside the fixed taxonomy also raises.
3. **Observability.** No new logging mechanism. The `21` runtime observability
   already captures the `13 planner_bridge` decision, the `11` proposal carrier,
   and the outbound dispatch; the new fields surface in the existing trace
   without R93 Phase 2 adding a new log surface.
4. **Compatibility and migration.** Phase 2 is **mostly backward-compatible** with
   Phase 1:
   - All R93 Phase 1 tests that exercise the R93 implicit-reply path continue
     to pass (the compat fallback when `action_intent is None and
     i_want_to_say is set` keeps the Phase 1 behavior).
   - The deterministic offline path's `emit_action` fallback is removed; this
     is a deliberate Phase 2 behavior change documented in §9.1.4. Tests
     that exercise the deterministic offline path may need to be updated
     (they are owner-internal test fixtures; no production code path
     changes).
   - The Phase 1 unit tests that assert "no implicit reply when continuation
     requested" and "no implicit reply when current_operator_id empty"
     continue to hold (the precedence rules in §9.2 cover both).
   - New tests cover the new fields and the new behavior.

## 11. Phase 2 Code Behavior Constraints

1. **Forbidden — fabricated reply.** When the envelope leaves `i_want_to_say`
   null/empty AND `action_intent != "reply"` AND no explicit `tool_op`, the
   runtime must not synthesize a reply. The cycle closes as internal-only.
2. **Forbidden — fabricated operator.** When `target_user_id` is empty AND
   the model has not set `current_operator_id` via the prompt-contract summary,
   no reply is constructed. The system never invents a default target.
3. **Forbidden — `13` content authoring.** `13 planner_bridge` does not
   construct reply content; it only validates and routes.
4. **Forbidden — fabricated driver.** The planner never routes a proposal to
   a driver that does not offer the op or is not available; the planner
   never routes to a driver that does not serve the target user unless the
   filter would yield an empty set (then it falls through, preserving the
   "reply is better than no reply" fail-soft bias).
5. **Boundary — driver self-description.** `bound_user_ids` is a transport
   fact declared by the driver. Composition threads it; the planner
   consumes it; cognition never sets it.
6. **Boundary — composition is the projector.** Composition still projects
   `current_operator_id` from `02 sensory_ingress` as a context fact (no
   change in projection logic). The change is only that `current_operator_id`
   is now labeled "context fact" rather than "forced default" in the prompt.

## 12. Phase 2 Impacted Modules

Modified:
1. `src/helios_v2/internal_thought/contracts.py` — additive
   `action_intent: str | None = None` and `target_user_id: str | None = None` on
   `StructuredThoughtEvidence`; constants for the action_intent taxonomy.
2. `src/helios_v2/internal_thought/engine.py` —
   `_parse_structured_thought` reads `action_intent` and `target_user_id`;
   `_emit_proposal` adds the new precedence (§9.2) and removes the legacy
   `emit_action` fallback; `_build_messages` rewrites the system-prompt schema
   description.
3. `src/helios_v2/channel/contracts.py` — additive
   `bound_user_ids: frozenset[str] = frozenset()` on `ChannelOpSpec`.
4. `src/helios_v2/channel/drivers/cli.py` — CLI driver sets
   `bound_user_ids=frozenset()` on its `reply_message` op spec.
5. `src/helios_v2/composition/bridges.py` —
   `ChannelSubsystemStateProvider.channel_descriptor_snapshot` threads
   `bound_user_ids` into the snapshot (auto from the descriptor; no new code).
6. `src/helios_v2/planner_bridge/engine.py` —
   `FirstVersionPlannerBridgePath._select_channel` rewritten per §9.6 to
   honor the target_user → preferred → iteration priority.

New tests:
7. `tests/test_internal_thought_parse_action_intent.py` — parsing semantics
   for `action_intent` (absent, valid string, invalid string, non-string raises,
   `target_user_id` parallel semantics).
8. `tests/test_internal_thought_emit_proposal_phase2.py` — the new precedence
   (explicit tool wins; reply compat path; `action_intent="reply"`; no proposal
   on `action_intent="no_action"`; deterministic offline path emits no
   proposal; `target_user_id` resolution).
9. `tests/test_channel_op_spec_bound_user_ids.py` — `ChannelOpSpec` carries
   the new field; CLI driver sets `frozenset()`; the provider threads it.
10. `tests/test_planner_bridge_routing_priority.py` — `_select_channel`
    priority: target_user → preferred → iteration; `bound_user_ids=frozenset()`
    wildcard; empty target_user filter falls through.
11. `tests/test_runtime_stage_chain_action_agency.py` — end-to-end:
    `action_intent="no_action"` produces no dispatch; explicit
    `action_intent="reply"` dispatches; `target_user_id` honored in a
    multi-driver fixture.

Real-LLM probes (per §8.2 of the requirement-authoring-standard):
12. `scripts/r93_probes/03_action_choice.json` — positive control: the model
    receives a present-field message, must explicitly set `action_intent="reply"`
    and produce a real CLI dispatch (i.e. the new prompt still surfaces real
    reply text, not just no-op).
13. `scripts/r93_probes/04_no_action_when_unmoved.json` — negative control:
    interoception-only / no-operator tick; the model sets
    `action_intent="no_action"` and the cycle closes internal-only.

Documentation (cross-file rule §8):
14. `docs/requirements/index.md` — the R93 row's notes column is updated to
    mention Phase 2 (action-agency + cross-channel routing).
15. `docs/OWNER_GUIDE.md` / `docs/OWNER_GUIDE.zh-CN.md` — `11` and `13` next-step
    sections updated; status header sync.
16. `docs/PROGRESS_FLOW.en.md` / `docs/PROGRESS_FLOW.zh-CN.md` — last-synced sync.
17. `docs/ARCHITECTURE_BOUNDARIES.md` — last-synced + a brief migration-history
    note (Phase 1 row + Phase 2 row).
18. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — `gap_execution_closure` row updated
    to note that the action-agency aspect is now closed (model can choose
    non-reply action classes; routing respects model choice).
19. `docs/ROADMAP.zh-CN.md` — extend the W2 section to mark Phase 2; advance
    the one-sentence ordering line; flag the embedded "next step" (real
    multi-channel assembly) as the natural trigger for further routing work.

## 13. Phase 2 Acceptance Criteria

1. `_parse_structured_thought` reads `action_intent` and `target_user_id` per
   §9.1, §9.4; the parser returns evidence whose `action_intent` and
   `target_user_id` match the rules above.
2. With a fake provider returning `{"thought":"...", "sufficiency":0.9,
   "action_intent":"reply", "i_want_to_say":"hello"}` and the channel-bound
   assembly running a CLI submission ("hi from operator"), the resulting tick
   produces an `ActionDecision` with `op_name="reply_message"` and
   `op_params={"outbound_text":"hello", "target_user_id":<cli source>}`,
   dispatched to the CLI sink.
3. With the same envelope but `action_intent="no_action"` instead, the
   implicit reply branch is silent; the cycle closes as internal-only; no
   CLI dispatch occurs.
4. With an envelope setting `target_user_id="alice"` and a multi-driver
   fixture (one CLI driver + one fake "alice-bound" driver offering
   `reply_message`), the planner routes the reply to the alice-bound driver
   (not the CLI driver).
5. With an envelope setting `target_user_id="ghost"` (a user not served by
   any connected driver), the planner falls through to a wildcard driver
   (CLI); the proposal is not rejected.
6. The default `assemble_runtime()` deterministic offline path emits no
   proposal (Phase 2 behavior change; documented in §9.1.4). All existing
   pre-R93 network-free tests that pass on the R93 assembly continue to
   pass on the R93 Phase 2 assembly.
7. The full network-free test suite is green: ≥ 1107 + R93 Phase 2 new
   tests passed / 4 skipped. The composition owner-boundary guard and the
   no-ad-hoc-logging guard remain green.
8. The real-LLM probe `scripts/r93_probes/03_action_choice.json` shows the
   model sets `action_intent="reply"` with operator-addressed reply text
   after the new system-prompt clause; the negative-control probe
   `04_no_action_when_unmoved.json` shows the model sets
   `action_intent="no_action"` and leaves the reply field null/empty.
9. All cross-file documentation is synced in the same change set.
