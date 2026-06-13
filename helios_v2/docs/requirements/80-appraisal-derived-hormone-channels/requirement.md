# Requirement 80 - Appraisal-Derived Serotonin / Oxytocin / Opioid / Acetylcholine Channels

## 1. Background and Problem

R36 made the `04` neuromodulator update path appraisal-derived, but only for three channels:
dopamine (reward + weak novelty), norepinephrine (novelty + uncertainty), and cortisol (threat).
The other six channels — serotonin, acetylcholine, oxytocin, opioid_tone, excitation, inhibition —
still regress to the tonic baseline every tick in `AppraisalDerivedNeuromodulatorUpdatePath`,
i.e. they are constants that never respond to appraisal.

Four of those constant channels are affective neuromodulators that `brain.mmd` ties to real
appraisal-relevant functions: serotonin (mood stability, punishment sensitivity, impulse
inhibition), oxytocin (social bonding, trust, social salience), opioid_tone (reward satisfaction,
soothing, social comfort), and acetylcholine (attention, sensory gain, encoding). Because they are
constant, the `04` state has only three channels that actually evolve across ticks, the
downstream `05` feeling (R38, which couples from oxytocin/opioid/serotonin/acetylcholine) loses
most of its affective breadth, and a praise vs neglect situation produces no difference on the
social/reward-satisfaction/mood-stability axes. The experimental branch confirmed this (5-HT / Oxy
/ Opioid sat at a constant 0.30 across opposite scenarios). This narrows FG-2 (affect must evolve
and shape behavior) to a three-channel affect system.

## 2. Goal

Give the `04` appraisal-derived drive real grounded mappings for serotonin, oxytocin, opioid_tone,
and acetylcholine from the real `03` salience dimensions (the only inputs `04` has, since `04`
runs before `05`), so these four affective channels evolve with appraisal instead of being
constants — widening the affect system to seven appraisal-responsive channels and giving `05`
feeling real breadth — while keeping the mapping deterministic, bounded, owner-owned, and
P5-learnable, with honest `C_engineering_hypothesis` grounding.

## 3. Functional Requirements

### 3.1 Four new appraisal-derived channel drives (`04` owner)

1. `AppraisalDerivedNeuromodulatorUpdatePath` must derive serotonin, oxytocin, opioid_tone, and
   acetylcholine from the aggregated `03` salience (threat / reward / novelty / social /
   uncertainty), replacing their current regress-to-baseline behavior, each as a bounded clamped
   linear combination around the tonic baseline:
   - serotonin must rise with social safety and fall with threat (mood stability under a safe,
     low-threat context).
   - oxytocin must rise with social presence (social bonding).
   - opioid_tone must rise with reward and social presence (reward satisfaction / social comfort).
   - acetylcholine must rise with novelty (and may rise with uncertainty) (attention / encoding
     gain for novel input).
2. Each channel's exact coefficients and the precise formula are defined in `design.md`; all
   inputs are `03` salience dimensions only.
3. excitation and inhibition remain at the tonic baseline in this slice (they are not affective
   appraisal-driven hormones; their drivers are a later slice).

### 3.2 Grounding and learnability

1. The mappings must be deterministic, bounded (clamped to the legal channel range), stateless in
   the drive path (the R43 dual-timescale wrapper still owns cross-tick carry and will now also
   carry these four channels), and contain no NN and no divergence.
2. The sensitivity coefficients must be explicit bounded first-version constants under the
   config's existing learned-parameter categories (P5-learnable later); they must not be a new
   ad-hoc constant outside that scheme.
3. The grounding must be documented as `C_engineering_hypothesis` (a cautious functional analogy
   to `brain.mmd`, not a calibrated neuroendocrine model); it must not be over-claimed.

### 3.3 Ownership and scope

1. The mapping is the `04` owner's cognitive policy and must live in the `04` owner
   (`helios_v2.neuromodulation`), not in composition glue (consistent with R56).
2. The drive path must read only the rapid-appraisal batch + config; it must not read `05`
   feeling, prior-tick levels, or any other owner's state.
3. This requirement does not add the LLM hormone-predict corroboration (that is R81); it only
   makes the four formula-derived channel drives real.

## 4. Non-Functional Requirements

1. Performance: a fixed extra linear combination per channel per tick; no new I/O, no new import.
2. Reliability: total deterministic function; every channel clamped to the legal range; an empty
   appraisal batch still yields the tonic baseline (unchanged).
3. Observability and logging: no new logging mechanism; `21` stays the single logging mechanism.
4. Compatibility and migration: this changes the semantic-memory assembly's `04` state on the four
   channels (an intended P3 deepening, not a regression). Tests that assert these channels stay at
   the constant baseline under the semantic assembly are migrated. Default `legacy_constant` and
   offline assemblies keep the constant `FirstVersionNeuromodulatorUpdatePath` and are unchanged.

## 5. Code Behavior Constraints

1. Forbidden: deriving these channels from `05` feeling or prior-tick state inside the drive path
   (`04` runs before `05`; cross-tick carry belongs to the R43 dual-timescale wrapper).
2. Forbidden: placing the salience→channel mapping in composition glue (it is `04` owner policy;
   the owner-boundary guard must stay green).
3. Forbidden: unclamped or NN-based channel values; all four channels are bounded linear
   combinations plus clamp.
4. The coefficients must sit under the declared learned-parameter categories, not as free
   constants.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/engine.py` — extend
   `AppraisalDerivedNeuromodulatorUpdatePath` with the four channel drives.
2. `helios_v2/src/helios_v2/neuromodulation/contracts.py` — only if a coefficient needs a declared
   category name (reuse existing categories where possible).
3. `helios_v2/tests/test_neuromodulator_engine.py` — channel-drive tests; migrate any constant-
   baseline assertions for these channels under the semantic assembly.
4. Docs: `requirements/index.md`, `OWNER_GUIDE.*` (`04` entry), `BRAIN_ARCHITECTURE_COMPARISON.md`
   (`03-07` row), `PROGRESS_FLOW.*` only if owner maturity color changes.

## 7. Acceptance Criteria

1. Under the semantic assembly, serotonin / oxytocin / opioid_tone / acetylcholine produce
   different values for different appraisal inputs (they are no longer constants).
2. A high-social, high-reward appraisal (praise-like) yields higher oxytocin and opioid_tone than
   a low-social appraisal (neglect-like); a high-threat appraisal yields lower serotonin than a
   low-threat one (verified with explicit appraisal batches).
3. acetylcholine rises with novelty relative to a low-novelty appraisal.
4. All four channels stay within the legal range; the drive path reads no `05`/prior-tick state;
   an empty batch yields the tonic baseline.
5. The mapping lives in the `04` owner; the composition owner-boundary guard stays green.
6. Default `legacy_constant`/offline assemblies are byte-for-byte unchanged; the full network-free
   suite is green (migrated constant-baseline assertions); `index.md` has a row 80 and the `04`
   `OWNER_GUIDE` entry + `BRAIN_ARCHITECTURE_COMPARISON` note record the four now-real channels
   with the honest `C_engineering_hypothesis` caveat.
