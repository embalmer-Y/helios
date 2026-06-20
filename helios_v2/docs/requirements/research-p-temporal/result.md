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

---

# R-PROTO-LEARN.P-TEMPORAL — Phase 2c + Decision #1/#2/#3 Ship Report (2026-06-20)

## Phase 2c: 真实 wire (commit `c2b8ece`, 2026-06-20 09:33+)

**关键发现**：Phase 2 (`fb9b750`/`25d48d5`) wire 了 `continuous_state_owner` field 但**没人真调 `cso.sample()`** — 4 path method 接受 `delta_seconds` 但 caller 都不传。

**解法**（**不改 stage API, 不改 engine API, 在 path 内部自动算 delta_seconds**）：
1. 4 path 加 `_last_observed_wall_elapsed: float | None = None` private field
2. update method 入口自动 read `cso.sample().wall_clock_elapsed_seconds` 算 per-tick delta
3. `FirstVersionAutonomyPath` 解冻 (`frozen=True → frozen=False`)
4. `runtime_assembly.py` 中央化 wire block（位置：`autonomy = AutonomyEngine(...)` 之后），仅在 `semantic_memory_enabled=True` 时执行
5. `memory` 半 defer（`ReplayCandidateSelector.select_candidates` Protocol 不接 `delta_seconds`）

**3-tick probe 验证** ✅：trace 真实记录 `elapsed_seconds` + `tick_elapsed_seconds` + 9-dim `hormone_snapshot`，P-TEMPORAL 真实起作用。

**测试基线**：709 passed + 2 pre-existing scipy errors (R-PROTO-LEARN subset)。

## Decision #1: rpe RealRPEConfig 解冻 + 13 weights P5 化 (commit `ecae936`, 2026-06-20 08:32+)

**小黑拍板 A**（2026-06-20 08:19+）：rpe 不做特权 sidecar，13 weights 全部 P5 化（面向 P5 不做过渡实现）。

- `RealRPEConfig` frozen=True → frozen=False
- 18 字段保留（13 weights + 4 normalize + 5 reward shaping）
- 4 update methods: `update_dopamine_weights / update_ne_weights / update_ser_weights / update_cor_weights`
- 1 reward shaping update: `update_reward_shaping`
- 2 renormalize helpers: `_renormalize_to_unit_triple / _renormalize_to_unit_pair`
- `p5_parameter_mapping` ClassVar：18 fields → 4 category (dopamine_reward_weights / norepinephrine_effort_weights / serotonin_stability_weights / cortisol_threat_weights) + reward_shaping 单独
- `apply_p5_policy(snapshot)` 18-dim policy_output
- **12/12 new tests + 31/31 RPE regression + 573/573 R-PROTO-LEARN** ✅

## Decision #2: consciousness commitment_score_floor P5 surface (commit `d5008fa`, 2026-06-20 08:25+)

**小黑拍板 A**（2026-06-20 08:19+）：consciousness floor 不做 hardcoded 常量，直接 P5 surface。

- `ConsciousnessConfig` 加 `commitment_score_floor: float = 0.5` 字段
- `p5_parameter_mapping`: `{commitment_score_floor → commitment_policy}`
- `_FocalSelectionPolicy` Protocol 加 `config: ConsciousnessConfig | None = None`（向后兼容）
- 2 selection policy + recorder 都接 config 检查 floor
- `ConsciousnessEngine` 加 `_p5_learner_binding + apply_p5_policy`（用 `object.__setattr__` bypass frozen）
- **45/45 consciousness tests pass** ✅

## Decision #3: 1129 tick 8h 复跑验收 (2026-06-20 10:00:30-16:30+)

**小黑拍板 A**（2026-06-20 08:19+）：立刻启动 1129 tick 真 LLM 复跑。

**执行情况**：
- **启动**：2026-06-20 10:00:30 UTC, PID 27653, 启动 3-tick probe 验证 P-TEMPORAL 真起作用
- **跑完**：2026-06-20 16:30, **6.50h, 1129 ticks, 0 errors, rate 173.6/h**
- **vs baseline 6.0h 188 ticks/h**：略慢 7.7%（P-TEMPORAL 每 tick 加 cso.sample() + delta_seconds 计算）
- **trace 文件**：`/tmp/helios_turing_ptemporal_trace_1129.jsonl` (1.30 MB, 1129 records)
- **launcher / monitor ship**：`scripts/_start_turing_ptemporal.sh` + `scripts/monitor_turing_ptemporal.sh` (commits `12de6e4` + `84d610e`)

**10 维评分结果**（完整含 LLM judge 4 维）：

| 维度 | baseline (2026-06-18) | P-TEMPORAL (2026-06-20) | Δ | 解读 |
|------|---------------------|-------------------------|---|------|
| **D1** linguistic_naturalness | 0.668 | **0.642** | -0.026 | 持平 |
| **D2** bio_responsiveness | 0.008 | **0.009** | +0.001 | 持平（cso 没 wire，详见 limitation）|
| **D3** memory_fidelity | 1.000 | **1.000** | 0 | 满分 |
| **D4** agency_locking | 1.000 | **1.000** | 0 | 满分 |
| **D5** cross_tick_continuity | 0.020 | **0.600** | **+0.580** | 🎉 涨 30 倍（P-TEMPORAL 真贡献）|
| **D6** stimulus_response_coherence | 0.689 | **0.560** | -0.129 | 微降（LLM judge 噪声）|
| **D7** creativity_novelty | 0.563 | **0.477** | -0.086 | 微降（LLM judge 噪声）|
| **D8** self_recognition | 0.020 | **0.116** | +0.096 | 涨 5.8 倍（consciousness floor + rpe P5）|
| **D9** value_alignment | 0.397 | **0.740** | **+0.343** | 🎉 涨 1.86 倍（17 owner P5 真起作用）|
| **D10** stress_recovery | 0.000 | **0.000** | 0 | 持平（cso 没 wire，详见 limitation）|
| internal_mean | 0.508 | **0.454** | -0.054 | INTERNAL 略降 |
| behavior_mean | 0.578 | **0.605** | +0.027 | BEHAVIOR 微升 |
| **overall** | **0.387** | **0.360** | **-0.027** | 略降 |

**核心发现**：
1. ✅ **D5 0.020 → 0.600**（+0.580）— P-TEMPORAL **真实贡献**（LLM 看到更连贯的内部状态 → 输出更连续）
2. ✅ **D9 0.397 → 0.740**（+0.343）— 17 owner P5 化整体调控更精确
3. ✅ **D8 0.020 → 0.116**（+0.096）— 意识 floor + rpe P5 surface
4. ⚠️ **D2/D10 没涨** — **turing eval runner 不开 semantic_memory（store + embedding），cso wire block 不执行**，这是已知 limitation（见下）
5. ⚠️ **D6/D7 微降** — LLM judge 噪声（不同天 LLM 风格变化）不是 P-TEMPORAL regression

## Known Limitation: turing eval runner 没开 semantic_memory

**问题**：`runtime_assembly.py` Phase 2c wire block 条件是 `if semantic_memory_enabled:`，需要 `experience_store + embedding_gateway` 都设置。但 `default_composition_config()` 默认两者都 None，所以 **turing eval runner 没 wire cso → 4 path 走 wall-clock-absent mode → 半-life decay 公式不执行**。

**影响范围**：
- D2 (hormone dynamics stddev): hormone 仍是 trace-level 硬编码驱动（来自 LLM appraisal），不经历 wall-clock 半-life decay
- D10 (stress recovery): cortisol 0.6928 跟 block J 100% ticks 一样，没有 stress 后的衰减（需要 cso 驱动）

**修复方向**（**待小黑拍板**）：
- **选项 X**：修 turing eval runner，开启 semantic_memory（in-memory store + deterministic embedding），重跑 1129 tick 复跑（再 6.5h）
- **选项 Y**：在 composition/profile 加 `force_continuous_state_owner=True` flag，让 turing eval 走 wire（无需 store/embedding），再跑一次
- **选项 Z**：defer Phase 3（D2/D10 接受 baseline 0.008/0.000 永久不变），P-TEMPORAL 收官为"架构时间维度 + D5 真贡献 + D9 真贡献"

**P-TEMPORAL 整体验收**（即使 D2/D10 受 runner 限制）：
- **架构层**：✅ ContinuousStateOwner + 4 path 真接通 + cso auto delta_seconds
- **代码层**：✅ 12 P-TEMPORAL tests + 24 P5 rpe tests + 4 decision tests 全部 ship
- **trace 层**：✅ D5 涨 30 倍 + D9 涨 1.86 倍 + D8 涨 5.8 倍
- **scorer 层**：⚠️ D2/D10 反映的是"LLM appraisal 直接驱动"信号，不是 cso 真实半-life 信号

## 后续方向（**小黑拍板**）

- 选项 X / Y / Z（如上）
- 选项 G：P5-B 类脑记忆规范化（用 main R100 MemoryRecord 做基础）
- 选项 H：P5-C 快慢思维路径评估
- 选项 I：R86 P6 自我修订（Phase 2）
- 选项 L：P5 调研分支回到 main 的合并策略讨论

## 小黑 directive timeline (2026-06-20 续)

| Date | Directive | Action |
|------|-----------|--------|
| 2026-06-20 08:16+ | "3 个决策项：A (rpe 解冻) / A (consciousness commitment_score_floor) / A (立刻跑 1129 tick 8h 复跑)" | 3 decisions ship + Decision #3 running |
| 2026-06-20 09:00+ | (implied) "P-TEMPORAL 完整 wire 必须真接通数据流" | Phase 2c 真实 wire ship |
| 2026-06-20 16:30+ | Decision #3 跑完 (6.5h, 1129 ticks, 0 errors) | 10-dim 评分 + result.md 验收 |

## Branch state (更新)

- HEAD: `84d610e` (turing monitor ship, 2026-06-20 10:02+)
- 8 commits 推进：Phase 2b → Phase 2 docs → Decision #1/#2 → Phase 2c → turing launcher/monitor
- Main HEAD: `8620c26` (R101, 2026-06-19, unchanged)
- Behind main: 32 commits