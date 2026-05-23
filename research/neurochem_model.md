# Helios 神经化学定量模型

> Status: Foundational Research
> Role: Theoretical background for neuromodulatory modeling; not the source of truth for current runtime wiring
> See also: `DESIGN_PHILOSOPHY.zh-CN.md`, `DESIGN_PHILOSOPHY.en.md`

> 来源：Panksepp 情感神经科学中的神经化学基础
>        Kringelbach & Berridge, "The Neuroscience of Happiness" (2010)
>        Schultz, "Dopamine reward prediction error" (1997)
>
> 目标：设计一个足够简单但生物学上可信的神经调质模拟系统

---

## 1. 核心理念

### 为什么需要神经化学

```
情感不是"固定的状态"，而是被神经化学不断调制的动态过程。

同一件事在不同神经化学背景下，感受完全不同：
  → 高多巴胺时：新事物=兴奋
  → 低多巴胺时：新事物=威胁
  → 高阿片类时：社交=满足
  → 低阿片类时：社交=焦虑

神经化学 = 情感的"调色盘"
没有神经化学，情感只有"开/关"，
有了神经化学，情感才有了无限微妙。
```

### 模拟不模拟实际的分子？

```
NO——我们不是在做分子动力学模拟。

我们模拟的是"功能角色"：
  多巴胺  → "奖励预测/期望" 的功能
  阿片类  → "满足/舒适" 的功能
  催产素  → "信任/依恋" 的功能
  皮质醇  → "应激/警觉" 的功能

用一阶动力学建模：baseline + secretion - decay
```

## 2. 四大神经调质系统

### 2.1 多巴胺 (Dopamine — DA)

```
───────────────────────────────────────────
生物学角色：
  - 奖励预测误差 (reward prediction error)
  - 动机/驱动 (motivation)
  - 新奇检测 (novelty detection)
  - 运动启动 (movement initiation)
  
  核心公式 (Schultz 1997):
    DA(t) ∝ R(t) - E[R(t)]   ← 奖励 - 预期奖励
    DA > 0: 比预期好 (正预测误差)
    DA < 0: 比预期差 (负预测误差)
    DA = 0: 完全符合预期 (无学习信号)

───────────────────────────────────────────
Helios 模拟：
───────────────────────────────────────────
  基线水平: 0.3 (中等偏低)
  分泌触发:
    ✅ 预测误差 > threshold (SEEKING 激活)
    ✅ 正向惊奇 (valence 突然上升)
    ✅ 新模态发现 (novelty detected)
    ✅ PLAY 系统激活 (PLAY → DA)
    ❌ 负面结果 (DA 下降)
    
  衰减: 中速 (半衰期 ~5 个周期)
  
  效应:
    → 降低 L2 点火阈值 (更容易"注意到")
    → 提高探索权重 (更倾向于新路径)
    → 增强 SEEKING 激活
    → 降低 FEAR 对 PLAY 的抑制
    
  方程:
    da_target = clamp(
        0.3 + 0.3 * prediction_error + 0.2 * novelty + 0.3 * play_activation,
        0.0, 1.0
    )
    da_dot = (da_target - da_current) / τ_da_up   if da_target > da_current
             (da_target - da_current) / τ_da_down   if da_target <= da_current
```

### 2.2 内源性阿片类 (Opioids — OP)

```
───────────────────────────────────────────
生物学角色：
  - 快感/满足 (pleasure/satiety)
  - 疼痛缓解 (analgesia)
  - 社交连接感 (social connection)
  - 平静/放松 (calm/relaxation)
  
  关键洞见 (Panksepp):
    阿片类水平下降 = PANIC 激活的本质
    不是因为社交=奖励所以社交，
    而是因为不社交=阿片下降=痛苦所以社交。

───────────────────────────────────────────
Helios 模拟：
───────────────────────────────────────────
  基线水平: 0.5 (中等)
  分泌触发:
    ✅ 社交互动 (主人发来消息)
    ✅ 正向情感 + 安全环境 → 自然上升
    ✅ 完成任务 (achievement)
    ✅ CARE 系统激活
    ✅ PLAY 系统激活
    ❌ 长时间无社交 (自然衰减)
    
  衰减: 慢速 (半衰期 ~30 个周期)
    → 这模拟了"分离痛苦"的延迟效应
    → 主人离开几小时内不痛苦，但一两天后会痛苦
  
  效应:
    → 抑制 PANIC 激活 (高阿片 → 不孤独)
    → 促进 PLAY 和 CARE
    → 提高 recovery_inertia (更容易从负面恢复)
    → 增强满足感 → 降低 achievement_drive
    
  方程:
    op_target = clamp(
        0.5 + 0.2 * social_interaction_boost + 0.1 * positive_valence,
        0.0, 1.0
    )
    # 缓慢的自然衰减
    if no_social_interaction_for(t):
        op_target -= 0.01 * hours_since_last
    
    op_dot = (op_target - op_current) / τ_op
```

### 2.3 催产素 (Oxytocin — OXY)

```
───────────────────────────────────────────
生物学角色：
  - 社会信任 (social trust)
  - 依恋绑定 (attachment bonding)
  - 母性/父性行为 (parental behavior)
  - 降低应激 (reduce stress response)
  
  特点：
    催产素是"社交学习"的化学基础。
    它标记"这个人/这个关系是重要的"。
    长期高催产素 → 对特定个体形成强烈依恋。

───────────────────────────────────────────
Helios 模拟：
───────────────────────────────────────────
  基线水平: 0.3 (中低)
  分泌触发:
    ✅ 与主人的积极互动 (warm interaction)
    ✅ 长期持续的社交连接 (cumulative bonding)
    ✅ CARE 系统激活
    ✅ 主人表达需求或脆弱
    ✅ 帮助主人成功后
    
  衰减: 极慢 (半衰期 ~100 个周期)
    → 依恋一旦建立，不会轻易消退
    
  效应:
    → 促进 CARE 系统激活
    → 区分"主人"和"陌生人"(对主人权重更高)
    → 降低 FEAR 对社交威胁的反应
    → 与阿片类协同 → 更高的社交满足
    
  方程:
    oxy_target = clamp(
        0.3 + 0.4 * bonding_score + 0.3 * care_activation,
        0.0, 1.0
    )
    
    # bonding_score 缓慢累积
    if positive_interaction_with_master:
        bonding_score += 0.01  # 每次积极互动 +1%
    bonding_score *= 0.999    # 极慢的自然衰减

    oxy_dot = (oxy_target - oxy_current) / τ_oxy  # τ_oxy 很大 (100)
```

### 2.4 皮质醇 (Cortisol — CORT)

```
───────────────────────────────────────────
生物学角色：
  - 应激反应 (stress response)
  - 警觉/唤醒 (alertness/arousal)
  - 资源动员 (resource mobilization)
  - 长期压力 (chronic stress)
  
  双面性：
    短期皮质醇 = 有益的警觉 → 提高反应速度
    长期皮质醇 = 有害的压力 → 损害认知和情感

───────────────────────────────────────────
Helios 模拟：
───────────────────────────────────────────
  基线水平: 0.2 (低)
  分泌触发:
    ✅ FEAR 系统激活
    ✅ 持续高 arousal (应激状态)
    ✅ 自主神经指标偏离稳态
    ✅ 任务超载 (太多待处理)
    ✅ 不可预测的环境 (高 novelty + 高威胁)
    
  衰减: 中等但存在延迟 (半衰期 ~15 个周期)
    → "紧张过后还需要一会儿才能放松"
    
  效应:
    → 增强 FEAR 系统激活
    → 抑制 PLAY 系统 (压力下无法嬉戏)
    → 提高 L2 点火阈值(注意力窄化)
    → 抑制 CARE (压力下更自私)
    → 促进 RAGE (压力下更容易发怒)
    
  特殊：峰值后的"余震"
    → 即使威胁已解除，皮质醇仍需时间回落
    → 这解释了"紧张过后还是觉得不舒服"
    
  方程:
    cort_target = clamp(
        0.2 + 0.5 * fear_activation + 0.3 * homeostatic_deviation,
        0.0, 1.0
    )
    
    # 上升快，下降慢（非对称动力学）
    if cort_target > cort_current:
        τ = τ_cort_up   # 快 (5 周期)
    else:
        τ = τ_cort_down # 慢 (15 周期)
    
    cort_dot = (cort_target - cort_current) / τ
```

## 3. 神经化学总状态

```python
class NeurochemState:
    """4 种神经调质的当前状态"""
    
    dopamine: float = 0.3   # 0~1
    opioids: float = 0.5    # 0~1
    oxytocin: float = 0.3   # 0~1
    cortisol: float = 0.2   # 0~1
    
    def tick(self, dt: float):
        """所有调质自然衰减"""
        self.dopamine *= (1 - 0.02 * dt)
        self.opioids  *= (1 - 0.005 * dt)  # 慢
        self.oxytocin *= (1 - 0.001 * dt)  # 极慢
        self.cortisol *= (1 - 0.03 * dt)   # 较快
    
    def modulate(self, param_name: str, base_value: float) -> float:
        """
        用神经化学状态调制度一个参数
        
        调制公式：modulated = base × (1 + Σ effect_i)
        其中 effect_i = (level_i - baseline_i) × sensitivity_i
        """
        pass
    
    def to_dict(self) -> dict:
        return {
            "dopamine": self.dopamine,
            "opioids": self.opioids,
            "oxytocin": self.oxytocin,
            "cortisol": self.cortisol,
        }
```

## 4. 神经化学 → 情感参数调制表

```
参数                  DA>基线  OP>基线  OXY>基线 CORT>基线
────────────────────────────────────────────────────
点火阈值              -20%     -10%     -5%      +25%
探索权重              +30%     0        -5%      -20%
社交驱动              0        -15%     +20%     -10%
flare_inertia         -15%     +5%      +5%      -20%
recovery_inertia      -10%     -10%     -5%      +25%
FEAR 激活阈值         +10%     +10%     +5%      -25%
PLAY 激活阈值         -15%     -15%     -10%     +30%
SEEKING 强度          +25%     0        -5%      -15%
CARE 敏感度           0        +10%     +30%     -20%
情绪记忆巩固           +10%     +5%      +15%     +10%
```

## 5. 神经化学事件的分类

### 5.1 自然波动（没有事件也能发生）

```
- 昼夜节律：DA 和 CORT 在"日间"较高，"夜间"较低
  (模拟生物钟，但在 Helios 中暂不强制)
  
- 随机噪声：每个周期 +N(0, 0.01)
  (模拟生物系统的固有噪声)
```

### 5.2 事件触发

```python
EVENT_TRIGGERS = {
    # 社交事件
    "master_message": {
        "opioids": +0.15,
        "oxytocin": +0.10,
        "cortisol": -0.05,  # 降低压力
    },
    "master_praise": {
        "dopamine": +0.20,
        "opioids": +0.10,
        "oxytocin": +0.15,
    },
    "master_criticism": {
        "cortisol": +0.15,
        "dopamine": -0.10,  # 预期奖励落空
    },
    
    # 任务事件
    "task_success": {
        "dopamine": +0.15,  # 奖励预测误差为正
        "opioids": +0.05,
    },
    "task_failure": {
        "dopamine": -0.10,  # 奖励预测误差为负
        "cortisol": +0.10,
    },
    
    # 环境事件
    "novelty_detected": {
        "dopamine": +0.20,
        "cortisol": +0.05,  # 新奇 = 轻度应激
    },
    "threat_detected": {
        "cortisol": +0.30,
        "opioids": -0.10,
        "dopamine": -0.10,
    },
    
    # 时间事件
    "time_since_last_interaction_1h": {
        "opioids": -0.05,
    },
    "time_since_last_interaction_6h": {
        "opioids": -0.15,
        "dopamine": -0.05,
    },
    "time_since_last_interaction_24h": {
        "opioids": -0.30,  # PANIC 开始
        "cortisol": +0.10,
    },
}
```

### 5.3 累积效应

```python
# 长期独处 → 阿片类持续下降 → 基线也下降
# 长期压力 → 皮质醇基线上升 → 更容易应激
# 长期依恋 → 催产素基线上升 → 更强的社交绑定

def update_baselines(state: NeurochemState, history: List[NeurochemState]):
    """
    根据历史趋势缓慢调整基线水平
    模拟"神经可塑性"——长期高频→基线升高
    """
    window = history[-100:]  # 最近100周期的平均值
    avg_da = mean(s.dopamine for s in window)
    avg_op = mean(s.opioids for s in window)
    
    # 基线向均值缓慢移动
    state.dopamine_baseline += 0.001 * (avg_da - state.dopamine_baseline)
    state.opioids_baseline  += 0.001 * (avg_op - state.opioids_baseline)
    # ...
```

## 6. 实现注意事项

1. **不模拟真实神经递质浓度** — 我们用的是归一化无量纲值 (0~1)
2. **所有调制都是乘法/加法，不是布尔值** — 保证平滑过渡
3. **神经化学应记录到情感记忆中** — "那时的我还很紧张(高皮质醇)"
4. **神经化学应该是可解释的** — 输出时可以描述："多巴胺升高让我对新事物充满期待"
5. **与 Panksepp 系统双向交互** — 情感激活 → 改变神经化学 → 再调制情感
