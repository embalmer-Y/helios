# Requirement 50 - Runtime interoceptive signal source (closing the BODY gap)

## 1. Background and Problem

The `05` interoceptive feeling owner is built to consume real internal body signals: the `InteroceptiveFeelingRuntimeStage` filters the `02` sensory batch for `modality in {body, interoceptive}` and forwards them to `05` as `internal_signals`, and `05`'s contract validates them (`validate_internal_body_signal`). But **nothing produces such signals**. The assembled sensory sources (`FirstVersionSensorySource`, the CLI driver) emit only `text` modality, so `internal_signals` is always empty, and `05`'s R38/R44 construction path derives feeling from the `04` neuromodulator state alone. The `BODY` node in the progress-flow maps is an interface-only placeholder with no owner that generates it — tracked as `gap_interoceptive_signal_source`.

This is a real gap, not a cosmetic one. In a brain, interoception is a genuine afferent stream (cardiac, respiratory, visceral, fatigue, pain) that is *bottom-up*: it reports the body's actual internal condition, independent of top-down neuromodulatory state. Helios has no physical body, but it runs on a real machine with a real internal condition: CPU load, memory pressure, tick latency, error/failure rate. The locked roadmap (`ARCHITECTURE_PHILOSOPHY.zh-CN.md` final-goal axis 2 "有情感", and the gap's own note) explicitly anticipates "a first-version proxy that maps real compute/runtime pressure (CPU, memory, latency, error rate) into bounded interoceptive signals" as the legitimate first producer.

Today `05` feeling is one-directional (top-down from `04` only). Without a real interoceptive afferent, the system cannot have a felt body-state grounded in any real internal condition, and FG-2 ("情感真实且可追溯地影响行为", including "在没有外部输入的纯内部 tick 上因情感/内感受状态而产生不同的内部行为") cannot be fully satisfied because there is no real bottom-up body signal to feel.

## 2. Goal

Establish a runtime interoceptive signal source owner that, each tick, samples the runtime's real internal condition (compute/runtime pressure: CPU load, memory pressure, tick latency, recent error rate) through an injected sampler and emits bounded normalized interoceptive `RawSignal`s (`signal_type="interoceptive"`) into sensory ingress, so the `02` chain produces real body/interoceptive stimuli that the `05` feeling owner already knows how to consume; the source owns only the sample-to-signal projection (it holds no feeling or salience policy), the sampler is injected behind a narrow protocol (so the runtime never blocks on or hard-depends on a specific telemetry backend), the signals are bounded and deterministic given a fixed sample, and the default assembly stays byte-for-byte unchanged (the source is opt-in).

## 3. Functional Requirements

### 3.1 Interoceptive source owner
1. A new owner (`helios_v2.interoception`) must provide a `RuntimeInteroceptiveSource` that conforms to the existing `SensorySource` protocol (a stable `source_name` and `emit_raw_signals()`), so it registers into sensory ingress exactly like any other source with no ingress change.
2. Each `emit_raw_signals()` call must sample the runtime's current internal condition through an injected sampler and project it into one or more bounded interoceptive `RawSignal`s with `signal_type="interoceptive"` (so `02` normalizes them to `modality="interoceptive"` stimuli that `05` already filters and consumes).
3. Each emitted signal must carry bounded, in-range content and metadata sufficient for `05` to treat it as a valid internal body signal (non-empty `signal_id`, `source_name`, `signal_type`, and `content`), preserving the source provenance.
4. The sample-to-signal projection (which runtime facts become which interoceptive channels, and how they are normalized into `[0,1]` bounded values) is owned by `helios_v2.interoception`. The owner must not compute feeling, salience, or any downstream cognitive judgment.

### 3.2 Injected sampler, no hard telemetry dependency
1. The runtime condition must be read through an injected sampler protocol (for example `RuntimePressureSampler` returning a bounded `RuntimePressureSample`), so the owner never hard-depends on a specific telemetry backend and tests inject a deterministic fake.
2. A first-version stdlib-based sampler must exist that reads real, cheap, network-free runtime facts (for example process/system CPU and memory via the standard library or an optional lightweight dependency imported lazily) and normalizes them into bounded `[0,1]` pressure values. If a particular fact is unavailable on the host, the sampler must return a defined bounded default for that channel rather than raising — sampling the body must never crash the tick.
3. Sampling must be cheap and synchronous (no blocking I/O, no network). It must not change the runtime stage execution structure.

### 3.3 Real feeling effect (closing the gap)
1. When the interoceptive source is enabled, the `05` feeling stage must receive non-empty `internal_signals` (the real interoceptive stimuli), demonstrating the BODY-to-`05` afferent path is live end to end.
2. This requirement establishes the producer and the live afferent path. Whether `05`'s construction path additionally *uses* the `internal_signals` to shape the feeling vector (beyond the `04`-derived target) may be a bounded first-version coupling in this slice or an explicitly-deferred follow-on; if deferred, the gap note must record that the producer exists but `05`'s consumption of it is the next slice. (Design decides; either way the producer and the live afferent are delivered here.)

### 3.4 Opt-in rollout and fail-fast
1. The interoceptive source must be an explicit opt-in assembly choice. The default assembly (and the existing channel-bound and semantic assemblies, when the source is not requested) must keep their current sources and behave exactly as today (no interoceptive stimuli).
2. A sampler failure must not silently fabricate a body state: the injected first-version sampler returns defined bounded defaults for unavailable facts (a defined reading, not a fabrication of a specific condition), but an outright sampler exception must propagate rather than be swallowed into a fake "healthy" body. There is no degraded body-state mode that pretends a condition the runtime is not in.

## 4. Non-Functional Requirements

1. Performance: sampling is one cheap synchronous read per tick; it must add no blocking I/O, no network, and no stage-structure change.
2. Reliability and fault tolerance: for an identical injected sample, the emitted interoceptive signals must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Interoceptive facts travel only through the existing `RawSignal`/`Stimulus` contracts.
4. Compatibility and migration: the new owner, the sampler protocol, the first-version sampler, and the opt-in wiring are additive. The default assembly is byte-for-byte unchanged when the source is off; existing tests pass unmodified. No new heavyweight or network dependency is introduced (any optional telemetry library must be imported lazily and degrade to a stdlib/default reading when absent).

## 5. Code Behavior Constraints

1. The interoception owner must hold no feeling, salience, or cognitive policy. It owns only the runtime-fact-to-interoceptive-signal projection. `05` keeps sole ownership of feeling; `03` keeps salience.
2. The owner must not import the feeling, appraisal, or neuromodulation owners. It emits `RawSignal`s through the existing `SensorySource` protocol; sensory ingress owns normalization.
3. The sampler is injected behind a narrow protocol; the owner must not hard-code a telemetry backend. The first-version sampler must degrade to defined bounded defaults for unavailable facts and must not raise for a merely-unavailable fact.
4. No degraded body-state mode that fabricates a specific condition; an outright sampler exception propagates.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/interoception/__init__.py`, `contracts.py`, `engine.py` (the new owner: `RuntimePressureSample`, `RuntimePressureSampler` protocol, a first-version stdlib sampler, and `RuntimeInteroceptiveSource` implementing `SensorySource`)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in registration of the interoceptive source into ingress alongside the existing source)
3. `helios_v2/tests/test_interoception_contracts.py` / `test_interoception_engine.py` (new: sample bounds, deterministic projection, signal shape, sampler-default behavior)
4. `helios_v2/tests/test_runtime_composition.py` (extend: opt-in assembly feeds non-empty `internal_signals` into `05`; default assembly unchanged / empty `internal_signals`)
5. `helios_v2/docs/requirements/index.md`
6. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
7. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (narrow/close `gap_interoceptive_signal_source`)
8. `helios_v2/docs/OWNER_GUIDE.md`
9. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
10. `helios_v2/docs/PROGRESS_FLOW.en.md` (recolor the BODY node: producer now exists)
11. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. A new `helios_v2.interoception` owner provides `RuntimeInteroceptiveSource` implementing `SensorySource`; it samples runtime condition through an injected sampler and emits bounded interoceptive `RawSignal`s (`signal_type="interoceptive"`) with preserved provenance.
2. The sampler is injected behind a protocol; a first-version stdlib sampler reads real, cheap, network-free runtime facts and normalizes them into bounded `[0,1]` values, returning defined bounded defaults for unavailable facts without raising.
3. For an identical injected sample, the emitted interoceptive signals are deterministic and in range.
4. When the source is enabled, the `05` feeling stage receives non-empty `internal_signals` (the live BODY-to-`05` afferent path), and they normalize to `modality="interoceptive"` stimuli that pass `validate_internal_body_signal`.
5. The interoception owner holds no feeling/salience/cognitive policy and imports no feeling/appraisal/neuromodulation owner; sampling failure for an unavailable fact yields a defined default, while an outright sampler exception propagates (no fabricated healthy body).
6. The source is opt-in; the default assembly is byte-for-byte unchanged (empty `internal_signals`); existing tests pass unmodified; no new heavyweight/network dependency (optional telemetry imported lazily, degrades when absent).
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R50 establishes the interoceptive producer and the live afferent path. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. `05` construction-path consumption of `internal_signals` to shape the felt body-state beyond the `04`-derived target (if not done in this slice), so real compute/runtime pressure measurably changes feeling (FG-2).
2. Feeding the same runtime-pressure reading into the `09` gate's `workload_pressure` input (currently a constant) through a composition bridge, as a second consumer of the interoceptive substrate.
3. Richer interoceptive channels (a simulated body-state model: cardiac/respiratory analogs, fatigue accumulation across ticks) beyond compute/runtime pressure.
4. P5 learning of the sample-to-signal normalization and of `05`'s coupling of interoceptive signals.

None of these may be smuggled into this slice unless the design explicitly scopes the first-version `05` coupling in. R50 changes only the existence of a real interoceptive producer and its opt-in wiring; it introduces no cognitive ownership into the source, no new default-on behavior, and no heavyweight/network dependency.
