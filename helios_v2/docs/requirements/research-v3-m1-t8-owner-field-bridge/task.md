# M1-T8 OwnerFieldBridge 任务清单

## Step 1: 写 `owner_field_bridge.py`

- [x] `OwnerFieldMapping` frozen dataclass (hormone_keys / feeling_keys / salience_keys / bias / scale)
- [x] `DEFAULT_MAPPINGS` 8 个默认映射
- [x] `OwnerFieldBridge` dataclass
  - [x] `default()` classmethod
  - [x] `with_mappings()` classmethod
  - [x] `bridge_input(h, f, s) → 8-dim I`
  - [x] `bridge_reflect(aspect_state, history?) → 8-dim reflect`(M2 预留)
  - [x] `describe_mapping() → str`
- [x] 4 个 fixture:neutral / high_positive / high_threat / low_energy

## Step 2: 更新 `__init__.py`

- [x] 添加 `from .owner_field_bridge import OwnerFieldBridge, OwnerFieldMapping`
- [x] 添加到 `__all__`

## Step 3: 写测试 `test_owner_field_bridge.py`

- [x] `TestOwnerFieldBridgeMapping` (4 tests)
- [x] `TestOwnerFieldBridgeSemantics` (5 tests)
- [x] `TestOwnerFieldBridgeReflect` (3 tests)
- [x] `TestOwnerFieldBridgeIntegration` (4 tests)
- [x] `TestOwnerFieldMapping` (2 tests)
- [x] `TestOwnerFieldBridgeDescribe` (2 tests)
- [x] **总计 20 tests 全过**

## Step 4: 写探针 `r_v3_m1_t8_probe.py`

- [x] 4 fixtures × 250 ticks = 1000 tick 轮询
- [x] 输出 summary + trace JSON
- [x] 检查 solver/NAN/R 范围 + fixture 分布

## Step 5: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 6: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)