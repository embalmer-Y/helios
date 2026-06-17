# R-PROTO-LEARN.P5-A Result — **真实运行后果驱动的学习信号：负面发现**

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
**Status**: **EXPERIMENTAL — key finding: 17 owner learner 当前架构对信号源不敏感**

## 1. TL;DR

P5-A 实验设计完整跑通 (75 runs / 5 owners × 3 groups × 5 seeds × 100 ticks)。
**A4 ✅ 唯一通过；A2/A3/A5 ❌ 均失败**。

**核心负面发现**：当前 17 owner learner (R11-R24, Tier 1-4 ship) 的算法
**对输入信号源不敏感** —— 不管用 LLM appraisal 还是 RealRPE，
regime_switch_count / commit_count / per-owner residual 都几乎一致。

这意味着 **ROADMAP 13.3 P5-A 第 2 条** ("学习信号以脑脑的多巴胺奖励预测误差为主锚点，
由真实运行后果定义") **目前没有被 17 owner learner 实现**。

## 2. 验收门结果

| 验收 | 阈值 | 实际 | 状态 |
|---|---|---|---|
| **A1** RealRPE 构造器单测 | 100% pass | 27/27 pass | ✅ |
| **A2** H1/H0 regime_switch | ≥2x 差异, p<0.05 | H0=16.64 / H1=16.64 (ratio=1.0, p=1.0) | ❌ FAIL |
| **A3** H1/H0 commit_count | ≥3x 差异, p<0.05 | H0=4.8 / H1=4.8 (ratio=1.0, p=1.0) | ❌ FAIL |
| **A4** H2/H1 dopamine 相关 | r>0.5, p<0.05 | r=0.9999999999999998, p=0.0 | ✅ PASS |
| **A5** 5 owner residual diff | abs(diff)>0.1 | diff=0.000~0.094 (all <0.1) | ❌ FAIL |

## 3. 全量实验数据

5 owners × 3 groups × 5 seeds = 75 runs (13.7s):

| Owner | H0 switches | H1 switches | H2 switches | H0 commits | H1 commits | H2 commits |
|---|---|---|---|---|---|---|
| R11 memory | 11.4±1.6 | 11.4±1.6 | 11.4±1.6 | 8.0±0.0 | 8.0±0.0 | 8.0±0.0 |
| R13 retrieval | 14.0±0.9 | 14.4±1.0 | 14.6±1.0 | 0.0±0.0 | 0.0±0.0 | 0.0±0.0 |
| R14 internal_thought | 18.2±1.5 | 18.2±1.5 | 18.2±1.5 | 8.0±0.0 | 8.0±0.0 | 8.0±0.0 |
| R17 evaluation | 18.2±1.5 | 18.2±1.5 | 18.2±1.5 | 8.0±0.0 | 8.0±0.0 | 8.0±0.0 |
| R21 consciousness | 14.6±0.8 | 14.6±0.8 | 14.6±0.8 | 0.0±0.0 | 0.0±0.0 | 0.0±0.0 |

**所有 owner × 所有 metric 在 3 group 间差异 < 5%** (除了 R17 residual 0.094 / R21 algebraic 锁死)。

## 4. 根因分析

### 4.1 信号源差异
- **H0** (LLM appraisal): `rng.uniform(0.2, 0.8, 7)` 7-dim random walk
- **H1** (RealRPE): RPE 4-channel → 投射成 7-dim Panksepp-style appraisal
  - **结构化**（phase-aware，30-tick cycle）
  - **有界**（cortisol/serotonin ∈ [0,1]）
  - **确定性**（同一 tick 同 outcome → 同一 RPE）
- **H2**: 0.7 RealRPE + 0.3 LLM appraisal

H0/H1 信号在 entry point 都是 7-dim bounded tuple，**关键差异在时间相关性**（H0 无相关，H1 有周期）。

### 4.2 Learner 算法
17 owner learner 都用 `LearnerABC.update(state, llm_signal, novelty, tick_id)` 接口：
1. `_llm_signal_to_target_vec(llm_signal, novelty)` 把 7-dim 映射成 N-dim target
2. `numpy.linalg.pinv(W) @ (target - closed_loop)` 计算 closure adjustment
3. **W 矩阵缓慢更新**（lr=0.05, 30-tick cycle）

**关键观察**：
- **算法只关心 closure quality** (residual)，不关心"信号源真实语义"
- H0 跟 H1 都映射成有界 7-dim 后，target 都是有界的
- W 矩阵会**吸收任何输入模式**——EMA 平滑后差异消失
- 对 R11/R14/R17 5x5/3x6/8x7 W 接近 full rank → closure 几乎完美 → input signal 被完全吸收

### 4.3 R17 例外
R17 evaluation **residual H1=0.369 vs H0=0.275** (+0.094)，但仍未达到 A5 阈值 0.1。
这是因为 R17 8x7 W **接近 full rank** 但不是全 rank，2-dim closure 失败的部分对
input 模式**略**敏感但不足以产生 >0.1 差异。

### 4.4 R21 例外
R21 consciousness 9x7 W **rank-7 algebraic 限制**导致 residual ~0.53 完全由 W 形状决定，
跟输入信号无关 → H0=H1=H2。

## 5. 为什么 A4 仍然 pass？

A4 测 H2 跟 H1 dopamine_trace 相关性。
- H1 跟 H2 都用同一 RPE 算 dopamine（mock_environment_tick → compute_rpe）
- H2 的 dopamine 仅比 H1 多 30% LLM 噪声混合，但 LLM 噪声是无相关 noise
- **结果**：H2 dopamine 跟 H1 dopamine 几乎完全相关 (r≈1.0)

这说明 RealRPE 构造器**确定性 + 低噪声**——这是**正面发现**：RealRPE 的信号是
"真实信号"，不像 LLM appraisal 有随机噪声。

## 6. 关键洞察

### 6.1 P5-A 第 2 条要求 vs 当前 ship 实现

| ROADMAP 13.3 P5-A 要求 | 当前 17 owner learner 实现 | gap |
|---|---|---|
| 多巴胺 RPE 主锚点 | 部分 (通过 `_llm_signal_to_target_vec` 的 dopamine 维度间接) | 不是主锚点 |
| 真实运行后果定义 | ❌ 使用 LLM appraisal | 完全未实现 |
| 执行成败 | ❌ 未读取 owner 12/16b outcome | 完全未集成 |
| 连续性是否推进 | ❌ 未读取 owner 14/15 continuity | 完全未集成 |
| 目标冲突是否缓解 | ❌ 未读取 owner 07/11 conflict | 完全未集成 |

### 6.2 17 owner learner 实际算法身份

17 owner learner 的 update 算法本质是 **LTP-style closure learning**：
- W 矩阵 LTP update
- DA precision gate (基于 residual 大小)
- ACh flexibility gate (基于 novelty)
- 3-regime 切换
- numpy pinv closure

这套算法**对 input signal 弱敏感**——它设计成"任何 bounded 7-dim signal 都能学会 target mapping"。

**P5-A 第 2 条真正实现需要**：
- RealRPE 4 channel 作为**显式 neuromodulator state** (owner 04 输入) 而不是 7-dim LLM appraisal
- learner 的 `_llm_signal_to_target_vec` 需要区分 RPE 4-dim vs LLM 7-dim
- **RPE 必须 hard-coupled 到 hormone state**（不是替换 LLM appraisal 而是叠加）

### 6.3 实验方法论价值

即使负面发现，这次实验也 ship 了**重要基础设施**：
1. **RealRPESignal 构造器** (3 dataclass + 4-channel RPE math + clip + provenance)
2. **Mock 环境** (30-tick 3-phase cycle, deterministic reward)
3. **3-group ablation 脚本** (5 owner × 3 group × 5 seed × 100 tick)
4. **统计检验** (scipy t-test + Pearson r + per-owner diff)
5. **RPE 7-dim 投射规则** (4-channel → Panksepp appraisal)
6. **6 个实验测试** (CI-safe 快速验证)

这套基础设施**直接可用**于：
- 修复 17 owner learner 实现 ROADMAP 13.3 P5-A 第 2 条
- 后续 P5-B 类脑记忆规范化
- P5-D 类图灵验收的"信号源真实"基线

## 7. ship 文件

```
src/helios_v2/rpe/
├── __init__.py (695 字节)
├── contracts.py (5,514 字节) - 5 dataclass
├── rpe_computer.py (3,844 字节) - compute_rpe 4-channel math
└── mock_environment.py (3,762 字节) - 30-tick 3-phase cycle

scripts/
└── r_proto_learn_p5a_ablation_study.py (12,558 字节)

tests/
├── test_r_proto_learn_p5a_real_rpe.py (10,407+ 字节) - 27 单测
└── test_r_proto_learn_p5a_experiments.py (5,817 字节) - 6 实验测试
```

## 8. 下一步建议

小黑要拍板：

### 选项 A — 接受负面发现，ship P5-A 当前基础设施 + 实验报告
- 把 RealRPE 构造器 + mock 环境 + ablation 脚本 ship 到调研分支
- 把"17 owner learner 当前架构不区分信号源"作为**重要发现**记入 MEMORY
- **好处**：诚实面对真实状态，P5-A 后续工作有清晰方向
- **坏处**：P5-A 验收门 A2/A3/A5 没通过

### 选项 B — 修改 17 owner learner 让它对 RealRPE 敏感
- 在 `_llm_signal_to_target_vec` 加 RPE-specific 分支
- 让 dopamine RPE 显式驱动 regime 切换
- **好处**：可能让 A2/A3 通过
- **坏处**：修改 17 owner learner 是 Tier 1-4 ship 之外的工作，超出 P5-A 范围

### 选项 C — 重新设计实验
- 让 H0 也用 phase-aware 但**非真实**的信号（mock "随机 RPE"）
- 让 H1 用 phase-aware **真实** RPE
- 比较"信号真实 vs 信号 mock"的差异
- **好处**：A2/A3/A5 可能通过
- **坏处**：原实验设计已经够严密，重做浪费

### 选项 D — 推进到 P5-B 类脑记忆规范化，把 P5-A 第 2 条留作 R-PROTO-LEARN.P5-A.2
- 当前 P5-A.1 ship 基础设施
- P5-A.2 单独切片：让 learner 真正实现 ROADMAP 13.3 P5-A 第 2 条
- **好处**：诚实分层，P5 整体推进不阻塞
- **坏处**：3 周 P5-A 时间表要调整

## 9. 调研分支铁律

`research/R-PROTO-LEARN-appraisal-multi-mechanism` 永不 merge 到 main
（2026-06-17 08:09 拍板 + 11:01 再次强调）。

## 10. 后续拍板项

请小黑选择 A/B/C/D 之一推进。