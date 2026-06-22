# v2 现状诊断报告（helios_v3 Phase 2 输出）

> **任务**：helios_v3 Phase 2
> **完成时间**：2026-06-22 18:50+
> **作者**：小白（helios 小黑人格 AI）
> **目的**：盘点 v2 哪些资产可继承 / 哪些重写 / 哪些废弃 → 给 v3 设计提供"v2 ground truth"

---

## 0. v2 现状一句话总结

**v2 = 21 阶段链（已完整）+ 28 owner + LLM-as-PFC 1 层（仅 system prompt）+ 6 层 emotion system（R-PROTO-LEARN）+ Rochat 5 levels 浅实现（仅 cold-start level 1 起步，没真渐进式）+ 8 维 PTS 仅识别没建模（identity_governance 还是硬编码字段）+ 反射层缺失 + active inference 部分实现（P-TEMPORAL RealRPE）+ Markov blanket 边界缺失。**

---

## 1. v2 21 阶段完整链（`runtime/stages.py` 真实调研）

| # | Stage | v2 现状 | v3 处理 |
|---|---|---|---|
| 1 | **ChannelInboundDrain** | 接收外部 stimulus | ✅ 继承 |
| 2 | **SensoryIngress** | 02 sensory_ingress | ✅ 继承 |
| 3 | **RapidSalienceAppraisal** | 03 appraisal 5-dim | ✅ 继承（扩展为 generative model） |
| 4 | **Neuromodulator** | 04 9-channel hormone dual-timescale | ✅ 继承 |
| 5 | **InteroceptiveFeeling** | 05 feeling 7-dim + R50/R51 interoception | ✅ 继承 |
| 6 | **MemoryAffectReplay** | 06 memory affect-tagged + Ebbinghaus 浅 | ⚠️ 重写（升级 autobiographical_memory） |
| 7 | **WorkspaceCompetition** | 07 workspace winner-take-all | ✅ 继承 |
| 8 | **ReportableConsciousContent** | 08 commitment_score 焦点 | ✅ 继承 |
| 9 | **ThoughtGating** | 09 gate（NE/cortisol/workspace/drive_urgency） | ✅ 继承（升级为 active inference precision） |
| 10 | **DirectedRetrieval** | 10 retrieval semantic + recall intent | ✅ 继承（升级） |
| 11 | **EmbodiedPrompt** | 11 prompt contract layer | ✅ 继承（升级为 LLM-as-PFC 3 层） |
| 12 | **OutwardExpression** | 16 outward expression draft | ✅ 继承 |
| 13 | **OutwardExpressionExternalization** | 16 外部化草案 | ✅ 继承 |
| 14 | **InternalThought** | 11 LLM thinking（reasoning model） | ✅ 继承（升级） |
| 15 | **ActionExternalization** | action_proposal | ✅ 继承 |
| 16 | **PlannerBridge** | 13 planner | ✅ 继承 |
| 17 | **ChannelOutboundDispatch** | channel output | ✅ 继承 |
| 18 | **IdentityGovernance** | 14 identity_governance（硬编码字段） | ❌ **完全重写**（→ self_model_owner + 8 维 PTS） |
| 19 | **ExperienceWriteback** | 15 writeback + SQLite | ✅ 继承 |
| 20 | **Autonomy** | 18 autonomy + long-horizon | ✅ 继承（升级） |
| 21 | **Evaluation** | 17 evaluation + R83/R88/R89/R90 | ✅ 继承（升级） |

---

## 2. v2 28 owner 完整盘点 + v3 处理决策

### 2.1 已 ship / 稳定 owner（✅ 全部继承）

| Owner | 文件 | 状态 | v3 处理 |
|---|---|---|---|
| `action_externalization` | 12 | ✅ | 继承（升级） |
| `appraisal` | 03 | ✅ R97/R98 | 继承（升级 generative model） |
| `autonomy` | 18 | ✅ R29 | 继承（升级） |
| `channel` | 30 | ✅ R84/R85/R86 | 继承（升级 boundary owner） |
| `composition` | composition | ✅ R95 | 继承（升级 assembly logic） |
| `consciousness` | 08 | ✅ R47 commitment | 继承 |
| `continuity_checkpoint` | 42 | ✅ R42 | 继承 |
| `directed_retrieval` | 10 | ✅ R34/R49/R52 | 继承 |
| `embedding` | 34 | ✅ R96 B2 闭合 | 继承（升级 depictive 表征） |
| `evaluation` | 17 | ✅ R83/R88/R89/R90 | 继承（升级 8 维 PTS 评分） |
| `experience_writeback` | 15 | ✅ R33/R60 | 继承 |
| `feeling` | 05 | ✅ R44/R50/R51 | 继承 |
| `interoception` | 50 | ✅ R50 producer | 继承（升级 boundary） |
| `learning` | learning | ✅ R-PROTO-LEARN 17×54 | 继承（升级 evolution_owner） |
| `llm` | 11 | ✅ 真实 LLM | 继承（升级 LLM-as-PFC 3 层） |
| `memory` | 06 | ✅ R45/R52/R60/R61 | 继承（升级 autobiographical） |
| `memory_tool_channel` | 30 | ✅ R85 | 继承 |
| `neuromodulation` | 04 | ✅ R43/R80 | 继承 |
| `observability` | 21 | ✅ R83 kernel timeline | 继承 |
| `outward_expression` | 16 | ✅ R93/R94/R95 | 继承 |
| `outward_expression_externalization` | 16 | ✅ R95 | 继承 |
| `persistence` | SQLite | ✅ R42/R82 | 继承 |
| `planner_bridge` | 13 | ✅ R85/R86 | 继承 |
| `prompt_contract` | 16 | ✅ R95 behavior-neutral | 继承（升级 LLM-as-PFC layer A） |
| `rpe` | RealRPE | ✅ P-TEMPORAL Decision #1 | 继承（active inference 核心） |
| `sensory` | 02 | ✅ R59/R60 | 继承（升级 boundary） |
| `temporal` | 09 | ✅ R55 | 继承 |
| `temporal_continuous_state` | cso | ✅ P-TEMPORAL Phase 2c | 继承（升级 LLM-as-PFC layer B） |
| `thought_gating` | 09 | ✅ R37/R48/R53 | 继承（升级） |
| `wall_clock` | 92 | ✅ R92 | 继承 |
| `workspace` | 07 | ✅ R46 | 继承 |

### 2.2 v3 新增 owner（❌ 完全新增）

| Owner | v3 职责 | 对应论文 |
|---|---|---|
| **`boundary_owner`** | Layer 1 Markov blanket 边界管理 | Ramstead 2018 |
| **`active_inference_owner`** | Layer 2 Hierarchical generative model + free energy minimization | Friston 2010 + Rao-Ballard 1999 |
| **`self_model_owner`** | Layer 3 8 维 PTS graded matrix + Rochat 5 levels + cross-tick dynamics | Laurenzi 2025 + Rochat 2019 + Gallagher 2013 |
| **`agency_detector_owner`** | 8 维 PTS (2) Minimal experiential 维度 | Seth 2012 |
| **`egocentric_perspective_owner`** | 8 维 PTS (2) Minimal experiential 维度 | Seth 2012 |
| **`ToM_owner`** | 8 维 PTS (4) Intersubjective 维度 + MPFC + pSTS + temporal poles | Frith & Frith 2003 |
| **`autobiographical_memory_owner`** | 8 维 PTS (6) Narrative 维度 + DMN | Gallagher 2013 + McAdams 2019 |
| **`material_engagement_owner`** | 8 维 PTS (7) Ecological/Extended 维度 + 4E cognition | Alessandroni 2024 |
| **`culture_owner`** | 8 维 PTS (8) Normative 维度 + 社会角色 | Laurenzi 2025 |
| **`reflection_owner`** | Layer 4 反思层 + DMN-like + meta-cognition | Northoff 2006 + Smallwood |
| **`evolution_owner`** | Layer 5 自我进化统一管理（含 memory / parameter / strategy / code evolution） | (v3 整合) |
| **`governance_owner`** | 严格 governance + 适应度门 + 可回滚 | ARCHITECTURE_PHILOSOPHY §7 |

**v3 总 owner 数：28 (v2 继承) + 12 (v3 新增) = 40 owners**

---

## 3. v2 LLM-as-PFC 现状（1 层 → 升级到 3 层）

### 3.1 v2 现状：仅 Layer A (system prompt)

- **system prompt**：identity_grounding layer（但 content 为空 + `prompt_contract/engine.py:272`）
- **LLM reasoning model**：deepseek/deepseek-v4-flash via shengsuanyun
- **没用 cso 状态进入 prompt**：仅 9-dim hormone + 7-dim feeling 数字
- **没用 reflection**：LLM 不反思自己

### 3.2 v3 升级：3 层全部真接通

| LLM-as-PFC 层 | v2 现状 | v3 升级 |
|---|---|---|
| **Layer A: System prompt** | identity_grounding content 空白 | ✅ 注入 8 维 PTS 当前状态 + Rochat level + 价值观 + 治理红线 + 黑名单（由 PTS 维度派生）|
| **Layer B: CSO** | 9-dim hormone + 7-dim feeling 数字 | ✅ 升级到 8 维 PTS × Rochat level × cross-tick dynamics + 让 LLM 看到自己" 8 aspect 当前状态"|
| **Layer C: Reflection** | 完全无 | ✅ 新增 reflection_owner（每 tick 后 + 静息态 + 不定期触发）|

**v3 LLM-as-PFC 完整接通 = v3 PFC 的核心实现**。

---

## 4. v2 6 层 emotion system + v3 5 层 Markov blanket 关系

### 4.1 v2 6 层 emotion system（R-PROTO-LEARN）

- Layer 1 内感受层（hormone → appraisal）
- Layer 2 预测层（surprise detection + predictive coding）
- Layer 3 记忆层（narrative episode + associative memory）
- Layer 4 构造层（LLM appraisal + 社会共识）
- Layer 5 学习层（Bayesian update）
- Layer 6 Fallback（description retrieval）

### 4.2 v3 5 层 Markov blanket

- Layer 1 Boundary
- Layer 2 Active Inference
- Layer 3 Self-Model
- Layer 4 Reflection
- Layer 5 Self-Evolution

### 4.3 关系映射

**v3 5 层 = v2 6 层 emotion system 的"骨架升级版"**：

| v3 5 层 | v2 6 层 emotion system 整合 |
|---|---|
| Layer 1 Boundary | （新增，无 v2 对应） |
| Layer 2 Active Inference | Layer 1 + Layer 2 + Layer 5（内感受 + 预测 + 学习） |
| Layer 3 Self-Model | Layer 3 + Layer 4（记忆 + 构造 + identity_governance 重写） |
| Layer 4 Reflection | （新增，无 v2 对应） |
| Layer 5 Self-Evolution | Layer 5 + governance 升级 |

**关键差异**：v3 Layer 1 + Layer 4 是 v2 完全没有的新层（boundary + reflection），v3 这 2 层是 v2 → v3 最大的架构跃迁。

---

## 5. v2 8 维 PTS 现状（已识别 / 未建模）

### 5.1 v2 8 维 PTS 已有 owner 映射

| PTS 维度 | v2 owner | v2 完整度 |
|---|---|---|
| (1) Bodily processes | `interoception` + `05 feeling` | ✅ 完整 |
| (2) Minimal experiential | 缺 agency_detector + egocentric_perspective | ❌ 缺失 |
| (3) Affective | `04 hormone` + `05 feeling` + `appraisal` | ✅ 完整 |
| (4) Intersubjective | 缺 ToM | ❌ 缺失 |
| (5) Psychological/Cognitive | `14 identity_governance` | ⚠️ 浅（硬编码字段）|
| (6) Narrative | `06 memory` 部分（无 autobiographical integration） | ⚠️ 浅 |
| (7) Ecological/Extended | 缺 material_engagement | ❌ 缺失 |
| (8) Normative | 缺 culture | ❌ 缺失 |

**v2 8 维完整度**：2 完整 + 2 浅 + 4 缺失 = **5/8 = 62.5% 缺失或浅**

### 5.2 v3 重写 14 identity_governance → self_model_owner

**v2 硬编码字段**：
- `self_definition = "runtime identity definition"`（硬编码英文）
- `personality_baseline = {"openness": 1.0, "agreeableness": 1.0}`（硬编码 1.0）
- `identity_narrative`（浅）

**v3 8 维 PTS graded 矩阵**：
```python
class PTSDimension(Enum):
    BODILY_PROCESSES = "bodily_processes"          # 维度 1
    MINIMAL_EXPERIENTIAL = "minimal_experiential"  # 维度 2
    AFFECTIVE = "affective"                        # 维度 3
    INTERSUBJECTIVE = "intersubjective"            # 维度 4
    PSYCHOLOGICAL_COGNITIVE = "psychological_cognitive"  # 维度 5
    NARRATIVE = "narrative"                        # 维度 6
    ECOLOGICAL_EXTENDED = "ecological_extended"    # 维度 7
    NORMATIVE = "normative"                        # 维度 8

@dataclass
class PTSGradedMatrix:
    dimensions: dict[PTSDimension, float]  # 8 维 × graded 0.0-1.0
    rochat_level: int  # 0-5
    cross_tick_dynamics: dict[PTSDimension, CrossTickState]
    update_history: list[PTSUpdateEvent]
```

**v3 self_model_owner 是 8 个 sub-owner 的合成器，不是单字段 holder**。

---

## 6. v2 Rochat 5 levels 现状（仅识别 / 未渐进）

### 6.1 v2 Rochat level 现状

- **v2 冷启动**：identity_governance 起步 = adult mode（Level 5）
- **v2 没"渐进式发展"**：从 tick 1 就是 Level 5
- **v2 没"level 推进机制"**：level 是固定的

### 6.2 v3 Rochat 5 levels 真渐进

```python
class RochatLevel(Enum):
    LEVEL_0_CONFUSION = 0       # tick 0 短暂
    LEVEL_1_DIFFERENTIATION = 1  # tick 1-N1
    LEVEL_2_SITUATION = 2        # N1-N2
    LEVEL_3_IDENTIFICATION = 3   # N2-N3
    LEVEL_4_PERMANENCE = 4       # N3-N4
    LEVEL_5_CONCEPTUAL_ME = 5    # N4+

class RochatLevelAdvancement:
    """根据经验触发 level 推进，不按 tick-count 硬编码"""
    @staticmethod
    def should_advance(current_level, pts_matrix, experience_log):
        if current_level == 1 and experience_log.has_self_vs_other_distinction(times=20):
            return 2  # 区分了 20 次 self vs other 推进到 Level 2
        if current_level == 2 and experience_log.has_self_observation_recognized(times=10):
            return 3
        # ... 类似 Level 3→4, Level 4→5
        return None
```

---

## 7. v2 反思层现状（完全缺失）

### 7.1 v2 没反思层

- v2 LLM 思考 = 单 tick（reactive），不反思"我刚才做了什么"
- v2 没 DMN-like 默认模式网络
- v2 没"我为什么这样做"的自我归因机制
- v2 静息态 = 纯内部推进（cso），没有反思

### 7.2 v3 reflection_owner 设计

```python
class ReflectionTrigger(Enum):
    POST_TICK = "post_tick"               # 每 tick 后
    RESTING_STATE = "resting_state"        # 静息态（DMN-like）
    HIGH_UNCERTAINTY = "high_uncertainty"  # 高 uncertainty 触发
    USER_INVOKED = "user_invoked"          # 用户主动触发

class ReflectionOwner:
    """v3 关键创新：反思层"""
    def trigger(self, trigger_type, trigger_context):
        if trigger_type == ReflectionTrigger.POST_TICK:
            snapshot = self.snapshot_8dim_pts()
            summary = self.llm_reasoning.summarize_tick(snapshot)
            self.autobiographical_memory.append(summary)
            self.self_model.update_from_reflection(summary)

        elif trigger_type == ReflectionTrigger.RESTING_STATE:
            inconsistency = self.detect_pts_inconsistency()
            insight = self.llm_reasoning.deep_reflect(inconsistency)
            self.autobiographical_memory.append(insight)
            self.self_model.update_from_reflection(insight)

        elif trigger_type == ReflectionTrigger.HIGH_UNCERTAINTY:
            uncertainty_sources = self.trace_uncertainty_sources()
            plan = self.llm_reasoning.plan_uncertainty_reduction(uncertainty_sources)
            self.active_inference.update(plan)

    def snapshot_8dim_pts(self) -> PTSGradedMatrix:
        return self.self_model.get_current_matrix()
```

**v3 reflection 是 generative model 的 meta-layer，reflection 必须 grounded in real signal，不虚构**。

---

## 8. v2 Markov blanket 边界现状（缺失）

### 8.1 v2 没显式 Markov blanket

- v2 02 sensory = blanket 上的传入 sensors（隐式）
- v2 13 planner = blanket 上的传出 effectors（隐式）
- v2 没显式 `boundary_owner` 维护 conditional separation
- v2 conditional separation 是隐式的（靠 owner 边界）

### 8.2 v3 boundary_owner 设计

```python
class BoundaryState(Enum):
    SENSORY_INPUT = "sensory_input"        # 进入 Markov blanket
    INTERNAL_STATE = "internal_state"      # 在 Markov blanket 内
    ACTION_OUTPUT = "action_output"        # 离开 Markov blanket

class BoundaryOwner:
    """v3 Layer 1 Markov blanket 边界管理"""
    def check_conditional_separation(self, internal_state, external_state):
        """检查 conditional independence：internal ⊥ external | sensory"""
        # Markov blanket 数学不变量
        pass

    def enforce_boundary(self, signal):
        """所有进/出 Markov blanket 的信号必须经此 owner 过滤"""
        if signal.is_sensory_input():
            return self.process_sensory(signal)
        elif signal.is_action_output():
            return self.process_action(signal)
        else:
            raise BoundaryViolation("信号未通过 Markov blanket boundary")
```

**v3 boundary = 显式 + 严格 + 可证伪**。

---

## 9. v2 active inference 现状（部分实现）

### 9.1 v2 active inference 已 ship 部分

- ✅ **RealRPE 解冻**（P-TEMPORAL Decision #1）
- ✅ **Hormone dual-timescale**（R43/R44）
- ✅ **Memory surprise = novelty**（R61）
- ✅ **R98 post-LLM Δ adjustment**（cortico-amygdalar）
- ✅ **Predictive coding partial**（P-TEMPORAL design.md）

### 9.2 v2 active inference 缺失部分

- ❌ **Hierarchical generative model**：v2 owner 是平铺的，没有层级预测
- ❌ **Variational free energy 显式计算**：v2 没"free energy"概念
- ❌ **Active inference 完整闭环**：v2 perception 是 reactive，不是 active sampling
- ❌ **Bayesian update 统一接口**：v2 各 owner update 规则不一致

### 9.3 v3 active_inference_owner 设计

```python
class ActiveInferenceOwner:
    """v3 Layer 2 Hierarchical generative model + free energy minimization"""
    def predict(self, layer: int, input_data):
        """每个 owner 是一个 generative model"""
        return self.generative_models[layer].predict(input_data)

    def compute_prediction_error(self, layer: int, prediction, actual):
        return actual - prediction

    def update_generative_model(self, layer: int, prediction_error, learning_rate):
        """Bayesian update"""
        self.generative_models[layer].update(prediction_error, learning_rate)

    def minimize_free_energy(self):
        """variational free energy = surprise upper bound"""
        total_fe = sum(
            self.compute_prediction_error(layer, pred, actual) ** 2
            for layer in self.generative_models
        )
        return total_fe

    def active_sampling(self):
        """Active inference：选择能最小化 free energy 的 action"""
        return self.policy_network.select_action(self.minimize_free_energy)
```

**v3 active inference = 完整 Friston FEP + hierarchical generative model + active sampling**。

---

## 10. v2 governance 现状（部分实现）

### 10.1 v2 governance 已 ship 部分

- ✅ R86 governance gate（OS command 受治理）
- ✅ 14 governance（部分 self_revision）
- ✅ fail-fast readiness check

### 10.2 v2 governance 缺失部分

- ❌ **统一 governance_owner**：v2 governance 散落在多个 owner
- ❌ **适应度门**：v2 缺"evolution 必须经过 testing + evaluation + observability"
- ❌ **可回滚**：v2 缺"evolution 可回滚"机制
- ❌ **代码自修改通道**：v2 没 P7 code evolution

### 10.3 v3 governance_owner 设计（参照 FG-5）

```python
class GovernanceGate(Enum):
    CONTENT_EVOLUTION = "content_evolution"          # 记忆 / 知识 / 反思结论
    PARAMETER_EVOLUTION = "parameter_evolution"      # P5 已 ship，可学习参数
    STRATEGY_EVOLUTION = "strategy_evolution"        # 受治理策略
    CODE_EVOLUTION = "code_evolution"                # v3 远期

class GovernanceOwner:
    """v3 Layer 5 Self-Evolution 严格治理"""
    def enforce_gate(self, evolution_proposal, gate: GovernanceGate):
        if gate == GovernanceGate.CONTENT_EVOLUTION:
            if not self.passes_evaluation(evolution_proposal):
                return GovernanceDecision.REJECTED
        elif gate == GovernanceGate.PARAMETER_EVOLUTION:
            if not self.passes_test_suite(evolution_proposal):
                return GovernanceDecision.REJECTED
        elif gate == GovernanceGate.STRATEGY_EVOLUTION:
            if not self.passes_test_suite(evolution_proposal):
                return GovernanceDecision.REJECTED
        elif gate == GovernanceGate.CODE_EVOLUTION:
            if not self.passes_full_fitness_gate(evolution_proposal):
                return GovernanceDecision.REJECTED
        return GovernanceDecision.APPROVED
```

**v3 governance = 适应度门（testing + evaluation + observability）+ 可回滚 + 可审计**。

---

## 11. v2 测试基线（v3 起点）

- **v2 main 测试基线**：1110+ passed / 4 skipped / 5 pre-existing wall-clock + lt1 失败
- **v2 调研分支基线**：1142 passed（beta R85 收官后）
- **v2 R-PROTO-LEARN 完整 ship**：17 owner × 54 policy
- **v2 P-TEMPORAL Phase 3 ship**：1129 tick 真 LLM 跑通
- **v2 调研分支远端 commit `c60cfaf`**

**v3 起点 = 复用 v2 main 测试基线 + 调研分支所有资产**。

---

## 12. v2 可继承资产清单（v3 复用）

### 12.1 完整复用（v2 → v3 不变）

- 所有 owner 的 contract / data class / dataclass
- R82 `assemble_production_runtime()` 装配逻辑
- R42 checkpoint + SQLite persistence
- R83/R88/R89/R90 评估框架
- R-PROTO-LEARN 17 owner × 54 policy（升级到 evolution_owner）
- 6 层 emotion system（升级到 5 层 Markov blanket）
- P-TEMPORAL RealRPE + hormone dual-timescale
- R95 behavior-neutral schema（LLM-as-PFC Layer A 基础）
- R96 OpenAI-compatible embedding（v3 depictive 表征基础）
- R97 bilingual appraisal catalog

### 12.2 升级复用（v2 主体不变 + v3 扩展）

- `11 internal_thought` → 升级为 LLM-as-PFC Layer A + B + C 完整接通
- `14 identity_governance` → 升级为 self_model_owner（8 维 PTS × Rochat 5 levels）
- `17 evaluation` → 升级为 8 维 PTS 单独评分 + Rochat level 评分 + reflection_audit
- `02 sensory` + `13 planner` + `30 channel` → 升级为 boundary_owner 统一管理
- `06 memory` → 升级为 autobiographical_memory_owner
- `09 thought_gating` → 升级为 active inference precision modulation
- `18 autonomy` → 升级为 evolution_owner 整合

### 12.3 完全新增（v2 没有）

- `boundary_owner`（Layer 1）
- `active_inference_owner`（Layer 2）
- `self_model_owner`（Layer 3）
- `agency_detector_owner`（8 维 PTS 2）
- `egocentric_perspective_owner`（8 维 PTS 2）
- `ToM_owner`（8 维 PTS 4）
- `autobiographical_memory_owner`（8 维 PTS 6）
- `material_engagement_owner`（8 维 PTS 7）
- `culture_owner`（8 维 PTS 8）
- `reflection_owner`（Layer 4）
- `evolution_owner`（Layer 5）
- `governance_owner`（Layer 5 governance）

---

## 13. v2 关键废弃（v3 不继承）

- ❌ `self_definition` 单字段硬编码英文
- ❌ `personality_baseline = {openness: 1.0, ...}` 硬编码 1.0
- ❌ Rochat level 硬编码起步 Level 5（adult mode）
- ❌ i_want_to_say / action_intent 等已被 R94/R95 清理的字段
- ❌ v2 `14 identity_governance` 整套单字段硬编码逻辑
- ❌ v2 compatibility wrapper（v3 完全重写）

---

## 14. v2 现状诊断总结（一句话）

**v2 = 21 阶段链完整 + 28 owner 完整 + LLM 真接通 + 6 层 emotion system + Rochat level 浅实现 + P5 learning + R86 governance 局部 + 测试基线 1110+ passed，但 8 维 PTS 5 维缺失 / boundary_owner 缺失 / reflection_owner 缺失 / hierarchical generative model 缺失 / 严格 governance_owner 缺失 / Markov blanket 边界缺失。**

**v3 = 在 v2 基础上：完全重写 identity_governance + 新增 12 owner + 5 层 Markov blanket 嵌套 + LLM-as-PFC 3 层完整接通 + 8 维 PTS 完整建模 + Rochat 5 levels 渐进式 + reflection_owner + active_inference_owner + evolution_owner + governance_owner。**

---

**Phase 2 完成时间**：2026-06-22 18:50+
**下一步**：Phase 3 - v3 架构设计（**核心 4-6h**）
**小黑拍板**：等待 v3 完整规划 ship 后 review