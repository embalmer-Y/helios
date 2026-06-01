# Requirement 15 - Execution writeback and autobiographical consolidation

## 1. Background and Problem

After `13` and `14`, Helios v2 can define formal action outcomes and formal identity-governance outcomes, but it still lacks a sole owner for how lived runtime results become long-horizon continuity. The final project goal requires not only action and revision decisions, but also experience writeback: visible or blocked external behavior, internal decisions, user/environment feedback, and accepted identity updates must be converted into bounded episodic evidence, autobiographical continuity, and semantic consolidation candidates for future ticks.

Without a dedicated owner, this writeback path would remain scattered across executor callbacks, feedback journals, memory backends, and governance side effects. That would break one of the project's core targets: a continuously running system whose external consequences and internal self-change both become durable, auditable experience rather than isolated events.

This slice corresponds to the transition from formal bridge/governance outcomes into continuity-preserving experience publication and consolidation handoff, not to planner ownership, governance ownership, or raw storage-engine implementation.

## 2. Goal

Create an execution-writeback owner that consumes formal execution outcomes and governance outcomes, publishes immutable experience-writeback results, derives bounded episodic/autobiographical/semantic consolidation candidates, and preserves continuity-critical provenance for later retrieval and self-model evolution without collapsing into planner, identity-governance, or raw storage-backend ownership.

## 3. Functional Requirements

### 3.1 Owner boundary
1. `15` must be the sole owner of post-outcome experience writeback, continuity-preserving publication, and consolidation-candidate assembly in this slice.
2. `15` must remain separate from planner/executor decision ownership, identity-governance judgment ownership, and raw storage-backend ownership.
3. `15` must not reinterpret feedback-journal persistence as sufficient continuity writeback.

### 3.2 Upstream input boundary
1. `15` must accept normalized execution-feedback results from `13` through a documented public contract.
2. `15` must accept normalized governance results and applied identity-state publications from `14` through documented public contracts.
3. `15` may accept quiet-tick, no-externalization, or blocked-externalization summaries later, but only through documented APIs.
4. `15` must not reach through private planner, channel, or identity-governance state.

### 3.3 Experience-writeback publication
1. Every eligible accepted, rejected, failed, or identity-mutating path must be convertible into one formal experience-writeback result.
2. Experience-writeback results must preserve at least source outcome id, origin provenance, outcome class, requested versus applied effect summary, and continuity-relevant reason trace.
3. Rejected or blocked actions must remain representable as lived experience rather than disappearing because no outbound text was sent.
4. Accepted identity revisions must remain representable as self-model experience rather than only as raw store mutation.

### 3.4 Consolidation-candidate ownership
1. `15` must derive bounded consolidation candidates for episodic, autobiographical, and semantic follow-up surfaces.
2. The owner must explicitly distinguish raw event persistence from consolidation candidacy.
3. Consolidation candidates must preserve why an event matters for future recall, identity continuity, or preference learning.
4. The owner must not claim final long-term storage-policy ownership beyond its documented handoff contracts.

### 3.5 Continuity semantics
1. `15` must support continuity-preserving writeback for successful external action, rejected externalization, execution failure, and accepted or rejected self-revision.
2. The owner must support linking an experience writeback to origin thought id, proposal id, decision id, revision id, or equivalent upstream provenance.
3. The owner must preserve whether a path changed the world, changed the self, was blocked, or remained unresolved.
4. The owner must make later retrieval and autobiographical assembly possible without scraping heterogeneous logs.

### 3.6 Separation from raw storage and retrieval
1. `15` may publish storage-ready packets or consolidation handoffs, but it must not own storage backends themselves.
2. `15` may publish retrieval-facing continuity metadata, but it must not own retrieval planning or ranking.
3. `15` must not silently write directly into unrelated memory stores without explicit public contracts.

### 3.7 No fallback behavior
1. Missing required upstream outcome provenance must fail explicitly.
2. `15` must not synthesize fake autobiographical continuity from incomplete or malformed outcomes.
3. `15` must not silently discard blocked, rejected, or failed outcomes that are continuity-relevant.

## 4. Non-Functional Requirements

1. Experience-writeback, consolidation-candidate, and applied-continuity publications must be immutable after publication.
2. Identical upstream outcomes and identical owner state must produce deterministic outputs for the same configured writeback policy.
3. The owner boundary must remain separate from planner, governance, retrieval, and storage-backend owners.
4. Published continuity artifacts must preserve enough provenance to support later retrieval, self-model continuity, and evaluation.

## 5. Code Behavior Constraints
1. Writeback code must not import private planner or channel internals directly.
2. Writeback code must not treat feedback journals as the sole continuity surface.
3. Writeback code must not blur accepted identity mutation and accepted external action into one undifferentiated event class.
4. Writeback code must not silently drop unresolved or blocked experience that matters for later continuity.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/experience_writeback/contracts.py`
2. `helios_v2/src/helios_v2/experience_writeback/engine.py`
3. `helios_v2/src/helios_v2/experience_writeback/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_experience_writeback_contracts.py`
6. `helios_v2/tests/test_experience_writeback_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The package defines a documented API from execution/governance outcomes into formal experience-writeback results.
2. The package defines explicit consolidation-candidate publication contracts.
3. Successful, blocked, failed, and identity-governance outcomes are all representable as continuity writeback.
4. The package records that raw storage backends remain downstream collaborators.
5. The package records that retrieval planning remains outside `15`.

## 8. Implementation Status

Status on 2026-06-01: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/experience_writeback/contracts.py` defines immutable writeback request, continuity-evidence packet, consolidation-candidate, result, and publication-op contracts.
2. `helios_v2/src/helios_v2/experience_writeback/engine.py` defines fail-fast request validation, owner-private `FirstVersionExperienceWritebackPath`, deterministic continuity classification, and bounded episodic/autobiographical/semantic candidate assembly.
3. `helios_v2/src/helios_v2/runtime/stages.py` wires `ExperienceWritebackRuntimeStage` after `13` and `14` through a runtime-owned `ExperienceWritebackRequestProvider`.
4. `helios_v2/tests/test_experience_writeback_contracts.py`, `helios_v2/tests/test_experience_writeback_engine.py`, and `helios_v2/tests/test_runtime_stage_chain.py` cover contract immutability, external-action writeback, blocked-or-failed continuity retention, identity-change writeback, and `13/14 -> 15` runtime chaining.

Validated outcomes:

1. `pytest helios_v2/tests/test_experience_writeback_contracts.py helios_v2/tests/test_experience_writeback_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `16 passed`
2. `pytest helios_v2/tests -q` -> `168 passed`

Implementation note:

1. The current first-version path keeps storage backends and retrieval planning outside the `15` owner boundary while making `executed`, `blocked-or-failed`, `accepted identity change`, and `rejected self-revision` outcomes continuity-visible through formal writeback results and consolidation candidates.
