# Requirement 86 - Governed OS command-execution task plan

## 1. Title

Requirement 86 - Governed OS command-execution effector, enforced risk-class gate, and `14` action
authorization

## 2. Task Breakdown (by increment; each increment ends green before the next)

### Increment 1 - command driver (self-contained)
1. `channel/drivers/os_command.py`: `CommandAllowRule`, `DEFAULT_COMMAND_ALLOWLIST`
   (`unrestricted`: ls/dir/cat/type/echo/git status/git diff/git log/python --version/-V;
   `governed`: mkdir/cp/mv), `OsCommandDriverConfig`, `CommandExecutor` protocol +
   `InlineCommandExecutor` (deterministic, no subprocess) + `SubprocessCommandExecutor`
   (no-shell, cwd=sandbox, timeout, output cap), `OsCommandChannelDriver` (R84 acceptance/async/
   reafference/backlog shape; op `run_command`, op-level `risk_class="governed"`, `local_host`).
2. Structural rejections: `command_not_allowlisted`, `unsafe_argument`, `unsafe_path_argument`,
   `self_code_write_denied`; failed dispatch outcome + failure reafference; static readiness = sandbox
   dir exists.
3. `channel/__init__.py` exports.
4. Tests `test_channel_os_command_driver.py`.

### Increment 2 - `13` planner enforced gate
5. `planner_bridge/contracts.py`: additive `PlannerBridgeRequest.governance_approval` (default empty),
   `PlannerBridgeResult.pending_governed_action` (default `None`); doc new rejection reasons
   `risk_class_restricted`/`governance_required`/`governance_denied`.
6. `planner_bridge/engine.py`: enforced risk-class gate (`unrestricted` unchanged; `restricted` →
   `risk_class_restricted`; `governed` → carried-auth lookup → bind / `governance_denied` /
   `governance_required` + publish pending action); `_match_command_policy`,
   `_action_authorization_key`, `_carried_authorization`.
7. Tests in `test_planner_bridge_engine.py` + `test_planner_bridge_contracts.py`.

### Increment 3 - `14` authorization + two-tick carry + composition
8. `identity_governance/contracts.py`: `GovernedActionAuthorization` (new); additive defaulted fields
   `IdentityGovernanceRequest.pending_governed_action`, `IdentityGovernanceResult.governed_action_authorization`,
   `IdentityGovernanceConfig.authorized_governed_action_prefixes`.
9. `identity_governance/engine.py`: `GovernedActionGovernancePath` +
   `FirstVersionGovernedActionGovernancePath` (authorize iff argv starts with a configured prefix and
   posture != stabilize) + `IdentityGovernanceEngine.authorize_governed_action` (inert when no pending
   action); `identity_governance/__init__.py` exports.
10. `14` runtime stage: call `authorize_governed_action` and publish into the result (self-revision
    unchanged).
11. Carry seam: `PriorGovernedAuthorizationHolder` + `RuntimeHandle._carry_governed_authorization`.
12. `composition/bridges.py` + `runtime_assembly.py`: project `command_policy`; project the same-tick
    `13` pending action into the `14` request; project the prior-tick carried authorization into the
    `13` request; build the `14` config with `authorized_governed_action_prefixes` when the command
    driver is bound; opt-in bind the command driver with injected executor + sandbox; readiness over all
    bound drivers; preserve cli-only / `os_fs`-only paths byte-for-byte.
13. `.gitignore`: `data/cmd_sandbox/`.
14. Tests in `test_identity_governance_engine.py`, `test_identity_governance_contracts.py`,
    `test_runtime_composition.py` (end-to-end `git status`; `rm -rf`/`python script.py` fail-closed
    `world_blocked`; `mkdir` two-tick handshake; reply/`fs_*`/default unchanged).

### Increment 4 - docs
15. `index.md` row 86; `OWNER_GUIDE.*` (`13` gate, `14` authorization, the command driver);
    `PROGRESS_FLOW.*`; `ARCHITECTURE_BOUNDARIES.md` (new §4.11 command driver + the gate + the `14`
    authorization); `BRAIN_ARCHITECTURE_COMPARISON.md` (`gap_execution_closure`); `ROADMAP.zh-CN.md`
    (R86 queue → done).

## 3. Dependencies

1. `84` effector pattern + `RuntimeProfile.channel_drivers` + reafference loop.
2. `85` `ChannelOpSpec`/`risk_class` + `op_specs`-driven validation + tool-intent fields +
   planner-rejection `world_blocked` closure.
3. `30`/`31` subsystem, `ChannelSubsystemStateProvider`, transport stages.
4. `13` `_select_channel`/`ActionDecision`; `14` `IdentityGovernanceEngine`; the R49/R62 carry pattern.
5. `25` unchanged (no function-calling). Network-free, subprocess-free CI (`InlineCommandExecutor`);
   real subprocess only via opt-in smoke.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/channel/drivers/os_command.py`, `channel/__init__.py`
2. `helios_v2/src/helios_v2/planner_bridge/contracts.py`, `planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/identity_governance/contracts.py`, `identity_governance/engine.py`,
   `identity_governance/__init__.py`
4. `helios_v2/src/helios_v2/composition/bridges.py`, `composition/runtime_assembly.py`
5. `.gitignore`
6. `helios_v2/tests/test_channel_os_command_driver.py`, `test_planner_bridge_engine.py`,
   `test_planner_bridge_contracts.py`, `test_identity_governance_engine.py`,
   `test_identity_governance_contracts.py`, `test_runtime_composition.py`
7. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.md`, `OWNER_GUIDE.zh-CN.md`,
   `PROGRESS_FLOW.en.md`, `PROGRESS_FLOW.zh-CN.md`, `ARCHITECTURE_BOUNDARIES.md`,
   `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 5. Implementation Order

Increment 1 → 2 → 3 → 4, each green before the next (see §2). The driver lands first (isolated), then
the gate (governed always fail-closed until the carry lands), then the `14` handshake + carry +
composition (completing the loop), then docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_channel_os_command_driver.py -q`
4. `pytest helios_v2/tests/test_planner_bridge_engine.py helios_v2/tests/test_planner_bridge_contracts.py -q`
5. `pytest helios_v2/tests/test_identity_governance_engine.py helios_v2/tests/test_identity_governance_contracts.py -q`
6. `pytest helios_v2/tests/test_runtime_composition.py -q`
7. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`
8. `pytest helios_v2/tests -q`
9. Opt-in real-subprocess smoke (manual, not CI).

## 7. Completion Criteria

1. The command driver declares `run_command` + the default-deny allowlist (`unrestricted` read-only +
   `governed` mkdir/cp/mv); structural rejections + sandboxed no-shell timed-out async execution with a
   single `tool_result` reafference; no interpreter allowlisted.
2. The `13` gate enforces `unrestricted` (unchanged) / `restricted` hard-deny / `governed` carried-auth;
   the per-command policy is driver-declared + composition-projected; no command name hardcoded.
3. `14` authorizes a pending governed action via its owner-private policy (configured prefixes + posture),
   publishes an audited `GovernedActionAuthorization` carried to the next tick, never selects/binds/
   executes; self-revision path + contracts unchanged.
4. End-to-end: `git status` loop; `rm -rf`/`python script.py` fail-closed `world_blocked`; `mkdir`
   two-tick handshake (govern → carry → re-propose → authorized → execute → reafference); opt-in
   real-subprocess smoke.
5. Reply/`fs_*`/no-action/self-revision/default paths + full suite green and network-free
   (subprocess-free in CI); owner-boundary + ad-hoc-logging guards pass; all docs updated in the same
   change set.
