# Requirement 06 - Memory affect and replay

## 1. Background and Problem

After interoceptive feeling state is published, Helios v2 still needs a dedicated owner that records affect-linked memory traces and decides which traces become replay candidates for later conscious workspace use. Without this owner, downstream modules would either attach private affect tags to memories, replay memories with inconsistent criteria, or collapse memory storage and workspace selection into the same contract.

Helios v2 explicitly requires a separate memory owner that handles affect-tagged memory formation and replay-candidate publication. This owner should correspond to memory capture and replay preparation, not to conscious selection, action routing, or identity-governance ownership.

## 2. Goal

Create a memory affect and replay owner that consumes `InteroceptiveFeelingState` plus upstream provenance needed for memory binding, produces immutable memory snapshots with affect tags and replay metadata, and exposes documented API and ops contracts without hardcoded heuristics, fallback behavior, or premature workspace-selection ownership.

## 3. Functional Requirements

### 3.1 Memory-owner boundary
1. The memory affect and replay layer must be the sole owner of affect-linked memory write, replay-candidate construction, and replay-candidate publication in this slice.
2. The owner must remain separate from feeling construction, conscious workspace competition, deliberative planning, identity governance, and action gating.
3. The owner must not reinterpret itself as the owner of final conscious content selection or narrative self-update in this slice.

### 3.2 Upstream input boundary
1. The memory affect and replay layer must accept `InteroceptiveFeelingState` as a required upstream input contract.
2. The owner may consume additional upstream provenance required for memory binding, but those inputs must remain explicit in the public contract surface rather than implicit module reach-through.
3. If `prediction mismatch or surprise` is used as a replay trigger, it must enter the memory owner as an explicit minimal evidence contract rather than as an implicit read-through into upstream modules.
3. The owner must not require direct ownership of conscious workspace state in this slice.
4. The owner must expose a public API for recording affect-linked memory state and surfacing replay candidates.

### 3.3 Memory-state families in scope
1. The public contract surface in this slice must represent memory items as candidate members of at least `episodic`, `semantic`, or `autobiographical` families.
2. The first implementation version may keep these families inside a single owner state as family-tagged items rather than requiring separate storage partitions.
2. The slice may preserve metadata relevant to later working-memory or consolidation flows, but it must not claim final ownership of conscious workspace contents.
3. The slice must preserve enough provenance to trace each memory item back to the source feeling state and any explicit upstream binding context used during memory formation.

### 3.4 Affect-tag schema
1. The memory owner must reuse `InteroceptiveFeelingVector` as the primary affect-tag representation in this slice.
2. Each affect-tagged memory snapshot must preserve provenance links to the source feeling state and any upstream state identifiers explicitly used by the owner.
3. The public contract must not require a second independent affect-language schema in this slice.

### 3.5 Replay-trigger scope for the first requirement version
1. The first requirement version must include replay-trigger support for `high affect intensity`.
2. The first requirement version must include replay-trigger support for `unresolved tension or discomfort`.
3. The first requirement version must include replay-trigger support for `prediction mismatch or surprise`, provided the mismatch signal is supplied through an explicit upstream contract.
4. Replay-trigger evaluation must remain inside the memory owner boundary and must not be delegated to workspace or action modules.

### 3.6 Forced consolidation rule
1. The owner must support an explicit forced-consolidation path for events that are both `high anomaly` and `high affect`.
2. The owner must not force consolidation for every anomaly by default.
3. Forced consolidation semantics must be represented as explicit owner outputs or metadata, not as hidden side effects.

### 3.7 Public API and ops exposure
1. The memory affect and replay layer must expose documented public API contracts for memory recording, replay-candidate surfacing, and memory-state publication.
2. The owner must define an op for memory-record requests.
3. The owner must define an op for replay-candidate publication.
4. The owner must define an op for memory-state publication.
5. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.8 Output boundary to later workspace owners
1. The owner must publish candidate memory items, including their memory-family type and affect tags, for later workspace competition.
2. The first public output granularity must be candidate memory items rather than a single merged memory packet.
3. The owner must not collapse multiple candidates into a single final conscious-content decision in this slice.
4. The owner may annotate replay candidacy and consolidation urgency, but it must not own final reportable-content choice.
5. The owner must not nominate or force-promote items into conscious workspace in this slice; later workspace owners remain responsible for promotion and competition.

### 3.9 Learned or runtime-provided memory/replay semantics
1. The owner must not hardcode permanent replay-weight formulas, routing branches, or threshold heuristics into the architecture contract.
2. Replay scoring, consolidation policy, and memory-family write policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, baseline empty-state defaults, and explicit owner-controlled storage initialization state.
4. Dynamic replay and consolidation semantics must remain learning-driven rather than permanently fixed.

### 3.10 No fallback behavior
1. The memory affect and replay layer must not synthesize fallback replay candidates when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic replay path when the configured replay or consolidation capability is unavailable.
3. The owner must fail explicitly when required input invariants or required memory/replay capabilities are missing.

## 4. Non-Functional Requirements

1. Memory-state and replay-candidate contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured memory and replay policy.
3. The owner boundary must remain separate from feeling, workspace, deliberation, identity, and inhibitory-gating owners.
4. Published state must preserve enough provenance to support later diagnostics, evaluation, and traceability of replay decisions.

## 5. Code Behavior Constraints

1. Memory affect and replay code must not import workspace, action-routing, or identity-governance owners.
2. Memory affect and replay code must expose only documented APIs and ops contracts across module boundaries.
3. Memory affect and replay code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Only legal bounds, empty-state defaults, and explicit owner-controlled storage initialization state may be initialized as priors; dynamic replay and consolidation semantics must not be frozen into architecture defaults.
5. Final conscious-content selection remains outside this owner.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/memory/contracts.py`
2. `helios_v2/src/helios_v2/memory/engine.py`
3. `helios_v2/src/helios_v2/memory/__init__.py`
4. `helios_v2/tests/test_memory_contracts.py`
5. `helios_v2/tests/test_memory_engine.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from feeling state into affect-linked memory recording.
2. The package defines documented ops contracts for memory-record requests, replay-candidate publication, and memory-state publication.
3. The contract surface reuses `InteroceptiveFeelingVector` as the affect-tag representation and preserves provenance links to the source feeling state.
4. The package encodes the confirmed first-version replay triggers: `high affect intensity`, `unresolved tension or discomfort`, and `prediction mismatch or surprise` through explicit upstream contract input.
5. The package encodes the confirmed forced-consolidation rule for `high anomaly + high affect` without forcing all anomalies to consolidate.
6. The package publishes candidate memory items for later workspace owners without claiming final conscious-content selection.
7. No test or implementation path demonstrates fallback replay synthesis or degraded heuristic substitution.
8. The package explicitly marks later workspace-promotion and identity-writeback integration as required follow-up coordination rather than silently omitting them.
