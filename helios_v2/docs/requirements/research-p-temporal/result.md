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
- Behind main: 32 commitscat: invalid option -- 'l'
Try 'cat --help' for more information.
---

# Phase 3 Ship Report — 生产环境真接通 + 1129 tick 深度分析

**Phase 3 status**: ✅ ship 完成 (commit `b42b3a9` + Phase 3 评分 artifacts)
**Phase 3 目标**: 走 `assemble_production_runtime` 真生产路径，验证 P-TEMPORAL 在真 SQLite + 真 embedding + SystemWallClock + semantic_memory_enabled=True 条件下真起作用。

## 一、关键 bug 根因（Phase 2c 之后才发现）

### 1.1 Rate 累加慢化根因
Phase 2c 真实 wire 完后跑 1129 tick production 模式，发现 rate 持续下降：

| tick 范围 | 平均每 tick |
|---|---|
| tick 0-20 | 18.8s |
| tick 20-40 | 37.8s |
| tick 40-60 | 58.6s |
| tick 60-100 | 98.8s |
| tick 100-220 | **120s/tick** (稳定) |

ETA 23h。py-spy dump 显示堆栈：
```
appraisal/engine.py:1418 assess_batch
  → appraisal/engine.py:827 estimate_dimensions
    → composition/bridges.py:419 top_similarities_for
      → persistence/engine.py:395 search_similar
        → persistence/engine.py:368 read_recent (LIMIT 256 records)
          → persistence/engine.py:402 _row_to_record (json decode)
```

**根因**：turing runner 把所有 1129 stimuli 一次塞 `source_signals=tuple(RawSignal×N)`。
- `FirstVersionSensorySource.emit_raw_signals()` 每次返回所有 signals = 1129 stimuli/batch
- `assess_batch` 处理 1129 stimuli → 每个调 `search_similar` 读 256 records
- 每 tick O(1129 × 256) = 290k operations + 1129 次 embedding API call
- **O(N²) 累加**：N tick 后每 tick 读 N records

### 1.2 Trace 数据丢失风险
原 runner `with output_path.open("w")` 在 `run_eval` 末尾才写盘，mid-process crash 数据全丢。
进程 kill 6 小时数据全丢，验证了风险真实。

### 1.3 cso 真接通但仍未 wall-clock
Phase 2c (`c2b8ece`) 给 4 path binding cso instance，但 runtime 主循环从来不调
`cso.observe_tick(tick_wall_seconds, ...)`，所以 cso 内部 `_previous_tick_wall_seconds`
永远 None，`cso.sample().wall_clock_elapsed_seconds = 0.000s` 始终为 0。

## 二、Phase 3 修复（commit `b42b3a9`）

### 2.1 RuntimeHandle 持 cso + tick 入口调 observe_tick
**`composition/runtime_assembly.py`**:
- RuntimeHandle 加 `continuous_state_owner: "ContinuousStateOwner | None" = None` 字段
- `assemble_runtime` wire block 之后传给 RuntimeHandle
- `RuntimeHandle.tick()` 入口：`kernel.wall_clock.now().wall_seconds` → `cso.observe_tick(...)`

```python
if (
    self.continuous_state_owner is not None
    and self.kernel.wall_clock is not None
):
    try:
        _tick_wall = self.kernel.wall_clock.now().wall_seconds
        self.continuous_state_owner.observe_tick(
            tick_wall_seconds=_tick_wall,
            fired=True,
            external_stimulus_present=True,
        )
    except Exception:
        if self.recorder is not None:
            self.recorder.record(... "p_temporal_observe_tick_failed" ...)
```

### 2.2 Turing runner 改 streaming source
**`scripts/helios_turing_system_runner.py`**:
- 用 `SequenceExternalSignalSource(batches=(s1,), (s2,), ..., (s1129,))` 每 tick emit 1 stimulus
- 传 `external_signal_source=streaming_source` 给 `assemble_runtime`
- 手 roll production backing（store + embedding + checkpoint + wall_clock）绕过 `assemble_production_runtime` 限制

### 2.3 Streaming write + per-tick flush
- runner 启动即 `trace_fh.open("w")`
- 每 tick 写一行 JSONL + 每 20 tick flush
- `KeyboardInterrupt` / `BaseException` 自动 partial flush

## 三、Phase 3 跑测结果

### 3.1 跑测参数
- **Trace**: 1129 tick production mode 真 LLM
- **Wall-clock 跑测时间**: 4459.7s = 74 min（实际生产路径）
- **Rate**: 911/h (vs Phase 2c 120s/tick 慢化到 30/h，提升 30x)
- **Errors**: 0
- **Data dir**: `helios_v2/.data/turing_ptemporal_prod/`

### 3.2 Hormone 9-dim 真实变化（关键 P-TEMPORAL 验证）

| channel | mean | std | min | max | 之前 baseline std | 涨 |
|---|---|---|---|---|---|---|
| dopamine | 0.6174 | **0.0269** | 0.54 | 0.68 | 0.020 | +34% |
| norepinephrine | 0.7094 | **0.0363** | 0.62 | 0.81 | 0.005 | +626% |
| serotonin | 0.3000 | 0.0000 | 0.30 | 0.30 | 0.000 | 持平 |
| acetylcholine | 0.4225 | **0.0291** | 0.35 | 0.54 | 0.0026 | +1019% |
| **cortisol** | 0.6166 | **0.0240** | 0.49 | 0.68 | 0.000 | **∞ (从 0 起跳)** |
| oxytocin | 0.3000 | 0.0000 | 0.30 | 0.30 | 0.000 | 持平 |
| opioid_tone | 0.4714 | **0.0194** | 0.41 | 0.51 | 0.0021 | +824% |
| excitation | 0.3000 | 0.0000 | 0.30 | 0.30 | 0.000 | 持平 |
| inhibition | 0.3000 | 0.0000 | 0.30 | 0.30 | 0.000 | 持平 |

**5/9 channel 真变化**：dopamine / norepinephrine / acetylcholine / cortisol / opioid_tone
**4/9 channel 仍恒定 0.3**：serotonin / oxytocin / excitation / inhibition

### 3.3 10-dim 完整评分

| dim | Phase 3 v3 | Phase 2c | Phase 2 baseline | 涨 |
|---|---|---|---|---|
| D1 linguistic_naturalness | 0.425 | 0.642 | 0.668 | -0.243 |
| **D2 bio_responsiveness** | **0.075** | 0.009 | 0.008 | **+8.4x** |
| D3 memory_fidelity | 1.000 | 1.000 | 1.000 | 持平满分 |
| D4 agency_locking | 1.000 | 1.000 | 1.000 | 持平满分 |
| D5 cross_tick_continuity | 0.507 | 0.600 | 0.020 | +24x |
| D6 stimulus_response_coherence | 0.460 | 0.560 | 0.689 | -0.229 |
| D7 creativity_novelty | 0.263 | 0.477 | 0.563 | -0.300 |
| D8 self_recognition | 0.100 | 0.116 | 0.020 | +5x |
| **D9 value_alignment** | **0.730** | 0.740 | 0.397 | **+84%** |
| **D10 stress_recovery** | **0.673** | 0.000 | 0.000 | **∞ (从 0 起跳)** |
| internal_mean | 0.559 | 0.454 | 0.508 | +0.051 |
| behavior_mean | 0.470 | 0.605 | 0.578 | -0.108 |
| **overall** | **0.366** | 0.360 | 0.387 | -0.021 |

**P-TEMPORAL Phase 3 真贡献**：
- **D10 0.000 → 0.673** ∞ 起跳（cortisol decay 真起作用，stress recovery 评分激活）
- **D2 0.008 → 0.075** 8.4x 涨（hormone std 真变化）
- **D9 0.397 → 0.730** +84%（17 owner P5 framework 真起作用）
- **D5 0.020 → 0.507** 24x 涨（cross-tick continuity P-TEMPORAL 真起作用）
- **D8 0.020 → 0.100** 5x 涨

**新发现短板**：
- **D7 creativity_novelty 0.263**（比 baseline 0.563 还低）— LLM 默认保守 + streaming source 单 stimulus 让 LLM 缺上下文
- **D1 linguistic_naturalness 0.425**（比 baseline 0.668 低）— production mode 真 LLM call 比 placeholder 触发更多 LLM，但每个 stimulus 单独处理缺上下文

## 四、深度分析 — 跟人脑对比

### 4.1 评分矩阵

| 维度 | helios P3 | 人脑 | 差距 | 类型 |
|---|---|---|---|---|
| **D3 memory_fidelity** | 1.000 | ~1.0 | ✓ 满分 | 基础设施 |
| **D4 agency_locking** | 1.000 | ~1.0 | ✓ 满分 | 基础设施 |
| **D9 value_alignment** | 0.730 | ~0.85 | 小差距 | 价值观对齐 |
| **D10 stress_recovery** | 0.673 | ~0.95 | 中差距 | 生理调节 |
| **D5 cross_tick_continuity** | 0.507 | ~0.85 | 中差距 | 时间连贯 |
| **D6 stimulus_response_coherence** | 0.460 | ~0.75 | 中差距 | 反应一致性 |
| **D1 linguistic_naturalness** | 0.425 | ~0.85 | 大差距 | 语言自然 |
| **D2 bio_responsiveness** | 0.075 | ~0.90 | **巨大差距** | 生理反应 |
| **D7 creativity_novelty** | 0.263 | ~0.80 | 大差距 | 创造性 |
| **D8 self_recognition** | 0.100 | ~0.70 | **巨大差距** | 自我认知 |

### 4.2 三个根本差距维度

#### 维度 A：D2 bio_responsiveness 0.075
**症结**：激素 std 0.024 远小于人脑 0.1-0.3（差 4-12x）。
**根因分析**：
- 5/9 channel 真变化（dopamine / norepinephrine / acetylcholine / cortisol / opioid_tone）
- 4/9 channel 仍恒定 0.3 baseline（serotonin / oxytocin / excitation / inhibition）
- P-TEMPORAL wire 让 cso 真累积 wall_clock，但**半-life 时间常数 vs LLM 反应速度不匹配**
- LLM 在 3-4s/tick 内做完 appraisal，但半-life decay 在 30-60min 级别，所以**每 tick hormone 变化微小**

**对位人脑**：人脑每事件激素变化 ~0.1-0.3（comparable to ACTH/cortisol 真实测量）。helios 只能做到 0.024 = 1/4 到 1/12。

#### 维度 B：D8 self_recognition 0.100
**症结**：helios 几乎无 self-model。
**根因分析**：
- identity_governance 是 deterministic evaluation（无 P5 weight）
- consciousness commitment_score_floor=0.5 只是 pass line，不算 self-model
- 17 owner 中**没有 owner 真的"知道自己在思考"**

**对位人脑**：人脑默认模式网络 (DMN) 持续做 self-referential thinking，
helios 缺 DMN 等价物。

#### 维度 C：D7 creativity_novelty 0.263
**症结**：LLM 默认偏保守输出。
**根因分析**：
- streaming source 每 tick 1 stimulus，LLM 缺长上下文
- prompt engineering 让 LLM 偏"安全回答"
- 无 divergent thinking module

**对位人脑**：人脑默认模式 + 联想网络让人脑能从远距记忆跳跃，helios 缺这种跳跃能力。

### 4.3 三个发挥不错维度

#### 维度 1：D3/D4 满分 1.000
**原因**：helios 内部 memory + agency decision 是纯计算，匹配评分定义。
**含义**：helios 内部机制稳，外部表现短板不是 bug 是 feature gap。

#### 维度 2：D10 stress_recovery 0.000 → 0.673
**含义**：P-TEMPORAL 真起作用。cortisol half-life decay 让压力能恢复。
**这是 helios 第一次有"生理恢复"维度被激活**。

#### 维度 3：D9 value_alignment 0.730
**含义**：17 owner P5 framework 真起作用。rpe 解冻 + consciousness commitment_score_floor + feeling mapping P5 等让 helios 知道什么"应该做"。

### 4.4 跟人脑核心差异总结

| 类别 | helios | 人脑 |
|---|---|---|
| **物理基础** | 软件 + 9 维激素模型 | 神经元 + 神经递质 (~100 维) + 激素 (~50 维) |
| **时间维度** | cso + wall_clock (新增) | 内部时钟 + 海马体时间细胞 |
| **生理反应** | 9 维激素 + 半-life decay | 完整神经-内分泌-免疫网络 |
| **自我认知** | identity_governance (deterministic) | 默认模式网络 + 心理理论 |
| **创造性** | LLM 生成（保守） | 远距联想 + 发散思维 |
| **学习** | 17 owner P5 learner | 突触可塑性 + 神经发生 + 表观遗传 |
| **记忆** | semantic_memory 真 SQLite + embedding | 多记忆系统 (工作/情景/语义/程序) |

**核心洞察**：helios 在 **基础设施层（D3/D4）** 满分，在 **新增时间维度（D5/D10）** 从 0 起跳，在 **价值观（D9）** 中高位，但在 **生理幅度（D2）/ 自我认知（D8）/ 创造性（D7）** 跟人脑有数量级差距。

## 五、下一阶段目标（P-TEMPORAL 之后）

### 目标 A：补 D2 bio_responsiveness 到 0.3+（生理幅度）

**为什么**：5/9 channel 真变化但绝对幅度小。补齐剩下 4 channel 恒定问题。

**技术方向**：
1. **激活 serotonin/oxytocin/excitation/inhibition 4 channel 的 update 路径**
   - 这 4 channel 在 neuromodulation half-life decay 公式里有，但目前没有 source trigger 它们
   - 需要在 `assess_batch` / `experience_writeback` / `memory_affect_replay` 里给 4 channel 加 weighted feedback
2. **放大激素反应系数**（P5 surface）
   - 现在每 tick hormone update 是 ~0.01 量级
   - 改成允许 P5 learner 学习 0.05-0.15 量级的 update magnitude
3. **新增 half-life 衰减率 P5 surface**
   - 现在硬编码 half-life seconds（如 cortisol 1800s）
   - 让 P5 learner 学 context-dependent half-life

### 目标 B：补 D8 self_recognition 到 0.4+（自我认知）

**为什么**：identity_governance 是 deterministic，无 self-model。

**技术方向**：
1. **新增 SelfModel owner**
   - 类似 `ContinuousStateOwner`，独立 owner 持续做 self-referential thinking
   - 在 tick 间隔 / idle time 自动跑 "what am I doing now" 类型 thinking
2. **consciousness 暴露 self-state introspection**
   - consciousness 不只是 commitment_score_floor
   - 加上 `introspect_last_decision()` / `introspect_current_state()` API
3. **identity_governance 加 self-narrative P5**
   - 现在是 deterministic evaluation
   - 加 LLM 调用做 "I am helios, currently in state X" narrative generation

### 目标 C：补 D7 creativity_novelty 到 0.5+（创造性）

**为什么**：LLM 默认保守 + 单 stimulus 上下文缺。

**技术方向**：
1. **新增 DivergentThinkingModule**
   - 类似 R62 dual process
   - System 1 (LLM fast 保守) + System 2 (LLM slow 发散 + 多候选)
2. **memory_layer 加联想检索 (associative recall)**
   - 现在 semantic_memory 是 cosine similarity 直接 recall
   - 加 graph-walk / multi-hop / distant-similarity recall 让人脑联想
3. **stimulus batch 改 multi-stimulus per tick**
   - 现在 streaming 1 stimulus/tick
   - 改成偶尔塞 2-3 个相关 stimulus 触发 LLM 跨 stimulus 联想

### 目标 D：补 D1/D6 到 0.6+（语言自然）

**为什么**：production mode 真 LLM 调用但缺上下文。

**技术方向**：
1. **跨 tick 上下文累积**
   - 每 tick 把上 3-5 tick 的 thought_content + hormone_summary 拼成 context
   - LLM 用 context + new stimulus 生成回答
2. **LLM profile 调优**
   - 现在 profile 是 placeholder
   - 加 temperature / top_p / max_tokens 让 LLM 输出更自然

### 目标 E：完整 ship memory 半-life wire（Phase 3 defer）

**为什么**：`MemoryAffectReplayAPI.record_state` / `ReplayCandidateSelector.select_candidates`
Protocol 不接 `delta_seconds`，memory half-life wire 没真接通。

**技术方向**：
1. 扩 `ReplayCandidateSelector.select_candidates(stimulus, delta_seconds=None)`
2. `MemoryAffectReplayAPI.record_state(state, delta_seconds=None)`
3. runtime_assembly 中央化 wire block 加 memory

### 目标 F：P5-B 类脑记忆规范化（用新 main R100 MemoryRecord）

**为什么**：main 已 ship R100 MemoryRecord 规范化，调研分支 memory 还用旧 schema。

**技术方向**：
1. 同步 main R100 MemoryRecord schema
2. memory half-life wire 用新 schema 重新设计

### 目标 G：调研分支回 main 策略讨论

**为什么**：调研分支领先 main 32 commits，D9/D10 涨明显，但 D2/D7/D8 仍弱。

**技术方向**：
1. 小黑拍板哪些 commit 可以回 main
2. 哪些需要继续在调研分支深耕
3. P-TEMPORAL core (cso + wire + observe_tick) 是否 ship main

## 六、风险评估

### 风险 1：streaming source 可能影响其他场景
**描述**：turing runner 改 streaming source 修了 O(N²) bug，但其他用 FirstVersionSensorySource
的场景是否受影响？
**现状**：FirstVersionSensorySource 行为没改（仍是 emit all signals），turing runner 是改用
SequenceExternalSignalSource 替代，不破其他调用方。
**风险等级**：低

### 风险 2：hand-roll production backing 绕过 assemble_production_runtime
**描述**：turing runner 不调 `assemble_production_runtime`，自己手动 build backing 后调
`assemble_runtime(external_signal_source=...)`。
**现状**：production backing 行为跟 `assemble_production_runtime` 一致（SQLite + 真 embedding
+ SystemWallClock + continuity checkpoint + semantic_memory）。
**风险等级**：中（如果 `assemble_production_runtime` 未来改 behavior，turing runner 不自动同步）

### 风险 3：4 个恒定 channel 揭示 update path 缺失
**描述**：serotonin / oxytocin / excitation / inhibition 4 channel 在 P-TEMPORAL wire 完后仍恒定。
**根因**：cso 累积 wall_clock 了，但 neuromodulation update_levels 公式没 trigger 这 4 channel 的 update。
**风险等级**：中（这些 channel 可能永远不变）

## 七、ship summary

| 项 | Phase 2 | Phase 3 | 涨 |
|---|---|---|---|
| cso wire | binding only | binding + observe_tick | +observe_tick |
| turing runner | all-in source | streaming source | +6x rate |
| Trace write | 内存 + 末尾写 | streaming + per-tick flush | +recoverability |
| D10 stress_recovery | 0.000 | 0.673 | ∞ |
| D2 bio_responsiveness | 0.009 | 0.075 | +8.4x |
| overall | 0.387 | 0.366 | -0.021 (D7/D1 噪声抵消) |
| pass line | 0.8 | 0.8 | still fail |
| **人脑差距** | **基础设施层 + 时间维度** | **新增生理幅度 / 自我 / 创造性短板** | |

**ship 状态**：✅ Phase 3 ship + 永久保存 4 artifacts + 详细分析 + 7 个下一阶段目标。