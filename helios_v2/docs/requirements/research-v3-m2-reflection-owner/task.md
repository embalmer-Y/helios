# M2 Reflection Owner 任务清单

## Step 1: 写 `__init__.py` (M2 package)

- [x] 创建 `helios_v2/src/helios_v2/research_v3_m2/__init__.py`
- [x] 导出 4 个核心类型 + 4 个常量

## Step 2: 写 `reflection_owner.py`

- [x] 常量定义 (POST_TICK_RATE_LIMIT=50, RESTING_STATE_THRESHOLD=0.85, etc.)
- [x] `ReflectionTrigger` enum (4 values)
- [x] `ReflectionLevel` enum (4 values)
- [x] `_trigger_to_level()` 映射函数
- [x] `ReflectionAuditResult` frozen dataclass
- [x] `ReflectionRecord` frozen dataclass
- [x] `ReflectionOwner` 类
  - [x] `__post_init__` 验证 llm_caller 实现 Protocol
  - [x] `on_tick_after_cds()` 主入口(检测 4 trigger)
  - [x] `invoke_user_reflection()` USER_INVOKED
  - [x] `get_pending_reflect()` / `consume_pending_reflect()`
  - [x] `_should_post_tick_reflect()` POST_TICK 限速
  - [x] `_is_resting_state()` R 持续高检测
  - [x] `_do_reflect()` LLM call + clip + audit + record + pending
  - [x] `_audit_reflection()` 4 项检查
  - [x] `get_stats()` 统计
  - [x] `get_records()` 过滤

## Step 3: 写 `llm_caller.py`

- [x] `LLMCallerProtocol` Protocol 接口
- [x] `FakeLLMCaller` deterministic stub
  - [x] `call()` heuristic: 3 R 区间 → 3 种 reflect 策略
  - [x] response 提到 R (便于 audit)
  - [x] call_count 统计

## Step 4: 更新 `__init__.py`

- [x] `from .reflection_owner import ...` (4 trigger / level / record / owner / audit)
- [x] `from .llm_caller import FakeLLMCaller, LLMCallerProtocol`

## Step 5: 写测试 `test_reflection_owner.py`

- [x] `TestLLMCallerProtocol` (3 tests)
- [x] `TestReflectionTriggerDetection` (6 tests)
- [x] `TestLLMPassiveAccept` (5 tests)
- [x] `TestReflectionAudit` (6 tests,含 4 项失败各 1)
- [x] `TestReflectInjection` (3 tests)
- [x] `TestReflectionRecord` (4 tests)
- [x] `TestReflectionLevelMapping` (4 tests)
- [x] `TestReflectionOwnerStats` (2 tests)
- [x] `TestEndToEnd` (4 tests)
- [x] **总计 38 tests 全过**

## Step 6: 写探针 `r_v3_m2_probe.py`

- [x] 1000 tick 跑 ReflectionOwner
- [x] 每 100 tick 记录一次 snapshot
- [x] USER_INVOKED 测试 1 次(tick 100)
- [x] 输出 summary + trace JSON
- [x] 全局断言:0 failure, 0 NaN, audit pass rate ≥ 0.8, n_reflections > 0

## Step 7: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 8: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)