# Requirements Index

## 1. 目的

本索引用于管理 Helios 在新类脑意识优先哲学下的 requirement 体系。

本轮 requirement 不再沿用“reply-first + internal-thought side path”的老问题定义，而是围绕以下目标建立：

- 让 LLM 回归内部意识循环
- 让外部行动从思考中产生
- 让刺激、通道、强度和治理进入一等架构概念
- 让人格、自我定义和记忆分层成为正式 owner

requirement 编写规范见：

- [requirement-authoring-standard.md](requirement-authoring-standard.md)

## 2. 当前状态

旧 requirement packages (`01-*` 到 `06-*`) 已从活动文档体系中移除。

当前 `docs/requirements/` 下保留的内容，只服务于新的类脑意识优先架构。

## 3. 新 requirement 体系目标

新的 requirement 体系至少需要覆盖以下顶层 concern：

1. consciousness-first LLM loop
2. stimulus weighting and thought gating
3. thought-to-action op bridge
4. identity bootstrap and self-revision governance
5. memory tiering and directed retrieval
6. prompt metric and channel context contract
7. terminal CLI channel
8. CLI brain-like evaluation

如模块审查矩阵确认后出现额外不可合并的 concern，应新增独立 package，而不是混入现有 package。

## 4. 推荐首批 requirement packages

| ID | 名称 | 优先级 | 状态 | 目标摘要 | Requirement | Design | Task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R07 | Consciousness-First LLM Loop | P0 | validated | 将 LLM 从 reply-first 路径收回到主意识循环，并定义思考触发、连续思考和主循环 owner。 | [requirement](07-consciousness-first-llm-loop/requirement.md) | [design](07-consciousness-first-llm-loop/design.md) | [task](07-consciousness-first-llm-loop/task.md) |
| R08 | Stimulus Weighting and Thought Gating | P0 | validated | 将来源、触发条件、输入强度、新异性与门控整合为统一刺激契约。 | [requirement](08-stimulus-weighting-and-thought-gating/requirement.md) | [design](08-stimulus-weighting-and-thought-gating/design.md) | [task](08-stimulus-weighting-and-thought-gating/task.md) |
| R09 | Thought-to-Action Op Bridge | P0 | in-progress | 允许思考结果提议结构化 op 和参数，并通过 planner/executor 受控外化。 | [requirement](09-thought-to-action-op-bridge/requirement.md) | [design](09-thought-to-action-op-bridge/design.md) | [task](09-thought-to-action-op-bridge/task.md) |
| R10 | Identity Bootstrap and Self-Revision | P0 | validated | 定义首启身份注入、用户锁定、内部自我修订治理、版本历史与审计。 | [requirement](10-identity-bootstrap-and-self-revision/requirement.md) | [design](10-identity-bootstrap-and-self-revision/design.md) | [task](10-identity-bootstrap-and-self-revision/task.md) |
| R11 | Memory Tiering and Directed Retrieval | P0 | validated | 定义短期/中期/长期/自传记忆，以及思考前的定向检索与 recall intent。 | [requirement](11-memory-tiering-and-directed-retrieval/requirement.md) | [design](11-memory-tiering-and-directed-retrieval/design.md) | [task](11-memory-tiering-and-directed-retrieval/task.md) |
| R12 | Prompt Metric and Channel Context Contract | P1 | validated | 统一 prompt 中的指标解释、上下限、channel 语义、ops 与身份边界。 | [requirement](12-prompt-metric-and-channel-context-contract/requirement.md) | [design](12-prompt-metric-and-channel-context-contract/design.md) | [task](12-prompt-metric-and-channel-context-contract/task.md) |
| R13 | Terminal CLI Channel | P1 | validated | 定义正式终端输入输出 channel、本地 session 边界和最小 CLI 管理命令，而不绕过现有 channel/tick/action owner。 | [requirement](13-terminal-cli-channel/requirement.md) | [design](13-terminal-cli-channel/design.md) | [task](13-terminal-cli-channel/task.md) |
| R14 | CLI Brain-Like Evaluation | P1 | in-progress | 定义 10 分钟 mixed-mode CLI 交互评估、分块评分、structured report 与分析 artifact，而不绕过现有 CLI/channel/tick/action owner。 | [requirement](14-cli-brain-like-evaluation/requirement.md) | [design](14-cli-brain-like-evaluation/design.md) | [task](14-cli-brain-like-evaluation/task.md) |

## 5. 依赖关系

1. R07 是主循环 owner 的基础 requirement。
2. R08 为 R07 和 R11 提供统一刺激输入语义。
3. R09 依赖 R07 与 R08，因为思考结果必须先成为正规 owner，刺激强度与来源也必须先被正式化。
4. R10 与 R07 强关联，因为“我是谁”的思考和自我修订必须从内部 thought loop 发出。
5. R11 依赖 R07 与 R08，因为 directed retrieval 服务于思考前置阶段。
6. R12 依赖 R07、R08、R09、R10、R11，因为 prompt contract 需要消费它们定义的正式指标和边界。
7. R13 依赖 R08、R09、R12，因为 terminal channel 需要复用正式 stimulus ingress、outbound action execution 与 channel/op contract 语义。
8. R14 依赖 R08、R09、R12、R13，因为类脑评估需要复用正式 stimulus/channel provenance、thought-to-action 路径、prompt/channel contract 和 CLI owner。

## 6. 建议实施顺序

1. R07 Consciousness-First LLM Loop
2. R08 Stimulus Weighting and Thought Gating
3. R11 Memory Tiering and Directed Retrieval
4. R09 Thought-to-Action Op Bridge
5. R10 Identity Bootstrap and Self-Revision
6. R12 Prompt Metric and Channel Context Contract
7. R13 Terminal CLI Channel
8. R14 CLI Brain-Like Evaluation

## 7. 状态规则

新 requirement package 状态建议统一为：

- `planned`
- `draft`
- `in-progress`
- `validated`
- `closed`

旧 package 在 reset 期间不再继续推进状态，只保留为 legacy context，直至删除。

## 8. 变更管理要求

1. 每个新 requirement package 必须同时维护 `requirement.md`、`design.md`、`task.md`。
2. requirement、design、task 的所有权、依赖、默认 rollout 和失败模式必须保持一致。
3. 若模块审查矩阵导致 requirement 拆分变化，必须同步更新本索引。
4. 不得在 `docs/requirements/` 下重新引入旧 reply-first requirement 包或兼容性占位包。

## 9. 下一步

下一步不是继续扩写旧 requirement，而是：

1. 基于模块审查矩阵继续完成分组确认。
2. 审阅并细化 `R07-R12` requirement packages。
3. 在 `R13` validated package 上继续做体验增强与回归维护。
4. 推进 `R14` CLI 类脑评估 requirement 与实现收敛。
5. 持续保持 requirement / design / task 与 runtime truth 对齐。
