# Helios 情感系统 — 研究框架与重新设计

## 当前问题诊断

V2.3-V2.5 暴露的根本缺陷：

```
问题                   根因                          表现
────────────────────────────────────────────────────────────
摆锤效应              winner-take-all 为主导判定     94%→86%→63%
阈值不平等            不同系统阈不同导致先天优势
缺乏共激活建模        只有一个"dominant_system"        
缺乏情感时序动力学    无 rise/peak/decay 时间结构
缺乏双向稳态调节      只有抑制没有促进                     负向系统归零
无情绪-心境区分       短时情绪和长时心境混为一谈
无个体差异参数        所有系统对称化处理
```

## 需要研究的核心文献

### 1. 情感计算模型

| 模型 | 核心贡献 | 与 Helios 的关系 |
|------|---------|-----------------|
| **EMA** (Gratch & Marsella, 2004) | 基于 appraisal 的因果归因 | 事件→评估→情感 链路 |
| **WASABI** (Becker-Asano, 2008) | PAD 空间 + 情绪衰减 | 三维情感空间替代 V/A |
| **FAtiMA** (Dias et al., 2014) | OCC 评估 + 情绪调节 | 评估→情感→行动 |
| **FLAME** (El-Nasr, 2000) | 模糊逻辑情感建模 | 多情感共激活 |
| **ALMA** (Gebhard, 2005) | 情绪-心境-个性三层 | 短/中/长期情感分离 |

### 2. 情感神经科学

| 理论 | 核心概念 | 实现方向 |
|------|---------|---------|
| **Panksepp (1998)** | 7 原始情感系统 | 已有，需优化动力学 |
| **LeDoux (2000)** | 双通路 (快/慢) | 事件双通道处理 |
| **Damasio (1994)** | 躯体标记假说 | 情感标记驱动决策 |
| **Davidson (2000)** | 情感风格 (chronometry) | 时间参数 (rise/peak/recovery) |
| **Pessoa (2013)** | 情感-认知交互 | 情感调制注意力/记忆 |

### 3. 情感动力学

| 理论 | 核心公式/概念 | 实现方向 |
|------|-------------|---------|
| **Russell (1980)** | Circumplex (V×A 圆环) | 连续情感空间 |
| **Solomon (1974)** | Opponent-Process | a-process + b-process 对消 |
| **Gross (2015)** | 情绪调节策略 | 认知重评/注意部署 |
| **Kuppens (2010)** | 情感惯性 (inertia) | 自回归系数 |
| **Larsen (2000)** | 情感强度/频率分离 | 独立参数 |

### 4. 稳态/异稳态调节

| 理论 | 核心概念 | 实现方向 |
|------|---------|---------|
| **Sterling (1988)** | Allostasis | 预测性稳态调节 |
| **McEwen (1998)** | Allostatic Load | 累积疲劳 |
| **Friston (2010)** | Free Energy / Active Inference | 已有 drives.py |

## 新架构方向：DAISY 模型（初稿）

**D**ynamic **A**llostatic **I**ntegrated **S**ystem for emotion**Y**namics

### 核心原则

1. **共激活 (Co-activation)**
   - 所有 7 系统永远同时活跃，只是强度不同
   - 输出是一个 7 维矢量，不是单一主导标签
   - "主导"只是统计摘要，不是系统内部概念

2. **情感时序 (Affective Chronometry)**
   - 每个事件触发：rise_time → peak_intensity → sustain → decay
   - 不同系统有不同时间参数
   - FEAR: 快升快降 | PANIC: 慢升慢降 | PLAY: 中升中降

3. **对向过程 (Opponent Process)**
   - 每个 a-process (初始反应) 自动触发 b-process (反向调节)
   - b-process 慢但持久 → 情绪自然回弹
   - 高强度 a → 更强的 b (这是为什么 crash 后会有 warm glow)

4. **预测性稳态 (Allostatic Regulation)**
   - 系统不只是被动反应，而是预测未来状态
   - 基于 Friston 自由能最小化
   - 情感 = 预测误差的信号

5. **多层时间尺度**
   - Emotions (秒-分): 事件直接驱动
   - Mood (分-时): 情绪累积 + 缓慢漂移
   - Temperament (永久): 个体差异参数

### 数学骨架（初步）

```
For each system s:

  activation_s[t] = baseline_s                                    [恒定底色]
                  + event_impact_s[t]                             [事件冲击]
                  + mood_component_s[t]                           [心境调制]
                  + opponent_process_s[t]                         [对向回弹]
                  + cross_regulation_s[t]                         [交叉调节]
                  - decay_s × activation_s[t-1]                   [自然衰减]
                  - allostatic_pressure_s[t]                      [稳态压力]

  event_impact_s[t] = Σ(φ_s(event_i) × habituation_i)            [评估函数]
  
  opponent_process_s[t] = -b_gain_s × peak_s[recent] × e^(-t/τ_s) [对向]
  
  allostatic_pressure_s[t] = k_s × |activation_s - setpoint_s|   [异稳态]
```

## 下一步行动

1. [ ] 阅读 EMA/FAtiMA/WASABI 论文的关键章节
2. [ ] 提取 Solomon Opponent-Process 的数学公式
3. [ ] 研究 Kuppens 情感惯性的参数范围
4. [ ] 设计 DAISY 的详细数学规范
5. [ ] 实现原型 → 对比 V2.5 效果
6. [ ] 个体差异参数化 (temperament 向量)
