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
2. `19` boundary-truth and `20` scientific-grounding documentation owners,
3. `21` unified runtime observability with an optional kernel-level emission seam and a read-only execution-timeline view,
4. `22` the runtime composition root assembling a single runnable runtime handle,
5. `23` execution-timeline-aware evaluation and `24` long-horizon continuity threads,
6. `25` the backend-neutral LLM inference gateway and `26-29` the LLM-backed, structured, internal-only-closing, cognition-derived thought/autonomy path,
7. `30-31` the channel driver subsystem and the first concrete (CLI) driver with an opt-in channel-bound assembly,
8. `32` execution-truth-corroborated consequence binding (wave_A closed at baseline),
9. `33` the durable experience store with restart continuity and `34` semantic experience retrieval (the P2 memory base),
10. a fail-fast runtime kernel and dependency gate that runs with or without injected observability, persistence, embedding, or channel transport.

See `docs/OWNER_GUIDE.md` for the by-owner responsibility/completeness/next-step reference,
`docs/ARCHITECTURE_PHILOSOPHY.zh-CN.md` for the final goal and P0→P7 phase roadmap, and
`docs/PROGRESS_FLOW.en.md` for the color-coded module progress map.

## Layout

```
helios_v2/
  docs/
  scripts/
  src/helios_v2/
  tests/
```

## Validation

Run the full network-free suite from the repository root:

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests -q
```

Run one focused owner slice (for example the durable experience store and semantic retrieval):

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_persistence_contracts.py helios_v2/tests/test_persistence_engine.py helios_v2/tests/test_embedding_contracts.py helios_v2/tests/test_embedding_engine.py -q
```