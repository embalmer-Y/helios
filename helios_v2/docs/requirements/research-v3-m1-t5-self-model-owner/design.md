# M1-T5 SelfModelOwner 设计

## 架构

```
                  SelfModelOwner
                       |
                       | owns
                       v
        +--------------+--------------+
        |                             |
   CoupledDynamicalSystem      EmergenceDetector
   - state (8,)                 - sync_cluster
   - C (8, 8)                   - phase_transition
   - kuramoto_R                 - resonance
   - self_unity
   - agency_strength
   - rochat_level_*
```

**关键决策**:
1. **SelfModelOwner = CDS + EmergenceDetector**:不引入额外抽象层。SelfModel 在 v3 = (8-dim ODE state + coupling matrix + emergence events)的动态过程。
2. **READ-ONLY snapshot**:`get_state_for_llm()` 返回 `dict`(不是 dataclass),Python 字典的浅复制天然防止 LLM 通过 `state[i] = X` 直接修改 CDS 内部数组。但要避免暴露 `cds` 引用本身(否则 LLM 可能 `snapshot["cds"] = owner.cds` 然后改 `owner.cds.state`)。
3. **耦合到 tick_count**:每次 `tick()` 都 `tick_count += 1`,这是 LLM 用作"时间锚"的唯一可信来源。
4. **可重入性**:`tick()` 不持有外部锁,允许同一 owner 在同一时刻被两个不同的 reflection owner 调用(M2 reflection owner 会用到这个性质)。

## 数据结构

```python
@dataclass
class SelfModelOwner:
    cds: CoupledDynamicalSystem          # 8-dim ODE + coupling
    emergence: EmergenceDetector         # 3 子检测器
    tick_count: int = 0                  # 单调递增 tick 计数
    experience_history: list[dict] = []  # 每个 tick 的 self_experience 快照(预留 M2)
```

## 核心 API

### `tick(I=None, reflect=None, reward=0.0) -> dict`
- 调用 `cds.tick(I=I, dt_tick=dt)`,ODE 推进一帧
- 调用 `emergence.detect(cds)`,获取新涌现事件
- 计算 `self_experience`(含 self_unity, agency_strength, rochat_level)
- `tick_count += 1`,追加到 `experience_history`
- 返回完整 result dict

### `get_state_for_llm() -> dict`
返回字段:
```python
{
    "8d_state": [float × 8],            # CDS state 浅复制
    "coupling_matrix_summary": {...},   # |C|max, mean(|C|), eig_top3
    "global_coherence_R": float,        # Kuramoto R ∈ [0, 1]
    "rochat_level_continuous": float,   # R² ∈ [0, 1]
    "rochat_level_discrete": int,       # 0-5 整数
    "self_unity": float,                # ∈ [0, 1]
    "agency_strength": float,           # ∈ [0, 1]
    "tick_count": int,
}
```

**关键**:绝不返回 `cds` 对象引用本身。只返回 `state` 数组的浅复制(`.copy()`)。

### `seed_prior_state(state, C=None)`
恢复 CDS 到指定 state(用于 checkpoint 恢复),可选同时设置 coupling matrix。

### `default() -> SelfModelOwner`
classmethod,构造标准初始状态:
- `cds = CoupledDynamicalSystem()` (state = 0, C = 0.1 × I)
- `emergence = EmergenceDetector()` (默认阈值)
- `tick_count = 0`
- `experience_history = []`

## 测试覆盖

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestSelfModelOwner` | 8 | default 构造、tick 返回字段、tick_count 递增、history 累积、snapshot read-only、seed_prior_state |
| `TestSelfModelOwnerEndToEnd` | 2 | 100 tick solver 稳定、emergence events 累积 |

## 与 M1-T6 协作

`SelfModelOwner` 调用 `EmergenceDetector.detect(cds)`,后者内部会调用 CDS 的 `kuramoto_R()` 和 `state` 属性。这是单向调用:CDS 不感知 EmergenceDetector 的存在。两个 owner 解耦,但通过 SelfModelOwner 协调。