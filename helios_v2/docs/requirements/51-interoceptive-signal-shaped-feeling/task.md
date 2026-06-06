# Requirement 51 - Interoceptive-signal-shaped feeling (tasks)

## 1. Task Breakdown

### Task 1 - Owner-owned interoceptive feeling construction path
In `helios_v2/src/helios_v2/feeling/engine.py`, add `InteroceptiveSignalModulatedFeelingConstructionPath` (implements `FeelingConstructionPath`) that wraps an inner `target_path`, computes the inner neuromodulator-derived target, reads bounded `pressure_channel`/`pressure_value` facts from the `internal_signals` stimuli metadata (max per channel; skip unrecognized/out-of-range/non-numeric without raising), and adds a bounded, non-negative, stress-directional per-dimension contribution (cpu->arousal/tension, memory->fatigue/tension, latency->fatigue/tension, error->pain_like/tension), clamped to the config legal range. Empty `internal_signals` returns the inner target byte-for-byte. Coefficients are first-version constants under `feeling_coupling_strength`. Add the two reserved metadata-key constants. Export the new path from `feeling/__init__.py`. The path imports no interoception/appraisal/neuromodulation/workspace owner.

### Task 2 - Opt-in assembly wiring
In `assemble_runtime`, when `semantic_memory_enabled and interoceptive_sampler is not None`, nest the new path between `PersistentFeelingConstructionPath` and `NeuromodulatorDerivedFeelingConstructionPath` (`persistence(interoceptive(neuromodulator))`). When the sampler is absent or the assembly is non-semantic, the construction path is unchanged. No new assembly parameter (reuse the existing R50 `interoceptive_sampler`).

### Task 3 - Validation
Extend `test_interoceptive_feeling_engine.py` (pressure raises the mapped stress dimensions; empty/unrecognized signals reproduce the inner target; bounded over extremes; deterministic; engine integration; composes with persistence) and `test_runtime_composition.py` (interoceptive+semantic assembly: high-pressure vs at-rest sampler yields different `05` feeling and different `07` competition score; default unchanged). Keep the suite network-free (constructed stimuli / fake sampler; no psutil) and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R51 row), `ARCHITECTURE_BOUNDARIES.md` (migration-state item: `05` now consumes the interoceptive afferent), `BRAIN_ARCHITECTURE_COMPARISON.md` (narrow `gap_interoceptive_signal_source`: consumption half closed for `05`; narrow the FG-2 grounding note), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`05` completeness/next-step), and both `PROGRESS_FLOW` maps (note `05` now body-shaped under interoceptive+semantic assembly; update last-synced + baseline test count).

## 2. Dependencies

1. Task 1 is independent (new path in the `05` owner; uses only the existing `FeelingConstructionPath` protocol + `Stimulus` metadata).
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/feeling/engine.py`, `helios_v2/src/helios_v2/feeling/__init__.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_interoceptive_feeling_engine.py`, `helios_v2/tests/test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (owner path) - the consumer, independently testable.
2. Task 2 (opt-in wiring) - makes the live afferent actually shape feeling.
3. Task 3 (validation) - prove body shapes feeling, empty reproduces target, bounded/deterministic, end-to-end to `07`, default unchanged.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_interoceptive_feeling_engine.py -q` (pressure raises mapped dimensions; empty/unrecognized reproduces target; bounded; deterministic; persistence composition).
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q` (interoceptive+semantic: high-pressure vs at-rest differ in `05` and `07`; default unchanged).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. `InteroceptiveSignalModulatedFeelingConstructionPath` in `helios_v2.feeling` adds a bounded, non-negative, stress-directional interoceptive contribution over the neuromodulator-derived target, reads pressure facts from stimulus metadata, skips unrecognized facts without raising, and reproduces the inner target byte-for-byte on empty `internal_signals`.
2. Wired opt-in as `persistence(interoceptive(neuromodulator))` only under the semantic+interoceptive assembly; all other assemblies byte-for-byte unchanged.
3. End-to-end: a high-pressure sample yields a different `05` feeling-state and a different `07` competition score than an at-rest sample, demonstrating the real machine-condition -> feeling -> workspace causal chain (FG-2).
4. Feeling stays bounded and deterministic; the mapping lives in `05`; no forbidden owner imports.
5. Full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set (gap note records consumption-half-closed; FG-2 first causal chain noted).
