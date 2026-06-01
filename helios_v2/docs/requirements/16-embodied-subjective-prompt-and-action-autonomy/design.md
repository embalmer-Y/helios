# Requirement 16 - Embodied subjective prompt and action autonomy design

## 1. Design Overview

The embodied-subjective prompt owner assembles the LLM-facing representation of the current moment from prior v2 owner outputs. The implemented first-version slice exposes one bounded contract family for `thought` and `outward_expression` consumers, preserving current-stimulus grounding, memory relevance, continuity carry, channel/op limits, and identity boundaries.

## 2. Implemented Slice

V2 now has a v2-native owner for grounded prompt assembly. `16` sits after directed retrieval and before internal thought, publishes a shared prompt-contract family for `thought` and `outward_expression`, provides the `thought` contract summary to `11` through explicit runtime wiring, derives a minimal outward-expression consumer view from the outward-expression-side contract, publishes an `OutwardExpressionRequest` handoff, feeds that handoff into a real independent outward-expression owner that prepares bounded pre-execution drafts, and then feeds those drafts into a downstream outward-expression externalization owner that prepares execution-adjacent externalization drafts.

## 3. Delivered Architecture

The implemented slice contains twelve public runtime concepts:

1. `EmbodiedPromptRequest`
2. `EmbodiedPromptContract`
3. `PromptContractLayer`
4. `PromptActionBoundary`
5. `BuildEmbodiedPromptOp`
6. `PublishEmbodiedPromptContractOp`
7. `OutwardExpressionPromptView`
8. `OutwardExpressionRequest`
9. `OutwardExpressionDraft`
10. `OutwardExpressionExternalizationRequest`
11. `OutwardExpressionExternalizationDraft`
12. `EmbodiedPromptAPI`

Implementation boundary confirmation:

1. `16` owns only prompt-contract assembly.
2. `16` does not own thought results, planner results, or governance judgments.
3. Prior owner outputs are consumed through explicit request contracts only.
4. `16` publishes an outward-expression-facing contract family member and consumes it into a minimal non-executing outward-expression view plus a formal owner request handoff without claiming execution ownership for that path.
5. The independent outward-expression owner consumes that handoff and publishes bounded drafts, but final planner/channel/transport authority remains outside the owner.
6. A downstream outward-expression externalization owner consumes those drafts and publishes more execution-adjacent externalization drafts, but final planner/channel/transport authority still remains outside the owner.

## 4. Data Structures

### 4.1 EmbodiedPromptRequest
- `request_id: str`
- `consumer_kind: str`
- `source_conscious_state_id: str`
- `source_gate_result_id: str`
- `source_retrieval_bundle_id: str`
- `stimulus_summary: dict[str, object]`
- `state_summary: dict[str, object]`
- `retrieval_summary: dict[str, object]`
- `capability_summary: dict[str, object]`
- `identity_boundary_summary: dict[str, object]`

### 4.2 PromptContractLayer
- `layer_name: str`
- `content: str`
- `required: bool`

### 4.3 PromptActionBoundary
- `supports_internal_action: bool`
- `supports_external_action_proposal: bool`
- `supports_self_revision_proposal: bool`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`

### 4.4 EmbodiedPromptContract
- `contract_id: str`
- `consumer_kind: str`
- `source_request_id: str`
- `layers: tuple[PromptContractLayer, ...]`
- `action_boundary: PromptActionBoundary`
- `capability_snapshot: dict[str, object]`
- `anti_theatrical_constraints: tuple[str, ...]`

### 4.5 OutwardExpressionPromptView
- `view_id: str`
- `source_contract_id: str`
- `rendered_prompt: str`
- `available_channels: tuple[str, ...]`
- `available_ops: tuple[str, ...]`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`
- `anti_theatrical_constraints: tuple[str, ...]`

### 4.6 OutwardExpressionRequest
- `request_id: str`
- `source_prompt_view_id: str`
- `source_prompt_contract_id: str`
- `rendered_prompt: str`
- `available_channels: tuple[str, ...]`
- `available_ops: tuple[str, ...]`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`
- `anti_theatrical_constraints: tuple[str, ...]`

### 4.7 OutwardExpressionDraft
- `draft_id: str`
- `source_request_id: str`
- `source_prompt_view_id: str`
- `source_prompt_contract_id: str`
- `rendered_prompt: str`
- `delivery_channels: tuple[str, ...]`
- `delivery_ops: tuple[str, ...]`
- `delivery_guidance: str`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`
- `anti_theatrical_constraints: tuple[str, ...]`

### 4.8 OutwardExpressionExternalizationRequest
- `request_id: str`
- `source_outward_expression_draft_id: str`
- `source_prompt_contract_id: str`
- `rendered_prompt: str`
- `delivery_channels: tuple[str, ...]`
- `delivery_ops: tuple[str, ...]`
- `delivery_guidance: str`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`
- `anti_theatrical_constraints: tuple[str, ...]`

### 4.9 OutwardExpressionExternalizationDraft
- `draft_id: str`
- `source_request_id: str`
- `source_outward_expression_draft_id: str`
- `source_prompt_contract_id: str`
- `externalization_prompt: str`
- `candidate_channels: tuple[str, ...]`
- `candidate_ops: tuple[str, ...]`
- `execution_boundary_summary: str`
- `forbidden_capabilities: tuple[str, ...]`
- `final_authorities: tuple[str, ...]`
- `anti_theatrical_constraints: tuple[str, ...]`

Implemented layer family:

1. `present_field`
2. `embodied_state`
3. `memory_and_continuity`
4. `action_autonomy`
5. `anti_theatrical_constraints`
6. `consumer_orientation`

The first-version path keeps the same layer family for both `thought` and `outward_expression`, while allowing consumer-specific orientation and action-boundary flags.

## 5. Module Changes

1. `prompt_contract/contracts.py` defines owner declaration, typed contracts, fixed consumer taxonomy, action-boundary contract, and ops contracts.
2. `prompt_contract/engine.py` implements bounded contract assembly, anti-theatrical constraints, explicit action-boundary publication, minimal outward-expression consumer-view derivation, and outward-expression request handoff assembly.
3. `outward_expression/contracts.py` defines the independent outward-expression request, bounded draft, config, and runtime-visible ops contracts.
4. `outward_expression/engine.py` implements bounded outward-expression draft assembly from the prompt-owned request while preserving non-authoritative delivery guidance semantics.
5. `outward_expression_externalization/contracts.py` defines the independent externalization request, bounded externalization draft, config, and runtime-visible ops contracts.
6. `outward_expression_externalization/engine.py` implements bounded outward-expression externalization draft assembly from the outward-expression draft while preserving non-authoritative execution-boundary semantics.
7. `prompt_contract/__init__.py`, `outward_expression/__init__.py`, and `outward_expression_externalization/__init__.py` export the public owner surfaces.
8. `runtime/stages.py` adds `EmbodiedPromptStageResult`, `EmbodiedPromptRequestProvider`, `EmbodiedPromptRuntimeStage`, `OutwardExpressionRuntimeStage`, and `OutwardExpressionExternalizationRuntimeStage`; `InternalThoughtRuntimeStage` still consumes only the `thought` contract through explicit stage chaining, while the outward-expression path now composes two draft owners in sequence.
9. `runtime/__init__.py` and `helios_v2/__init__.py` export the runtime and top-level public API surface.
10. Tests validate grounding, bounded layers, shared contract family, anti-theatrical constraints, outward-expression owner draft assembly, outward-expression externalization draft assembly, and runtime-stage wiring.

## 6. Failure Modes and Constraints

1. Missing required upstream owner output raises an explicit owner error.
2. Malformed capability summary must fail publication.
3. No reply-first fallback path is allowed.

## 7. Validation Strategy

1. Unit test immutable prompt contracts.
2. Unit test cross-path contract-family consistency.
3. Unit test explicit capability-boundary publication.
4. Unit test outward-expression request handoff assembly.
5. Unit test outward-expression draft assembly.
6. Unit test outward-expression externalization draft assembly.
7. Unit test runtime-stage/provider wiring.

## 8. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_outward_expression_externalization_contracts.py helios_v2/tests/test_outward_expression_externalization_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `12 passed`
2. `pytest helios_v2/tests -q` -> `185 passed`

Delivered first-version behavior:

1. Runtime publishes one `thought` embodied prompt contract and one `outward_expression` embodied prompt contract in the same tick from a shared layer family.
2. `11` consumes the `thought` contract through explicit runtime wiring instead of a placeholder prompt summary.
3. The `outward_expression` contract is consumed into a minimal `OutwardExpressionPromptView`, preserving a prompt-facing second-side consumer without turning prompt assembly into execution ownership.
4. The same outward-expression-side view is normalized into a formal `OutwardExpressionRequest`, which the independent outward-expression owner consumes directly.
5. The outward-expression owner publishes an `OutwardExpressionDraft` with bounded delivery guidance, while planner/channel/transport authority remains outside the owner.
6. A downstream outward-expression externalization owner consumes that draft and publishes an `OutwardExpressionExternalizationDraft` with execution-boundary guidance, while planner/channel/transport authority still remains outside the owner.
