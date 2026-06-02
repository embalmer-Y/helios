# Helios v2 Architecture Boundaries

> Status: baseline boundary-truth snapshot on 2026-06-02
> Scope: implementation-aligned owner and dependency truth for `helios_v2`

## 1. Purpose

This document is the boundary truth for Helios v2.

It operationalizes the philosophy, final-goal definition, and v2.0.0 release constraints defined in `ARCHITECTURE_PHILOSOPHY.zh-CN.md`.

API and ops formatting rules are defined in `API_AND_OPS_CONTRACT_GUIDE.md` and are mandatory for all public cross-module interfaces.

It defines:

1. owner modules,
2. allowed dependency directions,
3. prohibited implementation shortcuts,
4. startup and runtime hard-stop rules.
5. module API and ops exposure rules.
6. design-before-development workflow rules.

## 2. Global Constraints

1. Runtime strategy must not be hardcoded into source-level decision branches.
2. Runtime must not provide degraded, compatibility, or fallback behavior when critical dependencies are missing.
3. Missing critical dependencies must block startup or abort the active execution path.
4. One runtime concept must have one semantic owner.
5. Evaluation is read-only and cannot mutate runtime behavior.
6. Cross-module collaboration must happen through explicit APIs or ops contracts rather than direct state reach-through.
7. Public APIs and ops contracts must carry comments or docstrings describing ownership, inputs, outputs, and failure semantics.
8. Implementation work must not begin until requirement and design documents exist for the target slice.

## 3. Core Owner Map

| Domain | Owner package | Responsibility |
| --- | --- | --- |
| Runtime kernel | `helios_v2.runtime.kernel` | lifecycle orchestration, startup gating, stage dispatch |
| Runtime dependency gate | `helios_v2.runtime.dependencies` | critical dependency validation and fail-fast startup rules |
| Runtime observability | `helios_v2.observability` | structured runtime log events, severity/event-kind taxonomies, fail-fast sink dispatch, and the runtime observability recorder |
| Requirement truth | `helios_v2/docs/requirements/*` | behavioral boundary, design, and task authority |

## 4. Stable Runtime Owner Snapshot (`16-18`)

This section is the active boundary-truth snapshot for the currently stabilized owner wave.

### 4.1 Requirement `16` prompt and outward-expression chain

| Owner | Primary modules | Owns | Explicitly does not own |
| --- | --- | --- | --- |
| Embodied prompt owner | `helios_v2.prompt_contract` | embodied subjective prompt-contract assembly for `thought` and `outward_expression` consumers; anti-theatrical constraints; capability and authority boundary rendering; outward-expression request handoff | internal thought execution; planner authority; channel execution; identity-governance judgment |
| Outward-expression owner | `helios_v2.outward_expression` | bounded outward-expression draft assembly from prompt-owned request | final execution authority; planner decision; channel routing; transport dispatch |
| Outward-expression externalization owner | `helios_v2.outward_expression_externalization` | execution-adjacent externalization draft assembly from outward-expression draft | final planner/channel/transport authority |

Boundary rules:

1. `prompt_contract` is the sole owner of prompt-contract assembly, not the owner of user-visible execution.
2. `outward_expression` may prepare one bounded draft, but that draft is non-authoritative.
3. `outward_expression_externalization` may prepare an execution-adjacent draft, but that draft is still non-authoritative.
4. The formal chain is `EmbodiedPromptContract -> OutwardExpressionPromptView -> OutwardExpressionRequest -> OutwardExpressionDraft -> OutwardExpressionExternalizationDraft`.

### 4.2 Requirement `17` evaluation owner

| Owner | Primary modules | Owns | Explicitly does not own |
| --- | --- | --- | --- |
| Evaluation owner | `helios_v2.evaluation` | read-only evaluation request/evidence-bundle assembly, diagnostic artifact publication, gap analysis, long-range diagnostics | runtime mutation; planner authority; channel execution; governance judgment; storage writes |

Boundary rules:

1. `evaluation` consumes only explicit owner outputs and provenance-rich evidence bundles.
2. `evaluation` must not scrape transient locals or private mutable runtime state.
3. `evaluation` currently consumes thought, action externalization, planner, governance, writeback, prompt, outward-expression, outward-expression externalization, and autonomy evidence.

### 4.3 Requirement `18` autonomy owner

| Owner | Primary modules | Owns | Explicitly does not own |
| --- | --- | --- | --- |
| Autonomy owner | `helios_v2.autonomy` | proactive-drive integration, bounded disposition selection, deferred continuity publication, outward-vs-inward proactive distinction | prompt assembly; planner authority; channel execution; governance judgment |

Boundary rules:

1. `autonomy` is the sole owner of proactive-drive integration and deferred continuity in v2.
2. `autonomy` may request or justify proactive externalization semantically, but it must not directly execute a channel path.
3. Blocked proactive tendencies must become explicit deferred continuity records rather than disappearing silently.

### 4.4 Requirement `21` observability owner

| Owner | Primary modules | Owns | Explicitly does not own |
| --- | --- | --- | --- |
| Observability owner | `helios_v2.observability` | structured `LogEvent` contract, severity and event-kind taxonomies, `LogSink` protocol, first-version in-memory and JSON-line sinks, and the sequence-stamping `RuntimeObservabilityRecorder` | any cognitive runtime decision or state; planner authority; channel execution; governance judgment; authoritative inter-owner state transport; persistence policy beyond the sink boundary |

Boundary rules:

1. `observability` is read-only infrastructure. It consumes only already-public runtime artifacts and lifecycle facts and never mutates owner state.
2. The uniform emission point for the `01-18` chain is the runtime kernel, which observes public stage results and lifecycle events only. Cognitive owners do not import `observability` to self-log in this slice.
3. Log events must never be the authoritative source of any first-class runtime concept. No owner may depend on the log channel to receive another owner's decision.
4. The recorder is fail-fast: zero sinks raise at construction and sink emission failures propagate. There is no degraded no-op recorder.
5. Observability is default-off at the kernel: an absent recorder is a non-instrumented runtime, not a degraded cognitive mode.

## 5. Allowed Dependency Directions for `16-18`

The currently stabilized dependency directions are:

```mermaid
flowchart LR
	C10[10 Directed Retrieval] --> C16[16 Prompt Contract]
	C08[08 Conscious Content] --> C16
	C09[09 Thought Gating] --> C16
	C16 --> C11[11 Internal Thought]
	C16 --> O16A[16 Outward Expression]
	O16A --> O16B[16 Outward Expression Externalization]
	C11 --> C12[12 Action Externalization]
	C12 --> C13[13 Planner Bridge]
	C11 --> C14[14 Identity Governance]
	C13 --> C15[15 Experience Writeback]
	C14 --> C15
	C09 --> C18[18 Autonomy]
	C10 --> C18
	C11 --> C18
	C13 --> C18
	C14 --> C18
	C15 --> C18
	C16 --> C18
	O16A --> C18
	O16B --> C18
	C11 --> C17[17 Evaluation]
	C12 --> C17
	C13 --> C17
	C14 --> C17
	C15 --> C17
	C16 --> C17
	O16A --> C17
	O16B --> C17
	C18 --> C17
```

Interpretation rules:

1. `16` may consume upstream conscious, gating, and retrieval outputs only through explicit runtime request providers.
2. `18` may read explicit results from `09`, `10`, `11`, `13`, `14`, `15`, and the `16` outward-expression artifact chain, but it does not reclaim execution authority from those owners.
3. `17` is downstream and read-only. It may observe `18`, but `18` must never depend on `17` for runtime strategy.
4. No owner in `16-18` may bypass `13` when the path becomes externally consequential.

## 6. Prohibited Patterns

1. Branching to a low-capability execution path when an LLM, memory, evaluation, or channel capability is unavailable.
2. Encoding fixed routing rules, fixed prompt paths, or fixed decision thresholds directly in orchestration code.
3. Allowing a downstream adapter to silently reinterpret a rejected or unavailable capability as a different behavior.
4. Making runtime success depend on implicit defaults that hide dependency absence.
5. Importing another domain's private state or internal helper just to bypass its owner API.
6. Adding a new module without defining its owner, inbound API, outbound ops, and non-owned responsibilities.
7. Letting `prompt_contract` evolve into a hidden reply-first behavior owner.
8. Treating `OutwardExpressionDraft` or `OutwardExpressionExternalizationDraft` as final execution authority.
9. Letting `autonomy` emit timer-only outward text without planner and channel authority.
10. Allowing blocked proactive tendencies to vanish without deferred continuity evidence.
11. Letting `evaluation` infer strong runtime fidelity from missing provenance categories.

## 7. API and Ops Exposure Rules

1. Each module owner must expose a small public API surface.
2. Cross-domain commands must be expressed as ops-like contracts, not hidden helper calls.
3. Public API methods must document:
	- the owner responsibility,
	- required inputs,
	- returned outputs,
	- hard-stop conditions or raised errors.
4. Private helpers may remain undocumented only if they do not cross module boundaries.
5. If an interface is not stable enough to document, it is not stable enough to expose across module boundaries.
6. For `16-18`, every runtime stage result and provider protocol is part of the boundary truth and must preserve upstream provenance ids explicitly.

## 8. Migration-State Recording Rules

Current migration-state facts that must remain explicit rather than implied away:

1. `16` is stable at the current baseline, but its outward-expression path remains draft-only by design; final execution authority intentionally stays outside that owner family.
2. `17` is stable as a read-only diagnostic owner, but its first-version scoring depth is still shallower than the final project goal; baseline coverage does not mean complete evaluation semantics.
3. `18` now carries deferred continuity across ticks through owner-private stage state plus explicit request carry records, and the current baseline also includes long-horizon decay, same-key merge, and explicit resolved-or-expired accounting. It remains deterministic and bounded rather than a fully open-ended proactive-evolution policy.
4. Any later requirement that deepens `16-18` must update both its own package docs and this file's owner snapshot if boundary truth changes materially.
5. `21` observability landed as a baseline read-only owner plus an optional kernel emission seam. It is default-off, so existing runtime construction and tests are unaffected. Its current scope is the kernel-level lifecycle and per-stage timeline only; owner-level fine-grained emission remains intentionally out of scope until a later slice opens it through the same owner.

## 9. Requirement Citation Rules

When later requirement packages cite current boundary truth, they must reuse the following vocabulary instead of redefining it locally:

1. `prompt-contract owner`
2. `outward-expression draft owner`
3. `outward-expression externalization draft owner`
4. `evaluation owner`
5. `autonomy owner`
6. `deferred continuity`
7. `read-only evidence consumer`
8. `final execution authority remains outside the owner`

## 10. Development Workflow Rule

1. Every implementation slice must start with a requirement package or an explicit addition to an existing requirement package.
2. Every requirement slice must have design before code changes expand beyond scaffolding.
3. Task decomposition must reference concrete files and validation commands before development begins.
4. Code written ahead of requirement and design truth is considered invalid implementation debt.

## 11. Startup Gate Rule

Startup is valid only when all declared critical dependencies are present.

If any critical dependency is missing:

1. startup must fail,
2. the missing dependency set must be explicit,
3. runtime must not switch to a reduced mode.

## 12. Traceability Rules

1. `helios_v2/docs/requirements/index.md` is the maturity index, not the detailed boundary document.
2. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` is the active owner/boundary truth document for implemented slices.
3. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` is the active scientific-grounding companion document and must not override owner-boundary truth.
4. Requirement packages `16`, `17`, `18`, `19`, and `20` are the detailed implementation truth for their respective owner or documentation slices and must remain mutually consistent with this file when they cite current runtime reality.
5. Requirement package `21` is the detailed implementation truth for the observability owner and the kernel emission seam, and must remain consistent with the observability owner snapshot in this file.
6. If current runtime truth and target truth diverge, the conflict must be recorded in the requirement package and, when cross-cutting, in this document's migration-state section.