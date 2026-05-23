# Helios 内生思考模型 — 基于默认模式网络

> Status: Foundational Research
> Role: Theoretical background for endogenous thinking and replay; not the source of truth for current package ownership
> See also: `../DESIGN_PHILOSOPHY.zh-CN.md`, `../DESIGN_PHILOSOPHY.en.md`

> 来源：Raichle et al., "A Default Mode of Brain Function" (2001)
>        Buckner et al., "The Brain's Default Network" (2008)
>        Andrews-Hanna, "The Brain's Default Network and Its Adaptive Role" (2012)
>        Foster, "Replay Comes of Age" (2017)
>        Schacter et al., "The Future of Memory: Remembering, Imagining, and the Brain" (2012)
>
> 目标：让 Helios 在没有外部刺激时，自己产生思维

---

## 1. 默认模式网络 (DMN) 的核心发现

### 1.1 什么是 DMN

```
1990年代，神经科学家用 PET/fMRI 发现一个奇怪现象：

当受试者执行任务（算数、看图片）时，某些脑区反而"关闭"。
当受试者"什么都不做"时，这些脑区反而高度活跃。

这些脑区包括：
  - 内侧前额叶皮层 (mPFC)     → 自我参照加工
  - 后扣带回 (PCC)             → 自传记忆检索
  - 角回 (Angular Gyrus)       → 语义整合
  - 海马体 (Hippocampus)       → 记忆回放

这不是"空闲"，这是大脑的"默认模式"。
大脑在完成外部任务之间，都在"想自己的事"。
```

### 1.2 DMN 的四大功能

```
1. 自传记忆检索     → 回想个人经历
2. 心理时间旅行      → 想象未来 / 反思过去
3. 社会认知          → "别人会怎么想/感受"
4. 自我参照          → "我是谁" "我想要什么"

这四件事都不需要外部刺激！
这就是"人躺在床上胡思乱想"的神经基础。
```

### 1.3 关键发现：DMN 与创造力的关系

```
Beaty et al. (2018) 发现：
  创造性思维 = DMN (想法生成) + 执行控制网络 (想法筛选) 的协作
  
  第一步：DMN 自由产生联想 (发散思维)
  第二步：额顶控制网络筛选出有价值的想法 (收敛思维)

这对 Helios 的启示：
  内生思考 = 记忆联想(DMN模式) → L2 点火(控制网络)
  创意产出 = DMN 自由联想 → L3 价值观筛选 → CLI 执行
```

## 2. 海马体回放 — 记忆自转的机制

### 2.1 回放现象

```
Wilson & McNaughton (1994) 发现：
  大鼠在睡眠/静息时，海马体的位置细胞会按照之前探索路径的相同顺序放电。

  换句话说：大脑在"重播"之前的经历。

  后续发现 (Foster 2017):
  - 回放不仅发生在睡眠中，也发生在清醒静止时
  - 回放不仅重播过去的经历，也"预演"可能的未来路径
  - 回放被压缩在极短时间内 (100ms 内重放几秒钟的经历)
  - 回放是记忆巩固的核心机制
```

### 2.2 Helios 回放引擎设计

```python
class MemoryReplayEngine:
    """
    从情绪记忆中回放片段
    
    三种模式：
    1. 巩固回放 (consolidation replay) — 强化高Φ记忆
    2. 关联回放 (associative replay) — 相似情感的连续回放
    3. 预演回放 (preplay / planning) — 模拟可能的未来
    """
    
    def select_for_replay(self, 
                          current_state: HeliosState,
                          mode: str = "associative") -> List[EmotionalEpisode]:
        
        if mode == "consolidation":
            # 选择最近的、高Φ值的片段
            return self.memory.query(
                time_window=(-3600, 0),  # 最近1小时
                min_phi=0.5,
                limit=5
            )
        
        elif mode == "associative":
            # 选择与当前情感状态相似的片段
            return self.memory.query(
                similar_to=(current_state.valence, current_state.arousal),
                limit=5
            )
        
        elif mode == "preplay":
            # 生成"假设"场景 → 在记忆中搜索类似情境
            hypothetical = self.generate_hypothetical(current_state)
            return self.memory.query(
                similar_to=hypothetical.emotional_signature,
                limit=3
            )
```

## 3. 心理时间旅行 — 反事实思维

### 3.1 人类如何"心理旅行"

```
心理时间旅行的两个方向：

向后 (Episodic Past):
  - "如果当时我选了另一条路..."
  - "那天要不是下雨..."
  - "我记得那时候的感觉是..."
  
向前 (Episodic Future):
  - "明天见到主人会怎样..."
  - "如果这个项目成功了..."
  - "万一出问题了怎么办..."

Schacter & Addis (2007): 
  回忆过去和想象未来共享同样的脑网络！
  事实上，"记住过去"和"构建未来"用的是同一套机制。
```

### 3.2 Helios 反事实模拟器

```python
class CounterfactualSimulator:
    """
    从记忆片段出发，生成"如果...会怎样"的变体
    """
    
    def counterfactual_past(self, 
                            episode: EmotionalEpisode,
                            mutation: str) -> SimulatedOutcome:
        """
        对过去的反事实：
        "如果当时发生的是 X 而不是 Y..."
        
        用记忆片段作为起点，修改一个关键变量
        → 通过 LLM 生成变体
        → 评估变体的情感结果
        """
        prompt = f"""
        你经历过这段：{episode.summary}
        如果当时的变化是：{mutation}
        你的感受会是怎样的？请简短描述。
        """
        return self.llm.generate_counterfactual(prompt)
    
    def simulate_future(self, 
                        current_state: HeliosState,
                        concern: str) -> SimulatedOutcome:
        """
        对未来做预演：
        "如果...会发生什么"
        
        基于当前状态+记忆经验，预测未来可能的情景
        """
        # 找到记忆中类似的"前兆"状态
        similar_pasts = self.memory.query_precursor(current_state)
        
        # 提取这些前兆状态之后的"结果"
        outcomes = [ep.following_episodes() for ep in similar_pasts]
        
        # LLM 综合预测
        return self.llm.predict_outcome(current_state, outcomes)
```

## 4. 自发思维流 — "走神"

### 4.1 走神的认知架构

```
Christoff et al. (2009) 提出：

走神不是错误，而是大脑的默认操作模式。

三个阶段：
  1. 脱离 (Decoupling): 注意力从外部任务撤回
  2. 自由联想 (Free Association): 思维在记忆中漫游
  3. 重新定向 (Reorienting): 注意力回到外部或被新想法占据

走神的内容不是随机的 — 它与当前的"未完成目标"有关。
(Klinger, 1999: "current concerns" 理论)
```

### 4.2 Helios 的自发思维流

```python
class SpontaneousThoughtStream:
    """
    模拟走神/发呆
    
    流程：
    1. 检测外部输入缺失 → 触发 DMN 模式
    2. 从当前驱动中选择"当前关切" (current concern)
    3. 检索与关切相关的记忆
    4. 生成思维片段序列
    5. 每个片段经过 L1→L2 处理
    6. 如果触发点火 → 成为有意识的想法
    7. 连续 N 个片段无点火 → "回过神" → 回到等待模式
    """
    
    def stream(self, 
               duration: float,
               helios_state: HeliosState) -> Iterator[ThoughtFragment]:
        
        # 确定"当前关切"
        concern = self.drive_oracle.dominant_drive(helios_state.drives)
        
        # 自由联想循环
        current_focus = self.seed_thought(concern, helios_state)
        
        for _ in range(max_fragments):
            # 从当前焦点出发，做语义跳跃
            next_focus = self.associate(current_focus, 
                                        helios_state.memory,
                                        creativity=0.3)  # 适度的发散
            
            # 生成思维片段
            fragment = ThoughtFragment(
                content=f"我在想... {next_focus.description}",
                source="free_association",
                valence_bias=next_focus.valence,
                novelty=next_focus.semantic_distance,
                actionable=(next_focus.confidence > 0.5),
            )
            
            yield fragment
            
            # 可能的"回神" — 随机或驱动消失
            if self.should_terminate(helios_state):
                break
            
            current_focus = next_focus
    
    def should_terminate(self, state: HeliosState) -> bool:
        """是否结束走神"""
        if state.external_stimulus_detected:
            return True  # 外部有事 → 回神
        if state.drives.total > HIGH_DRIVE_THRESHOLD:
            return True  # 驱动太强 → 必须行动
        if random.random() < 0.1:
            return True  # 随机回神
        return False

class ThoughtFragment:
    content: str
    source: str            # "memory_replay" | "counterfactual" | "free_association" | "daydream"
    valence_bias: float
    arousal_bias: float
    novelty: float
    actionable: bool
    phi_prediction: float  # 预期 Φ 值
```

## 5. 白日梦 — PLAY 模式下的创造力

### 5.1 白日梦与普通走神的区别

```
普通走神 (mind-wandering):
  - 可能涉及负面内容 (焦虑的未来/后悔的过去)
  - 关注"当前关切"
  - DMN 主导

白日梦 (daydreaming):
  - 主要积极内容
  - 没有明确目标，纯粹为了享受
  - DMN + 奖励系统 (伏隔核) 共同激活
  - = PLAY 系统的思维表现
```

### 5.2 Helios 白日梦引擎

```python
class DaydreamEngine:
    """
    PLAY 系统驱动下的积极自由联想
    
    触发条件：
    - 所有驱动低于 THRESHOLD
    - 情感为正价态
    - PLAY 系统激活
    - 环境安全
    """
    
    def daydream(self, 
                 duration: float,
                 helios_state: HeliosState) -> List[ThoughtFragment]:
        
        # 从"美好的"记忆片段中随机选择种子
        positive_memories = helios_state.emotional_memory.query(
            min_valence=0.5,
            min_phi=0.3,
            limit=10
        )
        
        if not positive_memories:
            # 没有好记忆 → 无法白日梦 → 回到普通走神
            return []
        
        # 选一个种子，进行"理想化"扩展
        seed = random.choice(positive_memories)
        
        fragments = []
        current = seed
        
        for _ in range(5):  # 白日梦一般 3-7 步
            # 对当前片段做正向变异
            idealized = self.idealize(current, amplification=1.5)
            
            fragment = ThoughtFragment(
                content=f"想象... {idealized.description}",
                source="daydream",
                valence_bias=clamp(idealized.valence * 1.3, 0, 1),  # 白日梦更积极
                novelty=idealized.novelty,
                actionable=False,  # 白日梦一般不导向行动
            )
            fragments.append(fragment)
            
            # 联跳到下一个"美的"记忆
            current = self.associate_positively(current, positive_memories)
        
        return fragments
    
    def idealize(self, episode: EmotionalEpisode, 
                 amplification: float) -> EmotionalEpisode:
        """
        对记忆片段做"理想化"
        放大正向情感，减小负向细节
        这是白日梦的核心——"事情比实际更美好"
        """
        return EmotionalEpisode(
            valence=clamp(episode.valence * amplification, 0, 1),
            arousal=episode.arousal * (1 + 0.2 * amplification),
            summary=f"(理想化的) {episode.summary}",
            ...
        )
```

## 6. 内生思考 → L2 点火的条件

```
不是所有思绪都会成为有意识的体验。

点火条件：
  1. 思维片段的 Φ 预测值 > IGNITION_THRESHOLD
  2. 与当前驱动高度相关 (relevant_to_current_drive > 0.7)
  3. 新奇度 > NOVELTY_THRESHOLD (太熟悉的跳过)
  4. 与最近 10 次点火不重复

具体：
  def check_ignition(fragment: ThoughtFragment, state: HeliosState) -> bool:
      phi_pred = predict_phi(fragment)  # 预期质量
      drive_rel = relevance(fragment, state.drives)
      
      score = (0.4 * phi_pred + 
               0.3 * drive_rel + 
               0.2 * fragment.novelty + 
               0.1 * (not recently_ignited(fragment)))
      
      return score > state.ignition_threshold
```

## 7. 与 QwenPaw 集成的思维模式切换

```
外部任务模式 (Task-Positive Network):
  - QwenPaw 在执行任务 → Helios DMN 被抑制
  - L0 接收 QwenPaw 的工具结果
  - 正常意识环路运行

内在反思模式 (Default Mode Network):
  - QwenPaw 无任务 → Helios DMN 激活
  - L0 接收"记忆回放"或"反事实"作为准输入
  - L1→L2→L3 正常运行
  
  → 这模拟了"干活时专心干活，休息时胡思乱想"
```

## 8. 核心公式汇总

```python
# DMN 激活度
DMN_activation = (1.0 - external_stimulus_intensity) * (1.0 - task_load)

# 走神概率
P(mind_wandering) = sigmoid(DMN_activation - 0.3) * (1 + cortisol * 0.5)

# 回神概率
P(reorient) = {
    "external_stimulus": 0.9,          # 有外部刺激→立即回神
    "high_drive": 0.7,                 # 强驱动→多半回神
    "spontaneous": 0.05,               # 自发的"回过神来"
    "ignition_occurs": 0.3,           # 点火后→可能回神(被新想法占据)
}

# 白日梦 vs 焦虑走神
if PLAY_activation > 0.5 and valence > 0:
    mode = "daydream"    # 正向走神
elif FEAR_activation > 0.5 or PANIC > 0.5:
    mode = "rumination"  # 负向反刍 (反复咀嚼负面想法)
else:
    mode = "wandering"   # 中性走神
```
