# Requirement 16 - Embodied subjective prompt and action autonomy

## 1. Background and Problem

After `11-15`, Helios v2 can define the structural runtime chain from conscious content to thought, action, governance, and experience writeback, but it still lacks a sole owner for how the LLM-facing contract should represent the current subjective field. Without such an owner, prompt semantics can drift back into identity theater, reply-first heuristics, or path-specific persona divergence rather than remaining grounded in current stimuli, current state, current memory, and formal action/governance boundaries.

This slice is needed because the final project goal is not only structural state flow, but a coherent first-person integrative layer that turns those owner outputs into grounded thought and outward expression without inventing capabilities or bypassing planner/governance truth.

## 2. Goal

Create a prompt-contract owner that assembles embodied subjective inputs for thought and outward expression, preserves current-stimulus grounding, exposes formal action/governance boundaries to the model, and prevents drift into role-play consciousness or reply-first prompt ownership.

## 3. Functional Requirements

### 3.1 Owner boundary
1. `16` must be the sole owner of embodied subjective prompt-contract assembly in v2.
2. `16` must remain separate from thought-loop ownership, planner/executor ownership, and identity-governance judgment ownership.
3. `16` must not reinterpret itself as the owner of user-visible behavior decisions.

### 3.2 Embodied subjective input assembly
1. `16` must assemble current-stimulus summaries, affective state, continuation state, retrieval bundle, channel/op availability, and identity boundaries into one explicit prompt-facing contract.
2. The contract must represent current stimuli as present sensory field rather than generic chat metadata.
3. The contract must preserve provenance and capability limits rather than inventing channels, ops, or modalities.

### 3.3 Cross-path consistency
1. Internal thought and outward-expression paths must consume the same contract family.
2. Compatibility helpers may remain format adapters only.
3. No path may independently redefine the self-model.

### 3.4 Anti-theatrical constraints
1. `16` must explicitly discourage empty self-consciousness performance and untethered companionship filler.
2. First-person phrasing must remain bound to current evidence, current state, or current unresolved obligation.
3. The contract must preserve user anchoring and boundary respect for user-visible paths.

### 3.5 Action autonomy semantics
1. The contract must explain formal action proposal boundaries instead of allowing free-form execution.
2. Internal, external, and self-revision proposals must remain distinct.
3. Planner/channel/governance remain final truth outside `16`.

### 3.6 No fallback behavior
1. Missing required runtime inputs must fail explicitly.
2. `16` must not silently downgrade to reply-first prompt assembly when required embodied inputs are unavailable.

## 4. Non-Functional Requirements

1. Prompt-facing contract layers must be bounded, auditable, and reusable.
2. Identical upstream owner outputs must produce deterministic contract assembly for the same configured prompt policy.
3. Prompt contract changes must remain testable through runtime traces and evaluation artifacts.

## 5. Code Behavior Constraints
1. Prompt code must not invent capabilities or hidden channels.
2. Prompt code must not reclaim reply-first ownership.
3. Prompt code must not redefine identity-governance rules.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/prompt_contract/contracts.py`
2. `helios_v2/src/helios_v2/prompt_contract/engine.py`
3. `helios_v2/src/helios_v2/prompt_contract/__init__.py`
4. `helios_v2/src/helios_v2/outward_expression/contracts.py`
5. `helios_v2/src/helios_v2/outward_expression/engine.py`
6. `helios_v2/src/helios_v2/outward_expression/__init__.py`
7. `helios_v2/src/helios_v2/outward_expression_externalization/contracts.py`
8. `helios_v2/src/helios_v2/outward_expression_externalization/engine.py`
9. `helios_v2/src/helios_v2/outward_expression_externalization/__init__.py`
10. `helios_v2/src/helios_v2/runtime/stages.py`
11. `helios_v2/tests/test_prompt_contract_v2.py`
12. `helios_v2/tests/test_outward_expression_contracts.py`
13. `helios_v2/tests/test_outward_expression_engine.py`
14. `helios_v2/tests/test_outward_expression_externalization_contracts.py`
15. `helios_v2/tests/test_outward_expression_externalization_engine.py`
16. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The package defines a documented API for embodied subjective prompt-contract assembly.
2. Thought-facing and outward-expression-facing assembly use the same contract family.
3. Prompt semantics remain grounded in current owner outputs and capability truth.
4. The package explicitly records anti-theatrical and anti-reply-first constraints.
5. `16` publishes an outward-expression-side handoff that an independent outward-expression owner can consume without redefining prompt or execution authority.
6. The outward-expression owner publishes a bounded pre-execution draft without taking planner, channel, or transport authority.
7. A downstream outward-expression externalization owner consumes that bounded draft and publishes a more execution-adjacent externalization draft without taking final execution authority.

## 8. Implementation Status

Status on 2026-06-01: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/prompt_contract/contracts.py` defines immutable embodied-prompt request, layer, action-boundary, contract, minimal outward-expression consumer-view, and publication-op contracts.
2. `helios_v2/src/helios_v2/prompt_contract/engine.py` defines owner-private `FirstVersionEmbodiedPromptPath`, deterministic bounded layer assembly, anti-theatrical constraints, action-boundary publication, a minimal outward-expression consumer view, and a formal handoff builder for the outward-expression owner input contract.
3. `helios_v2/src/helios_v2/outward_expression/contracts.py` defines the independent `OutwardExpressionRequest`, `OutwardExpressionDraft`, config surface, and runtime-visible preparation/publication ops for outward-expression draft ownership.
4. `helios_v2/src/helios_v2/outward_expression/engine.py` defines owner-private `FirstVersionOutwardExpressionPath` and deterministic bounded draft assembly that preserves capability boundaries while keeping planner/channel authority outside the owner.
5. `helios_v2/src/helios_v2/outward_expression_externalization/contracts.py` defines the independent externalization-side request/draft contracts plus request/publication ops for the execution-adjacent outward-expression owner.
6. `helios_v2/src/helios_v2/outward_expression_externalization/engine.py` defines owner-private `FirstVersionOutwardExpressionExternalizationPath` and deterministic bounded externalization-draft assembly that preserves planner/channel authority outside the owner.
7. `helios_v2/src/helios_v2/runtime/stages.py` wires `EmbodiedPromptRuntimeStage` between `10` and `11`, wires `OutwardExpressionRuntimeStage` for bounded outward-expression draft assembly, and now also wires `OutwardExpressionExternalizationRuntimeStage` that consumes the outward-expression draft into a bounded externalization-side draft.
8. `11` continues consuming the `thought` prompt-contract summary through runtime wiring, while the outward-expression path now runs through `OutwardExpressionPromptView -> OutwardExpressionRequest -> OutwardExpressionDraft -> OutwardExpressionExternalizationDraft` without claiming final execution ownership.
9. `helios_v2/tests/test_prompt_contract_v2.py`, `helios_v2/tests/test_outward_expression_contracts.py`, `helios_v2/tests/test_outward_expression_engine.py`, `helios_v2/tests/test_outward_expression_externalization_contracts.py`, `helios_v2/tests/test_outward_expression_externalization_engine.py`, and `helios_v2/tests/test_runtime_stage_chain.py` cover contract immutability, cross-path contract-family consistency, anti-theatrical constraints, action-boundary publication, outward-expression owner draft assembly, externalization-side draft assembly, and runtime chaining.

Validated outcomes:

1. `pytest helios_v2/tests/test_outward_expression_externalization_contracts.py helios_v2/tests/test_outward_expression_externalization_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `12 passed`
2. `pytest helios_v2/tests -q` -> `185 passed`

Implementation note:

1. The current first-version path keeps planner, channel, and identity-governance authority outside `16`, and now proves a two-layer outward-expression path where one owner publishes bounded outward-expression drafts and a downstream owner publishes bounded externalization-side drafts without claiming final execution ownership.
