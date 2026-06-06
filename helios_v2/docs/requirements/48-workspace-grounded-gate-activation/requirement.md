# Requirement 48 - Workspace-grounded thought-gate activation

## 1. Background and Problem

With R46 the `07` workspace owner is a real attention bottleneck producing real `workspace_score_hint` values, and with R37 the `09` thought-gate already consumes one real upstream signal (`neuromodulatory_arousal` from `04`). But the `09` gate-signal snapshot still has five composition-injected constants. In `NeuromodulatorAwareThoughtGateSignalBridge` (and `FirstVersionThoughtGateSignalBridge`):

1. `global_activation_level = 0.9` (constant),
2. `workload_pressure = 0.1` (constant),
3. `temporal_signal = 0.4` (constant),
4. `drive_urgency_signal = 0.7` (constant),
5. `dmn_available = True` (constant),

plus a fabricated `selected_stimuli` tuple.

The `09` gate path weights `global_activation_level` at `* 0.20` of the gate score — it is the second-largest non-stimulus term — yet today it is a fixed `0.9` regardless of what the workspace actually did. In `brain.mmd` and global-workspace theory, the gate's "global activation level" is exactly the activation of the global workspace: how strongly the workspace ignited this tick. R46 now produces that real signal — the competition score of the held (retained) working-state content — so the gate's largest workspace-derived term can become real instead of a constant.

Of the five constants, `global_activation_level` is the one with a real upstream owner that runs before `09` today (`07` workspace). The other four have no real producer yet in the runtime order:

- `workload_pressure`, `temporal_signal`, `dmn_available` require currently-unowned producers (a real compute/runtime-pressure source, a clock/temporal source, a DMN-availability source) — the same family as the `gap_interoceptive_signal_source` BODY gap;
- `drive_urgency_signal` is owned by `18` autonomy, which runs *after* `09` in the canonical order, so it can only feed `09` through a cross-tick carry (a separate slice);
- `selected_stimuli` is a `02`/`03` provenance projection, a separate concern.

R48 de-shims `global_activation_level` only, from the real `07` workspace activation, and explicitly leaves the other four constants and the stimulus projection as documented future slices.

## 2. Goal

When workspace-grounded gate activation is enabled, the `09` gate-signal snapshot's `global_activation_level` is the real activation of the global workspace this tick — derived from the `07` working-state held content's competition strength (the maximum retained `workspace_score_hint`, or zero when nothing is held) — rather than a constant, so the gate score reflects how strongly the workspace actually ignited; the `09` owner keeps sole ownership of how `global_activation_level` couples into the gate (its existing weight), composition only forwards the real workspace activation fact, no contract changes, and the default and shim assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Workspace-grounded global activation
1. Under the semantic-memory assembly, composition must source the `09` snapshot's `global_activation_level` from the real `07` workspace stage result of the same tick (the `WorkspaceCompetitionStageResult` already present in the frame, since `07` runs before `09`), rather than the constant `0.9`.
2. The forwarded activation must be a bounded transport projection of already-published `07` values: the maximum `workspace_score_hint` among the candidates retained in the working state (the dominant ignition strength held in attention). When no candidate is retained, the activation must be `0.0` (the workspace did not ignite this tick). The value must stay within `[0,1]`.
3. The projection must be owner-neutral glue: it reads only already-published `07` stage-result values and forwards a raw activation fact. It must not compute the gate score, and it must not change how `09` weights `global_activation_level` (that weighting stays owned by the `09` gate path).

### 3.2 Preserved arousal coupling and contracts
1. The real `neuromodulatory_arousal` coupling from R37 must be preserved unchanged; R48 only additionally grounds `global_activation_level`. Both real facts ride the same gate-signal snapshot.
2. No contract may change. The activation flows through the existing `ThoughtGateSignalSnapshot.global_activation_level` field and the existing `09` gate path; only the value's source changes.
3. The `09` owner must continue to own the gate decision and the `global_activation_level` weight; composition must not move any gate semantic into the bridge.

### 3.3 Real downstream effect
1. The change must be observable: two ticks whose `07` working states hold content of differing competition strength must yield a measurably different `global_activation_level` at `09` (and a correspondingly different contribution to the gate score), attributable to the real workspace activation rather than a constant.
2. The real activation must flow unchanged into the `09` gate result's `contributing_signals["global_activation_level"]`, so evaluation/diagnostics see the real value.

### 3.4 Opt-in rollout and fail-fast
1. Workspace-grounded gate activation must activate on the existing semantic-memory opt-in (durable store and embedding gateway both present), consistent with R37/R46 — because the real `workspace_score_hint` it reads only exists once `07` is de-shimmed under that same opt-in. The default assembly and any assembly without the semantic opt-in must keep the constant `global_activation_level = 0.9` and behave exactly as today.
2. The `07` workspace stage runs before `09`, so its result must be present; a missing or wrong-typed workspace result must be a hard fail (the existing runtime stage error), never a silent fallback to the constant.

## 4. Non-Functional Requirements

1. Performance: the activation is one bounded max over the retained working-state candidates per tick; it must not change the runtime stage execution structure.
2. Reliability and fault tolerance: for identical `07` outputs, the forwarded `global_activation_level` must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. The activation travels only through the existing gate-signal snapshot and gate-result contracts.
4. Compatibility and migration: the workspace-grounded bridge and its wiring are additive and opt-in. The default assembly and the non-semantic assemblies keep their current `09` behavior; existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The activation projection must be owner-neutral composition glue. It reads only already-published `07` stage-result values, forwards a raw bounded activation fact, and computes no gate decision and no gate weighting.
2. The `09` owner must stay the sole owner of the gate decision and of the `global_activation_level` coupling weight. R48 changes the value's source only, not the gate path.
3. No contract change to `ThoughtGateSignalSnapshot` or any `09` contract.
4. No degraded or fallback path when enabled: a missing/wrong-typed `07` result is a hard fail; an empty retained set is a defined `0.0` activation, not a failure.
5. The other four constant gate signals (`workload_pressure`, `temporal_signal`, `drive_urgency_signal`, `dmn_available`) and the `selected_stimuli` projection are explicitly out of scope and remain first-version constants this slice.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (extend the semantic-assembly gate-signal bridge to source `global_activation_level` from the `07` workspace stage result; preserve the R37 arousal sourcing)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (wire the workspace stage name into the bridge if needed; no stage-order change)
3. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly grounds `global_activation_level` from `07`; differing workspace strength → differing activation; default keeps `0.9`)
4. `helios_v2/tests/test_runtime_stage_chain.py` (extend if the gate-signal bridge wiring is asserted there)
5. `helios_v2/docs/requirements/index.md`
6. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
7. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
8. `helios_v2/docs/OWNER_GUIDE.md`
9. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
10. `helios_v2/docs/PROGRESS_FLOW.en.md`
11. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, the `09` snapshot's `global_activation_level` equals the maximum retained `workspace_score_hint` from the same tick's `07` working state (or `0.0` when nothing is retained), within `[0,1]`, not the constant `0.9`.
2. Two ticks whose `07` working states hold content of differing competition strength yield a measurably different `global_activation_level` at `09`, and the real value appears in the gate result's `contributing_signals["global_activation_level"]`.
3. The R37 `neuromodulatory_arousal` coupling is preserved unchanged; both real facts ride the snapshot.
4. No contract changes; the `09` gate path and its `global_activation_level` weight are unchanged; the projection is owner-neutral glue.
5. A missing/wrong-typed `07` workspace result is a hard fail; an empty retained set yields a defined `0.0` activation.
6. Workspace-grounded activation activates only on the semantic-memory opt-in; the default and non-semantic assemblies keep the constant `0.9`, and their existing tests pass unmodified.
7. The four other constant gate signals and the stimulus projection remain first-version constants (explicitly out of scope).
8. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R48 de-shims the `09` `global_activation_level` only. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Real `workload_pressure` from a compute/runtime-pressure producer (the same future owner family as the `gap_interoceptive_signal_source` BODY gap).
2. Real `temporal_signal` from a clock/temporal source and real `dmn_available` from a DMN-availability source.
3. Real `drive_urgency_signal` from `18` autonomy through an explicit cross-tick carry (since `18` runs after `09`).
4. Real `selected_stimuli` provenance projected from the `02`/`03` chain rather than fabricated.
5. The cortisol/inhibition hard-gate coupling once `03` threat grounding is stronger (recorded in the `09` owner next-steps).

None of these may be smuggled into this slice. R48 changes only the source of `global_activation_level`, introduces no contract change, and adds no default-on behavior.
