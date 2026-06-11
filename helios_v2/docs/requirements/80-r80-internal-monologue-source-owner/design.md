# Design 80 - R80 Internal Monologue Source Owner

## 1. Architecture Overview

R80 introduces a second-order stimulus path that closes the rumination / self-talk loop at
the **sensory ingress boundary** rather than at the LLM-prompt boundary. The LLM (v3 path)
emits `i_want_to_think_more: true` and `think_more_about: "..."` in its JSON output, but the
v3 prompt contract (R79-A) does not currently route that output back to a stimulus. R80
adds that routing via a new sensory source + a new appraisal estimator:

```
                                              R80 adds
                                              ────────
external stimulus ──► 02 sensory ingress ──► 03 appraisal ──► 04 neuromodulation
                              ▲                    ▲
                              │                    │
                              │                    └─ InternalMonologueAppraisalEstimator
                              │                       (novelty=0.3, uncertainty=0.7, social=0.0,
                              │                        threat=0.0, reward=0.0)
                              │
                              └─ InternalMonologueSource
                                 (monologue_provider() -> dict | None -> RawSignal tuple)
```

The `monologue_provider` is the single seam where R80 connects to the LLM's self-talk output.
R80 does **not** wire that provider to a real LLM output consumer (that is R81's
`_carry_internal_monologue` work). R80 ships a `default_monologue_provider` that returns
`None` (no active monologue) and a test helper `StaticMonologueProvider` for unit tests.

## 2. Module-by-Module Design

### 2.1 `src/helios_v2/sensory/internal_monologue.py`

```python
@dataclass(frozen=True)
class InternalMonologueSource:
    """Owner: sensory ingress — internal-monologue second-order stimulus source.

    Purpose:
        Emit the runtime's self-produced internal-monologue content as bounded
        `RawSignal`s into sensory ingress, closing the second-order stimulus path
        (the rumination / self-talk loop).

    Failure semantics:
        Propagates an outright `monologue_provider()` exception as a hard stop.
        A `None` return from the provider means "no active monologue" and the
        source emits an empty tuple (zero stimuli that tick).

    Notes:
        Owns only the provider-to-signal projection: at most one
        `signal_type="internal_monologue"` `RawSignal` per call, with provenance
        `source_name="internal_monologue"`. The numeric content rides metadata;
        the content string is a bounded JSON projection of the provider's dict.
        Holds no feeling, salience, or cognitive policy and imports no
        feeling / appraisal / neuromodulation owner.
    """

    monologue_provider: Callable[[], Mapping[str, object] | None]
    source_name_value: str = "internal_monologue"

    @property
    def source_name(self) -> str:
        return self.source_name_value

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        monologue = self.monologue_provider()
        if not monologue:
            return ()
        return (
            RawSignal(
                signal_id="internal_monologue:active",
                source_name=self.source_name_value,
                signal_type="internal_monologue",
                content=_bounded_json(monologue),
                channel="self_talk",
                metadata={"monologue_keys": tuple(sorted(monologue.keys()))},
                required=False,
            ),
        )
```

`_bounded_json` truncates the provider dict to a bounded JSON projection (max 1024 bytes)
and is a small private helper colocated in the same file.

### 2.2 `src/helios_v2/appraisal/r80_internal_monologue.py`

```python
@dataclass(frozen=True)
class InternalMonologueAppraisalEstimator:
    """Owner: rapid salience appraisal — internal-monologue dimension estimator.

    Purpose:
        Map an `internal_monologue` `Stimulus` to a fixed `RapidDimensionEstimate`
        regardless of content. The R80 design is that an active internal monologue
        is "familiar but not social, not threatening, mildly novel, mildly uncertain".

    Failure semantics:
        Stateless; no failure modes beyond `RapidDimensionEstimate` validation
        (which the dataclass `__post_init__` enforces).

    Notes:
        Owns the dimension mapping for `modality == "internal_monilogue"`. The
        dispatch happens in `RapidSalienceAppraisalEngine._estimate_dimensions`.
        Constants are explicitly hand-authored and documented in the requirement
        as the R80 starting anchor — a later P5 learning slice / R81 calibration
        slice can revise them.
    """

    novelty: float = 0.3
    uncertainty: float = 0.7
    social: float = 0.0
    threat: float = 0.0
    reward: float = 0.0

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        return RapidDimensionEstimate(
            threat=self.threat,
            reward=self.reward,
            novelty=self.novelty,
            social=self.social,
            uncertainty=self.uncertainty,
        )
```

### 2.3 `RapidSalienceAppraisalEngine` dispatch extension

`RapidSalienceAppraisalEngine._estimate_dimensions` (currently a private dispatch that
forwards to a single `RapidDimensionEstimator` injected at construction) gains a new
optional dependency `internal_monologue_estimator: InternalMonologueAppraisalEstimator | None`
and a new branch:

```python
def _estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
    if stimulus.modality == "internal_monologue" and self.internal_monologue_estimator is not None:
        return self.internal_monologue_estimator.estimate_dimensions(stimulus)
    return self.dimension_estimator.estimate_dimensions(stimulus)
```

This preserves the existing default estimator for non-internal-monologue stimuli and adds
a per-modality override for `internal_monologue`.

### 2.4 `assemble_runtime` integration

New opt-in kwarg on `assemble_runtime`:

```python
def assemble_runtime(
    ...,
    internal_monologue_carry_provider: Callable[[], Mapping[str, object] | None] | None = None,
    ...
) -> RuntimeHandle:
```

When `internal_monologue_carry_provider is not None`:
1. Construct `InternalMonologueSource(monologue_provider=internal_monologue_carry_provider)`.
2. Register it via `ingress.register_source(...)`.
3. Construct `InternalMonologueAppraisalEstimator()` and pass it to
   `RapidSalienceAppraisalEngine(...)` as `internal_monologue_estimator=...`.

The profile field `enable_internal_monologue_source: bool = False` (R80 #4.5 below) maps
to this kwarg: when `True`, the kwarg is set to a `default_monologue_provider` that
returns `None`. Production wiring (provider reads `RuntimeHandle._carry_internal_monologue`)
is R81's deliverable.

### 2.5 `RuntimeProfile` extension

```python
@dataclass
class RuntimeProfile:
    ...,
    enable_internal_monologue_source: bool = False
```

The `_loose` tuple dispatch in `assemble_runtime` gains a new branch
`(resolved_profile.enable_internal_monologue_source, "enable_internal_monologue_source")`.

## 3. Test Plan

### 3.1 Unit tests (`tests/test_r80_internal_monologue.py`, 5 cases)

1. `test_r80_internal_monologue_source_emits_internal_monologue_signal` —
   `InternalMonologueSource(provider=StaticMonologueProvider({"i_want_to_think_more": True})).emit_raw_signals()`
   returns a 1-tuple of `RawSignal` with `signal_type="internal_monologue"`,
   `source_name="internal_monologue"`, `signal_id="internal_monologue:active"`.
2. `test_r80_internal_monologue_normalization_preserves_modality` —
   When the source's signals are passed through `02 sensory _normalize_signal`,
   the resulting `Stimulus.modality == "internal_monologue"` and
   `provenance_signal_id == "internal_monologue:active"`.
3. `test_r80_internal_monologue_appraisal_returns_fixed_dimensions` —
   `InternalMonologueAppraisalEstimator().estimate_dimensions(stub_stimulus)` returns
   `RapidDimensionEstimate(threat=0.0, reward=0.0, novelty=0.3, social=0.0, uncertainty=0.7)`.
4. `test_r80_internal_monologue_no_provider_no_source` —
   `assemble_runtime(...)` without `internal_monologue_carry_provider` is bit-identical:
   `handle.ingress.sources` does not contain `"internal_monologue"`.
5. `test_r80_internal_monologue_end_to_end_tick_produces_appraisal` —
   `assemble_runtime(..., internal_monologue_carry_provider=StaticMonologueProvider({"i_want_to_think_more": True}))`
   + `handle.tick(...)` produces a `RapidAppraisalBatch` containing an `internal_monologue`
   appraisal with the fixed dimensions.

### 3.2 R79-D framework extension (`tests/r79d/framework.py`)

Add a new optional kwarg `internal_monologue_carry_provider: Callable | None = None` to
`run_experiment`. When present, the framework's `inject_v3_prompt` closure captures the
provider and the `run_experiment` main loop calls it before each tick. The default
`RumintationMonologueProvider` (R80 fixture) returns `{"i_want_to_think_more": True,
"think_more_about": "the last user message", "internal_topics": ("<last LLM think_more_about>",)}`
whenever the previous tick's LLM output had `i_want_to_think_more: true`, else `None`.

### 3.3 20-tick probe (`logs/prompt_probe_scenarios/r80_baseline/`)

`python3 -m tests.r79d.framework run_r80_baseline_20tick_A_praise_with_rumination`:
- Scenario: A_praise loop, but with the rumination monologue provider.
- 20 ticks, real LLM.
- Analysis report at `reports/r80_20tick_norepinephrine_drift.md`:
  - Norepinephrine cumulative drift from tick 0 baseline (≥ 0.10 expected).
  - `i_want_to_think_more_freq` in the LLM output (≥ 0.3 expected).
  - Per-tick `internal_monologue` appraisal presence.

## 4. Doc Sync Plan

- `docs/OWNER_GUIDE.md` — append a one-line note under the `02 sensory` row:
  "Internal monologue (second-order self-talk) stimuli: `InternalMonologueSource` (R80)."
- `docs/OWNER_GUIDE.md` — append a one-line note under the `03 appraisal` row:
  "Internal monologue fixed-dimension estimator: `InternalMonologueAppraisalEstimator` (R80)."
- `docs/PROGRESS_FLOW.md` — `04` row gains one bullet: "R80 — internal_monologue path
  contributes novelty+uncertainty to rapid appraisal → norepinephrine (via existing
  `AppraisalDerivedNeuromodulatorUpdatePath`)."
- `docs/ARCHITECTURE_BOUNDARIES.md` — `02 sensory` boundary gains: "May register
  `InternalMonologueSource` (R80) when the runtime opts into the self-talk loop. The
  source holds no feeling, salience, or cognitive policy."
- `docs/requirements/index.md` — add the R80 row to the requirements index table.

## 5. Migration Plan

No migration. R80 is additive and opt-in via the new kwarg and `RuntimeProfile` field.
Default behavior (no kwarg / `enable_internal_monologue_source=False`) is bit-identical.

## 6. Risk Assessment

- **Risk 1**: The `RapidSalienceAppraisalEngine._estimate_dimensions` dispatch
  extension breaks the existing path. **Mitigation**: New branch only fires for
  `stimulus.modality == "internal_monilogue"`; all other stimuli continue to use
  `self.dimension_estimator`. Tested in T1 and T5.
- **Risk 2**: The 20-tick probe fails the "norepinephrine drift ≥ 0.10" acceptance
  if the rumination provider fires too rarely. **Mitigation**: The fixture
  `RumintationMonologueProvider` always returns a non-`None` dict on every tick where
  the previous LLM output had `i_want_to_think_more: true`; in the A_praise scenario
  this is expected to fire often (rumination shape), so norepinephrine should drift
  upward. The T7 probe is real-LLM, so a real probe failure is a real signal —
  documented as acceptance-failed-not-implementation-broken.

## 7. Owner-Governance Cross-Checks

- `02 sensory` boundary: R80 only adds a new source, doesn't change normalization.
  Verified by `test_r80_internal_monologue_normalization_preserves_modality`.
- `03 appraisal` boundary: R80 only adds a new per-modality estimator dispatch,
  doesn't change the existing dispatch. Verified by all 5 unit tests + the existing
  22 appraisal tests still passing.
- `04 neuromodulation` boundary: R80 doesn't change `04`'s drives; it relies on the
  existing `novelty+uncertainty` → norepinephrine path. Verified by the existing
  9 neuromodulation tests + the new T7 probe.
- `09 thought_gating` and `18 autonomy` boundaries: untouched by R80. R81's scope.
- Composition-guard: the new `InternalMonologueSource` lives in `helios_v2.sensory`,
  `InternalMonologueAppraisalEstimator` lives in `helios_v2.appraisal`,
  `assemble_runtime` integration lives in `helios_v2.composition`. No cross-owner
  imports added. Verified by `test_composition_owner_boundary_guard.py`.
- R21 (no ad-hoc logging): R80 uses no `print()` or `import logging` in product
  code. Verified by `test_no_adhoc_logging_guard.py`.
