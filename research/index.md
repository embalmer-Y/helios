# Helios Research Archive

This directory is now the foundational archive for Helios.

中文：当前系统文档已经迁入 `../docs/`。当你需要查看最新架构、运行时设计、实现映射或 HTML 导航入口时，请先读 `../docs/`。

English: The current system-definition docs now live under `../docs/`. When you need the latest architecture, runtime design, implementation mapping, or HTML entry points, start there.

## Start With Active Docs

- `../docs/docs_home.html`: bilingual documentation portal
- `../docs/index.md`: active documentation index
- `../docs/ARCHITECTURE.zh-CN.md` / `../docs/ARCHITECTURE.en.md`: current architecture overviews
- `../docs/DESIGN_PHILOSOPHY.zh-CN.md` / `../docs/DESIGN_PHILOSOPHY.en.md`: current detailed design docs
- `../docs/IMPLEMENTATION_REFERENCE.zh-CN.md` / `../docs/IMPLEMENTATION_REFERENCE.en.md`: implementation mapping
- `../docs/SOURCE_CATALOG.zh-CN.md` / `../docs/SOURCE_CATALOG.en.md`: source traceability and collection backlog
- `../docs/architecture_overview.html`: visual architecture page
- `../docs/current_structure.md`: quick boundary sheet

## Foundational Archive Contents

These files remain here because they explain the theory, historical synthesis, and research basis behind Helios rather than the current package ownership map.

- `dmn_thinking_model.md`: DMN / replay / endogenous thinking
- `preconscious_path_research.md`: bounded preconscious candidate path and architectural mapping
- `personality_influence_research.md`: trait-prior research and projection-layer mapping
- `neurochem_model.md`: neurochemical modulation model
- `panksepp_helio_mapping.md`: affect-system mapping
- `fep_formalization.md`: formal free-energy framing
- `friston_panksepp_synthesis.md`: combined theoretical synthesis
- `anthropic_emotion_concepts.txt`, `anthropic_emotion_paper.txt`, `anthropic_emotion_paper.pdf`: source materials preserved for traceability

## Interpretation Rule

If an archived research note conflicts with the codebase, prefer the codebase first, the active docs under `../docs/` second, and this archive third.# Helios Research Index

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
- `preconscious_path_research.md`: bounded preconscious candidate path and architectural mapping
- `personality_influence_research.md`: trait-prior research and projection-layer mapping
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