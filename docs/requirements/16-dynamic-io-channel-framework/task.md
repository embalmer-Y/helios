# Requirement 16 - Dynamic I/O Channel Framework

## 1. Task Breakdown
### T16-1 Author Requirement Package
1. 创建 `16-dynamic-io-channel-framework/requirement.md`。
2. 创建 `16-dynamic-io-channel-framework/design.md`。
3. 创建 `16-dynamic-io-channel-framework/task.md`。
4. 更新 `docs/requirements/index.md`，同步 R16 的状态、依赖与实施顺序。
5. 验证：按 requirement authoring standard 做文档 review。

### T16-2 Extend Channel Core Contracts
1. 扩展 `helios_io/channel.py` 的 lifecycle-aware status。
2. 增加 channel-owned config descriptor/snapshot/result contract。
3. 增加 generic management op compatibility boundary。
4. 验证：focused channel contract tests。

### T16-3 Upgrade ChannelGateway To Registry And Op Router
1. 在 `helios_io/channel_gateway.py` 中加入 management op dispatch。
2. 暴露 register/deregister discovery helpers 和 op-aware result surface。
3. 保持现有 outbound route 不回归。
4. 验证：`tests/test_channel_gateway.py` focused coverage。

### T16-4 Migrate CLIChannel As Reference Implementation
1. 在 `helios_io/channels/cli_channel.py` 中实现 lifecycle/config op 支持。
2. 让 CLI channel descriptor 暴露新 management ops 和 config semantics。
3. 保持普通文本 path 与本地 command path 不回归。
4. 验证：`tests/test_cli_channel.py`。

### T16-5 Add Compatibility Coverage For Existing Channel Paths
1. 验证 gateway outbound routing 仍能通过 descriptor-declared output ops 工作。
2. 验证未完全迁移的 channel 在 compatibility mode 下仍可被 registry/gateway 管理。
3. 为 QQ 或一个 multimodal channel 补最小 compatibility regression。
4. 验证：`tests/test_qq_channel.py`、`tests/test_multimodal_channels.py` focused cases。

### T16-6 Reduce Bootstrap Coupling
1. [x] 审计 `helios_main.py` 中的 channel constructor/config wiring。
2. [x] 收缩主循环中的 channel-specific lifecycle side effects，只保留 bootstrap owner 必需逻辑。
3. [x] 为后续 per-channel config bootstrap 预留 payload 注入边界。
4. [x] 将 optional channel bootstrap spec/factory registry 从 `Helios` 私有缓存收敛为 owner API。
5. [x] 将默认 optional channel payload 构建下沉到各 channel owner module。
6. [x] 将 `helios_io/optional_channel_bootstrap.py` 从静态默认 roster 组装收敛为 default builder registry owner。
7. [x] 将默认 optional roster 来源收敛为显式 config-driven builder selection (`HeliosConfig.OPTIONAL_CHANNEL_BOOTSTRAP_IDS`)。
8. [x] 将 optional bootstrap spec/factory registry 从 `Helios` 持有字段收敛为独立 owner (`OptionalChannelBootstrapRegistry`)。
9. [x] 将 optional bootstrap register/deregister/bootstrap_all orchestration 从 `Helios` 转发层收敛为独立 service owner (`OptionalChannelBootstrapManager`)。
10. [x] 将 optional bootstrap public facade 从 `Helios` 平铺 API 收敛为单一 runtime owner (`Helios.optional_channels`)。
11. [x] 将 optional bootstrap active/dormant summary 与 bootstrap warning logging 从 `Helios` 初始化段下沉到 `OptionalChannelRuntime`。
12. [x] 将 optional channel runtime observability 收敛为 owner snapshot，并由 `Helios` 通过 owner snapshot 暴露状态而不是散落查询。
13. [x] 将 `HeliosState` 中固定的 optional channel availability 语义收敛为动态 `channel_availability`，旧的 `tts/stt/vision` 字段仅保留兼容镜像。
14. [x] 验证：focused runtime wiring checks。

## 2. Dependencies
1. T16-1 依赖无前置。
2. T16-2 依赖 T16-1。
3. T16-3 依赖 T16-2。
4. T16-4 依赖 T16-2、T16-3。
5. T16-5 依赖 T16-3、T16-4。
6. T16-6 依赖 T16-3，建议在 T16-4 之后推进。

## 3. Files and Modules
1. `docs/requirements/16-dynamic-io-channel-framework/requirement.md`
2. `docs/requirements/16-dynamic-io-channel-framework/design.md`
3. `docs/requirements/16-dynamic-io-channel-framework/task.md`
4. `docs/requirements/index.md`
5. `helios_io/channel.py`
6. `helios_io/channel_gateway.py`
7. `helios_io/channels/cli_channel.py`
8. `helios_main.py`
9. `tests/test_channel_gateway.py`
10. `tests/test_cli_channel.py`
11. `tests/test_qq_channel.py`
12. `tests/test_multimodal_channels.py`

## 4. Implementation Order
1. T16-1
2. T16-2
3. T16-3
4. T16-4
5. T16-5
6. T16-6

## 5. Validation Plan
1. 先做文档级 review，确认 requirement/design/task/index 对齐。
2. channel contract 第一次 substantive edit 后，优先跑 `tests/test_channel_gateway.py` 的 focused validation。
3. CLI channel 第一次 substantive edit 后，优先跑 `tests/test_cli_channel.py`。
4. compatibility 扩展后，再跑 QQ/multimodal focused validation。
5. 任何 lifecycle/config op 改动后，都要验证 descriptor snapshot 和 status transition。

## 6. Completion Criteria
1. R16 requirement package 已创建并同步到 requirements index。
2. `channel.py` 已提供 lifecycle/config op 的正式 contract 边界。
3. `ChannelGateway` 已支持 management op dispatch 和动态 register/deregister visibility。
4. 至少一个 concrete channel 已完成 lifecycle/config op 样板迁移。
5. focused tests 已覆盖动态 registry、management op、config snapshot/update 和兼容 outbound route。
6. 主循环对 concrete channel 的耦合已缩减到 bootstrap wiring 范围内。

## 7. Implementation Record
1. 2026-05-28: `Helios` 新增 optional channel bootstrap spec/factory owner API，删除 optional channel instance cache，focused validation：`pytest tests/test_multimodal_channels.py -q`、`pytest tests/test_tick_response_wiring.py tests/test_cli_brain_like_evaluation.py -q`。
2. 2026-05-28: 默认 optional channel payload 构建下沉到 `helios_io/channels/cli_channel.py`、`tts_channel.py`、`stt_channel.py`、`vision_channel.py`，聚合层缩减为 registry assembly。
3. 2026-05-28: `helios_io/optional_channel_bootstrap.py` 新增 default builder registry register/deregister/query boundary，并补 focused registry test，作为 T16-6 持续推进记录。
4. 2026-05-28: `HeliosConfig` 新增 `OPTIONAL_CHANNEL_BOOTSTRAP_IDS`，默认 optional roster 改为配置驱动的 builder selection，并补 focused roster selection regression。
5. 2026-05-28: `OptionalChannelBootstrapRegistry` 成为 optional bootstrap spec/factory owner，`Helios` 仅保留 runtime bootstrap/deregister 编排与公开 owner API 转发。
6. 2026-05-28: `OptionalChannelBootstrapManager` 成为 optional bootstrap register/deregister/bootstrap orchestration owner；`Helios` 只提供 runtime callback 并转发公开 API。
7. 2026-05-28: optional bootstrap public facade 收敛为 `Helios.optional_channels` 单一 runtime owner；`Helios` 删除平铺的 optional bootstrap get/register/deregister API。
8. 2026-05-28: optional bootstrap active/dormant summary 与 bootstrap warning logging 下沉到 `OptionalChannelRuntime`；`Helios` 初始化不再维护 optional channel bootstrap 汇总循环。
9. 2026-05-28: optional channel runtime observability 收敛为 owner snapshot；`Helios` `_tick_once()` 与 `get_state()` 改为消费 `OptionalChannelRuntime` snapshot，而不是散落的 availability 查询。
10. 2026-05-28: `HeliosState` 新增动态 `channel_availability`，主循环不再在 tick state 构建时硬编码 `tts/stt/vision` availability；旧字段降级为兼容镜像。
11. 2026-05-28: `ChannelGateway` 成为 runtime channel register/deregister owner；`Helios.register_runtime_channel()` 与 `deregister_runtime_channel()` 收缩为委托，focused validation：`pytest tests/test_channel_gateway.py tests/test_multimodal_channels.py -q`，adjacent validation：`pytest tests/test_tick_response_wiring.py tests/test_cli_brain_like_evaluation.py -q`。
12. 2026-05-28: inbound polling 改为经由 `ChannelGateway.execute_input_op()` 走正式 input op boundary；`Helios` 初始化中的 QQ channel bootstrap 也切到 `ChannelGateway.register_runtime_channel(..., connect=False)`，focused validation：`pytest tests/test_channel_gateway.py -q`、`pytest tests/test_channel_gateway.py tests/test_multimodal_channels.py -q`，adjacent validation：`pytest tests/test_tick_response_wiring.py tests/test_cli_brain_like_evaluation.py -q`。
13. 2026-05-28: `ChannelGateway` 新增 runtime snapshot owner boundary，统一暴露 descriptor/status owner view；`Helios` 的被动回复、thought bridge、active trigger、preconscious fallback 与 routing consistency 检查改为消费 snapshot，而不再在主循环中反复拼装 `get_channel_descriptors()`/`get_channel_status()`，focused validation：`pytest tests/test_channel_gateway.py -q`、`pytest tests/test_tick_response_wiring.py -q`。
14. 2026-05-28: `ChannelGateway` 补齐显式 config/health owner API（`get_channel_config_snapshot`、`update_channel_config`、`health_check_channel`），`ThinkingEngineIntegration` 的 channel discovery 切到 gateway runtime snapshot owner，CLI evaluation harness 的 channel connect 也改为优先走 gateway management op boundary；focused validation：`pytest tests/test_channel_gateway.py -q`，adjacent validation：`pytest tests/test_cli_brain_like_evaluation.py tests/test_cli_channel.py tests/test_qq_channel.py tests/test_multimodal_channels.py tests/test_tick_response_wiring.py -q`。
15. 2026-05-28: R16 完成并关闭；requirements index 状态切换为 `closed`，后续仅做回归维护，不再扩写 requirement 范围。
