# M4 Active Inference Owner 设计

## 架构

```
                Sensory Input (8-dim)
                       |
                       v
        +-------------------------------+
        |  HierarchicalGenerativeModel |  <-- Layer 1 简化 generative model
        |  (5 层: 8→16→8→4→2)           |
        +-------------------------------+
                       |
                       | generate(latent) → sensory 重建
                       | recognize(sensory) → latent 推断
                       v
        +-------------------------------+
        |  ActiveInferenceOwner         |
        |  - predict                    |
        |  - compute_proxy_free_energy  |
        |  - minimize_proxy_free_energy |
        |  - active_sampling            |
        |  - variational_free_energy_TRUE (M8 placeholder)
        +-------------------------------+
                       |
                       v
                ActionPolicy (8-dim I 给 SelfModelOwner)
```

## 5 层 HGM 设计

```
sensory (8) → low (16) → mid (8) → high (4) → latent (2)
   ↑          ↑          ↑          ↑         ↑
   W3         W2         W1         W0      prior
   (8,16)     (16,8)     (8,4)      (4,2)

Top-down generate:
  latent → @W0 → tanh → @W1 → tanh → @W2 → tanh → @W3 → tanh → sensory

Bottom-up recognize:
  sensory → @W3.T → tanh → @W2.T → tanh → @W1.T → tanh → @W0.T → tanh → latent
```

**权重形状**:
- weights[0]: (4, 2)  - latent(2) → high(4)
- weights[1]: (8, 4)  - high(4) → mid(8)
- weights[2]: (16, 8) - mid(8) → low(16)
- weights[3]: (8, 16) - low(16) → sensory(8)

**Glorot 初始化**:
```python
scale = sqrt(2 / (in_dim + out_dim))
W = randn((out_dim, in_dim)) * scale
```

## proxy_free_energy vs 真 VFE

### proxy_free_energy (M4 实施)
$$F_{\text{proxy}} = \sum_i (\text{predicted}_i - \text{actual}_i)^2$$

**简化**:只有 prediction error²,缺少 KL 项。

### 真 VFE (M8 升级,Friston 2010)
$$F_{\text{VFE}} = D_{KL}[q(s|o) \| p(s)] - E_q[\ln p(o|s)]$$

**完整**:KL 项 + likelihood 项,需要 PyMC/NumPyro variational inference。

### 关键接口一致性
- `proxy_free_energy(predicted, actual)` → float(简化版)
- `variational_free_energy_TRUE()` → NotImplementedError(M8 placeholder)

M8 升级时,**API 不变**,只换实现。

## M4 训练流程

```python
# 1. 初始化 HGM
hgm = HierarchicalGenerativeModel(lr=0.1)

# 2. 给定 sensory, optimize latent 最小化 reconstruction error
# 用 数值梯度(中心差分,eps=1e-4)
for step in range(n_steps):
    grad = numerical_gradient(latent, sensory)  # 2-dim gradient
    latent = latent - lr * grad

# 3. 检查: F 在 fixed sensory 下应该单调下降
```

**为什么用数值梯度而非解析梯度**:
- 简化实施(M4 阶段够用)
- M8 升级用 PyMC 自动微分(更准确、更快)

## active_sampling 策略

```python
def active_sampling(sensory, n_candidates=5, exploration_noise=0.1):
    candidates = sample_n_candidates_with_noise()
    expected_Fs = estimate_F_for_each_candidate()
    best_idx = argmin(expected_Fs)
    return ActionPolicy(best_action, expected_F, confidence)
```

**简化版**:
- n_candidates 个随机扰动作为候选 action
- expected_F = current_F + penalty(action magnitude) + noise
- 选 expected_F 最小的(贪心策略)

**未来**:policy gradient 优化(留到 M5/M6 真 LLM 集成)

## ActionPolicy 数据结构

```python
@dataclass(frozen=True)
class ActionPolicy:
    action_id: str                  # UUID
    action_vector: np.ndarray       # 8-dim I
    expected_proxy_free_energy: float
    confidence: float               # 1 / (1 + expected_F)
    description: str
```

**frozen**: 防止 LLM 或 reflection owner 篡改已生成 policy。

## 测试覆盖 (39 个)

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestHierarchicalGenerativeModel` | 8 | layer dims / weights / biases / generate / recognize / train_step |
| `TestTrainStep` | 3 | 固定 sensory F 下降 / 多 steps 效果 / 正 float |
| `TestProxyFreeEnergy` | 5 | 完美预测 / 计算正确 / 对称 / HGM 接口 / docstring disclaimer |
| `TestActiveInferenceOwner` | 10 | 4 大方法 + stats + history |
| `TestVariationalFreeEnergyTrue` | 1 | NotImplementedError placeholder |
| `TestActiveInferenceTick` | 5 | tick() 返回字段 + 开关 / 100 tick 稳定 |
| `TestMonotonicallyDecreasing` | 2 | 短 history / 真 history 检查 |
| `TestStats` | 2 | get_stats / stats 更新 |
| `TestEndToEnd` | 3 | 1000 tick / F history / action range |

## 关键设计决策

### 决策 1:5 层 vs 3 层

**选择**:5 层(sensory → low → mid → high → latent)。

**理由**:
- v3 task §2.2 要求 5 层
- 提供足够的"抽象层级"用于不同 time-scale 的特征提取
- 简化实现 vs Friston 2010 严格分层

### 决策 2:数值梯度 vs 解析梯度

**选择**:M4 阶段用数值梯度(中心差分,eps=1e-4)。

**理由**:
- 简化实施,无需手推 backprop
- 慢但足够验证"gradient descent decreases F"的核心逻辑
- M8 用 PyMC 自动微分替换

### 决策 3:Latent optimization vs Weight optimization

**选择**:M4 只优化 latent(2-dim),不动 HGM 权重。

**理由**:
- Weight optimization 需要 backprop through 4 matrices,复杂
- Latent optimization 验证"minimize F"的 basic 概念
- M8 升级可考虑 variational inference 联合优化

### 决策 4:ActionPolicy frozen dataclass

**选择**:ActionPolicy 是 frozen。

**理由**:
- 类似 ReflectionRecord(BoundaryCrossing),防篡改
- audit 需求
- 跨 owner 共享时安全

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| proxy_free_energy 跟真 VFE 混淆 | docstring + 测试严格标注 "NOT VFE" |
| 数值梯度收敛慢 | M8 升级用 PyMC 自动微分 |
| 2-dim latent 限制优化空间 | M4 简化版,M8 variational inference |
| Active sampling 贪心策略次优 | M5/M6 真 LLM policy gradient 替换 |