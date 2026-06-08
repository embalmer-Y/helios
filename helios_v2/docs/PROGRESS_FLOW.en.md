# Helios v2 Module Progress Flow (English)

> Status: living progress map. MUST be updated in the same change set as any requirement that
> materially alters owner maturity, the runtime stage chain, or owner boundaries.
> Last synced: R68 (`14` identity cross-tick governance carry state: `GovernanceCarryState` wraps identity_state_snapshot, bounded trace history, accepted/rejected revision counts; `IdentityGovernanceRuntimeStage` advances carry state post-tick; `FirstVersionIdentityGovernanceRequestBridge` injects carry data via `carry_state_provider`, falls back to bootstrap constant byte-identical when no provider). Test baseline: 762 passed. HEAD-era: R68. Doc clarification (post-R41): 16 externalization labelled as non-authoritative premotor-prep draft.
> Companion: `PROGRESS_FLOW.zh-CN.md` (Chinese) must be updated together with this file.

## 1. Purpose

This document is the module-level progress map for Helios v2. It shows the canonical runtime
stage chain (the `CANONICAL_STAGE_ORDER` executed each tick) plus the supporting
infrastructure owners, color-coded by real implementation maturity, and marks the one
remaining structural gap (real external network transport: the local CLI round trip works
end to end through an opt-in assembly, but network drivers and a default channel-bound
runtime are still future).

It is intentionally implementation-facing: the colors reflect shipped code and validation
evidence, not planned architecture quality, and must match the `Maturity` column in
`requirements/index.md`.

For the detailed by-owner reference (each owner's responsibility, role in the loop,
completeness, and next development/optimization step), see the companion `OWNER_GUIDE.md`.

## 2. Legend

- Deep & real (green): LLM-driven cognition or `relatively_complete` owner behavior.
- Baseline (yellow): owner is real with fail-fast contracts and tests, but its inputs are
  still composition-injected deterministic shim.
- Infrastructure done (blue): supporting owner shipped (kernel, gateway, observability,
  composition, evaluation substrate, continuity threads).
- Gap, no owner yet (red, dashed): a first-class concept that is consistently referenced but
  has never been assigned an owner.

> Perspective note: this map's colors reflect "is it driven by real signals", which is a different
> lens from `index.md`'s "owner-boundary maturity". `08` is exactly where the two differ — by the
> owner-boundary lens it is `relatively_complete` in `index.md` (its owner semantics are rel.
> complete, and an upstream gap does not downgrade its own maturity), but by this map's
> real-signal lens its upstream 06/07 and commitment path are still first-version shim, so it is
> colored baseline. Both documents are correct; this is not a conflict.

## 3. Flow

```mermaid
flowchart TD
    classDef deep fill:#b7e1cd,stroke:#2e7d32,color:#1b5e20
    classDef base fill:#fff2cc,stroke:#bf9000,color:#7f6000
    classDef infra fill:#cfe2f3,stroke:#1c4587,color:#0b3d91
    classDef gap fill:#f4cccc,stroke:#990000,color:#660000,stroke-dasharray: 5 5

    EXT["External stimulus: real source injectable - R59 external_signal_source / CLI bound / QQ voice future"]:::base
    BODY["Internal body signal - interoceptive source: R50 producer delivered (helios_v2.interoception, compute/runtime pressure, opt-in); R51 05 consumes it to shape feeling"]:::base
    S02[02 Sensory Ingress - relatively complete]:::deep
    S03["03 Rapid Salience Appraisal - fully real (semantic): 5 dims + aggregate"]:::base
    S04["04 Neuromodulator System - appraisal-derived + dual-timescale (semantic)/evolves cross-tick"]:::base
    S05["05 Interoceptive Feeling - neuromodulator-derived + dual-timescale (semantic)/evolves cross-tick; R51 consumes real interoceptive pressure to shape feeling"]:::base
    S06["06 Memory Affect and Replay - formation de-shimmed + durable/semantic recall + recalled as multi-candidate (R52) + content from real percept (R60) + mismatch grounded in real novelty (R61)"]:::base
    S07["07 Workspace Competition - real competition (reads real 05 feeling) + bounded attention bottleneck + real multiplicity (R52, semantic)"]:::base
    S08["08 Reportable Conscious Content - real ignition commitment (semantic); R52 ignites winner over real multiplicity; upstream 06/07 de-shimmed"]:::base
    S09["09 Thought Gating - all inputs real - arousal + activation + workload + temporal/DMN + drive_urgency + selected_stimuli(R63) / no constant shim remains"]:::base
    S10["10 Directed Retrieval - recall-intent from real 11 handoff (semantic)/candidate source real"]:::base
    S16P[16 Embodied Prompt Contract - baseline]:::base
    S16O["16 Outward Expression Draft - baseline/draft-only (non-authoritative)"]:::base
    S16E["16 Outward Externalization Draft - non-authoritative premotor-prep draft (planner 13 + channel 30 hold execution)"]:::base
    S11[11 Internal Thought Loop - REAL LLM-driven]:::deep
    S12[12 Action Externalization - baseline]:::base
    S13[13 Planner Bridge - baseline/shim channel state]:::base
    S14[14 Identity Governance - baseline]:::base
    S15[15 Experience Writeback - baseline]:::base
    S18[18 Subjective Autonomy - rel. complete/cognition-derived]:::deep
    S17[17 Evaluation - baseline/corroborates execution truth]:::base
    CH["30 Channel Driver Subsystem + 31 CLI driver - real local round trip, opt-in"]:::infra

    S02 --> S03 --> S04 --> S05 --> S06 --> S07 --> S08 --> S09 --> S10
    S10 --> S16P --> S16O --> S16E --> S11
    S11 --> S12 --> S13 --> S14 --> S15 --> S18 --> S17
    EXT -. inbound transport (CLI bound; opt-in assembly) .-> CH
    BODY -. interoceptive signal .-> S02
    S13 -. accepted decision .-> CH
    S16E -. delivery draft .-> CH
    CH -. inbound RawSignal -> sensory (opt-in assembly) .-> S02
    CH -. real outbound transport to same external endpoint (CLI bound) .-> EXT
    S15 -. experience writeback loop .-> S06

    LLM[25 LLM Inference Gateway - infra done]:::infra
    LLM --> S11

    K01[01 Runtime Kernel - rel. complete]:::infra
    OBS[21 Observability Timeline - done]:::infra
    COMP[22 Composition Root - done]:::infra
    EV23[23 Timeline-aware Eval - done]:::infra
    TH24[24 Continuity Threads - done, now active]:::infra
    PER[33 Durable Experience Store - infra done, opt-in]:::infra
    EMB[34 Embedding Gateway - infra done, opt-in]:::infra
    CKPT[42/43/44 Continuity Checkpoint - infra done, opt-in]:::infra
    K01 -. startup gate + dispatch .-> S02
    OBS -. per-tick timeline .-> EV23
    EV23 --> S17
    TH24 --> S18
    COMP -. assembles all 19 stages .-> K01
    S15 -. durable append (opt-in persistence) .-> PER
    S06 -. affect-memory persist (opt-in semantic, salience-gated) .-> PER
    PER -. recency or semantic re-entry across restart (opt-in) .-> S10
    EMB -. embed-at-write + embed-at-query (opt-in semantic) .-> PER
    S09 -. continuation pressure (save after tick) .-> CKPT
    S18 -. deferred records + threads (save after tick) .-> CKPT
    S04 -. neuromodulator levels (save after tick, R43) .-> CKPT
    S05 -. feeling (save after tick, R44) .-> CKPT
    CKPT -. restore-at-startup seeds prior cross-tick state (opt-in) .-> S09
    CKPT -. restore-at-startup seeds prior cross-tick state (opt-in) .-> S18
    CKPT -. restore-at-startup seeds prior 04 levels (opt-in, R43) .-> S04
    CKPT -. restore-at-startup seeds prior 05 feeling (opt-in, R44) .-> S05
```

## 4. Status Summary

- Cognition main chain (02 to 17) runs end to end; 560 tests pass, network-free, plus real
  LLM smoke.
- Deep & real owners: 02 sensory, 11 internal thought (real LLM-driven
  cognition core), 18 autonomy (cognition-derived), plus infrastructure (01, 21, 22, 23, 24,
  25, 33, 34, 42).
  (Note: 08 reportable conscious content is owner-semantically rel. complete, but its upstream
  06/07 and commitment path are still first-version shim, so it is colored baseline under the same
  rule as 03-07 and no longer counted deep & real.)
- P3 began (R35): the `03` appraisal owner's novelty dimension is now a real signal under the
  semantic-memory assembly (novelty = 1 - max cosine similarity of the stimulus to stored
  experience, via the 34 embedding substrate + 33 store), the first cognitive consumer of the
  embedding base. `03` owns the novelty salience mapping; composition injects an owner-neutral
  similarity-fact source, so `03` imports neither the embedding nor persistence owner. The
  other four `03` dimensions stay shim (later P3 slices); default and recency-only assemblies
  keep constant novelty 0.6. First-version comparison is cross-register (stimulus vs 15 result
  summaries), noted and not over-claimed.
- P3 second de-shim (R36): the `04` neuromodulator owner is now the first real downstream
  consumer of `03` salience. Under the semantic-memory assembly the constant update path is
  replaced by an appraisal-derived one (composition-provided, conforming to the owner's
  `NeuromodulatorUpdatePath` protocol; the engine and contracts are unchanged): the batch is
  aggregated by per-dimension max, then each channel is `clamp(tonic_baseline + sum(sensitivity
  * salience), legal_min, legal_max)` - dopamine from reward (and weak novelty), norepinephrine
  from novelty and uncertainty, cortisol from threat, others regressing to tonic baseline. The
  derivation is deterministic, bounded (no NN, no divergence), and stateless (no prior-tick
  carry). Default, recency-only, and offline assemblies keep the constant path. Deferred:
  dual-timescale decay (prior-tick carry), P5 coefficient learning, cross-channel coupling, and
  downstream coupling into a de-shimmed 05/09.
- P3 third de-shim (R37): the `09` thought-gating decision is now the first real consumer of an
  `04` neuromodulator level. Under the semantic-memory assembly composition forwards the real
  `04` norepinephrine level into the gate-signal snapshot as a raw `neuromodulatory_arousal`
  fact, and the `09` owner's new arousal-aware gate path adds a bounded non-negative term
  (`arousal_gain = 0.15`) so elevated arousal measurably raises fire propensity. The mapping is
  owned by `09` (composition forwards the raw fact only), monotonic, deterministic, stateless,
  and structurally never a hard gate (0.15 < the 0.55 fire threshold; additive non-negative so
  it cannot suppress an otherwise-justified fire). The other gate-signal inputs stay
  first-version constants; with `neuromodulatory_arousal=None` the path is byte-for-byte the
  first-version path, so default/recency/offline assemblies are unchanged. Deferred:
  cortisol/inhibition hard gate, 04->05 feeling coupling, and de-shimming the other gate inputs
  (e.g. global_activation_level from 07).
- P3 fourth de-shim (R38): the `05` interoceptive feeling vector is now a real bounded function
  of the `04` neuromodulator state, bringing `04`'s second downstream consumer to real (with R37,
  both `09` gating and `05` feeling now consume the real `04` state). The constant feeling shim is
  replaced under the semantic-memory assembly by an owner-private
  `NeuromodulatorDerivedFeelingConstructionPath` in `helios_v2.feeling` (the channel->dimension
  mapping lives in `05` itself, since subjectivizing neuromodulator state into feeling is this
  owner's whole reason to exist; engine/contracts unchanged, no new bridge, no stage reorder). Each
  dimension = clamp(baseline + sum(coupling * level)): valence +DA/opioid/5-HT -cortisol, arousal
  +NE/excitation, tension +cortisol/NE, comfort +opioid/oxytocin/5-HT -cortisol, pain_like
  +cortisol -opioid, social_safety +oxytocin/5-HT -cortisol, fatigue +inhibition -excitation
  (weak). Deterministic, bounded (clamped to legal range), stateless (no prior-tick feeling).
  Default/recency/offline keep the constant feeling. Deferred: dual-timescale feeling persistence,
  real interoceptive-signal integration, and feeding the real feeling into 06/behavior (FG-2).
- P3 fifth de-shim (R39): two more `03` dimensions are real, so three of five (novelty, uncertainty,
  social) now ground in real facts. `uncertainty` reads retrieval ambiguity over the 34/33 substrate
  (top-two cosine margin: one dominant match -> low; several near-equal matches -> high; a distinct
  read from novelty, so familiar-but-ambiguous gives low novelty + high uncertainty). `social` reads
  transport provenance (external interactive-agent channel like the CLI operator -> high; internal
  body/background -> 0). Both mappings live in the owner-owned `GroundedDimensionEstimator`;
  composition supplies only raw facts (03 imports neither embedding, persistence, nor channel).
  Honest grounding: uncertainty is B_functional_inspiration (a proxy, not calibrated confidence);
  social is a pure transport fact bundled under the semantic opt-in only for one switch. The fast
  path stays deterministic, network-free, LLM-free. threat/reward stay constant pending R40
  (network-free prototype-embedding, weaker C_engineering_hypothesis grounding). Default/recency/
  offline keep constant uncertainty 0.3 / social 0.0; novelty unchanged.
- P3 sixth de-shim (R40): the last two `03` dimensions are real, so all five (novelty, uncertainty,
  social, threat, reward) now ground in real facts and the `04` reward->dopamine and
  threat->cortisol channels are driven by real signals on every channel (03 -> 04 -> 05/09 is now
  real end to end). threat/reward are scored by the stimulus's max cosine to owner-owned prototype
  phrase sets (THREAT_PROTOTYPES/REWARD_PROTOTYPES), embedded through the 34 substrate; 03 maps
  dimension = clamp(gain * max(0, max_cosine)) (positive correlation, proximity to a semantic
  anchor; None/empty -> 0). The prototype sets + mapping live in 03; composition's
  EmbeddingPrototypeSimilaritySource embeds the owner-provided phrases once and returns raw cosine
  (03 imports neither embedding nor persistence). No cold-start (prototypes embedded at assembly).
  HONEST GROUNDING C_engineering_hypothesis: the prototype set is a hand-authored, English-centric
  PLACEHOLDER anchor, not a calibrated affective model; it must not be over-claimed and is the
  surface a later P5 / 06 memory-affect / slow-LLM-re-appraisal slice replaces. Default/recency/
  offline keep constant threat 0.2 / reward 0.1; novelty/uncertainty/social unchanged. With all five
  dimensions real, the constant aggregate-salience estimator is the next sensible de-shim.
- P3 03-owner closeout (R41): the `03` aggregate judgment (RapidSalienceVector.aggregate) is now a
  real dimension-grounded convex combination of the five real dimensions (owner-owned
  WeightedAggregateEstimator: aggregate = clamp(sum(weight_k * dim_k)), first-version weights
  threat 0.25 / reward 0.25 / novelty 0.20 / uncertainty 0.15 / social 0.15, summing to 1.0), so
  EVERY 03 output (five dimensions + aggregate) is real under the semantic assembly, none constant.
  Monotonic, deterministic, bounded, stateless; needs no injected fact source (pure function of the
  dimensions). Honest caveats: the weights are a first-version PLACEHOLDER allocation (P5-learnable),
  and the aggregate inherits its inputs' grounding (threat/reward still the R40 C_engineering_hypothesis
  anchor). Default/recency/offline keep constant aggregate 0.4; the five dimensions unchanged. Next
  for 03: P5 weight/coefficient learning and model-assisted overall appraisal.
- Baseline owners (the majority): 03-07, 09-10, 12-17 (excluding 13's planner judgment which
  is real) - owners are real with contracts and tests, but their inputs are still
  composition-injected deterministic shim. In the default assembly 13's channel
  descriptor/status snapshots are still shim-injected; in the opt-in channel-bound assembly
  they come from the real `30` channel-state snapshot.
- wave_A behavioral truth closed at baseline (R32): the 17 evaluation owner now corroborates
  the prior tick's self-reported consequence outcome against that same tick's 21 execution
  timeline and publishes a `corroborated`/`discrepant`/`unverifiable_no_timeline` verdict,
  escalating contradictions to a `consequence_discrepancy` warning. The causal chain is now
  falsifiable against execution truth, not self-report alone. 17 stays baseline because its
  inputs remain shim; the corroboration is strictly additive (no scoring redesign).
- P2 opened (R33) and deepened (R34): a durable experience-store owner (33) persists the 15
  continuity stream to a SQLite file and, on an opt-in persistent assembly, surfaces it back
  through the 10 directed-retrieval candidate path so a prior session's experience re-enters
  the thought window after a process restart. With R34 an embedding capability owner (34,
  mirroring the 25 LLM gateway) embeds each record at write and recall is now semantic
  (bounded cosine similarity, `source="experience_store_semantic"`) rather than recency-only,
  so the system recalls experience relevant to the current query across restarts. Both are
  opt-in and default-off: the default assembly is byte-for-byte unchanged. Persistence owner
  never imports the embedding owner (query embedding is injected). `experience_store_ready` /
  `embedding_profile_ready` fail fast when their backends/profiles are not ready; semantic
  memory requires a durable store (else CompositionError); an embedding failure is a hard stop
  with no recency fallback.
- Transport owner now real for CLI (30 + 31): the channel driver subsystem framework plus the
  first concrete `CliChannelDriver` are shipped and wired through an opt-in 21-stage
  channel-bound assembly. A real local round trip works end to end: an operator line drains
  into a QoS-tagged RawSignal, sensory normalizes it, the cognition chain runs, and an
  externalizing decision is dispatched to the CLI sink. The default 19-stage assembly is
  unchanged.
- Remaining structural gaps: real external network transport (dashed EXT <-> CH; network
  drivers QQ/voice/vision and a default channel-bound runtime are future), and the rest of P2
  (R42 now checkpoints/restores the genuinely cross-tick `09`/`18`/`24` continuity; `06`/`04`/
  `05`/`14` are not yet durable — `04`/`05`/`14` only become checkpointable once their
  dual-timescale/persisted carry lands, and `06` memory items still need the durable base). The
  P2->P3 hinge is in place: real `03` novelty-from-memory builds on the R34 embedding substrate.
- The experience-writeback loop (15 -> 06) is implemented in-process, and with R33 the 15
  stream is now also durably persisted and re-entrant across restarts.
- P2 third slice (R42): a durable runtime-continuity checkpoint owner (42,
  `helios_v2.continuity_checkpoint`) keeps ONE latest-state snapshot of the genuinely cross-tick
  continuity state — the `09` continuation-pressure state and the `18`/`24` long-horizon
  continuity (deferred records + threads), reusing those owners' own contracts verbatim — in a
  single-row SQLite file (or an in-memory double). On an opt-in
  `assemble_runtime(continuity_checkpoint=...)` the runtime saves the latest snapshot after each
  tick (owner-neutral carry, mirroring `_persist_experience`, reading only published stage-result
  values) and restores it at startup (after the fail-fast gate), seeding the `09` and `18` stages'
  prior cross-tick state through explicit owner-neutral stage seed seams, so after a process
  restart against the same file the system resumes its prior continuation pressure and continuity
  threads instead of starting inert (advancing FG-5.1). Independent of 33/34 (a different state).
  Reconstruction runs the owners' own validation; a cold store keeps the inert defaults; a
  corrupt snapshot fails fast on load; `continuity_checkpoint_ready` fails fast on an
  un-initializable backend; no degraded path once enabled. `04`/`05`/`14`/`06` state stays out of
  scope (not cross-tick in-process today; the snapshot is versioned for additive extension).
  Default/33/34/channel-bound assemblies byte-for-byte unchanged when off.
- P2/P3 hinge (R43): `04` neuromodulator state now evolves across ticks. Under the semantic
  assembly the `04` update path is replaced (from stateless) by an owner-owned dual-timescale
  leaky-integrator (`DualTimescaleNeuromodulatorUpdatePath` wrapping the R36 instantaneous drive
  path): per channel `next = clamp(prior + alpha_phasic*(drive-prior) + alpha_tonic*(baseline-prior))`,
  phasic fast and tonic slow (`0 < alpha_tonic < alpha_phasic <= 1`, under the
  `decay_speed_persistence` category, P5-learnable). The instantaneous drive stays owned by the
  injected path; the cross-tick carry/decay is the new `04`-owned semantic. `NeuromodulatorUpdatePath`
  /`update_state` gain an additive optional `prior_levels`/`prior_state` (default `None` reproduces
  the stateless behavior byte-for-byte); `NeuromodulatorRuntimeStage` holds the prior-tick state
  (like 09/18) and exposes `seed_prior_state`. Cold start (no prior / cold checkpoint) defaults
  prior to the tonic baseline (one step from baseline; no fabricated history); the integrator is
  bounded (clamped, alpha in (0,1]); an unstable alpha ordering is rejected at construction. The
  R42 snapshot is bumped to version 2 with a `neuromodulator_levels` field, so `04` survives a
  restart (save reads the published levels, restore seeds the stage); a version mismatch or corrupt
  levels hard-stop on load (no v1 migration). Default/recency/offline keep the stateless constant
  `04`. Deferred: cross-channel coupling, P5 coefficient learning, cortisol/inhibition hard gate.
- P2/P3 hinge (R44): `05` interoceptive feeling now evolves across ticks (the `05` mirror of R43,
  completing the affect pair). Under the semantic assembly the `05` construction path is replaced
  (from stateless) by an owner-owned `PersistentFeelingConstructionPath` (wrapping the R38
  instantaneous neuromodulator-derived target path), per dimension the same form as R43:
  `next = clamp(prior + alpha_phasic*(target-prior) + alpha_tonic*(baseline-prior))` (under the
  `feeling_persistence` category, P5-learnable; same constants as R43 so the two affect owners
  share one decay timescale). The instantaneous target stays owned by the injected R38 path; the
  cross-tick carry is the new `05`-owned semantic. `FeelingConstructionPath`/`update_state` gain an
  additive optional `prior_feeling`/`prior_state` (default `None` reproduces stateless behavior
  byte-for-byte); `InteroceptiveFeelingRuntimeStage` holds the prior-tick state (like `04`/`09`/`18`)
  and exposes `seed_prior_state`. Cold start defaults prior to the baseline feeling. The snapshot is
  bumped to version 3 with a `feeling` field, so `05` survives a restart; a version mismatch (v1/v2)
  or corrupt feeling hard-stops on load. Default/recency/offline keep the stateless constant `05`.
  Also removed a pre-existing dead duplicate `NeuromodulatorDerivedFeelingConstructionPath`. Deferred:
  real interoceptive-signal integration, P5 coefficient learning, feeding the evolving `05` feeling
  into `06`/behavior (FG-2).
- P2 closeout / P3 mid-chain (R45): the `06` memory owner closes both its shims at once. Formation
  de-shim: an owner-owned `AffectGroundedMemoryFormationPath` replaces the constant shim under the
  semantic assembly, forming affect-tagged memory from the real `05` feeling state (the item's
  `affect_tag` is the genuine felt body-state, not a constant; owner-owned episodic/autobiographical
  family mapping, mismatch → autobiographical). Salience gate: an owner-owned
  `SalienceGatedReplayCandidateSelector` computes a bounded affect-intensity from the real feeling
  (arousal/tension/pain) + mismatch and sets each candidate's `forced_consolidation` + `priority_hint`
  from it (threshold/weights under `consolidation_policy`/`replay_priority_policy`, P5-learnable), so a
  flat low-affect tick consolidates nothing and a high-affect or high-mismatch tick consolidates.
  Durability: `PersistedExperienceRecord` gains an additive `record_kind` (default
  `experience_writeback`, so the 15 stream is byte-for-byte unchanged) + an opaque `metadata`; the
  SQLite backend upgrades an old file in place via a PRAGMA-guarded `ALTER TABLE`; an owner-neutral
  `MemoryRecordBridge` + `RuntimeHandle._persist_memory` carry persists exactly the
  `forced_consolidation` items as `record_kind="affect_memory"`, embedded at write, co-residing with
  the 15 stream. Recall: reuses the 34 semantic recall surface, so affect-memory is recallable through
  10 and resumes across restart; `_record_tier` maps by family. `06` imports neither persistence nor
  embedding; the carry seam re-derives no decision. Opt-in on the existing semantic-memory switch;
  default/recency assemblies keep the constant `06` shim. A request without store+embedding is a
  CompositionError; an embedding/store failure is a hard stop; no dedup/merge this slice. 607 tests
  green and network-free. Deferred: dedup/merge, deeper feeling-driven formation, real 06→07 candidates.
- P3 mid-chain (R46): the `07` workspace owner is de-shimmed into a real attention bottleneck.
  Competition: an owner-owned `SalienceWeightedWorkspaceCompetitionPath` scores each candidate as a
  bounded function of the real `06` `priority_hint` + the real `05` feeling salience
  (`clamp(0.6*priority + 0.4*feeling_salience)`), replacing the constant 0.95; every replay candidate
  stays in the candidate set (forced flag + provenance preserved, owner invariants hold). Bottleneck:
  an owner-owned `BoundedAttentionRetentionPath` retains only the top-K (`max_retained=3`, under
  `working_state_update_policy`) into the working state with a deterministic tie-break and a never-empty
  guarantee, replacing retain-everything. Brain-aligned semantic (owner-confirmed): "consolidated" (a
  `06`-forced candidate, persisted long-term) ≠ "held in attention" (the bounded working state) — a
  forced candidate may lose the competition and not be held this tick, while remaining in the candidate
  set (still reaching `08`) and still persisted. Opt-in on the same semantic-memory switch as R45;
  default/non-semantic assemblies keep the constant-score / retain-everything shim. No contract change;
  `07` imports no other owner. 618 tests green and network-free. Deferred: P5 weight/K learning, a
  sharper `08` commitment, multi-source competition.
- P3 mid-chain (R47): the `08` reportable conscious-content commitment is de-shimmed into
  global-workspace ignition. Problem: the count-based first-version policy declared
  `no_commit/semantic_conflict_unresolved` whenever the working state retained >1 candidate, and
  R46's bounded top-K working state retains >1 by design, so `08` would rarely become aware of
  anything. Fix: an owner-owned `IgnitionFocalSelectionPolicy` (injected through the existing
  `focal_selection_policy` seam, in `helios_v2.consciousness`) ignites the single
  highest-`workspace_score_hint` retained candidate as focal (winner-take-all, deterministic
  tie-break) and demotes the rest to supporting context (descending score, bounded by
  `max_supporting_context_items`). Preserved: `insufficient_commitment_signal` (zero retained) and
  `context_not_reportable` (empty focal summary); `semantic_conflict_unresolved` stays in the
  taxonomy for a future genuine-conflict slice but is no longer emitted for mere multiplicity. No
  contract/engine/renderer change. Opt-in on the same semantic-memory switch as R45/R46;
  default/non-semantic assemblies keep the count-based policy. End-to-end the chain forms one
  candidate per tick today, so the headline win (multiplicity → ignite winner) is owner-level tested
  now and becomes end-to-end visible once a multi-candidate source lands. 626 tests green and
  network-free. Deferred: genuine semantic-conflict detection, an LLM semantic renderer, P5
  ignition-threshold learning.
- P3 mid-chain (R48): the `09` gate's `global_activation_level` (its second-largest non-stimulus
  term, weight `* 0.20`) is de-shimmed from the constant `0.9` to the real `07` workspace
  activation. Under the semantic assembly the gate-signal bridge sources it from the same tick's
  `07` `WorkspaceCompetitionStageResult` — the maximum `workspace_score_hint` among the retained
  working-state candidates (the dominant ignition strength held in attention), or `0.0` when
  nothing is retained. Owner-neutral glue (the bridge forwards a raw bounded fact clamped to
  `[0,1]`); `09` keeps sole ownership of the gate decision and the term weight. The R37 arousal
  coupling is preserved (both real facts ride one snapshot). `07` runs before `09`, so a
  missing/wrong-typed `07` result is a hard fail. No contract change; the real value surfaces in
  `contributing_signals["global_activation_level"]`. Opt-in on the same switch; default/non-semantic
  keep `0.9`. The other four constant gate inputs (`workload_pressure`, `temporal_signal`,
  `drive_urgency_signal`, `dmn_available`) and the `selected_stimuli` projection remain first-version
  constants (no real producer running before `09` yet — `drive_urgency_signal` is owned by `18`,
  which runs after `09`; the rest need unowned compute/clock/DMN producers). 631 tests green and
  network-free.
- P3 mid-chain (R49): the `10` directed-retrieval request's `recall_intent`/`selected_memory_refs`
  are de-shimmed (the query-planning path itself was already real; only its inputs were shim). The
  constant `recall_intent="remember runtime chain context"` and fabricated refs are replaced, under
  the semantic assembly, by the prior tick's `11` `MemoryHandoffDirective` (when `11` saved one for
  the next tick), so a line of thought the system chose to continue steers what memory it retrieves
  next tick (memory-guided maintenance, `ARCHITECTURE_PHILOSOPHY` §5.3). The carry mirrors the
  R32/R42 pattern: an owner-neutral `PriorThoughtRecallHolder`, a post-tick
  `_carry_recall_directive` capture, and a `ThoughtDirectedRetrievalRequestBridge`. With no saved
  handoff (first tick / non-fired / `11` did not continue) the request falls back to the real `09`
  `compact_stimuli` with no recall intent (a defined behavior, always valid). Owner-neutral:
  composition transports the `11`-owned directive verbatim; `10`/`11` are unchanged. Opt-in on the
  same switch; default/non-semantic keep the constant. 635 tests green and network-free.
- P3 / FG-2 prerequisite (R50): the interoceptive producer lands, closing the **producer** half of
  `gap_interoceptive_signal_source`. A new owner `helios_v2.interoception` (a peripheral afferent
  producer) reports the runtime's real internal condition (compute/runtime pressure:
  cpu/memory/latency/error) as bounded `interoceptive` `RawSignal`s into `02`: a `RuntimePressureSample`
  contract (four `[0,1]` channels) + an injected `RuntimePressureSampler` protocol + a first-version
  `StdlibRuntimePressureSampler` (lazy psutil for real CPU/memory, degrading to stdlib load-average
  or a defined neutral default, never raising for a merely-unavailable fact) + a
  `RuntimeInteroceptiveSource` implementing the existing `SensorySource` (one bounded deterministic
  signal per channel). Sensory normalizes them to `modality="interoceptive"` stimuli that the `05`
  stage already filters and `validate_internal_body_signal` accepts, so `05` receives non-empty
  `internal_signals`. **Scope (no half-step):** this slice delivers the producer and the live,
  validated afferent; the `05` construction path still ignores `internal_signals` this slice (its
  feeling value is unchanged), so making `05` actually consume them to shape feeling is the next
  slice (FG-2). The owner holds no feeling/salience/cognitive policy and imports no
  feeling/appraisal/neuromodulation owner; a merely-unavailable fact degrades to a defined default,
  while an outright sampler exception propagates (no fabricated healthy body). Opt-in
  (`assemble_runtime(interoceptive_sampler=...)`); default/channel-bound/semantic assemblies are
  byte-for-byte unchanged when off; no new mandatory/network dependency (psutil lazy + degrades).
  635 -> 650 tests green and network-free.
- P3 FG-2 closure (R51): `05` feeling now actually consumes R50's interoceptive `internal_signals`,
  closing the **consumer** half of `gap_interoceptive_signal_source` and forming the **first
  end-to-end, evaluation-reconstructable FG-2 causal chain**. The `05` owner adds an
  `InteroceptiveSignalModulatedFeelingConstructionPath` wrapping the R38 neuromodulator target; it
  reads bounded `pressure_channel`/`pressure_value` facts from stimulus metadata (no content
  parsing; max per channel; unrecognized/out-of-range/non-numeric facts contribute nothing and never
  raise) and adds a bounded, non-negative, stress-directional per-dimension contribution
  (cpu->arousal/tension, memory->fatigue/tension, latency->fatigue/tension, error->pain_like/tension),
  clamped. The contribution is additive over the neuromodulator target (never replaces it); empty/
  unrecognized afferent reproduces the inner target byte-for-byte. Composition nests it as
  `persistence(interoceptive(neuromodulator))`, so the body contribution rides the same R44
  dual-timescale carry (no second persistence). Because `05` feeling already feeds `07` workspace
  competition (R46 reads arousal/tension/pain), a high-pressure sample now measurably changes both
  the `05` feeling-state and the `07` candidate score, so the real "machine condition -> feeling ->
  workspace competition" chain holds. The mapping lives in `helios_v2.feeling`; `05` imports no
  interoception/appraisal/neuromodulation/workspace owner. valence/comfort/social_safety untouched
  this slice (narrow, monotone first version); coefficients first-version constants under
  `feeling_coupling_strength` (P5-learnable). Opt-in on the semantic + interoceptive assembly;
  default/recency/channel-bound/semantic-without-sampler assemblies byte-for-byte unchanged.
  650 -> 664 tests green and network-free.
- P3 multiplicity activation (R52): `06` now recalls prior affect-memories as additional replay
  candidates feeding `07`, giving the workspace its **first genuine multiplicity to arbitrate** and
  exercising R46 competition / R47 ignition / R48 gate activation end to end (before R52 the chain
  formed one candidate per tick, so all three were owner-level tested only). The `06` owner gains a
  recalled-replay path: it re-forms each injected `RecalledMemoryFact` into a non-forced
  `MemoryReplayCandidate` (preserving the original `memory_id`, stored family, and original persisted
  `affect_tag`, anchored to the current feeling state + binding context so the `MemoryFormationState`
  invariants hold), with the priority from an owner-owned bounded blend of recall relevance + recalled
  affect intensity (under `replay_priority_policy`, P5-learnable). The recalled source is injected
  behind a narrow `RecalledMemoryProvider` protocol (the `06` owner imports neither persistence nor
  embedding); composition's `StoreBackedRecalledMemoryProvider` embeds the current binding-context
  content and ranks `affect_memory`-kind records by cosine similarity (reusing the R34 `search_similar`),
  reconstructing each recalled affect vector from the durable record. To enable faithful recall, the
  R45 `MemoryRecordBridge` now additionally writes the formed memory's affect vector into the
  affect-memory record's opaque `metadata` (additive string-encoded extension; no persistence contract
  change; legacy records without it are simply not workspace-recall-eligible). End-to-end under the
  semantic assembly, once a prior consolidation-worthy affect-memory exists, a later tick's `07`
  competes over >1 candidate, `08` ignites the single highest-scoring retained candidate as focal
  content (rest demoted to supporting context), and `09` `global_activation_level` equals the max
  retained score; a sufficiently strong recalled memory can win the workspace. Recalled candidates are
  additive and never `forced_consolidation` (so the R45 persistence carry does not re-store them); the
  current-tick formed memory and its gate are unchanged. A cold store / empty binding context / no
  similar memory yields zero recalled candidates (single-candidate behavior unchanged); an
  embedding/store failure during recall is a hard stop (no silent single-candidate fallback). Opt-in on
  the semantic assembly; default/recency/non-semantic/offline assemblies byte-for-byte unchanged;
  existing store files read back. 664 -> 678 tests green and network-free.
- P3 gate-input de-shim (R53): the `09` gate's `workload_pressure` is grounded in the runtime's real
  compute/runtime load, the second consumer of the interoceptive afferent (after `05` feeling, R51).
  Both gate-signal bridges hardcoded `workload_pressure=0.1`, yet in the `09` owner it is a real
  load-suppressive term (subtractive `* 0.45` in the gate score, and above
  `resource_pressure_block_threshold` with low continuation it blocks firing with
  `resource_pressure_too_high`). An owner-neutral `_interoceptive_workload_pressure(frame)` helper
  reads the R50 interoceptive cpu/memory load stimuli already present in the same tick's `02` batch
  (from the reserved `pressure_channel`/`pressure_value` metadata; max per channel = dominant
  resource pressure; unrecognized/out-of-range/non-numeric skipped, never raising) and both bridges
  forward it in place of `0.1`. The `09` owner keeps sole ownership of the gate weight and block
  threshold; the bridge forwards a raw bounded fact only and imports no interoception owner (the
  afferent flows through `02`). Real machine load now monotonically raises the gate's resource-pressure
  term, surfacing in `contributing_signals["workload_pressure"]`. **Surfaced constraint (recorded
  honestly):** high real load now correctly drives the gate to `resource_pressure_too_high`/no-fire,
  but the assembled chain has no gate-no-fire closure yet (directed retrieval raises on a non-fired
  gate), so R53 exercises the real value end to end only within the firing window (cpu/memory up to
  ~0.3 given the other first-version constant gate signals) and validates the
  high-load -> high-`workload_pressure` -> block relationship at the owner-neutral helper level; the
  full-range end-to-end exercise is unlocked by a dedicated **gate-no-fire tick-closure requirement**
  (the gating-no-fire analog of R28's `internal_only` closure). Absence of a recognized load stimulus
  keeps the constant `0.1` byte-for-byte, so the default, recency-only, channel-bound-without-interoception,
  and semantic-without-sampler assemblies are unchanged. 678 -> 685 tests green and network-free.
- P3 enabler (R54): gate no-fire tick closure. The assembled chain could not complete a tick whose
  `09` gate decided `no_fire` (the post-gate stages `10`/`16`-family/`11`/`12`/`14` hard-require a
  fired gate and raised), which blocked R53's high-load no-fire and would block R55/R56. R54 is the
  upstream mirror of R28's fired-but-no-proposal internal-only closure: each post-gate stage result
  gains an additive `activated: bool = True` discriminator (+ `inactive_id`, Optional artifacts, an
  `inactive(tick_id)` factory, all defaulting to the fired shape), and each post-gate stage observes
  the gate owner's published `decision` (or the upstream `activated` flag) and returns an explicit
  not-activated result without calling its owner's fired-path API — so those owners' "requires a
  fired gate" invariants are never violated or relaxed. The closure tail reuses R28: the planner
  stage's no-fire branch synthesizes an owner-neutral no-fire marker externalization result
  (`status="no_externalization"`, no fabricated proposal) and routes it through the existing
  `evaluate_internal_only` -> `no_actionable_proposal`; the writeback bridge already emits an
  `internal_only` continuity record (a governance-inactive guard added); `18` autonomy and `17`
  evaluation still run (autonomy integrates continuation/continuity regardless of firing; evaluation
  is read-only) from no-fire-marker-anchored requests with no-action drive inputs and explicit
  `activated=False` evidence — so continuation pressure and `18`/`24` long-horizon continuity carry
  across a no-fire tick and the tick is diagnostically reconstructable rather than aborting. No
  fabricated cognition (inactive results carry `None` artifacts; markers are ids only). The fired
  path is byte-for-byte unchanged. This lifts the R53 firing-window constraint: a high-compute-load
  tick now completes end to end as a no-fire tick. 685 -> 690 tests green and network-free.
- P3 gate-input de-shim (R55): the `09` gate's `temporal_signal` (was constant `0.4`) and
  `dmn_available` (was constant `True`) are grounded in a real temporal/rest-state source. A new
  owner `helios_v2.temporal` produces a bounded `TemporalPacingSample` (`temporal_signal` `[0,1]` +
  `dmn_available` bool); the first-version `RestStateTemporalSource` maps rest (no external stimulus)
  to `dmn_available=True` and an external task to `False` (DMN engages at rest, suppressed on task),
  and accumulates `temporal_signal` across consecutive no-fire ticks
  (`clamp(per_tick_increment * ticks_since_last_fire, 0, max_signal)`), resetting on a fire — the
  spontaneous-thought pacing of elapsed rest. Both gate-signal bridges forward the source's outputs
  in place of the constants via a shared `_temporal_inputs(frame, source)` helper (reading the raw
  external-stimulus fact from the `02` batch through `_external_stimulus_present`); the `09` owner
  keeps the gate weights and decision. The cross-tick elapsed state is advanced post-tick from the
  published gate decision through the owner-neutral `RuntimeHandle._carry_temporal` seam (fire
  resets, no-fire increments). R54 made this safe: a real temporal input can now drive a no-fire
  without aborting, so the runtime can express rest-state spontaneous-thought pacing and DMN
  task-disengagement. The temporal owner holds no salience/feeling/cognitive policy and imports no
  gate/appraisal/feeling/neuromodulation owner. Opt-in (`assemble_runtime(temporal_source=...)`);
  deterministic; default/recency/semantic/channel-bound/interoceptive assemblies keep `0.4`/`True`
  byte-for-byte when no source is wired. 690 -> 702 tests green and network-free.
- Owner-boundary recovery (R56): the mislocated `04` neuromodulator drive mapping is recovered out
  of composition into the `04` owner (no runtime behavior change). R36's
  `AppraisalDerivedNeuromodulatorUpdatePath` (with `reward_to_dopamine`/`threat_to_cortisol`-style
  sensitivity coefficients and `level = clamp(tonic_baseline + sum(sensitivity_k * salience_k))` —
  which salience drives which neuromodulator channel and how strongly, the `04` owner's defining
  cognitive policy) was defined in the assembly-only `composition/bridges.py`, violating
  `ARCHITECTURE_BOUNDARIES.md` §4.5 / `ARCHITECTURE_PHILOSOPHY` §3.2/§7.1, while its R43
  dual-timescale decay wrapper already lived in the `04` owner package. R56 relocates the drive
  policy (and its private `_aggregate_salience`/`_AggregatedSalience` helper) into the `04` owner
  package `helios_v2.neuromodulation` (reusing the owner's existing `_clamp`); composition now only
  constructs/injects/wraps it via the unchanged `NeuromodulatorUpdatePath` protocol. A new guard
  (`tests/test_composition_owner_boundary_guard.py`) fails if a `<salience>_to_<channel>` sensitivity
  coefficient reappears under `helios_v2/composition` (with a positive-control assertion so it is not
  vacuous). Behavior-preserving: identical neuromodulator levels for any batch/config and every
  assembly (default/recency/semantic/channel-bound/interoceptive/temporal/checkpoint) — a pure
  relocation, not a policy change. Accepted owner-neutral glue explicitly kept in composition: the
  constant first-version shim paths (`FirstVersion*`) and the pure projection bridges (which forward
  a published owner field with no scoring weight). `test_neuromodulator_engine.py` now imports the
  path from the `04` owner. No contract change; no new logging mechanism; 702 -> 704 tests green and
  network-free (+2 guard tests).
- Owner-boundary recovery (R57): the mislocated `18` autonomy drive-input mapping is recovered out
  of composition into the `18` owner (no runtime behavior change; the autonomy analog of R56 and
  deeper, because it coupled to the consumer owner's threshold). Previously
  `FirstVersionAutonomyRequestBridge` tuned the pressure constants (`_ACTION_CONTINUATION_PRESSURE=0.9`,
  etc.), owned the planner executed/blocked classification and the retrieval `/4.0` normalization,
  and — per its own docstring — reverse-engineered the `18` owner's `outward_drive >= 1.6` action
  threshold inside the assembly glue. "How strong a proactive drive a cognition outcome produces,
  relative to my own action threshold" is the `18` owner's defining judgment (violating §4.5 /
  `ARCHITECTURE_PHILOSOPHY` §7.1/§3.3). R57 adds an `18`-owned `ProactiveCognitionFacts` raw-fact
  input contract and an `18`-owned `AutonomyDriveInputProjection.derive_drive_inputs(facts)` that
  produces the five existing drive-input summaries (transcribing the mapping verbatim), and names the
  threshold as the owner constant `OUTWARD_ACTION_THRESHOLD = 1.6` (reused by
  `FirstVersionAutonomyPath`). The composition bridge is reduced to extracting raw facts, forwarding
  provenance ids, and calling the owner projection. `ProactiveDriveRequest` is unchanged in shape
  (existing autonomy/contract/stage-chain tests unaffected). The owner-boundary guard is extended to
  fail on an autonomy drive-pressure constant (`*_(CONTINUATION|TEMPORAL|IDENTITY)_PRESSURE = <num>`)
  or an `outward_drive >=` / `OUTWARD_ACTION_THRESHOLD =` reference under composition (positive-control
  asserted; scoped so it does not flag the legitimate `09` gate `workload_pressure` projection).
  Behavior-preserving: field-for-field identical `ProactiveDriveRequest` and byte-for-byte identical
  autonomy disposition for every fact combination (fired±action, continue, concluded, self-revision,
  each planner status, no-fire) and every assembly. No contract shape change; no new logging
  mechanism; 704 -> 716 tests green and network-free (+12 tests).
- P3 external-afferent honesty (R59): makes the external stimulus source a first-class injectable
  capability and stops counting the fabricated constant as a real signal. `02 -> 03` appraises the
  whole batch, so a varying external stimulus genuinely drives `03 -> 04 -> 05 -> 07`; but the
  default/semantic assemblies registered a constant `FirstVersionSensorySource` (fixed
  `content="hello runtime"` every tick), a composition-injected constant masquerading as input
  (violating FG-1), and because the content never changed the real `03` novelty collapsed to a
  fixed value after the first store write. R59 adds an opt-in `RuntimeProfile.external_signal_source`
  (conforming to the `02` `SensorySource` protocol); when provided it replaces the placeholder, and
  it is mutually exclusive with `channel_cli` (both-set is a `CompositionError`, validated in
  `RuntimeProfile.__post_init__`). The first-version `SequenceExternalSignalSource` replays
  caller-supplied tick-varying real `RawSignal`s and emits an explicitly empty batch when exhausted
  — it fabricates no content (honoring `ARCHITECTURE_PHILOSOPHY` §4.3/§8, no prompt theater); an
  empty afferent closes through the existing no-fire/internal-only path. A semantic-assembly test
  proves a varying external stimulus produces different `03` novelty and `04` state across ticks — a
  second FG-2 causal chain (external afferent) alongside R51's interoceptive one. The default
  placeholder is now documented as NON-REAL; R59 does not make the default real (that needs a real
  deployed source, network `wave_C`), it makes a real source injectable and retires the
  constant-as-real-afferent. Opt-in, default-off: default/recency/semantic/checkpoint/interoceptive/
  temporal assemblies byte-for-byte unchanged when off. No contract change; no new logging mechanism;
  721 -> 728 tests green and network-free (+7 tests).
- P3 memory-content de-shim (R60): the **content** of the memory `06` forms came from the
  composition binding-context bridge, which returned a hardcoded constant in every assembly
  (`content_kind="situational-summary"`, `salient_tokens=("hello","novelty")`, `summary:runtime`
  refs); `AffectGroundedMemoryFormationPath` copies it verbatim, so the durably-persisted (R45)
  and recalled (R52) memory was *about* a constant unrelated to the real percept — the next
  fabricated position after R59 made a real varying stimulus reach `02`/`03`, violating FG-1. R60
  rewrites the bridge to derive the content from the real `02` percept already in the frame
  (prefer external, fall back to the whole batch for interoceptive-only ticks; primary stimulus ->
  `content_kind="perceived-stimulus-summary"`, `summary_ref`=real stimulus id, `context_ref`=real
  batch id, `salient_tokens`=an owner-neutral mechanical tokenization of the real perceived content
  — every token a substring, capped at 8, never invented). Surfaced constraint (recorded
  honestly): the pre-gate `02-08` chain requires a memory every tick (the `07` workspace owner
  raises on zero replay candidates; R54's no-fire closure only covers post-gate stages), so a
  completely empty percept (no external and no interoceptive — R59 empty source / channel
  no-input) binds an honest no-percept marker anchored to the real `05` feeling state
  (`content_kind="no-perceived-stimulus"`, empty tokens, `summary_ref`=real feeling-state id)
  rather than `None` or fabricated content; a genuine zero-percept pre-gate closure is a separate
  future requirement. Default-on correctness/honesty change (not opt-in); the default assembly's
  memory content now derives from the `FirstVersionSensorySource` placeholder percept
  ("hello runtime" -> tokens `("hello","runtime")`) rather than a separate constant. The `06`
  affect tag, salience gate, durability, and recalled replay are unchanged in mechanism. 728 -> 732
  tests green and network-free (+4 tests).
- P3 mismatch/surprise de-shim (R61): the `06` salience gate's second input — the
  prediction-mismatch (surprise) evidence — was a composition constant (`mismatch_score=0.8`,
  making every memory autobiographical and always raising the consolidation floor), so surprise
  was asserted, not measured — the next fabricated position after R59/R60 made the percept and
  memory content real. R61 grounds it in the real `03` novelty already in the frame (`1 - max
  cosine similarity` to stored experience, the functional surprise core in a memory-grounded
  system): the bridge reads the batch-max real novelty/uncertainty and projects
  `mismatch_score=clamp(novelty)`, `anomaly_score=clamp(novelty)`, `confidence=clamp(1-uncertainty)`;
  below `_MISMATCH_NOVELTY_THRESHOLD` (0.5, a composition projection cut-point) a familiar/expected
  percept yields `None` (no surprise -> the `06` owner forms an episodic, not autobiographical,
  memory). The bridge computes no `06` gate/family policy and invents no forward-model prediction.
  Honest grounding (`B_functional_inspiration`): novelty-as-surprise, NOT a true predictive-coding
  forward-model error (a later P5 concern), recorded and not over-claimed. Default-on
  correctness/honesty change (not opt-in): default/recency assemblies (constant novelty `0.6` >=
  threshold) emit a `0.6`-derived mismatch (autobiographical) rather than the retired `0.8`
  constant; the semantic assembly tracks real memory-grounded novelty (cold/dissimilar ->
  autobiographical, similar -> episodic). The `06` salience gate, family mapping, durability, and
  recalled replay are unchanged in mechanism. 732 -> 735 tests green and network-free (+3 tests).
- P3 `09` gate drive-urgency de-shim (R62): the `09` gate's `drive_urgency_signal` (weight `* 0.10`)
  was the constant `0.7`; it is meant to be the proactive drive's urgency, owned by `18` autonomy
  which runs *after* `09`, so the gate could only ever see a constant. R62 carries the prior tick's
  real `18` `ProactiveDriveState.outward_drive` (clamped to `[0,1]`) forward through an owner-neutral
  `PriorDriveUrgencyHolder` advanced post-tick (the R49/R55 carry pattern) and read by the gate-signal
  bridge next tick; the `09` owner keeps the `* 0.10` weight. The first tick uses a documented neutral
  cold-start equal to the prior constant (`0.7`), so tick 1 of every assembly is byte-for-byte
  unchanged and the real prior drive supersedes it only from tick 2 (e.g. an externalizing prior tick
  with `outward_drive >= 1.6` makes the next tick's gate `drive_urgency_signal = 1.0`). No fabricated
  urgency; an absent `18` result leaves the carry unchanged. **Scope converged during implementation:**
  R62 originally bundled `selected_stimuli`, but projecting the real `03` appraisal drops the default
  (non-semantic) assembly's stimulus signal from `0.9` to the first-version aggregate `0.4`, pushing
  the default gate below the `0.55` fire threshold and flipping it to no-fire (17 fired-path tests
  depend on the default firing). That flip is honest but exposes a deeper "default-assembly has no real
  high-salience ignition source" problem that deserves its own requirement rather than being forced
  through by a weak constant or by patching the `09` threshold — so `selected_stimuli` is deferred to
  R63 and is the gate's last remaining constant input. 735 -> 738 tests green and network-free (+3 tests).
- Premotor-preparation vs execution (16 labels): the `16` outward-expression and externalization
  nodes produce NON-AUTHORITATIVE drafts, the functional analog of premotor/SMA motor preparation
  and internal rehearsal, NOT execution. The real go/no-go authority is `13` planner and the real
  transport is `30`/`31` channel. The draft carries explicit `forbidden_capabilities` /
  `final_authorities` / `execution_boundary_summary`; "draft" must never be read as "execution"
  (see `gap_premotor_preparation_vs_execution`).

## 5. Update Rule

This file and its Chinese companion `PROGRESS_FLOW.zh-CN.md` MUST be updated in the same
change set whenever a requirement materially changes:

1. an owner's maturity color,
2. the runtime stage chain order or membership,
3. owner boundaries (a new owner, a merged owner, or a closed gap).

The "Last synced" line at the top must name the requirement that last touched this file. A
change set that alters owner maturity without updating this map is incomplete, mirroring the
`requirements/index.md` maturity rule.
