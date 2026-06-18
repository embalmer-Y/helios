# R-PROTO-LEARN.P5-A.2 Task

## Phase 1 — LearnerConfig + LearnerABC 升级 (W1)

- [ ] **T1.1** 改 `src/helios_v2/learning/contracts.py`
  - `LearnerConfig` 加 2 字段:
    - `rpe_signal_enabled: bool = True`
    - `rpe_weight: float = 0.5`
  - `Learner` Protocol `update` 加可选 `rpe_signal: tuple[float, ...] | None = None` 参数

- [ ] **T1.2** 改 `src/helios_v2/learning/framework.py`
  - `LearnerABC.update` 加 `rpe_signal` 参数
  - 引入 `_signals_to_target_vec(llm_signal, rpe_signal, novelty)` 内部方法
  - 保留 `_llm_signal_to_target_vec` 作为子类 override 点
  - 加 default `_rpe_to_output_additions(dopamine, norepinephrine, serotonin, cortisol)` → 11-dim target contributions
  - 兼容老调用: rpe_signal=None 时退化到 7-dim (P5-A.1 行为)

## Phase 2 — 15 owner 升级 (W1)

- [ ] **T2.1** 升级 R11 memory_learner.py (5x11 W, override _rpe_to_output_additions)
- [ ] **T2.2** 升级 R12 thought_gating_learner.py (8x11 W)
- [ ] **T2.3** 升级 R13 retrieval_learner.py (11x11 W)
- [ ] **T2.4** 升级 R14 internal_thought_learner.py (3x11 W)
- [ ] **T2.5** 升级 R15 autonomy_learner.py (9x11 W)
- [ ] **T2.6** 升级 R16 action_externalization_learner.py (9x11 W)
- [ ] **T2.7** 升级 R17 evaluation_learner.py (8x11 W)
- [ ] **T2.8** 升级 R18 workspace_learner.py (9x11 W)
- [ ] **T2.9** 升级 R19 outward_expression_learner.py (9x11 W)
- [ ] **T2.10** 升级 R20 outward_expression_externalization_learner.py (9x11 W)
- [ ] **T2.11** 升级 R20b prompt_contract_learner.py (9x11 W)
- [ ] **T2.12** 升级 R21 consciousness_learner.py (9x11 W)
- [ ] **T2.13** 升级 R22 planner_bridge_learner.py (9x11 W)
- [ ] **T2.14** 升级 R23 identity_governance_learner.py (12x11 W)
- [ ] **T2.15** 升级 R24 experience_writeback_learner.py (9x11 W)

## Phase 3 — 单测 (W1-W2)

- [ ] **T3.1** 每个 owner 加 2 个新单测:
  - `test_<owner>_rpe_signal_changes_target`: 给不同 RPE 应该有不同 target
  - `test_<owner>_rpe_signal_none_compatible`: rpe_signal=None 跟 P5-A.1 行为一致

- [ ] **T3.2** 跑 5 owner × 4 test = 20 个新单测
  - **B1 验收**: 100% pass

## Phase 4 — Ablation 升级 (W2)

- [ ] **T4.1** 改 `scripts/r_proto_learn_p5a_ablation_study.py`
  - `_run()` 函数接受 rpe_signal
  - H1 组: 用 compute_rpe 算 rpe_signal → 投射成 4-dim tuple
  - H2 组: 0.7 RealRPE + 0.3 LLM appraisal (rpe_signal 不变, llm_signal 加噪声)

- [ ] **T4.2** 跑 75 runs ablation
  - **B2/B3/B4/B5 验收**

## Phase 5 — 整库回归 (W2)

- [ ] **T5.1** 跑整库 R-PROTO-LEARN 测试
  - 预期: 至少 95% pass (algebraic 限制 owner 部分 test 可能 fail)
  - **B6 验收**

## Phase 6 — 报告 + commit (W3)

- [ ] **T6.1** 写 `result.md`:
  - 5 owner × 3 group × 5 seed 完整结果表
  - 验收门 B1-B6 状态
  - 跟 P5-A.1 (commit `5f0db68`) 对比: A2/A3/A5 是否变成 PASS
  - 17 owner 整库回归状态

- [ ] **T6.2** commit + push 到调研分支
  - 铁律: 永不 merge main

- [ ] **T6.3** 写日报 `memory/2026-06-17-p5a-2.md`

## 验收门 Checklist

| 验收 | 阈值 | 状态 |
|---|---|---|
| **B1** 17 owner 双信号源单测 | 100% pass | T3.2 |
| **B2** H1/H0 regime_switch | ≥2x, p<0.01 | T4.2 |
| **B3** H1/H0 commit | ≥3x, p<0.01 | T4.2 |
| **B4** 5 owner residual diff | >0.1 | T4.2 |
| **B5** H2/H1 dopamine 相关 | r>0.5 | T4.2 |
| **B6** 整库回归 | ≥95% pass | T5.1 |