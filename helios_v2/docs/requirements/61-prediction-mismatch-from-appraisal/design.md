# Requirement 61 - Prediction-Mismatch Evidence Grounded in Real Appraisal Novelty

## 1. Design Overview

Replace the constant inside `FirstVersionPredictionMismatchEvidenceBridge` with a derivation
from the real `03` appraisal result already present in the frame. The memory stage runs after
`03` (stage 2), so the frame's `rapid_salience_appraisal` stage result holds the real
`RapidAppraisalBatch` this tick. The bridge reads the real per-stimulus `novelty` (the
functional surprise core: distance from stored experience) and `uncertainty` (retrieval
ambiguity), maps them into the `06` `PredictionMismatchEvidence` contract, and — below a
documented low-novelty threshold — returns `None` so the tick is treated as a non-surprising
`episodic` memory. No `06` policy moves into composition; no forward-model prediction is
invented. The functional grounding (novelty-as-surprise) is recorded honestly.

## 2. Current State and Gap

`FirstVersionPredictionMismatchEvidenceBridge.build_mismatch_evidence(frame, feeling_result)`
returns a fixed `PredictionMismatchEvidence(mismatch_score=0.8, anomaly_score=0.85,
confidence=0.9, source_reference_id=feeling_result.state.state_id)` every tick, in every
assembly. The `06` owner then:
- `SalienceGatedReplayCandidateSelector`: `mismatch_term = clamp(0.6 * 0.8) = 0.48`, taken
  `max` with affect intensity → always a high consolidation floor.
- `AffectGroundedMemoryFormationPath`: `mismatch_evidence is not None` → **every** tick's memory
  is `autobiographical`.

The frame already carries the real surprise signal: `RapidSalienceAppraisalRuntimeStage` writes
`frame.stage_results["rapid_salience_appraisal"]` (a `RapidSalienceAppraisalStageResult` with
`.batch.appraisals[*].salience.novelty` / `.uncertainty`). The mismatch bridge has the same
`frame`. Gap: it ignores the real novelty and emits the constant, so surprise is asserted, not
measured, and every memory is autobiographical.

## 3. Target Architecture

```
FirstVersionPredictionMismatchEvidenceBridge.build_mismatch_evidence(frame, feeling_result):
    appraisal = frame.stage_results.get("rapid_salience_appraisal")   # RapidSalienceAppraisalStageResult
    if not isinstance(appraisal, RapidSalienceAppraisalStageResult) or not appraisal.batch.appraisals:
        return None                                                   # no appraisal -> no surprise signal
    # The dominant percept's real surprise: max novelty across the batch (the most
    # unlike-anything-remembered stimulus drives surprise), plus its uncertainty.
    novelty = max(a.salience.novelty for a in appraisal.batch.appraisals)
    uncertainty = max(a.salience.uncertainty for a in appraisal.batch.appraisals)
    if novelty < MISMATCH_NOVELTY_THRESHOLD:                          # familiar/expected -> no surprise
        return None
    mismatch_score = clamp(novelty)                                   # surprise = novelty
    anomaly_score  = clamp(novelty)                                   # anomaly tracks novelty
    confidence     = clamp(1 - uncertainty)                           # certain when retrieval unambiguous
    return PredictionMismatchEvidence(
        evidence_id=f"mismatch:runtime:{tick_id}",
        source_reference_id=feeling_result.state.state_id,            # real feeling provenance
        mismatch_score=mismatch_score,
        anomaly_score=anomaly_score,
        confidence=confidence,
    )
```

`MISMATCH_NOVELTY_THRESHOLD` (first-version, e.g. `0.5`) is the documented boundary below which a
percept is "familiar/expected" and produces no surprise evidence, so a low-novelty tick becomes
`episodic`. The threshold is an explicit composition-glue constant for the projection cut-point,
not a `06` policy weight (the `06` gate weights stay in `06`).

Mapping rationale (honest, `B_functional_inspiration`): `novelty = 1 - max_cosine_similarity` to
stored experience is the real "this is unlike what I remember" signal — the functional core of
surprise / prediction mismatch in a memory-grounded system. `confidence = 1 - uncertainty` is
high when retrieval was unambiguous (one clear match or clearly nothing) and low when retrieval
was ambiguous. This is NOT a forward-model predictive-coding error; that is a later (P5) concern
and must not be over-claimed.

## 4. Data Structures

No contract changes. The bridge keeps returning the existing `PredictionMismatchEvidence` (or
`None`). New composition-glue constant only:

```python
# R61: below this real-novelty level a percept is familiar/expected and yields no surprise
# evidence (the formed memory is episodic, not autobiographical). First-version cut-point.
_MISMATCH_NOVELTY_THRESHOLD = 0.5
```

`novelty`/`uncertainty` are read from the real `RapidSalienceVector` (already in `[0,1]`); the
mapped scores are clamped/rounded for determinism and the contract's `[0,1]` validation.

## 5. Module Changes

1. `composition/bridges.py`
   - Rewrite `FirstVersionPredictionMismatchEvidenceBridge.build_mismatch_evidence` to read the
     real `03` `RapidSalienceAppraisalStageResult` from the frame, compute the batch-max novelty
     and uncertainty, return `None` below the threshold, and otherwise project the mapped scores
     into `PredictionMismatchEvidence`.
   - Add the module-level `_MISMATCH_NOVELTY_THRESHOLD` constant. Reuse the existing `_clamp`.
   - Lazily import `RapidSalienceAppraisalStageResult` inside the method (the existing bridge
     pattern for stage-result types).
2. Tests (see Validation Strategy).

No change to `MemoryAffectReplayRuntimeStage` or the `06` engine: they already accept
`mismatch_evidence=None` and a varying-score evidence.

## 6. Migration Plan

1. Add `_MISMATCH_NOVELTY_THRESHOLD`.
2. Rewrite the bridge method to derive from the real `03` batch with a low-novelty `None`.
3. Update existing stage-chain/composition tests that assert the old `0.8/0.85/0.9` mismatch
   constant or an always-autobiographical family.
4. Add focused tests: novel percept → high mismatch + autobiographical; familiar percept →
   None mismatch + episodic; default-assembly constant novelty `0.6` (≥ threshold) → a defined
   mismatch derived from `0.6`, not the `0.8` constant.
5. Run the full suite; confirm `06` owner-level tests stay green.
6. Update documentation truth.

Localized change inside one composition bridge method plus one constant; no contract or owner
change, no stage reorder.

## 7. Failure Modes and Constraints

1. No `03` appraisal result / empty appraisal batch → `None` mismatch (no surprise signal). The
   `06` owner already accepts `None` (episodic family, zero mismatch term); the tick proceeds.
   `03` always runs before `06` in the canonical order, so a missing result would be the
   existing hard fail, not silently masked.
2. Low real novelty (familiar percept) → `None` (below threshold). This is the intended
   non-surprising path; the memory is `episodic`.
3. The mapping is total and deterministic; scores are clamped to the `PredictionMismatchEvidence`
   `[0,1]` contract.
4. No fabricated surprise on any path: a high mismatch is emitted only when the real novelty is
   high; absence yields `None`, never a synthetic high score.

## 8. Rollout (Default-On vs Default-Off)

Default-on and unconditional (the bridge is used by every assembly). This is a
correctness/honesty change to the mismatch source, not an opt-in capability. Behavior change is
intended and documented: surprise is now measured from real novelty instead of asserted by a
constant, so not every memory is autobiographical. In the default/recency assemblies `03`
novelty is the first-version constant `0.6` (≥ the `0.5` threshold), so those assemblies still
produce a mismatch (derived from `0.6`, mapping to `mismatch_score=0.6`) and an autobiographical
memory — `03`-driven, not the separate `0.8` constant. In the semantic assembly the mismatch
tracks the real memory-grounded novelty: a cold/dissimilar store yields high novelty → high
mismatch → autobiographical; a similar repeated percept yields low novelty → `None` → episodic.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The bridge
uses neither `logging` nor `print`; the ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. Novelty-driven mismatch (semantic assembly): a cold-store / dissimilar percept (high real
   `03` novelty) yields a high `mismatch_score` (≈ novelty) and the formed memory is
   `autobiographical`; a percept highly similar to stored experience (low novelty) yields `None`
   mismatch and an `episodic` memory.
2. Mismatch tracks novelty: two ticks with different real novelty produce different
   `mismatch_score` (not the constant `0.8`).
3. No constant remains: assert no `0.8/0.85/0.9` mismatch literal in the composition bridge.
4. Default assembly: constant novelty `0.6` (≥ threshold) yields a mismatch derived from `0.6`
   (mapping to `0.6`), proving the source is `03`-driven, not the retired `0.8` constant.
5. `06` mechanism unchanged: the R45 salience-gate / family-mapping owner-level tests stay green
   (they operate on the new evidence without mechanism change). Full network-free suite green;
   owner-boundary and ad-hoc-logging guards green.
