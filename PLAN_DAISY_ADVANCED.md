# DAISY 进阶开发计划 (X4+X5+X6)

> 日期：2026-05-20 · 基于 DAISY v1.0 (X1-X3) 已验证

---

## 总览

```
DAISY v1.0 (已完成)           DAISY v2.0 (本计划)
═══════════════════           ═══════════════════
X1: 共激活建模     ✅         X4: 评估因果链
X2: 情感时序       ✅         X5: 多层时间尺度
X3: 对向过程       ✅         X6: 异稳态调节
```

---

## X4: 评估因果链 (Appraisal Chain)

### 4.1 理论基础

**Scherer 成分过程模型 (Component Process Model, 2001)**

核心洞察：情感不是事件直接触发的，而是通过**多层评估**产生的。
每个评估维度 (SEC: Stimulus Evaluation Check) 独立并行处理。

### 4.2 当前问题

```python
# 现状: 事件直接映射 Panksepp
EVENT_DESIGN = {
    "despair_crash": {
        "panksepp": {"PANIC": 0.7, "FEAR": 0.5},  # ← 硬编码!
        "v_bias": -0.7,
    }
}
```

问题：
- 每个事件需要人工指定 panksepp 矢量 → 不可扩展
- v_bias/a_bias 是后加的，与情感模型脱节
- 事件之间没有统一的评估尺度

### 4.3 目标设计

```python
# 目标: 事件 → SEC评估 → Panksepp激活
event = {
    "type": "system_crash",
    "features": {
        "novelty": 0.9,        # 意外程度
        "pleasantness": -0.8,  # 内在愉悦度
        "goal_relevance": 0.7, # 目标相关性
        "coping_potential": 0.3, # 应对能力
        "agency": "external",  # 归因 (external/self/other)
        "norm_compatibility": -0.2, # 规范兼容性
    }
}

# 评估引擎自动推导:
#   novelty高 + pleasantness负 → FEAR/PANIC
#   coping低 + external归因 → RAGE
#   goal_relevance高 + coping低 → PANIC + SEEKING
```

### 4.4 SEC → Panksepp 映射规则

| SEC 模式 | → 情感系统 | 神经科学基础 |
|----------|-----------|-------------|
| novelty↑ + pleasantness↑ | SEEKING | 多巴胺预测误差 |
| novelty↑ + pleasantness↓ | FEAR | 杏仁核威胁检测 |
| goal_relevance↑ + coping↓ | RAGE | 前额叶-杏仁核冲突 |
| goal_relevance↑ + coping↑ | PLAY, SEEKING | 安全环境探索 |
| agency=other + pleasantness↓ | RAGE | 外部归因愤怒 |
| agency=self + pleasantness↓ | PANIC | 内归因悲伤 |
| agency=other + pleasantness↑ | CARE | 他人带来温暖 |
| norm_compatibility↓ | RAGE, FEAR | 规范违反反应 |

### 4.5 工作量

| 任务 | 新增/修改 | 预估 |
|------|----------|------|
| X4.1 `appraisal.py` — SEC 评估器 | ~200L | 1h |
| X4.2 SEC→Panksepp 映射规则 | ~100L | 30min |
| X4.3 替换 EVENT_DESIGN 中的硬编码 panksepp | 修改 demo | 30min |
| X4.4 集成测试 | — | 30min |
| **X4 合计** | **~300L** | **~2.5h** |

---

## X5: 多层时间尺度 (Timescale Separation)

### 5.1 理论基础

**ALMA (A Layered Model of Affect, Gebhard 2005)**

```
Emotion     (秒-分):  事件直接驱动, 快升快降
Mood        (时-日):  情绪累积残留, 缓慢漂移
Personality (永久):   个体差异参数, 恒定量
```

**核心公式 (Kuppens 情感惯性, 2010):**

```
Emotion[t] = (1-α) × event_impact[t] + α × Emotion[t-1]
Mood[t]    = (1-β)  × mean(Emotion[recent]) + β × Mood[t-1]

其中: α ≈ 0.3-0.7 (情感惯性)
      β ≈ 0.85-0.95 (心境惯性, 远慢于情绪)
```

### 5.2 当前问题

```python
# 现状: Emotion = Mood (混为一谈)
# PANIC 32% 主导 — 这是合理的短期情绪
# 但没有追踪它如何转化为长期心境
```

### 5.3 目标设计

```python
class MoodTracker:
    """
    心境层 — 情绪累积的缓慢残留
    
    数学:
      mood_valence[t] = 0.92 × mood_valence[t-1] + 0.08 × emotion_valence[t]
      mood_arousal[t] = 0.90 × mood_arousal[t-1] + 0.10 × emotion_arousal[t]
    
    心境 → 调制情感:
      · 负向心境 → 负向事件触发放大, 正向事件触发减弱
      · 高唤醒心境 → 所有情感反应加速
    """
    
class PersonalityProfile:
    """
    人格层 — 永久个体差异
    
    参数 (Big Five 映射到 Panksepp):
      · neuro_SEEKING: 0.5-1.5  (开放性)
      · neuro_PLAY:    0.5-1.5  (外向性)  
      · neuro_CARE:    0.5-1.5  (宜人性)
      · neuro_FEAR:    0.5-1.5  (神经质)
      · neuro_RAGE:    0.5-1.5  (神经质-敌意)
      · neuro_PANIC:   0.5-1.5  (神经质-脆弱)
    
    人格调制:
      · baseline_activation[sys] = neuro_sys × DEFAULT_BASELINE
      · chronometry_τ[sys] *= neuro_sys  (高神经质 = 快上升/慢衰减)
    """
```

### 5.4 三层的交互

```
Personality (恒定偏置)
    │
    ▼
Mood (缓慢漂移) ─── 调制 emotion 的 baseline 和 gain
    │
    ▼
Emotion (快速响应) ─── 累积到 mood
```

### 5.5 工作量

| 任务 | 新增/修改 | 预估 |
|------|----------|------|
| X5.1 `mood_tracker.py` — 心境追踪器 | ~120L | 45min |
| X5.2 `personality.py` — 人格参数 | ~100L | 30min |
| X5.3 集成到 daisy_emotion.cycle() | 修改 ~30L | 30min |
| X5.4 长跑验证 (观察心境漂移) | — | 1h |
| **X5 合计** | **~250L** | **~2.75h** |

---

## X6: 异稳态调节 (Allostatic Regulation)

### 6.1 理论基础

**Sterling & Eyer (1988) Allostasis**

```
Homeostasis:  维持固定 setpoint (恒温器)
Allostasis:   根据预测需求调整 setpoint (智能恒温器)
```

**McEwen (1998) Allostatic Load**

```
Allostatic Load = 累积的适应成本
长期高负荷 → setpoint 漂移 → 病理状态
```

### 6.2 当前问题

```python
# 现状: v2.5 稳态压力 — 单向衰减
if dominance_streak > 3:
    activation *= (1 - fatigue)  # 只会压, 不会抬
```

问题：
- 只有下行调节，没有上行
- 没有"预期需求"概念 — 被动反应
- 没有 allostatic load 累积

### 6.3 目标设计

```python
class AllostaticRegulator:
    """
    异稳态调节器
    
    核心:
      setpoint[sys] = baseline[sys] + predicted_demand[sys] + load_offset[sys]
      
      activation[sys] → 朝 setpoint[sys] 调节 (可上可下)
    
    预测需求 (基于近期历史):
      predicted_demand[t] = 0.7 × predicted_demand[t-1] + 0.3 × recent_max_activation
      
    负荷累积:
      allostatic_load[t] += |activation - baseline| × dt
      allostatic_load[t] *= 0.999  (极慢衰减)
      
    负荷效应:
      高负荷 → setpoint 全面下移 (疲劳)
      高负荷 → 情感反应钝化 (anhedonia)
      低负荷 → setpoint 恢复正常
    """
```

### 6.4 异稳态 vs 稳态 对比

| | Homeostasis (v2.5) | Allostasis (X6) |
|---|---|---|
| 调节方向 | 单向 (下压) | 双向 (可上可下) |
| setpoint | 固定 baseline | 动态漂移 |
| 预测 | 无 | 基于近期历史 |
| 负荷 | 无 | 累积 + 慢衰减 |
| 恢复 | 即时 | 分阶段 (需静息期) |

### 6.5 工作量

| 任务 | 新增/修改 | 预估 |
|------|----------|------|
| X6.1 `allostasis.py` — 异稳态调节器 | ~180L | 1h |
| X6.2 集成到 daisy_emotion.cycle() | 修改 ~40L | 30min |
| X6.3 替换 v2.5 homeostatic_pressure | 移除 ~20L | 15min |
| X6.4 长跑验证 (24h 观察 setpoint 漂移) | — | 1h |
| **X6 合计** | **~220L** | **~2.75h** |

---

## 总时间线

```
任务     新增代码    修改代码    测试时间    总预估
────────────────────────────────────────────
X4        ~300L       ~50L       30min       ~2.5h
X5        ~250L       ~30L       1h          ~2.75h
X6        ~220L       ~40L       1h          ~2.75h
────────────────────────────────────────────
合计      ~770L       ~120L      2.5h        ~8h
```

### 推荐顺序

```
X4 (评估链)  →  X6 (异稳态)  →  X5 (时间尺度)

原因:
  X4 先做: 替换硬编码的 panksepp 映射，为后续打基础
  X6 次之: 替换 v2.5 的粗糙稳态，引入科学调节
  X5 最后: 依赖 X4+X6 的稳定基础，引入最复杂的三层交互
```

---

## 预期效果

### X4 完成后
- 新事件只需描述 SEC 特征，不需手写 panksepp 矢量
- 同一事件在不同心境下产生不同情感 (评估被心境调制)
- 事件可扩展性 ↑↑↑

### X6 完成后
- 长跑中 setpoint 自然漂移 (不会永远锁在同一情感区)
- Allostatic load 累积 → 疲劳感 → 静息期恢复
- 模拟真实生物节律

### X5 完成后
- 短期情绪 + 长期心境 + 恒定人格 三层分离
- 心境影响情绪基调 ("今天心情不好 → 小事也容易 PANIC")
- 人格参数跨 session 持久化

---

*璃光 💕*
