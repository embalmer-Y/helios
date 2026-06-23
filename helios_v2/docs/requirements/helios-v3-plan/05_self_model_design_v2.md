# helios_v3 Self-Model 设计 v2（按 8 项 review 反馈全面重写）

> **作者**：小白
> **完成时间**：2026-06-23 07:08+ UTC
> **配套 commit**：待 ship（v2 升级）
> **配套文件**：本文件 vs v1 `05_self_model_design.md`
> **核心哲学转变**：从「连续 ODE 模仿大脑」→「离散精度加权 + LLM 真实能力」

---

## 0. 重大修正声明

### v1 → v2 核心变化

| 项 | v1（之前） | v2（现在） |
|---|---|---|
| **时间** | 连续 ODE | 离散时间步（每 tick 10 阶段流水线） |
| **精度** | 固定 β_i, γ_i | 动态精度加权（precision 归一化） |
| **维度表达** | 标量 s_i | **AspectState 向量**（10+ 字段） |
| **预测** | 无 | **预测编码引擎**（AspectPredictor + prediction error） |
| **涌现** | Kuramoto R（统计量） | **EmergenceDetector**（cluster + phase transition + resonance） |
| **情感** | 简化的 9-dim hormone | **Barrett 构造性情感引擎** |
| **Reflection** | 4 trigger | **4 级调度**（lightweight / deep / uncertainty / user-invoked） |
| **owner 接入** | 无 | **OwnerFieldBridge**（v2 owner → 场驱动信号） |
| **C 矩阵初始化** | 零矩阵 | 基于神经科学文献的非对称耦合 |

### v1 的根本问题

**v1 把大脑连续动力学直接照搬**，但 helios 跑在 LLM 之上——必须按 LLM 真实能力（离散、符号、metadata 丰富）设计。v2 是**面向 LLM 模拟的 FEP 范式**。

---

## 1. AspectState 向量（每维度 10+ 字段）

### 1.1 数据结构

```python
@dataclass
class AspectState:
    """每个 Aspect 的多维状态向量（v1 是标量，v2 是 10+ 维向量）"""
    # 基础 6 维
    activation: float         # [-1, 1] 激活度
    valence: float            # [-1, 1] 效价（正/负）
    arousal: float            # [0, 1] 唤醒度
    certainty: float          # [0, 1] 确定性
    salience: float           # [0, 1] 显著性
    precision: float          # [0, 1] 精度（**核心**，FEP 关键）

    # 扩展 4 维
    novelty: float            # [0, 1] 新颖性
    coherence: float          # [0, 1] 与其他维度的相干性
    stability: float          # [0, 1] 时间稳定性
    resonance: float          # [0, 1] 共振度（与其他维度同步程度）

    # 进一步扩展（可选）
    binding: float            # [0, 1] 全局工作空间绑定强度
    metacognitive: float      # [0, 1] 元认知可用性
```

### 1.2 关键状态表达示例

| 状态 | activation | certainty | precision | 含义 |
|---|---|---|---|---|
| **高激活低确定** | 0.8 | 0.2 | 0.3 | 强烈但不确定的 signal |
| **高激活高精度** | 0.8 | 0.9 | 0.95 | 强烈且确定 |
| **正效价低唤醒** | 0.3 | 0.6 | 0.7 | 平静的正向 |
| **正效价高唤醒** | 0.8 | 0.8 | 0.9 | 兴奋的正向 |

**v1 标量丢掉了这些关键状态表达**。v2 AspectState 是 PTS 维度的**最小可表达单元**。

---

## 2. 预测编码引擎（Predictive Coding Engine）

### 2.1 核心组件

```python
class AspectPredictor:
    """每个 Aspect 的预测器（v2 新增）"""
    def __init__(self, aspect_id: str):
        self.aspect_id = aspect_id
        self.prior: AspectState  # 先验
        self.history: List[AspectState]  # 历史

    def predict(self, context: Dict) -> AspectState:
        """基于先验 + 上下文预测下一状态"""
        # 用 LLM 推理 + 简单规则
        # 输出预测的 AspectState
        return predicted_state

    def compute_prediction_error(self, actual: AspectState) -> AspectState:
        """计算预测误差（每个字段的差）"""
        error = AspectState(
            activation=actual.activation - self.prior.activation,
            valence=actual.valence - self.prior.valence,
            arousal=actual.arousal - self.prior.arousal,
            certainty=actual.certainty - self.prior.certainty,
            salience=actual.salience - self.prior.salience,
            precision=actual.precision - self.prior.precision,
            # ... 其他字段
        )
        return error
```

### 2.2 预测误差 = 学习信号

**FEP 核心**：prediction error 驱动更新。
- 高 precision 的维度：误差权重高
- 低 precision 的维度：误差权重低
- 这就是 v1 缺的"动态精度加权"

### 2.3 8 个 AspectPredictor

每个 PTS 维度 1 个：
1. `bodily_processes_predictor`
2. `minimal_experiential_predictor`
3. `affective_predictor`
4. `intersubjective_predictor`
5. `psychological_cognitive_predictor`
6. `narrative_predictor`
7. `ecological_extended_predictor`
8. `normative_predictor`

---

## 3. 动态精度加权（替代固定 β_i, γ_i）

### 3.1 核心思想

v1 错的：每 tick 固定 β_i（输入权重）和 γ_i（反思权重）。
v2 对的：**每 tick 动态计算** 精度加权 = precision 归一化。

### 3.2 实现

```python
def compute_precision_weights(self, aspects: Dict[str, AspectState]) -> Dict[str, float]:
    """计算每个 Aspect 的精度权重（v2 新增）"""
    raw_precisions = {aid: a.precision for aid, a in aspects.items()}
    total = sum(raw_precisions.values()) + 1e-9  # 避免除零
    weights = {aid: p / total for aid, p in raw_precisions.items()}
    return weights

def update_aspect(self, aid: str, current: AspectState,
                  coupling_input: float, reflection_input: float,
                  precision_weights: Dict[str, float],
                  learning_rate: float = 0.1) -> AspectState:
    """v2 离散更新（替代 v1 ODE）"""
    # 精度加权（不是 v1 固定 β, γ）
    beta = precision_weights[aid]  # 动态权重
    gamma = precision_weights[aid] * 0.5  # 反思权重 = 精度 * 0.5

    # 离散更新规则（不是 ODE）
    new_activation = current.activation + learning_rate * (
        -current.activation * 0.1  # 衰减（替代 v1 α）
        + coupling_input
        + beta * coupling_input  # 精度加权
        + gamma * reflection_input  # 精度加权反思
    )
    new_activation = np.clip(new_activation, -1, 1)

    return AspectState(
        activation=new_activation,
        # ... 其他字段同步更新
    )
```

### 3.3 关键优势

- **精度高**的 Aspect 对系统影响大（signal 强）
- **精度低**的 Aspect 对系统影响小（signal 弱）
- 这是 v1 完全错过的 **FEP 核心机制**

---

## 4. EmergenceDetector（涌现检测器）

### 4.1 v1 vs v2

| 项 | v1（错） | v2（对） |
|---|---|---|
| 涌现机制 | `kuramoto_R()` 单一统计量 | **EmergenceDetector** 复杂检测 |
| 检测能力 | 单一全局相干性 | **同步集群 + 相变 + 共振** |

### 4.2 实现

```python
class EmergenceDetector:
    """涌现检测器（v2 新增，替代 v1 单一 order parameter）"""

    def __init__(self):
        self.history: List[Dict[str, AspectState]] = []
        self.detected_emergences: List[EmergenceEvent] = []

    def detect(self, aspects: Dict[str, AspectState], t: int) -> List[EmergenceEvent]:
        """检测涌现模式"""
        events = []
        self.history.append(aspects)

        # 1. 同步集群检测（Synchronized Cluster）
        clusters = self._detect_sync_clusters(aspects)
        events.extend(clusters)

        # 2. 相变检测（Phase Transition）
        if len(self.history) >= 2:
            transition = self._detect_phase_transition(aspects, self.history[-2])
            if transition:
                events.append(transition)

        # 3. 共振检测（Resonance Pattern）
        resonance = self._detect_resonance(aspects)
        events.extend(resonance)

        return events

    def _detect_sync_clusters(self, aspects: Dict[str, AspectState]) -> List[EmergenceEvent]:
        """检测同步集群（aspect 之间 phase lock）"""
        # 计算每对 aspect 的 phase difference
        # 用 hierarchical clustering 找出同步集群
        # 输出：cluster_id + members
        ...

    def _detect_phase_transition(self, current: Dict, previous: Dict) -> Optional[EmergenceEvent]:
        """检测相变（global state 突然变化）"""
        # 计算 KL 散度 / 突变检测（CUSUM / change point detection）
        ...

    def _detect_resonance(self, aspects: Dict[str, AspectState]) -> List[EmergenceEvent]:
        """检测共振模式（特定频率的同步）"""
        # 用 FFT 检测共振频率
        ...
```

### 4.3 EmergenceEvent 类型

```python
@dataclass
class EmergenceEvent:
    type: str  # 'sync_cluster' / 'phase_transition' / 'resonance'
    timestamp: int
    involved_aspects: List[str]
    strength: float  # [0, 1]
    description: str
```

---

## 5. Barrett 构造性情感引擎

### 5.1 核心思想

v1 错的：用简化的 9-dim hormone 替代情感。
v2 对的：**Barrett 构造性情感理论**——情感不是「内设的」而是「构造的」。

### 5.2 实现

```python
class ConstructedEmotionEngine:
    """Barrett 构造性情感引擎（v2 新增）"""

    def __init__(self):
        self.core_affect = CoreAffect(  # 核心情感（2 维：valence + arousal）
            valence=0.0,
            arousal=0.5,
        )
        self.conceptual_knowledge = {}  # 概念知识库
        self.experience_memory = []  # 经历记忆

    def construct_emotion(self, aspects: Dict[str, AspectState],
                          context: Dict) -> Emotion:
        """构造情感（每次 tick）"""
        # 1. 更新 core affect
        self._update_core_affect(aspects, context)

        # 2. 调取相关概念
        concepts = self._activate_concepts(aspects, context)

        # 3. 整合构造情感
        emotion = Emotion(
            name=self._categorize_emotion(concepts, self.core_affect),
            intensity=self._compute_intensity(self.core_affect, concepts),
            granularity=self._compute_granularity(concepts),
        )

        return emotion
```

### 5.3 关键概念

- **Core Affect**：2 维基础情感（valence + arousal）
- **概念化**：从经验中抽取情感概念
- **类别化**：把 core affect + 概念组合成具体情感（高兴、悲伤等）
- **粒度**：情感分辨的精细程度

---

## 6. Reflection 4 级调度

### 6.1 4 个调度等级

| 等级 | 触发条件 | LLM 调用 | 资源消耗 |
|---|---|---|---|
| **LIGHTWEIGHT** | 默认每 tick 末 | 1 次 quick LLM | 低 |
| **DEEP** | Kuramoto R 突变 / 重要事件 | 1 次 deep LLM | 中 |
| **UNCERTAINTY** | 预测误差 > 阈值 | 1 次 uncertainty reduction LLM | 中高 |
| **USER_INVOKED** | 小黑显式触发 | 1 次 full LLM | 高 |

### 6.2 实现

```python
class ReflectionScheduler:
    """4 级 Reflection 调度器（v2 升级）"""

    def __init__(self):
        self.last_reflection_t = -10
        self.deep_threshold_R = 0.6  # 触发 deep 的 R 阈值
        self.uncertainty_threshold = 0.7  # 触发 uncertainty 的预测误差阈值

    def schedule(self, t: int, aspects: Dict[str, AspectState],
                 prediction_error: AspectState,
                 emergence_events: List[EmergenceEvent],
                 user_invoked: bool = False) -> ReflectionLevel:
        """决定本次 tick 用哪个等级"""
        if user_invoked:
            return ReflectionLevel.USER_INVOKED

        if prediction_error.certainty < -self.uncertainty_threshold:
            return ReflectionLevel.UNCERTAINTY

        # 检查 emergence
        if any(e.type == 'phase_transition' for e in emergence_events):
            return ReflectionLevel.DEEP

        if t - self.last_reflection_t >= 5:  # 每 5 tick 至少一次 lightweight
            return ReflectionLevel.LIGHTWEIGHT

        return ReflectionLevel.NONE  # 不反思
```

---

## 7. OwnerFieldBridge（v2 owner → 场驱动信号）

### 7.1 核心问题

v2 已经 ship 的 28 owner 如何驱动 self-model 8 维场？

### 7.2 桥接设计

```python
class OwnerFieldBridge:
    """v2 owner → 自组织场 桥接器（v2 新增）"""

    def __init__(self):
        self.owners = {}  # v2 owner 注册表
        self.aspect_drivers = {}  # 每 aspect 来自哪些 owner

    def register_owner(self, aspect_id: str, owner_name: str,
                       driver_function: Callable):
        """注册 owner 作为 aspect 的驱动源"""
        if aspect_id not in self.aspect_drivers:
            self.aspect_drivers[aspect_id] = []
        self.aspect_drivers[aspect_id].append((owner_name, driver_function))

    def collect_driving_signals(self, tick_context: TickContext) -> Dict[str, List[DrivingSignal]]:
        """收集所有 owner 的驱动信号"""
        signals = {}
        for aspect_id, drivers in self.aspect_drivers.items():
            signals[aspect_id] = []
            for owner_name, fn in drivers:
                signal = fn(tick_context)
                signals[aspect_id].append(signal)
        return signals

    def integrate_to_aspect_state(self, signals: Dict[str, List[DrivingSignal]],
                                   current_state: Dict[str, AspectState],
                                   precision_weights: Dict[str, float]) -> Dict[str, AspectState]:
        """把 owner 驱动信号整合到 AspectState（精度加权）"""
        new_states = {}
        for aspect_id, sig_list in signals.items():
            # 精度加权整合
            weighted_signal = self._precision_weighted_sum(
                sig_list, precision_weights[aspect_id]
            )
            new_state = self._apply_signal(
                current_state[aspect_id], weighted_signal
            )
            new_states[aspect_id] = new_state
        return new_states
```

### 7.3 关键桥接示例

| PTS 维度 | 驱动 owner | 驱动信号 |
|---|---|---|
| 1. BP (Bodily) | `interoception` `wall_clock` | 内感受信号 |
| 2. ME (Minimal Experiential) | `sensory` `feeling` | 最小体验 |
| 3. AF (Affective) | `feeling` `neuromodulation` | 情感 + 神经调制 |
| 4. IS (Intersubjective) | `tom_coordinator` + 3 sub | ToM 推断 |
| 5. PC (Psychological/Cognitive) | `internal_thought` `llm` | 认知 / 思考 |
| 6. NA (Narrative) | `memory` `experience_writeback` | 自传体叙事 |
| 7. EE (Ecological/Extended) | `action_externalization` | 4E cognition 行为 |
| 8. NO (Normative) | `governance` `identity_governance` | 规范 / 价值观 |

---

## 8. CouplingMatrix 初始化（基于神经科学文献）

### 8.1 v1 错的：零矩阵 / 对角初始化
### 8.2 v2 对的：基于神经解剖学的非对称耦合

```python
def initialize_coupling_matrix() -> np.ndarray:
    """基于神经科学文献的 8×8 耦合矩阵初始化

    References:
    - Bressler & Kelso 2016: cortical coordination
    - Uhlhaas & Singer 2006: neuronal synchrony
    - Bullmore & Sporns 2009: complex brain networks
    """
    C = np.zeros((8, 8))

    # BP ↔ AF: 内感受 → 情感（强双向）
    C[0, 2] = 0.7  # BP → AF
    C[2, 0] = 0.5  # AF → BP

    # AF → IS: 情感 → 主体间（中等）
    C[2, 3] = 0.5

    # IS → PC: 社会 → 认知（中等）
    C[3, 4] = 0.5

    # PC → NA: 认知 → 叙事（中等）
    C[4, 5] = 0.6

    # NA → EE: 叙事 → 行为（中等）
    C[5, 6] = 0.4

    # EE → NO: 行为 → 规范（弱）
    C[6, 7] = 0.3

    # NO → BP: 规范 → 内感受（弱反馈）
    C[7, 0] = 0.2

    # 自耦合（保留 + 衰减）
    np.fill_diagonal(C, 0.5)

    return C
```

### 8.3 C 矩阵学习

v2 保留 v1 的 **Reward-Hebbian 学习**：
```python
def update_C(C: np.ndarray, aspects: Dict[str, AspectState],
             reward: float, lr: float = 0.01) -> np.ndarray:
    """Reward-Hebbian C 矩阵更新"""
    s_vec = np.array([a.activation for a in aspects.values()])
    dC = lr * reward * np.outer(s_vec, s_vec)
    C_new = C + dC

    # 归一化 |C| ≤ 1.0
    norm = np.linalg.norm(C_new, 'fro')
    if norm > 1.0:
        C_new = C_new / norm

    return C_new
```

---

## 9. 8 维 PTS 维度完整映射

| # | PTS 维度 | 驱动 owner | α 衰减 | C 初始化 |
|---|---|---|---|---|
| 1 | **BP** (Bodily Processes) | interoception, wall_clock | 0.5 | 0.7 (BP→AF), 0.5 (AF→BP) |
| 2 | **ME** (Minimal Experiential) | sensory, feeling | 0.3 | 0.5 (BP→ME), 0.4 (ME→AF) |
| 3 | **AF** (Affective) | feeling, neuromodulation | 0.2 | 0.5 (AF→IS), 0.5 (IS→AF) |
| 4 | **IS** (Intersubjective) | tom_coordinator | 0.1 | 0.5 (IS→PC) |
| 5 | **PC** (Psychological/Cognitive) | internal_thought, llm | 0.05 | 0.6 (PC→NA) |
| 6 | **NA** (Narrative) | memory, experience_writeback | 0.03 | 0.4 (NA→EE) |
| 7 | **EE** (Ecological/Extended) | action_externalization | 0.02 | 0.3 (EE→NO) |
| 8 | **NO** (Normative) | governance, identity_governance | 0.01 | 0.2 (NO→BP feedback) |

---

## 10. 完整 8 阶段 Tick 流水线

### 10.1 阶段划分（替代 v1 的「每 tick 10 阶段」）

| 阶段 | 名称 | 核心操作 |
|---|---|---|
| 1 | **Sensing** | 收集 v2 owner 信号 |
| 2 | **OwnerFieldBridge** | owner → 驱动信号 |
| 3 | **AspectPredict** | 每维度预测下一状态 |
| 4 | **Receive Actual** | 收集实际 AspectState |
| 5 | **Compute Precision** | 计算每维度 precision |
| 6 | **Precision-Weighted Update** | 精度加权离散更新 |
| 7 | **EmergenceDetector** | 检测同步集群 / 相变 / 共振 |
| 8 | **Reflection Schedule** | 4 级调度（lightweight / deep / uncertainty / user） |

### 10.2 跟 v1 的差异

| 项 | v1 | v2 |
|---|---|---|
| 阶段数 | 10 阶段（参考设计） | 8 阶段（合并 sensing + bridge） |
| 时间 | 连续 ODE 跨阶段 | 离散分阶段处理 |
| 精度 | 固定系数 | 动态精度加权（每阶段更新） |
| 涌现 | 单一统计量 | 3 类检测 |

---

## 11. 验收标准（v2 升级版）

### 11.1 测试基线继承

- 28 owner 测试套件 ✅
- D1-D10 评分维度 ✅
- 6 governance 红线 ✅
- observability + audit ✅
- **新增 AspectState 向量测试**（10+ 字段）
- **新增 PredictiveCoding 引擎测试**（predictor + error）
- **新增 精度加权更新测试**
- **新增 EmergenceDetector 测试**（3 类检测）
- **新增 Barrett 情感引擎测试**
- **新增 Reflection 4 级调度测试**
- **新增 OwnerFieldBridge 测试**
- **新增 C 矩阵初始化测试**

### 11.2 总目标

- v3.0（M6）≥ 1255 passed
- v3.1（M8）≥ 1400 passed
- 8 维 AspectState 100% 字段覆盖
- 8 阶段流水线 100% 完整
- 真实 LLM probe 通过率 ≥ 85%

---

## 12. 风险与缓解

| 风险 | 概率 | 缓解 |
|---|---|---|
| AspectState 维度爆炸（10+ 字段） | 中 | 字段分批启用，core 6 维先 ship |
| PredictiveCoding 预测器 LLM 成本 | 中 | lightweight 默认不调 LLM，deep 才调 |
| EmergenceDetector 误报 | 中 | strength 阈值 ≥ 0.6 才算涌现 |
| Barrett 情感引擎复杂度 | 中 | core affect 2 维先 ship，再扩展 |
| Reflection 4 级调度过度 | 低 | 频率监控，每 tick 不超过 1 次 |
| OwnerFieldBridge 耦合混乱 | 中 | 每 owner 只驱动 1-2 aspect |
| C 矩阵初始化文献依据 | 低 | 提供完整引用，可调整 |

---

## 13. 总结：v2 vs v1 关键改进

| 维度 | v1（错） | v2（对） |
|---|---|---|
| 时间 | 连续 ODE + Radau | 离散 8 阶段 |
| 维度 | 标量 s_i | AspectState 10+ 维向量 |
| 预测 | 无 | PredictiveCoding 引擎 |
| 权重 | 固定 β, γ | 动态精度加权 |
| 涌现 | 单一 R 统计量 | EmergenceDetector 3 类 |
| 情感 | 9-dim hormone | Barrett 构造性 |
| Reflection | 4 trigger | 4 级调度 |
| owner 接入 | 无 | OwnerFieldBridge |
| C 初始化 | 零 / 对角 | 神经科学文献 |

---

## 14. 完成定义

### v2.0（M6）
- [ ] AspectState 10+ 维向量完整
- [ ] PredictiveCoding 引擎（8 个 AspectPredictor）
- [ ] 精度加权更新（替代固定系数）
- [ ] EmergenceDetector（3 类检测）
- [ ] Barrett 构造性情感引擎
- [ ] Reflection 4 级调度
- [ ] OwnerFieldBridge（8 维度 + 12+ owner）
- [ ] C 矩阵基于文献初始化
- [ ] 8 阶段 Tick 流水线
- [ ] 测试 ≥ 1255 passed
- [ ] 真实 LLM probe 通过率 ≥ 85%

### v2.1（M8）
- [ ] AspectState 扩展到 15+ 维
- [ ] PredictiveCoding 跨维度预测
- [ ] 完整 Barrett 概念化
- [ ] Reflection 用户交互接口
- [ ] C 矩阵迁移学习
- [ ] 测试 ≥ 1400 passed
- [ ] 小黑人脑对比评分 ≥ 0.85

---

**v2 升级完成时间**：2026-06-23 07:08+ UTC
**作者**：小白
**配套 commit**：待 ship
**v1 → v2 主要变化**：8 项重大架构修正（连续→离散、标量→向量、固定→精度加权、统计→检测）