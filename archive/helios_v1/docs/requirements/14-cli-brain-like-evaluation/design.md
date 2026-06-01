# Requirement 14 - CLI Brain-Like Evaluation

## 1. Design Overview

本设计把“10 分钟真实 CLI 类脑评估”提升为正式 evaluation owner concern。目标不是新造一条交互链，而是在复用现有 CLI/channel/tick/action 路径的前提下，定义统一的评估场景、证据采样、评分逻辑和报告输出，使后续人工分析与回归比较都有稳定的数据边界。

## 2. Current State and Gap

当前 gap：

1. 已存在 `tests/manual/run_30min_live_eval.py` 这类可复用模板，但没有正式 requirement 和独立评估 owner。
2. `helios_main.py` 的 `get_state()` 已暴露 memory、thought、routing、preconscious 等信息，但 neurochem 与 consciousness 细节不足以直接支撑评分。
3. 仓库中没有正式的 `EvaluationScenario`、`EvaluationReport` 或评分块 owner。
4. CLI 交互和日志观察仍偏手工，缺少统一 artifact 结构和报告格式。
5. mixed-mode 评估的人机协同边界尚未 formalize。

## 3. Target Architecture

目标结构：

1. 新增 `helios_evaluation/` 作为 CLI 类脑评估的正式 owner package。
2. 该 package 第一版至少包含：
   - scenario/data contract owner
   - scoring/report owner
   - in-process evaluation harness
3. 默认评估数据流为：
   - scenario prompt blocks
   - CLI owner path (programmatic submit 或 live CLI 输入)
   - Helios tick processing
   - periodic state sampling + history capture + log tail summary
   - dimension scoring
   - JSON/Markdown report output
4. `helios_main.py` 只负责评估所需 observability export，不拥有评估流程 orchestration。
5. live 10 分钟 runner 与 in-process harness 共享同一套 scenario 和 report contract，避免双重评分标准。

## 4. Data Structures

### 4.1 EvaluationPromptStep

```text
step_id
title
prompt
purpose
expected_signals
mode
``` 

### 4.2 EvaluationScenario

```text
scenario_id
title
duration_seconds
sample_interval_seconds
interaction_mode
prompt_steps
``` 

### 4.3 EvaluationStateSample

```text
timestamp
tick
state
``` 

### 4.4 EvaluationDimensionScore

```text
name
score_0_to_1
evidence
notes
``` 

### 4.5 EvaluationReport

```text
scenario_id
window
log_summary
transcript_excerpt
dimension_scores
subsystem_scores
total_score_0_to_1
analysis_notes
``` 

## 5. Module Changes

1. `helios_evaluation/cli_brain_like_evaluation.py`
   - 新增评估 owner。
   - 定义 scenario、sample、score、report 的正式数据契约。
   - 提供默认 10 分钟 mixed-mode CLI scenario。
   - 提供日志摘要、评分逻辑、JSON/Markdown 报告输出。
2. `helios_evaluation/__init__.py`
   - 暴露正式 public API。
3. `helios_main.py`
   - 扩充 `get_state()` 所需的 consciousness / neurochem observability export。
   - 不新增评估流程 owner，只提供结构化可观测面。
4. `tests/manual/run_10min_cli_eval.py`
   - 提供后续真实 10 分钟 runner 路径。
   - 第一版可先做 in-process 或半自动 runner，后续再演进为更强 live harness。
5. `tests/test_cli_brain_like_evaluation.py`
   - 增加评估 contract、score 结果和 observability export 的 focused coverage。

## 6. Migration Plan

1. 先创建 `R14` requirement/design/task 与 index entry，锁定 owner 与 scoring 边界。
2. 再扩充 `get_state()` 的评估观测面，避免后续 report 完全依赖文本日志推断。
3. 再新增评估 package 的 scenario + report + scoring 骨架。
4. 再补 in-process runner 和 focused tests。
5. 最后再补真实 10 分钟 live runner 与 closeout evidence。

默认 rollout：

1. 评估模块 default-off，不改变正常 Helios runtime。
2. observability export default-on，但保持只读和低侵入。
3. 第一版先完成可复跑的 structured evaluation scaffold，再追加更重的 live orchestration。

## 7. Failure Modes and Constraints

1. 若当前运行环境没有某个子系统（例如 `HAS_PHI=False` 或 `HAS_NEUROCHEM=False`），报告必须标记 unavailable。
2. 若 transcript 或 assistant reply 缺失，语言自然度必须显式降级评分，而不是给正常分。
3. 若日志路径不存在或不可读，log summary 必须回退为空摘要并保留错误说明。
4. 若 live runner 在 Windows 终端中长时间无输出，必须通过 heartbeat 或等价机制避免采集丢失。
5. mixed-mode 第一版不强制自动驱动所有人工交互；人工执行说明可以作为 scenario 的一部分存在。

## 8. Observability and Logging

必须记录或导出：

1. evaluation scenario id、interaction mode、duration 和 sample count。
2. consciousness 观测摘要：`phi`、label、source validity、history tail。
3. neurochem 观测摘要：raw neurochem scalar 与 gate summary。
4. routing / execution consistency summary。
5. log summary：error、fallback、outbound success/failure 等聚合结果。
6. dimension score evidence 与总分输出结果。
7. closeout-oriented bridge evidence fields：`action_explicit_samples`、`implicit_action_proposal_samples`、`equivalent_bridge_evidence_samples` 与对应 `r09_closeout.closeout_status`，用于区分“显式 action、implicit 但有 owner evidence、纯缺证据”三类 artifact。

## 9. Validation Strategy

1. 单元测试验证默认 10 分钟 scenario 的结构与提示块数量。
2. 单元测试验证 evaluator 能从 state samples、transcript 和 log lines 生成结构化 report。
3. 单元测试验证 JSON/Markdown report output 包含必须的分块评分和证据字段。
4. focused runtime test 验证 `get_state()` 暴露 consciousness / neurochem 评估观测面。
5. focused integration test 验证 in-process harness 能通过正式 CLI owner path 注入评估 prompt 并产出 report。
6. 后续 manual/live validation 验证真实 10 分钟 CLI session 的 artifact 与评分结果。
7. 当 evaluation artifact 被用于 R09 closeout 时，必须能把 `implicit_proposal_only` 与 `equivalent_bridge_evidence_observed` 区分开，避免把 heuristic thought-origin externalization 误判为 bridge evidence 缺失。