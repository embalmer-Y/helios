# Requirement 29 - Cognition-derived autonomy drive inputs

## 1. Background and Problem

The autonomy owner (`18`) decides each tick's proactive disposition (reflect, explore, externalize, defer) from a small set of drive inputs: `continuation_pressure`, `retrieval_pull`, `temporal_pressure`, `identity_unresolved_pressure`, and an outward-readiness pair (`outward_ready`, `externalization_blocked`). Its deterministic first-version path combines these into `outward_drive` and `proactive_action_requested = outward_drive >= 1.6`, then selects a disposition.

Today these drive inputs are hardcoded constants in the composition autonomy request bridge (`FirstVersionAutonomyRequestBridge`): `continuation_pressure=0.8`, `temporal_pressure=0.7`, `identity_unresolved_pressure=0.6`, `outward_ready=True`, `externalization_blocked=False`. With those constants, `outward_drive = 2.1 >= 1.6` and `outward_ready` are always true, so the autonomy owner externalizes on every tick regardless of what the thought owner actually decided.

After `26`/`27`/`28`, the thought owner (`11`) is real: it produces genuine LLM-backed cognition and, via the structured envelope, decides whether the cycle is sufficient, whether to continue, whether to propose an action, and whether to propose self-revision. `28` lets a no-action decision close through the chain. But the autonomy owner's drive inputs are still disconnected constants, so a tick where the thought owner explicitly chose not to act still drives the autonomy owner to `externalize`. A real LLM smoke run shows exactly this: the thought owner reports a no-action internal-only decision while the autonomy disposition is still `externalize` / `outward_proactive`.

This is an architectural self-inconsistency, not a crash: within one tick the cognition system says "do not act" while the proactivity system says "act". It is the pseudo-completion the philosophy warns about at the autonomy layer (apparent proactivity not grounded in internal state). It also has a concrete downstream cost: `24` continuity threads form only when the autonomy owner defers (produces deferred-continuity records). Because the constants force externalization every tick, deferred records are always cleared and `24` threads never form, so the long-horizon continuity structure built in `24` cannot actually run.

## 2. Goal

Make the autonomy owner's drive inputs derive from the thought owner's real fired-cycle decision (and the existing planner and continuation results) instead of hardcoded constants, so the proactive disposition becomes a faithful downstream consequence of genuine cognition, the no-action/continue decisions actually reach the autonomy owner, and the `24` continuity-thread layer can form and reinforce on real deferrals, while the autonomy owner remains the sole owner of disposition judgment and no new outward channel execution authority is introduced.

## 3. Functional Requirements

### 3.1 Cognition-derived drive inputs
1. The composition autonomy request bridge must derive `continuation_pressure`, `temporal_pressure`, `identity_unresolved_pressure`, the outward-readiness pair, and `retrieval_pull` from explicit upstream owner results for the current tick, not from hardcoded constants.
2. `continuation_pressure` must reflect the thought owner's actual continuation decision: a tick where the thought owner requested continuation must yield a higher continuation pressure than a tick where it concluded the cycle.
3. The outward-readiness pair must reflect whether the thought owner produced an externalizable action proposal: a tick with no action proposal (an internal-only or continue decision) must not present as outward-ready in a way that forces externalization, and a tick whose action proposal was blocked or rejected by the planner must present as externalization-blocked.
4. `identity_unresolved_pressure` must reflect whether the thought owner proposed a self-revision and/or the identity-governance outcome, rather than a fixed constant.
5. `retrieval_pull` may continue to derive from the retrieval bundle as it does today; this requirement does not change retrieval-derived pull.

### 3.2 Faithful proactive disposition
1. A tick where the thought owner produced a normalized, planner-executed action proposal must be able to drive the autonomy owner to `externalize`.
2. A tick where the thought owner explicitly chose not to act (internal-only) or chose to continue must not drive the autonomy owner to `externalize`; it must drive a reflect/explore/defer disposition consistent with the thought owner's decision.
3. A tick where the thought owner proposed an action but the planner blocked or rejected it must be able to drive the autonomy owner to `defer` with a deferred-continuity record, so blocked proactive tendencies are preserved rather than vanishing or being mislabeled as externalized.

### 3.3 Continuity-thread activation
1. Because deferrals now occur on real no-action/blocked ticks, the existing `24` deferred-continuity records and continuity threads must be able to form, reinforce, and arbitrate on real cognition, with no change to the `24` thread semantics themselves.
2. The autonomy owner's existing decay/merge/expire/resolution accounting must remain intact and must continue to operate on the now cognition-derived deferrals.

### 3.4 Owner boundary preserved
1. The bridge must only translate explicit upstream owner results into the autonomy owner's drive-input contract. It must not compute the proactive disposition, must not decide externalization, and must not reinterpret any owner's decision.
2. The autonomy owner remains the sole owner of disposition selection, deferred continuity, and long-horizon threads. The thought owner does not gain authority over autonomy; it only supplies the upstream results the bridge translates.
3. No owner gains outward channel execution authority in this requirement. The autonomy owner may still only request or defer; real outward transport remains a later wave_C requirement.

### 3.5 No fallback or fabrication
1. The drive inputs must be derived from real upstream results present in the current tick. Missing required upstream results must fail fast through the existing stage/owner errors, not be silently replaced by constants.
2. The derivation must be deterministic given the upstream results, so a fixed thought decision yields a fixed autonomy disposition.

## 4. Non-Functional Requirements

1. Determinism: for identical upstream owner results, the derived drive inputs and the resulting disposition must be deterministic and reconstructable.
2. Boundedness: derived numeric drive inputs must stay within the same bounded ranges the autonomy owner already expects; the derivation must not produce out-of-range values.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. The derived drive inputs travel through the existing autonomy request contract; the resulting disposition remains visible through the existing autonomy result and `17`/`23`/`24` diagnostics.
4. Compatibility and migration: additive at the bridge level. The autonomy owner's request and result contracts are unchanged in shape. Existing autonomy owner tests remain valid; composition tests that asserted the old always-externalize behavior are updated to reflect cognition-derived dispositions.

## 5. Code Behavior Constraints

1. The derivation logic must live in the composition autonomy request bridge (owner-neutral translation). The autonomy owner engine and contracts must not be changed to compute the disposition differently; this requirement changes inputs, not the owner's judgment rule.
2. The bridge must derive inputs only from explicit upstream owner result fields (thought-cycle result, planner-bridge result, continuation/gating result, identity-governance result), preserving their provenance.
3. No hardcoded constant may stand in for a value that the upstream owners actually determine this tick.
4. No degraded or fallback derivation is allowed; a missing required upstream result fails fast.
5. No `logging`/`print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (the autonomy request bridge derivation)
2. `helios_v2/src/helios_v2/runtime/stages.py` (only if the autonomy stage must pass an additional already-available upstream result into the bridge)
3. `helios_v2/tests/test_runtime_composition.py`
4. `helios_v2/tests/test_autonomy_engine.py` (only if additional owner-level coverage of derived-input dispositions is added; the owner rule itself is unchanged)
5. `helios_v2/docs/requirements/index.md`
6. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
7. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. The autonomy request bridge derives all drive inputs from explicit upstream owner results; no drive input is a hardcoded behavioral constant.
2. In the assembled runtime with a deterministic fake gateway, a "sufficient + intends_action" thought envelope drives the autonomy owner to `externalize`, and a "continue / no-action" envelope drives the autonomy owner to a non-externalize disposition (`reflect`) with the existing internal-only chain closure intact.
3. A "concluded / no-action" tick (or a planner-blocked action tick) drives the autonomy owner to `defer` and produces a deferred-continuity record, where the pre-R29 constants would have forced `externalize`.
4. Across repeated deferring ticks, the `24` continuity threads form and persist (`active_thread_count >= 1`, `max_thread_age` grows), demonstrating the thread layer now runs on real cognition where it was previously always inert (`active_thread_count` always 0). Stronger cross-tick reinforcement of a single key depends on the `18` continuity-key scheme and is out of scope here.
5. The autonomy owner engine and its contracts are unchanged in judgment logic and shape; the change is confined to the bridge derivation (plus any required stage plumbing for already-available results).
6. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement grounds autonomy drive in real cognition. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Real outward channel execution of a normalized proposal (wave_C outward closure), now meaningful because the externalize decision is cognition-grounded.
2. wave_B long-horizon adjacency (`14`, `15`) consuming the now-active continuity threads as real motive content.
3. Deriving the remaining shim owner inputs (`03-10`) from real signals.

None of these may be smuggled into this slice. This requirement does not introduce external transport, does not change the autonomy owner's judgment rule, and does not move disposition ownership out of `18`.
