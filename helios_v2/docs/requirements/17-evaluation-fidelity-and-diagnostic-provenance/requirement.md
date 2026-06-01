# Requirement 17 - Evaluation fidelity and diagnostic provenance

## 1. Background and Problem

By the time v2 reaches `13-16`, the runtime can define thought, action, governance, continuity writeback, and embodied prompt assembly. But none of that is sufficient unless the project can evaluate whether internal activation truly produces externally relevant behavior and long-horizon continuity. Evaluation must therefore become a first-class owner rather than an informal report layer.

The project philosophy explicitly forbids evaluation from mutating runtime behavior, yet it still needs one formal owner for evidence-driven diagnostic publication. Without that owner, the system risks overestimating progress by counting internal traces that never reach visible behavior, continuity, or governed self-evolution.

## 2. Goal

Create an evaluation owner that consumes read-only v2 owner outputs, publishes evidence-driven diagnostic artifacts, exposes thought-to-action-to-writeback gap analysis, and preserves provenance-rich fidelity reporting without mutating runtime behavior or bypassing owner boundaries.

## 3. Functional Requirements

### 3.1 Owner boundary
1. `17` must be the sole owner of read-only diagnostic artifact assembly and fidelity evaluation in v2.
2. `17` must remain separate from runtime mutation, planner authority, channel execution, governance decisions, and storage writes.
3. `17` must not reclaim control over runtime thresholds or execution policy.

### 3.2 Evidence-driven evaluation
1. Evaluation must consume structured owner outputs rather than relying on logs alone.
2. Evaluation must support at least thought, action proposal, planner outcome, execution outcome, continuity writeback, and identity-governance evidence.
3. Evaluation must expose where the chain broke when visible behavior or continuity did not materialize.

### 3.3 Diagnostic provenance
1. Every reported warning or score must be traceable to explicit runtime evidence categories.
2. Evaluation must distinguish internal activity from externally consequential activity.
3. Evaluation must distinguish blocked, rejected, executed, and continuity-written paths.

### 3.4 Long-range fidelity
1. Evaluation must support longer-horizon continuity diagnostics rather than single-turn snapshots only.
2. The owner must expose at least late-session degradation, continuity carry persistence, specific recall persistence, and user-visible anchoring drift diagnostics.
3. Evaluation must preserve provenance-rich artifact output for comparison between runs.

### 3.5 No fallback behavior
1. Missing required evidence inputs must fail explicitly or publish explicit incompleteness warnings.
2. `17` must not silently infer strong fidelity from missing provenance.

## 4. Non-Functional Requirements

1. Evaluation is read-only and must not mutate runtime behavior.
2. Diagnostic artifacts must be deterministic for identical evidence inputs and identical scoring policy.
3. Artifacts must remain comparable across runs.

## 5. Code Behavior Constraints
1. Evaluation code must not reach into private runtime state.
2. Evaluation code must not bypass owner APIs by scraping transient locals.
3. Evaluation code must not hide missing evidence behind optimistic defaults.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/evaluation/contracts.py`
2. `helios_v2/src/helios_v2/evaluation/engine.py`
3. `helios_v2/src/helios_v2/evaluation/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_evaluation_contracts.py`
8. `helios_v2/tests/test_evaluation_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The package defines a documented API for evidence-driven diagnostic artifact assembly.
2. Evaluation remains read-only by contract.
3. Diagnostic artifacts expose thought-to-action-to-writeback gap analysis.
4. Long-range fidelity diagnostics are represented explicitly.
5. Evaluation formally consumes the two-layer outward-expression artifact chain rather than relying on logs or ad-hoc scraping.

## 8. Implementation Status

Status on 2026-06-01: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/evaluation/contracts.py` defines immutable evaluation config, request, evidence-bundle, warning, artifact, and publication-op contracts.
2. `helios_v2/src/helios_v2/evaluation/engine.py` defines owner-private `FirstVersionEvaluationPath`, deterministic read-only artifact assembly, explicit gap analysis, incompleteness warnings, and long-range diagnostic publication from explicit evidence categories.
3. `helios_v2/src/helios_v2/runtime/stages.py` wires `EvaluationRuntimeStage` after `15`, with a runtime-owned `EvaluationRequestProvider` that converts explicit stage results into one `EvaluationRequest` and one `EvaluationEvidenceBundle`.
4. The evidence bundle now formally consumes `11` thought results, `12` action-externalization results, `13` planner outcomes, `14` governance outcomes, `15` writeback outcomes, `16` prompt contracts, and the two-layer outward-expression artifact chain (`OutwardExpressionDraft` plus `OutwardExpressionExternalizationDraft`).
5. `helios_v2/tests/test_evaluation_contracts.py`, `helios_v2/tests/test_evaluation_engine.py`, and `helios_v2/tests/test_runtime_stage_chain.py` cover immutability, explicit outward-expression artifact consumption, gap reporting, long-range diagnostics, and runtime-chain publication.

Validated outcomes:

1. `pytest helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `14 passed`
2. `pytest helios_v2/tests -q` -> `192 passed`

Implementation note:

1. The current first-version path is strictly read-only: it assembles evidence and publishes diagnostic artifacts, but does not mutate runtime behavior, planner authority, channel execution, governance judgment, or storage writes.
