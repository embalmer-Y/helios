# Design 95 — Behavior-Neutral Schema; Channel Self-Describes; LLM Has Full Agency

> Design companion to `requirement.md`. Describes the schema surgery, the
> engine rewrite, the system-prompt redesign, and the channel-surface
> projection. Mirrors R94's design-doc style (background, goal, design
> sections, trade-offs).

## 1. Background

R94 retired the most visible behavior-suggestive field (`i_want_to_say`)
and proved (probe 04) that the field name *itself* was the bias source.
But R94 was a *one-field* fix; the same family of bias persists across
the schema:

- `reply_text` (verb "reply", introduced by R94)
- `i_want_to_use_tool` (first-person + verb "use", introduced by R85)
- `wants_to_continue` / `continue_reason` (verb "wants", introduced by R81)
- `proposed_action.intends_action` / `.summary` (verb "intends", R81)
- `self_revision.intends_revision` / `.summary` (verb "intends", R81)
- `action_intent` (action-class taxonomy, structural preset, R93 P2)
- `target_user_id` (top-level; let LLM verify identity is wrong)

And the system prompt still privileges "reply" as a first-class action
class, even though the runtime treats reply as a tool op on the `cli`
driver. The LLM is *denied* channel-level agency because the prompt
gives it only one line: `Ready channels: cli.`

The user's Q1-Q7 decisions resolved the key design questions:
- **Q1=B**: merge `action_intent` into `tool_op`; reply is a tool op; no
  action is empty `tool_op`.
- **Q2=B**: replace `wants_to_continue` with `thinking_complete: bool` (a
  neutral, non-imperative signal). OWNER's continuation floors remain
  authoritative; the model's signal is advisory.
- **Q3=A**: directly delete `proposed_action` / `self_revision` whole
  objects. OWNER no longer reads these fields; OWNER decides self-revision
  purely on its own autobiographical + sufficiency floor.
- **Q4=A**: expose *all* ready channels × ops to the LLM in the system
  prompt (op_name, required_params, effect_class, risk_class,
  bound_user_ids).
- **Q5=完全移除 reply 类提示**: do not special-case `reply_message` in
  the system prompt. Let channel drivers self-describe their ops. The
  LLM autonomously figures out "if a message came from `qq`, reply via
  `qq.send_message`" (the user: "模型能力越来越强，诸如 QQ 发来消息从
  QQ 回复消息这种行为让 LLM 自行处理"). Add a new `channel_request`
  field so the LLM can express "I want op X but you don't have a
  channel for it".
- **Q6=A**: 8 real-LLM probes (4 R94-rewritten + 4 R95-new).
- **Q7=A**: probe 04 checks `tool_op` absence (not `action_intent`).
- **Q8-Q10**: remove top-level `target_user_id`; **do NOT assume channels
  mark `source_user_id`**. R93 P2's `current_operator_id` projection (from
  the inbound stimulus's `source_name`) is **over-engineering**: channels
  like `cli` literally have no ability to mark user_id — `cli.reply_message`
  declares `target_user_id` in `required_params` but the dispatch
  (`CliChannelDriver.send_outbound`) does not use it at all. The R95
  design is: **the engine does not auto-inject `target_user_id` from
  anywhere**; **the composition does not project any "current operator"
  field**; **the LLM is the only source of `target_user_id`** (if it
  includes it in `tool_params`, the planner validates; if it doesn't,
  the planner validates against the op's `required_params` and rejects
  if missing). The user's quote: "channel 标记 `source_user_id` 这一
  点要很小心，channel不是必须要求标记user_id的，包括像cli这样的
  channel理论上也根本没能力标记user_id，这不是一个feature" — this
  is a fundamental R95 principle: **identity is the LLM's content
  decision (if it has any), not a channel feature and not an
  engine-side projection**.

## 2. Goal

Make the LLM's action decision structurally driven by **what op to call on
which channel**, not by a schema-prescribed taxonomy. The LLM has full
agency over:
- whether to act at all (empty `tool_op` = no action);
- which op to call (any `tool_op` from the available channel surface);
- what params to pass (the LLM fills `tool_params`);
- which channel to route through (the LLM picks the op; the planner
  routes by `bound_user_ids` + `required_params`).

The LLM does *not* have agency over:
- identity (channel marks `source_user_id`; LLM does not verify);
- governance (`risk_class=governed` triggers `14` authorization; LLM
  is unaware of the gate; the OWNER enforces);
- the continuation decision (OWNER's floors are authoritative; the
  LLM's `thinking_complete` is advisory).

## 3. Design

### 3.1 Evidence dataclass: 14 fields → 5 fields

**R94 `StructuredThoughtEvidence`** (14 fields):
```
thought_text, model_sufficiency, wants_to_continue, continue_reason,
intends_action, action_summary, intends_self_revision,
self_revision_summary, hormone_prediction, intends_tool_use, tool_op,
tool_params, reply_text, action_intent, target_user_id
```

**R95 `StructuredThoughtEvidence`** (5 fields):
```
thought_text, model_sufficiency, thinking_complete (NEW), channel_request (NEW),
hormone_prediction, tool_op (promoted), tool_params
```

The R95 `tool_op` field is the **single primary action-class field**:
- empty / missing ⇒ no action (cycle closes internal-only)
- non-empty ⇒ the model picked this op; the OWNER builds a tool proposal

### 3.2 The 11 removed fields — why each

| Field | Reason for removal |
|---|---|
| `reply_text` | "reply" is a verb; the field name primes the model. Move reply text to `tool_params.outbound_text` (the standard op-param name for `reply_message`). |
| `i_want_to_use_tool` | "I want to use" is first-person + verb. R93 P2 already has `action_intent="tool"` as a stronger signal; the `i_want_to_use_tool` flag is redundant with `tool_op` non-empty. |
| `wants_to_continue` | "wants" is a verb. The OWNER has authoritative continuation floors (`runtime_forces_continue`, `low_context_forces_continue`). Replace with `thinking_complete: bool` (advisory). |
| `continue_reason` | Companion to `wants_to_continue`. Removed with it. |
| `proposed_action` (object) | "intends_action" is a verb. The OWNER does not need the model's intent — `tool_op` non-empty already implies the model intends an action. |
| `self_revision` (object) | "intends_revision" is a verb. The OWNER decides self-revision on its own autobiographical + sufficiency floor; the model's intent is redundant. |
| `action_intent` | The reply/tool/no_action taxonomy is a structural preset. Merge into `tool_op` (empty = no action; non-empty = the op). |
| `target_user_id` (top-level) | Letting the LLM verify identity is wrong. **The engine does not auto-inject `target_user_id` from any source** (no `current_operator_id` projection, no channel-derived `source_user_id`, no static default). The LLM may include `target_user_id` in `tool_params` if it has one; the planner validates against the op's `required_params`. Channels like `cli` don't have user_id to mark — `cli.reply_message`'s dispatch doesn't use `target_user_id` even though the op spec lists it as required. R95 keeps `target_user_id` in `cli.reply_message`'s `required_params` for forward-compat with future multi-user channels, but the engine makes NO attempt to populate it. |

### 3.3 The 2 new fields

#### `thinking_complete: bool = True`

- **Purpose**: a neutral, non-imperative signal that the model uses to
  indicate whether its current line of thought has concluded.
- **OWNER behavior**:
  - If `thinking_complete=False`, the OWNER *considers* this when
    computing `continuation_requested` — but the OWNER's two
    continuation floors (`runtime_forces_continue`,
    `low_context_forces_continue`) are authoritative and override
    the model's signal.
  - If `thinking_complete=True` (or absent / null), the model has
    indicated completion; the OWNER's floors still apply independently.
- **Why bool, not "wants_to_continue"**: "complete" is a state
  description; "wants" is a verb. State descriptions are neutral;
  verbs imply agency the model should not have.

#### `channel_request: dict | None = None`

- **Purpose**: lets the LLM express "I would use op X on channel Y
  but you don't have that channel / op" so a future gap-tracker (R96+
  or P4 channel track) can record the gap.
- **OWNER behavior in R95**: the field is parsed, validated, and
  carried through to the trace. The OWNER does not act on it (no
  gap-tracker exists yet). It is forward-compat infrastructure.
- **Why this design**: the user said "可以考虑增加一个字段：提示 LLM
  如果他想要用什么样的 tool 但我们没有做这样的 channel，可以留一个
  字段让 LLM 描述他需要怎么样的 channel" — this is exactly the
  field's purpose.

### 3.4 Engine: single-point decision

The R95 `_emit_proposal` is the simplest possible:

```python
def _emit_proposal(...):
    if evidence is None:
        # Deterministic offline path (R93 P1 acceptance, unchanged).
        return reply_legacy(thought)
    if evidence.tool_op:
        # The model picked an op. Build a tool proposal.
        target_user_id = request.prompt_contract_summary.get("current_operator_id", "")
        if isinstance(target_user_id, str):
            target_user_id = target_user_id.strip()
        op_params = dict(evidence.tool_params)
        if target_user_id and "target_user_id" not in op_params:
            op_params["target_user_id"] = target_user_id
        return ThoughtActionProposalCarrier(
            proposal_id=f"thought-action:{request.request_id}",
            scope="external",
            behavior_name=evidence.tool_op,
            requested_op=evidence.tool_op,
            preferred_channels=...,
            outbound_text=None,
            outbound_intensity=0.75,
            reason_trace=("thought picked a tool op for the current cycle",),
            governance_hints={"requires_identity_review": False},
            op_params=MappingProxyType(op_params),
        )
    return None  # tool_op empty ⇒ no action
```

**R94 vs R95 emit_proposal**:

| Decision | R94 | R95 |
|---|---|---|
| `evidence is None` (deterministic offline) | reply_legacy | **reply_legacy (unchanged)** |
| `action_intent == "no_action"` | explicit return None | **folded into "tool_op empty" branch** |
| `tool_intent_resolved` (intends_tool_use + tool_op, or action_intent=tool) | builds tool proposal | **folded into "tool_op non-empty" branch** |
| `action_intent == "reply"` + `reply_text` + target | builds reply proposal | **folded into "tool_op non-empty" branch** (model picks `tool_op="reply_message"` + `tool_params.outbound_text="..."`) |
| `intends_action` flag (legacy) | read for compat | **REMOVED** |
| `intends_self_revision` flag | read for self-revision | **REMOVED**; OWNER decides on its own |

The collapse from 5 branches to 1 is the cleanest possible "single point
of decision".

### 3.5 Self-revision: OWNER-only

```python
# R95 self-revision: no model input at all.
self_revision_allowed_by_owner = bool(autobiographical) and sufficiency_level >= 0.75
if self_revision_allowed_by_owner:
    self_revision_proposal = SelfRevisionProposalCarrier(...)
```

The OWNER's autobiographical + sufficiency condition is the *only* gate.
The model has no say in self-revision.

### 3.6 System prompt: Available channels section

The R95 system prompt is restructured:

1. **Identity** lines (unchanged): "You are the internal thought process
   of a continuous, brain-inspired runtime. Produce one concise internal
   thought for the current cycle. Do not perform theatrical
   self-narration; reflect the current state and context only."
2. **Active prompt-contract layers** (unchanged).
3. **Available channels** (NEW): a formatted block listing every ready
   channel × op with op_name, required_params, effect_class, risk_class,
   bound_user_ids. Rendered from `composition`'s projection of
   `ChannelStateSnapshot`.
4. **Response schema** (rewritten):
   ```
   Respond with a single JSON object only, no prose outside it:
   {
     "thought": "<concise internal thought>",
     "sufficiency": <number 0..1, how complete this cycle's thinking is>,
     "tool_op": "<op name from the Available channels list, or omit/empty for no action>",
     "tool_params": {<params for the chosen op, or omit/empty>},
     "thinking_complete": <bool, default true; false if you want the owner to consider continuing>,
     "channel_request": {<optional; describe a channel/op you wish existed but doesn't>},
     "hormone_response_i_predict": {<optional forecast>}
   }
   ```
5. **Decision guidance** (rewritten):
   ```
   - For each cycle, decide whether to act. If you do not act, leave
     `tool_op` empty/missing; the cycle closes internal-only.
   - If you do act, pick one op from the Available channels list. The
     runtime validates `tool_params` against the op's `required_params`
     and routes to the matching channel automatically.
  - **Identity is your content decision, not the runtime's**: the
    runtime does NOT auto-fill any user_id. If the op you pick
    requires `target_user_id` (see the op's `required_params` list)
    and you have a value for it (e.g. it appears in the inbound
    message text), include it in `tool_params.target_user_id`. The
    runtime does not verify or trust this value; it is a label for
    the receiving channel, not an authentication claim.
   - Do NOT reflexively reply. A low-salience or acknowledgment
     stimulus may legitimately close with no action.
   - If you find yourself wanting an op that no channel offers, fill
     `channel_request` so a future iteration can track the gap.
   ```

**Removed lines** (the 8 R94 schema lines that bias the model):
- `wants_to_continue`, `continue_reason` (lines)
- `proposed_action` (whole object)
- `self_revision` (whole object)
- `action_intent` (the reply/tool/no_action taxonomy)
- `reply_text` (the sub-detail)
- `target_user_id` (the identity-presupposition)
- `i_want_to_use_tool` (the R85 first-person flag)
- "reply: send a user-visible message. ALSO set 'reply_text'..."
  (the special-casing of reply)
- "tool: invoke a bound effector. ALSO set 'tool_op'..." (the special-casing
  of tool)
- "no_action: cycle closes as internal-only..." (the explicit no_action
  hint — no longer needed; "empty tool_op = no action" is implicit)

### 3.7 Composition: project channel state

`composition/bridges.py` projects the channel state into the
prompt-contract summary:

```python
# R95: project ready channels × ops to prompt-contract summary.
available_channel_ops = tuple(
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
prompt_contract_summary["available_channel_ops"] = available_channel_ops
```

`11._build_messages` reads this and renders the "Available channels"
section. The `current_operator_id` projection is **removed** (no
`target_user_id` to project to).

### 3.8 Channel drivers: no changes

R95 does not modify any channel driver. `cli`, `fs_sandbox`, `os_command`
keep their existing R84/R86 op specs. The R95 change is purely *exposure*
(channel state is now in the prompt) and *schema surgery* (LLM-facing
envelope is simplified).

### 3.9 Trade-offs

| Trade-off | R94 | R95 |
|---|---|---|
| Schema verbosity | 14 fields, 5 explicit branches | 5 fields, 1 explicit branch |
| LLM agency over action | partial (`action_intent` taxonomy) | full (`tool_op` is the single decision) |
| LLM agency over channel | partial (only `bound_user_ids` hint) | full (every op's `required_params` + `risk_class` is exposed) |
| Identity handling | LLM fills `target_user_id` (untrusted); composition projects `current_operator_id` as a fallback; engine auto-injects it | **Identity is the LLM's content decision only**; the composition makes NO identity projection; the engine does NOT auto-inject `target_user_id` from any source; channels do not mark `source_user_id` (it's not a feature) |
| Continuation decision | LLM `wants_to_continue` is one of 3 inputs | LLM `thinking_complete` is advisory; OWNER floors are authoritative |
| System prompt length | ~1500 tokens | ~1700 tokens (+~200 for Available channels; +~50 for new schema lines) |
| Test surface | 14 envelope fields × multiple paths | 5 fields × 1 path; structural tests are simpler |

## 4. Implementation Plan

See `task.md` for the per-task breakdown. High-level:

- **T1-T3**: constants + dataclass + parsers (in `contracts.py` and `engine.py`).
- **T4-T5**: engine precedence rewrite + continuation rewrite + self-revision rewrite.
- **T6**: system-prompt rewrite (Available channels section + 5-field schema).
- **T7**: composition projection of `ChannelStateSnapshot`.
- **T8-T10**: structural tests (no behavior-suggestive literals, channel_request,
  available channels, thinking_complete) + emit_proposal_r95 tests.
- **T11**: update existing tests (renames / field swaps) — ~7 test files.
- **T12**: real-LLM probes (8 JSONs, 4 rewritten + 4 new).
- **T13**: doc sync (ROADMAP, OWNER_GUIDE, PROGRESS_FLOW, requirements/index).
- **T14**: full test suite + commit.

## 5. Open Questions Resolved by User (Q1-Q10)

| Q | Decision | Implemented in |
|---|---|---|
| Q1 | B: merge `action_intent` into `tool_op` | §3.1, §3.4, §3.6 |
| Q2 | B: replace `wants_to_continue` with `thinking_complete: bool` (OWNER authoritative) | §3.3, §3.5 |
| Q3 | A: delete `proposed_action` / `self_revision` whole objects | §3.2 |
| Q4 | A: expose all ready channels × ops to LLM | §3.6, §3.7 |
| Q5 | 完全移除 reply 类提示 + add `channel_request` | §3.2, §3.3, §3.6 |
| Q6 | A: 8 probes (4 R94-rewritten + 4 R95-new) | requirement §5.2 |
| Q7 | A: probe 04 checks `tool_op` absence | requirement §5.2 |
| Q8-Q10 | remove top-level `target_user_id`; do NOT auto-inject; do NOT project any "current operator"; identity is the LLM's content decision only | §3.2, §3.4, §3.6, §3.7 |

## 6. References

- `requirement.md` (this folder) — the user-facing requirement.
- `task.md` (this folder) — the per-task implementation breakdown.
- `docs/ROADMAP.zh-CN.md` §10 W2.6 — the R95 row.
- `docs/requirements/94-drop-i-want-to-say-llm-agency/` — the R94
  one-field predecessor (for diff-style comparison).
- `helios_v2/channel/contracts.py` — `ChannelStateSnapshot` and
  `ChannelOpSpec` (the per-op self-description).
- `helios_v2/internal_thought/contracts.py` — the post-R94
  `StructuredThoughtEvidence` (R95's diff target).
- `helios_v2/composition/bridges.py` — the prompt-contract projection
  (R95's addition point).
