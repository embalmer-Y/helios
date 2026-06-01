# Requirement 07 - Workspace competition and working state design

## 1. Design Overview

Workspace competition and working state is the sole owner of short-lived workspace competition and working-state publication immediately after memory affect and replay and before later reportable consciousness, deliberative planning, or action arbitration. It consumes memory replay candidates plus current feeling state, computes a workspace candidate set, and publishes an immutable short-lived working-state snapshot for downstream owners.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, forced-consolidation handling, memory-only candidate-source restriction, and explicit non-owned responsibilities before any permanent competition implementation is written.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, and memory affect/replay owners, but no formal owner that turns replay candidates into a short-lived competitive workspace state. Without this layer, either memory owner would absorb workspace responsibilities or later modules would compete over candidates with private incompatible logic.

The gap is a typed, documented, fail-fast owner for workspace competition and working-state publication.

The next gap after that contract layer is a concrete owner skeleton that can:

1. accept `MemoryReplayCandidate` values,
2. accept `InteroceptiveFeelingState`,
3. build a workspace-competition request op,
4. invoke an owner-controlled competition and retention path,
5. publish an immutable workspace candidate set,
6. publish an immutable working-state snapshot,
7. reject malformed input or unavailable required workspace capability explicitly.

## 3. Target Architecture

The initial workspace slice contains eight runtime concepts:

1. `WorkspaceCandidate`: immutable workspace-visible candidate derived from a memory replay candidate.
2. `WorkspaceCandidateSet`: immutable published candidate set for later consciousness/report layers.
3. `WorkingStateSnapshot`: immutable short-lived owner snapshot representing the current working state.
4. `WorkspaceCompetitionConfig`: owner configuration surface for learned competition and retention policy categories.
5. `RunWorkspaceCompetitionOp`: runtime-visible request op describing one workspace competition cycle.
6. `PublishWorkingStateOp`: runtime-visible publication op describing one working-state snapshot.
7. `PublishWorkspaceCandidateSetOp`: runtime-visible publication op describing one workspace candidate-set snapshot.
8. `WorkspaceCompetitionAPI`: public owner-facing API for competition and publication.

Implementation boundary confirmation:

1. Workspace owner owns only workspace candidate competition and short-lived working-state publication.
2. It does not own memory replay generation, final reportable conscious commitment, action arbitration, or identity writeback.
3. It may expose replaceable internal competition interfaces, but those interfaces remain private to the owner until promoted by a later requirement slice.
4. `MemoryReplayCandidate + InteroceptiveFeelingState -> WorkspaceCandidateSet / WorkingStateSnapshot` is the first required public owner-facing transformation in this slice.

Lifecycle:

1. Memory affect and replay publishes `MemoryReplayCandidate` values.
2. Interoceptive feeling layer publishes an `InteroceptiveFeelingState`.
3. Workspace owner validates candidate provenance and feeling-state invariants.
4. The owner builds a workspace-competition request op for orchestration visibility.
5. An owner-controlled competition path computes the next workspace candidate set and working-state snapshot.
6. The owner publishes one immutable `WorkspaceCandidateSet` and one immutable `WorkingStateSnapshot`.
7. Later reportable-consciousness or deliberative owners consume the workspace output without transferring final ownership back into this owner.

Confirmed design constraints for this slice:

1. Required upstream inputs are `MemoryReplayCandidate` and `InteroceptiveFeelingState`.
2. Direct `NeuromodulatorState` input is excluded from the first public boundary.
3. Candidate sources are restricted to memory-derived candidates in the first version.
4. The first public output is a workspace candidate set rather than a single conscious item.
5. The owner also owns a short-lived working-state snapshot in the first version.
6. Upstream `forced_consolidation` guarantees candidate-set inclusion, but not final top-1 conscious commitment.
7. Competition, ranking, and retention semantics remain learning-driven rather than permanently fixed.

## 4. Data Structures

### 4.1 WorkspaceCandidate
- `candidate_id: str`
- `source_memory_candidate_id: str`
- `source_feeling_state_id: str`
- `priority_hint: float | None`
- `forced_consolidation: bool`
- `workspace_score_hint: float | None`

### 4.2 WorkspaceCandidateSet
- `set_id: str`
- `source_feeling_state_id: str`
- `candidates: tuple[WorkspaceCandidate, ...]`
- `tick_id: int | None`

### 4.3 WorkingStateSnapshot
- `state_id: str`
- `source_candidate_set_id: str`
- `retained_candidate_ids: tuple[str, ...]`
- `tick_id: int | None`

### 4.4 WorkspaceCompetitionConfig
- `legal_min_score: float`
- `legal_max_score: float`
- `working_state_bootstrap_id: str`
- `mandatory_learned_parameters: tuple[...]`

### 4.5 RunWorkspaceCompetitionOp
- `op_name: str`
- `owner: str`
- `candidate_count: int`
- `feeling_state_id: str`

### 4.6 PublishWorkingStateOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `candidate_set_id: str`
- `retained_candidate_count: int`

### 4.7 PublishWorkspaceCandidateSetOp
- `op_name: str`
- `owner: str`
- `set_id: str`
- `candidate_count: int`
- `forced_candidate_count: int`

## 5. Module Changes

1. `workspace/contracts.py` defines owner declaration, typed workspace contracts, public API protocol, ops contracts, and workspace-owner error type.
2. `workspace/engine.py` will implement the first owner skeleton for competition and publication.
3. `workspace/__init__.py` will export the public workspace surface.
4. `tests/test_workspace_contracts.py` will validate contract immutability, provenance, working-state ownership, and forced-consolidation inclusion semantics.
5. `tests/test_workspace_engine.py` will validate owner-skeleton behavior and fail-fast input handling.

## 6. Confirmation Gates

This requirement package must not guess the following unresolved semantics:

1. the exact learned competition policy used to convert replay candidates into workspace score hints,
2. the exact retention policy for how many candidates remain in the working-state snapshot,
3. the later promotion rules from workspace candidate sets into reportable or globally broadcast consciousness outputs,
4. whether some candidate families receive family-specific competition treatment beyond the shared first-version interface,
5. the later multi-source competition semantics once non-memory candidate sources are allowed.

These remain explicit design gates that require user confirmation before implementation of the permanent workspace path.

## 7. Deferred First-Version Items

The following items are explicitly recognized but allowed to remain unimplemented in the first version of this slice:

1. direct production of a final top-1 conscious item,
2. multi-source candidate competition beyond memory-derived inputs,
3. direct neuromodulator input into the public workspace boundary,
4. full global-broadcast or reportable-consciousness semantics,
5. direct action-arbitration integration.

These items must remain visible as deferred scope rather than disappearing from the architecture record.

## 8. Cross-Slice Coordination Markers

The following follow-up coordination work is explicitly required by the confirmed first-version boundary decisions:

1. Conscious/report layer follow-up: a later owner must consume `WorkspaceCandidateSet` and decide if, when, and how a single reportable item is committed.
2. Multi-source workspace follow-up: a later requirement must define how non-memory candidate sources are admitted without breaking the first-version memory-only contract.
3. Identity follow-up remains outside this slice; any identity consequences of workspace outputs must continue through later dedicated owners.
4. These are required downstream coordination tasks created by the confirmed first-version boundary choices, not optional nice-to-have notes.

## 9. Migration Plan

This slice does not port Helios v1 working-memory or attention heuristics directly.

It defines the v2 workspace owner boundary first so later consciousness, deliberation, and report layers can attach to a stable competitive workspace contract.

## 10. Failure Modes and Constraints

1. Missing memory-candidate provenance must raise an explicit workspace-owner error.
2. Missing feeling-state provenance must raise an explicit workspace-owner error.
3. Published candidate-set or working-state values outside the allowed contract range must raise an explicit workspace-owner error.
4. Publication must not occur for malformed workspace candidate sets or working-state snapshots.
5. No fallback workspace-competition path is allowed.
6. Missing required competition capability must abort execution rather than substituting a simpler heuristic path.
7. Permanent weighted formulas, permanent routing branches, and permanent threshold heuristics are prohibited.
8. The owner skeleton must reject malformed input before invoking its internal competition path.

## 11. Observability and Logging

This initial slice keeps observability structural:

1. workspace candidates preserve source memory-candidate and source feeling provenance,
2. candidate-set and working-state publication ops summarize owner activity,
3. forced-consolidation inclusion remains visible without claiming final conscious commitment ownership,
4. error types define malformed contract conditions explicitly.

## 12. Validation Strategy

1. Unit test immutable workspace-candidate, candidate-set, and working-state contracts.
2. Unit test provenance preservation from memory replay candidates and feeling state into workspace outputs.
3. Unit test forced-consolidation inclusion in the workspace candidate set.
4. Unit test exclusion of non-memory candidate sources from the first public boundary.
5. Unit test request and publication op summary fields.
6. Unit test explicit failure for malformed memory-candidate input.
7. Unit test explicit failure for malformed feeling-state input.
8. Unit test explicit failure when required competition capability is unavailable.
