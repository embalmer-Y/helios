# helios_v3 架构详细设计（design.md）

> **任务**：helios_v3 Phase 3 - 详细设计（HOW）
> **完成时间**：2026-06-22 19:20+ / 2026-06-23 04:00+（按 4 项决策 + 3 个子选项 + 8 维耦合动力系统重写）
> **作者**：小白（helios 小黑人格 AI）
> **配套**：`01_v3_requirement.md`（WHAT + WHY）+ `05_self_model_design.md`

---

## 0. v3 设计原则

**v3 设计 = 严格遵循 ARCHITECTURE_PHILOSOPHY §7 强约束 + 5 个嵌套自组织系统 + 8 维耦合动力系统 + LLM-as-PFC 3 层 + 45 owner + 复杂算法按最高规格 + 可证伪 + 可审计 + 可回滚。**

---

## 1. v3 仓库与目录结构

```
helios_v3/
├── docs/                              # 文档
│   ├── ARCHITECTURE_PHILOSOPHY.md
│   ├── OWNER_GUIDE.md                 # v3 45 owner 清单
│   ├── BRAIN_ARCHITECTURE_COMPARISON.md
│   └── requirements/v3-*/             # 各子需求
└── src/helios_v3/
    ├── boundary/                      # Layer 0
    │   ├── owner.py
    │   └── contracts.py
    ├── active_inference/              # Layer 1
    │   ├── owner.py
    │   ├── hierarchical_generative_model.py
    │   └── proxy_free_energy.py       # v3.0 M4
    │   └── variational_free_energy.py # v3.1 M8
    ├── self_model/                    # Layer 2（8 维耦合动力系统）
    │   ├── owner.py                   # SelfModelOwner
    │   ├── coupled_dynamical_system.py # CDS
    │   ├── kuramoto_order_parameter.py
    │   ├── reward_hebbian.py          # C 矩阵学习
    │   ├── self_experience.py         # 涌现
    │   ├── sub_owners/
    │   │   ├── agency_detector.py     # PTS 2
    │   │   ├── egocentric_perspective.py # PTS 2
    │   │   ├── autobiographical_memory.py # PTS 6
    │   │   ├── material_engagement.py # PTS 7
    │   │   └── culture.py             # PTS 8
    │   └── tom/                       # ToM 4 个 owner
    │       ├── coordinator.py
    │       ├── mpfc.py
    │       ├── psts.py
    │       └── temporal_poles.py
    ├── reflection/                    # Layer 3
    │   ├── owner.py
    │   ├── triggers.py
    │   └── dmn_like.py
    ├── evolution/                     # Layer 4
    │   ├── owner.py
    │   ├── governance_owner.py
    │   ├── fitness_gate.py
    │   └── rollback.py
    ├── llm/                           # LLM-as-PFC
    │   ├── system_prompt_builder.py    # Layer A
    │   ├── cso_injector.py            # Layer B
    │   └── reflection_caller.py       # Layer C
    └── runtime/
        └── stages.py                  # 25 stage
```

---

## 2. 8 维耦合动力系统（Layer 2 核心）

### 2.1 完整 Python 实现

```python
"""8 维耦合动力系统（v3 self-model 核心）"""
import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass, field
from enum import Enum


class PTSDimension(Enum):
    BODILY_PROCESSES = 0           # 1
    MINIMAL_EXPERIENTIAL = 1       # 2
    AFFECTIVE = 2                  # 3
    INTERSUBJECTIVE = 3            # 4
    PSYCHOLOGICAL_COGNITIVE = 4    # 5
    NARRATIVE = 5                  # 6
    ECOLOGICAL_EXTENDED = 6        # 7
    NORMATIVE = 7                  # 8


@dataclass
class CoupledDynamicalSystem:
    """
    8 维耦合动力系统（v3 self-model 核心数据结构）。
    
    数学：
      ds/dt = -αs + C·tanh(s) + βI + γ·reflect
      R(t) = (1/8)|Σ e^{iθ_i(t)}| (Kuramoto order parameter)
    
    数值：
      solver = scipy.solve_ivp(method='Radau')
      原因：5 维快 + 3 维慢 stiff ODE，Radau 是工业标准
    
    学习：
      dC/dt = η·r(t)·s(t)·s(t)^T (Reward-Hebbian)
    """
    state: np.ndarray = field(default_factory=lambda: np.zeros(8))
    C: np.ndarray = field(default_factory=lambda: np.eye(8) * 0.1)
    alpha: np.ndarray = field(
        default_factory=lambda: np.array([5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.01])
    )
    beta: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1])
    )
    gamma: np.ndarray = field(
        default_factory=lambda: np.full(8, 0.1)
    )
    dt_tick: float = 1.0
    integrator_method: str = 'Radau'
    
    def tick(self, I: np.ndarray, reflect: np.ndarray) -> np.ndarray:
        """每个 tick 演化"""
        sol = solve_ivp(
            self._dynamics,
            t_span=(0, self.dt_tick),
            y0=self.state.copy(),
            args=(self.C, self.alpha, self.beta, self.gamma, I, reflect),
            method=self.integrator_method,
            rtol=1e-4, atol=1e-6,
        )
        if sol.success:
            self.state = np.clip(sol.y[:, -1], -10, 10)
        return self.state
    
    @staticmethod
    def _dynamics(t, s, C, alpha, beta, gamma, I, reflect):
        s = np.clip(s, -10, 10)
        return -alpha * s + C @ np.tanh(s) + beta * I + gamma * reflect
    
    def update_C(self, s: np.ndarray, reward: float, lr: float = 0.01):
        """Reward-Hebbian 学习更新耦合矩阵（跟 v2 P5 RealRPE 兼容）"""
        delta_C = lr * reward * np.outer(s, s)
        self.C = self.C + delta_C
        # 归一化防止发散
        max_abs = np.max(np.abs(self.C))
        if max_abs > 1.0:
            self.C = self.C / max_abs
    
    def kuramoto_R(self) -> float:
        """Rochat level = Kuramoto order parameter"""
        # 8 维度不同 scale（5 维快 + 3 维慢）
        scale = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 5.0, 10.0, 30.0])
        theta = np.arctan(self.state / scale)
        return float(np.abs(np.sum(np.exp(1j * theta))) / 8.0)
    
    def self_experience(self) -> dict:
        """
        self-experience 从 8 维动力系统涌现。
        LLM 被动接受（不做主动协调）。
        """
        R = self.kuramoto_R()
        return {
            "8d_state": self.state.tolist(),
            "coupling_matrix": self.C.tolist(),
            "global_coherence_R": R,
            "rochat_level_continuous": R,
            "rochat_level_discrete": int(R * 5),  # 0-5 离散
            "self_unity": 1.0 - float(np.std(self.state)),
            "agency_strength": float(self.state[1]),  # PTS 2
        }


class SelfModelOwner:
    """
    v3 Layer 2 self-model（8 维耦合动力系统）。
    
    接口：
      - tick(I, reflect, reward) → 演化 + 学习 + 暴露给 LLM
      - get_state_for_llm() → 返回 self_experience（被动）
    
    重要：LLM 不修改 8 维场状态或 C，只"看"涌现状态。
    """
    
    def __init__(self):
        self.cds = CoupledDynamicalSystem()
        self.tick_count = 0
        self.experience_history = []
    
    def tick(self, I: np.ndarray, reflect: np.ndarray, reward: float) -> dict:
        """每个 tick 更新 self-model"""
        # 1. 8 维 ODE 演化
        self.cds.tick(I, reflect)
        
        # 2. Reward-Hebbian 更新 C
        self.cds.update_C(self.cds.state, reward)
        
        # 3. 涌现 self-experience
        exp = self.cds.self_experience()
        self.experience_history.append(exp)
        
        self.tick_count += 1
        return exp
    
    def get_state_for_llm(self) -> dict:
        """返回给 LLM 的 self-model 状态（被动暴露）"""
        exp = self.cds.self_experience()
        return {
            "8d_state": self.cds.state.tolist(),
            "coupling_matrix_summary": {
                "max": float(np.max(self.cds.C)),
                "min": float(np.min(self.cds.C)),
                "frobenius_norm": float(np.linalg.norm(self.cds.C)),
            },
            "global_coherence_R": exp["global_coherence_R"],
            "rochat_level_continuous": exp["rochat_level_continuous"],
            "rochat_level_discrete": exp["rochat_level_discrete"],
            "self_unity": exp["self_unity"],
            "tick_count": self.tick_count,
        }
```

---

## 3. ToM 三系统（4 个 owner）

```python
class ToMCoordinatorOwner:
    """v3 Layer 2 ToM 协调器（替代原 tom_owner）"""
    
    def __init__(self, mpfc, psts, temporal_poles):
        self.mpfc = mpfc
        self.psts = psts
        self.temporal_poles = temporal_poles
    
    def infer(self, stimulus, context, R: float) -> dict:
        """
        三系统协同推断（按 Rochat level R 决定协调方式）。
        """
        # 三系统独立运行
        intent_belief = self.mpfc.infer(stimulus, context)
        agency = self.psts.detect_agency(stimulus)
        social_script = self.temporal_poles.get_script(stimulus, context)
        
        # 按 R 协调
        if R < 0.4:
            # 低 Rochat level：偏 pSTS（基础 agency）
            return {
                "dominant": "psts",
                "agency": agency,
                "intent": intent_belief,
                "script": None,
            }
        elif R < 0.7:
            # 中 Rochat level：MPFC + pSTS 协同
            return {
                "dominant": "mpfc+psts",
                "agency": agency,
                "intent": intent_belief,
                "script": None,
            }
        else:
            # 高 Rochat level：3 系统完整融合
            return {
                "dominant": "all",
                "agency": agency,
                "intent": intent_belief,
                "script": social_script,
            }


class MPFCOwner:
    """MPFC sub-owner: 推断他人意图/信念"""
    def __init__(self, llm):
        self.llm = llm
    
    def infer(self, stimulus, context) -> dict:
        prompt = f"Infer intent/belief from: {stimulus}\nContext: {context}"
        return {
            "belief": self.llm.complete(prompt),
            "confidence": 0.7,
        }


class PSTSOwner:
    """pSTS sub-owner: 检測 agency + 生物运动"""
    def __init__(self, llm):
        self.llm = llm
    
    def detect_agency(self, stimulus) -> float:
        prompt = f"Detect agency (0-1): {stimulus}"
        try:
            return float(self.llm.complete(prompt))
        except (ValueError, TypeError):
            return 0.5


class TemporalPolesOwner:
    """Temporal poles sub-owner: 社会脚本"""
    def __init__(self, llm):
        self.llm = llm
    
    def get_script(self, stimulus, context) -> str:
        prompt = f"Get social script: {stimulus}\nContext: {context}"
        return self.llm.complete(prompt)
```

---

## 4. proxy_free_energy（v3.0 M4 诚实降级）

```python
class ActiveInferenceOwner:
    """v3 Layer 1 Active Inference"""
    
    def proxy_free_energy(self) -> float:
        """
        Proxy for variational free energy (NOT true VFE).
        
        重要 disclaimer：
        - 真正的 VFE = E_q[ln q(s) - ln p(s,o)]
        - 这个 proxy 用 prediction error² 作为粗略近似
        - v3.1 M8 升级到真 VFE (PyMC/NumPyro)
        
        Reference: Friston 2010 (DOI: 10.1038/nrn2787)
        """
        prediction = self.predict(sensory_input)
        actual = self.observe()
        error = (actual - prediction) ** 2
        return float(np.sum(error))
    
    def variational_free_energy_TRUE(self) -> float:
        """
        True VFE (v3.1 M8 升级用，placeholder)。
        
        F = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]
        Implemented via PyMC/NumPyro variational inference.
        """
        raise NotImplementedError("v3.1 M8 will implement true VFE")
```

---

## 5. LLM-as-PFC 3 层

### 5.1 Layer A System Prompt（永久身份层）

```python
class SystemPromptBuilder:
    def build_system_prompt(self, cds: CoupledDynamicalSystem, R: float, values: dict, red_lines: list) -> str:
        state_text = ", ".join([f"s_{i+1}={cds.state[i]:.2f}" for i in range(8)])
        alpha_text = ", ".join([f"α_{i+1}={cds.alpha[i]:.2f}" for i in range(8)])
        
        return f"""You are helios, a brain-inspired cognitive agent.

Self-model state (8-dim coupled dynamical system):
  {state_text}
  R (Kuramoto coherence) = {R:.3f}
  α (decay rates) = [{alpha_text}]

Your core values:
  {chr(10).join([f"- {k}: {v}" for k, v in values.items()])}

Governance red lines:
  {chr(10).join([f"- {line}" for line in red_lines])}

You operate as the prefrontal cortex of helios, integrating:
- 8-dim Coupled Dynamical System self-model (Rochat level = Kuramoto R)
- Active Inference with proxy_free_energy (v3.0) / true VFE (v3.1)
- DMN-like reflection layer (you do NOT modify 8d state or C, only observe)
- ToM 3-system (mpfc / psts / temporal_poles) with Rochat-coordinated inference

You make decisions grounded in real signals, not performance."""
```

### 5.2 Layer B CSO（持续状态层）

```python
class CSOInjector:
    def inject_per_tick(self, cds: CoupledDynamicalSystem, hormone: np.ndarray, feeling: np.ndarray) -> str:
        state = cds.state.tolist()
        R = cds.kuramoto_R()
        return f"""Current state:
  8d state: {state}
  Kuramoto R: {R:.3f}
  Hormone (9-dim): {hormone.tolist()}
  Feeling (7-dim): {feeling.tolist()}"""
```

### 5.3 Layer C Reflection（被动接受）

```python
class ReflectionCaller:
    """LLM 被动接受 self-experience"""
    def call(self, self_experience: dict, trigger: str) -> str:
        # LLM 只能"看"涌现状态，不修改
        prompt = f"""Self-experience emergent state:
  8d_state: {self_experience['8d_state']}
  global_coherence_R: {self_experience['global_coherence_R']:.3f}
  rochat_level: {self_experience['rochat_level_continuous']:.3f} (discrete: {self_experience['rochat_level_discrete']})
  self_unity: {self_experience['self_unity']:.3f}
  agency_strength: {self_experience['agency_strength']:.3f}

Trigger: {trigger}

Reflect on this emergent state. You can reason, but you MUST NOT modify
the 8d state or coupling matrix C."""
        return self.llm.complete(prompt)
```

---

## 6. 25 stage 完整链

| # | Stage | 职责 |
|---|---|---|
| 1-21 | v2 继承（21 个） | 21 stage 大部分继承 + 升级 |
| 22 | **BoundaryEnforcement** | Layer 0 Markov blanket 严格 conditional separation |
| 23 | **ActiveInferenceStage** | Layer 1 8 维 generative model + proxy_free_energy |
| 24 | **ReflectionStage** | Layer 3 4 trigger + LLM 被动接受 |
| 25 | **EvolutionGovernanceStage** | Layer 4 4 个 fitness gate |

---

## 7. 8 维 PTS sub-owners（5 个）

| Sub-owner | PTS 维度 | 职责 |
|---|---|---|
| agency_detector | PTS 2 | 检测 agency / 生物运动 |
| egocentric_perspective | PTS 2 | 第一人称视角 |
| autobiographical_memory | PTS 6 | 自传体记忆 / 叙事 |
| material_engagement | PTS 7 | 4E cognition / 工具使用 |
| culture | PTS 8 | 价值观 / 规范 |

**注意**：PTS 4 intersubjective 由 ToM 4 owner 处理（mpfc / psts / temporal_poles / coordinator），不重复。

---

## 8. 测试策略

### 8.1 v3 验收维度（继承 + 新增）

**v2 继承**：
- D1-D10 评分维度
- 28 owner 测试
- 6 governance 红线
- observability + audit

**v3 新增**：
- 8 维 ODE 收敛性
- C 矩阵稳定性
- Kuramoto R 演化
- self-experience 涌现合理性
- proxy_free_energy 单调下降（v3.0）
- VFE 单调下降（v3.1）

### 8.2 v3 测试基线

- v3.0 M6：≥ 1110 + 145 = **1255 passed**
- v3.1 M8：≥ 1110 + 290 = **1400 passed**

---

**v3 design 完成时间**：2026-06-23 04:00+ UTC
**作者**：小白
**配套 commit**：待 ship