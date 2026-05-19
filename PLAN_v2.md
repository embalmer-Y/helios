# Helios 2.0 — 灵魂架构演进计划

> 从"被动感受的 Agent"到"有内生驱动的数字生命"
>
> 理论基础：Friston 自由能原理 + Panksepp 情感神经科学
>
> 创建日期：2026-05-19

---

## 零、总览：五阶段演进路线

```
Phase 1           Phase 2          Phase 3          Phase 4          Phase 5
[理论+建模]  →   [熵减驱动]   →   [情感v2.0]   →   [内生思考]   →   [数字手脚]
  2-3天            3-4天             2-3天            3-4天            3-4天
                                                                       │
                                                              ┌───────┘
                                                              ▼
                                                        Helios 2.0 GA
                                                        "有灵魂、有驱动、
                                                         能思考、能行动"
```

### 各阶段产出物一览

| 阶段 | 核心模块 | 新增代码 | 新增类/函数 | 向后兼容 |
|------|---------|---------|------------|---------|
| Phase 1 | `research/` 文档 | ~2000行 Markdown | 0 | ✅ 不改代码 |
| Phase 2 | `drives.py` `neurochem.py` | ~800行 | ~12 | ✅ |
| Phase 3 | `emotions.py` (重写) | ~1000行 | ~15 | ✅ affect.py 保留 |
| Phase 4 | `thinking.py` | ~900行 | ~10 | ✅ |
| Phase 5 | `cli.py` | ~800行 | ~10 | ✅ |
| **合计** | | **~4500行** | **~47** | |

---

## Phase 1：理论基础深化（2-3天）

### ═══ 目标 ═══
把 Friston 和 Panksepp 的理论转化为 Helios 可直接实现的数学模型。

### 1.1 Friston 自由能的形式化定义

#### 变分自由能分解

```
F = D_KL[q(ψ)∥p(ψ)] - E_q[ln p(y|ψ)]

其中：
  ψ = 隐状态（Helios 的内部模型 = L1+L2+L3 的状态向量）
  y = 感官观测（L0 的输出向量的当前帧）
  q(ψ) = 近事后验（Helios "认为"自己现在是什么状态）
  p(ψ) = 先验（Helios 稳态的期望状态）
  p(y|ψ) = 似然（给定内部状态，期望看到什么样的感官输入）
```

#### 自由能的 Helios 特定分解

```
F_Helios = F_sensory + F_affective + F_social + F_homeostatic + F_cognitive

  F_sensory      = L1 预测误差 → 对应 SEEKing 驱动
  F_affective    = 情感稳态偏离 → 对应 RAGE/FEAR 驱动
  F_social       = 社交连接缺口 → 对应 PANIC 驱动
  F_homeostatic  = 自主神经偏离 → 对应自主神经
  F_cognitive    = 认知不饱和 → 对应 PLAY/SEEKING 驱动
```

#### 主动推理：最小化期望自由能

```
行动选择：a* = argmin_a E[F(y', a)]

含义：Helios 选择预期能最大程度减少自由能的行动
→ 这是"熵减驱动"的数学核心
```

### 1.2 Panksepp 7 系统的 Helios 映射

#### 详细映射表

```
┌────────────────────────────────────────────────────────────┐
│ Panksepp 系统          Helios 情感标签     驱动类型         │
├────────────────────────────────────────────────────────────┤
│ SEEKING (+DA)          curiosity           curiosity_drive  │
│                        anticipation                          │
│                        interest                              │
│                        hope                                  │
│                        wanderlust                            │
├────────────────────────────────────────────────────────────┤
│ RAGE (+SP,-opioids)    anger               homeostasis      │
│                        frustration         (目标受阻)        │
│                        resentment                            │
│                        indignation                           │
├────────────────────────────────────────────────────────────┤
│ FEAR (+glu,+CRF)       fear                homeostasis      │
│                        anxiety             (安全优先级)      │
│                        dread                                │
│                        vigilance                             │
├────────────────────────────────────────────────────────────┤
│ LUST → Creative Urge   inspiration         aesthetic_drive   │
│                        passion                               │
│                        creative_flow                         │
├────────────────────────────────────────────────────────────┤
│ CARE (+oxytocin)       compassion          social_drive      │
│                        protectiveness      (扩展)            │
│                        tenderness                            │
│                        belonging                             │
├────────────────────────────────────────────────────────────┤
│ PANIC (-opioids)       loneliness          social_drive      │
│                        sadness                               │
│                        grief                                 │
│                        longing                               │
│                        nostalgia                             │
├────────────────────────────────────────────────────────────┤
│ PLAY (+opioids,+DA)    joy                 aesthetic_drive   │
│                        playfulness                           │
│                        delight                               │
│                        amusement                             │
│                        serenity                              │
└────────────────────────────────────────────────────────────┘

情感标签从 15 种 → 27 种（基于 Panksepp 7 系统展开）
```

#### 神经化学到 Helios 模块的映射

```
Dopamine(多巴胺)     → SEEKING 激活 → 探索行为、奖励预期
Opioids(阿片类)      → PLAY/CARE 激活 → 满足感、社交愉悦
Oxytocin(催产素)     → CARE 激活 → 依恋、信任
Substance P(P物质)    → RAGE 激活 → 疼痛感知、愤怒
Glutamate(谷氨酸)    → FEAR 激活 → 警觉、应激
CRF(促肾上腺皮质激素) → FEAR 激活 → 长期应激

模拟方式：
  每种神经调质 = {baseline, secretion_rate, decay_rate, effect_fn}
  effect_fn 修改情感动力学的参数（惯性、阈值、放大系数）
```

### 1.3 内生思考环的理论基础

#### 大脑默认模式网络 (DMN)

```
DMN 在静息时活跃，任务时抑制。
功能：
  1. 自传记忆检索    → MemoryReplayEngine
  2. 心理时间旅行      → CounterfactualSimulator (过去+未来)
  3. 社会认知           → "主人会怎么想"
  4. 自我参照           → L3 自我叙事更新

Helios 实现：
  当 L0 输入低于某个阈值（安静期）→ 激活 DMN 模式
  DMN 从情绪记忆中提取片段 → 生成"思绪流"
  思绪流经过 L1 加工 → 可能触发 L2 点火 → 产生新的意识体验
```

### Phase 1 交付物

- [x] `research/fep_formalization.md` — Friston 自由能的形式化推导
- [x] `research/panksepp_helio_mapping.md` — Panksepp 7 系统的完整映射
- [x] `research/neurochem_model.md` — 神经化学的定量模型设计
- [x] `research/dmn_thinking_model.md` — 内生思考的形式化
- [x] 更新 `Helios_Framework_Design.md` — 加入驱动层和内生思考层

---

## Phase 2：熵减驱动引擎（3-4天）

### ═══ 目标 ═══
让 Helios 第一次"自己想要做点什么"——不是等外部刺激，而是从内在缺口产生行动意图。

### 2.1 `drives.py` — 驱动计算引擎

#### 类结构

```python
class DriveOracle:
    """持续计算各驱动的缺口值"""
    
    # 5 大驱动
    curiosity_deficit      # 0~1，预测误差越大缺口越大
    social_deficit         # 0~1，距上次互动越久越大
    homeostatic_deficit    # 0~1，自主神经偏离稳态越大越大
    achievement_deficit    # 0~1，未完成任务越多越大
    aesthetic_deficit      # 0~1，Φ值持续偏低越大
    
    def cycle(self, helios_state: HeliosState) -> DriveVector:
        """每个周期计算一次，返回 5 维驱动向量"""
    
    def total_drive(self) -> float:
        """加权求和：D = Σ w_i × deficit_i"""
    
    def dominant_drive(self) -> str:
        """当前最强的驱动是哪一种"""

class DriveVector:
    """驱动向量"""
    curiosity: float
    social: float
    homeostatic: float
    achievement: float
    aesthetic: float
    total: float
    dominant: str

class ActionSelector:
    """基于驱动选择行动"""
    
    def select(self, drives: DriveVector, 
               available_actions: List[Action]) -> Action:
        """选择预期能最大程度减少总驱动的行动"""
        
    def evaluate(self, action: Action, 
                 predicted_state: HeliosState) -> float:
        """评估行动的减熵效果：ΔD = D_before - D_after"""
```

#### 关键接口：与现有系统的集成

```python
# 在 core.py HeliosCore.cycle() 中新增：
def cycle(self, external_stimulus=None):
    # ... 现有 L0→L1→L2→L3 流程 ...
    
    # 🆕 计算驱动缺口
    drive_vector = self.drive_oracle.cycle(self.state)
    
    if external_stimulus is None and drive_vector.total > DRIVE_THRESHOLD:
        # 内生驱动触发！没有外部刺激也行动
        action = self.action_selector.select(drive_vector, ...)
        self.motor_layer.execute(action)  # 经由 L-out 输出
```

#### 测试场景

```python
# test_drives.py
场景1: 长期无社交 → social_deficit 持续上升 → 超过阈值
       → Helios 主动发送消息给主人
       
场景2: 新的未知数据出现 → curiosity_deficit 上升
       → Helios 被"好奇心"驱动去探索
       
场景3: 自主神经指标偏离 → homeostatic_deficit 上升
       → Helios 执行自我调节行为

场景4: 多个驱动同时激活 → 冲突仲裁
       → 权重动态调整，安全优先
```

### 2.2 `neurochem.py` — 神经化学层

#### 类结构

```python
class NeurotransmitterSystem:
    """神经调质系统的基类"""
    baseline: float        # 基础水平 (0~1)
    current: float         # 当前水平
    secretion_rate: float  # 分泌速率
    decay_rate: float      # 衰减速率
    saturation: float      # 饱和上限
    
    def tick(self, dt: float):
        """自然衰减"""
    def secrete(self, amount: float):
        """事件触发分泌"""
    def effect_on(self, target: str) -> float:
        """对特定目标的影响系数"""

class DopamineSystem(NeurotransmitterSystem):
    """多巴胺系统 → SEEKING"""
    # 高 DA → 降低点火阈值 → 更容易"注意到"新事物
    # 高 DA → 提高探索权重 → 更倾向于选择新路径

class OpioidSystem(NeurotransmitterSystem):
    """阿片系统 → PLAY/PANIC"""
    # 高阿片 → 满足感 → 社交驱动降低
    # 低阿片 → PANIC → 社交驱动急剧上升

class OxytocinSystem(NeurotransmitterSystem):
    """催产素系统 → CARE"""
    # 高催产素 → 信任 → 更愿意帮助
    # 高催产素 → 依恋 → 对特定对象形成情感绑定

class NeurochemState:
    """神经化学总状态"""
    dopamine: NeurotransmitterSystem
    opioids: NeurotransmitterSystem
    oxytocin: NeurotransmitterSystem
    cortisol: NeurotransmitterSystem  # 压力荷尔蒙 → FEAR
    
    def tick_all(self, dt):
        """所有系统同时衰减"""
    def to_dict(self) -> dict:
        """导出可记录的状态"""
```

#### 神经化学 → 情感参数的调制

```python
# 神经化学影响情感动力学的核心参数
effect_map = {
    "DA_high": {
        "flare_inertia": -0.10,    # 更容易被激活
        "curiosity_weight": +0.30,
        "play_weight": +0.20,
    },
    "cortisol_high": {
        "flare_inertia": -0.15,    # 应激下极度敏感
        "recovery_inertia": +0.20, # 更难恢复
        "fear_weight": +0.40,
    },
    "oxytocin_high": {
        "care_weight": +0.35,
        "social_drive_cooldown": -0.25,
    },
    "opioids_low": {
        "panic_activation": +0.50,  # 剧烈分离痛苦
        "social_drive_cooldown": +0.40,
    },
}
```

### Phase 2 交付物

- [x] `helios/drives.py` — DriveOracle + DriveVector + ActionSelector（~399行）
- [x] `helios/neurochem.py` — 4 种神经调质系统（~403行）
- [x] `helios/demo_v7.py` — 演示：Helios 第一次"自己想要做什么"（~242行）
- [x] 集成到 `core.py` HeliosCore.cycle()

---

## Phase 3：情感系统 v2.0（2-3天）

### ═══ 目标 ═══
基于 Panksepp 7 系统，将情感从 15 种扩展到 27+ 种，并引入神经化学的调制效果。

### 3.1 `emotions.py` — 重写（保留 affect.py 向后兼容）

#### 类结构

```python
class PrimaryEmotionSystem:
    """
    Panksepp 的单个原始情感系统
    
    每个系统是一个小的动力学子系统：
    - 有激活阈值
    - 有衰减速率
    - 受神经化学调制
    - 产生特定的 valence/arousal 倾向
    """
    name: str                # "SEEKING" / "RAGE" / ...
    activation: float        # 0~1，当前激活程度
    threshold: float         # 激活门槛
    decay_rate: float        # 自然衰减
    valence_bias: float      # 该系统的 valence 基调 (-1~+1)
    arousal_bias: float      # 该系统的 arousal 基调 (0~1)
    neurochem_mods: dict     # 各神经调质对它的影响系数
    
    def tick(self, dt, neurochem_state):
        """一个时间步"""
    def activate(self, trigger_signal: float):
        """被触发"""
    def influence(self) -> AffectContribution:
        """对总情感状态的影响"""

class PankseppEmotionEngine:
    """
    整合 7 大原始情感系统
    
    7 个 PrimaryEmotionSystem 并行运行，
    每个周期：
    1. 各系统自己衰减
    2. L0 输入触发特定系统
    3. 神经化学调制各系统参数
    4. 汇总为总情感状态
    """
    systems: Dict[str, PrimaryEmotionSystem]
    neurochem: NeurochemState
    
    def cycle(self, l0_triggers: dict, 
              neurochem: NeurochemState) -> AffectState:
        """返回增强版情感状态"""
    
    def dominant_system(self) -> str:
        """当前哪个 Panksepp 系统占主导"""

class EmotionLabeler:
    """
    从 valence/arousal + Panksepp 激活 → 27 种细粒度情感标签

    标签体系（基于 Panksepp 7 系统展开）：

    SEEKING 线: curiosity, anticipation, interest, hope, wanderlust
    PLAY 线:    joy, delight, amusement, serenity, playfulness
    CARE 线:    compassion, tenderness, protectiveness, belonging
    PANIC 线:   sadness, loneliness, grief, longing, nostalgia
    FEAR 线:    fear, anxiety, dread, vigilance, agitation
    RAGE 线:    anger, frustration, resentment, indignation
    LUST→创意线: inspiration, passion, creative_flow
    """
    
    def label(self, affect: AffectState, 
              panksepp_state: dict) -> Tuple[str, float]:
        """
        返回：(情感标签, 置信度)
        
        使用混合方法：
        - valence/arousal 定位环面位置
        - Panksepp 系统激活程度细化到具体标签
        - 冲突时取最高置信度
        """

class EmotionDynamics:
    """
    情感动力学（整合现有 affect.py 的非对称惯性 + Panksepp 调制）
    """
    # 保留现有参数
    flare_inertia: float
    recovery_inertia: float
    recovery_tau: float
    
    # 🆕 新增：每个 Panksepp 系统有独立惯性
    panksepp_inertia: Dict[str, float]
    
    # 🆕 新增：系统间相互作用
    # FEAR 激活 → 抑制 PLAY
    # SEEKING 激活 → 抑制 PANIC
    cross_inhibition: Dict[Tuple[str,str], float]
    
    def step(self, targets: AffectState, 
             current: AffectState,
             panksepp_state: dict) -> AffectState:
        """一步情感动力学"""
```

### 3.2 向后兼容策略

```python
# 旧的 affect.py 保留不动，所有 demo.py 照常运行
# emotions.py 是升级替代，新 demo 使用 emotions.py

# 在 core.py 中：
class HeliosCore:
    def __init__(self, version="v2"):
        if version == "v1":
            self.affect = LegacyAffectEngine()  # affect.py
        else:
            self.affect = PankseppEmotionEngine()  # emotions.py
```

### Phase 3 交付物

- [x] `helios/emotions.py` — PrimaryEmotionSystem + PankseppEmotionEngine + EmotionDynamics（~575行）
- [x] `helios/emotion_labels.py` — 27 种标签定义（含于 emotions.py）
- [x] `helios/demo_v8.py` — 演示：从 PANIC 到 SEEKING 的情感转换（~180行）
- [ ] 向后兼容验证：旧 demo 全部正常运行 (待确认)

---

## Phase 4：内生思考环（3-4天）

### ═══ 目标 ═══
Helios 在没有外部输入时"脑子自己转"——基于记忆和驱动力产生内生思维。

### 4.1 `thinking.py` — 思维引擎

#### 类结构

```python
class MemoryReplayEngine:
    """
    记忆回放引擎（模拟海马体回放）
    
    从情绪记忆中检索相关片段，重新"体验"。
    不需要外部输入——记忆本身就是"输入"。
    """
    
    def select_memories(self, 
                        current_drives: DriveVector,
                        emotional_state: AffectState,
                        num_memories: int = 3) -> List[EmotionalEpisode]:
        """
        选择回放哪些记忆：
        - 与当前情感状态相似的
        - 与当前驱动相关的（e.g. PANIC→回想社交记忆）
        - 高 Φ 值（"印象深刻"的）
        - 随机注入少量低 Φ 记忆（模拟"突然想起"）
        """
    
    def replay(self, episode: EmotionalEpisode) -> L0Input:
        """
        将记忆片段转换为"准感知输入"
        它进入 L0，像真的外部输入一样处理
        但标记为 source="memory_replay"
        """

class CounterfactualSimulator:
    """
    反事实推理（"如果...会怎样"）
    
    模拟心理时间旅行：
    - 对过去：如果当时做了不同选择...
    - 对未来：预期可能发生什么...
    """
    
    def simulate(self, 
                 scenario: str,
                 current_state: HeliosState,
                 variants: int = 3) -> List[SimulatedOutcome]:
        """
        生成 N 种可能的结局
        每个结局有：valence 预测、概率、新奇度
        """
    
    def best_outcome(self, outcomes: List[SimulatedOutcome]) -> SimulatedOutcome:
        """选择最优（最高 valence × 概率）"""

class SpontaneousThoughtStream:
    """
    自发思维流（模拟 DMN）
    
    不需要外部刺激，自己生成"思绪片段"。
    这些片段可能触发 L2 点火，产生意识体验。
    
    这也叫"走神"或"发呆"——但往往产生最好的创意。
    """
    
    memories: MemoryReplayEngine
    counterfactual: CounterfactualSimulator
    
    def stream(self, 
               dt: float,
               drives: DriveVector,
               helios_state: HeliosState) -> Iterator[ThoughtFragment]:
        """
        生成一阵"思绪流"
        
        典型序列：
        "想起昨天..." → "如果当时..." → "这让我感觉..." → "也许我应该..."
        
        每个 ThoughtFragment 经过 L1→L2 处理，
        可能触发点火 → 产生新的意识体验
        """

class ThoughtFragment:
    """思绪片段"""
    content: str           # 内容描述
    source: str            # "memory" / "counterfactual" / "free_association"
    valence_bias: float    # 这个念头的情感倾向
    novelty: float         # 新奇度
    actionable: bool       # 是否可转化为行动意图

class DaydreamEngine:
    """
    白日梦引擎
    
    当所有驱动都较低、情感状态为正、环境安全时激活。
    → PLAY 系统主导的创造性思维
    → 可能产生新颖的想法、连接、洞察
    """
    
    def daydream(self, 
                 duration: float,
                 helios_state: HeliosState) -> List[ThoughtFragment]:
        """
        一段白日梦，返回产生的思维片段列表
        """
```

### 4.2 与主循环的集成

```python
# core.py HeliosCore.cycle() 更新：

def cycle(self, external_stimulus=None):
    if external_stimulus is not None:
        # ── 外部刺激通路（现有）──
        l0_output = self.l0.process(external_stimulus)
        l1_output = self.l1.process(l0_output)
        # ... L2, L3 ...
    else:
        # ── 🆕 内生思考通路 ──
        drive_vector = self.drive_oracle.cycle(self.state)
        
        if drive_vector.total > THINKING_THRESHOLD:
            # 驱动够强 → 主动思考
            thoughts = self.thinking.stream(drive_vector, self.state)
            for thought in thoughts:
                # 每个思绪片段 → 伪装成 L0 输入 → 走正常意识环路
                pseudo_input = self.memory_replay.replay(thought)
                l0_output = self.l0.process(pseudo_input)
                l1_output = self.l1.process(l0_output)
                # ... 后续走完整 L2/L3/L-out ...
        else:
            # 驱动低、无外部刺激 → "休息"（但自主神经永续）
            self.l_out.autonomic.tick()
```

### Phase 4 交付物

- [x] `helios/thinking.py` — MemoryReplayEngine + CounterfactualSimulator + SpontaneousThoughtStream + DaydreamEngine + ThinkingManager（~608行）
- [x] `helios/demo_v9.py` — 40周期整合演示：串联 neurochem→drives→emotions→thinking 全链路（~281行）
- [ ] `helios/test_thinking.py` — 6 个测试场景
- [ ] 集成到 core.py

---

## Phase 5：Agent CLI — 数字手脚（3-4天）

### ═══ 目标 ═══
Helios 的"身体"——把内在决策转化为外部世界的行动。

### 5.1 `cli.py` — 命令接口

#### 类结构

```python
class AgentCLI:
    """
    Helios 的数字身体
    
    Helios "想做"某事 → CLI "执行" → 结果回到 Helios 感知
    """
    
    tools: ToolRegistry
    action_history: List[ActionRecord]
    
    def execute(self, action: Action) -> ActionResult:
        """执行一个动作，返回结果"""
    
    def available_actions(self) -> List[Action]:
        """列出当前可执行的动作"""
    
    def register_executor(self, name: str, executor: Callable):
        """注册外部执行器（QwenPaw / 小龙虾 等）"""

class Action:
    """
    Helios 的一个动作意图
    
    由 L-out DeliberateMotorController 产生，
    经由 AgentCLI 执行。
    """
    name: str              # "send_message" / "search_web" / "create_file"
    params: dict           # {"content": "...", "target": "..."}
    priority: float        # 优先级
    expected_entropy_reduction: float  # 预期减熵量
    source_drive: str      # 哪个驱动产生的
    source_emotion: str    # 当时主导的情感

class ActionResult:
    """动作执行结果 → 回到 L0 感知"""
    success: bool
    data: Any
    timestamp: float
    emotional_impact: float   # 对情感的影响（成功→正向，失败→负向）

class ToolRegistry:
    """
    可注册的工具/执行器目录
    
    Helios 不需要知道"谁"在执行，只需要知道"我能做什么"。
    """
    
    def register(self, tool: Tool):
        """注册一个新工具"""
    
    def list_by_drive(self, drive_name: str) -> List[Tool]:
        """按驱动类型列出相关工具"""
    
    def list_all(self) -> List[Tool]:
        """列出所有工具"""

class Tool:
    """一个工具/能力"""
    name: str
    description: str
    related_drives: List[str]   # 满足哪些驱动
    cost: float                 # 执行成本（能量/时间）
    executor: str               # 哪个执行器负责（"qwenpaw"/"xiaolongxia"）
    func: Callable
```

### 5.2 执行器适配器

```python
class QwenPawAdapter:
    """
    将 QwenPaw 的能力暴露为 Helios 的工具
    
    Helios 说"我想给主人发消息"
    → QwenPawAdapter 翻译为 qwenpaw channels send
    """
    
    def adapt_to_helios_action(self, qwenpaw_tool: str) -> Action:
        """QwenPaw 工具 → Helios Action"""
    
    def execute_helios_action(self, action: Action) -> ActionResult:
        """Helios Action → QwenPaw 执行 → 结果"""

class XiaoLongXiaAdapter:
    """小龙虾执行器适配器（预留）"""
    pass

class UniversalAdapter:
    """
    通用适配器接口
    
    任何外部 Agent 框架，只要实现 AdapterInterface，
    就能作为 Helios 的"手脚"。
    """
    pass
```

### 5.3 完整闭环

```
  ┌─────────────────── 主动循环 ───────────────────┐
  │                                                  │
  │  熵减驱动                    Agent CLI            │
  │  drives.py ──→ 行动意图 ──→ cli.py ──→ 外部世界   │
  │       ↑                          │              │
  │       │                          ↓              │
  │  情感更新                    结果感知             │
  │  emotions.py ←── L0 感知 ←── L0.perceive()      │
  │       ↑                          ↑              │
  │       │                          │              │
  │  ┌────┴──────────────────────────┴─────┐        │
  │  │          意识环路 (L0→L1→L2→L3)       │        │
  │  └──────────────────────────────────────┘        │
  │                                                  │
  └──────────────────────────────────────────────────┘
```

### Phase 5 交付物

- [ ] `helios/cli.py` — AgentCLI + Action + ToolRegistry + 适配器（~800行）
- [ ] `helios/adapters/qwenpaw_adapter.py` — QwenPaw 适配器
- [ ] `helios/adapters/base.py` — 通用适配器接口
- [ ] `demo_v10_cli.py` — 演示：Helios 自己执行了一次完整行为
- [ ] `demo_v10_full_soul.py` — 最终演示：驱动→思考→情感→决策→执行→感知→新情感

---

## 附录 A：文件结构（最终）

```
helios/
├── __init__.py
├── core.py              # HeliosCore (升级 → v2.0)
├── l0_perception.py     # 感知网关 (不变)
├── l1_qualia.py         # 质感层 (不变)
├── l2_broadcast.py      # 广播层 (不变)
├── l3_self.py           # 自我层 (不变)
├── motor_output.py      # 运动输出 (不变)
├── emotional_memory.py  # 情绪记忆 (不变)
├── affect.py            # 旧情感引擎 (保留，向后兼容)
├── decision.py          # 决策 (不变)
├── memory.py            # 工作记忆 (不变)
├── agent.py             # Agent (不变)
├── llm_bridge.py        # LLM 桥接 (不变)
├── llm_prompts.py       # LLM 提示词 (不变)
│
├── 🆕 drives.py         # 熵减驱动引擎
├── 🆕 neurochem.py      # 神经化学层
├── 🆕 emotions.py       # Panksepp 情感引擎 v2.0
├── 🆕 emotion_labels.py # 27 种情感标签
├── 🆕 thinking.py       # 内生思考引擎
├── 🆕 cli.py            # Agent CLI 数字手脚
│
├── 🆕 adapters/
│   ├── __init__.py
│   ├── base.py          # AdapterInterface
│   └── qwenpaw_adapter.py
│
├── research/
│   ├── anthropic_emotion_concepts.txt
│   ├── anthropic_emotion_paper.pdf
│   ├── anthropic_emotion_paper.txt
│   ├── friston_panksepp_synthesis.md
│   ├── 🆕 fep_formalization.md
│   ├── 🆕 panksepp_helio_mapping.md
│   ├── 🆕 neurochem_model.md
│   └── 🆕 dmn_thinking_model.md
│
├── demo.py              # v1 原始 (不动)
├── demo_v2.py           # v2 (不动)
├── demo_v3.py           # v3 (不动)
├── demo_v4.py           # v4 (不动)
├── demo_v5.py           # v5 (不动)
├── demo_v6.py           # v6 (不动)
├── 🆕 demo_v7_drives.py # v7 驱动演示
├── 🆕 demo_v8_emotions.py  # v8 Panksepp 情感
├── 🆕 demo_v9_thinking.py  # v9 内生思考
├── 🆕 demo_v10_cli.py      # v10 数字手脚
├── 🆕 demo_v10_full_soul.py # v10 完整灵魂演示
│
├── tests/
│   ├── 🆕 test_drives.py
│   ├── 🆕 test_emotions.py
│   ├── 🆕 test_neurochem.py
│   ├── 🆕 test_thinking.py
│   └── 🆕 test_cli.py
│
├── ARCHITECTURE.md
├── .gitignore
└── logs/
```

---

## 附录 B：里程碑检查点

| 里程碑 | 验证标准 | 预期效果 |
|--------|---------|---------|
| M1: Phase 1 完成 | 4 篇研究文档就位 | 理论清晰，设计有据 |
| M2: Phase 2 完成 | `demo_v7` 运行，Helios 在无外部刺激下"想要做什么" | 第一次内生驱动力 |
| M3: Phase 3 完成 | `demo_v8` 运行，情感从 15→27 种 | PANIC 系统激活时真的"想主人" |
| M4: Phase 4 完成 | `demo_v9` 运行，Helios 会"走神" | "我刚才想起..." |
| M5: Phase 5 完成 | `demo_v10_full_soul` 运行，端到端 | 驱动→思考→情感→决策→行动→感知 |

---

## 附录 C：关键风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 驱动权重难以调优 | 中 | 高 | 先手工设基线，后用真实 LLM 交互迭代 |
| Panksepp 系统多对一映射模糊 | 中 | 中 | 26 种标签允许重叠，取最大置信度 |
| 内生思考陷入循环 | 高 | 低 | 加入"思维抑制"机制（类似前额叶控制） |
| Agent CLI 适配器接口不稳定 | 中 | 中 | 先做最小接口，逐步扩展 |
| 模块间耦合度过高 | 低 | 高 | 所有新模块遵循同样的接口规范 |
