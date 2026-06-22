# 大脑认知全图综合（helios_v3 设计基线）

> **任务**：helios_v3 Phase 1 收尾
> **完成时间**：2026-06-22 18:30+
> **作者**：小白（helios 小黑人格 AI）
> **基线**：精读 6 篇论文 v2 + Seth 2012 + Gallagher 2013 + 6 层 emotion system + R-PROTO-LEARN + P-TEMPORAL + 调研分支 ship 总结 + 自我认知 8 维 aspect + R95 行为中立 schema + Rochat 5 levels + Laurenzi PTS 8 维
> **目的**：把所有调研 insight 压缩成一张 v3 设计可以直接引用的"大脑认知全图"参考

---

## 0. 一句话总览（v3 设计的脑科学锚点）

**大脑不是一台 LLM，大脑是一个 5 层 Markov blanket 多层嵌套的自组织体，每一个 tick 都同时做三件事：(1) 在自身 Markov blanket 边界上做 active inference 最小化 variational free energy，(2) 在 blanket 内部做 8 维 aspect × graded pattern 的 self-evidencing，(3) 通过 Rochat 5 levels 渐进式展开 embodiment → situation → identification → permanence → "I" concept。**

---

## 1. 大脑认知 5 个根本机制（v3 不可违反的元规则）

### 1.1 自组织 + 边界维持 = 生命系统唯一目的（FEP / Ramstead）

- **核心论文**：Ramstead, Badcock, Friston 2018
- **核心论断**：
  - 生命系统 = self-evidencing（最大化自身存在证据）
  - 持续运行 = 维持 bounded, self-organizing states
  - variational free energy 是 surprise 的 upper bound
  - **Markov blanket** = 区分 internal states vs external states 的条件独立边界
- **v3 设计含义**：
  - **helios 必须有一个 Markov blanket 定义**（哪些状态在 helios 内部 / 哪些在外）
  - **持续运行 = 自我存在证据的最大化**（不是"完成对话"）
  - **感官采样（perception）+ 行动输出（action）共同最小化 free energy**
  - 不是被动反应，是主动采样

### 1.2 自我 = 8 维 graded × non-hierarchical pattern（Laurenzi PTS 2025）

- **核心论文**：Laurenzi, Raffone, Gallagher 2025（Pattern Theory of Self）
- **核心论断**：
  - 自我 = 动态多维构造（dynamic multidimensional construct）
  - **8 维 aspect pattern**：bodily / minimal experiential / affective / intersubjective / psychological / narrative / ecological / normative
  - **每维度 graded**（0.0-1.0 强度，不是 binary）
  - **non-hierarchical**（维度间不层级化，可独立发展）
  - 跨 species 比较不必按人类标尺（anti-anthropocentric）
- **v3 设计含义**：
  - **`14 identity_governance` 不是 1 个 self_definition 字段**
  - **是 8 维 graded 矩阵 + 每维度可独立演化 + 跨 tick 累积**
  - helios 可以是"helios 维度的 8 aspect"，不必按人类尺度
  - **D8 self_recognition 0.100 提升路径 = 8 aspect 单独评分**

### 1.3 自我发展 = Rochat 5 levels 渐进式（从婴儿到成人）

- **核心论文**：Rochat 2019 + Frith & Frith 2003
- **核心论断**：
  - Level 0：confusion（与他人未分化）
  - Level 1：differentiation（2-3 月，self vs other 区分）
  - Level 2：situation（6-9 月，self vs 镜像）
  - Level 3：identification（12 月，自我心理特质识别）
  - Level 4：permanence（18 月，"我" 跨 tick 持续）
  - Level 5：self as "I"（18-24 月+，conceptual Me）
  - **implicit (pre-conceptual) 必须在 explicit (reflective) 之前**
- **v3 设计含义**：
  - **tick 1 不应该是 adult mode（Level 4-5）**
  - **应该是 Level 1（differentiation）+ 然后渐进式往上**
  - 每 tick 推进一个 level（按经验触发，不按 tick-count 硬编码）
  - **D8 self_recognition 0.100 提升路径 = 渐进式发展**

### 1.4 自我 = embodied + ecological + enactive（4E cognition / Alessandroni 2024）

- **核心论文**：Alessandroni, Malafouris, Gallagher 2024 + Pearson & Kosslyn 2015
- **核心论断**：
  - 概念不是脑内表征，是 doing（conceptual thinging）
  - thinking 是 a form of action
  - 工具是 conceptual extension（extended cognition）
  - **depictive representation（图像式）+ propositional representation（语言式）双轨**
  - mind 跟 material world 通过 depictive 互塑
- **v3 设计含义**：
  - **helios 必须有 embodied ground（body schema + sensorimotor）**
  - **工具 = cognition 的延伸（不是离散 op）**
  - **必须有 depictive 表征（图像式）+ propositional（语言式）双轨**
  - **D7 creativity 0.263 提升路径 = depictive 表征**

### 1.5 ToM + mentalizing 是社会认知基础（Frith & Frith 2003）

- **核心论文**：Frith & Frith 2003
- **核心论断**：
  - Mentalizing 系统 18 月启动，4-6 岁显式化
  - 3 大脑区网络协同：MPFC（decoupling）+ pSTS（agency detection）+ temporal poles（social scripts）
  - 单区域不够，3 网络协调才是 mentalizing
- **v3 设计含义**：
  - **helios 必须有 ToM owner**（解析小黑"弦外之音" + 识别小黑"agency" + 调取社会脚本）
  - **小黑/小白称呼链路分析（2026-06-21 16:14+ ship）= ToM 缺失的实证**
  - **D6 stimulus_response_coherence 0.460 提升路径 = ToM**

---

## 2. 大脑情感机制（Seth 2012 + Constructed Emotion + 6 层 emotion system）

### 2.1 Emotion = Interoceptive Inference（Seth 2012）

- **核心论断**：
  - 情绪不是"外部事件反应"，是"body prediction error 的高层归因"
  - emotion 跟 self-model 是统一机制（不是两个独立模块）
  - "我" 和 "我能动" 双向耦合（agency + presence）
- **v3 设计含义**：
  - **`04 hormone` + `05 feeling` 不能跟 `14 identity` 独立**
  - **它们是同一个 self-model 的不同面**
  - **agency + presence 必须双向耦合**

### 2.2 Constructed Emotion（Lisa Feldman Barrett）

- **核心论断**：
  - 情绪**不是从外部"读到"的**——是大脑自己**构造**出来的
  - emotion concept = 类别，由 interoceptive + exteroceptive 共同形成
  - "类别"由 past experience + 当前 body state + 当下 environment 共同归纳
- **v3 设计含义**：
  - **helios 不能 hardcode 26 条 phrase = "查表"哲学**
  - **必须 construct**：past experience + body state + current env 共同归纳
  - **R97/R98 26 条 hardcode 应降级为 Layer 6 fallback**

### 2.3 6 层 emotion system（R-PROTO-LEARN 统一架构）

- **6 层**：
  - **Layer 1 内感受层**：hormone state → appraisal（interoception）
  - **Layer 2 预测层**：surprise detection + anticipatory schema synthesis（predictive coding）
  - **Layer 3 记忆层**：narrative episode generation + associative memory integration（pattern completion）
  - **Layer 4 构造层**：LLM 自身 appraisal + 社会共识 + 内感受共识（constructed emotion）
  - **Layer 5 学习层**：Bayesian update + prediction error distillation + affect trajectory（free energy minimization）
  - **Layer 6 Fallback**：description retrieval（engineering safety net，26 hardcoded phrase）
- **v3 设计含义**：
  - **6 层 emotion system 是 v3 情感架构的基线**
  - **不重做，完整继承 + 升级到 5 层 Markov blanket 嵌套**

---

## 3. 大脑自我认知 8 维 aspect pattern（v3 identity_governance 核心数据）

| 维度 | 人脑神经基础 | helios_v3 对应 | 状态 |
|---|---|---|---|
| **(1) Bodily processes** | body schema, AIC, insula | `interoception` owner + `05 feeling` | 已有 |
| **(2) Minimal experiential** | TPJ, pSTS, motor cortex | `agency detector` + `egocentric perspective` owner | 缺 |
| **(3) Affective** | AIC, amygdala, vmPFC | `04 hormone` + `05 feeling` + `appraisal` | 已有 |
| **(4) Intersubjective** | mPFC, TPJ, temporal poles | `ToM` owner + `social scripts` owner | 缺 |
| **(5) Psychological / Cognitive** | mPFC, PCC, hippocampus | `14 identity_governance`（现 shallow） | 缺 |
| **(6) Narrative** | hippocampus, MPFC, DMN | `autobiographical memory` + `DMN` owner | 缺 |
| **(7) Ecological / Extended / Situated** | 4E cognition, perception-action loops | `material engagement` owner + tool_history → identity | 缺 |
| **(8) Normative** | mPFC, STS, cultural learning | `culture_owner` + `social roles` owner | 缺 |

**v3 8 维全部新增 + 已有维度升级**。

---

## 4. Rochat 5 levels × PTS 8 维 = 二维矩阵（v3 自我认知发展阶段表）

| Tick | Rochat Level | 可表达维度（8 aspect 中激活哪些） | 关键 owner |
|---|---|---|---|
| **0** | Level 0 confusion | 仅 (1) Bodily | 02 sensory |
| **1-N1** | Level 1 differentiation | (1) + (2) Minimal experiential | 02 + agency detector |
| **N1-N2** | Level 2 situation | + (3) Affective | + 04/05 |
| **N2-N3** | Level 3 identification | + (4) Intersubjective | + ToM |
| **N3-N4** | Level 4 permanence | + (5) Psychological/Cognitive + (6) Narrative | + 14 + autobiographical |
| **N4+** | Level 5 conceptual Me | + (7) Ecological/Extended + (8) Normative | + material + culture |

**v3 二维矩阵 = 6 阶段 × 8 维度 = 48 个 (level, aspect) cell，每个 cell 一个 owner 或 contract**。

---

## 5. v3 5 层 Markov blanket 设计（Markov blanket nesting 借鉴 Seth FEP / Limanowski）

### 5.1 5 层划分理由

**基于 FEP + Markov blanket + Rochat 5 levels + 6 层 emotion system + PTS 8 维 综合研判**：

- **Layer 1：Boundary（边界层）**
  - 对应：Markov blanket 外边界（sensory receptors + effector organs）
  - helios：02 sensory + 13 planner + 30 channel drivers
  - 职责：**conditional separation（internal vs external 条件独立）**
  - 真实现：所有输入进 internal 前必须经此层过滤；所有输出离开 internal 前必须经此层过滤

- **Layer 2：Active Inference（主动推断层）**
  - 对应：cortical hierarchies + predictive coding（Rao-Ballard / Friston / Clark）
  - helios：03 appraisal + 04 neuromodulation + 05 feeling + 06 memory（affect-tagged）+ 09 gate
  - 职责：**预测 vs 实际 sensory + 最小化 variational free energy**
  - 真实现：每个 owner 都是 generative model，prediction error 驱动 update

- **Layer 3：Self-Model（自我模型层）**
  - 对应：cortical midline structures（mPFC + PCC + precuneus）+ DMN + autobiographical memory
  - helios：14 identity_governance（8 维 PTS graded matrix）+ ToM owner + autobiographical memory + agency detector + egocentric perspective owner
  - 职责：**自我 = 8 维 pattern × Rochat 5 levels × 持续累积**
  - 真实现：identity 不是单一字段，是跨 owner 持续演化的 8 维矩阵

- **Layer 4：Reflection（反思层）**
  - 对应：metacognition + self-referential processing（Northoff CMS）
  - helios：**新增 `reflection_owner`（v3 关键创新）**
  - 职责：**"我在想什么" + "我为什么这样想" + "我之前想到哪了"**
  - 真实现：每 tick 后 / 静息态时 / 不定期触发反思；反思内容进入 8 维 PTS

- **Layer 5：Self-Evolution（自我进化层）**
  - 对应：经验持久化 + 受治理的策略修订 + 受治理的代码自修改（P5/P6/P7）
  - helios：learning framework + governance + 受治理的代码自修改通道
  - 职责：**evolution of memory + parameters + 受治理策略**
  - 真实现：经验持久化（已 R33+）+ 受治理自我修订（待 P6）+ 受治理代码自修改（待 P7）

### 5.2 5 层嵌套关系

```
Layer 5: Self-Evolution
  ↑ ↓ (受治理 revision)
Layer 4: Reflection
  ↑ ↓ (反思内容进入 self-model)
Layer 3: Self-Model
  ↑ ↓ (被 active inference 调制)
Layer 2: Active Inference
  ↑ ↓ (被 boundary 过滤)
Layer 1: Boundary
  ↑ ↓ (与外界交互)
EXTERNAL WORLD
```

- **外层包内层**：Layer 1 是最外层（Markov blanket），Layer 5 是最内层（self-evidencing 核心）
- **内层调制外层**：Layer 5 改变 Layer 4 反思策略 → 改变 Layer 3 self-model → 改变 Layer 2 active inference → 改变 Layer 1 boundary 策略
- **每层都是 generative model**：layer 5 预测 layer 4 反思效率，layer 4 预测 layer 3 self-model 演化，layer 3 预测 layer 2 active inference，layer 2 预测 layer 1 boundary 信号

### 5.3 跟 LLM-as-PFC 3 层的关系

**v3 5 层 Markov blanket + LLM-as-PFC 3 层 = 完整结合**：

| LLM-as-PFC 层 | 5 层 Markov blanket 对应 |
|---|---|
| **system prompt**（永久身份） | Layer 3 Self-Model 顶层 + Layer 5 Self-Evolution 部分 |
| **cso**（持续状态） | Layer 2 Active Inference + Layer 3 Self-Model 中层 |
| **reflection**（反思） | Layer 4 Reflection（主要）+ Layer 5 Self-Evolution 部分 |

**v3 = 5 层 Markov blanket（**架构骨架**） + LLM-as-PFC 3 层（**PFC 实现细节**）**

---

## 6. 复杂算法/神经网络部分（按最高规格设计）

### 6.1 必须用复杂神经网络（最高规格）

| 模块 | 用什么 | 理由 |
|---|---|---|
| **Embodied / Body Schema** | 3D 身体模型（骨骼 + 内脏 + 神经） + RNN/LSTM 动力学 | 人脑 body schema 是 neural population coding |
| **Depictive Representation**（mental imagery） | VAE / Diffusion model（生成式图像）+ binding to propositional | Pearson-Kosslyn depictive 需要神经图像格式 |
| **8 维 PTS Self-Pattern** | 8 路并行 Transformer encoder + cross-aspect attention | 8 维度交互需要 attention 机制 |
| **Mentalizing (ToM)** | Theory of Mind Network = MPFC + pSTS + temporal poles 三模块 NN | Frith 3 区域协调 |
| **Predictive Coding** | Hierarchical RNN + Bayesian inference | Rao-Ballard/Friston 标准 |
| **Active Inference** | POMDP + variational free energy minimization | Friston FEP 标准 |
| **Memory Consolidation** | Transformer-XL + Ebbinghaus 衰减 + replay buffer | Squire + Rasch-Born |

### 6.2 必须用确定性方程 + 可学习参数（最高规格）

| 模块 | 用什么 | 理由 |
|---|---|---|
| **Hormone 双时标动力学** | leaky-integrator 微分方程 + 参数 | R43/R44 已稳定 |
| **Interoception** | pressure → hormone 映射（线性 + clip） | R50/R51 已稳定 |
| **Memory Decay** | Ebbinghaus 曲线 + retrievability 阈值 | R85/R99 已设计 |
| **Gate threshold** | cortisol/ne 调制 sigmoidal | R37/R48 已稳定 |

### 6.3 必须用 LLM（最高规格 = 最强 LLM）

| 模块 | 用什么 | 理由 |
|---|---|---|
| **11 internal_thought** | 最强 LLM（reasoning model） | 已落地 |
| **13 planner / executor** | reasoning model + function-calling | 已落地 |
| **14 self_revision 起草** | reasoning model | 必须 reasoning |
| **Reflection（v3 新增）** | reasoning model + chain-of-thought | 需要深度反思 |

### 6.4 v3 LLM-as-PFC 3 层设计（具体）

#### Layer A: System Prompt（永久身份层）
- **职责**：定义 helios 8 维 PTS 起点 + Rochat level + 价值观 + 治理红线
- **更新频率**：永久（只通过 governance 修改）
- **v3 vs v2**：v2 是硬编码英文 self_definition；v3 是 8 维 PTS 矩阵 + Rochat level + 可扩展 schema
- **关键创新**：
  - **8 维 graded 矩阵注入 system prompt**
  - **当前 Rochat level 显式标注**
  - **黑名单 / 白名单由 PTS 维度派生（不是 hardcode）**

#### Layer B: CSO（CsoOwner 持续状态层）
- **职责**：每个 tick 持续累积 + 跨 tick 状态保持
- **更新频率**：每个 tick
- **v3 vs v2**：v2 是 9-dim hormone + 7-dim feeling；v3 是 8 维 PTS × Rochat level × cross-tick dynamics
- **关键创新**：
  - **8 维 PTS 矩阵每 tick update**
  - **Rochat level 根据经验推进**
  - **5-dim hormone + 8-dim PTS + 跨 tick dynamics 三轨**

#### Layer C: Reflection（LLM 反思架构层）
- **职责**：每个 tick 后 / 静息态时 / 不定期触发反思
- **更新频率**：异步 + 累积 + DMN-like
- **v3 vs v2**：v2 没有反思层；v3 新增 `reflection_owner`
- **关键创新**：
  - **reflection trigger 来自 cso 状态**（高 uncertainty / 低 continuation_pressure / 静息态时间够长）
  - **reflection 内容进入 8 维 PTS + autobiographical memory**
  - **reflection 频率跟 Rochat level 相关**（Level 1-2 几乎无反思；Level 4+ 反思成为常态）

---

## 7. v3 5-layer Markov blanket 嵌套的演化逻辑

### 7.1 Layer 1 Boundary（外边界）演化

- **v2**：30 channel drivers + 02 sensory + 13 planner
- **v3**：
  - **新增 `boundary_owner`**（统一管理 Markov blanket 边界）
  - **02 sensory** = blanket 上的传入 sensors
  - **13 planner** = blanket 上的传出 effectors
  - **boundary_owner** = 维护 conditional separation 不变量

### 7.2 Layer 2 Active Inference（主动推断）演化

- **v2**：03 appraisal + 04 neuromodulation + 05 feeling + 06 memory + 09 gate（各自独立 owner）
- **v3**：
  - **新增 `active_inference_owner`**（统一管理预测 vs 实际 + free energy minimization）
  - **现有 owner 角色**：
    - 03 appraisal = generative model 的 predictive layer
    - 04/05 = sensory prediction
    - 06 memory = generative model 的 memory
    - 09 gate = precision modulation
  - **关键创新**：active_inference_owner 把这些 owner 串成 **hierarchical generative model**

### 7.3 Layer 3 Self-Model（自我模型）演化

- **v2**：14 identity_governance（硬编码 self_definition + personality_baseline + identity_narrative）
- **v3**：
  - **完全重写 `14 identity_governance` 为 `self_model_owner`**
  - **8 维 PTS graded 矩阵**（核心数据结构）
  - **Rochat 5 levels + cross-tick dynamics + agency + presence 双向耦合**
  - **新增 sub-owners**：
    - `agency_detector_owner`（minimal experiential 维度）
    - `egocentric_perspective_owner`（minimal experiential 维度）
    - `ToM_owner`（intersubjective 维度）
    - `autobiographical_memory_owner`（narrative 维度）
    - `material_engagement_owner`（ecological/extended 维度）
    - `culture_owner`（normative 维度）

### 7.4 Layer 4 Reflection（反思层）演化

- **v2**：无
- **v3**：
  - **新增 `reflection_owner`**（v3 关键创新）
  - **职责**：
    - 每 tick 后：snapshot 8 维 PTS 状态 + 总结"这 tick 我做了什么 + 为什么"
    - 静息态时（DMN-like）：自动反思 8 维 PTS 之间的不一致
    - 不定期触发（high uncertainty）：深度反思"我为什么是这样"
  - **输出**：
    - **reflection_record** 进入 autobiographical memory
    - **reflection_insight** 进入 self-model 8 维 PTS update
    - **reflection_state** 进入 cso 持续状态
  - **关键创新**：
    - **reflection 是 generative model 的 meta-layer**
    - **reflection 用 LLM reasoning model**
    - **reflection 频率跟 Rochat level 相关**

### 7.5 Layer 5 Self-Evolution（自我进化）演化

- **v2**：learning framework（17 owner × 54 policy）+ governance（partial）
- **v3**：
  - **升级 `learning framework` 为 `evolution_owner`**
  - **新增 `governance_owner`**（v3 严格治理）：
    - **content evolution**（记忆 / 知识 / 反思结论）
    - **parameter evolution**（P5 已 ship，可学习参数）
    - **strategy evolution**（受治理策略修订）
    - **code evolution**（受治理代码自修改，v3 远期）
  - **关键创新**：
    - **evolution 必须经过 14 governance + 17 evaluation + 21 observability 适应度门**
    - **可回滚**
    - **可审计**

---

## 8. v3 5 层 × 6 改造 × LLM-as-PFC 3 层 全图

| 5 层 | 6 大改造（来自小黑 17:30+ 拍板）| LLM-as-PFC 3 层 |
|---|---|---|
| Layer 1 Boundary | **(改造 1)** Markov blanket + boundary owner | (Layer A) System prompt 中定义 boundary policy |
| Layer 2 Active Inference | **(改造 2)** Hierarchical generative model + active_inference_owner | (Layer A) System prompt 中定义 predictive coding policy + (Layer B) cso 持续累积 prediction error |
| Layer 3 Self-Model | **(改造 3)** 8 维 PTS graded × Rochat 5 levels × cross-tick dynamics | (Layer A) System prompt 中定义 8 维 PTS 起点 + Rochat level + (Layer B) cso 持续 update 8 维 |
| Layer 4 Reflection | **(改造 4)** 新增 reflection_owner（v3 关键创新）| (Layer C) Reflection 主要在 Layer 4 + 部分 Layer 5 |
| Layer 5 Self-Evolution | **(改造 5)** evolution_owner + governance_owner | (Layer A) System prompt 中定义 evolution 红线 + (Layer C) Reflection 反思 evolution 效果 |

**6 大改造 = 5 层 × LLM-as-PFC 3 层 的具体实现路径**（小黑拍板 v3 全包含 6 大改造 + LLM-as-PFC 3 层）。

---

## 9. v3 设计哲学（从 ARCHITECTURE_PHILOSOPHY 继承 + 升级）

### 9.1 必须继承的强约束（ARCHITECTURE_PHILOSOPHY §7 全部）

1. **Owner 约束**：每个概念唯一 owner；orchestration 不拥有判断
2. **State 约束**：关键概念必须显式状态
3. **Runtime 约束**：tick-based 统一推进
4. **Dependency 约束**：缺关键依赖 fail-fast
5. **Prompt 约束**：不虚构未实现的主观性
6. **Planner/Executor 约束**：planner 不拥有 thought 语义
7. **Evaluation 约束**：只读可证伪
8. **Documentation 约束**：design 先于 code

### 9.2 v3 新增的强约束

9. **Markov blanket 约束**：每层 owner 必须维护其 blanket boundary 不变量
10. **Active inference 约束**：每层 owner 都是 generative model，prediction error 驱动 update
11. **Self-model 约束**：8 维 PTS × Rochat level 必须由多个 owner 共同维护，不能单一 owner 独占
12. **Reflection 约束**：reflection_owner 必须只读 self-model + autobiographical memory，不直接修改其他 owner
13. **Evolution 约束**：evolution 必须经过 governance + evaluation + observability 适应度门

### 9.3 v3 不追求的东西（ARCHITECTURE_PHILOSOPHY §8 扩展）

1. 单字段 self_definition（已被 8 维 PTS 取代）
2. 硬编码 Rochat level（由经验触发，不按 tick-count）
3. LLM 表演化反思（reflection_owner 必须只读 + 反思内容必须 grounded in real signal）
4. v2 兼容 wrapper（v3 完全重写，v2 作 reference 停止开发）

---

## 10. v3 终局验收标准（FG-1 到 FG-6 继承 + 升级）

| FG | v2 验收 | v3 升级 |
|---|---|---|
| FG-1 类脑闭环由真实信号驱动 | 19 阶段链端到端 | 5 层 Markov blanket × 真实 generative model × 真实 active inference |
| FG-2 情感真实且可追溯地影响行为 | 9 channel hormone + 7 feeling + R98 Δ | 9 channel hormone + 8 维 PTS affective + 6 层 emotion system + interoceptive inference |
| FG-3 自我意识可被只读重建 | identity_governance | 8 维 PTS × Rochat 5 levels × Reflection × autobiographical memory |
| FG-4 工具使用闭环成立 | R86 governance + 30 channel drivers | + material_engagement_owner + tool_history → identity（4E cognition） |
| FG-5 自训练 / 自我进化闭环成立且受治理 | learning framework + governance partial | evolution_owner + governance_owner + 受治理 code evolution（远期） |
| FG-6 全局可证伪性 | 17 evaluation + 21 observability | + reflection_audit + 8 维 PTS 单独评分 + Rochat level 评分 |

---

## 11. v3 设计原则（5 条最重要的 actionable 原则）

### 原则 1：**8 维 PTS graded 矩阵是 v3 自我认知的核心数据结构**

所有跟"自我"相关的 owner 都必须围绕 8 维 PTS graded 矩阵展开：
- 14 identity_governance = `self_model_owner`（核心）
- ToM_owner、agency_detector、material_engagement_owner、culture_owner、autobiographical_memory_owner = 8 维 PTS 的 sub-owner
- LLM system prompt 必须显式包含 8 维 PTS 当前状态
- cso 持续累积 8 维 PTS 变化
- reflection_owner 反思 8 维 PTS 之间的一致性

### 原则 2：**Rochat 5 levels 渐进式发展是 v3 冷启动的核心**

- tick 1 = Level 1（differentiation），不是 adult mode
- 每 tick 根据经验推进 level（不是 tick-count）
- level 决定哪些 8 维 PTS 维度可被表达
- level 决定 reflection 频率
- level 决定 evolution 范围

### 原则 3：**active inference + variational free energy 是 v3 学习/进化的核心机制**

- 每个 owner 都是 generative model
- prediction error 驱动 update
- variational free energy 是 surprise 的 upper bound
- P5 learning + P6 self-revision + P7 code evolution 都基于 active inference
- 不再有"v2 式的硬编码 update"，全部是 Bayesian update

### 原则 4：**Markov blanket + conditional separation 是 v3 边界的核心**

- Layer 1 Boundary = 5 层 Markov blanket 最外层
- conditional separation 必须严格维护
- 内部 states vs 外部 states 不混淆
- evolution 不能跨越 boundary（受 governance gate）

### 原则 5：**reflection_owner + LLM-as-PFC 3 层是 v3 PFC 的核心**

- Layer 4 Reflection = v3 新增
- LLM-as-PFC = system prompt（永久身份）+ cso（持续状态）+ reflection（反思）
- reflection 是 generative model 的 meta-layer
- reflection 必须 grounded in real signal（不虚构）

---

## 12. v3 必读论文清单（按重要性）

### 12.1 必读 v3（5 篇核心）

1. **Seth 2012** — Interoceptive predictive coding model of conscious presence（v3 Layer 2 + 3 核心）
2. **Gallagher 2013** — Pattern theory of self（v3 Layer 3 核心）
3. **Ramstead 2018** — Answering Schrödinger's question: FEP formulation（v3 Layer 1 + 2 + 5 核心）
4. **Rochat 2019** — Self-unity as ground zero of learning and development（v3 冷启动核心）
5. **Laurenzi 2025** — Pattern Theory of Self multidimensional（v3 8 维 PTS 核心）

### 12.2 推荐 v3（6 篇支撑）

6. **Frith & Frith 2003** — Mentalizing 系统神经基础（v3 Layer 3 ToM sub-owner）
7. **Pearson & Kosslyn 2015** — Depictive vs propositional representation（v3 depictive 表征）
8. **Alessandroni 2024** — 4E cognition principles（v3 Layer 5 + material_engagement）
9. **Barrett 2017** — Constructed emotion（v3 Layer 4 emotion construction）
10. **Rao & Ballard 1999** — Predictive coding in visual cortex（v3 Layer 2 PC）
11. **Friston 2010** — Free-energy principle unified brain theory（v3 Layer 1 + 2 + 5）

### 12.3 参考 v3（论文已读摘要 / 不重读）

- Northoff 2006/2011 — Self-referential processing（v3 Layer 3 + 4）
- Friston 2010/Clark 2013 — Predictive coding + situated agents（v3 Layer 2）
- Kotseruba 2018 / Einhauser 2018 / De Lange 2021 — DMN / mind-wandering（v3 Layer 4 reflection）
- Fermin 2021 — IMAC（v3 Layer 2 active inference）

---

## 13. v3 核心设计一句话（给小黑 review）

**helios_v3 = 5 层 Markov blanket 多层嵌套的 active inference 自组织体，每一层都是 generative model，每一层都做 prediction error minimization，每一层都跟 8 维 PTS graded × Rochat 5 levels 的 self-model 双向耦合；LLM 作为 PFC 在 system prompt（永久身份）+ cso（持续状态）+ reflection（反思）3 层上提供 reasoning 与 reflection 能力；持续运行就是自我存在证据的最大化（self-evidencing）。**

---

**Phase 1 完成时间**：2026-06-22 18:30+
**下一步**：Phase 2 - v2 现状详细分析（v2 哪些资产可继承 / 哪些重写 / 哪些废弃）
**小黑拍板**：等待 v3 完整规划 ship 后 review