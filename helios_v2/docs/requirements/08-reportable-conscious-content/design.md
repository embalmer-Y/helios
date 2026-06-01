# Requirement 08 - Reportable conscious content design

## 1. Design Overview

Reportable conscious content is the sole owner of explicit conscious-content commitment immediately after workspace competition and before later thought-loop, report, or action-forming owners. It consumes `WorkspaceCandidateSet`, `WorkingStateSnapshot`, and one runtime-owned content-material bundle assembled from upstream public contracts, then publishes one formal conscious state every valid cycle.

This slice is intentionally contract-first. It establishes the owner boundary, runtime-owned bridge boundary, public API, ops contracts, semantic conscious payload shape, explicit `no_commit` behavior, and owner-controlled semantic commitment path before any permanent commitment policy is written.

The confirmed first-version direction for this slice is:

1. `07` remains unchanged as the owner of workspace candidate competition and working-state publication only.
2. `08` owns reportable conscious-content commitment.
3. A runtime-owned bridge assembles explicit candidate material covering the full `WorkspaceCandidateSet` from upstream public owner outputs.
4. `08` publishes one formal conscious state every valid cycle, including `commit_status = no_commit` cycles.
5. `08` publishes semantic conscious payload rather than a reference-only winner id.
6. `08` may use one owner-controlled LLM commitment path, but that path is restricted to conscious-content semantic commitment and must not expand into thought ownership.
7. The first-version LLM commitment path, if used, must operate only on current-cycle owner inputs and must not read cross-cycle historical state beyond explicit owner bootstrap metadata later confirmed by requirement updates.

The currently implemented first-version commitment rule is:

1. `08` does not re-rank or silently reinterpret the full `WorkspaceCandidateSet` into a new hidden winner-selection policy.
2. `WorkingStateSnapshot.retained_candidate_ids` is treated as the first-version commitment signal owned by upstream `07`.
3. If the retained id count is `0`, `08` publishes `commit_status = no_commit` with `no_commit_reason = insufficient_commitment_signal`.
4. If the retained id count is `1`, `08` commits that single retained item as the focal conscious item.
5. If the retained id count is greater than `1`, `08` publishes `commit_status = no_commit` with `no_commit_reason = semantic_conflict_unresolved` rather than introducing an implicit tie-break or top-1 re-ranking rule.
6. In all three cases, semantic focal/supporting text is generated inside `08` from current-cycle explicit material rather than copied through as upstream-owned report text.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect/replay, and workspace competition owners, but it still lacks a formal owner that turns workspace competition results into one explicit reportable conscious-content surface.

The review result that motivated this slice is:

1. `07` correctly stops at `WorkspaceCandidateSet + WorkingStateSnapshot`.
2. The current workspace output surface contains candidate ids, provenance ids, and score hints, but not enough semantic material to claim explicit conscious-content commitment by downstream inference.
3. Stretching `07` to publish final conscious content would collapse workspace and consciousness ownership.
4. Allowing a later thought or action owner to reconstruct conscious content privately would reintroduce hidden cross-owner reach-through.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for conscious-content commitment and publication,
2. a runtime-owned bridge that assembles explicit candidate material from existing public upstream contracts without changing `07` into a consciousness owner.

The next gap after this contract layer is a concrete owner skeleton that can:

1. accept `WorkspaceCandidateSet`,
2. accept `WorkingStateSnapshot`,
3. accept a `ConsciousContentMaterialSet` assembled by runtime from upstream public contracts,
4. build a conscious-commitment request op,
5. invoke an owner-controlled commitment path,
6. publish one immutable `ConsciousState` every valid cycle,
7. publish reportable conscious-content metadata when a focal item is committed,
8. reject malformed input or unavailable required commitment capability explicitly.

## 3. Target Architecture

The initial reportable-consciousness slice contains eleven runtime concepts:

1. `ConsciousContentMaterial`: immutable explicit candidate material aligned to one `WorkspaceCandidate`.
2. `ConsciousContentMaterialSet`: immutable runtime-owned bundle covering the full current `WorkspaceCandidateSet`.
3. `ReportableConsciousContent`: immutable semantic focal payload for one committed conscious item.
4. `SupportingContextItem`: immutable strictly auxiliary context item derived from explicit current-cycle material.
5. `ConsciousCommitStatus`: explicit commitment status for the current cycle.
6. `ConsciousState`: immutable published conscious-state snapshot for one cycle.
7. `ConsciousnessConfig`: owner configuration surface for learned commitment, quiet-state, and semantic-shaping policies.
8. `CommitConsciousContentOp`: runtime-visible request op for one conscious-commitment cycle.
9. `PublishConsciousStateOp`: runtime-visible publication op for one formal conscious state.
10. `PublishReportableConsciousContentOp`: runtime-visible publication op for one committed reportable conscious-content payload.
11. `ConsciousContentAPI`: public owner-facing API for conscious commitment and publication.

The initial owner also contains one private owner-controlled collaborator surface:

1. `ConsciousCommitmentPath`: private owner interface responsible for turning explicit current-cycle material into semantic conscious output.

Implementation boundary confirmation:

1. Reportable-consciousness owner owns only conscious-content commitment and conscious-state publication.
2. It does not own workspace competition, memory replay generation, internal thought execution, continuation pressure, action arbitration, planner routing, or identity writeback.
3. It may expose a replaceable internal commitment path, but that path remains private to the owner until promoted by a later requirement slice.
4. `WorkspaceCandidateSet + WorkingStateSnapshot + ConsciousContentMaterialSet -> ConsciousState` is the first required public owner-facing transformation in this slice.
5. If an LLM is used in this slice, that LLM call belongs to `08` and exists only to perform conscious-content semantic commitment inside this owner.
6. In the confirmed first-version direction, the commitment path reads only current-cycle `WorkspaceCandidateSet`, `WorkingStateSnapshot`, and `ConsciousContentMaterialSet`; it must not inspect prior conscious states, latent recall state, or broader runtime history.

### 3.1 Runtime-owned bridge boundary

The runtime-owned bridge is intentionally outside the consciousness owner.

Its responsibilities are:

1. read public outputs from upstream runtime stages,
2. assemble explicit candidate material aligned to the current `WorkspaceCandidateSet`,
3. preserve provenance from workspace candidate to replay candidate to memory item to feeling-state lineage,
4. fail explicitly if aligned explicit material cannot be assembled for any current workspace candidate.

The bridge must not:

1. rank candidates,
2. commit conscious content,
3. perform semantic shaping,
4. hide missing upstream material by synthesizing placeholders.

The bridge is expected to consume:

1. `WorkspaceCandidateSet` and `WorkingStateSnapshot` from `07`,
2. `MemoryFormationState` from `06`,
3. public feeling provenance already preserved through memory and workspace contracts,
4. any additional explicit public upstream snapshot later approved by requirement updates.

### 3.2 Lifecycle

1. Memory affect and replay publishes `MemoryFormationState` with memory items and replay candidates.
2. Workspace competition publishes `WorkspaceCandidateSet` and `WorkingStateSnapshot`.
3. A runtime-owned bridge assembles `ConsciousContentMaterialSet` for the full current `WorkspaceCandidateSet` by aligning workspace candidates to replay candidates and memory items through public provenance.
4. Reportable-consciousness owner validates workspace, working-state, and material-set invariants.
5. The owner builds a conscious-commitment request op for orchestration visibility.
6. An owner-controlled commitment path computes one semantic focal conscious item or explicit `no_commit` outcome from current-cycle explicit material only.
7. In the currently implemented first-version path, the owner reads `WorkingStateSnapshot.retained_candidate_ids` as the commitment signal rather than introducing a second hidden ranking layer inside `08`.
8. The owner generates focal and supporting semantic summaries inside `08` from normalized current-cycle material summaries plus salient tokens.
9. If the retained set is empty, the owner publishes `insufficient_commitment_signal`; if it contains more than one id, the owner publishes `semantic_conflict_unresolved`.
10. If a single retained item is semantically non-reportable after normalization, the owner publishes `context_not_reportable`.
11. The owner records a private end-to-end observability snapshot for the current cycle across selection, semantic render request, semantic render response, nested capability trace when present, and final conscious-state publication.
12. The owner-path and capability-path trace terminal statuses are fixed private enum taxonomies rather than open-ended strings.
13. The owner publishes one immutable `ConsciousState` every valid cycle.
14. If a focal conscious item exists, the owner also publishes one reportable conscious-content publication op.
15. Later thought, report, or action-forming owners consume the conscious-state output without transferring ownership back into this owner.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `WorkspaceCandidateSet`, `WorkingStateSnapshot`, and `ConsciousContentMaterialSet`.
2. `ConsciousContentMaterialSet` covers the full current `WorkspaceCandidateSet`, not only retained candidate ids.
3. `08` publishes one formal conscious state every valid cycle.
4. `ConsciousState.commit_status` is explicit and supports at least `committed` and `no_commit`.
5. The first-version conscious state is single-focal even when supporting context exists.
6. Supporting context is allowed for both committed and no-commit cycles but is capped at two auxiliary items.
7. `forced_consolidation` lineage remains relevant to evaluation eligibility but does not guarantee final commitment.
8. Broadcast-ready metadata is excluded from this slice.
9. Semantic commitment may use one owner-controlled LLM path, but that path must not generate recall intent, continuation pressure, deliberation, or action proposals.
10. `forced_consolidation` must remain an explicit commitment-path input factor rather than disappearing into passive provenance only.
11. The first-version `no_commit_reason` surface is fixed-enum rather than open-ended free text.
12. The currently implemented deterministic first-version path treats retained-id cardinality as the only commitment/no-commit selector and deliberately avoids introducing a second hidden ranking policy inside `08`.
13. Supporting context is generated from non-focal current-cycle materials in workspace order and remains capped by `ConsciousnessConfig.max_supporting_context_items`.
14. Semantic summary generation in `08` normalizes whitespace and composes reportable text from explicit `material_summary`, `content_kind`, and `salient_tokens` only.
15. Current private observability in `08` is owner-local only; it does not expand the public contract surface or runtime stage outputs.
16. The current LLM-preparation path in `08` is split into private request-builder, transport, strict response parser, owner-controlled response acceptance policy, and provenance-bound render-result conversion boundaries.
17. The current OpenAI-compatible transport skeleton accepts one owner-controlled request, executes `chat.completions.create`, expects a strict JSON payload with `focal_content` and `supporting_context`, and fails explicitly on malformed or non-traceable output.
18. The current first-version owner-private response policy rejects LLM outputs that change the already selected focal material, introduce focal content during a `no_commit` cycle, or exceed the configured supporting-context bound.
19. First-version private construction now uses explicit owner-controlled wiring helpers to choose either the deterministic semantic renderer path or the LLM-backed semantic renderer path; this choice is made inside `08` and does not introduce fallback from one path to the other.

## 4. Data Structures

### 4.1 ConsciousContentMaterial
- `material_id: str`
- `source_workspace_candidate_id: str`
- `source_memory_candidate_id: str`
- `source_memory_id: str`
- `source_feeling_state_id: str`
- `content_kind: str`
- `material_summary: str`
- `summary_ref: str | None`
- `context_ref: str | None`
- `salient_tokens: tuple[str, ...]`
- `affect_tag: InteroceptiveFeelingVector`
- `forced_consolidation: bool`
- `workspace_score_hint: float | None`
- `priority_hint: float | None`

Purpose:

1. expose explicit semantic commitment material without private owner reach-through,
2. align one published workspace candidate with its public memory and feeling provenance,
3. provide the minimal semantic payload required for `08` commitment,
4. reduce ambiguity in semantic commitment by exposing one explicit bridge-owned short summary per material.

### 4.2 ConsciousContentMaterialSet
- `set_id: str`
- `source_workspace_candidate_set_id: str`
- `source_working_state_id: str`
- `materials: tuple[ConsciousContentMaterial, ...]`
- `tick_id: int | None`

Purpose:

1. represent one immutable current-cycle bundle covering the full workspace candidate set,
2. give `08` an explicit bridge-owned semantic input surface,
3. preserve current-cycle alignment across workspace, working state, and material payloads.

### 4.3 ReportableConsciousContent
- `content_id: str`
- `source_material_id: str`
- `source_workspace_candidate_id: str`
- `source_memory_candidate_id: str`
- `source_feeling_state_id: str`
- `content_kind: str`
- `focal_summary: str`
- `affect_trace: InteroceptiveFeelingVector`
- `salient_tokens: tuple[str, ...]`
- `tick_id: int | None`

Purpose:

1. represent one immutable semantic focal conscious item,
2. be reportable by downstream owners without reconstructing semantics from refs alone,
3. remain tied to explicit upstream provenance.

### 4.4 SupportingContextItem
- `context_item_id: str`
- `source_material_id: str`
- `source_workspace_candidate_id: str`
- `content_kind: str`
- `summary: str`
- `affect_trace: InteroceptiveFeelingVector`

Constraints:

1. supporting context is auxiliary only,
2. no more than two supporting items may be published,
3. supporting items must not create an implicit second focal conscious item,
4. supporting-context summaries are generated by the `08` commitment path rather than copied through as upstream-owned report text.

### 4.5 ConsciousCommitStatus
- `committed`
- `no_commit`

Purpose:

1. make every cycle outcome explicit,
2. prevent silent reuse of previous conscious content,
3. support deterministic downstream handling of quiet cycles.

### 4.6 NoCommitReason
- `insufficient_commitment_signal`
- `semantic_conflict_unresolved`
- `context_not_reportable`
- `capability_rejected_cycle`

Purpose:

1. make quiet-cycle causes explicit and testable,
2. avoid open-ended free-text drift in the first version,
3. give downstream owners a stable no-commit taxonomy.

### 4.7 ConsciousState
- `state_id: str`
- `commit_status: ConsciousCommitStatus`
- `source_workspace_candidate_set_id: str`
- `source_working_state_id: str`
- `focal_content: ReportableConsciousContent | None`
- `supporting_context: tuple[SupportingContextItem, ...]`
- `no_commit_reason: NoCommitReason | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable formal conscious state for one cycle,
2. keep focal commitment explicit,
3. preserve quiet/no-commit cycles without hidden carry-over.

### 4.8 ConsciousnessConfig
- `legal_min_score: float`
- `legal_max_score: float`
- `conscious_state_bootstrap_id: str`
- `max_supporting_context_items: int`
- `mandatory_learned_parameters: tuple[...]`

Confirmed first-version learned-parameter categories:

1. `commitment_policy`
2. `quiet_state_policy`
3. `semantic_shaping_policy`

### 4.9 CommitConsciousContentOp
- `op_name: str`
- `owner: str`
- `workspace_candidate_count: int`
- `retained_candidate_count: int`
- `material_count: int`
- `working_state_id: str`
- `forced_material_count: int`

### 4.10 PublishConsciousStateOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `commit_status: str`
- `no_commit_reason: NoCommitReason | None`
- `supporting_context_count: int`

### 4.11 PublishReportableConsciousContentOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `content_id: str`
- `source_material_id: str`

## 5. Module Changes

1. `consciousness/contracts.py` will define owner declaration, typed conscious contracts, public API protocol, ops contracts, error type, and explicit commitment status surface.
2. `consciousness/engine.py` will implement the first owner skeleton for conscious commitment and publication, including the fixed no-commit taxonomy, the private commitment-path boundary, and owner-private observability traces.
3. The currently implemented first-version engine also includes `FirstVersionConsciousCommitmentPath`, which uses retained-id cardinality as the commitment signal, generates focal/supporting semantic summaries from explicit current-cycle material without hidden re-ranking, and records a private selection -> render -> final-state snapshot for each valid cycle.
4. The current private LLM-preparation path in `consciousness/engine.py` now includes an owner-controlled request builder, fixed private trace builders, fixed terminal-status taxonomies, an `_LLMBackedSemanticCommitmentCapability` skeleton, an owner-controlled response acceptance policy, and an `_OpenAICompatibleSemanticCommitmentTransport` skeleton with strict JSON parsing and provenance-bound fail-fast conversion.
5. `consciousness/engine.py` now also includes explicit private wiring helpers for first-version owner construction, so deterministic and LLM-backed semantic commitment modes are selected by `08` owner wiring rather than by scattered call-site assembly.
6. `consciousness/__init__.py` will export the public consciousness surface.
7. `runtime/stages.py` will add the runtime-owned bridge/provider and the `08` runtime stage adapter.
8. `tests/test_consciousness_contracts.py` will validate contract immutability, provenance preservation, supporting-context cap, fixed no-commit taxonomy, and semantic payload invariants.
9. `tests/test_consciousness_engine.py` now validates owner-skeleton behavior, the retained-id commitment rule, explicit `no_commit` publication, malformed-input rejection, forced-consolidation evaluation visibility, private observability snapshots, owner-controlled capability failure semantics, explicit first-version private wiring selection, the owner-controlled LLM response acceptance gate, and the OpenAI-compatible transport skeleton's fail-fast parse behavior.
10. `tests/test_runtime_stage_chain.py` will validate `07 -> 08` bridge alignment and runtime stage execution against the same first-version commitment rule.

## 6. Confirmation Gates

This requirement package must not guess the following unresolved semantics:

1. the exact learned commitment policy used to select or reject one focal item from current-cycle materials,
2. the exact LLM prompt contract used by the private conscious-commitment path if an LLM is used,
3. the exact acceptance or rejection rule that determines `committed` versus `no_commit`,
4. whether the bridge-owned material bundle must include an explicit current-feeling snapshot beyond affect tags already preserved on memory-derived material,
5. whether some memory families receive family-specific conscious-commitment treatment beyond the shared first-version interface.

These remain explicit design gates that require user confirmation before implementation of the permanent conscious-commitment path.

Current implementation note:

1. The first implemented path intentionally closes none of these permanent-policy gates.
2. The retained-id-driven deterministic rule is recorded only as the current first-version implementation, used to keep ownership and no-fallback semantics explicit before a later learned or LLM-backed path is introduced.
3. The current LLM-preparation work does not yet introduce provider-specific routing strategy or production prompt policy; it only establishes owner-private request, trace, transport, strict parse, response-acceptance, and provenance-bound conversion boundaries.
4. Any future promotion from the deterministic path to an owner-controlled LLM path must be treated as a deliberate follow-up design step, not a silent replacement.
5. The new private wiring helpers do not expand `08` into a broader orchestration owner; they only make the semantic commitment mode choice explicit inside the existing `08` boundary.

## 7. Deferred First-Version Items

The following items are explicitly recognized but allowed to remain unimplemented in the first version of this slice:

1. multi-focal simultaneous conscious commitment,
2. broadcast-ready metadata or global-broadcast distribution semantics,
3. direct thought-loop execution from inside the consciousness owner,
4. direct action-proposal generation from inside the consciousness owner,
5. identity-governance consequences of conscious-content publication,
6. non-memory candidate sources beyond the current workspace-material bridge.

These items must remain visible as deferred scope rather than disappearing from the architecture record.

## 8. Cross-Slice Coordination Markers

The following follow-up coordination work is explicitly required by the confirmed first-version boundary decisions:

1. Thought follow-up: a later owner must consume `ConsciousState` and decide if, when, and how conscious content enters internal thought execution.
2. Action follow-up: a later owner must define how conscious content contributes to action-forming or report-forming flows without moving that ownership back into `08`.
3. Broadcast follow-up: a later requirement must define whether reportable conscious content is also globally broadcast, externally reportable, or both.
4. Bridge follow-up: if future non-memory candidate sources are admitted upstream, the runtime-owned bridge must be extended explicitly rather than by reopening `08` owner assumptions.
5. These are required downstream coordination tasks created by the confirmed first-version boundary choices, not optional notes.

## 9. Migration Plan

This slice does not port Helios v1 reply-generation or internal-thought prompt logic directly.

It defines the v2 consciousness owner boundary first so later thought, report, and action layers can attach to a stable conscious-state contract.

The runtime-owned bridge is the deliberate migration tool that allows `08` to consume explicit semantic material without mutating `06` or `07` into a different owner shape.

## 10. Failure Modes and Constraints

1. Missing alignment between `WorkspaceCandidateSet` and `ConsciousContentMaterialSet` must raise an explicit consciousness-owner error.
2. Missing provenance from material to memory candidate or feeling lineage must raise an explicit consciousness-owner error.
3. A published conscious state with more than one focal item must raise an explicit consciousness-owner error.
4. A published conscious state with more than two supporting-context items must raise an explicit consciousness-owner error.
5. A `committed` conscious state without `focal_content` must raise an explicit consciousness-owner error.
6. A `no_commit` conscious state that silently carries forward prior focal content must raise an explicit consciousness-owner error.
7. Publication must not occur for malformed conscious states or malformed reportable conscious payloads.
8. No fallback conscious-commitment path is allowed.
9. Missing required commitment capability must abort execution rather than substituting a simpler heuristic path.
10. The owner skeleton must reject malformed input before invoking its internal commitment path.
11. The private LLM commitment path, if used, must not be reused as a hidden thought path or hidden action path.
12. The private LLM commitment path, if used, must reject access to undeclared cross-cycle state.
13. A `no_commit` conscious state must use only the fixed `NoCommitReason` taxonomy in the first version.
14. The first implemented deterministic path must not silently choose one winner when `WorkingStateSnapshot.retained_candidate_ids` contains more than one id; it must publish `semantic_conflict_unresolved`.
15. The first implemented deterministic path must not publish reference-only focal output when the retained material summary normalizes to empty text; it must publish `context_not_reportable`.

## 11. Observability and Logging

This initial slice keeps observability structural:

1. conscious states preserve workspace, working-state, memory-candidate, material, and feeling provenance,
2. commitment and publication ops summarize owner activity for each cycle,
3. `commit_status` and `no_commit_reason` remain explicit rather than hidden inside absence,
4. supporting-context count remains visible and bounded,
5. forced-consolidation lineage remains visible as an explicit evaluation factor without implying guaranteed final commitment,
6. error types define malformed contract conditions explicitly.

## 12. Validation Strategy

1. Unit test immutable `ConsciousContentMaterial`, `ReportableConsciousContent`, `SupportingContextItem`, and `ConsciousState` contracts.
2. Unit test provenance preservation from workspace, working state, memory candidate, and feeling lineage into conscious outputs.
3. Unit test explicit `committed` versus `no_commit` publication semantics.
4. Unit test the supporting-context cap of two items.
5. Unit test that `no_commit` cycles still publish one formal conscious state.
6. Unit test semantic conscious payload invariants, including required focal summary on committed output.
7. Unit test explicit failure for malformed bridge material.
8. Unit test explicit failure when required commitment capability is unavailable.
9. Unit test that forced-consolidation lineage remains eligible for evaluation but does not guarantee final commitment.
10. Unit test runtime bridge alignment for the full current `WorkspaceCandidateSet` rather than retained ids only.
11. Unit test that the private commitment path cannot observe undeclared cross-cycle state in the first version.
12. Unit test that `no_commit_reason` values stay inside the fixed first-version taxonomy.
13. Unit test that zero retained ids produce `insufficient_commitment_signal` without hidden focal carry-over.
14. Unit test that one retained id produces one committed focal item plus bounded auxiliary supporting context generated inside `08`.
15. Unit test that multiple retained ids produce `semantic_conflict_unresolved` rather than implicit re-ranking.
16. Unit test that whitespace-only retained material produces `context_not_reportable` rather than reference-only commit.