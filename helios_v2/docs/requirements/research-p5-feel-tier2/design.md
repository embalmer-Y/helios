# R-PROTO-LEARN Tier 2 — 行为对位 (Design)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## Architecture (consistent with Tier 1)

```
helios_v2/learning/                       (existing, shared framework)
├── contracts.py                          (LearnerConfig, Regime, Learner)
├── framework.py                          (LearnerABC + numpy pinv closure)
├── memory_learner.py                     (R11)
├── thought_gating_learner.py             (R12)
├── retrieval_learner.py                  (R13)
├── internal_thought_learner.py           (R14)
├── autonomy_learner.py                   (R15)
├── action_externalization_learner.py     (R16) ← NEW
└── evaluation_learner.py                  (R17) ← NEW
```

## R16 — owner 12 action_externalization

**Mandatory learned parameters (3)**:
- `normalization_policy` — when to take a thought and prepare it for
  outbound (intensity filter, format selection, scope decision)
- `bridge_evidence_policy` — when equivalent-evidence-only is acceptable
  (LLM hasn't produced explicit candidate_channels / target_user_id)
- `bridge_rejection_policy` — when to hard-reject (schema mismatch,
  scope conflict)

**3 policies → 9-dim output**:
```
output[0:3] = normalization_policy
    (3 dims: intensity_scaling × scope_decision × format_priority)
output[3:6] = bridge_evidence_policy
    (3 dims: minimum_evidence_score × equivalent_threshold × signal_strength)
output[6:9] = bridge_rejection_policy
    (3 dims: schema_strictness × scope_conflict_sensitivity × rejection_threshold)
```

**Input** (7-dim):
- action_intensity (0-1): how strong the proposed action is
- proposal_scope ("internal" or "external" → mapped to 0.0/1.0)
- candidate_channel_count (0-1, normalized)
- evidence_count (0-1)
- dopamine (0-1, confidence signal)
- acetylcholine (0-1, flexibility)
- novelty (0-1)

Wait — R16 needs 7 input dims to match framework's 7-dim signal protocol.
Let me reconsider:
- input_dim = 7 (action_intensity, scope, candidate_channels, evidence,
  dopamine, ach, novelty)
- output_dim = 9 (3 policies × 3 dims)

**Academic mapping**:
- Kotseruba 2018 self-regulation: normalization_policy picks how to
  package the action
- Parisi 2019 intrinsic motivation: bridge_evidence_policy decides if
  low-confidence is acceptable (curiosity-driven exploration)
- Kotseruba 2018 self-observation: bridge_rejection_policy enforces
  hard constraints

## R17 — owner 17 evaluation

**Mandatory learned parameters (3)**:
- `fidelity_scoring_policy` — how to score execution fidelity (did
  the action match the proposal?)
- `gap_analysis_policy` — how to identify gaps between proposal and
  execution (3 categories: missing, partial, divergent)
- `long_range_diagnostic_policy` — how to roll up diagnostics across
  session windows (trend, drift, regression)

**3 policies → 8-dim output**:
```
output[0:3] = fidelity_scoring_policy
    (3 dims: execution_match × signal_alignment × temporal_fidelity)
output[3:5] = gap_analysis_policy
    (2 dims: missing_threshold × partial_threshold)
output[5:8] = long_range_diagnostic_policy
    (3 dims: window_size × trend_sensitivity × drift_threshold)
```

**Input** (7-dim):
- execution_fidelity (0-1): how well execution matched proposal
- evidence_count (0-1)
- dopamine (0-1, confidence in claim)
- acetylcholine (0-1, flexibility in updating scores)
- novelty (0-1, new context)
- session_tick (0-1, normalized to window position)
- cross_session_drift (0-1, accumulated drift signal)

**Academic mapping**:
- Kotseruba 2018 self-observation: fidelity_scoring_policy is the
  observation layer
- Kotseruba 2018 self-analysis: gap_analysis_policy classifies where
  the gap is
- Parisi 2019 continual learning: long_range_diagnostic_policy is the
  "did the system regress" detector

## W Matrix Sizing

| Learner | input_dim | output_dim | Closure |
|---|---|---|---|
| R16 action_externalization | 7 | 9 | rank-7 best-effort (residual ~0.3-0.5) |
| R17 evaluation | 7 | 8 | rank-7 best-effort (residual ~0.2-0.4) |

## Smoke Strategy

- 2 owner × 8 ticks each
- Use synthetic LLM appraisal tuple (7-dim) → mapped to owner-specific
  features via the `_llm_signal_to_target_vec` adapter
- Verify: residual trend, regime progression, commit count

## Constraint Adherence

- **No main baseline mutation**: 2 new files in `helios_v2/learning/`,
  no `helios_v2/action_externalization/` or `helios_v2/evaluation/`
  imports from `learning/`.
- **Sidecar observer**: Tier 2 is for demonstrating the framework
  applies to behavior owners. Real integration with owner 12 / 17
  engines is **out of scope** for this slice (Tier 2 不接入 engine).
- **R21 ad-hoc logging guard**: no `print(` / `import logging` in
  `src/`.

## File Touch List

```
src/helios_v2/learning/
├── action_externalization_learner.py     (NEW, R16)
└── evaluation_learner.py                  (NEW, R17)

tests/
├── test_r_proto_learn_16_action_externalization_learner.py  (NEW)
└── test_r_proto_learn_17_evaluation_learner.py              (NEW)

scripts/
└── r_proto_learn_tier2_smoke.py          (NEW, 2 owner smoke)
```
