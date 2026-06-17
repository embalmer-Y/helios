# R-PROTO-LEARN Tier 3 — 协议对位 (Design)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`

## Architecture (consistent with Tier 1+2)

```
helios_v2/learning/                          (existing, shared framework)
├── contracts.py                             (LearnerConfig, Regime, Learner)
├── framework.py                             (LearnerABC + numpy pinv closure)
├── memory_learner.py                        (R11)
├── thought_gating_learner.py                (R12)
├── retrieval_learner.py                     (R13)
├── internal_thought_learner.py              (R14)
├── autonomy_learner.py                      (R15)
├── action_externalization_learner.py        (R16)
├── evaluation_learner.py                    (R17)
├── workspace_learner.py                     (R18) ← NEW
├── outward_expression_learner.py            (R19) ← NEW
├── outward_expression_externalization_learner.py  (R20) ← NEW
└── prompt_contract_learner.py               (R20b) ← NEW
```

## R18 — owner 07 workspace

**Mandatory learned parameters (3)**:
- `competition_policy` — when candidates compete for activation
- `candidate_retention_policy` — when to keep vs discard candidates
- `working_state_update_policy` — how to integrate new signal into
  working state

**3 policies → 9-dim output**:
```
output[0:3] = competition_policy
    (3 dims: activation_threshold × novelty_boost × conflict_penalty)
output[3:6] = candidate_retention_policy
    (3 dims: retention_score × decay_rate × promotion_threshold)
output[6:9] = working_state_update_policy
    (3 dims: integration_strength × signal_decay × revision_threshold)
```

**Input** (7-dim):
- candidate_count, signal_strength, dopamine, ach, novelty,
  working_state_size, cross_tick_carry

**Academic mapping**:
- Kotseruba 2018 global workspace theory (Baars 1988):
  `competition_policy` is the activation competition
- Parisi 2019 transfer learning: `candidate_retention_policy` is the
  cross-tick carry decision

## R19 — owner 16a outward_expression

**Mandatory learned parameters (3)**:
- `delivery_guidance_policy` — how to compose the LLM-visible draft
- `boundary_rendering_policy` — what governance bounds to render
  into the prompt
- `draft_publication_policy` — when to publish the draft (vs hold)

**3 policies → 9-dim output**:
```
output[0:3] = delivery_guidance_policy
    (3 dims: tone_strength × detail_level × persona_emphasis)
output[3:6] = boundary_rendering_policy
    (3 dims: governance_strictness × identity_signal × constraint_depth)
output[6:9] = draft_publication_policy
    (3 dims: publication_threshold × cooling_off × revision_pressure)
```

**Input** (7-dim):
- draft_intensity, governance_pressure, identity_strength,
  dopamine, ach, novelty, last_publish_tick

**Academic mapping**:
- Kotseruba 2018 self-observation: `delivery_guidance_policy` is the
  observation layer that styles the output
- Helios R80 governance: `boundary_rendering_policy` is the
  governance signal that shapes the system prompt

## R20 — owner 16b outward_expression_externalization

**Mandatory learned parameters (3)**:
- `envelope_rendering_policy` — how to format the message for the
  channel (text/voice/etc.)
- `delivery_selection_policy` — which channel to use
- `execution_boundary_policy` — what execution safety bounds apply

**3 policies → 9-dim output**:
```
output[0:3] = envelope_rendering_policy
    (3 dims: format_alignment × length_pressure × format_priority)
output[3:6] = delivery_selection_policy
    (3 dims: channel_weight × signal_strength × fall_back_score)
output[6:9] = execution_boundary_policy
    (3 dims: safety_strictness × identity_signal × constraint_depth)
```

**Input** (7-dim):
- envelope_priority, channel_availability, safety_pressure,
  dopamine, ach, novelty, last_execution_tick

**Academic mapping**:
- Parisi 2019 transfer learning: `delivery_selection_policy` is the
  transfer of internal representation to a public channel
- Helios R80 governance: `execution_boundary_policy` is the safety
  bound

## R20b — owner prompt_contract

**Mandatory learned parameters (3)**:
- `layering_policy` — how many prompt layers to assemble
- `anti_theatrical_policy` — how aggressively to suppress
  theatrical/persona performance
- `action_boundary_policy` — what action boundary to render into
  the system prompt

**3 policies → 9-dim output**:
```
output[0:3] = layering_policy
    (3 dims: layer_count × layer_ordering × layer_depth)
output[3:6] = anti_theatrical_policy
    (3 dims: suppression_strength × authenticity_weight × risk_threshold)
output[6:9] = action_boundary_policy
    (3 dims: action_strength × boundary_strictness × fallback_path)
```

**Input** (7-dim):
- context_complexity, persona_drift_signal, action_pressure,
  dopamine, ach, novelty, last_pressure_tick

**Academic mapping**:
- Helios R79-R80 governance: `anti_theatrical_policy` directly
  encodes the no-theater constraint
- Kotseruba 2018 self-regulation: `layering_policy` decides how to
  structure the prompt layers

## W Matrix Sizing

| Learner | input_dim | output_dim | Closure |
|---|---|---|---|
| R18 workspace | 7 | 9 | rank-7 best-effort (residual ~0.3-0.5) |
| R19 outward_expression | 7 | 9 | rank-7 best-effort (residual ~0.3-0.5) |
| R20 outward_expression_externalization | 7 | 9 | rank-7 best-effort |
| R20b prompt_contract | 7 | 9 | rank-7 best-effort |

## Smoke Strategy

- 4 owner × 8 ticks each
- Use synthetic LLM appraisal tuple (7-dim) → mapped to owner-specific
  features via the `_llm_signal_to_target_vec` adapter
- Verify: residual trend, regime progression, commit count
- Real LLM smoke: 3 blocks, varied Chinese scenarios

## Constraint Adherence

- **No main baseline mutation**: 4 new files in `helios_v2/learning/`,
  no `helios_v2/workspace/`, `outward_expression/`,
  `outward_expression_externalization/`, or `prompt_contract/`
  imports from `learning/`.
- **Sidecar observer**: Tier 3 is for demonstrating the framework
  applies to protocol owners. Real integration with engine is
  **out of scope** for this slice.
- **R21 ad-hoc logging guard**: no `print(` / `import logging` in
  `src/`.

## File Touch List

```
src/helios_v2/learning/
├── workspace_learner.py                       (NEW, R18)
├── outward_expression_learner.py              (NEW, R19)
├── outward_expression_externalization_learner.py  (NEW, R20)
└── prompt_contract_learner.py                 (NEW, R20b)

tests/
├── test_r_proto_learn_18_workspace_learner.py
├── test_r_proto_learn_19_outward_expression_learner.py
├── test_r_proto_learn_20_outward_expression_externalization_learner.py
└── test_r_proto_learn_20b_prompt_contract_learner.py

scripts/
└── r_proto_learn_tier3_real_llm_smoke.py
```
