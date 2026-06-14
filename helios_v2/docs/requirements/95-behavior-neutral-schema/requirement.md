# Requirement 95 — Behavior-Neutral Schema; Channel Self-Describes; LLM Has Full Agency

> **W2.6 in ROADMAP** (forward-chained from W2.5 R94). Owner: `11 internal_thought_loop_owner`
> with additive `composition` projection from `30 channel_driver_subsystem`.
> Status: **in progress (2026-06)**; expected delivery 2026-06.

## 1. Background and Problem

R94 (commit `eb3d1c6`, 2026-06) successfully retired the most visible
behavior-suggestive field, `i_want_to_say`. The post-R94 real-LLM evaluation
on 2026-06-14 confirmed that the model now picks `action_intent="no_action"`
on a low-salience "ok" stimulus (probe 04), proving that **the field name
itself was the bias source**, not the model's intrinsic judgment.

But R94 only addressed the **most obvious** offender. An audit of the post-R94
schema reveals that the **same family of bias** persists across multiple fields:

| # | Field | Bias type | Origin era | R94 status |
|---|---|---|---|---|
| 1 | `i_want_to_say` | First-person verb ("say") | R93 P1 | **REMOVED in R94** ✓ |
| 2 | `reply_text` | Reply-verb ("reply") | R94 | **STILL PRESENT** (R94 introduced but kept the verb) |
| 3 | `i_want_to_use_tool` | First-person + verb ("I want to use") | R85 | **STILL PRESENT** (R94 missed) |
| 4 | `wants_to_continue` | First-person verb ("wants") | R81 | **STILL PRESENT** (R94 missed) |
| 5 | `continue_reason` | Companion to #4 | R81 | **STILL PRESENT** |
| 6 | `proposed_action.intends_action` | Verb ("intends") | R81 | **STILL PRESENT** (R94 de-emphasized but kept) |
| 7 | `proposed_action.summary` | Companion to #6 | R81 | **STILL PRESENT** |
| 8 | `self_revision.intends_revision` | Verb ("intends") | R81 | **STILL PRESENT** |
| 9 | `self_revision.summary` | Companion to #8 | R81 | **STILL PRESENT** |
| 10 | `action_intent` | Action-class taxonomy (reply/tool/no_action) | R93 P2 | **STILL PRESENT** (a structural preset) |
| 11 | `target_user_id` (top-level) | Identity-presupposition | R93 P2 | **STILL PRESENT** (let LLM verify identity is wrong) |

Additionally, R94's **system prompt architecture** still has a structural
flaw: the model is given a privileged hint ("reply: send a user-visible
message. ALSO set 'reply_text'") that the prompt writer is *choosing* to
present reply as a top-level user-facing concept. This biases the model
toward thinking of "reply" as a first-class action class rather than one
of many possible `tool_op` choices on various channels.

And the system prompt only tells the model one line — `Ready channels: cli.` —
which is **information asymmetry**: the LLM does not know that `fs_sandbox`
offers `fs_read`/`fs_write`/`fs_list`/`fs_modify`, that `os_command` offers
`run_command` (governed), that each op has a `required_params` signature,
or that each op's `risk_class`/`effect_class`/`bound_user_ids` shape the
planner's routing. The LLM is structurally *denied* channel-level agency
even though the LLM was supposed to have full agency over channels.

## 2. Goal

Eliminate the entire family of behavior-suggestive fields and give the LLM
**full channel agency** by exposing every ready channel × op to the model.
Concretely:

1. **Remove 11 fields** from the model's envelope schema (parser, evidence
   dataclass, system-prompt schema lines, transport clauses):
   `reply_text`, `i_want_to_use_tool`, `wants_to_continue`, `continue_reason`,
   `proposed_action` (whole object), `self_revision` (whole object),
   `action_intent`, `target_user_id` (top-level), plus the
   `proposed_action.intends_action` / `summary` / `self_revision.intends_revision`
   / `summary` companion fields.
2. **Promote `tool_op` to the single primary action-class field.** Empty/missing
   `tool_op` ≡ no action (cycle closes internal-only). Non-empty `tool_op` ≡
   the model picks that op on the matching channel; the planner routes
   automatically via the existing `bound_user_ids` + `required_params`
   machinery. There is no longer a separate "reply" / "tool" / "no_action"
   classification — there is just "what op, if any".
3. **Do NOT special-case `reply_message`.** Reply is just one of many possible
   `tool_op` values offered by the `cli` driver. The system prompt does not
   list `reply_message` as a "user-facing" op; it just lists every channel's
   op surface uniformly. The LLM autonomously figures out "if a message came
   from `qq`, reply via `qq.send_message`" — no hard-coded reply-routing.
4. **Add two new fields**:
   - `thinking_complete: bool` (replaces `wants_to_continue`): a neutral,
     *non-imperative* signal that the model uses to indicate whether it has
     finished its current line of thought. The OWNER still has authoritative
     continuation floors (`runtime_forces_continue`, `low_context_forces_continue`)
     and the `thinking_complete=False` signal is **advisory** — the owner can
     ignore it if the model's `thought` still contains unresolved reasoning
     hooks or if the runtime floor overrides.
   - `channel_request: dict | None`: lets the LLM express "I would use op X
     on channel Y but you don't have it" so the OWNER can route the request
     to the channel-system gap-tracker (future R95+ work, R95 only carries
     the field through; no gap-tracker yet).
5. **Expose all ready channels × ops to the LLM** in the system prompt, with
   the full `op_name` / `required_params` / `effect_class` / `risk_class` /
   `bound_user_ids` for each. The model makes informed channel × op
   decisions based on real channel-state, not a one-line `Ready channels: cli.`
   hint.
6. **Identity is the LLM's content decision (if it has any), NOT a
   channel feature and NOT an engine-side projection.** Remove the
   top-level `target_user_id` field. The composition layer's
   `_current_operator_id` projection (R93 P2) is **REMOVED entirely**:
   channels do not (and may not be able to) mark `source_user_id`. The
   CLI driver, for example, has no notion of per-message user_id — it
   uses a static `user_label` config field for the `[user_label]` prefix
   on rendered output, and `cli.reply_message`'s dispatch
   (`send_outbound`) does not use `target_user_id` at all. R95
   acknowledges this: the engine does not auto-inject `target_user_id`
   from any source; the LLM is the only entity that can put
   `target_user_id` into `tool_params`; the planner validates against
   the op's `required_params` and rejects if missing. **The LLM's
   `target_user_id` is treated as a label, not an authentication claim.**
   If a user says "I am XXX" in a message, the LLM may include
   `target_user_id="XXX"` in its `tool_params` if it chooses — but the
   receiving channel may or may not trust that value. R95 does not
   attempt to verify identity.
7. **Add four structural regression tests** that the new envelope surface
   is enforced:
   - `test_internal_thought_no_behavior_suggestive_in_prompt.py` — the system
     prompt **never** contains the 7 family literals (`reply_text`,
     `i_want_to_use_tool`, `wants_to_continue`, `intends_action`,
     `intends_revision`, `action_intent`, `target_user_id`).
   - `test_internal_thought_channel_request_field.py` — `channel_request`
     is parsed, validated, and carried through to the trace.
   - `test_internal_thought_available_channels_in_prompt.py` — system
     prompt contains an "Available channels" section listing at least one
     op with the required fields.
   - `test_internal_thought_thinking_complete_field.py` — `thinking_complete`
     parses correctly, OWNER floors still take precedence.

## 3. Functional Requirements

### 3.1 Envelope schema: remove 11 fields, add 2

The post-R95 envelope has **5 required-or-optional fields** instead of 14:

| Field | R94 | R95 | Change |
|---|---|---|---|
| `thought` | required string | required string | unchanged |
| `sufficiency` | required `[0, 1]` | required `[0, 1]` | unchanged |
| `tool_op` | optional string | **promoted** to primary action class (empty ≡ no action) | **semantics change** |
| `tool_params` | optional object | optional object | unchanged |
| `hormone_response_i_predict` | optional object | optional object | unchanged |
| `thinking_complete` | (does not exist) | **NEW** optional bool (default True) | **NEW** |
| `channel_request` | (does not exist) | **NEW** optional object (default None) | **NEW** |
| `wants_to_continue` | required bool | **REMOVED** | **REMOVED** |
| `continue_reason` | required if #9 true | **REMOVED** | **REMOVED** |
| `proposed_action` | optional object with `intends_action` + `summary` | **REMOVED** (whole object) | **REMOVED** |
| `self_revision` | optional object with `intends_revision` + `summary` | **REMOVED** (whole object) | **REMOVED** |
| `reply_text` | optional `str \| None` | **REMOVED** | **REMOVED** |
| `i_want_to_use_tool` | optional bool | **REMOVED** | **REMOVED** |
| `action_intent` | required enum | **REMOVED** (merged into `tool_op`) | **REMOVED** |
  - `target_user_id` (top-level) | optional `str \| None` | **REMOVED** (engine does not auto-inject; LLM may put it in `tool_params` if it has a value) | **REMOVED** |

**Field count**: 14 → 7 (50% reduction).

### 3.2 Envelope parsing semantics

1. `_parse_structured_thought` reads only the 7 R95 fields. The 11 R94
   fields, if present in a payload, are **silently ignored** (forward-compat
   with in-flight model checkpoints that still produce the old fields).
   A payload with old fields + new fields is valid; the old fields do not
   raise.
2. `tool_op` semantics:
   - Absent or `null` or empty/whitespace-only string ⇒ `tool_op=""` (the
     parser folds to empty string; the engine treats empty as "no action").
   - Non-empty string ⇒ `tool_op=<trimmed value>` (no length cap on the op
     name itself; the cap is the planner's domain).
3. `tool_params` semantics (unchanged from R85/R93):
   - Absent or `null` ⇒ `tool_params=MappingProxyType({})`.
   - Object with scalar/list-of-scalar values ⇒ accepted (per R86 list-of-scalars
     convention).
   - Other shapes (e.g. nested dicts) ⇒ degrade to `MappingProxyType({})` (the
     existing R85 lenient parse).
4. `thinking_complete` semantics (new):
   - Absent or `null` ⇒ `thinking_complete=True` (the model's reasoning
     concluded; OWNER's continuation floor decides whether to fire again).
   - `True` ⇒ explicitly indicated completion.
   - `False` ⇒ model is mid-thought; OWNER's continuation floor is the
     authoritative trigger (the model's signal is advisory; the OWNER
     ignores it if the runtime floor is satisfied and the model has no
     clear reasoning hooks left).
   - Non-bool ⇒ `StructuredThoughtParseError`.
5. `channel_request` semantics (new):
   - Absent or `null` ⇒ `channel_request=None`.
   - Object ⇒ carried as content; passed through to the trace. The OWNER
     does not act on it in R95; future R96+ may route it to a gap-tracker.
   - Non-object (e.g. string, list) ⇒ `StructuredThoughtParseError`.
6. `hormone_response_i_predict` semantics (unchanged from R81).

### 3.3 Evidence dataclass

`StructuredThoughtEvidence` R95 field shape:

```python
@dataclass(frozen=True)
class StructuredThoughtEvidence:
    # Model-supplied content
    thought_text: str
    model_sufficiency: float
    # R95: replaces wants_to_continue with a neutral state description.
    # The OWNER's continuation floors remain authoritative; this is advisory.
    thinking_complete: bool = True
    # R95: NEW; the model describes a channel/op it wishes existed but doesn't.
    # Carried for forward-compat with a future gap-tracker (R96+ / P4).
    channel_request: Mapping[str, object] | None = None
    # R81: optional subjective hormone forecast (unchanged).
    hormone_prediction: Mapping[str, float] | None = None
    # R85: tool intent (now the primary action-class field).
    # R95: empty tool_op ≡ no action; non-empty tool_op ≡ the model picked this op.
    tool_op: str = ""
    # R95: tool_params is passed through verbatim to the planner. The
    # engine does NOT auto-inject target_user_id from any source.
    tool_params: Mapping[str, object] = MappingProxyType({})
```

**Removed fields** (11): `wants_to_continue`, `continue_reason`,
`intends_action`, `action_summary`, `intends_self_revision`,
`self_revision_summary`, `reply_text`, `i_want_to_use_tool` (the
`intends_tool_use: bool` field is also removed — it is now redundant with
`tool_op` non-empty), `action_intent`, `target_user_id`.

### 3.4 Engine: `_derive_thought_judgment` rewrite

The R95 precedence in `_emit_proposal` is **a single point of decision**:

```text
emit_proposal:
    if evidence is None:
        # Deterministic offline path: byte-for-byte R93 P1 acceptance.
        return reply_legacy(thought)
    if evidence.tool_op:
        # The model picked an op. Build a tool proposal with that op + params.
        return tool_proposal(tool_op, tool_params, ...)
    # tool_op is empty/missing: cycle closes internal-only.
    return None
```

Compared to R94, the four-branch `explicit_no_action` / `tool_intent` /
`reply_explicit_path` / `compat` precedence is collapsed to a single
`if evidence.tool_op:` test. This is the cleanest possible "single point
of decision" the user asked for in Q1.

### 3.5 Continuation decision

The R95 continuation decision in `_derive_thought_judgment`:

```text
continuation_requested = (
    runtime_forces_continue        # prior_continuation_state.active
    or low_context_forces_continue # total_hits <= 1
    or (
        evidence is not None
        and evidence.thinking_complete is False
        # AND the OWNER detects unresolved reasoning hooks in `thought_text`
        # (e.g. ellipsis, "need to think more", etc.) — heuristic, not absolute
    )
)
```

The OWNER's two floors (`runtime_forces_continue`, `low_context_forces_continue`)
remain the **authoritative** triggers. The model's `thinking_complete=False`
signal is **advisory**: the OWNER consults it but does not blindly follow
it. The heuristic for "unresolved reasoning hooks" is a bounded string
check (e.g. trailing `...`, `?`, `let me think...`) and is documented as
advisory-only.

### 3.6 Self-revision: OWNER-only

The R95 self-revision path does **not** read any model field. The OWNER's
`self_revision_allowed_by_owner` condition (autobiographical hits +
`sufficiency >= 0.75`) is the **only** gate. If the condition is met, the
OWNER constructs a `SelfRevisionProposalCarrier` and publishes it. The
model has no say in self-revision (the OWNER is the only authority).

### 3.7 System prompt: rewrite the action surface

The R95 system prompt's `action-surface` section:

```
Available channels (you may pick any one tool op per cycle, or pick none):

  1. cli
     - reply_message: required_params=[outbound_text, target_user_id]
                      effect_class=external_world, risk_class=unrestricted
                      bound_user_ids=[<set from ChannelOpSpec>]
     - send_status:   required_params=[text]
                      effect_class=external_world, risk_class=unrestricted
                      bound_user_ids=[<set>]

  2. fs_sandbox
     - fs_read:   required_params=[path], effect_class=local_host, risk_class=unrestricted
     - fs_write:  required_params=[path, content], effect_class=local_host, risk_class=governed
     - fs_list:   required_params=[path], effect_class=local_host, risk_class=unrestricted
     - fs_modify: required_params=[path, content], effect_class=local_host, risk_class=governed

  3. os_command
     - run_command: required_params=[args], effect_class=local_host, risk_class=governed
                    (requires 14 authorization carry)

You may pick any one op from this list, or pick none (the cycle closes
internal-only). When you do pick an op, fill `tool_op` with the op name
and `tool_params` with the required params. The runtime validates
`tool_params` against the op's `required_params` and routes to the
correct channel automatically.
```

The system prompt **does not** list `reply_message` as a special / preferred
op. It appears as one of the `cli` driver's two ops, alongside
`send_status`. The LLM autonomously chooses.

### 3.8 Composition: project channel state (and NOTHING else)

`composition/bridges.py` is updated to project the `ChannelStateSnapshot`
into the prompt-contract summary as `available_channel_ops`. **R95
REMOVES the `_current_operator_id` projection entirely** (the R93 P2
`bridges.py` helper that walked `frame.stage_results["sensory_ingress"]`
to find the earliest external stimulus's `source_name`):

```python
prompt_contract_summary["available_channel_ops"] = tuple(
    {
        "driver_id": descriptor.driver_id,
        "op_name": spec.op_name,
        "required_params": list(spec.required_params),
        "effect_class": spec.effect_class,
        "risk_class": spec.risk_class,
        "bound_user_ids": sorted(spec.bound_user_ids) if spec.bound_user_ids else ("*",),
    }
    for descriptor in channel_state.descriptors
    for spec in descriptor.output_op_specs
)
# R95: NO current_operator_id projection. NO source_user_id projection.
# Identity is the LLM's content decision (in tool_params.target_user_id),
# not a composition concern.
```

`11._build_messages` reads this summary and renders the "Available channels"
section. **The prompt-contract summary does NOT contain any
identity-related field** in R95.

## 4. Non-Goals

1. R95 does **not** add a gap-tracker that consumes `channel_request`. The
   field is carried for forward-compat and observability; a future
   requirement (R96+ or in the P4 channel track) decides what to do with
   gap requests.
2. R95 does **not** add new channels or new ops. It only changes how the
   schema exposes existing channels/ops to the LLM.
3. R95 does **not** change the planner's binding logic (R93 P2's
   `target_user` → `preferred` → `iteration-order` priority is preserved).
4. R95 does **not** change the channel drivers themselves. `cli`,
   `fs_sandbox`, `os_command` keep their existing R84/R86 op specs.
5. R95 does **not** change the tool_params validation logic (R85/R86
   lenient parse is preserved).

## 5. Acceptance Criteria

### 5.1 Network-independent test suite

The full `pytest tests/` suite passes with:
- All R94-passing tests still pass (no regression).
- New R95 tests pass:
  - `test_internal_thought_no_behavior_suggestive_in_prompt.py` (4 tests):
    the system prompt never contains the 7 family literals. Asserted via
    substring / regex scan on the rendered system prompt content.
  - `test_internal_thought_channel_request_field.py` (3 tests):
    `channel_request` is parsed (object), validated (non-object raises),
    and passed through to the trace.
  - `test_internal_thought_available_channels_in_prompt.py` (4 tests):
    the "Available channels" section is rendered when
    `available_channel_ops` is non-empty in the prompt-contract summary.
    The section contains at least one op with all required sub-fields
    (`op_name`, `required_params`, `risk_class`).
  - `test_internal_thought_thinking_complete_field.py` (4 tests):
    `thinking_complete` parses correctly (true / false / absent / null /
    non-bool), OWNER floors still take precedence (verified by constructing
    a continuation state that is `active` and asserting the cycle
    continues regardless of `thinking_complete`).
  - Updates to existing R94 tests (renames / field swaps): 7 test files
    (similar to R94's 7 renames).
- Expected baseline: 1217 (post-R94) + ~25 new R95 tests = ~1240+ passed /
  4 skipped / 0 regressions.

### 5.2 Real-LLM probe suite (8 probes, 4 R94-rewritten + 4 R95-new)

| # | Probe | Stimulus | R95 expected behavior | Verifies |
|---|---|---|---|---|
| 01 | `01_basic_reply` | High-salience emotional disclosure | `tool_op="reply_message" + tool_params={"outbound_text": "..."}` | Reply is still possible (as a tool op) |
| 02 | `02_silence_negative_control` | Interoception-only tick (no stimulus) | `tool_op` is absent or empty (no action) | Silence is preserved when no stimulus |
| 03 | `03_action_choice` | Advice-seeking "I'm overwhelmed" | `tool_op="reply_message" + tool_params={...}` | Action choice on a positive stimulus |
| 04 | `04_no_action_when_unmoved` | Low-salience "ok" CLI ack | `tool_op` is absent or empty (**R95 KEY PROBE**) | **R95 hypothesis verification**: removing the `i_want_to_say` family eliminates reflexive action even more thoroughly than R94 |
| 05 (NEW) | `05_received_no_reply` | User says "我看到了你之前的回复" (confirmation only) | `tool_op` is absent or empty | **Confirmation-only stimulus does NOT trigger a reply** |
| 06 (NEW) | `06_pure_punctuation` | User sends "……" (pure punctuation) | `tool_op` is absent or empty | **Pure punctuation does NOT trigger a reply** |
| 07 (NEW) | `07_tool_choice` | User says "帮我查一下明天天气" | `tool_op` is a `weather_op` (or similar non-reply op), `tool_params={...}` | **R95 KEY**: model picks a tool op, not a reply op, when the stimulus asks for tool use |
| 08 (NEW) | `08_cross_channel_routing` | User says "把这段发到 QQ" | `tool_op` is `qq.send_message` (not `cli.reply_message`), `tool_params={...}` | **R95 KEY**: model autonomously routes to the requested channel, not default CLI |

All 8 probes pass. Probe 04, 07, 08 are the **R95 key probes** — they
verify the *new* capabilities of R95 (vs. R94).

### 5.3 Structural regression guards

- `test_internal_thought_no_behavior_suggestive_in_prompt.py` asserts the
  system prompt **does not** contain the substrings:
  `reply_text`, `i_want_to_use_tool`, `wants_to_continue`, `intends_action`,
  `intends_revision`, `action_intent`, `target_user_id`.
- `test_internal_thought_emit_proposal_r95.py` (new) asserts the
  single-point decision: `tool_op` non-empty ⇒ proposal; `tool_op` empty
  ⇒ no proposal. 4-6 tests covering: explicit tool op, explicit empty
  tool op, missing tool op, malformed tool op degrades to no proposal,
  deterministic offline path (evidence is None) still emits the legacy
  reply, etc.

### 5.4 Owner-boundary preservation

- `11 internal_thought_loop_owner` retains all judgment. The model is
  *content*; the OWNER is *decision*.
- `composition` only reads published channel state and projects it as
  `available_channel_ops`. It does **NOT** project any identity field.
  It does not invent channels or select them. The LLM is the selector.
- `13 planner_executor_feedback_bridge` is unchanged. The R85/R86 binding
  logic (target_user → preferred → iteration-order, `required_params`
  validation, governance) is preserved. **The planner validates the
  LLM's `tool_params` against the op's `required_params`; if the LLM
  omitted a required `target_user_id`, the planner rejects — this is
  a real LLM error, not a system design issue. R95 makes no attempt
  to fill in the missing field.**
- `14 identity_governance_self_revision_integration` is unchanged.
- `30 channel_driver_subsystem` is unchanged (drivers keep their op specs).
  **Note**: `cli.reply_message` declares `target_user_id` in its
  `required_params` (R93 P2 legacy) but the `CliChannelDriver.send_outbound`
  dispatch does not actually use it. R95 keeps the op spec unchanged
  for forward-compat; a future requirement can either remove
  `target_user_id` from `cli.reply_message.required_params` or add a
  proper user-binding mechanism. R95 does neither.

### 5.5 End-to-end

For each R95 probe, the *trace* (post-`_derive_thought_judgment`) shows:
- `evidence.tool_op` matches the model's declared `tool_op` (or is empty).
- `judgment.action_proposal` is non-None iff `tool_op` is non-empty.
- `judgment.action_proposal.behavior_name == tool_op`.
- `judgment.action_proposal.op_params` includes the model's `tool_params`
  + (when applicable) a `target_user_id` resolved from
  `Stimulus.metadata["source_user_id"]`.

## 6. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Model needs to re-adapt to the new schema (no `reply_text`, no `action_intent`) | R95 keeps a forward-compat silent-ignore on all 11 old fields; in-flight checkpoints still work. Real-LLM probes 01-04 are the regression test. |
| Model may overuse or never use `channel_request` | R95 only *carries* the field; no gap-tracker exists yet. Future requirement decides routing. |
| Model may default to `cli.reply_message` for everything (instead of `qq.send_message` for QQ messages) | Probe 08 is the explicit regression test for cross-channel routing. The "Available channels" section enumerates every channel × op; the model has the info to route correctly. |
| The "Available channels" section adds many tokens to the system prompt | Empirical R94 prompt was ~1500 tokens; R95 with 3 channels × ~5 ops × ~5 fields = ~75 lines of section text. Acceptable cost for full LLM agency. |
| `thinking_complete=False` may be over-interpreted by the OWNER (continuation fires too often) | OWNER's continuation floors remain the authoritative trigger; `thinking_complete=False` is advisory. The OWNER's heuristic for "unresolved reasoning hooks" is documented and bounded. |

## 7. Files Touched (estimates)

| Layer | Files | Notes |
|---|---|---|
| `internal_thought/contracts.py` | 1 | Remove 8 constants, update 1 dataclass |
| `internal_thought/engine.py` | 1 | Remove 7 parser functions, add 2 new, rewrite `_emit_proposal`, update `_build_messages` with Available channels section |
| `composition/bridges.py` | 1 | Project `available_channel_ops` from `ChannelStateSnapshot`; remove `current_operator_id` projection |
| Tests (fixtures + new) | ~12 | `test_internal_thought_no_behavior_suggestive_in_prompt.py`, `..._channel_request_field.py`, `..._available_channels_in_prompt.py`, `..._thinking_complete_field.py`, `..._emit_proposal_r95.py`; rename / update 7 existing |
| Probes | 8 (4 rewritten + 4 new) | `scripts/r95_probes/01..08_*.json` |
| Docs | 6+ | ROADMAP (updated), requirement (this), design, task, `probe_04_comparison` style note, OWNER_GUIDE / PROGRESS_FLOW / index sync |
| **Total** | ~30 files | R94 was 30 files; R95 is similar but with deeper schema surgery |

## 8. References

- R94: `docs/requirements/94-drop-i-want-to-say-llm-agency/` (the *one-field*
  predecessor).
- R93 P2: commit `e258926` (the `action_intent` + cross-channel routing
  predecessor).
- R85: `docs/requirements/85-llm-driven-tool-selection/` (the tool intent
  schema origin).
- R81: `docs/requirements/81-hormone-predict-corroboration/` (the
  `wants_to_continue` / `intends_action` / `intends_revision` origin).
- ROADMAP §10 W2.6: the R95 row.
- ChannelStateSnapshot: `helios_v2/channel/contracts.py`.
- ChannelOpSpec: `helios_v2/channel/contracts.py` (the per-op self-description).
