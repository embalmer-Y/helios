# Requirement 51 - Interoceptive-signal-shaped feeling (closing the first FG-2 causal chain)

## 1. Background and Problem

R50 closed the *producer* half of `gap_interoceptive_signal_source`: the new `helios_v2.interoception` owner samples the runtime's real internal condition (CPU/memory/latency/error pressure) and emits bounded `interoceptive` `RawSignal`s into sensory ingress, so the `02 -> 05` afferent path that already existed in code finally carries real signals. On an opt-in assembly the `05` feeling stage now receives non-empty, validated `internal_signals`.

But R50 explicitly stopped half-way by design: `05`'s construction path (`NeuromodulatorDerivedFeelingConstructionPath` wrapped by `PersistentFeelingConstructionPath`) still **ignores** `internal_signals` (`del internal_signals`). The felt body-state is therefore still derived top-down from the `04` neuromodulator state alone. The real interoceptive afferent is delivered and validated, but no feeling dimension changes when the machine's real condition changes.

This is the single most leveraged remaining P3 gap, because every prerequisite is already in place:

1. The afferent producer exists (R50) and carries a numeric `pressure_value` plus a `pressure_channel` discriminator on each interoceptive stimulus's `metadata` (preserved verbatim by sensory normalization).
2. The `05` feeling owner already evolves across ticks (R44 dual-timescale persistence) and already feeds a real downstream consumer: under the semantic-memory assembly `07` workspace competition (R46) scores each candidate as `0.6*priority + 0.4*feeling_salience`, where `feeling_salience` reads the real `05` arousal/tension/pain.

So the only missing link is `05` consuming `internal_signals`. Once it does, a complete, evaluation-reconstructable causal chain exists: **real compute/runtime pressure -> `05` felt body-state (tension/arousal/fatigue/pain) -> `07` workspace competition score -> `08` ignition / `09` gate activation**. That is exactly what FG-2 requires ("情感真实且可追溯地影响行为", including "在没有外部输入的纯内部 tick 上因情感/内感受状态而产生不同的内部行为"): a real bottom-up body signal that measurably and traceably changes downstream behavior.

## 2. Goal

Make the `05` interoceptive feeling owner consume the real interoceptive `internal_signals` it already receives, so that the runtime's real internal condition (CPU/memory/latency/error pressure) measurably and deterministically shapes the felt body-state in addition to the `04`-derived target; the body-signal-to-feeling mapping is owned by the `05` owner (as the channel-to-dimension neuromodulator mapping already is), is bounded and clamped to the legal range, is additive over the existing neuromodulator-derived target so it composes with the R44 dual-timescale persistence carry, and reduces to the existing behavior byte-for-byte when no interoceptive signal is present (so the default and non-interoceptive assemblies are unchanged).

## 3. Functional Requirements

### 3.1 Interoceptive consumption in the `05` owner
1. The `05` feeling owner must provide an owner-owned construction path that, given non-empty interoceptive `internal_signals`, derives an interoceptive pressure contribution and adds it to the neuromodulator-derived instantaneous target feeling.
2. The mapping from interoceptive pressure channels to feeling dimensions (which channel raises which dimension, and by how much) must be owned inside the `05` owner. It must not live in composition glue, sensory, or the interoception producer.
3. Higher compute/runtime pressure must monotonically push the body-state toward stress/load: at minimum CPU pressure must not decrease arousal/tension, memory and latency pressure must not decrease fatigue/tension, and error pressure must not decrease pain/tension. The contribution must be non-negative-stress-directional and bounded.
4. The produced feeling vector must always remain within the configured legal range (every dimension clamped), for any combination of interoceptive pressures in `[0,1]`.

### 3.2 Reading the afferent fact
1. The owner must read each interoceptive signal's bounded numeric pressure fact (`pressure_value`) and its `pressure_channel` discriminator from the stimulus the producer set, rather than parsing the human-readable content string.
2. A body/interoceptive signal that does not carry a recognized pressure channel/value (for example a future body signal from a different producer) must contribute nothing to the pressure mapping rather than raising. The owner reads only the pressure facts it understands in this first version.
3. The pressure contribution must be deterministic for a fixed set of `internal_signals` and independent of wall-clock time.

### 3.3 Composition with neuromodulator target and persistence
1. The interoceptive contribution must apply to the instantaneous target feeling, so the existing R44 dual-timescale persistence integrator carries and decays it across ticks exactly like the neuromodulator-derived component (no second persistence mechanism).
2. When `internal_signals` is empty, the construction path must reproduce the neuromodulator-derived target byte-for-byte, so an assembly with the real feeling path but no interoceptive source behaves exactly as before this requirement.

### 3.4 Opt-in rollout and fail-fast
1. The interoceptive-shaped feeling must activate only on an assembly that has both the real (semantic-memory) feeling path and the interoceptive source enabled. The default assembly, the recency-only assembly, the channel-bound assembly without interoception, and the semantic assembly without an interoceptive sampler must be byte-for-byte unchanged.
2. There must be no degraded feeling mode: a malformed feeling output still fails fast through the existing `05` invariants, and an absent interoceptive fact is a defined zero contribution (not a fabricated body condition).

## 4. Non-Functional Requirements

1. Performance: the contribution is one bounded arithmetic pass over a small fixed set of interoceptive signals per tick; no I/O, no network, no stage-structure change.
2. Reliability and fault tolerance: for an identical neuromodulator state and identical `internal_signals`, the produced feeling is deterministic and bounded for arbitrarily many ticks.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. Interoceptive facts continue to travel only through the `RawSignal`/`Stimulus` contracts and the `05` feeling-state contract.
4. Compatibility and migration: the change is additive (a new owner-owned construction path plus opt-in wiring). No contract change to `Stimulus`, `RawSignal`, the `FeelingConstructionPath` protocol, `InteroceptiveFeelingState`, or any downstream owner. Existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The body-signal-to-feeling mapping is owned by `helios_v2.feeling`. The interoception producer keeps owning only the runtime-fact-to-signal projection; composition keeps owning only assembly.
2. The `05` owner must not import the interoception, appraisal, neuromodulation, or workspace owners to do this; it consumes the already-normalized `Stimulus` values it is given through the existing engine signature.
3. The contribution must be additive over the neuromodulator-derived target and clamped; it must not replace or bypass the neuromodulator-derived component, and it must not introduce a non-deterministic or unbounded term.
4. No fabricated body condition: an unrecognized or absent pressure fact is a zero contribution, never a default non-zero stress.
5. No `logging`/`print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/feeling/engine.py` (new owner-owned `InteroceptiveSignalModulatedFeelingConstructionPath` wrapping the neuromodulator-derived target; the body-signal-to-feeling mapping)
2. `helios_v2/src/helios_v2/feeling/__init__.py` (export the new path)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (wire the new path into the feeling engine when the semantic feeling path and the interoceptive sampler are both present)
4. `helios_v2/tests/test_interoceptive_feeling_engine.py` (new owner-level tests: pressure raises stress dimensions, empty signals reproduce the target, bounded over extremes, deterministic, ignores unrecognized body signals)
5. `helios_v2/tests/test_runtime_composition.py` (extend: an interoceptive+semantic assembly produces a different `05` feeling and a different `07` competition score than the same assembly with at-rest pressure; default unchanged)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (narrow `gap_interoceptive_signal_source`: consumption half now closed; narrow the FG-2 note)
9. `helios_v2/docs/OWNER_GUIDE.md`, `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
10. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. With the real (semantic) feeling path and a non-empty interoceptive `internal_signals` set, the produced `05` feeling differs from the neuromodulator-only feeling: higher CPU pressure yields not-lower arousal/tension, higher memory/latency pressure yields not-lower fatigue/tension, and higher error pressure yields not-lower pain/tension, with at least one dimension strictly increasing for a high-pressure sample versus an at-rest sample.
2. With empty `internal_signals`, the construction path returns the neuromodulator-derived target byte-for-byte (the assembly without an interoceptive source is unchanged).
3. The feeling vector remains within the legal range for every combination of pressures in `[0,1]`, and is deterministic across repeated calls and across many ticks.
4. A body/interoceptive stimulus without a recognized pressure channel/value contributes nothing and does not raise.
5. The body-signal-to-feeling mapping lives in `helios_v2.feeling`; the `05` owner imports no interoception/appraisal/neuromodulation/workspace owner for it; the interoceptive contribution is additive over the neuromodulator-derived target and composes with the R44 persistence carry.
6. End-to-end (composition): under the interoceptive+semantic assembly, a high-pressure interoceptive sample produces a measurably different `05` feeling-state and a measurably different `07` workspace competition score than an at-rest sample, demonstrating the real "machine condition -> feeling -> workspace competition" causal chain. The default and non-interoceptive assemblies are byte-for-byte unchanged.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R51 closes the consumption half of `gap_interoceptive_signal_source` for `05`. The following remain explicitly future, each via its own requirement, and must preserve the owner boundaries established here:

1. Feeding the same runtime-pressure reading into the `09` gate's `workload_pressure` input (still a constant) as a second interoceptive consumer.
2. Richer interoceptive channels (cardiac/respiratory analogs; cross-tick fatigue accumulation as a first-class body-state rather than a per-tick pressure reading).
3. Real tick-latency and recent-error-rate sourcing for the latency/error channels (still first-version injectable defaults in the R50 sampler).
4. P5 learning of the interoceptive coupling coefficients (declared under the existing `feeling_coupling_strength` learned-parameter category).
