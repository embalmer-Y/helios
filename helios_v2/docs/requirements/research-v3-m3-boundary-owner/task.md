# M3 Boundary Owner 任务清单

## Step 1: 写 `__init__.py` (M3 package)

- [x] 创建 `helios_v2/src/helios_v2/research_v3_m3/__init__.py`
- [x] 导出 Signal / SignalType / MarkovBlanketBoundary / ConditionalSeparationResult
- [x] 导出 check_conditional_separation_partial_corr / mutual_info
- [x] 导出 BoundaryOwner / BoundaryCrossing / NestedSubsystem
- [x] 导出 DEFAULT_PARTIAL_CORR_THRESHOLD

## Step 2: 写 `signals.py`

- [x] `SignalType` enum (4 values)
- [x] `Signal` frozen dataclass (signal_id, type, source, target, payload, timestamp)
- [x] `Signal.make()` 工厂方法自动生成 UUID + timestamp
- [x] `__repr__` 自定义

## Step 3: 写 `markov_blanket.py`

- [x] `_partial_correlation()` 内部辅助
- [x] `_mutual_information()` 内部辅助
- [x] `check_conditional_separation_partial_corr()` 公开 API
- [x] `check_conditional_separation_mutual_info()` 公开 API
- [x] `ConditionalSeparationResult` frozen dataclass
- [x] `MarkovBlanketBoundary` dataclass
  - [x] ALL_SUBSYSTEMS 类常量 (4 个 subsystem 名)
  - [x] record_internal / record_external / record_sensory
  - [x] add_sensory_signal / add_active_signal / add_external_signal (类型验证)
  - [x] check_separation(subsystem, method)
  - [x] check_all_subsystems
  - [x] get_stats

## Step 4: 写 `boundary_owner.py`

- [x] `NestedSubsystem` dataclass (name, state, update_fn, layer)
- [x] `BoundaryCrossing` frozen dataclass
- [x] `BoundaryOwner` 类
  - [x] `__init__` (subsystems, mb, partial_corr_threshold, enforce_separation_check)
  - [x] `check_signal(signal)` - 4 信号类型 + 强制不变量检查
  - [x] `_on_signal_admitted(signal)` - 内部方法
  - [x] `_extract_scalar(payload)` - payload 标量化
  - [x] `check_signal_dry(signal)` - 不自动记录版本
  - [x] `cross(signal)` - check_signal 别名
  - [x] `update_subsystem(name, sensory_payload)` - 更新 + 记录 internal
  - [x] `update_all_subsystems(sensory_payload)`
  - [x] `emit_active(source, target, payload)` - 子系统发 active
  - [x] `record_external(value)` - 记录外部世界状态
  - [x] `get_stats()`
  - [x] `get_audit_log(signal_type, admitted_only)` - 多维过滤
  - [x] `clear_audit_log()` - 返回清空数量
  - [x] `stage_22_boundary_enforcement()` - 25 stage 接入

## Step 5: 写测试 `test_boundary_owner.py`

- [x] `TestSignal` (5 tests)
- [x] `TestMarkovBlanketBoundary` (5 tests)
- [x] `TestConditionalSeparation` (7 tests,含 linear/nonlinear + edge cases)
- [x] `TestBoundaryOwnerCheckSignal` (7 tests)
- [x] `TestBoundaryOwnerAuditLog` (5 tests)
- [x] `TestBoundaryOwnerSubsystemUpdate` (4 tests)
- [x] `TestBoundaryOwnerEmitActive` (2 tests)
- [x] `TestBoundaryOwnerSeparationEnforcement` (3 tests)
- [x] `TestBoundaryOwnerStage22` (3 tests)
- [x] `TestEndToEnd` (4 tests)
- [x] **总计 45 tests 全过**

## Step 6: 写探针 `r_v3_m3_probe.py`

- [x] 1000 tick BoundaryOwner
- [x] 用 check_signal_dry + manual record 保证样本对齐
- [x] 每 100 tick 验证 separation(9 个 checkpoint)
- [x] 输出 summary + trace JSON
- [x] 全局断言:信号计数 + stage 22 all_passed

## Step 7: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 8: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)