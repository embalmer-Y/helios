# M1-T8 OwnerFieldBridge 设计

## 映射架构

```
            v2 owner 数据 (21 字段)
   +-------------------------------+
   | Hormone9D  (9)                |
   | Feeling7D  (7)                |
   | Salience5D (5 + aggregate)    |
   +---------------+---------------+
                   |
                   v
          OwnerFieldBridge
          (8 个 OwnerFieldMapping)
                   |
                   | bridge_input(h, f, s)
                   v
          +--------+--------+
          |                 |
        CDS I (8-dim)    CDS reflect (8-dim) [M2 预留]
          |                 |
          v                 v
       SelfModelOwner.tick(I, reflect)
```

## OwnerFieldMapping 数据结构

```python
@dataclass(frozen=True)
class OwnerFieldMapping:
    hormone_keys: dict[str, float]   # e.g. {"dopamine": 0.3}
    feeling_keys: dict[str, float]   # e.g. {"valence": 0.6}
    salience_keys: dict[str, float]  # e.g. {"threat": 0.6}
    bias: float = 0.0
    scale: float = 1.0
```

**为什么分 3 个 dict**:语义清晰,h/feeling/salience 分别对应 v2 三个 owner 子系统,易于维护。

## 默认映射 (DEFAULT_MAPPINGS)

8 个维度,每个对应一个 OwnerFieldMapping:

| i | PTS dim | 权重配置 (示例) |
|---|---------|---------------|
| 0 | bodily | h.cortisol=+0.4, h.opioid_tone=+0.3, f.pain_like=+0.3, f.fatigue=-0.2 |
| 1 | minimal_experiential | h.serotonin=+0.6, h.acetylcholine=+0.2, f.comfort=+0.4, s.uncertainty=-0.3 |
| 2 | affective | h.dopamine=+0.3, h.NE=+0.3, f.valence=+0.6, f.arousal=+0.5, f.tension=+0.4, s.reward=+0.3 |
| 3 | intersubjective | h.oxytocin=+0.7, f.social_safety=+0.6, f.comfort=+0.2, s.social=+0.5 |
| 4 | psychological_cognitive | h.dopamine=+0.4, h.ACh=+0.4, f.tension=+0.2, s.novelty=+0.4, s.uncertainty=+0.3 |
| 5 | narrative | h.excitation=+0.5, h.dopamine=+0.3, f.valence=+0.2, s.reward=+0.5, s.novelty=+0.3 |
| 6 | ecological_extended | h.NE=+0.5, f.arousal=+0.3, s.threat=+0.6, s.novelty=+0.4 |
| 7 | normative | h.inhibition=+0.5, h.serotonin=+0.3, f.comfort=+0.4, s.uncertainty=-0.3 |

**权重来源**:
- v3 设计文档 §02 "v2 owner → v3 self-model" 映射章节
- v2 04/05/03 owner 子系统的功能描述
- 经验调整:每个维度的"主信号"权重 = 0.5-0.7,辅信号 = 0.2-0.4,反向信号 < 0

## bridge_input 算法

```python
def bridge_input(self, h, f, s) -> np.ndarray:
    I = np.zeros(8)
    for i, mapping in enumerate(self.mappings):
        value = mapping.bias
        for key, w in mapping.hormone_keys.items():
            value += w * getattr(h, key)
        for key, w in mapping.feeling_keys.items():
            value += w * getattr(f, key)
        for key, w in mapping.salience_keys.items():
            value += w * getattr(s, key)
        I[i] = value * mapping.scale
    return np.clip(I, -1.0, 1.0)
```

**关键**:
- `np.clip(-1, 1)`:CDS tick 会再 clip 一次到 [-10, 10],但 bridge 这层先 clip 到 [-1, 1] 保证数值在合理语义范围
- `mapping.scale`:允许缩放整体幅度,但默认 1.0
- 加权是**线性**的(不引入非线性),保证可解释性

## bridge_reflect 算法(M2 预留)

把 AspectState(10 字段)线性映射到 CDS 8 维 reflect:

```python
reflect[0] = 0.5 * a["arousal"] + 0.3 * abs(a["activation"])  # bodily
reflect[1] = 0.4 * a["certainty"] + 0.3 * a["coherence"]        # minimal
reflect[2] = 0.5 * a["valence"] + 0.4 * a["arousal"]            # affective
reflect[3] = 0.6 * a["resonance"]                              # intersubjective
reflect[4] = 0.4 * a["precision"] + 0.4 * a["novelty"]          # psychological
reflect[5] = 0.4 * a["salience"] + 0.3 * a["stability"]        # narrative
reflect[6] = 0.5 * a["novelty"] + 0.3 * a["salience"]           # ecological
reflect[7] = 0.5 * a["stability"] + 0.3 * a["coherence"]        # normative
```

**为什么 M2 才用**:M1-T8 只验证 bridge 的输入语义,reflect 是"self-model 对自己的影响",属于 reflection owner 的语义范畴。

## 4 个 fixture

| fixture | 语义 | 期望 |I| 均值 |
|---------|------|----------------|
| `fixture_neutral` | 所有字段=0 | \|I\| = 0 |
| `fixture_high_activation_high_valence` | DA/NE 高 + valence/arousal 高 | \|I\| ≈ 0.76 |
| `fixture_high_threat_high_cortisol` | threat 高 + cortisol 高 | \|I\| ≈ 0.52 |
| `fixture_low_energy_fatigue` | 低 DA + 高 fatigue | \|I\| ≈ 0.22 |

**设计意图**:
- neutral 作为"零输入"baseline
- high_positive 触发 I[2] (affective) 接近 1
- high_threat 触发 I[6] (ecological) 接近 1
- low_energy 各维度普遍低,作为"低激活"对照

## 测试覆盖 (20 个)

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestOwnerFieldBridgeMapping` | 4 | 8 mappings / neutral=0 / shape / range |
| `TestOwnerFieldBridgeSemantics` | 5 | 4 个 fixture 的语义排序 |
| `TestOwnerFieldBridgeReflect` | 3 | reflect shape / range / 高 arousal → bodily |
| `TestOwnerFieldBridgeIntegration` | 4 | 驱动 SelfModelOwner / 100 tick 稳定 / 确定性 / 不同 mapping |
| `TestOwnerFieldMapping` | 2 | 默认构造 / 8 mappings 互不相同 |
| `TestOwnerFieldBridgeDescribe` | 2 | 9 行 / 含 PTS_DIMENSION_NAMES |

## 关键设计决策

### 决策 1:线性权重 vs 神经网络

**选择**:线性加权。**理由**:
- 可解释性(每个权重都有 v2 设计文档依据)
- 可测试性(线性函数可直接断言)
- v3 阶段目标是验证 v2 → v3 桥接可行性,非线性映射会掩盖桥接 bug
- **未来扩展**:M8 可尝试学得权重,但 M1-T8 先用 hand-tuned

### 决策 2:CDS I clip [-1, 1]

**理由**:v2 owner 字段都在 [-1, 1](语义化)或 [0, 1](概率化),加权后可能超界但 clip 到 [-1, 1] 仍是合理语义范围。CDS 内部会再 clip 到 [-10, 10],这是数值稳定层。

### 决策 3:4 个 fixture 而非更多

**理由**:M1-T8 目标是验证 bridge 协议可行性,不是穷举语义场景。4 个 fixture 覆盖了 baseline + 高正价 + 高威胁 + 低能量 4 个对角,足够验证映射正确性。M5 真 LLM 集成时可用更多 fixture。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 权重不准确导致语义错位 | 5 个 semantic test 验证关键 fixture → 期望 CDS 维度 |
| CDS I 长期饱和 | bridge 这层 clip [-1, 1] 防止单维度爆炸 |
| 映射无法扩展到其他 v2 owner schema | OwnerFieldMapping dataclass 允许自定义权重 |
| bridge_reflect 误用(M1 阶段) | 在 docstring 中标注 "M2 预留" |