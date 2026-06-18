# R-PROTO-LEARN.P5-A.2 Design

## 1. 架构总览

```
                 ┌──────────────────────────────────────┐
                 │ RealRPESignal (4 channel)            │
                 │  - dopamine (RPE)                    │
                 │  - norepinephrine (effort)           │
                 │  - serotonin (stability)             │
                 │  - cortisol (threat)                 │
                 └────────────────┬─────────────────────┘
                                  │ RPE 通道映射
                                  ↓
┌────────────────────┐    ┌────────────────────────────┐
│ LLM appraisal (7d) │ ──→│ _signals_to_target_vec()   │ ──→ 11-dim target vec
│  (主观信号)         │    │  7 LLM + 4 RPE explicit    │       ↓
└────────────────────┘    └────────────────────────────┘  17 owner W 矩阵
                                                          (input_dim 7→11)
                                                               ↓
                                                          numpy pinv closure
                                                               ↓
                                                          regime 切换
                                                          (RPE 触发)
```

## 2. 关键代码改动

### 2.1 LearnerConfig 加 rpe 字段

```python
@dataclass(frozen=True)
class LearnerConfig:
    learning_rate: float = 0.05
    commit_threshold: float = 0.3
    min_stable_ticks: int = 8
    frozen_ticks_post_commit: int = 5
    regime_hysteresis_ticks: int = 2
    flexibility_threshold: float = 0.3
    flexibility_floor: float = 0.1
    flexibility_ceiling: float = 1.0
    dopamine_precision_gain: float = 0.3
    frozen_commit: bool = True
    habitual_residual_threshold: float = 0.5
    # RPE-A.2 新增: rpe_signal 是否显式影响
    rpe_signal_enabled: bool = True  # 关闭则行为跟 P5-A.1 一致
    rpe_weight: float = 0.5          # RPE 在 11-dim target 中的权重
```

### 2.2 LearnerABC.update 加 rpe_signal 参数

```python
def update(
    self,
    state: object,
    llm_signal: tuple[float, ...] | None,
    novelty: float,
    tick_id: int | None,
    rpe_signal: tuple[float, ...] | None = None,  # 新增
) -> _LearningSnapshot:
    ...
    target_vec = self._signals_to_target_vec(llm_signal, rpe_signal, novelty)
    ...
```

### 2.3 _signals_to_target_vec 内部实现

```python
def _signals_to_target_vec(
    self,
    llm_signal: tuple[float, ...] | None,
    rpe_signal: tuple[float, ...] | None,
    novelty: float,
) -> np.ndarray:
    # 子类覆盖 _llm_signal_to_target_vec 提供 7-dim LLM 映射
    if llm_signal is not None:
        llm_target = self._llm_signal_to_target_vec(llm_signal, novelty)
    else:
        llm_target = np.zeros(self.output_dim)
    
    if rpe_signal is None or not self._config.rpe_signal_enabled:
        # 退化为 7-dim 输入 (兼容 P5-A.1 行为)
        return llm_target
    
    # RPE 4 channel: (dopamine, norepinephrine, serotonin, cortisol)
    # 显式 clip 到 [0, 1] (RPE dopamine 是 signed)
    rpe_dopamine = max(0.0, min(1.0, (rpe_signal[0] + 1.0) / 2.0))
    rpe_ne = max(0.0, min(1.0, rpe_signal[1]))
    rpe_ser = max(0.0, min(1.0, rpe_signal[2]))
    rpe_cor = max(0.0, min(1.0, rpe_signal[3]))
    
    # 每个 owner override _rpe_to_output_additions 提供 RPE 通道 → output dim 映射
    rpe_additions = self._rpe_to_output_additions(rpe_dopamine, rpe_ne, rpe_ser, rpe_cor)
    
    # 11-dim 联合: 7 LLM (input_dim 假设 7) + 4 RPE 通道在 output 上的贡献
    return llm_target * (1.0 - self._config.rpe_weight) + rpe_additions * self._config.rpe_weight
```

### 2.4 每个 owner override `_rpe_to_output_additions`

5 owner (R11/R14/R17) + Tier 2 (R12/R16) + Tier 3 (R18/R19/R20) + Tier 4 (R21/R22/R23/R24) + R20b

每个 owner 的 output dim 不同, RPE 4 通道映射规则:
- **dopamine RPE** → 总是影响 "confidence" 类输出 (output dim 0)
- **norepinephrine** → 总是影响 "effort" 类输出 (output dim 1)
- **serotonin** → 总是影响 "stability" 类输出 (output dim 2)
- **cortisol** → 总是影响 "threat" 类输出 (output dim 3)
- **剩余 dim 走 LLM appraisal** (跟 P5-A.1 一致)

```python
def _rpe_to_output_additions(
    self, dopamine: float, norepinephrine: float, serotonin: float, cortisol: float
) -> np.ndarray:
    """Default: 4 channel 映射到 output dim 0-3, 剩余走 LLM."""
    additions = np.zeros(self.output_dim)
    if self.output_dim >= 1:
        additions[0] = dopamine
    if self.output_dim >= 2:
        additions[1] = norepinephrine
    if self.output_dim >= 3:
        additions[2] = serotonin
    if self.output_dim >= 4:
        additions[3] = cortisol
    return additions
```

子类可 override 这个方法提供 owner-specific 映射。

## 3. 17 owner 升级清单

| Owner | input_dim 旧/新 | output_dim | RPE 4 channel 映射规则 |
|---|---|---|---|
| R11 memory | 7/11 | 5 | dim0=family, dim1=replay, dim2=consolidation, dim3=priority, dim4=evict |
| R12 thought_gating | 7/11 | 8 | dim0=confidence, dim1=effort, dim2=stability, dim3=threat, dim4-7=LLM |
| R13 retrieval | 7/11 | 11 | dim0=confidence, dim1=effort, dim2=stability, dim3=threat, dim4-10=LLM |
| R14 internal_thought | 7/11 | 3 | dim0=dopamine, dim1=norepinephrine, dim2=serotonin |
| R15 autonomy | 7/11 | 9 | dim0=drive, dim1=effort, dim2=stability, dim3=threat, dim4-8=LLM |
| R16 action_ext | 7/11 | 9 | dim0=confidence, dim1=effort, dim2=stability, dim3=threat, dim4-8=LLM |
| R17 evaluation | 7/11 | 8 | dim0=confidence, dim1=effort, dim2=stability, dim3=threat, dim4-7=LLM |
| R18 workspace | 7/11 | 9 | 同 R16 模式 |
| R19 outward_expression | 7/11 | 9 | 同 R16 模式 |
| R20 outward_expression_ext | 7/11 | 9 | 同 R16 模式 |
| R20b prompt_contract | 7/11 | 9 | 同 R16 模式 |
| R21 consciousness | 7/11 | 9 | 同 R16 模式 |
| R22 planner_bridge | 7/11 | 9 | 同 R16 模式 |
| R23 identity_governance | 7/11 | 12 | dim0-3=RPE, dim4-11=LLM |
| R24 experience_writeback | 7/11 | 9 | 同 R16 模式 |

## 4. 风险: W 矩阵 rank 限制

新 input_dim=11 vs output_dim 5/8/9/11/12:
- R11: 5x11 W rank ≤ 5 → residual 不能为 0 (algebraic 限制) — 接受
- R12: 8x11 W rank ≤ 8 → algebraic 限制仍存在
- R13: 11x11 W rank ≤ 11 → 接近 full rank (跟 R17 类似)
- R14: 3x11 W rank ≤ 3 → 大幅降维
- R23: 12x11 W rank ≤ 11 → algebraic 限制仍在 (12x7 → 12x11, rank 7 → 11)

**预期**: R11/R14/R17 残差会显著上升 (W 不能 capture 11-dim input 全部信号),
但这恰好让 learner 对输入 signal 变化更敏感 → **A2/A3/A5 可能通过**。

## 5. 实施步骤

1. **W1 D1**: 改 `LearnerConfig` 加 rpe_signal_enabled + rpe_weight
2. **W1 D2**: 改 `LearnerABC.update` 加 rpe_signal 参数
3. **W1 D3**: 改 framework.py: `_llm_signal_to_target_vec` → `_signals_to_target_vec(llm, rpe, novelty)`
4. **W1 D4**: 加 default `_rpe_to_output_additions` 实现
5. **W1 D5**: 15 owner 全部升级 + 单测
6. **W2 D1**: 改 ablation 脚本支持 rpe_signal 传入
7. **W2 D2**: 跑 75 runs ablation
8. **W2 D3**: 整库回归 + 报告
9. **W3**: commit + push

## 6. 文件结构

```
src/helios_v2/learning/
├── contracts.py (LearnerConfig 加 2 字段)
├── framework.py (LearnerABC 加 rpe_signal 参数, 默认 _rpe_to_output_additions)
├── memory_learner.py (R11: 5x11 W)
├── thought_gating_learner.py (R12: 8x11 W)
├── retrieval_learner.py (R13: 11x11 W)
├── internal_thought_learner.py (R14: 3x11 W)
├── autonomy_learner.py (R15: 9x11 W)
├── action_externalization_learner.py (R16: 9x11 W)
├── evaluation_learner.py (R17: 8x11 W)
├── workspace_learner.py (R18: 9x11 W)
├── outward_expression_learner.py (R19: 9x11 W)
├── outward_expression_externalization_learner.py (R20: 9x11 W)
├── prompt_contract_learner.py (R20b: 9x11 W)
├── consciousness_learner.py (R21: 9x11 W)
├── planner_bridge_learner.py (R22: 9x11 W)
├── identity_governance_learner.py (R23: 12x11 W)
└── experience_writeback_learner.py (R24: 9x11 W)

scripts/
└── r_proto_learn_p5a_ablation_study.py (改: 接受 rpe_signal)

tests/
├── test_r_proto_learn_p5a_experiments.py (改: 验证 H0≠H1)
└── test_r_proto_learn_{11-24}_*.py (改: 加 rpe_signal 测试)
```