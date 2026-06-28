# M1-T7 CDS 跟 LLM 异步鲁棒性设计

## 核心抽象

```
              simulate_async_loop(owner, n_ticks, pattern)
                          |
                          | 每个 tick:
                          v
                  +-------+--------+
                  |                |
          AsyncReflectBuffer   SelfModelOwner
          (LLM 响应时间轴)      (CDS + Emergence)
                  |                ^
                  | advance_to_tick|
                  | (时间推进)     |
                  |                | tick(I, reflect)
                  +-------+--------+
                          |
                          v
                  AsyncSimulationStats
                  (汇总: failures / NaN / R / reflect counts)
```

## AsyncReflectBuffer 数据结构

```python
@dataclass
class PendingReflect:
    request_id: int
    submitted_at_tick: int
    expected_arrival_tick: int  # = submitted_at_tick + delay_ticks
    reflect: np.ndarray
    arrived: bool = False
    arrival_tick: int | None = None


class AsyncReflectBuffer:
    _pending: list[PendingReflect]   # heapq,按 expected_arrival_tick 排序
    _arrived: list[PendingReflect]   # 已到达但还没 drain
    _all: dict[int, PendingReflect]  # request_id → PendingReflect
    max_age_ticks: int               # 默认 10,reflect 超过这个 tick 算 stale
```

### 关键 API

- `submit(reflect, current_tick, delay_ticks) → request_id`:加入 heap
- `advance_to_tick(current_tick) → int`:把 `expected_arrival_tick <= current_tick` 的 pending 弹出,标记为 arrived。返回新 arrived 数量
- `get_latest_arrived(current_tick) → np.ndarray | None`:取最新 arrived 且未 stale 的 reflect
- `cleanup_stale(current_tick) → int`:清理超过 `max_age*2` 还没到的 pending(视为 timeout)。返回清理数量

### 为什么用 heapq?

`submit()` 是 O(log n),`advance_to_tick()` 是 O(k log n)(k = 新 arrived 数量)。最坏情况 O(n log n) 但实践中 n 受 max_age 限制,实际是 O(1) ~ O(log 100)。

### 为什么 max_age=10?

经验值:CDS tick ≈ 1 秒模拟时间,LLM 响应通常 < 5 秒。如果 LLM 响应超过 10 tick(≈ 10 秒)还没到,说明已经过时,直接 timeout。

## simulate_async_loop 流程

```python
for tick in range(n_ticks):
    # 1. 时间推进:把 expected 的 pending 转为 arrived
    buffer.advance_to_tick(tick)
    
    # 2. 清理 stale(超时未到的 pending)
    buffer.cleanup_stale(tick)
    
    # 3. 取最新 arrived reflect
    reflect = buffer.get_latest_arrived(tick) or np.zeros(8)
    
    # 4. 跑 CDS tick(同步)
    result = owner.tick(I=..., reflect=reflect)
    
    # 5. 提交下一个 reflect 请求(模拟 LLM 调用)
    buffer.submit(reflect_vec, current_tick=tick, delay_ticks=delay)
```

## 5 个 reflect_pattern

| 场景 | pattern 名 | delay_ticks | 用途 |
|------|------------|-------------|------|
| A | `pattern_synchronous` | 1 | baseline,等价同步 LLM |
| B | `pattern_fast_async` | 1-2 | 真实 LLM 响应延迟(0.5-1.5 秒) |
| C | `pattern_slow_async` | 5 | 慢 LLM(深度推理模型) |
| D | `pattern_random_jitter` | uniform(0, 8) | 极端抖动场景 |
| E | `pattern_with_timeouts` | 100(10%) | LLM 超时场景 |

## AsyncSimulationStats 字段

| 字段 | 含义 |
|------|------|
| `n_ticks` | 总 tick 数 |
| `n_solved` | solver 成功次数 |
| `n_solver_failures` | solver 失败次数 |
| `n_nan` | state 含 NaN 的次数 |
| `n_reflect_applied` | reflect 被成功应用的次数 |
| `n_reflect_dropped_stale` | reflect 因为 stale 被丢弃的次数 |
| `n_reflect_timeout` | pending 因为超时被 cleanup 的次数 |
| `state_min/max/abs_max` | state 极值 |
| `R_min/max/mean` | Kuramoto R 极值与均值 |
| `pending_peak` / `arrived_peak` | buffer 峰值大小 |

## 测试覆盖

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestAsyncReflectBuffer` | 8 | submit/advance/drain/cleanup/heap order |
| `TestAsyncSimulationScenarios` | 5 | A/B/C/D/E 5 场景 |
| `TestAsyncSimulationProperties` | 6 | R ∈ [0,1] / state 合法 / 0 NaN / buffer 不爆炸 |
| `TestReflectBufferEdgeCases` | 4 | empty / 0 delay / cleanup 无 stale |

**总计 23 个测试,全过**。

## 关键设计决策

### 决策 1:同步仿真 vs 真 async/await

**选择**:M1-T7 用**同步仿真**(单线程循环 + heapq)。**理由**:
- CDS 本身是同步 ODE 求解器,不存在真异步
- 验证"异步鲁棒性"的本质是验证 buffer 协议,跟真 LLM 异步 I/O 无关
- M5-T1 接入真 LLM 时,只需替换 `reflect_pattern(tick)` 为 `await llm_call(...)`,buffer 协议不变

### 决策 2:max_age = 10 ticks

**理由**:经验值。若 max_age 太大,buffer 累积过多;若太小,正常 LLM 响应会被误判 stale。
10 ticks ≈ 10 秒模拟时间,足以覆盖正常 LLM 响应(通常 0.5-3 秒)且及时清理异常情况。

### 决策 3:Reflect 在 stale 时直接 drop,不补默认值

**理由**:补默认值(= 全零)会让 LLM 的"未响应"跟"刻意沉默"无法区分。drop + stats 计数让 M2 reflection_audit 能识别"LLM 缺席"事件。

### 决策 4:State clip 到 [-10, 10]

**来源**:M1-T2 ship 的 CDS 设计。clip 防止 ODE 在极端输入下发散。M1-T7 探针中 state_abs_max=10.0 是因为这个 clip,不是发散信号。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Buffer peak 过高 | `cleanup_stale()` 在每 tick 调用,max_age_ticks=10 |
| Reflect 时序错乱 | `get_latest_arrived()` 按 arrival_tick 排序 |
| Stale reflect 误导 | 计入 `n_reflect_dropped_stale`,M2 可观测 |
| Timeout 请求未识别 | `cleanup_stale()` 检查 `current_tick - submitted_at_tick > max_age_ticks * 2` |