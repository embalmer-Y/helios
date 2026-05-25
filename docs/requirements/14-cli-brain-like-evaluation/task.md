# Requirement 14 - CLI Brain-Like Evaluation

## 1. Task Breakdown

### T14-1 建立 requirement package 与索引同步
1. 新增 `14-cli-brain-like-evaluation/requirement.md`。
2. 新增 `14-cli-brain-like-evaluation/design.md`。
3. 新增 `14-cli-brain-like-evaluation/task.md`。
4. 更新 `docs/requirements/index.md`，加入 R14 状态、依赖与实施顺序。

### T14-2 补齐评估观测面
1. 在 `helios_main.py` 中补充 consciousness 评估摘要导出。
2. 在 `helios_main.py` 中补充 neurochem 评估摘要导出。
3. 保持导出只读，不把评估流程逻辑塞进主 tick。
4. 为不可用子系统定义明确 unavailable 表达。

### T14-3 实现 evaluation data contracts 与 scoring owner
1. 新增 `helios_evaluation/` package。
2. 定义 scenario、prompt step、sample、dimension score、report contract。
3. 实现默认 10 分钟 mixed-mode CLI scenario。
4. 实现情感反应、语言自然度、子系统健康与总分 scoring logic。

### T14-4 实现 report output 与 log summary
1. 实现 log tail summary helper。
2. 实现 JSON report 输出。
3. 实现 Markdown report 输出。
4. 确保每个评分块都有 evidence 摘要。

### T14-5 实现 runner 路径
1. 提供至少一条 in-process evaluation harness 路径。
2. 该 runner 必须复用正式 CLI owner path，而不是直接调用 reply owner。
3. 预留后续真实 10 分钟 live runner 的入口脚本位置。
4. 为 Windows 长时运行保留 heartbeat 约束。

### T14-6 补齐 focused tests
1. 测试 scenario contract。
2. 测试评分逻辑与 report completeness。
3. 测试 `get_state()` 新增观测字段。
4. 测试 in-process harness 的最小运行语义。

## 2. Dependencies

1. 依赖 R08 的正式 stimulus ingress 与 provenance 语义。
2. 依赖 R09 的正式 thought-to-action / planner / executor 路径。
3. 依赖 R12 的 prompt / channel context contract 与 observability discipline。
4. 依赖 R13 的正式 terminal CLI channel owner。

## 3. Files and Modules

1. `docs/requirements/14-cli-brain-like-evaluation/requirement.md`
2. `docs/requirements/14-cli-brain-like-evaluation/design.md`
3. `docs/requirements/14-cli-brain-like-evaluation/task.md`
4. `docs/requirements/index.md`
5. `helios_main.py`
6. `helios_evaluation/__init__.py`
7. `helios_evaluation/cli_brain_like_evaluation.py`
8. `tests/test_cli_brain_like_evaluation.py`
9. `tests/manual/run_10min_cli_eval.py`

## 4. Implementation Order

1. T14-1
2. T14-2
3. T14-3
4. T14-4
5. T14-5
6. T14-6

## 5. Validation Plan

1. 文档 review 验证 R14 requirement/design/task 与 index 保持一致。
2. focused test 验证 scenario/report/scoring contract。
3. focused test 验证 `get_state()` 的 consciousness / neurochem export。
4. focused integration test 验证 in-process evaluation harness 使用正式 CLI owner path。
5. 后续 live validation 验证真实 10 分钟 CLI artifact。

## 6. Completion Criteria

1. 存在正式 R14 requirement package，且索引已同步。
2. `get_state()` 暴露评估所需 consciousness / neurochem 观测摘要。
3. 存在正式 evaluation package，拥有 scenario、scoring、report contract。
4. 默认 10 分钟 mixed-mode CLI evaluation scenario 已定义。
5. 评估报告能输出分块评分、总分与 evidence。
6. focused tests 能验证评估骨架与新增 observability。
7. 至少存在一条后续可执行的 runner 路径，用于真实 CLI 评估 closeout。