# Requirement 16 - Dynamic I/O Channel Framework

## 1. Design Overview
本设计把 Helios 的 channel abstraction 从“静态 wiring 的 transport adapter”升级为“动态 registry + op router + lifecycle/config framework”。目标不是仅给现有 channel 增加几个新方法，而是把 channel 的生命周期、配置、发现和能力调用提升为正式 runtime concern，使 planner、executor、gateway 与主循环都通过统一的 descriptor/op contract 与 channel 交互。

## 2. Current State and Gap
当前 gap：

1. `helios_main.py` 直接实例化并注册具体 channel，channel add/remove 仍是静态 bootstrap 行为。
2. `ChannelGateway` 负责 inbound poll 和 outbound route，但尚未成为统一 lifecycle/config op owner。
3. `ChannelStatus` 只能表达 connected/disconnected/error/reconnecting，无法覆盖 pause/suspend/deinit 等状态。
4. `ChannelDescriptor` 与 `ChannelOpDescriptor` 已存在，但 lifecycle/config 管理能力没有被 formalize 为统一 management ops。
5. channel config 仍然主要由 constructor 参数和全局 config 注入，缺少 channel-owned snapshot/update contract。
6. 现有 planner/executor 仍隐含依赖 send/connect/disconnect 这类具体方法语义，而不是完全收敛到 framework op plane。

## 3. Target Architecture
目标结构：

1. `helios_io/channel.py` 作为 channel contract owner，扩展：
   - lifecycle-aware `ChannelStatus`
   - channel-owned config snapshot/update contract
   - generic management op execution contract
2. `helios_io/channel_gateway.py` 作为：
   - runtime registry owner
   - descriptor snapshot owner
   - lifecycle/config op router
   - outbound op dispatcher
3. 具体 channel (`cli_channel.py`、`qq_channel.py`、`tts_channel.py` 等) 负责：
   - descriptor declaration
   - lifecycle/config op implementation
   - local validation and state transition
4. `helios_main.py` 仅保留 bootstrap wiring owner，不再持续扩张为 channel lifecycle/config owner。
5. planner/executor 层继续依赖 descriptor-declared ops，不新增 concrete-channel bypass。

### 3.1 Runtime Flow
目标 runtime flow：

1. bootstrap 阶段创建初始 channel 实例并注册到 `ChannelGateway`
2. runtime 通过 gateway 查询 descriptor snapshot
3. outbound action 通过 output op dispatch 路由到目标 channel
4. lifecycle/config action 通过 management op dispatch 路由到目标 channel
5. channel 返回 ack/result，并更新自身状态
6. gateway 记录结果、对外暴露状态和 descriptor snapshot

## 4. Data Structures
### 4.1 ChannelConfigDescriptor
```text
config_key
description
required
mutable_at_runtime
default_value
schema_hint
```

### 4.2 ChannelConfigSnapshot
```text
channel_id
status
config_values
mutable_fields
validation_errors
```

### 4.3 ChannelManagementResult
```text
channel_id
op_name
success
status
message
payload
error_code
```

### 4.4 ChannelLifecycleState
```text
status
initialized
connected
paused
suspended
last_error
```

## 5. Module Changes
1. `helios_io/channel.py`
   - 扩展 `ChannelStatus` 支持 lifecycle-aware state。
   - 增加 config descriptor/snapshot/result contract。
   - 增加默认 `execute_management_op()`、`get_config_snapshot()`、`update_config()`、`health_check()` 兼容边界。
2. `helios_io/channel_gateway.py`
   - 新增 generic management op dispatch。
   - 保留现有 outbound route，并统一为 descriptor/op-aware router。
   - 暴露 runtime registry discovery helper。
3. `helios_io/channels/cli_channel.py`
   - 作为第一阶段样板 channel。
   - 实现 lifecycle/config op 支持。
   - 将本地命令与 framework management op 对齐。
4. `helios_main.py`
   - 第一阶段仅保持 bootstrap wiring，不新增新耦合。
   - 后续可把 channel config bootstrap 改造成 per-channel config payload 注入。
5. 其他 channel owners
   - 第二阶段逐步迁移到统一 lifecycle/config op contract。

## 6. Migration Plan
1. 先创建 requirement/design/task，并同步 index。
2. 第一阶段扩展 `channel.py` 与 `channel_gateway.py` 的 contract 和 generic dispatch，不破坏现有 send/poll path。
3. 第二阶段把 `CLIChannel` 迁移成样板，实现 lifecycle/config op 支持。
4. 第三阶段为其他 channel 增加 compatibility adapters 或原生实现。
5. 第四阶段收紧 `helios_main.py` 和 executor 对 concrete channel methods 的依赖。

默认 rollout：

1. 新的 descriptor/op contract default-on。
2. fully dynamic runtime channel management default-off，先通过 tests/owner APIs 收敛。
3. 兼容期允许 `connect` / `disconnect` 继续存在，但通过 management op 路由对外暴露。

## 7. Failure Modes and Constraints
1. 若 channel 不支持某个 management op，framework 必须返回结构化失败结果，而不是 silent no-op。
2. 若 runtime config 更新校验失败，原配置必须保持有效，不得进入半更新状态。
3. 若 lifecycle op 执行抛错，channel 状态必须退回到明确错误或前置稳定状态。
4. 若某个 channel 未完成迁移，framework 必须允许 compatibility behavior，但 descriptor 需要显式反映 capability 缺失。
5. 第一阶段不强制把所有 inbound path 都改成 generic input op dispatcher，但 poll 必须继续保持 descriptor 可见性和 owner 清晰度。

## 8. Observability and Logging
必须记录：

1. channel register / deregister 事件
2. management op dispatch：target、op、result、status
3. config snapshot / update 摘要
4. lifecycle state transition
5. compatibility fallback 是否被触发
6. outbound op routing 和 lifecycle/config op routing 的失败原因

## 9. Validation Strategy
1. focused tests 验证 gateway register/deregister 和 descriptor snapshot。
2. focused tests 验证 management op dispatch 成功/失败路径。
3. focused tests 验证 CLIChannel 的 get/update config 与 lifecycle state transition。
4. focused tests 验证现有 outbound route 不回归。
5. 后续阶段再扩展 QQ/multimodal channel coverage，验证 compatibility migration path。
