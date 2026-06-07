# Requirement 59 - Injectable External Afferent Source (Retire the Fabricated Constant Stimulus)

## 1. Design Overview

Add an optional `external_signal_source` to the `RuntimeProfile` (R58) that conforms to the
existing `02` `SensorySource` protocol. When provided, `assemble_runtime` registers it as the
external sensory source instead of the constant `FirstVersionSensorySource`; its emitted
`RawSignal`s flow through `02` normalization into the appraised batch unchanged, so a real,
tick-varying external stimulus drives `03 -> 04 -> 05 -> 07` in any assembly. When absent, the
default placeholder source is registered exactly as today. The injected external source and
`channel_cli=True` are mutually exclusive (both own the external afferent position). A
first-version `SequenceExternalSignalSource` is shipped for tests/dev that replays
caller-supplied real signals tick by tick — never a fabricated constant.

This is a transport seam, not a new owner. Composition forwards; `02` normalizes; `03`
appraises. No cognitive policy moves into composition.

## 2. Current State and Gap

- `assemble_runtime` registers `FirstVersionSensorySource(signals=resolved_config.source_signals)`
  when `channel_cli` is off, else `SubsystemBackedSensorySource` (R31). The constant source emits
  a fixed `"hello runtime"` `RawSignal` every tick unless `source_signals` is non-empty.
- `RapidSalienceAppraisalRuntimeStage` appraises the whole `02` batch, so a varying external
  stimulus would genuinely drive the affect chain — but no first-class injection seam exists for
  the default/semantic assembly; only the channel-bound assembly can carry a real external source.
- `config.source_signals` exists but is a static per-assembly constant tuple, not a per-tick
  varying source; it is still composition-injected fixed data, not a real afferent.

Gap: the external afferent has no injectable real source seam parallel to the `50` interoceptive
sampler and `55` temporal source, so `FG-1`'s external branch stays fabricated.

## 3. Target Architecture

```
RuntimeProfile (R58)
  external_signal_source: SensorySource | None = None   # new, additive
  __post_init__: external_signal_source and channel_cli both set -> CompositionError

assemble_runtime
  if profile.channel_cli:
      register SubsystemBackedSensorySource            # R31, unchanged
  elif profile.external_signal_source is not None:
      register profile.external_signal_source          # NEW: real external afferent
  else:
      register FirstVersionSensorySource(...)          # placeholder, unchanged

helios_v2.composition.bridges
  @dataclass
  class SequenceExternalSignalSource:                  # first-version injectable real source
      source_name_value: str = "external"
      batches: tuple[tuple[RawSignal, ...], ...] = ()  # caller-supplied per-tick real signals
      _cursor: int                                     # advances each emit; empty tail -> () 
      # emit_raw_signals(): returns batches[cursor] then advances; past the end -> ()
      # NO constant fabrication: empty input yields an explicitly empty afferent
```

`SequenceExternalSignalSource` is the in-repo demonstration source: it replays exactly the real
`RawSignal`s the caller supplies, one batch per tick, and emits an empty tuple when exhausted
(honest absence). It never invents content. Real deployments inject their own `SensorySource`
(e.g. a network driver adapter in `wave_C`).

The mutual-exclusion check lives in `RuntimeProfile.__post_init__` (next to the existing
`embedding requires store` rule), keeping all cross-capability validation in one place (R58).

## 4. Data Structures

No `02` contract changes. `RawSignal`/`Stimulus`/`StimulusBatch` are unchanged. The injected
source emits the existing `RawSignal`. New composition-owned types only:

```python
# RuntimeProfile gains one additive field:
external_signal_source: "SensorySource | None" = None

# First-version injectable real source (composition, test/dev):
@dataclass
class SequenceExternalSignalSource:
    source_name_value: str = "external"
    batches: tuple[tuple[RawSignal, ...], ...] = ()
    _cursor: int = field(default=0, init=False)
    @property
    def source_name(self) -> str: ...
    def emit_raw_signals(self) -> tuple[RawSignal, ...]: ...   # batches[cursor], then advance; empty past end
```

`source_name` defaults to `"external"` (distinct from the placeholder's `"cli"`), so a stimulus
from the real source carries honest provenance (`source_name`/`channel`) into `03`'s
transport-grounded social appraisal and the store.

## 5. Module Changes

1. `runtime_assembly.py`
   - `RuntimeProfile`: add `external_signal_source` field; extend `__post_init__` with the
     `external_signal_source and channel_cli` mutual-exclusion `CompositionError`.
   - `_resolve_profile` / `assemble_runtime`: add `external_signal_source` to the loose-kwarg
     bridge and the `_UNSET` sentinel set (R58 pattern), so it is accepted both as a loose kwarg
     and via an explicit profile.
   - The sensory-source registration branch becomes: `channel_cli` -> subsystem source; elif
     `external_signal_source` -> the injected source; else -> `FirstVersionSensorySource`.
2. `bridges.py`
   - Add `SequenceExternalSignalSource` (the first-version injectable real source). Document it
     as the honest demonstration source: replays caller-supplied real signals, empty when
     exhausted, no constant fabrication.
3. `composition/__init__.py`
   - Export `SequenceExternalSignalSource` for tests/dev callers.
4. Tests in `test_runtime_composition.py` (see Validation Strategy).

## 6. Migration Plan

1. Add the `RuntimeProfile` field + mutual-exclusion validation.
2. Thread the field through `_resolve_profile`, the `_UNSET` loose-kwarg set, and the
   registration branch.
3. Add `SequenceExternalSignalSource` and export it.
4. Add focused tests (injection, mutual exclusion, varying-source affect chain, empty afferent,
   default unchanged).
5. Run the full suite; assert default behavior is byte-for-byte unchanged.
6. Update documentation truth, including the honest `FG-1` external-afferent status.

No rewrite, no parallel chain. The registration branch is the only behavioral change, gated on a
new opt-in field; everything else is additive.

## 7. Failure Modes and Constraints

1. `external_signal_source` + `channel_cli=True` -> `CompositionError` at profile construction.
2. A source `emit_raw_signals` failure propagates as a hard stop (existing `02` behavior); no
   fabricated stimulus substitutes.
3. An injected source emitting an empty batch is a defined honest-absence behavior: the tick
   proceeds on other afferents or closes through the existing no-fire/internal-only path
   (R54/R28). The required-signal validation in `02` only rejects a required signal with empty
   content, not an empty batch.
4. The default placeholder source is unchanged and explicitly documented as NON-REAL; this
   requirement does not make the default real (that needs a real deployed source), it makes a
   real source injectable and stops counting the constant as a real afferent.

## 8. Rollout (Default-On vs Default-Off)

Opt-in and default-off. With no `external_signal_source` and `channel_cli=False`, the assembly
registers the same constant placeholder as today and is byte-for-byte unchanged. The capability
activates only when a caller injects a real source.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. Neither the
new source nor the registration branch uses `logging`/`print`; the ad-hoc-logging guard stays
green.

## 10. Validation Strategy

1. Injection replaces the constant: assembling with an `external_signal_source` registers it and
   a tick's batch carries that source's `source_name`/content, not `"hello runtime"`.
2. Mutual exclusion: `assemble_runtime(external_signal_source=..., channel_cli=True)` raises
   `CompositionError`.
3. Affect chain driven by external stimulus (semantic assembly): a `SequenceExternalSignalSource`
   with two distinct-content batches yields measurably different `03` novelty and different
   `04`/`05` state across the two ticks (a second `FG-2` causal chain alongside R51's
   interoceptive one), reconstructable from the stage results.
4. Honest absence: an injected source that emits an empty batch completes the tick (no-fire or
   internal-only closure), no crash.
5. Default unchanged: with the field unset, the existing composition/stage-chain/persistence
   tests stay green; the full network-free suite is green with only the added focused tests in
   the count; owner-boundary and ad-hoc-logging guards stay green.
