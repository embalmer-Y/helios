# Requirement 46 - Workspace competition de-shim (real attention bottleneck)

## 1. Background and Problem

With R45 the `06` memory owner is de-shimmed: replay candidates now carry a real `priority_hint` from an owner-owned salience gate over the real `05` feeling, and the consolidation-worthy set is genuine. The next mid-chain shim is the `07` workspace competition owner, the attention bottleneck that decides what working content is held for the conscious-content commit (`08`).

`07` is shimmed in composition in two independent ways:

1. **Competition assigns a constant score.** `FirstVersionWorkspaceCompetitionPath` promotes each replay candidate into a workspace candidate with a fixed `workspace_score_hint=0.95` for every candidate, ignoring the candidate's real `priority_hint` and the real `05` feeling. There is no competition — every candidate "wins" identically.

2. **Retention keeps everything.** `FirstVersionWorkingStateRetentionPath` retains *every* candidate id in the working state. There is no bottleneck — nothing is selected over anything else, so the "working state" is just the full candidate set echoed back.

In `brain.mmd`, the workspace/FPN is an attention bottleneck: a competition among candidates where only a bounded winning subset is held in the working state and made available to reportable consciousness. The `08` consciousness stage already builds conscious-content material from the workspace candidate set and references the working-state snapshot, so a real bottleneck at `07` is the difference between "everything is equally conscious" and "the most salient content is held in mind". The real inputs to make this non-trivial now exist (R45 real `priority_hint`; R38/R44 real `05` feeling), so this is the right next P3 de-shim.

The owner, its `WorkspaceCandidateSet`/`WorkingStateSnapshot` contracts, its provenance validation, and its tests are all real today; only the injected competition/retention values are shim.

## 2. Goal

When real workspace competition is enabled, the `07` owner scores each workspace candidate through an owner-owned competition function of the candidate's real `priority_hint` and the real `05` feeling salience (rather than a constant), and the working state retains only a bounded top-scoring subset as the attention bottleneck (rather than every candidate), so the most salient memory content is held in mind and surfaced to `08` while lower-salience content competes and loses; the `07` owner keeps sole ownership of the competition and retention policy, preserves every owner provenance and forced-consolidation invariant it already enforces, and the default and shim assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Owner-owned real competition scoring
1. The `07` owner must score each workspace candidate through a `07`-owned competition path, not a composition-injected constant. The score must be a bounded deterministic function of the candidate's real `priority_hint` (from `06`) and the real `05` feeling salience (for example arousal/tension), within the `[0,1]` `workspace_score_hint` contract range.
2. The competition path must remain owned by `helios_v2.workspace`. It must continue to include every replay candidate in the published candidate set (the existing owner invariant that forced-consolidation candidates are never dropped from the set is preserved), and must continue to preserve each candidate's `forced_consolidation` flag and feeling-state provenance verbatim.
3. Scoring must be deterministic given identical inputs and must not depend on wall-clock time.

### 3.2 Owner-owned attention bottleneck (bounded retention)
1. The `07` owner must select, through a `07`-owned retention path, a bounded top-scoring subset of the candidate set into the working state, rather than retaining every candidate. The retained subset is the attention bottleneck.
2. The retained-count bound must be an explicit bounded first-version constant declared under the owner config's existing learned-parameter categories (`working_state_update_policy` / `candidate_retention_policy`), so a later `P5` slice can learn it without changing the retention shape.
3. Retention must respect the existing owner invariant that the working state may retain only candidate ids published in the same candidate set, and selection among equal scores must be deterministic (explicit tie-break).
4. The retention bottleneck must never produce an empty working state when the candidate set is non-empty: at least the single top-scoring candidate is retained, so a real bottleneck narrows attention without erasing it.

### 3.3 Real downstream effect
1. The competition score and the bounded retention must flow through the existing `WorkspaceCandidateSet` / `WorkingStateSnapshot` contracts unchanged, so `08` consciousness consumes them through the existing boundary with no contract change.
2. The change must be observable: given a candidate set with differing real `priority_hint` values, the working state must retain the higher-salience candidate(s) and exclude the lower-salience one(s) once the candidate count exceeds the retention bound; the difference must be attributable to the real competition score, not to a constant.

### 3.4 Opt-in rollout and fail-fast
1. Real workspace competition must activate on the existing semantic-memory opt-in (durable store and embedding gateway both present), consistent with R45 — because the real `priority_hint` it competes over only exists once `06` is de-shimmed under that same opt-in. The default assembly and any assembly without the semantic opt-in must keep the constant first-version competition/retention paths and behave exactly as today.
2. The owner must continue to fail fast on its existing invariants (malformed feeling state, dropped forced candidate, retained-but-unpublished candidate id, provenance mismatch). No new degraded or fallback path is introduced.

## 4. Non-Functional Requirements

1. Performance: competition is one bounded pass over the candidate set plus one bounded sort/selection per tick; it must not change the runtime stage execution structure.
2. Reliability and fault tolerance: for identical replay candidates and identical feeling state, the candidate scores and the retained subset must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Competition facts travel only through the existing workspace contracts.
4. Compatibility and migration: the real competition/retention paths and their wiring are additive and opt-in. The default assembly and the recency-only/non-semantic assemblies keep their current `07` behavior; existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The `07` owner must stay the sole owner of competition and retention policy. The competition score and the retention bound live in `helios_v2.workspace`; composition injects the owner-owned paths but holds no scoring or bottleneck policy.
2. The competition path must not drop or reorder owner invariants: every replay candidate stays in the candidate set, forced-consolidation flags and feeling provenance are preserved, and no duplicate `source_memory_candidate_id` is published.
3. The retention bottleneck lives in the working-state retention path only; it must not mutate the candidate set (the full set still reaches `08` as material; the working state is the bounded held subset).
4. No degraded or fallback path: the owner keeps failing fast on its existing invariants; the bounded retention never empties a non-empty set.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/workspace/engine.py` (a `07`-owned real competition path and bounded retention path implementing the existing `WorkspaceCompetitionPath` / `WorkingStateRetentionPath` protocols)
2. `helios_v2/src/helios_v2/workspace/__init__.py` (export the new owner-owned paths)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in selection of the real competition/retention paths under the semantic-memory opt-in; constant paths otherwise)
4. `helios_v2/tests/test_workspace_engine.py` (extend: real scoring from priority_hint + feeling; bounded retention selects top-K; never empties; deterministic; invariants preserved)
5. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly retains a bounded high-salience subset; lower-salience candidate excluded once over bound; default unchanged)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
9. `helios_v2/docs/OWNER_GUIDE.md`
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The `07` owner scores each workspace candidate through an owner-owned competition path that is a bounded deterministic function of the real `priority_hint` and the real `05` feeling salience, within `[0,1]`; it is not a constant.
2. The `07` owner retains only a bounded top-scoring subset into the working state (the attention bottleneck), with the bound declared under the existing learned-parameter categories; selection is deterministic with an explicit tie-break.
3. Given differing real `priority_hint` values and a candidate count above the retention bound, the working state retains the higher-salience candidate(s) and excludes the lower-salience one(s); the difference is attributable to the real score, not a constant. A non-empty candidate set never yields an empty working state.
4. The competition score and bounded retention flow through the unchanged `WorkspaceCandidateSet` / `WorkingStateSnapshot` contracts to `08`; no downstream contract changes.
5. All existing `07` owner invariants still hold and still fail fast (forced candidate never dropped from the set, retained ids are a subset of the published set, provenance preserved).
6. Real competition activates only on the semantic-memory opt-in; the default assembly and non-semantic assemblies keep the constant `07` behavior, and their existing tests pass unmodified.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R46 de-shims `07` competition and retention only. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. `P5` learning of the competition weights and the retention bound from real outcome feedback, replacing the first-version constants without changing the competition/retention shape.
2. Multi-source competition (candidates from sources beyond `06` replay) once those sources are real, with the same owner-owned policy.
3. A real `08` commitment path consuming the bounded working state more sharply (top-1 reportable content), the next mid-chain de-shim after `07`.
4. Recency/affect-weighted or attention-learned scoring once richer upstream signals land.

None of these may be smuggled into this slice. R46 changes only the `07` competition score and the working-state retention bound, introduces no contract change, and adds no default-on behavior.
