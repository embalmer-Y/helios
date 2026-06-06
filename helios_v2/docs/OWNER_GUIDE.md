# Helios v2 Owner Guide

> Status: living owner reference. Last synced: R46. Test baseline: 618 passed (network-free).
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
- Completeness: `baseline_real` (fully de-shimmed under the semantic-memory assembly: all five dimensions real — novelty since R35, uncertainty + social since R39, threat + reward since R40 — plus the aggregate judgment since R41; every `03` output is real, none constant).
- Responsibility: fast-path coarse salience (threat/reward/novelty/social/uncertainty + aggregate) per stimulus, through injected estimators. Does not own fine semantic interpretation, memory, or routing.
- Role in the loop: shapes downstream salience right after sensory; the appraisal batch feeds modulation and gating signals.
- Next step (staged P3 de-shim of this owner):
  1. **R35 — novelty from memory (shipped).** The `novelty` dimension is a real signal: `novelty = clamp(1 - max_similarity, 0, 1)`, where `max_similarity` is the highest cosine similarity between the embedded stimulus and any stored experience embedding (via the `34` embedding gateway + `33` store similarity search). `03` defines a narrow `MemorySimilaritySource` protocol and owns the novelty salience mapping in `MemoryGroundedDimensionEstimator`; composition injects an owner-neutral `MemoryGroundedSimilaritySource` returning the raw cosine fact (or `None`), so `03` imports neither the embedding nor persistence owner. Triggers on the semantic-memory opt-in (store + embedding both present); cold store / empty stimulus content yield the defined maximum novelty `1.0` (no gateway call for empty content); a runtime embedding/store failure is a hard stop (no constant fallback). Default and recency-only assemblies keep constant novelty `0.6`.
     - **Known first-version caveat (cross-register comparison):** the store currently holds only `15` result/continuity summaries, not the raw stimulus text, so R35 novelty compares the incoming *stimulus input* against past *result summaries* sharing the same embedding profile. This is directionally correct (shared content is captured by cosine) but is an input-vs-summary approximation, not a strict input-vs-input comparison. It must not be over-claimed as exact stimulus novelty.
  2. **Method B — apples-to-apples novelty (later slice).** Persist the raw stimulus text stream (a `15`/`33` extension or a dedicated stimulus log) so novelty compares stimulus-against-prior-stimuli in the same register, retiring the cross-register caveat above. This is a separate requirement because it touches the writeback/persistence owners, not `03`.
  3. **R39 — uncertainty + social (shipped).** `uncertainty` is grounded in retrieval ambiguity: `03` reads the top-two cosine similarities (via the owner-defined `RetrievalAmbiguitySource`, injected from composition over the same `34`/`33` substrate) and maps `uncertainty = clamp(1 - (n1 - n2), 0, 1)` over the normalized top-two (no comparable memory → `1.0`; one dominant match → low; several near-equal matches → high). This is a distinct read from novelty (familiar-but-ambiguous → low novelty, high uncertainty). `social` is grounded in transport provenance: `03` reads a bounded `social_presence` fact (via the owner-defined `SocialContextSource`; composition owns the channel-to-presence classification, external interactive-agent channel → high, internal body/background → 0) and maps `social = clamp(social_floor + social_gain * presence, 0, 1)`. Both mappings live in the owner-owned `GroundedDimensionEstimator`. **Honest grounding:** uncertainty is `B_functional_inspiration` (a retrieval-ambiguity proxy, not a calibrated confidence); social is a pure transport fact that does not need the embedding substrate and is bundled under the semantic opt-in only for one rollout switch (a later slice may enable it in the channel-bound assembly independently). The fast path stays deterministic, network-free, and LLM-free.
  4. **R40 — threat/reward from prototype embedding (shipped).** `threat`/`reward` are scored by the stimulus's maximum cosine similarity to owner-owned prototype phrase sets (`THREAT_PROTOTYPES`/`REWARD_PROTOTYPES`), embedded through the `34` substrate: `03` defines a `PrototypeSimilaritySource` protocol and maps `dimension = clamp(gain * max(0, max_cosine), 0, 1)` (positive correlation — proximity to a semantic anchor, the inverse of novelty's distance read; `None`/empty content → `0.0`); composition's `EmbeddingPrototypeSimilaritySource` embeds the owner-provided phrases once (cached) and returns the raw cosine, so `03` imports neither the embedding nor persistence owner. The prototype sets and mapping live in `03`. No cold-start (prototypes embedded at assembly time). **Honest grounding `C_engineering_hypothesis`:** the prototype phrase set is a hand-authored, English-centric PLACEHOLDER anchor, NOT a calibrated affective model; it must not be over-claimed as real threat/reward understanding. It is the surface a later slice replaces — P5 learning of the prototypes/gains, a `06` memory-affect grounding scoring threat/reward from the good/bad outcomes of similar past experience, or a slow `11`-LLM second-stage re-appraisal (a distinct owner concern from the fast `03` path). With all five dimensions now real, the constant aggregate-salience estimator (item 5) is the next sensible de-shim.
  5. **R41 — aggregate salience (shipped).** The aggregate judgment (`RapidSalienceVector.aggregate`) is now a real dimension-grounded convex combination of the five real dimensions via the owner-owned `WeightedAggregateEstimator`: `aggregate = clamp(sum(weight_k * dimension_k), 0, 1)` with first-version weights summing to 1.0 (`threat 0.25, reward 0.25, novelty 0.20, uncertainty 0.15, social 0.15`). Monotonic, deterministic, bounded, stateless; needs no injected fact source (a pure function of the dimensions). This closes the `03` owner P3 de-shim — every `03` output is now real. **Honest caveats:** the weights are a first-version PLACEHOLDER allocation (an engineering choice, not a calibrated importance prior; P5-learnable), and the aggregate inherits its inputs' grounding strength — while threat/reward are the R40 `C_engineering_hypothesis` anchor, the aggregate's threat/reward contribution is only as strong as that anchor (it strengthens automatically as the inputs are upgraded). Default/recency/offline keep constant aggregate `0.4`. Future: P5 weight learning, a model-assisted/non-linear or slow-`11`-LLM second-stage overall appraisal, affect/recency weighting.
  6. **Downstream coupling (shipped for novelty→`04`→`05`/`09`).** Real `03` salience already shapes the `04` neuromodulator state (R36) and through it `05` feeling (R38) and `09` gating (R37); with R40 the reward→dopamine and threat→cortisol channels are now driven by real signals too. Remaining: feed real threat/reward into the cortisol/inhibition hard gate and richer `05`/`06` coupling once they land; later affect-weight or recency-weight the dimensions. **Grounding-power ordering constraint:** while threat/reward remain the R40 `C_engineering_hypothesis` placeholder anchor, avoid granting them high-power downstream couplings (e.g. a cortisol/inhibition hard gate that can veto a fire) until they are upgraded to a stronger grounding (P5 / `06` memory-affect); a weak anchor must not gain veto power over cognition.

### 2.4 `04` Neuromodulator System — `helios_v2.neuromodulation`
- Completeness: `baseline_real` (levels appraisal-derived under the semantic-memory assembly, and since R43 they evolve across ticks through dual-timescale dynamics and resume across restart).
- Responsibility: independently modeled neuromodulator level state (DA/NE/5-HT/ACh/cortisol/oxytocin/opioid + excitation/inhibition) with explicit learned-parameter categories. Does not own feeling subjectivation or action.
- Role in the loop: the modulation layer that should bias gating thresholds, retrieval, and externalization intensity.
- Completeness detail: with `36` (P3 second de-shim) the constant update path is replaced under the semantic-memory assembly by the composition-provided `AppraisalDerivedNeuromodulatorUpdatePath`, which derives each channel's **instantaneous drive** as `clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)` (dopamine from reward+weak novelty, norepinephrine from novelty+uncertainty, cortisol from threat, others regressing to baseline). With `43` (the P2/P3 hinge) the owner adds **dual-timescale dynamics** on top: under the semantic assembly the update path becomes the owner-owned `DualTimescaleNeuromodulatorUpdatePath` (wrapping that drive path), per channel `next = clamp(prior + alpha_phasic*(drive-prior) + alpha_tonic*(baseline-prior))` (phasic fast, tonic slow; `0 < alpha_tonic < alpha_phasic <= 1`; under the `decay_speed_persistence` category, P5-learnable). The instantaneous drive stays owned by the injected path; the cross-tick carry/decay is the new `04`-owned semantic. `NeuromodulatorUpdatePath`/`update_state` gain an additive optional `prior_levels`/`prior_state` (default `None` reproduces the stateless behavior byte-for-byte); `NeuromodulatorRuntimeStage` holds the prior-tick state (like `09`/`18`) and exposes `seed_prior_state`. Cold start defaults prior to the tonic baseline (one step from baseline; no fabricated history); the integrator is bounded; an unstable alpha ordering is rejected at construction. The `04` state survives a restart through the R42 checkpoint (snapshot bumped to v2 with `neuromodulator_levels`). The default, recency-only, and offline assemblies keep the stateless constant path. Caveat: only novelty is a real `03` driver feeding the drive today (R35); the other four salience dimensions are still first-version constants.
- Next step: (1) ✅ dual-timescale tonic/phasic decay carrying prior-tick levels + cross-restart resumption — **delivered in R43**; (2) `P5` learning of the bounded sensitivity/alpha coefficients via reward-prediction-error (DA) and outcome feedback, keeping the equation shape; (3) cross-channel coupling (the declared `cross_channel_coupling_strength` category) beyond the first-version independent mapping; (4) downstream coupling — both `04` consumers are now real: norepinephrine couples into `09` gating (`37`) and the full `04` state drives `05` feeling (`38`); still pending are the cortisol/inhibition hard gate into `09` and additional channels (dopamine→retrieval/exploration) into their consumers (FG-1/FG-2); (5) de-shim the remaining four `03` dimensions so all neuromodulator drivers are real.

### 2.5 `05` Interoceptive Feeling Layer — `helios_v2.feeling`
- Completeness: `baseline_real` (feeling neuromodulator-derived under the semantic-memory assembly, and since R44 it evolves across ticks through dual-timescale persistence and resumes across restart).
- Responsibility: subjective body-feeling vector (valence/arousal/tension/comfort/fatigue/pain/social-safety) from neuromodulator state + internal signals; soft-modulation output only. Does not own neuromodulator state or memory.
- Role in the loop: the "what does my body state feel like" layer feeding conscious content and continuity.
- Completeness detail: with `38` (P3 fourth de-shim) the constant construction shim is replaced under the semantic-memory assembly by the owner-private `NeuromodulatorDerivedFeelingConstructionPath` (each dimension `clamp(baseline + sum(coupling_k * level_k))`, the **instantaneous target** feeling). With `44` (the P2/P3 hinge, the `05` mirror of R43) the owner adds **dual-timescale persistence**: under the semantic assembly the construction path becomes the owner-owned `PersistentFeelingConstructionPath` (wrapping the R38 target path), per dimension the same form as R43 `next = clamp(prior + alpha_phasic*(target-prior) + alpha_tonic*(baseline-prior))` (under the `feeling_persistence` category, P5-learnable; same constants as R43 so the two affect owners share one decay timescale). The instantaneous target stays owned by the injected R38 path; the cross-tick carry is the new `05`-owned semantic. `FeelingConstructionPath`/`update_state` gain an additive optional `prior_feeling`/`prior_state` (default `None` reproduces stateless behavior byte-for-byte); `InteroceptiveFeelingRuntimeStage` holds the prior-tick state (like `04`/`09`/`18`) and exposes `seed_prior_state`. Cold start defaults prior to the baseline feeling. The `05` feeling survives a restart through the checkpoint (snapshot bumped to v3 with `feeling`). Default/recency/offline assemblies keep the constant feeling. Caveat: the real `05` feeling does not yet measurably shape `06`/behavior, and real interoceptive `internal_signals` are not yet integrated.
- Next step: (1) ✅ dual-timescale feeling persistence + cross-restart resumption — **delivered in R44**; (2) integrate real internal body/interoceptive signals once a real interoceptive source exists — an unowned gap (`gap_interoceptive_signal_source`); (3) `P5` learning of the bounded coupling/alpha coefficients; (4) feed the real feeling into `06` memory-affect tagging, conscious content, and behavior so body-state causally matters downstream (FG-2); (5) de-shim the remaining `03` dimensions so all upstream drivers are real.

### 2.6 `06` Memory Affect and Replay — `helios_v2.memory`
- Completeness: `baseline_real` (formation de-shimmed and memory durable under the semantic-memory assembly; inputs above `05` still depend on the opt-in).
- Responsibility: affect-tagged memory formation and replay-candidate surfacing with forced-consolidation constraints. Does not own retrieval planning, workspace promotion, or identity writeback.
- Role in the loop: forms episodic/affect memory and supplies replay candidates toward the workspace.
- Completeness detail: `45` (P2 closeout / P3 mid-chain) closes both `06` shims at once. Formation: an owner-owned `AffectGroundedMemoryFormationPath` replaces the constant shim under the semantic-memory assembly, forming affect-tagged memory from the real `05` `InteroceptiveFeelingState` (the item's `affect_tag` is the genuine felt body-state, not a constant), with an owner-owned episodic-vs-autobiographical family mapping (mismatch evidence → autobiographical). Salience gate: an owner-owned `SalienceGatedReplayCandidateSelector` computes a bounded affect-intensity from the real feeling (arousal/tension/pain) and mismatch, setting each candidate's `forced_consolidation` + `priority_hint` from it (threshold/weights under the declared `consolidation_policy`/`replay_priority_policy` learned-parameter categories, P5-learnable), so a flat low-affect tick consolidates nothing and a high-affect or high-mismatch tick consolidates. Durability: an owner-neutral `MemoryRecordBridge` + a `RuntimeHandle._persist_memory` carry seam (mirroring `_persist_experience`) durably persists exactly the `forced_consolidation` items as `record_kind="affect_memory"`, embedded at write, co-residing with the `15` stream. Recall: reuses the `34` semantic recall surface, so affect-memory is recallable through `10` and survives a restart. `06` imports neither persistence nor embedding; the carry seam re-derives no decision (filters by the flag `06` set). Default/recency assemblies keep the constant shim. Caveat: memory content shaping is still minimal (binding-context content only); dedup/merge not done this slice.
- Next step (P2/P3): (1) ✅ formation de-shim + durable store — **delivered in R45**; (2) deduplication and same-memory merge/consolidation (under `consolidation_policy`, bounded, owner-owned), retiring this slice's no-dedup constraint; (3) drive formation from the real `05` feeling beyond the affect tag, and feed real `06` candidates into `07`; (4) same-register novelty once R35 method B (persist the raw stimulus) lands.

### 2.7 `07` Workspace Competition and Working State — `helios_v2.workspace`
- Completeness: `baseline_real` (competition + attention bottleneck de-shimmed under the semantic-memory assembly; first-version weights/bound, single-source candidates).
- Responsibility: candidate-set competition and short-lived working-state retention; promotion boundary for memory-derived content. Does not own conscious commitment or retrieval.
- Role in the loop: the attentional bottleneck (FPN-style competition) that decides what reaches conscious content.
- Completeness detail: `46` (P3 mid-chain, building on R45's real `priority_hint`) closes both `07` shims. Competition: an owner-owned `SalienceWeightedWorkspaceCompetitionPath` scores each candidate as a bounded function of the real `06` `priority_hint` + the real `05` feeling salience (`score = clamp(0.6*priority + 0.4*feeling_salience)`), replacing the constant `0.95`; every replay candidate stays in the published set (forced flag + feeling provenance preserved, so owner invariants hold). Attention bottleneck: an owner-owned `BoundedAttentionRetentionPath` retains only the top-K (`max_retained=3`, under `working_state_update_policy`) into the working state with a deterministic tie-break and a never-empty guarantee, replacing the retain-everything shim. Brain-aligned semantic (owner-confirmed): "consolidated" (a `06`-forced candidate, persisted long-term) is distinct from "held in attention" (the bounded working state) — a forced candidate may lose the attention competition and not be held this tick, while remaining in the candidate set (still reaching `08`) and still persisted. Opt-in on the same semantic-memory opt-in as R45; default/non-semantic assemblies keep the constant-score / retain-everything shim. No contract change; `07` imports no other owner; existing invariants still fail fast.
- Next step (P3 / P5): (1) ✅ real competition + attention bottleneck — **delivered in R46**; (2) P5 learning of the competition weights and the retention bound; (3) a sharper real `08` commitment path consuming the bounded working state (top-1 reportable content), the next mid-chain de-shim; (4) multi-source competition once sources beyond `06` are real.

### 2.8 `08` Reportable Conscious Content — `helios_v2.consciousness`
- Completeness: `baseline_real` (owner semantics rel. complete, but upstream 06/07 and the commitment path `FirstVersionConsciousCommitmentPath` are still first-version shim, so it is colored baseline under the same rule as 03-07).
- Responsibility: commit globally reportable conscious content (or explicit no-commit) from workspace outputs, with a non-reach-through upstream content-material boundary. Does not own thought generation or gating.
- Role in the loop: the "what am I consciously aware of this cycle" commitment that gating and prompt assembly consume.
- Next step: a real commitment path once upstream 06/07 are de-shimmed; tie committed content more strongly to downstream behavioral/diagnostic consequence.

### 2.9 `09` Thought Gating and Continuation Pressure — `helios_v2.thought_gating`
- Completeness: `baseline_real` (most inputs shim; arousal input now real under the semantic-memory assembly).
- Responsibility: the sole owner of thought-window firing decisions and multi-tick continuation-pressure carry; compact gate observability. Does not collapse into retrieval or thought generation.
- Role in the loop: decides whether a tick fires a thought path, and carries continuation pressure forward.
- Completeness detail: with `37` (P3 third de-shim) the `09` gate decision is the first real consumer of an `04` neuromodulator level. The owner gained an `ArousalAwareThoughtGatePath` and one additive optional raw-fact field `neuromodulatory_arousal` on `ThoughtGateSignalSnapshot`; under the semantic-memory assembly composition forwards the real `04` norepinephrine level into it (raw fact only — the arousal-to-gate mapping is owned here, not in composition). The path adds one non-negative bounded term `arousal_gain * arousal` (first-version `0.15`, under the `gate_policy` category) to the gate score; it is monotonic, deterministic, stateless, and structurally never a hard gate (weight `0.15 < fire_threshold 0.55`, additive non-negative). The other gate-signal inputs (`global_activation_level`, `workload_pressure`, `temporal_signal`, `drive_urgency_signal`, `dmn_available`) remain first-version constants; when `neuromodulatory_arousal` is `None` the path reproduces the first-version behavior byte-for-byte (default/recency/offline unchanged).
- Next step: (1) de-shim the other gate-signal inputs from their real owners (for example `global_activation_level` from a de-shimmed `07` workspace), each as its own slice; (2) couple the cortisol/inhibition hard-gate-eligibility channels (which may legitimately suppress a fire, with their own safety semantics) once `03` threat is real; (3) P5 learning of `arousal_gain` and the gate thresholds under the `gate_policy` category; (4) deepen multi-tick carry; (5) persist/restore continuation pressure across restart — **landed in R42**: `09` continuation pressure now survives a restart through the `42` checkpoint (opt-in).

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
- Next step (wave_B / P6): deeper long-horizon governed self-evolution (developmental, not only audited patches); persist/restore identity state across restart (P2 checkpoint slice — `14` identity state is not yet cross-tick in-process, so it joins the `42` checkpoint once it carries state); eventually the governed self-revision path of P6.

### 2.18 `15` Experience Writeback and Autobiographical Consolidation — `helios_v2.experience_writeback`
- Completeness: `baseline_real` (its continuity stream is now durably persisted via `33`).
- Responsibility: the sole owner of execution-result writeback, continuity-evidence packets, and consolidation-candidate handoff. Does not own planner/governance decisions or raw storage backends.
- Role in the loop: classifies each tick's outcome into a continuity packet and feeds the `15 → 06` loop; its stream is what `33` persists.
- Next step (wave_B): stronger long-range carry and re-entry; richer consolidation once `06` shares the durable base.

### 2.19 `18` Subjective Autonomy and Proactive Evolution — `helios_v2.autonomy`
- Completeness: `deep_real` (`relatively_complete`; cognition-derived since R29; includes the `24` long-horizon continuity-thread layer).
- Responsibility: proactive-drive integration, bounded disposition selection, deferred-continuity publication, and long-horizon continuity threads (recurrence reinforcement, conflict arbitration, owner-owned `LongHorizonContinuityState`). May request proactive externalization semantically but never executes a channel path.
- Role in the loop: integrates real cognition into a proactive disposition (act → externalize, no-action → reflect/defer) and forms/reinforces continuity threads across ticks.
- Next step (wave_B): richer long-horizon motive evolution beyond bounded carry; sharper continuity-key scheme; persist/restore the long-horizon state across restart — **landed in R42**: `18`/`24` deferred records and continuity threads now survive a restart through the `42` checkpoint (opt-in).

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
- Next step (P2): latest-state checkpoint/restore for `18`/`09`/`14` — **`09`/`18`/`04`/`05` landed (R42/R43/R44)**, `14` joins once it carries cross-tick state; ✅ connect `06` memory items to the store — **delivered in R45** (affect-memory co-resides with the `15` stream via the `record_kind` discriminator); later, consolidation/forgetting policies and the durable substrate for P5 learning.

### 3.6 `34` Embedding Inference Gateway — `helios_v2.embedding`
- Completeness: `infra_done` (opt-in).
- Responsibility: backend-neutral embedding request/result contracts, named-profile registry, injected provider protocol + lazy OpenAI-compatible provider, fail-fast gateway, network-free static readiness, opt-in live probe. Owns no cognition; never interprets a vector.
- Role: turns text into a vector so the store can rank experience by semantic similarity; query/record embedding is injected into the store by composition (the store does not depend on this owner).
- Next step (P3 hinge): feed `03` novelty-from-memory (distance to nearest stored memory); re-embedding/backfill of pre-semantic records; an ANN index at scale.

### 3.7 `42` Durable Runtime-Continuity Checkpoint — `helios_v2.continuity_checkpoint`
- Completeness: `infra_done` (opt-in).
- Responsibility: the `RuntimeContinuitySnapshot` contract (an owner-neutral serializable projection of the genuinely cross-tick continuity state — `09` continuation pressure plus the `18`/`24` long-horizon continuity, reusing those owners' own contracts verbatim), the `CheckpointStoreBackend` protocol (single-row SQLite file backend + in-memory double), and the `ContinuityCheckpointStore` facade (`save_latest` replace / `load_latest` or explicit absence). Keeps one latest-state snapshot (not an append log); computes and re-interprets no continuity decision.
- Role: gives the system cross-restart continuity of "where my thinking was / the tendencies I keep returning to" (FG-5.1). On an opt-in `assemble_runtime(continuity_checkpoint=...)` it saves after each tick and restores at startup (after the fail-fast gate), seeding the `09`/`18` stages' prior cross-tick state through explicit owner-neutral stage seed seams. Independent of `33`/`34`.
- Next step (P2): fold `04`/`05` (once they carry dual-timescale state) and `14` identity into the versioned snapshot additively; fold `06` once it joins the durable base.

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
3. `wave_A_behavioral_truth` (evaluation falsifiability) closed at baseline with R32. `P2` (durable memory) opened with R33, gained semantic recall with R34, and gained cross-restart continuity-state resumption with R42 (`09` continuation pressure + `18`/`24` long-horizon continuity).
4. The next highest-leverage moves are: real `03` novelty-from-memory (P3 first slice, builds on R34), and the rest of P2 (`04`/`05`/`14` into the checkpoint once they carry dual-timescale/persisted state; `06` on the durable base).
5. The owners genuinely driven by real signals today are `02`, `08`, `11`, `18`, plus all infrastructure owners; everything else is honest baseline awaiting its de-shim wave.

## 6. Update rule

This document is a living owner reference. It MUST be updated in the same change set as any
requirement that materially changes an owner's responsibility, completeness, boundary, or next
step — the same discipline that governs `requirements/index.md` and the progress-flow maps.
The "Last synced" line at the top must name the most recent requirement reflected here.
