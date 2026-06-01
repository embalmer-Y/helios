# Requirement 06 - Memory affect and replay design

## 1. Design Overview

Memory affect and replay is the sole owner of affect-linked memory write, replay-candidate construction, and replay-candidate publication immediately after interoceptive feeling and before later conscious workspace competition, autobiographical narration, or identity writeback. It consumes feeling state plus explicit upstream binding signals, constructs immutable memory snapshots with affect tags, and publishes replay candidates for downstream owners.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, confirmed replay triggers, forced-consolidation rule, and explicit non-owned responsibilities before any permanent storage or replay implementation is written.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, and interoceptive feeling owners, but no formal owner that binds affect into memory traces and prepares replay candidates for later workspace use. Without this layer, downstream owners would either attach their own affect semantics to memory items or pull feeling state directly, which would destroy traceable memory ownership.

The gap is a typed, documented, fail-fast owner for affect-linked memory recording and replay-candidate publication.

The next gap after that contract layer is a concrete owner skeleton that can:

1. accept `InteroceptiveFeelingState`,
2. accept explicit upstream binding context required for memory formation,
3. build a memory-record request op,
4. invoke an owner-controlled memory write and replay-selection path,
5. publish immutable memory-state snapshots,
6. publish candidate memory items for later workspace competition,
7. reject malformed input or unavailable required memory/replay capability explicitly.

## 3. Target Architecture

The initial memory affect and replay slice contains seven runtime concepts:

1. `MemoryFamily`: typed classification for `episodic`, `semantic`, and `autobiographical` candidate families.
2. `PredictionMismatchEvidence`: explicit minimal upstream evidence contract for `prediction mismatch or surprise` replay triggers.
3. `MemoryContentPacket`: minimal content payload contract carried by each memory item.
4. `MemoryBindingContext`: explicit upstream binding-context contract used during memory formation.
5. `AffectTaggedMemoryItem`: immutable memory item carrying affect tags, minimal content, and provenance.
6. `MemoryReplayCandidate`: immutable replay candidate carrying replay reason and urgency metadata.
7. `MemoryFormationState`: immutable owner snapshot with cycle identity and storage-facing provenance.
8. `RecordMemoryOp`: runtime-visible request op describing one affect-linked memory write request.
9. `PublishReplayCandidatesOp`: runtime-visible publication op describing one replay-candidate batch.
10. `PublishMemoryFormationStateOp`: runtime-visible publication op describing one owner-state snapshot.
11. `MemoryAffectReplayAPI`: public owner-facing API for record and publication.

Implementation boundary confirmation:

1. Memory affect and replay owns only affect-linked memory formation, replay-candidate construction, and replay-candidate publication.
2. It does not own feeling construction, final conscious-content selection, planning, identity writeback, or inhibitory gate execution.
3. It may expose replaceable internal memory/replay interfaces, but those interfaces remain private to the owner until promoted by a later requirement slice.
4. `InteroceptiveFeelingState -> AffectTaggedMemoryItem / MemoryReplayCandidate` is the first required public owner-facing transformation in this slice.

Lifecycle:

1. Interoceptive feeling layer publishes an `InteroceptiveFeelingState`.
2. Memory affect and replay validates feeling provenance and any explicit binding-context invariants.
3. The owner builds a memory-record request op for orchestration visibility.
4. An owner-controlled memory/replay path forms or updates immutable memory items.
5. The owner evaluates first-version replay triggers.
6. The owner publishes one memory-state snapshot and one replay-candidate publication op.
7. Later workspace owners consume candidate memory items without transferring final selection ownership back into memory.

Confirmed design constraints for this slice:

1. Required upstream input is `InteroceptiveFeelingState`.
2. `prediction mismatch or surprise` enters this owner through an explicit minimal `PredictionMismatchEvidence` contract rather than through implicit reach-through into upstream owners.
3. Affect tags reuse `InteroceptiveFeelingVector` rather than introducing a second affect language.
4. Memory families remain in one owner state as family-tagged items in the first implementation version; separate storage partitioning is deferred.
5. Each memory item carries a minimal `MemoryContentPacket` rather than a full event snapshot.
6. The first public output granularity is candidate memory items classified as `episodic`, `semantic`, or `autobiographical`.
7. The first confirmed replay triggers are `high affect intensity`, `unresolved tension or discomfort`, and `prediction mismatch or surprise` when mismatch is supplied by an explicit upstream contract.
8. Replay priority remains an optional bounded continuous `priority_hint` rather than an ordinal rank in the first version.
9. Forced consolidation applies only to `high anomaly + high affect` rather than all anomalies.
10. Final conscious-content selection remains outside this owner.
11. Replay scoring and write policy remain learning-driven rather than permanently fixed.

## 4. Data Structures

### 4.1 MemoryFamily
- `episodic`
- `semantic`
- `autobiographical`

### 4.2 AffectTaggedMemoryItem
- `memory_id: str`
- `family: MemoryFamily`
- `source_feeling_state_id: str`
- `affect_tag: InteroceptiveFeelingVector`
- `content: MemoryContentPacket`
- `binding_context_id: str | None`
- `tick_id: int | None`

### 4.3 MemoryReplayCandidate
- `candidate_id: str`
- `memory_id: str`
- `family: MemoryFamily`
- `replay_reasons: tuple[str, ...]`
- `forced_consolidation: bool`
- `priority_hint: float | None`

### 4.4 MemoryFormationState
- `state_id: str`
- `source_feeling_state_id: str`
- `memory_items: tuple[AffectTaggedMemoryItem, ...]`
- `replay_candidates: tuple[MemoryReplayCandidate, ...]`
- `tick_id: int | None`

### 4.5 RecordMemoryOp
- `op_name: str`
- `owner: str`
- `feeling_state_id: str`
- `binding_context_id: str | None`

### 4.6 PublishReplayCandidatesOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `candidate_count: int`
- `families: tuple[str, ...]`

### 4.7 PublishMemoryFormationStateOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `source_feeling_state_id: str`
- `memory_count: int`
- `candidate_count: int`

## 5. Module Changes

1. `memory/contracts.py` defines owner declaration, typed memory/replay contracts, public API protocol, ops contracts, and memory-owner error type.
2. `memory/engine.py` will implement the first owner skeleton for memory record and replay-candidate publication.
3. `memory/__init__.py` will export the public memory surface.
4. `tests/test_memory_contracts.py` will validate contract immutability, provenance, and affect-tag reuse.
5. `tests/test_memory_engine.py` will validate owner-skeleton behavior and fail-fast input handling.

## 6. Confirmation Gates

This requirement package must not guess the following unresolved semantics:

1. the exact explicit upstream contract shape that supplies `prediction mismatch or surprise` into the memory owner before that signal receives its own requirement slice,
2. the exact storage partitioning and retrieval mechanics across episodic, semantic, and autobiographical families beyond the confirmed first-version single-state family-tagged representation,
3. the exact semantics of bounded continuous `priority_hint` beyond its safe public range,
4. the exact content payload shape attached to a memory item beyond the confirmed minimal content packet,
5. the later promotion rules from replay candidates into conscious workspace contents,
6. the later writeback rules from memory outputs into identity-governance owners.

These remain explicit design gates that require user confirmation before implementation of the permanent memory and replay path.

## 7. Deferred First-Version Items

The following items are explicitly recognized but allowed to remain unimplemented in the first version of this slice:

1. replay trigger support for `repeated recurrence pattern`,
2. replay trigger support for `goal blockage or unfinished intention`,
3. replay trigger support for `user-signaled importance`,
4. permanent storage retrieval policy beyond the minimal candidate publication contract,
5. full conscious-content promotion policy,
6. identity writeback semantics based on memory replay outputs.

These items must remain visible as deferred scope rather than disappearing from the architecture record.

## 8. Cross-Slice Coordination Markers

The following follow-up coordination work is now explicitly required because this slice intentionally adopts `5A` and `6A`:

1. Workspace integration follow-up: a later workspace owner must define the promotion and competition contract that consumes `MemoryReplayCandidate` items without requiring memory owner changes in-place.
2. Identity integration follow-up: a later identity-governance owner must define how replay outputs are interpreted for identity writeback, because this slice intentionally publishes provenance only and does not emit identity-facing hints.
3. Interface stability requirement: later workspace and identity slices must consume the public memory contracts rather than reaching through private engine internals.
4. These are not optional nice-to-have items; they are required downstream coordination tasks created by the confirmed first-version boundary decisions.

## 9. Migration Plan

This slice does not port Helios v1 memory heuristics directly.

It defines the v2 owner boundary first so later workspace, narrative, and identity slices can attach to a stable affect-linked memory contract.

## 10. Failure Modes and Constraints

1. Missing feeling provenance must raise an explicit memory-owner error.
2. Published memory or replay-candidate values outside the allowed contract range must raise an explicit memory-owner error.
3. Publication must not occur for malformed memory or replay-candidate states.
4. No fallback replay-candidate path is allowed.
5. Missing required memory or replay capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent weighted formulas, permanent routing branches, and permanent threshold heuristics are prohibited.
7. The owner skeleton must reject malformed input before invoking its internal memory/replay path.

## 11. Observability and Logging

This initial slice keeps observability structural:

1. memory items preserve source feeling provenance,
2. affect tags preserve reuse of the feeling-state dimensional contract,
3. record and replay publication ops summarize owner activity,
4. replay reasons and forced-consolidation flags support downstream diagnostics without transferring workspace ownership,
5. error types define malformed contract conditions explicitly.

## 12. Validation Strategy

1. Unit test immutable memory-item, replay-candidate, and owner-state contracts.
2. Unit test reuse of `InteroceptiveFeelingVector` as the affect-tag contract.
3. Unit test provenance preservation from `InteroceptiveFeelingState` into memory items and owner state.
4. Unit test candidate publication by `episodic`, `semantic`, and `autobiographical` family.
5. Unit test surfacing of the three confirmed first-version replay triggers.
6. Unit test encoding of the forced-consolidation rule for `high anomaly + high affect`.
7. Unit test request and publication op summary fields.
8. Unit test explicit failure for malformed feeling input.
9. Unit test explicit failure when required memory or replay capability is unavailable.
