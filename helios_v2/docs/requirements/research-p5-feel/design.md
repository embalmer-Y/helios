# Design: P5-feel — owner 05 feeling 真学习算法

> 配套 requirement.md
> 范围：5 项算法（探索/固化/DA precision/ACh flexibility/三态切换）一次 ship

## 1. 整体架构

### 1.1 当前位置
helios 评估链：
```
visitor input
  → owner 02 sensory_ingress
    → owner 03 rapid_salience_appraisal (R40 + R-PROTO-LEARN.6 层)
      → owner 04 neuromodulation (R36/R80/R81/R98 9 通道 hormone)
        → owner 05 interoceptive_feeling (R36/R43 7 维 feeling)  ← 本切片改造点
          → owner 06 memory_affect_replay
            → owner 11 internal_thought
              → owner 12-18 ...
```

### 1.2 P5-feel 在 05 owner 内的位置

```
                              owner 05 feeling
                              ┌─────────────────────────────┐
hormone state (9 通道)        │  InteroceptiveFeelingState   │
       │                      │   (7 维)                     │
       ▼                      │                             │
┌──────────────────┐          │   ┌───────────────┐         │
│ feeling_p5_learn │ ────────►│   │  mapping      │         │
│  .py (NEW)       │ 写入      │   │  weights W    │ ──────►│ feeling vector
│                  │ weights  │   │  (7×9 matrix) │         │  (output)
│  - 探索阶段      │          │   │               │         │
│  - 固化阶段      │          │   │  W:           │         │
│  - DA precision  │          │   │  7 行 (感受维) │         │
│  - ACh flex      │          │   │  9 列 (激素)  │         │
│  - 三态切换      │          │   │  + bias 7 维  │         │
└──────────────────┘          │   └───────────────┘         │
       ▲                      └─────────────────────────────┘
       │                              ▲
ground truth (R-PROTO-LEARN.2 LLM)     │ (R36/R43 现行公式)
                                      │
                              feeling = ReLU(W @ hormone + bias)
```

**关键不变量**：
- R36/R43 现行公式（`feeling = ReLU(W @ hormone + bias)`）保留，**只让 W 和 bias 可学习**
- 9→7 mapping 形状不变（7 feeling dim × 9 hormone channel）
- owner 05 边界保持：只读 neuromodulator state + 输出 feeling vector

### 1.3 P5-feel 数据流图

```
每个 tick 1 次 P5-feel update：

  hormone_state (9 通道, [0,1])
        │
        ▼
  ┌──────────────────────────────────────┐
  │  P5FeelLearningPath.update(          │
  │    hormone_state,                    │
  │    llm_appraisal: 7-dim [0,1] | None │  ← R-PROTO-LEARN.2
  │    prior_state: InteroceptiveFeeling │  ← R43 dual-timescale
  │    novelty: float [0,1]              │  ← R35/R40 appraisal
  │    dopamine: float [0,1]             │  ← R36/R80 neuromodulator
  │    acetylcholine: float [0,1]         │  ← R36/R80 neuromodulator
  │    tick_id: int                       │
  │  )                                   │
  └──────────────────────────────────────┘
        │
        ├──► 5 项算法各自运行
        │   1. 探索阶段:  llm_appraisal - current_feeling = residual
        │   2. 固化阶段:  residual < threshold AND stable N tick → commit
        │   3. DA precision: |residual| → precision_weight (高残差低 confidence)
        │   4. ACh flexibility: novelty * ACh → flexibility (high → enable explore)
        │   5. 三态切换: residual trend → explore/model/habitual
        │
        ▼
  ┌──────────────────────────────────────┐
  │  W_new, bias_new, regime             │
  │  - if regime == habitual: W += lr * (LLM_feeling - feeling) * hormone * DA
  │  - if regime == model_based: W += lr * (LLM_feeling - feeling) * hormone * DA * ACh
  │  - if regime == exploratory: W += lr * (LLM_feeling - feeling) * hormone * ACh (no DA gate)
  │  - clip W 形状 / 数值
  └──────────────────────────────────────┘
        │
        ▼
  owner 05 InteroceptiveFeelingState (W_new, bias_new, 7 维)
        │
        ▼
  R43 dual-timescale 包装 → 后续 owner
```

## 2. 5 项算法详细设计

### 2.1 探索阶段（aINS-equivalent）

**输入**：
- `llm_appraisal: tuple[float, ...]` (7 维 [0,1]) ← R-PROTO-LEARN.2 LLM
- `current_feeling: tuple[float, ...]` (7 维 [0,1]) ← owner 05 现行 W @ hormone

**算法**：
```python
def explore_residual(llm_feeling, current_feeling) -> np.ndarray:
    return np.array(llm_feeling) - np.array(current_feeling)  # 7-dim
```

**关键**：
- LLM appraisal 仅在 `llm_appraisal is not None` 时进入（避免 LLM 不可用时强制写入）
- 残差 > 0.05 维数 ≤ 3 维时**不算"探索信号"**（轻微不一致）

### 2.2 固化阶段（gINS-equivalent）

**输入**：
- 滑动窗口 `last_residuals: deque[np.ndarray]` (长度 N=10)
- `commit_threshold: float = 0.02` (residuals 绝对值 < threshold)
- `min_stable_ticks: int = 20` (最少稳定 tick 数)

**算法**：
```python
def should_commit(last_residuals, commit_threshold, min_stable_ticks):
    if len(last_residuals) < min_stable_ticks:
        return False
    return all(np.max(np.abs(r)) < commit_threshold for r in list(last_residuals)[-min_stable_ticks:])
```

**关键**：
- 满足条件 → W 写入 owner 05 config（**首次固化**）
- 写入后**冻结 N tick**（避免在 commit 当下立即开始新探索）

### 2.3 精度信号（DA precision）

**输入**：
- `residual: np.ndarray` (7 维)
- `dopamine: float` [0,1] ← R36/R80
- `precision_floor: float = 0.1`
- `precision_ceiling: float = 1.0`

**算法**（R81 corroboration 范式）：
```python
def dopamine_precision(residual, dopamine, precision_floor, precision_ceiling):
    magnitude = float(np.max(np.abs(residual)))
    # 高残差 → 低 precision（不确定）；低残差 → 高 precision
    base = max(precision_floor, 1.0 - magnitude)
    # dopamine 调 confidence（高精度需要 dopamine 同意）
    return max(precision_floor, min(precision_ceiling, base * (0.5 + 0.5 * dopamine)))
```

**关键**：
- Dopamine 0.5 → precision 减半（中立）
- Dopamine 1.0 + 低残差 → precision 接近 1.0（强学习）
- Dopamine 0.0 → precision 始终 floor（不学）
- 残差 > 0.3 → precision 极低（避免在巨大误差下暴力学）

### 2.4 灵活性信号（ACh flexibility）

**输入**：
- `novelty: float` [0,1] ← R35/R40 appraisal
- `acetylcholine: float` [0,1] ← R36/R80
- `flexibility_threshold: float = 0.4`
- `flexibility_floor: float = 0.1`
- `flexibility_ceiling: float = 1.0`

**算法**：
```python
def ach_flexibility(novelty, acetylcholine, flexibility_threshold, flexibility_floor, flexibility_ceiling):
    # Fermin 2021: ACh = flexibility (新映射 vs 稳定性)
    if acetylcholine < flexibility_threshold:
        return flexibility_floor  # ACh 低 → 不学新 mapping
    raw = novelty * acetylcholine
    return max(flexibility_floor, min(flexibility_ceiling, raw))
```

**关键**：
- ACh < 0.4 → flexibility floor（保守，gINS-equivalent 行为）
- ACh > 0.4 + novelty > 0.5 → flexibility > 0.5（强探索）
- ACh > 0.4 + novelty < 0.2 → flexibility < 0.3（"熟悉 → 弱探索"）
- **作用**：ACh 控制 W 更新幅度 + 是否允许 commit

### 2.5 三态切换（IMAC 三回路）

**输入**：
- `residual_history: deque[np.ndarray]` (长度 N=20)
- `dopamine: float`, `acetylcholine: float`, `novelty: float`

**算法**：
```python
def determine_regime(residual_history, dopamine, acetylcholine, novelty):
    if len(residual_history) < 5:
        return Regime.EXPLORATORY  # 早期默认探索
    recent_magnitude = np.mean([np.max(np.abs(r)) for r in list(residual_history)[-5:]])
    older_magnitude = np.mean([np.max(np.abs(r)) for r in list(residual_history)[-20:-5]])

    # 1. 探索: ACh 高 + novelty 高
    if acetylcholine > 0.4 and novelty > 0.5:
        return Regime.EXPLORATORY
    # 2. 习惯: 残差小且收敛
    if recent_magnitude < 0.02 and abs(recent_magnitude - older_magnitude) < 0.01:
        return Regime.HABITUAL
    # 3. 模型驱动: 默认
    return Regime.MODEL_BASED
```

**关键**：
- 早期 (< 5 tick) → 默认 EXPLORATORY
- 稳定收敛 → HABITUAL
- ACh + novelty 高 → EXPLORATORY
- 其他 → MODEL_BASED
- 三态控制 W 更新方式（见 1.3 数据流图）

## 3. W 更新公式（**3 态差异化**）

```
设：e = LLM_feeling - current_feeling (7-dim residual)
设：h = hormone_state (9-dim)

# HABITUAL（gINS-equivalent）：高 DA precision + 低 ACh flexibility
W_new = W + lr * outer(h, e) * dopamine_precision * 0.5  # ACh floor 时降速

# MODEL_BASED（dINS-equivalent）：DA precision * ACh flexibility 全开
W_new = W + lr * outer(h, e) * dopamine_precision * ach_flexibility

# EXPLORATORY（aINS-equivalent）：ACh flexibility 主导，DA precision 弱
W_new = W + lr * outer(h, e) * ach_flexibility  # DA 不 gate
```

**学习率**：`lr: float = 0.01`（保守，避免发散）
**clip**：`clip W_new in [-2.0, 2.0]`（数值稳定）
**commit 冻结**：commit 后冻结 N=10 tick 不更新

## 4. 公共 API（owner 边界保护）

### 4.1 新文件
- `src/helios_v2/feeling/learning_path.py`（**新**，P5-feel 主体）
  - `P5FeelLearningPath`（class）
  - `Regime`（enum: EXPLORATORY / MODEL_BASED / HABITUAL）
  - `P5FeelLearningConfig`（dataclass: lr / threshold / clip bounds / min_stable_ticks / ...）
  - 公共方法：
    - `update(hormone_state, llm_appraisal, prior_feeling, novelty, dopamine, acetylcholine, tick_id) -> (W_new, bias_new, regime)`
    - `regime() -> Regime`（公开方法）
    - `weights_snapshot() -> tuple[tuple[float, ...], ...]`（7×9 矩阵）
    - `commit_if_stable(last_residuals) -> bool`（公开）

### 4.2 owner 05 集成（**轻微**改动）
- `src/helios_v2/feeling/engine.py`：
  - `InteroceptiveFeelingConfig` 加 `p5_feel_path: P5FeelLearningPath | None = None`（opt-in）
  - `InteroceptiveFeelingState` 加 `weights: tuple[tuple[float, ...], ...]` + `bias: tuple[float, ...]`（默认 = R36/R43 hardcoded）
  - `update_state(...)` 在公式计算后调 `p5_feel_path.update(...)` 拿到新 W/bias → 写入新 state
- 边界保持：owner 05 不直接调 LLM；LLM appraisal 通过 Protocol 注入（与 R-PROTO-LEARN.1/.2 一致）

### 4.3 Protocol 注入（**新增**）
- `LlmAppraisalSource`（已存在，R-PROTO-LEARN.2）— 直接复用
- `NeuromodulatorStateSource`（已存在，R-PROTO-LEARN.1）— 直接复用
- `P5FeelLearningConfig` 接受 `llm_appraisal_source: LlmAppraisalSource | None` + `neuromodulator_source: NeuromodulatorStateSource | None`

## 5. 测试设计

### 5.1 单元测试（**30+ 测试**）
- 探索残差计算（5 测试）
- 固化判定（5 测试）
- DA precision（5 测试）
- ACh flexibility（5 测试）
- 三态切换（5 测试）
- W 更新 clip / 数值稳定（5 测试）

### 5.2 集成测试
- 整库：`pytest tests/ -q --ignore=scratch_r79b`（**0 失败**）
- 新文件：`tests/test_r_proto_learn_7_p5_feel.py`（30+ 测试）

### 5.3 真 LLM smoke
- 沿用 `scripts/r_proto_learn_real_llm_smoke.py` 数据集（8 条 ZH 情绪对话）
- 增 5-7 条 cover 慢路径（连续同情绪 / 激素驱动 / ACh 触发）
- 跑通：每条对话看 7 维 feeling 是否：
  - 与 LLM appraisal 方向一致
  - 经过 N tick 后 W 真有变化
  - dopamine precision 真实作用
  - ACh flexibility 真实触发
  - 三态切换可观察

## 6. 失败兜底（**5 项一起 ship 失败时**）

| 失败模式 | 兜底 |
|---|---|
| 真实 LLM 暴露 DA 公式 bug | 调系数 + 同 commit 修 |
| ACh flexibility 触发太频繁 / 不触发 | 调 threshold 0.4 → 0.3 或 0.5 |
| 三态切换震荡 | 加 hysteresis（连续 2 tick 同 regime 才切换）|
| W 矩阵发散 | 数值 clip + 限制更新幅度 |
| 5 项一起 ship commit 太大 | **失败就放弃，不切分**（按小黑拍板）|

## 7. 不做

- **5 项切片化**：不做（按小黑拍板 1 commit ship）
- **owner 11 PFC 反思 feeling**：不做
- **社会 affective**：不做
- **R40/R97 26 条清理**：不做
- **真实 fMRI 验证**：做不了（用 R83 长跑 + R88 漂移评估作 proxy）

## 8. 与 R-PROTO-LEARN 6 层的关系

| R-PROTO-LEARN 层 | 与 P5-feel 关系 |
|---|---|
| L1 fallback (R40/R97/R98) | P5-feel 假设 hardcoded prototype 仍是 ground truth 候选 |
| L1 interoception (.1) | P5-feel **接收 .1 的 hormone bias** 作 input |
| L2 LLM appraisal (.2) | P5-feel **消费 .2 的 LLM appraisal** 作 ground truth |
| L3 predictive coding (.3) | 不直接耦合 |
| L4 pattern completion (.4) | 不直接耦合（后续可加）|
| L5 Bayesian concept (.5) | P5-feel 提供"7 dim feeling" → .5 消费作 evidence |
