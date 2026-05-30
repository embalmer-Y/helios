# Requirement 19 - Architecture boundary and owner documentation

## 1. Background and Problem

Helios 当前已经形成较大的运行面：主循环、认知、记忆、调节、身份治理、I/O channel、evaluation 等模块彼此关联紧密，但文档层面对 owner、边界、协作流、禁止跨层调用和数据所有权的说明仍不完整。模块审查矩阵已经给出第一轮保留/调整/重构结论，但尚未收敛为可执行的边界文档。

缺少正式边界文档的直接后果是：需求拆分容易漂移，模块间会重新出现 shortcut 调用，评估、channel、memory、identity 等 concern 之间的 owner 关系难以复核，后续开发也缺少统一的图示与术语基线。

## 2. Goal

建立与当前代码结构对齐的中文架构边界文档体系，明确每个域的 owner、数据流、禁止越界调用、协作顺序和迁移约束，使 requirement、design、实现和评估都能引用同一套边界真相。

## 3. Functional Requirements

### 3.1 域边界定义

1. 文档体系 must 明确至少以下域的 owner 与职责：root runtime、core infrastructure、cognition、memory、identity/governance、helios I/O、regulation、evaluation。
2. 每个域 must 说明输入、输出、拥有的数据、允许依赖和禁止依赖。
3. 每个域 must 标注当前状态属于保留、调整接口、保留实现重定哲学或重构/重建。

### 3.2 协作流与调用约束

1. 文档 must 给出主要运行协作流，包括 stimulus ingress、thought continuation、thought-to-action、channel outbound、memory consolidation、evaluation sampling。
2. 文档 must 明确禁止的 shortcut，例如 channel 绕过 ops、evaluation 绕过 owner 直接取临时状态、identity 由 prompt 文本直接改写。
3. 主要协作流 should 以图示方式表达，便于 requirement 和实现共同引用。

### 3.3 文档对齐与索引

1. `docs/index.md`、requirements index 和模块审查矩阵 must 相互可追踪。
2. 新边界文档 must 与现有 `ARCHITECTURE_PHILOSOPHY`、`HIGH_LEVEL_DESIGN`、`IMPLEMENTATION_ROADMAP` 对齐，而不是另起一套术语。
3. 文档中 must 明确哪些内容是当前 runtime truth，哪些是待迁移目标。

## 4. Non-Functional Requirements

1. 文档 must 以中文为主，并使用稳定术语，避免同一概念反复换名。
2. 文档更新 should 与 requirement 变更同提交，避免边界说明落后于实现。
3. 图示与表格应保持可维护，避免只能人工猜测的叙述性大段落。
4. 边界文档不得依赖未实现的理想状态；若目标尚未落地，必须标明迁移态。

## 5. Code Behavior Constraints

1. 不得用 README 式概述替代正式 owner/boundary 文档。
2. 不得把“谁 currently 访问了谁”误写成“谁应该拥有谁”；边界文档必须表达目标 owner 关系。
3. 不得把 requirement/task 文档中的临时 TODO 混入永久性架构边界定义。
4. 文档中的边界约束若与实现冲突，必须记录冲突点，而不是静默忽略。

## 6. Impacted Modules

1. `docs/ARCHITECTURE_PHILOSOPHY.zh-CN.md`
2. `docs/HIGH_LEVEL_DESIGN.zh-CN.md`
3. `docs/IMPLEMENTATION_ROADMAP.zh-CN.md`
4. `docs/MODULE_REVIEW_MATRIX.zh-CN.md`
5. `docs/index.md`
6. `docs/requirements/index.md`

## 7. Acceptance Criteria

1. 至少形成一份面向 owner/boundary 的中文文档，覆盖主要域、协作流和禁止 shortcut。
2. 模块审查矩阵中的所有一级分组都有已确认结论或明确迁移状态说明。
3. requirements index 能引用新增边界文档，并说明其对 R17-R20 的支撑关系。
4. 文档审阅者可以从文档直接判断一个新改动是否越过 owner 边界，而不需要先通读源码。
