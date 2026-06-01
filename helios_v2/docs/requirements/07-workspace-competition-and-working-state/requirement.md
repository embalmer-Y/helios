# Requirement 07 - Workspace competition and working state

## 1. Background and Problem

After memory affect and replay publishes candidate memory items, Helios v2 still needs a dedicated owner that receives those candidates, maintains a short-lived working-state surface, and performs workspace competition without collapsing that role into memory, action arbitration, or final reportable consciousness.

Helios v2 explicitly requires a separate workspace owner because `06` intentionally stops at candidate publication. Without this owner, later modules would either pull replay candidates directly and invent private competition logic, or memory owner would grow into a mixed memory-workspace controller.

## 2. Goal

Create a workspace competition and working-state owner that consumes `MemoryReplayCandidate` plus `InteroceptiveFeelingState`, maintains an immutable short-lived working-state snapshot, produces a workspace candidate set for later conscious/reportable layers, and exposes documented API and ops contracts without hardcoded heuristics, fallback behavior, or direct action-selection ownership.

## 3. Functional Requirements

### 3.1 Workspace-owner boundary
1. The workspace competition and working-state layer must be the sole owner of workspace candidate competition and short-lived working-state snapshots in this slice.
2. The owner must remain separate from memory replay construction, final reportable conscious-content commitment, deliberative planning, and action gating.
3. The owner must not reinterpret itself as the owner of final consciousness output or motor arbitration in this slice.

### 3.2 Upstream input boundary
1. The workspace layer must accept `MemoryReplayCandidate` as a required upstream input contract.
2. The workspace layer must accept `InteroceptiveFeelingState` as a required upstream input contract.
3. The workspace layer must not require `NeuromodulatorState` as a direct public input in this first version.
4. The workspace layer must not accept non-memory candidate sources in this first version.
5. The owner must expose a public API for workspace competition and working-state publication.

### 3.3 Workspace candidate output granularity
1. The first public output of this slice must be a workspace candidate set rather than a single conscious item.
2. The owner may rank or annotate candidates inside the set, but it must not publish a final top-1 conscious item in this slice.
3. The owner must preserve enough provenance to trace each workspace candidate back to the source memory replay candidate and source feeling state.

### 3.4 Working-state ownership
1. The workspace layer must own a short-lived working-state snapshot in this first version.
2. The working-state snapshot must be distinct from long-term memory storage and from later reportable-consciousness outputs.
3. The working-state snapshot must contain only the workspace owner's short-lived competitive state and publication metadata in this slice.

### 3.5 Forced-consolidation handling
1. If an upstream memory replay candidate is marked with `forced_consolidation`, the workspace owner must guarantee inclusion of that candidate in the workspace candidate set.
2. Forced consolidation must not guarantee selection as a final conscious item in this slice.
3. Forced consolidation handling must remain a workspace competition input rule, not a final reportable-content rule.

### 3.6 Candidate-source restrictions
1. The first version of the workspace owner must only process memory-derived candidates.
2. The owner must not accept feeling-derived, appraisal-derived, or arbitrary external candidate sources in this slice.
3. Support for multi-source workspace competition must remain a later requirement rather than an implicit extension of this slice.

### 3.7 Public API and ops exposure
1. The workspace layer must expose documented public API contracts for candidate competition, working-state update, and workspace-state publication.
2. The owner must define an op for workspace competition requests.
3. The owner must define an op for working-state publication.
4. The owner must define an op for workspace candidate-set publication.
5. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.8 Learned or runtime-provided workspace semantics
1. The owner must not hardcode permanent competition-weight formulas, routing branches, or threshold heuristics into the architecture contract.
2. Competition policy, candidate retention policy, and working-state update policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, baseline empty working-state defaults, and explicit owner-controlled working-state bootstrap metadata.
4. Dynamic competition and retention semantics must remain learning-driven rather than permanently fixed.

### 3.9 No fallback behavior
1. The workspace layer must not synthesize fallback workspace candidates when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic competition path when the configured competition capability is unavailable.
3. The owner must fail explicitly when required input invariants or required workspace capabilities are missing.

## 4. Non-Functional Requirements

1. Working-state and workspace-candidate contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured workspace policy.
3. The owner boundary must remain separate from memory, final consciousness/reporting, deliberation, identity, and inhibitory-gating owners.
4. Published state must preserve enough provenance to support later diagnostics and evaluation of candidate competition.

## 5. Code Behavior Constraints

1. Workspace competition code must not import action-routing, identity-governance, or final-report owners.
2. Workspace competition code must expose only documented APIs and ops contracts across module boundaries.
3. Workspace competition code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Only legal bounds, empty working-state defaults, and explicit working-state bootstrap metadata may be initialized as priors; dynamic competition semantics must not be frozen into architecture defaults.
5. Final reportable conscious-item selection remains outside this owner.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/workspace/contracts.py`
2. `helios_v2/src/helios_v2/workspace/engine.py`
3. `helios_v2/src/helios_v2/workspace/__init__.py`
4. `helios_v2/tests/test_workspace_contracts.py`
5. `helios_v2/tests/test_workspace_engine.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from memory replay candidates plus feeling state into workspace competition and working-state update.
2. The package defines documented ops contracts for workspace competition requests, working-state publication, and workspace candidate-set publication.
3. The contract surface publishes a workspace candidate set and a short-lived working-state snapshot without claiming final conscious-item ownership.
4. The package encodes the confirmed first-version boundaries: memory-only candidate sources, no direct neuromodulator input, and forced consolidation guarantees inclusion in the candidate set but not top-1 finality.
5. No test or implementation path demonstrates fallback workspace-candidate synthesis or degraded heuristic substitution.
