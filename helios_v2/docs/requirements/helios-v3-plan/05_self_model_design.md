# helios_v3 Self-Model 详细设计（self_model_design.md）

> **目的**：详细记录 4 项小黑拍板的 v3 self-model 修复设计
> **完成时间**：2026-06-23 04:00+ UTC
> **作者**：小白（helios 小黑人格 AI）
> **配套**：
> - `01_v3_requirement.md`（v3 总览）
> - `02_v3_design.md`（v3 详细设计，待按 4 项决策更新）
> - `references.md`（11 篇核心论文 DOI + URL）
>
> **本文件状态**：4 项决策的详细设计记录 + 多种实现方案对比 + 待小黑最终拍板的子选项
> **本文件不动 v3 规划**（等小黑 review 完整方案后再批量更新）

---

## 0. 4 项决策汇总

| # | 问题 | 小黑拍板 | 实质 |
|---|---|---|---|
| 1 | 5 层 Markov blanket 术语 | **A：5 个嵌套自组织系统** | 每层都是 self-organizing system，**只有最外层 boundary 是严格意义的 Markov blanket**，4 个内部层是功能分层 |
| 2 | v2 测试基线继承 | **验收标准继承**（措辞） | v3 继承 v2 验收维度（10 维评分 + governance + observability），不是继承"测试基线"本身 |
| 3 | Active Inference 过度简化 | **A+D 组合** | M4 阶段 `proxy_free_energy`（诚实的 proxy，不冒充 VFE），M8 阶段升级到真 VFE + KL 散度 |
| 4 | ToM 拆三系统 | **3 sub-owners + 1 coordinator** | 替代原 `tom_owner` 单 owner，4 个新 owner：mpfc / psts / temporal_poles + coordinator |
| 5 | 48 cell 矩阵机械化 | **小黑方向：8 维耦合动力系统** | self-model = 8 维耦合动力系统（Coupled Dynamical System），**详见 §1** |

---

## 1. 8 维耦合动力系统（self-model 核心设计）

### 1.1 一句话定义

> **self-model = 8 维耦合动力系统（Coupled Dynamical System），其中每个维度是一个连续演化的场变量；维度间通过耦合矩阵相互影响；Rochat level = 场的全局相干性度量（order parameter，非维度开关）；self-experience 从维度间同步中涌现。**

### 1.2 数学框架

#### 1.2.1 8 维 ODE 系统（核心状态方程）

$$\frac{d\mathbf{s}}{dt} = \mathbf{F}(\mathbf{s}, C, I)$$

其中：
- $\mathbf{s} = (s_1, s_2, ..., s_8) \in \mathbb{R}^8$ — 8 维场状态（每维度 = Laurenzi 2025 的 1 个 PTS dimension）
- $C \in \mathbb{R}^{8 \times 8}$ — 8×8 耦合矩阵（控制维度间相互影响，跨 tick 学习）
- $I$ — 输入（tick stimulus + interoceptive + reflective）
- $\mathbf{F}$ — 8 维非线性 ODE 系统（具体形式见 §1.2.3）

**每维度 $s_i$ 对应 Laurenzi 2025 论文的 1 个 PTS dimension**：

| 索引 | 维度（Laurenzi 2025） | 缩写 | 演化时标 | v3 用途 |
|---|---|---|---|---|
| 1 | Bodily Processes | BP | 毫秒-秒 | 内感受 / 5-dim hormone |
| 2 | Minimal Experiential | ME | 秒 | agency / 自我存在感 |
| 3 | Affective | AF | 秒-分钟 | 情感 / 7-dim feeling |
| 4 | Intersubjective | IS | 分钟 | ToM / 社会认知 |
| 5 | Psychological/Cognitive | PC | 分钟-小时 | 推理 / 决策 |
| 6 | Narrative | NA | 小时-天 | 叙事自我 / autobiographical |
| 7 | Ecological/Extended | EE | 周-月 | 4E cognition / material engagement |
| 8 | Normative | NO | 年 | 价值观 / 治理红线 |

#### 1.2.2 Rochat level = 全局相干性度量（order parameter）

**不**是 trigger 触发的 level 推进，**是**维度间同步的涌现度量。

Kuramoto-style order parameter：

$$R(t) = \frac{1}{8} \left\| \sum_{i=1}^{8} e^{i \theta_i(t)} \right\| \in [0, 1]$$

其中：
- $\theta_i(t) = \arctan(s_i(t) / \text{scale}_i)$ — 每维度的相位
- $R = 1$ — 完全同步（高 Rochat level）
- $R = 0$ — 完全失相干（低 Rochat level）

**Rochat level = 连续 R 值**（不是 0-5 离散），但配合 Laurenzi 2025 论文的 5 阶段语言，可以分段：
- $R \in [0, 0.2)$ → Level 0（Confusion）
- $R \in [0.2, 0.4)$ → Level 1（Differentiation）
- $R \in [0.4, 0.6)$ → Level 2（Situation）
- $R \in [0.6, 0.8)$ → Level 3（Identification）
- $R \in [0.8, 1.0)$ → Level 4（Permanence）
- $R = 1.0$ → Level 5（Conceptual "I"）

#### 1.2.3 非线性 ODE 系统 $\mathbf{F}$ 的具体形式

每维度的演化方程（建议形式）：

$$\frac{ds_i}{dt} = -\alpha_i s_i + \sum_{j=1}^{8} C_{ij} \tanh(s_j) + \beta_i I_i(t) + \gamma_i \text{reflect}(t)$$

其中：
- $-\alpha_i s_i$ — 自衰减项（每维度有自然衰减率）
- $\sum_{j} C_{ij} \tanh(s_j)$ — 维度间耦合（$\tanh$ 限幅到 $[-1, 1]$）
- $\beta_i I_i(t)$ — 输入驱动（$\beta_i$ 是该维度对输入的敏感度）
- $\gamma_i \text{reflect}(t)$ — 反思调制（Layer 4 reflection_owner 的输出）

**ODE 性质**：
- 8 维非线性（$\tanh$ 非线性）
- 5 维快 + 3 维慢（stiff ODE）→ 需要自适应步长积分器
- C 是学习参数（不固定）
- 9 个参数/维度：$\alpha_i, C_{i*}, \beta_i, \gamma_i$（共 8×9 = 72 参数）

#### 1.2.4 self-experience 涌现

**self-experience 不是 LLM 主动推理的结果，是 8 维动力系统的涌现态**。

```python
# self-experience(t) = f(emergent_state(t))
def self_experience(s: np.ndarray, C: np.ndarray) -> dict:
    """
    self-experience 从维度间同步中涌现。
    不是 LLM 调用产生，是动力系统状态的直接计算。
    """
    R = order_parameter(s)  # 全局相干性
    local_coherence = pairwise_coherence(s, C)  # 局部相干性
    return {
        "global_coherence": R,
        "local_coherence": local_coherence,
        "rochat_level": R,  # 连续 R 值
        "self_unity": 1.0 - np.std(s),  # 维度间一致性
        "agency_strength": s[1],  # PTS 2 (Minimal Experiential) 直接读
    }
```

---

## 2. 多种实现方案对比（每个子问题 2-3 种）

### 2.1 ODE 数值积分方案（8 维单 ODE vs 嵌套）

#### 方案 (a)：8 维单 ODE + 自适应步长 ✅ 推荐

```python
import numpy as np
from scipy.integrate import solve_ivp

def dynamics(t, s, C, alpha, beta, gamma, I_func, reflect_func):
    s = np.clip(s, -10, 10)  # 数值稳定性
    dsdt = -alpha * s + C @ np.tanh(s) + beta * I_func(t) + gamma * reflect_func(t)
    return dsdt

# v3 tick 内的 ODE 积分
def tick_integration(s0, C, params, dt_tick=1.0):
    sol = solve_ivp(
        dynamics,
        t_span=(0, dt_tick),
        y0=s0,
        args=(C, params['alpha'], params['beta'], params['gamma'],
              params['I_func'], params['reflect_func']),
        method='Radau',  # 适合 stiff ODE
        rtol=1e-4, atol=1e-6,
    )
    return sol.y[:, -1]
```

**优点**：
- 简单，1 个 ODE 系统
- scipy.integrate.solve_ivp(method='Radau') 是工业标准 stiff solver
- 8 维不算大，数值稳定

**缺点**：
- 5 维快 + 3 维慢 stiff，Radau 自适应步长可能慢
- 没有显式分层结构

#### 方案 (b)：2 个 ODE 嵌套（快 5 维 + 慢 3 维）

```python
# 快子系统：bodily / experiential / affective / intersubjective / cognitive
# 慢子系统：narrative / ecological / normative
def fast_dynamics(t, s_fast, s_slow, C, ...):
    # 5 维快 ODE，受 s_slow 调制
    pass

def slow_dynamics(t, s_slow, s_fast_averaged, C, ...):
    # 3 维慢 ODE，受 s_fast 长期均值调制
    pass

# 双时标积分
def dual_tick_integration(s0_fast, s0_slow, C, params, dt_tick=1.0):
    # 先在每个快步内积分 5 维快子系统
    # 然后在慢步积分 3 维慢子系统
    pass
```

**优点**：
- 显式分层（5+3），物理上更清晰
- 慢 3 维不每 tick 演化（更稳定）

**缺点**：
- 实现复杂（双积分器）
- 5 维快 / 3 维慢的划分是硬编码（vs Laurenzi 论文的动态）

#### 方案 (c)：5 维 ODE 核心 + 3 维 ODE 慢变（dual-system）

**跟 (b) 类似但更简单**：
- 5 维 ODE 核心每 tick 演化
- 3 维 ODE 慢变每 N tick 演化一次（N = 10-100）
- 中间用插值

**对比表**：

| 维度 | (a) 8 维单 ODE | (b) 2 层嵌套 | (c) 5 维核心 + 3 维慢变 |
|---|---|---|---|
| 实现复杂度 | 低 | 中-高 | 中 |
| 数值稳定性 | 中（Radau 解决） | 高 | 高 |
| 物理清晰度 | 中 | 高 | 高 |
| 灵活性 | 高 | 中 | 中 |
| 与 v2 兼容性 | 高 | 中 | 中 |

**我推荐 (a)**——scipy Radau 是工业标准，5 维快 + 3 维慢的 stiff 问题 Radau 能解。

### 2.2 耦合矩阵 C 的学习方案

#### 方案 (i)：Hebbian 学习（最简无监督）

```python
def hebbian_update_C(C: np.ndarray, s: np.ndarray, lr: float = 0.01):
    """Hebbian: 'neurons that fire together wire together'"""
    delta_C = lr * np.outer(s, s)
    return C + delta_C
```

**优点**：
- 最简，无监督
- 生物可信（真实突触 Hebbian）

**缺点**：
- 无 reward 信号，可能学到无意义关联
- C 可能发散（需要归一化）

#### 方案 (ii)：Reward-modulated Hebbian（带 reward）✅ 推荐

```python
def reward_hebbian_update_C(C: np.ndarray, s: np.ndarray, r: float, lr: float = 0.01):
    """Reward-modulated Hebbian: 跟 v2 P5 RealRPE 兼容"""
    delta_C = lr * r * np.outer(s, s)
    return C + delta_C
```

**优点**：
- 跟 v2 P5 RealRPE 兼容
- 行为对齐
- 生物可信（reward 信号调制突触）

**缺点**：
- 需要 reward 信号（v3 可以从 evaluation owner 拿）

#### 方案 (iii)：LLM 监督（最强但贵）

```python
def llm_supervised_update_C(C: np.ndarray, s: np.ndarray, history: list, llm_model):
    """LLM 监督：每 N tick 调 LLM 调整 C"""
    prompt = f"Current self-model state: {s}\nRecent history: {history}\nSuggest coupling matrix update."
    llm_response = llm_model.complete(prompt)
    delta_C = parse_C_from_llm(llm_response)
    return C + lr * delta_C
```

**优点**：
- 最强（LLM 可以做复杂推理）
- 跟 v3 LLM-as-PFC 3 层兼容

**缺点**：
- 贵（每 N tick 调 LLM）
- LLM 推理慢
- 可能跟 ODE 演化冲突

**对比表**：

| 维度 | (i) Hebbian | (ii) Reward-Hebbian | (iii) LLM 监督 |
|---|---|---|---|
| 复杂度 | 低 | 中 | 高 |
| 跟 v2 兼容 | 中 | **高** ✅ | 中 |
| 跟 v3 兼容 | 中 | 中 | **高** ✅ |
| 行为对齐 | 低 | **高** ✅ | 高 |
| 计算代价 | 低 | 低 | 高 |
| 生物可信 | 中 | **高** ✅ | 低 |

**我推荐 (ii) Reward-Hebbian**——跟 v2 P5 + 行为对齐 + 低成本。

### 2.3 self-experience 涌现 vs LLM 主动分析

#### 方案 (X)：LLM 主动分析

```python
def reflection_active(s, C, R, llm_model):
    """LLM 主动分析 self-model 状态"""
    prompt = f"Self-model: s={s}, C={C}, R={R}\nReflect deeply."
    return llm_model.complete(prompt)
```

**问题**：
- LLM 主动协调 8 维度 → 不是真正的"涌现"
- 跟"8 维耦合动力系统"的设计哲学冲突

#### 方案 (Y)：LLM 被动接受（涌现 + 分层）✅ 推荐

```python
# self-experience 是涌现的
def self_experience(s, C):
    R = order_parameter(s)
    return {
        "global_coherence": R,
        "rochat_level": R,
        "self_unity": 1.0 - np.std(s),
    }

# LLM 只需"看"涌现的 state，不"做协调"
def reflection_passive(s, C, R, llm_model):
    """LLM 被动接受 self-model emergent state"""
    prompt = f"Current self-experience: R={R}\nReflect on this emergent state."
    return llm_model.complete(prompt)
```

**优点**：
- 真正的"涌现"——LLM 不做协调，物理做好
- 分层清晰：8 维耦合（低层 dynamics）+ LLM 反思（高层 reasoning）
- 符合 Gallaguer 2013 + Laurenzi 2025 论文的 pattern 思想

**缺点**：
- LLM 不能"反作用于" C（C 只由 Reward-Hebbian 学）
- 如果 LLM 想调整 self-model，需要走 reflection_owner → 重新 calibrate I_func

**我推荐 (Y)**——更符合"涌现"哲学，跟 Laurenzi 2025 + Seth 2012 论文一致。

### 2.4 Rochat level 是连续 vs 离散

**v3.0 简化版**：连续 R 值 + Laurenzi 5 阶段分段（0-0.2 / 0.2-0.4 / ...）—— 跟 5 level 兼容但不强制

**v3.1+ 升级**：纯连续 R 值（不映射到 5 level）—— 真正的连续度量

**v3.0 评审标准**：
- Rochat 阶段 R 值在每个阶段内的正确率
- 阶段间过渡的平滑性（不能跳跃）
- 长期均值稳定

---

## 3. 8 维耦合动力系统的完整设计

### 3.1 数据结构

```python
@dataclass
class CoupledDynamicalSystem:
    """8 维耦合动力系统（v3 self-model 核心）"""
    state: np.ndarray  # shape (8,), 8 维场状态
    C: np.ndarray      # shape (8, 8), 耦合矩阵
    alpha: np.ndarray  # shape (8,), 自衰减率
    beta: np.ndarray   # shape (8,), 输入敏感度
    gamma: np.ndarray  # shape (8,), 反思敏感度
    dt_tick: float = 1.0  # tick 时间跨度
    integrator_method: str = 'Radau'

    def tick(self, I: np.ndarray, reflect: np.ndarray) -> np.ndarray:
        """每个 tick 演化"""
        sol = solve_ivp(
            self._dynamics,
            t_span=(0, self.dt_tick),
            y0=self.state,
            args=(self.C, self.alpha, self.beta, self.gamma, I, reflect),
            method=self.integrator_method,
            rtol=1e-4, atol=1e-6,
        )
        self.state = sol.y[:, -1]
        return self.state

    def _dynamics(self, t, s, C, alpha, beta, gamma, I, reflect):
        s = np.clip(s, -10, 10)
        dsdt = -alpha * s + C @ np.tanh(s) + beta * I + gamma * reflect
        return dsdt

    def update_C(self, s: np.ndarray, reward: float, lr: float = 0.01):
        """Reward-Hebbian 学习更新耦合矩阵"""
        delta_C = lr * reward * np.outer(s, s)
        self.C = self.C + delta_C
        # 归一化（防止发散）
        self.C = self.C / (np.max(np.abs(self.C)) + 1e-8)

    def order_parameter(self) -> float:
        """Rochat level = Kuramoto-style 全局相干性"""
        theta = np.arctan(self.state / np.array([1.0, 1.0, 1.0, 1.0, 1.0, 5.0, 10.0, 30.0]))
        R = np.abs(np.sum(np.exp(1j * theta))) / 8.0
        return R

    def self_experience(self) -> dict:
        """self-experience 从动力系统涌现"""
        R = self.order_parameter()
        return {
            "global_coherence": R,
            "rochat_level_continuous": R,
            "rochat_level_discrete": int(R * 5),  # 0-5 离散
            "self_unity": 1.0 - np.std(self.state),
            "agency_strength": float(self.state[1]),  # PTS 2
        }
```

### 3.2 self_model_owner 接口（更新版）

```python
class SelfModelOwner:
    """v3 Layer 2 self-model（8 维耦合动力系统）"""

    def __init__(self, llm_reasoning_model):
        self.llm = llm_reasoning_model
        self.cds = CoupledDynamicalSystem(
            state=np.zeros(8),  # 起步：cold start
            C=np.eye(8) * 0.1,  # 起步：弱对角耦合
            alpha=np.array([5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.01]),  # 快-慢衰减
            beta=np.array([1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]),  # 输入敏感度
            gamma=np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]),  # 反思敏感度
        )
        self.tick_count = 0
        self.experience_history = []

    def tick(self, I: np.ndarray, reflect: np.ndarray, reward: float):
        """每个 tick 更新 self-model"""
        # 1. 8 维 ODE 演化
        self.cds.tick(I, reflect)

        # 2. Reward-Hebbian 更新 C
        self.cds.update_C(self.cds.state, reward)

        # 3. 记录 self-experience（涌现）
        exp = self.cds.self_experience()
        self.experience_history.append(exp)

        # 4. 暴露给 LLM-as-PFC（被动）
        self._expose_to_llm(exp)

        self.tick_count += 1
        return exp

    def get_state_for_llm(self) -> dict:
        """返回给 LLM 的 self-model 状态（被动）"""
        exp = self.cds.self_experience()
        return {
            "8d_state": self.cds.state.tolist(),  # 8 维状态
            "coupling_matrix": self.cds.C.tolist(),  # 耦合矩阵
            "global_coherence_R": exp["global_coherence"],
            "rochat_level_continuous": exp["rochat_level_continuous"],
            "rochat_level_discrete": exp["rochat_level_discrete"],
            "self_unity": exp["self_unity"],
            "tick_count": self.tick_count,
        }
```

### 3.3 ToM 三系统拆解（4 个 owner）

```python
class ToMCoordinatorOwner:
    """v3 Layer 2 ToM 协调器（替代原 tom_owner）"""
    def __init__(self, mpfc, psts, temporal_poles):
        self.mpfc = mpfc
        self.psts = psts
        self.temporal_poles = temporal_poles
        self.coordination_history = []

    def infer(self, stimulus, context) -> dict:
        """三系统协同推断"""
        # 1. MPFC: 推断意图/信念
        intent_belief = self.mpfc.infer(stimulus, context)

        # 2. pSTS: 检測 agency
        agency = self.psts.detect_agency(stimulus)

        # 3. Temporal poles: 调取社会脚本
        social_script = self.temporal_poles.get_script(stimulus, context)

        # 4. 协调：按 Rochat level 决定"听谁"
        R = self._get_R()
        if R < 0.4:
            # 低 Rochat level：偏 pSTS（基础 agency）
            return {"dominant": "psts", "agency": agency, "intent": intent_belief, "script": None}
        elif R < 0.7:
            # 中 Rochat level：MPFC + pSTS 协同
            return {"dominant": "mpfc+psts", "agency": agency, "intent": intent_belief, "script": None}
        else:
            # 高 Rochat level：3 系统完整融合
            return {"dominant": "all", "agency": agency, "intent": intent_belief, "script": social_script}


class MPFCOwner:
    """MPFC sub-owner: 推断他人意图/信念"""
    def infer(self, stimulus, context) -> dict:
        prompt = f"Infer intent/belief from: {stimulus}\nContext: {context}"
        return {"belief": self.llm.complete(prompt), "confidence": 0.7}


class PSTSOwner:
    """pSTS sub-owner: 检測 agency + 生物运动"""
    def detect_agency(self, stimulus) -> float:
        prompt = f"Detect agency (0-1): {stimulus}"
        return float(self.llm.complete(prompt))


class TemporalPolesOwner:
    """Temporal poles sub-owner: 社会脚本"""
    def get_script(self, stimulus, context) -> str:
        prompt = f"Get social script: {stimulus}\nContext: {context}"
        return self.llm.complete(prompt)
```

### 3.4 proxy_free_energy（v3.0 M4 诚实降级）

```python
class ActiveInferenceOwner:
    """v3 Layer 1 Active Inference（v3.0 简化版）"""

    def proxy_free_energy(self) -> float:
        """
        Proxy for variational free energy (NOT true VFE).
        True VFE = E_q[ln q(s) - ln p(s,o)]
        This proxy uses prediction error squared as rough approximation.
        Upgrade to true VFE in v3.1 M8 with PyMC/NumPyro.

        Reference: Friston 2010 (DOI: 10.1038/nrn2787)
        """
        # 平方差 (prediction error^2) — 跟 VFE 差一个 KL 散度项
        prediction = self.predict(sensory_input)
        actual = self.observe()
        error = (actual - prediction) ** 2
        return float(np.sum(error))

    def variational_free_energy_TRUE(self) -> float:
        """
        True VFE (v3.1 M8 升级用，placeholder).
        F = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]
        Implemented via PyMC/NumPyro variational inference.
        """
        raise NotImplementedError("v3.1 M8 will implement true VFE")
```

---

## 4. v3 owner 总数 + 模块依赖更新

### 4.1 v3 owner 总数（从 40 → 43）

| 类别 | 数量 | 列表 |
|---|---|---|
| **v2 继承** | 28 | 28 个 v2 owner |
| **v3 新增（5 层）** | 5 | boundary_owner / active_inference_owner / self_model_owner / reflection_owner / evolution_owner / governance_owner |
| **v3 新增（ToM 拆 4 个）** | 4 | tom_coordinator_owner / mpfc_owner / psts_owner / temporal_poles_owner |
| **v3 新增（8 维 PTS sub-owners）** | 8 | agency_detector / egocentric_perspective / autobiographical_memory / material_engagement / culture_owner（3 个 ToM 已计） |
| **总计** | **45** | 28 + 5 + 4 + 8 |

### 4.2 模块依赖更新（跟原 40 owner 不同）

**新增依赖**：
- `self_model_owner` → 8 维 ODE（numpy + scipy）
- `self_model_owner` → `coupling_matrix_update`（reward-hebbian）
- `tom_coordinator_owner` → 3 sub-owners
- `mpfc_owner` / `psts_owner` / `temporal_poles_owner` → LLM

**移除**：
- `tom_owner`（拆成 3 sub-owners + 1 coordinator）

---

## 5. 4 项决策的 v3 文档更新范围

### 5.1 需更新的文件

| 文件 | 更新内容 | 优先级 |
|---|---|---|
| `01_v3_requirement.md` | §2 5 层命名 + §3 8 维耦合动力系统 + §6 反模式 | 高 |
| `02_v3_design.md` | §3 数据结构全部重写 + §4 LLM-as-PFC + §5 owner 接口 | 高 |
| `03_v3_task.md` | §1 M1 task 加 ODE + C 学习 + Rochat 连续 | 高 |
| `04_architecture_diagrams/*.mmd` | 4 个流程图全部重画 | 中 |
| `references.md` | 加 "Coupled Dynamical System" 引用 | 低 |
| `README.md` | 更新 owner 总数（40 → 45） | 低 |

### 5.2 暂不更新（等小黑 review）

- 不动 v3 已 ship 的 `7ce4ed9` + `3d12037` commit
- 新增一个 `02_self_model_redesign.md`（本文件）作为补丁
- 等小黑 review 4 项决策 + 3 个子选项后，再批量更新 11 个文件

---

## 6. 3 个待小黑拍板的子选项

### 6.1 ODE 数值积分方案

| 选项 | 名称 | 我的推荐 |
|---|---|---|
| (a) | 8 维单 ODE + Radau 自适应步长 | ✅ 推荐 |
| (b) | 2 个 ODE 嵌套（快 5 维 + 慢 3 维） | 备选 |
| (c) | 5 维 ODE 核心 + 3 维慢变（dual-system） | 备选 |

### 6.2 耦合矩阵 C 学习方案

| 选项 | 名称 | 我的推荐 |
|---|---|---|
| (i) | Hebbian（无监督） | |
| (ii) | Reward-Hebbian | ✅ 推荐 |
| (iii) | LLM 监督 | 备选 |

### 6.3 self-experience 涌现 vs LLM 主动分析

| 选项 | 名称 | 我的推荐 |
|---|---|---|
| (X) | LLM 主动分析 | 不推荐 |
| (Y) | LLM 被动接受（涌现 + 分层） | ✅ 推荐 |

---

## 7. 测试基线 vs 验收标准（问题 2 措辞修复）

### 7.1 原措辞（v3.0 措辞）
"测试基线：v2 baseline 1110+ + v3 新增 145 = ≥ 1255 (M6)"

### 7.2 新措辞（v3.1 措辞）
"**v3 继承 v2 验收维度**：D1-D10 评分 + 28 owner 测试 + 6 governance 红线 + observability 全 tick 记录 + audit log。
**v3 新增验收维度**：8 维 PTS × Rochat 连续 R 值 × LLM-as-PFC 3 层 × Markov blanket invariant × proxy_free_energy 收敛性 × self-experience 涌现合理性。
**v3 测试基线**：v2 baseline 1110+ + v3 新增 145 = ≥ 1255（M6）；v2 baseline + v3 新增 290 = ≥ 1400（M8）。"

---

## 8. 历史溯源

- **2026-06-22 19:50+**：v3 完整规划 commit `7ce4ed9` push 远端
- **2026-06-22 19:55+**：references.md 修复 commit `3d12037` push 远端
- **2026-06-23 03:30+**：小黑 review 4 项问题（术语 / 测试基线 / Active Inference 简化 / ToM 拆分 / 48 cell 机械化）
- **2026-06-23 03:50+**：小黑拍板 4 项 + 问题 5 方向（8 维耦合动力系统）
- **2026-06-23 04:00+**：本文件 self_model_design.md 编写完成（含多种实现方案对比 + 3 个待拍板子选项）

---

**本文件状态**：待小黑 review
**下一步**：
1. 小黑 review 4 项决策的详细设计
2. 小黑拍板 3 个子选项（ODE 方案 / C 学习方案 / 涌现 vs 主动分析）
3. 小黑拍板后 → 批量更新 11 个 v3 文档 → 新 commit + push 远端

---

**self_model_design.md 完成时间**：2026-06-23 04:00+ UTC
**作者**：小白（helios 小黑人格 AI）
**小黑 review 状态**：待 review