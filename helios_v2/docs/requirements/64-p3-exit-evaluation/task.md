# Requirement 64 - P3 Exit Evaluation: Task Breakdown

## 1. Title

R64 Task Plan - P3 退出评估

## 2. Task Breakdown

### T1 - 需求文档创建
- 创建 `docs/requirements/64-p3-exit-evaluation/` 目录。
- 创建 `requirement.md`（8 个标准章节）。
- 创建 `design.md`（10 个标准章节）。
- 创建 `task.md`（本文件，7 个标准章节）。
- **验证**：目录结构完整，三个文件存在。

### T2 - 自动化评估测试实现
- 创建 `helios_v2/tests/test_p3_exit_evaluation.py`。
- 实现 5 个测试函数：
  1. `test_p3_de_shim_coverage` — FG-1 覆盖率检查
  2. `test_p3_fg2_emotion_evolves` — FG-2.1 情感跨 tick 演化
  3. `test_p3_fg2_causal_chain_external` — FG-2.2 外部因果链
  4. `test_p3_fg2_causal_chain_internal` — FG-2.2 内部因果链
  5. `test_p3_exit_verdict` — 综合退出判定
- **验证**：`pytest helios_v2/tests/test_p3_exit_evaluation.py -v` 全绿。

### T3 - 全套件验证
- 运行 `pytest helios_v2/tests -q` 确保全套件保持全绿。
- **验证**：全套件 passed，无 regression。

### T4 - 文档同步
- `index.md`：添加 R64 行（depends on `09, 03, 04, 05, 06, 07, 08, 10`），maturity = `baseline_implementation`。
- `PROGRESS_FLOW.zh-CN.md` / `PROGRESS_FLOW.en.md`：更新"最近同步"行为 R64。
- `OWNER_GUIDE.zh-CN.md` / `OWNER_GUIDE.md`：P3 相关 owner 的"下一步"标注 P3 退出评估已完成。
- **验证**：文档内容与测试证据一致。

### T5 - Git 提交与推送
- 创建分支 `feat/R64-p3-exit-evaluation`。
- 提交所有变更。
- 推送到远端。
- **验证**：远端分支存在。

## 3. Dependencies

| Task | Depends On |
|------|-----------|
| T2 | T1 |
| T3 | T2 |
| T4 | T3 |
| T5 | T4 |

## 4. Files and Modules

| 文件 | 操作 |
|------|------|
| `helios_v2/docs/requirements/64-p3-exit-evaluation/requirement.md` | 新增 |
| `helios_v2/docs/requirements/64-p3-exit-evaluation/design.md` | 新增 |
| `helios_v2/docs/requirements/64-p3-exit-evaluation/task.md` | 新增 |
| `helios_v2/tests/test_p3_exit_evaluation.py` | 新增 |
| `helios_v2/docs/requirements/index.md` | 修改 |
| `helios_v2/docs/PROGRESS_FLOW.en.md` | 修改 |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` | 修改 |
| `helios_v2/docs/OWNER_GUIDE.md` | 修改 |
| `helios_v2/docs/OWNER_GUIDE.zh-CN.md` | 修改 |

## 5. Implementation Order

1. T1: 需求文档（已有）
2. T2: 评估测试实现
3. T3: 全套件验证
4. T4: 文档同步
5. T5: Git 提交推送

## 6. Validation Plan

1. **T2 验证**：`pytest helios_v2/tests/test_p3_exit_evaluation.py -v` — 5 个测试全绿。
2. **T3 验证**：`pytest helios_v2/tests -q` — 全套件 passed。
3. **T4 验证**：检查 index.md 包含 R64 行，PROGRESS_FLOW 最近同步包含 R64。

## 7. Completion Criteria

1. 5 个评估测试全绿。
2. 全套件无 regression。
3. `P3ExitVerdict` 产出 `passed == True`。
4. 不在 P3 范围的剩余 shim 被显式列出。
5. 所有文档同步更新。
6. 分支已推送到远端。
