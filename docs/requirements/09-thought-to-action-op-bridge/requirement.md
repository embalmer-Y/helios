# Requirement 09 - Thought-to-Action Op Bridge

## 1. Background and Problem

当前 thought 与 action 之间的桥接仍受旧设计限制：

1. `cognition/preconscious.py` 产生的 proposal 被限制为 `internal_only`。
2. thought 结果不能正式提议对外 op 和参数。
3. planner 目前主要消费 policy 产生的 proposal，而不是 thought owner 的结构化行动结果。
4. 输出强度还没有成为 action proposal/decision 的正式字段。

这使得“思考后决定采取行动”这一类脑路径无法成立。

## 2. Goal

建立一个受控的 thought-to-action op bridge，使思考结果可以提议结构化 op、参数和输出强度，但仍由 planner、policy、executor 和 channel capability 共同决定是否允许外化以及如何执行。

## 3. Functional Requirements

### 3.1 Thought Action Proposal

1. thought result 必须允许包含结构化 action proposal。
2. action proposal 至少包含：
   - behavior or intent
   - preferred op
   - params
   - target constraints
   - outbound intensity in `[0, 1]`
   - reason trace
3. LLM 可以提议 op + params，但不得直接执行。

### 3.2 Planner Governance

1. planner 必须对 thought-origin proposal 执行 schema、capability、channel availability 和 governance 校验。
2. planner 必须能够拒绝无效或越权 proposal，并记录 rejection reason。
3. planner 必须支持对 outbound intensity 的限制、裁剪或归一化。

### 3.3 Executor and Channel Ops

1. executor 必须能消费包含 op、params 和 outbound intensity 的决议。
2. channel 层必须支持基于 op schema 的执行，而不仅是简单 send text。
3. 行动执行结果必须回写为统一反馈事件。

### 3.4 Internal vs External Actions

1. thought result 可以提议内部行动，也可以提议对外行动。
2. 不再把 thought-origin proposal 永久限制为 `internal_only`。
3. 若某个 proposal 被治理规则判定只能内部执行，系统必须明确记录约束原因。

## 4. Non-Functional Requirements

1. action proposal 和 decision 必须可追溯到 originating thought。
2. planner rejection 必须可解释，便于调试和审计。
3. 旧 `internal_only` 兼容层不是必须目标，允许直接替换。
4. channel op 扩展必须保持 schema 明确，不得退回隐式字符串参数。

## 5. Code Behavior Constraints

1. 不得保留 `internal_only` 作为 thought-origin proposal 的永久硬约束。
2. 不得让 LLM 绕过 planner / executor 直接操作 channel。
3. 不得让 outbound intensity 只存在于 prompt 或日志中。
4. 不得继续扩展 reply-only send-text 路径作为唯一外化手段。

## 6. Impacted Modules

1. `cognition/preconscious.py`
2. `cognition/thinking_integration.py`
3. `helios_io/action_models.py`
4. `helios_io/planning.py`
5. `helios_io/limb.py`
6. `helios_io/channel.py`
7. `helios_io/channel_gateway.py`
8. `helios_main.py`
9. `behavior_registry/`

## 7. Acceptance Criteria

1. thought result 可正式产出包含 op、params 和 outbound intensity 的 action proposal。
2. planner 可对 thought-origin proposal 做接受/拒绝，并返回结构化 reason。
3. executor 可执行结构化 op 决议，而不限于简单文本发送。
4. thought-origin proposal 不再默认 `internal_only`。
5. 所有外化行动均可追溯到 originating thought 与 planner decision。
