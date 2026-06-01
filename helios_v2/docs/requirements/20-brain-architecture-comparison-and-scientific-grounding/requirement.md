# Requirement 20 - Brain architecture comparison and scientific grounding

## 1. Background and Problem

Helios v2 is explicitly aimed at a brain-inspired architecture, but that goal must remain scientifically grounded and bounded. Without a formal documentation owner slice for cautious comparison and grounding, discussions of "brain-like" risk becoming marketing language, while requirement priority risks drifting away from the actual functional gaps that matter.

## 2. Goal

Create the formal scientific-grounding documentation package for v2 that maps owner domains to cautious brain-function analogs, explicit non-goals, evidence categories, and requirement-linked gap analysis.

## 3. Functional Requirements

### 3.1 Cautious functional mapping
1. `20` must map major v2 owner domains to cautious brain-function analogs.
2. The package must distinguish functional analogy, engineering substitute, and current absence.
3. The package must not claim one-to-one organ equivalence.

### 3.2 Evidence categories
1. The package must distinguish stronger evidence, functional inspiration, and engineering hypothesis.
2. Literature references must support architecture reasoning rather than promotional claims.

### 3.3 Requirement-linked gap analysis
1. Scientific grounding must produce an explicit gap list.
2. Each major gap must trace back to one or more v2 requirements.
3. Explicit non-goals must be recorded to prevent scope inflation.

### 3.4 Owner-wave roadmap
1. The package must convert major grounding gaps into an explicit owner-wave roadmap rather than leaving them as an unprioritized list.
2. Each wave must name the owner slice it depends on, the grounding claim it strengthens, and the gap it is expected to narrow.
3. The roadmap must remain subordinate to requirement truth and must not replace concrete requirement packages.

## 4. Non-Functional Requirements

1. Documentation must remain professionally cautious.
2. Scientific grounding must support architecture prioritization directly.

## 5. Code Behavior Constraints
1. Scientific grounding must not replace software architecture documents.
2. Unsupported brain-region equivalence claims are prohibited.

## 6. Impacted Modules
1. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
2. `helios_v2/docs/requirements/20-brain-architecture-comparison-and-scientific-grounding/*`
3. `helios_v2/docs/requirements/index.md`
4. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 7. Acceptance Criteria
1. A formal v2 scientific-grounding package exists.
2. The package maps owner domains to cautious analogs and explicit gaps.
3. Major gaps trace back to v2 requirements.
4. Major gaps are ordered into an explicit owner-wave roadmap.

## 8. Implementation Status Snapshot

1. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` now acts as the active v2 scientific-grounding document rather than leaving grounding only in an outer-repo working draft.
2. The R20 package now formalizes evidence categories, explicit non-goals, cautious owner-domain mappings, and requirement-linked gap analysis for the current implemented and near-term v2 owner set.
3. The active grounding document now also carries an owner-wave gap roadmap that orders current scientific-grounding deficits by owner leverage instead of treating them as a flat list.
4. The requirements index now marks `20` as `baseline_implementation`, so grounding progress no longer remains falsely `not_started` after the active comparison document landed.

## 9. Validated Outcomes

1. Manual cross-document review completed for `BRAIN_ARCHITECTURE_COMPARISON.md`, `ARCHITECTURE_BOUNDARIES.md`, and requirement packages `17`, `18`, `19`, and `20`.
2. Requirements index alignment updated so `20` now matches the landed documentation slice.
