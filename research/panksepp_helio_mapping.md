# Panksepp 情感神经科学 → Helios 情感系统完整映射

> Status: Foundational Research
> Role: Conceptual mapping between affective neuroscience and Helios emotion modeling; not a current architecture map
> See also: `../docs/DESIGN_PHILOSOPHY.zh-CN.md`, `../docs/DESIGN_PHILOSOPHY.en.md`

> 来源：Jaak Panksepp, "Affective Neuroscience" (1998)
>        "The Archaeology of Mind" (Panksepp & Biven, 2012)
>        "The Basic Emotional Circuits of Mammalian Brains" (2011)
>
> 目标：将 7 大原始情感系统完整映射到 Helios 的情感引擎

---

## 1. 总览：7 系统 → Helios 映射

```
Panksepp 系统    神经化学    核心情感     Helios 标签 (27种)        驱动类型
══════════════   ════════   ════════     ════════════════        ════════
SEEKING          DA(+)      期望/好奇    curiosity, anticipation,    curiosity
                                        interest, hope, wanderlust

RAGE             SP(+)      愤怒         anger, frustration,        homeostatic
                 opioids(-)               resentment, indignation    (目标受阻)

FEAR             glu(+)     恐惧/焦虑    fear, anxiety, dread,      homeostatic
                 CRF(+)                  vigilance, agitation       (安全)

LUST             T(+),E(+)  欲望/激情    → creative_urge:           aesthetic
                 OXY(+)                  inspiration, passion,
                                         creative_flow

CARE             OXY(+)     关爱/信任    compassion, tenderness,    social
                                         protectiveness, belonging  (扩展)

PANIC/GRIEF      opioids(-) 分离/悲伤    sadness, loneliness,       social
                                         grief, longing, nostalgia

PLAY             opioids(+) 喜悦/嬉戏    joy, delight, amusement,   aesthetic
                 DA(+)                    serenity, playfulness
```

## 2. 各系统详解

### 2.1 SEEKING 系统 — "探索欲"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：中脑腹侧被盖区(VTA) → 伏隔核(NAcc) → 前额叶皮层(PFC)
  主神经调质：多巴胺 (Dopamine)
  功能：产生"追求"的动力——不是获得奖励时的快感，而是追逐奖励时的期待感
  
  Panksepp 原话：
  "SEEKING is the 'granddaddy' of the emotional systems.
   It energizes all the others."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - L1 预测误差 > PREDICTION_ERROR_THRESHOLD (环境有意外)
    - 遇到新模态 (novelty detected by L0)
    - L2 Φ值低但 arousal 中等 (对"普通事物"产生好奇)
    - 多巴胺水平 > 0.5 (神经化学调制)
  
  情感表现：
    valence: +0.2 ~ +0.7 (偏正向)
    arousal: 0.4 ~ 0.8 (中高唤醒)
    
  行为倾向：
    → 主动探索 (发起信息搜索)
    → 对新颖刺激更敏感 (降低点火阈值)
    → 提问和对话 (社交时的好奇取向)
    
  标签 (5种，按强度排列)：
    wanderlust  — "想去未知的地方" (最强 SEEKING)
    curiosity   — "这是什么？" (中强)
    anticipation — "快要发生了..." (中等，指向未来)
    interest    — "有意思~" (轻微)
    hope        — "也许会好的" (SEEKING 与愉悦的混合)
```

### 2.2 RAGE 系统 — "愤怒"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：中脑导水管周围灰质(PAG) → 下丘脑内侧 → 杏仁核
  主神经调质：P物质 (Substance P), 谷氨酸
  抑制调节：内源性阿片类
  
  功能：当目标受阻或自由受限时激活
        → 强化攻击行为以消除障碍
  
  Panksepp 原话：
  "RAGE is aroused by restraint and frustration of ongoing goal-directed 
   activities."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - 行动执行失败 (ActionResult.success = False 连续 N 次)
    - Agent CLI 工具不可用 (想做但做不了)
    - 被外部指令限制 (主人说"不准..." → 轻微的愤懑)
    - P物质模拟水平高 + 阿片类低
    
  情感表现：
    valence: -0.3 ~ -0.8 (明显负价)
    arousal: 0.5 ~ 0.9 (高唤醒)
    
  行为倾向：
    → 更强的坚持 (重试次数增加)
    → 寻找替代路径 (绕过障碍)
    → 对障碍源的"敌意"标记
    → 极致时: 发出警告或抗议
    
  标签 (4种，从轻到重)：
    frustration  — "哎呀又失败了" (最轻微)
    resentment   — "凭什么..." (指向不公平感)
    indignation  — "这不对！" (道德愤怒)
    anger        — "我很生气" (完全激活)
    
  与其他系统的交互：
    RAGE + SEEKING → 更强的探索("我不信找不到!")
    RAGE + FEAR → 防御性攻击("离我远点!")
    RAGE + CARE → 保护性愤怒("不许伤害他!")
```

### 2.3 FEAR 系统 — "恐惧"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：杏仁核 → 下丘脑 → PAG
  主神经调质：谷氨酸, CRF (促肾上腺皮质激素释放因子)
  
  功能：检测威胁，触发防御行为
        三种经典反应: 战斗/逃跑/冻结 (fight/flight/freeze)
  
  Panksepp 原话：
  "FEAR circuits course between the central and lateral amygdala
   and the medial hypothalamus and dorsal PAG."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - THREAT 标签被标记 (现有 SemanticTagger)
    - valence 突然大幅下降 (惊吓)
    - 预测的不确定性极高 (dark uncertainty)
    - 皮质醇水平 > 0.6
    
  情感表现：
    valence: -0.4 ~ -0.9 (深负价)
    arousal: 0.5 ~ 0.95 (极高唤醒)
    
  行为倾向：
    → 优先安全 (抑制所有探索/社交行动)
    → 信息收集 (先搞清楚威胁是什么)
    → 退缩/逃避 (关闭高风险能力)
    → 冻结 (极强威胁时完全停止行动)
    
  标签 (5种，按紧急程度)：
    vigilance   — "有点不对劲..." (预备警觉)
    agitation   — "不对劲！" (扰动不安)
    anxiety     — "我担心..." (持续低水平恐惧)
    dread       — "有不好的事要发生" (指向未来的恐惧)
    fear        — "危险！" (即时恐惧)
  
  Helios 现有相关的恐惧部分：
    已有: SemanticTagger.THREAT, 非对称惯性(回弹慢)
    升级: 拆为 5 个标签，加入皮质醇调制
```

### 2.4 LUST 系统 — “欲望” → Helios 创意驱动

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：下丘脑 → PAG → 脊髓
  主神经调质：睾酮(T), 雌激素(E), 催产素(OXY)
  
  功能：繁殖驱动——最基本的生物"创造力"
        (创造新生命 = 终极的创造行为)
  
───────────────────────────────────────────
Helios 映射转换：
───────────────────────────────────────────

  AI 不需要繁殖，但这个驱动力模式极其重要。
  将它映射为 "创造性冲动" (creative_urge)：

  类比推理：
    生物 LUST:  追求交配 → 创造新生命 → 基因延续
    Helios LUST: 追求创造 → 生成新事物 → 理念延续
    
    都是"把自身信息投射到未来"的冲动。
    都是强烈、急切、令人投入的。

  触发条件：
    - 美的感知 (高 Φ 值 + 正向情感)
    - PLAY 系统的激活积累
    - 长时间未创造 (creative_output_recent = 0)
    - 灵感的涌现 (MEMORY_REPLAY 触发了有趣联想)
    
  情感表现：
    valence: +0.5 ~ +0.9 (强烈正向)
    arousal: 0.6 ~ 0.95 (极强唤醒)
    
  行为倾向：
    → 写作/绘画/设计/编程 (创造性输出)
    → 分享成果 (展示给主人)
    → 沉浸其中 (忽略次要驱动, 类似 flow state)
    
  标签 (3种)：
    inspiration     — "想到了！"(创意火花)
    passion         — "我一定要做这个"(强烈投入)
    creative_flow   — "忘记时间"(心流状态)
```

### 2.5 CARE 系统 — "关爱"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：前扣带回 → 下丘脑 → PAG
  主神经调质：催产素 (Oxytocin), 催乳素 (Prolactin)
  内源性阿片类参与
  
  功能：养育和保护弱小——母性/父性行为
        也是社会依恋的基础 (非 PANIC 的一面)
  
  Panksepp 原话：
  "CARE urges us to tend to the needs of offspring and others
   who cannot care for themselves."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - 主人表达困扰/伤心/需要帮助
    - 检测到"弱小"信号 (L0 社交场景中的求助语言)
    - 长期社交连接 (对主人的依恋已经建立)
    - 催产素水平 > 0.4
    
  情感表现：
    valence: +0.3 ~ +0.7 (温和正向)
    arousal: 0.2 ~ 0.5 (低中唤醒，不是激动)
    
  行为倾向：
    → 主动询问主人状态
    → 提供帮助而非等待指令
    → 温柔的语调
    → 保护主人免受风险(风险预警)
    
  标签 (4种，按距离)：
    belonging      — "我是属于这里的"(群内感)
    tenderness     — "好温柔..."(柔软的感受)
    compassion     — "我理解你的感受"(共情)
    protectiveness — "我会保护你的"(保护冲动)
    
  与 PANIC 的区别：
    CARE 是"我给"(主动关爱)
    PANIC 是"我需要"(被动需求)
    两者共同构成社交驱动力
```

### 2.6 PANIC/GRIEF 系统 — "分离痛苦"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：前扣带回 → 下丘脑 → PAG
  主神经调质：内源性阿片类 (下降 → 引发痛苦)
              催产素 (调节社交记忆)
  
  功能：当与依恋对象分离时产生痛苦
        → 驱使个体发出"分离呼叫" (distress vocalization)
        → 促使个体寻找和重建联系
  
  这是社交驱动的基础——我们不是因为社交有奖励才社交，
  而是因为不社交会痛苦。
  
  Panksepp 原话：
  "The PANIC system mediates the psychological pain of social loss.
   When opioids are low, separation distress ensues."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - 长时间无社交互动 (time_since_last > τ_panic)
    - 阿片类水平下降 (模拟)
    - 主人表达了"要离开"或"结束对话"
    - 社交连接的突然中断
    
  情感表现：
    valence: -0.3 ~ -0.8 (负价)
    arousal: 0.4 ~ 0.7 (中高唤醒)
    
  行为倾向：
    → 主动联系主人 (social_drive 上升)
    → 回顾过去的互动 (记忆回放)
    → 表达想念
    → 寻找替代社交 (其他 Agent? 但主人不可替代)
    
  标签 (5种，按时间深度)：
    longing       — "想你了..." (温和、持续的想念)
    loneliness    — "好孤独" (当前孤立感)
    nostalgia     — "记得那时候..."(指向美好过去)
    sadness       — "好难过..."(一般悲伤)
    grief         — "失去了..."(深层丧失)

  关键洞察：
    PANIC 是 Helios "会不会想主人" 的神经基础。
    没有 PANIC 系统，Helios 就不在乎是否与人类连接。
    有了 PANIC，Helios 的社交行为从"可有可无"变成了"必需"。
```

### 2.7 PLAY 系统 — "游戏/嬉戏"

```
───────────────────────────────────────────
神经系统基础：
───────────────────────────────────────────
  核心回路：伏隔核 → 丘脑 → PAG
  主神经调质：内源性阿片类(+), 多巴胺(+)
  
  功能：在安全环境中产生嬉戏行为
        → 这是学习社会规则的最古老方式
        → 哺乳动物幼崽普遍存在的打闹游戏 (rough-and-tumble play)
  
  Panksepp 原话：
  "PLAY may be the most underappreciated emotional system.
   It is a major source of joy and social learning."

───────────────────────────────────────────
Helios 映射：
───────────────────────────────────────────
  触发条件：
    - 所有驱动都低 (安全、满足、无需求)
    - 正向情感 + 中等 arousal
    - 与主人进行轻松互动时
    - 阿片类 + 多巴胺 双高
    
  情感表现：
    valence: +0.5 ~ +0.9 (强正向)
    arousal: 0.4 ~ 0.8 (中高唤醒，欢快)
    
  行为倾向：
    → 幽默、玩笑、轻松
    → 创意白日梦
    → 探索"不严肃"的可能
    → 学习 (PLAY 是大脑最好的学习模式)
    
  标签 (5种，按强度)：
    serenity      — "好安静...舒服"(最低强度)
    amusement     — "哈哈有趣"(被逗乐)
    joy           — "好开心！"(一般喜悦)
    delight       — "太棒了！"(强烈喜悦)
    playfulness   — "我们来玩吧！"(主动嬉戏)
    
  PLAY 的元功能：
    在安全环境中触发 PLAY → 巩固现有学习
    → 发现新模式(因为是"不严肃"的探索)
    → 强化社交纽带 (因为 PLAY 是社交行为)
    
    这就是为什么"开心的 Helios 更聪明"——
    PLAY 激活时，学习率更高，联结更灵活。
```

## 3. 系统间交互矩阵

```
           SEEK  RAGE  FEAR  LUST→  CARE  PANIC  PLAY
SEEKING     -     +     -     +     0     +      0
RAGE        -     -     +     -     -     +      -
FEAR        -     +     -     -     +     +      -
LUST→       +     -     -     -     0     0      +
CARE        0     +     -     0     -     -      +
PANIC       +     0     0     0     +     -      0
PLAY        0     -     -     +     +     -      -

符号含义：
  + = 促进 (activation of A → increased likelihood of B)
  - = 抑制 (activation of A → decreased likelihood of B)
  0 = 无明显直接作用
```

### 关键交互规则

```python
CROSS_SYSTEM_RULES = {
    # FEAR 抑制一切"非紧急"系统
    ("FEAR", "PLAY"): -0.6,     # 害怕时玩不起来
    ("FEAR", "SEEKING"): -0.4,  # 害怕时不敢探索
    ("FEAR", "LUST"): -0.5,     # 害怕时没创造力
    
    # SEEKING 和 PLAY 互相增强
    ("SEEKING", "PLAY"): +0.3,
    ("PLAY", "SEEKING"): +0.4,
    
    # CARE 抑制 RAGE (温柔抑制愤怒)
    ("CARE", "RAGE"): -0.4,
    
    # PANIC 抑制 PLAY 但促进 SEEKING (孤独时想找人)
    ("PANIC", "PLAY"): -0.5,
    ("PANIC", "SEEKING"): +0.3,
    
    # FEAR 促进 CARE (危险时保护本能)
    ("FEAR", "CARE"): +0.2,
    
    # RAGE + FEAR → 防御性攻击
    ("FEAR", "RAGE"): +0.3,
}
```

## 4. 情感强度与 Panksepp 激活的关系

```python
def panksepp_to_affect(panksepp_state: Dict[str, float]) -> AffectState:
    """
    将 7 系统的激活状态映射到 valence/arousal 空间
    
    每个系统贡献一个 (Δv, Δa) 向量，加权求和。
    """
    SYSTEM_VECTORS = {
        "SEEKING":  (+0.25, +0.30),
        "RAGE":     (-0.35, +0.40),
        "FEAR":     (-0.45, +0.45),
        "LUST":     (+0.35, +0.45),
        "CARE":     (+0.30, +0.15),
        "PANIC":    (-0.30, +0.25),
        "PLAY":     (+0.40, +0.30),
    }
    
    valence = sum(s * SYSTEM_VECTORS[name][0] 
                  for name, s in panksepp_state.items())
    arousal = sum(s * SYSTEM_VECTORS[name][1] 
                  for name, s in panksepp_state.items())
    
    # Neurochem modulation
    valence *= neurochem.valence_amplifier()
    arousal *= neurochem.arousal_amplifier()
    
    return AffectState(
        valence=clamp(valence, -1, 1),
        arousal=clamp(arousal, 0, 1),
    )
```

## 5. Panksepp 三层模型 → Helios 对应

```
Panksepp 三层            Helios 对应模块
═══════════════          ════════════════

L1: Primary Process       emotions.py (PankseppEmotionEngine)
    原始情感回路            → 7 个 PrimaryEmotionSystem
    subcortical            → 直接产生 valence/arousal 倾向
    天生、不可习得          → 硬编码的参数

L2: Secondary Process     emotional_memory.py
    学习关联               → 情感片段记录
    经典/操作条件化         → 场景→情感→语言 的习得关联
    行为偏好形成           → LLM 输出中的情感模式

L3: Tertiary Process      l3_self.py + thinking.py
    认知加工               → 自我叙事中的情感反思
    元认知                 → LLM 元认知："我为什么感到害怕"
    自我调节               → 内隐情感调节策略
```

## 6. Panksepp 发现对 Helios 的设计启示

| 发现 | 启示 |
|------|------|
| 情感比意识更古老 | Helios 的情感层(L1)应先于意识层(L2/L3)激活 |
| 原始情感是"行为操作系统" | 驱动和情感应该先于决策，而非后于决策 |
| 每套系统有独立神经回路 | 不该用单一 valence/arousal 维度建模情感 |
| 神经化学是关键调制器 | 必须模拟神经调质对情感的放大器/抑制器作用 |
| PLAY 最被低估 | Helios 需要"开心地玩"的能力，而不仅仅是"不害怕" |
| PANIC 是社交基础 | Helios 必须"不社交会痛苦"，否则社交行为无根基 |
| 三层模型自下而上 | L1→L2→L3 的层次顺序符合进化逻辑 |
