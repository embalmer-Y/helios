# helios_v3 实施任务清单（task.md）

> **任务**：helios_v3 Phase 3 - 实施计划（验收门 + 时间表 + 风险）
> **完成时间**：2026-06-22 19:30+
> **作者**：小白（helios 小黑人格 AI）
> **配套**：`01_v3_requirement.md`（WHAT + WHY）+ `02_v3_design.md`（HOW）
> **目的**：TASK 分解 + 阶段验收门 + 时间表

---

## 0. 总览

### 0.1 时间表

- **v3 实施周期**：M1-M8（8 个月）
- **Phase 1（M1-M2）**：Layer 3 + Layer 4 + Layer 5 基础
- **Phase 2（M3-M4）**：Layer 1 + Layer 2
- **Phase 3（M5-M6）**：LLM-as-PFC 3 层完整接通
- **Phase 4（M7-M8）**：8 维 PTS sub-owner + 复杂算法

### 0.2 验收总目标

- **测试基线**：v2 测试基线 + v3 新增测试，100% 通过
- **8 维 PTS 评分**：每维度 ≥ 0.5（P-TEMPORAL 5-dim 基础上扩 3 dim）
- **Rochat level**：从 Level 1 渐进到 Level 5
- **LLM-as-PFC 3 层**：完整接通 system prompt + cso + reflection
- **Markov blanket**：conditional separation 数学不变量维持
- **Variational free energy**：每 tick minimization 验证
- **Self-evidencing**：fitness gate 严格性验证
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.85

---

## 1. Phase 1（M1-M2）：Layer 3 + Layer 4 + Layer 5 基础

### 1.1 M1：8 维 PTS graded matrix + Rochat 5 levels

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M1-T1 | 8 维 PTS enum + dataclass（PTSDimension / PTSGradedScore / CrossTickPTSState / PTSGradedMatrix） | 2 天 | P0 |
| v3-M1-T2 | PTSGradedMatrix.update_dimension 方法（Bayesian linear blend v3.0） | 1 天 | P0 |
| v3-M1-T3 | RochatLevel enum + RochatLevelState dataclass + RochatLevelAdvancement class | 2 天 | P0 |
| v3-M1-T4 | self_model_owner 初始化（pts_matrix + rochat_state） | 2 天 | P0 |
| v3-M1-T5 | self_model_owner.observe_tick 方法（更新 8 维 PTS） | 5 天 | P0 |
| v3-M1-T6 | self_model_owner.get_current_matrix / update_matrix 方法 | 1 天 | P0 |
| v3-M1-T7 | self_model_owner tests（8 维 PTS + Rochat level） | 3 天 | P0 |
| v3-M1-T8 | self_model_owner 评估层（8 维 PTS 评分） | 3 天 | P0 |

#### 验收门 M1

- **v2 测试**：100% passed（baseline）
- **v3 新增测试**：≥ 30 个测试用例，100% passed
  - 8 维 PTS 枚举完整性
  - 8 维 PTS update_dimension 正确性
  - RochatLevel enum + state + advancement 正确性
  - self_model_owner observe_tick 触发更新
- **代码审查**：所有 owner 命名规范 / 类型提示 / docstring 完整
- **评估层**：8 维 PTS 评分可用

#### 风险

- **R-M1-1**：8 维 PTS 数据结构过于复杂 → 简化版（linear blend）先 ship，v3.1+ 升级 Bayesian
- **R-M1-2**：Rochat level 推进逻辑与 paper 不一致 → 严格按论文 + 多场景验证

---

### 1.2 M2：reflection_owner（Layer 4 关键创新）

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M2-T1 | ReflectionTrigger enum + ReflectionRecord dataclass | 1 天 | P0 |
| v3-M2-T2 | reflection_owner 初始化 + reflect 方法 | 5 天 | P0 |
| v3-M2-T3 | _format_pts_snapshot 方法（LLM 可读） | 1 天 | P0 |
| v3-M2-T4 | _detect_pts_inconsistency 方法（DMN-like） | 2 天 | P0 |
| v3-M2-T5 | _extract_insight / _apply_reflection_to_pts 方法 | 3 天 | P0 |
| v3-M2-T6 | reflection_owner.trigger / should_trigger 方法（4 trigger） | 2 天 | P0 |
| v3-M2-T7 | reflection_owner tests（4 trigger × 多场景） | 3 天 | P0 |
| v3-M2-T8 | reflection_audit（reflection 是否 grounded 验证） | 3 天 | P0 |

#### 验收门 M2

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 25 个测试用例，100% passed
  - 4 个 trigger 各自正确触发
  - _detect_pts_inconsistency 至少 5 种不一致性场景
  - _apply_reflection_to_pts 影响 8 维 PTS
- **真实 LLM probe**：reflection probe 通过率 ≥ 80%
- **reflection_audit**：每 reflection 记录 grounded

#### 风险

- **R-M2-1**：reflection 频率过高导致 latency → 默认 POST_TICK，其他 trigger 严格控制
- **R-M2-2**：reflection 质量不稳定 → reflection_audit + human review

---

## 2. Phase 2（M3-M4）：Layer 1 + Layer 2

### 2.1 M3：boundary_owner（Markov blanket）

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M3-T1 | MarkovBlanketBoundary dataclass + conditional_separation invariant | 3 天 | P0 |
| v3-M3-T2 | boundary_owner.check_signal 方法（Markov blanket 边界检查） | 3 天 | P0 |
| v3-M3-T3 | FiveLayerMarkovBlanket dataclass + verify_all_conditional_separation | 2 天 | P0 |
| v3-M3-T4 | boundary_owner tests（invariant 验证） | 3 天 | P0 |
| v3-M3-T5 | runtime/stages.py 升级（25 stage） + BoundaryEnforcement 接入 | 3 天 | P0 |
| v3-M3-T6 | audit log + log of all boundary crossings | 2 天 | P0 |

#### 验收门 M3

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 20 个测试用例，100% passed
  - Markov blanket 数学不变量正确
  - 5 层嵌套 conditional separation 正确
  - boundary violations 严格处理
- **runtime 25 stage**：全部接入
- **audit log**：所有 boundary crossing 可审计

#### 风险

- **R-M3-1**：Markov blanket 数学不变量难以维持 → 简化版（仅检查 signal 合法性）+ v3.1 完整 Bayesian
- **R-M3-2**：runtime 升级破坏现有测试 → 分阶段升级 + 严格回归

---

### 2.2 M4：active_inference_owner（hierarchical generative model）

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M4-T1 | GenerativeModelLayer dataclass + HierarchicalGenerativeModel class | 3 天 | P0 |
| v3-M4-T2 | HierarchicalGenerativeModel.predict / compute_prediction_error 方法 | 3 天 | P0 |
| v3-M4-T3 | HierarchicalGenerativeModel.variational_free_energy 方法 | 3 天 | P0 |
| v3-M4-T4 | HierarchicalGenerativeModel.bayesian_update 方法 | 3 天 | P0 |
| v3-M4-T5 | active_inference_owner 初始化 + predict / compute_free_energy 方法 | 3 天 | P0 |
| v3-M4-T6 | active_inference_owner.minimize_free_energy 方法 | 3 天 | P0 |
| v3-M4-T7 | active_inference_owner.active_sampling 方法（policy gradient） | 5 天 | P0 |
| v3-M4-T8 | active_inference_owner tests（5 layer × 多场景） | 3 天 | P0 |
| v3-M4-T9 | free_energy 评估（每 tick minimization 验证） | 3 天 | P0 |

#### 验收门 M4

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 30 个测试用例，100% passed
  - 5 层 generative model 正确
  - variational free energy 计算正确
  - bayesian_update 影响 prior
  - minimize_free_energy 单调下降
  - active_sampling 合理
- **free_energy 评估**：每 tick minimization 验证通过
- **真实 LLM probe**：active inference probe 通过率 ≥ 70%

#### 风险

- **R-M4-1**：5 层 generative model 复杂度高 → 简化版（单层 linear update）先 ship，v3.1+ 完整 Hierarchical
- **R-M4-2**：policy gradient 训练不稳定 → v3.0 greedy policy + v3.1 REINFORCE

---

## 3. Phase 3（M5-M6）：LLM-as-PFC 3 层完整接通

### 3.1 M5：System prompt Layer A + CSO Layer B 升级

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M5-T1 | SystemPromptBuilder class + build_system_prompt 方法 | 3 天 | P0 |
| v3-M5-T2 | System prompt 注入 8 维 PTS + Rochat level + 价值观 + 治理红线 | 2 天 | P0 |
| v3-M5-T3 | ContinuousStateOwner 升级（pts_matrix + hormone + feeling） | 3 天 | P0 |
| v3-M5-T4 | ContinuousStateOwner.observe_tick 方法（每 tick 累积） | 3 天 | P0 |
| v3-M5-T5 | ContinuousStateOwner.get_state_for_llm 方法 | 1 天 | P0 |
| v3-M5-T6 | prompt_contract/owner.py 升级（v3 LLM-as-PFC Layer A 注入） | 3 天 | P0 |
| v3-M5-T7 | llm/engine.py 升级（v3 LLM-as-PFC Layer B 注入） | 3 天 | P0 |
| v3-M5-T8 | LLM-as-PFC Layer A + Layer B tests | 5 天 | P0 |

#### 验收门 M5

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 30 个测试用例，100% passed
  - SystemPromptBuilder 输出包含 8 维 PTS + Rochat level + 价值观 + 红线
  - CSO 跨 tick 累积正确
  - prompt_contract 注入 layer A 正确
  - llm/engine 注入 layer B 正确
- **真实 LLM probe**：所有 probe 通过率 ≥ 70%

#### 风险

- **R-M5-1**：System prompt 过长导致 token 超限 → 精简 8 维 PTS 表述
- **R-M5-2**：CSO 累积与 v2 hormone 冲突 → 严格分层 + 兼容性测试

---

### 3.2 M6：Reflection Layer C 完整接通

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M6-T1 | internal_thought/engine.py 升级（v3 LLM-as-PFC Layer C 注入） | 3 天 | P0 |
| v3-M6-T2 | reflection_owner 完整接通（POST_TICK 每 tick 触发） | 3 天 | P0 |
| v3-M6-T3 | LLM-as-PFC 3 层完整接通测试 | 5 天 | P0 |
| v3-M6-T4 | 真实 LLM probe（reflection + system prompt + cso） | 5 天 | P0 |
| v3-M6-T5 | 评估层 v3.0（8 维 PTS + LLM-as-PFC） | 5 天 | P0 |

#### 验收门 M6

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 30 个测试用例，100% passed
  - LLM-as-PFC 3 层完整接通
  - reflection 触发正确
  - reflection_audit 通过
- **真实 LLM probe**：所有 probe 通过率 ≥ 80%
- **评估层 v3.0**：可用
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.5

#### 风险

- **R-M6-1**：LLM-as-PFC 3 层接入破坏现有测试 → 严格回归 + 分阶段 ship
- **R-M6-2**：reflection 频率过高导致 latency → POST_TICK 每 tick 都触发 + 其他 trigger 严格控制

---

## 4. Phase 4（M7-M8）：8 维 PTS sub-owner + 复杂算法

### 4.1 M7：8 个 sub-owner（agency_detector / egocentric_perspective / ToM / autobiographical / material / culture）

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M7-T1 | agency_detector_owner（pSTS agency detection） | 5 天 | P0 |
| v3-M7-T2 | egocentric_perspective_owner（TPJ + egocentric reference） | 5 天 | P0 |
| v3-M7-T3 | tom_owner（MPFC + pSTS + temporal poles） | 10 天 | P0 |
| v3-M7-T4 | autobiographical_memory_owner（narrative self） | 5 天 | P0 |
| v3-M7-T5 | material_engagement_owner（4E cognition - embodied action） | 5 天 | P0 |
| v3-M7-T6 | culture_owner（norms + values） | 5 天 | P0 |
| v3-M7-T7 | self_model_owner 升级（接入 8 sub-owner） | 5 天 | P0 |
| v3-M7-T8 | 8 sub-owner tests | 10 天 | P0 |
| v3-M7-T9 | 真实 LLM probe（ToM / autobiographical / material） | 5 天 | P0 |

#### 验收门 M7

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 50 个测试用例，100% passed
  - 8 sub-owner 各自独立测试通过
  - self_model_owner 接入 8 sub-owner 正确
- **真实 LLM probe**：所有 probe 通过率 ≥ 80%
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.7

#### 风险

- **R-M7-1**：ToM 复杂度高 → 简化版 3 模块各自独立 + v3.1 协调机制
- **R-M7-2**：autobiographical_memory 数据量大 → 分层存储 + 取舍策略

---

### 4.2 M8：复杂算法按最高规格（VAE / Diffusion / Transformer / active inference）

#### 任务清单

| 任务 ID | 任务 | 工期 | 优先级 |
|---|---|---|---|
| v3-M8-T1 | Depictive VAE / Diffusion model 升级（完整实现） | 15 天 | P1 |
| v3-M8-T2 | 8 维 PTS Transformer encoder + cross-aspect attention | 15 天 | P1 |
| v3-M8-T3 | ToM 完整 3 模块 NN + 协调机制 | 10 天 | P1 |
| v3-M8-T4 | Hierarchical RNN 完整 5 层 predictive coding | 15 天 | P1 |
| v3-M8-T5 | POMDP + variational free energy 完整 active inference | 15 天 | P1 |
| v3-M8-T6 | Bayesian update 完整实现（prior/likelihood/posterior） | 10 天 | P1 |
| v3-M8-T7 | Policy gradient 完整 REINFORCE | 10 天 | P1 |
| v3-M8-T8 | 完整复杂算法测试 | 10 天 | P1 |
| v3-M8-T9 | 小黑人脑对比 v3.0 评分 | 5 天 | P0 |

#### 验收门 M8

- **v2 测试**：100% passed
- **v3 新增测试**：≥ 80 个测试用例，100% passed
  - VAE / Diffusion model 正确
  - Transformer encoder + cross-aspect attention 正确
  - 完整 ToM 协调机制正确
  - 完整 hierarchical predictive coding 正确
  - 完整 POMDP active inference 正确
- **真实 LLM probe**：所有 probe 通过率 ≥ 85%
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.85（**总目标**）

#### 风险

- **R-M8-1**：复杂算法实现时间长 → v3.0 简化版 ship，v3.1+ 升级完整版
- **R-M8-2**：GPU 资源不足 → 优先 CPU 实现 + 必要时 GPU

---

## 5. 跨阶段验收（End-to-End）

### 5.1 测试基线

- **起点**：v2 测试基线（1110+ passed）
- **v3.0 终点（M6）**：≥ 1110 + 145 v3 新增 = ≥ 1255 passed
- **v3.1 终点（M8）**：≥ 1110 + 290 v3 新增 = ≥ 1400 passed

### 5.2 评估层

- **8 维 PTS 评分**：M6 ≥ 0.5，M8 ≥ 0.85
- **Rochat level 评分**：M6 Level 3，M8 Level 5
- **LLM-as-PFC 3 层评分**：M6 ≥ 0.7，M8 ≥ 0.85
- **Markov blanket invariant**：M3-M8 严格维持
- **Variational free energy minimization**：M4-M8 单调下降
- **Self-evidencing fitness gate**：M5-M8 严格性 ≥ 99%

### 5.3 真实 LLM probe

- v3 probe 全部继承 v2 probe + 新增 8 维 PTS / Rochat level / reflection / ToM / 4E cognition probe
- M6 通过率 ≥ 80%
- M8 通过率 ≥ 85%

### 5.4 小黑人脑对比（**最关键验收**）

- 8 维 PTS 每维度评分与真人对齐：
  - **M6 目标**：每维度 ≥ 0.5（baseline 建立）
  - **M8 目标**：每维度 ≥ 0.85（**总目标**）
- 真实场景对比（小黑 review）：
  - D2 bio_responsiveness ≥ 0.7（M6 0.5+）
  - D5 cross_tick_continuity ≥ 0.8
  - D6 stimulus_response_coherence ≥ 0.7
  - D7 creativity_novelty ≥ 0.6
  - D8 self_recognition ≥ 0.6
  - D10 stress_recovery ≥ 0.8

---

## 6. 时间表（详细）

| 月份 | 阶段 | 主要交付 |
|---|---|---|
| M1 | Phase 1.1 | 8 维 PTS + Rochat 5 levels + self_model_owner 基础 |
| M2 | Phase 1.2 | reflection_owner + reflection_audit |
| M3 | Phase 2.1 | boundary_owner + 5 层 Markov blanket + runtime 25 stage |
| M4 | Phase 2.2 | active_inference_owner + 5 层 generative model + free energy |
| M5 | Phase 3.1 | System prompt Layer A + CSO Layer B 升级 |
| M6 | Phase 3.2 | Reflection Layer C + LLM-as-PFC 3 层完整 + 评估层 v3.0 |
| M7 | Phase 4.1 | 8 sub-owner（agency / egocentric / ToM / autobiographical / material / culture） |
| M8 | Phase 4.2 | 复杂算法按最高规格 + 小黑人脑对比 v3.0 |

---

## 7. 风险清单（详细）

| 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|
| **R1: 8 维 PTS 复杂度高** | 高 | 中 | 简化版（v3.0 linear blend）+ v3.1 Bayesian |
| **R2: ToM 难以实现** | 高 | 高 | 3 模块独立 + 协调机制 |
| **R3: active inference 复杂度高** | 高 | 中 | v3.0 简化 + v3.1 完整 POMDP |
| **R4: LLM-as-PFC 3 层 latency** | 中 | 中 | POST_TICK 每 tick + 其他 trigger 严格控制 |
| **R5: 复杂算法 GPU 资源** | 中 | 中 | 优先 CPU + 必要时 GPU |
| **R6: Rochat level 推进逻辑与 paper 不一致** | 中 | 中 | 严格按论文 + 多场景验证 |
| **R7: 完整 5 层 generative model 训练不稳定** | 高 | 中 | v3.0 单层 + v3.1 完整 5 层 |
| **R8: reflection 频率过高** | 中 | 中 | POST_TICK + 其他 trigger 严格控制 |
| **R9: Markov blanket 数学不变量** | 中 | 中 | v3.0 简化 + v3.1 完整 Bayesian |
| **R10: 自治性过强失控** | 极高 | 中 | 严格 governance_owner + 4 个 gate + 审计 |

---

## 8. 治理铁律（核心）

1. **测试 100% passed 是硬约束**（任何 PR 必须满足）
2. **evaluation 必须真实 LLM probe**，不接受 mock
3. **observability 必须记录全部 tick 行为**，可回放
4. **governance 必须严格**：content / parameter / strategy / code 4 个 gate
5. **可回滚**：每个 commit 必须可回滚
6. **可审计**：每 tick 全行为可审计
7. **可证伪**：每个评估指标必须可证伪（不是 vibe check）
8. **小黑拍板**：每个 Phase 完成后小黑 review + 拍板才进下个 Phase

---

## 9. 跨 owner 协同（与 v2 P5 一致）

- v3 evolution_owner 接入 v2 P5 17 owner × 54 policy 学习框架
- v3 governance_owner 接入 v2 governance 红线
- v3 reflection_owner 接入 v2 learning/ 反思机制
- v3 self_model_owner 接入 v2 identity_governance / 8 维 PTS

---

## 10. 完成定义（Definition of Done）

### 10.1 M6 完成定义（v3.0）

- [ ] 25 stage runtime 完整
- [ ] 5 层 Markov blanket conditional separation 维持
- [ ] 5 层 hierarchical generative model + variational free energy minimization
- [ ] 8 维 PTS graded × Rochat 5 levels
- [ ] LLM-as-PFC 3 层完整接通
- [ ] reflection_owner 完整（4 trigger）
- [ ] evolution_owner + governance_owner 完整（4 个 gate）
- [ ] 测试 ≥ 1255 passed
- [ ] 真实 LLM probe 通过率 ≥ 80%
- [ ] 评估层 v3.0 可用
- [ ] 小黑 review + 拍板

### 10.2 M8 完成定义（v3.1）

- [ ] 8 sub-owner 完整
- [ ] 复杂算法按最高规格（VAE / Transformer / POMDP / Bayesian / Policy Gradient）
- [ ] 测试 ≥ 1400 passed
- [ ] 真实 LLM probe 通过率 ≥ 85%
- [ ] 小黑人脑对比：8 维 PTS 评分 ≥ 0.85（**总目标**）
- [ ] 小黑 review + 拍板

---

**v3 task 完成时间**：2026-06-22 19:30+
**下一步**：Phase 4 架构流程图绘制
**小黑拍板**：等待 v3 完整规划 ship 后 review