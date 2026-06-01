# Requirement 13 - Terminal CLI Channel

## 1. Design Overview

本设计把本地终端交互提升为正式 runtime channel，而不是开发时临时 REPL。目标是让 terminal stdin/stdout 与 QQ 等 channel 一样接入 `ChannelGateway` 和现有 thought/action owner path，同时把本地 CLI 管理命令定义为独立于普通用户刺激的管理边界。

## 2. Current State and Gap

当前 gap：

1. `helios_io/channels/` 下没有正式 terminal/CLI bidirectional channel owner。
2. 现有架构已具备 channel abstraction、descriptor、poll/send、stimulus contract 和 outbound route，但本地终端场景没有正式接入口。
3. 若直接追加终端交互，最容易出现的错误是把 stdin/stdout 实现在主循环中，形成同步 REPL bypass。
4. 终端管理命令与普通文本消息的边界尚未被 formalize。
5. 本地 session 的 `user_id` / `session_name` 配置和 conversation boundary 没有明确 owner。

## 3. Target Architecture

目标结构：

1. 新增 `helios_io/channels/cli_channel.py` 作为 terminal CLI channel 的正式 owner。
2. 该 channel 实现 `BidirectionalChannel`，并向 `ChannelGateway` 暴露正式 descriptor。
3. channel 内部使用后台 stdin reader + thread-safe queue 读取输入，`poll()` 仅负责非阻塞 drain queue。
4. 普通文本输入路径为：
   - terminal stdin
   - CLIChannel reader
   - queued inbound record
   - `poll()` -> `ChannelMessage`
   - `ChannelGateway` stimulus evaluation
   - `helios_main.py` tick / thought path
5. 普通文本输出路径为：
   - thought / policy / planner
   - executor
   - `ChannelGateway.route_outbound()`
   - `CLIChannel.send()`
   - stdout rendered text
6. CLI 管理命令路径与普通文本分离：
   - command line enters CLI owner
   - command parser identifies management command
   - local management output or orderly runtime control is executed
   - command result does not masquerade as ordinary user stimulus

## 4. Data Structures

### 4.1 CLIChannelConfig

```text
channel_id
user_id
session_name
prompt_prefix
enable_commands
command_prefix
stdout_flush
``` 

### 4.2 CLIInboundEnvelope

```text
raw_text
received_at
user_id
session_name
is_command
command_name
command_args
``` 

### 4.3 CLICommandResult

```text
command_name
handled
rendered_lines
requests_shutdown
exposes_state_summary
history_scope
error_message
``` 

### 4.4 TerminalRenderRecord

```text
original_text
rendered_text
expression_profile
channel_id
user_id
rendered_at
``` 

## 5. Module Changes

1. `helios_io/channels/cli_channel.py`
   - 新增 terminal CLI channel owner。
   - 实现非阻塞 stdin reader、queue drain、command parsing 与 stdout render。
   - 仅拥有 CLI-specific command/session/render 生命周期；普通文本的 SEC/trigger/cognitive-impact 注释必须复用共享 text-annotation owner，不得反向依赖 QQ channel owner。
   - 暴露 bidirectional descriptor 与最小 management ops。
2. `helios_io/channels/inbound_text_annotation.py`
   - 新增共享 text inbound annotation owner。
   - 负责 text -> SEC result -> event_triggers -> cognitive_impact 的通用转换。
   - 供 CLI / QQ / STT 等文本类 channel 复用，避免 channel-to-channel 依赖。
3. `helios_io/channel.py`
   - 若现有 descriptor/op metadata 不足，可补充 terminal-specific capability summary，但不得破坏现有 channel owner。
4. `helios_io/channel_gateway.py`
   - 复用现有 inbound poll / outbound route 机制，不新增 CLI bypass path。
5. `helios_main.py`
   - 新增 CLI channel 注册与 startup config 注入点。
   - 仅负责 wiring 与跨-channel runtime side effect coordination，不直接持有 terminal REPL loop，也不得把 CLI inbound side effect 伪装成 QQ-specific owner logic。
6. `helios_io/prompt_contract.py`
   - 复用现有 channel/op contract；必要时补充 terminal channel descriptor summary 进入 prompt builder。
7. `helios_io/response_pipeline.py`
   - 复用已有 conversation/history helper，不新增 CLI-special reply owner。
8. `tests/`
   - 增加 channel owner、command boundary、wiring 和 manual path 的 focused coverage。

## 6. Migration Plan

1. 先新增 CLI channel owner 与最小 config/data structures。
2. 再实现非阻塞 stdin reader 与 outbound render。
3. 再引入 command parser/dispatcher，锁定普通文本与管理命令边界。
4. 再把 CLI channel 注册到 `helios_main.py` 的 channel bootstrap 流程。
5. 最后补 focused tests 与 manual validation flow。

默认 rollout 建议：

1. CLI channel default-off，通过显式 config / startup flag 启用。
2. 启用后它成为正式 connected local channel，可与其他 channel 共存。
3. standalone launcher 不属于本轮正式 owner，只可作为未来薄包装层。

## 7. Failure Modes and Constraints

1. 若 stdin 不可读或 reader thread 启动失败，CLI channel 必须进入明确非 connected / degraded 状态。
2. 若 stdout 写失败，`send()` 必须返回失败并保留可审计 trace。
3. 若 command parsing 失败，CLI owner 必须返回受控错误文本，不得把原始命令静默丢弃。
4. `/state` 与 `/history` 必须输出受控摘要，而不是默认倾倒无界内部对象。
5. CLI channel 第一版只承诺文本 I/O 与最小命令控制，不承诺富文本、ANSI 美化、实时 token 流式显示或多模态控制台。
6. 若同时存在其他 channel，routing/policy 仍由既有 owner 决定；CLI channel 不自动抢占为唯一默认外发通道。

## 8. Observability and Logging

必须记录：

1. CLI channel startup / connected / disconnected 状态。
2. stdin reader started / stopped / failed。
3. 普通 terminal input accepted count 与 command handled count。
4. command 名称、handled 结果、是否请求 shutdown。
5. outbound terminal render success / failure。
6. 若存在 expression modulation，记录 render 后文本与 expression profile 的摘要。

## 9. Validation Strategy

1. 单元测试验证 CLI channel `poll()` 非阻塞且能 drain reader queue。
2. 单元测试验证普通文本输入会生成正式 inbound `ChannelMessage`，并带有 configured `user_id` / `session_name` 语义。
3. 单元测试验证 `/help`、`/quit`、`/state`、`/history` 被 CLI owner 拦截而不是进入普通 stimulus path。
4. 单元测试验证 `send()` 走 stdout render，并消费 expression modulation 结果。
5. 集成测试验证 `helios_main.py` 能在启用 CLI channel 时完成注册与正常 polling/routing。
6. 集成测试验证 startup-configured local session identity 会影响 conversation/history boundary。
7. manual validation 验证本地终端会话中的普通文本、管理命令和 orderly shutdown。