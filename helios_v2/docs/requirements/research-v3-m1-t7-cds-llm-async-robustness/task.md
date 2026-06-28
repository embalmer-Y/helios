# M1-T7 CDS 跟 LLM 异步鲁棒性任务清单

## Step 1: 写 `async_loop.py`

- [x] `PendingReflect` dataclass (含 __lt__ 用于 heapq)
- [x] `AsyncReflectBuffer` 类
  - [x] __init__ (max_age_ticks=10)
  - [x] submit() → request_id
  - [x] advance_to_tick() → 新 arrived 数量
  - [x] drain_arrived() → 按 arrival_tick 降序
  - [x] get_latest_arrived() → 最新 arrived reflect
  - [x] cleanup_stale() → 清理超时 pending
  - [x] pending_count() / arrived_count() / total_in_flight()
- [x] `AsyncSimulationStats` dataclass
  - [x] update_R / update_state
  - [x] R_mean property
  - [x] to_dict()
- [x] `simulate_async_loop(owner, n_ticks, reflect_pattern, seed)` 函数
- [x] 5 个 reflect_pattern: synchronous / fast_async / slow_async / random_jitter / with_timeouts

## Step 2: 写测试 `test_async_robustness.py`

- [x] `TestAsyncReflectBuffer` (8 tests)
  - [x] submit_and_advance
  - [x] get_latest_returns_none_if_empty
  - [x] get_latest_returns_fresh
  - [x] stale_arrived_dropped
  - [x] pending_timeout_cleanup
  - [x] multiple_pending_with_different_delays
  - [x] heap_order_is_by_arrival_tick
  - [x] drain_arrived_returns_sorted_by_recency
- [x] `TestAsyncSimulationScenarios` (5 tests: A/B/C/D/E)
- [x] `TestAsyncSimulationProperties` (6 tests: R bounds / state bounds / 0 NaN / buffer 不爆炸)
- [x] `TestReflectBufferEdgeCases` (4 tests)
- [x] **总计 23 tests 全过**

## Step 3: 写探针 `r_v3_m1_t7_probe.py`

- [x] 5 场景 × 1000 tick = 5000 total
- [x] 输出 summary JSON
- [x] 全局断言:0 failure, 0 NaN, R ∈ [0, 1], state |·| < 30

## Step 4: 更新 `__init__.py`

- [x] 添加 `from .async_loop import AsyncReflectBuffer, simulate_async_loop, AsyncSimulationStats`

## Step 5: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 6: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)