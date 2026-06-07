# Requirement 56 - Owner Boundary Recovery of Appraisal-Derived Neuromodulation

## 1. Background and Problem

The runtime composition root (`helios_v2.composition`) is assembly-only by boundary
truth (`ARCHITECTURE_BOUNDARIES.md` §4.5): it constructs owners, owner-neutral bridges,
and the kernel, and holds no cognitive policy. `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §3.2 /
§7.1 are explicit: orchestration must not own a downstream owner's semantic judgment.

During the P3 de-shim waves a genuine `04` cognitive policy was introduced inside the
composition glue instead of the `04` owner. `AppraisalDerivedNeuromodulatorUpdatePath`
(R36) lives in `helios_v2/composition/bridges.py`. It is not a constant placeholder: it
owns the **appraisal-salience to neuromodulator-channel mapping** — the sensitivity
coefficients `reward_to_dopamine`, `novelty_to_dopamine`, `novelty_to_norepinephrine`,
`uncertainty_to_norepinephrine`, `threat_to_cortisol`, and the per-channel drive equation
`level = clamp(tonic_baseline + sum(sensitivity_k * salience_k))`. Deciding which salience
drives which neuromodulator channel, and how strongly, is the defining cognitive
responsibility of the `04` neuromodulator owner.

This is observable as a boundary violation, not a hypothetical one:

1. The path's owner-confirmed sibling `DualTimescaleNeuromodulatorUpdatePath` (R43) already
   lives in the `04` owner package (`helios_v2/neuromodulation/engine.py`) and wraps the
   R36 drive path. The drive and its decay are split across two packages with the policy
   half on the wrong side.
2. `tests/test_neuromodulator_engine.py` validates the `04` channel-drive semantics
   (`reward → dopamine`, `threat → cortisol`, per-dimension-max aggregation) by importing
   the class from `helios_v2.composition.bridges` — an owner-behavior test reaching into
   composition for owner policy.
3. `bridges.py` is the largest source file in the repository (~2400 lines). Letting
   cognitive policy accrete there is the early shape of the v1 technical-debt failure mode
   v2 was created to avoid.

This requirement does not change runtime behavior. It relocates an existing, tested
cognitive policy to its correct owner and installs a guard so this class of violation
cannot silently recur.

## 2. Goal

Move the appraisal-derived neuromodulator drive mapping (the salience-to-channel
sensitivity policy) from the composition glue into the `04` neuromodulator owner without
changing any neuromodulator levels the runtime produces, so the `04` channel-drive semantic
is owned by `04`, composition only injects/wraps it, and a repository guard prevents
neuromodulator-channel sensitivity policy from being defined in composition again.

## 3. Functional Requirements

### 3.1 Ownership relocation

1. The appraisal-derived drive mapping (today `AppraisalDerivedNeuromodulatorUpdatePath`
   plus its private salience-aggregation helper) must be defined in the `04` owner package
   `helios_v2.neuromodulation` and must be importable from `helios_v2.neuromodulation`.
2. The relocated path must conform to the owner's existing `NeuromodulatorUpdatePath`
   protocol unchanged, so the `04` engine and the R43 `DualTimescaleNeuromodulatorUpdatePath`
   wrapper consume it through the same seam as before.
3. The sensitivity coefficients and the per-channel drive equation must reside with the
   relocated owner-owned path, not in composition.
4. Composition must no longer define the appraisal-derived drive mapping. It may continue
   to construct and inject it, and may continue to wrap it in the R43 dual-timescale path,
   because construction and wiring are assembly concerns.

### 3.2 Behavioral invariance

1. For any appraisal batch and config, the relocated path must produce neuromodulator
   levels byte-for-byte identical to the pre-relocation path (same coefficients, same
   equation, same per-dimension-max aggregation, same clamp/rounding).
2. The default, recency-only, semantic-memory, channel-bound, interoceptive, temporal, and
   continuity-checkpoint assemblies must produce identical runtime output to before this
   change. This is a pure relocation, not a policy change.

### 3.3 Recurrence guard

1. A repository guard test must fail if `helios_v2/composition` defines a neuromodulator
   channel-sensitivity mapping (a `<salience>_to_<channel>` style coefficient that encodes
   which salience drives which neuromodulator channel).
2. The guard must pass for the legitimately-owner-neutral composition contents that remain:
   constant first-version shim paths and pure projection bridges that forward an already
   published owner field without applying a scoring weight.

### 3.4 Boundary-truth recording

1. The migration-state truth in `ARCHITECTURE_BOUNDARIES.md`, the `04` entry in both
   `OWNER_GUIDE` files, and the status notes in both `PROGRESS_FLOW` maps must record that
   the appraisal-derived `04` drive mapping is now owner-owned.
2. The documents must explicitly record what remains intentionally in composition as an
   accepted migration state (the constant first-version shims and the pure projection
   bridges), so the boundary truth distinguishes "recovered policy" from "accepted glue".

## 4. Non-Functional Requirements

1. Performance: no runtime performance change; this is a code-location change only.
2. Reliability: the relocated path keeps the same fail-fast semantics — it is a total
   deterministic function of the batch and config, never branches into a degraded mode, and
   always clamps every channel into the legal range.
3. Observability and logging: no new logging mechanism; the `21` observability owner remains
   the single logging mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: pure internal relocation. No public owner contract
   (`NeuromodulatorState`, `NeuromodulatorLevels`, `NeuromodulatorConfig`,
   `NeuromodulatorUpdatePath`) changes shape. Default rollout is immediate and unconditional
   (there is nothing to opt into); behavior is unchanged for every assembly.

## 5. Code Behavior Constraints

1. Forbidden: defining a neuromodulator channel-sensitivity mapping
   (`<salience>_to_<channel>` coefficient policy) anywhere under `helios_v2/composition`.
2. Forbidden: changing any sensitivity coefficient value, the drive equation, the
   per-dimension-max aggregation, or the clamp/rounding during relocation. The diff must be
   behavior-preserving.
3. Boundary rule: the `04` owner owns the appraisal-to-channel drive semantic; composition
   may construct, inject, and wrap owner paths but must not author their scoring policy.
4. Boundary rule (scope guard): this requirement recovers only the appraisal-derived
   neuromodulator drive mapping. The constant first-version shim paths used by the
   non-semantic assemblies, and the pure projection bridges (which forward a published owner
   field with no scoring weight), are explicitly out of scope and remain accepted
   owner-neutral composition glue under `ARCHITECTURE_BOUNDARIES.md` §4.5 rule 2.
5. Failure mode: a malformed appraisal batch is still rejected by the `04` engine before the
   update path runs (unchanged); the relocated path adds no new failure branch.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/engine.py` — receives the relocated owner-owned
   path and its salience-aggregation helper.
2. `helios_v2/src/helios_v2/neuromodulation/__init__.py` — re-exports the relocated path.
3. `helios_v2/src/helios_v2/composition/bridges.py` — removes the relocated path and its
   private helper; keeps the constant shim path, the pure projection helpers, and `_clamp`
   (still used by other bridges).
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — imports the relocated path
   from the `04` owner instead of from `.bridges`.
5. `helios_v2/tests/test_neuromodulator_engine.py` — imports the relocated path from the
   `04` owner.
6. `helios_v2/tests/test_composition_owner_boundary_guard.py` — new repository guard.
7. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md`.

## 7. Acceptance Criteria

1. `AppraisalDerivedNeuromodulatorUpdatePath` is importable from `helios_v2.neuromodulation`
   and is defined in `helios_v2/neuromodulation/engine.py`; it is no longer defined in
   `helios_v2/composition/bridges.py`.
2. A focused test asserts the relocated path produces identical levels to the documented
   first-version coefficients for representative batches (high/low novelty, reward, threat;
   empty batch → tonic baseline; full-salience batch stays within `[0,1]`; per-dimension-max
   aggregation), proving behavioral invariance. `test_neuromodulator_engine.py` imports the
   path from the `04` owner and stays green.
3. The new boundary guard fails when a `<salience>_to_<channel>` sensitivity coefficient is
   present under `helios_v2/composition`, and passes on the post-relocation tree.
4. The ad-hoc-logging guard and the full network-free suite stay green
   (`pytest helios_v2/tests -q`), with the suite count unchanged except for the added guard
   test(s).
5. `index.md` has a row 56; both `OWNER_GUIDE` files' `04` entry and both `PROGRESS_FLOW`
   maps' status notes record the recovered ownership and the accepted-glue scope, with the
   "Last synced" / sync line naming R56.
