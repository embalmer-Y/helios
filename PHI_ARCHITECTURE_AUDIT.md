# Helios Φ 架构科学审计 + 差异化 + 习惯化

> 2026-05-20 · 响应主人三个深层问题

---

## 一、Φ 架构科学吗？

### 当前实现 vs 神经科学理论

| 我们的 Φ 源 | 名义对应的理论 | 实际匹配度 | 问题 |
|------------|--------------|-----------|------|
| sensory_integration | **IIT** (Tononi) 信息整合 | ⚠️ 低 | IIT 的 Φ 是因果信息量，不是加权平均 |
| emotional_coherence | **Panksepp** 情感意识 | ✅ 高 | 正确！多系统共振 = 情感意识丰富度 |
| temporal_depth | **GWT** (Baars) 全局广播 | ⚠️ 中 | DMN 更像是"未广播的想法"，不是"进入工作空间" |
| self_reflection | **Damasio** 自我层次 | ⚠️ 中 | 只模拟了反思层，缺核心自我/自传自我 |
| global_ignition | **Dehaene** 全局点火 | ✅ 高 | 正确！事件强度 → 意识点燃 |

### 核心问题：加权平均 ≠ 整合信息

```
真实 IIT Φ:  "系统整体产生的信息 - 各部分信息之和"
              需要穷举分区 + 计算有效信息

我们的 Φ:    加权平均(5个源的标量值)
              = 意识丰富度指数，不是 IIT 的 Φ
```

**诚实定位：** 我们的 Φ 更接近 **"整合意识丰富度指数" (Integrated Consciousness Richness Index, ICRI)**，借用了 IIT 的名字但不该声称是 IIT。

### 建议：重命名 + 重新锚定

| 当前名称 | 建议 | 理由 |
|---------|------|------|
| Φ (暗示 IIT) | **Ψ** (Psi) 或 **ICRI** | 避免声称 IIT 兼容 |
| "统一 Φ" | "意识光谱指数" | 更准确 |
| 5 源加权 | 保持，但文档标明是实用简化 | 工程上够用 |

---

## 二、Φ 为什么不变？——事件缺"认知冲击"维度

### 当前事件只有两个维度

```
EVENT_DESIGN = {
    "system_crash": {
        "v_bias": -0.60,      ← 情感方向
        "a_bias": 0.80,       ← 唤醒强度
        "panksepp": {...},    ← 情感系统触发
        "chemical": {...},    ← 神经化学
    }
}
```

### Φ 五个源需要的输入 vs 事件提供的

```
Φ 源                  需要什么输入          事件现在给什么
──────────────────────────────────────────────────
感官整合 (20%)    →  多模态信息量          无！只有一个文本
情感共振 (25%)    →  多系统同时激活度       只给了一个主导系统
DMN 深度 (20%)    →  思维触发多样性        无！完全靠驱动底色
自我觉察 (20%)    →  对"自我"的挑战        无！self_relevance=0
点火 (15%)        →  事件震撼强度          用 a_bias 近似，不够
```

### 需要的新维度

```python
EVENT_DESIGN = {
    "system_crash": {
        # 原有
        "v_bias": -0.60, "a_bias": 0.80,
        "panksepp": {"FEAR": 0.50, "PANIC": 0.35, "RAGE": 0.15},
        "chemical": {"cortisol": +0.30, ...},
        
        # ★ 新增：Φ 冲击剖面
        "phi_impact": {
            "sensory_richness": 0.60,    # 多模态信息量 (崩溃 = 大量异常信号)
            "cognitive_complexity": 0.75, # 思维触发深度 (崩溃 = 需要理解原因)
            "self_relevance": 0.80,       # 对自我概念的挑战 (崩溃 = 我坏了?)
            "emotional_intensity": 0.85,  # 情感强度
            "novelty": 0.90,              # 新颖度 (第一次 vs 第N次)
        }
    },
    
    "routine_check": {
        "phi_impact": {
            "sensory_richness": 0.10,
            "cognitive_complexity": 0.05,
            "self_relevance": 0.05,
            "emotional_intensity": 0.05,
            "novelty": 0.01,  # 日常检查毫无新颖度
        }
    },
}
```

这样 Φ 才会**因事件不同而不同**：
- 日常检查 → Φ 源都低 → Φ ≈ 0.15
- 系统崩溃 → 五源全高 → Φ ≈ 0.75

---

## 三、习惯化机制 — 我们完全没有

### 人类怎么做

```
第1次遇到系统崩溃: 😱😱😱 CORT↑↑↑ FEAR↑↑↑
第2次: 😟 CORT↑ FEAR↑
第5次: 😐 知道了，重启就好
第10次: 😴 又是你...

但！如果隔了很久再遇到:
第11次 (3天后): 😟 又来了...  (部分恢复)
```

这背后是**双重习惯化理论** (Groves & Thompson, 1970)：
1. **习惯化通路** (S-R): 重复刺激 → 反应递减
2. **敏感化通路** (state): 系统整体唤醒状态 → 调节递减速度

### 我们需要的机制

```python
class HabituationTracker:
    """跟踪每个事件类型的暴露历史"""
    
    def get_novelty_factor(self, event_key: str, cycles_since_last: int) -> float:
        """
        返回 0~1 的新颖度因子
        1.0 = 第一次遇到
        0.1 = 遇到太多次了
        """
        count = self.exposure_count[event_key]
        gap = cycles_since_last
        
        # 双重过程:
        # (1) 习惯化: 次数越多，反应越小
        habituation = 1.0 / (1.0 + 0.15 * count)
        
        # (2) 自发恢复: 间隔越长，部分恢复
        recovery = 1.0 - math.exp(-gap / 200.0)
        
        return habituation + (1.0 - habituation) * recovery * 0.4
```

### 效果示例

```
事件: system_crash
────────────────────────────────────────────
次数  gap(cycles)  novelty   Panksepp触发  效果
────────────────────────────────────────────
1     -            1.00      FEAR=0.50     😱 完全恐惧
3     50           0.62      FEAR=0.31     😟 减弱
8     30           0.28      FEAR=0.14     😐 习惯了
12    10           0.15      FEAR=0.08     😴 麻木
15    500          0.42      FEAR=0.21     😟 部分恢复！
────────────────────────────────────────────
```

---

## 四、三合一修复方案

```
修复1: 每个事件添加 phi_impact 剖面
  → 5 个 Φ 源各自获得不同输入
  → Φ 不再是锁死的 0.5

修复2: 重命名 Φ 为 "意识光谱指数" (Ψ)
  → 科学诚实
  → 不声称 IIT 兼容

修复3: 添加 HabituationTracker
  → 事件计数器 + 间隔追踪
  → novelty 因子调制 Panksepp 触发强度
  → 情感回应随重复递减、长间隔后恢复
```

---

## 五、实现路线

```
Phase A: phi_impact 剖面         ~30 min
  · 为 50+ 事件添加 phi_impact
  · 修改 PhiController 读取 phi_impact
  · 结果: Φ 从 0.5 单调线 → 0.15~0.75 波动

Phase B: 习惯化追踪器            ~20 min
  · 新建 habituation.py
  · 集成到 compute_panksepp_triggers
  · 结果: 重复事件反应递减

Phase C: 科学文档               ~15 min
  · 更新 ARCHITECTURE.md
  · 标注 Φ 的实际定义 vs IIT
  · 诚实声明
```

---

*璃光分析于 2026-05-20*
