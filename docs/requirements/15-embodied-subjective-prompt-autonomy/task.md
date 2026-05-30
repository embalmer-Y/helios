# Requirement 15 - Embodied Subjective Prompt and Action Autonomy

## 1. Task Breakdown

### T15-1 Author Requirement Package

1. 创建 `15-embodied-subjective-prompt-autonomy/requirement.md`。
2. 创建 `15-embodied-subjective-prompt-autonomy/design.md`。
3. 创建 `15-embodied-subjective-prompt-autonomy/task.md`。
4. 更新 `docs/requirements/index.md`，同步 R15 的状态、依赖与实施顺序。
5. 验证：按 requirement authoring standard 做文档 review。
6. 完成定义：requirement、design、task 与 index 一致，可进入实现评审。

### T15-2 Refactor Shared Prompt Contract Terminology

1. 修改 `helios_io/prompt_contract.py` 的 identity wording，使其从 awakened-role framing 收敛为 subjective-integrator framing。
2. 增加 sensory-field 语义层与 anti-theatrical first-person constraints。
3. 保持 R12 中已有 metric/channel/op semantics 完整，不做回退。
4. 验证：focused prompt snapshot review 与 `tests/test_prompt_contract.py`。
5. 完成定义：shared contract 能渲染新语义，且未破坏必需层。

### T15-3 Align Internal Thought Prompt

1. 修改 `cognition/thinking_integration.py` 的 internal thought task wording。
2. 保持 mixed structured output schema 稳定。
3. 强化 no-action、continue-thinking、external action proposal 的区分语义。
4. 验证：focused `tests/test_thinking_integration_pbt.py` 与 thought trace inspection。
5. 完成定义：internal thought 继续是 primary autonomy owner，且 structured parse 未回退。

### T15-4 Align Active Speech Prompt

1. 修改 `helios_io/llm/speech.py`，使 active speech 复用 shared embodied-subjective contract。
2. 删除与 internal thought 冲突的独立 identity/performance framing。
3. 保留 speech-specific 的长度、节奏与 channel expression constraint 作为薄特化。
4. 验证：speech-path focused tests 与 prompt snapshot review。
5. 完成定义：active speech 不再维护冲突 self-model。

### T15-5 Tighten Passive Helper Boundary

1. 审计 `helios_io/response_pipeline.py` 中的 helper prompt 语义。
2. 审计 `helios_io/reply_prompt_builder.py` 的 compatibility 语言。
3. 若保留 compatibility helper，显式标注 non-owner status，并消除冲突的 self-model wording。
4. 验证：focused response-pipeline tests 与 grep-based boundary review。
5. 完成定义：passive helper paths 明确为 non-owning and semantically aligned。

### T15-6 Add Feature-Flagged Rollout

1. 新增 runtime flag，用于切换 baseline contract 与 embodied-subjective contract。
2. 将 internal thought 与 active speech 路径接入该 flag。
3. 保持日志与 observability 能区分两种模式。
4. 验证：narrow runtime checks 覆盖 flag on/off 两种状态。
5. 完成定义：新 prompt 架构可安全进行 A/B 对比与 staged rollout。

### T15-7 Add Anti-Theatrical and Grounding Regressions

1. 新增空泛自我存在句与陪伴套话的 focused regressions。
2. 新增 stimulus anchoring、structured no-action 与 capability hallucination regressions。
3. 新增 cross-path prompt semantics 的 focused regressions，防止 speech 与 thought 再次漂移。
4. 新增 mixed-affect parsing、negative acknowledgement、specific recall、boundary respect 和 user-anchored utterance 相关 regressions。
4. 验证：`tests/test_prompt_contract.py`、`tests/test_thinking_integration_pbt.py`、`tests/test_response_pipeline.py`、必要时补充 `tests/test_cli_brain_like_evaluation.py`。
5. 完成定义：核心 regression risk 已被最小化覆盖。

### T15-8 Run Comparative CLI Evaluation

1. 使用现有 CLI evaluation harness 分别运行 baseline 模式与 embodied-subjective 模式。
2. 比较语言自然度、自我聚焦、刺激锚定、动作 grounding 和 late-session degradation。
3. 审查 thought-origin action request 是否仍然 grounded 且受治理约束。
4. 将 mixed-affect parsing、negative acknowledgement、specific recall、boundary respect 和 user-visible line quality 作为显式对照观察项。
4. 验证：生成 JSON/Markdown evaluation artifacts，并形成 closeout evidence。
5. 完成定义：已有 evidence 支撑 keep / revise / revert 决策。

## 2. Dependencies

1. T15-1 依赖无前置，实现后阻塞所有后续任务。
2. T15-2 依赖 T15-1。
3. T15-3 依赖 T15-2。
4. T15-4 依赖 T15-2，可在 T15-3 之后或并行推进。
5. T15-5 依赖 T15-2，可与 T15-3 / T15-4 并行推进。
6. T15-6 依赖 T15-3、T15-4、T15-5。
7. T15-7 依赖 T15-3、T15-4、T15-5、T15-6。
8. T15-8 依赖 T15-7。

## 3. Files and Modules

1. `docs/requirements/15-embodied-subjective-prompt-autonomy/requirement.md`
2. `docs/requirements/15-embodied-subjective-prompt-autonomy/design.md`
3. `docs/requirements/15-embodied-subjective-prompt-autonomy/task.md`
4. `docs/requirements/index.md`
5. `helios_io/prompt_contract.py`
6. `cognition/thinking_integration.py`
7. `helios_io/llm/speech.py`
8. `helios_io/response_pipeline.py`
9. `helios_io/reply_prompt_builder.py`
10. `helios_main.py`
11. `tests/test_prompt_contract.py`
12. `tests/test_thinking_integration_pbt.py`
13. `tests/test_response_pipeline.py`
14. `tests/test_cli_brain_like_evaluation.py`

## 4. Implementation Order

1. T15-1
2. T15-2
3. T15-3
4. T15-4
5. T15-5
6. T15-6
7. T15-7
8. T15-8

## 5. Validation Plan

1. 先做文档级 review，确认 requirement/design/task/index 对齐。
2. shared contract 的第一次 substantive edit 后，优先跑 focused prompt-contract validation。
3. internal thought 的第一次 substantive edit 后，优先跑 thought parse / structured output focused validation。
4. active speech 的第一次 substantive edit 后，优先跑 speech-path focused validation。
5. 在进入 comparative CLI evaluation 前，必须先完成 planner/executor governance boundary validation。
6. comparative CLI evaluation 完成后，必须保留可复核 artifact。

## 6. Completion Criteria

1. R15 requirement package 已完成并通过开发前评审。
2. shared prompt semantics 已统一为 embodied subjectivity。
3. internal thought 仍是 primary structured autonomy owner。
4. active speech 与 passive helper 不再与 internal thought 发生 self-model drift。
5. regressions 已覆盖 self-focus、stimulus grounding 与 capability hallucination。
6. comparative evaluation artifacts 已生成并能支撑是否切换 default-on 的决策。