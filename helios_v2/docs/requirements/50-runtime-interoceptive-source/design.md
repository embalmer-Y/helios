# Requirement 50 - Runtime interoceptive signal source (design)

## 1. Design Overview

R50 adds a new owner, `helios_v2.interoception`, that produces real interoceptive `RawSignal`s from the runtime's actual internal condition (compute/runtime pressure) and registers into sensory ingress as an ordinary `SensorySource`. This closes the *producer* half of `gap_interoceptive_signal_source`: the `02 -> 05` afferent path that already exists in code (the `05` stage filters `modality in {body, interoceptive}`) finally carries real signals.

Three pieces, all in the new owner plus opt-in composition wiring:

1. A `RuntimePressureSample` contract (bounded `[0,1]` pressure channels: cpu, memory, latency, error rate) and a narrow injected `RuntimePressureSampler` protocol.
2. A first-version `StdlibRuntimePressureSampler` that reads real, cheap, network-free runtime facts (lazily using `psutil` if importable, else stdlib `os`/process facts), normalizes them into `[0,1]`, and returns defined bounded defaults for unavailable facts (never raising for a merely-unavailable fact).
3. A `RuntimeInteroceptiveSource` implementing `SensorySource`: each `emit_raw_signals()` samples and projects the sample into bounded interoceptive `RawSignal`s (`signal_type="interoceptive"`).

Composition registers the source as an additional ingress source under an explicit opt-in. Default-off: the default assembly is byte-for-byte unchanged.

Scope boundary (honest, no half-step): R50 delivers the **producer** and the **live afferent** (`05` receives non-empty, validated `internal_signals`). `05`'s R38/R44 construction path continues to ignore `internal_signals` this slice exactly as today, so the felt body-state value is unchanged; making `05` *use* the interoceptive signal to shape feeling is the explicitly-deferred next slice. This is a real, testable milestone (the BODY producer now exists and the afferent is live and validated) without over-claiming that feeling is yet body-driven.

## 2. Current State and Gap

Current state (verified in code):

1. `InteroceptiveFeelingRuntimeStage.run` filters `sensory_result.batch.stimuli` for `modality in {body, interoceptive}`, validates each via `validate_internal_body_signal`, and forwards them to `05` as `internal_signals`. This path is live but always empty.
2. `validate_internal_body_signal` requires `modality in {body, interoceptive}` and non-empty `stimulus_id`/`source_name`/`provenance_signal_id`. Sensory normalization sets `stimulus_id=f"stimulus:{source_name}:{signal_id}"`, `modality=signal_type`, `provenance_signal_id=signal_id` — so a `RawSignal(signal_type="interoceptive", ...)` from a registered source normalizes into a valid internal body signal automatically.
3. Composition registers exactly one of `FirstVersionSensorySource` (default) or `SubsystemBackedSensorySource` (channel-bound). Ingress supports multiple sources (`register_source` keyed by unique name), so an interoceptive source co-exists with either.
4. `RuntimePressureSample` / a sampler / a producer owner do not exist.

Gap: no owner produces body/interoceptive signals; `05` feeling is top-down (`04`) only.

## 3. Target Architecture

### 3.1 Contracts (`helios_v2.interoception.contracts`)

```
@dataclass(frozen=True)
class RuntimePressureSample:
    """Bounded snapshot of the runtime's real internal condition. All fields in [0,1]."""
    cpu_pressure: float
    memory_pressure: float
    latency_pressure: float
    error_pressure: float
    def __post_init__(self): # validate each in [0,1], else InteroceptionError

@runtime_checkable
class RuntimePressureSampler(Protocol):
    def sample(self) -> RuntimePressureSample: ...

class InteroceptionError(RuntimeError): ...
```

### 3.2 First-version stdlib sampler (`helios_v2.interoception.engine`)

```
@dataclass
class StdlibRuntimePressureSampler(RuntimePressureSampler):
    """Reads real, cheap, network-free runtime facts; normalizes to [0,1]; defined defaults
    for unavailable facts (never raises for a merely-unavailable fact)."""
    default_latency_pressure: float = 0.0
    default_error_pressure: float = 0.0
    def sample(self) -> RuntimePressureSample:
        cpu = self._cpu_pressure()       # psutil.cpu_percent()/100 if importable, else os.getloadavg-derived, else default
        mem = self._memory_pressure()    # psutil.virtual_memory().percent/100 if importable, else default
        return RuntimePressureSample(
            cpu_pressure=cpu, memory_pressure=mem,
            latency_pressure=self.default_latency_pressure,
            error_pressure=self.default_error_pressure,
        )
```

`psutil` is imported lazily inside the helper and wrapped: `ImportError` or any read error for a fact falls back to the defined default (a defined bounded reading, not a fabricated "healthy" claim — the default for unavailable cpu/memory is documented as "unknown -> neutral baseline"). Latency/error pressure are injectable defaults this slice (a later slice can feed real tick-latency / recent-error-rate from observability). The sampler imports no helios owner.

Tests inject a deterministic `FakeRuntimePressureSampler(sample=RuntimePressureSample(...))`; the suite never depends on the host's real CPU/memory and never imports psutil (the fake bypasses `_cpu_pressure`).

### 3.3 Interoceptive source owner (`helios_v2.interoception.engine`)

```
@dataclass
class RuntimeInteroceptiveSource:   # implements SensorySource
    sampler: RuntimePressureSampler
    source_name_value: str = "interoception"
    @property
    def source_name(self) -> str: return self.source_name_value
    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        sample = self.sampler.sample()
        return tuple(
            RawSignal(
                signal_id=f"interoceptive:{channel}",
                source_name=self.source_name_value,
                signal_type="interoceptive",
                content=f"{channel}={value:.4f}",   # non-empty, bounded, deterministic
                channel="interoception",
                metadata={"pressure_channel": channel, "pressure_value": value},
                required=False,
            )
            for channel, value in (
                ("cpu", sample.cpu_pressure),
                ("memory", sample.memory_pressure),
                ("latency", sample.latency_pressure),
                ("error", sample.error_pressure),
            )
        )
```

Each emitted `RawSignal` has `signal_type="interoceptive"`, so sensory normalizes it to `Stimulus(modality="interoceptive", ...)`, which the `05` stage filters in and `validate_internal_body_signal` accepts. The content string is bounded and deterministic for a fixed sample. `required=False` so an empty content (impossible here, but defensive) would be skipped rather than aborting the batch. The source owns only this projection; it computes no feeling/salience.

Design note (why four `RawSignal`s, one per channel, not one bundled signal): one signal per interoceptive channel mirrors distinct afferent streams (cardiac/respiratory/visceral are distinct in the brain), lets `05` (in a later slice) weight channels independently, and keeps each stimulus a single bounded fact. The `pressure_value` rides metadata for a future `05` consumer that reads the numeric value rather than parsing content.

### 3.4 Opt-in wiring in assembly

`assemble_runtime` gains an opt-in (for example `interoceptive_source: RuntimePressureSampler | None = None`, or a boolean `interoception=True` that constructs the stdlib sampler). When provided/enabled, after registering the primary sensory source, composition also registers `RuntimeInteroceptiveSource(sampler=...)`. Default-off: when not requested, no interoceptive source is registered and the assembly is unchanged.

The interoceptive source co-exists with both the default `FirstVersionSensorySource` and the channel-bound `SubsystemBackedSensorySource` (ingress keys sources by unique name; `"interoception"` does not collide). This slice wires it for the default/semantic assemblies; the channel-bound combination is allowed but not required to be exercised here.

### 3.5 Default rollout

Default-off. Only an assembly that explicitly opts into interoception registers the source. The default, channel-bound, and semantic assemblies are byte-for-byte unchanged when interoception is off (`internal_signals` stays empty).

## 4. Data Structures

1. `RuntimePressureSample` (frozen, four `[0,1]` channels) — `helios_v2.interoception.contracts`.
2. `RuntimePressureSampler` protocol + `InteroceptionError` — `helios_v2.interoception.contracts`.
3. `StdlibRuntimePressureSampler` (first-version, lazy psutil, defined defaults) — `helios_v2.interoception.engine`.
4. `RuntimeInteroceptiveSource` (implements the existing `SensorySource`) — `helios_v2.interoception.engine`.
No change to `RawSignal`/`Stimulus`/`SensorySource`/`05` contracts.

## 5. Module Changes

1. New `helios_v2/src/helios_v2/interoception/__init__.py`, `contracts.py`, `engine.py`.
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: add the opt-in parameter; when enabled, register `RuntimeInteroceptiveSource` into ingress after the primary source. No stage-order change.

## 6. Migration Plan

1. All new code is additive and in a new owner package; the default assembly registers no interoceptive source and is unchanged.
2. No contract change to sensory or `05`; the afferent path already exists and simply starts carrying signals when the source is enabled.
3. No stage-order change; the source is an ingress source, collected in the existing `02` stage.
4. `psutil` is optional and lazily imported; absence degrades to defined defaults, so no new mandatory dependency.

## 7. Failure Modes and Constraints

1. An unavailable runtime fact (no psutil, or a read error for cpu/memory): the sampler returns the defined bounded default for that channel (documented "unknown -> neutral baseline"), never raising. This is a defined reading, not a fabricated specific condition.
2. An outright sampler exception (a bug in an injected sampler, not a merely-unavailable fact): propagates as a hard stop; the runtime does not swallow it into a fake healthy body.
3. The emitted signals are bounded (`[0,1]` enforced by `RuntimePressureSample.__post_init__`) and deterministic for a fixed sample.
4. The owner holds no feeling/salience/cognitive policy and imports no feeling/appraisal/neuromodulation owner; sensory ingress owns normalization.
5. No `logging`/`print` under `src/`; the guard test stays green.
6. `05`'s feeling value is unchanged this slice (its construction path still ignores `internal_signals`); the deliverable is the live, validated afferent, explicitly recorded so the gap note distinguishes "producer exists" from "05 consumes it".

## 8. Observability and Logging

No new logging mechanism. Interoceptive facts travel through the existing `RawSignal` -> `Stimulus` contracts and appear as `modality="interoceptive"` stimuli in the `02` batch and the `05` stage's `internal_signals`. No emission is added.

## 9. Validation Strategy

Network-free, deterministic, using an injected fake sampler (the suite never reads the host's real CPU/memory and never imports psutil).

1. `test_interoception_contracts.py`:
   - `RuntimePressureSample` accepts `[0,1]` values and rejects out-of-range (raises `InteroceptionError`).
2. `test_interoception_engine.py`:
   - `RuntimeInteroceptiveSource` with a fake sampler emits one `interoceptive` `RawSignal` per channel, each with non-empty fields, `signal_type="interoceptive"`, bounded metadata, and deterministic content for a fixed sample.
   - the emitted signals, run through `SensoryIngress`, normalize to `modality="interoceptive"` stimuli that pass `validate_internal_body_signal`.
   - `StdlibRuntimePressureSampler` returns a `RuntimePressureSample` with all channels in `[0,1]` even when psutil is absent (monkeypatch the lazy import to raise `ImportError`), using the defined defaults; it does not raise for an unavailable fact.
3. `test_runtime_composition.py` (extend):
   - opt-in interoception assembly: a tick's `05` feeling stage received non-empty `internal_signals` (assert via the `02` batch carrying `modality="interoceptive"` stimuli, and/or the `05` update op's `internal_signal_count > 0`).
   - default assembly: no interoceptive stimuli; `internal_signals` empty; `05` behavior unchanged.
4. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_interoception_engine.py -q
```
