# Requirement 17 - Evaluation fidelity and diagnostic provenance design

## 1. Design Overview

The evaluation owner assembles read-only diagnostic artifacts from v2 runtime evidence. It publishes structured scores, warnings, long-range continuity diagnostics, and cross-run comparison-ready provenance without influencing runtime behavior.

## 2. Implemented Slice

V2 now has a first-version evaluation owner. `17` sits after `15`, consumes explicit stage results from thought, action externalization, planner bridge, identity governance, experience writeback, prompt-contract publication, and the two-layer outward-expression artifact chain, then publishes one read-only evaluation artifact.

## 3. Target Architecture

The implemented slice contains eight runtime concepts:

1. `EvaluationRequest`
2. `EvaluationEvidenceBundle`
3. `EvaluationArtifact`
4. `FidelityWarning`
5. `EvaluateEvidenceBundleOp`
6. `PublishEvaluationArtifactOp`
7. `EvaluationStageResult`
8. `EvaluationAPI`

Implementation boundary confirmation:

1. `17` is read-only.
2. `17` consumes only explicit owner outputs and recorded provenance.
3. `EvidenceBundle -> EvaluationArtifact` is the required public transformation.
4. `17` consumes the two-layer outward-expression artifact chain through formal runtime evidence rather than logs.

## 4. Data Structures

### 4.1 EvaluationRequest
- `request_id: str`
- `scenario_kind: str`
- `time_window_summary: dict[str, object]`

### 4.2 EvaluationEvidenceBundle
- `bundle_id: str`
- `source_request_id: str`
- `thought_evidence: tuple[dict[str, object], ...]`
- `action_evidence: tuple[dict[str, object], ...]`
- `planner_evidence: tuple[dict[str, object], ...]`
- `governance_evidence: tuple[dict[str, object], ...]`
- `writeback_evidence: tuple[dict[str, object], ...]`
- `prompt_evidence: tuple[dict[str, object], ...]`
- `outward_expression_evidence: tuple[dict[str, object], ...]`
- `outward_expression_externalization_evidence: tuple[dict[str, object], ...]`

### 4.3 FidelityWarning
- `warning_id: str`
- `warning_kind: str`
- `evidence_refs: tuple[str, ...]`

### 4.4 EvaluationArtifact
- `artifact_id: str`
- `source_bundle_id: str`
- `dimension_scores: dict[str, float]`
- `gap_summary: dict[str, object]`
- `fidelity_warnings: tuple[FidelityWarning, ...]`
- `long_range_diagnostics: dict[str, object]`

### 4.5 EvaluateEvidenceBundleOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `bundle_id: str`
- `scenario_kind: str`

## 5. Module Changes

1. `evaluation/contracts.py` defines typed read-only evaluation contracts.
2. `evaluation/engine.py` implements deterministic artifact assembly, gap reporting, incompleteness warnings, and long-range diagnostics from explicit evidence bundles.
3. `runtime/stages.py` adds `EvaluationRequestProvider`, `EvaluationStageResult`, and `EvaluationRuntimeStage`, which convert explicit upstream stage results into one evaluation request and one evidence bundle.
4. `runtime/__init__.py` and `helios_v2/__init__.py` export the runtime and top-level public API surface.
5. Tests validate evidence completeness, outward-expression artifact consumption, gap reporting, and deterministic artifact generation.

## 6. Failure Modes and Constraints

1. Missing required evidence categories produce explicit incompleteness warnings.
2. No runtime mutation path exists inside `17`.
3. Missing request-to-bundle provenance is a hard-stop contract error.

## 7. Validation Strategy

1. Unit test immutable evaluation artifacts.
2. Unit test explicit thought-to-action gap reporting.
3. Unit test long-range diagnostics publication.
4. Unit test formal outward-expression artifact-chain consumption.
5. Unit test runtime-stage/provider wiring.

## 8. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `14 passed`
2. `pytest helios_v2/tests -q` -> `192 passed`

Delivered first-version behavior:

1. Runtime publishes one read-only `EvaluationArtifact` after the writeback stage from explicit owner outputs only.
2. The evidence bundle distinguishes thought, action, planner, governance, writeback, prompt, outward-expression, and outward-expression externalization evidence.
3. The artifact publishes explicit gap summaries for thought-to-action, action-to-writeback, and the two-layer outward-expression artifact chain.
4. Long-range diagnostics are published explicitly from request time-window context plus evidence-derived continuity state.
