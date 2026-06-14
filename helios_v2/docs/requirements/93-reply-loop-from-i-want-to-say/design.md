# Requirement 93 - Reliable Reply Loop From `i_want_to_say` — Design

## 1. Design Overview

R93 is a strictly additive change in three small surfaces that closes the
"LLM intends to reply -> 11 normalizes -> 13 binds reply_message -> CLI dispatch"
chain the R91 emotion long-run found broken at two ends:

1. **Parse**: `_parse_structured_thought` learns to read the top-level
   `i_want_to_say` field already named in the engine's system prompt; the parsed
   text lands in a new `StructuredThoughtEvidence.intended_reply_text` slot.
2. **Emit**: `11`'s `_emit_proposal` gains an **implicit reply branch** below the
   explicit `tool_op` precedence — when `intended_reply_text` is non-empty and no
   explicit tool intent is set, the owner constructs a `reply_message` tool intent
   with `op_params={"outbound_text": <text>, "target_user_id": <operator id>}`,
   so R85's existing planner spine validates and binds it like any other effector.
3. **Project**: composition adds one owner-neutral key `current_operator_id` to the
   `prompt_contract_summary`, projected from the same-frame `02 sensory_ingress`
   external stimulus's `source_name` (using the same `_INTERNAL_MODALITIES` filter
   R91 / R92 already use). When no operator is present the value is `""`, and
   `11`'s implicit reply branch silently abstains (no fabricated target).

The system-prompt schema description is updated to tell the model that
`i_want_to_say`, when set, will be transported as a real `reply_message` to the
current operator through `cli`. This is one bounded clause; the schema itself is
otherwise unchanged.

The legacy `emit_action` fallback path (taken when `evidence is None`, the
deterministic offline assembly) is unchanged on its inputs and outputs. R85's
explicit `tool_op` path is unchanged.

## 2. Current State and Gap

- `_parse_structured_thought` (`internal_thought/engine.py` ~L295-L370) reads
  `thought` / `sufficiency` / `wants_to_continue` / `continue_reason` /
  `proposed_action.intends_action` / `self_revision.intends_revision` / optional
  `hormone_response_i_predict` (R81) / optional `i_want_to_use_tool` / `tool_op` /
  `tool_params` (R85). It **does not** read `i_want_to_say` even though
  `_build_messages` writes `"i_want_to_say": "<optional words to say outward>"`
  into the system prompt.
- `_emit_proposal` (~L495-L535) has three branches:
  1. continuation requested -> save handoff, no proposal;
  2. explicit tool intent (`evidence.intends_tool_use and evidence.tool_op`) ->
     build proposal with `op_params=evidence.tool_params`;
  3. fallback `emit_action` (when `evidence is None` OR
     `model_intends_action` is true) -> build proposal with
     `behavior_name="reply_message"`, `outbound_text=thought.content`,
     `preferred_channels=("cli",)`, **no `op_params`**.
  Branch (3) carries the **narration** as outbound text and supplies no
  `target_user_id`. R85's `13` planner-bridge `required_params` validation
  (`reply_message` requires `outbound_text` AND `target_user_id`) rejects this
  with `missing_op_inputs`, producing a `world_blocked` continuity record. CLI
  sees nothing.
- The composition `prompt_contract_summary` already carries `ready_channels` and
  other capability hints. It does **not** carry the operator's identity, so even
  if `11` knew the model wanted to reply, it could not fill `target_user_id`.
- The system prompt today lists `i_want_to_say` as "optional words to say outward"
  but does not tell the model that the runtime will actually transport that text.
  The model fills it inconsistently; some replies show 1st-person inner monologue
  rather than direct operator-addressed content.

## 3. Target Architecture

### 3.1 Contract change (`internal_thought/contracts.py`)

```python
INTENDED_REPLY_TEXT_MAX_CHARS: Final = 2000
INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX: Final = "…(truncated)"

@dataclass(frozen=True)
class StructuredThoughtEvidence:
    ...existing fields...
    tool_params: Mapping[str, object] = MappingProxyType({})
    intended_reply_text: str = ""   # NEW (additive)
```

Validation: `intended_reply_text` is normalized to a stripped string; over-cap is
deterministically truncated with `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX`. Default
`""` preserves byte-for-byte the pre-R93 evidence shape.

### 3.2 Parser update (`internal_thought/engine.py`)

In `_parse_structured_thought`:

```python
intends_tool_use, tool_op, tool_params = _optional_tool_intent(payload)

intended_reply_text = ""
if "i_want_to_say" in payload and payload["i_want_to_say"] is not None:
    raw = payload["i_want_to_say"]
    if not isinstance(raw, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'i_want_to_say' must be a string when present"
        )
    stripped = raw.strip()
    if stripped:
        if len(stripped) > INTENDED_REPLY_TEXT_MAX_CHARS:
            cap = INTENDED_REPLY_TEXT_MAX_CHARS - len(INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX)
            intended_reply_text = stripped[:cap] + INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX
        else:
            intended_reply_text = stripped

return StructuredThoughtEvidence(
    ...existing fields...,
    intended_reply_text=intended_reply_text,
)
```

Accepted shapes:
- absent / null / empty / whitespace-only -> `""`,
- non-empty string -> trimmed string (cap-truncated as needed),
- non-string -> raises (existing fail-fast discipline).

### 3.3 Emit-proposal update (`internal_thought/engine.py`)

In `_emit_proposal` after the existing `tool_intent` flag, add:

```python
explicit_tool_intent = (
    evidence is not None and evidence.intends_tool_use and bool(evidence.tool_op)
)
implicit_reply_intent = (
    evidence is not None
    and not explicit_tool_intent
    and bool(evidence.intended_reply_text)
    and bool(_current_operator_id_from(request))
)
emit_action = (
    evidence is None
    or model_intends_action
    or explicit_tool_intent
    or implicit_reply_intent
)
```

The proposal-construction block becomes:

```python
if explicit_tool_intent:
    # existing R85 path; unchanged
    ...
elif implicit_reply_intent:
    operator_id = _current_operator_id_from(request)  # already non-empty
    ready_channels = request.prompt_contract_summary.get("ready_channels", ())
    preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
    action_proposal = ThoughtActionProposalCarrier(
        proposal_id=f"thought-action:{request.request_id}",
        scope="external",
        behavior_name="reply_message",
        requested_op="reply_message",
        preferred_channels=preferred_channels,
        outbound_text=None,            # text lives in op_params (R85 spine)
        outbound_intensity=0.75,
        reason_trace=("thought intends to reply to the current operator",),
        governance_hints={"requires_identity_review": False},
        op_params=MappingProxyType({
            "outbound_text": evidence.intended_reply_text,
            "target_user_id": operator_id,
        }),
    )
elif emit_action:
    # legacy fallback (evidence is None OR model_intends_action without an
    # explicit tool intent and without an intended_reply_text). UNCHANGED for
    # the deterministic offline path; for the LLM path with model_intends_action
    # but no intended_reply_text, this branch keeps the prior behavior (which
    # may still be rejected by `13` when target_user_id is missing — that is
    # acceptable because the model declined to fill `i_want_to_say`).
    action_proposal = ThoughtActionProposalCarrier(...existing call...)
```

Helper:
```python
def _current_operator_id_from(request: InternalThoughtRequest) -> str:
    value = request.prompt_contract_summary.get("current_operator_id", "")
    return value.strip() if isinstance(value, str) else ""
```

### 3.4 System-prompt update (`internal_thought/engine.py._build_messages`)

Add one bounded clause to `system_lines` after the `proposed_action` line, before
`Set wants_to_continue and intends_action to false ...`:

```python
'  "i_want_to_say": "<optional words to say outward as a reply to the current operator>",',
```

And one explicit transport clause appended at the end of `system_lines`:

```text
"When you set 'i_want_to_say' to a non-empty string, the runtime will transport
that text as a 'reply_message' to the current operator through the 'cli' user-
visible channel. Use 'i_want_to_say' for direct operator-addressed replies; use
'i_want_to_use_tool' / 'tool_op' / 'tool_params' for non-reply effectors only."
```

This is one declarative paragraph, no schema rewrite.

### 3.5 Composition projection (`composition/bridges.py`)

Add an owner-neutral helper:

```python
def _current_operator_id(frame) -> str:
    """Owner: composition (R93). Project the same-frame `02 sensory_ingress`
    earliest external stimulus's `source_name` as the current operator id.

    Reads only published `02` fields. Filters internal modalities (`body` /
    `interoceptive` / `background`) so an interoceptive afferent never becomes a
    "speaker" reply target. Returns `""` when no external stimulus is present
    (honest absence; never invents a target_user_id).
    """
    from helios_v2.runtime.stages import SensoryIngressStageResult

    stage_results = frame.stage_results or {}
    sensory = stage_results.get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult):
        return ""
    for stimulus in sensory.batch.stimuli:
        if stimulus.modality in _INTERNAL_MODALITIES:
            continue
        if stimulus.source_name:
            return stimulus.source_name
    return ""
```

Both `SemanticInternalThoughtRequestBridge.build_request` and
`FirstVersionInternalThoughtRequestBridge.build_request` add to their
`prompt_contract_summary` dict:

```python
"current_operator_id": _current_operator_id(frame),
```

This is owner-neutral: composition reads only published `02` and forwards the
fact verbatim. `11` consumes it as a flat string and never imports `02`.

## 4. Data Structures

### 4.1 `StructuredThoughtEvidence` (additive)

```python
@dataclass(frozen=True)
class StructuredThoughtEvidence:
    ...existing fields...
    tool_params: Mapping[str, object] = MappingProxyType({})
    intended_reply_text: str = ""   # NEW (additive)
```

### 4.2 `prompt_contract_summary` reserved keys

The `prompt_contract_summary` mapping (already passed through
`InternalThoughtRequest`) gains one reserved key string:

```python
# Reserved in helios_v2.composition.bridges:
"current_operator_id": str  # earliest same-frame external stimulus's source_name; "" when absent
```

This is documentation; the dict already carries arbitrary string keys.

### 4.3 Implicit-reply `ThoughtActionProposalCarrier` shape

The carrier shape itself does not change. The implicit-reply branch sets:

| field | value |
| --- | --- |
| `behavior_name` | `"reply_message"` |
| `requested_op` | `"reply_message"` |
| `outbound_text` | `None` (data lives in `op_params`) |
| `op_params["outbound_text"]` | `evidence.intended_reply_text` |
| `op_params["target_user_id"]` | `current_operator_id` |
| `preferred_channels` | tuple of `ready_channels` |
| `outbound_intensity` | `0.75` (matches existing R85 path) |
| `reason_trace` | `("thought intends to reply to the current operator",)` |
| `governance_hints` | `{"requires_identity_review": False}` |

## 5. Module Changes

### 5.1 `helios_v2/internal_thought/contracts.py`

- Add module-level constants `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` and
  `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"`.
- Add additive `intended_reply_text: str = ""` to `StructuredThoughtEvidence`.

### 5.2 `helios_v2/internal_thought/engine.py`

- `_parse_structured_thought` reads `i_want_to_say` per §3.2; the parser raises
  on a non-string value; the parsed string is stripped and capped.
- `_emit_proposal` adds the implicit-reply branch per §3.3, with explicit-tool
  precedence and honest-absence on missing operator id.
- `_build_messages` appends one schema line and one transport-clause line per
  §3.4.

### 5.3 `helios_v2/composition/bridges.py`

- Add the owner-neutral `_current_operator_id(frame)` helper per §3.5.
- Both internal-thought request bridges add the
  `current_operator_id` key into the `prompt_contract_summary` dict.

## 6. Module Changes (summary table)

| File | Change kind | Summary |
| --- | --- | --- |
| `helios_v2/internal_thought/contracts.py` | MOD additive | `INTENDED_REPLY_TEXT_MAX_CHARS`, `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX`, `StructuredThoughtEvidence.intended_reply_text` |
| `helios_v2/internal_thought/engine.py` | MOD | parser reads `i_want_to_say`; `_emit_proposal` implicit-reply branch; system-prompt schema clause |
| `helios_v2/composition/bridges.py` | MOD additive | `_current_operator_id(frame)` helper; both request bridges add `current_operator_id` to summary |

## 7. Migration Plan

1. **In-process migration**: every additive contract field defaults to the
   pre-R93 behavior. The parser keeps accepting envelopes that omit
   `i_want_to_say` byte-for-byte. The implicit-reply branch only activates when
   the model fills `i_want_to_say` AND there is a current operator AND no
   explicit `tool_op`. The deterministic offline path (`evidence is None`)
   remains byte-for-byte unchanged.
2. **Test migration**: existing tests that exercise the offline / no-evidence
   path keep passing without modification. New R93 tests use the network-free
   `_FakeThoughtProvider` pattern (already used by R85/R91/R92) to inject an
   envelope that fills `i_want_to_say`.
3. **Production rollout**: no flag, no opt-in. The implicit-reply branch is
   "active when the model fills the field and an operator is present" — this is
   the desired default. No legacy mode is needed because the prior behavior was
   broken (89/89 -> 1 reply); R93 fixes it.
4. **Beta-branch overlap**: the beta `aggressive-radical-persona-no-theater`
   branch's R79 work also extends the schema (a v3 envelope with `i_will_send_it`
   / `i_send_through` / etc.). R93 is independent of v3 schema reach: it
   promotes one existing field (`i_want_to_say`, already in the legacy schema)
   without touching the v3 layer. A future requirement may bring v3 schema fully
   to the LLM and unify the two paths; R93 is a strict subset.

## 8. Failure Modes and Constraints

1. **Forbidden — fabricated reply**. When `i_want_to_say` is null/empty, the
   implicit-reply branch is silent. No reply is constructed. The existing
   "internal-only" close path applies.
2. **Forbidden — fabricated target**. When `current_operator_id` is `""`, the
   implicit-reply branch is silent. The system never invents a default operator.
3. **Forbidden — `13` content authoring**. The implicit-reply branch is owned by
   `11`; the planner bridge `13` continues to validate `op_params` against the
   driver's `required_params` and reject malformed proposals (defense in depth).
4. **Forbidden — composition policy**. The composition projection only forwards
   the earliest external stimulus's `source_name`; it does not select which
   stimulus is "the operator" by any cognitive criterion (no salience read, no
   priority, no preference). The "earliest" rule mirrors R92's elapsed-clause
   ordering.
5. **Length cap**. `intended_reply_text` is bounded at 2000 chars with a
   deterministic suffix. The CLI driver's outbound buffer is bounded by its own
   config; in practice 2000 chars is well below any driver's limit.
6. **Explicit precedence**. An explicit `tool_op` (R85) wins. A model that
   fills both `i_want_to_say` and `i_want_to_use_tool=true` gets the explicit
   tool path; the reply is not emitted.

## 9. Observability and Logging

No new logging mechanism. The `21` runtime observability already records the
`13 planner_bridge` `evaluate` op (which now sees the filled `op_params`), and
the channel subsystem records the outbound-dispatch outcome. The implicit-reply
path is reconstructable from the existing timeline. No `print` / `logging` in
`src/`; the existing guards stay green.

## 10. Validation Strategy

### 10.1 Network-free unit / contract tests

| File | Asserts |
| --- | --- |
| `tests/test_internal_thought_parse_i_want_to_say.py` | parser default `""`; non-empty string preserved; whitespace-only -> `""`; non-string raises; over-cap deterministically truncated |
| `tests/test_internal_thought_implicit_reply_intent.py` | `_emit_proposal`: explicit tool wins over implicit reply; implicit reply built when `i_want_to_say` set + operator present; implicit reply silent when operator absent; deterministic offline path (`evidence is None`) unchanged |
| `tests/test_composition_current_operator_id.py` | earliest external stimulus's `source_name` returned; internal-modality stimuli skipped; empty when no external stimulus / no `02` result |
| `tests/test_runtime_stage_chain_implicit_reply.py` | end-to-end with the channel-bound semantic assembly: a CLI submission + a fake provider returning `i_want_to_say="hello"` produces a real CLI sink dispatch with `outbound_text="hello"` |

### 10.2 Composition / boundary guards

- The composition owner-boundary guard test stays green (no new owner-policy
  strings reach `composition/`; the projection helper is owner-neutral).
- The no-ad-hoc-logging guard stays green.

### 10.3 Real-LLM probes (per §8.2)

- `scripts/r93_probes/01_basic_reply.json` — system prompt with the new
  transport clause; the model should fill `i_want_to_say` with operator-
  addressed reply text (positive control).
- `scripts/r93_probes/02_silence_negative_control.json` — interoception-only
  user prompt; the model should leave `i_want_to_say` null/empty.

Output saved to git-ignored `logs/prerun/r93_probes/`; observed PASS recorded in
this design's §10.3 after run.

### 10.4 Implementation-time smoke

After the code lands, run `scripts/emotion_test_run.py` with a short visitor
fixture (5-10 messages) using the production assembly (real LLM). Confirm the
`replies` list now contains real CLI dispatches matching the model's
`i_want_to_say` content per tick, captured in the `--llm-log` JSONL alongside
the parsed envelope and the planner decision. R91 §11.2 lesson: probe verifies
the model end, smoke verifies the composition end. Both must pass.

### 10.5 Acceptance gate

The full network-free test suite (currently 1107 passed / 4 skipped) must reach
≥ 1107 + new tests passed (expected ≈ 20-25 new R93 tests) with 0 regressions;
the composition owner-boundary guard and the no-ad-hoc-logging guard remain
green; both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, the boundary doc,
the comparison doc, the index, and the ROADMAP are synced in this same change
set.

---

# Phase 2 (2026-06) - Action Agency and Cross-Channel Routing - Design

## 8. Phase 2 Design Overview

Phase 2 fixes three architectural defects in Phase 1 that the 2026-06-14
real-LLM visitor-eval surfaced:

1. **D1 (action-class default)**: Phase 1 made reply the implicit default when
   `i_want_to_say` was set. Phase 2 makes action class an explicit choice the
   model must declare via `action_intent`; reply is one of three options
   (`reply` / `tool` / `no_action`), not the only one.
2. **D2 (target_user_id authority)**: Phase 1 forced `target_user_id` to the
   input source's `source_name` (the "confiding machine" pattern). Phase 2 makes
   `target_user_id` the model's pick; the composition-projected
   `current_operator_id` is a context fact, not a forced default.
3. **D3 (planner routing)**: Phase 1 planner `_select_channel` ignored both
   the model's `preferred_channels` hint and the `target_user_id` in
   `op_params`. Phase 2 makes the planner honor a priority
   `target_user` -> `preferred` -> `iteration-order` strategy, with each driver
   self-describing the user IDs it serves via a new
   `ChannelOpSpec.bound_user_ids` field.

Phase 2 is a four-surface change:

- `internal_thought/contracts.py` - additive `action_intent` and
  `target_user_id` fields on `StructuredThoughtEvidence`; new
  `_ACTION_INTENT_VALUES` constant.
- `internal_thought/engine.py` - parser reads the new fields; `_emit_proposal`
  rewrites the precedence rules and removes the legacy `emit_action` fallback;
  `_build_messages` rewrites the system-prompt schema description.
- `channel/contracts.py` + `channel/drivers/cli.py` - additive
  `bound_user_ids: frozenset[str] = frozenset()` on `ChannelOpSpec`; CLI sets
  `frozenset()` (wildcard).
- `planner_bridge/engine.py` - `_select_channel` rewritten to honor the
  target_user -> preferred -> iteration priority.

## 9. Phase 2 Contract Changes

### 9.1 `StructuredThoughtEvidence` (additive)

```python
# helios_v2/internal_thought/contracts.py
INTENDED_REPLY_TEXT_MAX_CHARS = 2000  # unchanged
INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "...(truncated)"  # unchanged
TARGET_USER_ID_MAX_CHARS: Final = 256  # NEW
ACTION_INTENT_NONE: Final = None
ACTION_INTENT_REPLY: Final = "reply"
ACTION_INTENT_TOOL: Final = "tool"
ACTION_INTENT_NO_ACTION: Final = "no_action"
_ACTION_INTENT_VALUES: Final = frozenset({ACTION_INTENT_REPLY, ACTION_INTENT_TOOL, ACTION_INTENT_NO_ACTION})

@dataclass(frozen=True)
class StructuredThoughtEvidence:
    # ...existing fields...
    intended_reply_text: str = ""
    # NEW (Phase 2):
    action_intent: str | None = None
    target_user_id: str | None = None
```

Validation:

- `action_intent` must be `None` or one of the three string literals; any other
  value raises `StructuredThoughtParseError` upstream.
- `target_user_id` is normalized to a stripped string; over-cap (256 chars) is
  deterministically truncated with the same `…(truncated)` suffix convention.
- `intended_reply_text` behavior is unchanged from Phase 1.

### 9.2 Parser helpers

```python
def _optional_action_intent(payload):
    if "action_intent" not in payload:
        return None
    raw = payload.get("action_intent")
    if raw is None:
        return None
    if not isinstance(raw, str) or raw not in _ACTION_INTENT_VALUES:
        raise StructuredThoughtParseError(
            "Structured thought envelope action_intent must be reply/tool/no_action when present"
        )
    return raw

def _optional_target_user_id(payload):
    if "target_user_id" not in payload:
        return None
    raw = payload.get("target_user_id")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope target_user_id must be a string when present"
        )
    stripped = raw.strip()
    if not stripped:
        return None
    if len(stripped) > TARGET_USER_ID_MAX_CHARS:
        cap = TARGET_USER_ID_MAX_CHARS - len(INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX)
        return stripped[:cap] + INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX
    return stripped
```

Both are read at the same point as `_optional_intended_reply_text` and threaded
into the `StructuredThoughtEvidence(...)` constructor.

### 9.3 `_emit_proposal` precedence rewrite

```python
def _derive_thought_judgment(...):
    # ...existing retrieval-sufficiency + judgment logic...
    if continuation_requested:
        # ...existing memory handoff (unchanged)...
    else:
        # Resolve target_user_id once: model-supplied > composition-projected current_operator_id.
        target_user_id = ""
        if evidence is not None and evidence.target_user_id:
            target_user_id = evidence.target_user_id
        if not target_user_id:
            operator_value = request.prompt_contract_summary.get("current_operator_id", "")
            if isinstance(operator_value, str):
                target_user_id = operator_value.strip()

        explicit_tool_intent = (
            evidence is not None
            and evidence.intends_tool_use
            and bool(evidence.tool_op)
        )
        reply_compat_path = (
            evidence is not None
            and not explicit_tool_intent
            and evidence.intended_reply_text
            and target_user_id
        )
        reply_explicit_path = (
            evidence is not None
            and evidence.action_intent == ACTION_INTENT_REPLY
            and target_user_id
        )
        implicit_reply_intent = reply_compat_path or reply_explicit_path

        explicit_tool_path_via_intent = (
            evidence is not None
            and evidence.action_intent == ACTION_INTENT_TOOL
        )
        tool_intent = explicit_tool_intent or explicit_tool_path_via_intent

        # Phase 2: the legacy `emit_action` fallback (which built a reply
        # from thought.content when model_intends_action was true) is REMOVED.
        emit_action = tool_intent or implicit_reply_intent

        if tool_intent:
            # ...existing R85 tool path, unchanged...
            ready_channels = request.prompt_contract_summary.get("ready_channels", ())
            preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
            action_proposal = ThoughtActionProposalCarrier(
                # ...existing fields...
            )
        elif implicit_reply_intent:
            ready_channels = request.prompt_contract_summary.get("ready_channels", ())
            preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name="reply_message",
                requested_op="reply_message",
                preferred_channels=preferred_channels,
                outbound_text=None,
                outbound_intensity=0.75,
                reason_trace=("thought intends to reply to the resolved target",),
                governance_hints={"requires_identity_review": False},
                op_params=MappingProxyType({
                    "outbound_text": evidence.intended_reply_text,
                    "target_user_id": target_user_id,
                }),
            )
        # No legacy fallback. When emit_action is False (no tool, no reply),
        # action_proposal stays None and the cycle closes internal-only.
```

Key changes from Phase 1:

- Reply is no longer the implicit default; it requires either
  `action_intent="reply"` (explicit) or `action_intent is None` and
  `intended_reply_text` non-empty (Phase 1 compat).
- The legacy `emit_action` fallback (which built a reply from
  `thought.content` when `model_intends_action` was true) is removed.
- `target_user_id` resolution priority: model-supplied > composition-projected
  `current_operator_id`. The composition-projected value is now a context
  fact, not the forced value.

### 9.4 System prompt rewrite

```python
system_lines = [
    "You are the internal thought process of a continuous, brain-inspired runtime.",
    "Produce one concise internal thought for the current cycle.",
    "Do not perform theatrical self-narration; reflect the current state and context only.",
    f"Active prompt-contract layers: {layer_text}.",
    "Respond with a single JSON object only, no prose outside it, with this shape:",
    "{",
    '  "thought": "<concise internal thought>",',
    '  "sufficiency": <number 0..1>,',
    '  "wants_to_continue": <bool>,',
    '  "continue_reason": "<why, required if wants_to_continue is true>",',
    '  "proposed_action": {"intends_action": <bool>, "summary": "<optional>"},',
    '  "self_revision": {"intends_revision": <bool>, "summary": "<optional>"},',
    '  "i_want_to_say": "<optional words to say outward as a reply to the current operator>",',
    '  "i_want_to_use_tool": <bool>, "tool_op": "<optional>", "tool_params": {<optional>},',
    '  "action_intent": "reply" | "tool" | "no_action" | null,',
    '  "target_user_id": "<optional override of the current operator id>",',
    "}",
    "Action class is a CHOICE, not a default. After each cycle, decide whether to act and what class:",
    "  - reply: send a user-visible message via the connected operator-facing channel.",
    "  - tool: invoke a bound effector via tool_op + tool_params.",
    "  - no_action: cycle closes as internal-only.",
    "Do NOT reflexively reply just because an input arrived.",
]
```

The `i_want_to_say` field is retained for backward compat (existing fine-tunes
already learned it) but its semantics are reframed in the prompt as a synonym
for `action_intent="reply" + reply_text=...`.

### 9.5 `ChannelOpSpec.bound_user_ids`

```python
@dataclass(frozen=True)
class ChannelOpSpec:
    op_name: str
    required_params: tuple[str, ...] = ()
    user_visible: bool = False
    effect_class: OpEffectClass = "external_world"
    risk_class: OpRiskClass = "unrestricted"
    bound_user_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # ...existing validations...
        for user_id in self.bound_user_ids:
            if not isinstance(user_id, str) or not user_id:
                raise ChannelError(
                    "ChannelOpSpec bound_user_ids must not contain empty or non-string values"
                )
```

```python
# helios_v2/channel/drivers/cli.py
def _cli_descriptor(config: CliDriverConfig) -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        # ...existing fields...,
        output_op_specs=(
            ChannelOpSpec(
                op_name=CLI_OUTPUT_OP,
                required_params=("outbound_text", "target_user_id"),
                user_visible=True,
                effect_class="external_world",
                risk_class="unrestricted",
                bound_user_ids=frozenset(),  # CLI is a wildcard
            ),
        ),
    )
```

The `ChannelSubsystemStateProvider.channel_descriptor_snapshot` (in
`composition/bridges.py`) already iterates `descriptor.output_op_specs` and
projects them into the snapshot dict; the only addition is one new key per
op-spec:

```python
"op_specs": {
    spec.op_name: {
        "required_params": tuple(spec.required_params),
        "user_visible":    spec.user_visible,
        "effect_class":    spec.effect_class,
        "risk_class":      spec.risk_class,
        "bound_user_ids":  tuple(spec.bound_user_ids),  # empty tuple == wildcard
    }
    for spec in descriptor.output_op_specs
},
```

No additional composition code is needed; the field is auto-threaded.

### 9.6 Planner routing priority rewrite

```python
def _select_channel(self, request, requested_op, proposal):
    # Select the channel for an accepted proposal, honoring a priority strategy.
    #
    # Priority:
    #   1. Filter to candidates whose supported_ops includes the op and
    #      whose status.available is True.
    #   2. If the proposal params carries a non-empty target_user_id:
    #      filter to candidates whose op_specs[op].bound_user_ids either
    #      contains that user OR is the wildcard (empty tuple).
    #      - If a non-empty filtered set results: prefer candidates also in
    #        proposal.preferred_channels (intersection); if any, return the
    #        first. Otherwise return the first in iteration order.
    #      - If the filter is empty: fall through to step 3 (do not reject the
    #        proposal; a wildcard driver may still be the right target).
    #   3. From the unfiltered candidate set: prefer candidates also in
    #      proposal.preferred_channels. If any, return the first. Otherwise
    #      return the first in iteration order.
    descriptors = request.channel_descriptor_snapshot
    statuses = request.channel_status_snapshot
    preferred = set(proposal.preferred_channels or ())
    target_user = ""
    if isinstance(proposal.params, Mapping):
        candidate = proposal.params.get("target_user_id", "")
        if isinstance(candidate, str):
            target_user = candidate.strip()

    def _is_candidate(channel_id):
        descriptor = descriptors.get(channel_id)
        if not isinstance(descriptor, dict):
            return False
        if requested_op not in descriptor.get("supported_ops", ()):
            return False
        status = statuses.get(channel_id)
        if not isinstance(status, dict) or not status.get("available", False):
            return False
        return True

    candidates = [cid for cid in descriptors if _is_candidate(cid)]
    if not candidates:
        return None

    def _serves_user(channel_id):
        if not target_user:
            return True
        descriptor = descriptors.get(channel_id, {})
        op_specs = descriptor.get("op_specs", {})
        spec = op_specs.get(requested_op, {})
        bound = spec.get("bound_user_ids", ())
        return not bound or target_user in bound

    if target_user:
        user_serving = [cid for cid in candidates if _serves_user(cid)]
        if user_serving:
            intersection = [cid for cid in user_serving if cid in preferred]
            return (intersection or user_serving)[0]

    if preferred:
        intersection = [cid for cid in candidates if cid in preferred]
        if intersection:
            return intersection[0]

    return candidates[0]
```

This preserves R85 iteration-order fallback for the case where neither
`target_user_id` nor `preferred_channels` are set.

## 10. Phase 2 Data Structures

### 10.1 New envelope field shapes

```json
{
  "thought": "...",
  "sufficiency": 0.9,
  "wants_to_continue": false,
  "proposed_action": {"intends_action": true},
  "self_revision": {"intends_revision": false},
  "i_want_to_say": "...",
  "i_want_to_use_tool": false,
  "tool_op": "",
  "tool_params": {},
  "action_intent": "reply" | "tool" | "no_action",
  "target_user_id": "...",
  "hormone_response_i_predict": {...}
}
```

### 10.2 `ChannelOpSpec` addition

```python
bound_user_ids: frozenset[str] = field(default_factory=frozenset)
```

Threaded automatically into `channel_descriptor_snapshot` via the existing
`ChannelSubsystemStateProvider`.

## 11. Phase 2 Module Changes (summary table)

| File | Change kind | Summary |
| --- | --- | --- |
| `helios_v2/internal_thought/contracts.py` | MOD additive | `StructuredThoughtEvidence.action_intent` + `.target_user_id`; `TARGET_USER_ID_MAX_CHARS`; `_ACTION_INTENT_VALUES` |
| `helios_v2/internal_thought/engine.py` | MOD | parser reads new fields; `_emit_proposal` new precedence, legacy `emit_action` removed; `_build_messages` system-prompt rewrite |
| `helios_v2/channel/contracts.py` | MOD additive | `ChannelOpSpec.bound_user_ids`; `__post_init__` validation |
| `helios_v2/channel/drivers/cli.py` | MOD additive | CLI driver sets `bound_user_ids=frozenset()` on `reply_message` op spec |
| `helios_v2/composition/bridges.py` | MOD additive (1-line) | `ChannelSubsystemStateProvider.channel_descriptor_snapshot` includes `bound_user_ids` in `op_specs` |
| `helios_v2/planner_bridge/engine.py` | MOD | `FirstVersionPlannerBridgePath._select_channel` priority rewrite |

## 12. Phase 2 Migration Plan

1. **In-process migration**: every additive contract field defaults to the
   Phase 1 behavior. The implicit-reply compat path
   (`action_intent is None and i_want_to_say set`) preserves Phase 1 semantics.
   The deterministic offline path `emit_action` fallback is removed; this
   is a documented Phase 2 behavior change.
2. **Test migration**: existing Phase 1 unit tests continue to pass. New
   Phase 2 tests cover the new fields and the new planner routing priority.
3. **Production rollout**: no flag, no opt-in. Phase 2 is the new default.

## 13. Phase 2 Failure Modes and Constraints

1. **Forbidden - fabricated reply.** When `i_want_to_say` is null/empty AND
   `action_intent != "reply"`, the runtime must not synthesize a reply.
2. **Forbidden - fabricated operator.** When `target_user_id` is empty AND
   `current_operator_id` is empty, no reply is constructed.
3. **Forbidden - `13` content authoring.** `13 planner_bridge` only validates
   and routes; it does not construct reply content.
4. **Forbidden - fabricated driver.** The planner never routes to a driver
   that does not offer the op or is not available; it never routes to a
   driver that does not serve the target user unless the filter would
   yield an empty set (then it falls through, fail-soft).
5. **Forbidden - legacy `emit_action`.** Phase 2 removes the legacy
   `emit_action` fallback path.
6. **Length cap.** `target_user_id` is bounded at 256 chars.
7. **Backward compat.** The R93 Phase 1 tests that exercise the compat
   reply path continue to pass.
8. **Pre-emption.** When the planner target_user filter yields an empty
   set, the planner falls through to a wildcard driver.

## 14. Phase 2 Observability and Logging

No new logging mechanism. The new fields surface in the existing trace
without R93 Phase 2 adding a new log surface. The composition
owner-boundary guard and the no-adhoc-logging guard stay green.

## 15. Phase 2 Validation Strategy

### 15.1 Network-free unit / contract tests

| File | Asserts |
| --- | --- |
| `tests/test_internal_thought_parse_action_intent.py` | parser default None; accepted strings; whitespace-empty; non-string raises; over-cap truncates |
| `tests/test_internal_thought_emit_proposal_phase2.py` | new precedence; `action_intent="reply"`; `action_intent="no_action"`; deterministic offline emits no proposal; `target_user_id` resolution |
| `tests/test_channel_op_spec_bound_user_ids.py` | `ChannelOpSpec` carries new field; CLI driver sets `frozenset()`; provider threads it |
| `tests/test_planner_bridge_routing_priority.py` | `_select_channel` priority; `bound_user_ids=frozenset()` wildcard; empty target_user filter falls through |
| `tests/test_runtime_stage_chain_action_agency.py` | end-to-end: `action_intent="no_action"` produces no dispatch; explicit `action_intent="reply"` dispatches; `target_user_id` honored in a multi-driver fixture |

### 15.2 Real-LLM probes

- `scripts/r93_probes/03_action_choice.json` - positive control.
- `scripts/r93_probes/04_no_action_when_unmoved.json` - negative control.

### 15.3 Acceptance gate

The full network-free test suite must reach >= 1107 + R93 Phase 2 new tests
passed / 4 skipped with 0 regressions; the composition owner-boundary guard
and the no-adhoc-logging guard remain green; all docs synced in this same
change set.
