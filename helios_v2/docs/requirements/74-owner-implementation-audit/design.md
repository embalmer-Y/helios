# Requirement 74 - Owner Implementation Audit — Design

## 1. Design Overview

A read-only audit module with 14 tests organized into four audit dimensions:
contract completeness (A1), owner boundary compliance (A2), semantic assembly
correctness (A3), and R70 bridge integrity (A4). Each dimension has multiple
tests; a composite verdict aggregates all.

## 2. Current State and Gap

Owner boundary guards exist (`test_composition_owner_boundary_guard.py`, R56) and
semantic assembly tests exist (`test_semantic_assembly_default.py`, R69). No module
aggregates contract completeness, boundary compliance, assembly correctness, and
bridge integrity into a single audit.

## 3. Target Architecture

```
test_owner_implementation_audit.py
├── AuditCheck / AuditVerdict dataclasses
├── A1: Contract completeness (2 tests)
│   ├── test_owner_packages_have_contracts_module
│   └── test_owner_packages_have_init_exports
├── A1+: Support packages (1 test)
│   └── test_support_packages_importable
├── A2: Boundary compliance (3 regex guard tests)
│   ├── test_composition_no_neuromodulator_sensitivity_policy
│   ├── test_composition_no_autonomy_drive_pressure
│   └── test_composition_no_feeling_coupling_coefficients
├── A3: Assembly correctness (2 tests)
│   ├── test_semantic_assembly_enables_de_shim_chain
│   └── test_semantic_assembly_novelty_not_constant
├── A4: R70 bridge integrity (3 tests)
│   ├── test_semantic_bridges_defined_in_composition
│   ├── test_semantic_bridges_used_in_semantic_assembly
│   └── test_legacy_bridges_used_in_legacy_assembly
├── Fail-fast + startup (2 tests)
│   ├── test_embedding_requires_store
│   └── test_default_assembly_startup_succeeds
└── Composite: test_owner_audit_composite_verdict
```

## 4. Data Structures

### 4.1 AuditCheck / AuditVerdict

```python
@dataclass
class AuditCheck:
    dimension: str      # "A1", "A2", "A3", "A4"
    name: str
    passed: bool
    detail: str

@dataclass
class AuditVerdict:
    checks: list[AuditCheck]
    def add(self, check): ...
    @property
    def overall_pass(self) -> bool: ...
```

## 5. Module Changes

### 5.1 `tests/test_owner_implementation_audit.py`

New module. Uses `importlib` for structural checks and `re` for boundary regex guards.
Helpers: `_ready_gateway()`, `_embedding_gateway()`, `_assemble_semantic()`.

## 6. Migration Plan

No migration. Pure additive.

## 7. Failure Modes and Constraints

1. **Regex false positives**: guard patterns are specific enough to avoid matching
   legitimate composition code.
2. **Import-time side effects**: structural checks use `importlib.import_module`,
   which may trigger lazy initialization; this is acceptable for audit purposes.

## 8. Observability and Logging

No new logging. Verdict via `pytest -s`.

## 9. Validation Strategy

1. Each test validates one audit dimension.
2. Composite aggregates all into one verdict.
3. All offline with fake providers.
