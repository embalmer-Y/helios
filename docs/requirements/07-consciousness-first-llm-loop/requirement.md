# Requirement 07 - Consciousness-First LLM Loop

## 1. Background and Problem

当前运行时把 LLM 同时放在被动回复链路和内部思考链路上，但主路径仍然偏向外部输入后的 reply-first 生成。这导致以下结构性问题：

1. `helios_main.py` 同时维护 passive reply path 与 internal thought path，系统主循环没有围绕统一意识循环组织。
2. `cognition/thinking_integration.py` 目前是旁路式内部 thought owner，而不是主循环 owner。
3. 内部 thought 是否继续、是否不足、是否需要下一 tick 延续，尚未成为正式状态。
4. LLM 仍被旧设计哲学视为外部响应工具，而不是内在意识流参与者。

这些问题会持续把实现拉回 chatbot-first 或 reply-first 方向，直接违背新的类脑意识优先哲学。

## 2. Goal

将 LLM 重新定位为 Helios 主意识循环中的核心思考参与者，使主循环在每个 tick 中围绕刺激整合、思考门控、记忆定向检索、思考产出、连续思考压力和行动形成组织，而不再保留 reply-first 的默认主路径。

## 3. Functional Requirements

### 3.1 主循环所有权

1. 主循环必须围绕统一的 thought-centered orchestration 组织，而不是并列维护 passive reply path 与 internal thought path。
2. 系统必须在每个 tick 中显式经历以下阶段：刺激输入、状态更新、思考门控、定向记忆检索、思考执行、连续思考判断、行动形成、反馈写入。
3. LLM 的主职责必须是参与内部思考，而不是直接生成面向外部的回复文本。

### 3.2 思考触发

1. 并非每个 tick 都必须触发 LLM 思考。
2. 系统必须根据统一门控结果决定当前 tick 是否进入思考。
3. 当不进入思考时，系统仍必须完成内部状态演化与 quiet tick 的可观测记录。

### 3.3 思考结果

1. 每次思考必须至少产出以下结构化结果：
   - thought content
   - sufficiency assessment
   - continuation request
   - optional recall intent
   - optional action proposal
   - optional self-revision proposal
2. 思考结果必须可被下一个 tick 消费，而不是只写日志或只写自由文本。
3. 思考结果必须允许明确表达“当前思考不充分，需要下一 tick 继续”。

### 3.4 连续思考压力

1. 当思考结果标记为不充分时，系统必须生成 continuation pressure。
2. continuation pressure 必须成为正式运行状态，并影响后续 tick 的思考触发概率或强度。
3. continuation pressure 不得仅作为 prompt 文本或临时局部变量存在。

### 3.5 reply-first 路径移除

1. 旧的 reply-first 默认主路径不得继续作为系统的主要 LLM 调用入口。
2. 若存在面向外部文本生成的残留路径，其角色必须被降级为 thought externalization 或过渡期 fallback，而不是主 owner。
3. 不要求保留旧 reply-first 接口兼容层。

## 4. Non-Functional Requirements

1. 思考门控和思考执行必须能在 quiet tick 中保持稳定，不得因为无外部输入而退化为无意义空转。
2. 思考结果、continuation pressure 和 quiet tick 结果必须具备明确 observability，不得只依赖散乱 debug 文本。
3. 主循环重构过程中不要求保留旧接口兼容，但必须保持实现边界清晰，避免新的多路径漂移。
4. 若 LLM 不可用，系统必须存在受控 fallback，且 fallback 仍遵守统一思考结果结构。

## 5. Code Behavior Constraints

1. 不得在 `helios_main.py` 中继续扩展独立的 reply-first orchestration 分支。
2. 不得让 `cognition/thinking_integration.py` 仅作为 passive reply 的附属上下文生成器。
3. 不得把 continuation pressure 只存为 prompt 说明或未持久化的局部状态。
4. 不得为了兼容旧行为而保留无意义的 wrapper 或双路径 owner。

## 6. Impacted Modules

1. `helios_main.py`
2. `cognition/thinking_integration.py`
3. `cognition/thinking.py`
4. `cognition/phi.py`
5. `core/helios_state.py`
6. `helios_io/response_pipeline.py`
7. `helios_io/llm/speech.py`
8. `helios_io/icri_temperature.py`

## 7. Acceptance Criteria

1. 主循环中存在一个明确的 thought-centered 阶段顺序，且旧 reply-first path 不再是默认主 owner。
2. 每次思考结果都能以结构化对象被记录和消费，至少包含 sufficiency assessment 与 continuation request。
3. 当思考标记为不充分时，下一 tick 的运行状态中可观察到 continuation pressure 已建立并参与门控。
4. quiet tick 可被观察和验证，不依赖是否存在外部消息。
5. LLM 不可用时，fallback 仍返回符合结构约束的思考结果，而不是重新走旧回复路径。
