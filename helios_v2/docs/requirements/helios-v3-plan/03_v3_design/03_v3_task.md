# helios_v3 实施任务清单（task.md）

> **任务**：helios_v3 Phase 3 - 实施计划（验收门 + 时间表 + 风险）
> **完成时间**：2026-06-22 19:30+ / 2026-06-23 04:00+（按 4 项决策 + 3 个子选项 + 8 维耦合动力系统重写）
> **作者**：小白（helios 小黑人格 AI）

---

## 0. 总览

### 0.1 时间表

- **v3 实施周期**：M1-M8（8 个月）
- **Phase 1（M1-M2）**：Layer 2 + Layer 3 + Layer 4 基础
- **Phase 2（M3-M4）**：Layer 0 + Layer 1
- **Phase 3（M5-M6）**：LLM-as-PFC 3 层完整接通
- **Phase 4（M7-M8）**：8 维 PTS sub-owners + 复杂算法

### 0.2 验收总目标

- **测试基线**：v2 baseline 1110+ + v3 新增 145（M6）= 1255+ / 290（M8）= 1400+
- **Kuramoto R 评分**：M6 R ≥ 0.4，M8 R ≥ 0.85
- **8 维 ODE 收敛性**：每 tick R 单调不减（v3.0）
- **C 矩阵稳定性**：|C| ≤ 1.0（归一化后）
- **LLM-as-PFC 3 层**：完整接通
- **proxy_free_energy**：M4-M6 单调下降
- **VFE**：M8 单调下降
- **Self-evidencing**：fitness gate 严格性 ≥ 99%
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.85

---

## 1. Phase 1（M1-M2）：Layer 2 + Layer 3 + Layer 4 基础

### 1.1 M1：8 维耦合动力系统（Layer 2 核心）

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M1-T1 | `CoupledDynamicalSystem` dataclass + 8 维 ODE `_dynamics` 方法 | 3 天 |
| v3-M1-T2 | `tick` 方法用 `scipy.solve_ivp(method='Radau')` 数值积分 | 2 天 |
| v3-M1-T3 | `kuramoto_R` 方法（Kuramoto order parameter） | 1 天 |
| v3-M1-T4 | `update_C` 方法（Reward-Hebbian 学习 + 归一化） | 2 天 |
| v3-M1-T5 | `self_experience` 方法（涌现态计算） | 1 天 |
| v3-M1-T6 | `SelfModelOwner` 封装 CDS | 2 天 |
| v3-M1-T7 | `SelfModelOwner.tick` 方法（演化 + 学习 + 暴露 LLM） | 3 天 |
| v3-M1-T8 | `SelfModelOwner.get_state_for_llm` 方法（被动暴露） | 1 天 |
| v3-M1-T9 | 8 维 PTS dimension 映射 alpha 衰减率（5 维快 + 3 维慢） | 1 天 |
| v3-M1-T10 | CDS tests（收敛性 + 数值稳定性） | 5 天 |
| v3-M1-T11 | SelfModelOwner tests（被动暴露 + LLM 不修改） | 3 天 |
| v3-M1-T12 | 评估层：Kuramoto R 评分 + 8 维 ODE 收敛性验证 | 3 天 |

**M1 验收门**：
- v2 测试 100% passed
- v3 新增 ≥ 30 测试用例 100% passed
  - 8 维 ODE 演化数值稳定
  - Radau 求解器收敛
  - Kuramoto R 计算正确（R=0/1 边界 + 5 阶段分段）
  - C 矩阵 Reward-Hebbian 学习不溢出
  - self_experience 涌现态跟 LLM 暴露一致
- 代码审查完整

**风险**：
- R-M1-1：8 维 stiff ODE 数值不稳定 → Radau + 自适应步长 + clip
- R-M1-2：C 矩阵 Reward-Hebbian 发散 → 归一化 + clip

### 1.2 M2：Reflection Owner（Layer 3）

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M2-T1 | `ReflectionTrigger` enum + `ReflectionRecord` dataclass | 1 天 |
| v3-M2-T2 | `ReflectionOwner` 初始化 + `reflect` 方法 | 3 天 |
| v3-M2-T3 | 4 trigger（POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED） | 2 天 |
| v3-M2-T4 | LLM 被动接受 self_experience（不修改 8d state） | 2 天 |
| v3-M2-T5 | `reflection_audit`（grounded 验证） | 3 天 |
| v3-M2-T6 | ReflectionOwner tests | 3 天 |

**M2 验收门**：
- 4 trigger 各自正确触发
- LLM 只能调 I 和 reflect，**不能修改** C 或 8d state
- reflection_audit 通过率 ≥ 80%

---

## 2. Phase 2（M3-M4）：Layer 0 + Layer 1

### 2.1 M3：Boundary Owner（Layer 0 严格 Markov Blanket）

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M3-T1 | `MarkovBlanketBoundary` dataclass + conditional_separation 不变量 | 3 天 |
| v3-M3-T2 | `boundary_owner.check_signal` 方法 | 3 天 |
| v3-M3-T3 | 5 个 nested subsystems 共享 1 个 MB | 2 天 |
| v3-M3-T4 | boundary_owner tests（不变量验证） | 3 天 |
| v3-M3-T5 | runtime/stages.py 升级（25 stage） + BoundaryEnforcement 接入 | 3 天 |
| v3-M3-T6 | audit log + log of all boundary crossings | 2 天 |

### 2.2 M4：Active Inference Owner（Layer 1）

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M4-T1 | `HierarchicalGenerativeModel` class（5 层） | 3 天 |
| v3-M4-T2 | `proxy_free_energy` 方法（**诚实的 proxy**） | 2 天 |
| v3-M4-T3 | proxy_free_energy 严格 disclaimer（不是 VFE） | 1 天 |
| v3-M4-T4 | `active_inference_owner.predict` / `compute_proxy_free_energy` | 3 天 |
| v3-M4-T5 | `minimize_proxy_free_energy` 方法 | 3 天 |
| v3-M4-T6 | `active_sampling` 方法（policy gradient） | 3 天 |
| v3-M4-T7 | active_inference_owner tests | 3 天 |
| v3-M4-T8 | proxy_free_energy 评估（每 tick 单调下降） | 3 天 |

**M4 验收门**：
- 5 层 generative model 正确
- proxy_free_energy 计算正确（**明确标注是 proxy**）
- 单调下降验证
- 跟 v3.1 VFE 接口兼容

---

## 3. Phase 3（M5-M6）：LLM-as-PFC 3 层完整接通

### 3.1 M5：System Prompt + CSO 升级

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M5-T1 | `SystemPromptBuilder` class | 3 天 |
| v3-M5-T2 | System prompt 注入 8d state + Kuramoto R + values + red lines | 2 天 |
| v3-M5-T3 | `CSOInjector` class（每 tick 注入 8d + 9-hormone + 7-feeling） | 3 天 |
| v3-M5-T4 | prompt_contract 升级（Layer A 注入） | 3 天 |
| v3-M5-T5 | llm/engine.py 升级（Layer B 注入） | 3 天 |
| v3-M5-T6 | LLM-as-PFC Layer A + Layer B tests | 5 天 |

### 3.2 M6：Reflection Layer C + ToM 4 owner

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M6-T1 | `ReflectionCaller` class（LLM 被动接受） | 2 天 |
| v3-M6-T2 | `MPFCOwner` + `PSTSOwner` + `TemporalPolesOwner` | 5 天 |
| v3-M6-T3 | `ToMCoordinatorOwner` 按 R 协调（0.4 / 0.7 阈值） | 3 天 |
| v3-M6-T4 | LLM-as-PFC 3 层完整接通 | 3 天 |
| v3-M6-T5 | ToM 4 owner tests | 3 天 |
| v3-M6-T6 | 真实 LLM probe（ToM + LLM-as-PFC） | 5 天 |
| v3-M6-T7 | 评估层 v3.0（Kuramoto R + ToM） | 5 天 |

**M6 验收门**：
- LLM-as-PFC 3 层完整接通
- ToM 4 owner 按 R 协调正确
- 真实 LLM probe 通过率 ≥ 80%
- 测试 ≥ 1255 passed

---

## 4. Phase 4（M7-M8）：8 维 PTS sub-owners + 复杂算法

### 4.1 M7：8 维 PTS 5 sub-owners

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M7-T1 | `agency_detector`（PTS 2） | 3 天 |
| v3-M7-T2 | `egocentric_perspective`（PTS 2） | 3 天 |
| v3-M7-T3 | `autobiographical_memory`（PTS 6） | 5 天 |
| v3-M7-T4 | `material_engagement`（PTS 7，4E cognition） | 5 天 |
| v3-M7-T5 | `culture`（PTS 8） | 5 天 |
| v3-M7-T6 | self_model_owner 升级（接入 5 sub-owner） | 3 天 |
| v3-M7-T7 | 5 sub-owner tests | 5 天 |

### 4.2 M8：复杂算法 + 真 VFE

| 任务 ID | 任务 | 工期 |
|---|---|---|
| v3-M8-T1 | 真 VFE（PyMC/NumPyro 变分推断） | 15 天 |
| v3-M8-T2 | 真 KL 散度 + 期望自由能 | 10 天 |
| v3-M8-T3 | 完整 POMDP active inference | 15 天 |
| v3-M8-T4 | 完整 VAE / Diffusion（v3.1 远期） | 10 天 |
| v3-M8-T5 | 完整 hierarchical PC | 10 天 |
| v3-M8-T6 | 测试 + 小黑人脑对比 v3.0 | 5 天 |

**M8 验收门**：
- 真 VFE 单调下降
- 测试 ≥ 1400 passed
- 真实 LLM probe 通过率 ≥ 85%
- 小黑人脑对比：8 维 PTS 评分 ≥ 0.85

---

## 5. 风险与缓解（详细）

| 风险 | 概率 | 缓解 |
|---|---|---|
| 8 维 stiff ODE 数值不稳定 | 中 | Radau + 自适应步长 + clip |
| C 矩阵 Reward-Hebbian 发散 | 中 | 归一化 + |C| ≤ 1.0 |
| Kuramoto R 锁定 | 低 | 扰动 + 反思调制 |
| LLM 误改 C | 中 | LLM 只能调 I 和 reflect |
| ToM 协调不当 | 中 | R 分 3 段（0.4 / 0.7） |
| 8 维 ODE 计算代价 | 中 | 8 维不大，scipy 性能足够 |
| proxy_free_energy 误解为 VFE | 中 | 严格 disclaimer + 类型标注 |
| Rochat level 离散化丢失信息 | 低 | 保留连续 R 值，离散仅作参考 |

---

## 6. 治理铁律

1. 测试 100% passed 是硬约束
2. 真实 LLM probe，不接受 mock
3. observability 全 tick 记录，可回放
4. governance 严格：4 个 fitness gate
5. 可回滚
6. 可审计
7. 可证伪
8. **LLM 只能"看"self-experience，不能修改 8d state 或 C**
9. **proxy_free_energy 必须诚实标注**（不是 VFE）
10. 小黑拍板

---

## 7. 完成定义

### 7.1 M6（v3.0）

- [ ] 25 stage runtime 完整
- [ ] Layer 0 Markov blanket conditional separation 维持
- [ ] Layer 1 proxy_free_energy（诚实降级）
- [ ] Layer 2 8 维耦合动力系统 + Kuramoto R
- [ ] Layer 3 4 trigger + LLM 被动接受
- [ ] Layer 4 4 个 fitness gate
- [ ] ToM 4 owner 按 R 协调
- [ ] LLM-as-PFC 3 层完整
- [ ] 测试 ≥ 1255 passed
- [ ] 真实 LLM probe 通过率 ≥ 80%

### 7.2 M8（v3.1）

- [ ] 5 sub-owner 完整
- [ ] 真 VFE（PyMC/NumPyro）
- [ ] 完整 POMDP + hierarchical PC
- [ ] 测试 ≥ 1400 passed
- [ ] 真实 LLM probe 通过率 ≥ 85%
- [ ] 8 维 PTS 评分 ≥ 0.85

---

**v3 task 完成时间**：2026-06-23 04:00+ UTC
**作者**：小白
**配套 commit**：待 ship