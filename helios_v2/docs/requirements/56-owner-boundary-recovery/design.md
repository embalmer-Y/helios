# Requirement 56 - Owner Boundary Recovery of Appraisal-Derived Neuromodulation

## 1. Design Overview

This is a behavior-preserving relocation plus a recurrence guard. The R36
appraisal-derived neuromodulator drive mapping currently lives in
`helios_v2/composition/bridges.py` as `AppraisalDerivedNeuromodulatorUpdatePath` (with the
private `_AggregatedSalience` dataclass and `_aggregate_salience` helper). It encodes the
`04` owner's defining cognitive policy — which appraisal salience drives which
neuromodulator channel and how strongly. The design moves that class and its private helper
into the `04` owner package `helios_v2.neuromodulation`, leaves composition to only
construct/inject/wrap it, and adds a repository guard that fails if a neuromodulator
channel-sensitivity mapping reappears under `helios_v2/composition`.

No equation, coefficient, aggregation, or clamp changes. No public contract changes. No
assembly behavior changes.

## 2. Current State and Gap

Current wiring (`runtime_assembly.py`):

```
neuromodulator = NeuromodulatorEngine(
    config=resolved_config.neuromodulator,
    update_path=(
        DualTimescaleNeuromodulatorUpdatePath(            # owner package (R43)
            drive_path=AppraisalDerivedNeuromodulatorUpdatePath()   # composition (R36)  <-- gap
        )
        if semantic_memory_enabled
        else FirstVersionNeuromodulatorUpdatePath()       # composition constant shim (accepted)
    ),
    active_channel_reporter=FirstVersionActiveChannelReporter(),
)
```

Gap: the dual-timescale **decay** wrapper is owner-owned, but the **drive policy** it wraps
is defined in composition. The two halves of one `04` semantic are split across packages,
with the policy half on the assembly-only side. `tests/test_neuromodulator_engine.py`
imports the drive path from composition to test `04` channel-drive behavior, confirming the
behavior under test is owner policy, not glue.

What is correctly owner-neutral and stays in composition (not a gap):

1. `FirstVersionNeuromodulatorUpdatePath` — a constant 9-channel placeholder for the
   non-semantic assemblies. It contains no salience-to-channel mapping; it is an accepted
   first-version shim under `ARCHITECTURE_BOUNDARIES.md` §4.5 rule 2.
2. `FirstVersionActiveChannelReporter` — a constant diagnostic reporter, no scoring policy.
3. The pure projection bridges (e.g. `_workspace_activation`, `_interoceptive_workload_pressure`,
   `NeuromodulatorAwareThoughtGateSignalBridge`) — they forward an already-published owner
   field as a raw bounded fact and apply no scoring weight; the consuming owner owns the
   mapping. These remain accepted glue.

## 3. Target Architecture

```
helios_v2.neuromodulation (04 owner)
  engine.py
    NeuromodulatorUpdatePath               (protocol, unchanged)
    _aggregate_salience / _AggregatedSalience   (relocated here, owner-private)
    AppraisalDerivedNeuromodulatorUpdatePath     (relocated here, owner-owned)
    DualTimescaleNeuromodulatorUpdatePath        (already here, R43; unchanged)
  __init__.py
    re-exports AppraisalDerivedNeuromodulatorUpdatePath

helios_v2.composition (assembly-only)
  bridges.py
    FirstVersionNeuromodulatorUpdatePath    (kept: accepted constant shim)
    FirstVersionActiveChannelReporter       (kept)
    _clamp                                   (kept: used by other bridges)
    AppraisalDerivedNeuromodulatorUpdatePath (removed)
    _aggregate_salience / _AggregatedSalience (removed)
  runtime_assembly.py
    imports AppraisalDerivedNeuromodulatorUpdatePath from helios_v2.neuromodulation
    wiring expression unchanged in shape
```

The owner now owns the full appraisal-derived drive: aggregation + sensitivity coefficients
+ per-channel equation. Composition constructs it (`AppraisalDerivedNeuromodulatorUpdatePath()`),
injects it, and wraps it in the owner-owned R43 dual-timescale path exactly as before.

## 4. Data Structures

No contract data structures change. The relocated owner-private helper is unchanged in
shape:

```python
@dataclass(frozen=True)
class _AggregatedSalience:
    threat: float
    reward: float
    novelty: float
    social: float
    uncertainty: float
```

The relocated path keeps its first-version coefficient fields verbatim:

```python
@dataclass
class AppraisalDerivedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    novelty_to_norepinephrine: float = 0.5
    uncertainty_to_norepinephrine: float = 0.3
    reward_to_dopamine: float = 0.5
    novelty_to_dopamine: float = 0.15
    threat_to_cortisol: float = 0.5
```

The drive equation per channel is unchanged:
`level = clamp(tonic_baseline + sum(sensitivity_k * salience_k), legal_min, legal_max)`,
with the non-driven channels regressing to the clamped tonic baseline, salience aggregated
per-dimension-max across the batch, and an empty batch yielding all-zero salience (so the
result reduces to the tonic baseline).

## 5. Module Changes

1. `neuromodulation/engine.py`
   - Add `_aggregate_salience` + `_AggregatedSalience` (owner-private). The owner already
     defines a module-level `_clamp`; reuse it (do not duplicate).
   - Add `AppraisalDerivedNeuromodulatorUpdatePath` with the verbatim equation and
     coefficients, conforming to `NeuromodulatorUpdatePath`. Update its docstring ownership
     line from "Owner: composition" to "Owner: neuromodulator system (R36, recovered R56)".
2. `neuromodulation/__init__.py`
   - Add `AppraisalDerivedNeuromodulatorUpdatePath` to imports and `__all__`.
3. `composition/bridges.py`
   - Remove `AppraisalDerivedNeuromodulatorUpdatePath`, `_AggregatedSalience`,
     `_aggregate_salience`.
   - Keep `FirstVersionNeuromodulatorUpdatePath`, `FirstVersionActiveChannelReporter`,
     `_clamp` (still referenced by recall/pressure bridges).
4. `composition/runtime_assembly.py`
   - Import `AppraisalDerivedNeuromodulatorUpdatePath` from `helios_v2.neuromodulation`
     (alongside `DualTimescaleNeuromodulatorUpdatePath`); drop it from the `.bridges` import.
   - Wiring expression unchanged.
5. `tests/test_neuromodulator_engine.py`
   - Change the import to `from helios_v2.neuromodulation import
     AppraisalDerivedNeuromodulatorUpdatePath`.
6. `tests/test_composition_owner_boundary_guard.py` (new)
   - Scan `helios_v2/composition/*.py` source text for a `<word>_to_<word>` attribute/keyword
     pattern that denotes a salience-to-neuromodulator-channel sensitivity coefficient, and
     fail if any is found. Use a bounded allowlist-free regex tuned to the channel names so
     legitimate identifiers are not falsely flagged.

## 6. Migration Plan

1. Copy the class and helper into `neuromodulation/engine.py`, reusing the owner's existing
   `_clamp`.
2. Re-export from the `04` package `__init__`.
3. Repoint the composition import and delete the composition definitions.
4. Repoint the test import.
5. Add the boundary guard test.
6. Run the full suite; assert identical pass behavior (count grows only by the new guard).
7. Update documentation truth in the same change set.

No rewrite, no parallel path, no behavior toggle. The relocation is atomic: the symbol moves
and every reference repoints in the same change set.

## 7. Failure Modes and Constraints

1. Malformed appraisal batch: rejected by `NeuromodulatorEngine.update_state` /
   `_validate_appraisal_batch` before the update path runs — unchanged.
2. The relocated path is a total deterministic function; it never branches into a degraded
   mode and clamps every channel into the legal range. No new failure branch is introduced.
3. The guard must not over-match: it targets the salience-to-channel sensitivity pattern
   (the recovered policy), not arbitrary identifiers. It must pass on the post-relocation
   tree, where the only remaining neuromodulator-related composition code is the constant
   shim and the pure projection bridges.
4. There is no fallback to design: this is unconditional and behavior-preserving for every
   assembly.

## 8. Failure Modes and Constraints (Default-On vs Default-Off)

This change is unconditionally default-on and behavior-invariant. There is no opt-in flag,
because relocating a symbol does not change what the runtime computes. Every assembly
(default, recency-only, semantic, channel-bound, interoceptive, temporal, checkpoint)
produces identical neuromodulator levels before and after.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The
ad-hoc-logging guard (`test_no_adhoc_logging_guard.py`) stays green because neither the
relocated path nor the new guard uses `logging`/`print`.

## 10. Validation Strategy

1. Behavioral-invariance tests in `test_neuromodulator_engine.py` (already present) now run
   against the owner-imported path and must stay green: high/low novelty → norepinephrine
   ordering, reward → dopamine, threat → cortisol, empty batch → tonic baseline, full
   salience stays in `[0,1]`, determinism, non-driven channels regress to baseline,
   per-dimension-max aggregation.
2. New owner-boundary guard test: asserts no salience-to-channel sensitivity mapping under
   `helios_v2/composition`, and (as a positive control) that the same pattern is detectable
   so the guard is not vacuous.
3. Full network-free suite (`pytest helios_v2/tests -q`) green, count = prior + the new
   guard test(s).
4. A focused runtime-equivalence check (semantic assembly): one tick through
   `assemble_runtime(experience_store=..., embedding_gateway=...)` yields the same
   `neuromodulator_system` stage levels as before relocation (covered transitively by the
   existing composition/runtime tests, which must stay green unchanged).
