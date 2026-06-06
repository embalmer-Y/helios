# Requirement 46 - Workspace competition de-shim (design)

## 1. Design Overview

R46 makes the `07` workspace owner a real attention bottleneck under the semantic-memory assembly, without changing any contract and without `07` importing another owner. It is the next P3 mid-chain de-shim after `06` (R45).

Two additive, opt-in pieces, both owned by `helios_v2.workspace`:

1. A `WorkspaceCompetitionPath` (`SalienceWeightedWorkspaceCompetitionPath`) that scores each workspace candidate as a bounded function of the candidate's real `priority_hint` (from `06`'s R45 salience gate) and the real `05` feeling salience, replacing the constant `workspace_score_hint=0.95`. Every replay candidate is still promoted into the candidate set (preserving the owner invariant), only the score becomes real.
2. A `WorkingStateRetentionPath` (`BoundedAttentionRetentionPath`) that selects a bounded top-K subset of the candidate set into the working state (the attention bottleneck), replacing the "retain everything" shim. K is an explicit owner-config-categorized constant; selection is deterministic with an explicit tie-break and never empties a non-empty set.

Composition selects these owner-owned paths under the existing semantic-memory opt-in (the same opt-in that makes `06` real), because the real `priority_hint` they compete over only exists once `06` is de-shimmed. Default and non-semantic assemblies keep the constant paths.

Everything stays within the existing `WorkspaceCandidateSet` / `WorkingStateSnapshot` contracts. `08` consciousness consumes them unchanged; only which candidates win and which are held in the working state changes.

## 2. Current State and Gap

Current state (verified in code):

1. `WorkspaceCompetitionEngine` calls injected `WorkspaceCompetitionPath` + `WorkingStateRetentionPath`. In composition those are `FirstVersionWorkspaceCompetitionPath` (constant `workspace_score_hint=0.95` per candidate; otherwise faithfully preserves provenance + forced flag) and `FirstVersionWorkingStateRetentionPath` (retains every candidate id).
2. With R45 `MemoryReplayCandidate.priority_hint` is a real salience-gate output and `05` feeling is real (R38/R44), so `07` now has real inputs to compete over.
3. The `08` `WorkspaceConsciousContentMaterialBridge` builds material from `candidate_set.candidates` and references `working_state.state_id`; the engine's `_validate_working_state` already enforces that retained ids are a subset of the published candidate set, and `_validate_workspace_candidates` enforces that forced-consolidation candidates remain in the set.

Gap: competition does not compete (constant score) and retention does not bottleneck (keeps all). The substrate to make both real exists and is unused.

## 3. Target Architecture

### 3.1 Owner-owned real competition (in `helios_v2.workspace`)

`07` stays the competition owner. The competition path scores each candidate from real inputs:

```
@dataclass
class SalienceWeightedWorkspaceCompetitionPath(WorkspaceCompetitionPath):
    priority_weight: float = 0.6          # under competition_policy (P5-learnable)
    feeling_weight: float = 0.4
    def build_candidate_set(self, replay_candidates, feeling_state, config, tick_id):
        feeling_salience = clamp(0.5*feeling.arousal + 0.3*feeling.tension + 0.2*feeling.pain_like, 0, 1)
        candidates = []
        for index, rc in enumerate(replay_candidates):
            priority = rc.priority_hint if rc.priority_hint is not None else 0.0
            score = clamp(self.priority_weight*priority + self.feeling_weight*feeling_salience, 0, 1)
            candidates.append(WorkspaceCandidate(
                candidate_id=f"workspace-candidate:runtime:{tick_id}:{index}",
                source_memory_candidate_id=rc.candidate_id,
                source_feeling_state_id=feeling_state.state_id,
                priority_hint=rc.priority_hint,
                forced_consolidation=rc.forced_consolidation,   # preserved verbatim
                workspace_score_hint=score,                      # REAL, was constant 0.95
            ))
        return WorkspaceCandidateSet(set_id=f"workspace-set:runtime:{tick_id}", source_feeling_state_id=feeling_state.state_id, candidates=tuple(candidates), tick_id=tick_id)
```

Every replay candidate is still in the set (so the engine's forced-candidate invariant holds); only `workspace_score_hint` becomes a real bounded function of the real `priority_hint` and the real felt salience. The feeling-salience reading reuses the same arousal/tension/pain reading family the `06` gate uses (consistent affect interpretation), but it is an owner-private competition input here, not a shared contract.

### 3.2 Owner-owned attention bottleneck (in `helios_v2.workspace`)

The retention path selects a bounded top-K winning subset:

```
@dataclass
class BoundedAttentionRetentionPath(WorkingStateRetentionPath):
    max_retained: int = 3                  # under working_state_update_policy (P5-learnable)
    def retain_working_state(self, candidate_set, config, tick_id):
        ranked = sorted(candidate_set.candidates,
                        key=lambda c: (-(c.workspace_score_hint or 0.0), c.candidate_id))  # score desc, id tie-break
        retained = ranked[: max(1, self.max_retained)]                 # never empty for a non-empty set
        return WorkingStateSnapshot(
            state_id=f"working-state:runtime:{tick_id}",
            source_candidate_set_id=candidate_set.set_id,
            retained_candidate_ids=tuple(c.candidate_id for c in retained),
            tick_id=tick_id,
        )
```

This is the bottleneck: when the candidate count exceeds `max_retained`, lower-scoring candidates are excluded from the working state (but remain in the candidate set, which still reaches `08` as material). `max(1, ...)` guarantees a non-empty set never yields an empty working state. The retained ids are a subset of the published set, satisfying `_validate_working_state`.

Design note (forced candidates): the owner invariant `_validate_workspace_candidates` requires forced candidates to stay in the *candidate set*, not in the *working state*. So bounded retention may legitimately exclude a forced candidate from the held working state if it loses the salience competition — the forced flag governs set membership (it is consolidated/persisted by `06`), while the working state is the bounded attention focus. This keeps the bottleneck real without violating any invariant. (Documented so the distinction "consolidated ≠ held in attention" is explicit.)

### 3.3 Opt-in selection in assembly

`assemble_runtime` selects the workspace paths on the existing `semantic_memory_enabled` flag (store + embedding both present), the same trigger as R45:

1. semantic-memory assembly → `WorkspaceCompetitionEngine(competition_path=SalienceWeightedWorkspaceCompetitionPath(), retention_path=BoundedAttentionRetentionPath())`.
2. default / recency-only / non-semantic → the existing `FirstVersionWorkspaceCompetitionPath` + `FirstVersionWorkingStateRetentionPath` (unchanged behavior).

No new public assembly flag. The real `priority_hint` competition only matters once `06` is real, which is the same opt-in.

### 3.4 Default rollout

Default-off. The default assembly and any assembly without the semantic opt-in keep the constant `workspace_score_hint=0.95` and retain-everything behavior. Only the semantic-memory assembly gains real competition and the bounded bottleneck.

## 4. Data Structures

No new cross-owner data contract. `WorkspaceCandidate`, `WorkspaceCandidateSet`, `WorkingStateSnapshot` are unchanged. New types:

1. `SalienceWeightedWorkspaceCompetitionPath` (in `helios_v2.workspace`) — implements `WorkspaceCompetitionPath`; owns the real competition score (priority + feeling salience), explicit bounded weights under `competition_policy`.
2. `BoundedAttentionRetentionPath` (in `helios_v2.workspace`) — implements `WorkingStateRetentionPath`; owns the bounded top-K attention bottleneck, `max_retained` under `working_state_update_policy`, deterministic tie-break, never-empty guarantee.

## 5. Module Changes

1. `helios_v2/src/helios_v2/workspace/engine.py`: add `SalienceWeightedWorkspaceCompetitionPath` and `BoundedAttentionRetentionPath` (the competition score and the retention bound live here).
2. `helios_v2/src/helios_v2/workspace/__init__.py`: export both.
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: select the owner-owned paths under `semantic_memory_enabled`; keep `FirstVersion*` otherwise. Import the two new paths from `helios_v2.workspace` (not from bridges — they are owner-owned, not composition glue).

## 6. Migration Plan

1. All new code is additive and owner-owned. The default `FirstVersion*` paths are unchanged and remain the default.
2. No contract changes to `WorkspaceCandidateSet`/`WorkingStateSnapshot`, so `08` consumes workspace output exactly as before — only the score and the retained subset change when the opt-in is on.
3. No stage-order change; `07` is the same stage with different injected collaborators.
4. The semantic-memory assembly automatically gains real competition (same `semantic_memory_enabled` trigger as R45), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. A candidate with `priority_hint = None`: treated as priority `0.0` in scoring (a defined floor), still scored by the feeling term; not a failure.
2. A non-empty candidate set: bounded retention always keeps at least the top-1 (`max(1, max_retained)`), so the working state is never empty for a non-empty set.
3. The owner's existing invariants are unchanged and still fail fast: forced candidate dropped from the *set* → error; retained id not in the published set → error; provenance mismatch → error.
4. The competition score and `priority_hint` are clamped into `[0,1]` (the `WorkspaceCandidate` contract range); scoring is rounded for determinism.
5. `07` imports no other owner; composition injects the owner-owned paths. The bottleneck lives in retention only and never mutates the candidate set.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. Competition facts travel only through the `WorkspaceCandidateSet.workspace_score_hint` and `WorkingStateSnapshot.retained_candidate_ids`. No emission is added in `07` or composition.

## 9. Validation Strategy

Network-free, deterministic.

1. `test_workspace_engine.py` (extend):
   - `SalienceWeightedWorkspaceCompetitionPath`: a candidate with a higher real `priority_hint` gets a higher `workspace_score_hint` than a lower one under the same feeling; score in `[0,1]`; `forced_consolidation` and feeling provenance preserved; every replay candidate still in the set.
   - feeling sensitivity: raising the feeling salience raises scores monotonically (same candidates).
   - `BoundedAttentionRetentionPath`: with more candidates than `max_retained`, only the top-K by score are retained; a non-empty set never yields an empty working state; deterministic tie-break by candidate id; retained ids ⊆ candidate set.
   - integration through `WorkspaceCompetitionEngine.compete`: real paths pass all existing owner invariants (forced candidate stays in the set even if not retained in the working state).
   - determinism: identical inputs → identical scores + retained set.
2. `test_runtime_composition.py` (extend):
   - semantic-memory assembly: over several ticks the working state retains a bounded subset (size ≤ `max_retained`) while the candidate set may be larger; `workspace_score_hint` values are not the constant `0.95`.
   - a constructed candidate set with differing priorities (via the real `06` gate across ticks) shows the higher-salience candidate retained; assert the retained set is bounded and score-ordered.
   - default assembly keeps `workspace_score_hint == 0.95` and retains all candidates (constant path); existing tests unmodified.
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_workspace_engine.py -q
```
