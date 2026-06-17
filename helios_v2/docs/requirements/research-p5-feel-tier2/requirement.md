# R-PROTO-LEARN Tier 2 — 行为对位 (Requirement)

**Date**: 2026-06-17
**Status**: In progress
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
**Iron rule**: never merge to main (2026-06-17 08:09 小黑拍板)

## Goal

Continue P5 real-learning slicing for **2 owners (行为对位 layer)**:
- **R16** owner 12 action_externalization
- **R17** owner 17 evaluation

Each owner has 3 mandatory_learned_parameter policies that, in main
baseline, are hard-coded or never updated. The slice replaces them with
real P5 learning sidecars (numpy pinv closure + 5-algorithm W matrix
+ 3-regime switching) following the unified `helios_v2/learning/`
framework established in R-PROTO-LEARN.Tier1.

## Why Tier 2

Tier 1 (R11-R15) covers the 5 **decision** owners: memory, gating,
retrieval, thought, autonomy.

Tier 2 covers the 2 owners that handle **行为对位** — what the system
actually *does* and how it *evaluates* what it did:

- **owner 12 action_externalization** decides whether to push a thought
  outward as an action (the act of behavior selection)
- **owner 17 evaluation** reads execution evidence and produces
  fidelity / gap / long-range diagnostics (the act of self-evaluation)

These are the **observable behavior** owners: their outputs directly
shape what the user sees and what downstream owners consume.

## Academic Grounding

- **Kotseruba 2018 "40 years of cognitive architectures"** — metacognition
  triad (self-observation, self-analysis, self-regulation).  R16
  normalizes outward actions (self-regulation), R17 evaluates after the
  fact (self-analysis + self-observation).
- **Parisi 2019 "Continual lifelong learning"** — intrinsic motivation
  (par 4.3).  R17's `long_range_diagnostic_policy` is exactly the
  self-observation loop that distinguishes a learning agent from a
  reactive one.

## Scope

- 2 owner learners, total 6 policies (3 + 3)
- 2 unit-test files (16 tests each = 32 tests)
- 1 smoke script: 2 owner × 8 ticks each
- 1 commit (小黑拍板: 5 切片 1 commit → 此处 2 owner 1 commit)
- 整库 regression: 1445+ passed

## Out of Scope

- **Tier 3 (R18-R20)** 协议对位 — owner 07/16a/16b/prompt_contract
  (4 owner, 13 LPC)
- 提高 input_dim 或换非线形 mapping 解决 R12/R13/R15 residual 0.4-0.8 问题
- 真接入 owner 12 / 17 engine（仅旁路观察者，opt-in `p5_learner` 字段）

## Acceptance

- 2 owner learner module + 6 LPC 全部实现
- 2 unit-test file, 32 测试全 pass
- 2-owner smoke 跑通
- 整库 1445+ passed + 3 skipped（5 failed = main 已有）
- 调研分支 HEAD 1 commit ahead
- 铁律：分支不 merge main
