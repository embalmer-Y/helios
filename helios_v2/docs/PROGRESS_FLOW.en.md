# Helios v2 Module Progress Flow (English)

> Status: living progress map. MUST be updated in the same change set as any requirement that
> materially alters owner maturity, the runtime stage chain, or owner boundaries.
> Last synced: R29 (cognition-derived autonomy drive). Test baseline: 332 passed. HEAD-era: R29.
> Companion: `PROGRESS_FLOW.zh-CN.md` (Chinese) must be updated together with this file.

## 1. Purpose

This document is the module-level progress map for Helios v2. It shows the canonical runtime
stage chain (the `CANONICAL_STAGE_ORDER` executed each tick) plus the supporting
infrastructure owners, color-coded by real implementation maturity, and marks the one
structural gap (channel execution / outward transport) that has no owner yet.

It is intentionally implementation-facing: the colors reflect shipped code and validation
evidence, not planned architecture quality, and must match the `Maturity` column in
`requirements/index.md`.

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

    IN([External stimulus / internal body signal]):::infra
    S02[02 Sensory Ingress - relatively complete]:::deep
    S03[03 Rapid Salience Appraisal - baseline/shim in]:::base
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
    S17[17 Evaluation - baseline]:::base
    CH[Channel Execution / Outward Transport - NO OWNER yet]:::gap
    OUT([Real external output: QQ / voice / CLI]):::gap

    IN --> S02 --> S03 --> S04 --> S05 --> S06 --> S07 --> S08 --> S09 --> S10
    S10 --> S16P --> S16O --> S16E --> S11
    S11 --> S12 --> S13 --> S14 --> S15 --> S18 --> S17
    S13 -. accepted decision .-> CH
    S16E -. delivery draft .-> CH
    CH -. real transport .-> OUT
    S15 -. experience writeback loop .-> S06

    LLM[25 LLM Inference Gateway - infra done]:::infra
    LLM --> S11

    K01[01 Runtime Kernel - rel. complete]:::infra
    OBS[21 Observability Timeline - done]:::infra
    COMP[22 Composition Root - done]:::infra
    EV23[23 Timeline-aware Eval - done]:::infra
    TH24[24 Continuity Threads - done, now active]:::infra
    K01 -. startup gate + dispatch .-> S02
    OBS -. per-tick timeline .-> EV23
    EV23 --> S17
    TH24 --> S18
    COMP -. assembles all 19 stages .-> K01
```

## 4. Status Summary

- Cognition main chain (02 to 17) runs end to end; 332 tests pass, network-free, plus real
  LLM smoke.
- Deep & real owners: 02 sensory, 08 conscious content, 11 internal thought (real LLM-driven
  cognition core), 18 autonomy (cognition-derived), plus infrastructure (01, 21, 22, 23, 24,
  25).
- Baseline owners (the majority): 03-07, 09-10, 12-17 (excluding 13's planner judgment which
  is real) - owners are real with contracts and tests, but their inputs are still
  composition-injected deterministic shim. 13's channel descriptor/status snapshots are
  shim-injected.
- Single structural gap: Channel Execution / Outward Transport (dashed CH -> OUT), the
  brain.mmd `M outward output` stage. Consistently referenced since R01-R20 but never
  assigned an owner. This is the largest remaining final-goal gap (controlled outward
  externalization).
- The experience-writeback loop (15 -> 06) is implemented, so each tick is subjectively
  connected to the previous one.

## 5. Update Rule

This file and its Chinese companion `PROGRESS_FLOW.zh-CN.md` MUST be updated in the same
change set whenever a requirement materially changes:

1. an owner's maturity color,
2. the runtime stage chain order or membership,
3. owner boundaries (a new owner, a merged owner, or a closed gap).

The "Last synced" line at the top must name the requirement that last touched this file. A
change set that alters owner maturity without updating this map is incomplete, mirroring the
`requirements/index.md` maturity rule.
