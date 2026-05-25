# Requirement 13 - Terminal CLI Channel

## 1. Background and Problem

当前 Helios 已有正式 channel abstraction、ChannelGateway、planner/executor 与 stimulus contract，但本地交互仍缺少一个正式的终端输入输出通道。结果是：

1. 本地调试、演示或单机交互只能依赖临时脚本、日志观察或外部 transport。
2. 终端场景下没有正式 inbound stimulus owner，容易退化为直接 `input()` 驱动一轮处理的同步 REPL。
3. 终端场景下没有正式 outbound channel sink，容易退化为绕过 planner/executor/channel route 的 `print()` 输出。
4. 本地 session 的 `user_id` / `session_name` 边界和 CLI 管理命令边界没有正式定义。
5. 若以后引入本地 CLI 控制面，普通用户文本与本地管理命令容易混入同一语义路径，破坏 stimulus / action owner 边界。

## 2. Goal

建立一个正式的终端 CLI channel，使 Helios 能在本地终端中以非阻塞、tick-driven 的方式接收用户文本输入并输出正式用户可见回复，同时为最小 CLI 管理命令提供清晰边界，且不绕过现有 channel、stimulus、planner、executor 和 prompt contract 体系。

## 3. Functional Requirements

### 3.1 Terminal Channel Runtime Path

1. 终端交互必须作为正式 channel 接入 Helios runtime，而不是独立旁路脚本 owner。
2. 终端普通文本输入必须进入正常 inbound channel path，并在后续 tick 中被处理。
3. 终端普通文本输入不得通过同步阻塞式 REPL 直接驱动一次完整 thought/reply 处理。
4. 终端用户可见输出必须通过正式 outbound channel route 外发，而不是由主循环直接打印用户消息正文。
5. 终端 channel 必须支持双向 text I/O。

### 3.2 Inbound Terminal Input Semantics

1. 终端普通文本输入必须被标准化为正式 `ChannelMessage` 与等价 stimulus contract 输入。
2. 终端输入必须带有明确的 channel identity、source kind、trigger condition 和 stimulus provenance。
3. 终端 channel 必须支持启动时配置 `user_id` 与 `session_name`，并把它们稳定用于本地会话边界。
4. 终端在一次运行期内应保持 conversation continuity，不得为每条输入隐式生成新的本地用户身份。
5. 当 stdin 关闭、不可读或 reader 线程失败时，系统必须显式暴露 channel 状态，而不是静默丢失输入能力。

### 3.3 Outbound Terminal Output Semantics

1. 终端 channel 必须接收正式 outbound `ChannelMessage` 并将其渲染到 stdout 或等价终端输出 sink。
2. 终端普通输出必须展示正式用户可见 `outbound_text` 或 render 后文本，而不是 internal thought 文本。
3. 若 outbound metadata 中存在 `normalized_intensity` 或 `outbound_intensity`，终端输出应消费与现有 text channel 一致的表达调制语义。
4. 终端输出必须保留 channel receipt / execution trace 所需的最小 metadata 语义。
5. 当 stdout 不可写、渲染失败或终端已关闭时，系统必须产生显式失败结果或可审计 trace。

### 3.4 CLI Command Boundary

1. `/help`、`/quit`、`/state`、`/history` 必须作为正式 CLI 管理命令边界定义，而不是临时约定。
2. CLI 管理命令不得伪装成普通用户文本 stimulus 进入 thought loop，除非未来 requirement 明确允许。
3. `/quit` 必须触发有序 shutdown 或等价终止流程，而不是粗暴中断导致状态丢失。
4. `/state` 与 `/history` 必须返回明确受控的 CLI 管理输出，不得默认泄露内部 thought 正文或无界 runtime internals。
5. `/help` 必须能暴露支持的 CLI 命令与普通文本交互规则。
6. CLI 命令输出属于本地管理输出，不应被记录为对用户发送的普通 channel reply owner。

### 3.5 Compatibility with Existing Ownership Model

1. 终端 channel 必须复用现有 `ChannelGateway`、stimulus weighting、planner/executor 和 thought-to-action owner path。
2. terminal input prompt/context 语义必须消费既有 channel/op contract，而不是引入 CLI 特有的并行 prompt owner。
3. terminal output 若由 thought-origin action 提议，仍必须遵守 R09 的正式 action proposal -> planner/executor -> channel send 路径。
4. terminal channel 的引入不得重新打开 reply-first、direct-user-message 或 direct `print()` owner 路径。

## 4. Non-Functional Requirements

1. 终端输入采集必须非阻塞，不能冻结 tick loop。
2. 终端 channel 必须具备可靠的 startup / shutdown 行为，包括 stdin reader 停止、queue 清理和状态切换。
3. 终端 channel 必须具备可审计 observability，至少覆盖 connect/disconnect、input accepted、command handled、output rendered、output failed 等关键事件。
4. 第一版必须兼容现有无 QQ / 无 TTS 的本地运行场景，不得要求外部 transport 凭证。
5. 第一版 requirement 不要求完整 shell UI、美化排版、富文本或多模态终端展示，但 design 应保留可扩展边界。

## 5. Code Behavior Constraints

1. 不得把 `input()` / `print()` 循环直接放进 `helios_main.py` 作为正式 runtime owner path。
2. 不得绕过 `ChannelMessage`、channel descriptor、`ChannelGateway` 或 planner/executor 直接处理普通用户文本与正式用户可见输出。
3. 不得让 CLI 管理命令与普通用户刺激共用无区分自由文本路径。
4. 不得默认把 internal thought、prompt dump 或完整 `get_state()` 原样流式输出给终端普通用户界面。
5. 不得为 terminal channel 引入与现有 channel/op contract 矛盾的独立 prompt 语义。
6. 不得让 startup `user_id` / `session_name` 成为仅日志可见、但不影响 runtime conversation boundary 的空配置。

## 6. Impacted Modules

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

## 7. Acceptance Criteria

1. 存在正式 terminal CLI channel owner，且其实现位置在 `helios_io/channels/` 下，而不是主循环内嵌 REPL。
2. 普通终端文本输入经由正式 channel poll path 进入后续 tick，而不是同步直接调用完整处理链。
3. 普通终端输出经由正式 outbound channel send path 外发，并可消费表达调制后的 render 文本。
4. `/help`、`/quit`、`/state`、`/history` 具有明确命令边界，且不会默认被当作普通用户刺激送入 thought loop。
5. startup `user_id` / `session_name` 可影响本地会话边界与 history / routing 归属。
6. focused tests 能验证 terminal channel 的非阻塞 poll、outbound render、command handling 和 shutdown 语义。
7. 至少存在一条 manual validation 路径，能在本地终端中验证普通文本输入、普通输出和最小 CLI 命令集。
8. 代码库中不存在把 terminal 交互重新实现为 reply-first 或 direct `print()` / `input()` 主 owner 路径的正式实现。