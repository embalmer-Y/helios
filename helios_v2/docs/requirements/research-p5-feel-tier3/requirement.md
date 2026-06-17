# R-PROTO-LEARN Tier 3 — 协议对位 (Requirement)

**Date**: 2026-06-17
**Status**: In progress
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
**Iron rule**: never merge to main (2026-06-17 08:09 小黑拍板)

## Goal

Continue P5 real-learning slicing for **4 owners (协议对位 layer)**:
- **R18** owner 07 workspace (competition / candidate_retention / working_state_update)
- **R19** owner 16a outward_expression (delivery_guidance / boundary_rendering / draft_publication)
- **R20** owner 16b outward_expression_externalization (envelope_rendering / delivery_selection / execution_boundary)
- **R20b** owner prompt_contract (layering / anti_theatrical / action_boundary)

Each owner has 3 mandatory_learned_parameter policies that, in main
baseline, are hard-coded or never updated. The slice replaces them with
real P5 learning sidecars (numpy pinv closure + 5-algorithm W matrix
+ 3-regime switching) following the unified `helios_v2/learning/`
framework established in R-PROTO-LEARN.Tier1+2.

## Why Tier 3

Tier 1 (R11-R15) covers the 5 **decision** owners.
Tier 2 (R16-R17) covers the 2 **behavior** owners (action + eval).

Tier 3 covers the 4 **protocol** owners — the system that decides
*how* thought becomes a published surface to the user:

- **owner 07 workspace** keeps multiple candidate thoughts active and
  selects which to commit to (competition + retention)
- **owner 16a outward_expression** prepares the LLM-visible draft
  (delivery guidance + boundary + publication)
- **owner 16b outward_expression_externalization** wraps the draft in
  channel-specific envelopes (envelope + selection + boundary)
- **owner prompt_contract** is the final protocol layer that decides
  which prompt layers go to the LLM (layering + anti-theatrical +
  action boundary)

These are the **boundary owners**: their outputs directly shape what
the LLM sees as system prompt and what the user sees as final message.

## Academic Grounding

- **Kotseruba 2018 "40 years of cognitive architectures"** — global
  workspace theory (Baars 1988, cited extensively in Kotseruba).
  R18's `competition_policy` + `working_state_update_policy` are
  the global workspace competition dynamics.
- **Parisi 2019 "Continual lifelong learning"** — par 4.2 transfer
  learning.  R19/R20's envelope/delivery selection is the act of
  transferring an internal representation to a public channel.
- **Helios R80/R79 persona governance** — anti-theatrical policy is
  the system constraint that keeps the persona authentic
  (R-PROTO-LEARN.9 also notes "no theater").  R20b's
  `anti_theatrical_policy` is the direct codification of this
  constraint as a learnable parameter.

## Scope

- 4 owner learners, total 12 policies (3 × 4)
- 4 unit-test files (16 tests each = 64 tests)
- 1 smoke script: 4 owner × 8 ticks each
- 1 commit (小黑拍板: 5 切片 1 commit → 此处 4 owner 1 commit)
- 整库 regression: 1479+ passed

## Out of Scope

- 提高 input_dim 或换非线形 mapping 解决 residual 0.4-0.8 问题
- 真接入 owner 07/16a/16b/prompt_contract engine（仅旁路观察者，
  opt-in `p5_learner` 字段）

## Acceptance

- 4 owner learner module + 12 LPC 全部实现
- 4 unit-test file, 64 测试全 pass
- 4-owner smoke 跑通（含真 LLM）
- 整库 1479+ passed + 3 skipped（5 failed = main 已有）
- 调研分支 HEAD 1 commit ahead
- 铁律：分支不 merge main
