# Requirement 85 - LLM-driven autonomous tool selection (cognition to planner-bound effector op)

## 1. Background and Problem

Requirement `84` shipped the first effector driver (the sandboxed OS file-system `ChannelDriver`) and
the efference -> reafference loop: a planner-accepted `fs_*` op executes inside a sandbox and its
result re-enters `02` sensory as a `tool_result` stimulus. R84 deliberately stopped at the loop
*mechanism*: it demonstrated the loop by dispatching an `OutboundPacket` directly through the
subsystem in a test, because the planner does not yet receive a real `fs_*` op intent from cognition.

Today the cognition-to-action chain can only externalize a user-visible reply. The `11` internal
thought owner emits a `ThoughtActionProposalCarrier` whose only payload beyond an op name is a
reply-specific `outbound_text`; the `16` v3 embodied-prompt schema lets the model say something
(`i_want_to_say`/`i_send_through`) but has no field to express "I want to use a tool, this op, these
parameters"; and the `NormalizedThoughtActionProposal` requires `outbound_text` for every external
proposal. So even though the `13` planner already routes an op to whatever driver declares it
(`_select_channel(requested_op)` matches a driver whose `supported_ops` contains the op, binds it, and
publishes an `ActionDecision(selected_op, validated_params)`), no real tool intent ever reaches it.

The final-goal capability axis FG-4 ("会熟练使用工具") requires the system to **autonomously** choose,
bind, and initiate a tool call from its own reasoning: thought produces a tool intent -> the planner
binds the tool -> the tool executes -> the result re-enters perception -> the system thinks again. This
requirement closes that gap on top of the R84 effector, keeping owner boundaries intact: the model
supplies tool-intent *content*, the `13` planner remains the sole selection/binding/validation
authority, and each driver owns its own per-op input schema.

## 2. Goal

Enable the LLM-backed `11` thought owner to express a structured tool intent (which op, what
parameters) in its v3 structured output; carry that intent as a first-class effector proposal through
`12` action externalization into the `13` planner; have the planner bind the requested op to whichever
connected driver declares it, validate the op's inputs against that driver's own declared per-op input
schema, and publish an `ActionDecision` that the existing channel-bound dispatch transports to the
effector so its result re-enters `02` and the system can think again - all without native LLM
function-calling, without moving selection authority out of `13`, and without a degraded or fabricated
tool path.

## 3. Functional Requirements

### 3.1 Tool intent in the structured thought output (`16` + `11`)
1. The `16` v3 embodied-prompt schema must declare additional optional tool-intent fields the model
   may populate: a tool-use flag, a tool op name, and a tool parameter object, alongside hard rules
   (a tool op only when the flag is set; tool parameters only with a tool op).
2. The `11` thought owner must parse these fields from the structured envelope and, when the model
   asserts a tool intent, construct a `ThoughtActionProposalCarrier` representing that tool intent
   (carrying the requested op, the tool parameters, and the preferred effector channel) as model
   **content**, while the owner retains all sufficiency/continuation/proposal judgment.
3. A malformed or partial tool intent (flag set but no op, op set but ill-typed params) must not crash
   the tick: the owner must treat it as no tool proposal (the existing `insufficient`/no-proposal
   closure holds), never fabricate an op or parameters.
4. The reply path (`i_want_to_say`/`i_send_through`) and the no-action path must be byte-for-byte
   unchanged when the model asserts no tool intent.

### 3.2 Effector proposal carry (`11` -> `12`)
1. The `ThoughtActionProposalCarrier` must carry a generic, bounded tool-parameter mapping
   (additive `op_params`), so a tool op's parameters (e.g. a file path and content) travel without a
   reply-specific field.
2. The proposal `scope` taxonomy stays `internal` (no effector op; pure continuation) vs `external`
   (invokes an effector op); no per-tool scope value is added. Whether an op is user-visible (and thus
   requires reply content/target) is NOT decided by the proposal or scope - it is a property the owning
   driver declares per op (see 3.3). An effector op is therefore an `external` proposal whose op is
   declared non-user-visible, and it must not be forced to carry `outbound_text` or be misclassified as
   `internal`.
3. The `12` action-externalization owner must normalize a proposal structurally only (it runs before the
   planner and has no channel-state): preserve the requested op, merge the tool parameters into `params`,
   preserve the preferred channels and provenance, and reject only structural problems (e.g. no preferred
   channel). It must not require `outbound_text` by scope, and must not hold any per-op user-visibility
   knowledge.
4. A proposal missing its preferred channel must be a formal structural bridge rejection (existing
   `bridge_rejected` taxonomy), never a silent drop.

### 3.3 Per-op driver self-description (`30` + `31`/`84`)
1. Each `ChannelDriver` must declare, per output op, a small fixed-taxonomy property set: the required
   parameter keys, whether the op is user-visible, the op's effect class, and the op's risk class. This
   declaration is part of the driver's self-description (descriptor) and travels to the planner through
   the real channel-state snapshot.
2. The `required_params` and `user_visible` properties must be actively used in R85; the `effect_class`
   and `risk_class` properties must be declared by the driver but are consumed later (effect_class by
   `17`/`23` in R87; risk_class enforced by `13`+`14` in R86). Each declared property must have a named
   consumer; no property is declared without one.
3. The CLI driver must declare that its reply op is user-visible and requires the reply text and target
   keys; the OS file-system driver must declare each `fs_*` op's required parameters (e.g. `fs_read`
   requires a path; `fs_write` requires a path and content), non-user-visible, with a local-host effect
   class.
4. The planner must validate a proposal's parameters against the selected driver's declared per-op
   required keys generically, replacing any hardcoded per-op input knowledge in the planner; this single
   generic check must uniformly cover the reply op and the `fs_*` ops. A missing required parameter must
   produce the existing `missing_op_inputs` consistency failure. When an op declares no spec (legacy
   shim), the planner falls back to its existing reply check so the default assembly is unchanged.

### 3.4 Planner binding and capability registry (`13`)
1. The planner must remain the sole authority that selects the channel, binds the op, validates the
   inputs, and accepts or rejects the proposal. The thought owner must never select or bind a channel.
2. A tool op must be treated as a registered, reviewed behavior **iff** a connected driver declares
   that output op (the driver's self-description is the capability registry). The composition root must
   project this from the real channel-state snapshot into the planner request; no tool op is acceptable
   unless a connected driver actually offers it.
3. An asserted tool op that no connected driver offers must be a formal planner rejection
   (`no_channel_available` / `requested_op_unavailable`), never a fabricated execution.

### 3.5 End-to-end autonomous tool loop
1. In a channel-bound assembly with the OS file-system driver bound, a fired tick whose model output
   asserts a tool intent must result in the planner publishing an `ActionDecision` for that op, the
   dispatch stage transporting it to the effector, the effector executing it, and the result
   re-entering `02` on a later tick as a `tool_result` stimulus - reconstructable end to end.
2. The complete causal chain (thought tool intent -> planner bind -> effector execute -> result
   reafference -> next-tick thought) must be observable through the existing `21`/`17`/`23` surfaces.
3. A tool failure, rejection, or unavailable op must be written back as a formal non-success outcome
   (planner rejection / consistency failure, or the R84 failure reafference), never silently swallowed
   and never reported as success.

## 4. Non-Functional Requirements

1. Performance: tool-intent parsing and planner validation are bounded per tick; no new per-tick
   network call beyond the single existing thought inference; the effector executes asynchronously
   (R84) so a slow tool never blocks the tick.
2. Reliability and fault tolerance: every malformed intent, missing parameter, unavailable op, and
   execution failure has an explicit formal outcome; there is no degraded tool path and no fabricated
   op or parameter.
3. Observability and logging: no new logging mechanism; tool intent, the bound decision, and the
   result reafference travel through the existing `11`/`12`/`13`/`30` contracts and the `21`/`17`/`23`
   surfaces. No `logging`/`print` under `src/`.
4. Compatibility and migration: additive. The reply path, the no-action path, the default assembly, and
   the `legacy_constant` path are unchanged when no tool intent is asserted. CI stays network-free
   (deterministic fake provider); a real model is exercised only by an opt-in smoke.

## 5. Code Behavior Constraints

1. No native LLM function-calling: tool intent rides the existing structured `json_object` envelope.
   The `25` gateway is unchanged; the model supplies tool-intent content and the owner judges it
   (`ARCHITECTURE_PHILOSOPHY` §14 content/judgment separation).
2. The thought owner (`11`) must not select, bind, or validate a channel; it expresses intent only.
   Selection/binding/validation stays in `13`.
3. Per-op input knowledge must live in the owning driver's self-description, not hardcoded in the
   planner. The planner validates generically against the declared schema.
4. A tool op is acceptable only when a connected driver declares it; an unoffered op is a formal
   rejection. No fabricated execution, no degraded fallback.
5. Effector proposals are not a separate scope value: an effector op is an `external` proposal whose
   user-visibility comes from the owning driver's per-op declaration, never hardcoded by op name in
   `12`/`13` and never smuggled through a reply-specific field.
6. No `logging`/`print` under `helios_v2/src`; the owner-boundary and ad-hoc-logging guard tests stay
   green.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/internal_thought/contracts.py` (additive `op_params`)
2. `helios_v2/src/helios_v2/internal_thought/engine.py` (parse tool-intent fields; build the effector carrier)
3. `helios_v2/src/helios_v2/action_externalization/contracts.py` (drop the external-scope outbound_text rule)
4. `helios_v2/src/helios_v2/action_externalization/engine.py` (structural-only normalization; carry `op_params`)
5. `helios_v2/src/helios_v2/channel/contracts.py` (per-op `ChannelOpSpec` on the descriptor)
6. `helios_v2/src/helios_v2/channel/drivers/cli.py`, `helios_v2/src/helios_v2/channel/drivers/os_fs.py` (declare per-op required params)
7. `helios_v2/src/helios_v2/channel/engine.py` (carry the per-op schema in the channel-state snapshot)
8. `helios_v2/src/helios_v2/planner_bridge/engine.py` (generic per-op input validation from the declared schema)
9. `helios_v2/src/helios_v2/prompt_contract/engine.py` (v3 schema tool-intent fields)
10. `helios_v2/src/helios_v2/composition/bridges.py`, `helios_v2/src/helios_v2/composition/runtime_assembly.py` (project per-op schema + tool-op capability into the planner request; wire the tool-intent prompt/parse)
11. `helios_v2/tests/test_internal_thought_*.py`, `test_action_externalization_*.py`, `test_planner_bridge_*.py`, `test_channel_*_driver.py`, `test_runtime_composition.py` (new tool-path tests)
12. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 7. Acceptance Criteria

1. The `16` v3 schema declares the tool-intent fields with their cross-field rules; the `11` owner
   parses a tool intent into an `external`-scope `ThoughtActionProposalCarrier` carrying the op and
   `op_params`, while a malformed/partial intent yields no tool proposal and the tick still closes.
2. `12` normalizes a proposal structurally (op + merged `op_params`/target binding into `params`,
   preferred channels, provenance) without any per-op user-visibility knowledge and without a
   scope-driven outbound_text requirement; a missing preferred channel is a formal structural rejection.
3. Each driver declares its per-op spec (CLI reply op: user-visible, requires reply text + target;
   `fs_write`: requires path+content, non-user-visible, local-host effect; the other `fs_*` ops likewise),
   covering `required_params`/`user_visible` actively and `effect_class`/`risk_class` as declared, and the
   spec reaches the planner through the channel-state snapshot.
4. The planner validates a proposal's params against the selected driver's declared `required_params`
   generically (uniform for reply and `fs_*`; a missing key -> `missing_op_inputs`), binds the op to the
   declaring driver, derives the capability gate from real channel-state, rejects an op no connected
   driver offers, and falls back to the legacy reply check when an op declares no spec.
5. In a channel-bound assembly with the OS driver bound, a model-asserted `fs_write` intent drives an
   end-to-end loop: planner binds -> dispatch transports -> effector executes inside the sandbox -> the
   result re-enters `02` as a `tool_result` on a later tick, verified network-free with a deterministic
   provider; an opt-in real-LLM smoke shows a real model can drive the same loop.
6. The reply path, the no-action path, the default assembly, and the full `helios_v2/tests` suite
   remain green and network-free; the owner-boundary and ad-hoc-logging guard tests pass.

## 8. Future Extension Scope

1. Requirement `86` (OS command execution) reuses this tool-selection path and adds `13`/`14`
   fail-closed governance for high-risk ops; R85 deliberately does not add governance review (file
   read/write is low-risk and the driver self-description plus sandbox are the R85 gate).
2. Requirement `87` upgrades `17`/`23` consequence corroboration to "really-delivered" using the real
   tool effect.
3. Real network/external drivers (QQ/Lark/voice) reuse the same tool-selection path once bound.
4. Richer tool-intent semantics (multi-op plans, tool-call sequences, retries on failed reafference)
   are out of scope; R85 ships single-op autonomous selection.
