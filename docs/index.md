# Helios Documentation Index

This directory is now the canonical home for Helios active documentation.

Read the files here when you need the current system definition, runtime wiring, implementation mapping, or the primary bilingual documentation entry points. Use `../research/` only for foundational theory and archived background notes.

## Active Documentation

- `docs_home.html`: unified bilingual HTML landing page for active docs, visuals, and reading order
- `ARCHITECTURE.zh-CN.md`: 当前项目整体架构说明（中文）
- `ARCHITECTURE.en.md`: Current project architecture overview (English)
- `DESIGN_PHILOSOPHY.zh-CN.md`: 当前详细设计说明与设计原则（中文）
- `DESIGN_PHILOSOPHY.en.md`: Current detailed design and engineering principles (English)
- `IMPLEMENTATION_REFERENCE.zh-CN.md`: 模块/类/关键函数与理论、论文、测试之间的映射（中文）
- `IMPLEMENTATION_REFERENCE.en.md`: Implementation-to-theory and implementation-to-test mapping (English)
- `SOURCE_CATALOG.zh-CN.md`: 研究资料目录、引用条目与待收集清单（中文）
- `SOURCE_CATALOG.en.md`: Source catalog, citation entries, and collection backlog (English)
- `architecture_overview.html`: HTML 版整体架构图、tick 流程图与关键对象流
- `diagrams/`: standalone Mermaid diagram files extracted from the active architecture and design docs
- `current_structure.md`: short-form structural reference after cleanup and migration

## Relationship To `research/`

The `../research/` directory now acts as the foundational archive. It keeps theory notes, historical synthesis, and source materials that explain why Helios was designed this way, but it no longer defines current package ownership or runtime structure.

Start there only when you need conceptual background such as DMN, neurochemistry, Panksepp mapping, free-energy framing, or the preconscious and personality research notes.

## Reading Order

1. Open `docs_home.html` for the consolidated bilingual navigation view.
2. Read `ARCHITECTURE.zh-CN.md` or `ARCHITECTURE.en.md`.
3. Read `DESIGN_PHILOSOPHY.zh-CN.md` or `DESIGN_PHILOSOPHY.en.md` for the detailed runtime design and principles.
4. Read `IMPLEMENTATION_REFERENCE.zh-CN.md` or `IMPLEMENTATION_REFERENCE.en.md` to trace modules back to research and tests.
5. Read `SOURCE_CATALOG.zh-CN.md` or `SOURCE_CATALOG.en.md` when you need source provenance, citations, or collection status.
6. Open `architecture_overview.html` when you need a visual map of the current architecture.
7. Use `current_structure.md` as the quick boundary sheet.
8. Consult `../research/index.md` only when tracing the theoretical basis behind the active design.

## Interpretation Rule

If an older research note conflicts with the codebase, the codebase wins first, the active docs in this directory win second, and the foundational archive under `../research/` is background only.