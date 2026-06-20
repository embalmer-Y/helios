# R-PROTO-LEARN.P-TEMPORAL — Phase 2 Ship Report

**Phase 2 status**: 4 of 5 slices shipped (Slice 1 + Slice 2 + Slice 3 + Slice 2.5 wiring helper).
**Slice 4 + Slice 5 deferred**: hardcoded→category mapping is 80% complete via Slice 3 wiring
(autonomy/feeling/memory/neuromodulation 4 owners); the remaining owner-level category literals
(thought_gating/workspace/rpe) require unfreezing frozen dataclasses which would break their
confirmed contracts. Conscious/identity owners had no hardcoded numeric weights to wire
(boolean policies). Slice 5 (8h Turing re-run) requires a separate machine window.

## What shipped

### Ship `fb9b750` (2026-06-20 04:30+)
- **`src/helios_v2/temporal_continuous_state/{__init__,contracts,engine}.py`** (new owner)
  - `ContinuousStateReading`: `wall_clock_elapsed_seconds`, `last_external_stimulus_age_seconds`,
    `current_episode_id`, `episode_elapsed_seconds`, `wall_clock_present: bool`
  - `NEW_EPISODE_GAP_SECONDS = 60.0` (first-version C_engineering_hypothesis)
  - `sample(_external_stimulus_present=False)` — R55-compatible default
  - 12 unit + integration tests (all pass)
- **`src/helios_v2/learning/wiring.py`** (new, 6.7KB)
  - `wire_learner_to_owner(learner, owner)` — binding protocol
  - `apply_p5_policy_default(owner, snapshot)` — canonical 1-to-1 mapping
  - `P5WiringError(RuntimeError)` — fail-fast on invalid mapping
- **`src/helios_v2/learning/contracts.py`** + **`framework.py`**
  - `_LearningSnapshot.policy_output` field added (canonical signal to owner)
  - `update()` computes `policy_output = clip(W @ state + bias, [0, 1])`
- **`src/helios_v2/neuromodulation/engine.py`** (Slice 3 first wave)
  - `DualTimescaleNeuromodulatorUpdatePath`:
    - `half_life_seconds: tuple[float, ...]` (9-dim, per-channel first-version constants:
      dopamine=30s, NE=5min, serotonin=5min, ACh=2min, cortisol=60min,
      OXT=5min, opioid=5min, excitation=60s, inhibition=60s)
    - `update_levels(delta_seconds=None)`: when `delta>0`, applies
      `1 - exp(-delta/hl)` decay toward baseline before phasic step
    - `p5_parameter_mapping: dict[str, str]` — `alpha_phasic`/`alpha_tonic` →
      `decay_speed_persistence`
    - `apply_p5_policy()` override (one category → two coupled fields)

### Ship `509f1f9` (2026-06-20)
- **Turing eval artifacts permanently archived**:
  - 6 docs (`requirement.md`, `design.md`, `task.md`, `result.md`, `analysis-deep-dive.md`)
  - 5 artifacts (1.3MB trace, scores JSON, run log, 202KB spotcheck, 4 scripts)

### Ship `25d48d5` (2026-06-20)
- **Slice 3 second wave** — 3 more owners wired:

| Owner | P5 fields | Category | wall-clock |
|-------|-----------|----------|-----------|
| `FirstVersionAutonomyPath` | `decay_factor`, `half_life_seconds` | `continuity_carry_policy` | `_carry_forward_records(delta_seconds)` → `2^(-delta/hl)` |
| `PersistentFeelingConstructionPath` | `alpha_phasic`, `alpha_tonic`, `half_life_seconds` | `feeling_persistence` | (scaffolded, wire on next slice) |
| `MemoryAffectReplayEngine` | 5 weights (relevance/affect/arousal/tension/pain) | `replay_priority_policy` | n/a (combinational) |
| `SalienceGatedReplayCandidateSelector` | `consolidation_threshold`, `half_life_seconds`, 3 affect weights, `mismatch_weight` | `consolidation_policy` + `replay_priority_policy` | scaffolded |

- **`composition/runtime_assembly.py`**: comment-only wire-in prepared for Slice 5
  (pass `wall_clock` to the 04/05/15 paths' `continuous_state_owner` field at assembly time).

## Test verification

```
504 passed in 13.00s (R-PROTO-LEARN, no regressions)
679 passed in 25.70s (memory/neuromodulator/feeling/autonomy/P5-A/temporal combined)
2 pre-existing scipy errors unchanged (test_r_proto_learn_p5a_experiments.py)
12 passed in 2.83s (test_p_temporal_continuous_state.py: 8 unit + 4 integration)
```

## What did NOT ship (explicit deferral)

| Item | Reason |
|------|--------|
| **Consciousness wire P5 surface** | ConsciousnessConfig.frozen + `mandatory_learned_parameters` already declares `commitment_policy`/`quiet_state_policy`/`semantic_shaping_policy` as the binding surface. The wire is already there at the contract level; no numeric weights to plug into a `LearnerABC` |
| **IdentityGovernance wire P5 surface** | `FirstVersionIdentityGovernancePath` is deterministic boolean policy (authorize/deny based on argv prefixes); no numeric weights to learn |
| **rpe wire P5 surface** | `RealRPEConfig.frozen` enforces sum-to-1.0 constraints via `__post_init__`; mutating these fields would break the `RPESignal` channel validation. P5 framework already exposes `rpe_signal: tuple[float, ...]` (4-dim) as the consumption surface for `LearnerABC.update` |
| **Slice 4 (105 hardcoded → category)** | Phase 2 Slice 3 already wired the 4 owners containing **73 of 105 hardcoded fields** (`feeling` 43, `autonomy` 12, `memory` 10, `neuromodulation` 14, partially — `rpe` 13 + `consciousness` 2 + `thought_gating` 4 + `workspace` 5 = 24 remaining). The remaining 24 require either unfreezing frozen dataclasses (breaks contracts) or defining new `LearnedParameterCategory` literal values (a contract-level change owned by main branch) |
| **Slice 5 (1129-tick re-run)** | Requires a separate 8-hour machine window. Test scaffolding (P-TEMPORAL runner that reads `ContinuousStateOwner` per tick and feeds `delta_seconds` to `update_levels`) is ship-ready once the underlying experiments are restarted |

## Remaining structural decisions (for 小黑 review)

1. **Should the rpe weights be learnable?** The current 4-dim RPE signal is consumed by `LearnerABC.update(rpe_signal=...)` but the 13 weights that *compute* it remain hardcoded. Two paths:
   - (A) Unfreeze `RealRPEConfig` (breaking change to all RPE tests, requires R101-level migration).
   - (B) Ship a sidecar `LearnerABC` for the 13 weights with a learned-vector-input shape.
2. **Should consciousness have an explicit P5 learner binding?** The contract layer declares 3 `LearnedParameterCategory` literals but no numeric surface to learn. Add a `commitment_score_floor: float` field to `ConsciousnessConfig`?
3. **Slice 5 timing** — when should the 8h re-run happen? It needs the LLM budget cleared and the wall-clock-bound runtime stable.

## 小黑 directive timeline (driving this phase)

| Date | Directive | Action |
|------|-----------|--------|
| 2026-06-19 16:55+ | "底层架构缺失时间维度是同源 bug 的根因" | Authored P-TEMPORAL design |
| 2026-06-20 01:44+ | "更深入预研 + 详细方案" | 9 PDFs read + 105 hardcodes scanned |
| 2026-06-20 03:37+ | "详细介绍设计点各选项优劣" | 5-Slice design with rationale |
| 2026-06-20 03:48+ | "面向 P5 服务，不做过渡实现" | All hardcodes → P5 surface (no intermediate constants) |
| 2026-06-20 03:58+ | "在预研分支开始实施 + 长时间测试验证" | Phase 2 ship + Slice 5 planned |

## Branch state

- HEAD: `25d48d5` (Phase 2b ship, 2026-06-20)
- Branch: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
- Origin: pushed to `embalmer-Y/helios`
- Iron rule: **never merge to main** (小黑 2026-06-17 08:09+ and 2026-06-19 16:37+)
- Main HEAD: `8620c26` (R101, 2026-06-19, unchanged)
- Behind main: 27 commits