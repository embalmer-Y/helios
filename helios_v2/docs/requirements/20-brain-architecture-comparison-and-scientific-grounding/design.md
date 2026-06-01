# Requirement 20 - Brain architecture comparison and scientific grounding design

## 1. Design Overview

`20` is a documentation-owner slice that turns the project's brain-inspired ambition into a bounded, evidence-aware comparison layer. It records functional mappings, evidence categories, non-goals, requirement-linked gap analysis, and an owner-wave roadmap for closing the highest-value grounding gaps.

## 2. Target Documentation Set

1. Functional mapping matrix.
2. Evidence-category annotations.
3. Explicit non-goals.
4. Requirement-linked gap analysis.
5. Owner-wave gap roadmap.

## 2.1 Implemented baseline

The current baseline implementation centers on one active artifact plus one traceability package:

1. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` as the active scientific-grounding document.
2. The requirements index as the maturity anchor.
3. Requirement package `20` as the detailed traceable grounding truth for the current snapshot.

## 3. Target Artifacts

1. `FunctionalAnalogyEntry`
2. `EvidenceCategoryEntry`
3. `NonGoalEntry`
4. `RequirementGapEntry`
5. `OwnerWaveRoadmapEntry`

## 4. Implemented Baseline Vocabulary

1. `functional analogy`
2. `engineering substitute`
3. `current absence`
4. `A_stronger_grounding`
5. `B_functional_inspiration`
6. `C_engineering_hypothesis`
7. `explicit non-goal`
8. `requirement-linked gap`
9. `owner-wave roadmap`
10. `wave exit signal`

## 5. Validation Strategy

1. Manual review that major owner domains and major gaps are covered.
2. Manual review that unsupported equivalence claims are absent.
3. Manual review that roadmap ordering follows owner leverage and does not invert requirement dependencies.

## 6. Implemented Baseline Snapshot

1. The active grounding document now distinguishes cautious owner-domain mappings from stronger biological claims instead of leaving that distinction implicit.
2. The document explicitly separates functional analogy, engineering substitute, and current absence so later requirement work cannot quietly turn metaphor into architecture truth.
3. The document now records concrete gap statements that point back to v2 requirements, keeping scientific grounding tied to planning priority rather than broad aspiration.
4. The document now orders those gaps into owner waves with priority rationale and exit signals, so roadmap use stays traceable rather than impressionistic.
