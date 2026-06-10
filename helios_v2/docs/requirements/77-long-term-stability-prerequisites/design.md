# Requirement 77 - Long-Term Stability Prerequisites — Design

## 1. Design Overview

A read-only prerequisite module with tests covering six long-term stability properties.
Each test validates one property using the assembled runtime and its supporting
infrastructure. A composite verdict aggregates all.

## 2. Current State and Gap

Individual properties are partially validated by feature tests (R65 zero-percept, R54
no-fire, R56 owner boundary). No module aggregates long-term stability prerequisites
into a single assessment.

## 3. Target Architecture

```
test_long_term_stability_prerequisites.py
├── StabilityCheck / StabilityVerdict dataclasses
├── test_lt1_resource_boundedness          — 20 ticks, memory + store bounded
├── test_lt2_state_isolation               — 2 handles, no cross-leakage
├── test_lt3_checkpoint_corruption         — corrupted file → fail-fast
├── test_lt4_embedding_failure_isolation   — raising provider → hard stop
├── test_lt5_zero_percept_and_high_load    — empty + high-load tick closure
├── test_lt6_owner_boundary_non_regression — composition guard patterns
└── test_stability_composite_verdict       — aggregate
```

## 4. Data Structures

### 4.1 StabilityCheck / StabilityVerdict

```python
@dataclass
class StabilityCheck:
    check_id: str       # "LT-1", "LT-2", etc.
    name: str
    passed: bool
    detail: str

@dataclass
class StabilityVerdict:
    checks: list[StabilityCheck]
    def add(self, check): ...
    @property
    def overall_pass(self) -> bool: ...
```

## 5. Module Changes

### 5.1 `tests/test_long_term_stability_prerequisites.py`

New module. Helpers reuse patterns from R71–R76:
- `_semantic_assembly()`, `_ready_gateway()`, `_embedding_gateway()`
- `_RaisingEmbeddingProvider` for LT-4
- `_HighPressureSampler` for LT-5

## 6. Migration Plan

No migration. Pure additive.

## 7. Failure Modes and Constraints

1. **Resource test flakiness**: memory threshold (500 MB) is generous; real usage is
   typically < 50 MB.
2. **Checkpoint corruption**: write random bytes to the checkpoint file; the loader
   must raise `PersistenceError` or JSON decode error.
3. **State isolation**: use separate `InMemoryExperienceStoreBackend` instances for
   each handle.

## 8. Observability and Logging

No new logging. Verdict via `pytest -s`.

## 9. Validation Strategy

1. Each test validates one stability property.
2. Composite aggregates all.
3. All offline with fake providers.
