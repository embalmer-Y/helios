# Requirement 17 - Evaluation fidelity and diagnostic provenance

## 1. Design Overview

本设计将现有 CLI 类脑评估从“结果打分器”升级为“证据驱动诊断器”。核心变化不是新增更多主观维度，而是让每个维度分数都依赖统一的诊断证据模型，并把分数、负向归因、责任 owner、样本片段和 warning 一起输出到 artifact。实现上以 `CliBrainLikeEvaluator` 为 owner，复用 harness 的时间采样和报告落盘机制，不引入新的 runtime 旁路。

## 2. Current State and Gap

当前 `CliBrainLikeEvaluator.evaluate()` 已有 6 个评分维度和行为门控，但存在 4 个主要缺口：

1. 维度评分依赖状态存在性和范围约束，缺少因果证据链。
2. 负向事件只体现在总览计数里，没有成为维度级扣分依据。
3. report 输出的是最终分数和摘要文案，无法回答“为什么是这个分数”。
4. harness 无法稳定区分“未观测到”“观测到失败”“通过 fallback 勉强工作”和“稳定真实工作”。

基于 2026-05-29 的最新 paired runs，原始缺口还需要再细化为两个 owner 级问题：

1. forced fallback 语义不能只停留在 runner 配置层；若 `LLMSECEvaluator(api_key="")` 仍回退复用环境变量凭证，对照条件会被污染。
2. SEC provenance 不能只靠日志正则汇总；评估器必须优先消费 runtime `sec_evaluator` 计数，否则 artifact 可能出现 `sec_fallback_delta` 和真实运行态不一致，进而吞掉总分差异。

## 3. Target Architecture

目标结构由 4 个部分组成：

1. `EvaluationEvidenceRecord`：单条证据结构，记录维度、事件类型、来源、严重度、计数、样本片段和 owner hint。
2. `DimensionDiagnosticSummary`：单维度诊断汇总，输出 base score、penalties、warnings、positive evidence、negative evidence 和 gap summary。
3. `BehavioralFidelityGate`：统一行为真实性门控，消费语言、情感、主动性、外发成功率和回退率等指标，对内部健康维度施加上限。
4. `EvaluationReportRenderer` 的轻量扩展：把诊断 summary 直接渲染到 JSON/Markdown artifact，而不是在渲染阶段重新推断。
5. `RuntimeSECProvenanceSnapshot`：由 `helios.get_state()` 暴露的只读 SEC 观测快照，至少包含 `total_evaluations`、`llm_successes`、`fallback_count`，供 evaluator 覆盖日志噪声。

数据流如下：

1. harness 收集 transcript、state snapshots、log counters。
2. evaluator 先合并 runtime SEC provenance 与 log summary，形成同一份 SEC 计数语义。
3. evaluator 将原始输入归一化为 evidence records。
4. 各维度 scorer 消费 evidence records，产出 `DimensionDiagnosticSummary`。
5. fidelity gate 对 summary 做统一压顶和 warning 注入，确保 forced fallback 对照条件不会在总分层被打平。
6. renderer 直接输出结构化 artifact。

## 4. Data Structures

建议新增或扩展以下结构：

```python
@dataclass(frozen=True)
class EvaluationEvidenceRecord:
    dimension_id: str
    event_type: str
    owner_hint: str
    severity: str
    count: int
    sample_refs: list[str]
    detail: dict[str, Any]

@dataclass(frozen=True)
class DimensionDiagnosticSummary:
    dimension_id: str
    score: float
    base_score: float
    penalties: list[dict[str, Any]]
    positive_evidence: list[EvaluationEvidenceRecord]
    negative_evidence: list[EvaluationEvidenceRecord]
    warnings: list[str]
    gap_summary: str
    owner_hints: list[str]

@dataclass(frozen=True)
class BehavioralFidelitySnapshot:
    language_floor: float
    emotional_floor: float
    proactive_signal: float
    outbound_success_rate: float
    fallback_rate: float
    rejection_rate: float
```

同时扩展现有 report model，使 JSON 中新增 `dimension_diagnostics`、`fidelity_warnings`、`evidence_counters` 字段。

对于 SEC 相关 evidence，结构化 artifact 至少还应稳定输出：

1. `sec_fallback_events`
2. `sec_total_evaluations`
3. `sec_llm_successes`
4. 可由上述字段推导的 `sec_fallback_ratio`

## 5. Module Changes

1. `helios_evaluation/cli_brain_like_evaluation.py`
   - 新增 evidence 提取层。
   - 重写维度 scorer，使其先计算 base score，再叠加 penalties。
   - 扩展行为门控，纳入主动性、fallback、外发成功率，并确保高 fallback ratio 会在总分层形成稳定负向差异。
2. `helios_main.py` / `core/helios_state.py`
   - 若当前 state 缺少主动性、思考产出、执行状态或 SEC provenance 计数，则仅补充最小只读指标出口。
3. `helios_io/llm_debug.py`
   - 统一 SEC fallback、JSON parse failure 等计数命名，便于 harness 消费。
4. `tests/test_cli_brain_like_evaluation.py`
   - 增加负向归因、门控压顶和 JSON/Markdown 一致性测试。

## 6. Migration Plan

1. 第一阶段先保留现有 report 顶层字段，新增诊断字段，不破坏现有 artifact 消费者。
2. 第二阶段将旧 scorer 内部的 presence-based 逻辑替换为 evidence-based 逻辑。
3. 第三阶段补充 live harness 的 warning 输出与 fixture tests。
4. 默认 rollout 为开启新诊断字段和新扣分逻辑；如果某些证据暂时不可得，维度结果降级为 lower confidence，而不是回退到旧高分逻辑。
5. forced fallback 对照运行属于正式验证条件，不是临时调试路径；其语义必须由 runtime owner、evaluator owner 和 artifact owner 共同保持一致。

## 7. Failure Modes and Constraints

1. 如果某次运行缺少日志或 transcript 片段，evaluator 输出 `unknown evidence` warning，并保守降分。
2. 如果某一类 counter 在旧环境不存在，report 中必须明确标记 `not_available`，而不是填 0 假装没有失败。
3. 如果 Markdown 渲染失败，JSON artifact 仍必须完整落盘。
4. 本 requirement 不负责修复主动性本身；它只负责更真实地暴露主动性缺失。

## 8. Observability and Logging

1. evaluator 应输出每个维度的 `base_score`、`penalty_total`、`final_score`。
2. harness 应汇总 `fallback_rate`、`rejection_rate`、`outbound_success_rate`。
3. Markdown report 应新增“诊断归因”章节，列出 top negative factors 和 owner hints。
4. JSON report 应提供稳定字段，便于后续 requirement 比较不同版本前后差异。
5. 对 SEC 相关对照运行，artifact 应显式区分“runtime forced fallback”与“occasional parser/timeout fallback”，避免两者混成一个笼统计数后失去解释力。

## 9. Validation Strategy

1. 为 scorer 构造窄范围 fixture，覆盖高内部健康但低行为真实性的失真场景。
2. 为 report renderer 验证 JSON/Markdown 的关键指标一致性。
3. 使用已有 live harness 命令跑一次短时评估，确认 artifact 结构完整且不会因可选 channel 缺失崩溃。
4. 对 fallback 高频场景增加回归测试，确保 warning 和 penalty 同时出现。
5. 至少保留一组 5 分钟 paired artifact 作为验收样本，要求 forced fallback 一侧在 `sec_fallback_delta`、总分和至少一个对外行为维度上都与 normal SEC 一侧形成稳定负向差异。
