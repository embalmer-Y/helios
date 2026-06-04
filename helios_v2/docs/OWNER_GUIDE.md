# Helios v2 Owner Guide

> Status: living owner reference. Last synced: R36. Test baseline: 486 passed (network-free).
> Role: the by-owner explanation of responsibility, role in the loop, completeness, and the
> next development/optimization direction for every Helios v2 owner.
> Companion documents:
> - `OWNER_GUIDE.zh-CN.md` — the Chinese companion of this file, kept in sync.
> - `ARCHITECTURE_PHILOSOPHY.zh-CN.md` — final goal, locked acceptance criteria, P0→P7 phase roadmap.
> - `ARCHITECTURE_BOUNDARIES.md` — owner boundaries, allowed dependency directions, migration-state truth.
> - `BRAIN_ARCHITECTURE_COMPARISON.md` — brain-function analogs, gap analysis, owner-wave roadmap.
> - `PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md` — the color-coded module progress map.
> - `requirements/index.md` — the authoritative per-requirement `Maturity` column.

## 1. Purpose and how to read this document

This document is the single by-owner reference for Helios v2. For each owner it states:

1. Owner — the requirement number and the owning Python package.
2. Responsibility — what the owner owns (and the adjacent concerns it explicitly does not own).
3. Role in the loop — where it sits in the tick and what it consumes/produces.
4. Completeness — its real implementation maturity plus the honest caveat (for example "inputs are still composition-injected shim").
5. Next step — the concrete development or optimization direction, tied to the phase roadmap.

It is implementation-facing: the completeness labels must match `requirements/index.md` and the
color-coding in the progress-flow maps. When an owner's maturity, boundary, or stage membership
changes, this document must be updated in the same change set, exactly like the progress maps.

### 1.1 Completeness vocabulary

| Label | Meaning |
| --- | --- |
| `deep_real` | LLM-driven cognition or a `relatively_complete` owner whose main runtime outcome is real, not placeholder. |
| `baseline_real` | Owner executes a real first-version behavior with fail-fast contracts and tests, but a material part of its inputs or downstream consequence is still shallow or composition-injected shim. |
| `infra_done` | Supporting infrastructure/capability owner shipped and validated; not a cognitive owner. |
| `docs_owner` | Documentation owner: its deliverable is a maintained document set, not runtime code. |

### 1.2 The single biggest current caveat

The cognition main chain runs end to end, but most early-and-mid-chain cognitive owners
(`03-07`, `09-10`, `12`) are `baseline_real` with **composition-injected deterministic shim
inputs**: their contracts, validation, and tests are real, but the values flowing into them are
fixed first-version constants, not real signals. De-shimming these is the substance of phase
`P3`. The owners that are genuinely signal-driven today are `02`, `08`, `11` (LLM), `18`, and
the infrastructure owners.

---

## 2. Cognitive chain owners (the per-tick loop)

These run every tick in `CANONICAL_STAGE_ORDER` (19 stages; the channel-bound variant inserts
two transport stages for 21).

### 2.1 `01` Runtime Kernel — `helios_v2.runtime.kernel`
- Completeness: `deep_real` (infra-grade).
- Responsibility: lifecycle orchestration, fail-fast startup gating, ordered stage dispatch, and (when a recorder is injected) per-stage lifecycle emission. Does not own any cognitive decision.
- Role in the loop: drives the whole tick; constructs the per-stage `RuntimeFrame` and aggregates stage results into a `RuntimeTickResult`.
- Next step: keep orchestration owner-safe as later owners deepen; no expansion planned. Its final-goal confidence is only as strong as the owners it dispatches.

### 2.2 `02` Sensory Ingress — `helios_v2.sensory`
- Completeness: `deep_real`.
- Responsibility: normalize external and internal raw signals into a deduplicated `Stimulus`/`StimulusBatch`; preserve transport-intrinsic QoS metadata. Does not own salience, retrieval, or routing.
- Role in the loop: first cognitive stage; turns `RawSignal` (from a source or the channel subsystem) into the normalized batch every later owner builds on.
- Next step: protect boundary truth; no de-shim needed. Real external (network) signal sources arrive with future channel drivers, not here.

### 2.3 `03` Rapid Salience Appraisal — `helios_v2.appraisal`
- Completeness: `baseline_real` (novelty dimension is real under the semantic-memory assembly since R35; the other four dimensions are still shim).
- Responsibility: fast-path coarse salience (threat/reward/novelty/social/uncertainty + aggregate) per stimulus, through injected estimators. Does not own fine semantic interpretation, memory, or routing.
- Role in the loop: shapes downstream salience right after sensory; the appraisal batch feeds modulation and gating signals.
- Next step (staged P3 de-shim of this owner):
  1. **R35 — novelty from memory (shipped).** The `novelty` dimension is a real signal: `novelty = clamp(1 - max_similarity, 0, 1)`, where `max_similarity` is the highest cosine similarity between the embedded stimulus and any stored experience embedding (via the `34` embedding gateway + `33` store similarity search). `03` defines a narrow `MemorySimilaritySource` protocol and owns the novelty salience mapping in `MemoryGroundedDimensionEstimator`; composition injects an owner-neutral `MemoryGroundedSimilaritySource` returning the raw cosine fact (or `None`), so `03` imports neither the embedding nor persistence owner. Triggers on the semantic-memory opt-in (store + embedding both present); cold store / empty stimulus content yield the defined maximum novelty `1.0` (no gateway call for empty content); a runtime embedding/store failure is a hard stop (no constant fallback). Default and recency-only assemblies keep constant novelty `0.6`.
     - **Known first-version caveat (cross-register comparison):** the store currently holds only `15` result/continuity summaries, not the raw stimulus text, so R35 novelty compares the incoming *stimulus input* against past *result summaries* sharing the same embedding profile. This is directionally correct (shared content is captured by cosine) but is an input-vs-summary approximation, not a strict input-vs-input comparison. It must not be over-claimed as exact stimulus novelty.
  2. **Method B — apples-to-apples novelty (later slice).** Persist the raw stimulus text stream (a `15`/`33` extension or a dedicated stimulus log) so novelty compares stimulus-against-prior-stimuli in the same register, retiring the cross-register caveat above. This is a separate requirement because it touches the writeback/persistence owners, not `03`.
  3. **Other four dimensions (separate later slices).** De-shim threat/reward/social/uncertainty from their own appropriate real signals (lightweight classifier or LLM scoring), one dimension per slice so each estimator stays independently testable and owner-bounded.
  4. **Aggregate salience.** Replace the constant aggregate estimator with a learned or model-assisted overall judgment once the dimensions are real.
  5. **Downstream coupling.** Feed novelty (and later the other real dimensions) into a de-shimmed `04` neuromodulator dynamics model and `09` gating so real salience measurably shapes gating thresholds (FG-1/FG-2), and later affect-weight or recency-weight novelty once `04`/`05` produce real signals.

### 2.4 `04` Neuromodulator System — `helios_v2.neuromodulation`
- Completeness: `baseline_real` (levels now appraisal-derived under the semantic-memory assembly; stateless).
- Responsibility: independently modeled neuromodulator level state (DA/NE/5-HT/ACh/cortisol/oxytocin/opioid + excitation/inhibition) with explicit learned-parameter categories. Does not own feeling subjectivation or action.
- Role in the loop: the modulation layer that should bias gating thresholds, retrieval, and externalization intensity.
- Completeness detail: with `36` (P3 second de-shim) the constant update path is replaced under the semantic-memory assembly by the composition-provided `AppraisalDerivedNeuromodulatorUpdatePath` (conforms to the owner's `NeuromodulatorUpdatePath` protocol; the engine and contracts are unchanged). It aggregates the rapid-appraisal batch by per-dimension max, then derives each channel as `clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)`: dopamine driven by reward (and weakly by novelty), norepinephrine by novelty and uncertainty, cortisol by threat, other channels regressing to their tonic baseline. The derivation is deterministic, bounded (no NN, no divergence), and **stateless** (no prior-tick levels carried). The default, recency-only, and offline assemblies keep the constant path. Caveat: only novelty is a real `03` driver today (R35); the other four salience dimensions feeding `04` are still first-version constants, and `04`'s levels are not yet coupled into a de-shimmed `05`/`09`.
- Next step: (1) dual-timescale tonic/phasic decay carrying prior-tick levels (depends on a neuromodulator-state carry/checkpoint, the `18`/`09`/`14` state-checkpoint family); (2) `P5` learning of the bounded sensitivity coefficients via reward-prediction-error (DA) and outcome feedback, keeping the equation shape; (3) cross-channel coupling (the declared `cross_channel_coupling_strength` category) beyond the first-version independent mapping; (4) downstream coupling so the real `04` state measurably shapes a de-shimmed `05` feeling and `09` gating (FG-1/FG-2); (5) de-shim the remaining four `03` dimensions so all neuromodulator drivers are real.

### 2.5 `05` Interoceptive Feeling Layer — `helios_v2.feeling`
- Completeness: `baseline_real` (inputs shim).
- Responsibility: subjective body-feeling vector (valence/arousal/tension/comfort/fatigue/pain/social-safety) from neuromodulator state + internal signals; soft-modulation output only. Does not own neuromodulator state or memory.
- Role in the loop: the "what does my body state feel like" layer feeding conscious content and continuity.
- Next step (P3): real feeling construction from real `04` state; make body-state causally matter downstream (FG-2) instead of a fixed vector. Later: persist/restore feeling state (a P2 checkpoint slice).

### 2.6 `06` Memory Affect and Replay — `helios_v2.memory`
- Completeness: `baseline_real` (inputs shim; durable store exists in `33` but `06` formation still fabricates items in-process).
- Responsibility: affect-tagged memory formation and replay-candidate surfacing with forced-consolidation constraints. Does not own retrieval planning, workspace promotion, or identity writeback.
- Role in the loop: forms episodic/affect memory and supplies replay candidates toward the workspace.
- Next step (P2/P3): connect `06` memory items to the `33` durable store (form → persist → share the same durable base with `10`), so memory formation stops fabricating per tick. Then de-shim formation from real feeling/mismatch evidence.

### 2.7 `07` Workspace Competition and Working State — `helios_v2.workspace`
- Completeness: `baseline_real` (inputs shim).
- Responsibility: candidate-set competition and short-lived working-state retention; promotion boundary for memory-derived content. Does not own conscious commitment or retrieval.
- Role in the loop: the attentional bottleneck (FPN-style competition) that decides what reaches conscious content.
- Next step (P3): real competition scoring (a learnable/attention-style scorer) once upstream candidates are real; preserve owner purity while increasing downstream impact.

### 2.8 `08` Reportable Conscious Content — `helios_v2.consciousness`
- Completeness: `deep_real`.
- Responsibility: commit globally reportable conscious content (or explicit no-commit) from workspace outputs, with a non-reach-through upstream content-material boundary. Does not own thought generation or gating.
- Role in the loop: the "what am I consciously aware of this cycle" commitment that gating and prompt assembly consume.
- Next step: tie committed content more strongly to downstream behavioral/diagnostic consequence; deepening, not de-shimming.

### 2.9 `09` Thought Gating and Continuation Pressure — `helios_v2.thought_gating`
- Completeness: `baseline_real` (inputs shim).
- Responsibility: the sole owner of thought-window firing decisions and multi-tick continuation-pressure carry; compact gate observability. Does not collapse into retrieval or thought generation.
- Role in the loop: decides whether a tick fires a thought path, and carries continuation pressure forward.
- Next step (P3 + wave_B): drive the gate from real salience/affect/continuation signals; deepen multi-tick carry. Later: persist/restore continuation pressure across restart (P2 checkpoint slice).

### 2.10 `10` Directed Retrieval Into Thought Window — `helios_v2.directed_retrieval`
- Completeness: `baseline_real` (planning shim; candidate source now real when persistence/semantic memory is enabled).
- Responsibility: the sole owner of retrieval-query planning, tiered selection, and bounded thought-window bundle assembly. Does not own memory persistence or thought generation.
- Role in the loop: assembles the bounded memory window the thought owner reasons over.
- Next step: with `33`/`34` the candidate provider is real (recency, then semantic). Remaining: deepen query-plan policy and recall-intent closure from real upstream gating; connect retrieval intent to later continuity (wave_B).

### 2.11 `16` Embodied Prompt Contract — `helios_v2.prompt_contract`
- Completeness: `baseline_real`.
- Responsibility: embodied subjective prompt-contract assembly for the `thought` and `outward_expression` consumers; anti-theatrical constraints; capability/authority boundary rendering. Does not own thought execution, planner authority, or governance.
- Role in the loop: formats committed state + retrieval + capability boundaries into the contract the thought owner and outward-expression owner consume.
- Next step: keep it a contract formatter (never a reply-first behavior owner); enrich layers as real upstream signals land. Deepening only.

### 2.12 `16` Outward Expression Draft — `helios_v2.outward_expression`
- Completeness: `baseline_real` (draft-only by design).
- Responsibility: one bounded, non-authoritative outward-expression draft from the prompt-owned request. Does not own final execution, planner decision, or channel routing.
- Role in the loop: prepares a candidate outward draft; never authoritative.
- Next step (wave_C): richer proactive draft shaping once execution closure deepens; final authority stays outside this owner family.

### 2.13 `16` Outward Expression Externalization Draft — `helios_v2.outward_expression_externalization`
- Completeness: `baseline_real` (draft-only by design).
- Responsibility: an execution-adjacent externalization draft from the outward-expression draft. Does not own final planner/channel/transport authority.
- Role in the loop: the last pre-execution shaping step in the prompt→draft chain.
- Next step (wave_C): connect the draft to real outward transport via the planner + channel path; remains non-authoritative until then.

### 2.14 `11` Internal Thought Loop — `helios_v2.internal_thought`
- Completeness: `deep_real` (real LLM-driven cognition core).
- Responsibility: the sole owner of fired-path thought execution and the structured judgment (sufficiency, continuation, recall intent, memory handoff, action proposal, self-revision proposal). The model supplies content + structured self-assessment; the owner keeps all final judgment. Does not own persistence, planning, or governance acceptance.
- Role in the loop: the cognitive heart — sources thought content from the `25` LLM gateway through a neutral structured request and parses it into owner-owned judgment.
- Next step: stronger sufficiency/continuation/consequence closure; tighter coupling to real upstream signals as P3 de-shims land. This is the most mature cognitive owner.

### 2.15 `12` Action Proposal and Externalization Contract — `helios_v2.action_externalization`
- Completeness: `baseline_real`.
- Responsibility: the sole owner of thought-origin proposal normalization, externalization-contract publication, and bridge-level rejection semantics. Does not own planner acceptance or executor dispatch.
- Role in the loop: normalizes a thought's action proposal into the contract the planner bridge consumes.
- Next step (wave_C): keep contract truth stable while real outward action closure deepens downstream.

### 2.16 `13` Planner Executor Feedback Bridge — `helios_v2.planner_bridge`
- Completeness: `baseline_real` (planner judgment is real; channel-state snapshot is shim in the default assembly, real in the channel-bound assembly).
- Responsibility: the sole owner of proposal-to-decision bridging, formal rejection/execution-outcome publication, and normalized bridge feedback. Owns final binding/acceptance, not thought semantics; does not own transport or feedback persistence.
- Role in the loop: turns a normalized proposal into an accept/reject/execute decision; publishes `no_actionable_proposal` for internal-only ticks.
- Next step (wave_C): real outward channel execution of an accepted proposal beyond local CLI; richer proactive provenance into action selection.

### 2.17 `14` Identity Governance and Self Revision — `helios_v2.identity_governance`
- Completeness: `baseline_real`.
- Responsibility: the sole owner of self-revision governance, identity-state mutation, proactive governance pressure, and formal revision-result publication. Does not own thought generation, personality projection, or audit persistence.
- Role in the loop: governs whether a self-revision proposal is accepted and applies governed identity change.
- Next step (wave_B / P6): deeper long-horizon governed self-evolution (developmental, not only audited patches); persist/restore identity state across restart (P2 checkpoint slice); eventually the governed self-revision path of P6.

### 2.18 `15` Experience Writeback and Autobiographical Consolidation — `helios_v2.experience_writeback`
- Completeness: `baseline_real` (its continuity stream is now durably persisted via `33`).
- Responsibility: the sole owner of execution-result writeback, continuity-evidence packets, and consolidation-candidate handoff. Does not own planner/governance decisions or raw storage backends.
- Role in the loop: classifies each tick's outcome into a continuity packet and feeds the `15 → 06` loop; its stream is what `33` persists.
- Next step (wave_B): stronger long-range carry and re-entry; richer consolidation once `06` shares the durable base.

### 2.19 `18` Subjective Autonomy and Proactive Evolution — `helios_v2.autonomy`
- Completeness: `deep_real` (`relatively_complete`; cognition-derived since R29; includes the `24` long-horizon continuity-thread layer).
- Responsibility: proactive-drive integration, bounded disposition selection, deferred-continuity publication, and long-horizon continuity threads (recurrence reinforcement, conflict arbitration, owner-owned `LongHorizonContinuityState`). May request proactive externalization semantically but never executes a channel path.
- Role in the loop: integrates real cognition into a proactive disposition (act → externalize, no-action → reflect/defer) and forms/reinforces continuity threads across ticks.
- Next step (wave_B): richer long-horizon motive evolution beyond bounded carry; sharper continuity-key scheme; persist/restore the long-horizon state across restart (P2 checkpoint slice).

### 2.20 `17` Evaluation Fidelity and Diagnostic Provenance — `helios_v2.evaluation`
- Completeness: `baseline_real` (read-only; corroborates execution truth since R32; consumes the `23` timeline).
- Responsibility: the sole read-only owner of evidence-driven evaluation, consequence-binding path outcomes, execution-truth corroboration (`corroborated`/`discrepant`/`unverifiable_no_timeline`), and diagnostic-provenance publication. Mutates no runtime state.
- Role in the loop: the last stage; rebuilds the internal-to-visible causal chain and now falsifies the self-reported outcome against the kernel execution timeline.
- Next step: richer discrepancy taxonomies and scoring depth once non-deterministic cognition produces variable paths; preserved-vs-resolved-vs-degraded continuity corroboration (wave_B); durable cross-run comparison of artifacts (depends on P2).

---

## 3. Infrastructure and capability owners

Not cognitive owners. They provide substrate the cognitive chain depends on.

### 3.1 `21` Unified Runtime Observability — `helios_v2.observability`
- Completeness: `infra_done`.
- Responsibility: structured `LogEvent` contract, severity/event-kind taxonomies, the `LogSink` protocol + first-version sinks, the sequence-stamping recorder, and the read-only `ExecutionTimelineView` + `ExecutionTimelineReconstructor` (the `23` substrate). Never an authoritative inter-owner transport.
- Role: default-off kernel instrumentation; the timeline view is the only sanctioned form for downstream timing-fact consumption.
- Next step: owner-level fine-grained emission (plan C) beyond kernel lifecycle, opened through this same owner when a later slice needs it.

### 3.2 `22` Runtime Composition Root — `helios_v2.composition`
- Completeness: `infra_done`.
- Responsibility: assembly-only wiring of the dependency gate, the canonical stage chain, owner-neutral first-version bridges, the optional recorder, and the opt-in channel/persistence/embedding seams into a runnable `RuntimeHandle`. Holds no cognitive policy; provides no degraded assembly path.
- Role: the only place that holds full wiring truth; owns `CANONICAL_STAGE_ORDER` / `CHANNEL_BOUND_STAGE_ORDER` and the owner-neutral bridges.
- Next step: as owners de-shim, replace the first-version bridges with the owners' real cross-owner contracts; keep assembly free of cognitive policy.

### 3.3 `25` LLM Inference Gateway — `helios_v2.llm`
- Completeness: `infra_done`.
- Responsibility: backend-neutral request/completion contracts, the named-profile registry, the injected provider protocol + first-version OpenAI-compatible provider (lazy SDK), network-free static readiness, and the opt-in live probe. Owns no cognition; never interprets completion text.
- Role: the capability the `11` thought owner consumes; binds per-consumer profiles via composition.
- Next step: additional bound consumers (for example `13` tool-call planning, `14` self-revision drafting) as those owners gain real generation needs.

### 3.4 `30` Channel Driver Subsystem — `helios_v2.channel` (+ `31` CLI driver — `helios_v2.channel.drivers.cli`)
- Completeness: `infra_done` (framework + CLI driver real; opt-in; not the default runtime).
- Responsibility: a Linux-driver-style transport owner — the uniform `ChannelDriver` protocol, registry, NAPI-style bounded inbound drain emitting QoS-tagged `RawSignal`, bounded outbound dispatch, real per-driver channel state, and fail-fast readiness. Transport only: not normalization (`02`), salience (`03`), selection (`13`), or content shaping (`16`).
- Role: when the channel-bound assembly is opted in, a local CLI round trip runs end to end (operator line → stimulus → cognition → externalizing decision → sink).
- Next step (wave_C): real external (network) drivers (QQ/voice/vision) and making a channel-bound assembly the default runtime; both are future requirements.

### 3.5 `33` Durable Experience Store — `helios_v2.persistence`
- Completeness: `infra_done` (opt-in).
- Responsibility: the `PersistedExperienceRecord`/`PriorExistenceSnapshot` contracts, the injected backend protocol (SQLite file + in-memory double), the `ExperienceStore` facade (append / recent-N / count / snapshot / similarity search), and the recency + semantic candidate providers. Durable append of the `15` continuity stream; deterministic recency or cosine-similarity re-entry into `10`. Never embeds text itself; never an authoritative inter-owner transport.
- Role: gives the system memory that survives a restart (FG-5.1); persisted experience re-enters the thought window.
- Next step (P2): latest-state checkpoint/restore for `18`/`09`/`14`; connect `06` memory items to the store; later, consolidation/forgetting policies and the durable substrate for P5 learning.

### 3.6 `34` Embedding Inference Gateway — `helios_v2.embedding`
- Completeness: `infra_done` (opt-in).
- Responsibility: backend-neutral embedding request/result contracts, named-profile registry, injected provider protocol + lazy OpenAI-compatible provider, fail-fast gateway, network-free static readiness, opt-in live probe. Owns no cognition; never interprets a vector.
- Role: turns text into a vector so the store can rank experience by semantic similarity; query/record embedding is injected into the store by composition (the store does not depend on this owner).
- Next step (P3 hinge): feed `03` novelty-from-memory (distance to nearest stored memory); re-embedding/backfill of pre-semantic records; an ANN index at scale.

---

## 4. Documentation owners

### 4.1 `19` Architecture Boundary and Owner Documentation
- Completeness: `docs_owner`.
- Responsibility: keep `ARCHITECTURE_BOUNDARIES.md` (and this owner map) aligned with runtime truth — owner boundaries, allowed dependencies, migration notes, prohibited shortcuts.
- Next step: update boundary truth in the same change set as every owner-wave closure (it currently tracks through R34).

### 4.2 `20` Brain Architecture Comparison and Scientific Grounding
- Completeness: `docs_owner`.
- Responsibility: keep `BRAIN_ARCHITECTURE_COMPARISON.md` aligned — cautious brain-function analogs, evidence categories, explicit non-goals, gap analysis, and the owner-wave roadmap.
- Next step: narrow/retire gaps as owner waves close; keep the wave roadmap aligned with the phase roadmap in the philosophy doc.

---

## 5. Whole-system reading (replaces the retired distance snapshots)

This section absorbs the aggregate "distance-to-final-goal" lens previously kept in the
retired `TOTAL_DISTANCE_TO_FINAL_GOAL.md` and `REQUIREMENT_DISTANCE_TO_FINAL_GOAL.md`, now kept
live here.

1. The system is architecturally real and owner-complete at a first-version level. It is not yet final-goal-complete.
2. The current heaviest remaining runtime distance is the de-shimming of `03-07`/`09-10`/`12` (phase `P3`) and outward execution closure (`13`/`16`, wave_C).
3. `wave_A_behavioral_truth` (evaluation falsifiability) closed at baseline with R32. `P2` (durable memory) opened with R33 and gained semantic recall with R34.
4. The next highest-leverage moves are: real `03` novelty-from-memory (P3 first slice, builds on R34), and the rest of P2 (state checkpoint/restore; `06` on the durable base).
5. The owners genuinely driven by real signals today are `02`, `08`, `11`, `18`, plus all infrastructure owners; everything else is honest baseline awaiting its de-shim wave.

## 6. Update rule

This document is a living owner reference. It MUST be updated in the same change set as any
requirement that materially changes an owner's responsibility, completeness, boundary, or next
step — the same discipline that governs `requirements/index.md` and the progress-flow maps.
The "Last synced" line at the top must name the most recent requirement reflected here.
