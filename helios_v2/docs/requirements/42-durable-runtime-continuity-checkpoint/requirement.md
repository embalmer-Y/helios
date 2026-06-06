# Requirement 42 - Durable Runtime Continuity Checkpoint and Restart Resumption

## 1. Background and Problem

Requirements `33` and `34` opened the P2 persistence base: the `15` experience-writeback
continuity stream is durably appended to a SQLite file and re-enters the `10` directed-retrieval
thought window after a restart (recency in `33`, semantic in `34`). That is durable *episodic
experience* — what happened can be recalled.

But the system's genuinely cross-tick *runtime continuity state* is still lost on process exit.
Two owner-published states are carried across ticks purely in process memory today:

1. The `09` thought-gating owner's `ContinuationPressureState`, held in
   `ThoughtGatingRuntimeStage._prior_continuation_state` and fed back into the next tick's gate
   evaluation. Active continuation pressure (unresolved thinking that should continue next tick)
   is the architecture's first-class "I was in the middle of thinking about something" signal.
2. The `18` autonomy owner's long-horizon continuity (`DeferredContinuityRecord` tuple and the
   `24` `ContinuityThread` tuple), held in `AutonomyRuntimeStage._prior_deferred_records` and
   `._prior_continuity_threads` and fed back into the next tick's proactive-drive request. These
   are the architecture's first-class long-horizon "tendencies I keep returning to" signal.

On restart both reset to inert: continuation pressure becomes `ContinuationPressureState.inactive()`
and the deferred-record / thread tuples become empty. So even with `33`/`34` enabled, a restarted
process can recall *what happened* but resumes as if it had never been mid-thought and had no
long-horizon threads. This directly weakens the locked final-goal acceptance criterion `FG-5.1`
("after a process restart, the system retains continuity and subjectively re-enters a prior
existence") and the philosophy's P2 hard-constraint that P2 is the prerequisite for all later
self-evolution phases. The `ARCHITECTURE_PHILOSOPHY` §13.2 marks P2 as the highest-priority next
phase, and `OWNER_GUIDE` §5 lists "latest-state checkpoint/restore" as an explicit P2 remainder
for `09`/`18`/`14`.

This requirement adds a durable latest-state checkpoint of the genuinely cross-tick runtime
continuity state and restores it at startup, so a restarted runtime resumes its prior continuation
pressure and long-horizon continuity threads instead of starting inert.

## 2. Goal

Establish a durable runtime-continuity checkpoint owner that, on an opt-in assembly, saves a
latest-state snapshot of the genuinely cross-tick owner-published continuity state (`09`
continuation pressure and `18`/`24` long-horizon continuity) after each tick, and restores it at
startup so the `09` and `18` owners resume from their prior cross-tick state after a process
restart against the same durable file; the checkpoint owner stores and returns owner-published
state verbatim and never computes, reinterprets, or owns any continuity decision, and the default
(non-checkpointing) runtime is byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Checkpoint owner and contracts

1. A new infrastructure owner `helios_v2.continuity_checkpoint` must own a durable latest-state
   checkpoint of runtime continuity state.
2. The owner must define a `RuntimeContinuitySnapshot` contract that carries, as owner-neutral
   serializable values, the latest `09` continuation-pressure state and the latest `18`/`24`
   long-horizon continuity state (deferred-continuity records plus continuity threads), plus the
   `tick_id` the snapshot was captured at.
3. The owner must define a `CheckpointStoreBackend` protocol with a first-version SQLite file
   backend and a deterministic in-memory backend double.
4. The owner must expose a `ContinuityCheckpointStore` facade that supports saving the latest
   snapshot (overwriting any prior latest snapshot) and loading the latest snapshot (or reporting
   explicit absence when none exists).
5. The checkpoint is latest-state only: the store must keep one current snapshot, not an append
   log. Saving a new snapshot must replace the prior one.

### 3.2 Save-after-tick

1. On an opt-in assembly with checkpointing enabled, after each completed tick the runtime must
   capture the just-completed tick's published `09` continuation-pressure state and `18`/`24`
   long-horizon continuity state from the tick's stage results and save them as the latest
   snapshot.
2. The capture must read only owner-published stage-result values; it must not recompute or
   reinterpret any continuity decision.
3. A snapshot save failure must propagate as a hard stop; the runtime must not silently continue
   without persisting (no degraded non-checkpointing path once checkpointing is enabled).

### 3.3 Restore-at-startup

1. On an opt-in assembly with checkpointing enabled, at assembly/startup the runtime must load the
   latest snapshot (when one exists) and seed the `09` thought-gating stage's prior
   continuation-pressure state and the `18` autonomy stage's prior deferred-records and continuity
   threads from it, so the first post-restart tick resumes from the restored cross-tick state.
2. When no prior snapshot exists (cold checkpoint store), the runtime must start with the existing
   inert defaults (inactive continuation pressure, empty deferred records, empty threads), exactly
   as the non-checkpointing runtime does.
3. Restoration must reconstruct the owners' own state contracts (so the owners' validation runs on
   the restored values); a corrupt or invariant-violating stored snapshot must fail fast rather
   than seed an invalid state.

### 3.4 Rollout and boundary

1. Checkpointing must be opt-in and default-off. The default and existing `33`/`34`/channel-bound
   assemblies must be byte-for-byte unchanged when checkpointing is not enabled.
2. A `continuity_checkpoint_ready` critical dependency must be added to the startup gate only when
   checkpointing is enabled, failing fast when the checkpoint backend cannot initialize (for
   example an unwritable path).
3. Checkpointing must be independent of `33`/`34`: it may be enabled with or without the durable
   experience store, since it persists a different state (latest cross-tick continuity vs the
   episodic experience stream).

## 4. Non-Functional Requirements

1. Performance: a save writes one bounded latest-state row per tick; a load reads one row at
   startup. No per-tick scan of history.
2. Reliability: the SQLite backend must persist across process exit and re-open of the same file;
   save must be atomic at the single-snapshot granularity (a new save fully replaces the prior
   latest snapshot or fails).
3. Observability: the checkpoint owner must not introduce a second logging mechanism; it emits
   nothing itself. Existing `21` kernel-level observability is unchanged.
4. Compatibility/migration: no new heavyweight dependency (standard-library `sqlite3` and `json`
   only). The checkpoint file must be git-ignored.

## 5. Code Behavior Constraints

1. The checkpoint owner must not import any cognitive owner (`09`, `18`, `24`) to compute state; it
   stores and returns owner-published serializable values only. Reconstruction of owner state
   contracts from a loaded snapshot is owner-neutral composition glue, not checkpoint-owner policy.
2. The checkpoint owner must never fabricate, default, or partially synthesize a continuity state.
   A missing snapshot is reported as explicit absence; a corrupt snapshot is a hard stop.
3. No degraded path: once checkpointing is enabled, a backend initialization failure or a save
   failure must fail fast, never silently fall back to a non-persistent run.
4. The save/restore carry must remain owner-neutral, mirroring the existing `_persist_experience`
   and timeline-carry seams in `RuntimeHandle`. It must not move continuity ownership out of `09`
   or `18`.
5. Scope honesty: this requirement checkpoints only the state that is genuinely cross-tick in the
   current runtime (`09` continuation pressure; `18`/`24` long-horizon continuity). The `04`
   neuromodulator, `05` feeling, and `14` identity states are not cross-tick in-process state in
   the current codebase (they are stateless-per-tick or snapshot-supplied), so they are explicitly
   out of scope here; the snapshot contract must be shaped so they can be added additively when
   their dual-timescale or persisted carry lands. `06` memory-item persistence is also a separate
   slice.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/continuity_checkpoint/__init__.py` (new owner package)
2. `helios_v2/src/helios_v2/continuity_checkpoint/contracts.py` (new: snapshot + backend protocol)
3. `helios_v2/src/helios_v2/continuity_checkpoint/engine.py` (new: facade, SQLite + in-memory backends)
4. `helios_v2/src/helios_v2/runtime/stages.py` (seed seam on `ThoughtGatingRuntimeStage` and `AutonomyRuntimeStage` prior-state fields)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in wiring: save-after-tick, restore-at-startup, dependency spec)
6. `helios_v2/src/helios_v2/composition/bridges.py` (owner-neutral snapshot projection/reconstruction)
7. `helios_v2/src/helios_v2/composition/dependencies.py` (`continuity_checkpoint_ready` spec + provider)
8. `helios_v2/tests/test_continuity_checkpoint_contracts.py`, `tests/test_continuity_checkpoint_engine.py`, and a restart-resumption composition test (new)
9. `helios_v2/docs/requirements/index.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (truth sync on implementation)

## 7. Acceptance Criteria

1. With checkpointing enabled against a SQLite file, after running ticks that produce active
   continuation pressure and at least one continuity thread, a fresh runtime assembled against the
   same file (a simulated restart) starts its first tick with the restored continuation-pressure
   state and the restored deferred-records/threads, verified by provenance (the restored values
   equal the last saved snapshot's values), not by string match.
2. With a cold checkpoint store, the restored runtime starts with inactive continuation pressure
   and empty deferred-records/threads, identical to the non-checkpointing runtime.
3. The default assembly and the existing `33`/`34`/channel-bound assemblies are unchanged when
   checkpointing is off (existing tests stay green; no stage-order or contract change).
4. The SQLite and in-memory backends round-trip a `RuntimeContinuitySnapshot` exactly (the loaded
   snapshot's continuation state, deferred records, and threads equal the saved ones) across a
   backend re-open.
5. A save failure or backend-initialization failure fails fast (`continuity_checkpoint_ready`
   surfaces unavailable at the startup gate; a save error propagates), with no silent
   non-persistent fallback.
6. A corrupt or invariant-violating stored snapshot raises on load rather than seeding an invalid
   owner state.
7. The full test suite passes and remains network-free.
