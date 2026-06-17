# R-PROTO-LEARN Tier 1 — Design

## 1. 统一学习框架架构

```
┌────────────────────────────────────────────────────────────────────┐
│ helios_v2/learning/                                                 │
│ ├── __init__.py (统一导出)                                          │
│ ├── contracts.py (LearnerConfig, Regime, Learner Protocol)         │
│ ├── framework.py (LearnerABC 通用基类)                              │
│ ├── memory_learner.py (R11 owner 06)                                │
│ ├── thought_gating_learner.py (R12 owner 09)                        │
│ ├── retrieval_learner.py (R13 owner 10)                             │
│ ├── internal_thought_learner.py (R14 owner 11)                      │
│ └── autonomy_learner.py (R15 owner 18)                              │
└────────────────────────────────────────────────────────────────────┘
        │       │       │        │         │
        ▼       ▼       ▼        ▼         ▼
┌────────────────────────────────────────────────────────────────────┐
│ 5 owner 各自 engine 集成点 (opt-in p5_learner 字段)               │
│ 06 memory  │ 09 thought_gating │ 10 retrieval │ 11 internal │ 18 auto│
└────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────┐
│ Canonical owner state (R85 已有 4 层 / R43 dual-timescale / R70)  │
│ - P5 learner 是旁路观察者，**不修改** canonical state                │
│ - 只更新 learner 内部的 W/bias/regime/commit                        │
└────────────────────────────────────────────────────────────────────┘
```

## 2. 通用 LearnerABC 架构

### 2.1 5 项核心算法（**与 P5-feel 完全一致**）

```
1. Exploration (aINS): LLM appraisal → numpy pinv hormone adjustment
2. Consolidation (gINS): 连续 N tick mapping 不变 → 写入 config
3. Precision signal (DA): dopamine > 0.7 → 接受 / < 0.3 → 拒绝
4. Flexibility signal (ACh): ACh > threshold → 学新 mapping / < → 固守
5. Regime switching: EXPLORATORY / MODEL_BASED / HABITUAL
```

### 2.2 numpy-only closure（与 R9 完全一致）

```python
# module-level import numpy as np
import numpy as np

def _compute_hormone_adjustment(W, hormone, target, strength, clip):
    """R-PROTO-LEARN.9 closure (reused)."""
    current_feeling = W @ hormone
    residual = target - current_feeling
    adj0 = np.linalg.pinv(W) @ residual
    adj = strength * adj0
    if clip >= 1.0:
        return adj  # unclamped
    return np.clip(adj, -clip, clip)
```

### 2.3 W 矩阵 dense 化（与 P5-feel 一致）

- 默认 W 矩阵 50%+ 非零
- 学习率 lr=0.05（与 P5-feel 一致）
- commit_threshold=0.3 / min_stable_ticks=8 / frozen_ticks_post_commit=5

### 2.4 3 态 Regime 切换

```python
class Regime(Enum):
    EXPLORATORY = "exploratory"
    MODEL_BASED = "model_based"
    HABITUAL = "habitual"

# Regime decision tree
def _determine_regime(history, ach, novelty, regime_prev):
    if len(history) < 5:
        return Regime.EXPLORATORY
    if ach > flexibility_threshold and novelty > 0.5:
        return Regime.EXPLORATORY
    if _is_habitual_candidate(history):
        return Regime.HABITUAL
    return Regime.MODEL_BASED

# Hysteresis: keep previous regime until N consecutive new regime
```

## 3. 5 owner 各自细节

### 3.1 R11 owner 06 memory (`MemoryLearner`)
**3 维输入向量 → 1 维 priority / 1 维 rate / 3 维 family weights**

```python
class MemoryLearnerConfig(LearnerConfig):
    input_dim: int = 5  # affect_intensity, prediction_mismatch, autobio_salience, time_since_replay, novelty
    output_dim: int = 5  # 3 policy outputs

class MemoryLearner(LearnerABC):
    # 3 policies:
    # - replay_priority_policy: 5→1
    # - consolidation_policy: 4→1
    # - memory_family_write_policy: 3→3 (softmax)
```

### 3.2 R12 owner 09 thought_gating (`ThoughtGatingLearner`)
**6/4/5 维输入 → 1/1/1 维 gate/continuation/signal weights**

```python
class ThoughtGatingLearner(LearnerABC):
    # 3 policies:
    # - signal_normalization_policy: 6→6
    # - continuation_policy: 4→1
    # - gate_policy: 5→1
```

### 3.3 R13 owner 10 directed_retrieval (`RetrievalLearner`)
**6/5/4 维输入 → 4/3/4 维 tier/planning/window**

```python
class RetrievalLearner(LearnerABC):
    # 3 policies:
    # - tier_selection_policy: 6→4 (softmax)
    # - retrieval_planning_policy: 5→3 (softmax)
    # - thought_window_shaping_policy: 4→4
```

### 3.4 R14 owner 11 internal_thought (`InternalThoughtLearner`)
**6/4/5 维输入 → 1/1/1 维 generation/sufficiency/emission**

```python
class InternalThoughtLearner(LearnerABC):
    # 3 policies:
    # - thought_generation_policy: 6→1
    # - sufficiency_policy: 4→1
    # - proposal_emission_policy: 5→1
```

### 3.5 R15 owner 18 autonomy (`AutonomyLearner`)
**7/4/5 维输入 → 7/1/1 维 drive/carry/proactive**

```python
class AutonomyLearner(LearnerABC):
    # 3 policies:
    # - drive_integration_policy: 7→7
    # - continuity_carry_policy: 4→1
    # - proactive_externalization_policy: 5→1
```

## 4. 集成模式（与 P5-feel 完全一致）

### 4.1 owner engine 修改

```python
# owner 06 memory/engine.py
class MemoryEngine:
    def __init__(
        self,
        config: MemoryConfig,
        p5_learner: MemoryLearner | None = None,  # R-PROTO-LEARN.11 旁路
    ):
        self._config = config
        self._p5_learner = p5_learner

    def update_state(self, state, llm_signal, novelty, tick_id):
        # ... 现有逻辑 ...
        canonical_state = ...  # R85 已有
        if self._p5_learner is not None:
            learner_state = self._p5_learner.update(
                state=canonical_state,
                llm_signal=llm_signal,
                novelty=novelty,
                tick_id=tick_id,
            )
            # canonical_state 永不被 learner 修改
        return canonical_state
```

### 4.2 测试 helper pattern

```python
def _memory_engine(p5_learner=None):
    return MemoryEngine(
        config=MemoryConfig(),
        p5_learner=p5_learner,
    )

# 默认 None 跟生产一致
```

## 5. 论文调研映射（细节）

### 5.1 Kotseruba 2018 metacognition 3 机制 → Tier 1
- **Self-observation** (内省观察):
  - R11 memory `replay_priority_policy` 观察 replay trigger
  - R14 internal_thought `thought_generation_policy` 观察 thought 状态
  - R15 autonomy `continuity_carry_policy` 观察 cross-tick 一致性
- **Self-analysis** (内省分析):
  - R12 thought_gating `signal_normalization_policy` 分析 effort
  - R13 retrieval `tier_selection_policy` 分析 tier 权重
- **Self-regulation** (内省调节):
  - R15 autonomy `proactive_externalization_policy` 主动外化

### 5.2 Parisi 2019 6 大神经机制 → Tier 1
- **Structural plasticity** → R11 memory `consolidation_policy`
- **Memory replay** → R11 memory `replay_priority_policy`
- **Curriculum learning** → R12 thought_gating `continuation_policy`
- **Transfer learning** → R13 retrieval `retrieval_planning_policy`
- **Intrinsic motivation** → R15 autonomy `drive_integration_policy`
- **Multisensory integration** → R14 internal_thought `thought_generation_policy`

### 5.3 De Lange 2021 replay-based → R11
- R11 `replay_priority_policy` = De Lange 2021 唯一 work 的范式
- 4 层 L2-L5 store (R85) 选 replay-based 路线

### 5.4 Bhatt 2019 LTP→DNA methylation → R11
- R11 `consolidation_policy` = DNA methylation 模拟
- 双时间尺度: fast LTP (R85 4 层 L4) / slow DNA methylation (R85 4 层 L5)

### 5.5 Einhauser 2018 pupil = effort → R12
- R12 `signal_normalization_policy` ↔ LC-NE system (pupil dilation)
- norepinephrine → effort → gate sensitivity 学习

## 6. 测试策略

### 6.1 unit test pattern (与 P5-feel 一致)
- **5 算法** 各 3-4 个 test
- **3 态 Regime** 各 1-2 个 test
- **numpy 集成** 2 个 test
- **硬耦合** 1 个 test
- **每 owner 16+ test**
- **总 80+ test**

### 6.2 真 LLM smoke pattern
- `scripts/r_proto_learn_tier1_smoke.py`
- 4 block × 48 对话
- 5 owner 同时跑，验证 P5 learning 不破坏 canonical state
- 比较 R11-R15 之前 vs 之后

## 7. 范围限制（与 P5-feel 一致）
- numpy-only path，**无 fallback**（小黑 2026-06-17 06:59 拍板）
- 5 owner 各自 opt-in 旁路（**不修改** canonical contract）
- 调研分支不 merge main
- 1 commit ship 5 slice
