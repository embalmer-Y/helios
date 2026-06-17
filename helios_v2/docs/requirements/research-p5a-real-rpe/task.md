# R-PROTO-LEARN.P5-A Task

## Task 列表

### Phase 1 — RealRPESignal 构造器（**W1**）

- [ ] **T1.1** 写 `src/helios_v2/rpe/contracts.py`
  - ExecutionOutcome dataclass (action_id / executed / succeeded / response_received / response_accepted / latency_ticks)
  - ContinuityMetric dataclass (long_term_goal / short_term_actions / alignment_score / consecutive_ticks)
  - ConflictResolution dataclass (candidate_count / accepted_count / suppressed_count / resolution_efficiency)
  - RPESignal dataclass (dopamine / norepinephrine / serotonin / cortisol / tick_id / provenance)
  - RealRPEConfig dataclass

- [ ] **T1.2** 写 `src/helios_v2/rpe/rpe_computer.py`
  - `compute_rpe(predicted_reward, actual_outcome, continuity, conflict, config) -> RPESignal`
  - 4 channel 公式（参考 Schultz 1997 + Einhauser 2018 + Bhatt 2019）
  - clip 到合法范围 [0, 1] / [-1, 1]
  - provenance 自动记录

- [ ] **T1.3** 写 `src/helios_v2/rpe/__init__.py`
  - 导出所有 public API

- [ ] **T1.4** 写 `tests/test_r_proto_learn_p5a_real_rpe.py`
  - 至少 25 个单测
  - 覆盖：成功路径 / 失败路径 / 混合路径 / clip 边界 / provenance 追踪
  - **A1 验收**：100% pass

### Phase 2 — Mock 环境 + 单 owner smoke（**W1**）

- [ ] **T2.1** 写 `src/helios_v2/rpe/mock_environment.py`
  - `mock_environment_tick(tick, owner) -> tuple[ExecutionOutcome, ContinuityMetric, ConflictResolution]`
  - 3 phase cycle：easy (0-9) / medium (10-19) / hard (20-29) × repeat

- [ ] **T2.2** 写 `scripts/r_proto_learn_p5a_real_rpe_smoke.py`
  - 单 owner (R11 memory) 跑 50 tick
  - 验证 dopamine RPE 在 phase B 显著负向
  - 验证 cortisol 在 phase C 显著上升

### Phase 3 — 三组对照实验（**W2**）

- [ ] **T3.1** H0 baseline (LLM appraisal) 跑通
  - 5 owner × 5 seeds × 100 tick
  - 5 × 100 = 500 runs per owner → 2500 LLM calls
  - 记录：regime_switch_count / commit_count / residual / dopamine_trace

- [ ] **T3.2** H1 (RealRPE only) 跑通
  - 5 owner × 5 seeds × 100 tick
  - 0 LLM calls (mock only)
  - 记录：同 H0

- [ ] **T3.3** H2 (mixed 0.7 RealRPE + 0.3 LLM) 跑通
  - 5 owner × 5 seeds × 100 tick
  - 250 LLM calls (sparse every 2 ticks)
  - 记录：同 H0

- [ ] **T3.4** 写 `scripts/r_proto_learn_p5a_ablation_study.py`
  - 跑全部 75 runs
  - 统计检验 t-test + Pearson r
  - 报告 regime_switch / commit_count / residual_corr

- [ ] **T3.5** 写 `tests/test_r_proto_learn_p5a_experiments.py`
  - pytest 跑实验验证（**快模式 5 tick**）
  - 验证：H1 跟 H0 regime switch count 不同
  - 验证：H1 commit 少于 H0
  - 验证：H2 跟 H1 dopamine 相关
  - **A2/A3/A4/A5 验收**：100% pass

### Phase 4 — commit + push（**W3**）

- [ ] **T4.1** 写 `docs/requirements/research-p5a-real-rpe/result.md`
  - 5 个 owner × 3 group × 5 seed 完整结果表
  - 统计检验结论
  - 是否达成 A1-A5 验收门

- [ ] **T4.2** commit + push 到 `research/R-PROTO-LEARN-appraisal-multi-mechanism`
  - 调研分支铁律：永不 merge main

- [ ] **T4.3** 写日报 `memory/2026-06-17-p5a.md`

## 验收门 Checklist

| 验收 | 阈值 | 状态 |
|---|---|---|
| **A1** RealRPE 构造器单测 | 100% pass | T1.4 ✅ |
| **A2** H1/H0 regime switch | ≥2x 差异, p<0.01 | T3.5 |
| **A3** H1/H0 commit count | ≥3x 差异, p<0.01 | T3.5 |
| **A4** H2/H1 dopamine 相关 | r>0.5, p<0.01 | T3.5 |
| **A5** 5 owner 显著差异 | abs(diff)>0.1 | T3.5 |