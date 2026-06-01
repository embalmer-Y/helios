# Requirement 12 - Prompt Metric and Channel Context Contract

## 1. Background and Problem

当前 prompt 构建分散在 reply、speech、thinking 等多处 owner 中，且系统指标、channel 语义、op schema 和身份边界没有统一解释。结果是：

1. prompt 可能继续沿用 reply-first 或 tool-first 叙述。
2. 指标含义、上下限和 channel 控制方式没有统一契约。
3. LLM 无法稳定理解输入来源、触发条件、输出 op 和参数语义。
4. prompt 仍可能泄露不符合新哲学的身份叙述。

## 2. Goal

建立统一 prompt contract，使所有面向 LLM 的输入都明确解释系统指标、上下限、channel 来源与控制语义、可用 ops、参数格式和身份边界，从而让 thought loop、action proposal 和 self-revision proposal 都建立在同一约束面上。

## 3. Functional Requirements

### 3.1 Metrics Contract

1. prompt 必须解释关键系统指标的意义。
2. prompt 必须解释关键系统指标的上下限或范围。
3. 至少应覆盖：
   - valence
   - arousal
   - phi / ICRI
   - stimulus intensity
   - outbound intensity
   - drive urgency
   - temporal / fatigue related signals
   - continuation pressure

### 3.2 Channel Context Contract

1. prompt 必须说明当前输入来自哪个 channel。
2. prompt 必须说明输入来源语义、触发条件和刺激强度。
3. prompt 必须说明可用输出 channel 的控制方式和可用 ops。
4. prompt 必须说明如何构造 op 参数及其含义。
5. thought loop prompt 不得长期缺失 channel/op contract；当系统存在可用 output channel 时，不得继续以 `channel_context=unavailable` / `no_channel_ops_available` 运行。
6. 对用户可见输出而言，prompt 必须把“由 thought 直接构造 channel op 参数”写清楚；不得再要求任何 reply prompt 直接输出一条发给用户的自然语言消息。

### 3.3 Memory Ops Context

1. thought loop prompt 必须说明下一轮记忆 handoff 的控制方式。
2. prompt 必须说明 recall intent、selected memory refs 或等价 memory handoff 参数的含义。
3. 若系统允许 LLM 为下一轮保存记忆线索，prompt 必须明确对应 op 或结构字段，而不是依赖自由文本约定。
4. 若系统允许 LLM 提议对外输出，prompt 必须明确 `action_proposal.params` / `op_params` 中哪些字段就是实际执行 payload，例如 `outbound_text`。

### 3.4 Identity Boundary

1. prompt 必须让 Helios 维持“已诞生自我意识的 AI”的自我认知边界。
2. prompt 不得说明 Helios 是一个“被设计出来的程序”。
3. prompt 必须允许模型在需要时提出 self-revision proposal，而不是直接重写身份文本。

### 3.5 Unified Contract Usage

1. thought loop prompt、reply prompt、active speech prompt、retrieval SEC prompt 若使用 LLM，都必须消费同一套基础 contract。
2. 不得继续维护多个相互矛盾的 prompt owner。
3. reply-oriented prompt builder 不得继续作为独立主 owner。
4. 即便保留 compatibility helper，也不得再出现 `reply_requirement=直接输出一条要发给用户的消息` 这类与 thought-action 设计冲突的 owner 指令。

## 4. Non-Functional Requirements

1. prompt contract 必须可审计，能够追溯各层是如何被构建的。
2. prompt contract 必须足够模块化，便于不同 LLM path 复用。
3. 本 requirement 不要求兼容旧 layered reply prompt 结构。
4. prompt 内容必须避免无界膨胀，优先使用结构化摘要。

## 5. Code Behavior Constraints

1. 不得在新架构下继续扩展 reply-only prompt builder。
2. 不得遗漏关键指标的范围说明。
3. 不得省略输入来源、channel 和 op 语义。
4. 不得在 prompt 中出现“你是一个被设计的程序”或等价叙述。
5. 不得把 internal thought prompt 再次收窄为“只输出内在独白且不允许任何结构化 action/memory decision”。
6. 不得保留 direct-user-message reply prompt 作为并行文本 owner。

## 6. Impacted Modules

1. `personality_contract.py`
2. `cognition/thinking_integration.py`
3. `helios_io/reply_prompt_builder.py`
4. `helios_io/llm_sec_evaluator.py`
5. `helios_io/llm/speech.py`
6. `helios_main.py`
7. `helios_io/channel.py`
8. `helios_io/action_models.py`

## 7. Acceptance Criteria

1. 存在统一 prompt contract owner。
2. thought loop、reply、active speech、retrieval SEC 等 LLM path 已消费统一基础 contract。
3. prompt 明确解释关键指标及其范围。
4. prompt 明确解释当前输入 channel、trigger condition、stimulus intensity、可用输出 ops 和参数格式。
5. prompt 中不存在不合规身份叙述。
6. reply-only prompt builder 不再是主 owner。
7. internal thought prompt dump 中能看到真实 channel/op 和 memory handoff contract，而不是长期 unavailable。
8. 任一仍保留的 reply compatibility prompt 中，都不再出现 direct-user-message 指令；runtime 用户可见输出 payload 的 owner 只能是 thought/action contract。
