# M1-T2: 8 维 CDS + Radau stiff solver(HOW)

> **任务**:M1-T2 详细设计
> **完成时间**:2026-06-28

## 0. 设计原则

1. **8 维 stiff ODE**:从 v3 plan §3.2 直接引用 alpha 衰减率 + Kuramoto scale
2. **Radau 数值积分**:scipy.solve_ivp(method='Radau')(stiff ODE 工业标准)
3. **clip 防爆**:state ∈ [-10, 10],防 tanh 饱和爆炸
4. **归一化防发散**:|C|max ≤ 1.0,Reward-Hebbian 后等比缩放
5. **owner-neutral**:不污染 v2,独立模块 helios_v2.research_v3_m1.cds

## 1. CDS 数据结构

### 1.1 CDSODEParams(dataclass frozen)

| 字段 | 含义 | 默认值 |
|---|---|---|
| alpha | 8 维衰减率 | [5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.01] |
| beta | 8 维输入权重 | [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1] |
| gamma | 8 维反射权重 | [0.1] × 8 |
| rtol | Radau 相对容差 | 1e-4 |
| atol | Radau 绝对容差 | 1e-6 |

### 1.2 CoupledDynamicalSystem 类

```python
class CoupledDynamicalSystem:
    state: np.ndarray (8 dim)
    C: np.ndarray (8x8 耦合矩阵)
    
    def tick(I, reflect, reward) -> dict:
        # 1. Radau 演化 ODE
        # 2. clip 到 [-10, 10]
        # 3. 可选 reward: Reward-Hebbian 更新 C
        # 4. 归一化 |C|max ≤ 1.0
        # 5. 返回 {state, kuramoto_R, rochat_level_*, solver_success}
    
    @staticmethod
    def _dynamics(t, s, params, C, I, reflect):
        # ds/dt = -alpha*s + C·tanh(s) + beta*I + gamma*reflect
    
    def kuramoto_R(self) -> float:
        # R = (1/8) |sum exp(i * arctan(s_i / scale_i))|
    
    def update_C(self, reward, lr=0.01):
        # dC/dt ~ lr * reward * s * s^T,归一化 max(|C|) ≤ 1.0
    
    def self_experience(self) -> dict:
        # LLM 被动接受:8d_state + R + Rochat + self_unity + agency_strength
```

## 2. 8 维 ODE 演化

### 2.1 数学

```
ds/dt = -alpha * s + C · tanh(s) + beta * I + gamma * reflect
```

### 2.2 数值积分

```python
sol = solve_ivp(
    fun=self._dynamics,
    t_span=(0, self.dt_tick),
    y0=self.state.copy(),
    args=(self.params, self.C, I, reflect),
    method="Radau",   # stiff ODE solver
    rtol=self.params.rtol,
    atol=self.params.atol,
)
```

### 2.3 数值稳定性(clip)

```python
s_safe = np.clip(s, -10.0, 10.0)  # 防 tanh 饱和
```

```python
new_state = np.clip(sol.y[:, -1], -10.0, 10.0)  # 防 solver 极值
```

## 3. Kuramoto R order parameter

### 3.1 数学

```
R(t) = (1/8) |sum_i exp(i * theta_i)|
theta_i = arctan(s_i / scale_i)
```

### 3.2 异构 scale 补偿

8 维 PTS alpha 衰减率差 500 倍(快 vs 慢),theta 必须用异构 scale 才能统一可比:

| 索引 | PTS dimension | scale |
|---|---|---|
| 0 | Bodily Processes | 1.0 |
| 1 | Minimal Experiential | 1.0 |
| 2 | Affective | 1.0 |
| 3 | Intersubjective | 1.0 |
| 4 | Psychological-Cognitive | 1.0 |
| 5 | Narrative | 5.0 |
| 6 | Ecological-Extended | 10.0 |
| 7 | Normative | 30.0 |

scale_i = alpha_i 的倒数归一化:慢维需要更大 state 才能达到相同 theta。

### 3.3 Rochat 5 levels 分段

```
R ∈ [0, 0.2) → Level 0 Confusion
R ∈ [0.2, 0.4) → Level 1 Differentiation
R ∈ [0.4, 0.6) → Level 2 Situation
R ∈ [0.6, 0.8) → Level 3 Identification
R ∈ [0.8, 1.0) → Level 4 Permanence
R = 1.0 → Level 5 Conceptual "I"
```

rochat_level_discrete = int(R * 5)(连续 R → 离散 level)。

## 4. Reward-Hebbian 学习

### 4.1 数学

```
dC/dt = eta * r(t) * s(t) * s(t)^T
```

eta = 0.01(默认学习率),r(t) = reward signal(来自 P5-A RealRPE 或外部)。

### 4.2 归一化防发散

```python
delta_C = lr * reward * np.outer(self.state, self.state)
self.C = self.C + delta_C
max_abs = float(np.max(np.abs(self.C)))
if max_abs > 1.0:
    self.C = self.C / max_abs  # 等比缩放,保持比例
```

## 5. self_experience 涌现态

```python
def self_experience(self) -> dict:
    R = self.kuramoto_R()
    return {
        "8d_state": self.state.tolist(),
        "global_coherence_R": R,
        "rochat_level_continuous": R,
        "rochat_level_discrete": int(R * 5),
        "self_unity": 1.0 - float(np.std(self.state)),
        "agency_strength": float(self.state[1]),  # PTS 2 Minimal Experiential
    }
```

LLM **被动接受**(v3 治理铁律 #8):只"看"涌现态,不修改 8d state 或 C。

## 6. 跨 tick carry(seed_prior_state)

checkpoint v3(R42) 持久化的 CDS state 通过 seed_prior_state 恢复:

```python
def seed_prior_state(self, state, C=None):
    if state.shape != (8,):
        raise ValueError(f"state shape must be (8,), got {state.shape}")
    self.state = state.copy()
    if C is not None:
        if C.shape != (8, 8):
            raise ValueError(f"C shape must be (8, 8), got {C.shape}")
        self.C = C.copy()
```

R42 checkpoint 升级计划:v3 → v4 加 CDS state + C(独立切片)。
