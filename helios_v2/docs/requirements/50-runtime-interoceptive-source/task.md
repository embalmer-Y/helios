# Requirement 50 - Runtime interoceptive signal source (tasks)

## 1. Task Breakdown

### Task 1 - Interoception owner (contracts + sampler + source)
Create `helios_v2/src/helios_v2/interoception/` with `contracts.py` (`RuntimePressureSample` frozen `[0,1]`-validated dataclass, `RuntimePressureSampler` protocol, `InteroceptionError`), `engine.py` (`StdlibRuntimePressureSampler` reading real cheap network-free facts with lazy psutil and defined bounded defaults; `RuntimeInteroceptiveSource` implementing `SensorySource`, emitting one bounded `interoceptive` `RawSignal` per pressure channel), and `__init__.py` exports. The owner imports no feeling/appraisal/neuromodulation owner and holds no cognitive policy.

### Task 2 - Opt-in assembly wiring
In `assemble_runtime`, add an opt-in (a sampler/source parameter or an `interoception` flag). When enabled, register `RuntimeInteroceptiveSource(sampler=...)` into ingress after the primary source. Default-off: no interoceptive source otherwise; the default/channel-bound/semantic assemblies are unchanged when off.

### Task 3 - Validation
Add `test_interoception_contracts.py` and `test_interoception_engine.py`; extend `test_runtime_composition.py` per the design validation strategy (opt-in feeds non-empty `internal_signals` into `05`; default empty; deterministic; stdlib sampler degrades without psutil). Keep the suite network-free (inject a fake sampler; never read real host telemetry) and the logging guard green.

### Task 4 - Documentation truth sync
Update `index.md` (add R50 row), `ARCHITECTURE_BOUNDARIES.md` (new `helios_v2.interoception` owner + migration-state item), `BRAIN_ARCHITECTURE_COMPARISON.md` (narrow `gap_interoceptive_signal_source`: producer now exists; `05` consumption still pending if deferred), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (new owner entry; `05` next-step), and both `PROGRESS_FLOW` maps (recolor/relabel the BODY node: real producer now exists, opt-in; update last-synced + baseline count).

## 2. Dependencies

1. Task 1 is independent (new owner; uses only the existing `SensorySource`/`RawSignal` contracts).
2. Task 2 depends on Task 1.
3. Task 3 depends on Tasks 1-2.
4. Task 4 depends on Task 3 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/interoception/{__init__,contracts,engine}.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_interoception_contracts.py`, `test_interoception_engine.py`, `test_runtime_composition.py` (Task 3)
4. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 4)

## 4. Implementation Order

1. Task 1 (owner) - the producer, independently testable.
2. Task 2 (opt-in wiring) - registers the source so the afferent is live.
3. Task 3 (validation) - prove bounded deterministic signals, live `05` afferent, default unchanged, stdlib degradation.
4. Task 4 (doc sync) - align index, boundary, grounding, owner guide, progress maps (recolor BODY).

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_interoception_engine.py helios_v2/tests/test_interoception_contracts.py -q` (bounded sample; per-channel interoceptive signals; normalize to valid internal body signals; stdlib degradation without psutil).
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q` (opt-in feeds non-empty `internal_signals`; default empty).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. `helios_v2.interoception` provides `RuntimeInteroceptiveSource` (implements `SensorySource`) emitting bounded `interoceptive` `RawSignal`s from an injected sampler; a first-version stdlib sampler reads real cheap network-free facts with defined bounded defaults and never raises for an unavailable fact.
2. When opted in, the `05` stage receives non-empty `internal_signals` that pass `validate_internal_body_signal`; the BODY-to-`05` afferent is live end to end.
3. The owner holds no cognitive policy and imports no feeling/appraisal/neuromodulation owner; an outright sampler exception propagates (no fabricated healthy body).
4. The source is opt-in; default/channel-bound/semantic assemblies are byte-for-byte unchanged when off; no new mandatory/network dependency (psutil lazy + degrades).
5. Deterministic for a fixed sample; full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set (BODY node recolored; gap note records producer-exists vs `05`-consumes distinction).
