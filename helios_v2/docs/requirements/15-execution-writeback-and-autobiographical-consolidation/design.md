# Requirement 15 - Execution writeback and autobiographical consolidation design

## 1. Design Overview

The execution-writeback owner closes the post-outcome continuity gap between formal runtime outcomes and later memory-driven self continuity. This slice now consumes normalized planner-bridge and identity-governance outcomes, publishes one immutable experience-writeback result per eligible path, derives bounded consolidation candidates, and hands those candidates to downstream storage or retrieval collaborators without taking over either domain.

## 2. Implemented Slice

Helios v2 now includes a formal `15` owner that transforms post-outcome runtime artifacts into continuity-bearing experience. `13` still owns proposal-to-decision bridging and normalized execution feedback, `14` still owns self-revision governance and applied identity state, and `15` now owns the next transition: continuity-preserving writeback plus bounded consolidation-candidate assembly.

## 3. Delivered Architecture

The implemented slice contains eight public runtime concepts:

1. `ExperienceWritebackRequest`
2. `ExperienceWritebackStatus`
3. `ExperienceWritebackResult`
4. `ContinuityEvidencePacket`
5. `ConsolidationCandidate`
6. `PublishExperienceWritebackOp`
7. `PublishConsolidationCandidateOp`
8. `ExperienceWritebackAPI`

Implementation boundary confirmation:

1. `15` owns continuity-oriented publication and consolidation-candidate assembly.
2. `15` does not own planner, governance, retrieval ranking, or raw backend writes.
3. `PlannerBridgeResult/IdentityGovernanceResult -> ExperienceWritebackRequest -> ExperienceWritebackResult (+ ConsolidationCandidate)` is the delivered public transformation.

## 4. Data Structures

### 4.1 ExperienceWritebackRequest
- `request_id: str`
- `source_outcome_kind: str`
- `source_outcome_id: str`
- `source_outcome_status: str`
- `outcome_class: str`
- `source_provenance: dict[str, object]`
- `requested_effect_summary: str`
- `applied_effect_summary: str`
- `reason_trace: tuple[str, ...]`
- `tick_id: int | None`

### 4.2 ExperienceWritebackStatus
- `written`
- `written_blocked_outcome`
- `written_identity_change`
- `written_unresolved_outcome`

### 4.3 ContinuityEvidencePacket
- `packet_id: str`
- `continuity_kind: str`
- `source_outcome_kind: str`
- `source_outcome_id: str`
- `outcome_class: str`
- `summary: str`
- `requested_effect_summary: str`
- `applied_effect_summary: str`
- `reason_trace: tuple[str, ...]`

Implemented taxonomy:

1. `continuity_kind` distinguishes `external_action`, `blocked_action`, `failed_action`, `identity_change`, and `blocked_identity_change`.
2. `outcome_class` distinguishes `world_changed`, `world_blocked`, `world_failed`, `self_changed`, and `self_blocked`.

### 4.4 ConsolidationCandidate
- `candidate_id: str`
- `target_memory_family: str`
- `priority_hint: float`
- `salience_reason: str`
- `continuity_packet: ContinuityEvidencePacket`

### 4.5 ExperienceWritebackResult
- `result_id: str`
- `source_request_id: str`
- `status: ExperienceWritebackStatus`
- `continuity_packet: ContinuityEvidencePacket`
- `consolidation_candidates: tuple[ConsolidationCandidate, ...]`

Implemented status mapping:

1. `written` for successful external action continuity.
2. `written_blocked_outcome` for blocked external action continuity.
3. `written_identity_change` for accepted identity mutation continuity.
4. `written_unresolved_outcome` for failed external action and rejected self-revision continuity.

## 5. Module Changes

1. `experience_writeback/contracts.py` defines owner declaration, typed contracts, explicit fixed taxonomies, and the public API protocol.
2. `experience_writeback/engine.py` implements the first owner skeleton, including deterministic continuity classification and three-family candidate publication.
3. `experience_writeback/__init__.py` exports the public writeback surface.
4. `runtime/stages.py` adds `ExperienceWritebackStageResult`, `ExperienceWritebackRequestProvider`, and `ExperienceWritebackRuntimeStage`.
5. `runtime/__init__.py` and `helios_v2/__init__.py` export the runtime and top-level public API surface.
6. Tests validate immutability, provenance preservation, blocked-outcome retention, identity-change distinction, and runtime-chain publication.

## 6. Failure Modes and Constraints

1. Missing upstream provenance raises an explicit owner error.
2. Malformed continuity packets must not publish.
3. No fallback direct backend write path is allowed.

## 7. Validation Strategy

1. Unit test immutable contracts.
2. Unit test blocked externalization still becomes continuity writeback.
3. Unit test identity revision outcomes become distinct writeback results.
4. Unit test runtime-stage wiring from `13/14` into `15`.

## 8. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_experience_writeback_contracts.py helios_v2/tests/test_experience_writeback_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `16 passed`
2. `pytest helios_v2/tests -q` -> `168 passed`

Delivered first-version behavior:

1. Runtime can emit zero-to-multiple writeback requests per tick from adjacent `13` and `14` outcomes.
2. The current runtime chain validates one executed external-action writeback and one accepted identity-change writeback in the same tick.
3. Engine tests validate blocked, failed, and rejected continuity paths as explicit writeback results instead of silent loss.
