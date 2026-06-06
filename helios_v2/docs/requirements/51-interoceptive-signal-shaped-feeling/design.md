# Requirement 51 - Interoceptive-signal-shaped feeling (design)

## 1. Design Overview

R51 makes the `05` feeling owner consume the interoceptive `internal_signals` it already receives (delivered live by R50) so the runtime's real internal condition shapes the felt body-state. The change is one new owner-owned construction path plus opt-in composition wiring; no contract changes anywhere.

The new path, `InteroceptiveSignalModulatedFeelingConstructionPath`, lives in `helios_v2.feeling` and **wraps** the existing `NeuromodulatorDerivedFeelingConstructionPath` (the R38 instantaneous target). It:

1. computes the neuromodulator-derived target feeling through the wrapped inner path (unchanged),
2. reads the bounded interoceptive pressure facts (`pressure_channel` + `pressure_value`) from the `internal_signals` the `05` engine passes in,
3. adds a bounded, non-negative, stress-directional per-dimension contribution to the target, clamped to the legal range.

The composition assembly nests it inside the existing R44 `PersistentFeelingConstructionPath`, so the interoceptive contribution flows through the same dual-timescale leaky-integrator carry as the neuromodulator-derived component — no second persistence mechanism. The final wiring under the interoceptive+semantic assembly is:

```
PersistentFeelingConstructionPath(                       # R44 cross-tick carry/decay
    target_path=InteroceptiveSignalModulatedFeelingConstructionPath(  # R51 body contribution
        target_path=NeuromodulatorDerivedFeelingConstructionPath()    # R38 top-down target
    )
)
```

Scope boundary (honest): R51 changes only how the instantaneous target is computed when interoceptive signals are present. When `internal_signals` is empty (no interoceptive source), the new path returns the inner neuromodulator-derived target byte-for-byte, so every assembly without an interoceptive source is unchanged. The downstream consumer that makes this a real FG-2 chain (`07` workspace competition reading arousal/tension/pain via R46) already exists and is unchanged.

## 2. Current State and Gap

Current state (verified in code):

1. `InteroceptiveFeelingEngine.update_state` validates each internal signal (`validate_internal_body_signal`) and forwards `internal_signals` plus `prior_state.feeling` to `construction_path.construct_feeling(...)`.
2. `NeuromodulatorDerivedFeelingConstructionPath.construct_feeling` does `del internal_signals` — it ignores the afferent and derives feeling from `04` levels only.
3. `PersistentFeelingConstructionPath` wraps the target path and applies the R44 dual-timescale step; it forwards `internal_signals`/`tick_id` to the inner target path but the inner path drops them.
4. R50 interoceptive signals normalize to `Stimulus(modality="interoceptive", metadata={"pressure_channel": <cpu|memory|latency|error>, "pressure_value": <float in [0,1]>}, ...)`; sensory preserves `metadata` verbatim onto the `Stimulus`.
5. `SalienceWeightedWorkspaceCompetitionPath` (R46) already scores candidates from `05` arousal/tension/pain, so a changed `05` feeling already changes `07` competition under the semantic assembly.

Gap: `05` ignores the afferent, so the real machine condition never reaches the felt body-state or anything downstream.

## 3. Target Architecture

### 3.1 New owner-owned construction path (`helios_v2.feeling.engine`)

```
# Owner-owned reserved metadata keys the R50 producer sets (read, not parsed from content).
_PRESSURE_CHANNEL_KEY = "pressure_channel"
_PRESSURE_VALUE_KEY = "pressure_value"

@dataclass
class InteroceptiveSignalModulatedFeelingConstructionPath(FeelingConstructionPath):
    """Owner: interoceptive feeling layer (R51).

    Wraps an inner target path (the R38 neuromodulator-derived instantaneous feeling) and adds a
    bounded, non-negative, stress-directional contribution derived from the real interoceptive
    pressure afferent, so the runtime's real internal condition shapes the felt body-state. The
    body-signal-to-feeling mapping is owned here. Additive over the inner target and clamped; an
    empty/unrecognized afferent reproduces the inner target byte-for-byte.
    """
    target_path: FeelingConstructionPath
    # cpu pressure -> alertness/load
    cpu_to_arousal: float = 0.30
    cpu_to_tension: float = 0.20
    # memory pressure -> sustained load / fatigue
    memory_to_fatigue: float = 0.30
    memory_to_tension: float = 0.15
    # latency pressure -> sluggishness / fatigue
    latency_to_fatigue: float = 0.20
    latency_to_tension: float = 0.10
    # error pressure -> distress
    error_to_pain_like: float = 0.30
    error_to_tension: float = 0.20

    def construct_feeling(self, neuromodulator_state, internal_signals, config, tick_id, prior_feeling=None):
        target = self.target_path.construct_feeling(
            neuromodulator_state, internal_signals, config, tick_id, prior_feeling
        )
        pressures = self._read_pressures(internal_signals)   # dict channel -> max pressure in [0,1]
        if not pressures:
            return target                                    # byte-for-byte: no afferent contribution
        cpu = pressures.get("cpu", 0.0)
        memory = pressures.get("memory", 0.0)
        latency = pressures.get("latency", 0.0)
        error = pressures.get("error", 0.0)
        low, high = config.legal_min, config.legal_max
        return InteroceptiveFeelingVector(
            valence=target.valence,                          # unchanged this slice
            arousal=_clamp(target.arousal + self.cpu_to_arousal * cpu, low.arousal, high.arousal),
            tension=_clamp(
                target.tension
                + self.cpu_to_tension * cpu
                + self.memory_to_tension * memory
                + self.latency_to_tension * latency
                + self.error_to_tension * error,
                low.tension, high.tension,
            ),
            comfort=target.comfort,                          # unchanged this slice
            fatigue=_clamp(
                target.fatigue + self.memory_to_fatigue * memory + self.latency_to_fatigue * latency,
                low.fatigue, high.fatigue,
            ),
            pain_like=_clamp(target.pain_like + self.error_to_pain_like * error, low.pain_like, high.pain_like),
            social_safety=target.social_safety,              # unchanged this slice
        )

    def _read_pressures(self, internal_signals) -> dict[str, float]:
        """Read bounded pressure facts from interoceptive stimuli metadata (max per channel).

        Reads only the reserved metadata keys the R50 producer sets; a signal without a recognized
        channel/numeric value in [0,1] contributes nothing (no raise, no fabricated condition).
        """
        pressures: dict[str, float] = {}
        for signal in internal_signals:
            metadata = signal.metadata or {}
            channel = metadata.get(_PRESSURE_CHANNEL_KEY)
            value = metadata.get(_PRESSURE_VALUE_KEY)
            if not isinstance(channel, str):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            v = float(value)
            if v < 0.0 or v > 1.0:
                continue
            pressures[channel] = max(pressures.get(channel, 0.0), v)
        return pressures
```

Design choices:

1. **Wrap, don't modify.** The R38 `NeuromodulatorDerivedFeelingConstructionPath` stays byte-for-byte (it still `del internal_signals`). R51 is a separate path the assembly nests, mirroring how R44 wraps R38. This keeps each owner concern in its own path and keeps the non-interoceptive assemblies provably unchanged.
2. **Read metadata, not content.** The producer (R50) put the numeric value on `metadata["pressure_value"]` precisely "for a future `05` consumer that reads the numeric value rather than parsing content." R51 is that consumer.
3. **Max per channel.** R50 emits one signal per channel; `max` is defensive against duplicates and keeps the contribution a bounded function of the strongest reading per channel.
4. **Stress-directional, additive, non-negative.** Every coefficient is `>= 0` and pressures are `>= 0`, so the contribution can only push toward stress/load (arousal/tension/fatigue/pain) and is then clamped. It never lowers a dimension and never replaces the neuromodulator-derived target. valence/comfort/social_safety are intentionally untouched this slice (mapping pressure to lowered valence/comfort is a defensible later refinement; first version keeps the claim narrow and monotone).
5. **Coefficients are first-version constants** under the config's declared `feeling_coupling_strength` learned-parameter category (P5-learnable later), like R38/R44.

### 3.2 Composition wiring (`runtime_assembly.py`)

Today:

```
construction_path=(
    PersistentFeelingConstructionPath(target_path=NeuromodulatorDerivedFeelingConstructionPath())
    if semantic_memory_enabled
    else FirstVersionFeelingConstructionPath()
)
```

Target: when the semantic feeling path is active **and** an interoceptive sampler is wired, nest the R51 path between persistence and the neuromodulator target:

```
if semantic_memory_enabled:
    target_path = NeuromodulatorDerivedFeelingConstructionPath()
    if interoceptive_sampler is not None:
        target_path = InteroceptiveSignalModulatedFeelingConstructionPath(target_path=target_path)
    feeling_construction_path = PersistentFeelingConstructionPath(target_path=target_path)
else:
    feeling_construction_path = FirstVersionFeelingConstructionPath()
```

So:
- semantic + interoceptive sampler -> persistence(interoceptive(neuromodulator)): body shapes feeling (new).
- semantic, no interoceptive sampler -> persistence(neuromodulator): unchanged (the R51 path is never constructed; even if it were, empty `internal_signals` reproduces the target).
- non-semantic -> `FirstVersionFeelingConstructionPath`: unchanged.

`interoceptive_sampler` is the existing R50 `assemble_runtime` parameter; no new assembly parameter is required.

### 3.3 Default rollout

Default-off. The body contribution exists only when both the semantic feeling path and the interoceptive sampler are enabled. Default, recency-only, channel-bound-without-interoception, and semantic-without-sampler assemblies are byte-for-byte unchanged.

## 4. Data Structures

No new contract. One new owner-owned construction path class (`InteroceptiveSignalModulatedFeelingConstructionPath`) implementing the existing `FeelingConstructionPath` protocol. It reads the existing reserved metadata keys the R50 producer already sets (`pressure_channel`, `pressure_value`) — these become owner-read keys in `05`, mirroring how the `30` QoS metadata key is an owner-read reserved key. No change to `Stimulus`, `RawSignal`, `InteroceptiveFeelingState`, `InteroceptiveFeelingVector`, or the protocol signature.

## 5. Module Changes

1. `helios_v2/src/helios_v2/feeling/engine.py`: add `InteroceptiveSignalModulatedFeelingConstructionPath` and the two reserved-key constants.
2. `helios_v2/src/helios_v2/feeling/__init__.py`: export the new path.
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: nest the new path when `semantic_memory_enabled and interoceptive_sampler is not None`.

## 6. Migration Plan

1. Additive new path; the R38 and R44 paths are unchanged.
2. No contract change; the afferent and downstream consumer already exist.
3. No stage-order change.
4. The only assembly whose behavior changes is the semantic+interoceptive opt-in, which previously delivered the afferent but dropped it; now it consumes it. All other assemblies are byte-for-byte unchanged.

## 7. Failure Modes and Constraints

1. An interoceptive stimulus without a recognized `pressure_channel` (non-string) or `pressure_value` (non-numeric, bool, or outside `[0,1]`) contributes nothing (skipped), never raising — no fabricated body condition.
2. Empty `internal_signals` returns the inner neuromodulator-derived target byte-for-byte.
3. The contribution is non-negative and clamped, so the feeling vector is always within the legal range for any pressures in `[0,1]`; `InteroceptiveFeelingVector.__post_init__` still enforces it as a backstop.
4. Malformed neuromodulator state is still rejected by the `05` engine before construction runs.
5. The mapping lives in `helios_v2.feeling`; the path imports no interoception/appraisal/neuromodulation/workspace owner.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The body's influence is visible only as changed values in the existing `InteroceptiveFeelingState.feeling` contract (and, downstream, in the `07` `WorkspaceCompetitionStageResult` candidate scores). No emission is added.

## 9. Validation Strategy

Network-free, deterministic, using constructed `Stimulus` values with pressure metadata (no real telemetry, no psutil).

1. `test_interoceptive_feeling_engine.py` (extend):
   - A helper builds an interoceptive `Stimulus(modality="interoceptive", metadata={"pressure_channel": c, "pressure_value": v}, ...)`.
   - High CPU pressure yields arousal/tension not lower than at-rest, with arousal strictly greater for cpu=0.9 vs cpu=0.0.
   - High memory pressure raises fatigue; high latency raises fatigue; high error raises pain_like; each raises tension.
   - Empty `internal_signals` returns exactly the inner `NeuromodulatorDerivedFeelingConstructionPath` output (assert equality with the directly-computed target).
   - A body signal with no/invalid pressure metadata contributes nothing (equals the empty-signals result) and does not raise.
   - Bounded over a maxed neuromodulator state + all pressures = 1.0 (every dimension in `[0,1]`).
   - Deterministic across repeated calls.
   - Through the real `05` engine with the R51 path: a high-pressure signal set yields a feeling-state whose tension/fatigue/pain exceed the at-rest set's.
   - Nested with `PersistentFeelingConstructionPath`: across two ticks the carried feeling reflects the body contribution (the persistence carry composes with the body contribution).
2. `test_runtime_composition.py` (extend):
   - An interoceptive+semantic assembly run with a fake high-pressure sampler produces a `05` feeling-state and a `07` competition candidate score that differ from the same assembly run with an at-rest (all-zero) sampler.
   - The default assembly is unchanged (no interoceptive stimuli; `05` feeling identical to pre-R51).
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_interoceptive_feeling_engine.py -q
```
