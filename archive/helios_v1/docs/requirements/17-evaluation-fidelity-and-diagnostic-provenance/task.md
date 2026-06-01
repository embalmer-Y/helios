# Requirement 17 - Evaluation fidelity and diagnostic provenance

## 1. Task Breakdown

## 1.1 Progress Snapshot

1. 已完成：`EvaluationReport` 已输出 `evidence_counters`、`visible_behavior_chain`、`dimension_diagnostics`、`fidelity_warnings` 与 `long_range_diagnostics`，并保持 JSON/Markdown 同构渲染。
2. 已完成：6 个维度 scorer 已切到 base score + penalty 模型，SEC fallback、planner reject、execution consistency failure、thought-to-visible gap 已进入扣分或总分 gate。
3. 已完成：`CliBrainLikeEvaluationHarness.compare_reports()`、`load_report()` 与 `write_comparison_report()` 已落地，手工 runner 已支持 `--compare-left/--compare-right` 生成对照 artifact。
4. 已完成：focused regression 已覆盖维度诊断、score penalty、comparison artifact、long-range diagnostics，最近一次命令 `pytest tests/test_cli_brain_like_evaluation.py -q` 为 16 passed。
5. 已完成：短时 live smoke 已落地 artifact，确认真实输出中存在 `long_range_diagnostics` 字段。
6. 已完成：comparison artifact 已纳入 `long_range_diagnostics` 状态差异与数值差异，并会把 long-range root cause 写入 comparison summary。
7. 已完成：fresh paired runner 已能产出同 scenario 的 paired artifacts；最新短时 smoke 显示 SEC normal side 不再出现此前那种持续性空 JSON fallback，`sec_fallback_delta=7`，总分差重新拉开为 `-0.018`。
8. 已完成：`helios_io/llm_sec_evaluator.py` 已完成 runtime-oriented hardening，改为专用短 prompt、`reasoning_effort="low"`、更高 completion budget，并保留 fenced/partial JSON recovery；同时 `LLMSECEvaluator(api_key="")` 已修正为显式 forced-disable，不再回退复用环境 key。focused regression `pytest tests/test_llm_sec_evaluator.py -q` 为 22 passed。
9. 已完成：fresh paired compare 的 forced-fallback 语义、runtime provenance 计数与 scorer/gate 口径已修正。R17 evaluator 现优先消费 runtime `sec_evaluator` 计数而不是纯日志正则，最新 5 分钟 paired artifact `cli_brain_like_eval_sec_compare_5min_after_scoring_fix*` 显示 `sec_fallback_delta=37`，总分从 `0.55` 降到 `0.46`，且情感/语言维度均出现稳定负向差异，不再与正常结构化 SEC 条件打平。

### Task 1 - 建立诊断证据模型

1. 在评估模块中引入维度证据与诊断汇总数据结构。
2. 将现有 transcript、state、log summary 映射为统一 evidence records。
3. 完成定义：当证据缺失时返回 `unknown`，不再默认通过。
4. 首个验证：为 evidence extraction 增加窄范围单测。
5. 当前状态：已完成。

### Task 2 - 重写维度评分与 fidelity gate

1. 将 6 个维度 scorer 改为 base score + penalty 模型。
2. 让 SEC fallback、policy rejection、planner no-op、outbound failure 成为负向因素。
3. 扩展行为门控，把主动性和外发成功率纳入上限约束。
4. 把 `thought produced -> action proposed -> planner accepted -> visible reply emitted / why not emitted` 做成可渲染的主诊断链，而不是仅输出离散 counters。
5. 首个验证：运行 `pytest tests/test_cli_brain_like_evaluation.py -q`。
6. 当前状态：已完成，后续只保留与 fresh paired runs 对齐的微调空间。

### Task 3 - 扩展 artifact 与报告渲染

1. 为 JSON report 新增 `dimension_diagnostics`、`fidelity_warnings`、`evidence_counters`。
2. 为 Markdown report 增加“维度归因”和“下一跳检查模块”区块。
3. 保持旧顶层字段兼容，避免破坏现有人工审阅流程。
4. 首个验证：对同一 fixture 同时断言 JSON 和 Markdown 核心内容一致。
5. 当前状态：已完成。基础字段扩展、long-range diagnostics 与 comparison summary 已全部消费最新差异，并已纳入 paired artifact root-cause summary。

### Task 4 - live harness 接入与回归

1. 让 live harness 输出新的诊断字段。
2. 使用短时 live 运行验证 artifact 可落盘且字段完整。
3. 固化一个失真案例，保证未来不会回到 presence-based 高分。
4. 增加 SEC 正常结构化输出条件与 SEC fallback 高频条件的对照评估步骤，保留两组可比较 artifact。
5. 首个验证：运行手工 harness 命令并检查生成 artifact。
6. 当前状态：已完成。短时 smoke 已验证 forced-fallback 语义与 provenance 口径，5 分钟 paired artifact `cli_brain_like_eval_sec_compare_5min_after_scoring_fix*` 已验证 normal side 与 fallback side 在总分和对外行为维度上都重新出现稳定可解释差异。

## 2. Dependencies

1. 依赖 R14 已有 CLI evaluation harness 与 report 输出基础。
2. 依赖 `helios.get_state()` 暴露必要的最小状态快照。
3. 依赖现有 log summary 或 debug counters 可被稳定读取。

## 3. Files and Modules

1. `helios_evaluation/cli_brain_like_evaluation.py`
2. `tests/test_cli_brain_like_evaluation.py`
3. `tests/manual/run_10min_cli_eval.py`
4. `helios_main.py`
5. `core/helios_state.py`
6. `helios_io/llm_debug.py`

## 4. Implementation Order

1. 先做 evidence data model 和 extraction。
2. 再做 scorer 与 fidelity gate 重写。
3. 然后扩展 report renderer。
4. 最后跑 live harness 并补回归测试。

## 4.1 Next Slice

1. 若后续更长时段 paired run 仍出现 occasional SEC truncation，则继续细化 provider 参数或引入 SEC 专用模型开关，避免评估侧再次被 reasoning budget 污染。
2. 在后续 R18/R19 推进时，把 R17 的 forced-fallback artifact 作为固定回归样本，防止主观主动性或边界文档改动再次稀释评分真实性。
3. 若后续 scorer 再调整，优先复核 forced-fallback 对总分、情感反应类人度和语言表达自然度的方向性是否仍稳定保持。

## 5. Validation Plan

1. `pytest tests/test_cli_brain_like_evaluation.py -q`
2. 若 state/export 有改动，再补相关窄范围测试。
3. 使用 `python tests/manual/run_10min_cli_eval.py --duration 300 --sample-interval 15 --report-prefix cli_brain_like_eval_5min_diag` 做人工验证。
4. 对生成的 JSON/Markdown artifact 进行字段完整性检查。
5. 对同一 scenario 保留至少一组 SEC 正常 vs fallback 高频的 artifact 对照结果。

## 6. Completion Criteria

1. 评分维度均能输出可追踪的 evidence 和 owner hints。
2. 高频 fallback 或低外发成功率场景会稳定拉低相关维度分数。
3. JSON 与 Markdown report 均输出 fidelity warning 和维度归因。
4. 存在自动化测试覆盖失真压制与 artifact 一致性。
5. report 能直接回答“为什么 thought 没有变成可见输出”。
