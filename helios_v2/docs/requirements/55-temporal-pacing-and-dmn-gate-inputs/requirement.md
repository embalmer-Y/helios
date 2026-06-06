# Requirement 55 - Temporal pacing and DMN rest-state gate inputs

## 1. Background and Problem

Two of the `09` thought-gate's inputs are still composition-injected constants: `temporal_signal` (hardcoded `0.4`) and `dmn_available` (hardcoded `True`). Both are real, behaviorally-active gate terms in the `09` owner: the gate score adds `temporal_signal * 0.10` and `+0.10 when dmn_available`. So a constant `0.4`/`True` means the gate always receives a fixed temporal nudge and always treats the default-mode network as engaged, regardless of the runtime's actual situation.

These two inputs map to a well-grounded brain dynamic that the constants flatten away. The default-mode network (DMN: mPFC/PCC/precuneus/hippocampus — self-narrative, recall, simulation, introspection) is anti-correlated with the task-positive frontoparietal network: it engages during rest (no external task) and is suppressed during external task engagement. And the propensity for spontaneous, internally-generated thought accumulates the longer the system has been at rest without thinking — the temporal pacing of mind-wandering. With both inputs constant, Helios cannot express the most basic rest-state cognition: a system that, left without external stimulus, grows progressively more likely to start an internally-generated thought, and that disengages the DMN when an external task arrives.

R54 made grounding these safe: a real temporal/DMN input can now legitimately fail to push the gate over threshold (a no-fire tick) without aborting the runtime, so the gate can be driven by real situational facts across its full range.

## 2. Goal

Ground the `09` gate's `temporal_signal` and `dmn_available` in a real temporal/rest-state source instead of constants, so that under an opt-in temporal assembly the default-mode network is reported available only when the runtime is at rest (no external stimulus this tick) and the temporal pacing signal accumulates across consecutive non-firing ticks (resetting when a thought fires), making the runtime progressively more likely to start a spontaneous internally-generated thought the longer it has been at rest; the temporal-to-gate and rest-to-DMN mappings are owned by a new temporal source owner, composition forwards only the raw situational facts and the cross-tick elapsed state, the `09` owner keeps its gate weights, and assemblies without a temporal source keep the constant `0.4`/`True` byte-for-byte.

## 3. Functional Requirements

### 3.1 Temporal source owner
1. A new owner (`helios_v2.temporal`) must provide a `TemporalSource` that produces a bounded `TemporalPacingSample` carrying a `temporal_signal` in `[0,1]` and a `dmn_available` boolean.
2. The first-version source must derive `dmn_available` from a real rest-state fact: the default-mode network is available (engaged) when there is no external stimulus in the current tick (rest), and unavailable when an external stimulus is present (the system is engaged in an external task). The owner owns this rest-to-DMN mapping; composition supplies only the raw external-stimulus-presence fact.
3. The first-version source must derive `temporal_signal` from a real elapsed-rest fact: a bounded accumulation that rises across consecutive ticks in which no thought fired and resets when a thought fires (the spontaneous-thought pacing of rest). The owner owns this elapsed-to-signal mapping and the accumulation/reset dynamics; composition supplies only the per-tick fire/no-fire fact.
4. The temporal source must own its cross-tick elapsed state (ticks since the last fired thought) as a first-class owner concept, advanced by an explicit per-tick fire/no-fire observation; it must not be a hidden global or a fabricated value.

### 3.2 Gate wiring
1. When a temporal source is wired, the composition gate-signal bridge must forward the source's `temporal_signal` and `dmn_available` into the `ThoughtGateSignalSnapshot` in place of the constants, reading the raw external-stimulus-presence fact from the current tick's `02` sensory batch and the elapsed state from the source.
2. The bridge must forward only raw facts and the source's bounded outputs. The gate weights (`temporal_signal * 0.10`, the `dmn_available` `0.10` term) and all gate-decision semantics remain owned by the `09` thought-gating owner (unchanged).
3. The cross-tick elapsed state must be advanced after each tick from the published `09` gate decision (fire resets the accumulation; no-fire advances it), through an explicit owner-neutral post-tick carry seam, so the temporal signal genuinely reflects elapsed rest.

### 3.3 Absence and rollout
1. The temporal source is an explicit opt-in. Assemblies without a temporal source keep the constant `temporal_signal=0.4` and `dmn_available=True` byte-for-byte (the default, recency-only, semantic, channel-bound, and interoceptive assemblies are unchanged when no temporal source is wired).
2. The temporal source must be deterministic given its inputs (a fixed sequence of fire/no-fire observations and external-stimulus facts yields a deterministic signal sequence), independent of wall-clock time.
3. There is no degraded temporal mode: an unsupplied source is the defined constant; a supplied source is always a real bounded reading.

## 4. Non-Functional Requirements

1. Performance: one bounded read over the already-present `02` batch and one integer-state read per tick; no I/O, no network, no new stage.
2. Reliability and fault tolerance: deterministic and bounded for a fixed observation sequence; the accumulation is clamped to `[0,1]`.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. The real values surface only in the existing `ThoughtGateResult.contributing_signals` and the gate decision.
4. Compatibility and migration: additive — a new owner, an opt-in assembly parameter, a shared bridge helper, and a post-tick carry seam. No contract change to `ThoughtGateSignalSnapshot`/`ThoughtGateResult`. Existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The rest-to-DMN and elapsed-to-temporal mappings and the accumulation/reset dynamics are owned by `helios_v2.temporal`. The bridge is owner-neutral glue forwarding raw facts; the `09` owner keeps the gate weights.
2. The temporal owner must hold no salience/feeling/cognitive policy and must not import the gate, appraisal, feeling, or neuromodulation owners. It consumes only bounded situational facts (external-stimulus presence, fire/no-fire) it is given.
3. No fabricated temporal state: the elapsed accumulation is advanced only by real per-tick fire/no-fire observations; an unsupplied source is the defined constant, never an invented non-constant value.
4. No `logging`/`print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/temporal/__init__.py`, `contracts.py`, `engine.py` (new owner: `TemporalPacingSample`, `TemporalSource` protocol, `TemporalError`, first-version `RestStateTemporalSource`)
2. `helios_v2/src/helios_v2/composition/bridges.py` (a shared `_temporal_inputs(frame, temporal_source)` helper + an `_external_stimulus_present(frame)` reader; both gate-signal bridges forward the temporal source's outputs)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in `temporal_source` param; inject into the active gate-signal bridge; a `_carry_temporal` post-tick seam advancing the elapsed state from the gate decision)
4. `helios_v2/tests/test_temporal_contracts.py` / `test_temporal_engine.py` (new: sample bounds, rest-to-DMN, elapsed accumulation/reset, determinism)
5. `helios_v2/tests/test_runtime_composition.py` (temporal assembly: rest ticks accumulate temporal_signal and report dmn_available; an external stimulus disengages DMN; default keeps `0.4`/`True`)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (new temporal/DMN analog row or note; narrow the `09-11` gate-input shim note)
9. `helios_v2/docs/OWNER_GUIDE.md`, `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
10. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. A new `helios_v2.temporal` owner provides a `TemporalSource` producing a bounded `TemporalPacingSample` (`temporal_signal` in `[0,1]`, `dmn_available` bool); the first-version `RestStateTemporalSource` maps rest (no external stimulus) to `dmn_available=True`, an external stimulus to `dmn_available=False`, and accumulates `temporal_signal` across consecutive no-fire ticks, resetting it on a fire.
2. Under an opt-in temporal assembly, the gate-signal bridge forwards the source's `temporal_signal` and `dmn_available` into the snapshot (surfacing the real values in `contributing_signals`); the `09` gate weights and decision semantics are unchanged.
3. Across consecutive no-fire rest ticks the `temporal_signal` strictly increases (until clamped) and resets after a firing tick; a tick with an external stimulus reports `dmn_available=False`. The source is deterministic for a fixed observation sequence.
4. The elapsed state is advanced post-tick from the published gate decision through an owner-neutral seam; the temporal owner imports no gate/appraisal/feeling/neuromodulation owner.
5. With no temporal source wired, the gate keeps `temporal_signal=0.4` and `dmn_available=True` byte-for-byte; the default and other assemblies are unchanged.
6. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R55 grounds the temporal/DMN gate inputs. The following remain future:

1. `drive_urgency_signal` carried from `18` across ticks (R56), the last remaining constant gate input besides the stimulus projection.
2. The `selected_stimuli` gate/retrieval projection grounded in the real `02`/`03` output (a later slice).
3. Richer temporal dynamics (circadian/ultradian rhythms, a real wall-clock or tick-rate pacing) and P5 learning of the accumulation rate and the gate weights.
4. A sharper DMN model (graded engagement rather than a binary rest/task switch; coupling DMN availability to introspective retrieval).
