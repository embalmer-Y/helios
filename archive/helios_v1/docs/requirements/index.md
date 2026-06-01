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
9. embodied subjective prompt and action autonomy
10. dynamic I/O channel framework
11. evaluation fidelity and diagnostic provenance
12. subjective autonomy and proactive evolution
13. architecture boundary and owner documentation
14. brain architecture comparison and scientific grounding

如模块审查矩阵确认后出现额外不可合并的 concern，应新增独立 package，而不是混入现有 package。

## 4. 推荐首批 requirement packages

| ID | 名称 | 优先级 | 状态 | 目标摘要 | Requirement | Design | Task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R07 | Consciousness-First LLM Loop | P0 | validated | 将 LLM 从 reply-first 路径收回到主意识循环，并定义思考触发、连续思考和主循环 owner。 | [requirement](07-consciousness-first-llm-loop/requirement.md) | [design](07-consciousness-first-llm-loop/design.md) | [task](07-consciousness-first-llm-loop/task.md) |
| R08 | Stimulus Weighting and Thought Gating | P0 | validated | 将来源、触发条件、输入强度、新异性与门控整合为统一刺激契约。 | [requirement](08-stimulus-weighting-and-thought-gating/requirement.md) | [design](08-stimulus-weighting-and-thought-gating/design.md) | [task](08-stimulus-weighting-and-thought-gating/task.md) |
| R09 | Thought-to-Action Op Bridge | P0 | in-progress | 允许思考结果提议结构化 op 和参数，并通过统一主路径受控外化；最终移除独立 passive reply owner。 | [requirement](09-thought-to-action-op-bridge/requirement.md) | [design](09-thought-to-action-op-bridge/design.md) | [task](09-thought-to-action-op-bridge/task.md) |
| R10 | Identity Bootstrap and Self-Revision | P0 | validated | 定义首启身份注入、用户锁定、内部自我修订治理、版本历史与审计。 | [requirement](10-identity-bootstrap-and-self-revision/requirement.md) | [design](10-identity-bootstrap-and-self-revision/design.md) | [task](10-identity-bootstrap-and-self-revision/task.md) |
| R11 | Memory Tiering and Directed Retrieval | P0 | validated | 定义短期/中期/长期/自传记忆，以及思考前的定向检索与 recall intent。 | [requirement](11-memory-tiering-and-directed-retrieval/requirement.md) | [design](11-memory-tiering-and-directed-retrieval/design.md) | [task](11-memory-tiering-and-directed-retrieval/task.md) |
| R12 | Prompt Metric and Channel Context Contract | P1 | validated | 统一 prompt 中的指标解释、上下限、channel 语义、ops 与身份边界。 | [requirement](12-prompt-metric-and-channel-context-contract/requirement.md) | [design](12-prompt-metric-and-channel-context-contract/design.md) | [task](12-prompt-metric-and-channel-context-contract/task.md) |
| R13 | Terminal CLI Channel | P1 | validated | 定义正式终端输入输出 channel、本地 session 边界和最小 CLI 管理命令，而不绕过现有 channel/tick/action owner。 | [requirement](13-terminal-cli-channel/requirement.md) | [design](13-terminal-cli-channel/design.md) | [task](13-terminal-cli-channel/task.md) |
| R14 | CLI Brain-Like Evaluation | P1 | in-progress | 定义 10 分钟 mixed-mode CLI 交互评估、分块评分、structured report 与分析 artifact，而不绕过现有 CLI/channel/tick/action owner。 | [requirement](14-cli-brain-like-evaluation/requirement.md) | [design](14-cli-brain-like-evaluation/design.md) | [task](14-cli-brain-like-evaluation/task.md) |
| R15 | Embodied Subjective Prompt and Action Autonomy | P1 | draft | 定义具身主观 prompt 架构，使 LLM 作为当前主观整合层整合感官场、状态、记忆与结构化动作自治，而不退回身份表演或 reply-first prompt。 | [requirement](15-embodied-subjective-prompt-autonomy/requirement.md) | [design](15-embodied-subjective-prompt-autonomy/design.md) | [task](15-embodied-subjective-prompt-autonomy/task.md) |
| R16 | Dynamic I/O Channel Framework | P0 | closed | 将 channel 子系统升级为动态 registry + op router + lifecycle/config framework，使 channel 可动态 add/remove 且统一通过 channel-exposed ops 交互。 | [requirement](16-dynamic-io-channel-framework/requirement.md) | [design](16-dynamic-io-channel-framework/design.md) | [task](16-dynamic-io-channel-framework/task.md) |
| R17 | Evaluation Fidelity and Diagnostic Provenance | P0 | validated | 将 CLI 评估从 presence-based 打分升级为 evidence-driven 诊断，显式暴露维度归因、负向事件和 fidelity warning，并已通过 forced-fallback paired artifact 验证总分与对外维度差异。 | [requirement](17-evaluation-fidelity-and-diagnostic-provenance/requirement.md) | [design](17-evaluation-fidelity-and-diagnostic-provenance/design.md) | [task](17-evaluation-fidelity-and-diagnostic-provenance/task.md) |
| R18 | Subjective Autonomy and Proactive Evolution | P0 | draft | 恢复内部驱动、连续思考和受控主动外化，使系统在弱输入或无输入窗口中仍保持主观活动和可审计自我演化。 | [requirement](18-subjective-autonomy-and-proactive-evolution/requirement.md) | [design](18-subjective-autonomy-and-proactive-evolution/design.md) | [task](18-subjective-autonomy-and-proactive-evolution/task.md) |
| R19 | Architecture Boundary and Owner Documentation | P1 | in-progress | 建立中文 owner/boundary 文档体系，明确域职责、协作流、禁止 shortcut 与迁移态，作为后续 requirement 和实现的统一边界真相。 | [requirement](19-architecture-boundary-and-owner-documentation/requirement.md) | [design](19-architecture-boundary-and-owner-documentation/design.md) | [task](19-architecture-boundary-and-owner-documentation/task.md) |
| R20 | Brain Architecture Comparison and Scientific Grounding | P2 | draft | 建立 Helios 与人脑功能系统的谨慎映射、文献支撑和差距分析，为类脑目标和 requirement 优先级提供科学 grounding。 | [requirement](20-brain-architecture-comparison-and-scientific-grounding/requirement.md) | [design](20-brain-architecture-comparison-and-scientific-grounding/design.md) | [task](20-brain-architecture-comparison-and-scientific-grounding/task.md) |

## 5. 依赖关系

1. R07 是主循环 owner 的基础 requirement。
2. R08 为 R07 和 R11 提供统一刺激输入语义。
3. R09 依赖 R07 与 R08，因为思考结果必须先成为正规 owner，刺激强度与来源也必须先被正式化。
4. R10 与 R07 强关联，因为“我是谁”的思考和自我修订必须从内部 thought loop 发出。
5. R11 依赖 R07 与 R08，因为 directed retrieval 服务于思考前置阶段。
6. R12 依赖 R07、R08、R09、R10、R11，因为 prompt contract 需要消费它们定义的正式指标和边界。
7. R13 依赖 R08、R09、R12，因为 terminal channel 需要复用正式 stimulus ingress、outbound action execution 与 channel/op contract 语义。
8. R14 依赖 R08、R09、R12、R13，因为类脑评估需要复用正式 stimulus/channel provenance、thought-to-action 路径、prompt/channel contract 和 CLI owner。
9. R15 依赖 R07、R08、R09、R11、R12、R13、R14，因为具身主观 prompt 必须建立在正式 thought loop、stimulus ingress、thought-to-action、directed retrieval、prompt contract、CLI owner 与 evaluation evidence 之上。
10. R16 依赖 R09、R12、R13，因为动态 channel framework 需要复用正式 op contract、channel descriptor 语义与现有 channel owner path，同时把 lifecycle/config 管理提升为一等 runtime concern。
11. R17 依赖 R14、R16，因为评估真实性诊断必须建立在现有 live harness 与正式 channel/runtime owner 边界之上。
12. R18 依赖 R07、R08、R09、R11、R15、R16、R19，并建议与 R17 并行收敛，因为主观主动性需要以正式 thought/action/channel 语义、边界基线和真实评估诊断共同驱动。
13. R19 依赖模块审查矩阵、现有哲学/HLD/roadmap 文档，以及 R07-R16 已形成的 owner 边界事实，用于把这些事实收敛成可执行的文档基线。
14. R20 依赖 R19 提供的 owner/boundary 基线，并参考 R07-R18 的 requirement 事实来形成科学比较和差距映射。

R19 的当前活跃文档载体是 [ARCHITECTURE_BOUNDARIES.zh-CN.md](../ARCHITECTURE_BOUNDARIES.zh-CN.md)；该文档与 [MODULE_REVIEW_MATRIX.zh-CN.md](../MODULE_REVIEW_MATRIX.zh-CN.md) 一起构成 R17-R20 的共同边界引用基线。后续 requirement 若需要说明 owner、允许依赖、禁止 shortcut 或迁移态，应优先引用这两份文档，而不是重新定义一套局部边界术语。

## 6. 建议实施顺序

1. R07 Consciousness-First LLM Loop
2. R08 Stimulus Weighting and Thought Gating
3. R11 Memory Tiering and Directed Retrieval
4. R09 Thought-to-Action Op Bridge
5. R10 Identity Bootstrap and Self-Revision
6. R12 Prompt Metric and Channel Context Contract
7. R13 Terminal CLI Channel
8. R14 CLI Brain-Like Evaluation
9. R15 Embodied Subjective Prompt and Action Autonomy
10. R16 Dynamic I/O Channel Framework
11. R17 Evaluation Fidelity and Diagnostic Provenance
12. R18 Subjective Autonomy and Proactive Evolution
13. R19 Architecture Boundary and Owner Documentation
14. R20 Brain Architecture Comparison and Scientific Grounding

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

1. 保持 R17 的 artifact 与 scorer 回归样本稳定，避免后续 R18/R19 改动重新引入 presence-based 失真。
2. 并行推进 R19，补齐 owner/boundary 文档与模块确认闭环。
3. 基于已稳定的 R17 诊断输出推进 R18，恢复主观主动性与自我演化闭环。
4. 将 R20 作为科学 grounding 文档包，在 R19 边界文档稳定后补齐文献映射与差距分析。
5. 对 R14 保持实现收敛，但新增真实性诊断优先沉淀到 R17，而不是继续堆叠在 R14 范围内。
6. 在 R16 closed package 上仅做回归维护，不再扩写 requirement 范围。
7. 持续保持 requirement / design / task 与 runtime truth 对齐。

## 10. Unfinished Review and Checkpoints

截至 2026-05-30，当前仍应视为未完成或未正式 closeout 的 requirement package 包括：R09、R14、R15、R18、R19、R20。

推荐执行顺序调整为：

1. `R09` Thought-to-Action Op Bridge
2. `R18` Subjective Autonomy and Proactive Evolution
3. `R14` CLI Brain-Like Evaluation 与 `R19` Architecture Boundary and Owner Documentation 的状态/证据同步
4. `R15` Embodied Subjective Prompt and Action Autonomy closeout
5. `R20` Brain Architecture Comparison and Scientific Grounding

排序理由：

1. `R09` 仍存在 reopen runtime gap；若 structured thought decision 到正式 action proposal 的真实 trace 不能稳定闭合，后续 `R18` 主观主动性与 `R15` 动作自治都缺少可信执行基底。
2. `R18` 当前已经具备大部分 state/export、deferred trace、governance consumption 和 evaluation observability，但后续阈值细调与 closeout 需要建立在 `R09` 已闭合且 `R17/R14` artifact 可判别的前提上。
3. `R14` 与 `R19` 当前更像“维护与收口”而非主阻塞项，应服务于 `R09/R18`，保证 report、边界术语和 closeout 证据持续与 runtime truth 对齐。
4. `R15` 已有较多实现切片，但其最终 closeout 仍依赖 thought/action grounding 与 comparative evidence，因此排在 `R09/R18` 之后更稳。
5. `R20` 是 grounding 文档包，不应抢在执行主路径与 closeout 证据之前。

开发 checkpoints：

1. `Checkpoint A / R09 bridge truth`：真实 runtime artifact 中，若 `action_explicit=true`，则必须看到非空 `action_proposal` 或显式 `drop_reason`；不得再出现 silent `{}` closeout。
2. `Checkpoint B / R18 calibration admissibility`：任何用于 R18 阈值校准的 artifact，必须满足 `deferred_trace_samples > 0` 或真实 rejection evidence，且 `governance_signal_monitor_samples > 0`。
3. `Checkpoint C / R14-R19 evidence sync`：evaluation report、requirements index、boundary documents 三者对 owner、trace 字段和 closeout 证据的口径必须一致；若不一致，优先修正文档/评估层，不继续放大需求范围。
4. `Checkpoint D / R15 autonomy grounding`：comparative prompt/autonomy artifact 必须证明动作 grounding、用户锚定和反戏剧化约束没有因 prompt 变化而回退。
5. `Checkpoint E / R20 last-mile`：只有当 R09/R18/R15 的 closeout 证据已稳定，才进入 R20 的科学映射与差距分析。

2026-05-30 R09 review update:

1. 旧的 `thought_action_gap` 结论已经被修正 evaluator 口径后的 fresh live artifact 部分排除：当前 live report 已显示 `action_proposal_samples > 0`、`final_action_summaries=["speak_share:send"]`、`visible_reply_events > 0`，说明 `thought -> action proposal -> visible outbound` 的主链路并未在该 artifact 中断裂。
2. 随后的 T09-9 修复已进一步证明，`speak_share` 这类 heuristic thought-origin externalization 不应继续被简单归类为 `missing_action_explicit`。fresh short live artifact `cli_brain_like_eval_r09_focus_6min_20260530_t099_equiv.json` 中 `action_explicit_samples=0`，但 `equivalent_bridge_evidence_samples=5`，且 `r09_closeout.closeout_status="equivalent_bridge_evidence_observed"`、`blocking_reasons=[]`。
3. 新 comparison artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_equiv_compare.comparison.json` 已把旧短场景 artifact 与新 artifact 并排对比，确认主要变化点是 closeout 语义从 `implicit_proposal_only` 收口为 `equivalent_bridge_evidence_observed`，而不是 R18 admissibility 或可见输出比率变化。
4. 继续直追 explicit structured-decision live owner path 后，runtime 已确认真正的 owner boundary 缺口在 `helios_main.py`：thought-origin `speak_*` 缺失 `outbound_text` 时，过去会落到下游 `LLMSpeechGenerator` 补文案；现已改为记录 `execution_consistency_failure(reason=missing_outbound_text)` 并拒绝外发。
5. fresh live artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_explicit_probe_v4.json` 已出现 `execution_consistency_failure_events=6`、`top_rejection_reasons=["missing_outbound_text:6"]`、`visible_reply_events=0`。这说明当前 blocker 已从“implicit evidence 是否缺失”进一步缩小到“explicit structured-decision / thought-origin payload 没有稳定给出 `outbound_text`”。
6. evaluator 现已把这类 artifact 的 `r09_closeout` 收口为 `blocked_missing_outbound_text`，避免继续把 owner-boundary rejection 误算成 closeout 成功。
7. 随后对 `cognition/thinking_integration.py` 的 structured decision 归一化补上 `op_name/requested_op` 与 `visible_text/message_text/reply_text/utterance/text/message` 等近邻字段 canonicalization 后，fresh live artifact `tests/reports/cli_brain_like_eval_r09_focus_6min_20260530_explicit_probe_v5.json` 已显示 `structured_output_valid_samples=1`、`action_explicit_samples=1`。这说明当前 live provider 的一部分 explicit JSON 已开始穿过 bridge，不再完全卡死在字段别名层。
8. 但同一 artifact 仍显示 `execution_consistency_failure_events=6`、`top_rejection_reasons=["missing_outbound_text:6"]`、`r09_closeout.closeout_status="blocked_missing_outbound_text"`。由此可见，R09 当前剩余工作不再是泛化地追 `missing_action_explicit`，而是继续确认真正 explicit structured-decision path 在 live artifact 中也能稳定保留 `action_explicit` / `drop_reason`，并稳定产出必需的 `outbound_text`；在此完成前，R18 targeted harness 仍不应成为主工作面。
9. R09 的终态目标现已进一步明确：系统不再保留与主路径并列竞争用户可见输出 owner 的 passive 承接路径；外部输入仍可作为 stimulus ingress 存在，但所有用户可见外发都必须统一经由 `internal thought / thought_action_bridge -> planner / executor / channel` 主路径处理。
