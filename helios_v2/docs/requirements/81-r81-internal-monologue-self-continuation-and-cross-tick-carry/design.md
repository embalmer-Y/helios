# Design 81 - R81 Internal Monologue Self-Continuation and Cross-Tick Carry

## 1. Architecture Overview

R81 extends the R80 second-order stimulus loop into a **self-continuation** loop. The
runtime is reorganized as a 4-step feedback chain that already exists in pieces (R49 +
R52 + R62 + R80) and is now closed by R81:

```
┌──────────┐  prompt   ┌────────┐  envelope  ┌─────────────────┐
│  02 → 03 │ ────────→ │  LLM   │ ─────────→ │ _carry_internal │
│  → 04    │           │  v3    │            │   _monologue   │
└──────────┘           └────────┘            └────────┬────────┘
       ▲                                            │
       │  re-inject                                 │  self_continuation
       │  prior envelope                            │  signal
       └────────────────────────────────────────────┘
```

The four R81 sub-deliverables (carry, gate signal, autonomy source_kind, snapshot v4)
are the four walls of this loop closure.

## 2. Component Design

### 2.1 `InternalMonologueCarryState` Contract (new in `42`)

```python
@dataclass(frozen=True)
class InternalMonologueCarryState:
    """One immutable snapshot of the LLM envelope carried across ticks.

    Owner: 42 continuity_checkpoint (lives in the snapshot module, not in
    22 composition, because the envelope persists in the checkpoint file).

    Construction:
        - last_envelope is the verbatim subset of the LLM JSON envelope
          produced by the v3 prompt path. May be None (v1 baseline) or a
          Mapping (v3 baseline).
        - last_tick_id is the tick_id when last_envelope was captured. None
          if no envelope has been captured yet.
        - i_want_to_think_more is a convenience projection of
          last_envelope["i_want_to_think_more"] (default False).
        - think_more_about is a convenience projection of
          last_envelope["think_more_about"] (default "").

    Failure semantics:
        - last_envelope must be a Mapping[str, object] or None. Any other
          type (str, int, list, etc.) raises CheckpointError.
        - i_want_to_think_more and think_more_about are coerced from
          last_envelope: missing key or wrong type -> False / "".
          These coercions do NOT raise.
        - The seam in 22 composition that writes the carry validates
          the envelope shape (must be a Mapping with only allowed v3 keys).
          This keeps the contract minimal and the seam's fail-fast localized.
    """

    last_envelope: Mapping[str, object] | None
    last_tick_id: int | None
    i_want_to_think_more: bool
    think_more_about: str

    def __post_init__(self) -> None:
        if self.last_envelope is not None and not isinstance(self.last_envelope, Mapping):
            raise CheckpointError(
                "InternalMonologueCarryState.last_envelope must be a Mapping or None; "
                f"got {type(self.last_envelope).__name__}"
            )
        if self.last_tick_id is not None and self.last_tick_id < 0:
            raise CheckpointError(
                "InternalMonologueCarryState.last_tick_id must be >= 0 or None"
            )
```

### 2.2 `RuntimeHandle._carry_internal_monologue` Seam (in `22`)

```python
# helios_v2.composition.runtime_assembly
def _carry_internal_monologue(self, result: RuntimeTickResult) -> None:
    """Capture the current tick's LLM envelope as the next tick's carry.

    Reads from result.stage_results["internal_thought_path"] or the v3
    prompt path's post-LLM envelope storage. Validates the envelope shape
    and raises CompositionError on invalid input.

    After the seam runs, self._internal_monologue_carry is set to a new
    InternalMonologueCarryState (or remains None if no envelope was emitted).
    """
```

**Carry capture source**: the v3 prompt path `AggressiveRadicalEmbodiedPromptPath`
publishes its parsed JSON envelope into `result.stage_results["internal_thought_path"].state.last_envelope`
(or a similar owner-owned location — TBD in T1 implementation, but the seam's contract
is: "if a post-LLM envelope is present in the result, capture it; otherwise leave the
carry unchanged").

**Validation**: only the keys `what_i_think` / `i_want_to_say` / `i_send_through` /
`i_want_to_think_more` / `think_more_about` / `i_want_to_act` / `act_type` /
`remember_this` / `remember_because` are allowed (the v3 schema's 11 fields minus the
3 visual / temporal ones we don't carry). Any other key raises `CompositionError` with
a precise message.

**Read site**: the `02` `SensoryIngress._resolve_internal_monologue_source` step
(in `helios_v2.sensory.ingress`, new method) reads
`self._internal_monologue_carry` (exposed via `assemble_runtime` or a new
`handle.ingress_resolve_carry` method) and constructs a `RawSignal` whose JSON projection
is the prior envelope (if non-empty).

### 2.3 `09` `ThoughtGateSignalSnapshot.self_continuation_signal` (additive field)

```python
@dataclass(frozen=True)
class ThoughtGateSignalSnapshot:
    # ... existing 11 fields ...
    self_continuation_signal: float = 0.0  # NEW, added at bottom

    def __post_init__(self) -> None:
        # ... existing 5 validations ...
        _validate_unit_interval(
            "ThoughtGateSignalSnapshot.self_continuation_signal",
            self.self_continuation_signal,
        )  # NEW
```

**`09` policy integration**: `evaluate_thought_gate` reads the new field and adds
`policy.self_continuation_weight * self_continuation_signal` to the selection_pressure
before applying the threshold. The weight is on `ThoughtGateConfig`:

```python
@dataclass(frozen=True)
class ThoughtGateConfig:
    # ... existing fields ...
    self_continuation_weight: float = 0.3  # NEW
```

**Reset semantics**: the carry seam (`_carry_internal_monologue`) decides when to reset
the carry. The reset rule: after a successful `evaluate_thought_gate` fire where
`prior_self_continuation_signal > 0`, the carry is reset to `None` (the prior envelope
has been consumed). After a no-fire, the carry persists (and `self_continuation_signal`
is carried over). This is the R81 emulation of "越想越气" (rumination), encoded as
**carry persistence on no-fire**.

### 2.4 `18` `DeferredContinuityRecord.source_kind` (additive Literal field)

```python
@dataclass(frozen=True)
class DeferredContinuityRecord:
    # ... existing 7 fields ...
    source_kind: Literal[
        "external_stimulus", "retrieval", "internal_monologue"
    ] = "external_stimulus"  # NEW

    def __post_init__(self) -> None:
        # ... existing 7 validations ...
        if self.source_kind not in (
            "external_stimulus", "retrieval", "internal_monologue"
        ):
            raise AutonomyError(
                f"DeferredContinuityRecord.source_kind must be one of "
                f"'external_stimulus', 'retrieval', 'internal_monologue'; "
                f"got {self.source_kind!r}"
            )
```

**`proactive_drive_urgency` multiplier** in the `18` engine:

```python
SOURCE_KIND_URGENCY_MULTIPLIER = {
    "external_stimulus": 1.0,
    "retrieval": 0.8,
    "internal_monologue": 0.5,
}
```

**New emit site**: the `internal_monologue_carry` path emits a `DeferredContinuityRecord`
with `source_kind="internal_monologue"` when the carry persists across a no-fire tick.
This is the `18`-side counterpart of the `09` self-continuation signal.

### 2.5 `42` `RuntimeContinuitySnapshot` v4 Schema

```python
SNAPSHOT_VERSION = 4  # bumped from 3

@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    tick_id: int | None
    continuation_state: ContinuationPressureState
    deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    continuity_threads: tuple[ContinuityThread, ...] = ()
    neuromodulator_levels: NeuromodulatorLevels | None = None
    feeling: InteroceptiveFeelingVector | None = None
    snapshot_version: int = SNAPSHOT_VERSION
    internal_monologue: InternalMonologueCarryState | None = None  # NEW
```

**v3 → v4 migration** (`_migrate_v3_to_v4`):

```python
def _migrate_v3_to_v4(snapshot: RuntimeContinuitySnapshot) -> RuntimeContinuitySnapshot:
    """Migrate a v3 snapshot to v4 by setting internal_monologue=None."""
    if snapshot.snapshot_version == 4:
        return snapshot
    if snapshot.snapshot_version == 3:
        return replace(
            snapshot,
            internal_monologue=None,
            snapshot_version=4,
        )
    raise CheckpointError(
        f"Cannot migrate v{snapshot.snapshot_version} to v4"
    )
```

**Load-time warning**: `CheckpointStoreBackend.load_latest()` calls `_migrate_v3_to_v4`
on the loaded snapshot and emits a one-shot `CheckpointMigrationWarning` via the `21`
observability owner (using the existing warning channel, not a print or stdlib logger).

## 3. Test Design

### 3.1 Unit tests (8)

| # | Test | What it asserts |
|---|---|---|
| 1 | `test_carry_seam_writes_envelope_verbatim` | `_carry_internal_monologue` writes the LLM envelope into `_internal_monologue_carry.last_envelope` byte-for-byte. |
| 2 | `test_carry_seam_survives_across_ticks` | 3-tick harness; carry on tick 2 = tick 1's envelope, carry on tick 3 = tick 2's envelope. |
| 3 | `test_carry_seam_validates_envelope_keys` | Unknown key in envelope raises `CompositionError`. |
| 4 | `test_gate_signal_field_validates_unit_interval` | `self_continuation_signal` outside `[0, 1]` raises `ThoughtGatingError`. |
| 5 | `test_evaluate_thought_gate_reads_self_continuation` | `evaluate_thought_gate(signal_with_self_continuation=0.8, weight=0.3)` raises `selection_pressure` by `0.24`. |
| 6 | `test_deferred_record_source_kind_literal` | `source_kind="invalid"` raises `AutonomyError`. |
| 7 | `test_proactive_drive_urgency_internal_monologue_multiplier` | `compute_drive_urgency(record(source_kind="internal_monologue"))` returns `0.5x` the default. |
| 8 | `test_snapshot_v4_with_internal_monologue` | `RuntimeContinuitySnapshot(internal_monologue=InternalMonologueCarryState(...))` passes `__post_init__`. |

### 3.2 E2E cross-tick harness (1)

`tests/test_r81_internal_monologue_cross_tick_e2e.py`:

```python
def test_cross_tick_carry_reaches_02_and_09():
    """A 3-tick cycle asserts:
    - Tick 1: provider supplies envelope with i_want_to_think_more=True.
    - Tick 2: 02 ingestion includes the prior envelope; 09 GateSignal has
      self_continuation_signal >= 0.5 (per requirement §3.2 formula: 0.5 * 1.0 + 0.5 * 0.0).
    - Tick 3: after a fire on tick 2, the carry is reset; GateSignal has
      self_continuation_signal == 0.
    """
```

### 3.3 20-tick real-LLM probe (1)

`helios_v2.tests.r79d.r81_carry_probe`:

- Reuse the R79-D framework's A_praise + rumination fixture.
- Add a 20-tick `RealLlmGateway` run with the R81 profile enabled.
- Assert:
  - Carry envelope is non-empty on ticks 2..20 (`self.last_envelope is not None`).
  - `self_continuation_signal` correlates with `i_want_to_think_more` (Pearson r > 0.5).
  - The LLM emits a self-talk continuation on at least 50% of no-fire ticks.
- Save the JSONL + report to `logs/prompt_probe_scenarios/r81_carry/r81_20tick.{jsonl,report.md}`.

## 4. Migration & Backward Compat

- **No silent migration**: v3 → v4 is explicit at load-time, with a one-shot
  `CheckpointMigrationWarning` emitted via the `21` observability owner.
- **Default bit-identical assembly**: `assemble_runtime()` without R81-specific kwargs
  produces a runtime whose `_internal_monologue_carry` is `None`,
  `ThoughtGateSignalSnapshot.self_continuation_signal` is `0.0`, and
  `DeferredContinuityRecord.source_kind` is `"external_stimulus"`.
- **Composition owner-boundary guard**: the new `02` re-injection is owner-neutral glue;
  no new owner import is added in the carry seam.

## 5. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `02` re-injection might double-count the LLM envelope (R80 already has a provider lambda) | The `02` resolution step prefers the carry over the provider; the provider is only consulted when the carry is `None`. |
| `09` `self_continuation_weight = 0.3` might over-fire | The weight is a config-time constant; R82 drift evaluator will measure fire rate and feed back. |
| `18` `source_kind="internal_monologue"` urgency multiplier (0.5) might be too low | The multiplier is configurable via `18` policy; R82 will measure carry→fire rate. |
| v3 → v4 migration might lose data | Migration is additive (`internal_monologue=None`); the v3 fields are preserved verbatim. |
| `_carry_internal_monologue` runs even when no envelope is emitted | The seam is no-op when `result.stage_results["internal_thought_path"]` has no `last_envelope`. |
