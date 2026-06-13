# Requirement 80 - Appraisal-Derived Serotonin / Oxytocin / Opioid / Acetylcholine Channels

## 1. Task Breakdown

### T1 - Add the four channel drives
In `neuromodulation/engine.py`, add the four coefficient fields to
`AppraisalDerivedNeuromodulatorUpdatePath` and replace the four regress-to-baseline lines
(serotonin/oxytocin/opioid_tone/acetylcholine) in `update_levels` with the bounded clamped drives
defined in `design.md`. Update the class docstring. Leave excitation/inhibition at baseline.

### T2 - Tests
In `tests/test_neuromodulator_engine.py`, add focused tests: serotonin rises with social/low
threat and falls with threat; oxytocin rises with social; opioid_tone rises with reward + social;
acetylcholine rises with novelty; empty batch yields `clamp(base)`; all channels stay in range.

### T3 - Migrate existing assertions
Find and migrate any test asserting these four channels equal the constant baseline under the
appraisal-derived path; the `legacy_constant`/`FirstVersion` path assertions stay unchanged.

### T4 - Documentation sync
Update `index.md` (row 80), `OWNER_GUIDE.*` (`04` entry: four channels now appraisal-derived,
honest `C_engineering_hypothesis` caveat), `BRAIN_ARCHITECTURE_COMPARISON.md` (`03-07` row).
`PROGRESS_FLOW.*` only if `04`'s maturity color changes (it does not).

## 2. Dependencies

1. T1 -> T2/T3 -> T4.
2. External: `04` (R36 drive path, R43 dual-timescale wrapper), `03` salience. No new owner, no
   contract change.

## 3. Files and Modules

1. `src/helios_v2/neuromodulation/engine.py` (T1)
2. `tests/test_neuromodulator_engine.py` (T2, T3)
3. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`/`.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T4)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4.

## 5. Validation Plan

1. After T1/T2: `pytest helios_v2/tests/test_neuromodulator_engine.py helios_v2/tests/test_neuromodulator_contracts.py -q` green.
2. Guards + full: `pytest helios_v2/tests/test_composition_owner_boundary_guard.py -q` and
   `pytest helios_v2/tests -q` green.

## 6. Completion Criteria

1. The four channels are bounded appraisal-derived drives (no longer constants) under the
   semantic assembly; verified by contrasting-batch unit tests.
2. excitation/inhibition unchanged; empty batch yields `clamp(base)`; all channels in range.
3. Mapping lives in the `04` owner; owner-boundary guard green.
4. `legacy_constant`/offline unchanged; full network-free suite green (migrated assertions).
5. `index.md` row 80; `04` `OWNER_GUIDE` + `BRAIN_ARCHITECTURE_COMPARISON` note record the four
   now-real channels with the `C_engineering_hypothesis` caveat.
