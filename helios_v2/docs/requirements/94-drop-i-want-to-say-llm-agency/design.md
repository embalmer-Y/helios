# Design 94 — Drop `i_want_to_say`; LLM full agency over action + channel

## 1. Background

R93 Phase 1 introduced the top-level `i_want_to_say` envelope field as the
mechanism for the model to declare "outward reply text". The intent was
correct — the model needed a way to put a reply on the wire — but the field
name is biased: the verb "say" primes the model to fill the field, even
when its primary action class is `no_action` or `tool`.

R93 Phase 2 (commit `e258926`, 2026-06) addressed the action-class taxonomy
gap with the `action_intent` envelope field (`reply` / `tool` / `no_action`)
and the planner's `target_user` → `preferred` → `iteration-order` priority.
The R93 P2 evaluation showed real progress: the model could now pick
`no_action` on a low-salience "ok" stimulus (probe 04) and the planner
could route to a specific driver via `target_user_id` + `bound_user_ids`.

But the `i_want_to_say` field is still in the schema. The R93 P2 design
kept a backward-compat path: when `action_intent is None` and
`i_want_to_say` is set, the owner still constructs a reply. This was a
deliberate Phase-1 → Phase-2 migration aid, but it perpetuates the
structural bias: any model that fills `i_want_to_say` *implicitly* triggers
a reply even when its action class is `no_action`. The owner enforces the
precedence (explicit `no_action` wins), but the schema still invites the
conflict.

R94 retires the migration aid. The field is removed; the reply path is
driven by `action_intent="reply" + reply_text`; the `i_want_to_say` literal
is forbidden by a structural test.

## 2. Goal

Eliminate the `i_want_to_say` field from the `11` internal-thought schema
so the LLM's reply / tool / no_action choice is structurally driven by
`action_intent` alone. The model is granted full agency over its action
class without the schema subtly biasing it toward text.

## 3. Design

### 3.1 Evidence: rename field, change type

**Field changes on `StructuredThoughtEvidence`** (R94 is breaking relative
to R93 / R93 P2):

| Field | R93 / R93 P2 | R94 |
| --- | --- | --- |
| `intended_reply_text` | `str = ""` (default empty) | **REMOVED** |
| `reply_text` | (does not exist) | `str \| None = None` |

**Constants** (rename only; values preserved):

| Constant | R93 / R93 P2 | R94 |
| --- | --- | --- |
| Length cap | `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` | `REPLY_TEXT_MAX_CHARS = 2000` |
| Truncation suffix | `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"` | `REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"` |

**Rationale for `str \| None`** (vs. R93 P2's `str = ""`):
- `None` is the honest absence signal: the model did not supply reply text.
  An empty string `"\"\"` would be ambiguous (did the model supply an empty
  text, or did the parser coerce None to empty?).
- The `_emit_proposal` reply-explicit branch can write `if
  evidence.reply_text is not None:` to require an actual model-supplied
  value; the empty-string case is folded into None.
- Symmetric with `target_user_id: str | None` (R93 P2): both are model
  declarations of "what to put on the wire" that may be honestly absent.

**Backward compat with `i_want_to_say` in the payload**: the parser
silently ignores the field. A model that still produces `i_want_to_say`
is not broken — its `i_want_to_say` content is simply not used. The
forward-compat test asserts that the parser does not raise on a payload
with `i_want_to_say` set; the `reply_text` field is read independently.

### 3.2 Engine: precedence rewrite

The new precedence in `_derive_thought_judgment._emit_proposal`:

```text
emit_proposal:
    if evidence is None:
        # Deterministic offline path (Phase-1 acceptance criterion, unchanged):
        # reply with outbound_text=thought.content + preferred_channels=("cli",).
        return reply_legacy(thought)
    if evidence.action_intent == "no_action":
        return None                  # explicit abstention
    if tool_intent (intends_tool_use + tool_op) OR action_intent == "tool":
        return tool_proposal(...)
    if action_intent == "reply" AND reply_text is not None AND target is not empty:
        return reply_proposal(reply_text, target)
    # Default: cycle closes internal-only. No compat path.
    return None
```

Compared to R93 P2, the `reply_compat_path` branch is removed. The
precedence is now:

| Branch | R93 P2 | R94 |
| --- | --- | --- |
| Explicit `tool_op` (R85) | wins | wins (unchanged) |
| Explicit `action_intent="tool"` | wins | wins (unchanged) |
| `action_intent="reply"` + `reply_text` + target | builds reply | **only** reply path (no compat) |
| `action_intent="reply"` + `reply_text` + no target | None | None (unchanged) |
| `action_intent="reply"` + no `reply_text` | builds reply (uses `thought.content`?) | **None** (no fabrication) |
| `action_intent=None` + `i_want_to_say` set | compat reply (REMOVED in R94) | **None** (no compat) |
| `action_intent=None` + nothing | None | None (unchanged) |
| `action_intent="no_action"` | None | None (unchanged) |
| `evidence is None` (deterministic) | legacy reply | legacy reply (unchanged) |

The single-source change is in `_derive_thought_judgment._emit_proposal`
within `engine.py`. The function is reorganized:

```python
def _emit_proposal(...):
    if evidence is None:
        return _legacy_deterministic_reply(thought)  # unchanged from R93
    if evidence.action_intent == ACTION_INTENT_NO_ACTION:
        return None
    if _resolved_tool_intent(evidence):
        return _build_tool_proposal(evidence, request, target_user_id)
    if (
        evidence.action_intent == ACTION_INTENT_REPLY
        and evidence.reply_text is not None
        and target_user_id
    ):
        return _build_reply_proposal(evidence.reply_text, target_user_id, request)
    return None
```

The `_resolved_tool_intent` helper consolidates the R93 P2 dual-tool-path
logic (explicit `intends_tool_use` AND `action_intent="tool"`) into a
single boolean.

### 3.3 System prompt rewrite

The R93 P2 system prompt is replaced with an R94 variant. The diff:

```diff
- "i_want_to_say": "<optional words to say outward as a reply to the current operator>",
+ "action_intent": "reply" | "tool" | "no_action" (REQUIRED — pick one every cycle),
+ "reply_text": "<when action_intent=reply, the text to send. Omit otherwise.>",
+ "target_user_id": "<optional override of the current operator id, used for reply/tool>",
  "i_want_to_use_tool": <bool>, "tool_op": "<optional>", "tool_params": {<optional>},
- "action_intent": "reply" | "tool" | "no_action" | null,
- "target_user_id": "<optional override of the current operator id>",
```

The transport clause is rewritten to be `action_intent`-led:

```diff
- When you set 'i_want_to_say' to a non-empty string, the runtime will transport
- that text as a 'reply_message' to the current operator through the 'cli'
- user-visible channel. Use 'i_want_to_say' for direct operator-addressed
- replies; use 'i_want_to_use_tool' / 'tool_op' / 'tool_params' for non-reply
- effectors only.
+ When you set 'action_intent' to 'reply' AND supply 'reply_text', the runtime
+ will transport that text as a 'reply_message' to the resolved 'target_user_id'
+ through the connected driver serving that user. When you set 'action_intent'
+ to 'tool', the runtime will execute the bound effector named in 'tool_op' with
+ 'tool_params'. When you set 'action_intent' to 'no_action', the cycle closes
+ as internal-only — no proposal, no dispatch. 'reply_text' is a sub-detail of
+ the reply action class, not an independent choice.
```

The "Action class is a CHOICE" paragraph from R93 P2 is preserved and
strengthened. The action class is the **first decision** the model
makes on every cycle; `reply_text` is a sub-detail of the reply class.

### 3.4 Structural test

`test_internal_thought_no_i_want_to_say_in_prompt.py` enforces the
literal-absence of `i_want_to_say` in three layers:

1. **Source code**: scan `engine.py` and `contracts.py` for the literal
   string `i_want_to_say` and fail if any match.
2. **Build messages**: drive `LlmBackedInternalThoughtPath._build_messages`
   on a sample request and assert the system + user message content
   strings do not contain `i_want_to_say`.
3. **Test fixture surface**: assert `_internal_thought_test_fixtures.envelope`
   does not accept a `i_want_to_say` parameter (introspect via
   `inspect.signature`).

A future R that reintroduces the field is caught at test time, before
the regression reaches a real-LLM evaluation.

### 3.5 Test fixture surface

`envelope()` signature change:

```diff
 def envelope(
     *,
     thought: str = "model thought",
     sufficiency: float = 0.9,
     wants_to_continue: bool = False,
     continue_reason: str = "",
     intends_action: bool = False,
     intends_revision: bool = False,
-    i_want_to_say: Any = None,
+    reply_text: Any = None,
     i_want_to_use_tool: Any = None,
     tool_op: Any = None,
     tool_params: Any = None,
     action_intent: Any = None,
     target_user_id: Any = None,
 ) -> dict:
     ...
-    if i_want_to_say is not None:
-        payload["i_want_to_say"] = i_want_to_say
+    if reply_text is not None:
+        payload["reply_text"] = reply_text
```

Call sites that previously did `i_want_to_say="<text>"` are updated to
`reply_text="<text>", action_intent="reply"` to exercise the explicit-
reply branch. The R93 P2 path of `i_want_to_say` without `action_intent`
is no longer expressible via the fixture (which is the point).

### 3.6 Probe re-runs

All 4 R93 probes are re-run with the R94 system prompt captured in the
JSON. Concretely:

| Probe | R93 P2 `must_contain` (relevant slice) | R94 `must_contain` |
| --- | --- | --- |
| 01_basic_reply | `["苏蕊", "i_want_to_say"]` | `["苏蕊", "reply_text"]` |
| 02_silence | (unchanged: no operator engagement) | (unchanged) |
| 03_action_choice | `["action_intent", "reply", "i_want_to_say"]` | `["action_intent", "reply", "reply_text"]` |
| 04_no_action_when_unmoved | (asserts no fabricated reply) | (unchanged; focus is no_action stability) |

**Evaluation focus (probe 04)**: the R93 P2 evaluation showed the model
picks `no_action` on a low-salience "ok" stimulus ~80% of the time. The
R94 evaluation checks whether the R94 schema (with `i_want_to_say` removed)
**maintains or improves** this rate. If the rate regresses (i.e. the
model now reflexively fills `reply_text` + `action_intent="reply"` on
the same low-salience stimulus), it suggests the underlying issue is not
the field name but the model's tendency to mirror schema fields; this
would escalate to R96 (Chinese appraisal grounding) for a deeper
investigation of the action-class decision.

## 4. Functional Requirements (recap from `requirement.md`)

The complete functional / non-functional / acceptance criteria are in
`requirement.md`. This design file focuses on the architectural
decisions and the engine rewrite.

## 5. Non-Functional Requirements (recap)

Same as `requirement.md` §4: no extra LLM call, fail-fast on non-string
`reply_text`, no fabricated reply, no new logging, no new `preferred_channel`
field, no compat path. The owner boundary rules from R93 / R93 P2 are
preserved.

## 6. Code Behavior Constraints (recap)

1. Forbidden: `i_want_to_say` in schema (enforced by structural test).
2. Forbidden: implicit reply from absent `action_intent`.
3. Forbidden: fabricated reply text.
4. Forbidden: fabricated operator.
5. Forbidden: `13` content authoring.
6. Boundary: driver self-description via `bound_user_ids`.
7. Boundary: composition is the projector (`current_operator_id` is
   a fallback for `target_user_id`, not a forced value).
8. No-adhoc-logging guard: preserved.

## 7. Impacted Modules

See `requirement.md` §6 for the full list. The design file's
contribution is the engine-side architecture:

- `src/helios_v2/internal_thought/contracts.py` — constants rename only
  (no semantic change).
- `src/helios_v2/internal_thought/engine.py` — `StructuredThoughtEvidence`
  field swap; `_optional_intended_reply_text` → `_optional_reply_text`;
  `_derive_thought_judgment._emit_proposal` precedence rewrite; system
  prompt rewrite.
- All channel / planner / composition / CLI driver code is unchanged.

## 8. Acceptance Criteria (recap)

See `requirement.md` §7. The architecturally significant criteria are:

1. `_parse_structured_thought` reads `reply_text`, ignores `i_want_to_say`.
2. The system prompt contains no `i_want_to_say` literal (structural test).
3. `_emit_proposal` requires `action_intent="reply" + reply_text + target`
   for a reply proposal; no compat path.
4. The deterministic offline path is byte-for-byte unchanged.
5. The full network-free test suite is green: ≥ 1195 + new tests passed.
6. The R93 P2 baseline comparison for probe 04 is recorded; if the
   `no_action` choice regresses, escalate to R96.
