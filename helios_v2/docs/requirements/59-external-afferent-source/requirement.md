# Requirement 59 - Injectable External Afferent Source (Retire the Fabricated Constant Stimulus)

## 1. Background and Problem

The `02` sensory ingress chain appraises the whole stimulus batch each tick
(`RapidSalienceAppraisalRuntimeStage` calls `assess_batch(sensory_result.batch)`), so any
real, varying stimulus that enters `02` genuinely drives `03` -> `04` -> `05` -> `07`. This
is the brain-inspired afferent path the whole cognitive chain is built on.

But in the default and semantic-memory assemblies the external afferent is a fabricated
constant. `FirstVersionSensorySource.emit_raw_signals` returns a fixed
`RawSignal(content="hello runtime", ...)` every tick. Two concrete consequences:

1. It is a composition-injected deterministic constant masquerading as external input. Under
   the final-goal acceptance criterion `FG-1`, the `02 -> 17` chain must consume real signals,
   not a fixed shim constant. The external afferent is the one source position still
   fabricated in the cognitive assembly.
2. Because the content never changes, after the first store write the real `03` novelty
   dimension (cosine distance to stored experience) collapses to a fixed value and the
   downstream `04`/`05`/`07` "real" signals run on a frozen input. The pipeline is real but the
   water does not move, so the external-stimulus branch of `FG-2` (a real external stimulus
   measurably changing affect and behavior across ticks) is never actually exercised.

The honest gap is the absence of a real external afferent *seam*, not the absence of a way to
fabricate varying text. Fabricating varying canned stimulus text would manufacture a
non-existent external world, which `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §4.3 (no prompt theater)
and §8 explicitly forbid. The real external afferent must come from a real source (the `31`
CLI channel today, a future `wave_C` network driver) or be honestly absent, never a hardcoded
constant.

Today a real external source can only enter through the opt-in channel-bound assembly
(`channel_cli=True`, the `SubsystemBackedSensorySource`). There is no first-class way to inject
a real external `SensorySource` into the default or semantic assembly the way `50`
interoceptive sampling and `55` temporal pacing are injected, so the external afferent cannot
be made real without the full channel subsystem.

## 2. Goal

Make the external afferent a first-class injectable runtime capability, mirroring the `50`
interoceptive sampler and `55` temporal source, so a real external `SensorySource` can drive
the `02 -> 03 -> 04 -> 05 -> 07` chain in any assembly; and record honestly that the default
`FirstVersionSensorySource` is a non-real placeholder, not a real external signal, so the
fabricated constant is never again counted as a real `FG-1` afferent.

## 3. Functional Requirements

### 3.1 Injectable external afferent

1. The runtime profile must carry an optional external afferent source
   (`external_signal_source`), an object conforming to the existing `02` `SensorySource`
   protocol.
2. When an external source is provided, composition must register it as the primary external
   sensory source in place of `FirstVersionSensorySource`, so its emitted `RawSignal`s flow
   through `02` normalization into the appraised stimulus batch unchanged.
3. The injected source must be owner-neutral transport: composition must not interpret or shape
   its content. `02` still owns normalization; `03` still owns appraisal.

### 3.2 Honest default and mutual exclusion

1. When no external source is injected and the channel-bound assembly is not selected, the
   default assembly must remain byte-for-byte unchanged (the `FirstVersionSensorySource`
   constant), so existing callers and tests are unaffected. This default must be recorded as a
   NON-REAL placeholder afferent, not a real external signal.
2. The injected external source and the channel-bound assembly (`channel_cli=True`) both own the
   external afferent position; supplying both must fail fast with `CompositionError` rather than
   registering two competing external sources.
3. The injected external source must not fabricate a fixed constant; that is the caller's
   contract. The first-version in-repo source shipped for tests/dev must emit a caller-supplied,
   tick-varying sequence of real `RawSignal`s (or an explicitly empty batch), never a hardcoded
   constant, so the seam is demonstrated without prompt theater.

### 3.3 Real external stimulus measurably drives cognition

1. With a real external source whose stimulus content varies across ticks, the `03` appraisal
   output (at minimum the real novelty dimension under the semantic assembly) must measurably
   differ across ticks, and that difference must propagate into the `04` neuromodulator state
   and the `05` feeling state, reconstructable as a causal chain.
2. An externally-empty afferent (the injected source emits no signal this tick) must be a
   defined behavior, not a crash: the tick proceeds on whatever other real afferents exist
   (interoceptive/temporal) or closes through the existing no-fire / internal-only path.

## 4. Non-Functional Requirements

1. Performance: no measurable per-tick overhead beyond the injected source's own emission.
2. Reliability: a source emission failure propagates as a hard stop (the existing `02`
   behavior); no fabricated stimulus substitutes for a failure.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the external source is opt-in and default-off. Default,
   recency-only, semantic, checkpoint, interoceptive, and temporal assemblies are byte-for-byte
   unchanged when no external source is injected. The capability is an additive `RuntimeProfile`
   field (building on `58`).

## 5. Code Behavior Constraints

1. Forbidden: emitting fabricated, hardcoded, or pseudo-random "external" stimulus content to
   simulate a changing external world. A real external afferent is real input or honest
   absence (`ARCHITECTURE_PHILOSOPHY` §4.3/§8).
2. Forbidden: composition interpreting, scoring, or shaping the injected source's content
   (that is `02`/`03` owner territory).
3. Boundary rule: the external afferent is a transport seam conforming to the `02`
   `SensorySource` protocol; it introduces no new cognitive owner.
4. Failure mode: injecting both an external source and `channel_cli=True` is a fail-fast
   `CompositionError`; a source emission error is a hard stop.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — add `external_signal_source` to
   `RuntimeProfile`, the mutual-exclusion validation, and the registration branch.
2. `helios_v2/src/helios_v2/composition/bridges.py` — a first-version injectable
   `SequenceExternalSignalSource` (caller-supplied tick-varying real signals; no constant
   fabrication) for tests/dev, distinct from the placeholder `FirstVersionSensorySource`.
3. `helios_v2/src/helios_v2/composition/__init__.py` — export the new source type if needed by
   callers/tests.
4. `helios_v2/tests/test_runtime_composition.py` — focused tests: injection replaces the
   constant; mutual exclusion with `channel_cli`; a varying external source measurably changes
   `03`/`04`/`05` across ticks under the semantic assembly; default unchanged when off.
5. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 external-afferent status).

## 7. Acceptance Criteria

1. `RuntimeProfile` carries `external_signal_source`; when provided, the assembled runtime
   registers it as the external sensory source and the constant `FirstVersionSensorySource` is
   not registered.
2. Supplying both `external_signal_source` and `channel_cli=True` raises `CompositionError`.
3. A focused test with a real varying external source (under the semantic assembly) shows the
   `03` novelty dimension and the resulting `04`/`05` state differ across at least two ticks,
   verifying the external stimulus measurably drives the affect chain (a second `FG-2` causal
   chain alongside the R51 interoceptive one).
4. An externally-empty injected source completes the tick without crashing (no-fire or
   internal-only closure), proving honest absence is a defined behavior.
5. With no external source injected, the default assembly is byte-for-byte unchanged (existing
   composition/stage-chain tests stay green); the full network-free suite is green with only the
   added focused tests in the count.
6. `index.md` has a row 59; the `02` `OWNER_GUIDE` entries and the `BRAIN_ARCHITECTURE_COMPARISON`
   FG-1 note record that the default external afferent is a non-real placeholder and the real
   external afferent is now injectable (CLI today, network `wave_C` future), with sync lines
   naming R59.
