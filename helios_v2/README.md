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

The current implementation baseline now includes:

1. owner packages `01-18` for the main runtime cognition and continuity chain,
2. `19` boundary-truth documentation,
3. `20` scientific-grounding and owner-wave gap-roadmap documentation,
4. `21` unified runtime observability and logging with an optional kernel-level emission seam,
5. a fail-fast runtime kernel and dependency gate that can run with or without injected observability.

## Layout

```
helios_v2/
  docs/
  scripts/
  src/helios_v2/
  tests/
```

## Validation

Run one focused test slice from the repository root:

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_runtime_dependencies.py -q
```

For the current observability owner slice:

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_observability_contracts.py helios_v2/tests/test_observability_engine.py helios_v2/tests/test_runtime_kernel_observability.py -q
```