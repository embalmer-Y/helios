# Requirement 80 - R80 Internal Monologue Source Owner

## 1. Background and Problem

R79-A / R79-B / R79-C / R79-D (all delivered) built the prompt-side aggressive-radical-no-theater
v3 path, channel catalog runtime injection + LLM arbitration, 5-HT / Oxy / Opioid appraisal drives,
and the v3 live-render framework.

All of them are **stimulus-driven** in the sense that they wait for an external input to fire:
a user message, a CLI event, a system signal. The runtime has no first-class notion of
**self-generated internal monologue** — a thought that the system already produced and that
re-enters the next tick as a stimulus to itself.

This is the rumination / self-talk loop that makes a system able to keep thinking about a topic
without new external input. Without it, the v3 path can *request* `i_want_to_think_more: true`
in the LLM output, but the runtime has nowhere to route that "I want to keep thinking" signal
back into itself as a stimulus on the next tick.

The `sensory` owner (02) only registers externally-provided sources today
(`FirstVersionSensorySource`, `RuntimeInteroceptiveSource` for runtime pressure). The
`appraisal` owner (03) maps each stimulus's content to five coarse dimensions (threat / reward /
novelty / social / uncertainty) via per-stimulus estimators. There is no path for a **second-order
stimulus** (a thought the system already had) to re-enter the sensory → appraisal → neuromodulation
pipeline.

## 2. Goal

R80 introduces a `InternalMonologueSource` sensory-source owner that emits the runtime's
self-produced internal-monologue content as a `RawSignal` (with `signal_type="internal_monologue"`)
on every tick, and a `InternalMonologueAppraisalEstimator` that maps that stimulus's
content to fixed coarse dimensions (novelty=0.3, uncertainty=0.7, social=0.0, threat=0.0,
reward=0.0), so the self-talk re-enters the `02 → 03 → 04` pipeline as a second-order
stimulus.

After R80, a `RuntimeProfile` that opts into the v3 path's `internal_monologue=True` will, on
every tick, surface a bounded `internal_monologue` `Stimulus` to the appraisal owner, which
will contribute novelty+uncertainty to the rapid-appraisal aggregate, which in turn drives
the norepinephrine channel of the `04` neuromodulator owner (via the existing
`AppraisalDerivedNeuromodulatorUpdatePath`).

## 3. Scope

### 3.1 In Scope

- `src/helios_v2/sensory/internal_monologue.py` — new `InternalMonologueSource` owner
  (one `@dataclass(frozen=True)` value class implementing `SensorySource` via
  `source_name` property + `emit_raw_signals()` method).
- `src/helios_v2/sensory/__init__.py` — export `InternalMonologueSource`.
- `src/helios_v2/appraisal/r80_internal_monologue.py` — new
  `InternalMonologueAppraisalEstimator` (one `@dataclass(frozen=True)` value class implementing
  `RapidDimensionEstimator` via `estimate_dimensions()` method, returning a constant
  `RapidDimensionEstimate(novelty=0.3, uncertainty=0.7, social=0.0, threat=0.0, reward=0.0)`).
- `src/helios_v2/appraisal/__init__.py` — export `InternalMonologueAppraisalEstimator`.
- `src/helios_v2/composition/runtime_assembly.py` — new opt-in kwarg
  `internal_monologue_carry_provider` on `assemble_runtime` (default `None`); when
  provided, register the `InternalMonologueSource` and route it through the appraisal
  pipeline via the existing `RapidSalienceAppraisalEngine` injection seam.
- `src/helios_v2/composition/profile.py` — new `RuntimeProfile` field
  `enable_internal_monologue_source: bool = False` and `assemble_runtime` profile consumer.
- `tests/test_r80_internal_monologue.py` — 5 unit tests:
  1. Source emits exactly one `RawSignal` with `signal_type="internal_monologue"` and
     `signal_id`/`source_name` provenance.
  2. `02` normalization preserves `signal_type` → `Stimulus.modality="internal_monologue"`.
  3. Estimator returns fixed dimensions (`novelty=0.3, uncertainty=0.7, social=0.0,
     threat=0.0, reward=0.0`).
  4. No-provider fallback: when no provider is injected, no source is registered
     (assembly is unchanged).
  5. End-to-end `assemble_runtime` integration: 1-tick run with a stub provider that
     returns `{"i_want_to_think_more": True, "think_more_about": "earlier topic"}` produces
     a `RapidAppraisalBatch` containing an `internal_monologue` appraisal with the
     fixed dimensions.
- `tests/r79d/framework.py` — R79-D framework extension: add `internal_monologue_carry_provider`
  scenario field; when present, the 20-tick A_praise run injects a stub provider that
  returns a rumination-shape dict on every tick.
- `logs/prompt_probe_scenarios/r80_baseline/` — 20-tick A_praise + rumination real-LLM run
  + analysis report.
- Documentation: OWNER_GUIDE, PROGRESS_FLOW, ARCHITECTURE_BOUNDARIES, index.md
  owner-row update for `02 sensory` and `03 appraisal`.
- R21 + composition-guard verification.

### 3.2 Out of Scope (R81+)

- **Runtime carry of internal monologue across ticks** (R81 T7):
  `RuntimeHandle._carry_internal_monologue` field, `assemble_runtime` seam extension,
  and the v3→v4 `RuntimeContinuitySnapshot` bump.
- **`09` thought gating `self_continuation_signal`** (R81 T7).
- **`18` autonomy `source_kind="internal_monologue"`** (R81 T7).
- **`aggregate_coupling_bias` producer→consumer wiring** (R79-C out-of-scope
  recommendation (b)).
- **Salience aggregator per-language sentiment upgrade** (R79-C out-of-scope
  recommendation (a)).
- **17-dim behavior drift evaluation** (R82).

## 4. Non-Goals

- R80 does **not** change the v3 aggressive-radical prompt contract; the LLM is not
  told about the source.
- R80 does **not** introduce a new neuromodulator drive formula; the existing
  `AppraisalDerivedNeuromodulatorUpdatePath` already drives norepinephrine from
  `novelty + uncertainty` and that's exactly the surface internal_monologue targets.
- R80 does **not** change `02 sensory` normalization semantics; `_normalize_signal` already
  preserves `signal_type` → `modality` verbatim (verified in T3 unit test).
- R80 does **not** change `assemble_runtime` default behavior; without an explicit
  `internal_monologue_carry_provider` kwarg, the assembly is bit-identical.

## 5. Acceptance Criteria

| # | Criterion | Measurable Test |
|---|-----------|-----------------|
| 1 | `InternalMonologueSource` exists, is exported, and implements `SensorySource` | `test_r80_internal_monologue_source_emits_internal_monologue_signal` |
| 2 | `02` normalization preserves `signal_type="internal_monologue"` → `Stimulus.modality="internal_monologue"` | `test_r80_internal_monologue_normalization_preserves_modality` |
| 3 | `InternalMonologueAppraisalEstimator` returns fixed dimensions | `test_r80_internal_monologue_appraisal_returns_fixed_dimensions` |
| 4 | No-provider fallback is bit-identical (no source registered) | `test_r80_internal_monologue_no_provider_no_source` |
| 5 | End-to-end assembly + 1-tick run produces a `RapidAppraisalBatch` containing an internal_monologue appraisal | `test_r80_internal_monologue_end_to_end_tick_produces_appraisal` |
| 6 | Full test suite green | `pytest tests/ -q --tb=no` returns 0 failed (modulo the 2 pre-existing perf-flake) |
| 7 | R21 + composition-guard green | `pytest tests/test_no_adhoc_logging_guard.py tests/test_composition_owner_boundary_guard.py -q` returns 5/5 passed |
| 8 | 20-tick A_praise + rumination probe shows `norepinephrine` cumulative drift `>= 0.10` | `logs/prompt_probe_scenarios/r80_baseline/reports/r80_20tick_norepinephrine_drift.md` |
| 9 | 20-tick A_praise probe LLM `i_want_to_think_more_freq` `> 0.3` (rumination LLM signal) | same report as #8 |
| 10 | Branch + commit on `aggressive-radical-persona-no-theater` | `git log --oneline` shows the new R80 commit |

### 5.1 Acceptance Criterion 8 — Design Correction

R79-parent task.md T6 originally wrote "5-HT / Cort 累计 drift `>= 0.10`" as the R80
acceptance. R79-C (delivered) implements 5-HT as `safety_social_to_serotonin * (1-threat) * social`
and cortisol as `threat_to_cortisol * threat` — both **gated on social/threat**, neither
gated on novelty/uncertainty. With `InternalMonologueAppraisalEstimator` returning
`social=0.0, threat=0.0` (per R79-parent T6), 5-HT and cortisol **cannot** drift from
the tonic baseline.

R80 therefore **corrects** the R80 acceptance to: **"norepinephrine 累计 drift `>= 0.10`"**
because norepinephrine's formula is `novelty_to_ne * novelty + uncertainty_to_ne * uncertainty`,
both of which are non-zero for the internal_monologue dimensions (novelty=0.3,
uncertainty=0.7). This is recorded in `task.md` acceptance table as the corrected
expectation.

## 6. Open Questions (Resolved Pre-Implementation)

- **Q1**: How does the source obtain the internal-monologue dict?  
  **A1**: The source receives an injected `monologue_provider: Callable[[], Mapping[str, object] | None]`.
  The provider is called once per `emit_raw_signals()` and may return `None` (no active
  monologue → empty tuple of signals), or a mapping. The provider is **not** wired to
  `RuntimeHandle._carry_internal_monologue` in R80; that seam is R81's responsibility
  (per R79-parent T7). R80's `assemble_runtime` accepts a `default_monologue_provider`
  for tests; production wiring is R81.

- **Q2**: What does the `RawSignal.content` look like?  
  **A2**: A bounded, deterministic projection: the JSON of the dict if non-empty, else
  empty (which is treated as `required=False` by `02` normalization, so the source
  contributes zero stimuli on idle ticks).

- **Q3**: Where does the appraisal pick up the `internal_monologue` appraisal?  
  **A3**: R80 adds the `InternalMonologueAppraisalEstimator` as a new dimension
  estimator in the `RapidSalienceAppraisalEngine` dimension-estimator dispatch. The
  dispatch is by `stimulus.modality`; the engine gains a new branch
  `if modality == "internal_monologue": return InternalMonologueAppraisalEstimator().estimate_dimensions(stimulus)`.
  This preserves the existing `GroundedDimensionEstimator` default and does not break
  the semantic-memory-driven path.

- **Q4**: Does R80 require a config / sensitivity change?  
  **A4**: No. The existing `NeuromodulatorConfig` and `AppraisalDerivedNeuromodulatorUpdatePath`
  weights already cover the `novelty + uncertainty` → norepinephrine path. R80 is a
  pure stimulus-source + appraisal-estimator addition.
