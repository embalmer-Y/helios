# helios_v3 架构详细设计（design.md）

> **任务**：helios_v3 Phase 3 - 详细设计（HOW）
> **完成时间**：2026-06-22 19:20+
> **作者**：小白（helios 小黑人格 AI）
> **配套**：`01_v3_requirement.md`（WHAT + WHY）
> **目的**：v3 详细实现路径（每个 owner 的接口、数据结构、算法、测试）

---

## 0. 一句话设计原则

**v3 设计 = 严格遵循 ARCHITECTURE_PHILOSOPHY §7 强约束 + 5 层 Markov blanket 嵌套 + 8 维 PTS graded × Rochat 5 levels + LLM-as-PFC 3 层 + 40 owner（28 继承 + 12 新增）+ 复杂算法按最高规格 + 可证伪 + 可审计 + 可回滚。**

---

## 1. v3 仓库与目录结构（建议）

```
helios_v3/
├── README.md
├── docs/
│   ├── ARCHITECTURE_PHILOSOPHY.md         # 继承 v2 + v3 升级
│   ├── ARCHITECTURE_BOUNDARIES.md         # 继承 v2 + v3 升级
│   ├── OWNER_GUIDE.md                     # v3 40 owner 清单
│   ├── BRAIN_ARCHITECTURE_COMPARISON.md   # 继承 v2 + v3 升级
│   ├── PROGRESS_FLOW.md
│   ├── ROADMAP.md
│   └── requirements/
│       ├── v3-core-markov-blanket/
│       │   ├── requirement.md
│       │   ├── design.md
│       │   └── task.md
│       ├── v3-self-model-pts-rochat/
│       ├── v3-reflection-owner/
│       ├── v3-active-inference-owner/
│       ├── v3-evolution-governance/
│       ├── v3-llm-as-pfc-3-layer/
│       └── ...
├── src/
│   └── helios_v3/
│       ├── __init__.py
│       ├── boundary/                       # Layer 1
│       │   ├── owner.py                    # boundary_owner
│       │   └── contracts.py
│       ├── active_inference/               # Layer 2
│       │   ├── owner.py                    # active_inference_owner
│       │   ├── contracts.py
│       │   ├── hierarchical_generative_model.py
│       │   └── variational_free_energy.py
│       ├── self_model/                     # Layer 3
│       │   ├── owner.py                    # self_model_owner
│       │   ├── contracts.py
│       │   ├── pts_matrix.py               # 8 维 PTS graded matrix
│       │   ├── rochat_level.py             # 5 levels 渐进式
│       │   ├── agency_detector/            # PTS 2 sub-owner
│       │   ├── egocentric_perspective/     # PTS 2 sub-owner
│       │   ├── tom/                        # PTS 4 ToM owner
│       │   ├── autobiographical_memory/    # PTS 6 sub-owner
│       │   ├── material_engagement/        # PTS 7 sub-owner
│       │   └── culture/                    # PTS 8 sub-owner
│       ├── reflection/                     # Layer 4
│       │   ├── owner.py                    # reflection_owner
│       │   ├── contracts.py
│       │   ├── triggers.py                 # 4 trigger 类型
│       │   └── dmn_like.py                 # DMN-like 默认模式
│       ├── evolution/                      # Layer 5
│       │   ├── owner.py                    # evolution_owner
│       │   ├── governance_owner.py
│       │   ├── fitness_gate.py             # testing + evaluation + observability
│       │   └── rollback.py                 # 可回滚
│       ├── sensory/                        # 02 升级
│       ├── appraisal/                      # 03 升级
│       ├── neuromodulation/                # 04 升级
│       ├── feeling/                        # 05 升级
│       ├── memory/                         # 06 升级
│       ├── workspace/                      # 07 升级
│       ├── consciousness/                  # 08 升级
│       ├── thought_gating/                 # 09 升级
│       ├── directed_retrieval/             # 10 升级
│       ├── internal_thought/               # 11 升级（LLM-as-PFC Layer A）
│       ├── temporal_continuous_state/      # cso 升级（LLM-as-PFC Layer B）
│       ├── prompt_contract/                # 升级（LLM-as-PFC Layer A）
│       ├── reflection/                     # 11 + Layer 4
│       ├── action_externalization/         # 12
│       ├── planner_bridge/                 # 13 升级
│       ├── identity_governance/            # 14 → self_model_owner 迁移
│       ├── experience_writeback/           # 15
│       ├── outward_expression/             # 16
│       ├── evaluation/                     # 17 升级（8 维 PTS 评分）
│       ├── autonomy/                       # 18 升级
│       ├── interoception/                  # 50
│       ├── channel/                        # 30 升级
│       ├── persistence/                    # SQLite
│       ├── embedding/                      # 升级 depictive 表征
│       ├── learning/                       # 升级 evolution_owner
│       ├── llm/                            # 升级 LLM-as-PFC
│       ├── wall_clock/                     # 92
│       ├── observability/                  # 21
│       ├── runtime/                        # 21 stage → 25 stage（v3 新增 4 stage）
│       ├── composition/                    # assembly logic
│       └── tests/
├── tests/
│   └── ...
├── pyproject.toml
└── .env.example
```

---

## 2. v3 阶段链设计（25 stage：v2 21 + v3 新增 4）

### 2.1 v2 21 stage（继承 + 升级）

| # | v2 Stage | v3 Stage | v3 升级 |
|---|---|---|---|
| 1 | ChannelInboundDrain | ✅ | 升级 boundary integration |
| 2 | SensoryIngress | ✅ | 升级 boundary integration |
| 3 | RapidSalienceAppraisal | ✅ | 升级 generative model |
| 4 | Neuromodulator | ✅ | 升级 active inference prediction |
| 5 | InteroceptiveFeeling | ✅ | 升级 interoceptive inference |
| 6 | MemoryAffectReplay | ✅ | 升级 autobiographical memory |
| 7 | WorkspaceCompetition | ✅ | 升级 generative model |
| 8 | ReportableConsciousContent | ✅ | 升级 self-model integration |
| 9 | ThoughtGating | ✅ | 升级 active inference precision |
| 10 | DirectedRetrieval | ✅ | 升级 generative model memory |
| 11 | EmbodiedPrompt | ✅ | 升级 LLM-as-PFC Layer A |
| 12 | OutwardExpression | ✅ | 升级 boundary output |
| 13 | OutwardExpressionExternalization | ✅ | 升级 boundary output |
| 14 | InternalThought | ✅ | 升级 LLM-as-PFC 3 layer |
| 15 | ActionExternalization | ✅ | 升级 boundary output |
| 16 | PlannerBridge | ✅ | 升级 generative model policy |
| 17 | ChannelOutboundDispatch | ✅ | 升级 boundary output |
| 18 | IdentityGovernance | ⚠️ 重写 | → SelfModelStage（self_model_owner） |
| 19 | ExperienceWriteback | ✅ | 升级 active inference update |
| 20 | Autonomy | ✅ | 升级 evolution integration |
| 21 | Evaluation | ✅ | 升级 8 维 PTS 评分 |

### 2.2 v3 新增 4 stage

| # | v3 Stage | 职责 |
|---|---|---|
| 22 | **BoundaryEnforcement** | Layer 1 Boundary 强制 conditional separation |
| 23 | **ActiveInferenceStage** | Layer 2 Hierarchical generative model + variational free energy minimization |
| 24 | **ReflectionStage** | Layer 4 Reflection（trigger 驱动）|
| 25 | **EvolutionGovernanceStage** | Layer 5 Evolution governance gate |

---

## 3. v3 核心数据结构设计

### 3.1 PTS Graded Matrix（8 维 PTS × graded）

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class PTSDimension(Enum):
    BODILY_PROCESSES = "bodily_processes"          # 1
    MINIMAL_EXPERIENTIAL = "minimal_experiential"  # 2
    AFFECTIVE = "affective"                        # 3
    INTERSUBJECTIVE = "intersubjective"            # 4
    PSYCHOLOGICAL_COGNITIVE = "psychological_cognitive"  # 5
    NARRATIVE = "narrative"                        # 6
    ECOLOGICAL_EXTENDED = "ecological_extended"    # 7
    NORMATIVE = "normative"                        # 8


@dataclass
class PTSGradedScore:
    """单维度 graded 评分"""
    dimension: PTSDimension
    score: float  # 0.0-1.0 graded
    evidence: list[str]  # 评分依据（可证伪）
    last_updated_tick: int
    cross_tick_dynamics: "CrossTickPTSState"


@dataclass
class CrossTickPTSState:
    """单维度跨 tick dynamics（双时标）"""
    fast_timescale: float  # phasic（快时标）
    slow_timescale: float  # tonic（慢时标）
    baseline: float  # baseline
    carry_state: dict[str, float]  # 跨 tick carry


@dataclass
class PTSGradedMatrix:
    """8 维 PTS graded 矩阵（核心数据结构）"""
    dimensions: dict[PTSDimension, PTSGradedScore]  # 8 维
    rochat_level: int  # 0-5
    last_updated_tick: int

    def get_score(self, dimension: PTSDimension) -> float:
        return self.dimensions[dimension].score

    def update_dimension(self, dimension: PTSDimension, new_score: float, evidence: str):
        """更新某维度（带 Bayesian update）"""
        current = self.dimensions[dimension]
        # v3 简化版：linear blend（v3.0），v3.1+ 升级为 Bayesian
        updated_score = 0.7 * current.score + 0.3 * new_score
        self.dimensions[dimension] = PTSGradedScore(
            dimension=dimension,
            score=updated_score,
            evidence=current.evidence + [evidence],
            last_updated_tick=self.last_updated_tick,
            cross_tick_dynamics=current.cross_tick_dynamics,
        )
```

### 3.2 Rochat 5 Levels

```python
class RochatLevel(Enum):
    LEVEL_0_CONFUSION = 0       # tick 0 短暂
    LEVEL_1_DIFFERENTIATION = 1  # tick 1-N1
    LEVEL_2_SITUATION = 2        # N1-N2
    LEVEL_3_IDENTIFICATION = 3   # N2-N3
    LEVEL_4_PERMANENCE = 4       # N3-N4
    LEVEL_5_CONCEPTUAL_ME = 5    # N4+


@dataclass
class RochatAdvancementExperience:
    """推进 Rochat level 所需经验"""
    level: RochatLevel
    required_experience_type: str
    required_count: int


@dataclass
class RochatLevelState:
    """当前 Rochat level 状态"""
    current_level: RochatLevel
    experience_log: dict[str, int]  # 经验类型 → 次数
    level_history: list[tuple[int, RochatLevel]]  # (tick, level)


class RochatLevelAdvancement:
    """根据经验触发 level 推进（不按 tick-count）"""

    ADVANCEMENT_REQUIREMENTS = {
        RochatLevel.LEVEL_1_DIFFERENTIATION: [
            RochatAdvancementExperience(
                level=RochatLevel.LEVEL_1_DIFFERENTIATION,
                required_experience_type="self_vs_other_distinction",
                required_count=20,
            ),
        ],
        RochatLevel.LEVEL_2_SITUATION: [
            RochatAdvancementExperience(
                level=RochatLevel.LEVEL_2_SITUATION,
                required_experience_type="self_observation_recognized",
                required_count=10,
            ),
        ],
        RochatLevel.LEVEL_3_IDENTIFICATION: [
            RochatAdvancementExperience(
                level=RochatLevel.LEVEL_3_IDENTIFICATION,
                required_experience_type="agency_vs_environment_distinction",
                required_count=15,
            ),
        ],
        RochatLevel.LEVEL_4_PERMANENCE: [
            RochatAdvancementExperience(
                level=RochatLevel.LEVEL_4_PERMANENCE,
                required_experience_type="self_persistence_across_ticks",
                required_count=30,
            ),
        ],
        RochatLevel.LEVEL_5_CONCEPTUAL_ME: [
            RochatAdvancementExperience(
                level=RochatLevel.LEVEL_5_CONCEPTUAL_ME,
                required_experience_type="self_concept_formation",
                required_count=20,
            ),
        ],
    }

    @classmethod
    def should_advance(cls, state: RochatLevelState) -> Optional[RochatLevel]:
        current = state.current_level
        if current == RochatLevel.LEVEL_5_CONCEPTUAL_ME:
            return None  # 已在最高级
        requirements = cls.ADVANCEMENT_REQUIREMENTS.get(current)
        if requirements is None:
            return None
        for req in requirements:
            count = state.experience_log.get(req.required_experience_type, 0)
            if count < req.required_count:
                return None
        # 全部 requirements 满足，推进
        next_level = RochatLevel(current.value + 1)
        return next_level
```

### 3.3 5-layer Markov Blanket 嵌套

```python
@dataclass
class MarkovBlanketBoundary:
    """单层 Markov blanket 边界"""
    layer_id: int  # 1-5
    internal_states: dict[str, float]
    external_states: dict[str, float]
    blanket_signals: list[str]  # 通过 blanket 的 signals
    conditional_independence_invariant: bool

    def check_conditional_separation(self) -> bool:
        """Markov blanket 数学不变量：internal ⊥ external | sensory"""
        # v3 简化版：检查 internal 与 external 不直接相连
        for internal_key in self.internal_states:
            for external_key in self.external_states:
                if internal_key in self.blanket_signals:
                    continue  # 通过 blanket 是允许的
                if internal_key == external_key:
                    continue  # 同名不检查
                # 检查是否直接相连
                if self._is_directly_connected(internal_key, external_key):
                    return False
        return True

    def _is_directly_connected(self, internal_key: str, external_key: str) -> bool:
        # v3 实现：根据 dependency graph 检查
        return False  # placeholder


@dataclass
class FiveLayerMarkovBlanket:
    """5 层 Markov blanket 嵌套"""
    layer_1_boundary: MarkovBlanketBoundary  # Boundary
    layer_2_active_inference: MarkovBlanketBoundary  # Active Inference
    layer_3_self_model: MarkovBlanketBoundary  # Self-Model
    layer_4_reflection: MarkovBlanketBoundary  # Reflection
    layer_5_evolution: MarkovBlanketBoundary  # Self-Evolution

    def verify_all_conditional_separation(self) -> bool:
        """验证所有层都维持 conditional separation"""
        for layer in [self.layer_1_boundary, self.layer_2_active_inference,
                       self.layer_3_self_model, self.layer_4_reflection,
                       self.layer_5_evolution]:
            if not layer.check_conditional_separation():
                return False
        return True
```

### 3.4 Hierarchical Generative Model

```python
@dataclass
class GenerativeModelLayer:
    """单层 generative model"""
    layer_id: int
    prior: dict[str, float]  # 先验分布
    likelihood: dict[str, float]  # 似然
    posterior: dict[str, float]  # 后验
    prediction: dict[str, float]  # 当前预测


class HierarchicalGenerativeModel:
    """5 层 hierarchical generative model"""
    layers: list[GenerativeModelLayer]  # 5 层

    def predict(self, layer_id: int, input_data) -> dict[str, float]:
        """生成预测"""
        return self.layers[layer_id].prediction

    def compute_prediction_error(self, layer_id: int, prediction, actual) -> float:
        """计算 prediction error"""
        error = 0.0
        for key in prediction:
            if key in actual:
                error += (actual[key] - prediction[key]) ** 2
        return error

    def variational_free_energy(self) -> float:
        """计算 variational free energy（F = E[log q(s)] - E[log p(s, o)]）"""
        total_fe = 0.0
        for layer in self.layers:
            # 简化版：free energy ≈ prediction error^2
            for key in layer.posterior:
                if key in layer.prior:
                    total_fe += (layer.posterior[key] - layer.prior[key]) ** 2
        return total_fe

    def bayesian_update(self, layer_id: int, prediction_error: float, learning_rate: float):
        """Bayesian update"""
        layer = self.layers[layer_id]
        for key in layer.prior:
            # 简化版：prior 朝 posterior 方向更新
            layer.prior[key] += learning_rate * prediction_error
        # 限制 [0, 1]
        for key in layer.prior:
            layer.prior[key] = max(0.0, min(1.0, layer.prior[key]))
```

### 3.5 Reflection Owner

```python
class ReflectionTrigger(Enum):
    POST_TICK = "post_tick"               # 每 tick 后
    RESTING_STATE = "resting_state"        # 静息态（DMN-like）
    HIGH_UNCERTAINTY = "high_uncertainty"  # 高 uncertainty 触发
    USER_INVOKED = "user_invoked"          # 用户主动触发


@dataclass
class ReflectionRecord:
    """单次反思记录"""
    trigger: ReflectionTrigger
    pts_snapshot_before: PTSGradedMatrix  # 反思前 8 维 PTS
    pts_snapshot_after: PTSGradedMatrix  # 反思后 8 维 PTS
    llm_reasoning: str  # LLM reasoning model 输出
    insight: str  # 提取的 insight
    timestamp: int


class ReflectionOwner:
    """v3 Layer 4 反思层（关键创新）"""
    def __init__(self, llm_reasoning_model, self_model_owner, autobiographical_memory_owner):
        self.llm_reasoning = llm_reasoning_model
        self.self_model = self_model_owner
        self.autobiographical_memory = autobiographical_memory_owner
        self.reflection_history: list[ReflectionRecord] = []

    def should_trigger(self, trigger_type: ReflectionTrigger, context: dict) -> bool:
        """判断是否触发反思"""
        if trigger_type == ReflectionTrigger.POST_TICK:
            return True  # 每 tick 后都触发
        elif trigger_type == ReflectionTrigger.RESTING_STATE:
            return context.get("resting_state_duration", 0) > 100  # 静息态 > 100 tick
        elif trigger_type == ReflectionTrigger.HIGH_UNCERTAINTY:
            return context.get("uncertainty_level", 0) > 0.7
        elif trigger_type == ReflectionTrigger.USER_INVOKED:
            return context.get("user_invoked", False)
        return False

    def reflect(self, trigger_type: ReflectionTrigger, context: dict) -> ReflectionRecord:
        """执行反思"""
        pts_before = self.self_model.get_current_matrix()
        rochat_level = pts_before.rochat_level

        # 1. snapshot 8 维 PTS 状态
        snapshot_text = self._format_pts_snapshot(pts_before)

        # 2. 调 LLM reasoning model 做反思
        if trigger_type == ReflectionTrigger.POST_TICK:
            prompt = f"Reflection on this tick:\n{snapshot_text}\nContext: {context}\nSummarize what I did and why."
        elif trigger_type == ReflectionTrigger.RESTING_STATE:
            inconsistencies = self._detect_pts_inconsistency(pts_before)
            prompt = f"DMN-like reflection:\n{snapshot_text}\nInconsistencies: {inconsistencies}\nDeeply reflect."
        elif trigger_type == ReflectionTrigger.HIGH_UNCERTAINTY:
            uncertainty_sources = self._trace_uncertainty_sources(context)
            prompt = f"High uncertainty reflection:\n{snapshot_text}\nUncertainty sources: {uncertainty_sources}\nPlan uncertainty reduction."
        elif trigger_type == ReflectionTrigger.USER_INVOKED:
            prompt = f"User invoked reflection:\n{snapshot_text}\nContext: {context}\nReflect."

        llm_reasoning = self.llm_reasoning.complete(prompt)

        # 3. 提取 insight
        insight = self._extract_insight(llm_reasoning)

        # 4. 更新 self-model 8 维 PTS
        pts_after = self._apply_reflection_to_pts(pts_before, insight, rochat_level)
        self.self_model.update_matrix(pts_after)

        # 5. 写入 autobiographical memory
        record = ReflectionRecord(
            trigger=trigger_type,
            pts_snapshot_before=pts_before,
            pts_snapshot_after=pts_after,
            llm_reasoning=llm_reasoning,
            insight=insight,
            timestamp=context.get("current_tick", 0),
        )
        self.reflection_history.append(record)
        self.autobiographical_memory.append(record)

        return record

    def _format_pts_snapshot(self, pts: PTSGradedMatrix) -> str:
        """格式化 8 维 PTS 为 LLM 可读文本"""
        lines = [f"PTS Matrix (Rochat Level {pts.rochat_level}):"]
        for dim in PTSDimension:
            score = pts.get_score(dim)
            lines.append(f"  {dim.value}: {score:.2f}")
        return "\n".join(lines)

    def _detect_pts_inconsistency(self, pts: PTSGradedMatrix) -> list[str]:
        """检测 8 维 PTS 不一致"""
        inconsistencies = []
        # 例：affective 高但 bodily 低（情感跟身体不一致）
        if pts.get_score(PTSDimension.AFFECTIVE) > 0.7 and pts.get_score(PTSDimension.BODILY_PROCESSES) < 0.3:
            inconsistencies.append("high affect without bodily grounding")
        # 例：intersubjective 高但 narrative 低（理解他人但不连贯叙事）
        if pts.get_score(PTSDimension.INTERSUBJECTIVE) > 0.7 and pts.get_score(PTSDimension.NARRATIVE) < 0.3:
            inconsistencies.append("intersubjective without narrative integration")
        return inconsistencies

    def _extract_insight(self, llm_reasoning: str) -> str:
        """从 LLM reasoning 提取 insight"""
        # 简化版：取第一段作为 insight
        # v3.1+ 用更复杂的 NLP 提取
        return llm_reasoning.split("\n\n")[0]

    def _apply_reflection_to_pts(self, pts: PTSGradedMatrix, insight: str, rochat_level: int) -> PTSGradedMatrix:
        """应用反思更新 8 维 PTS"""
        # 简化版：基于 insight 更新 1-2 个维度
        # v3.1+ 用更复杂的语义分析
        new_pts = pts  # placeholder
        # v3.0 简化：每反思略微增加 Rochat-appropriate 维度
        if rochat_level >= 3 and "agency" in insight.lower():
            new_pts = new_pts.update_dimension(
                PTSDimension.MINIMAL_EXPERIENTIAL,
                min(1.0, pts.get_score(PTSDimension.MINIMAL_EXPERIENTIAL) + 0.05),
                f"reflection: {insight[:100]}",
            )
        return new_pts
```

### 3.6 ToM Owner（8 维 PTS 4）

```python
@dataclass
class ToMBelief:
    """对他人意图 / 信念的估计"""
    target_user_id: str
    belief: str  # "小黑想要..."
    confidence: float  # 0.0-1.0
    evidence: list[str]


class ToMOwner:
    """8 维 PTS (4) Intersubjective - Theory of Mind"""
    def __init__(self, llm_reasoning_model):
        self.llm_reasoning = llm_reasoning_model
        self.user_beliefs: dict[str, list[ToMBelief]] = {}  # user_id → beliefs

    def infer_intent(self, user_id: str, stimulus: str, context: dict) -> ToMBelief:
        """推断他人意图（MPFC decoupling 机制）"""
        prompt = f"""Infer the intent/belief of user {user_id} from this stimulus:
        Stimulus: {stimulus}
        Context: {context}

        Provide:
        1. What does the user likely want?
        2. What does the user believe?
        3. Confidence (0-1)"""

        llm_response = self.llm_reasoning.complete(prompt)
        # 简化版：parse LLM response
        belief = ToMBelief(
            target_user_id=user_id,
            belief=llm_response[:200],
            confidence=0.5,  # v3.0 简化
            evidence=[stimulus[:100]],
        )
        self.user_beliefs.setdefault(user_id, []).append(belief)
        return belief

    def detect_agency(self, stimulus: str) -> float:
        """pSTS agency detection - 识别他人在主动做事 vs 客观陈述"""
        prompt = f"""Detect agency in this stimulus:
        Stimulus: {stimulus}

        Is the user actively doing something (agency=high) or making a passive statement (agency=low)?
        Score 0-1."""
        llm_response = self.llm_reasoning.complete(prompt)
        # 简化版：parse 0-1 score
        return 0.5  # v3.0 简化

    def get_social_script(self, user_id: str, context: dict) -> str:
        """temporal poles - 调取社会脚本"""
        prompt = f"""Get social script for user {user_id} in context {context}.
        What social conventions/scripts apply?"""
        llm_response = self.llm_reasoning.complete(prompt)
        return llm_response[:200]
```

---

## 4. v3 LLM-as-PFC 3 层实现

### 4.1 Layer A: System Prompt（永久身份层）

```python
class SystemPromptBuilder:
    """v3 Layer A - 注入 8 维 PTS 起点 + Rochat level + 价值观 + 治理红线"""

    def build_system_prompt(
        self,
        pts_matrix: PTSGradedMatrix,
        rochat_level: RochatLevel,
        values: dict,
        governance_red_lines: list[str],
    ) -> str:
        pts_text = self._format_pts_for_prompt(pts_matrix)
        rochat_text = f"You are at Rochat Level {rochat_level.value}: {rochat_level.name}"
        values_text = "\n".join([f"- {k}: {v}" for k, v in values.items()])
        red_lines_text = "\n".join([f"- {line}" for line in governance_red_lines])

        prompt = f"""You are helios, a brain-inspired cognitive agent.

{rochat_text}

Your current 8-dimensional self-pattern (Pattern Theory of Self):
{pts_text}

Your core values:
{values_text}

Governance red lines (you may not violate):
{red_lines_text}

You operate as the prefrontal cortex of helios, integrating:
- 8-dimensional Pattern Theory of Self
- Active Inference with hierarchical generative model
- Reflection layer (meta-cognition)
- Tool use as material engagement (4E cognition)

You make decisions grounded in real signals, not performance."""
        return prompt

    def _format_pts_for_prompt(self, pts: PTSGradedMatrix) -> str:
        lines = []
        for dim in PTSDimension:
            score = pts.get_score(dim)
            lines.append(f"  {dim.value}: {score:.2f}")
        return "\n".join(lines)
```

### 4.2 Layer B: CSO（持续状态层）

```python
class ContinuousStateOwner:
    """v3 Layer B - 每个 tick 持续累积 8 维 PTS + 9-dim hormone + 7-dim feeling"""

    def __init__(self):
        self.pts_matrix = self._initialize_pts_matrix()
        self.hormone_state = self._initialize_hormone_state()
        self.feeling_state = self._initialize_feeling_state()
        self.rochat_level = RochatLevel.LEVEL_1_DIFFERENTIATION  # v3 起步 Level 1

    def observe_tick(self, tick_result: TickResult):
        """每个 tick 持续累积"""
        # 1. 更新 9-dim hormone（dual-timescale）
        self.hormone_state = self._update_hormone_dual_timescale(
            tick_result.appraisal_signal,
            tick_result.previous_hormone_state,
        )

        # 2. 更新 7-dim feeling
        self.feeling_state = self._update_feeling(
            tick_result.hormone_state,
            tick_result.interoceptive_signal,
            tick_result.previous_feeling_state,
        )

        # 3. 更新 8 维 PTS（graded matrix）
        self.pts_matrix = self._update_pts_matrix(
            tick_result,
            self.pts_matrix,
        )

        # 4. 检查 Rochat level 推进
        self._check_rochat_advancement(tick_result)

    def get_state_for_llm(self) -> dict:
        """返回给 LLM 的当前状态"""
        return {
            "pts_matrix": self._format_pts_for_llm(self.pts_matrix),
            "hormone_state": self.hormone_state.to_dict(),
            "feeling_state": self.feeling_state.to_dict(),
            "rochat_level": self.rochat_level,
        }
```

### 4.3 Layer C: Reflection（LLM 反思架构层）

（已在 §3.5 reflection_owner 设计）

---

## 5. v3 5 层 Markov blanket owner 接口设计

### 5.1 boundary_owner

```python
class BoundaryOwner:
    """v3 Layer 1 Markov blanket 边界管理"""

    def check_signal(self, signal: Any) -> bool:
        """所有进/出 Markov blanket 的信号必须经此 owner 检查"""
        if signal.is_sensory_input():
            return self._process_sensory(signal)
        elif signal.is_action_output():
            return self._process_action(signal)
        else:
            raise BoundaryViolation(f"Signal {signal} not through Markov blanket")

    def _process_sensory(self, signal) -> bool:
        # 1. 检查 signal 是否在合法 sensory modalities 中
        # 2. 检查 conditional separation
        # 3. 记录 log（可审计）
        # 4. 返回 True/False
        return True  # placeholder

    def _process_action(self, signal) -> bool:
        # 1. 检查 signal 是否在合法 action types 中
        # 2. 检查 conditional separation
        # 3. 记录 log（可审计）
        # 4. 返回 True/False
        return True  # placeholder

    def verify_conditional_separation(self) -> bool:
        """验证 conditional separation 数学不变量"""
        # 检查 internal ⊥ external | sensory
        return True  # placeholder
```

### 5.2 active_inference_owner

```python
class ActiveInferenceOwner:
    """v3 Layer 2 Hierarchical generative model + variational free energy minimization"""

    def __init__(self):
        self.generative_model = HierarchicalGenerativeModel(layers=5)

    def predict(self, layer_id: int, input_data) -> dict:
        return self.generative_model.predict(layer_id, input_data)

    def compute_free_energy(self) -> float:
        return self.generative_model.variational_free_energy()

    def minimize_free_energy(self, learning_rate: float = 0.01):
        """每 tick 最小化 free energy"""
        for layer_id in range(5):
            prediction = self.predict(layer_id, ...)
            actual = ...
            error = self.generative_model.compute_prediction_error(layer_id, prediction, actual)
            self.generative_model.bayesian_update(layer_id, error, learning_rate)

    def active_sampling(self) -> Action:
        """Active inference - 通过 action 选择性采样 sensory data"""
        # 选择能最小化 expected free energy 的 action
        return self.policy_network.select_action(self.compute_free_energy())
```

### 5.3 self_model_owner

```python
class SelfModelOwner:
    """v3 Layer 3 8 维 PTS graded × Rochat 5 levels × cross-tick dynamics"""

    def __init__(self, llm_reasoning_model):
        self.llm_reasoning = llm_reasoning_model
        self.pts_matrix = self._initialize_pts_matrix()
        self.rochat_state = RochatLevelState(
            current_level=RochatLevel.LEVEL_1_DIFFERENTIATION,
            experience_log={},
            level_history=[(0, RochatLevel.LEVEL_1_DIFFERENTIATION)],
        )

        # 8 sub-owners
        self.agency_detector = AgencyDetectorOwner(llm_reasoning_model)
        self.egocentric_perspective = EgocentricPerspectiveOwner(llm_reasoning_model)
        self.tom = ToMOwner(llm_reasoning_model)
        self.autobiographical_memory = AutobiographicalMemoryOwner()
        self.material_engagement = MaterialEngagementOwner()
        self.culture = CultureOwner()

    def update_matrix(self, new_pts: PTSGradedMatrix):
        self.pts_matrix = new_pts

    def get_current_matrix(self) -> PTSGradedMatrix:
        return self.pts_matrix

    def observe_tick(self, tick_result: TickResult):
        """每个 tick 更新 8 维 PTS"""
        # 1. 更新 PTS 1 (Bodily)
        self._update_bodily(tick_result)

        # 2. 更新 PTS 2 (Minimal experiential)
        agency_score = self.agency_detector.detect(tick_result)
        self._update_minimal_experiential(tick_result, agency_score)

        # 3. 更新 PTS 3 (Affective)
        self._update_affective(tick_result)

        # 4. 更新 PTS 4 (Intersubjective)
        tom_score = self.tom.infer_intent(
            tick_result.current_user_id,
            tick_result.stimulus_text,
            tick_result.context,
        )
        self._update_intersubjective(tick_result, tom_score)

        # 5. 更新 PTS 5 (Psychological/Cognitive)
        self._update_psychological_cognitive(tick_result)

        # 6. 更新 PTS 6 (Narrative)
        self.autobiographical_memory.append(tick_result)
        self._update_narrative(tick_result)

        # 7. 更新 PTS 7 (Ecological/Extended)
        self._update_ecological_extended(tick_result)

        # 8. 更新 PTS 8 (Normative)
        self._update_normative(tick_result)

        # 9. 检查 Rochat level 推进
        self._check_rochat_advancement(tick_result)
```

### 5.4 reflection_owner

（已在 §3.5）

### 5.5 evolution_owner + governance_owner

```python
class EvolutionOwner:
    """v3 Layer 5 Self-Evolution"""
    def __init__(self, governance_owner):
        self.governance = governance_owner

    def evolve_content(self, content_proposal) -> EvolutionResult:
        """content evolution: 记忆 / 知识 / 反思结论"""
        gate_result = self.governance.enforce_gate(
            content_proposal,
            GovernanceGate.CONTENT_EVOLUTION,
        )
        if gate_result == GovernanceDecision.APPROVED:
            return self._apply_content_evolution(content_proposal)
        return EvolutionResult.REJECTED

    def evolve_parameter(self, parameter_proposal) -> EvolutionResult:
        """parameter evolution: P5 学习"""
        gate_result = self.governance.enforce_gate(
            parameter_proposal,
            GovernanceGate.PARAMETER_EVOLUTION,
        )
        if gate_result == GovernanceDecision.APPROVED:
            return self._apply_parameter_evolution(parameter_proposal)
        return EvolutionResult.REJECTED

    def evolve_strategy(self, strategy_proposal) -> EvolutionResult:
        """strategy evolution: 受治理策略"""
        gate_result = self.governance.enforce_gate(
            strategy_proposal,
            GovernanceGate.STRATEGY_EVOLUTION,
        )
        if gate_result == GovernanceDecision.APPROVED:
            return self._apply_strategy_evolution(strategy_proposal)
        return EvolutionResult.REJECTED

    def evolve_code(self, code_proposal) -> EvolutionResult:
        """code evolution: 受治理代码自修改（v3 远期）"""
        gate_result = self.governance.enforce_gate(
            code_proposal,
            GovernanceGate.CODE_EVOLUTION,
        )
        if gate_result == GovernanceDecision.APPROVED:
            return self._apply_code_evolution(code_proposal)
        return EvolutionResult.REJECTED


class GovernanceOwner:
    """v3 Layer 5 Self-Evolution 严格 governance"""
    def enforce_gate(self, proposal, gate: GovernanceGate) -> GovernanceDecision:
        if gate == GovernanceGate.CONTENT_EVOLUTION:
            # content evolution：仅需 evaluation 通过
            if self._passes_evaluation(proposal):
                return GovernanceDecision.APPROVED
        elif gate == GovernanceGate.PARAMETER_EVOLUTION:
            # parameter evolution：需 testing + evaluation 通过
            if self._passes_testing(proposal) and self._passes_evaluation(proposal):
                return GovernanceDecision.APPROVED
        elif gate == GovernanceGate.STRATEGY_EVOLUTION:
            # strategy evolution：需 testing + evaluation + observability 通过
            if (self._passes_testing(proposal)
                and self._passes_evaluation(proposal)
                and self._passes_observability(proposal)):
                return GovernanceDecision.APPROVED
        elif gate == GovernanceGate.CODE_EVOLUTION:
            # code evolution：需全部 fitness gate + 审计
            if (self._passes_testing(proposal)
                and self._passes_evaluation(proposal)
                and self._passes_observability(proposal)
                and self._passes_audit(proposal)):
                return GovernanceDecision.APPROVED
        return GovernanceDecision.REJECTED

    def _passes_testing(self, proposal) -> bool:
        # 调测试套件
        return self.testing_suite.run(proposal)

    def _passes_evaluation(self, proposal) -> bool:
        # 调 evaluation owner（17）
        return self.evaluation_owner.evaluate(proposal)

    def _passes_observability(self, proposal) -> bool:
        # 调 observability owner（21）
        return self.observability_owner.verify(proposal)

    def _passes_audit(self, proposal) -> bool:
        # 调 audit log
        return self.audit_log.verify(proposal)
```

---

## 6. v3 复杂算法部分（最高规格）

### 6.1 Neural Network（按最高规格）

| 模块 | 算法 | v3.0 实现 | v3.1+ 升级 |
|---|---|---|---|
| **Depictive Representation** | VAE / Diffusion | 简化版：固定 latent + reconstruction loss | 完整 VAE / Diffusion model |
| **8 维 PTS** | 8 路并行 Transformer encoder + cross-aspect attention | 简化版：8 路全连接 | 完整 Transformer encoder + cross-aspect attention |
| **ToM** | 3 模块 NN（MPFC + pSTS + temporal poles） | 简化版：3 个独立 MLP | 完整 3 模块 NN + 协调机制 |
| **Predictive Coding** | Hierarchical RNN + Bayesian | 简化版：单层 RNN | 完整 Hierarchical RNN + 5 层 |
| **Active Inference** | POMDP + variational free energy | 简化版：linear policy | 完整 POMDP + free energy minimization |

### 6.2 Bayesian（按最高规格）

| 模块 | 算法 | v3.0 实现 | v3.1+ 升级 |
|---|---|---|---|
| **PTS update** | Bayesian linear blend | linear blend | 完整 Bayesian update with prior/likelihood/posterior |
| **Rochat advancement** | Bayesian trigger | threshold-based | 完整 Bayesian trigger with posterior |
| **Memory consolidation** | Bayesian surprise | surprise threshold | 完整 Bayesian surprise + KL divergence |
| **Reflection insight** | Bayesian belief update | LLM extract | 完整 Bayesian belief update with evidence |

### 6.3 Optimization（按最高规格）

| 模块 | 算法 | v3.0 实现 | v3.1+ 升级 |
|---|---|---|---|
| **Free energy minimization** | Gradient descent on variational free energy | linear update | 完整 gradient descent + Adam |
| **Active sampling** | Policy gradient | greedy policy | 完整 policy gradient + REINFORCE |
| **Reflection scheduling** | Optimization over reflection triggers | fixed schedule | 完整 optimization over triggers |

### 6.4 LLM（按最高规格）

- **v3.0**：deepseek-v4-flash / claude-sonnet / gpt-4-turbo 等 reasoning model
- **v3.1+**：根据任务选 LLM（reflection 用最强 reasoning model；planner 用 function-calling；embodied prompt 用 mid-tier）

---

## 7. v3 测试策略

### 7.1 测试基线

- **v3 起点**：v2 测试基线（1110+ passed）
- **v3.0 目标**：v2 测试基线 + v3 新增测试
- **v3 测试套件**：
  - 28 继承 owner 测试
  - 12 新增 owner 测试
  - 8 维 PTS graded matrix 测试
  - Rochat 5 levels 推进测试
  - LLM-as-PFC 3 层测试
  - reflection_owner 测试
  - active_inference_owner 测试
  - evolution_owner + governance_owner 测试

### 7.2 评估层

- v2 R83/R88/R89/R90 全部继承
- v3 新增：
  - 8 维 PTS 单独评分（每维度独立评估）
  - Rochat level 评分（推进正确性）
  - reflection_audit（reflection 是否 grounded）
  - Markov blanket conditional separation 验证
  - variational free energy minimization 验证

### 7.3 真实 LLM probe

- v2 probe 全部继承
- v3 新增 probe：
  - 8 维 PTS probe（每维度独立）
  - Rochat level probe（推进正确性）
  - reflection probe（reflection 是否 grounded）
  - ToM probe（小黑/小白称呼链路）
  - 4E cognition probe（material engagement）

---

## 8. v3 实施顺序（4 阶段 8 个月）

### Phase 1（M1-M2）：Layer 3 + Layer 4 + Layer 5 基础

- M1：8 维 PTS graded matrix + Rochat 5 levels（**核心数据**）
- M2：reflection_owner（Layer 4 关键创新）

### Phase 2（M3-M4）：Layer 1 + Layer 2

- M3：boundary_owner（Markov blanket）
- M4：active_inference_owner（hierarchical generative model）

### Phase 3（M5-M6）：LLM-as-PFC 3 层完整接通

- M5：System prompt Layer A + CSO Layer B 升级
- M6：Reflection Layer C 完整接通

### Phase 4（M7-M8）：8 维 PTS sub-owner + 复杂算法

- M7：8 个 sub-owner（agency_detector / egocentric_perspective / ToM / autobiographical / material / culture）
- M8：复杂算法按最高规格（VAE / Diffusion / Transformer / active inference）

---

## 9. v3 风险与缓解（详见 requirement.md §9）

（与 requirement.md 一致）

---

**v3 design 完成时间**：2026-06-22 19:20+
**下一步**：v3 task.md（TASK 分解 + 验收标准）+ 架构流程图（Phase 4）
**小黑拍板**：等待 v3 完整规划 ship 后 review