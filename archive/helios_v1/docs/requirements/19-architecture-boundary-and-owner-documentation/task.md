# Requirement 19 - Architecture boundary and owner documentation

## 1. Task Breakdown

## 1.1 Progress Snapshot

1. 已完成：`docs/ARCHITECTURE_BOUNDARIES.zh-CN.md` 已落地为 active owner/boundary working draft，覆盖主要域 owner、允许依赖、禁止 shortcut 与关键协作流。
2. 已完成：`docs/MODULE_REVIEW_MATRIX.zh-CN.md` 已补齐 `11.4` 到 `11.8` 的一级分组确认结果，形成模块审查闭环。
3. 已完成：`docs/index.md` 已将边界文档纳入 canonical documents 与 reading order。
4. 已完成：`docs/requirements/index.md` 已显式写明边界文档对 R17-R20 的支撑关系，requirements index 与 active docs truth 的引用链已不再只靠隐含语义连接。

### Task 1 - 补全模块审查矩阵确认结果

1. 将 memory、identity、helios I/O、regulation、tests/scripts/data 的确认结果补入矩阵。
2. 明确每个一级分组的确认日期或当前状态。
3. 标注已知冲突与迁移态。
4. 首个验证：人工检查矩阵是否覆盖全部一级分组。
5. 当前状态：已完成。

### Task 2 - 新增 owner/boundary 主文档

1. 编写中文主文档，定义域 owner、输入输出、拥有数据和禁止依赖。
2. 为关键协作流补充图示或时序说明。
3. 明确当前态与目标态边界。
4. 首个验证：检查文档结构、术语和跨文档链接。
5. 当前状态：已完成，当前文档状态为 working draft，后续只继续收敛迁移态描述与引用链。

### Task 3 - 对齐 requirements 与总文档入口

1. 更新 `docs/requirements/index.md` 中的 R19 信息与依赖关系。
2. 更新 `docs/index.md`，把新边界文档挂入总入口。
3. 确保后续 requirement 可以直接引用该边界文档。
4. 首个验证：检查索引链接和引用链闭环。
5. 当前状态：已完成。`docs/index.md` 与 `docs/requirements/index.md` 均已同步到当前边界文档事实。

## 2. Dependencies

1. 依赖当前模块审查矩阵已有的 Root Runtime 和 Cognition 确认结果。
2. 依赖已存在的哲学、HLD、roadmap 文档。
3. 与 R17、R18、R20 强相关，因为这些 requirement 都需要稳定 owner 术语和边界引用。

## 3. Files and Modules

1. `docs/MODULE_REVIEW_MATRIX.zh-CN.md`
2. `docs/ARCHITECTURE_PHILOSOPHY.zh-CN.md`
3. `docs/HIGH_LEVEL_DESIGN.zh-CN.md`
4. `docs/IMPLEMENTATION_ROADMAP.zh-CN.md`
5. `docs/index.md`
6. `docs/requirements/index.md`

## 4. Implementation Order

1. 先补矩阵确认结果。
2. 再新增边界主文档。
3. 最后同步 requirements 和 docs 总入口。

## 4.1 Next Slice

1. 视 R18/R20 后续推进情况，把具体 requirement package 对边界文档的引用方式继续统一到同一术语面。
2. 若 `ARCHITECTURE_BOUNDARIES.zh-CN.md` 中的迁移态条目发生变化，同步复核 requirements index 与矩阵中的边界口径是否仍一致。

## 5. Validation Plan

1. 检查 `docs/requirements/index.md` 和 `docs/index.md` 链接完整性。
2. 人工 spot check 关键模块 owner 与文档描述是否一致。
3. 确认一级分组都有 confirmed 或待迁移说明。

## 6. Completion Criteria

1. 模块审查矩阵完成一级分组确认闭环。
2. 新增 owner/boundary 主文档可被后续 requirement 直接引用。
3. requirements index 和 docs 总入口已纳入该文档。
4. 审阅者能够依据文档判断主要越界问题。
