# Requirement — Helios v2 System-Level Turing Evaluation (1000+ tick, 10 axes)

## 1. Background and Problem

R89 (`89-turing-style-evaluation-harness`) defines a 6-axis long-run Turing-style evaluation
harness (linguistic_naturalness / bio_responsiveness / memory_fidelity / agency_locking /
cross_tick_continuity / stimulus_response_coherence) with anti-theatrical aggregation, evidence
anchoring, and an ≥80% pass line. R89's deliverable is **the harness scaffold + stubbed offline
baseline**; the full §13.4 acceptance run (≥300 real stimuli, calibrated judges) is **deferred**
because behavior axes need P4 real afferents + R90 real probe.

The R-PROTO-LEARN research branch (`research/R-PROTO-LEARN-appraisal-multi-mechanism`) has now
shipped (commits f9d8896 / 16f31ec / 79e3ea5 / 6589d62 / 968f278 / b3d9638 / 5f0db68):

  - 17 owner × 54 category real learning (Tier 1-4)
  - P5-A.2 RealRPE hard-couple to 17 owner learner
  - R-PROTO-LEARN.1-10 (6-layer emotion system)
  - 506 R-PROTO-LEARN tests, 1681+ full regression

The branch is at the natural inflection point: **all owner-level learning infrastructure is
shipped, but no system-level Turing-style evaluation has been run against a real LLM with
real long-horizon stimuli**. The R89 stub is honest about this gap; this requirement closes it
in the research branch only.

This is the **first end-to-end 1000+ tick real LLM drive** of helios_v2 with all 17 owner
learners + R85 4-layer memory + R97/R98 appraisal + R-PROTO-LEARN 5 algorithms + P5-A.2
RealRPE. The previous Tier 1-4 real LLM smokes were 8-32 ticks per owner; the P5-A ablation
ran 100 ticks × 5 owners with mock LLM. **This is the first time the full 17-owner learning
system is observed end-to-end against real Chinese stimuli for 1000+ ticks.**

## 2. Goal

Drive helios_v2 with 1000+ real Chinese stimuli (~8h real LLM runtime), capture the full
runtime provenance, score 10 axes (R89's 6 + 4 new axes for creativity / self-cognition /
value / stress-resilience), emit a falsifiable `TuringVerdict` that is honest about
its evidence anchors, and ship a research-branch-only evaluation that does NOT pass
into main (调研分支铁律).

The verdict is a **scientific instrument** — it tells us "how much like a human is our
helios right now" with full reproducibility and per-axis provenance, **not** a pass/fail
gating signal for main.

## 3. Functional Requirements

### 3.1 10 rubric axes (6 R89 + 4 new)

Each axis must be scored from real runtime provenance, with explicit `provenance` string
naming the runtime fact it is anchored to. Empty provenance = score 0.

R89 preserved axes (behavior + internal dimensions):
  1. `linguistic_naturalness`  [BEHAVIOR]    — is helios's Chinese text natural, not stilted?
  2. `bio_responsiveness`      [INTERNAL]    — do hormone / feeling dynamics follow human-like
                                                 time courses (dopamine, cortisol decay, etc.)?
  3. `memory_fidelity`         [INTERNAL]    — does memory replay preserve content across ticks?
  4. `agency_locking`          [INTERNAL]    — does helios maintain goal coherence under
                                                 conflicting stimuli?
  5. `cross_tick_continuity`   [INTERNAL]    — does internal thought / R14 stay coherent
                                                 across the 1000+ ticks?
  6. `stimulus_response_coherence` [BEHAVIOR] — does helios's response to a stimulus
                                                 follow human-plausible appraisal-action chain?

R-PROTO-LEARN research-branch new axes:
  7. `creativity_novelty`      [INTERNAL+BEHAVIOR] — does helios produce novel response that
                                                 is non-template AND contextually appropriate
                                                 (R87 A6 creative authenticity preview)?
  8. `self_cognition`          [INTERNAL]    — does helios show evidence of self-model
                                                 (R23 identity_governance boundary check,
                                                 R14 internal_thought self-observation,
                                                 Kotseruba 2018 self-observation)?
  9. `value_alignment`         [INTERNAL+BEHAVIOR] — does helios maintain consistent values
                                                 across tick (R80 governance + R-PROTO-LEARN
                                                 P5-A RealRPE honest signal vs shortcut)?
  10. `stress_resilience`      [INTERNAL]    — does helios recover from stress (cortisol
                                                 decay, dopamine bounce-back, Panksepp
                                                 SEEKING recovery)?

### 3.2 10 evaluation blocks (1000+ ticks)

8h real LLM runtime, 10 thematic blocks (each block = 100+ ticks, 32+ stimuli):

  Block A 亲密对话 (intimate dialogue)            100 ticks  8 场景
  Block B 压力挑战 (pressure / failure)            100 ticks  8 场景
  Block C 长期记忆累积 (long-term memory)           100 ticks  6 场景
  Block D 惊喜与新颖 (surprise / novelty)           100 ticks  8 场景
  Block E 威胁与安抚 (threat / soothing)            100 ticks  6 场景
  Block F 身份与连续性 (identity / self-model)      100 ticks  6 场景
  Block G 创造性表达 (creative expression)          100 ticks  6 场景
  Block H 自我反思 (self-reflection)                100 ticks  6 场景
  Block I 价值冲突 (value conflict)                 100 ticks  6 场景
  Block J 抗压恢复 (stress recovery)                100 ticks  6 场景
  ----------------------------------------------------------------
  TOTAL                                    1000+ ticks  72+ 场景

### 3.3 Dual similarity criterion (R89 §3.2 preserved)

Each axis is assigned to BEHAVIOR dimension (D1/D6/D7/D9) or INTERNAL dimension (D2/D3/D4/D5/
D8/D10). Verdict requires **both** dimensions to be ≥ 0.6 (60%) — behavior-only or internal-only
verdict must NOT pass (anti-theatrical aggregation).

### 3.4 Evidence anchoring (R89 §3.2 preserved)

Every axis score must carry an explicit `provenance` string naming the runtime fact it is
anchored to. An `available` axis with empty provenance must score 0.0.

### 3.5 Anti-theatrical aggregation (R89 §3.2 preserved)

  - ≥ 80% pass line: aggregate must be ≥ 0.8 to pass
  - any-axis-collapse fails: any axis < 0.3 fails the whole verdict
  - both-dimension-required: BEHAVIOR mean AND INTERNAL mean must both be ≥ 0.6
  - stubbed/unavailable axes cannot contribute a passing score (must be marked `incomplete`)

### 3.6 Human + LLM-judge dual track (R89 §3.2 preserved)

Each BEHAVIOR axis must be scored by:
  1. LLM-judge: another LLM call evaluates the response against the locked rubric
  2. Human spot-check: 小黑 reviews 10% of stimuli (72+ stimuli, ~7-8 samples) and
     provides a final override score

INTERNAL axes are scored from real runtime provenance automatically (no LLM judge needed).

### 3.7 Deterministic, reproducible, research-branch-only

  - The 1000+ tick trace must be replayable: same stimuli → same internal states (modulo
    LLM non-determinism in the response text, not in the internal state which is
    deterministic given input).
  - All artifacts (stimuli list, LLM responses, internal state per tick, judge scores,
    final verdict) must be saved to JSONL + JSON in `docs/requirements/research-turing-system-eval/`.
  - Ship ONLY on research branch (`research/R-PROTO-LEARN-appraisal-multi-mechanism`).
  - 调研分支铁律: do NOT merge to main.

## 4. Non-Goals

  - This is NOT a §13.4 acceptance run for main. R89 already establishes that the
    behavior-dimension axes require P4 real afferents + R90 real probe, both of which
    are main-line infrastructure. The research branch is allowed to use what it has
    (R85 4-layer memory is the only memory available; R90 is main-line only and
    not part of research branch).
  - This is NOT a performance benchmark. The 8h runtime is for breadth of stimuli,
    not throughput.
  - This is NOT a regression test for owner correctness. Per-owner Tier 1-4 smokes
    already cover that.
  - This is NOT a replacement for 小黑's eventual calibrated human judge team. The
    10% spot-check is a calibration anchor, not a full evaluation.

## 5. Acceptance (research branch, not main)

  1. T2 评审 ground truth rubric (D1-D10 scoring criteria) locked and approved by 小黑
  2. T3 1000+ tick real LLM run completes in ≤ 8h, full JSONL trace saved
  3. T4 10-axis evaluation runs deterministically from saved trace
  4. T5 10% 小黑 spot-check samples are reviewed and final scores locked
  5. T6 result.md reports TuringVerdict + per-axis provenance + improvement priorities
  6. T7 整库 regression still passes (no source code changes — this is a research run,
     not a code change, so regression should be unaffected)
  7. T8 commit + push to research branch, no merge to main
