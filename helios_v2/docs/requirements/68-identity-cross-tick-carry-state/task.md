# Requirement 68 - Identity Cross-Tick Governance Carry State: Task

## 1. Title
Task Plan: Identity Cross-Tick Governance Carry State

## 2. Task Breakdown

### Task 1: Add `GovernanceCarryState` contract
- **Description**: Add frozen `GovernanceCarryState` dataclass to `identity_governance/contracts.py` with `identity_state_snapshot`, `recent_governance_trace_history`, `accepted_revision_count`, `rejected_revision_count`. Include `__post_init__` validation.
- **Completion**: Dataclass importable and constructable.
- **Validation**: `python -m pytest tests/test_identity_governance_contracts.py -xvs`

### Task 2: Add cross-tick carry to `IdentityGovernanceRuntimeStage`
- **Description**: Add `_prior_carry_state` field (default `None`) and `seed_prior_carry_state()` method. Post-evaluation in `run()`: compute next carry state from result + prior. Pass carry state to the request provider via a new `_carry_state` attribute on the stage (readable by the bridge).
- **Completion**: Stage holds and advances carry state across ticks.
- **Validation**: existing stage-chain tests pass.

### Task 3: Update composition bridge to inject carry state
- **Description**: `FirstVersionIdentityGovernanceRequestBridge` gains an optional `carry_state: GovernanceCarryState | None` attribute. `build_request()` uses carry state's `identity_state_snapshot` and `recent_governance_trace_history` when present; falls back to bootstrap constant when `None`. Derives a `governance_trace_summary` dict from the trace history.
- **Completion**: Bridge produces evolved requests; cold-start requests are byte-for-byte identical.
- **Validation**: `python -m pytest tests/test_runtime_composition.py -xvs`

### Task 4: Wire carry state in `runtime_assembly.py`
- **Description**: The `assemble_runtime` function wires the governance bridge's `carry_state` from the runtime stage. The stage exposes `_prior_carry_state` which the bridge reads at request-build time.
- **Completion**: Assembled runtime has cross-tick identity carry.
- **Validation**: existing assembly tests pass.

### Task 5: Add unit tests for carry state
- **Description**: Add tests to `test_identity_governance.py`: (a) request with evolved identity snapshot preserves it; (b) trace history accumulates across simulated ticks.
- **Completion**: Tests pass.

### Task 6: Add integration tests for identity evolution
- **Description**: Add tests to `test_runtime_composition.py`: (a) revision on tick 2 persists into tick 3; (b) 5+ ticks with governance activity accumulate trace history.
- **Completion**: Tests pass.

### Task 7: Run full test suite
- **Description**: Run complete 755+ test suite.
- **Completion**: All pass.

### Task 8: Update index.md and progress flow maps
- **Description**: Add R68 row to index.md; update PROGRESS_FLOW files.
- **Completion**: R68 documented.

## 3. Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1.
- Task 4 depends on Tasks 2, 3.
- Tasks 5, 6 depend on Task 4.
- Task 7 depends on Tasks 5, 6.
- Task 8 depends on Task 7.

## 4. Files and Modules
| File | Change Type |
|------|-------------|
| `helios_v2/src/helios_v2/identity_governance/contracts.py` | Add `GovernanceCarryState` |
| `helios_v2/src/helios_v2/runtime/stages.py` | Add carry state to `IdentityGovernanceRuntimeStage` |
| `helios_v2/src/helios_v2/composition/bridges.py` | Inject carry state in bridge |
| `helios_v2/src/helios_v2/composition/runtime_assembly.py` | Wire carry state |
| `helios_v2/tests/test_identity_governance.py` | Add carry unit tests |
| `helios_v2/tests/test_runtime_composition.py` | Add integration tests |
| `helios_v2/docs/requirements/index.md` | Add R68 row |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` | Update last-synced |
| `helios_v2/docs/PROGRESS_FLOW.en.md` | Update last-synced |

## 5. Implementation Order
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8

## 6. Validation Plan
- After Task 1: contract tests.
- After Task 4: existing assembly tests.
- After Task 6: new integration tests.
- After Task 7: full suite.

## 7. Completion Criteria
- R68 acceptance criteria 1-5 all satisfied.
- No regression in the full test suite.
- Index and progress flow maps updated.
