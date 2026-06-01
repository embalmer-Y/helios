# Requirement 13 - Terminal CLI Channel

## 0. Execution Status

- Status: validated
- Review result: CLI channel owner、runtime wiring、manual validation 与体验层增强已完成，当前 package 进入 validated closeout 维护状态。
- Scope lock:
	- integrated Helios runtime channel
	- asynchronous stdin -> later tick processing
	- startup-configurable `user_id` / `session_name`
	- `/help`、`/quit`、`/state`、`/history` 纳入 v1 command boundary
	- normal terminal output 仅显示正式 outbound/rendered text

## 1. Task Breakdown

### T13-1 定义 CLI channel owner 与 descriptor
1. 已完成：新增 `cli_channel.py` 正式 owner。
2. 已完成：定义 config、descriptor 与最小 management op summary。
3. 已完成：明确 terminal channel 的 input/output/bidirectional capability。
4. 已完成：focused unit tests 已覆盖 descriptor/owner shape。

### T13-2 实现非阻塞 stdin reader 与 inbound queue
1. 已完成：后台 reader thread 已实现。
2. 已完成：thread-safe inbound queue 已实现。
3. 已完成：`poll()` 非阻塞 drain queue 并输出正式 `ChannelMessage`。
4. 已完成：空队列、断连发送与 reader 状态切换已覆盖。

### T13-3 实现 outbound render 与表达调制对接
1. 已完成：`send()` 通过稳定 line render path 实现 stdout render。
2. 已完成：复用 `expression_modulation.py` 的 text modulation 语义。
3. 已完成：记录 rendered text / expression profile 摘要。
4. 已完成：stdout 写失败、multiline render 与断连发送已覆盖。

### T13-4 定义 CLI command boundary
1. 已完成：`/help`、`/quit`、`/state`、`/history` 解析。
2. 已完成：management command 与普通用户文本已分离。
3. 已完成：本地管理输出、session banner 与 orderly shutdown 边界已明确。
4. 已完成：未知命令、空命令名和帮助输出已覆盖。

### T13-5 接入 Helios bootstrap 与 runtime wiring
1. 已完成：`helios_main.py` 中新增 CLI channel config、显式启动参数与注册逻辑。
2. 已完成：CLI channel 与既有 channel 共存，而非替代所有 channel。
3. 已完成：startup `user_id` / `session_name` 已进入 history / routing / conversation boundary。
4. 已完成：enable/disable 配置、channel-aware logging 与 QQ side effect boundary 已覆盖。

### T13-6 补齐 focused integration tests
1. 已完成：CLI ordinary text -> inbound stimulus -> later tick 语义已验证。
2. 已完成：CLI command 不进入普通 thought stimulus path。
3. 已完成：outbound render 仍遵守 planner/executor/channel send 路径。
4. 已完成：shutdown command 的 orderly behavior 已验证。

### T13-7 执行 manual local terminal validation
1. 已完成：启动 Helios CLI channel。
2. 已完成：发送普通文本并确认后续 tick 响应。
3. 已完成：执行 `/help`、`/state`、`/history`、`/quit`。
4. 已完成：已记录手工验证结果并形成 closeout 证据。

## 2. Dependencies

1. 依赖 R08 的正式 stimulus ingress 语义。
2. 依赖 R09 的正式 outbound action execution 路径。
3. 依赖 R12 的 channel/op prompt contract 与 descriptor 语义。
4. 与 `helios_io/channel.py`、`channel_gateway.py`、`helios_main.py` 强相关。

## 3. Files and Modules

1. `helios_io/channels/cli_channel.py`
2. `helios_io/channel.py`
3. `helios_io/channel_gateway.py`
4. `helios_main.py`
5. `helios_io/expression_modulation.py`
6. `helios_io/prompt_contract.py`
7. `helios_io/response_pipeline.py`
8. `tests/test_channel_gateway.py`
9. `tests/test_tick_response_wiring.py`
10. `tests/`

## 4. Implementation Order

1. T13-1
2. T13-2
3. T13-3
4. T13-4
5. T13-5
6. T13-6
7. T13-7

## 5. Validation Plan

1. 已验证：CLI channel descriptor 与 owner shape。
2. 已验证：非阻塞 stdin queue 与 `poll()` 语义。
3. 已验证：outbound render、multiline render 与表达调制接入。
4. 已验证：command boundary、session banner、help text 与 orderly shutdown。
5. 已验证：`helios_main.py` wiring、local session identity、CLI 启动参数与 channel-aware side effects。
6. 已验证：manual local terminal session。

## 6. Completion Criteria

1. 存在正式 CLI channel owner，且不在主循环中内嵌同步 REPL。
2. 普通文本输入进入正式 inbound channel/tick 路径。
3. 普通终端输出进入正式 outbound channel 路径，并支持 render 后文本。
4. `/help`、`/quit`、`/state`、`/history` 已具备清晰 management boundary。
5. startup `user_id` / `session_name` 已影响本地会话边界。
6. focused automated tests 已覆盖 poll、send、command 和 wiring。
7. 至少完成一轮 manual terminal interaction closeout 验证。

## 7. Closeout Review

1. 已完成：CLI channel owner、descriptor、queue-based reader、outbound render、command boundary 和 bootstrap wiring。
2. 已完成：共享 text inbound annotation owner 已收敛，CLI/QQ/STT 不再通过 QQ 静态 helper 横向耦合。
3. 已完成：CLI 体验层补齐了显式启动参数、session banner、help summary 和更稳定的 terminal line rendering。
4. 自动化验证：此前 focused/broader regressions 已分别通过 `43 passed`、`62 passed`、`135 passed`；本轮补充 CLI 启动参数与体验层 focused tests，并完成全量 `pytest -q` 验证，结果为 `710 passed in 335.31s`。
5. 手工验证：真实 CLI 运行已确认普通文本回复、`/help`、`/state`、`/history`、`/quit` 正常，日志归属为 `CLI`，且不会误触发 QQ target auto-capture。
6. Closeout gate：本轮代码后的全量 `pytest -q` 已完成，R13 package closeout 证据完整。