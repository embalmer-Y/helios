# Requirement 48 - Workspace-grounded thought-gate activation (design)

## 1. Design Overview

R48 grounds the `09` gate-signal snapshot's `global_activation_level` in the real `07` workspace activation under the semantic-memory assembly, without changing any contract or the `09` gate path. It is the next P3 de-shim after `08` (R47), and it reuses the gate-signal bridge seam R37 already established.

One additive, opt-in change, owner-neutral composition glue:

1. The semantic-assembly gate-signal bridge (today `NeuromodulatorAwareThoughtGateSignalBridge`, which already forwards the real `04` norepinephrine as `neuromodulatory_arousal`) additionally sources `global_activation_level` from the same tick's `07` `WorkspaceCompetitionStageResult`: the maximum `workspace_score_hint` among the retained working-state candidates (the dominant ignition strength held in attention), or `0.0` when nothing is retained.

The `09` owner is unchanged: it still owns the gate decision and weights `global_activation_level` at `* 0.20` exactly as today. Only the value's source changes from the constant `0.9` to the real workspace activation. Composition forwards a raw fact; the gate semantic stays in `09`.

## 2. Current State and Gap

Current state (verified in code):

1. The `09` gate path (`_evaluate_first_version_gate`) computes `gate_score` including `+ signal_snapshot.global_activation_level * 0.20` and records it in `contributing_signals["global_activation_level"]`.
2. Composition builds the snapshot via `FirstVersionThoughtGateSignalBridge` (default) or `NeuromodulatorAwareThoughtGateSignalBridge` (semantic assembly, R37). Both set `global_activation_level=0.9` constant. The semantic bridge already reads the `04` stage result from the frame to forward real `neuromodulatory_arousal`.
3. R46 made `07` produce real `workspace_score_hint` on each `WorkspaceCandidate`, and the working state holds a bounded top-K of them. `07` runs before `09` in `CANONICAL_STAGE_ORDER`, so its result is in the frame at `09` time.
4. `WorkspaceCompetitionStageResult` exposes `candidate_set` (all candidates, each with `workspace_score_hint`) and `working_state` (`retained_candidate_ids`).

Gap: `global_activation_level` is a constant `0.9`, ignoring the real workspace activation that now exists one stage upstream.

## 3. Target Architecture

### 3.1 Workspace-grounded activation projection (composition glue)

The semantic-assembly gate-signal bridge gains a workspace stage source. It reads the `07` result from the frame, computes the activation as the max retained `workspace_score_hint`, and forwards it:

```
@dataclass
class WorkspaceAndNeuromodulatorAwareThoughtGateSignalBridge:   # extends the R37 bridge role
    neuromodulator_stage_name: str = "neuromodulator_system"
    workspace_stage_name: str = "workspace_competition_and_working_state"

    def build_signal_snapshot(self, frame, conscious_result) -> ThoughtGateSignalSnapshot:
        # ... resolve neuromodulator_result exactly as R37 (hard-fail if missing/wrong type) ...
        norepinephrine = neuromodulator_result.state.levels.norepinephrine
        workspace_result = <frame.stage_results[workspace_stage_name], hard-fail if missing/wrong type>
        activation = _workspace_activation(workspace_result)   # max retained score, or 0.0
        return ThoughtGateSignalSnapshot(
            ...,
            global_activation_level=activation,                # REAL, was constant 0.9
            ...,
            neuromodulatory_arousal=norepinephrine,            # preserved from R37
        )
```

where the activation projection is:

```
def _workspace_activation(workspace_result) -> float:
    retained = set(workspace_result.working_state.retained_candidate_ids)
    scores = [
        c.workspace_score_hint or 0.0
        for c in workspace_result.candidate_set.candidates
        if c.candidate_id in retained
    ]
    return round(min(1.0, max(0.0, max(scores))), 4) if scores else 0.0
```

Rationale for "max retained score": the global workspace's activation level is the strength of the dominant content it is currently holding in attention (the same content `08` ignites). An empty working state means the workspace did not ignite this tick → `0.0`. This reuses already-published `07` values only; it computes no gate decision and does not touch the `09` weight.

Implementation choice: rather than a second bridge class, R48 may either (a) rename/extend the existing `NeuromodulatorAwareThoughtGateSignalBridge` to also accept the workspace stage name and ground activation, or (b) add a new `WorkspaceAndNeuromodulatorAwareThoughtGateSignalBridge`. Option (a) keeps one semantic-assembly gate bridge and avoids a dead class; the R37 behavior is preserved as a strict superset. The design picks (a): extend the existing bridge to ground `global_activation_level` while keeping its name's intent (it is the semantic-assembly gate-signal bridge). If clarity is preferred, (b) is acceptable as long as the old class is removed from the assembly path. (Tasks pick (a).)

### 3.2 Opt-in selection in assembly

`assemble_runtime` already selects `NeuromodulatorAwareThoughtGateSignalBridge` under `semantic_memory_enabled` and `FirstVersionThoughtGateSignalBridge` otherwise. R48 keeps that selection; the semantic bridge now also needs the workspace stage name (a constant default, no new caller flag). Default/non-semantic assemblies keep `FirstVersionThoughtGateSignalBridge` and the constant `0.9`.

### 3.3 Default rollout

Default-off. The default assembly and any assembly without the semantic opt-in keep `global_activation_level = 0.9`. Only the semantic-memory assembly grounds it in `07`.

## 4. Data Structures

No new contract. `ThoughtGateSignalSnapshot`, `ThoughtGateResult`, `WorkspaceCompetitionStageResult` are unchanged. The change is internal to the composition gate-signal bridge plus a small activation helper.

## 5. Module Changes

1. `helios_v2/src/helios_v2/composition/bridges.py`: extend the semantic-assembly gate-signal bridge (`NeuromodulatorAwareThoughtGateSignalBridge`) to additionally source `global_activation_level` from the `07` `WorkspaceCompetitionStageResult` (max retained `workspace_score_hint`, `0.0` if none); add the `_workspace_activation` helper; preserve the R37 arousal sourcing and the existing hard-fail semantics; add a `workspace_stage_name` field defaulting to the canonical name. Update the class docstring.
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: no change required if the bridge default `workspace_stage_name` is the canonical name; otherwise pass it explicitly. No stage-order change.

## 6. Migration Plan

1. The change is additive and confined to the semantic-assembly gate-signal bridge. The default `FirstVersionThoughtGateSignalBridge` path is unchanged and remains the default.
2. No contract change to `ThoughtGateSignalSnapshot`/`ThoughtGateResult`, so the `09` gate path consumes the snapshot exactly as before — only the `global_activation_level` value changes when the opt-in is on.
3. No stage-order change; `07` already runs before `09`.
4. The semantic-memory assembly automatically gains real activation (same `semantic_memory_enabled` trigger as R37/R46), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. Missing or wrong-typed `07` workspace result at `09` time: hard fail (the existing `RuntimeStageExecutionError`), mirroring the R37 neuromodulator-result handling. No silent fallback to the constant.
2. Empty retained working state: defined `0.0` activation (the workspace did not ignite this tick), not a failure.
3. A candidate with `workspace_score_hint = None`: treated as `0.0` in the max (a defined floor).
4. The activation is clamped into `[0,1]` and rounded for determinism, satisfying the snapshot's `_validate_unit_interval`.
5. Composition glue only: it forwards a raw activation fact; the `09` gate weight and decision are unchanged. The R37 arousal coupling is preserved.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The real activation travels through the existing `ThoughtGateSignalSnapshot.global_activation_level` and surfaces in the existing `ThoughtGateResult.contributing_signals["global_activation_level"]`. No emission is added.

## 9. Validation Strategy

Network-free, deterministic.

1. `test_runtime_composition.py` (extend):
   - semantic-memory assembly: the `09` gate result's `contributing_signals["global_activation_level"]` equals the max retained `workspace_score_hint` from the same tick's `07` working state (read both stage results from the tick), and is not the constant `0.9`.
   - differing workspace strength across ticks → differing `global_activation_level` at `09` (the felt-state momentum from R44 already varies the `07` score across ticks, as observed in R46).
   - default assembly: `global_activation_level` stays `0.9` at `09` (constant bridge); existing tests unmodified.
   - the R37 `neuromodulatory_arousal` coupling still appears in `contributing_signals` on the semantic assembly (regression guard).
2. `test_runtime_stage_chain.py` (adjust if it asserts the gate-signal snapshot constants under a semantic-style wiring; the default-wired chain test keeps `0.9`).
3. A focused unit test for `_workspace_activation` (empty retained → 0.0; max of retained scores; None → 0.0 floor) may live in the composition test module.
4. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_composition.py -q
```
