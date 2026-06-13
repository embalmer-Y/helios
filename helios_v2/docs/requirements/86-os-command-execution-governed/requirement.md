# Requirement 86 - Governed OS command-execution effector, enforced risk-class gate, and `14` action authorization

## 1. Background and Problem

Requirement `84` shipped the first effector (sandboxed OS file-system driver) and the
efference→reafference loop; `85` made tool selection autonomous and established per-op driver
self-description (`ChannelOpSpec` with `required_params`, `user_visible`, `effect_class`, `risk_class`),
leaving `risk_class` as **read-through only** (recorded in the planner `policy_trace`, not a gate). So
today the only host effects are sandboxed file operations; the system cannot run a process, and there is
no enforced authorization tier separating a harmless command from a dangerous one, and no governance
authority over high-risk actions.

The final-goal capability axis FG-4 ("会熟练使用工具") and the P4 exit gate
(`ARCHITECTURE_PHILOSOPHY` §13.3.2) require OS command execution, but the project's strong constraints
(§7.4 fail-fast, §2 no degraded/fallback, §12.7 no capability via prompt-theater/degradation, §7.6
planner owns binding but not thought, §7.1 one owner per concept) require command execution to be
**governed**: a default-deny allowlist, a hard-denied restricted tier that never executes, and a
fail-closed governance handshake for the mutating ("governed") tier — never a silent or fabricated
success.

R86 closes this gap with three coordinated pieces:
1. a governed OS command-execution effector driver reusing the R84 effector pattern,
2. turning the R85 `risk_class` read-through into an **enforced fail-closed gate** in the `13` planner,
3. extending the `14` identity-governance owner (additively) to be the **authorization authority** for
   the `governed` action tier, through a two-tick, audited, carried, fail-closed approval handshake.

It does NOT execute interpreters or arbitrary code (see §5.6), does NOT implement governed self-code
modification (restricted/denied here; that is P7), and does NOT add native function-calling.

## 2. Goal

Enable the system to autonomously run host commands inside a sandbox and re-perceive their results,
under a first-class, fail-closed, evaluation-reconstructable authorization model: the owning driver
self-describes its per-command allowlist and per-command risk; the `13` planner enforces the
risk-class gate before binding (`unrestricted` proceeds, `restricted`/unknown is hard-denied,
`governed` is fail-closed unless a prior-tick `14` authorization is carried for that exact action); and
the `14` owner is the sole authority that authorizes a `governed` action, publishing an audited
approve/deny decision carried to the next tick. Every rejection, denial, timeout, and execution failure
is a formal non-success outcome. No native function-calling (`25` unchanged); cognition never
selects/binds/authorizes a channel or command; per-command policy lives in the owning driver; action
authorization lives in `14`; the gate lives in `13`.

## 3. Functional Requirements

### 3.1 Governed OS command-execution driver (new `helios_v2.channel.drivers.os_command`)
1. A new effector `ChannelDriver` (`OsCommandChannelDriver`) declares one output op `run_command`
   (`required_params=("command",)`, optional `args` list of string scalars, `user_visible=False`,
   `effect_class="local_host"`, op-level `risk_class="governed"` — the op needs per-invocation policy
   evaluation; see 3.3).
2. The driver owns a declarative **allowlist**: an ordered tuple of allow rules, each an `argv` prefix
   plus a per-command `risk_class` (`unrestricted` or `governed`; a driver never ships a `restricted`
   rule — restricted is "no matching rule"). A request's full argv (`[command, *args]`) must start with
   an allowed prefix to match; the first matching rule's risk applies; no match is denied. The
   first-version allowlist is:
   - **`unrestricted`** (read-only / diagnostic, auto-allowed): `ls`, `dir`, `cat`, `type`, `echo`,
     `git status`, `git diff`, `git log`, `python --version`, `python -V`.
   - **`governed`** (sandbox-confined, bounded mutation; requires `14` authorization): `mkdir`, `cp`,
     `mv`.
   No interpreter, recursive/destructive, privileged, networked, package-installing, or repo-write
   command ships allowlisted (those are restricted by being unlisted; see §5.6).
3. Execution is **no-shell**: argv list + `shell=False`; the driver never interprets shell
   metacharacters, pipes, redirection, or chaining. An argv with a shell metacharacter
   (`| & ; < > $ \` ( ) { } * ? newline`), an absolute-path argument, or a `..` path-traversal argument
   is a structural rejection, never executed.
4. The command runs with cwd confined to a configured sandbox root (default `data/cmd_sandbox/`,
   git-ignored), under a wall-clock timeout, with a bounded captured-output size, and with no driver-
   enabled network. A timeout kills the process and writes a failure reafference.
5. The driver never writes/modifies the Helios source tree or requirement documents: any resolved path
   argument inside the repository `src/`/`docs/` tree is rejected (defense in depth with the restricted
   tier; self-code modification is out of scope, P7).
6. Like R84, execution is asynchronous through an **injected executor**: the network-free
   test/CI/long-run path uses a deterministic `InlineCommandExecutor` (no real subprocess); production
   uses a real `SubprocessCommandExecutor`. The op result (stdout/stderr/exit-code, or a structural
   rejection / timeout / failure) is enqueued exactly once as a `tool_result` `InboundPacket` carrying
   the originating decision's correlation provenance, drained on a later tick into `02`.
7. Failure is never silent and never fabricated as success: a structural rejection returns a failed
   dispatch outcome AND a failure reafference (double write-back); an execution failure (non-zero exit,
   timeout, spawn error) enqueues a failure reafference only; the driver never falls back to a different
   command. The driver executes only an argv matched by an `unrestricted` rule, or by a `governed` rule
   for which the planner already produced a `14`-authorized binding (defense in depth: it would reject a
   `governed`/unknown argv arriving without that authorization). Static readiness = sandbox root exists
   as a directory (fail-fast startup gate when bound; no degraded path).

### 3.2 Driver allowlist projected to the planner as a capability fact
1. The driver's per-command allowlist (argv-prefix → risk_class) is a transport/capability fact the
   driver declares; composition projects it into the planner's channel-state snapshot (additive,
   alongside the R85 `op_specs`), so the planner computes a proposal's per-invocation risk without
   hardcoding any command name.
2. The planner never owns the allowlist content; adding or reclassifying a command is a driver-config
   change, not a planner change.

### 3.3 Enforced risk-class gate in the `13` planner
1. The R85 `op_risk_class` read-through becomes an **enforced gate**. For the selected op the planner
   computes the **effective per-invocation risk**: for an op whose op-level `risk_class` is
   `unrestricted` (reply, `fs_*`) the effective risk is `unrestricted` (byte-for-byte unchanged — no
   command-policy lookup); for an op whose op-level `risk_class` is `governed`/`restricted` (the command
   op) the effective risk is the driver-projected per-command allowlist lookup of `[command, *args]`,
   defaulting to `restricted` when no rule matches.
2. Gate outcomes (all formal, all written back; never a fabricated execution):
   - `unrestricted` → proceed to the existing bind/validate/execute path.
   - `restricted` (including an unknown/non-allowlisted command) → fail-closed rejection
     (`risk_class_restricted`); never bound.
   - `governed` → the planner consults the carried `14` authorization (3.4) keyed by the action's stable
     `action_authorization_key`. When a matching `authorized=True` authorization is carried, the op
     proceeds to bind/execute; otherwise it is a fail-closed rejection (`governance_required` when none
     is carried, `governance_denied` when the carried decision denied it); never bound.
3. The gate is global but behavior-preserving for existing ops: every op shipped before R86 (reply,
   `fs_*`) is op-level `unrestricted`, so the gate is a no-op for them.
4. Defense in depth: the planner refuses to bind a `restricted`/unknown or unauthorized-`governed` op,
   and the driver independently refuses to execute a non-allowlisted command. Neither relies on the
   other.
5. The fixed risk-class taxonomy (`unrestricted`/`governed`/`restricted`) is reused verbatim from R85
   (`OpRiskClass`); R86 adds no new taxonomy value. The op's `effect_class` continues to ride the policy
   trace (R87 consumer); R86 does not consume it.

### 3.4 `14` action authorization (additive; the governance authority for the `governed` tier)
1. The `14` identity-governance owner is the sole authority that authorizes a `governed` action. It is
   extended **additively**: alongside self-revision governance it gains a `GovernedActionAuthorization`
   responsibility. The planner (`13`) enforces the gate; `14` makes the authorize/deny judgment;
   cognition never authorizes. This keeps one owner per concept (`14` = governance authority).
2. The handshake is two-tick and fail-closed, honoring the canonical stage order (`13` → `14` → `15`):
   - Tick N: `11` proposes a `governed` command. `13` finds `governed` with no carried authorization →
     fail-closed `governance_required` (no bind/execute) and publishes the pending action descriptor
     (op, command, args, and a deterministic `action_authorization_key` independent of tick-specific
     ids). `14`, running after `13`, reads the pending action, evaluates it through its owner-private
     `GovernedActionGovernancePath` against its governance config/state, and publishes a
     `GovernedActionAuthorization(action_authorization_key, authorized, reason)`. The authorization is
     carried to the next tick by an owner-neutral holder (the R49/R62 carry pattern). `15` writes the
     `governance_required` rejection as a `world_blocked` continuity record (R85 closure).
   - Tick N+1: if `11` re-proposes the same command (same `action_authorization_key`), `13` finds the
     carried `authorized=True` authorization and proceeds to bind/execute. Execution requires a fresh
     re-proposal from current cognition; the planner never acts on a stored intent without a current
     proposal.
3. `14`'s first-version governed-action policy is a bounded, deterministic, owner-held decision (an
   owner-config governed-action policy plus a governance-posture check), auditable through `14`'s
   existing governance trace, and is NOT auto-approve-everything (that would defeat fail-closed). A
   command that the driver allowlists as `governed` but that `14`'s policy does not authorize stays
   denied.
4. `14` authorizes only the action's authorization (approve/deny); it does not select, bind, or execute
   a channel/command, and it does not own the allowlist (the driver does) or the gate (the planner
   does). The authorization decision and its reason are auditable and carried as formal state, never
   prompt-asserted.

### 3.5 End-to-end governed command loop
1. `unrestricted` command (e.g. `git status`): a fired tick whose model output asserts the
   `run_command` intent binds → dispatches → executes inside the sandbox → re-enters `02` as a
   `tool_result` on a later tick, reconstructable through `21`/`17`/`23`.
2. `restricted`/unknown command (e.g. `rm -rf`, `python script.py`): a fail-closed `risk_class_restricted`
   rejection at the planner, written back as a `world_blocked` continuity record, autonomy/evaluation
   still running; never executed, never partially executed, never reported as success.
3. `governed` command (e.g. `mkdir build`): a two-tick handshake — tick N fail-closed
   `governance_required` + `14` authorization published & carried; tick N+1 (same command re-proposed)
   `14`-authorized → bind → execute → `tool_result` reafference. A `14` denial keeps it
   `governance_denied`, never executed.

## 4. Non-Functional Requirements

1. Performance: allowlist lookup, the planner gate, and `14` authorization are bounded per tick; command
   execution is asynchronous (R84 model) so a slow/timed-out command never blocks the tick.
2. Reliability and fault tolerance: every non-allowlisted command, restricted command, unauthorized/
   denied governed command, structural rejection, timeout, and execution failure has an explicit formal
   outcome; there is no degraded command path and no fabricated result.
3. Security: no-shell, default-deny allowlist, conservative arg-safety (no shell-metachar/absolute/`..`
   args), sandbox cwd, no self-code writes, wall-clock timeout, bounded output cap, no interpreters/
   arbitrary code (§5.6), and a fail-closed governance handshake for mutation. Credentials/privileged
   escalation are never used.
4. Observability and logging: no new logging mechanism; the command intent, the bound decision, the gate
   verdict (policy trace), the `14` authorization, and the result reafference travel through the existing
   `11`/`12`/`13`/`14`/`30` contracts and `21`/`17`/`23` surfaces. No `logging`/`print` under `src/`.
5. Compatibility and migration: additive and opt-in. The reply path, the `fs_*` loop, the no-action
   path, the self-revision governance path, the default assembly, and the `legacy_constant` path are
   byte-for-byte unchanged. CI stays network-free and subprocess-free (deterministic
   `InlineCommandExecutor`); a real subprocess is exercised only by an opt-in smoke.

## 5. Code Behavior Constraints

1. No native LLM function-calling: the command tool intent rides the R85 structured tool-intent fields
   (`i_want_to_use_tool`/`tool_op="run_command"`/`tool_params`). `25` unchanged.
2. Cognition (`11`) never selects, binds, or authorizes a channel/command; selection/binding/validation
   stays in `13`; per-command policy in the driver; action authorization in `14`.
3. The `restricted` tier is a hard deny that never executes; the `governed` tier executes only after a
   carried `14` `authorized=True` for that exact action and a fresh re-proposal. No degraded fallback,
   no fabricated success.
4. No-shell only: argv list + `shell=False`; no pipes/redirection/chaining; shell-metachar, absolute-
   path, and `..` arguments rejected. No self-code (`src/`/`docs/`) writes.
5. `14` is extended additively (new authorization responsibility); its self-revision governance,
   identity-state mutation, and existing contracts/results are unchanged; the owner-boundary and
   ad-hoc-logging guard tests stay green.
6. No interpreters / arbitrary code in R86: `python <script>`, `bash`, `sh`, `node`, `pytest`,
   `powershell`, `cmd`, etc. are NOT allowlisted (restricted), because argv-level allowlisting cannot
   contain effects inside an executed script; true interpreter execution needs OS-level isolation
   (a future requirement). The governed tier is limited to sandbox-confined, bounded, non-interpreter
   mutations.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/channel/drivers/os_command.py` (new), `channel/__init__.py`
2. `helios_v2/src/helios_v2/planner_bridge/contracts.py`, `planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/identity_governance/contracts.py`, `identity_governance/engine.py`,
   `identity_governance/__init__.py`
4. `helios_v2/src/helios_v2/composition/bridges.py`, `composition/runtime_assembly.py` (project command
   policy + pending action; carry the authorization; opt-in bind the command driver; sandbox/executor)
5. `.gitignore` (`data/cmd_sandbox/`)
6. `helios_v2/tests/test_channel_os_command_driver.py` (new), `test_planner_bridge_engine.py`,
   `test_planner_bridge_contracts.py`, `test_identity_governance_engine.py`,
   `test_identity_governance_contracts.py`, `test_runtime_composition.py`
7. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`,
   `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 7. Acceptance Criteria

1. The command driver declares `run_command` and a default-deny allowlist (`unrestricted`: the listed
   read-only/diagnostic commands; `governed`: `mkdir`/`cp`/`mv`); a non-allowlisted command, a
   shell-metachar/absolute/`..` arg, and a self-code-path arg are structural rejections; execution is
   no-shell, sandboxed, timed-out, output-bounded, async via the injected executor, with exactly one
   `tool_result` (success or failure) carrying correlation provenance; no interpreter is allowlisted.
2. The planner enforces the gate: `unrestricted` (reply/`fs_*`/allowlisted read-only command) proceeds
   byte-for-byte; a `restricted`/unknown command → fail-closed `risk_class_restricted`; a `governed`
   command with no carried authorization → fail-closed `governance_required`, with a carried denial →
   `governance_denied`, with a carried `authorized=True` → bind/execute; the per-command policy is
   driver-declared and composition-projected and the planner hardcodes no command name.
3. `14` authorizes a pending `governed` action through its owner-private policy, publishes an audited
   `GovernedActionAuthorization` carried to the next tick, and never selects/binds/executes; its
   self-revision governance path and contracts are unchanged.
4. End-to-end (channel-bound, deterministic `InlineCommandExecutor`): an allowlisted `git status` binds
   → executes → re-enters `02`; an `rm -rf`/`python script.py` is a fail-closed `risk_class_restricted`
   `world_blocked`, never executed; a `governed` `mkdir build` runs the two-tick handshake (tick N
   `governance_required` + `14` authorize/carry; tick N+1 re-propose → authorized → execute →
   `tool_result`); an opt-in real-subprocess smoke drives the same loops.
5. The reply path, the `fs_*` loop, the no-action path, the self-revision governance path, the default
   assembly, and the full `helios_v2/tests` suite stay green and network-free (subprocess-free in CI);
   the owner-boundary and ad-hoc-logging guard tests pass; index, owner guide, both progress-flow maps,
   boundary, grounding, and roadmap docs are updated in the same change set.

## 8. Future Extension Scope

1. Interpreter / arbitrary-code execution (`python <script>`, `pytest`, shells) under real OS-level
   isolation (container/seccomp/restricted user) is a future requirement; R86 keeps them restricted.
2. Governed self-code modification (writing Helios's own source/requirements under a fitness gate) is
   P7; R86 hard-denies it.
3. Richer command semantics (interactive processes, streaming output, env control, pipes/chaining) are
   out of scope.
4. `effect_class`-driven consequence-truth corroboration of a real command effect is R87.
5. Real network/external drivers (QQ/Lark/voice) reuse the same tool-selection + authorization path.
