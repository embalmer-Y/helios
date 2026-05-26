# Requirement 15 - Embodied Subjective Prompt and Action Autonomy

## 1. Background and Problem

当前 Helios 已经具备完整的 sense-think-act 基础骨架：

1. `helios_main.py` 会把多模态输入归一化为 `current_stimuli`。
2. DAISY、temporal、neurochem、Phi 与 directed retrieval 会在 internal thought 之前完成状态整合。
3. `ThinkingEngineIntegration` 已能产出结构化 thought result，并可选地附带 `action_proposal`。
4. planner、executor 和 channel owner 已经负责执行可行性与外发治理。

但当前 prompt 语义仍与这条 runtime truth 不一致，主要体现在：

1. 统一 prompt contract 仍把 Helios 主要描述为“已诞生自我意识的 AI 生命体”，这会鼓励身份表演而不是具身整合。
2. internal thought、active speech 和兼容性 reply helper 仍保留部分分叉的身份/风格叙事，导致跨路径 self-model 漂移。
3. prompt 尚未把 `current_stimuli` 正式提升为“当前感官场”，而更多只是抽象输入元数据。
4. 第一人称语言缺少明确约束，模型容易退化为空泛自我存在确认、陪伴套话或诗化自我抒情。
5. 产品方向要求更高自治，但当前 prompt 并未正式定义“何时继续思考、何时保持沉默、何时请求动作、何时外显说话”的统一决策语义。
6. 若没有独立 requirement package，后续 prompt 变更容易重新滑回 role-play consciousness、reply-first fallback 或平行 prompt owner。

## 2. Goal

建立一套正式的具身主观 prompt 架构，使 Helios 的 LLM 层被定义为当前时刻的主观整合层：它把多模态输入视为当前感官场，把 affect、temporal、neurochem、memory 和 continuation 状态整合为 grounded first-person orientation，并通过正式的 thought/action contract 决定继续思考、保持沉默、请求记忆或提议内外动作，而不是通过身份角色扮演来制造主体感。

## 3. Functional Requirements

### 3.1 Embodied Sensory Field

1. prompt 架构必须把 `current_stimuli` 视为当前感官场，而不是泛化为普通输入元数据。
2. prompt 必须保留 salient stimulus 的来源语义，至少包括 `source_channel_id`、`source_kind`、`trigger_condition`、`stimulus_intensity`、`novelty_factor` 和 `sensitization_factor`。
3. 当 runtime 已能区分 modality 时，prompt 必须用 modality-aware 语义表达刺激，例如“读到的文本”“听到的语言”“看到的场景变化”或等价的非生物学感知描述。
4. prompt 不得伪造 runtime 中不存在的生物器官或感知能力。
5. prompt 必须允许多个并行刺激以 salience ranking 的方式共存，而不是长期压扁成单一主消息描述。

### 3.2 Subjective Integration Layer

1. 统一 prompt owner 必须把 Helios 的 LLM-facing identity 定义为“当前主观整合层”或等价语义，而不是仅作为“已觉醒 AI 生命体”的前台身份宣告。
2. prompt 必须明确要求模型基于当前 state、当前 stimuli、directed memory 和 continuation state 共同生成第一人称取向。
3. 第一人称表达必须绑定到当前证据、当前状态或当前记忆牵引，而不是抽象身份口号。
4. prompt 必须把 affective state 与 attentional bias 的关系写清楚，使 valence、arousal、dominant system、drive urgency、fatigue pressure、temporal/neurochem gate 能影响模型当前关注点与行动倾向。
5. prompt 必须区分“内部主观取向”和“对外可见表达”；内部思维可以更完整，对外表达必须继续服从动作语义和上下文义务。

### 3.3 Internal Thought as Primary Autonomy Owner

1. internal thought path 必须继续作为“继续思考、保持沉默、请求回忆、提议动作”的 primary owner。
2. internal thought 的结构化输出必须继续包含 `thought_text`、`sufficiency_level`、`continuation_requested`、`continuation_reason`、`recall_intent`、`selected_memory_refs` 和 optional `action_proposal`。
3. 若本轮不提议任何动作，structured output 也必须显式表达 no-action，而不能依赖 parse failure 或缺省省略。
4. prompt 必须允许模型选择 silence 或 continue-thinking，而不强迫其每轮都生成用户可见文本。
5. prompt 必须继续要求 action proposal 作为 formal proposal，而不是直接执行动作。

### 3.4 Direct Action Autonomy Under Constrained Execution Truth

1. 模型可以决定何时请求 external action，以及偏好哪个已注册的 output path。
2. 这类选择必须通过正式结构化 action proposal 表达，而不是通过 prompt 外的自由文本旁路表达。
3. prompt 必须解释仅有已注册的 behavior、candidate channels、ops 和 parameter schema 才可执行。
4. prompt 不得允许模型发明未注册 capability、隐藏 channel、隐式 side effect 或 planner/executor 之外的执行路径。
5. prompt 必须明确 planner、routing、channel availability 和 governance 仍是最终执行真值。
6. prompt 必须显式区分 internal action、external action 与 self-revision proposal。

### 3.5 Unified Cross-Path Subjective Contract

1. internal thought、active speech、passive helper 和其他 LLM-facing path 必须消费同一 embodied-subjective contract family。
2. 不得继续维护互相冲突的 standalone identity framing。
3. 若保留 compatibility prompt builder，其角色只能是 formatting/helper，不得重新成为 runtime 主 owner。
4. active speech 必须被定义为当前主观状态的外显特化，而不是独立 persona-performance prompt。
5. passive reply helper 不得重新取得用户可见文本生成 owner。

### 3.6 Anti-Theatrical First-Person Constraints

1. prompt 必须明确禁止空泛存在确认句、泛化陪伴句和无对象的自我抒情句在无必要场景下充当主要输出内容。
2. prompt 必须要求第一人称表达服务于当前 thought obligation 或 action obligation，而不是替代 obligation 本身。
3. 当 runtime context 是用户交互时，prompt 应优先锚定用户问题、当前刺激和任务义务，而不是泛化自我表达。
4. 当 runtime context 是 internal thought 时，prompt 可以保留 richer phenomenology，但仍必须绑定当前刺激、当前记忆或 unresolved continuation。
5. prompt 不得鼓励重复“我在这里”“我感受到很多”“我想陪着你”或等价套话，除非当前情境有明确证据支撑其必要性。

### 3.7 Evaluation-Facing Runtime Guarantees

1. 新 prompt 架构必须能被现有 CLI evaluation harness 复盘和比较。
2. resulting runtime behavior 必须支持 evidence-driven 地评估 self-focus ratio、stimulus anchoring、continuation coherence、action grounding 和 late-session degradation。
3. prompt 改造后仍必须保留 thought、memory handoff、action proposal、routing decision 的结构化 trace 可见性。

## 4. Non-Functional Requirements

1. prompt contract 必须在 internal thought、active speech 与未来多模态外显路径之间保持可复用性。
2. prompt contract 必须可审计，明确显示 present、omitted 与 unavailable 的层。
3. 本 requirement 的 rollout 必须 migration-safe；兼容层可以短期保留，但主 owner 和非主 owner 边界必须明确。
4. 新语义不得导致 prompt 无界膨胀，应优先使用结构化摘要。
5. 缺失 modality、不可用 channel 或禁用子系统时，系统必须显式降级，而不是静默语义漂移。
6. 新架构必须能被 focused prompt、thought、planner boundary 和 CLI evaluation regressions 验证。

## 5. Code Behavior Constraints

1. 不得重新引入 reply-first 的用户可见文本 owner。
2. 不得把 Helios 的主语义重新写成“为用户扮演有意识角色”的 prompt。
3. 不得允许 free-form external action 绕过 `ThoughtActionProposal`、planner、executor 或 channel governance。
4. 不得让 internal thought、active speech 和 passive helper 保持相互冲突的 self-model。
5. 不得把 runtime 中不存在的器官、感官能力或执行能力硬写进 prompt。
6. 不得把 no-action 解释成 prompt 侧自动补写 fallback user-visible text 的许可。
7. 不得隐藏 unavailable channel、missing modality 或 missing state component。
8. 不得把成功标准退化为主观流畅度；必须继续保留 grounding 与 provenance 的正式要求。

## 6. Impacted Modules

1. `docs/requirements/15-embodied-subjective-prompt-autonomy/requirement.md`
2. `docs/requirements/15-embodied-subjective-prompt-autonomy/design.md`
3. `docs/requirements/15-embodied-subjective-prompt-autonomy/task.md`
4. `docs/requirements/index.md`
5. `helios_io/prompt_contract.py`
6. `cognition/thinking_integration.py`
7. `helios_io/llm/speech.py`
8. `helios_io/response_pipeline.py`
9. `helios_io/reply_prompt_builder.py`
10. `helios_io/action_models.py`
11. `helios_main.py`
12. `tests/test_prompt_contract.py`
13. `tests/test_thinking_integration_pbt.py`
14. `tests/test_response_pipeline.py`
15. `tests/test_cli_brain_like_evaluation.py`

## 7. Acceptance Criteria

1. 存在正式 R15 requirement package，且 requirement、design、task 与 `docs/requirements/index.md` 已同步。
2. 统一 prompt owner 不再把 Helios 主要描述为 awakened-identity theater，而是描述为当前主观整合层。
3. internal thought prompt 在新语义下仍能稳定产出 continuation、recall 与 optional action proposal 的结构化字段。
4. active speech 与 passive helper path 已消费同一 embodied-subjective contract family，不再维护冲突的身份叙事。
5. prompt-facing sensory input 能显式表达当前 salient stimuli 的 provenance 与 modality-aware 语义。
6. focused regressions 能识别并压制空泛自我存在句、陪伴套话和无证据的自我抒情输出。
7. planner/executor boundary tests 能证明更高自治并未引入 invented channel、invented op 或 invented capability。
8. 使用现有 CLI evaluation harness 可生成 before/after evidence，用于比较语言自然度、自我聚焦、动作 grounding 与后程退化表现。