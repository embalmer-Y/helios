# Requirement 55 - Temporal pacing and DMN rest-state gate inputs (tasks)

## 1. Task Breakdown

### Task 1 - Temporal source owner
Create `helios_v2/src/helios_v2/temporal/` with `contracts.py` (`TemporalPacingSample` frozen, `temporal_signal` `[0,1]`-validated + `dmn_available` bool; `TemporalSource` protocol with `sample(external_stimulus_present)` + `observe_tick(fired)`; `TemporalError`), `engine.py` (`RestStateTemporalSource`: `dmn_available = not external_stimulus_present`, `temporal_signal = clamp(per_tick_increment * ticks_since_last_fire, 0, max_signal)`, cross-tick elapsed state advanced by `observe_tick`), and `__init__.py` exports. The owner imports no gate/appraisal/feeling/neuromodulation owner and holds no cognitive policy.

### Task 2 - Gate bridge wiring + cross-tick advance
In `bridges.py`, add `_INTERNAL_MODALITIES`, `_external_stimulus_present(frame)`, and `_temporal_inputs(frame, temporal_source)` (returns `(0.4, True)` when source is None); add an optional `temporal_source` field to both gate-signal bridges and replace the `temporal_signal`/`dmn_available` constants via the helper. In `runtime_assembly.py`, add the opt-in `temporal_source` param, set it on the active gate-signal bridge, store it on `RuntimeHandle`, and add a `_carry_temporal` post-tick seam (advance from the published gate decision: fire -> reset, no-fire -> increment) called in `tick()`.

### Task 3 - Validation
Add `test_temporal_contracts.py` + `test_temporal_engine.py` (bounds; rest-to-DMN; accumulation/reset; determinism); extend `test_runtime_composition.py` (temporal assembly: rest ticks accumulate temporal_signal + DMN engaged, external stimulus disengages DMN, reset after fire; default keeps `0.4`/`True`). Network-free; logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (R55 row), `ARCHITECTURE_BOUNDARIES.md` (new `helios_v2.temporal` owner + migration-state item), `BRAIN_ARCHITECTURE_COMPARISON.md` (temporal/DMN analog; narrow `09-11` gate-input shim note), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`09` next-step + new temporal owner entry), both `PROGRESS_FLOW` maps (S09 label + status bullet; last-synced + baseline count).

## 2. Dependencies

1. Task 1 independent.
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/temporal/{__init__,contracts,engine}.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/bridges.py`, `runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_temporal_contracts.py`, `test_temporal_engine.py`, `test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` + four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (owner).
2. Task 2 (wiring + carry).
3. Task 3 (validation).
4. Task 4 (doc sync).

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_temporal_engine.py helios_v2/tests/test_temporal_contracts.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; logging guard green.

## 6. Completion Criteria

1. `helios_v2.temporal` provides `RestStateTemporalSource` producing bounded `TemporalPacingSample`: rest -> `dmn_available=True`, external stimulus -> `False`; `temporal_signal` accumulates across no-fire ticks and resets on fire; deterministic.
2. Both gate-signal bridges forward the source's outputs when wired; the `09` gate weights/decision are unchanged; the real values surface in `contributing_signals`.
3. The cross-tick elapsed state is advanced post-tick from the published gate decision through an owner-neutral seam; the temporal owner imports no gate/appraisal/feeling/neuromodulation owner.
4. With no temporal source, the gate keeps `temporal_signal=0.4`/`dmn_available=True` byte-for-byte; default and other assemblies unchanged.
5. Full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set.
