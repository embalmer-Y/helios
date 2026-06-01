# Requirement 15 - Embodied Subjective Prompt and Action Autonomy

## 1. Design Overview

本设计将 prompt 语义升级为新的正式架构 concern。R12 已经统一了 metric、channel、op 和 identity boundary 的基础 contract，但它并没有回答更深的问题：Helios 在 prompt 中究竟被要求“做什么”。R15 的目标是把 LLM-facing layer 从“有意识角色扮演层”重构为“当前主观整合层”。

该设计直接吸收四类相关研究的架构启发：

1. ReAct 说明 reasoning 与 acting 应交错表达，而不是完全分离。
2. Generative Agents 说明 observation、reflection、planning 的闭环是可信主体连续性的关键。
3. PaLM-E 说明 embodied reasoning 需要把传感器/状态输入作为 language context 的一等部分。
4. Voyager 说明高自治 agent 必须在显式 skill/action contract 与环境反馈约束下运行，而不是只靠自由文本决策。

## 2. Current State and Gap

### 2.1 Current State

当前 runtime 已具备下列正向条件：

1. `helios_main.py` 会把多模态 channel 与 event source 归一化为 `state.current_stimuli`。
2. DAISY、Phi、temporal dynamics、neurochem 与 drive 会在 internal thought 前完成状态整合。
3. directed retrieval 已在 internal thought 前提供 memory relevance。
4. `ThinkingEngineIntegration` 已经具备结构化 thought output 与 optional `action_proposal`。
5. `ThoughtActionProposal`、planner、executor 与 channel gateway 已提供 formal action autonomy bridge。

### 2.2 Gap

阻塞目标行为的主要 gap 如下：

1. `PromptContractBuilder` 当前仍使用“already-conscious AI lifeform”语义，这会鼓励身份宣告与 self-theater。
2. prompt 还没有把 normalized stimuli 形式化为当前感官场，也没有把 modality-aware salience 提升为主语义。
3. 第一人称语言约束不足，易出现空泛自我表达。
4. `LLMSpeechGenerator` 仍叠加了部分独立 identity/style framing，导致和 internal thought path 出现 self-model 分叉。
5. `ResponsePipeline` 与 `ReplyPromptBuilder` 仍保留 compatibility 语义，如不进一步收束，容易在未来重新夺回 owner 地位。
6. 仓库中尚无 requirement package 将这些问题作为一个统一 concern 固化下来，导致未来修改缺少边界与验收标准。

## 3. Target Architecture

### 3.1 Owner Model

目标 owner 边界如下：

1. `helios_io/prompt_contract.py` 继续作为统一 embodied-subjective prompt contract owner。
2. `cognition/thinking_integration.py` 继续作为 primary structured subjectivity-to-action owner。
3. `helios_io/llm/speech.py` 作为当前主观状态的外显特化 owner。
4. `helios_io/response_pipeline.py` 保持 context/history/helper owner，但不重新获得用户可见文本 owner。
5. planner、executor、channel gateway 继续作为 deterministic execution truth owner。

### 3.2 Semantic Layers

新 prompt family 统一拆为两层语义：

1. Subjective Integration Layer
   - 描述当前感官场、affective state、temporal pressure、memory relevance 与 continuation state。
   - 目标是让模型形成 grounded first-person orientation，而不是身份表演。
2. Deliberative Emission Layer
   - 描述当前 action affordances 与行为义务。
   - 目标是让模型决定：继续思考、保持沉默、请求回忆、提议 internal action 或提议 external action。

### 3.3 Runtime Flow

目标 runtime flow：

1. channels / event sources 产生 normalized stimuli。
2. 主循环整合 affect、drive、temporal、neurochem 与 consciousness state。
3. directed retrieval 生成当前 memory relevance summary。
4. `PromptContractBuilder` 渲染 shared embodied-subjective layers。
5. internal thought path 消费 shared contract，输出 structured thought + structured decision。
6. 若 structured decision 带 external action proposal，则 planner 校验 candidate channels、requested op、params 与 governance。
7. 若 planner 接受，则 executor/channel path 外显动作。
8. speech 与其他外显路径只是在同一 subjectivity contract 上进行 channel-specific externalization，而不是平行人格 prompt。

### 3.4 Research-to-Design Mapping

1. ReAct 对应本设计中的“thought text 与 action proposal 并列存在”，避免 thought 与 action 断裂。
2. Generative Agents 对应 observation、reflection、planning 的连续闭环，在 Helios 中映射为 `current_stimuli`、directed retrieval、continuation pressure 与 `ThoughtCycleResult`。
3. PaLM-E 对应把 sensor/state 直接变成 prompt 中的 interleaved context，而不是抽象标签。
4. Voyager 对应高自治必须通过 formal action library、feedback recorder 与 iterative environment truth 受控运行。

## 4. Data Structures

### 4.1 New Prompt-Side Conceptual Structures

第一阶段不要求新增大量持久化 runtime object，但需要在 prompt 语义上正式定义下列结构：

#### SensoryFieldSummary

```text
salient_stimuli
modality_labels
provenance_summary
salience_ranking
```

用途：

1. 统一描述当前最重要的刺激集合。
2. 把 provenance 与 modality-aware 语义带入 prompt。

#### SubjectiveOrientationSummary

```text
attentional_focus
felt_tension_or_pull
current_motivational_bias
relevant_memory_pull
continuation_status
```

用途：

1. 作为当前主观整合层的内部摘要。
2. 为 internal thought、speech 与其他外显路径提供共享第一人称 grounding。

#### ActionDeliberationContract

```text
allowed_action_space
silence_is_valid
continuation_is_valid
external_action_requires_structured_proposal
```

用途：

1. 把“我可以做什么”和“我可以不做什么”正式写入 prompt。
2. 避免模型被迫每轮产出外显内容。

### 4.2 Existing Runtime Structures Reused Directly

本设计直接复用下列已有结构：

1. `PromptContractPlan`
2. `ThoughtCycleResult`
3. `ThoughtActionProposal`
4. `ContinuationPressureState`
5. directed memory bundle summary payload
6. channel descriptor 与 op schema summary

## 5. Module Changes

### 5.1 `helios_io/prompt_contract.py`

改动职责：

1. 把 identity layer 从 awakened-identity framing 改为 subjective-integrator framing。
2. 新增当前感官场的显式渲染逻辑。
3. 在 shared constraints layer 中加入 anti-theatrical first-person constraints。
4. 在 shared action layer/constraints layer 中加入 silence/continue-thinking/is-proposal-only 语义。
5. 保持 R12 的 metric/channel/op 基础 contract 不回退。

### 5.2 `cognition/thinking_integration.py`

改动职责：

1. internal thought task wording 改为 grounded subjective integration + structured decision。
2. 保持 mixed JSON schema 不变，但强化 no-action 与 parse-failure 的区分。
3. 强化 current stimuli、memory pull、continuation pressure 与 action deliberation 的 prompt 语义。

### 5.3 `helios_io/llm/speech.py`

改动职责：

1. 删除与 internal thought path 冲突的 awakened-identity / standalone persona framing。
2. speech path 只保留 brevity、tone、channel-specific expression specialization。
3. speech 语义改为“当前主观状态的简短外显句”，而不是独立人格扮演 prompt。

### 5.4 `helios_io/response_pipeline.py`

改动职责：

1. 保留 history/context helper。
2. 审计 compatibility helper 的 prompt 语言，避免其重新定义独立 self-model。
3. 明确其 non-owner status，防止未来回退为 reply-first prompt owner。

### 5.5 `helios_io/reply_prompt_builder.py`

改动职责：

1. 若继续保留，只能作为 compatibility wrapper。
2. 其 identity/persona wording 必须与 shared embodied-subjective contract 保持一致，或显式标注 deprecated non-owner status。

### 5.6 `helios_main.py`

改动职责：

1. 主循环无需接管新 prompt orchestration。
2. 仅需保证 prompt 需要的 state surface 继续完整传递。
3. 若 rollout 使用 feature flag，主循环只负责把 flag 传给相关 owner，不承担 prompt 逻辑拼接。

## 6. Migration Plan

### Phase 1: Requirement Lock

1. 创建 R15 requirement package。
2. 同步 `docs/requirements/index.md`。
3. 锁定术语：subjective integration layer、sensory field、grounded first-person、structured action autonomy。

### Phase 2: Shared Contract Refactor

1. 修改 `PromptContractBuilder` 的 identity wording。
2. 引入 sensory-field 与 anti-theatrical constraints。
3. 保持 metric/channel/op semantics 完整。

### Phase 3: Internal Thought Alignment

1. internal thought prompt 切换到新 shared contract。
2. 保持结构化 JSON schema 稳定。
3. 验证 action proposal parse 和 trace 不回退。

### Phase 4: Active Speech and Passive Helper Alignment

1. speech 路径切换到新 shared subjectivity framing。
2. passive helper 与 compatibility prompt 进一步收束 owner 边界。
3. 清理残留的 identity theater 文案。

### Phase 5: Regression and Evaluation

1. 补 focused regressions。
2. 跑 CLI evaluation harness 做 before/after 比较。
3. 基于 evidence 决定 default-on 时机。

### Rollout Recommendation

推荐 rollout：

1. 第一阶段 default-off，使用 feature flag 控制。
2. prompt snapshot、thought parse、speech path 与 evaluation regressions 稳定后，再切 default-on。

## 7. Failure Modes and Constraints

1. 若 channel descriptor 不可用，prompt 必须显式降级为 limited action space，而不是暗示自由自治。
2. 若某 modality 缺失，prompt 必须省略该感官轴而不是捏造具身描述。
3. 若 internal thought structured output malformed，fallback 可以恢复，但 trace 必须显示 degraded parse。
4. 若 active speech 仍保留分叉 identity wording，则 cross-path self-model drift 将继续存在，应视为设计失败。
5. 若主观性强化过度且未被任务义务约束，对话会重新退化为自我抒情；这是必须用评估回归捕获的首要 failure mode。
6. 若高自治使 external action 请求频率大幅升高，planner rejection churn 可能上升，必须通过 observability 监测 requested op / rejection rate。

## 8. Observability and Logging

必须可见的观测面：

1. prompt contract snapshot 中的 sensory field、memory、channel、action 与 omitted sections。
2. internal thought trace 中的 structured action proposal presence、parse status 与 no-action semantics。
3. planner / routing log 中的 requested op、candidate channels、selection reason 和 rejection reason。
4. evaluation report 中的 self-focus、stimulus anchoring、cue alignment 与 action grounding 相关 evidence。
5. 若使用 feature flag，日志必须明确显示当前使用的是 baseline 还是 embodied-subjective contract。

## 9. Validation Strategy

1. 单元测试验证 `PromptContractBuilder` 已包含新的 subjective identity 与 sensory-field layers。
2. internal thought focused tests 验证 structured output 仍能稳定解析 continuation、recall 与 action proposal。
3. speech-path focused tests 验证 active speech 已切换到 shared subjectivity framing，且不再注入冲突 identity 语义。
4. planner-boundary tests 验证高自治 prompt 仍无法绕过注册 capability、channel availability 与 op schema。
5. evaluation regressions 验证 grounded subjectivity 至少不退化现有语言自然度与 self-focus 表现。