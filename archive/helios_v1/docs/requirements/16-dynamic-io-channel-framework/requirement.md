# Requirement 16 - Dynamic I/O Channel Framework

## 1. Background and Problem
当前 Helios 的 channel abstraction 已经具备 descriptor、poll/send 和 gateway wiring，但 channel 子系统仍然主要以静态集成方式运行。`helios_main.py` 在启动阶段直接实例化并注册 QQ、CLI、TTS、STT、Vision 等 channel；channel lifecycle 仍主要通过 `connect()` / `disconnect()` 等直接方法驱动；channel config 仍主要以全局配置字段加 constructor 注入的方式散落在 runtime wiring 中。

这种结构不足以支撑后续的多 channel 扩展和治理要求。新增或移除 channel 仍需要修改主初始化逻辑；planner、gateway 和 runtime 仍会直接依赖具体 channel 的方法级语义；`init`、`deinit`、`pause`、`resume`、`suspend`、`unsuspend`、`get_config`、`update_config` 等生命周期和配置操作没有被 formalize 为统一 ops；channel config 也没有成为每个 channel 各自拥有的独立 contract。

如果继续在当前结构上追加 channel，系统会越来越依赖 `helios_main.py` 的静态 wiring 和 channel-specific side effects，违反架构哲学中对来源、能力、治理、边界清晰度的要求，也会削弱未来将 channel 彻底从系统耦合中摘干净的目标。

## 2. Goal
将 Helios 的 I/O channel 子系统升级为一个动态、可扩展、以 channel-exposed ops 为唯一交互边界的 framework，使 channel 的注册、反注册、初始化、反初始化、暂停、恢复、挂起、解除挂起、配置读取、配置更新和健康检查都通过正式 descriptor 和 ops contract 完成，其他模块不再直接调用具体 channel 方法或依赖其内部配置结构。

## 3. Functional Requirements
### 3.1 Dynamic Channel Registration
1. Channel framework must support runtime registration and deregistration of channel instances without requiring a Helios process restart.
2. `ChannelGateway` must become the owner of channel registry state and runtime add/remove operations.
3. Runtime registration and deregistration must preserve channel descriptor discoverability and status visibility.

### 3.2 Lifecycle Ops Contract
1. Every managed channel must expose lifecycle management through formal channel ops rather than only direct Python methods.
2. At minimum, the framework must support `init`, `deinit`, `pause`, `resume`, `suspend`, `unsuspend`, and `health_check` as management ops or explicit compatibility aliases.
3. If `connect` and `disconnect` remain during migration, they must be treated as lifecycle compatibility ops rather than the long-term primary boundary.
4. Lifecycle execution results must be observable through structured ack payloads and status transitions.

### 3.3 Channel-Owned Config Contract
1. Each channel must own an explicit config contract describing its current configuration snapshot, mutable fields, immutable fields, and validation constraints.
2. The framework must expose `get_config` and `update_config` as formal management ops for channels that support runtime configuration.
3. Global runtime wiring may provide bootstrap defaults, but channel configuration semantics must not remain hardcoded in `helios_main.py` constructor call sites.
4. Channel config updates must be validated at the channel owner boundary before they affect runtime behavior.

### 3.4 Op-Only Invocation Boundary
1. Modules outside the channel framework must invoke channel behavior through descriptor-declared ops instead of calling concrete channel lifecycle or transport methods directly.
2. Outbound execution, lifecycle control, and config mutation must all route through the channel framework op boundary.
3. The framework may keep polling as a framework-owned loop during migration, but the polling capability must still be modeled as a first-class input op in the descriptor contract.

### 3.5 Status and Capability Semantics
1. Channel status must support lifecycle-relevant states beyond connected/disconnected, including paused and suspended semantics.
2. The framework must expose a descriptor snapshot containing supported input ops, output ops, management ops, config capabilities, and health signals for every registered channel.
3. Capability discovery must remain transport-agnostic so planner and executor layers can reason about channels without importing concrete channel classes.

## 4. Non-Functional Requirements
1. Dynamic registration, deregistration, and lifecycle op execution must not block the main tick longer than the concrete channel operation requires, and failures must degrade locally rather than crashing the runtime.
2. Every lifecycle/config operation must emit structured logs sufficient to diagnose owner, op name, target channel, result, and failure reason.
3. The first rollout must be migration-safe: existing channels may adapt through compatibility methods while the new op contract is phased in.
4. The initial implementation may remain default-off for fully dynamic runtime control, but the descriptor and op boundary introduced by this requirement must be default-on once landed.

## 5. Code Behavior Constraints
1. `helios_main.py` must not continue expanding concrete channel constructor logic and channel-specific lifecycle control beyond bootstrap wiring needs.
2. Planner, executor, and other runtime modules must not directly call `connect()`, `disconnect()`, `send()`, or other channel-specific lifecycle methods on concrete channel instances once equivalent framework ops exist.
3. New channel implementations must not rely on global config fields as their only configuration boundary; each channel must expose a channel-owned config contract.
4. The channel framework must not encode channel-specific management logic in `ChannelGateway` branches when the same behavior can be expressed through channel descriptor metadata and op dispatch.
5. Lifecycle/config semantics must be implemented as runtime behavior and not only as documentation or logging conventions.

## 6. Impacted Modules
1. `helios_io/channel.py`
2. `helios_io/channel_gateway.py`
3. `helios_main.py`
4. `helios_io/planning.py`
5. `helios_io/limb.py`
6. `helios_io/channels/cli_channel.py`
7. `helios_io/channels/qq_channel.py`
8. `helios_io/channels/tts_channel.py`
9. `helios_io/channels/stt_channel.py`
10. `helios_io/channels/vision_channel.py`
11. `tests/test_channel_gateway.py`
12. `tests/test_cli_channel.py`
13. `tests/test_qq_channel.py`
14. `tests/test_multimodal_channels.py`

## 7. Acceptance Criteria
1. A focused runtime test can register a channel instance into `ChannelGateway`, query its descriptor, deregister it, and observe that the descriptor disappears without restarting Helios.
2. A focused test can invoke lifecycle management through formal management ops for at least one concrete channel and observe valid status transitions or compatibility ack results.
3. A focused test can call `get_config` and `update_config` for at least one concrete channel and observe validated config snapshots through the channel owner boundary.
4. Outbound routing still succeeds through descriptor-declared ops after the framework changes, and existing focused channel routing tests continue to pass.
5. The framework exposes paused and suspended lifecycle semantics in status/descriptors without regressing existing connected/disconnected behavior.
6. Focused logging or ack assertions can verify target channel id, op name, success/failure result, and failure reason for lifecycle/config operations.
