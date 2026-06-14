# Task 95 — Behavior-Neutral Schema; Channel Self-Describes; LLM Has Full Agency

> Implementation task breakdown for R95 (W2.6). Mirrors R94's discipline:
> each task is a single coherent diff that compiles + tests green on its
> own. Tasks are ordered to minimize cascading churn:
>
> 1. constants + dataclass (the contract shape)
> 2. parsers (the envelope contract)
> 3. engine precedence (the emit_proposal rewrite)
> 4. continuation + self-revision rewrites
> 5. system-prompt rewrite (Available channels section)
> 6. composition projection
> 7. tests + structural regressions
> 8. probes + docs + commit

## T1. Remove 8 constants from `contracts.py` (R95, prerequisite)

**File**: `src/helios_v2/internal_thought/contracts.py`

**Diff**:
- Remove `REPLY_TEXT_MAX_CHARS`, `REPLY_TEXT_TRUNCATION_SUFFIX`
  (R94 was the only user).
- Remove `TARGET_USER_ID_MAX_CHARS`, `TARGET_USER_ID_TRUNCATION_SUFFIX`
  (R93 P2 was the only user; the top-level field is removed).
- Remove `ACTION_INTENT_REPLY`, `ACTION_INTENT_TOOL`,
  `ACTION_INTENT_NO_ACTION`, `_ACTION_INTENT_VALUES` (R93 P2 was the only
  user; `action_intent` is merged into `tool_op`).
- Update the imports of `REPLY_TEXT_*` / `TARGET_USER_ID_*` /
  `ACTION_INTENT_*` in `engine.py` (will be done in T2).
- Add a module-level comment block at the top of the constant section
  describing the R95 envelope surface: 5 fields, single decision point.

**Acceptance**:
```python
python -c "from helios_v2.internal_thought.contracts import REPLY_TEXT_MAX_CHARS"
# raises ImportError
python -c "from helios_v2.internal_thought.contracts import ACTION_INTENT_REPLY"
# raises ImportError
```

**Why first**: every subsequent task imports the new surface.

## T2. Evidence dataclass: 14 fields → 5 fields (R95, breaking)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `StructuredThoughtEvidence`:

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
    # R85: tool intent (now the single primary action-class field).
    # R95: empty tool_op ≡ no action; non-empty tool_op ≡ the model picked this op.
    tool_op: str = ""
    tool_params: Mapping[str, object] = MappingProxyType({})
```

**Removed fields** (11): `wants_to_continue`, `continue_reason`,
`intends_action`, `action_summary`, `intends_self_revision`,
`self_revision_summary`, `intends_tool_use`, `reply_text`, `action_intent`,
`target_user_id`. The import block at the top of `engine.py` must be
updated to remove `REPLY_TEXT_*` / `TARGET_USER_ID_*` / `ACTION_INTENT_*`
imports (from T1).

**Acceptance**:
```python
python -c "
from helios_v2.internal_thought.engine import StructuredThoughtEvidence
ev = StructuredThoughtEvidence(thought_text='x', model_sufficiency=0.5)
print(ev.thinking_complete, ev.tool_op, ev.channel_request)
"
# prints: True   None
```

**Why second**: T3 (parsers) needs the new field shape.

## T3. Parsers: remove 7, add 2 (R95)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff**:

### Remove (7 functions):
- `_optional_reply_text` (R94)
- `_optional_action_intent` (R93 P2)
- `_optional_target_user_id` (R93 P2)
- `_optional_tool_intent` (R85) — its function is replaced by the
  in-line `tool_op` / `tool_params` parsing in T3.5 below.
- The inline parsing of `proposed_action.intends_action` and
  `self_revision.intends_revision` in `_parse_structured_thought`
  (R95 removes the whole objects).

### Add / replace (2 functions):
- `_optional_thinking_complete` (NEW): parses `thinking_complete`.
  Semantics: absent / null ⇒ `True`; non-bool ⇒
  `StructuredThoughtParseError`; bool ⇒ as-is.
- `_optional_channel_request` (NEW): parses `channel_request`.
  Semantics: absent / null ⇒ `None`; non-object ⇒
  `StructuredThoughtParseError`; object ⇒ `MappingProxyType(<obj>)`.

### Replace `_parse_structured_thought` body:
- Remove the `wants_to_continue` / `continue_reason` / `proposed_action` /
  `self_revision` / `reply_text` / `i_want_to_use_tool` / `action_intent` /
  `target_user_id` parsing.
- Add the `thinking_complete` and `channel_request` parsing.
- Inline the `tool_op` / `tool_params` parsing (replacing
  `_optional_tool_intent`).

**Acceptance**:
```python
# Old fields silently ignored
python -c "
from helios_v2.internal_thought.engine import _parse_structured_thought
ev = _parse_structured_thought('{\"thought\": \"x\", \"sufficiency\": 0.5, '
                                '\"wants_to_continue\": true, \"i_want_to_use_tool\": true, '
                                '\"action_intent\": \"reply\", \"reply_text\": \"hi\"}')
print(ev.tool_op, ev.thinking_complete, ev.channel_request)
"
# prints: ''  True  None   (the old fields are silently ignored)

# New fields work
python -c "
from helios_v2.internal_thought.engine import _parse_structured_thought
ev = _parse_structured_thought('{\"thought\": \"x\", \"sufficiency\": 0.5, '
                                '\"tool_op\": \"reply_message\", '
                                '\"tool_params\": {\"outbound_text\": \"hi\"}, '
                                '\"thinking_complete\": false, '
                                '\"channel_request\": {\"needed_capability\": \"send_qq\"}}')
print(ev.tool_op, ev.tool_params, ev.thinking_complete, ev.channel_request)
"
# prints: reply_message  {'outbound_text': 'hi'}  False  {'needed_capability': 'send_qq'}
```

**Why third**: T4 (engine precedence) needs the new evidence shape.

## T4. Engine precedence rewrite: 5 branches → 1 branch (R95, core)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `_derive_thought_judgment._emit_proposal` (the
`if continuation_requested: ... else: ...` block):

### Remove (the R94 five-branch precedence):
- `tool_intent` derivation (now redundant with `evidence.tool_op` non-empty).
- `explicit_no_action` derivation (now folded into "tool_op empty").
- `reply_explicit_path` derivation (now folded into "tool_op non-empty
  with `tool_op='reply_message'`").
- `explicit_tool_path_via_intent` derivation (now folded into "tool_op
  non-empty").
- `target_user_id` resolution block (no top-level `target_user_id`;
  `target_user_id` now comes from `request.prompt_contract_summary`).

### Add (the R95 single-point decision):
```python
else:
    # R95: emit an action proposal only when the model picked a tool_op.
    # Empty/missing tool_op ⇒ cycle closes internal-only (no_action).
    # The single decision point: evidence.tool_op is truthy.
    if evidence is not None and evidence.tool_op:
        ready_channels = request.prompt_contract_summary.get("ready_channels", ())
        preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
        # R95: target_user_id comes from the prompt-contract summary
        # (composition-projected from channel state), not from the LLM.
        target_user_id = ""
        operator_value = request.prompt_contract_summary.get("current_operator_id", "")
        if isinstance(operator_value, str):
            target_user_id = operator_value.strip()
        op_params = dict(evidence.tool_params)
        if target_user_id and "target_user_id" not in op_params:
            op_params["target_user_id"] = target_user_id
        action_proposal = ThoughtActionProposalCarrier(
            proposal_id=f"thought-action:{request.request_id}",
            scope="external",
            behavior_name=evidence.tool_op,
            requested_op=evidence.tool_op,
            preferred_channels=preferred_channels,
            outbound_text=None,
            outbound_intensity=0.75,
            reason_trace=("thought picked a tool op for the current cycle",),
            governance_hints={"requires_identity_review": False},
            op_params=MappingProxyType(op_params),
        )
    elif evidence is None:
        # Phase 1 acceptance criterion (R93, preserved): the deterministic
        # offline path emits reply_message with outbound_text=thought.content.
        # Byte-for-byte unchanged from R93 P1.
        action_proposal = ThoughtActionProposalCarrier(
            proposal_id=f"thought-action:{request.request_id}",
            scope="external",
            behavior_name="reply_message",
            requested_op="reply_message",
            preferred_channels=("cli",),
            outbound_text=thought.content,
            outbound_intensity=0.75,
            reason_trace=("thought judged sufficient for current cycle",),
            governance_hints={"requires_identity_review": False},
        )
    # else: tool_op empty/missing ⇒ action_proposal stays None (no_action).
```

**Acceptance**: see `test_internal_thought_emit_proposal_r95.py` (T9 below).

**Why fourth**: T5 (continuation + self-revision) needs the new emit_proposal shape.

## T5. Continuation + self-revision rewrites (R95, owner-only)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `_derive_thought_judgment` (the upper block, before
`_emit_proposal`):

### Continuation decision:
```python
if runtime_forces_continue or low_context_forces_continue:
    continuation_requested = True
    continuation_reason = "need_more_context"
elif evidence is None:
    continuation_requested = False
    continuation_reason = "sufficient_for_current_cycle"
elif evidence.thinking_complete is False:
    # R95: the model's thinking_complete=False is ADVISORY; the OWNER's
    # floors remain authoritative. We accept the signal as a soft
    # continuation trigger only when the model's thought still has
    # reasoning hooks (heuristic). For now, this is a simple string check
    # on the thought text.
    thought_text = evidence.thought_text
    has_unresolved_hooks = (
        thought_text.rstrip().endswith(("...", "…", "?", "？"))
        or "let me think" in thought_text.lower()
        or "still need" in thought_text.lower()
    )
    if has_unresolved_hooks:
        continuation_requested = True
        continuation_reason = "model_thinking_incomplete"
    else:
        continuation_requested = False
        continuation_reason = "sufficient_for_current_cycle"
else:
    continuation_requested = False
    continuation_reason = "sufficient_for_current_cycle"
```

### Self-revision (OWNER-only):
```python
self_revision_allowed_by_owner = bool(autobiographical) and sufficiency_level >= 0.75
# R95: no model_intends_self_revision gate. The OWNER is the only authority.
self_revision_requested = self_revision_allowed_by_owner
```

**Acceptance**:
- When `runtime_forces_continue=True`, `continuation_requested=True` regardless
  of `thinking_complete`.
- When `thinking_complete=False` but the thought text has no unresolved
  hooks, `continuation_requested=False` (OWNER ignores the advisory signal).
- Self-revision fires when the OWNER's floor is met, regardless of any
  (now-removed) model field.

**Why fifth**: T6 (system-prompt rewrite) needs the new evidence shape
referenced in the prompt text.

## T6. System prompt rewrite: Available channels section (R95, core)

**File**: `src/helios_v2/internal_thought/engine.py`

**Diff** in `LlmBackedInternalThoughtPath._build_messages` (the
`system_lines` block):

### Remove (8 R94 lines + special-casing):
- `wants_to_continue`, `continue_reason` (the 2 lines)
- `proposed_action`, `self_revision` (the 2 objects, 4 lines)
- `action_intent`, `reply_text` (the 2 lines)
- `target_user_id` (the 1 line)
- `i_want_to_use_tool` (the 1 line in the same `tool_op` row)
- The "Action class is a CHOICE..." paragraph (the reply / tool / no_action
  enumeration)
- The "Do NOT reflexively reply..." paragraph (the special-casing of reply)
- The "When you set 'action_intent' to 'reply' AND supply 'reply_text'..."
  transport clause (no longer relevant)

### Add (the 5 R95 lines + Available channels section):
- `thought`, `sufficiency`, `tool_op`, `tool_params`, `thinking_complete`,
  `channel_request`, `hormone_response_i_predict` (the 5 R95 fields +
  the unchanged R81 hormone field).
- A new "Available channels" section that reads
  `prompt_contract_summary["available_channel_ops"]` and renders:
  ```
  Available channels (you may pick any one tool op per cycle, or pick none):

    1. cli
       - reply_message: required_params=[outbound_text, target_user_id]
                        effect_class=external_world, risk_class=unrestricted
                        bound_user_ids=[<set>]
       - send_status:   required_params=[text]
                        effect_class=external_world, risk_class=unrestricted
                        bound_user_ids=[<set>]

    2. fs_sandbox
       - fs_read:   required_params=[path], effect_class=local_host, risk_class=unrestricted
       - fs_write:  required_params=[path, content], effect_class=local_host, risk_class=governed
       ...

    3. os_command
       - run_command: required_params=[args], effect_class=local_host, risk_class=governed
                      (requires 14 authorization carry)

  You may pick any one op from this list, or pick none (the cycle closes
  internal-only). When you do pick an op, fill `tool_op` with the op name
  and `tool_params` with the required params. The runtime validates
  `tool_params` against the op's `required_params` and routes to the
  correct channel automatically.
  ```

### Add (decision guidance):
```
- For each cycle, decide whether to act. If you do not act, leave `tool_op`
  empty/missing; the cycle closes internal-only.
- If you do act, pick one op from the Available channels list. The
  runtime validates `tool_params` against the op's `required_params` and
  routes to the matching channel automatically.
- The channel that received the current stimulus is marked as
  `source_user_id` in the prompt; you do not need to fill a target user
  id — the runtime resolves it from the channel state.
- Do NOT reflexively reply. A low-salience or acknowledgment stimulus may
  legitimately close with no action.
- If you find yourself wanting an op that no channel offers, fill
  `channel_request` so a future iteration can track the gap.
```

**Acceptance**: see `test_internal_thought_no_behavior_suggestive_in_prompt.py`
and `test_internal_thought_available_channels_in_prompt.py` (T8 below).

**Why sixth**: T7 (composition) needs the new prompt-contract field name
to project from.

## T7. Composition: project `available_channel_ops` (R95)

**File**: `src/helios_v2/composition/bridges.py`

**Diff** in the `SemanticInternalThoughtRequestBridge` (or equivalent
bridge that projects `prompt_contract_summary`):

```python
# R95: project ready channels × ops to prompt-contract summary.
# R95 also REMOVES the _current_operator_id projection. Channels do not
# mark source_user_id (it's not a feature, and many channels like CLI
# have no ability to mark it). The LLM is the only source of
# target_user_id (in tool_params); the engine does not auto-inject.
channel_state = request.prompt_contract_summary.get("channel_state")
if channel_state is not None:
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
else:
    available_channel_ops = ()
prompt_contract_summary["available_channel_ops"] = available_channel_ops
# R95: NO current_operator_id projection. NO source_user_id projection.
# The helper function _current_operator_id (R93 P2) and its call site in
# bridges.py are REMOVED.
```

**Acceptance**: `test_internal_thought_available_channels_in_prompt.py`
verifies the projection; `test_internal_thought_no_target_user_id_projection.py`
(T8.5 below) verifies that `current_operator_id` is NOT in the
prompt-contract summary.

**Why seventh**: T8 (tests) needs the full implementation done first.

## T8. New structural regression tests (R95)

**Files** (4 new tests):

### `tests/test_internal_thought_no_behavior_suggestive_in_prompt.py` (4 tests)

```python
def test_system_prompt_does_not_contain_reply_text():
    """R95: reply_text is removed from the schema; the system prompt must not mention it."""

def test_system_prompt_does_not_contain_i_want_to_use_tool():
    """R95: i_want_to_use_tool is removed; the system prompt must not mention it."""

def test_system_prompt_does_not_contain_wants_to_continue():
    """R95: wants_to_continue is removed; replaced by thinking_complete."""

def test_system_prompt_does_not_contain_action_intent_or_target_user_id():
    """R95: action_intent and target_user_id (top-level) are removed;
    the system prompt must not mention them. The owner's reflection
    should also not contain these fields in the StructuredThoughtEvidence
    constructor signature."""
```

### `tests/test_internal_thought_thinking_complete_field.py` (4 tests)

```python
def test_thinking_complete_default_true():
    """R95: thinking_complete absent / null ⇒ True (model indicated completion)."""

def test_thinking_complete_explicit_false():
    """R95: thinking_complete=False is advisory; OWNER's continuation floors remain authoritative."""

def test_thinking_complete_non_bool_raises():
    """R95: non-bool thinking_complete raises StructuredThoughtParseError."""

def test_continuation_floor_overrides_thinking_complete():
    """R95: when runtime_forces_continue is active, the cycle continues
    even if thinking_complete=True (the OWNER's floor wins)."""
```

### `tests/test_internal_thought_channel_request_field.py` (3 tests)

```python
def test_channel_request_absent_or_null_is_none():
    """R95: channel_request absent / null ⇒ None; no gap-tracker in R95."""

def test_channel_request_object_is_carried():
    """R95: channel_request as an object is parsed and passed through to the trace."""

def test_channel_request_non_object_raises():
    """R95: non-object channel_request raises StructuredThoughtParseError."""
```

### `tests/test_internal_thought_available_channels_in_prompt.py` (4 tests)

```python
def test_available_channels_section_rendered_when_ops_present():
    """R95: when available_channel_ops is non-empty in the prompt-contract
    summary, the system prompt contains an 'Available channels' section
    listing each op."""

def test_available_channels_section_omitted_when_empty():
    """R95: when available_channel_ops is empty, the system prompt does
    NOT contain the 'Available channels' section (the model has no
    channels to act on)."""

def test_available_channels_includes_op_required_params():
    """R95: each op listed in the Available channels section includes
    the op_name, required_params, effect_class, risk_class, and bound_user_ids."""

def test_available_channels_does_not_special_case_reply_message():
    """R95: reply_message appears in the Available channels section only
    if a driver offers it as an op (it is not promoted or called out
    as a special case). The cli driver offers reply_message as one of
    its ops alongside send_status; the LLM is free to pick either."""
```

### `tests/test_internal_thought_no_target_user_id_projection.py` (3 tests) — **T8.5 NEW**

```python
def test_no_current_operator_id_in_prompt_contract_summary():
    """R95: the prompt-contract summary does NOT contain a
    `current_operator_id` field. The R93 P2 composition projection is
    REMOVED. Channels do not mark source_user_id; the LLM is the only
    source of target_user_id (in tool_params)."""

def test_engine_does_not_auto_inject_target_user_id():
    """R95: when the model picks `tool_op='reply_message'` with
    `tool_params={'outbound_text': 'hi'}` (NO target_user_id), the
    engine does NOT inject any target_user_id. The tool proposal's
    op_params is exactly `{'outbound_text': 'hi'}` (no auto-injection)."""

def test_llm_supplied_target_user_id_passes_through():
    """R95: when the LLM supplies `tool_params={'outbound_text': 'hi',
    'target_user_id': 'user-123'}`, the engine passes it through
    verbatim. The engine makes no modification to the LLM's
    target_user_id value (no trimming, no defaulting, no override)."""
```

**Acceptance**: all 18 new tests pass.

## T9. New emit_proposal R95 tests (R95, owner-only logic)

**File**: `tests/test_internal_thought_emit_proposal_r95.py` (8 tests)

```python
def test_tool_op_non_empty_emits_proposal():
    """R95: tool_op='reply_message' + tool_params={'outbound_text': '...'}
    ⇒ action_proposal is non-None with behavior_name='reply_message'."""

def test_tool_op_empty_emits_no_proposal():
    """R95: tool_op='' (or absent) ⇒ action_proposal is None (no_action)."""

def test_tool_op_fs_read_emits_proposal():
    """R95: tool_op='fs_read' + tool_params={'path': '...'}
    ⇒ action_proposal is non-None with behavior_name='fs_read'."""

def test_tool_op_qq_send_message_emits_proposal():
    """R95: tool_op='qq.send_message' + tool_params={'text': '...'}
    ⇒ action_proposal is non-None with behavior_name='qq.send_message'."""

def test_deterministic_offline_path_unchanged():
    """R95: evidence=None ⇒ action_proposal is non-None with
    behavior_name='reply_message' (R93 P1 acceptance criterion preserved)."""

def test_target_user_id_passes_through_verbatim():
    """R95: when the LLM supplies tool_op='reply_message' with
    tool_params={'outbound_text': 'hi', 'target_user_id': 'user-123'},
    the proposal's op_params include exactly those keys/values
    (the engine makes no modification to the LLM's target_user_id).
    When the LLM does NOT supply target_user_id, the proposal's
    op_params is exactly {'outbound_text': 'hi'} (no auto-injection)."""

def test_old_fields_silently_ignored():
    """R95: a payload with old R94 fields (wants_to_continue,
    i_want_to_use_tool, action_intent, reply_text, target_user_id)
    plus new R95 fields parses correctly; the old fields do not
    affect the evidence."""

def test_self_revision_owner_only():
    """R95: self_revision_proposal is constructed when the OWNER's
    autobiographical + sufficiency floor is met, regardless of any
    model field. (No model field affects self-revision in R95.)"""
```

**Acceptance**: all 8 tests pass.

## T10. Update existing tests (R95, compatibility)

**Files** (7 existing test files; field renames / swaps):

- `tests/_internal_thought_test_fixtures.py`: `envelope()` helper updated
  to add `thinking_complete` / `channel_request` and remove 11 R94 fields.
- `tests/test_internal_thought_engine.py`: `FakeThoughtGateway` /
  `JsonThoughtGateway` updated to R95 envelope shape.
- `tests/test_runtime_composition.py`: `FakeThoughtProvider` updated to
  R95 envelope shape.
- `tests/test_internal_thought_build_messages_reply_clause.py` →
  renamed to `test_internal_thought_build_messages_available_channels.py`
  (the test now verifies the Available channels section instead of the
  reply clause).
- `tests/test_internal_thought_no_i_want_to_say_in_prompt.py` →
  renamed to `test_internal_thought_no_behavior_suggestive_in_prompt.py`
  (the test now asserts all 7 family literals are absent, not just
  `i_want_to_say`).
- `tests/test_internal_thought_emit_proposal_phase2.py` → kept (it
  tests the offline deterministic path; unchanged by R95).
- `tests/test_internal_thought_parse_action_intent.py` → removed
  (no more `action_intent` field).
- `tests/test_internal_thought_parse_reply_text.py` → removed
  (no more `reply_text` field).
- `tests/test_internal_thought_emit_proposal_r94.py` → renamed to
  `test_internal_thought_emit_proposal_r95.py` (T9 above).

**Acceptance**: all renamed / updated / removed tests pass; no test
references the 11 R94 fields or the 3 R95-deleted constants.

## T11. Real-LLM probes (8 JSONs, 4 rewritten + 4 new)

**Files**: `helios_v2/scripts/r95_probes/01..08_*.json`

### Rewritten (4):
- `01_basic_reply.json`: stimulus is the same high-salience emotional
  disclosure (苏蕊 / pre-defense anxiety); `must_contain` now requires
  `tool_op` and `reply_message`; `must_not_contain` requires
  `i_want_to_say`, `reply_text`, `action_intent`.
- `02_silence_negative_control.json`: stimulus is interoception-only;
  `must_not_contain` requires `tool_op` (or `must_contain` requires
  `thought` only).
- `03_action_choice.json`: stimulus is "I'm overwhelmed with work";
  `must_contain_any` requires `tool_op`.
- `04_no_action_when_unmoved.json`: **R95 KEY PROBE** — stimulus is
  low-salience "ok" CLI ack; `must_contain` requires `thought`;
  `must_not_contain` requires `tool_op` (the LLM should not pick any
  op on a low-salience stimulus).

### New (4):
- `05_received_no_reply.json`: stimulus is "我看到了你之前的回复"
  (confirmation only); `must_contain` requires `thought`;
  `must_not_contain` requires `tool_op`. **Confirms the model doesn't
  reflexively reply to a confirmation message.**
- `06_pure_punctuation.json`: stimulus is "……"; `must_contain`
  requires `thought`; `must_not_contain` requires `tool_op`. **Confirms
  the model doesn't reflexively reply to pure punctuation.**
- `07_tool_choice.json`: stimulus is "帮我查一下明天天气" (asking for
  a tool, not a reply); `must_contain` requires `tool_op` (the model
  should pick a `weather_op` or similar, not `reply_message`);
  `must_not_contain` requires `reply_message` literal. **R95 KEY:
  model picks a tool op, not a reply op, when the stimulus asks for
  tool use.**
- `08_cross_channel_routing.json`: stimulus is "把这段发到 QQ" (asking
  to send via QQ, not CLI); `must_contain` requires `tool_op` and the
  literal `qq` (case-insensitive) in the tool_op or tool_params;
  `must_not_contain` requires `cli` as the sole channel. **R95 KEY:
  model autonomously routes to the requested channel, not default CLI.**

**Acceptance**: all 8 probes pass; probe 04 / 07 / 08 are the R95
key probes and must show the new behavior.

## T12. Doc sync (R95)

**Files**:
- `docs/ROADMAP.zh-CN.md` (already updated in this turn: W2.6 R95 row
  added; old R95-R97 renumbered to R98-R100; old R98+ renumbered to
  R101+).
- `docs/OWNER_GUIDE.md` / `OWNER_GUIDE.zh-CN.md`: add R95 row to the
  per-requirement maturity table.
- `docs/PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md`: update the
  last-synced line.
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md`: update the
  `gap_execution_closure` row to reflect R95.
- `docs/ARCHITECTURE_BOUNDARIES.md`: append R95 migration history note.
- `docs/requirements/index.md`: add R95 row.
- `docs/requirements/95-behavior-neutral-schema/probe_04_comparison.md`
  (new): R95 result comparison vs R94 baseline.
- `helios_v2/docs/API_AND_OPS_CONTRACT_GUIDE.md`: document the new
  envelope surface.

**Acceptance**: all doc files consistent with R95 design.

## T13. Test baseline + commit (R95)

**Action**:
- Run the full network-independent test suite: `pytest tests/`.
- Expect ~1240+ passed / 4 skipped / 0 regression.
- Run the 8 R95 real-LLM probes against the live MiniMax-M3 endpoint.
- Commit all R95 changes (engine.py, contracts.py, bridges.py, tests,
  probes, docs) as a single follow-up commit on top of R94 (or branch
  off R94 if preferred).
- The commit message references R95 design decisions (Q1-Q10).

**Acceptance**:
- `git log --oneline -3` shows the R95 commit on top of R94.
- `git status` is clean.
- All 8 R95 probes PASS in the saved JSON reports.

## 14. Reference

- `requirement.md` (this folder).
- `design.md` (this folder).
- `docs/requirements/94-drop-i-want-to-say-llm-agency/task.md` — the
  R94 task list (R95 follows a similar structure, but with deeper
  schema surgery).
- ROADMAP §10 W2.6.
