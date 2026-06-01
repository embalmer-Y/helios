# Helios v2

Helios v2 is a fresh implementation branch for a brain-inspired AI runtime.

This project does not inherit the legacy runtime by default. It reuses only validated patterns and explicit contracts from the original Helios codebase.

## Principles

1. No hardcoded strategy paths in runtime decision-making.
2. No degraded or fallback execution modes.
3. Critical dependencies must be available before startup.
4. Each runtime concept has one clear owner.
5. Requirement, design, and task documents are the source of truth before implementation expands.
6. Modules collaborate through explicit APIs and ops contracts.
7. Public interfaces must be documented in code.

## Development Workflow

1. Clarify requirement scope first.
2. Write or update design before expanding implementation.
3. Expose cross-module behavior only through named APIs or ops.
4. Keep each owner narrow: a module owns its domain logic and does not absorb adjacent concerns.
5. Add comments or docstrings to every public interface.

See `docs/API_AND_OPS_CONTRACT_GUIDE.md` for the required interface format.

## Current Scope

The current implementation slice establishes:

1. Project layout.
2. Architecture boundary baseline.
3. Requirement package scaffolding.
4. A minimal fail-fast runtime kernel and dependency gate.

## Layout

```
helios_v2/
  docs/
  src/helios_v2/
  tests/
```

## Validation

Run the focused test slice from the repository root:

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_dependencies.py -q
```