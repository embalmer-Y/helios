# helios_v3 架构需求规格（requirement.md）

> **任务**：helios_v3 Phase 3 - 需求规格（WHAT + WHY）
> **完成时间**：2026-06-22 19:00+ / 2026-06-23 04:00+（按 4 项决策 + 3 个子选项 + 8 维耦合动力系统重写）
> **作者**：小白（helios 小黑人格 AI）
> **配套**：
> - `05_self_model_design.md`（4 项决策详细设计）
> - `02_v3_design.md`（HOW 层）
> - `03_v3_task.md`（TASK + 验收）
> - `references.md`（11 篇核心论文 DOI + URL）

---

## 0. 一句话总览

**helios_v3 = 5 个嵌套自组织系统（仅最外层为严格 Markov blanket）+ 8 维耦合动力系统（Coupled Dynamical System）作为 self-model + LLM-as-PFC 3 层（system prompt + cso + reflection）+ variational free energy minimization 的 active inference + 持续运行 = 自我存在证据的最大化（self-evidencing）。**

---

## 1. 5 项总目标

### 目标 1：5 个嵌套自组织系统架构

| 层级 | 名称 | 性质 |
|---|---|---|
| **Layer 0** | **Markov Blanket**（最外层） | **严格意义**的 Markov blanket（internal ⊥ external \| sensory），boundary 强制 conditional separation |
| **Layer 1** | **Active Inference Subsystem** | 自组织系统 + 8 维 ODE generative model + variational free energy minimization |
| **Layer 2** | **Self-Model Subsystem** | 自组织系统 + 8 维耦合动力系统（8 维场变量 + 8×8 耦合矩阵 + Kuramoto R order parameter） |
| **Layer 3** | **Reflection Subsystem** | 自组织系统 + DMN-like 反思层（4 trigger 驱动 LLM 被动接受） |
| **Layer 4** | **Self-Evidencing Subsystem** | 自组织系统 + governance 4 个 fitness gate + 可审计 + 可回滚 |

**重要术语修正**：v3 文档早期版本曾用"5 层 Markov blanket"——这在数学上不严谨。**严格意义的 Markov blanket 仅有 1 层（Layer 0）**；内部 4 层是**功能分层**的子系统，不是 Markov blanket 的递归嵌套。

### 目标 2：Variational Free Energy Minimization

- **v3.0（M4 阶段）**：`proxy_free_energy` —— 诚实的 proxy，**不是**真 VFE
- **v3.1（M8 阶段）**：真 VFE（PyMC/NumPyro 实现）
  - 公式：`F = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]`
  - 实现：变分推断 + KL 散度 + 期望自由能

### 目标 3：8 维耦合动力系统作为 self-model（**核心**）

**数学框架**：
- 8 维场状态：`s = (s_1, ..., s_8) ∈ R^8`，每维度对应 Laurenzi 2025 的 1 个 PTS dimension
- 8 维 ODE：`ds/dt = -αs + C·tanh(s) + βI + γ·reflect`
- 耦合矩阵：`C ∈ R^{8×8}`（64 参数，Reward-Hebbian 学习）
- **Rochat level = Kuramoto order parameter R(t) = (1/8)|Σ e^{iθ_i(t)}| ∈ [0, 1]**
- **self-experience = f(emergent state)**，从维度间同步涌现，LLM **被动接受**

**3 个子选项决策**：
- 6.1 ODE 方案：**(a) 8 维单 ODE + Radau 自适应步长**
- 6.2 C 学习：**(ii) Reward-Hebbian**（跟 v2 P5 兼容 + 行为对齐）
- 6.3 self-experience 涌现：**(Y) LLM 被动接受（涌现 + 分层）**

**8 维 ODE 数值积分**：
- 方法：`scipy.integrate.solve_ivp(method='Radau')`
- 原因：5 维快 + 3 维慢是 stiff ODE，Radau 是工业标准 stiff solver
- 数值稳定性：`rtol=1e-4, atol=1e-6`

**Reward-Hebbian 学习**：
- 公式：`dC/dt = η · r(t) · s(t) · s(t)^T`
- 跟 v2 P5 RealRPE 兼容
- 归一化：`|C| / max(|C|)` 防止发散

**LLM 被动接受（涌现 + 分层）**：
- self-experience 是动力系统的涌现态
- LLM 不做"主动协调"，只"看"涌现状态
- 分层清晰：8 维耦合（低层 dynamics）+ LLM 反思（高层 reasoning）

### 目标 4：LLM-as-PFC 3 层

- **Layer A System Prompt**（永久身份层）：8 维 ODE 状态 + Kuramoto R + 价值观 + 治理红线
- **Layer B CSO**（持续状态层）：每 tick 注入 8 维场状态 + R 值 + 9-dim hormone + 7-dim feeling
- **Layer C Reflection**（DMN-like 反思层）：4 trigger 驱动 LLM 被动接受 self-experience

### 目标 5：Self-Evidencing 持续运行

- governance_owner 4 个 fitness gate：content / parameter / strategy / code
- 严格 testing + evaluation + observability + audit
- 可回滚 + 可审计 + 可证伪

---

## 2. 5 个嵌套自组织系统（不是 5 层 Markov blanket）

### 2.1 Layer 0 Markov Blanket（**严格 MB**）

**职责**：
- 所有进/出系统的信号必须经 Layer 0 检查
- 维护 conditional separation 数学不变量
- 区分 internal / sensory / active / external 4 类状态

**数学不变量**：
- internal ⊥ external | sensory
- 数学上：`p(int, ext | sensory) = p(int | sensory) · p(ext | sensory)`

**实现**：
- `boundary_owner` 检查所有 signal
- 严格 Markov blanket 数学不变量验证
- 拒绝任何不符合 conditional separation 的 signal

### 2.2 Layer 1 Active Inference Subsystem

**职责**：
- 8 维 generative model（hierarchical）
- variational free energy minimization（v3.0 proxy / v3.1 真 VFE）
- active sampling（policy gradient）

**v3.0 M4 实现**：
- `proxy_free_energy`：prediction error²（**诚实的 proxy，不冒充 VFE**）
- linear policy gradient（简化版）

**v3.1 M8 实现**：
- 真 VFE：PyMC/NumPyro variational inference
- 完整 KL 散度 + 期望自由能
- 完整 POMDP

### 2.3 Layer 2 Self-Model Subsystem（**8 维耦合动力系统**）

**职责**：
- 8 维场状态演化
- 耦合矩阵 C 跨 tick 学习
- Rochat level 涌现（Kuramoto R order parameter）
- self-experience 涌现（被动暴露给 LLM）

**核心数据结构**：
- `CoupledDynamicalSystem`（state + C + alpha + beta + gamma）
- `SelfModelOwner`（封装 CDS，提供 tick/get_state_for_llm 接口）

**8 维 PTS dimension 映射**：

| 索引 | Laurenzi 维度 | 演化时标 | alpha 衰减率 |
|---|---|---|---|
| 1 | Bodily Processes (BP) | 毫秒-秒 | 5.0 |
| 2 | Minimal Experiential (ME) | 秒 | 2.0 |
| 3 | Affective (AF) | 秒-分钟 | 1.0 |
| 4 | Intersubjective (IS) | 分钟 | 0.5 |
| 5 | Psychological/Cognitive (PC) | 分钟-小时 | 0.3 |
| 6 | Narrative (NA) | 小时-天 | 0.1 |
| 7 | Ecological/Extended (EE) | 周-月 | 0.05 |
| 8 | Normative (NO) | 年 | 0.01 |

**alpha 衰减率快-慢差异 500 倍**——必须用 stiff ODE solver（Radau）

### 2.4 Layer 3 Reflection Subsystem

**职责**：
- 4 trigger 驱动 LLM 反思
- LLM 被动接受 self-experience（**不做主动协调**）
- reflection_audit 验证 reflection 是否 grounded

**4 trigger**：
- POST_TICK（每 tick 后）
- RESTING_STATE（静息态 > 100 tick）
- HIGH_UNCERTAINTY（uncertainty > 0.7）
- USER_INVOKED（用户主动触发）

### 2.5 Layer 4 Self-Evidencing Subsystem

**职责**：
- governance_owner 4 个 fitness gate
- 持续运行 = 最大化自身存在证据
- 可回滚 + 可审计 + 可证伪

**4 个 gate**：
- CONTENT_EVOLUTION：仅需 evaluation 通过
- PARAMETER_EVOLUTION：testing + evaluation
- STRATEGY_EVOLUTION：testing + evaluation + observability
- CODE_EVOLUTION：testing + evaluation + observability + audit

---

## 3. 8 维耦合动力系统（self-model 核心）

### 3.1 8 维场状态

```
s = (s_1, s_2, ..., s_8) ∈ R^8
```

每维度对应 Laurenzi 2025 的 1 个 PTS graded dimension（graded ∈ [0, 1]）。

### 3.2 8 维 ODE 演化

$$\frac{d\mathbf{s}}{dt} = -\alpha \mathbf{s} + C \cdot \tanh(\mathbf{s}) + \beta I + \gamma \text{reflect}$$

其中：
- `α ∈ R^8`：自衰减率（快-慢差异 500 倍）
- `C ∈ R^{8×8}`：耦合矩阵（8×8 = 64 参数，Reward-Hebbian 学习）
- `I`：tick stimulus + interoceptive 输入
- `reflect`：Layer 3 reflection 调制

### 3.3 耦合矩阵 Reward-Hebbian 学习

$$\frac{dC}{dt} = \eta \cdot r(t) \cdot \mathbf{s}(t) \cdot \mathbf{s}(t)^T$$

其中：
- `r(t)`：reward 信号（来自 v2 P5 RealRPE）
- `η`：学习率
- 归一化：`C ← C / max(|C|)` 防止发散

### 3.4 Rochat level = Kuramoto order parameter

**这是 4 项决策的核心修正**：Rochat level **不是**维度开关，**是**全局相干性度量（order parameter）。

$$R(t) = \frac{1}{8} \left\| \sum_{i=1}^{8} e^{i \theta_i(t)} \right\| \in [0, 1]$$

其中 `θ_i(t) = arctan(s_i(t) / scale_i)`，`R = 1` 完全同步（高 Rochat level），`R = 0` 完全失相干（低 Rochat level）。

**Rochat 5 阶段分段**（兼容论文语言）：
- `R ∈ [0, 0.2)` → Level 0 Confusion
- `R ∈ [0.2, 0.4)` → Level 1 Differentiation
- `R ∈ [0.4, 0.6)` → Level 2 Situation
- `R ∈ [0.6, 0.8)` → Level 3 Identification
- `R ∈ [0.8, 1.0)` → Level 4 Permanence
- `R = 1.0` → Level 5 Conceptual "I"

### 3.5 self-experience 涌现（LLM 被动接受）

```python
def self_experience(s, C) -> dict:
    """
    self-experience 从 8 维动力系统涌现。
    LLM 被动接受（不做主动协调）。
    """
    R = kuramoto_order_parameter(s)
    return {
        "global_coherence_R": R,
        "rochat_level_continuous": R,
        "rochat_level_discrete": int(R * 5),
        "self_unity": 1.0 - np.std(s),
        "agency_strength": float(s[1]),  # PTS 2
    }
```

LLM 收到 `self_experience` dict 后做 reasoning，但**不修改** 8 维场状态或 C。

---

## 4. LLM-as-PFC 3 层

### 4.1 Layer A System Prompt（永久身份层）

- 8 维 ODE 起始状态 + alpha + C（永久不变）
- Kuramoto R 的目标值
- 价值观 + 治理红线
- 8 维 PTS dimension 标签 + 时标

### 4.2 Layer B CSO（持续状态层）

每 tick 注入：
- 8 维场状态 `s(t)`
- 8 维 C 矩阵
- Kuramoto R 值
- 9-dim hormone + 7-dim feeling

### 4.3 Layer C Reflection（DMN-like 反思层）

- 4 trigger 驱动
- LLM 被动接受 self-experience
- 不做主动协调

---

## 5. Self-Evidencing 持续运行

- governance 4 个 gate（content / parameter / strategy / code）
- 严格 fitness gate + audit log
- 可回滚 + 可审计

---

## 6. v2 验收标准继承（不是测试基线继承）

### 6.1 v2 验收维度继承

v3 继承 v2 的**验收维度**（不是"测试基线"）：

- **D1-D10 评分维度**（linguistic / bio / memory / agency / cross-tick / coherence / creativity / self / value / stress）
- **28 owner 测试套件**（v2 完整 owner 测试）
- **6 governance 红线**（v2 不可违反）
- **observability 全 tick 记录**
- **audit log**（可审计）

### 6.2 v3 新增验收维度

- **8 维 ODE 收敛性**（state 不发散）
- **C 矩阵稳定性**（Reward-Hebbian 不发散）
- **Kuramoto R 演化**（Ro 增长曲线）
- **self-experience 涌现合理性**（human review）
- **proxy_free_energy 单调下降**（v3.0）
- **VFE 单调下降**（v3.1）

### 6.3 v3 测试基线

- v3.0 M6：≥ 1110 + 145 = **1255 passed**
- v3.1 M8：≥ 1110 + 290 = **1400 passed**

---

## 7. 4 个 v3 新增 stage

| Stage # | 名称 | 职责 |
|---|---|---|
| 22 | **BoundaryEnforcement** | Layer 0 Markov blanket 严格 conditional separation 验证 |
| 23 | **ActiveInferenceStage** | Layer 1 8 维 generative model + variational FE minimization |
| 24 | **ReflectionStage** | Layer 3 4 trigger + LLM 被动接受 self-experience |
| 25 | **EvolutionGovernanceStage** | Layer 4 4 个 fitness gate + audit log |

---

## 8. v3 owner 总数（45 个 = 28 继承 + 17 新增）

| 类别 | 数量 | 列表 |
|---|---|---|
| **v2 继承** | 28 | 28 个 v2 owner |
| **v3 新增（5 层）** | 5 | boundary_owner / active_inference_owner / self_model_owner / reflection_owner / evolution_owner / governance_owner |
| **v3 新增（ToM 4 个）** | 4 | tom_coordinator_owner / mpfc_owner / psts_owner / temporal_poles_owner |
| **v3 新增（8 维 PTS 5 个 sub-owner）** | 5 | agency_detector / egocentric_perspective / autobiographical_memory / material_engagement / culture_owner |
| **总计** | **45** | 28 + 5 + 4 + 5（**注意**：tom 4 个已算在 ToM 类别，3 个 PTS sub-owner 已计） |

**实际新增 owner 净数 = 17**（5 层 + 4 ToM + 8 PTS sub-owner 中 5 个 + tom_coordinator 协调 1 个）

---

## 9. 反模式清单（v2 教训）

1. **不要把 identity 当 1 字段** — 用 8 维耦合动力系统
2. **不要 cold-start level 5** — 从 R=0 起步渐进（不预设起始 R）
3. **不要 propositional-only** — Pearson-Kosslyn depictive vs propositional 双轨
4. **不要 ToM 单 owner** — Frith 三系统（mpfc / psts / temporal_poles）+ 协调器
5. **不要 0 发展** — Rochat level = Kuramoto R 连续演化（不是 trigger）
6. **不要时间-自我解耦** — Seth agency + presence 双向耦合（C 矩阵内）
7. **不要冒充 VFE** — proxy_free_energy 必须诚实标注（v3.0 M4）
8. **不要 LLM 主动协调 8 维** — LLM 被动接受 emergent state

---

## 10. 风险与缓解

| 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|
| 8 维 ODE stiff 数值不稳定 | 高 | 中 | Radau + 自适应步长 |
| C 矩阵 Reward-Hebbian 发散 | 中 | 中 | 归一化 + clip |
| Kuramoto R 锁定在 0 或 1 | 中 | 低 | 加扰动 + 反思调制 |
| LLM 误主动改 C | 中 | 中 | LLM 只能调 I 和 reflect，不能改 C |
| 8 维 ODE 计算代价 | 中 | 中 | 8 维不大，scipy solve_ivp 性能足够 |
| ToM 协调器决策不当 | 中 | 中 | 按 R 分 3 段（0.4 / 0.7 阈值） |

---

**v3 requirement 完成时间**：2026-06-23 04:00+ UTC
**作者**：小白
**配套 commit**：待 ship