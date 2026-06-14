# Requirement 93 - Reliable Reply Loop From `i_want_to_say` — Task

## 1. Task Breakdown

R93 lands as six small ordered slices. Each slice is independently testable
and the full-suite gate runs after each one to catch regressions early.

### T1 — Contract: `intended_reply_text` field on `StructuredThoughtEvidence`

- Modified: `src/helios_v2/internal_thought/contracts.py`.
- Adds module-level constants `INTENDED_REPLY_TEXT_MAX_CHARS = 2000` and
  `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"`.
- Adds additive optional field `intended_reply_text: str = ""` to
  `StructuredThoughtEvidence`.
- New test: `tests/test_internal_thought_evidence_intended_reply.py` (≈ 5 cases:
  default empty, accepted non-empty, frozen, length cap, deterministic suffix).

### T2 — Parser: read `i_want_to_say` from envelope

- Modified: `src/helios_v2/internal_thought/engine.py` `_parse_structured_thought`.
- Reads optional `i_want_to_say` per design §3.2: absent / null / empty /
  whitespace-only -> `""`; non-empty trimmed string -> stored (over-cap
  truncated); non-string -> `StructuredThoughtParseError`.
- New test: `tests/test_internal_thought_parse_i_want_to_say.py` (≈ 8 cases).
- Validation: `pytest tests/test_internal_thought_parse_i_want_to_say.py
  tests/test_internal_thought_engine.py -q` is green.

### T3 — Composition: `_current_operator_id(frame)` projection

- Modified: `src/helios_v2/composition/bridges.py`.
- Adds the owner-neutral `_current_operator_id(frame)` helper per design §3.5.
- Adds `current_operator_id` key into the `prompt_contract_summary` dict in
  both `SemanticInternalThoughtRequestBridge.build_request` and
  `FirstVersionInternalThoughtRequestBridge.build_request`.
- New test: `tests/test_composition_current_operator_id.py` (≈ 6 cases:
  earliest external wins, internal modalities skipped, empty when no `02`,
  empty when only internal stimuli, both bridges add the key).

### T4 — Engine: implicit-reply branch in `_emit_proposal`

- Modified: `src/helios_v2/internal_thought/engine.py` `_emit_proposal`.
- Adds the implicit-reply branch per design §3.3 with the explicit-tool
  precedence rule and the silent-when-operator-empty rule.
- New test: `tests/test_internal_thought_implicit_reply_intent.py` (≈ 8
  cases: implicit reply built when `i_want_to_say` set + operator present;
  silent when operator absent; explicit `tool_op` wins; legacy fallback path
  unchanged when `evidence is None`; both `intended_reply_text` and
  `model_intends_action` true => implicit reply path; continuation requested
  takes precedence over both).

### T5 — System prompt: tell the model `i_want_to_say` is transported

- Modified: `src/helios_v2/internal_thought/engine.py` `_build_messages`.
- Adds the explicit `i_want_to_say` schema line and the transport-clause
  paragraph per design §3.4. Legacy fallback (no envelope) path is unchanged.
- New test: `tests/test_internal_thought_build_messages_reply_clause.py`
  (≈ 3 cases: system prompt now contains the transport clause; the
  `i_want_to_say` schema entry exists; user message unchanged for both legacy
  and present-field cases — backward compatibility).

### T6 — End-to-end smoke + real-LLM probes + docs sync

- New: `tests/test_runtime_stage_chain_implicit_reply.py` end-to-end test
  using the channel-bound semantic assembly + a fake provider returning
  `i_want_to_say="hello"` to verify a real CLI sink dispatch occurs with the
  reply text + `executed` continuity record.
- New: `scripts/r93_probes/01_basic_reply.json` (positive control) and
  `scripts/r93_probes/02_silence_negative_control.json` (negative control).
- Documentation sync per cross-file rule §8 / §8.1:
  `docs/requirements/index.md`, `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`,
  `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md`,
  `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`,
  `ROADMAP.zh-CN.md`.

## 2. Dependencies

| Task | Depends on |
| --- | --- |
| T1 | (none) |
| T2 | T1 |
| T3 | (none — composition projection is independent of evidence shape) |
| T4 | T1, T2, T3 (needs the field, the parsed value, and the operator id) |
| T5 | (none — pure system-prompt update; semantically depends on T4 but parsing/emission still works without T5) |
| T6 | T1–T5 (end-to-end test) |

Independent slices T1, T3, T5 can land in parallel; T2 follows T1; T4 follows
T1+T2+T3; T6 follows everything.

## 3. Files and Modules

### 3.1 Modified code

- `src/helios_v2/internal_thought/contracts.py`
- `src/helios_v2/internal_thought/engine.py`
- `src/helios_v2/composition/bridges.py`

### 3.2 New tests

- `tests/test_internal_thought_evidence_intended_reply.py`
- `tests/test_internal_thought_parse_i_want_to_say.py`
- `tests/test_composition_current_operator_id.py`
- `tests/test_internal_thought_implicit_reply_intent.py`
- `tests/test_internal_thought_build_messages_reply_clause.py`
- `tests/test_runtime_stage_chain_implicit_reply.py`

### 3.3 New scripts

- `scripts/r93_probes/01_basic_reply.json`
- `scripts/r93_probes/02_silence_negative_control.json`

### 3.4 Documentation

- `docs/requirements/93-reply-loop-from-i-want-to-say/{requirement.md, design.md, task.md}`
- `docs/requirements/index.md`
- `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`
- `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md`
- `docs/ROADMAP.zh-CN.md`

## 4. Implementation Order

1. T1 — contract field (foundation; everything else imports from it)
2. T2 — parser reads the field
3. T3 — composition projection (independent; can run in parallel with T2)
4. T4 — implicit-reply branch in `_emit_proposal`
5. T5 — system prompt clause
6. T6 — end-to-end + probes + docs sync

## 5. Validation Plan

### 5.1 Per-task focused validation

| Task | Command |
| --- | --- |
| T1 | `pytest helios_v2/tests/test_internal_thought_evidence_intended_reply.py -q` |
| T2 | `pytest helios_v2/tests/test_internal_thought_parse_i_want_to_say.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T3 | `pytest helios_v2/tests/test_composition_current_operator_id.py -q` |
| T4 | `pytest helios_v2/tests/test_internal_thought_implicit_reply_intent.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T5 | `pytest helios_v2/tests/test_internal_thought_build_messages_reply_clause.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T6 | `pytest helios_v2/tests/test_runtime_stage_chain_implicit_reply.py helios_v2/tests/test_runtime_stage_chain.py -q` + the real-LLM probe runs |

### 5.2 Full-suite gate (closes the change set)

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests -q
```

Expected outcome: ≥ 1107 + new R93 tests passed, 4 skipped, 0 failed,
0 errors. The composition owner-boundary guard and the no-ad-hoc-logging
guard must both stay green.

## 6. Completion Criteria

R93 is complete when ALL of the following hold:

1. `_parse_structured_thought` reads `i_want_to_say` per design §3.2;
   `StructuredThoughtEvidence.intended_reply_text` carries the parsed value.
2. `_emit_proposal` builds an implicit `reply_message` tool intent with
   `op_params={"outbound_text", "target_user_id"}` when the conditions in
   design §3.3 hold; explicit `tool_op` (R85) takes precedence; missing
   operator id silently abstains.
3. Composition projects `current_operator_id` from the same-frame `02`
   external stimulus into the `prompt_contract_summary` of both internal-
   thought request bridges.
4. `_build_messages` includes the new schema line and transport clause; the
   model can know that `i_want_to_say` is transported as a reply.
5. End-to-end test: a fake provider returning `i_want_to_say="hello"`
   under the channel-bound semantic assembly produces a real CLI sink
   dispatch carrying the reply text and an `executed` continuity record.
6. The legacy `assemble_runtime()` deterministic offline path remains
   byte-for-byte unchanged. The pre-R93 network-free test suite (1107
   passed / 4 skipped) is green; the new R93 tests are green; the
   composition owner-boundary guard and the no-ad-hoc-logging guard are
   green.
7. The real-LLM probe `scripts/r93_probes/01_basic_reply.json` shows the
   model fills `i_want_to_say` with operator-addressed reply text after
   the new system-prompt clause; the negative-control probe shows the model
   leaves the field null/empty when no operator is present.
8. `docs/requirements/index.md`, both `OWNER_GUIDE` files, both
   `PROGRESS_FLOW` maps, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`, and `ROADMAP.zh-CN.md` are updated
   in the same change set.

---

## 7. Phase 2 (2026-06) - Action Agency and Cross-Channel Routing - Task

R93 Phase 2 lands as four small ordered slices. Each slice is independently
testable and the full-suite gate runs after each one to catch regressions
early. Phase 2 must land in the same change set as Phase 1 because the
contract is additive on top of Phase 1.

### T7 — Contract: `action_intent` and `target_user_id` fields on `StructuredThoughtEvidence`

- Modified: `src/helios_v2/internal_thought/contracts.py`.
- Adds module-level constants
  `TARGET_USER_ID_MAX_CHARS = 256`,
  `ACTION_INTENT_REPLY = "reply"`,
  `ACTION_INTENT_TOOL = "tool"`,
  `ACTION_INTENT_NO_ACTION = "no_action"`,
  `_ACTION_INTENT_VALUES = frozenset({...})`.
- Adds two additive optional fields to `StructuredThoughtEvidence`:
  - `action_intent: str | None = None` — must be one of `_ACTION_INTENT_VALUES`
    or `None`; any other value raises `StructuredThoughtParseError`.
  - `target_user_id: str | None = None` — normalized to stripped string;
    over-cap deterministically truncated with the same suffix convention.
- New test: `tests/test_internal_thought_parse_action_intent.py` (≈ 7 cases:
  default `None`; accepted `reply` / `tool` / `no_action`; explicit `None`
  null; whitespace-empty normalized; non-string raises; over-cap
  truncates).

### T8 — Engine: rewrite `_emit_proposal` precedence and remove the legacy `emit_action` fallback

- Modified: `src/helios_v2/internal_thought/engine.py`.
- Parser reads the new `action_intent` and `target_user_id` envelope fields
  per design §9.2 and threads them into the
  `StructuredThoughtEvidence(...)` constructor.
- Rewrites `_emit_proposal` (or its dedicated helper `_derive_thought_judgment`)
  per design §9.3: explicit-tool wins; then `reply_compat_path` (Phase 1
  compat) or `reply_explicit_path` (Phase 2 explicit); then
  `explicit_tool_path_via_intent`; otherwise `emit_action = False`. The
  legacy `emit_action` fallback (which built a reply from
  `thought.content` when `model_intends_action` was true) is REMOVED.
- Resolves `target_user_id` priority:
  `evidence.target_user_id` > composition-projected `current_operator_id`.
  When both are empty, no reply is constructed (silent-when-operator-empty
  rule is preserved).
- Rewrites `_build_messages` system prompt per design §9.4: the schema
  description now lists `action_intent` and `target_user_id`; a new
  "Action class is a CHOICE" paragraph tells the model that reply is one
  of three options and that it must not reflexively reply on input arrival.
- New tests:
  - `tests/test_internal_thought_emit_proposal_phase2.py` (≈ 8 cases:
    new precedence order; `action_intent="reply"` builds implicit reply;
    `action_intent="no_action"` with otherwise-implicit content yields
    `action_proposal is None`; deterministic offline
    `assemble_runtime()` path still emits a reply when the legacy code
    expected; `target_user_id` resolution priority; explicit
    `tool_op` wins over `action_intent="reply"`; missing operator id +
    `action_intent="reply"` yields `None`; `model_intends_action` is no
    longer sufficient by itself).
  - `tests/test_runtime_stage_chain_action_agency.py` (≈ 4 cases:
    end-to-end: `action_intent="no_action"` produces no dispatch; explicit
    `action_intent="reply"` dispatches; `target_user_id` honored in a
    multi-driver fixture; `action_intent="tool"` routes to a tool driver
    via the existing R85 path).

### T9 — Channel: `bound_user_ids` on `ChannelOpSpec` and the CLI driver

- Modified: `src/helios_v2/channel/contracts.py`.
- Adds additive `bound_user_ids: frozenset[str] = field(default_factory=frozenset)`
  on `ChannelOpSpec`.
- Extends `__post_init__` validation: any non-string or empty value in
  `bound_user_ids` raises `ChannelError` ("must not contain empty or
  non-string values").
- Modified: `src/helios_v2/channel/drivers/cli.py`.
- Sets `bound_user_ids=frozenset()` (wildcard) on the `reply_message`
  `ChannelOpSpec` per design §9.5.
- Modified: `src/helios_v2/composition/bridges.py` — 1-line additive
  change: `ChannelSubsystemStateProvider.channel_descriptor_snapshot`
  projects `bound_user_ids=tuple(spec.bound_user_ids)` into each
  `op_specs[op_name]` dict.
- New test: `tests/test_channel_op_spec_bound_user_ids.py` (≈ 6 cases:
  default `frozenset()`; non-empty set honored; non-string raises;
  empty-string raises; CLI driver sets `frozenset()`; the composition
  provider threads the field through the snapshot).

### T10 — Planner: rewrite `_select_channel` priority

- Modified: `src/helios_v2/planner_bridge/engine.py`
  `FirstVersionPlannerBridgePath._select_channel`.
- New priority: `target_user` -> `preferred` -> `iteration-order`.
- Filters candidates to those whose `supported_ops` includes the op and
  whose status is `available`; from those, if `proposal.op_params`
  carries a non-empty `target_user_id`, filters to candidates whose
  `op_specs[op].bound_user_ids` either contains that user OR is the
  wildcard (empty tuple). If the user-serving filter is non-empty, prefers
  candidates also in `proposal.preferred_channels`; falls back to
  iteration order. If the user-serving filter is empty, falls through
  (fail-soft) to the next step. From the unfiltered set, prefers
  `preferred_channels` intersection; falls back to iteration order.
- New test: `tests/test_planner_bridge_routing_priority.py` (≈ 8 cases:
  iteration order when no hints; `preferred` wins when no `target_user`;
  `target_user` filter is applied first; wildcard driver (CLI) always
  passes user filter; non-wildcard driver with matching user passes; non-
  wildcard driver with non-matching user is filtered out; target_user
  filter empty set falls through; all candidates filtered out yields
  `None`).

## 8. Phase 2 Dependencies

| Task | Depends on |
| --- | --- |
| T7 | T1 (additive on the same dataclass) |
| T8 | T7 (needs the new fields on the evidence) |
| T9 | (none — independent surface) |
| T10 | T9 (needs `bound_user_ids` in the snapshot) |

Independent slices T7 and T9 can land in parallel; T8 follows T7; T10
follows T9.

## 9. Phase 2 Files and Modules

### 9.1 Modified code

- `src/helios_v2/internal_thought/contracts.py` — additive fields.
- `src/helios_v2/internal_thought/engine.py` — parser + emit rewrite.
- `src/helios_v2/channel/contracts.py` — additive field.
- `src/helios_v2/channel/drivers/cli.py` — driver field set.
- `src/helios_v2/composition/bridges.py` — 1-line provider projection.
- `src/helios_v2/planner_bridge/engine.py` — routing priority rewrite.

### 9.2 New tests

- `tests/test_internal_thought_parse_action_intent.py`
- `tests/test_internal_thought_emit_proposal_phase2.py`
- `tests/test_channel_op_spec_bound_user_ids.py`
- `tests/test_planner_bridge_routing_priority.py`
- `tests/test_runtime_stage_chain_action_agency.py`

### 9.3 New scripts

- `scripts/r93_probes/03_action_choice.json` — positive control.
- `scripts/r93_probes/04_no_action_when_unmoved.json` — negative control.

### 9.4 Documentation

The same docs as Phase 1 plus the doc updates specified in design §15.3.

## 10. Phase 2 Implementation Order

1. T7 — contract field (foundation).
2. T8 — engine rewrite (uses T7; independent of T9).
3. T9 — channel contract (independent of T7/T8).
4. T10 — planner rewrite (uses T9).

## 11. Phase 2 Validation Plan

### 11.1 Per-task focused validation

| Task | Command |
| --- | --- |
| T7 | `pytest helios_v2/tests/test_internal_thought_parse_action_intent.py -q` |
| T8 | `pytest helios_v2/tests/test_internal_thought_emit_proposal_phase2.py helios_v2/tests/test_runtime_stage_chain_action_agency.py helios_v2/tests/test_internal_thought_engine.py -q` |
| T9 | `pytest helios_v2/tests/test_channel_op_spec_bound_user_ids.py helios_v2/tests/test_channel_contracts.py helios_v2/tests/test_channel_drivers.py -q` |
| T10 | `pytest helios_v2/tests/test_planner_bridge_routing_priority.py helios_v2/tests/test_planner_bridge_engine.py -q` |

### 11.2 Full-suite gate (closes the change set)

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests -q
```

Expected outcome: ≥ 1107 + R93 Phase 1 tests + R93 Phase 2 new tests
passed, 4 skipped, 0 failed, 0 errors. The composition owner-boundary
guard and the no-ad-hoc-logging guard must both stay green.

## 12. Phase 2 Completion Criteria

R93 Phase 2 is complete when ALL of the following hold:

1. `_parse_structured_thought` reads `action_intent` and `target_user_id`
   per design §9.2; `StructuredThoughtEvidence.action_intent` and
   `.target_user_id` carry the parsed values.
2. `_emit_proposal` (or its dedicated helper) builds the implicit
   `reply_message` only when one of the new precedence paths fires per
   design §9.3; the legacy `emit_action` fallback is gone;
   `target_user_id` is resolved model-supplied > composition-projected.
3. `_build_messages` system prompt now lists `action_intent` /
   `target_user_id` schema entries and the "Action class is a CHOICE"
   paragraph per design §9.4.
4. `ChannelOpSpec.bound_user_ids` is honored by the CLI driver
   (`frozenset()`) and threaded through the composition provider
   snapshot.
5. `FirstVersionPlannerBridgePath._select_channel` honors the
   `target_user` -> `preferred` -> `iteration-order` priority per design
   §9.6.
6. End-to-end test: a fake provider returning
   `action_intent="no_action"` yields no dispatch; a fake provider
   returning `action_intent="reply"` yields a real CLI sink dispatch.
7. The pre-R93 network-free test suite (1107 passed / 4 skipped) is
   green; the R93 Phase 1 tests are green; the R93 Phase 2 new tests
   are green; the composition owner-boundary guard and the
   no-adhoc-logging guard are green.
8. The real-LLM probe `scripts/r93_probes/03_action_choice.json` shows
   the model choosing an action class appropriate to the stimulus; the
   negative-control probe `scripts/r93_probes/04_no_action_when_unmoved.json`
   shows the model choosing `no_action` (or absent `i_want_to_say`) when
   the stimulus is unmoving.
9. All eight docs (`index.md`, `ROADMAP.zh-CN.md`, `OWNER_GUIDE.md`,
   `OWNER_GUIDE.zh-CN.md`, `PROGRESS_FLOW.en.md`, `PROGRESS_FLOW.zh-CN.md`,
   `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`) are
   updated in the same change set.
