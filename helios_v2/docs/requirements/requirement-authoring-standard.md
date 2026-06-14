# Requirement Authoring Standard

## 1. Purpose
This document defines the mandatory rules for authoring requirement packages under `docs/requirements` so the resulting requirements are architecture-first, implementable, testable, and safe for staged migration.

## 2. Scope
This standard applies to all requirement packages created or updated under `docs/requirements`, including:

1. New numbered requirement folders.
2. New or updated `requirement.md` files.
3. New or updated `design.md` files.
4. New or updated `task.md` files.
5. Updates to the requirements index.

This standard also governs maturity assessment for requirement tracking. When an index tracks implementation maturity, the maturity value must be evaluated and updated under the rules in this document.

## 3. Directory and Naming Rules

### 3.1 Folder naming
Each requirement must be created as a dedicated folder under `docs/requirements` using the following pattern:

`NN-short-name`

Rules:

1. `NN` is a two-digit incremental number, starting from `01`.
2. `short-name` is concise, lowercase, with words joined by hyphen.
3. Use only letters, numbers, and hyphen.
4. Keep `short-name` within 3 to 6 words when practical.

Examples:

1. `06-memory-retrieval-ranking`
2. `07-thought-to-action-bridge`

### 3.2 File naming
Each requirement folder must contain:

1. `requirement.md`
2. `design.md`
3. `task.md`

Legacy packages may be normalized in follow-up changes, but any actively maintained package must contain all three files.

## 4. Mandatory Structure by File Type

### 4.1 requirement.md
Every `requirement.md` must include all sections below and preserve the order.

1. Title
2. Background and Problem
3. Goal
4. Functional Requirements
5. Non-Functional Requirements
6. Code Behavior Constraints
7. Impacted Modules
8. Acceptance Criteria

### 4.2 design.md
Every `design.md` must include all sections below and preserve the order.

1. Title
2. Design Overview
3. Current State and Gap
4. Target Architecture
5. Data Structures
6. Module Changes
7. Migration Plan
8. Failure Modes and Constraints
9. Observability and Logging
10. Validation Strategy

### 4.3 task.md
Every `task.md` must include all sections below and preserve the order.

1. Title
2. Task Breakdown
3. Dependencies
4. Files and Modules
5. Implementation Order
6. Validation Plan
7. Completion Criteria

## 5. Writing Rules by File Type

### 5.1 Title
1. Use format: `Requirement NN - Short requirement name`.
2. The title must represent the architectural intent, not just a symptom.

### 5.2 Background and Problem
1. Describe the current runtime behavior and observable symptoms.
2. State why the current behavior is insufficient.
3. Avoid vague wording such as "improve quality" without concrete failure evidence.

### 5.3 Goal
1. Must be one concise paragraph.
2. Must define the target runtime behavior, not only implementation work.

### 5.4 Functional Requirements
1. Break down into numbered subsections.
2. Use normative language:
   - `must` for mandatory behavior
   - `should` for recommended behavior
   - `may` for optional behavior
3. Each key statement must describe observable runtime behavior.
4. If a new runtime concept is introduced, it must be first-class in the architecture, not just metadata or logging text.

### 5.5 Non-Functional Requirements
At minimum cover applicable dimensions:

1. Performance.
2. Reliability and fault tolerance.
3. Observability and logging.
4. Compatibility and migration constraints.

### 5.6 Code Behavior Constraints
1. State explicit forbidden patterns where needed.
2. Define module boundary rules and owning abstractions.
3. Include failure-mode constraints, not only happy-path behavior.

### 5.7 Impacted Modules
1. List concrete file-level modules likely affected.
2. Include new owning abstractions when the requirement introduces a first-class concept.
3. Keep the list actionable for implementation planning.

### 5.8 Acceptance Criteria
1. Must be objectively verifiable.
2. Must include runtime behavior checks and test expectations.
3. Must avoid purely subjective criteria such as "feels better".
4. Must avoid brittle string-only acceptance unless literal string behavior is the product goal.
5. When data ownership or routing correctness is the goal, acceptance must validate source provenance rather than only prompt substrings.

### 5.9 design.md rules
1. Design must describe implementation shape, not repeat the requirement statement.
2. Design must define target runtime data flow, module boundaries, and state transitions.
3. Design must include explicit data structures when the change affects inputs, outputs, traces, persisted records, or ownership contracts.
4. Design must identify the owning abstraction for every new runtime concept.
5. Design must explain how the current implementation migrates to the target state without a full rewrite.
6. Design must state failure modes and fallback behavior for missing dependencies, unavailable capabilities, or partial rollout.
7. Design must make default-on vs default-off rollout explicit for newly introduced behavior.
8. Design must include a validation strategy that can be translated into focused tests.

### 5.10 task.md rules
1. Task documents must break the design into ordered implementation units that can be completed and verified independently.
2. Each task must state its dependency, touched modules, completion definition, and validation step.
3. Tasks must be implementation-oriented and architecture-aware; they must not restate the background problem in long form.
4. Task order must reflect dependency order and migration order.
5. Each task must point to a concrete code or test surface where the work will land.
6. Task documents must identify the first narrow validation command or check for each phase when practical.
7. If a feature has independently configurable sinks or outputs, tasks must model them independently instead of through one umbrella toggle.

### 5.11 Requirement maturity assessment rules
Requirement indexes that track implementation maturity must use explicit, evidence-based maturity labels rather than informal comments.

Mandatory rules:

1. Maturity is implementation-facing, not aspiration-facing. It must reflect shipped code and validation evidence, not planned architecture quality.
2. Maturity must be reassessed whenever a change set materially alters owner behavior, runtime integration, validation coverage, or implementation depth.
3. Maturity judgments must be made against the requirement's owner boundary. Missing downstream work in later requirements must not downgrade an already-implemented owner unless that later work is part of the same requirement's stated scope.
4. Documentation-only authoring does not count as implementation progress.
5. A requirement must not be marked above `pure_skeleton` unless there is executable code implementing owner behavior plus focused validation.
6. A requirement must not be marked `relatively_complete` if the owner is still mostly pass-through wiring, placeholder policy, or shape-only validation.
7. If evidence is mixed, the lower maturity must be used until focused validation demonstrates the higher level.

Required maturity labels and standards:

1. `not_started`
    - Requirement/design/task docs may exist, but no meaningful owner implementation has landed.
    - Allowed signals:
       - docs only
       - unimplemented package references
       - no runtime or test surface for the owner
    - Disallowed signals:
       - claiming progress because filenames or empty package shells exist

2. `pure_skeleton`
    - The owner package, contracts, or runtime wiring shell exists, but behavior is still mainly structural.
    - Typical evidence:
       - interfaces and dataclasses exist
       - owner methods mostly delegate without confirmed first-version policy
       - runtime stage shell exists without meaningful owner behavior
       - tests validate only construction, shapes, or placeholder wiring
    - This label is appropriate when the code proves the architecture boundary but does not yet provide a narrow, usable owner behavior.

3. `baseline_implementation`
    - The owner executes a real first-version behavior inside its scoped boundary.
    - Required evidence:
       - concrete owner behavior, not only contracts
       - fail-fast validation on core inputs or outputs
       - focused tests covering the owner behavior
       - if applicable, at least one adjacent integration path showing the owner can participate in runtime flow
    - Typical limitations still allowed:
       - injected or intentionally shallow first-version policy
       - reduced semantics compared with the final requirement vision
       - partial surrounding ecosystem still missing in later requirements

4. `relatively_complete`
    - The owner has a substantial first-version implementation and is no longer best described as a thin baseline.
    - Required evidence:
       - concrete owner behavior covering most of the requirement's stated scope
       - runtime integration where the requirement expects it
       - focused validation plus adjacent validation for the owner path
       - no dominant reliance on placeholder semantics for the owner's main runtime outcome
    - This label does not mean the requirement is final or perfect. It means the owner is materially implemented and the remaining gaps are iterative rather than foundational.

## 6. Quality Bar
A requirement package is acceptable only if all checks pass.

1. Specific: states exactly what changes in runtime behavior.
2. Testable: each key statement can be validated by logs, assertions, or integration checks.
3. Bounded: defines scope and explicit constraints.
4. Traceable: maps to one clear problem statement.
5. Safe: includes fallback or degradation behavior when dependencies fail.
6. Architecturally owned: every new runtime concept has a clear owner module and integration path.
7. Migration-safe: default rollout behavior and compatibility behavior are both explicit.
8. Maturity-aware: if the index tracks maturity, the assigned maturity label is justified by concrete implementation and validation evidence.

## 7. Language and Style Rules

1. Keep terms consistent across all requirement files.
2. Prefer short declarative sentences.
3. Do not mix implementation TODO notes with requirement statements.
4. Avoid contradictory requirements in the same document.
5. Keep one requirement package focused on one architectural concern.

## 8. Cross-File Update Rules
When adding or materially changing a requirement package, the author must also update `docs/requirements/index.md` with:

1. Overview table changes.
2. Priority changes if relevant.
3. Dependency changes if relevant.
4. Suggested implementation sequence changes if order changes.
5. Maturity changes if implementation coverage changed.

A requirement change set is incomplete if `index.md` is stale.

When updating a requirement package, the author must keep requirement, design, and task aligned:

1. `requirement.md` defines the behavioral boundary.
2. `design.md` defines the target runtime shape and owning abstractions.
3. `task.md` defines the implementation slices and validation path.

If design or task changes alter ordering, ownership, rollout strategy, or implementation maturity, `index.md` must be updated in the same change set.

If implementation changes alter owner maturity, the index update must include both the new maturity label and enough change context for a reviewer to understand why that maturity changed.

### 8.1 Progress flow map sync rule

The module progress flow maps `docs/PROGRESS_FLOW.en.md` and `docs/PROGRESS_FLOW.zh-CN.md` are living implementation-facing documents. A requirement change set MUST update both maps in the same change set whenever it materially changes:

1. an owner's maturity color (the map colors must match the `index.md` `Maturity` column),
2. the runtime stage chain order or membership,
3. owner boundaries (a new owner, a merged owner, or a closed gap).

Both maps must be updated together (English and Chinese), and each map's "Last synced" line must name the requirement that last touched it. A change set that alters owner maturity, the stage chain, or owner boundaries without updating both progress flow maps is incomplete, exactly like a stale `index.md`.

### 8.2 Prompt-change validation rule (real-LLM probe)

Any requirement that adds or changes an LLM-facing prompt — a system/user prompt, an embodied
prompt-contract layer (`16`), or what an owner projects into an LLM request (e.g. the `11`
internal-thought request, the R70 semantic bridges) — MUST validate the EXPECTED enhanced prompt
against the real configured model BEFORE or as part of implementation, using
`scripts/run_llm_prompt_probe.py`.

Mandatory steps:

1. Construct the expected prompt (the system/user pair the change will produce) as a probe
   `--case-file` (or direct `--system-prompt`/`--user-prompt`), including the new context fields.
2. Run it against the real configured model (`.env` `OPENAI_API_KEY`/`OPENAI_BASE_URL`/
   `HELIOS_LLM_MODEL`), and confirm the model behaves as intended: it engages the new context, parses
   (when a structured envelope is expected), and trips no `must_not_contain` anti-pattern (e.g. a
   theatrical phrase, or a "no real signal" symptom the change is meant to fix).
3. For reasoning models (e.g. MiniMax-M3) pass `--strip-reasoning` (mirrors the `11` parser's
   `<think>`/code-fence stripping) and an adequate `--max-tokens` (>= 2048; a richer prompt makes the
   model think longer, so too small a budget truncates inside `<think>` with `finish_reason=length`).
4. Save the probe JSON (`--save-json`, under git-ignored `logs/`) and record the probe outcome
   (PASS + the key observation) in the requirement's `design.md` Validation Strategy.

A prompt-changing requirement whose design does not cite a real-LLM probe result is incomplete. The
probe is for design validation; it does not replace the network-free owner/contract tests.

## 9. Requirement Template
Use this template when creating a new `requirement.md`.

# Requirement NN - <name>

## 1. Background and Problem
<current behavior, issue evidence, impact>

## 2. Goal
<target behavior>

## 3. Functional Requirements
### 3.1 <subtopic>
1. <mandatory behavior>
2. <mandatory behavior>

### 3.2 <subtopic>
1. <mandatory behavior>

## 4. Non-Functional Requirements
1. <performance or reliability constraint>
2. <observability or migration constraint>

## 5. Code Behavior Constraints
1. <forbidden pattern>
2. <boundary rule>

## 6. Impacted Modules
1. <module path>
2. <module path>

## 7. Acceptance Criteria
1. <verifiable criterion>
2. <verifiable criterion>

## 10. Review Checklist for AI Authors
Before finalizing, verify:

1. Folder and file naming follow the standard.
2. All mandatory sections exist and are complete.
3. Each `must` statement is testable.
4. Acceptance criteria are objective and runnable.
5. The design identifies the owning abstraction for new runtime concepts.
6. The design states default rollout behavior and fallback behavior.
7. The task document contains ordered, verifiable implementation slices.
8. `index.md` has been updated.
9. No unresolved placeholder text remains.
10. Any maturity label present in the index is still justified by the current implementation and validation evidence.
