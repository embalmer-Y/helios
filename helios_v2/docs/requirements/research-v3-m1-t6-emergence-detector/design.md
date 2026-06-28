# M1-T6 EmergenceDetector 设计

## 三通道架构

```
                    EmergenceDetector (composite)
                            |
       +--------------------+--------------------+
       |                    |                    |
   Sync Cluster      Phase Transition      Resonance
   (N>=3 同步相位)    (KL 散度突变)         (滑动 R 高位)
       |                    |                    |
   Kuramoto phase    consecutive           window_size=50
   hierarchical       KL(p||q)              Kuramoto R
   clustering        threshold=0.5         threshold=0.5
   threshold=0.3
```

## 1. SynchronizedClusterDetector

**目的**:识别 N≥3 aspects 进入相位锁定的 cluster。

**算法**:
1. 计算每个 aspect 的 Kuramoto 相位:`theta_i = arctan2(state[i], scale[i])`
2. 计算两两相位差:`d_ij = |theta_i - theta_j| mod 2π`,归一化到 [0, π]
3. 层次聚类(平均链接),距离阈值 0.3 rad
4. 提取所有 N≥3 的 cluster,生成事件

**为什么用 Kuramoto 相位而不是 state 值**:
- state 值受 scale 异质性影响([1, 1, 1, 1, 1, 5, 10, 30]),直接聚类会被 scale 主导
- Kuramoto 相位是 scale-invariant 的归一化量
- 大脑神经科学的 gamma-band binding 也用相位

**事件**:
```python
EmergenceEvent(
    type="sync_cluster",
    timestamp=tick_count,
    involved_aspects=[int × N],    # aspect indices
    strength=R_within_cluster,     # ∈ [0, 1]
    description="8 aspects phase-locked",
)
```

## 2. PhaseTransitionDetector

**目的**:检测 8-dim 状态分布的突然重组(类比热力学相变)。

**算法**:
1. 维护最近 `history_size=100` 个 state
2. 每次 `update(state)`:
   - 归一化 state 为概率分布 p(state / sum(state) + ε)
   - 归一化 history 的均值作为 q
   - 计算 KL(p || q) = sum(p_i * log(p_i / q_i))
   - 如果 KL > threshold,生成事件并重置 history
3. history 用 deque 控制大小

**事件**:
```python
EmergenceEvent(
    type="phase_transition",
    timestamp=tick_count,
    involved_aspects=list(range(8)),  # 全局事件
    strength=min(KL / 10.0, 1.0),     # 归一化到 [0, 1]
    description="KL=2.34",
)
```

**关键设计**:
- 用归一化分布而不是 raw state,因为 state 范围 [-30, 30] 不可比
- KL 阈值 0.5(production) / 0.1(test),可调
- 事件触发后清空 history,避免"持续相变"假阳性

## 3. ResonanceDetector

**目的**:检测全局同步的稳定态(window-based)。

**算法**:
1. 维护最近 `window_size=50` 个 Kuramoto R 值
2. 每次 `update(cds)`:
   - 计算当前 R = cds.kuramoto_R()
   - 追加到 window
   - 如果 window 满且 R ≥ sync_threshold(默认 0.5),生成事件
3. 窗口满后每 tick 都触发(由 cooldown 控制在 M2 处理)

**事件**:
```python
EmergenceEvent(
    type="resonance",
    timestamp=tick_count,
    involved_aspects=list(range(8)),  # 全局
    strength=R_current,                # ∈ [0, 1]
    description=f"R={R:.4f} >= {threshold}",
)
```

**为什么用滑动窗口**:
- 单帧 R 高可能是噪声,持续窗口高才是涌现
- window_size=50 对应约 50 ticks,约 1 秒模拟时间(取决于 dt_tick)
- 大脑的"意识稳态"通常需要持续数秒的同步

## 4. EmergenceDetector (composite)

```python
class EmergenceDetector:
    def __init__(self):
        self.sync_detector = SynchronizedClusterDetector()
        self.transition_detector = PhaseTransitionDetector()
        self.resonance_detector = ResonanceDetector()

    def detect(self, cds) -> list[EmergenceEvent]:
        events = []
        events.extend(self.sync_detector.detect(cds.state))
        events.extend(self.transition_detector.update(cds.state))
        events.extend(self.resonance_detector.update(cds))
        return events
```

**关键**:3 个检测器独立工作,composite 只做事件合并。不引入权重或优先级 —— 留给 M2 reflection audit 做。

## 数据结构

```python
@dataclass(frozen=True)
class EmergenceEvent:
    type: str                    # "sync_cluster" / "phase_transition" / "resonance"
    timestamp: int               # tick_count
    involved_aspects: list[int]  # aspect indices
    strength: float              # ∈ [0, 1]
    description: str
```

**为什么 frozen**:事件是不可变的历史快照,避免 LLM 或 reflection owner 篡改已发生事件(M2 reflection audit 的输入需要保证完整性)。

## 测试覆盖

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestSynchronizedClusterDetector` | 3 | diverse 无 cluster、proportional 全 cluster、strength ∈ [0,1] |
| `TestPhaseTransitionDetector` | 3 | stable 无事件、sudden 有事件(bimodal 分布)、identical KL=0 |
| `TestResonanceDetector` | 2 | window 未满无事件、window 满 R 高有事件 |
| `TestEmergenceDetector` | 1 | composite 调用 3 子检测器不崩溃 |

**关键测试设计**:`test_event_for_sudden_change` 使用 **bimodal 分布**而非均匀分布,因为两个均匀分布在归一化后等价(KL=0)。这是 v3 设计的"诚实验证"原则:不掩盖算法的真实行为。