# Requirement 85 - LLM-driven autonomous tool selection (cognition to planner-bound effector op)

## 1. Design Overview

R85 connects real cognition to the R84 effector under one organizing principle: **cognition names an
op and its parameters; each driver self-describes the op's properties; the planner / governance /
evaluation owners interpret those properties.** This extends the `30` device-driver-self-description
model (and its transport-intrinsic QoS) to tool semantics. The `16` v3 output gains tool-intent fields;
`11` parses them into an effector action proposal carrying generic `op_params`; `12` normalizes it
structurally; and the `13` planner binds the op to whichever connected driver declares it and validates
the op's inputs against that driver's own declared per-op spec. No native function-calling (`25`
unchanged). All op-aware validation lives in `13` (the only owner with channel-state); `12` does
structural normalization only. Everything is additive and opt-in on the channel-bound assembly; the
reply path, the no-action path, and the default assembly are preserved.

## 2. Current State and Gap

1. `16` v3 declares reply/act fields but no tool-op + tool-params field.
2. `11` `ThoughtActionProposalCarrier` carries `requested_op`/`preferred_channels`/`outbound_text` but
   no generic parameter mapping; its `scope` is `internal`/`external`.
3. `12` `NormalizedThoughtActionProposal` requires non-empty `outbound_text` for every `external`-scope
   proposal, and `12`'s engine hardcodes a `_USER_VISIBLE_OPS` set to gate `target_user_id`/
   `outbound_text`/`scope_conflict`. `_build_params` copies only `outbound_text` + target binding.
4. `13` planner already routes by op (`_select_channel`) and binds, but its `missing_op_inputs` check is
   hardcoded to `{reply_message, send_message, speak_text}`; it has no generic per-op input knowledge.
   Both planner request bridges hardcode `behavior_snapshot.registered/reviewed = True` (a shim).
5. `30` `ChannelDriverDescriptor` declares `output_ops` (names) but no per-op properties.

## 3. Target Architecture

### 3.1 Per-op driver self-description (`30`)

The descriptor gains a per-op property declaration. Each op's properties are a small fixed taxonomy on
each axis; the driver declares them, and each axis has a named consumer:

```python
# channel/contracts.py
OpEffectClass = Literal["internal_cognitive", "local_host", "external_world"]
OpRiskClass  = Literal["unrestricted", "governed", "restricted"]

@dataclass(frozen=True)
class ChannelOpSpec:
    op_name: str
    required_params: tuple[str, ...] = ()       # R85-active: 13 generic input validation
    user_visible: bool = False                   # R85-active: 13 user-visible checks; 16 rendering
    effect_class: OpEffectClass = "external_world"   # declared in R85; deep consumer 17/R87
    risk_class: OpRiskClass = "unrestricted"     # declared in R85; enforced 13+14 in R86
    # __post_init__: non-empty op_name and required-param keys; taxonomy membership

class ChannelDriverDescriptor:
    ...
    output_op_specs: tuple[ChannelOpSpec, ...] = ()   # additive, default empty
    # __post_init__: each spec.op_name in output_ops; unique per op
    def op_spec(self, op_name: str) -> ChannelOpSpec | None: ...
```

Axis discipline (honoring `ARCHITECTURE_PHILOSOPHY` §8 - no orphan taxonomy): every axis has a real
near-term consumer. `required_params` and `user_visible` are **exercised in R85**; `effect_class` is
**declared in R85** and consumed by `17`/`23` consequence classification in R87; `risk_class` is
**declared in R85** and enforced by the `13`+`14` fail-closed gate in R86 (command execution). The
driver genuinely knows all four; declaring `effect_class`/`risk_class` now is honest forward design
(stated as declared-not-enforced), not theater, and avoids re-touching every driver in R86/R87.

Driver declarations:

- CLI: `reply_message` -> `required_params=("outbound_text","target_user_id")`, `user_visible=True`,
  `effect_class="external_world"`, `risk_class="unrestricted"`.
- OS file-system: `fs_read` -> `("path",)`; `fs_modify` -> `("path","content")`;
  `fs_write` -> `("path","content")`; `fs_list` -> `()`. All `user_visible=False`,
  `effect_class="local_host"`, `risk_class="unrestricted"` (R85; R86 may reclassify writes as
  `governed`).

The specs travel to the planner with no new transport: `ChannelStateSnapshot` already carries the
descriptors; `ChannelSubsystemStateProvider.channel_descriptor_snapshot` projects an additive
`op_specs: {op_name: {required_params, user_visible, effect_class, risk_class}}` into the planner
descriptor snapshot.

### 3.2 `16` v3 tool-intent schema fields

The v3 `response_schema` layer gains three optional fields plus hard rules:

- `i_want_to_use_tool` (bool), `tool_op` (string | null), `tool_params` (object of scalar values | null).
- Hard rules: `tool_op` only when `i_want_to_use_tool`; `tool_params` only with a non-null `tool_op`; a
  tool op and a user-visible send are independent (owner + planner arbitrate). Available ops are
  described from the injected ready-channel/op facts (extend the R79 ready-channel projection to list
  each connected driver's op names), so the model is told which ops exist rather than guessing.

Pure prompt-layer text; no `EmbodiedPromptContract` field change.

### 3.3 `11` tool-intent parse and carrier

`_parse_structured_thought` extracts the tool-intent fields (after the existing think/fence stripping).
The judgment-mapping helper builds a `ThoughtActionProposalCarrier` when a tool intent is present:

- `scope="external"` (the D1 meaning: it invokes an effector op; `internal` stays "no effector op,
  pure continuation"), `requested_op=tool_op`, `op_params=<bounded scalar tool_params>`,
  `preferred_channels` left to the planner (an optional non-authoritative model channel hint may be
  recorded), `outbound_text=None`, `behavior_name=tool_op`, a `reason_trace`, `governance_hints`.
- The owner maps at most one action proposal per tick with a documented deterministic precedence (a
  tool intent takes the action slot when present; the reply/say path is unchanged when absent),
  recorded in `reason_trace`.
- A malformed/partial tool intent (flag set but no op; op set but `tool_params` not an object; a
  non-scalar param value) yields **no** tool proposal; the tick closes through the existing no-proposal
  path. The owner never fabricates an op or params.

Contract additions (`internal_thought/contracts.py`): `op_params: Mapping[str, object] = {}` (additive;
bounded scalar values; frozen in `__post_init__`). The `scope` taxonomy is unchanged
(`internal`/`external`); no `"tool"` value is added (D1). A `tool`-style proposal is just an `external`
proposal whose op is not user-visible - the op's `user_visible` property (from the driver), not the
scope, decides user-visibility.

### 3.4 `12` structural normalization only (D2a)

`12` no longer performs op-aware (channel-state-dependent) validation, because it runs before the
planner and has no channel-state. It does structural normalization + structural rejection only:

- Reject `missing_candidate_channels` when the proposal declares no preferred channels (structural).
- `_build_params` merges `proposal.op_params` + the existing `target_binding_context` (and
  `outbound_text` when present) into the normalized `params`. So for a reply, composition's injected
  `target_user_id`/`outbound_text` land in `params`; for `fs_write`, `path`/`content` land in `params`.
- Drop the hardcoded `_USER_VISIBLE_OPS` set and the `target_user_id`/`outbound_text`/`scope_conflict`
  checks - those move to `13` (§3.5).
- `NormalizedThoughtActionProposal.__post_init__` drops the "external requires outbound_text" rule
  (relaxation; enforcement relocates to `13` via the op's declared `required_params`). `scope` taxonomy
  unchanged.

The `12` bridge-rejection reasons `missing_outbound_text`/`missing_target_user_id`/`scope_conflict`
remain in the taxonomy (compat) but are no longer emitted by the first-version path; the equivalent
enforcement is the planner's generic `missing_op_inputs` consistency failure.

### 3.5 `13` planner: generic op-aware validation + capability gate

- Generic input validation: for the selected op, read the selected channel descriptor's
  `op_specs[selected_op].required_params` and fail `missing_op_inputs` (consistency failure) if any key
  is absent from `proposal.params`. This single generic check replaces the hardcoded reply check and
  uniformly covers reply (`outbound_text`+`target_user_id`) and `fs_*` (`path`/`content`). When an op
  declares no spec (legacy shim descriptors), fall back to the existing reply-op `outbound_text` check
  so the default/`legacy_constant` assembly is byte-for-byte unchanged.
- `user_visible` handling: the planner reads the op's `user_visible` from the spec; the user-visible
  required keys (`target_user_id`) are simply part of `required_params`, so no separate scope check is
  needed. (A future user-visible-specific policy, e.g. content moderation, has a clean hook here.)
- Capability gate (Q2): composition derives `behavior_snapshot.registered`/`reviewed` from real
  channel-state - an op offered by a connected outbound driver is a registered, reviewed behavior; an
  unoffered op is `registered=False` (-> `behavior_not_registered`), reinforcing `_select_channel`'s
  `no_channel_available`. The driver self-description is the capability registry; no `14` governance in
  R85.
- `risk_class` is read-through only in R85 (recorded in the policy trace for observability); it is not
  yet a gate. R86 adds the `governed` -> `14` fail-closed enforcement here.

### 3.6 Composition wiring (opt-in, channel-bound)

- `ChannelSubsystemStateProvider.channel_descriptor_snapshot` projects `op_specs` (the four axes) per
  driver into the planner descriptor snapshot.
- `ChannelBackedPlannerBridgeRequestBridge` derives the capability gate (`registered`/`reviewed`) from
  whether the proposal's op is offered by a connected driver.
- The v3 prompt path's ready-channel projection is extended to list each connected driver's op names so
  the model is told which tools exist.
- The end-to-end loop runs on the channel-bound assembly with the OS driver bound
  (`channel_drivers=(os_fs,)` from R84).

## 4. Data Structures

1. `ChannelOpSpec` (new) + `ChannelDriverDescriptor.output_op_specs` (additive) + `op_spec(op_name)`;
   `OpEffectClass`/`OpRiskClass` taxonomies. Axes: `required_params`, `user_visible` (R85-active);
   `effect_class` (R87 consumer), `risk_class` (R86 consumer).
2. `ThoughtActionProposalCarrier.op_params` (additive). `scope` taxonomy unchanged (no `"tool"`).
3. `NormalizedThoughtActionProposal`: the `external`-scope outbound_text rule removed; `scope` taxonomy
   unchanged.
4. Planner descriptor snapshot gains an additive `op_specs` key (composition projection).
5. v3 schema tool-intent fields (prompt layer text only; no `EmbodiedPromptContract` field change).
6. No change to `RawSignal`, `OutboundPacket`, `ActionDecision`, the transport stages, or `25`.

## 5. Module Changes

1. `channel/contracts.py` - `ChannelOpSpec` + `output_op_specs` + `op_spec` + taxonomies.
2. `channel/drivers/cli.py`, `channel/drivers/os_fs.py` - declare `output_op_specs`.
3. `channel/engine.py` - the per-op specs ride the existing `ChannelStateSnapshot` (no change beyond
   descriptors already being carried; confirm projection in composition).
4. `prompt_contract/engine.py` - v3 tool-intent fields + ready-ops listing.
5. `internal_thought/contracts.py` - `op_params` (additive).
6. `internal_thought/engine.py` - parse tool-intent fields; build the carrier with deterministic
   action-slot precedence; malformed -> no proposal.
7. `action_externalization/contracts.py` - drop the external-scope outbound_text rule.
8. `action_externalization/engine.py` - structural-only normalization; merge `op_params`; drop
   `_USER_VISIBLE_OPS` gating.
9. `planner_bridge/engine.py` - generic `required_params` validation from `op_specs` (legacy reply
   fallback); record `risk_class`/`effect_class` in the policy trace.
10. `composition/bridges.py`, `composition/runtime_assembly.py` - project `op_specs`; derive the
    capability gate from channel-state; extend the v3 ready-ops projection.
11. Tests + docs (see `task.md`).

## 6. Migration Plan

1. Additive and opt-in. With no tool intent asserted, `11`/`12`/`13` behavior is unchanged.
2. The reply path is preserved but enforced generically in `13` (via the CLI op spec's
   `required_params`) instead of `12`'s hardcoded set; `12` relocates those checks to `13` (D2a).
   Existing reply tests are migrated to assert the rejection now surfaces as the planner's
   `missing_op_inputs` consistency failure rather than `12`'s `bridge_rejected`.
3. The planner's generic validation falls back to the existing reply check when an op declares no spec,
   so the default/`legacy_constant` assembly (shim descriptors, no `op_specs`) is byte-for-byte
   unchanged.
4. `effect_class`/`risk_class` are declared but not enforced in R85 (recorded only); R86/R87 enforce.
5. The end-to-end autonomous loop runs only on the channel-bound assembly with the OS driver bound; CI
   uses a deterministic provider, with an opt-in real-LLM smoke.

## 7. Failure Modes and Constraints

1. Malformed/partial tool intent -> no tool proposal (no fabrication); the tick closes through the
   no-proposal path.
2. Tool op with no preferred channel -> `12` `missing_candidate_channels` (structural rejection).
3. Op no connected driver offers -> planner `behavior_not_registered` / `no_channel_available`; never a
   fabricated execution.
4. Missing required param for the selected op -> planner `missing_op_inputs` consistency failure
   (uniform across reply and tool ops).
5. Effector execution failure -> the R84 failure `tool_result` reafference; never reported as success.
6. Constraints: cognition never selects/binds/validates a channel; per-op properties live in the
   driver, not the planner or cognition; no native function-calling; no degraded path;
   `effect_class`/`risk_class` declared honestly as not-yet-enforced. Owner-boundary + ad-hoc-logging
   guards stay green.

## 8. Observability and Logging

No new logging mechanism. Tool intent rides the structured envelope; the bound decision rides the
existing `ActionDecision`/dispatch contracts (the policy trace now records the op's
`effect_class`/`risk_class`); the result rides the R84 `tool_result` reafference. The full chain is
reconstructable through the existing `21`/`17`/`23` surfaces. No `logging`/`print` under `src/`.

## 9. Validation Strategy

1. Unit (`30`/drivers): each driver's descriptor declares the per-op spec (four axes); `op_spec`
   returns it; CLI reply + each `fs_*` op covered; a spec referencing an undeclared op raises.
2. Unit (`11`): a tool-intent envelope parses into an `external`-scope carrier with the op + `op_params`;
   a malformed intent yields no tool proposal; reply/no-action paths unchanged; deterministic
   action-slot precedence when both a say and a tool intent are present.
3. Unit (`12`): a tool proposal normalizes with `op_params` in `params` and no outbound_text
   requirement; only structural rejections remain (missing channels); the reply normalization still
   carries `outbound_text`/`target_user_id` into `params`.
4. Unit (`13`): generic validation passes a complete `fs_write` (path+content) and a complete reply
   (outbound_text+target_user_id), fails a missing key with `missing_op_inputs`, binds the op to the
   declaring driver, rejects an unoffered op (`behavior_not_registered`/`no_channel_available`), and the
   legacy reply fallback still catches a missing reply text when no spec is declared; the op's
   `effect_class`/`risk_class` appear in the policy trace.
5. Composition (network-free, deterministic provider): a channel-bound assembly with the OS driver bound
   and a model-asserted `fs_write` intent binds -> dispatches -> executes -> the result re-enters `02`
   as a `tool_result` on the next tick (assert via a tmp sandbox + the inbound drain).
6. Composition: an unoffered tool op is a formal rejection; a reply-only tick is unchanged; the default
   assembly is unchanged.
7. Opt-in real-LLM smoke (not in CI): a real model asked to use a file tool drives the same loop.
8. Guards: owner-boundary + ad-hoc-logging green; full network-free suite green.
