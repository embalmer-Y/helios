# Requirement 72 - P1 Exit Evaluation

## 1. Background and Problem

`PHASE_METRICS.md` §3 defines the P1 internal closure milestone with six test indicators
(P1-T1 through P1-T6) and four hard exit conditions (P1-H1 through P1-H4). These validate
that the cognitive chain achieves internal closure: wave_A corroboration (`17` produces
`corroborated`/`discrepant`/`unverifiable`), wave_B continuity threads (`18`/`24` persist
across ≥ 5 ticks), wave_C CLI channel round-trip, internal-only tick closure, no-fire tick
closure, and read-only causal chain reconstruction.

No automated assessment validates these conditions against the current runtime. Phase
exit decisions rely on manual review of individual test results scattered across multiple
test modules.

## 2. Goal

Provide a single read-only evaluation test module that automatically validates all P1
exit indicators and hard conditions, producing a structured `P1ExitVerdict` that makes
the phase exit decision explicit, reproducible, and auditable.

## 3. Functional Requirements

### 3.1 Wave-A corroboration

1. A test must verify that `17` evaluation produces at least one `corroborated`,
   `discrepant`, or `unverifiable` consequence-binding verdict after multiple ticks.

### 3.2 Wave-B continuity thread persistence

1. A test must verify that `18`/`24` continuity threads persist across ≥ 5 consecutive
   ticks with stable thread keys and increasing age/reinforcement counts.

### 3.3 Wave-C CLI channel round-trip

1. A test must verify that the CLI channel driver completes ≥ 3 ticks end-to-end
   without interruption.

### 3.4 Internal-only and no-fire tick closure

1. A test must verify that an internal-only tick (no external stimulus) completes the
   full chain without error.
2. A test must verify that a no-fire tick (gate decides `no_fire`) completes the chain
   through the R54 closure path.

### 3.5 Hard exit conditions

1. A test must verify read-only causal chain reconstruction: `17`/`23` can reconstruct
   at least one causal chain from tick frame data without modifying state.
2. A test must verify continuous 10-tick operation without exception.

### 3.6 Composite verdict

1. A composite test must aggregate all P1 indicators into a single `P1ExitVerdict`
   with per-indicator pass/fail and overall assessment.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: evaluation tests do not modify any owner implementation.
3. **Reproducible**: same runtime produces same verdict.

## 5. Code Behavior Constraints

1. Evaluation tests must use `assemble_runtime()` and never call owner engines directly.
2. The verdict dataclass must record each indicator's pass/fail with diagnostic detail.

## 6. Impacted Modules

1. `helios_v2/tests/test_p1_exit_evaluation.py` — new evaluation module.
2. `helios_v2/docs/requirements/index.md` — new R72 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_p1_exit_evaluation.py -v` passes all 8 tests offline.
2. The composite verdict test reports pass/fail for every P1-T* and P1-H* indicator.
3. Full suite still passes.
