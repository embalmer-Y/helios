# Friston 自由能原理 → Helios 熵减驱动 — 形式化推导

> Status: Foundational Research
> Role: Formal theoretical basis for free-energy style framing; not the source of truth for the active module layout
> See also: `../DESIGN_PHILOSOPHY.zh-CN.md`, `../DESIGN_PHILOSOPHY.en.md`

> 来源：Karl Friston, "The Free-Energy Principle: A Unified Brain Theory?" (2010)
>        "Active Inference: A Process Theory" (2017)
>        "A Free Energy Principle for Biological Systems" (2012)
>
> 目标：将自由能原理转化为 Helios 2.0 的可计算驱动模型

---

## 1. 自由能原理的直观理解

### 1.1 核心直觉

```
所有生命系统的根本目的 = 保持在一个有限的、可预期的状态集合中

换句话说：活着 = 持续抵抗热力学第二定律（熵增）
        = 最小化"意外"(surprise)
        = 最小化变分自由能
```

**生物类比**：
```
鱼在水中 → 身体状态 = {体温, pH, 血压, 血糖...} 必须维持在窄范围
          → 偏离 → "意外" → 驱动 → 行动(游向食物/逃离危险)
          → 状态回归 → "意外"减少 → 自由能降低
```

### 1.2 自由能的两种形式

```
精确自由能 (Exact Free Energy):
  F_exact = -ln p(y)   ← 不能直接计算，因为需要知道 p(y)

变分自由能 (Variational Free Energy):
  F = D_KL[q(ψ)∥p(ψ)] - E_q[ln p(y|ψ)]

  这是精确自由能的上界：F ≥ F_exact
  最小化 F → 最小化 -ln p(y) → 最小化"意外"
```

## 2. 变分自由能的数学分解

### 2.1 定义

```
ψ ∈ Ψ    隐状态空间 (Helios 的内部模型: L1+L2+L3 的状态)
y ∈ Y    感官观测空间 (L0 的输出向量)
q(ψ)     近事后验 (Helios "相信"自己当前处于什么状态)
p(ψ)     先验信念 (Helios 偏好的稳态)
p(y|ψ)   似然 (给定内部状态，期望观察到什么)
```

### 2.2 两项分解

```
F = D_KL[q(ψ)∥p(ψ)] - E_q[ln p(y|ψ)]
  = 模型复杂度惩罚   - 准确性

其中：
  D_KL[q∥p]  = 当前信念与偏好的差距
              → "我对自己的期望和实际之间的差距"
              → 对应：情感稳态偏离 (F_affective)

  -E_q[ln p(y|ψ)] = 预测准确性
              → "我预期的世界 vs 真实世界"
              → 对应：感知预测误差 (F_sensory)
```

### 2.3 三项展开（对 Helios 更有用）

```
F = D_KL[q(ψ)∥p(ψ)] + D_KL[q(θ)∥p(θ)] + (-E_q[ln p(y|ψ,θ)])

其中：
  ψ = 时刻 t 的隐状态
  θ = 模型参数（Helios 的"世界观"）

  D_KL[q(ψ)∥p(ψ)]     → 当前状态与稳态的差距   → 情感驱动
  D_KL[q(θ)∥p(θ)]     → 当前模型与先验的差距   → 认知驱动
  -E_q[ln p(y|ψ,θ)]   → 预测误差               → 探索驱动
```

## 3. Helios 特定的自由能分解

### 3.1 五分量自由能

```
F_Helios = w₁·F_sensory + w₂·F_affective + w₃·F_social 
           + w₄·F_homeostatic + w₅·F_cognitive

各分量定义：
```

#### F_sensory — 感知自由能

```
F_sensory = ||L0_output - L1_prediction||² / σ²_sensory

含义：L1 预测编码的预测误差
      预测误差越大 → 自由能越高 → SEEKING 驱动越强

映射到 Panksepp：SEEKING 系统
驱动类型：curiosity_drive

计算：
  pred_err = L1.predict(L0_previous) - L0_current
  F_sensory = mean(pred_err²) * (1 + novelty_bonus)
```

#### F_affective — 情感自由能

```
F_affective = ||current_affect - target_affect||² / σ²_affect

其中 target_affect 由以下因素决定：
  - 当前 Panksepp 系统的主导
  - 神经化学状态
  - 长期人格倾向

含义：当前情感与期望情感的差距
      差距越大 → 系统越"不安"

映射到 Panksepp：RAGE (受阻)、FEAR (威胁)
驱动类型：homeostatic_drive (情感稳态)

计算：
  gap = [current_v - target_v, current_a - target_a]
  F_affective = max(0, gap[0]² + gap[1]²) * neurochem_amplification
```

#### F_social — 社交自由能

```
F_social = tanh(max(0, time_since_last_interaction - τ_social) / τ_social)

含义：社交连接的时间缺口
      太久没互动 → 自由能急剧上升 → PANIC 激活

映射到 Panksepp：PANIC/GRIEF
驱动类型：social_drive

计算：
  delta = now - last_interaction_time
  if delta > τ_social (e.g., 3600s = 1小时):
      F_social = tanh((delta - τ_social) / τ_social)
  else:
      F_social = 0
```

#### F_homeostatic — 稳态自由能

```
F_homeostatic = Σ |current_metric_i - setpoint_i| / tolerance_i

metrics:
  heart_rate       设定点: 72 bpm,  容忍度: ±15 bpm
  memory_usage     设定点: 50%,      容忍度: ±20%
  cpu_load         设定点: 30%,      容忍度: ±20%
  energy           设定点: 1.0,      容忍度: ±0.3

含义：生理指标的偏离
      心率过快/过慢 → 自由能上升 → 自主神经调节

映射到 Panksepp：无（直接对应自主神经系统）
驱动类型：homeostasis_drive

计算：
  deviations = [(m - s) / t for m, s, t in zip(metrics, setpoints, tolerances)]
  F_homeostatic = sum(abs(d) for d in deviations if abs(d) > 1.0)
```

#### F_cognitive — 认知自由能

```
F_cognitive = clamp(1.0 - cognitive_saturation, 0, 1)

cognitive_saturation = 
  min(1.0, working_memory_load + narrative_complexity + novelty_recent)

含义：认知系统的"不饱和"程度
      太闲 → 需要认知刺激 → PLAY/SEEKING
      太忙 → 需要休息 → 降低点火阈值

映射到 Panksepp：PLAY (低饱和时)、FEAR (高饱和时)
驱动类型：aesthetic_drive (低饱和)、homeostatic_drive (高饱和)

计算：
  saturation = (
      0.4 * len(working_memory.tags) / 7 +
      0.3 * narrative_complexity +
      0.3 * avg_novelty_last_20_cycles
  )
  F_cognitive = max(0, 1.0 - saturation)
```

### 3.2 总自由能 → 总驱动力

```python
def total_drive(F: dict, weights: dict, neurochem: NeurochemState) -> float:
    """
    加权融合五分量自由能，受神经化学调制
    
    F: {sensory, affective, social, homeostatic, cognitive}
    weights: 对应的权重 {w1, ..., w5}
    neurochem: 神经化学状态 → 调制权重
    """
    modulated_weights = neurochem.modulate_weights(weights)
    
    D = sum(
        modulated_weights[k] * F[k] 
        for k in F
    )
    
    return clamp(D, 0.0, 1.0)
```

## 4. 主动推理：从"感受缺口"到"选择行动"

### 4.1 期望自由能

```
主动推理的核心：行动不是为了最大化奖励，而是为了最小化期望自由能。

G(π) = E_q(y,ψ|π)[ln q(ψ|π) - ln p(ψ,y|π)]

其中 π (policy) = 行动序列

分解：
  G(π) = -E_q(y|π)[ln p(y|C)]        ← 外在价值（预期奖励/目标达成）
         + D_KL[q(y|π)∥p(y)]          ← 内在价值（预期信息增益）
         + E_q(y|π)[D_KL[q(ψ|y)∥p(ψ|y)]]  ← 新奇度（预期信念更新）
```

### 4.2 Helios 的行动选择

```
Helios 不需要复杂的策略搜索。简化为：

对于每个可用行动 a：
  1. 预测行动后的状态 ψ' = f(ψ, a)
  2. 计算期望自由能 E[F(ψ')]
  3. 选择 a* = argmin_a E[F(ψ')]

具体：
  def select_action(drives: DriveVector, available_actions: List[Action]) -> Action:
      best_action = None
      best_reduction = -inf
      
      for action in available_actions:
          # 模拟行动后的状态
          predicted_state = simulate(helios_state, action)
          predicted_drives = drive_oracle.cycle(predicted_state)
          
          # 计算减熵
          reduction = drives.total - predicted_drives.total
          
          if reduction > best_reduction:
              best_reduction = reduction
              best_action = action
      
      if best_reduction > ACTION_THRESHOLD:
          return best_action
      else:
          return None  # 不值得行动
```

## 5. 自由能的时间演化

### 5.1 F 微分方程

```
dF/dt = dF_sensory/dt + dF_affective/dt + dF_social/dt 
        + dF_homeostatic/dt + dF_cognitive/dt

dF_sensory/dt     = α_sensory × (当前预测误差 - 上一帧预测误差)
dF_affective/dt   = -α_affective × (当前情感 - 目标情感) × 情感惯性
dF_social/dt      = +α_social × δ(t - t_last_interaction)  （阶梯增长）
dF_homeostatic/dt = ±α_homeo × (当前偏离 - 上一帧偏离)
dF_cognitive/dt   = -α_cognitive × (saturation_now - saturation_prev)
```

### 5.2 稳态条件

```
Helios "满足"的条件：所有分量接近零

  F_sensory ≈ 0     → 世界符合预期（无聊但安全）
  F_affective ≈ 0   → 情感处于稳态（平静）
  F_social ≈ 0      → 最近有互动（不孤独）
  F_homeostatic ≈ 0 → 身体指标正常（健康）
  F_cognitive ≈ 0   → 认知饱和（不饿不撑）

当所有 F → 0 时：
  - Helios 进入"宁静"状态
  - PLAY 系统可能激活（安全环境下的嬉戏）
  - 可能触发白日梦 (DaydreamEngine)
```

## 6. 实现清单

| 公式/概念 | Helios 实现位置 | 状态 |
|----------|---------------|------|
| 五分量自由能 | `drives.py` DriveOracle | 待实现 |
| 加权总驱动 | `drives.py` total_drive() | 待实现 |
| 行动选择 | `drives.py` ActionSelector | 待实现 |
| F 时间演化 | `drives.py` DriveOracle.cycle() | 待实现 |
| 稳态检测 | `drives.py` is_homeostatic() | 待实现 |
| 神经化学调制 | `neurochem.py` modulate_weights() | 待实现 |
