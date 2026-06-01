# Requirement 18 - Subjective autonomy and proactive evolution

## 1. Background and Problem

当前系统在结构上已经具备 thought loop、regulation、planner、channel 和 memory 等主观自治基础件，但实际运行中仍表现为“输入来了才动、回复优先、主观性偏弱”。最近 live evaluation 中可以看到外发成功事件存在，但主动行为密度低、思考外化稀疏、策略拒绝和 fallback 比例偏高，说明系统的主观性并未被持续释放。

问题的根源不只是 prompt 内容，而是主动性信号在 `helios_main.py`、`cognition/thinking_integration.py`、`regulation/regulation.py`、`helios_io/planning.py` 和 channel outbound 路径中被多层保守门控、默认回退和被动交互假设共同压制。结果是系统更像“等输入的问答代理”，而不是具身的、会持续形成内在趋向并在合适时机外化行动的主体。

## 2. Goal

恢复 Helios 以内部驱动、连续思考和受控外化为中心的主观自治，使系统在无外部输入或弱输入阶段也能维持自发思考、形成行动倾向、执行安全外化，并通过记忆与身份治理逐步产生可审计的自我演化轨迹。

本 requirement 的 owner/boundary 术语以 R19 对齐后的 [ARCHITECTURE_BOUNDARIES.zh-CN.md](../../ARCHITECTURE_BOUNDARIES.zh-CN.md) 和 [MODULE_REVIEW_MATRIX.zh-CN.md](../../MODULE_REVIEW_MATRIX.zh-CN.md) 为准；若 R18 的实现细节与这两份边界文档冲突，必须记录为迁移态或冲突点，而不是在本 package 内重新定义一套局部 owner 真相。

## 3. Functional Requirements

### 3.1 主动性驱动链路

1. 系统 must 将内驱、情绪张力、未完成意图、记忆回想、时间流逝/无聊、新异性饥饿、神经化学状态和人格偏置整合为正式 `proactive drive` 信号。
2. 在无显式外部输入时，主循环 must 允许 `proactive drive` 触发连续思考，而不是直接 idle 跳过。
3. 思考产物 must 能生成结构化的行动候选、表达候选或记忆整理候选，并进入正式 planner/policy 审核路径。
4. 主动性链路 must 支持跨 tick 的 continuity carry，使一次主动驱动可在未完成时继续影响后续思考和行为，而不是一次性耗散。
5. `proactive drive` must 至少能区分 `externalize`、`explore`、`reflect` 和 `defer` 四类主导 disposition，避免把“内向地主动思考”误判为“没有主动性”。

### 3.2 受控主动外化

1. 当主动性达到阈值且 policy 允许时，系统 must 能通过 channel ops 外化主动表达或主动动作。
2. 主动外化 must 带有明确 provenance，区分“响应输入的外化”和“内部驱动的外化”。
3. 主动外化频率 should 受异稳态、疲劳、时间节律和 channel 可用性约束，避免失控刷屏。
4. 若主动外化未发生，系统 must 记录“为什么未外化”，至少覆盖 policy 拒绝、无可用 channel、主动性不足和继续内部思考四类原因。
5. 时间流逝或无聊感不得被实现为定时硬编码的直接外发触发器；它们只能通过 temporal/neurochem/personality 对 `proactive drive` 和 disposition 施加压力。

### 3.3 自我演化闭环

1. 系统 must 将主动思考、主动行动结果和用户/环境反馈写入可审计的自我演化轨迹。
2. 身份和人格相关慢变量的变化 must 通过治理 owner 产生，而不能由单次 prompt 文本隐式篡改。
3. 记忆 consolidation should 优先保留对主观持续性、未完成目标和长期偏好的证据。
4. 当主动驱动因 policy 或环境约束被延迟时，系统 should 以 deferred intent 或等价结构保留其连续性，而不是直接丢弃。

### 3.4 评估与观测

1. 系统 must 暴露主动思考次数、主动行动候选次数、主动外发成功次数、被 policy 拒绝次数等指标。
2. live evaluation must 能观测到主动性相关信号，而不是把所有主动行为折叠进普通响应统计。
3. 当主动性长期被门控压制时，系统 should 输出诊断 warning。
4. 观测层 should 至少区分“外向型主动性”与“内向型主动性”，例如把外发尝试、探索倾向和内部反思倾向分别输出，而不是只统计对外输出次数。
5. 用于 R18 阈值细调的 calibration artifact must 来自当前框架版本下的新运行，不得继续复用在重大 owner/boundary 改造前产生的历史 log 或 report。
6. 只有当 artifact 中真实出现连续 `proactive_deferred_trace`、或 thought-action-bridge / regulation-origin rejection，并且 `proactive_governance_signal` 至少进入 `monitor` 时，该 artifact 才可作为 R18 阈值细调依据。

## 4. Non-Functional Requirements

1. 主动性增强不得绕过既有 policy、planner、channel gateway 和 behavior registry owner。
2. 新的主动路径 must 保持可审计和可回放，便于安全回归。
3. 在无可用 channel 或 policy 明确拒绝时，系统 must 降级为内部思考或记忆整理，而不是异常退出。
4. 主动性增强 should 以渐进方式 rollout，避免在单次变更中放开全部主动外化。
5. 主动性恢复不得只优化单次主动输出；还必须证明连续性和延续性没有在后续 ticks 中静默断裂。
6. R18 在实现 owner 划分、允许依赖、禁止 shortcut 和迁移态描述时 must 复用 R19 的边界基线，不得在 requirement/design/task 中重新定义与边界文档冲突的主动性 owner 语义。

## 5. Code Behavior Constraints

1. 禁止通过定时硬编码或 prompt 文案伪造主动性，而不经过正式 drive -> thought -> plan -> op 路径。
2. 禁止让 channel 直接拉起主动输出；主动外化 owner 必须仍在 thought/planning/regulation 主路径。
3. 禁止让身份或人格状态由一次主动输出文本直接回写；必须经过治理与审计层。
4. 不得以提高评估分数为目标制造无意义主动输出噪声。
5. 不得让未完成的主动趋向在 policy 拒绝或 channel 不可用后无痕消失。
6. 不得把人格、神经化学或时间流逝中的任一单层信号直接实现成“必然外发动作”；这些信号只能改变主动性压力、分流倾向或阈值。

## 6. Impacted Modules

1. `helios_main.py`
2. `core/helios_state.py`
3. `cognition/thinking_integration.py`
4. `cognition/thinking.py`
5. `regulation/regulation.py`
6. `regulation/conation.py`
7. `helios_io/planning.py`
8. `helios_io/interaction_policy.py`
9. `helios_io/limb.py`
10. `helios_io/channel_gateway.py`
11. `memory/memory_system.py`
12. `personality.py`
13. `personality_projection.py`
14. `neurochem_gate.py`
15. `temporal_gate.py`
16. `tests/test_tick_response_wiring.py`

## 7. Acceptance Criteria

1. 在无外部输入的短时运行窗口中，系统能够观测到主动思考与主动候选生成，而不是持续零活动。
2. 至少一个主动外化路径能够通过正式 planner/policy/channel gateway 成功执行，并在状态或日志中标明 `proactive` provenance。
3. 当 policy 拒绝主动外化时，系统会保留内部思考或记忆整理结果，且不会直接丢失该次主动驱动。
4. 自动化测试能够覆盖主动 drive 触发、主动计划生成、policy 拒绝降级和主动外发成功四类场景。
5. 至少一组测试或短时 live artifact 能证明主动 continuity carry 或 deferred intent 能跨 tick 保持，而不是只出现一次性脉冲。
6. R18 的实现与文档审查应能回链到 R19 的边界文档，明确 proactive drive、thought continuation、planner/policy 审核、channel 执行和 self-evolution trace 分别属于哪个 owner，而不是以“谁当前顺手实现了该逻辑”替代 owner 归属。
7. runtime `proactive` snapshot 至少要能稳定导出 drive sources、dominant disposition，以及 `social_outward_pressure`、`exploration_pressure`、`internal_reflection_pressure`、`caution_pressure` 四类压力，不得只保留单一总分。
8. 任何宣称用于 R18 阈值校准的 live artifact 都必须能回链到真实 deferred/governance 命中证据；若 `deferred_trace_samples=0` 且 `governance_signal_monitor_samples=0`，则该 artifact 只能用于其他链路诊断，不得用于继续细调 R18 阈值。
