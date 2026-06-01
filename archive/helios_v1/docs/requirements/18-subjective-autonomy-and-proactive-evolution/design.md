# Requirement 18 - Subjective autonomy and proactive evolution

## 1. Design Overview

本设计把“主观主动性”定义为正式 runtime concern，而不是 prompt 风格增强。实现上新增 `proactive drive` 汇总、`proactive thought session`、`proactive decision provenance` 和 `self-evolution trace` 四个概念，并保持 owner 分层不变：主循环负责调度，thinking integration 负责触发与连续思考，regulation 负责内在趋向，planning/policy 负责可执行候选审核，channel gateway 只负责按 provenance 执行 ops。

R18 的主动性不应被压缩成“要不要对外说话”的一维信号，而应被建模为多个上游层共同塑造的 disposition 分流结果：

1. 情感层回答“当前主观张力来自什么”。
2. 时间/无聊层回答“为什么主动压力正在累积”。
3. 神经化学层回答“此刻更偏探索、表达、谨慎还是安抚”。
4. 人格层回答“同样的压力更倾向外化、探索还是内省”。
5. regulation / thinking / planning 再决定这股压力最终是 `externalize`、`explore`、`reflect` 还是 `defer`。

R18 的 owner/boundary 解释不单独发明局部术语，而是直接继承 R19 已固定的 [ARCHITECTURE_BOUNDARIES.zh-CN.md](../../ARCHITECTURE_BOUNDARIES.zh-CN.md) 与 [MODULE_REVIEW_MATRIX.zh-CN.md](../../MODULE_REVIEW_MATRIX.zh-CN.md)。本 design 只补充“主动性如何穿过这些 owner 边界”，不重写“边界本身是谁”。

## 2. Current State and Gap

当前系统的主动性缺口主要体现在：

1. idle 或弱输入阶段缺少正式的 proactive trigger 聚合。
2. thinking integration 偏向响应外部事件，而非维持内部连续思考。
3. planning 和 interaction policy 对主动输出没有单独语义，导致主动候选被视为异常或直接压制。
4. 主动行为即使发生，也缺少 provenance 和后续自我演化记录。
5. 现有 temporal gate、neurochem gate 和 personality projection 已经提供了探索/表达/谨慎/反思偏置，但这些信号还没有被统一提升成 R18 的正式 `proactive drive` 和 `dominant disposition` 语义。

结合 R19 边界文档的当前态，R18 还需要显式承认两条迁移态事实：

1. `helios_main.py` 仍未完全摆脱被动响应历史语义，因此 proactive path 的第一阶段应优先补 state/export 和原因链，而不是先放大外发频率。
2. proactive drive 仍未成为正式 state/export owner 字段，因此主动性缺口目前既是行为问题，也是 observability 问题。

## 3. Target Architecture

目标架构新增以下运行路径：

1. `ProactiveDriveSnapshot`
   - owner: `regulation/regulation.py`
   - 输入: drives、emotion tension、allostasis、pending intentions、memory recall urge、temporal rhythm、neurochem gate、temporal gate、personality projection。
   - 输出: 主动性强度、候选主题、建议动作类型、继续思考压力，以及 disposition 所需的结构化压力分量。
2. `ProactiveThoughtSession`
   - owner: `cognition/thinking_integration.py`
   - 在无外部输入或外部输入较弱时，允许由 proactive drive 拉起 thought。
3. `DecisionProvenance.proactive`
   - owner: `helios_io/planning.py`
   - 区分 reactive 与 proactive 候选，使 policy 和 evaluation 能正确识别。
4. `SelfEvolutionTraceRecord`
   - owner: identity/memory governance 组合层
   - 记录主动驱动、形成的意图、执行结果、反馈和可能的慢变量更新。

整体数据流为：

1. 主循环计算外部刺激与内部 proactive drive。
2. 主循环先把 proactive drive 分解为 `social_outward_pressure`、`exploration_pressure`、`internal_reflection_pressure`、`caution_pressure`，并导出 `dominant_disposition`。
3. thinking integration 决定拉起 reactive 或 proactive thought session。
4. preconscious / planning 生成结构化候选并标记 provenance。
5. policy 决定外化、延期、压制或仅内部沉淀。
6. 结果进入 memory consolidation 与 self-evolution trace。

## 4. Data Structures

建议新增或扩展以下数据结构：

```python
@dataclass(frozen=True)
class ProactiveDriveSnapshot:
    score: float
    sources: list[str]
    topic_hints: list[str]
    continuation_pressure: float
   social_outward_pressure: float
   exploration_pressure: float
   internal_reflection_pressure: float
   caution_pressure: float
   dominant_disposition: str  # externalize | explore | reflect | defer
    recommended_actions: list[str]

@dataclass(frozen=True)
class DecisionProvenance:
    kind: str  # reactive | proactive | mixed
    trigger_sources: list[str]
    drive_score: float

@dataclass(frozen=True)
class SelfEvolutionTraceRecord:
    tick_id: int
    provenance: DecisionProvenance
    thought_summary: str
    selected_op: str | None
    outcome: str
    feedback_summary: str | None
```

若现有数据结构已能承载部分字段，应以增量扩展为主，避免重复建模。

## 5. Module Changes

1. `helios_main.py`
   - 在 tick 中增加 proactive drive 汇总、disposition 分流、idle-path 决策与最小原因链导出。
2. `regulation/regulation.py` / `regulation/conation.py`
   - 输出稳定的 proactive drive snapshot。
3. `cognition/thinking_integration.py` / `cognition/thinking.py`
   - 支持 proactive thought session 和连续思考延续。
4. `personality_projection.py` / `temporal_gate.py` / `neurochem_gate.py`
   - 继续作为 proactive drive 的上游 bias provider，而不是直接拥有动作决策权。
5. `helios_io/planning.py` / `helios_io/interaction_policy.py`
   - 将 proactive provenance 纳入候选审核。
6. `helios_io/limb.py` / `helios_io/channel_gateway.py`
   - 执行层接受 provenance，但仍不拥有主动性决策权。
7. `memory/memory_system.py` / identity persistence
   - 写入 self-evolution trace 与未完成意图。

## 6. Migration Plan

1. 第一阶段先引入 `proactive drive` 统计与内部 thought 触发，不直接扩大外发频率。
2. 第二阶段引入 planner/policy 对 proactive provenance 的显式支持。
3. 第三阶段放开受控主动外化，并为 evaluation 提供指标。
4. 默认 rollout 为“主动思考默认开启，主动外发默认受 policy 严格限制”。

按 R19 边界约束，第一阶段的最小落地点应优先满足：

1. proactive drive 有正式 owner 和 state/export 出口。
2. policy 拒绝、channel 不可用、继续内部思考等未外化原因可被 evaluation 读取。
3. 主动性增强仍走 thought -> plan -> op 主路径，而不是在 channel 或 prompt 层面伪造。
4. 时间流逝/无聊只允许提升 exploration / expression pressure，不允许被实现为直接定时外发触发器。

## 7. Failure Modes and Constraints

1. 若 proactive drive 计算失败，主循环回退为现有 reactive-only 模式，但输出 warning。
2. 若 policy 拒绝主动外化，结果必须保留为内部 thought 或 memory trace。
3. 若 channel 不可用，planner 仍可选择非外发类候选，如记忆整理或延迟计划。
4. 本 requirement 不允许通过提升输出频率来伪造主观性；必须保持语义和治理一致性。
5. 内向型主动性不得被误判为“没有主动性”；如果 disposition 倾向 `reflect` 或 `explore`，评估层不应仅因未外发就判定该 tick 为零主动性。

## 8. Observability and Logging

1. `HeliosState` 应暴露 proactive drive score、proactive thought count、proactive outbound attempts/successes。
2. 关键日志应包含 proactive provenance、policy disposition 和 selected op。
3. evaluation harness 应能区分 proactive 与 reactive 成功率。
4. 对长期零主动性的会话输出 warning，便于诊断主动链路被压制的位置。
5. evaluation 侧的 proactive 指标命名和 owner 解释应与 R19 边界文档保持一致，避免在评估器中重新发明一套“主动性来源”口径。
6. `HeliosState.proactive` 至少应导出 `drive_sources`、`dominant_disposition`、`social_outward_pressure`、`exploration_pressure`、`internal_reflection_pressure`、`caution_pressure`，使评估层能区分外向型主动性和内向型主动性。

## 9. Validation Strategy

1. 为 idle-path proactive thought 触发增加窄范围单测。
2. 为 proactive candidate -> policy -> channel gateway 路径增加集成测试。
3. 验证 policy 拒绝后的降级行为仍会保留内部 trace。
4. 使用短时 live 运行确认在无输入窗口中能够产生可观测 proactive signal。
5. 若要继续细调 `proactive_governance_signal` 阈值，必须优先构造或筛选能真实命中 deferred trace / rejection -> governance `monitor` 的定向 artifact；仅出现 SEC 退化、长程质量漂移或输出稀疏，而未进入 deferred/governance 路径的 artifact，不得作为阈值调参依据。
