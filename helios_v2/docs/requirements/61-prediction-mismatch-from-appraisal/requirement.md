# Requirement 61 - Prediction-Mismatch Evidence Grounded in Real Appraisal Novelty

## 1. Background and Problem

The `06` memory owner consumes optional `PredictionMismatchEvidence` for two decisions:

1. `SalienceGatedReplayCandidateSelector` folds `mismatch_score` into the consolidation
   salience (`max(affect_intensity, 0.6 * mismatch_score)`), so a high mismatch makes a tick's
   memory consolidation-worthy even when affect is flat.
2. `AffectGroundedMemoryFormationPath` maps a tick that carries mismatch evidence to the
   `autobiographical` memory family (genuine surprise → autobiographical), and a tick without
   it to `episodic`.

Today that evidence comes from `FirstVersionPredictionMismatchEvidenceBridge`, which returns a
hardcoded constant in every assembly:

```
PredictionMismatchEvidence(
    evidence_id=f"mismatch:runtime:{tick_id}",
    source_reference_id=feeling_result.state.state_id,
    mismatch_score=0.8, anomaly_score=0.85, confidence=0.9,
)
```

Two concrete consequences:

1. Under `FG-1`, the mismatch/surprise signal is a composition-injected constant, not a real
   signal. It is the `06` salience gate's second input (the first, affect intensity, became
   real with R45/R51); with R59/R60 the perception and memory-content positions are real, so
   the mismatch constant is the next fabricated position in the perception-affect-memory chain.
2. Because the constant is always present and high (`0.8`), every tick's memory is marked
   `autobiographical` and the consolidation gate is always pushed toward forced consolidation
   regardless of whether the percept was actually surprising. So "surprise drives what the
   system remembers" — a core hippocampal/ACC function — is asserted by a constant, not
   measured.

The architecture already computes a real functional analog of surprise: the `03` appraisal
`novelty` dimension is `1 - max_cosine_similarity` to stored experience ("this is unlike
anything I remember"), and `uncertainty` is retrieval ambiguity. R61 grounds the mismatch
evidence in those real `03` signals instead of a constant, without fabricating a forward-model
prediction.

## 2. Goal

Derive the `06` prediction-mismatch evidence each tick from the real `03` appraisal output
(novelty as the surprise core, with uncertainty as retrieval ambiguity) so that genuinely
novel/surprising percepts measurably raise consolidation salience and bias memory toward the
autobiographical family, while familiar/expected percepts produce low or no mismatch — replacing
the hardcoded constant, and without inventing a predicted state the system does not have.

## 3. Functional Requirements

### 3.1 Mismatch grounded in real appraisal

1. The mismatch evidence each tick must be derived from the real `03` `RapidSalienceAppraisalStageResult`
   in the frame: `mismatch_score` must be a bounded function of the real appraisal `novelty`
   (the surprise core), and `anomaly_score`/`confidence` must be derived mechanically from the
   real appraisal signals (e.g. anomaly from novelty, confidence from how much comparable memory
   existed / retrieval certainty), never hardcoded constants.
2. The derivation must be owner-neutral transport: composition projects real `03` facts into the
   `06` `PredictionMismatchEvidence` contract; it must not compute the `06` consolidation gate or
   family mapping (those stay in the `06` owner), and must not invent a predicted state.
3. The mismatch evidence must preserve real provenance (referencing the real appraisal/feeling
   state) so a later reader can trace why a memory was treated as surprising.

### 3.2 Honest low/absent mismatch

1. When the percept is not novel (low real novelty — familiar/expected, e.g. a repeated
   stimulus close to stored experience), the bridge must produce a correspondingly low mismatch,
   and below a documented threshold it must produce no mismatch evidence (`None`) so the `06`
   owner treats the tick as a non-surprising `episodic` memory rather than always
   `autobiographical`.
2. Producing `None` on a non-surprising tick must keep the tick valid: `06` already accepts
   `mismatch_evidence=None` (it maps to `episodic` family and a zero mismatch term), and the
   chain closes normally.

### 3.3 Behavioral scope

1. The change must affect only the mismatch-evidence source. The `06` salience gate, family
   mapping, durability, and recalled replay are unchanged in mechanism; they now operate on a
   real novelty-grounded mismatch instead of the constant.
2. The default and recency-only assemblies (where `03` novelty is the first-version constant
   `0.6`, not memory-grounded) must produce a defined, documented mismatch from that constant
   novelty rather than the separate `0.8` mismatch constant — still `03`-driven, not a second
   hardcoded constant.

## 4. Non-Functional Requirements

1. Performance: no measurable per-tick overhead beyond reading the already-present `03` result.
2. Reliability: a malformed `03` result is the existing hard fail upstream; the bridge adds no
   new failure branch and fabricates no mismatch on absence.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the `06` `PredictionMismatchEvidence` contract is unchanged in
   shape. This replaces the evidence *source* inside the composition bridge. Tests asserting the
   old constant scores or always-autobiographical family are updated.

## 5. Code Behavior Constraints

1. Forbidden: a hardcoded mismatch-evidence constant in composition (the `0.8`/`0.85`/`0.9`
   literals) once the appraisal-grounded derivation lands.
2. Forbidden: fabricating a forward-model prediction or a predicted state the runtime does not
   actually hold; the mismatch is grounded in the real, already-computed `03` novelty/uncertainty
   (`ARCHITECTURE_PHILOSOPHY` §4.3/§8). The functional grounding (novelty-as-surprise) must be
   recorded honestly and not over-claimed as a true predictive-coding error signal.
3. Boundary rule: the mismatch bridge is owner-neutral composition glue projecting real `03`
   facts into the `06` contract; it computes no `06` memory policy.
4. Failure mode: a non-surprising (low-novelty) tick yields a low mismatch or `None`, never a
   fabricated high mismatch.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` — replace
   `FirstVersionPredictionMismatchEvidenceBridge`'s constant with derivation from the real `03`
   appraisal result in the frame, with a documented low-novelty `None` threshold.
2. `helios_v2/tests/test_runtime_composition.py` and/or `tests/test_runtime_stage_chain.py` —
   tests: a novel percept yields high mismatch + autobiographical family; a familiar percept
   yields low/no mismatch + episodic family; no hardcoded constant remains; chain stays valid.
3. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 mismatch/surprise grounding + honest caveat).

## 7. Acceptance Criteria

1. With a real semantic assembly and a novel percept (cold/dissimilar store → high real `03`
   novelty), the bridge produces a high `mismatch_score` and the formed memory is
   `autobiographical`; with a familiar percept (high similarity → low novelty) the bridge
   produces a low mismatch or `None` and the formed memory is `episodic`.
2. The `mismatch_score` is a function of the real `03` novelty (verified: different novelty →
   different mismatch), not the constant `0.8`; no `0.8/0.85/0.9` mismatch constant remains in
   composition.
3. The `06` salience gate, family mapping, durability, and recalled replay are unchanged in
   mechanism (their owner-level tests stay green); only the mismatch-evidence source changed.
4. A non-surprising tick that yields `None` mismatch completes the chain without crashing; the
   full network-free suite is green with updated/added tests; owner-boundary and ad-hoc-logging
   guards stay green.
5. `index.md` has a row 61; the `06`/`03` `OWNER_GUIDE` entries and the
   `BRAIN_ARCHITECTURE_COMPARISON` FG-1 note record that mismatch is now grounded in real
   appraisal novelty (with the honest `B_functional_inspiration` caveat that it is
   novelty-as-surprise, not a true predictive-coding error), with sync lines naming R61.
