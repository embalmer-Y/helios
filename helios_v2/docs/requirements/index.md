# Helios v2 Requirements Index

| Req | Name | Status | Maturity | Depends On | Notes |
| --- | --- | --- | --- | --- | --- |
| 01 | Runtime Kernel | draft | relatively_complete | none | Establishes startup gating, lifecycle orchestration, and owner-safe stage dispatch |
| 02 | Sensory Ingress | draft | relatively_complete | 01 | Establishes owned stimulus normalization, source registration, and ingress API/ops contracts |
| 03 | Rapid Salience Appraisal | draft | baseline_implementation | 02 | Establishes fast-path coarse salience appraisal and the sensory-ingress to appraisal API/ops boundary |
| 04 | Neuromodulator System | draft | baseline_implementation | 03 | Establishes independently modeled neuromodulator state contracts, modulation update API/ops, and explicit confirmation gates for learned update semantics |
| 05 | Interoceptive Feeling Layer | draft | baseline_implementation | 04 | Establishes subjective body-feeling state from neuromodulator state and normalized internal signals, with soft-modulation-only output contracts |
| 06 | Memory Affect and Replay | draft | baseline_implementation | 05 | Establishes affect-tagged memory snapshots, replay-candidate surfacing, forced consolidation constraints, and candidate memory supply to later workspace owners |
| 07 | Workspace Competition and Working State | draft | baseline_implementation | 06 | Establishes candidate-set competition, short-lived working-state ownership, and workspace-facing promotion boundaries for memory-derived content |
| 08 | Reportable Conscious Content | draft | relatively_complete | 07 | Establishes conscious-content commitment from workspace outputs, explicit no-commit semantics, and a non-reach-through upstream content-material boundary |
| 09 | Thought Gating and Continuation Pressure | draft | baseline_implementation | 08 | Establishes the sole owner of thought-window firing decisions, compact gate observability, and multi-tick continuation-pressure carry without collapsing into retrieval or thought generation |
| 10 | Directed Retrieval Into Thought Window | draft | baseline_implementation | 09 | Establishes the sole owner of retrieval-query planning, tiered memory selection, and bounded thought-window bundle assembly without collapsing retrieval policy back into memory ownership |
| 11 | Internal Thought Loop Owner | draft | baseline_implementation | 10 | Establishes the sole owner of fired-path thought execution, sufficiency and continuation judgment, and proposal emission without collapsing into persistence, planning, or governance acceptance |
| 12 | Action Proposal and Externalization Contract | draft | baseline_implementation | 11 | Establishes the sole owner of thought-origin proposal normalization, externalization contract publication, and bridge-level rejection semantics without collapsing into planner acceptance or executor dispatch |
| 13 | Planner Executor Feedback Bridge | draft | baseline_implementation | 12 | Establishes the sole owner of proposal-to-decision bridging, formal rejection and execution-outcome publication, and normalized bridge feedback semantics without collapsing into transport or feedback persistence |
| 14 | Identity Governance and Self Revision Integration | draft | baseline_implementation | 13 | Establishes the sole owner of self-revision governance, identity-state mutation, proactive governance pressure, and formal revision-result publication without collapsing into thought generation, personality projection, or audit persistence |
| 15 | Execution Writeback and Autobiographical Consolidation | draft | baseline_implementation | 13, 14 | Establishes the sole owner of execution-result writeback, autobiographical/semantic consolidation handoff, and continuity-preserving experience publication without collapsing into planner, governance, or raw storage backends |
| 16 | Embodied Subjective Prompt and Action Autonomy | draft | baseline_implementation | 11, 12, 13, 15 | Establishes the sole owner of embodied subjective prompt-contract assembly for thought and outward expression without collapsing into thought ownership, planner authority, or identity governance |
| 17 | Evaluation Fidelity and Diagnostic Provenance | draft | baseline_implementation | 13, 15, 16 | Establishes the sole owner of evidence-driven runtime evaluation and diagnostic provenance publication without collapsing into runtime mutation or planner/channel shortcuts |
| 18 | Subjective Autonomy and Proactive Evolution | draft | relatively_complete | 09, 10, 11, 13, 15, 16, 17 | Establishes the sole owner of proactive-drive integration, multi-tick self-directed continuation, long-horizon deferred-continuity decay/merge/resolution, and controlled proactive externalization without collapsing into prompt theater or channel-owned triggering |
| 19 | Architecture Boundary and Owner Documentation | draft | baseline_implementation | 01-18 | Establishes the formal v2 boundary-truth documentation set that keeps runtime owners, allowed dependencies, migration notes, and prohibited shortcuts aligned with implementation truth |
| 20 | Brain Architecture Comparison and Scientific Grounding | draft | baseline_implementation | 19 | Establishes the formal scientific-grounding documentation set that maps v2 owner domains to cautious brain-function analogs, evidence categories, explicit non-goals, requirement-linked gap analysis, and an owner-wave gap roadmap |
| 21 | Unified Runtime Observability and Logging | draft | baseline_implementation | 01 | Establishes the sole owner of structured runtime log events, severity/event-kind taxonomies, fail-fast sink dispatch, and an optional kernel-level emission seam that produces a correlated per-tick stage timeline across the `01-18` chain without becoming authoritative state or a cross-owner reach-through channel |
| 22 | Runtime Composition Root and Runnable Runtime | draft | baseline_implementation | 01-18, 21 | Establishes the sole assembly owner that wires the dependency gate, the canonical nineteen-stage chain with shipped first-version owner-neutral bridges, and an optional observability recorder into a single runnable runtime handle plus a thin driver, and enforces the `21` owner as the single logging mechanism, without owning cognitive policy or introducing any degraded assembly path |
| 23 | Execution-Timeline-Aware Evaluation and Consequence Binding | draft | baseline_implementation | 17, 21, 22 | Establishes observability-owned read-only execution-timeline reconstruction and upgrades the evaluation owner to consume the prior-tick timeline as formal evidence and publish consequence-binding scores distinguishing internally-activated, blocked, rejected, executed, and continuity-written outcomes, without the log channel becoming an authoritative decision transport |
| 24 | Long-Horizon Continuity Threads and Reinforcement | draft | not_started | 18, 22, 23 | Establishes a first-class continuity-thread concept in the autonomy owner that aggregates deferred continuity across ticks into reinforceable, conflict-arbitrated, age-aware long-horizon threads and publishes an owner-owned long-horizon continuity state to the read-only evaluation owner, building on the existing decay/merge/expire semantics without inventing motive content or moving continuity ownership out of `18` |

## Maturity Scale

The `Maturity` column is implementation-facing and must be reassessed whenever requirement, design, task, or code changes materially alter runtime coverage.

1. `not_started`
	- Requirement/design/task may exist, but no owner implementation has landed for the runtime concept.
	- Documentation-only progress does not count as implementation progress.
2. `pure_skeleton`
	- Code package or owner shell exists, but behavior is still mostly structural.
	- Typical signs: placeholder policies, pass-through wiring, missing runtime chain integration, or tests that validate only shapes rather than owner behavior.
3. `baseline_implementation`
	- The owner executes a real first-version behavior with fail-fast contracts and focused tests.
	- The core runtime path works end-to-end for the requirement's narrow owner responsibility, but major policy depth or downstream closure remains intentionally incomplete.
4. `relatively_complete`
	- The owner has a concrete first-version implementation, is integrated into its expected runtime path where applicable, and covers most of the requirement's intended owner behavior with focused and adjacent validation.
	- Further iteration may still deepen policy quality or later-stage integration, but the requirement is no longer mainly a scaffold or thin baseline.

## Authoring Rules

All requirement packages in Helios v2 must follow the same structure enforced by `d:/Software/project/helios/helios_v2/docs/requirements/requirement-authoring-standard.md`.

Additional Helios v2 constraints:

1. No requirement may specify fallback runtime behavior for critical capability loss.
2. Failure modes must be written as hard-stop or abort semantics.
3. Any adaptive policy must identify how it is learned, provided, or initialized without hardcoded runtime strategy branches.
4. Every design must name the module owner, the public API or ops it exposes, and the responsibilities it explicitly does not own.
5. Every task plan must show requirement -> design -> implementation order and must not skip directly to coding.
6. Every cross-module interface introduced by a requirement must be documented with comments or docstrings in code.
7. Every new public interface must follow `helios_v2/docs/API_AND_OPS_CONTRACT_GUIDE.md`.
8. Every material change to implementation coverage must update the `Maturity` column using the standard defined in `d:/Software/project/helios/helios_v2/docs/requirements/requirement-authoring-standard.md`.