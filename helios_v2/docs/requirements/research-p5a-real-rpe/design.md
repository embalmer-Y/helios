# R-PROTO-LEARN.P5-A Design

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│ RealRPESignal 构造器 (新 ship)                                       │
│                                                                       │
│  输入 (3 个 owner 真实后果):                                          │
│  ├─ owner 12/16b action outcome (executed/succeeded/responded)       │
│  ├─ owner 14/15 continuity metric (跨 tick 一致性推进)                │
│  └─ owner 07/11 goal conflict resolution (candidate 是否被接受)       │
│                                                                       │
│  输出 (4 个 neuromodulator channel):                                  │
│  ├─ dopamine = predicted_reward − actual_outcome   (RPE 核心)        │
│  ├─ norepinephrine = execution_attempt_difficulty  (努力信号)         │
│  ├─ serotonin = continuity_progress_metric         (稳定信号)        │
│  └─ cortisol = unresolved_goal_conflict_intensity  (威胁信号)         │
└─────────────────────────────────────────────────────────────────────┘
            ↓
    替换 17 owner learner 的 LLM appraisal 输入
            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 17 owner learner (R11-R24, 已 ship)                                  │
│  - update(state, llm_signal, novelty, tick_id)                        │
│  - 现在 llm_signal 来源 = RealRPE / LLM / 混合                        │
└─────────────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 三组对照实验 (H0/H1/H2)                                              │
│  - 5 owner: R11/R13/R14/R17/R21 (代表 4 个 tier + 不同 W 形状)        │
│  - 5 seeds × 100 tick × 3 group = 7500 跑                            │
│  - 统计: regime_switch_count / commit_count / residual_corr          │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. RealRPESignal 数据结构

```python
@dataclass(frozen=True)
class ExecutionOutcome:
    """owner 12/16b 真实外化后果."""
    action_id: str
    executed: bool             # 草稿/工具是否真发出去
    succeeded: bool            # 是否成功（不抛异常 + 没被拒绝）
    response_received: bool    # 对话对方有没有回应
    response_accepted: bool    # 回应是否接受（vs 重写请求）
    latency_ticks: int         # 多久收到回应（0=瞬时，1=下一 tick）

@dataclass(frozen=True)
class ContinuityMetric:
    """owner 14/15 连续性推进."""
    long_term_goal: tuple[float, ...]      # 5-dim 长期目标
    short_term_actions: tuple[float, ...]  # 7-dim 短期行动
    alignment_score: float                 # [-1, 1] 短期对齐长期程度
    consecutive_ticks: int                 # 连续保持对齐多少 tick

@dataclass(frozen=True)
class ConflictResolution:
    """owner 07/11 目标冲突解决."""
    candidate_count: int                   # workspace 候选数
    accepted_count: int                    # 被接受数
    suppressed_count: int                  # 被抑制数
    resolution_efficiency: float           # accepted / total

@dataclass(frozen=True)
class RPESignal:
    """真实运行后果 → 4 channel neuromodulator signal."""
    dopamine: float            # RPE (reward prediction error)
    norepinephrine: float      # effort / arousal
    serotonin: float           # long-term stability
    cortisol: float            # threat / conflict
    tick_id: int
    provenance: tuple[str, ...]  # 输入来源 owner 列表（可审计）
```

## 3. RealRPE 计算公式

```python
def compute_rpe(
    predicted_reward: float,        # P5-feel 上一步的 W*hormone 预测
    actual_outcome: ExecutionOutcome,
    continuity: ContinuityMetric,
    conflict: ConflictResolution,
    config: RealRPEConfig,
) -> RPESignal:
    # 1. dopamine RPE = predicted - actual (Schultz 1997)
    actual_reward = (
        0.4 * (1.0 if actual_outcome.succeeded else -0.3) +
        0.3 * (0.8 if actual_outcome.response_accepted else -0.5) +
        0.3 * max(0.0, 1.0 - actual_outcome.latency_ticks / 10.0)
    )
    dopamine = predicted_reward - actual_reward  # 残差

    # 2. norepinephrine effort = action 难度
    norepinephrine = (
        0.5 if actual_outcome.executed else 0.2 +
        0.3 * (1.0 if not actual_outcome.succeeded else 0.0) +
        0.2 * (actual_outcome.latency_ticks / 10.0)
    )

    # 3. serotonin stability = 连续性推进
    serotonin = (
        0.6 * continuity.alignment_score +
        0.4 * min(1.0, continuity.consecutive_ticks / 20.0)
    )

    # 4. cortisol threat = 未解决冲突
    unresolved_ratio = 1.0 - conflict.resolution_efficiency
    cortisol = (
        0.5 * unresolved_ratio +
        0.3 * (conflict.candidate_count / 10.0) +
        0.2 * (conflict.suppressed_count / max(1, conflict.candidate_count))
    )

    return RPESignal(
        dopamine=clip(dopamine, -1.0, 1.0),
        norepinephrine=clip(norepinephrine, 0.0, 1.0),
        serotonin=clip(serotonin, 0.0, 1.0),
        cortisol=clip(cortisol, 0.0, 1.0),
        tick_id=...,
        provenance=("12", "16b", "14", "15", "07", "11"),
    )
```

## 4. 实验环境

### 4.1 受控 reward 函数
仿真环境用 deterministic reward — 避免 LLM 调用 variability：

```python
def mock_environment_tick(tick: int, owner: str) -> tuple[ExecutionOutcome, ContinuityMetric, ConflictResolution]:
    """3 类 mock scenario 周期切换，避免过拟合单一 pattern."""
    phase = tick % 30

    if phase < 10:
        # Phase A: easy success (high reward)
        return (
            ExecutionOutcome(action_id=f"a{tick}", executed=True, succeeded=True,
                           response_received=True, response_accepted=True, latency_ticks=1),
            ContinuityMetric(..., alignment_score=0.8, consecutive_ticks=phase+1),
            ConflictResolution(candidate_count=3, accepted_count=3, suppressed_count=0,
                             resolution_efficiency=1.0),
        )
    elif phase < 20:
        # Phase B: medium difficulty (mixed reward)
        return (...)
    else:
        # Phase C: hard failure (low reward, high conflict)
        return (...)
```

### 4.2 实验矩阵

| 参数 | 值 |
|---|---|
| Owner | R11/R13/R14/R17/R21 (5 个代表) |
| Signal source | H0=LLM / H1=RealRPE / H2=mixed (0.7 RealRPE + 0.3 LLM) |
| Seeds | 5 (random hash seed) |
| Ticks | 100 per run |
| Total runs | 5 × 3 × 5 = 75 runs (each 100 tick) |
| Total LLM calls (H0/H2 only) | 5 owner × 50 ticks (sparse) × 5 seeds × 2 groups = 2,500 calls |

### 4.3 统计检验

```python
# A2: regime_switch_count
t_stat, p_val = ttest_ind(H0_switches, H1_switches)
assert p_val < 0.01 and mean(H1) > 2 * mean(H0)

# A3: commit_count
t_stat, p_val = ttest_ind(H0_commits, H1_commits)
assert p_val < 0.01 and mean(H0) > 3 * mean(H1)

# A4: H1/H2 dopamine correlation
r, p_val = pearsonr(H1_dopamine_trace, H2_dopamine_trace)
assert r > 0.5 and p_val < 0.01

# A5: H1 vs H0 residual difference (per owner)
for owner_id in 5_owners:
    diff = H1_residual[owner_id] - H0_residual[owner_id]
    assert abs(diff) > 0.1  # 不是 noise
```

## 5. 文件结构

```
src/helios_v2/rpe/   ← 新增
├── __init__.py
├── contracts.py            (ExecutionOutcome, ContinuityMetric, ConflictResolution, RPESignal)
├── rpe_computer.py         (compute_rpe + RealRPEConfig)
└── mock_environment.py     (mock_environment_tick)

src/helios_v2/learning/    ← 复用
└── ... (17 owner learner 已 ship)

scripts/
├── r_proto_learn_p5a_real_rpe_smoke.py      (单 owner 真 LLM smoke)
└── r_proto_learn_p5a_ablation_study.py      (75 runs)

tests/
├── test_r_proto_learn_p5a_real_rpe.py         (单测)
└── test_r_proto_learn_p5a_experiments.py     (实验 + 统计检验)
```

## 6. 实施步骤

1. **W1 D1-D2**：写 `rpe/contracts.py` + `rpe/rpe_computer.py` + 单测
2. **W1 D3-D4**：写 `rpe/mock_environment.py` + 单 owner smoke + commit
3. **W1 D5**：单 owner 真 LLM 跑通 (sparse LLM 调用)
4. **W2 D1**：5 owner 真 LLM smoke (H0 baseline)
5. **W2 D2-D3**：H1 (RealRPE only) 跑 5 seeds × 100 tick
6. **W2 D4**：H2 (mixed) 跑 5 seeds × 100 tick
7. **W2 D5**：统计检验 + 报告
8. **W3**：commit + push + 调研文档

## 7. 风险与回退

- **风险 1**：RealRPE 跟 LLM appraisal 维度不完全对应（4 vs 7 dim） → 用 PAD 3-dim 投射 + 2 dim 拼接
- **风险 2**：mock environment 跟真实运行差异大 → 3 phase cycle 覆盖 easy/medium/hard
- **风险 3**：统计检验不显著 → 扩大 sample size (5 → 20 seeds) 或调整 mock 环境振幅