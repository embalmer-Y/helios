# Requirement 14 - Identity governance and self revision integration

## 1. Background and Problem

After `13` closes the thought-to-action bridge, Helios v2 still lacks a sole owner for long-horizon self continuity. The legacy runtime already exposes a real identity-governance loop: internal thought emits optional `self_revision_proposal`, governance validates and judges that proposal, proactive governance pressure can monitor or backpressure low-confidence revisions, accepted revisions mutate identity state, and the runtime emits an auditable revision result. But this behavior is currently split across `cognition/thinking_integration.py`, `identity_governance.py`, `helios_main.py`, `personality_contract.py`, and `feedback_recorder.py`.

Without a dedicated owner, the architecture still leaves critical questions unresolved: who decides whether a thought-origin self revision is valid, who owns proactive governance pressure as a decision input rather than an evaluation artifact, who owns identity mutation, and who publishes the formal result that later personality and audit systems consume.

This slice corresponds to the transition from optional thought-origin self-revision proposal into explicit governance decision and identity-state mutation, not to thought generation, personality projection, or feedback-journal persistence.

## 2. Goal

Create an identity-governance owner that consumes normalized self-revision proposals, evaluates them under explicit governance policy and proactive-pressure state, publishes immutable revision decisions and revision outcomes for accepted and rejected paths, mutates identity state when permitted, and collaborates with downstream personality synchronization and audit persistence without fallback behavior, private reach-through, or ownership collapse into thought generation or projection rendering.

## 3. Functional Requirements

### 3.1 Identity-governance owner boundary
1. Identity governance must be the sole owner of self-revision proposal validation, governance acceptance or rejection, proactive governance pressure evaluation, identity-store mutation, and formal revision-result publication in this slice.
2. The owner must remain separate from thought generation, action bridging, personality projection rendering, and audit persistence.
3. The owner must not reinterpret itself as the owner of thought extraction or of all personality read-model logic.

### 3.2 Upstream input boundary
1. The owner must accept normalized self-revision proposals from upstream thought execution through a documented public contract.
2. The owner may later accept other normalized identity-revision proposal sources, but only through documented public APIs.
3. The owner must consume current identity state and prior governance-trace state only through documented public contracts.
4. The owner must not require private reach-through into thought internals, personality projection internals, or feedback-storage internals.
5. The owner must not require direct memory-system mutation in this slice.

### 3.3 Proposal validation and governance decision ownership
1. The first public output of this slice must be one formal governance result rather than store mutation or logs alone.
2. The owner must validate required proposal fields including origin thought reference, revision type, requested change, scope, and governance-relevant confidence or reason-trace data.
3. If the proposal is malformed or unsupported, the owner must publish one formal rejected governance result.
4. If the proposal is valid, the owner must evaluate whether it should be accepted, monitored, delayed, or rejected according to owner-controlled governance policy.
5. Rejected governance paths must not be represented only as downstream audit events or logs.

### 3.4 Proactive governance pressure ownership
1. Proactive governance pressure, monitoring, and backpressure semantics must belong to `14` because they directly participate in revision judgment.
2. The owner must compute or consume explicit governance pressure state from bounded governance-trace history under its control.
3. The owner must distinguish at least no pressure, monitoring pressure, and stabilizing backpressure semantics.
4. Monitoring pressure may annotate accepted revisions with explicit review hints or reason trace.
5. Stabilizing backpressure may reject low-confidence identity revisions according to owner-controlled policy.
6. Governance pressure state must not exist only as passive observability metadata.

### 3.5 Identity mutation ownership
1. If a revision is accepted, the owner must apply the allowed mutation to identity state.
2. Identity mutation must support at least self-definition revision, personality-baseline adjustment, and autobiographical identity-narrative revision.
3. Unsupported revision types must produce explicit rejected governance results.
4. Identity-boundary violations must produce explicit rejected governance results.
5. Accepted identity mutations must publish applied-change detail separately from requested-change detail.
6. The owner must update revision history and current revision only through explicit accepted revision handling.

### 3.6 Formal revision-result publication
1. Every evaluated proposal path must publish one formal revision result whether accepted or rejected.
2. Formal revision results must preserve proposal provenance, requested change, applied change, result status, and reason trace.
3. Invalid proposal payloads must produce explicit formal rejected outcomes rather than disappearing into runtime-local trace dictionaries.
4. The contract surface must make governance monitoring, governance backpressure, and identity-boundary rejection distinguishable.

### 3.7 Separation from personality sync and audit persistence
1. The owner may publish updated identity state for downstream personality synchronization, but it must not own personality projection or personality sync application in this slice.
2. The owner may collaborate with downstream audit persistence, but it must not own feedback-journal persistence in this slice.
3. The owner must publish normalized revision results before or alongside downstream collaboration rather than relying on recorder state as the primary contract.
4. The owner must not directly own prompt rendering or expression generation in this slice.

### 3.8 Learned or runtime-provided governance semantics
1. The owner must not hardcode permanent identity policies, rejection formulas, or personality ideals into the architecture contract.
2. Governance evaluation policy, pressure interpretation policy, supported revision policy, and boundary-check policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than frozen strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit bootstrap defaults, and explicit owner-controlled schema metadata.
4. If the first-version implementation uses deterministic revision-type handling or deterministic confidence thresholds, that path must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic identity governance must remain learning-driven rather than frozen into architecture defaults.

### 3.9 No fallback behavior
1. The owner must not synthesize an accepted revision when required proposal or identity-state inputs are missing or malformed.
2. The owner must not downgrade to ad hoc direct store mutation when the configured governance capability is unavailable.
3. The owner must fail explicitly when required proposal, governance-state, or identity-state invariants are missing.
4. The owner must not silently let downstream personality or audit layers repair malformed revision decisions.
5. The owner must not silently drop rejected governance outcomes just because downstream persistence still occurs.

## 4. Non-Functional Requirements

1. Governance request, governance result, identity mutation result, and revision-state publication contracts must be immutable after publication.
2. Identical proposals and identical identity-governance state must produce deterministic results for the same configured governance policy.
3. The owner boundary must remain separate from thought generation, personality projection rendering, and audit persistence.
4. Published state must preserve enough provenance and reason-trace detail to support later evaluation of why a self revision was accepted, monitored, backpressured, or rejected.
5. Accepted mutation, monitored acceptance, rejected governance result, and invalid payload rejection must remain explicitly distinguishable.

## 5. Code Behavior Constraints
1. Governance code must not import internal-thought generation owners, personality rendering owners, or feedback-storage internals directly.
2. Governance code must expose only documented APIs and ops contracts across module boundaries.
3. Governance code must not encode permanent hardcoded thresholds, personality ideals, or fallback repair branches as architecture truth.
4. Governance code must not blur owner boundaries by taking ownership of personality projection or audit persistence.
5. Rejected or invalid revision outcomes must not disappear into logs alone.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/identity_governance/contracts.py`
2. `helios_v2/src/helios_v2/identity_governance/engine.py`
3. `helios_v2/src/helios_v2/identity_governance/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_identity_governance_contracts.py`
6. `helios_v2/tests/test_identity_governance_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The requirement package defines a documented API from normalized self-revision proposals into one formal governance result and, when accepted, one applied identity-state publication.
2. The package defines documented ops contracts for governance evaluation request, revision-result publication, governance-pressure publication, and applied-identity-state publication.
3. The contract surface publishes formal governance results for accepted, monitored-accepted, rejected, and invalid-proposal paths.
4. The package records that proactive governance pressure is owned inside `14` rather than left as passive observability.
5. The package records that personality synchronization remains downstream collaboration rather than part of the identity-governance owner itself.
6. The package records that audit persistence remains downstream collaboration rather than part of the identity-governance owner itself.
7. The package does not claim thought-generation, personality-projection, or feedback-persistence ownership.
8. No test or implementation path demonstrates silent repair of malformed revision proposals by downstream layers or silent disappearance of rejected governance outcomes.

## 8. Implementation Status

Status on 2026-06-01: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/identity_governance/contracts.py` defines immutable governance request, normalized self-revision proposal, pressure-state, revision-decision, applied-identity-state, result, and ops contracts.
2. `helios_v2/src/helios_v2/identity_governance/engine.py` defines fail-fast validation, owner-private `FirstVersionIdentityGovernancePath`, deterministic proactive-pressure evaluation, revision judgment, and identity-state publication behavior.
3. `helios_v2/src/helios_v2/runtime/stages.py` wires `IdentityGovernanceRuntimeStage` from `11` through a runtime-owned `IdentityGovernanceRequestProvider`.
4. `helios_v2/tests/test_identity_governance_contracts.py`, `helios_v2/tests/test_identity_governance_engine.py`, and `helios_v2/tests/test_runtime_stage_chain.py` cover contract immutability, accepted-with-monitoring, stabilizing backpressure rejection, accepted mutation publication, and `11 -> 14` runtime chaining.

Validated outcomes:

1. `pytest helios_v2/tests/test_identity_governance_contracts.py helios_v2/tests/test_identity_governance_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `159 passed`

Implementation note:

1. The current first-version path preserves three deterministic mutation categories: `self_definition_revision`, `personality_adjustment`, and `autobiographical_identity_narrative_revision`, while keeping personality synchronization and audit persistence outside the `14` owner boundary.