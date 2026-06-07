# Requirement 59 - Injectable External Afferent Source (Retire the Fabricated Constant Stimulus)

## 1. Task Breakdown

### T1 - Add the `external_signal_source` profile field + mutual exclusion
In `runtime_assembly.py`, add `external_signal_source: "SensorySource | None" = None` to
`RuntimeProfile`, and extend `__post_init__` to raise `CompositionError` when both
`external_signal_source` and `channel_cli` are set (both own the external afferent position).

### T2 - Thread the field through resolution and the loose-kwarg seam
Add `external_signal_source` to the `_UNSET` sentinel set and the loose-kwarg collection in
`assemble_runtime` (the R58 pattern), so it is accepted both as a loose kwarg and via an
explicit profile.

### T3 - Add the external-source registration branch
Change the sensory-source registration to: if `channel_cli` -> subsystem source (unchanged);
elif `external_signal_source` is not None -> register the injected source as the external
sensory source; else -> `FirstVersionSensorySource` (unchanged). The injected source registers
through the same `ingress.register_source` path; interoceptive registration is unaffected.

### T4 - Add the first-version injectable real source
In `bridges.py`, add `SequenceExternalSignalSource` (caller-supplied per-tick real `RawSignal`
batches; advances a cursor each emit; emits an empty tuple when exhausted; never fabricates a
constant). Export it from `composition/__init__.py`.

### T5 - Tests
In `test_runtime_composition.py`: injection replaces the constant; mutual exclusion with
`channel_cli` raises; a two-batch varying source under the semantic assembly produces different
`03` novelty + `04`/`05` state across ticks; an empty-batch source completes the tick; default
(field unset) unchanged.

### T6 - Documentation
Update `index.md` (row 59), both `OWNER_GUIDE` files (`02` entry: default afferent is a
non-real placeholder, real external afferent now injectable), both `PROGRESS_FLOW` maps (BODY/EXT
node + status note), and `BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 external-afferent honesty).

## 2. Dependencies

1. T1 -> T2 -> T3 (the field and validation must exist before resolution and registration use it).
2. T4 can land in parallel with T1-T3 but is needed before T5.
3. T5 after T3+T4. T6 after T1-T5.
4. External requirement dependencies: 02 (`SensorySource` protocol), 58 (`RuntimeProfile`), 31
   (channel-bound external source, for the mutual-exclusion rule), 35-41/43/44 (the real
   `03`/`04`/`05` chain the varying-source test exercises). No new owner.

## 3. Files and Modules

1. `src/helios_v2/composition/runtime_assembly.py` (T1, T2, T3)
2. `src/helios_v2/composition/bridges.py` (T4)
3. `src/helios_v2/composition/__init__.py` (T4)
4. `tests/test_runtime_composition.py` (T5)
5. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T6)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5 -> T6. Field + validation, resolution wiring, registration branch,
the injectable source, tests, then documentation.

## 5. Validation Plan

1. After T3 (default unchanged):
   `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_sensory_ingress.py -q`
   green (the loose-kwarg/default path is unchanged).
2. After T4+T5 (injection behavior):
   `pytest helios_v2/tests/test_runtime_composition.py -q` green, including the varying-source
   affect-chain test and the mutual-exclusion test.
3. Guards:
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   green.
4. Full suite:
   `pytest helios_v2/tests -q` green; count = prior baseline (721) + the added tests.

## 6. Completion Criteria

1. `RuntimeProfile.external_signal_source` exists; when set, the injected source is registered
   in place of `FirstVersionSensorySource`; both-set-with-`channel_cli` raises `CompositionError`.
2. `SequenceExternalSignalSource` is defined and exported, replays caller-supplied real signals,
   and fabricates no constant (empty when exhausted).
3. A semantic-assembly test proves a varying external stimulus measurably changes `03` novelty
   and the `04`/`05` state across ticks; an empty-batch source completes the tick without crashing.
4. The default assembly (field unset) is byte-for-byte unchanged; the full network-free suite is
   green with only the added tests; owner-boundary and ad-hoc-logging guards stay green.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `BRAIN_ARCHITECTURE_COMPARISON.md` record that the default external afferent is a non-real
   placeholder and the real external afferent is now injectable, with sync lines naming R59.
