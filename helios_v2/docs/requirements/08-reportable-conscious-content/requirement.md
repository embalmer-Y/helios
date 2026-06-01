# Requirement 08 - Reportable conscious content

## 1. Background and Problem

After workspace competition publishes a `WorkspaceCandidateSet` plus `WorkingStateSnapshot`, Helios v2 still lacks a dedicated owner that commits those competitive results into one explicit reportable conscious-content surface. Without this owner, later modules would either consume workspace candidates directly and invent private commitment logic, or workspace owner would silently expand into a mixed workspace-consciousness controller.

This requirement is a review-driven follow-up to `07`. The review result is that `07` correctly stops at candidate competition and short-lived working state, but the current workspace output surface only carries candidate identities, provenance ids, and score hints. That is not enough to safely claim conscious-content commitment by direct downstream inference. Therefore `08` must require an explicit conscious-content owner boundary and an explicit upstream content-material contract rather than private reach-through into memory or workspace internals.

This slice corresponds to the transition from competitive workspace state into explicit globally integrated or reportable conscious content, not to internal thought-loop ownership, action arbitration, or external execution.

## 2. Goal

Create a reportable conscious-content owner that consumes workspace outputs plus explicit candidate material needed for semantic commitment, commits one explicit conscious-content state for downstream thought, reporting, or action-forming layers, and exposes documented API and ops contracts without hardcoded heuristics, fallback behavior, or ownership collapse into workspace, thought, or action modules. In the confirmed first-version direction, this owner may invoke one owner-controlled LLM commitment path when that path is required to shape reportable conscious-content semantics, but that LLM use remains strictly inside the `08` owner boundary and must not expand into thought-loop ownership.

Implementation note for the current first version:

1. The currently implemented first-version path is deterministic and retained-id-driven rather than LLM-driven.
2. It treats `WorkingStateSnapshot.retained_candidate_ids` as the current-cycle commitment signal owned upstream by `07` instead of introducing a second hidden top-1 ranking policy inside `08`.
3. This implementation note documents current behavior only; it does not promote retained-id-driven commitment into permanent architecture truth for later requirement slices, and any future promotion to an owner-controlled LLM commitment path must be treated as a deliberate follow-up design step rather than a silent replacement.

## 3. Functional Requirements

### 3.1 Conscious-content owner boundary
1. The reportable conscious-content layer must be the sole owner of conscious-content commitment and conscious-state publication in this slice.
2. The owner must remain separate from workspace competition, replay-candidate construction, internal thought-loop execution, action arbitration, and identity-governance ownership.
3. The owner must not reinterpret itself as the owner of long-horizon continuation pressure, final motor choice, or direct external channel execution in this slice.

### 3.2 Upstream input boundary
1. The conscious-content layer must accept `WorkspaceCandidateSet` as a required upstream input contract.
2. The conscious-content layer must accept `WorkingStateSnapshot` as a required upstream input contract.
3. The conscious-content layer must accept an explicit upstream content-material contract for the candidate items still eligible for commitment in the current cycle.
4. In the confirmed first-version boundary, the explicit content-material contract must cover the full set of candidates published in the current `WorkspaceCandidateSet`, not only the retained ids in `WorkingStateSnapshot`.
5. The explicit content-material contract must preserve enough semantic payload and provenance to support conscious commitment without private module reach-through.
6. The explicit content-material contract must be assembled by a runtime-owned bridge or provider rather than by stretching `07` into a richer consciousness owner.
7. The first public boundary of this slice must not require direct imports into memory-owner internals, workspace-owner internals, or runtime frame-private state.
8. If current feeling content is required beyond ids and provenance, it must enter through an explicit public contract rather than an implicit read-through into upstream owners.
9. If the first-version implementation uses an owner-controlled LLM commitment path, that path must operate only on the current cycle's declared owner inputs and must not read prior conscious states, latent recall state, or broader runtime history.

### 3.3 Conscious commitment granularity
1. The first public output of this slice must be a committed conscious-content state rather than another unordered candidate set.
2. The first version of this slice must make explicit whether the current cycle committed zero or one focal conscious item.
3. Every valid cycle in this slice must publish one formal conscious state, including cycles with `commit_status = no_commit`.
4. If no focal conscious item is committed in a valid cycle, the owner must publish an explicit no-commit or quiet outcome rather than silently reusing the previous conscious item.
5. The owner may preserve supporting context around the focal conscious item, but it must not collapse back into a generic workspace-candidate publication surface.
6. In the confirmed first-version boundary, supporting context is allowed for both committed and no-commit cycles, but it must remain strictly auxiliary and must not create an implicit second focal item.
7. Supporting context must be capped at two auxiliary items in the first version of this slice.
8. Multi-item simultaneous conscious commitment remains outside this first-version requirement unless later requirement work expands the surface explicitly.

### 3.4 Provenance and traceability
1. A committed conscious-content state must preserve provenance to the source workspace candidate set.
2. A committed conscious-content state must preserve provenance to the source working-state snapshot.
3. A committed conscious-content state must preserve provenance to the source memory candidate or candidate-material reference used for commitment.
4. A committed conscious-content state must preserve provenance to the source feeling state used by upstream owners.
5. The owner must not synthesize non-traceable conscious content that cannot be tied back to explicit upstream material.
6. In the confirmed first-version direction, the public conscious-content payload must be semantic rather than reference-only: it must preserve explicit reportable content fields such as focal summary, affect trace, and provenance rather than exposing only selected candidate ids.

### 3.5 Output boundary to later owners
1. The conscious-content owner must publish a documented public API for conscious commitment and publication.
2. The owner must define an op for conscious-content commitment requests.
3. The owner must define an op for conscious-state publication.
4. The owner must define an op for reportable conscious-content publication.
5. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.
6. Outputs of this owner must be consumable by later thought, report, or action-forming owners without transferring ownership back into this slice.
7. Broadcast-ready publication metadata remains outside this requirement and must be introduced only by a later dedicated requirement if needed.

### 3.6 Separation from thought and action owners
1. The conscious-content owner may expose one committed conscious item or explicit quiet outcome, but it must not execute an internal thought loop in this slice.
2. The conscious-content owner must not produce final external action proposals in this slice.
3. The conscious-content owner must not call planner, executor, channel, or identity-revision owners directly as part of conscious commitment.
4. The owner may invoke one owner-controlled LLM commitment path to transform current-cycle candidate material into reportable conscious-content semantics, but that path must remain limited to conscious commitment and must not generate continuation pressure, recall intent, internal deliberation, or external action proposals.
5. Any later thought-loop or action-forming consumption of conscious content must remain downstream follow-up work rather than implicit scope inside this requirement.

### 3.7 Learned or runtime-provided commitment semantics
1. The owner must not hardcode permanent top-1 formulas, routing branches, or threshold heuristics into the architecture contract.
2. Conscious commitment policy, quiet/no-commit policy, and contextual integration policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty-conscious-state defaults, and explicit owner-controlled bootstrap metadata.
4. If the confirmed first-version implementation uses an owner-controlled LLM commitment path, prompt structure, semantic shaping policy, and acceptance policy must remain owner-controlled and must not be delegated implicitly to later thought owners.
5. Dynamic commitment semantics must remain learning-driven rather than permanently frozen into architecture defaults.

### 3.8 No fallback behavior
1. The conscious-content layer must not synthesize fallback conscious content when required upstream contracts are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic `pick highest score and continue` path when the configured commitment capability is unavailable.
3. The owner must fail explicitly when required input invariants or required commitment capability are missing.
4. The owner must not silently reinterpret missing semantic payload as permission to commit from ids alone.
5. The owner must not silently bypass its declared semantic-commitment path and publish reference-only output under the name of reportable conscious content.

## 4. Non-Functional Requirements

1. Conscious-content and publication contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured conscious-commitment policy.
3. The owner boundary must remain separate from workspace competition, thought-loop execution, action planning, identity governance, and channel execution owners.
4. Published state must preserve enough provenance to support later diagnostics, evaluation, and causal tracing of why one focal conscious item was or was not committed.
5. The first-version conscious state must remain single-focal even when supporting context is present.

## 5. Code Behavior Constraints

1. Conscious-content code must not import planner, executor, channel, or identity-governance owners directly.
2. Conscious-content code must not reach through runtime stage results or upstream private helpers to reconstruct semantic payloads.
3. Conscious-content code must expose only documented APIs and ops contracts across module boundaries.
4. Conscious-content code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
5. Conscious-content code must not blur owner boundaries by reusing its LLM commitment path as a hidden thought loop, recall planner, or action planner.
6. Final thought execution, action selection, and identity revision remain outside this owner.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/consciousness/contracts.py`
2. `helios_v2/src/helios_v2/consciousness/engine.py`
3. `helios_v2/src/helios_v2/consciousness/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_consciousness_contracts.py`
6. `helios_v2/tests/test_consciousness_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from `WorkspaceCandidateSet` plus `WorkingStateSnapshot` into reportable conscious-content commitment.
2. The package defines an explicit runtime-owned bridge content-material requirement covering the full `WorkspaceCandidateSet` rather than allowing private reach-through into `06` or `07` owners.
3. The package defines documented ops contracts for conscious-content commitment request, conscious-state publication, and reportable conscious-content publication.
4. The contract surface publishes one formal conscious state every valid cycle, including explicit `no_commit` cycles, without collapsing back into workspace-candidate ownership.
5. The contract surface publishes semantic conscious content with focal summary, affect trace, and provenance rather than a reference-only winner id.
6. Supporting context is allowed but capped at two strictly auxiliary items and must not violate the single-focal boundary.
7. The package preserves provenance from committed conscious content back to workspace, working-state, memory-candidate material, and feeling-state lineage.
8. The package does not claim internal thought-loop, action-arbitration, planner, executor, or identity-governance ownership, even when `08` uses its own owner-controlled LLM commitment path.
9. Forced-consolidation lineage remains eligible for conscious evaluation in `08`, but does not guarantee final commit.
10. No test or implementation path demonstrates fallback conscious-content synthesis or degraded heuristic substitution.

## 8. Review Findings Incorporated Into This Requirement

1. `07` remains the owner of candidate competition and short-lived working state only; it must not be stretched into final conscious-content commitment.
2. `08` requires richer explicit upstream content material than the current `WorkspaceCandidate` id-and-score surface alone provides, and that material is supplied through a runtime-owned bridge covering the full current `WorkspaceCandidateSet`.
3. `08` publishes one formal conscious state every valid cycle, including explicit `no_commit` cycles with at most two auxiliary supporting-context items.
4. `08` owns reportable semantic conscious payload generation; in the confirmed first-version direction this may include one owner-controlled LLM commitment path, but that path must not expand into thought-loop ownership.
5. Forced-consolidation lineage remains relevant to conscious evaluation eligibility in `08`, but does not guarantee final conscious commitment.
6. The boundary from conscious content into later thought or action layers is intentionally deferred; this requirement only establishes the conscious-content owner itself.
7. Any follow-up requirement that consumes conscious content must do so through explicit downstream contracts rather than by re-opening workspace or memory private state access.
