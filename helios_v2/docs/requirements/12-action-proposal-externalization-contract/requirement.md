# Requirement 12 - Action proposal and externalization contract

## 1. Background and Problem

After `11` publishes a formal thought-cycle result, Helios v2 still lacks a dedicated owner that turns optional thought-origin proposal carriers into one explicit externalization contract for later planner and executor owners. Without this owner, the internal-thought layer would continue to normalize channel and outbound fields privately, or the planner would silently absorb thought-origin contract cleanup, drop reasons, and provenance shaping into one mixed controller.

The current legacy implementation proves that the bridge between thought and external action is a real runtime concept rather than incidental plumbing. It already carries `ThoughtActionProposal`, thought-origin `owner_path=thought_action_bridge`, candidate channels, requested op, outbound intensity, explicit drop reasons, and `equivalent_bridge_evidence`, but these semantics remain mixed into thought generation and downstream planner wiring. Helios v2 must separate externalization-contract ownership before planner-executor bridging is defined.

This slice corresponds to the transition from optional thought-origin proposal carriers into a formal externalization contract and explicit bridge-level acceptance or rejection semantics, not to thought generation, planner acceptance, executor dispatch, or identity-governance acceptance.

## 2. Goal

Create an action-proposal externalization owner that consumes optional thought-origin proposal carriers after `11`, normalizes them into one immutable externalization contract, publishes explicit bridge-level rejection or drop outcomes when normalization fails, and preserves thought-to-visible-behavior provenance without fallback behavior, private reach-through, or ownership collapse into planner acceptance or executor dispatch.

## 3. Functional Requirements

### 3.1 Externalization owner boundary
1. The action-proposal externalization layer must be the sole owner of thought-origin proposal normalization and formal externalization-contract publication in this slice.
2. The owner must remain separate from internal-thought execution, planner acceptance, executor dispatch, channel transport, and identity-governance acceptance.
3. The owner must not reinterpret itself as the owner of thought generation, planner feasibility, or final execution success.

### 3.2 Upstream input boundary
1. The action-proposal externalization layer must accept `ThoughtCycleResult` as a required upstream input contract for any thought-origin externalization path.
2. The owner may consume one optional thought-origin proposal carrier from `11`, but only through a documented public contract.
3. The owner may consume bounded current-cycle context needed to normalize target bindings or candidate channels, but only through documented public contracts rather than arbitrary runtime reach-through.
4. The owner must not require direct planner, executor, or channel-owner internals in this slice.
5. The owner must not require direct identity-governance internals in this slice.

### 3.3 Formal externalization contract
1. The first public output of this slice must be one formal thought-origin externalization contract rather than an ad hoc dict carried forward from `11`.
2. The formal contract must preserve at least origin thought id, source owner path, behavior name, preferred op, channel constraints, outbound intensity, reason trace, and governance hints.
3. The formal contract must preserve whether the proposal is explicit or only equivalent bridge evidence.
4. The formal contract must distinguish internal-only versus external-scope proposals explicitly.
5. The formal contract must preserve bridge-level provenance needed to trace a visible action back to one thought cycle.

### 3.4 Bridge-level rejection and drop semantics
1. The externalization owner must publish explicit bridge-level rejection or drop outcomes when a thought-origin proposal carrier cannot be normalized safely.
2. The bridge-level rejection taxonomy must cover at least malformed schema, missing candidate channels, missing required target binding, and missing required outbound text for user-visible external behaviors.
3. The owner must not silently discard an explicit thought-origin proposal carrier.
4. The owner must not silently reinterpret malformed external proposals as internal-only proposals.
5. Bridge-level rejection does not imply planner rejection; those remain distinct downstream semantics.

### 3.5 Equivalent bridge evidence
1. The externalization owner may preserve `equivalent_bridge_evidence` when the current cycle demonstrates thought-origin externalization evidence without a fully explicit formal proposal.
2. Equivalent bridge evidence must remain explicitly distinct from a successfully normalized explicit externalization contract.
3. The owner must preserve `bridge_evidence_kind` or equivalent first-version taxonomy when equivalent evidence is published.
4. Equivalent bridge evidence must not be mislabeled as a fully explicit action proposal.

### 3.6 User-visible outbound text rule
1. If a thought-origin proposal declares `scope=external` for a user-visible speaking or messaging behavior, the formal externalization contract must carry the final outbound user-visible text.
2. The owner must not leave user-visible outbound text generation to later planner, executor, or channel owners.
3. If required outbound text is absent for a user-visible external behavior, the owner must publish an explicit bridge-level rejection or drop outcome.
4. Internal-only proposals and non-user-visible behaviors may omit outbound text when the behavior contract does not require it.

### 3.7 Separation from downstream planner and executor owners
1. The externalization owner may normalize a thought-origin proposal into a formal externalization contract, but it must not decide final planner acceptance in this slice.
2. The externalization owner must not select the final channel binding in this slice.
3. The externalization owner must not execute channel ops in this slice.
4. The externalization owner must not interpret planner or executor failures as if the proposal never existed.

### 3.8 Learned or runtime-provided externalization semantics
1. The owner must not hardcode permanent proposal-normalization formulas, channel-selection formulas, or permanent drop heuristics into the architecture contract.
2. Normalization policy, bridge evidence policy, and bridge-level rejection policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty-proposal defaults, and explicit owner-controlled bootstrap metadata.
4. If the first-version implementation uses deterministic normalization or deterministic bridge evidence rules, that path must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic externalization semantics must remain learning-driven rather than frozen into architecture defaults.

### 3.9 No fallback behavior
1. The action-proposal externalization layer must not synthesize a successful externalization contract when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic externalization path when the configured bridge capability is unavailable.
3. The owner must fail explicitly when required externalization-input invariants are missing.
4. The owner must not silently let downstream planner or executor owners repair malformed thought-origin proposals.
5. The owner must not silently generate missing user-visible text for thought-origin external behaviors in downstream modules.

## 4. Non-Functional Requirements

1. Externalization-contract, bridge-level rejection, and equivalent-evidence contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured externalization policy.
3. The owner boundary must remain separate from thought execution, planner acceptance, executor dispatch, and governance acceptance owners.
4. Published state must preserve enough provenance and bridge-level diagnostics to support later evaluation of whether internal thought truly reached a visible externalization edge.
5. Explicit proposal and equivalent-evidence paths must remain distinguishable in observability and evaluation surfaces.

## 5. Code Behavior Constraints

1. Externalization code must not import planner, executor, channel transport, or identity-governance owners directly.
2. Externalization code must expose only documented APIs and ops contracts across module boundaries.
3. Externalization code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Externalization code must not blur owner boundaries by taking ownership of planner acceptance, executor dispatch, or downstream governance approval.
5. The owner must not permit user-visible external behaviors to proceed without final outbound text in the formal contract.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/action_externalization/contracts.py`
2. `helios_v2/src/helios_v2/action_externalization/engine.py`
3. `helios_v2/src/helios_v2/action_externalization/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_action_externalization_contracts.py`
6. `helios_v2/tests/test_action_externalization_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from `ThoughtCycleResult` into one formal thought-origin externalization contract or one explicit bridge-level rejection outcome.
2. The package defines documented ops contracts for externalization request, successful contract publication, and bridge-level rejection publication.
3. The contract surface preserves origin thought id, owner path, behavior name, preferred op, channel constraints, outbound intensity, reason trace, and governance hints.
4. The contract surface preserves equivalent bridge evidence as a distinct explicit outcome rather than conflating it with a successful explicit proposal.
5. The package records that user-visible external behaviors must carry final outbound text inside the formal externalization contract.
6. The package records that planner acceptance and executor dispatch remain outside `12`.
7. The package does not claim thought generation, planner acceptance, executor dispatch, or governance acceptance ownership.
8. No test or implementation path demonstrates silent drop of explicit thought-origin proposals, downstream repair of malformed proposals, or downstream generation of missing user-visible outbound text.