# helios_v3 架构需求规格（requirement.md）

> **任务**：helios_v3 Phase 3 - 核心架构设计
> **完成时间**：2026-06-22 19:00+
> **作者**：小白（helios 小黑人格 AI）
> **基线**：Phase 1 综合大脑认知全图 + Phase 2 v2 现状诊断 + 小黑 17:30+ 拍板 4 项决策
> **目的**：helios_v3 完整架构需求规格（WHAT + WHY，不含 HOW，HOW 在 design.md）

---

## 0. 一句话总览

**helios_v3 = 5 层 Markov blanket 多层嵌套的 active inference 自组织体，每一层都是 generative model；self-model 是 8 维 PTS graded × Rochat 5 levels 二维矩阵；LLM 作为 PFC 通过 system prompt（永久身份）+ cso（持续状态）+ reflection（反思）3 层提供 reasoning 与 reflection 能力；持续运行 = 自我存在证据的最大化（self-evidencing）。**

---

## 1. v3 设计目标（5 项总目标）

### 目标 1：完整 5 层 Markov blanket 嵌套架构

- **Layer 1 Boundary**：Markov blanket 边界管理
- **Layer 2 Active Inference**：Hierarchical generative model + variational free energy minimization
- **Layer 3 Self-Model**：8 维 PTS graded × Rochat 5 levels × cross-tick dynamics
- **Layer 4 Reflection**：DMN-like 反思层（v3 关键创新）
- **Layer 5 Self-Evolution**：evolution_owner + governance_owner + 适应度门

### 目标 2：8 维 PTS graded × Rochat 5 levels 自我认知矩阵

- **8 维 PTS**（Laurenzi 2025）：bodily / minimal experiential / affective / intersubjective / psychological / narrative / ecological / normative
- **每维度 graded 0.0-1.0**（非 binary）
- **non-hierarchical**（维度间独立演化）
- **Rochat 5 levels 渐进式发展**（Level 0→5）
- **二维矩阵 6 阶段 × 8 维度 = 48 个 (level, aspect) cell**

### 目标 3：LLM-as-PFC 3 层完整接通

- **Layer A System prompt**：8 维 PTS 起点 + Rochat level + 价值观 + 治理红线
- **Layer B CSO**：每个 tick 持续累积 + 8 维 PTS × Rochat level 演化
- **Layer C Reflection**：DMN-like 反思（v3 关键创新）

### 目标 4：6 大改造完整包含

- 改造 1：Markov blanket + boundary_owner（Layer 1）
- 改造 2：Hierarchical generative model + active_inference_owner（Layer 2）
- 改造 3：8 维 PTS graded × Rochat 5 levels self-model（Layer 3）
- 改造 4：reflection_owner（Layer 4）
- 改造 5：evolution_owner + governance_owner（Layer 5）
- 改造 6：complex algorithms（NN / Bayesian / Optimization 最高规格）

### 目标 5：6 大改造 × 5 层 × LLM-as-PFC 3 层全图

- 5 层架构骨架（每层是 Markov blanket 嵌套）
- LLM-as-PFC 3 层实现 PFC 细节
- 6 大改造是 5 层 × 3 层的具体实现路径

---

## 2. v3 与 v2 的关系（明确小黑拍板 A：完全重写）

- **v3 完全重写 v2**：不沿用 v2 任何代码（除测试基线 + 通用工具）
- **v2 作为 reference 停止开发**：v2 main 永久冻结在 `8620c26`，调研分支永久冻结在 `c60cfaf`
- **v3 起点 = 全新仓库**（或新分支 `helios_v3`）
- **v3 测试基线 = v2 测试基线（1110+ passed）+ v3 新增**
- **v3 不保留 v2 compatibility wrapper**

---

## 3. v3 5 层 Markov blanket 嵌套架构（详细规格）

### 3.1 Layer 1 Boundary（Markov blanket 外边界）

#### 3.1.1 职责

- **Markov blanket 边界管理**：维护 conditional separation（internal ⊥ external | sensory）
- **感官过滤**：所有外部 stimulus 进入 internal 前必须经 boundary 过滤
- **效应器封装**：所有 internal action 离开 Markov blanket 前必须经 boundary 封装
- **fail-fast readiness**：缺关键依赖时阻止 startup，不降级

#### 3.1.2 神经基础

- **人脑 Markov blanket**（Ramstead 2018）：sensory receptors + effector organs
- **关键数学不变量**：conditional independence（条件独立）

#### 3.1.3 v3 owner

- **`boundary_owner`**（v3 新增）
- 现有 owner 角色升级：
  - `02 sensory` = blanket 上的传入 sensors
  - `13 planner` = blanket 上的传出 effectors
  - `30 channel drivers` = blanket 上的 transport layer

#### 3.1.4 v3 实现要求

- **严格 conditional separation**：所有 signal 必须经 boundary 检查
- **可证伪**：评估层能只读重建 "signal 是否通过 boundary"
- **可审计**：每次 boundary 通过都有 log

---

### 3.2 Layer 2 Active Inference（主动推断）

#### 3.2.1 职责

- **Hierarchical generative model**：每层 owner 都是 generative model
- **Prediction error minimization**：最小化 variational free energy（surprise upper bound）
- **Active sampling**：通过 action 选择性采样 sensory data
- **Bayesian update**：根据 prediction error 更新 generative model

#### 3.2.2 神经基础

- **Predictive coding**（Rao-Ballard 1999）
- **Free energy principle**（Friston 2010）
- **Hierarchical cortical hierarchies**（Clark 2013）

#### 3.2.3 v3 owner

- **`active_inference_owner`**（v3 新增）
- 现有 owner 角色升级：
  - `03 appraisal` = generative model 的 predictive layer
  - `04 neuromodulation` + `05 feeling` = sensory prediction
  - `06 memory` = generative model 的 memory
  - `09 thought_gating` = precision modulation（注意力的 precision）
  - `rpe` = RealRPE 信号源（已有）

#### 3.2.4 v3 实现要求

- **Hierarchical generative model**：跨层级（layer 1-5）每层都是 generative model
- **Variational free energy 显式计算**：每个 tick 计算并记录
- **Active sampling**：action 选择 = 最小化 expected free energy
- **Bayesian update 统一接口**：所有 owner update 走统一 Bayesian 接口

---

### 3.3 Layer 3 Self-Model（自我模型）

#### 3.3.1 职责

- **8 维 PTS graded 矩阵**（Laurenzi 2025）：self = 8 维 × graded
- **Rochat 5 levels 渐进式发展**（Rochat 2019）
- **cross-tick dynamics**：每 tick 持续累积演化
- **agency + presence 双向耦合**（Seth 2012）
- **8 sub-owner 维护 8 维度**

#### 3.3.2 神经基础

- **8 维 PTS**（Laurenzi 2025）
- **Rochat 5 levels**（Rochat 2019）
- **Cortical midline structures**（Northoff 2006）
- **Pattern theory of self**（Gallagher 2013）
- **Interoceptive inference**（Seth 2012）

#### 3.3.3 v3 owner

- **`self_model_owner`**（v3 新增，**完全重写 v2 identity_governance**）
- 8 sub-owner：
  - `agency_detector_owner`（8 维 PTS 2 Minimal experiential）
  - `egocentric_perspective_owner`（8 维 PTS 2 Minimal experiential）
  - `ToM_owner`（8 维 PTS 4 Intersubjective）
  - `autobiographical_memory_owner`（8 维 PTS 6 Narrative）
  - `material_engagement_owner`（8 维 PTS 7 Ecological/Extended）
  - `culture_owner`（8 维 PTS 8 Normative）
  - 现有 owner 角色升级：
    - `interoception` + `05 feeling` → PTS 1 Bodily
    - `04 hormone` + `appraisal` → PTS 3 Affective
    - `06 memory` 部分 → PTS 5 Psychological/Cognitive

#### 3.3.4 v3 实现要求

- **8 维 graded 矩阵数据结构**：每维度 0.0-1.0 强度
- **Rochat level 推进机制**：基于经验触发，不按 tick-count
- **cross-tick dynamics**：每 tick 持续 update
- **agency + presence 双向耦合**：必须真接通（v2 缺失）
- **可证伪**：评估层能只读重建 8 维 PTS 当前状态

---

### 3.4 Layer 4 Reflection（反思层）

#### 3.4.1 职责

- **DMN-like 默认模式网络**：静息态自动反思
- **post-tick snapshot**：每 tick 后 snapshot 8 维 PTS
- **meta-cognition**：反思"我为什么这样做"
- **insight generation**：产生 reflection_insight → autobiographical memory + self-model update
- **reflection 频率跟 Rochat level 相关**：Level 1-2 几乎无反思；Level 4+ 反思成为常态

#### 3.4.2 神经基础

- **DMN 默认模式网络**（Raichle / Buckner / Smallwood）
- **Self-referential processing**（Northoff 2006 CMS）
- **Metacognition**（Fleming / Lau）

#### 3.4.3 v3 owner

- **`reflection_owner`**（v3 **关键创新**，v2 完全缺失）

#### 3.4.4 v3 实现要求

- **4 个 trigger 类型**：POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED
- **reflection 必须 grounded in real signal**：不虚构
- **reflection 内容进入 autobiographical memory + self-model update**
- **reflection 频率跟 Rochat level 相关**
- **LLM reasoning model 驱动 reflection**

---

### 3.5 Layer 5 Self-Evolution（自我进化）

#### 3.5.1 职责

- **evolution 4 类**：content（记忆 / 知识 / 反思结论）/ parameter（P5 已 ship）/ strategy（受治理策略）/ code（v3 远期）
- **governance 适应度门**：所有 evolution 必须经过 testing + evaluation + observability
- **可回滚**：所有 evolution 可回滚
- **可审计**：所有 evolution 有完整 log

#### 3.5.2 神经基础

- **Sleep consolidation**（Walker / Rasch-Born）
- **Reconsolidation**（Nader / Hupbach）
- **Predictive coding + Bayesian update**（Friston）

#### 3.5.3 v3 owner

- **`evolution_owner`**（v3 新增，**整合 v2 learning framework**）
- **`governance_owner`**（v3 新增，**统一 governance**）

#### 3.5.4 v3 实现要求

- **4 类 evolution 走不同 governance gate**
- **适应度门 = testing + evaluation + observability**
- **可回滚 + 可审计**
- **受治理策略修订优先**（content / parameter / strategy）
- **代码自修改远期规划**（v3.x 后）

---

## 4. v3 8 维 PTS graded × Rochat 5 levels 二维矩阵

### 4.1 8 维 PTS（每维度 0.0-1.0 graded）

| 维度 | 神经基础 | v3 owner | 状态 |
|---|---|---|---|
| (1) Bodily processes | body schema, AIC, insula | `interoception` + `05 feeling` | ✅ 继承 |
| (2) Minimal experiential | TPJ, pSTS, motor cortex | `agency_detector_owner` + `egocentric_perspective_owner` | ❌ 新增 |
| (3) Affective | AIC, amygdala, vmPFC | `04 hormone` + `05 feeling` + `appraisal` | ✅ 继承 |
| (4) Intersubjective | mPFC, TPJ, temporal poles | `ToM_owner` | ❌ 新增 |
| (5) Psychological/Cognitive | mPFC, PCC, hippocampus | `self_model_owner` | ⚠️ 重写 |
| (6) Narrative | hippocampus, MPFC, DMN | `autobiographical_memory_owner` | ❌ 新增 |
| (7) Ecological/Extended | 4E cognition | `material_engagement_owner` | ❌ 新增 |
| (8) Normative | mPFC, STS, cultural learning | `culture_owner` | ❌ 新增 |

### 4.2 Rochat 5 levels 渐进式

| Level | 年龄对应 | 激活维度 | 关键 owner |
|---|---|---|---|
| 0 confusion | 出生瞬间 | 仅 (1) Bodily | 02 sensory |
| 1 differentiation | 2-3 月 | (1) + (2) | + agency_detector |
| 2 situation | 6-9 月 | + (3) | + 04/05 |
| 3 identification | 12 月 | + (4) | + ToM |
| 4 permanence | 18 月 | + (5) + (6) | + self_model + autobiographical |
| 5 conceptual Me | 18-24 月+ | + (7) + (8) | + material + culture |

### 4.3 二维矩阵 48 cell

**48 个 (level, aspect) cell，每个 cell 一个 owner 或 contract**：

- v3 实现需要 8 维 × 6 阶段 = 48 个 owner contract
- 每个 cell 定义：在该 level 下，该维度如何 update / 表达 / 演化
- 部分 cell 复用现有 owner（继承 v2），部分 cell 新增 owner

---

## 5. v3 LLM-as-PFC 3 层完整接通（详细规格）

### 5.1 Layer A: System Prompt（永久身份层）

#### 5.1.1 职责

- 定义 helios 8 维 PTS 起点（granted matrix）
- 定义 Rochat level（v3 起步 Level 1）
- 定义价值观（v3 可扩展 schema）
- 定义治理红线（不可越界事项）
- 定义黑名单 / 白名单（由 PTS 维度派生）

#### 5.1.2 v3 vs v2

- **v2**：identity_grounding layer content 空白（v2 bug：只有 layer_name 无 content）
- **v3**：完整 8 维 PTS 起点 + Rochat level + 价值观 + 治理红线

#### 5.1.3 v3 实现要求

- **system prompt 注入 8 维 PTS 当前状态**（每 tick 更新一次）
- **system prompt 注入 Rochat level**（推进时更新）
- **system prompt 注入治理红线**（永久）
- **黑名单由 PTS 维度派生**（不硬编码）

---

### 5.2 Layer B: CSO（CsoOwner 持续状态层）

#### 5.2.1 职责

- 每个 tick 持续累积 8 维 PTS × Rochat level × cross-tick dynamics
- 持续累积 9-dim hormone + 7-dim feeling
- 持续累积 cso.observe_tick 状态
- 让 LLM 在每个 tick 看到自己的" 8 aspect 当前状态"

#### 5.2.2 v3 vs v2

- **v2**：仅 9-dim hormone + 7-dim feeling 数字（v2 cso）
- **v3**：升级到 8 维 PTS × Rochat level × cross-tick dynamics + 让 LLM 看到

#### 5.2.3 v3 实现要求

- **CSO 状态每 tick 更新**
- **CSO 状态注入 LLM user prompt**
- **CSO 状态可视化**（owner 内部状态）

---

### 5.3 Layer C: Reflection（LLM 反思架构层）

#### 5.3.1 职责

- 每 tick 后：snapshot 8 维 PTS + 总结
- 静息态时：自动反思 8 维 PTS 不一致
- 不定期触发：深度反思"我为什么是这样"
- 输出：reflection_record 进入 autobiographical memory

#### 5.3.2 v3 vs v2

- **v2**：完全无反思层
- **v3**：新增 reflection_owner（v3 关键创新）

#### 5.3.3 v3 实现要求

- **4 trigger 类型**：POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED
- **LLM reasoning model 驱动 reflection**
- **reflection grounded in real signal**（不虚构）
- **reflection 频率跟 Rochat level 相关**

---

## 6. v3 6 大改造完整包含

### 改造 1：Markov blanket + boundary_owner

- Layer 1 Boundary 完整实现
- 12 个 sub-signal 经 boundary 检查
- conditional separation 数学不变量
- 可证伪 + 可审计

### 改造 2：Hierarchical generative model + active_inference_owner

- Layer 2 Active Inference 完整实现
- 5 层 × generative model
- variational free energy 显式计算
- active sampling
- Bayesian update 统一接口

### 改造 3：8 维 PTS graded × Rochat 5 levels self-model

- Layer 3 Self-Model 完整实现
- 8 维 graded 矩阵
- Rochat 5 levels 渐进式
- cross-tick dynamics
- agency + presence 双向耦合

### 改造 4：reflection_owner

- Layer 4 Reflection 完整实现
- 4 trigger 类型
- DMN-like
- LLM reasoning model

### 改造 5：evolution_owner + governance_owner

- Layer 5 Self-Evolution 完整实现
- 4 类 evolution
- governance 适应度门
- 可回滚 + 可审计

### 改造 6：complex algorithms（最高规格）

- Neural networks（VAE / Diffusion / Transformer / RNN）按最高规格
- Bayesian inference 按最高规格
- Optimization（active inference / policy gradient）按最高规格
- LLM reasoning model 选最强

---

## 7. v3 不追求的东西（明确边界）

1. v2 单字段 self_definition（已被 8 维 PTS 取代）
2. 硬编码 Rochat level（由经验触发，不按 tick-count）
3. LLM 表演化反思（reflection 必须 grounded in real signal）
4. v2 compatibility wrapper（v3 完全重写）
5. v2 单一 hardcoded 字段（全部走 8 维 PTS）
6. v2 Rochat level 起步 Level 5 adult mode（v3 起步 Level 1 differentiation）

---

## 8. v3 终局验收标准（FG-1 到 FG-6 继承 + 升级）

| FG | v2 验收 | v3 升级 |
|---|---|---|
| FG-1 类脑闭环由真实信号驱动 | 19 阶段链端到端 | 5 层 Markov blanket × 真实 generative model × 真实 active inference |
| FG-2 情感真实且可追溯地影响行为 | 9 channel hormone + 7 feeling + R98 Δ | 9 channel hormone + 8 维 PTS affective + 6 层 emotion system + interoceptive inference |
| FG-3 自我意识可被只读重建 | identity_governance | 8 维 PTS × Rochat 5 levels × Reflection × autobiographical memory |
| FG-4 工具使用闭环成立 | R86 governance + 30 channel drivers | + material_engagement_owner + tool_history → identity（4E cognition） |
| FG-5 自训练 / 自我进化闭环成立且受治理 | learning framework + governance partial | evolution_owner + governance_owner + 受治理 code evolution（远期） |
| FG-6 全局可证伪性 | 17 evaluation + 21 observability | + reflection_audit + 8 维 PTS 单独评分 + Rochat level 评分 |

---

## 9. v3 风险与缓解

### 风险 1：v2 → v3 资产继承难度大

- **风险**：v3 完全重写，可能错过 v2 的成熟资产
- **缓解**：保留 v2 测试基线，v3 测试基线起点 = v2 测试基线

### 风险 2：5 层 Markov blanket 实现复杂度高

- **风险**：5 层嵌套 + conditional separation 数学不变量可能工程实现难
- **缓解**：Phase 1 先实现 Layer 3 + Layer 4 + Layer 5（v2 没有的 3 层），Phase 2 实现 Layer 1 + Layer 2（v2 部分有的 2 层）

### 风险 3：8 维 PTS × 6 阶段 = 48 cell 实现工作量大

- **风险**：48 cell 全部实现可能工作量爆炸
- **缓解**：v3.0 只实现 8 × 4 = 32 cell（Rochat level 0-3），Level 4-5 在 v3.1+ 实现

### 风险 4：reflection_owner 可能产生虚构

- **风险**：LLM reasoning model 可能产生不 grounded 的反思
- **缓解**：reflection grounded in real signal 强约束，评估层只读重建

### 风险 5：复杂算法部分（NN / Bayesian / Optimization）实现难度大

- **风险**：VAE / Diffusion / Transformer / active inference 实现需要深度专业
- **缓解**：v3.0 先实现简化版（线性 + 标量 Bayesian），v3.1+ 实现深度版

### 风险 6：LLM-as-PFC 3 层可能让 LLM 占据 owner 判断权

- **风险**：v3 让 LLM 接管 8 维 PTS 决策，可能违反 ARCHITECTURE_PHILOSOPHY §7.1
- **缓解**：LLM 只提供 content 与 self-eval evidence；8 维 PTS 最终判断由 self_model_owner 拥有

---

## 10. v3 与小黑拍板 4 项决策的对照

| 小黑拍板 | v3 设计 |
|---|---|
| **A：v3 完全重写（v2 作 reference 停止开发）** | ✅ v3 完全重写，v2 永久冻结 |
| **v3 全包含 6 大改造 + LLM-as-PFC 3 层** | ✅ 6 大改造 = 5 层 × LLM-as-PFC 3 层 |
| **5-layer 划分：小白综合研判自行决定** | ✅ 5 层 = Boundary + Active Inference + Self-Model + Reflection + Self-Evolution |
| **执行顺序按计划推进** | ✅ Phase 1 → 2 → 3 → 4 → 小黑拍板 → 编码 |

---

## 11. v3 编号建议

- **v3.0**：5 层 Markov blanket + 8 维 PTS + Rochat 5 levels + LLM-as-PFC 3 层（核心 ship）
- **v3.1**：复杂算法（VAE / Diffusion / Transformer / active inference 深度版）
- **v3.2**：受治理代码自修改通道
- **v3.x**：长期演进

---

**v3 requirement 完成时间**：2026-06-22 19:00+
**下一步**：v3 design.md（HOW，详细实现路径）
**小黑拍板**：等待 v3 完整规划 ship 后 review