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
