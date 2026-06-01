# Requirement 19 - Architecture boundary and owner documentation

## 1. Background and Problem

Helios v2 is explicitly requirement-first and owner-boundary-driven. That means documentation is not secondary polish; it is part of the architecture truth. As v2 expands from `01-18`, the project needs a stable documentation owner slice that keeps owner maps, allowed dependencies, migration notes, and prohibited shortcuts aligned with implementation truth.

## 2. Goal

Create the formal v2 documentation baseline that describes owner boundaries, allowed dependency directions, migration-state notes, and prohibited shortcuts in a way that can be used directly by later requirement, design, implementation, and review work.

## 3. Functional Requirements

### 3.1 Boundary-truth documents
1. `19` must define the formal v2 owner/boundary documentation set.
2. The set must cover owner domains, allowed dependencies, explicit non-owned responsibilities, and migration-state notes.
3. Runtime truth and target truth must remain distinguishable.

### 3.2 Cross-document alignment
1. The v2 requirements index, architecture-boundary docs, roadmap docs, and package-level requirements must remain mutually traceable.
2. New requirements must be able to cite the same boundary-truth vocabulary rather than redefining it locally.

### 3.3 Prohibited shortcut documentation
1. The documentation set must record prohibited shortcuts and boundary violations explicitly.
2. Conflicts between current implementation and target owner truth must be recorded, not hidden.

## 4. Non-Functional Requirements

1. Documentation must remain concise, stable, and reviewable.
2. Documentation must not depend on unpublished implementation assumptions.

## 5. Code Behavior Constraints
1. Documentation must not be replaced by README-level summaries.
2. Documentation must not confuse current coupling with intended ownership.

## 6. Impacted Modules
1. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
2. `helios_v2/docs/requirements/index.md`
3. `helios_v2/docs/requirements/16-embodied-subjective-prompt-and-action-autonomy/*`
4. `helios_v2/docs/requirements/17-evaluation-fidelity-and-diagnostic-provenance/*`
5. `helios_v2/docs/requirements/18-subjective-autonomy-and-proactive-evolution/*`
6. `helios_v2/docs/requirements/19-architecture-boundary-and-owner-documentation/*`

## 7. Acceptance Criteria
1. A formal v2 owner/boundary documentation package exists.
2. The package defines traceable alignment rules for requirements and boundary docs.
3. Migration-state conflicts are explicitly representable.

## 8. Implementation Status Snapshot

1. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` now acts as the active v2 boundary-truth document rather than a generic scaffold.
2. The document now records stable owner boundaries, allowed dependency directions, prohibited shortcuts, migration-state notes, and traceability rules for the current stabilized `16-18` owner wave.
3. The requirements index now marks `19` as `baseline_implementation`, and later requirement packages can cite shared boundary vocabulary from the boundary-truth document instead of redefining it locally.

## 9. Validated Outcomes

1. Manual cross-document review completed for `ARCHITECTURE_BOUNDARIES.md` and requirement packages `16`, `17`, `18`, and `19`.
2. Requirements index alignment updated so `19` no longer remains falsely `not_started` after the boundary-truth snapshot landed.
