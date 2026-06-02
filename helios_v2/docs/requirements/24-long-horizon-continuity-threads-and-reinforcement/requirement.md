# Requirement 24 - Long-horizon continuity threads and reinforcement in autonomy

## 1. Background and Problem

The autonomy owner (`18`) already preserves deferred continuity across ticks. It carries prior `DeferredContinuityRecord` objects forward, decays their pressure, merges records that share a continuity key, expires records that fall below a pressure floor or run out their tick budget, and publishes generated/merged/resolved/expired counts in the drive-state pressure snapshot.

However, this is still record-level bookkeeping, not thread-level continuity. The wave B exit signal in `BRAIN_ARCHITECTURE_COMPARISON.md` requires autonomy to handle richer continuity evolution than simple bounded carry-forward, and to expose longer-horizon continuity states that remain owner-owned and diagnostically visible. The concrete gaps are:

1. Continuity has no identity beyond a single decaying record. When the same tendency recurs across many ticks, the system cannot say "this is the same long-running concern, now reinforced", only "here is another record that happens to merge by key this tick".
2. Recurrence is not reinforcement. Today a recurring tendency merges or decays, but a tendency that keeps reappearing is not strengthened or distinguished from a one-off tendency that is fading.
3. Competing tendencies have no conflict semantics. Multiple active continuity keys coexist, but there is no explicit notion of which long-horizon thread currently dominates and which is suppressed.
4. There is no explicit long-horizon continuity state for the evaluation owner (`17`/`23`) to consume. Diagnostics can see per-record counts but cannot see thread age, reinforcement, dominance, or suppression.

This matters for the final-goal subjective-continuity standard: a subject that merely carries decaying records is weaker than one that maintains, reinforces, and arbitrates persistent long-running concerns. The structure for that must exist before real cognition can fill it with substantive motive content.

Scope-honesty constraint: this requirement builds the long-horizon continuity-thread structure while the cognition chain is still deterministic first-version shim. It deliberately does not invent rich motive content. Substantive motive evolution is realized later, once real cognition lands, by populating these same thread structures. This requirement is the skeleton, not the content.

## 2. Goal

Introduce a first-class continuity-thread concept in the autonomy owner that aggregates deferred continuity across ticks into reinforceable, conflict-arbitrated, age-aware long-horizon threads, publishes an explicit owner-owned long-horizon continuity state, and exposes that state as formal evidence to the read-only evaluation owner, without inventing motive content, without bypassing planner/channel/governance, and without weakening the existing decay/merge/expire semantics.

## 3. Functional Requirements

### 3.1 Owner boundary
1. The continuity-thread concept must be owned solely by the autonomy owner (`18`). It must not move continuity ownership into composition, evaluation, planner, channel, or governance.
2. The thread layer must build on the existing deferred-continuity record semantics rather than replacing them. Decay, merge, expiry, and resolved/expired accounting must remain intact.
3. The autonomy owner must remain separate from planner authority, channel execution, and governance judgment. Threads must not trigger outward action directly.

### 3.2 Continuity threads
1. The owner must define a first-class `ContinuityThread` concept keyed by continuity key, aggregating the carry history of a recurring tendency across ticks.
2. Each thread must carry at least: a stable thread id, the continuity key, the originating reference, the number of ticks the thread has persisted (age), a reinforcement count, an aggregate thread strength, the current activity state, and the most recent carry reason.
3. A thread must persist across ticks as long as its underlying deferred continuity persists, and must be retired explicitly when its underlying continuity expires or resolves, never dropped silently.

### 3.3 Reinforcement
1. When a tendency recurs (the same continuity key reappears or is re-deferred in a later tick), the owner must reinforce the corresponding thread rather than treat it as unrelated.
2. Reinforcement must increase the thread's reinforcement count and strengthen its aggregate thread strength under an explicit, bounded, deterministic rule.
3. Reinforcement must not bypass the existing per-record pressure decay. Decay still applies to individual carried records; reinforcement is a thread-level signal layered on top.

### 3.4 Conflict arbitration
1. When multiple continuity threads are active in the same tick, the owner must arbitrate them into an explicit dominant thread plus zero or more suppressed threads, using a deterministic rule based on thread strength and age.
2. Suppressed threads must remain preserved as continuity, not discarded. Suppression is a current-tick arbitration outcome, not retirement.
3. The arbitration outcome must be explicit and reconstructable, not implied by ordering alone.

### 3.5 Long-horizon continuity state
1. The owner must publish an explicit long-horizon continuity state summarizing the active threads: total active thread count, the dominant thread, suppressed thread ids, the maximum thread age, and aggregate reinforcement.
2. This state must be a formal owner-owned contract, not a transient dict embedded only in a pressure snapshot.
3. The state must distinguish a freshly-formed thread from a long-persisting reinforced thread.

### 3.6 Evaluation visibility
1. The evaluation owner must be able to consume the long-horizon continuity state as formal read-only evidence, extending the existing autonomy evidence.
2. Evaluation must be able to report long-horizon continuity diagnostics (for example whether a dominant long-running thread is present and reinforced) from this evidence, without mutating autonomy state.
3. Missing long-horizon continuity evidence must be reported explicitly rather than inferred.

### 3.7 No fallback behavior
1. Missing or malformed continuity inputs must fail explicitly through the owner's existing error semantics.
2. Threads must never be dropped silently; retirement must be explicit (expired or resolved).
3. The owner must not fabricate reinforcement or dominance that the carry history does not support.

## 4. Non-Functional Requirements

1. Determinism: for identical request state and identical policy, thread formation, reinforcement, arbitration, and the published long-horizon state must be deterministic and reconstructable.
2. Boundedness: thread count, reinforcement strength, and age accounting must be bounded and must not grow without limit; expiry and resolution must continue to retire threads.
3. Observability: long-horizon continuity must be expressible through the existing `21` event surface and the `23` evaluation timeline-aware diagnostics without a second logging mechanism.
4. Compatibility: the thread layer is additive. Existing autonomy construction, the existing deferred-record carry, and existing tests must remain valid; the existing pressure-component counts must continue to be published.

## 5. Code Behavior Constraints

1. The continuity-thread concept must live in the autonomy owner package. No other owner may compute thread reinforcement or arbitration.
2. The thread layer must not bypass planner/channel/governance, and must not equate any single thread strength with guaranteed outward action.
3. The thread layer must not silently discard a suppressed or carried thread.
4. No degraded or fallback thread mode is allowed; missing inputs fail explicitly.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.
6. The autonomy owner must keep the multi-tick carry state owner-private (in the runtime stage), consistent with the existing deferred-record carry, rather than distributing thread state across unrelated owners.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/autonomy/contracts.py`
2. `helios_v2/src/helios_v2/autonomy/engine.py`
3. `helios_v2/src/helios_v2/autonomy/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/evaluation/contracts.py`
6. `helios_v2/src/helios_v2/evaluation/engine.py`
7. `helios_v2/src/helios_v2/composition/bridges.py`
8. `helios_v2/tests/test_autonomy_contracts.py`
9. `helios_v2/tests/test_autonomy_engine.py`
10. `helios_v2/tests/test_evaluation_engine.py`
11. `helios_v2/tests/test_runtime_composition.py`
12. `helios_v2/docs/requirements/index.md`
13. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
14. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. The autonomy owner exposes a documented, immutable `ContinuityThread` contract and an explicit long-horizon continuity-state contract, both owner-owned.
2. A tendency that recurs across ticks reinforces its thread: reinforcement count and aggregate strength increase under a deterministic bounded rule, while per-record decay still applies.
3. When multiple threads are active, the owner publishes an explicit dominant thread and explicit suppressed thread ids; suppressed threads remain preserved as continuity.
4. The long-horizon continuity state publishes active thread count, dominant thread, suppressed thread ids, maximum thread age, and aggregate reinforcement, and distinguishes a fresh thread from a long-persisting reinforced one.
5. The evaluation owner consumes the long-horizon continuity state as formal read-only evidence and reports an explicit long-horizon continuity diagnostic, with explicit absence handling.
6. Existing deferred-record decay, merge, expiry, and resolved/expired accounting remain intact, and threads are retired only explicitly (expired or resolved).
7. The single-logging-mechanism guard test still passes and the full `helios_v2/tests` suite remains green.

## 8. Future Extension Scope

This requirement is the long-horizon continuity skeleton. Its subjective-continuity value grows once real cognition lands and populates threads with substantive motive content. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. R14/R15 adjacency: connecting long-horizon threads to identity-governance self-evolution and experience-writeback long-range carry, as separate requirements that do not move thread ownership out of `18`.
2. Substantive motive evolution once non-deterministic cognition can shape thread content rather than only deterministic recurrence.
3. Richer arbitration policy (for example value- or goal-conditioned dominance) once cognition provides the conditioning signal.

None of these may be smuggled into this slice. This requirement does not introduce LLM cognition, does not change R14/R15 ownership, and does not grant autonomy any direct channel or planner authority.
