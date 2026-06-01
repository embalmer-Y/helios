# Helios Documentation Index

This directory now uses a minimal canonical document set for the consciousness-first architecture direction.

The goal of this reduced set is to stop historical documents, archived requirements, and research collections from continuing to mislead implementation work or future AI-assisted development.

## Canonical Documents

The following files are the new direction-setting set and should be treated as the active reading path during the reset:

- `ARCHITECTURE_PHILOSOPHY.zh-CN.md`: 项目最高方向约束文档，定义 Helios 的类脑意识优先哲学
- `HIGH_LEVEL_DESIGN.zh-CN.md`: 顶层设计文档，定义主要 owner、运行流和跨层约束
- `ARCHITECTURE_BOUNDARIES.zh-CN.md`: owner / boundary 真相文档，定义域职责、允许依赖、禁止 shortcut 和关键协作流
- `IMPLEMENTATION_ROADMAP.zh-CN.md`: 总任务路标，定义实施阶段与批准门槛
- `MODULE_REVIEW_MATRIX.zh-CN.md`: 全项目模块审查矩阵，用于逐组确认保留/调整/重构
- `BRAIN_ARCHITECTURE_COMPARISON.zh-CN.md`: Helios 与人脑功能系统的谨慎映射、差距分析和文献 grounding
- `requirements/index.md`: 新 requirement 体系入口
- `requirements/requirement-authoring-standard.md`: requirement package 编写规范

## Reading Order

1. Read `ARCHITECTURE_PHILOSOPHY.zh-CN.md`.
2. Read `HIGH_LEVEL_DESIGN.zh-CN.md`.
3. Read `ARCHITECTURE_BOUNDARIES.zh-CN.md`.
4. Read `MODULE_REVIEW_MATRIX.zh-CN.md`.
5. Read `IMPLEMENTATION_ROADMAP.zh-CN.md`.
6. Read `BRAIN_ARCHITECTURE_COMPARISON.zh-CN.md` after the boundary documents.
7. Read `requirements/index.md`.
8. Use `requirements/requirement-authoring-standard.md` when authoring or reviewing requirement packages.

## Interpretation Rule

This minimal canonical set is the only active documentation surface under `docs/`.

If future documents are added, they must remain subordinate to this set and to the requirement packages indexed under `docs/requirements/`.

The two working-draft documents added in this phase, `ARCHITECTURE_BOUNDARIES.zh-CN.md` and `BRAIN_ARCHITECTURE_COMPARISON.zh-CN.md`, are part of that active surface and are intended to be cited by R17-R20 design and task work.