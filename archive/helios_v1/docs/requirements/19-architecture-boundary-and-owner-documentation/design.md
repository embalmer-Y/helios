# Requirement 19 - Architecture boundary and owner documentation

## 1. Design Overview

本设计不引入新的 runtime owner，而是把当前代码结构和目标迁移边界收敛为一套正式文档面。核心产物包括：域边界总览文档、模块审查矩阵确认结果补全、关键协作流图和 requirements index 对齐更新。文档 owner 以 `docs/` 为主，矩阵继续作为模块级审查源，新的边界文档负责给出跨域协作与禁止 shortcut。

## 2. Current State and Gap

当前文档缺口主要有 3 类：

1. 已有哲学/HLD/roadmap 更多描述方向，缺少域 owner 级边界真相。
2. 模块审查矩阵只完成了部分确认，未形成完整已确认结果。
3. requirement packages 与总架构文档之间的引用链还不够稳定，后续实现容易脱锚。

基于 2026-05-28 之后的最新文档状态，上述缺口已有部分收敛：

1. `docs/ARCHITECTURE_BOUNDARIES.zh-CN.md` 已作为 active owner/boundary working draft 落地。
2. `docs/MODULE_REVIEW_MATRIX.zh-CN.md` 已补齐 `11.4` 到 `11.8` 的一级分组确认结果。
3. 当前剩余主缺口已收敛为 requirements index 与后续 requirement package 对该边界文档的稳定引用链仍需正式化。

## 3. Target Architecture

目标文档结构建议如下：

1. 在 `docs/` 下新增一份中文主文档，专注说明 owner、边界、禁止依赖和协作流。
2. `MODULE_REVIEW_MATRIX.zh-CN.md` 继续维护模块级审查结论，并补全各一级分组的已确认状态。
3. `requirements/index.md` 负责 requirement 编号、依赖、状态和与边界文档的映射。
4. 现有 `ARCHITECTURE_PHILOSOPHY` / `HIGH_LEVEL_DESIGN` / `IMPLEMENTATION_ROADMAP` 保留其定位，但通过链接和术语统一与新边界文档对齐。

协作图建议至少覆盖：

1. stimulus ingress -> cognition -> planning -> channel ops
2. proactive drive -> thought continuation -> plan selection -> outbound or internal consolidation
3. memory retrieval/consolidation 与 identity governance 的关系
4. evaluation sampling 对 runtime owner 的只读观察路径

## 4. Data Structures

本 requirement 以文档结构为主，不引入生产代码数据结构，但要求文档中稳定表达以下概念表：

1. 域 owner 表
2. 数据拥有权表
3. 允许依赖矩阵
4. 禁止 shortcut 清单
5. 当前态 / 目标态 / 迁移态对照表

## 5. Module Changes

1. `docs/MODULE_REVIEW_MATRIX.zh-CN.md`
   - 已补全 `11.4` 到 `11.8` 已确认结果；后续只维护迁移态与冲突点。
2. 新增边界主文档
   - `docs/ARCHITECTURE_BOUNDARIES.zh-CN.md` 已落地，描述 owner、域职责、协作流、禁止 shortcut。
3. `docs/requirements/index.md`
   - 增加 R19 及其对 R17-R20 的边界支撑说明，并把边界文档作为 requirement 引用基线。
4. `docs/index.md`
   - 已将边界文档纳入总入口；后续只维护 active reading path 的表述一致性。

## 6. Migration Plan

1. 第一阶段已完成：补齐矩阵一级分组确认结果，并固定 requirement 编号和依赖。
2. 第二阶段已完成：新增 owner/boundary 主文档并沉淀关键协作流图。
3. 第三阶段进行中：把 requirements index 与后续 requirement package 的引用链统一收敛到边界文档。
4. 默认 rollout 为文档即刻生效；若实现尚未完全符合，需标记为迁移态。

## 7. Failure Modes and Constraints

1. 若某个模块当前实现与目标边界明显冲突，文档必须记录冲突，不得粉饰为已完成。
2. 若某个域仍未完成源码审查，必须标记 `待确认`，不得凭印象补完。
3. 图示必须服务于实现，不得为了美观引入与代码不一致的理想化路径。
4. 本 requirement 不要求一次性重写所有旧文档，但要求新边界真相可被后续 requirement 直接引用。

## 8. Observability and Logging

1. 文档应明确哪些运行指标属于哪个 owner，以便后续观测和评估。
2. 对每个关键协作流，文档应标明可观察状态或日志出口。
3. 对已知冲突点应建立 issue-style 记录，便于后续 requirement 跟踪。

## 9. Validation Strategy

1. 验证新增文档与矩阵、requirements index 之间的链接完整性。
2. 逐项检查一级分组是否都有 confirmed 或待迁移说明。
3. 通过实际代码 spot check，确认文档所写 owner 与源码方向一致。
4. 让后续 requirement 在 design 中引用该文档，验证其可操作性。
