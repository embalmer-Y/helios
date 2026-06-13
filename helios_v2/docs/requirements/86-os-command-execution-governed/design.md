# Requirement 86 - Governed OS command-execution effector, enforced risk-class gate, and `14` action authorization

## 1. Design Overview

R86 adds a governed OS command-execution effector, turns the R85 `risk_class` read-through into an
enforced fail-closed gate in `13`, and extends `14` (additively) to be the authorization authority for
the `governed` action tier, organized as: **the owning driver self-describes its per-command allowlist
and per-command risk (a transport/capability fact); the `13` planner enforces the risk-class gate
before binding (it owns selection/binding/validation); the `14` owner authorizes a `governed` action
through a two-tick, audited, carried, fail-closed handshake (it owns governance judgment); the
`restricted` tier is a hard deny that never executes; no interpreters / arbitrary code.** The driver
reuses the R84 effector pattern verbatim. Everything is additive and opt-in on the channel-bound
assembly; the reply path, the `fs_*` loop, the no-action path, the self-revision governance path, and
the default assembly are byte-for-byte preserved (every pre-R86 op is op-level `unrestricted`, so the
new gate is a no-op for them; the `14` extension is a new optional method/field that defaults to
inert).

## 2. Current State and Gap

1. Effectors: only the R84 `os_fs` driver. No process execution.
2. `13` (`FirstVersionPlannerBridgePath.evaluate`) selects/binds/validates and records the op's
   `risk_class` in `policy_trace` via `_op_class` — **read-through only**; no gate.
3. `ChannelOpSpec.risk_class` exists (R85) but is unenforced.
4. The composition `ChannelSubsystemStateProvider` projects per-driver descriptors + (R85) `op_specs`
   into the planner request; there is no per-command policy projection and no governance-approval carry.
5. `14` (`IdentityGovernanceEngine`) governs self-revision only; it has no action-authorization concept.
6. The R85 planner-rejection closure (`policy_rejected` → `world_blocked` continuity, autonomy/
   evaluation still run) exists and is reused for R86 fail-closed rejections.
7. Cross-tick carry seams (R49 recall, R62 drive, R55 temporal) establish the owner-neutral
   `RuntimeHandle._carry_*` + prior-holder + request-bridge pattern reused here.

## 3. Target Architecture

### 3.1 Governed command driver (`helios_v2.channel.drivers.os_command`)

Mirrors `os_fs.py`:

```python
OS_COMMAND_DRIVER_ID = "os_command"
RUN_COMMAND = "run_command"

@dataclass(frozen=True)
class CommandAllowRule:
    argv_prefix: tuple[str, ...]
    risk_class: OpRiskClass = "unrestricted"   # unrestricted | governed (never "restricted")
    # __post_init__: non-empty prefix; risk in {unrestricted, governed}

DEFAULT_COMMAND_ALLOWLIST = (
    CommandAllowRule(("ls",)),  CommandAllowRule(("dir",)),
    CommandAllowRule(("cat",)), CommandAllowRule(("type",)), CommandAllowRule(("echo",)),
    CommandAllowRule(("git","status")), CommandAllowRule(("git","diff")), CommandAllowRule(("git","log")),
    CommandAllowRule(("python","--version")), CommandAllowRule(("python","-V")),
    CommandAllowRule(("mkdir",), risk_class="governed"),
    CommandAllowRule(("cp",),    risk_class="governed"),
    CommandAllowRule(("mv",),    risk_class="governed"),
)

@dataclass(frozen=True)
class OsCommandDriverConfig:
    sandbox_root: Path
    driver_id: str = OS_COMMAND_DRIVER_ID
    allowlist: tuple[CommandAllowRule, ...] = DEFAULT_COMMAND_ALLOWLIST
    timeout_seconds: float = 10.0
    max_output_chars: int = 8192
    max_backlog: int = 128
    sandbox_root_resolved: Path = field(init=False)   # resolved once

@runtime_checkable
class CommandExecutor(Protocol):
    def submit(self, work: Callable[[], None]) -> None: ...

class InlineCommandExecutor:      # CI/test: runs work() synchronously, NO subprocess
class SubprocessCommandExecutor:  # production: ThreadPoolExecutor + subprocess.run(shell=False)
```

Op spec on the descriptor: `ChannelOpSpec(RUN_COMMAND, required_params=("command",),
user_visible=False, effect_class="local_host", risk_class="governed")` (op-level `governed` = "needs
per-invocation policy evaluation"; the actual per-invocation risk is the allowlist match).

`send_outbound` reuses the R84 acceptance/async/reafference shape. `_structural_rejection`:
- op not `run_command`, empty `command` → reject.
- argv matches no allow rule → `command_not_allowlisted`.
- matched rule's risk is `unrestricted` → execute. Matched rule's risk is `governed` → execute (the
  planner gate already authorized the binding; the driver trusts the binding but still applies the
  arg-safety checks). The driver never executes an argv that matched no rule.
- shell metacharacter in any arg → `unsafe_argument`; absolute path or `..` arg → `unsafe_path_argument`;
  an arg resolving into repo `src/`/`docs/` → `self_code_write_denied`.

`_execute` runs the command no-shell (real executor: `subprocess.run(argv, shell=False,
cwd=sandbox_root_resolved, capture_output=True, text=True, timeout=...)`; inline executor: a
deterministic canned result keyed by argv for tests), catches `TimeoutExpired`/`OSError`/`CalledProcess`,
and enqueues exactly one `tool_result` `{op, ok, command, exit_code, stdout, stderr}` (truncated)
with correlation provenance. Non-zero exit → `ok=False`; never fabricated success.

`static_readiness` = sandbox root is a directory.

### 3.2 Driver command-policy projected to the planner

`ChannelSubsystemStateProvider.channel_descriptor_snapshot` adds, for a driver declaring the command op,
an additive `command_policy: ({"argv_prefix": (...), "risk_class": "..."}, ...)` (the driver allowlist
as plain data). A driver without a command op projects none. The planner reads it; it hardcodes no
command name.

### 3.3 Enforced risk-class gate in `13`

`FirstVersionPlannerBridgePath.evaluate` gains one gate step after op/spec resolution, before producing
the `ActionDecision`:

```
op_risk = op_spec.risk_class  (default "unrestricted" when no spec)
if op_risk == "unrestricted":
    effective = "unrestricted"
else:
    effective = _match_command_policy(command_policy, command, args)  # argv-prefix; no match -> "restricted"
if effective == "unrestricted":
    proceed (unchanged)
elif effective == "restricted":
    -> policy_rejected("risk_class_restricted")            # hard deny, never bound
elif effective == "governed":
    auth = _carried_authorization(request, action_key)     # from request.governance_approval
    if auth is approved: proceed
    elif auth is denied:  -> policy_rejected("governance_denied")
    else:                 -> policy_rejected("governance_required")   # + publish pending action for 14
```

- `action_key = _action_authorization_key(selected_op, command, args)` — a deterministic stable hash
  (independent of tick-specific ids), computed by the planner. The same key is recomputed on the
  re-proposal tick, so a carried authorization matches.
- On a `governance_required` rejection the planner records the pending action
  (`{action_authorization_key, op, command, args}`) in an additive `PlannerBridgeResult.pending_governed_action`
  field so `14` (running after `13`) can authorize it.
- `request.governance_approval` is an additive mapping `{action_authorization_key: {"authorized": bool,
  "reason": str}}` projected by composition from the prior-tick carried `14` authorization (default
  empty → fail-closed).
- For every pre-R86 op (`unrestricted` op-level), `effective == "unrestricted"` with no lookup —
  byte-for-byte unchanged.
- New `policy_rejected` reasons: `risk_class_restricted`, `governance_required`, `governance_denied`
  (additive; reuse the existing rejection → `world_blocked` closure).

### 3.4 `14` action authorization (additive extension)

`14` gains a second, independent responsibility alongside self-revision, all additive (no existing
field/method/validator changes):

- New contracts (`identity_governance/contracts.py`):
  - `GovernedActionAuthorization` (frozen): `action_authorization_key: str`, `authorized: bool`,
    `reason: str`, `reason_trace: tuple[str,...]` (validated: non-empty key/reason/trace).
  - `IdentityGovernanceRequest.pending_governed_action: Mapping[str,object] | None = None` (additive,
    default `None` → existing construction unchanged; carries `{action_authorization_key, op, command,
    args}`).
  - `IdentityGovernanceResult.governed_action_authorization: GovernedActionAuthorization | None = None`
    (additive, default `None` → existing results unchanged).
  - `IdentityGovernanceConfig.authorized_governed_action_prefixes: tuple[tuple[str,...],...] = ()`
    (additive, default empty → fail-closed: authorize nothing unless explicitly configured).
- New owner-private path + engine method:
  - `GovernedActionGovernancePath` protocol + `FirstVersionGovernedActionGovernancePath`: given the
    pending action + config + the request's governance pressure context, return a
    `GovernedActionAuthorization`. First-version policy: `authorized=True` iff the action's argv
    (`[command, *args]`) starts with one of `config.authorized_governed_action_prefixes` AND the
    governance posture is not `stabilize` (reuse the existing pressure computation); else `authorized=
    False` with a reason. Bounded, deterministic, owner-held, auditable; NOT auto-approve-everything.
  - `IdentityGovernanceEngine.authorize_governed_action(request) -> GovernedActionAuthorization | None`:
    returns `None` when `request.pending_governed_action is None` (inert by default); otherwise runs the
    path. The stage calls both `evaluate_self_revision` (unchanged) and `authorize_governed_action`
    (new) and the result carries both.
- The `14` runtime stage publishes the authorization into its result; the existing self-revision result
  shape is unchanged when no pending action is present.

### 3.5 Two-tick carry seam (composition + RuntimeHandle)

Reuses the R49/R62 owner-neutral carry pattern:
- `RuntimeHandle._carry_governed_authorization`: after a tick, read the `14` result's
  `governed_action_authorization` (if any) and store it in a `PriorGovernedAuthorizationHolder` keyed by
  `action_authorization_key` (bounded; the latest decision per key).
- `14` request bridge (composition): when the same-tick `13` `PlannerBridgeResult.pending_governed_action`
  is present, project it into `IdentityGovernanceRequest.pending_governed_action` (owner-neutral
  forward; composition computes nothing — the planner already produced the descriptor + key).
- `13` request bridge (composition): project the prior-tick carried authorizations into
  `PlannerBridgeRequest.governance_approval` (`{key: {authorized, reason}}`).
- Key computation lives only in the planner (`_action_authorization_key`); composition and `14` only
  forward/echo it.

### 3.6 Composition wiring (opt-in, channel-bound)

- `RuntimeProfile.channel_drivers` (R84) gains the command driver when opted in; coexists with CLI/
  `os_fs` on one subsystem, one sensory source, one readiness gate.
- `ChannelSubsystemStateProvider` projects `command_policy`.
- The `14` `IdentityGovernanceConfig` is built with `authorized_governed_action_prefixes` =
  the governed command set (`("mkdir",), ("cp",), ("mv",)`) when the command driver is bound; empty
  otherwise (fail-closed).
- Production uses `SubprocessCommandExecutor` + `data/cmd_sandbox/`; CI uses `InlineCommandExecutor` +
  a tmp sandbox.
- `CHANNEL_BOUND_STAGE_ORDER` (21 stages) unchanged (just another driver on the subsystem).

## 4. Data Structures

1. `CommandAllowRule`, `OsCommandDriverConfig`, `CommandExecutor`/`InlineCommandExecutor`/
   `SubprocessCommandExecutor`, `OsCommandChannelDriver` (new, `channel/drivers/os_command.py`).
2. `ChannelOpSpec` reused verbatim; the command op declares `risk_class="governed"`.
3. Planner descriptor snapshot gains an additive `command_policy` key; `PlannerBridgeRequest`
   gains `governance_approval` (additive, default empty); `PlannerBridgeResult` gains
   `pending_governed_action` (additive, default `None`); additive rejection reasons.
4. `14`: `GovernedActionAuthorization` (new); additive optional fields on `IdentityGovernanceRequest`,
   `IdentityGovernanceResult`, `IdentityGovernanceConfig`; `GovernedActionGovernancePath` +
   `authorize_governed_action`.
5. `PriorGovernedAuthorizationHolder` + `RuntimeHandle._carry_governed_authorization` (composition).
6. No change to `RawSignal`, `OutboundPacket`, `ActionDecision`, the transport stages, the v3 schema,
   `25`, or any existing `14` self-revision contract field/validator.

## 5. Module Changes

1. `channel/drivers/os_command.py` (new) + `channel/__init__.py` (exports).
2. `planner_bridge/contracts.py` (`governance_approval`, `pending_governed_action`, reasons) +
   `planner_bridge/engine.py` (gate, `_match_command_policy`, `_action_authorization_key`,
   `_carried_authorization`).
3. `identity_governance/contracts.py` (additive contracts/fields) + `identity_governance/engine.py`
   (`GovernedActionGovernancePath`, `FirstVersionGovernedActionGovernancePath`,
   `authorize_governed_action`) + `identity_governance/__init__.py` (exports).
4. `runtime/...` or `composition/runtime_assembly.py` `RuntimeHandle` (`_carry_governed_authorization`)
   + `composition/bridges.py` (`command_policy` projection, pending-action projection into `14`,
   authorization projection into `13`, `PriorGovernedAuthorizationHolder`).
5. `.gitignore` (`data/cmd_sandbox/`).
6. Tests + docs (see `task.md`).

## 6. Migration Plan

1. Additive and opt-in. With the command driver unbound: `13` gate is a no-op (all ops `unrestricted`);
   `14.authorize_governed_action` returns `None` (no pending action); the carry holder is empty; the
   default/`legacy_constant`/`fs_*`/reply paths are byte-for-byte unchanged.
2. The `14` self-revision path, contracts, and validators are untouched; the new authorization is a
   separate method + optional defaulted fields.
3. CI is subprocess-free (`InlineCommandExecutor`); a real subprocess runs only in an opt-in smoke and
   production.
4. `effect_class` stays read-through (R87); interpreters stay restricted (future OS-isolation req).

## 7. Failure Modes and Constraints

1. Non-allowlisted/unknown command → `risk_class_restricted` (gate) + driver `command_not_allowlisted`.
2. Interpreter / recursive-destructive / privileged / networked / repo-write command → not allowlisted →
   `risk_class_restricted`; never executes.
3. `governed` command, tick N (no carried auth) → `governance_required` + `14` authorizes/denies →
   carried; tick N+1 re-proposal → authorized → execute, or denied → `governance_denied`.
4. Shell-metachar/absolute/`..`/self-code-path arg → driver structural rejection.
5. Timeout / non-zero exit / spawn error → failure `tool_result` reafference; never fabricated success.
6. Missing sandbox root when bound → not-ready → fail-fast startup gate.
7. Constraints: no-shell; default-deny; no interpreters; cognition never selects/binds/authorizes;
   per-command policy in the driver, authorization in `14`, gate in `13`; no native function-calling;
   owner-boundary + ad-hoc-logging guards stay green.

## 8. Observability and Logging

No new logging mechanism. The intent rides the R85 tool-intent fields; the gate verdict rides the
`policy_trace` + the formal `policy_rejected` outcome (now incl. effective risk + the pending-action
key); the `14` authorization rides the additive result field; the bound decision rides
`ActionDecision`/dispatch; the result rides the R84 `tool_result` reafference. The full chain
(intent → gate → `14` authorize → carry → re-propose → bind → execute → reafference) is reconstructable
through `21`/`17`/`23`. No `logging`/`print` under `src/`.

## 9. Validation Strategy

1. Unit (driver): descriptor + op spec; the default allowlist (`unrestricted` read-only +
   `governed` mkdir/cp/mv); structural rejections (non-allowlisted, shell-metachar, absolute/`..`,
   self-code path); inline-executor success/failure/timeout reafference; readiness.
2. Unit (planner gate): `unrestricted` op unchanged (no lookup); allowlisted read-only command binds;
   non-allowlisted → `risk_class_restricted`; `governed` with no carried auth → `governance_required`
   (+ pending-action published); with carried approve → binds; with carried deny → `governance_denied`;
   `_match_command_policy` argv-prefix correctness; `_action_authorization_key` stability.
3. Unit (`14`): `authorize_governed_action` returns `None` with no pending action (self-revision path
   unchanged); authorizes a configured governed prefix (posture ok) and denies an unconfigured one / a
   `stabilize` posture; `GovernedActionAuthorization` validation; existing self-revision tests green.
4. Composition (network-free, `InlineCommandExecutor`, deterministic provider): allowlisted `git status`
   end-to-end loop; `rm -rf`/`python script.py` fail-closed `risk_class_restricted` `world_blocked`,
   never executed; `mkdir build` two-tick handshake (tick N `governance_required` + `14` authorize/carry;
   tick N+1 re-propose → authorized → execute → `tool_result` reafference); reply/`fs_*`/default
   unchanged.
5. Opt-in real-subprocess smoke (not in CI): a real allowlisted command + a real governed `mkdir`
   handshake.
6. Guards: owner-boundary (gate reads driver-projected policy; authorization in `14`; no command policy
   in composition/cognition) + ad-hoc-logging green; full network-free, subprocess-free suite green.
