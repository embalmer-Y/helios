# Requirement 55 - Temporal pacing and DMN rest-state gate inputs (design)

## 1. Design Overview

R55 adds a new owner `helios_v2.temporal` that produces the two still-constant `09` gate inputs — `temporal_signal` and `dmn_available` — from real situational facts, and wires it into the gate-signal bridge (the same forward-a-raw-fact seam R37/R48/R53 use). It mirrors R50's `interoception` owner structure (a small contract + injected-source protocol + first-version source), but the outputs feed the gate-signal bridge directly (a gate modulation input), not `02` sensory.

Two real facts drive it:

1. **DMN availability (rest vs task):** the default-mode network is engaged at rest and suppressed during external task. The source reports `dmn_available = (no external stimulus this tick)`. The raw fact "is there an external stimulus this tick" is read by composition from the `02` batch (any stimulus whose modality is not internal — `body`/`interoceptive`/`background`).

2. **Temporal pacing (elapsed rest):** the propensity for spontaneous internally-generated thought accumulates the longer the system has been at rest without thinking. The source holds a cross-tick `ticks_since_last_fire` count and maps it to a bounded `temporal_signal` that rises across consecutive no-fire ticks and resets on a fire.

The cross-tick elapsed state is advanced after each tick from the published `09` gate decision through an owner-neutral `RuntimeHandle._carry_temporal` seam (mirroring `_carry_recall_directive`): a `fire` resets the count to 0; a `no_fire` increments it. The source owns the count and the mapping; composition only observes the published decision and calls the owner's advance method.

Scope: opt-in. When no temporal source is wired, both bridges keep the constant `0.4`/`True` byte-for-byte.

## 2. Current State and Gap

Verified in code:

1. `09` gate score adds `signal_snapshot.temporal_signal * 0.10 + (0.10 if signal_snapshot.dmn_available else 0.0)`. Both are real, bounded gate terms.
2. Both gate-signal bridges (`NeuromodulatorAwareThoughtGateSignalBridge` semantic, `FirstVersionThoughtGateSignalBridge` default) hardcode `temporal_signal=0.4`, `dmn_available=True`.
3. The bridge already receives `frame` and (R53) reads the `02` `SensoryIngressStageResult` batch via a helper. Stimulus modality distinguishes external (`text`/`cli`/...) from internal (`body`/`interoceptive`/`background`).
4. R54 closed the no-fire tick, so a grounded temporal input that fails to push the gate over threshold completes the tick as a no-fire rather than aborting.

Gap: the temporal/DMN gate inputs are constants; the runtime cannot express rest-state spontaneous-thought pacing or DMN task-disengagement.

## 3. Target Architecture

### 3.1 Contracts (`helios_v2.temporal.contracts`)

```
@dataclass(frozen=True)
class TemporalPacingSample:
    """Bounded temporal/rest-state gate inputs for one tick."""
    temporal_signal: float   # [0,1], spontaneous-thought pacing from elapsed rest
    dmn_available: bool       # default-mode network engaged (rest) vs suppressed (external task)
    def __post_init__(self): # validate temporal_signal in [0,1], else TemporalError

@runtime_checkable
class TemporalSource(Protocol):
    def sample(self, external_stimulus_present: bool) -> TemporalPacingSample: ...
    def observe_tick(self, fired: bool) -> None: ...   # advance cross-tick elapsed state

class TemporalError(RuntimeError): ...
```

`sample(external_stimulus_present)` returns the current tick's pacing + DMN fact (DMN from the rest fact, temporal_signal from the current elapsed count). `observe_tick(fired)` advances the elapsed state after the tick (fire -> reset, no-fire -> increment).

### 3.2 First-version source (`helios_v2.temporal.engine`)

```
@dataclass
class RestStateTemporalSource(TemporalSource):
    """First-version temporal/rest-state source.

    dmn_available = not external_stimulus_present (DMN engages at rest, suppressed on external task).
    temporal_signal = clamp(per_tick_increment * ticks_since_last_fire, 0, max_signal), rising across
    consecutive no-fire ticks and reset on a fire. The increment/cap are bounded first-version
    constants under a declared learned-parameter category (P5-learnable)."""
    per_tick_increment: float = 0.2
    max_signal: float = 1.0
    _ticks_since_last_fire: int = 0   # init=False owner state

    def sample(self, external_stimulus_present: bool) -> TemporalPacingSample:
        signal = min(self.max_signal, self.per_tick_increment * self._ticks_since_last_fire)
        return TemporalPacingSample(temporal_signal=round(signal, 4),
                                    dmn_available=not external_stimulus_present)

    def observe_tick(self, fired: bool) -> None:
        self._ticks_since_last_fire = 0 if fired else self._ticks_since_last_fire + 1
```

Design notes:
- The elapsed count starts at 0 (cold start: no accumulated rest, so the first tick's `temporal_signal` is 0 — a defined cold start, not a fabricated history, consistent with the R43/R44 cold-start convention).
- `temporal_signal` is monotonic non-decreasing across consecutive no-fire ticks until clamped, and resets to 0 the tick after a fire. This is exactly the "longer at rest -> more likely to spontaneously think; just thought -> pacing resets" dynamic.
- The owner holds no salience/feeling policy and imports no other owner.

### 3.3 Bridge wiring (`bridges.py`)

A shared helper reads the raw external-stimulus fact and asks the source for the sample:

```
_INTERNAL_MODALITIES = frozenset({"body", "interoceptive", "background"})

def _external_stimulus_present(frame) -> bool:
    sensory = (frame.stage_results or {}).get("sensory_ingress")
    if not isinstance(sensory, SensoryIngressStageResult):
        return False
    return any(s.modality not in _INTERNAL_MODALITIES for s in sensory.batch.stimuli)

def _temporal_inputs(frame, temporal_source) -> tuple[float, bool]:
    if temporal_source is None:
        return 0.4, True   # constant first-version values, byte-for-byte
    sample = temporal_source.sample(_external_stimulus_present(frame))
    return sample.temporal_signal, sample.dmn_available
```

Both gate-signal bridges gain an optional `temporal_source` field (default `None`) and replace the constants:

```
temporal_signal, dmn_available = _temporal_inputs(frame, self.temporal_source)
return ThoughtGateSignalSnapshot(..., temporal_signal=temporal_signal, dmn_available=dmn_available, ...)
```

`temporal_source is None` reproduces the constant path exactly.

### 3.4 Cross-tick advance (`runtime_assembly.py`)

`assemble_runtime` gains `temporal_source: TemporalSource | None = None`. When provided, it is set on the active gate-signal bridge (`bridge.temporal_source = temporal_source`) and stored on the `RuntimeHandle`. A new post-tick seam advances it:

```
def _carry_temporal(self, result):
    if self.temporal_source is None:
        return
    gate = result.stage_results.get("thought_gating_and_continuation_pressure")
    decision = getattr(getattr(gate, "result", None), "decision", None)
    if decision is None:
        return
    self.temporal_source.observe_tick(fired=(decision == "fire"))
```

Called in `tick()` alongside the other carry seams. The source is owner-neutral state advanced only by the published decision; composition computes nothing.

### 3.5 Default rollout

Default-off. Only an assembly that passes `temporal_source=...` grounds these inputs; every other assembly keeps `0.4`/`True` byte-for-byte (the helper returns the constants when the source is `None`, and the source is never constructed).

## 4. Data Structures

1. `TemporalPacingSample` (frozen, validated) + `TemporalSource` protocol + `TemporalError` — `helios_v2.temporal.contracts`.
2. `RestStateTemporalSource` (first-version, cross-tick elapsed state) — `helios_v2.temporal.engine`.
3. An optional `temporal_source` field on both gate-signal bridges; a `temporal_source` param + `_carry_temporal` seam on the runtime. No change to `ThoughtGateSignalSnapshot`/`ThoughtGateResult`.

## 5. Module Changes

1. New `helios_v2/src/helios_v2/temporal/{__init__,contracts,engine}.py`.
2. `bridges.py`: `_INTERNAL_MODALITIES`, `_external_stimulus_present`, `_temporal_inputs`; `temporal_source` field on both gate-signal bridges; constants replaced via the helper.
3. `runtime_assembly.py`: `temporal_source` param; set on the active bridge; `RuntimeHandle.temporal_source` + `_carry_temporal` seam called in `tick()`.

## 6. Migration Plan

1. Additive new owner; both bridges default `temporal_source=None` and return the constants.
2. No contract or stage-order change; the gate-signal bridge already runs after `02`.
3. The only behavior change is on an assembly that wires a temporal source.

## 7. Failure Modes and Constraints

1. No temporal source -> the defined constants `0.4`/`True` (current behavior), never a fabricated non-constant value.
2. The elapsed accumulation is clamped to `[0,1]` and advanced only by real per-tick fire/no-fire observations; deterministic for a fixed observation sequence.
3. A missing `02` result in `_external_stimulus_present` is treated as no external stimulus (rest) — a defined reading, consistent with an empty tick.
4. The temporal owner imports no gate/appraisal/feeling/neuromodulation owner; the gate weights stay in `09`.
5. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The real values surface only in `ThoughtGateResult.contributing_signals["temporal_signal"]` and the gate decision (and `dmn_available` through its `+0.10` gate-score contribution).

## 9. Validation Strategy

Network-free, deterministic.

1. `test_temporal_contracts.py`: `TemporalPacingSample` accepts `[0,1]` and rejects out-of-range `temporal_signal`.
2. `test_temporal_engine.py`:
   - `RestStateTemporalSource.sample(external_stimulus_present=False)` -> `dmn_available=True`; `=True` -> `dmn_available=False`.
   - Across consecutive `observe_tick(fired=False)` calls, `sample(...).temporal_signal` strictly increases until clamped at `max_signal`; after `observe_tick(fired=True)` it resets to 0.
   - Deterministic for a fixed observation sequence.
3. `test_runtime_composition.py` (extend):
   - A temporal assembly run over several no-input (rest) ticks shows `contributing_signals["temporal_signal"]` increasing across ticks and `dmn_available` engaged (its `+0.10` reflected in the gate score / decision), then resetting after a fired tick.
   - A tick with an external stimulus reports `dmn_available=False` (DMN disengaged).
   - The default assembly keeps `temporal_signal=0.4` (and the DMN term) byte-for-byte.
4. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_temporal_engine.py -q
```
