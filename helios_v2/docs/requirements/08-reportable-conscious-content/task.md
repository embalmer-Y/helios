# Requirement 08 - Reportable conscious content task plan

## 1. Task Breakdown

1. Define the reportable-consciousness API and ops contracts.
2. Define the runtime-owned bridge contracts that assemble `ConsciousContentMaterialSet` from current-cycle upstream public outputs without mutating `07` ownership.
3. Encode the confirmed first-version boundaries: full `WorkspaceCandidateSet` bridge coverage, formal per-cycle `ConsciousState` publication, single-focal semantic payload, maximum two auxiliary supporting-context items, fixed `NoCommitReason` taxonomy, and forced-consolidation evaluation eligibility without commit guarantee.
4. Encode the confirmed owner boundary for the `08` private commitment path: if an LLM path is used, it belongs to `08` only, sees only current-cycle declared inputs, and must not expand into thought, recall, continuation, or action ownership.
5. Keep the remaining unresolved commitment semantics as explicit confirmation gates.
6. Keep the allowed first-version deferrals as explicit unimplemented items.
7. Mark the required downstream coordination created by the lack of thought, broadcast, and action ownership as explicit follow-up work.
8. Implement the public contracts for conscious material, semantic focal content, supporting context, conscious state, commitment status, no-commit taxonomy, config, API, and ops contracts.
9. Implement the owner skeleton for input validation, commitment-request op construction, semantic commitment invocation, explicit `committed` versus `no_commit` publication, and fail-fast capability checks.
10. Implement the runtime-owned bridge/provider and `08` runtime stage adapter.
11. Export the public consciousness contract surface.
12. Add focused contract, owner-skeleton, and runtime-bridge tests for immutability, provenance, supporting-context cap, no-commit publication, fixed no-commit taxonomy, forced-consolidation evaluation visibility, no-fallback behavior, and current-cycle-only commitment inputs.

## 2. Dependencies

1. `07-workspace-competition-and-working-state` for upstream `WorkspaceCandidateSet` and `WorkingStateSnapshot`.
2. `06-memory-affect-and-replay` for upstream `MemoryFormationState`, memory-item material, replay-candidate provenance, and forced-consolidation lineage.
3. `05-interoceptive-feeling-layer` for upstream affect lineage preserved through memory and workspace contracts.
4. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/consciousness/contracts.py`
2. `helios_v2/src/helios_v2/consciousness/engine.py`
3. `helios_v2/src/helios_v2/consciousness/__init__.py`
4. `helios_v2/tests/test_consciousness_contracts.py`
5. `helios_v2/tests/test_consciousness_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/tests/test_runtime_stage_chain.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/08-reportable-conscious-content/requirement.md`
2. `helios_v2/docs/requirements/08-reportable-conscious-content/design.md`
3. `helios_v2/docs/requirements/08-reportable-conscious-content/task.md`

## 4. Contract-First Implementation Order

1. Requirement and design confirmation
2. Confirmed gate encoding
3. Deferred-item encoding
4. Cross-slice coordination marker encoding for later thought, broadcast, and action follow-up
5. Residual confirmation-gate review for still-unresolved commitment semantics
6. Public consciousness contracts
7. Runtime-owned bridge contracts and bridge-alignment rules
8. Owner skeleton
9. Runtime stage adapter and stage-result wiring
10. Export surface
11. Private owner observability and LLM-preparation skeleton
12. Focused tests
13. Adjacent runtime-chain validation

## 5. Slice-by-Slice Implementation Notes

### 5.1 Contracts slice
1. Define frozen dataclasses for `ConsciousContentMaterial`, `ConsciousContentMaterialSet`, `ReportableConsciousContent`, `SupportingContextItem`, `ConsciousState`, and ops contracts.
2. Define `ConsciousCommitStatus` and fixed `NoCommitReason` taxonomy as explicit public contract surfaces.
3. Define `ConsciousnessConfig` and `ConsciousContentAPI` with documented owner/purpose/input/output/failure semantics.
4. Ensure contracts preserve provenance from workspace candidate set, working state, memory candidate/material, and feeling lineage.

### 5.2 Bridge slice
1. Add a runtime-owned provider or bridge contract in `runtime/stages.py` that assembles `ConsciousContentMaterialSet` from `MemoryFormationState` and `WorkspaceCandidateSet`.
2. Enforce full current `WorkspaceCandidateSet` coverage rather than retained-id-only coverage.
3. Enforce fail-fast behavior if any current workspace candidate lacks aligned public material.
4. Keep semantic shaping and commitment outside the bridge.

### 5.3 Owner skeleton slice
1. Validate `WorkspaceCandidateSet`, `WorkingStateSnapshot`, and `ConsciousContentMaterialSet` before invoking the private commitment path.
2. Build one `CommitConsciousContentOp` per valid cycle.
3. Accept only current-cycle declared inputs in the private commitment path.
4. Publish one `ConsciousState` every valid cycle.
5. Publish explicit `committed` versus `no_commit` outcomes with fixed `NoCommitReason` values.
6. Enforce a maximum of two auxiliary supporting-context items.
7. Preserve forced-consolidation lineage as an explicit evaluation input without turning it into commit guarantee.
8. Fail explicitly when commitment capability is unavailable or malformed.
9. In the implemented first version, treat `WorkingStateSnapshot.retained_candidate_ids` as the sole commitment signal instead of re-ranking `WorkspaceCandidateSet` again inside `08`.
10. Encode `0 retained -> insufficient_commitment_signal`, `1 retained -> committed focal item`, and `>1 retained -> semantic_conflict_unresolved` as the current first-version rule.
11. Generate focal/supporting semantic text inside `08` from current-cycle `ConsciousContentMaterial.material_summary`, `content_kind`, and `salient_tokens` after whitespace normalization.
12. Return `context_not_reportable` when the single retained material cannot produce a non-empty normalized semantic summary.
13. Record owner-private observability across focal selection, semantic render request/response, nested capability trace when present, and final-state publication without expanding the public contract surface.
14. Use fixed private terminal-status taxonomies for capability and owner-path observability to avoid string drift.
15. Prepare the future LLM path as private request-builder, client-provider, transport, strict response parser, owner-controlled response acceptance policy, and provenance-bound render-result conversion boundaries only.
16. Centralize first-version deterministic-vs-LLM private construction behind owner-controlled wiring helpers rather than scattered call-site assembly, and keep that construction fail-fast rather than fallback-based.

### 5.4 Runtime stage slice
1. Add an `08` stage result dataclass in `runtime/stages.py`.
2. Add a runtime-owned bridge/provider contract and the `ReportableConsciousContentRuntimeStage` adapter.
3. Wire `07 -> 08` through immutable runtime frame inputs only.
4. Keep runtime orchestration as a bridge only; the kernel must not own commitment logic.

## 6. Focused Validation Plan

### 6.1 Primary focused validation
1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_consciousness_contracts.py helios_v2/tests/test_consciousness_engine.py -q`

Observed implementation status:

1. The focused owner-slice validation now covers the real first-version commitment path rather than only collaborator stubs.
2. It also now covers owner-private observability snapshots, fixed private terminal-status taxonomies, the LLM request-builder skeleton, the OpenAI-compatible transport skeleton, strict fail-fast response parsing, and the owner-controlled response-acceptance gate.
3. It now also covers explicit private wiring helpers selecting deterministic versus LLM-backed first-version construction without fallback.
4. Current verified result: `26 passed` for `helios_v2/tests/test_consciousness_engine.py -q`.

### 6.2 Bridge and chain validation
1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_runtime_stage_chain.py -q -k "conscious or workspace or memory"`

Observed implementation status:

1. The runtime-chain validation now exercises the real `FirstVersionConsciousCommitmentPath` through the `07 -> 08` stage boundary.
2. Current verified result: `7 passed` for `helios_v2/tests/test_runtime_stage_chain.py -q`.

### 6.3 Adjacent regression validation
1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_memory_contracts.py helios_v2/tests/test_memory_engine.py helios_v2/tests/test_workspace_contracts.py helios_v2/tests/test_workspace_engine.py helios_v2/tests/test_consciousness_contracts.py helios_v2/tests/test_consciousness_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`

Observed implementation status:

1. This adjacent regression now verifies memory/workspace provenance plus the real first-version `08` commitment rule in one focused slice.
2. Current verified result: `53 passed`.

## 7. Completion Criteria

1. A documented API from `WorkspaceCandidateSet + WorkingStateSnapshot + ConsciousContentMaterialSet` into conscious-content commitment exists.
2. A runtime-owned bridge contract exists for assembling current-cycle explicit material from upstream public contracts without extending `07` ownership.
3. Commitment-request, conscious-state publication, and reportable conscious-content publication ops are defined and documented.
4. The contract surface publishes one formal `ConsciousState` every valid cycle, including explicit `no_commit` cycles.
5. The contract surface publishes semantic focal content with explicit provenance, affect trace, and focal summary rather than a reference-only winner id.
6. Supporting context is allowed but capped at two auxiliary items and remains single-focal by contract.
7. The fixed `NoCommitReason` taxonomy is encoded as a public contract rather than open-ended text.
8. The owner skeleton enforces fail-fast malformed-input handling, current-cycle-only commitment inputs, and no-fallback behavior.
9. Forced-consolidation lineage remains visible as an evaluation input but does not guarantee final commitment.
10. Required downstream coordination work for later thought, broadcast, and action integration remains explicitly documented rather than disappearing from the plan.
11. Deferred first-version items remain explicitly documented as unimplemented scope rather than disappearing from the plan.
12. Only the remaining truly unresolved semantics remain as explicit confirmation gates.
13. Focused contract, owner-skeleton, and runtime-bridge tests pass.
14. The package explicitly records that the implemented first-version `08` path does not introduce implicit re-ranking and instead consumes `07` retained ids as the commitment signal.
15. The package records that current LLM-related implementation work remains private to `08` and currently stops at request-builder, default OpenAI-compatible client provider, transport skeleton, strict parse, owner-controlled response acceptance, and provenance-bound render-result conversion rather than provider strategy or production prompt policy.
16. The package records that deterministic-vs-LLM path selection is now an explicit owner-private construction decision inside `08`, and that this does not authorize `08` to expand into thought ownership, action ownership, or cross-owner fallback orchestration.
