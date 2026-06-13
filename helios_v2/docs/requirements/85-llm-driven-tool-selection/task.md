# Requirement 85 - LLM-driven autonomous tool selection task plan

## 1. Title

Requirement 85 - LLM-driven autonomous tool selection (cognition to planner-bound effector op)

## 2. Task Breakdown

1. `30` per-op self-description: add `ChannelOpSpec` (axes `required_params`, `user_visible`,
   `effect_class`, `risk_class`) + `ChannelDriverDescriptor.output_op_specs` + `op_spec(op_name)` in
   `channel/contracts.py` (additive, validated against `output_ops`).
2. Declare per-op specs on the drivers: CLI `reply_message` (user_visible, requires
   `outbound_text`+`target_user_id`, external_world); OS file-system `fs_read`->`("path",)`,
   `fs_write`/`fs_modify`->`("path","content")`, `fs_list`->`()`, all non-user-visible, local_host.
3. `13` planner generic input validation: replace the hardcoded reply outbound_text check in
   `planner_bridge/engine.py` with a generic check against the selected channel's `op_specs[op].required_params`
   (uniform reply + `fs_*`), keeping the reply-op fallback when an op declares no spec; record the op's
   `effect_class`/`risk_class` in the policy trace (read-through, not yet a gate).
4. `11` contracts: add `op_params` (additive) to `ThoughtActionProposalCarrier`; the `scope` taxonomy is
   unchanged (no `tool` value).
5. `12` contracts/engine: drop the `NormalizedThoughtActionProposal` external-scope outbound_text rule;
   make the engine structural-only (drop `_USER_VISIBLE_OPS` and the outbound_text/target_user_id/
   scope_conflict checks - relocated to `13`); merge `op_params`+target binding into `params`.
6. `16` v3 schema: add `i_want_to_use_tool`/`tool_op`/`tool_params` fields + hard rules in
   `prompt_contract/engine.py`; list available ops from injected ready-channel/op facts.
7. `11` engine: parse the tool-intent fields; build the effector carrier with deterministic action-slot
   precedence; malformed intent -> no tool proposal.
8. Composition: project per-driver `op_specs` into the planner descriptor snapshot and derive the
   capability gate (`registered`/`reviewed`) from real channel-state in
   `ChannelBackedPlannerBridgeRequestBridge`; extend the v3 ready-ops projection
   (`composition/bridges.py`, `runtime_assembly.py`).
9. Tests: driver specs, `11` parse, `12` structural normalize, `13` generic validation/binding/rejection
   (incl. reply migrated to `13`'s `missing_op_inputs`), and the channel-bound end-to-end loop
   (deterministic) + opt-in real-LLM smoke.
10. Docs: `index.md` row 85, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`, `ARCHITECTURE_BOUNDARIES.md`,
    `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`.

## 3. Dependencies

1. `84` OS file-system effector driver + the generalized multi-driver channel-bound assembly
   (`RuntimeProfile.channel_drivers`) and the result reafference loop.
2. `30`/`31` channel subsystem, `ChannelSubsystemStateProvider`, the two transport stages.
3. `26`/`27`/`79` LLM-backed structured-thought path and the v3 embodied-prompt path.
4. `13` planner `_select_channel(requested_op)` op routing + `ActionDecision`.
5. `25` LLM gateway (`json_object`), unchanged; no function-calling.
6. Network-free CI (deterministic provider); a real model only via an opt-in smoke.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/channel/contracts.py`, `channel/drivers/cli.py`, `channel/drivers/os_fs.py`,
   `channel/engine.py`
2. `helios_v2/src/helios_v2/internal_thought/contracts.py`, `internal_thought/engine.py`
3. `helios_v2/src/helios_v2/action_externalization/contracts.py`, `action_externalization/engine.py`
4. `helios_v2/src/helios_v2/planner_bridge/engine.py`
5. `helios_v2/src/helios_v2/prompt_contract/engine.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`, `composition/runtime_assembly.py`
7. `helios_v2/tests/test_internal_thought_engine.py`, `test_action_externalization_engine.py`,
   `test_planner_bridge_engine.py`, `test_channel_os_fs_driver.py`, `test_channel_cli_driver.py`,
   `test_runtime_composition.py`
8. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.md`, `OWNER_GUIDE.zh-CN.md`,
   `PROGRESS_FLOW.en.md`, `PROGRESS_FLOW.zh-CN.md`, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 5. Implementation Order

1. Land the `30` per-op input schema + driver declarations + the `13` generic validation (with legacy
   fallback) first; unit-test in isolation (no cognition change yet).
2. Add the `11`/`12` contract additions (`op_params`, `tool` scope) + the `12` effector normalization;
   unit-test the carry and rejections.
3. Add the `16` v3 tool-intent schema + the `11` parse/build; unit-test parsing and precedence.
4. Wire composition (op_input_schema projection + capability gate + v3 ready-ops); add the channel-bound
   end-to-end loop test.
5. Add the opt-in real-LLM smoke.
6. Run focused suites, then the full network-free suite and the guards.
7. Update index, owner guide, both progress-flow maps, boundary, grounding, and roadmap docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_channel_os_fs_driver.py helios_v2/tests/test_channel_cli_driver.py -q`
4. `pytest helios_v2/tests/test_internal_thought_engine.py helios_v2/tests/test_action_externalization_engine.py helios_v2/tests/test_planner_bridge_engine.py -q`
5. `pytest helios_v2/tests/test_runtime_composition.py -q`
6. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`
7. `pytest helios_v2/tests -q`
8. Opt-in real-LLM smoke (manual, not CI): a tool-use prompt drives the file-tool loop end to end.

## 7. Completion Criteria

1. Each driver declares its per-op spec (four axes; `required_params`/`user_visible` active,
   `effect_class`/`risk_class` declared); the planner validates generically against `required_params`
   (missing key -> `missing_op_inputs`), with the legacy reply fallback preserving default behavior.
2. `11` parses a tool intent into an `external`-scope carrier with `op_params`; a malformed intent
   yields no tool proposal; reply/no-action paths unchanged (no `tool` scope value added).
3. `12` normalizes structurally (op + merged `op_params`/target binding into `params`) with no per-op
   user-visibility knowledge and no scope-driven outbound_text rule; a missing preferred channel is a
   formal structural rejection; the reply/tool user-visible + required-param checks now surface in `13`.
4. The planner binds a model-asserted `fs_write` to the OS driver and publishes an `ActionDecision`; an
   unoffered op is a formal rejection; the capability gate is derived from real channel-state.
5. The channel-bound assembly runs the end-to-end autonomous loop (tool intent -> bind -> execute ->
   result reafference into `02`) network-free with a deterministic provider; the opt-in real-LLM smoke
   drives the same loop.
6. The default assembly and the full `helios_v2/tests` suite stay green and network-free; the
   owner-boundary and ad-hoc-logging guards pass; index, owner guide, both progress-flow maps, boundary,
   grounding, and roadmap docs are updated in the same change set.
