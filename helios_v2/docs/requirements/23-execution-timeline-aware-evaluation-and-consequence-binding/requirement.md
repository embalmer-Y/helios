# Requirement 23 - Execution-timeline-aware evaluation and consequence binding

## 1. Background and Problem

After `21` (observability) and `22` (composition root), Helios v2 is a runnable runtime that advances across ticks and, when a recorder is injected, emits a structured per-tick stage timeline. The `17` evaluation owner already consumes explicit owner outputs and publishes a read-only diagnostic artifact.

However, the wave A exit signal in `BRAIN_ARCHITECTURE_COMPARISON.md` is not yet met. Two concrete gaps remain:

1. Evaluation does not consume the `21` kernel execution timeline at all. The structured per-tick stage timeline produced by the recorder exists as a disconnected log surface. Evaluation cannot currently tell, from formal evidence, which stages actually ran, in what order, with what duration, and whether any stage failed during a tick.
2. Evaluation scoring is binary presence-checking. Today `17` scores each dimension as `1.0 if evidence else 0.0` and reports gaps as strings. It does not distinguish whether internal activation actually became externally consequential: a thought that was blocked, a proposal that was policy-rejected, an action that executed, and an outcome that was written back all collapse into coarse presence flags.

This matters because the final-goal standard requires the system to be falsifiable: it must be possible to tell apart "the runtime really closed the internal-to-visible causal chain" from "internal traces were produced but never reached consequence". Without timeline-aware evidence and consequence-binding scoring, the project can still overstate progress by counting internal activity that never closed into visible outcome.

A hard boundary constraint applies. `21` states that no owner may depend on the log channel to receive another owner's decision. Therefore evaluation must not read raw log events as authoritative input, and must not treat any owner's semantic decision as if it arrived through the log. Only kernel execution-timing facts (stage order, duration, started/completed/failed lifecycle) may be reconstructed for diagnostic use, and that reconstruction must be owned by the observability owner and exposed as a formal read-only contract.

## 2. Goal

Strengthen the evaluation owner so it consumes a formal, read-only execution-timeline view reconstructed by the observability owner and produces consequence-binding fidelity scores that distinguish blocked, rejected, executed, and continuity-written paths, while preserving owner boundaries, remaining read-only, failing fast on missing timeline evidence rather than inferring fidelity, and not consuming raw log events as authoritative state.

## 3. Functional Requirements

### 3.1 Observability-owned timeline reconstruction
1. The observability owner (`helios_v2.observability`) must own a formal, immutable execution-timeline view contract that summarizes one tick of kernel execution: the tick id, the ordered stage entries, and per-stage started/completed/failed status and duration.
2. The observability owner must own a reconstructor that builds the timeline view from already-captured log events. The reconstructor is read-only and derives the view only from kernel-emitted execution-timing facts (stage order, duration, lifecycle), never from any owner's semantic decision payload.
3. The timeline view is the only sanctioned form in which downstream owners may consume execution-timing facts. Downstream owners must not parse raw `LogEvent` objects to obtain timing facts.
4. Reconstruction from an event stream that lacks the required lifecycle events for a tick must fail explicitly or produce an explicitly incomplete view, never a fabricated one.

### 3.2 Evaluation consumes the timeline as formal evidence
1. The evaluation evidence bundle must gain a dedicated execution-timeline evidence category sourced from the observability timeline view.
2. Evaluation must consume the timeline view as a formal read-only contract, not as a raw list of log events.
3. Timeline evidence must carry the tick id it describes, so evaluation can state which tick's execution it is reasoning about.
4. When timeline evidence is absent (for example an uninstrumented runtime), evaluation must publish an explicit incompleteness warning and must not infer execution fidelity from its absence.

### 3.3 Cross-tick evaluation
1. Evaluation must reason about the execution timeline of the previous completed tick, not the current in-progress tick, because the current tick is not yet complete when the evaluation stage runs.
2. The composition owner must carry the previous tick's timeline view forward and supply it to the evaluation evidence assembly for the next tick, through an explicit owner-neutral bridge.
3. On the first tick, when there is no previous tick, evaluation must record an explicit "no prior execution timeline" status rather than fabricate one.

### 3.4 Consequence-binding scoring
1. Evaluation must replace binary presence scoring for the consequence-relevant dimensions with scoring that distinguishes at least these path outcomes: internally activated only, blocked, rejected, executed, and continuity-written.
2. Evaluation must publish an explicit internal-to-visible consequence-binding assessment that states whether internal activation in the chain reached an externally consequential outcome for the evaluated tick.
3. Consequence-binding scoring must use the formal status taxonomies already published by the owners (for example the planner bridge status set: accepted, policy_rejected, execution_consistency_failed, executed, execution_failed) rather than re-deriving status from heuristics.
4. Evaluation must annotate which scored dimensions are currently derived from deterministic first-version shim evidence, so the diagnostic does not overstate fidelity while the cognition chain is still deterministic.

### 3.5 No fallback behavior
1. Missing timeline evidence must produce an explicit incompleteness warning, never an optimistic default score.
2. The timeline reconstructor must not invent lifecycle events that did not occur.
3. Evaluation must not mutate runtime behavior, planner authority, channel execution, governance decisions, or storage, and must remain read-only.

## 4. Non-Functional Requirements

1. Performance: timeline reconstruction must be bounded by the number of events in one tick and must not change runtime execution behavior.
2. Reliability: for identical evidence and identical scoring policy, evaluation artifacts must remain deterministic and comparable across runs.
3. Observability and logging: this requirement consumes the `21` event surface; it must not introduce a second logging mechanism, and it must not use `logging` or `print`.
4. Compatibility and migration: the timeline view and the new evidence category are additive. An uninstrumented runtime (no recorder) must still assemble and run; evaluation simply records explicit timeline incompleteness in that case.

## 5. Code Behavior Constraints

1. The execution-timeline view and its reconstructor must live in the observability owner. Evaluation must not reconstruct timelines itself, and must not import raw event parsing logic.
2. Evaluation must not depend on the log channel to receive any owner's semantic decision. Only kernel execution-timing facts may flow through the timeline view, and authoritative owner decisions must still arrive through the existing owner result contracts.
3. The composition owner remains assembly-only. Carrying the previous tick's timeline forward must be owner-neutral glue, not a new cognitive decision.
4. No degraded or fallback scoring is allowed. Missing evidence is reported explicitly.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/observability/contracts.py`
2. `helios_v2/src/helios_v2/observability/engine.py`
3. `helios_v2/src/helios_v2/observability/__init__.py`
4. `helios_v2/src/helios_v2/evaluation/contracts.py`
5. `helios_v2/src/helios_v2/evaluation/engine.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`
7. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
8. `helios_v2/tests/test_observability_timeline.py`
9. `helios_v2/tests/test_evaluation_engine.py`
10. `helios_v2/tests/test_runtime_composition.py`
11. `helios_v2/docs/requirements/index.md`
12. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
13. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 7. Acceptance Criteria

1. The observability owner exposes a documented, immutable execution-timeline view contract and a read-only reconstructor that builds it from captured kernel lifecycle events, with explicit incompleteness when required lifecycle events are missing.
2. The reconstructed timeline view for a multi-stage tick lists the stages in canonical execution order with per-stage completed/failed status and duration, derived only from kernel timing facts.
3. The evaluation evidence bundle includes an execution-timeline evidence category carrying the described tick id, consumed as a formal contract rather than raw events.
4. Evaluation reasons about the previous completed tick's timeline; on the first tick it records an explicit "no prior execution timeline" status, and across later ticks it consumes the carried-forward view.
5. Evaluation publishes consequence-binding scores that distinguish internally-activated, blocked, rejected, executed, and continuity-written outcomes, using owner-published status taxonomies, and annotates which dimensions are still shim-derived.
6. When no recorder is attached, evaluation publishes an explicit timeline incompleteness warning and does not infer execution fidelity from the absence.
7. The single-logging-mechanism guard test still passes, and the full `helios_v2/tests` suite remains green.

## 8. Future Extension Scope

This requirement builds the measurement framework while the cognition chain is still deterministic first-version shim. Its falsifiability value is fully realized once real cognition (for example an LLM-backed thought path) lands, at which point the same timeline-aware, consequence-binding evaluation begins scoring genuinely non-deterministic behavior. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Durable persistence and cross-run comparison of timeline-aware artifacts.
2. Deeper consequence-binding metrics once non-deterministic cognition produces variable paths.
3. Richer long-horizon continuity scoring as `18`, `14`, and `15` deepen (wave B).
4. Owner-level fine-grained observability emission feeding finer timeline detail, opened through the `21` owner under plan C.

None of these may be smuggled into this slice. This requirement does not introduce LLM cognition, does not change any cognitive owner's policy, and does not grant evaluation any runtime write authority.
