# M1-T6 EmergenceDetector 需求

## 背景

v3 设计原则 §2:"self 是 process,不是 state" —— 这意味着 self 不能只用一个 8-dim 向量描述;它必然包含"涌现"(emergence)现象:M1-T2 的 Kuramoto R 衡量全局同步,M1-T5 的 SelfModelOwner 需要能识别"何时发生了显著的涌现"以便 reflection owner (M2) 触发反思。

目前 M1-T2 提供了底层度量(Kuramoto R、8-dim state),但缺少一个**统一的、可扩展的涌现检测层**。

## 目标

设计并实现 `EmergenceDetector`,提供 3 种涌现检测通道(每种对应大脑的一种涌现机制):

1. **同步集群(Synchronized Clusters)**:基于 Kuramoto 相位的层次聚类,识别 N≥3 个 aspects 进入相位锁定。类比大脑的 gamma-band binding。
2. **相变(Phase Transitions)**:基于 KL 散度的状态分布突变检测,识别 8-dim 状态分布的突然重组。类比热力学相变。
3. **共振(Resonance)**:基于滑动窗口的 Kuramoto R 高位持续检测,识别全局同步的稳定态。类比脑节律稳态。

## 范围

✅ 包含:
- `EmergenceEvent` dataclass (type, timestamp, involved_aspects, strength, description)
- `SynchronizedClusterDetector` (Kuramoto phase hierarchical clustering)
- `PhaseTransitionDetector` (KL divergence on consecutive states)
- `ResonanceDetector` (sliding window Kuramoto R)
- `EmergenceDetector` (composite, calls all 3 sub-detectors)

❌ 不包含:
- 涌现事件的下游消费方(M2 reflection audit 会用,但留到 M2)
- 事件的优先级排序(M2 阶段会加 `event_significance`)
- 事件持久化到 disk(checkpoint 留到 M2)

## 验收标准

1. ✅ 67 个 M1 测试全部通过(其中 22 个新增,涵盖 3 种检测器)
2. ✅ 1000 tick 探针:emergence events > 0,各类事件类型分布合理
3. ✅ 各检测器可独立使用(detector.detect(state) or detector.update(cds) 接口)
4. ✅ `EmergenceDetector.detect(cds)` 是 composite,调用全部 3 个子检测器并合并结果
5. ✅ `EmergenceEvent.strength ∈ [0, 1]`,timestamp 单调递增

## 关键决策(待 master 拍板)

### 决策 1:检测器是 NMS 风格还是允许重叠?

当前设计允许重叠事件(sync_cluster 可能每 tick 都触发,因为 8-dim 系统在全同步状态下大多 aspects 都被聚到一起)。

**风险**:可能淹没 reflection owner。**缓解**:M2 阶段加入 `event_significance` 评分。

### 决策 2:窗口大小是 50 还是可配置?

当前 `ResonanceDetector.window_size=50`,在 1000 tick 中很快就填满,导致几乎每 tick 都触发。

**风险**:resonance 事件过频,稀释了"罕见但重要"的涌现信号。**缓解**:M2 阶段可加入 cooldown 机制(连续 N tick 内同一类型事件最多 1 次)。

### 决策 3:PhaseTransition KL 阈值是 0.5 还是 0.1?

当前 `PhaseTransitionDetector.kl_threshold=0.1`(测试中),生产探针用 0.5(避免噪声)。

**风险**:阈值敏感度过高,可能在不同输入下行为差异大。**缓解**:默认值采用"探索"值 0.1,生产环境用 0.5;M2 阶段做参数扫描。

## 不在范围

- 事件的优先级排序(M2)
- 事件的持久化(M2 reflection audit)
- 跨 owner 的事件总线(M2+)