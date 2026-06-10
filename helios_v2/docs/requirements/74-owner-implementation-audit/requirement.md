# Requirement 74 - Owner Implementation Audit

## 1. Background and Problem

The Helios v2 cognitive architecture comprises 18 owner modules (`01`–`18`), each governed
by the contract-first discipline: every owner must have a contract module, an engine, a
runtime stage, and focused tests. R56/R57 recovered owner boundaries after drift, and R70
introduced semantic bridges that read real owner state.

However, no automated audit validates that all owners maintain the four-piece contract
discipline, that composition glue respects owner boundaries (no cognitive policy leakage),
and that the semantic assembly's de-shim chain is complete and non-constant.

## 2. Goal

Provide a read-only audit test module that validates owner implementation completeness,
composition boundary compliance, semantic assembly correctness, and R70 bridge integrity,
producing a structured verdict for architectural governance.

## 3. Functional Requirements

### 3.1 Contract completeness

1. A test must verify that every owner (`01`–`18`) has a `contracts` submodule with
   exported contract types.
2. A test must verify that every owner's `__init__.py` exports its primary types.

### 3.2 Support packages

1. A test must verify that all support packages (embedding, persistence, composition)
   are importable and export their primary types.

### 3.3 Owner boundary compliance

1. A test must verify that `composition/bridges.py` does not import cognitive policy
   from owner engines (three regex guards: neuromodulator sensitivity policy,
   autonomy drive pressure, feeling coupling coefficients).

### 3.4 Semantic assembly correctness

1. A test must verify that the semantic assembly enables the full de-shim chain
   (`03`–`10` all produce real non-constant signals).
2. A test must verify that `03` novelty is not the legacy constant `0.6` under
   semantic assembly.

### 3.5 R70 bridge integrity

1. A test must verify that `SemanticEmbodiedPromptRequestBridge` and
   `SemanticInternalThoughtRequestBridge` are defined in composition.
2. A test must verify that semantic assembly uses semantic bridges.
3. A test must verify that legacy assembly uses first-version bridges.

### 3.6 Fail-fast and composite

1. A test must verify that embedding without store raises (fail-fast).
2. A test must verify that default assembly startup succeeds.
3. A composite test must aggregate all audit checks.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: no owner code modification.
3. **Regex guards**: boundary checks use `re.search` on source code, not import-time
   side effects.

## 5. Code Behavior Constraints

1. Audit tests must not call owner engines directly; they validate structural
   properties and assembly behavior.
2. Boundary regex guards must be explicit patterns, not free-text search.

## 6. Impacted Modules

1. `helios_v2/tests/test_owner_implementation_audit.py` — new audit module.
2. `helios_v2/docs/requirements/index.md` — new R74 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_owner_implementation_audit.py -v` passes all 14 tests.
2. Composite verdict covers contract completeness, boundary compliance, assembly
   correctness, and bridge integrity.
3. Full suite still passes.
