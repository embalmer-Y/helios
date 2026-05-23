# Helios Research Index

This directory now separates current project documentation from theoretical references.

## Active

Read these first when you need the current system definition.

- `research_home.html`: unified HTML landing page for active docs, architecture visuals, and reading order
- `ARCHITECTURE.zh-CN.md`: 当前项目整体架构说明（中文）
- `ARCHITECTURE.en.md`: Current project architecture overview (English)
- `DESIGN_PHILOSOPHY.zh-CN.md`: 新版详细设计说明与设计原则（中文）
- `DESIGN_PHILOSOPHY.en.md`: Detailed design and engineering principles (English)
- `IMPLEMENTATION_REFERENCE.zh-CN.md`: 模块/类/关键函数与理论、论文、测试之间的映射（中文）
- `IMPLEMENTATION_REFERENCE.en.md`: Implementation-to-theory and implementation-to-test mapping (English)
- `SOURCE_CATALOG.zh-CN.md`: 研究资料目录、引用条目与待收集清单（中文）
- `SOURCE_CATALOG.en.md`: Source catalog, citation entries, and collection backlog (English)
- `architecture_overview.html`: HTML 版整体架构图、tick 流程图与关键对象流
- `diagrams/`: standalone Mermaid diagram files extracted from the main architecture and design docs for easier reading
- `current_structure.md`: short-form structural reference after cleanup and migration

## Foundational Research

These files explain the scientific and conceptual basis behind Helios. They are not the source of truth for current package ownership or runtime wiring.

- `dmn_thinking_model.md`: DMN / replay / endogenous thinking
- `neurochem_model.md`: neurochemical modulation model
- `panksepp_helio_mapping.md`: affect-system mapping
- `fep_formalization.md`: formal free-energy framing
- `friston_panksepp_synthesis.md`: combined theoretical synthesis

## Reading Order

1. Open `research_home.html` for the consolidated navigation view.
2. Read `ARCHITECTURE.zh-CN.md` or `ARCHITECTURE.en.md`.
3. Read `DESIGN_PHILOSOPHY.zh-CN.md` or `DESIGN_PHILOSOPHY.en.md` for the detailed runtime design and principles.
4. Read `IMPLEMENTATION_REFERENCE.zh-CN.md` or `IMPLEMENTATION_REFERENCE.en.md` to trace modules back to research and tests.
5. Read `SOURCE_CATALOG.zh-CN.md` or `SOURCE_CATALOG.en.md` when you need source provenance, citations, or collection status.
6. Open `architecture_overview.html` when you need a visual map of the current architecture.
7. Use `current_structure.md` as the quick boundary sheet.
8. Consult foundational research files only when tracing why the architecture was designed this way.

## Interpretation Rule

If an older research note conflicts with the codebase, the codebase and the active architecture documents win.