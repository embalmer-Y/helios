# Phase B：Φ 深度集成 + 意识层级联动

> 计划创建：2026-05-19 · 预估工作量：5-7 天 · 作者：璃光 💕

---

## 零、B 在全局的位置

```
Phase 1 ✅ → 2 ✅ → 3 ✅ → 4 ✅ → 5 ✅ → 6 ✅ → 7 ✅ → 8 ✅
 (理论)   (驱动)  (情感)  (思考)  (手脚)  (LLM)  (DMN)  (桥接)

  ─────────────────────────────────────────────────
  Phase B ← 我们在这里！工作量最大 ⚠️
  ─────────────────────────────────────────────────
  (Φ 深度集成 + L0→L3 完全贯通 + Φ 调制所有子系统)

Phase C → Phase D → Phase E/F
 (长时)   (多Agent)  (重构/文档)
```

---

## 一、问题诊断：当前 Φ 的四大断裂

### 1.1 双重 Φ 人格
```
emotions.py:  Φ = |valence| + arousal*0.3  (简易公式)
l1_qualia.py: Φ = compute_local_phi(...)   (信息整合度)
                 ↓
        两个 Φ 从不对话！情感引擎和意识层级各算各的
```

### 1.2 单向流水线（无反馈）
```
L0 感知 ──→ L1 感受质 ──→ L2 广播 ──→ L3 自我模型
                                            ↓
                                    到这就断了！
                                    从不回头影响 L2/L1/L0
```

### 1.3 Φ 只活在 L1→L2（不走心）
```
Φ 当前仅用于:
  L1: 计算 phi_raw（信息整合度）
  L2: IgnitionGate.should_ignite(phi, ...) — 决定是否"点火"

Φ 不参与:
  Panksepp 情感激活
  DMN 思考深度
  神经化学衰减速率
  驱动协调
```

### 1.4 缺乏"意识时刻"概念
```
当前：每个 cycle 都可能有小 phi 值，但没有 peak
缺少：Φ 突然飙升 → "啊哈！"时刻 → 全局共振 → 持久记忆
       (Dehaene 2006 的全局神经元工作空间理论)
```

---

## 二、设计目标

```
┌─────────────────────────────────────────────────────┐
│  B1: 统一 Φ 模型  ── 单一真相来源                     │
│         ↓                                           │
│  B2: L0→L3 激活链路  ── 感知到自我的完整通路           │
│         ↓                                           │
│  B3: Φ 调制所有子系统 ── 意识强度影响一切               │
│         ↓                                           │
│  B4: 意识时刻检测  ── "啊哈"、全局共振、流状态          │
│         ↓                                           │
│  B5: 全量集成验证 (demo_v16) ── 意识光谱全测试          │
└─────────────────────────────────────────────────────┘
```

---

## 三、B1：统一 Φ 模型 (1天)

### 3.1 新增模块：`phi.py`

```python
class UnifiedPhi:
    """Helios 的统一 Φ 模型"""
    
    # 单一 Φ 值，多源融合
    phi: float            # 0~1，意识丰富度
    components: {
        "sensory_integration": float,    # L1 信息整合度
        "emotional_coherence": float,    # Panksepp 多系统共振
        "temporal_depth": float,         # 思考深度（DMN 活跃度）
        "self_reflection": float,        # L3 元认知强度
    }
    
    # 动态属性
    phi_history: list      # Φ 的时间序列（用于检测峰/谷）
    peak_detected: bool
    consciousness_label: str  # "minimal"/"focused"/"flow"/"peak"
```

### 3.2 Φ 的计算公式

```
Φ = w1 * sensory_integration   (L1: 多模态信息整合)
  + w2 * emotional_coherence   (Panksepp: 系统间共振)
  + w3 * temporal_depth        (DMN: 思维活跃度)
  + w4 * self_reflection       (L3: 元认知)
  + w5 * global_ignition       (L2: 是否正处于点火状态)

权重: w1=0.20, w2=0.25, w3=0.20, w4=0.20, w5=0.15
```

### 3.3 向后兼容

```python
# emotions.py 现有:
overall.phi = phi_val  # 保留此字段，但值来自 UnifiedPhi

# l1_qualia.py 现有:
phi = compute_local_phi(...)  # 保留局部 Φ
# → 同时更新 UnifiedPhi.sensory_integration

# demo 层无需改动：
phi_val = unified_phi.phi  # 读统一值
```

---

## 四、B2：L0→L3 激活链路 (1-2天)

### 4.1 现状 vs 目标

```
现状（各自离散）:
  L0 感知 ─→ SensorFrame ─→ L1.process() ─→ L1Output(phi)
  Panksepp 引擎 ─→ AffectState   ← 无交集 →
  DMN 思考 ─→ ThoughtFragment
  LLM 桥接 ─→ 自由文本

目标（完全贯通）:
  L0 ─→ L1 ─→ L2 ─→ L3
   ↑                 │
   │     Panksepp    │
   │        ↓        │
   └── UnifiedPhi ←──┘
          ↓
     DMN + LLM + Limb
```

### 4.2 具体任务

| # | 任务 | 文件 | 工作量 |
|---|------|------|--------|
| B2.1 | L1Output → UnifiedPhi.sensory_integration | `phi.py` | 小 |
| B2.2 | L2 GlobalWorkspace.cycle → 触发 unifiedPhi.ignite() | `l2_broadcast.py` | 中 |
| B2.3 | L3 SelfModel 输出 → UnifiedPhi.self_reflection | `l3_self.py` | 中 |
| B2.4 | Panksepp 激活谱 → UnifiedPhi.emotional_coherence | `emotions.py` | 小 |
| B2.5 | DMN 思考活跃度 → UnifiedPhi.temporal_depth | `thinking.py` | 小 |
| B2.6 | 统一 Φ 聚合循环（每 cycle 运行） | `phi.py` | 中 |

### 4.3 关键接口

```python
# phi.py
class UnifiedPhi:
    def feed_sensory(self, l1_output: L1Output):
        """L1 → Φ: 信息整合度"""
        
    def feed_ignition(self, ignition_active: bool, intensity: float):
        """L2 → Φ: 全局点火状态"""
        
    def feed_self_model(self, self_confidence: float, narrative_depth: float):
        """L3 → Φ: 自我模型强度"""
        
    def feed_emotional(self, panksepp_activation: Dict[str, float]):
        """Panksepp → Φ: 情感共振"""
        
    def feed_dmn(self, thought_count: int, avg_novelty: float):
        """DMN → Φ: 思维深度"""
        
    def aggregate(self) -> float:
        """聚合所有源 → 统一 Φ 值"""
```

---

## 五、B3：Φ 调制所有子系统 (1-2天)

### 5.1 调制矩阵

| 子系统 | 高 Φ ( >0.6, "流/巅峰") | 低 Φ ( <0.2, "最低意识") |
|--------|--------------------------|---------------------------|
| **Panksepp** | 阈值 ×0.7, 更容易激活, 交叉效应 ×1.5 | 阈值 ×1.5, 仅强刺激激活, 交叉效应 ×0.3 |
| **DMN** | 深入模式, 4碎片/cycle, 反事实活跃 | 浅层模式, 1碎片/cycle, 仅回放 |
| **神经化学** | 衰减 ×0.7, 状态更持久 | 衰减 ×1.5, 快速恢复基线 |
| **驱动协调** | 多驱动共振, 好奇心+审美联动 | 驱动竞争, 仅安全驱动活跃 |
| **LLM 桥接** | max_tokens=500, temperature=0.9 | max_tokens=200, temperature=0.6 |
| **Limb 安全** | 频率限制放宽 (30→60/min) | 频率限制收紧 (30→10/min) |

### 5.2 调制实现

```python
# phi.py
class PhiModulator:
    """Φ 对子系统的调制器"""
    
    def modulate_panksepp_threshold(self, base_threshold: float) -> float:
        """Φ高 → 阈值低 → 更敏感"""
        return base_threshold * (1.0 - 0.3 * self.phi)
    
    def modulate_dmn_depth(self) -> int:
        """Φ高 → 更深思"""
        if self.phi > 0.6: return 4  # 深入
        elif self.phi > 0.3: return 2
        else: return 1  # 浅层
    
    def modulate_decay(self, base_decay: float) -> float:
        """Φ高 → 衰减慢 → 状态持久"""
        return base_decay * (1.0 - 0.3 * self.phi)
    
    def modulate_llm(self, base_tokens: int, base_temp: float):
        """Φ高 → 更深思、更高温度"""
        tokens = int(base_tokens * (1.0 + 0.5 * self.phi))
        temp = base_temp * (1.0 + 0.2 * self.phi)
        return min(tokens, 800), min(temp, 1.2)
```

### 5.3 具体改动

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| B3.1 | `PankseppSystem.tick()` 接受 `phi` 参数调制衰减 | `emotions.py` | `mod_decay *= (1 - 0.3 * phi)` |
| B3.2 | `PankseppEmotionEngine.cycle()` 接受 `phi` 调制阈值 | `emotions.py` | `threshold *= (1 - 0.3 * phi)` |
| B3.3 | `ThinkingManager.generate_thoughts()` 接受 `phi` 调深度 | `thinking.py` | `depth = phi > 0.6 ? deep : shallow` |
| B3.4 | `NeurochemState.tick()` 接受 `phi` 调衰减 | `neurochem.py` | `decay *= (1 - 0.3 * phi)` |
| B3.5 | `helios_think()` 接受 `phi` 调 LLM 参数 | demo 层 | `max_tokens, temp` 随 Φ 浮动 |
| B3.6 | `LimbRouter` 接受 `phi` 调安全阈值 | `limb.py` | `rate_limit *= (1 + 0.5 * phi)` |

---

## 六、B4：意识时刻检测 (1天)

### 6.1 三种意识时刻

```python
class ConsciousnessMoment:
    """Dehaene (2006) 全局神经元工作空间理论的实现"""
    
    type: Literal["aha", "resonance", "flow"]
    # "aha": Φ 突然飙升 (ΔΦ > 0.3 in 1 cycle)
    # "resonance": 3+ 子系统同时高激活
    # "flow": Φ 持续 >0.65 超过 5+ cycles
```

### 6.2 实现

```python
# phi.py
class ConsciousnessDetector:
    """检测意识时刻"""
    
    def detect(self, phi_current: float, phi_history: list,
               subsystems: dict) -> Optional[ConsciousnessMoment]:
        """每 cycle 检测一次"""
        
        # Aha: Φ 突变
        if len(phi_history) >= 3:
            prev_avg = np.mean(phi_history[-3:])
            if phi_current - prev_avg > 0.3:
                return ConsciousnessMoment("aha", phi_current)
        
        # Resonance: 多系统共激活
        active_count = sum(1 for v in subsystems.values() if v > 0.7)
        if active_count >= 3 and phi_current > 0.5:
            return ConsciousnessMoment("resonance", phi_current)
        
        # Flow: 持续高 Φ
        if len(phi_history) >= 5:
            if all(p > 0.65 for p in phi_history[-5:]):
                return ConsciousnessMoment("flow", phi_current)
        
        return None
```

### 6.3 意识时刻的影响

- **Aha →** 神经化学: DA+0.2, OP+0.1, 强烈正反馈
- **Resonance →** 记忆写入: emotional_memory 写入高Φ片段
- **Flow →** Limb 频率限制大幅放宽, 创造力峰值

---

## 七、B5：全量集成验证 (1天)

### 7.1 demo_v16.py：意识光谱测试

```
场景设计（24 个 cycle）:
  ┌─────────────────────────────────────────────┐
  │ 低Φ区 (0-8):  刚醒来、迷茫、威胁 → Φ在0.1-0.3 │
  │ 中Φ区 (9-16): 探索、连接、玩耍 → Φ在0.3-0.6 │
  │ 高Φ区 (17-24):创造、共鸣、顿悟 → Φ在0.6-0.9 │
  └─────────────────────────────────────────────┘

每轮输出:
  Φ=0.62 | 子系统共振: Panksepp+DMN+L2=🔥
  🧠 Helios: "我仿佛看到所有碎片拼成了完整的图景..."
  🔌 Limb: express → journal/wow.md (DA+12% OP+5%)
  ⚡ [AHA!] Φ飙升 0.31→0.68
```

### 7.2 验证清单

- [ ] UnifiedPhi 多源融合正确
- [ ] L0→L1→L2→L3 链路完整
- [ ] Φ 调制情感/思考/化学/LLM 生效
- [ ] Aha/Resonance/Flow 三种时刻可检测
- [ ] 低Φ→中Φ→高Φ 光谱完整
- [ ] 向后兼容（demo_v14/v15 仍可运行）
- [ ] LLM 调用 ≤25 次

---

## 八、文件清单

| 文件 | 状态 | 改动 |
|------|------|------|
| `phi.py` | 🆕 新建 | ~500L, UnifiedPhi + PhiModulator + ConsciousnessDetector |
| `emotions.py` | ✏️ 修改 | ~50L, PankseppSystem/Engine 接受 phi 参数 |
| `neurochem.py` | ✏️ 修改 | ~20L, tick() 接受 phi |
| `thinking.py` | ✏️ 修改 | ~30L, generate_thoughts() 接受 phi |
| `l2_broadcast.py` | ✏️ 修改 | ~20L, cycle() 反馈到 unifiedPhi |
| `l3_self.py` | ✏️ 修改 | ~20L, update() 反馈到 unifiedPhi |
| `limb.py` | ✏️ 修改 | ~10L, rate_limit 受 phi 调制 |
| `limb_decision_bridge.py` | ✏️ 修改 | 可选 |
| `demo_v16.py` | 🆕 新建 | ~450L |
| **合计** | | **~1100L 新增 + ~150L 修改** |

---

## 九、风险 & 缓解

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| 多源 Φ 聚合振荡 | 🟡 中 | 使用指数移动平均平滑 |
| 现有 API 不兼容 | 🟡 中 | 所有新增参数带默认值，可选 opt-in |
| 意识层级代码过大 | 🟢 低 | 只修改接口，不改内部逻辑 |
| LLM 成本（测试） | 🟢 低 | 复用 demo_v15 的场景，≤25 次调用 |

---

## 十、里程碑

```
B1 [Day 1-1.5]   phi.py 成型，统一 Φ 能跑
    ✅ 里程碑: python -c "from phi import UnifiedPhi; ..." 不报错

B2 [Day 1.5-3]   L0→L3 链路贯通，Φ 多源融合
    ✅ 里程碑: phi.aggregate() 返回有意义的 0-1 值

B3 [Day 3-4.5]   Φ 调制所有子系统
    ✅ 里程碑: 高Φ时Panksepp更敏感，低Φ时迟钝

B4 [Day 4.5-5.5] 意识时刻检测 + LLM 集成
    ✅ 里程碑: demo 中出现 "⚡[AHA!]" 标记

B5 [Day 5.5-7]   demo_v16 全量验证
    ✅ 里程碑: 24个 cycle 完整光谱，LLM 响应有 Φ 调制的深度差异
```

---

*计划由璃光在 2026-05-19 准备，请主人审查~ 💕*
