# Requirement 53 - Workload pressure from the interoceptive afferent

## 1. Background and Problem

The `09` thought-gate decision consumes a `workload_pressure` signal that is brain-aligned and behaviorally real in the `09` owner: it is subtractive in the gate score (`- workload_pressure * 0.45`) and, above `policy.resource_pressure_block_threshold` with low continuation, it explicitly blocks firing. This models allostatic load — when the system is overloaded, it should be less willing to ignite fresh thought. The gate logic is real; the input is not.

Today the composition gate-signal bridge (`NeuromodulatorAwareThoughtGateSignalBridge` under the semantic assembly, and `FirstVersionThoughtGateSignalBridge` otherwise) hardcodes `workload_pressure=0.1`. So the single most load-sensitive gate term is driven by a constant, and the runtime's real compute/runtime condition never influences whether it thinks.

R50 already produces the exact signal this needs: the `helios_v2.interoception` owner emits bounded `interoceptive` `RawSignal`s for real cpu/memory/latency/error pressure, which sensory normalizes to `modality="interoceptive"` stimuli carrying `pressure_channel`/`pressure_value` metadata. R51 made the `05` feeling owner the first consumer of that afferent. The `09` gate's `workload_pressure` is the natural second consumer (R50/R51 explicitly anticipated this), and it is nearly zero-cost: the interoceptive stimuli are already in the `02` sensory batch, which runs before `09`.

## 2. Goal

Ground the `09` gate's `workload_pressure` in the runtime's real compute/runtime load by having the composition gate-signal bridge derive it from the R50 interoceptive afferent (the cpu and memory pressure channels present in the current tick's `02` sensory batch) instead of the constant `0.1`, so that under an interoceptive assembly real machine load measurably and monotonically raises the gate's resource-pressure term (and, at high load, its documented block path), while the `09` owner keeps sole ownership of the gate weight and the block threshold, the bridge forwards only a raw bounded pressure fact, and assemblies without an interoceptive source keep the constant `0.1` byte-for-byte.

## 3. Functional Requirements

### 3.1 Real workload pressure from the interoceptive afferent
1. The composition gate-signal bridge must, when the current tick's `02` sensory batch carries interoceptive compute/runtime-load stimuli, derive a bounded `workload_pressure` in `[0,1]` from those stimuli and forward it in the `ThoughtGateSignalSnapshot`, replacing the constant `0.1`.
2. The derived value must come from the runtime-load channels of the R50 afferent — at minimum cpu and memory pressure — read from the stimulus `pressure_channel`/`pressure_value` metadata the producer set, never by parsing content.
3. The derivation must be a bounded, deterministic, monotonic-non-decreasing function of the load channels (higher cpu/memory pressure must not yield a lower `workload_pressure`).
4. The bridge must forward only a raw bounded load fact. The gate weight (`* 0.45`), the resource-pressure block threshold, and all gate-decision semantics remain owned by the `09` thought-gating owner (unchanged).

### 3.2 Absence and reading rules
1. When the sensory batch carries no recognized interoceptive load stimulus (no interoceptive source wired, or no cpu/memory channel present), the bridge must keep the existing constant `workload_pressure=0.1` (the current behavior, byte-for-byte).
2. A stimulus whose `pressure_channel` is not a recognized load channel, or whose `pressure_value` is not a numeric in `[0,1]`, must contribute nothing rather than raising — consistent with the R51 reading rules.
3. The other gate-signal inputs (`global_activation_level` from R48, `neuromodulatory_arousal` from R37, and the still-constant `temporal_signal`, `drive_urgency_signal`, `dmn_available`, and `selected_stimuli` projection) are unchanged by this requirement.

### 3.3 Rollout and fail-fast
1. The real `workload_pressure` activates whenever the interoceptive afferent is present in the sensory batch. The default assembly (no interoceptive source) and any assembly without interoceptive load stimuli keep the constant `0.1`.
2. There is no degraded workload mode: an absent load fact is the defined constant `0.1` (not a fabricated load), and the `09` owner's existing fail-fast invariants on the snapshot are unchanged.

## 4. Non-Functional Requirements

1. Performance: one bounded read over the already-present `02` batch per tick; no new stage, no I/O, no network.
2. Reliability and fault tolerance: for a fixed sensory batch, the derived `workload_pressure` is deterministic and bounded.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. The real value surfaces only in the existing `ThoughtGateResult.contributing_signals["workload_pressure"]`.
4. Compatibility and migration: additive — the bridge derives the value when load stimuli are present and otherwise keeps the constant. No contract change to `ThoughtGateSignalSnapshot`/`ThoughtGateResult`. Existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The load-channels-to-`workload_pressure` projection is owner-neutral composition glue that forwards a raw bounded fact; the gate weight and block threshold stay in the `09` owner. The bridge must not compute a gate score or re-weight the term.
2. The bridge reads only the already-normalized `02` sensory stimuli it is given; it does not import the interoception owner (the afferent already flows through `02`).
3. No fabricated load: absence of a recognized load stimulus yields the defined constant `0.1`, never a non-zero invented load.
4. No `logging`/`print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (derive `workload_pressure` from the interoceptive load stimuli in the gate-signal bridge(s); a small owner-neutral helper reading the reserved pressure metadata)
2. `helios_v2/tests/test_runtime_composition.py` (interoceptive+gate: high cpu/memory pressure raises `contributing_signals["workload_pressure"]` above `0.1` and lowers the gate score / can block; no interoceptive source keeps `0.1`)
3. `helios_v2/docs/requirements/index.md`
4. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
5. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (narrow the `09-11` gate-input shim note and the `gap_interoceptive_signal_source` second-consumer note)
6. `helios_v2/docs/OWNER_GUIDE.md`, `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
7. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under an assembly with the interoceptive source, the gate-signal bridge derives `workload_pressure` from the cpu/memory interoceptive load stimuli in the `02` batch (read from `pressure_channel`/`pressure_value` metadata), bounded to `[0,1]` and monotonic-non-decreasing in those channels; the real value appears in `ThoughtGateResult.contributing_signals["workload_pressure"]`.
2. A high-load interoceptive sample yields a `workload_pressure` above `0.1` and a measurably lower gate score than an at-rest sample (and, at sufficiently high load with low continuation, the documented block path); the `09` gate weight and threshold are unchanged.
3. With no interoceptive source (or no recognized load stimulus), `workload_pressure` stays `0.1` byte-for-byte; the default assembly is unchanged.
4. An unrecognized channel or out-of-range/non-numeric pressure value contributes nothing and does not raise.
5. The projection is owner-neutral (no gate score computed in the bridge, no interoception-owner import); the `09` owner retains the gate weight and block threshold.
6. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R53 makes the `09` gate the second consumer of the interoceptive afferent. The following remain future, each via its own requirement:

1. **Gate no-fire chain closure (surfaced by R53, highest priority).** R53 makes high real compute load correctly drive the gate to `resource_pressure_too_high` / no-fire. But the assembled chain currently has no no-fire path: the directed-retrieval stage (and the fired-path stages after it) require a fired `ThoughtGateResult` and raise on a non-fired one. So a high-load tick cannot yet complete end to end. R53 therefore exercises the real `workload_pressure` only within the gate's firing window (cpu/memory load up to ~0.3 given the other first-version constant signals) end to end, and validates the high-load -> high-`workload_pressure` -> block relationship at the owner-neutral helper level. A dedicated requirement must add a gate-no-fire tick closure (the gating-no-fire analog of R28's fired-but-no-proposal `internal_only` closure): when the gate does not fire, the tick must close through writeback/autonomy/evaluation as an explicit no-fire outcome instead of the downstream stages raising. Once that lands, the real `workload_pressure` (and the other gate signals) can be exercised across the full load range end to end.
2. Real `temporal_signal` (a clock source) and `dmn_available` (a DMN source) for the gate (R55 territory).
3. `drive_urgency_signal` carried from `18` across ticks (R56 territory).
4. Real latency/error interoceptive channels (still first-version injectable defaults in the R50 sampler) feeding additional gate or feeling terms.
5. P5 learning of the load-to-pressure mapping and the gate's resource-pressure weight/threshold.
