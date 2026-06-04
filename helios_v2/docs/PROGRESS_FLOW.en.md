# Helios v2 Module Progress Flow (English)

> Status: living progress map. MUST be updated in the same change set as any requirement that
> materially alters owner maturity, the runtime stage chain, or owner boundaries.
> Last synced: R35 (memory-grounded novelty appraisal; P3 first cognitive-owner de-shim). Test baseline: 476 passed. HEAD-era: R35.
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

## 3. Flow

```mermaid
flowchart TD
    classDef deep fill:#b7e1cd,stroke:#2e7d32,color:#1b5e20
    classDef base fill:#fff2cc,stroke:#bf9000,color:#7f6000
    classDef infra fill:#cfe2f3,stroke:#1c4587,color:#0b3d91
    classDef gap fill:#f4cccc,stroke:#990000,color:#660000,stroke-dasharray: 5 5

    EXT([External stimulus: CLI bound now / QQ / voice future]):::base
    BODY([Internal body signal - interoceptive source]):::infra
    S02[02 Sensory Ingress - relatively complete]:::deep
    S03[03 Rapid Salience Appraisal - novelty real (semantic)/4 dims shim]:::base
    S04[04 Neuromodulator System - baseline/shim in]:::base
    S05[05 Interoceptive Feeling - baseline/shim in]:::base
    S06[06 Memory Affect and Replay - baseline/shim in]:::base
    S07[07 Workspace Competition - baseline/shim in]:::base
    S08[08 Reportable Conscious Content - rel. complete]:::deep
    S09[09 Thought Gating - baseline/shim in]:::base
    S10[10 Directed Retrieval - baseline/shim in]:::base
    S16P[16 Embodied Prompt Contract - baseline]:::base
    S16O[16 Outward Expression Draft - baseline/draft-only]:::base
    S16E[16 Outward Externalization Draft - baseline/draft-only]:::base
    S11[11 Internal Thought Loop - REAL LLM-driven]:::deep
    S12[12 Action Externalization - baseline]:::base
    S13[13 Planner Bridge - baseline/shim channel state]:::base
    S14[14 Identity Governance - baseline]:::base
    S15[15 Experience Writeback - baseline]:::base
    S18[18 Subjective Autonomy - rel. complete/cognition-derived]:::deep
    S17[17 Evaluation - baseline/corroborates execution truth]:::base
    CH[30 Channel Driver Subsystem + 31 CLI driver - real local round trip, opt-in]:::infra

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
    K01 -. startup gate + dispatch .-> S02
    OBS -. per-tick timeline .-> EV23
    EV23 --> S17
    TH24 --> S18
    COMP -. assembles all 19 stages .-> K01
    S15 -. durable append (opt-in persistence) .-> PER
    PER -. recency or semantic re-entry across restart (opt-in) .-> S10
    EMB -. embed-at-write + embed-at-query (opt-in semantic) .-> PER
```

## 4. Status Summary

- Cognition main chain (02 to 17) runs end to end; 476 tests pass, network-free, plus real
  LLM smoke.
- Deep & real owners: 02 sensory, 08 conscious content, 11 internal thought (real LLM-driven
  cognition core), 18 autonomy (cognition-derived), plus infrastructure (01, 21, 22, 23, 24,
  25, 33, 34).
- P3 began (R35): the `03` appraisal owner's novelty dimension is now a real signal under the
  semantic-memory assembly (novelty = 1 - max cosine similarity of the stimulus to stored
  experience, via the 34 embedding substrate + 33 store), the first cognitive consumer of the
  embedding base. `03` owns the novelty salience mapping; composition injects an owner-neutral
  similarity-fact source, so `03` imports neither the embedding nor persistence owner. The
  other four `03` dimensions stay shim (later P3 slices); default and recency-only assemblies
  keep constant novelty 0.6. First-version comparison is cross-register (stimulus vs 15 result
  summaries), noted and not over-claimed.
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
  (latest-state checkpoint/restore, persisting 06/04/05/14 once de-shimmed). The P2->P3 hinge
  is in place: real `03` novelty-from-memory can now build on the R34 embedding substrate.
- The experience-writeback loop (15 -> 06) is implemented in-process, and with R33 the 15
  stream is now also durably persisted and re-entrant across restarts.

## 5. Update Rule

This file and its Chinese companion `PROGRESS_FLOW.zh-CN.md` MUST be updated in the same
change set whenever a requirement materially changes:

1. an owner's maturity color,
2. the runtime stage chain order or membership,
3. owner boundaries (a new owner, a merged owner, or a closed gap).

The "Last synced" line at the top must name the requirement that last touched this file. A
change set that alters owner maturity without updating this map is incomplete, mirroring the
`requirements/index.md` maturity rule.
